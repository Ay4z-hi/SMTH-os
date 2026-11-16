//! File-manager backend: the operations that must be correct.
//!
//! The GTK file manager shells out to `smthd` for destructive operations so a
//! single tested implementation decides collision names, path traversal rules
//! and trash metadata.

use std::fs;
use std::io;
use std::path::{Component, Path, PathBuf};

#[derive(Debug)]
pub enum FsError {
    Io { path: PathBuf, source: io::Error },
    Invalid(String),
    NotFound(PathBuf),
}

impl std::fmt::Display for FsError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FsError::Io { path, source } => write!(f, "{}: {source}", path.display()),
            FsError::Invalid(m) => write!(f, "invalid request: {m}"),
            FsError::NotFound(p) => write!(f, "not found: {}", p.display()),
        }
    }
}

impl std::error::Error for FsError {}

fn io_at(path: &Path, source: io::Error) -> FsError {
    FsError::Io {
        path: path.to_path_buf(),
        source,
    }
}

/// Resolve a user-supplied relative path beneath `root`, rejecting anything
/// that could escape it (`..`, absolute paths, Windows prefixes).
pub fn safe_join(root: &Path, relative: &str) -> Result<PathBuf, FsError> {
    if relative.trim().is_empty() {
        return Err(FsError::Invalid("empty path".into()));
    }
    let candidate = Path::new(relative);
    let mut out = PathBuf::from(root);
    for component in candidate.components() {
        match component {
            Component::Normal(part) => {
                let part = part.to_string_lossy();
                if part.contains('\0') {
                    return Err(FsError::Invalid("path contains NUL".into()));
                }
                out.push(part.as_ref());
            }
            Component::CurDir => {}
            Component::ParentDir => return Err(FsError::Invalid("path traversal blocked".into())),
            Component::RootDir | Component::Prefix(_) => {
                return Err(FsError::Invalid("absolute paths are not allowed".into()))
            }
        }
    }
    if out == root {
        return Err(FsError::Invalid("path resolves to the root".into()));
    }
    Ok(out)
}

/// `name`, then `name (2)`, `name (3)` … until the path is free.
pub fn unique_path(dir: &Path, name: &str) -> PathBuf {
    let first = dir.join(name);
    if !first.exists() {
        return first;
    }
    let path = Path::new(name);
    let stem = path
        .file_stem()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| name.into());
    let ext = path.extension().map(|e| e.to_string_lossy().to_string());
    for n in 2..10_000 {
        let candidate = match &ext {
            Some(ext) => dir.join(format!("{stem} ({n}).{ext}")),
            None => dir.join(format!("{stem} ({n})")),
        };
        if !candidate.exists() {
            return candidate;
        }
    }
    dir.join(format!("{stem}-{}", std::process::id()))
}

fn copy_recursive(src: &Path, dst: &Path) -> Result<(), FsError> {
    let meta = fs::symlink_metadata(src).map_err(|e| io_at(src, e))?;
    if meta.file_type().is_symlink() {
        let target = fs::read_link(src).map_err(|e| io_at(src, e))?;
        #[cfg(unix)]
        std::os::unix::fs::symlink(target, dst).map_err(|e| io_at(dst, e))?;
        #[cfg(not(unix))]
        {
            let _ = target;
            return Err(FsError::Invalid(
                "symlinks are not supported on this platform".into(),
            ));
        }
    } else if meta.is_dir() {
        fs::create_dir_all(dst).map_err(|e| io_at(dst, e))?;
        for entry in fs::read_dir(src).map_err(|e| io_at(src, e))? {
            let entry = entry.map_err(|e| io_at(src, e))?;
            copy_recursive(&entry.path(), &dst.join(entry.file_name()))?;
        }
        fs::set_permissions(dst, meta.permissions()).map_err(|e| io_at(dst, e))?;
    } else {
        fs::copy(src, dst).map_err(|e| io_at(src, e))?;
    }
    Ok(())
}

/// Copy `src` into `dest_dir`, never overwriting: the returned path is unique.
pub fn copy_into(src: &Path, dest_dir: &Path) -> Result<PathBuf, FsError> {
    if !src.exists() {
        return Err(FsError::NotFound(src.to_path_buf()));
    }
    let name = src
        .file_name()
        .ok_or_else(|| FsError::Invalid("source has no file name".into()))?
        .to_string_lossy()
        .to_string();
    fs::create_dir_all(dest_dir).map_err(|e| io_at(dest_dir, e))?;
    let dest = unique_path(dest_dir, &name);
    copy_recursive(src, &dest)?;
    Ok(dest)
}

/// Move `src` into `dest_dir` without overwriting.
pub fn move_into(src: &Path, dest_dir: &Path) -> Result<PathBuf, FsError> {
    if !src.exists() {
        return Err(FsError::NotFound(src.to_path_buf()));
    }
    let name = src
        .file_name()
        .ok_or_else(|| FsError::Invalid("source has no file name".into()))?
        .to_string_lossy()
        .to_string();
    fs::create_dir_all(dest_dir).map_err(|e| io_at(dest_dir, e))?;
    let dest = unique_path(dest_dir, &name);
    match fs::rename(src, &dest) {
        Ok(()) => Ok(dest),
        Err(e) if e.raw_os_error() == Some(18) => {
            // EXDEV: different filesystems, fall back to copy + remove.
            copy_recursive(src, &dest)?;
            remove(src)?;
            Ok(dest)
        }
        Err(e) => Err(io_at(src, e)),
    }
}

