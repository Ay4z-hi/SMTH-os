//! Persistent user settings with atomic writes.
//!
//! Replaces the previous behaviour of sprinkling flag files around
//! `~/.config/smth` (a boolean existed only as the presence of a file), which
//! could not be read back safely, migrated or validated.

use serde::{Deserialize, Serialize};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

pub const SCHEMA_VERSION: u32 = 1;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LayoutMode {
    Auto,
    Desktop,
    Mobile,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LockMethod {
    None,
    Pin,
    Pattern,
    Password,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Settings {
    pub schema: u32,
    pub layout: LayoutMode,
    pub reduce_motion: bool,
    pub ahian: bool,
    pub wallpaper: Option<String>,
    pub lock: LockMethod,
    /// Hash produced by `smth-lock set`; the plain secret is never stored.
    pub lock_secret_hash: Option<String>,
    pub timezone: String,
}

impl Default for Settings {
    fn default() -> Self {
        Settings {
            schema: SCHEMA_VERSION,
            layout: LayoutMode::Auto,
            reduce_motion: false,
            ahian: false,
            wallpaper: None,
            lock: LockMethod::None,
            lock_secret_hash: None,
            timezone: "UTC".into(),
        }
    }
}

#[derive(Debug)]
pub enum SettingsError {
    Io(io::Error),
    Json(String),
    UnsupportedSchema(u32),
    Invalid(String),
}

impl std::fmt::Display for SettingsError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SettingsError::Io(e) => write!(f, "settings io error: {e}"),
            SettingsError::Json(e) => write!(f, "settings file is corrupt: {e}"),
            SettingsError::UnsupportedSchema(v) => write!(f, "unsupported settings schema {v}"),
            SettingsError::Invalid(m) => write!(f, "invalid setting: {m}"),
        }
    }
}

impl std::error::Error for SettingsError {}

impl From<io::Error> for SettingsError {
    fn from(e: io::Error) -> Self {
        SettingsError::Io(e)
    }
}

impl Settings {
    pub fn load(path: &Path) -> Result<Settings, SettingsError> {
        let text = fs::read_to_string(path)?;
        let settings: Settings =
            serde_json::from_str(&text).map_err(|e| SettingsError::Json(e.to_string()))?;
        if settings.schema > SCHEMA_VERSION {
            return Err(SettingsError::UnsupportedSchema(settings.schema));
        }
        // Schema 0 files predate the field; adopt the current version.
        let mut settings = settings;
        if settings.schema < SCHEMA_VERSION {
            settings.schema = SCHEMA_VERSION;
        }
        settings.validate()?;
        Ok(settings)
    }

    /// Load, or fall back to defaults when the file is missing. A corrupt file
    /// is reported as an error so the caller can warn instead of silently
    /// discarding the user's configuration.
    pub fn load_or_default(path: &Path) -> Result<Settings, SettingsError> {
        match Settings::load(path) {
            Ok(s) => Ok(s),
            Err(SettingsError::Io(e)) if e.kind() == io::ErrorKind::NotFound => {
                Ok(Settings::default())
            }
            Err(e) => Err(e),
        }
    }

    pub fn validate(&self) -> Result<(), SettingsError> {
        if self.timezone.trim().is_empty() {
            return Err(SettingsError::Invalid("timezone is empty".into()));
        }
        if self.lock_secret_hash.as_ref().is_some_and(|h| h.len() < 16) {
            return Err(SettingsError::Invalid("lock hash looks truncated".into()));
        }
        if self.wallpaper.as_ref().is_some_and(|w| !w.starts_with('/')) {
            return Err(SettingsError::Invalid(
                "wallpaper must be an absolute path".into(),
            ));
        }
        Ok(())
    }

    /// Write through a temporary file in the same directory, then rename. A
    /// crash mid-write therefore leaves the previous settings intact.
    pub fn save(&self, path: &Path) -> Result<(), SettingsError> {
        self.validate()?;
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let tmp: PathBuf = path.with_extension(format!("tmp-{}", std::process::id()));
        let json =
            serde_json::to_string_pretty(self).map_err(|e| SettingsError::Json(e.to_string()))?;
        fs::write(&tmp, json + "\n")?;
        // fsync the file so the rename below cannot publish zero bytes.
        if let Ok(file) = fs::File::open(&tmp) {
            let _ = file.sync_all();
        }
        fs::rename(&tmp, path)?;
        Ok(())
    }

