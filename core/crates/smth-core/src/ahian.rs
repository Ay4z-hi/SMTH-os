//! The AHIAN script: timing data for the terminal easter egg.
//!
//! The Python shell renders this plan with GTK, `smth-ahian` prints it as JSON
//! and the tests below pin the user-visible contract:
//!
//! 1. the terminal prints a progressive error sequence,
//! 2. error dialogs appear gradually and fill the screen over about 10 s,
//! 3. a Windows-style blue screen appears,
//! 4. it displays "wants to make your life beautiful",
//! 5. a 9 second countdown runs,
//! 6. the system transitions into the AHIAN experience (purple/teal).
//!
//! `unahian` shows an angry red screen reading "looks like you dont like
//! ahian" and restores the normal experience.

use crate::layout::Rect;
use crate::Rng;
use serde::{Deserialize, Serialize};

/// Exact AHIAN promise text. Tests and the UI read this constant, so the copy
/// cannot drift between the terminal, the blue screen and the docs.
pub const AHIAN_MESSAGE: &str = "wants to make your life beautiful";
/// Exact unahian complaint text.
pub const UNAHIAN_MESSAGE: &str = "looks like you dont like ahian";
/// Wallpaper file used by AHIAN mode.
pub const AHIAN_WALLPAPER: &str = "/usr/share/backgrounds/smth/ahian-teal.png";
/// Wallpaper restored by `unahian`.
pub const NORMAL_WALLPAPER: &str = "/usr/share/backgrounds/smth/wallpaper.png";
/// How long the dialog storm takes to fill the screen.
pub const FILL_MS: u32 = 10_000;
/// Countdown length shown on the blue screen.
pub const COUNTDOWN_SECONDS: u8 = 9;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DialogKind {
    Error,
    Warning,
    Critical,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ErrorLine {
    /// Milliseconds after the script starts.
    pub at_ms: u32,
    pub text: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DialogSpec {
    pub at_ms: u32,
    pub rect: Rect,
    pub kind: DialogKind,
    pub title: String,
    pub body: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Bsod {
    pub at_ms: u32,
    pub heading: String,
    pub message: String,
    pub stop_code: String,
    pub countdown_seconds: u8,
    pub accent: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AhianPlan {
    pub seed: u64,
    pub screen: Rect,
    pub errors: Vec<ErrorLine>,
    pub dialogs: Vec<DialogSpec>,
    pub fill_ms: u32,
    pub bsod: Bsod,
    pub wallpaper: String,
    pub core_version: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct UnahianPlan {
    pub heading: String,
    pub message: String,
    pub accent: String,
    pub hold_ms: u32,
    pub restore_wallpaper: String,
}

const FAILURES: [&str; 10] = [
    "smth-core: cannot resolve symbol `home`",
    "segmentation fault (core dumped)",
    "wayland: compositor rejected surface",
    "ahian.so: undefined reference to `beauty`",
    "error: 0x0000A1A1 memory not found",
    "warn: dot grid desynchronised",
    "error: palette overflow in column 7",
    "fatal: the void looked back",
    "error: 42 unnecessary pixels",
    "AHIAN: something wants to be beautiful",
];

const DIALOG_TITLES: [&str; 6] = [
    "smth-core has stopped working",
    "AHIAN subsystem",
    "Kernel mode dot mismatch",
    "System alert",
    "Critical process died",
    "SMTH OS",
];

const DIALOG_BODIES: [&str; 6] = [
    "A problem caused the program to stop working correctly.",
    "The dot engine could not keep up with your expectations.",
    "0x000000A1: attempted to divide beauty by zero.",
    "The window manager would like to apologise.",
    "Something is trying to make your life beautiful.",
    "This dialog will close itself. Probably.",
];

fn text_lines(seed: u64) -> Vec<ErrorLine> {
    let mut rng = Rng::new(seed ^ 0xA1A1);
    let mut out = Vec::new();
    let mut at = 0u32;
    // 26 lines spread across the first ~4.5 s so the terminal feels alive but
    // still finishes before the dialog storm peaks.
    for i in 0..26u32 {
        let failure = FAILURES[(i as usize + (seed as usize % FAILURES.len())) % FAILURES.len()];
        out.push(ErrorLine {
            at_ms: at,
            text: format!("[{:02}] {}", i + 1, failure),
        });
        at += rng.range(40, 240) as u32;
    }
    // The last line announces the transition; keep it just before the blue screen.
    out.push(ErrorLine {
        at_ms: FILL_MS - 400,
        text: "AHIAN: preparing a better experience".into(),
    });
    out
}

fn dialogs(seed: u64, screen: Rect) -> Vec<DialogSpec> {
    let mut rng = Rng::new(seed ^ 0xD1A1);
    // A 6x4 grid of overlapping cells, visited in a shuffled order. Dialogs are
    // big enough to overlap and small enough that later ones remain reachable;
    // the point is a screen that slowly becomes unusable.
    let cols = 6i32;
    let rows = 4i32;
    let cell_w = (screen.w as i32 / cols).max(220);
    let cell_h = (screen.h as i32 / rows).max(110);
    let mut cells: Vec<(i32, i32)> = (0..rows)
        .flat_map(|r| (0..cols).map(move |c| (c, r)))
        .collect();
    for i in (1..cells.len()).rev() {
        let j = rng.range(0, i as i32) as usize;
        cells.swap(i, j);
    }
    let total = 34usize.min(cells.len());
    let mut out = Vec::with_capacity(total);
    // Quadratic spacing packs the screen early and keeps a visible trickle at
    // the end: the sequence still occupies the full FILL_MS window.
    for (n, (col, row)) in cells.into_iter().take(total).enumerate() {
        let t = (n as f64 + 1.0) / total as f64;
        let at_ms = (t.powf(1.35) * (FILL_MS - 600) as f64) as u32 + rng.range(0, 40) as u32;
        let w = (cell_w as f64 * (0.78 + rng.unit() * 0.3)) as u32;
        let h = (cell_h as f64 * (0.85 + rng.unit() * 0.4)) as u32;
        let x = screen.x + col * cell_w + rng.range(-24, 24);
        let y = screen.y + row * cell_h + rng.range(-18, 18);
        let spec = Rect::new(x, y, w.max(220), h.max(110));
        let kind = match n % 7 {
            0 => DialogKind::Critical,
            1..=3 => DialogKind::Warning,
            _ => DialogKind::Error,
        };
        out.push(DialogSpec {
            at_ms,
            rect: spec.clamped_into(&screen),
            kind,
            title: DIALOG_TITLES[(n + seed as usize) % DIALOG_TITLES.len()].to_string(),
            body: DIALOG_BODIES[(n * 3 + seed as usize) % DIALOG_BODIES.len()].to_string(),
        });
    }
    out.sort_by_key(|d| d.at_ms);
    out
}

/// Build the full AHIAN plan for a screen of `width` x `height` CSS pixels.
pub fn ahian_plan(seed: u64, width: u32, height: u32, accent: &str) -> AhianPlan {
    let screen = Rect::new(0, 0, width.max(640), height.max(480));
    AhianPlan {
        seed,
        screen,
        errors: text_lines(seed),
        dialogs: dialogs(seed, screen),
        fill_ms: FILL_MS,
        bsod: Bsod {
            at_ms: FILL_MS,
            heading: "SMTH OS".into(),
            message: AHIAN_MESSAGE.into(),
            stop_code: "AHIAN_BEAUTY_ATTEMPTED".into(),
            countdown_seconds: COUNTDOWN_SECONDS,
            accent: accent.to_string(),
        },
        wallpaper: AHIAN_WALLPAPER.into(),
        core_version: crate::CORE_VERSION.into(),
    }
}

/// Build the `unahian` plan: angry red screen, then restore normal mode.
pub fn unahian_plan(accent: &str) -> UnahianPlan {
    UnahianPlan {
        heading: "AHIAN HAS BEEN DISABLED".into(),
        message: UNAHIAN_MESSAGE.into(),
        accent: accent.to_string(),
        hold_ms: 2_600,
        restore_wallpaper: NORMAL_WALLPAPER.into(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn plan() -> AhianPlan {
        ahian_plan(42, 1920, 1080, "#d71921")
    }

    #[test]
    fn script_matches_the_required_sequence() {
        let p = plan();
        assert_eq!(p.bsod.message, "wants to make your life beautiful");
        assert_eq!(p.bsod.countdown_seconds, 9);
        assert_eq!(p.fill_ms, 10_000);
        assert!(
            p.wallpaper.contains("ahian"),
            "AHIAN needs its own wallpaper"
        );
        assert!(p.errors.first().unwrap().at_ms < p.errors.last().unwrap().at_ms);
        assert!(p.errors.iter().any(|e| e.text.contains("AHIAN")));
    }

    #[test]
    fn dialogs_fill_the_screen_progressively() {
        let p = plan();
        assert!(
            p.dialogs.len() >= 24,
            "expected a screen-filling storm, got {}",
            p.dialogs.len()
        );
        let first = p.dialogs.first().unwrap().at_ms;
        let last = p.dialogs.last().unwrap().at_ms;
        assert!(first < 2_000, "first dialog arrives too late: {first}ms");
        assert!(
            last <= p.fill_ms,
            "last dialog must not arrive after the blue screen"
        );
        assert!(
            last >= p.fill_ms - 1_500,
            "dialog storm ends too early: {last}ms"
        );
        for pair in p.dialogs.windows(2) {
            assert!(
                pair[0].at_ms <= pair[1].at_ms,
                "dialog order must be chronological"
            );
        }
        for d in &p.dialogs {
            assert!(
                p.screen.contains(&d.rect),
                "dialog off-screen: {:?}",
                d.rect
            );
            assert!(d.rect.area() > 0);
            assert!(!d.title.is_empty() && !d.body.is_empty());
        }
        // The storm must actually cover a large share of the screen area.
        let covered: u64 = p
            .dialogs
            .iter()
            .map(|d| d.rect.area())
            .sum::<u64>()
            .min(p.screen.area() * 3);
        assert!(covered > p.screen.area(), "dialogs do not fill the screen");
    }

    #[test]
    fn plans_are_deterministic_per_seed() {
        assert_eq!(plan(), plan());
        assert_ne!(
            plan().dialogs,
            ahian_plan(43, 1920, 1080, "#d71921").dialogs
        );
    }

    #[test]
    fn works_on_small_screens() {
        let p = ahian_plan(1, 320, 240, "#d71921");
        for d in &p.dialogs {
            assert!(
                p.screen.contains(&d.rect),
                "{:?} escapes {:?}",
                d.rect,
                p.screen
            );
        }
    }

    #[test]
    fn unahian_matches_the_required_copy() {
        let u = unahian_plan("#d71921");
        assert_eq!(u.message, "looks like you dont like ahian");
        assert_eq!(u.accent, "#d71921");
        assert_eq!(u.restore_wallpaper, NORMAL_WALLPAPER);
        assert!(u.hold_ms > 0);
    }
}