/// Rename inside the same directory, rejecting empty names and separators.
pub fn rename_within(path: &Path, new_name: &str) -> Result<PathBuf, FsError> {
    let new_name = new_name.trim();
    if new_name.is_empty() || new_name.contains('/') || new_name.contains('\0') {
        return Err(FsError::Invalid("invalid file name".into()));
    }
    let parent = path
        .parent()
        .ok_or_else(|| FsError::Invalid("path has no parent".into()))?;
    let dest = parent.join(new_name);
    if dest.exists() && dest != path {
        return Err(FsError::Invalid(
            "a file with that name already exists".into(),
        ));
    }
    fs::rename(path, &dest).map_err(|e| io_at(path, e))?;
    Ok(dest)
}

/// Create a directory, choosing a unique name when `name` already exists.
pub fn create_dir(dir: &Path, name: &str) -> Result<PathBuf, FsError> {
    let name = name.trim();
    if name.is_empty() || name.contains('/') || name == "." || name == ".." {
        return Err(FsError::Invalid("invalid folder name".into()));
    }
    let dest = unique_path(dir, name);
    fs::create_dir(&dest).map_err(|e| io_at(&dest, e))?;
    Ok(dest)
}

/// Remove a file, symlink or directory tree.
pub fn remove(path: &Path) -> Result<(), FsError> {
    let meta = fs::symlink_metadata(path).map_err(|e| io_at(path, e))?;
    if meta.is_dir() && !meta.file_type().is_symlink() {
        fs::remove_dir_all(path).map_err(|e| io_at(path, e))
    } else {
        fs::remove_file(path).map_err(|e| io_at(path, e))
    }
}

/// Per-user trash root (`$XDG_DATA_HOME/Trash`, falling back to
/// `~/.local/share/Trash`).
pub fn trash_root(home: &Path, xdg_data_home: Option<&Path>) -> PathBuf {
    xdg_data_home.unwrap_or(home).join("Trash")
}

/// Move `path` into the trash and write freedesktop-compliant metadata.
pub fn trash(path: &Path, trash_root: &Path) -> Result<PathBuf, FsError> {
    if !path.exists() && fs::symlink_metadata(path).is_err() {
        return Err(FsError::NotFound(path.to_path_buf()));
    }
    let files = trash_root.join("files");
    let info = trash_root.join("info");
    fs::create_dir_all(&files).map_err(|e| io_at(&files, e))?;
    fs::create_dir_all(&info).map_err(|e| io_at(&info, e))?;
    let name = path
        .file_name()
        .ok_or_else(|| FsError::Invalid("cannot trash a filesystem root".into()))?
        .to_string_lossy()
        .to_string();
    let dest = unique_path(&files, &name);
    let dest_name = dest.file_name().unwrap().to_string_lossy().to_string();
    let deletion_date = chrono_like_now();
    let absolute = fs::canonicalize(path).unwrap_or_else(|_| path.to_path_buf());
    let metadata = format!(
        "[Trash Info]\nPath={}\nDeletionDate={}\n",
        absolute.display(),
        deletion_date
    );
    fs::write(info.join(format!("{dest_name}.trashinfo")), metadata)
        .map_err(|e| io_at(&info, e))?;
    match fs::rename(path, &dest) {
        Ok(()) => Ok(dest),
        Err(_) => {
            copy_recursive(path, &dest)?;
            remove(path)?;
            Ok(dest)
        }
    }
}