    pub fn set_ahian(&mut self, on: bool) {
        self.ahian = on;
    }

    pub fn set_wallpaper(&mut self, path: Option<&Path>) -> Result<(), SettingsError> {
        match path {
            Some(p) if !p.is_absolute() => {
                Err(SettingsError::Invalid("wallpaper must be absolute".into()))
            }
            Some(p) => {
                self.wallpaper = Some(p.to_string_lossy().to_string());
                Ok(())
            }
            None => {
                self.wallpaper = None;
                Ok(())
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU32, Ordering};

    fn temp_path(tag: &str) -> PathBuf {
        static N: AtomicU32 = AtomicU32::new(0);
        let n = N.fetch_add(1, Ordering::SeqCst);
        std::env::temp_dir().join(format!(
            "smth-settings-{}-{tag}-{n}.json",
            std::process::id()
        ))
    }

    #[test]
    fn defaults_when_missing() {
        let s = Settings::load_or_default(&temp_path("missing")).unwrap();
        assert_eq!(s, Settings::default());
        assert_eq!(s.schema, SCHEMA_VERSION);
        assert_eq!(s.layout, LayoutMode::Auto);
        assert!(!s.ahian);
    }

    #[test]
    fn roundtrip_and_atomic_write() {
        let path = temp_path("roundtrip");
        let mut s = Settings {
            layout: LayoutMode::Mobile,
            reduce_motion: true,
            ..Default::default()
        };
        s.set_ahian(true);
        s.lock = LockMethod::Pin;
        s.lock_secret_hash = Some("a".repeat(64));
        s.set_wallpaper(Some(Path::new("/usr/share/backgrounds/smth/eclipse.png")))
            .unwrap();
        s.save(&path).unwrap();
        assert_eq!(Settings::load(&path).unwrap(), s);
        // No temporary files left behind.
        let dir = path.parent().unwrap();
        let leftovers: Vec<_> = fs::read_dir(dir)
            .unwrap()
            .filter_map(|e| e.ok())
            .filter(|e| {
                e.file_name().to_string_lossy().contains("tmp-") && e.path().parent() == Some(dir)
            })
            .collect();
        // The directory is shared, so only assert that this exact temp name is gone.
        assert!(!path
            .with_extension(format!("tmp-{}", std::process::id()))
            .exists());
        let _ = leftovers;
        fs::remove_file(&path).ok();
    }

    #[test]
    fn corrupt_and_unknown_files_are_handled() {
        let corrupt = temp_path("corrupt");
        fs::write(&corrupt, b"{oops").unwrap();
        assert!(matches!(
            Settings::load(&corrupt),
            Err(SettingsError::Json(_))
        ));
        assert!(matches!(
            Settings::load_or_default(&corrupt),
            Err(SettingsError::Json(_))
        ));

        let future = temp_path("future");
        fs::write(&future, format!("{{\"schema\":{}}}", SCHEMA_VERSION + 1)).unwrap();
        assert!(matches!(
            Settings::load(&future),
            Err(SettingsError::UnsupportedSchema(_))
        ));

        let tolerant = temp_path("extra");
        fs::write(
            &tolerant,
            b"{\"schema\":1,\"something_new\":\"ignored\",\"ahian\":true}",
        )
        .unwrap();
        let s = Settings::load(&tolerant).unwrap();
        assert!(s.ahian);
        assert_eq!(s.layout, LayoutMode::Auto);

        for p in [corrupt, future, tolerant] {
            fs::remove_file(p).ok();
        }
    }

    #[test]
    fn validation_rejects_bad_values() {
        let s = Settings {
            timezone: "  ".into(),
            ..Default::default()
        };
        assert!(s.validate().is_err());
        let s = Settings {
            wallpaper: Some("relative.png".into()),
            ..Default::default()
        };
        assert!(s.validate().is_err());
        let mut s = Settings::default();
        assert!(s.set_wallpaper(Some(Path::new("relative.png"))).is_err());
        s.lock_secret_hash = Some("short".into());
        assert!(s.validate().is_err());
    }
}