/// `YYYY-MM-DDThh:mm:ss` without pulling a date crate into the ISO.
fn chrono_like_now() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let days = secs / 86_400;
    let rem = secs % 86_400;
    let (h, m, s) = (rem / 3600, (rem % 3600) / 60, rem % 60);
    // Civil-from-days (Howard Hinnant) — UTC only, which is what Trash Info wants.
    let z = days as i64 + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = if month <= 2 { y + 1 } else { y };
    format!("{year:04}-{month:02}-{d:02}T{h:02}:{m:02}:{s:02}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU32, Ordering};

    struct TempDir(PathBuf);
    static COUNTER: AtomicU32 = AtomicU32::new(0);

    impl TempDir {
        fn new(tag: &str) -> TempDir {
            let n = COUNTER.fetch_add(1, Ordering::SeqCst);
            let path =
                std::env::temp_dir().join(format!("smth-fsops-{}-{tag}-{n}", std::process::id()));
            let _ = fs::remove_dir_all(&path);
            fs::create_dir_all(&path).unwrap();
            TempDir(path)
        }
        fn path(&self) -> &Path {
            &self.0
        }
    }

    impl Drop for TempDir {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn safe_join_blocks_escapes() {
        let root = Path::new("/home/smth");
        assert_eq!(
            safe_join(root, "Pictures/a.png").unwrap(),
            PathBuf::from("/home/smth/Pictures/a.png")
        );
        assert_eq!(
            safe_join(root, "./a").unwrap(),
            PathBuf::from("/home/smth/a")
        );
        for bad in ["../etc/passwd", "a/../../b", "/etc/passwd", "", "   "] {
            assert!(safe_join(root, bad).is_err(), "{bad} should be rejected");
        }
        assert!(safe_join(root, ".").is_err());
    }

    #[test]
    fn unique_names_never_overwrite() {
        let t = TempDir::new("unique");
        let dir = t.path();
        assert_eq!(unique_path(dir, "notes.txt"), dir.join("notes.txt"));
        fs::write(dir.join("notes.txt"), b"a").unwrap();
        assert_eq!(unique_path(dir, "notes.txt"), dir.join("notes (2).txt"));
        fs::write(dir.join("notes (2).txt"), b"b").unwrap();
        assert_eq!(unique_path(dir, "notes.txt"), dir.join("notes (3).txt"));
        assert_eq!(unique_path(dir, "README"), dir.join("README"));
        fs::create_dir(dir.join("README")).unwrap();
        assert_eq!(unique_path(dir, "README"), dir.join("README (2)"));
    }

    #[test]
    fn copy_move_and_rename() {
        let t = TempDir::new("ops");
        let dir = t.path();
        let src = dir.join("src");
        fs::create_dir_all(src.join("sub")).unwrap();
        fs::write(src.join("sub/a.txt"), b"hello").unwrap();
        fs::write(src.join("b.txt"), b"world").unwrap();

        let dest_dir = dir.join("dest");
        let copied = copy_into(&src, &dest_dir).unwrap();
        assert!(copied.join("sub/a.txt").is_file());
        assert_eq!(fs::read(copied.join("b.txt")).unwrap(), b"world");
        assert!(src.exists(), "copy must keep the source");

        let moved = move_into(&dir.join("b.txt.example"), &dest_dir).unwrap_err();
        assert!(matches!(moved, FsError::NotFound(_)));

        fs::write(dir.join("c.txt"), b"c").unwrap();
        let moved = move_into(&dir.join("c.txt"), &dest_dir).unwrap();
        assert_eq!(moved, dest_dir.join("c.txt"));
        assert!(!dir.join("c.txt").exists());

        let renamed = rename_within(&moved, "renamed.txt").unwrap();
        assert_eq!(renamed, dest_dir.join("renamed.txt"));
        assert!(rename_within(&renamed, "").is_err());
        assert!(rename_within(&renamed, "a/b").is_err());
        fs::write(dest_dir.join("renamed.txt.bak"), b"x").unwrap();
        fs::write(dest_dir.join("other"), b"x").unwrap();
        assert!(
            rename_within(&renamed, "other").is_err(),
            "rename must not overwrite"
        );
        assert!(copy_into(&dir.join("missing"), &dest_dir).is_err());
    }

    #[test]
    fn create_dir_picks_unique_names_and_validates() {
        let t = TempDir::new("mkdir");
        let dir = t.path();
        assert_eq!(
            create_dir(dir, "New folder").unwrap(),
            dir.join("New folder")
        );
        assert_eq!(
            create_dir(dir, "New folder").unwrap(),
            dir.join("New folder (2)")
        );
        for bad in ["", " ", "a/b", "..", "."] {
            assert!(create_dir(dir, bad).is_err(), "{bad:?} should be rejected");
        }
    }

    #[test]
    fn trash_moves_and_writes_metadata() {
        let t = TempDir::new("trash");
        let dir = t.path();
        fs::write(dir.join("junk.txt"), b"junk").unwrap();
        let trash_dir = dir.join("Trash");
        let dest = trash(&dir.join("junk.txt"), &trash_dir).unwrap();
        assert!(dest.starts_with(trash_dir.join("files")));
        assert!(!dir.join("junk.txt").exists());
        let info = fs::read_to_string(trash_dir.join("info/junk.txt.trashinfo")).unwrap();
        assert!(info.starts_with("[Trash Info]\nPath=/"));
        assert!(info.contains("DeletionDate="));
        assert!(info.ends_with('\n'));
        assert!(trash(&dir.join("nope"), &trash_dir).is_err());
    }

    #[test]
    fn trash_root_prefers_xdg_data_home() {
        let home = Path::new("/home/smth");
        assert_eq!(trash_root(home, None), PathBuf::from("/home/smth/Trash"));
        assert_eq!(
            trash_root(home, Some(Path::new("/data/xdg"))),
            PathBuf::from("/data/xdg/Trash")
        );
    }

    #[test]
    fn date_format_is_stable() {
        let d = chrono_like_now();
        assert_eq!(d.len(), 19, "{d}");
        assert_eq!(&d[4..5], "-");
        assert_eq!(&d[10..11], "T");
        assert_eq!(&d[13..14], ":");
    }
}
