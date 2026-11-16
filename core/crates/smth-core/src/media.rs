//! The Dynamic-Island-style pill: how media, notifications and countdowns
//! decide what occupies the single compact surface at the top of the desktop.
//!
//! Priority rules (tested below) keep the pill predictable instead of letting
//! whichever writer ran last win.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PillKind {
    Media,
    Notification,
    Countdown,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Media {
    pub title: String,
    pub artist: String,
    pub playing: bool,
    /// 0.0..=1.0; clamped on read.
    pub progress: f32,
    pub source: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Notification {
    pub app: String,
    pub summary: String,
    /// freedesktop urgency hint: 0 low, 1 normal, 2 critical.
    pub urgency: u8,
    pub at_ms: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Pill {
    pub kind: PillKind,
    pub title: String,
    pub subtitle: String,
    pub progress: Option<f32>,
    pub priority: u8,
    pub expandable: bool,
}

/// Notifications stay on the pill for this long before yielding to media.
pub const NOTIFICATION_TTL_MS: u64 = 6_000;
/// Critical notifications keep the pill even while media plays.
pub const CRITICAL_TTL_MS: u64 = 12_000;

fn clamp_progress(p: f32) -> f32 {
    if p.is_nan() {
        0.0
    } else {
        p.clamp(0.0, 1.0)
    }
}

/// Decide what the island shows right now, or `None` when it should collapse.
pub fn island(media: Option<&Media>, notifications: &[Notification], now_ms: u64) -> Option<Pill> {
    let critical = notifications
        .iter()
        .filter(|n| n.urgency >= 2 && now_ms.saturating_sub(n.at_ms) <= CRITICAL_TTL_MS)
        .max_by_key(|n| n.at_ms);
    if let Some(n) = critical {
        return Some(Pill {
            kind: PillKind::Notification,
            title: n.summary.clone(),
            subtitle: n.app.clone(),
            progress: None,
            priority: 100,
            expandable: true,
        });
    }

    // Paused media keeps a residual progress value; only a playing source owns
    // the island. A paused player is not something the user needs on screen.
    let media_pill = media.filter(|m| m.playing).map(|m| Pill {
        kind: PillKind::Media,
        title: m.title.clone(),
        subtitle: m.artist.clone(),
        progress: Some(clamp_progress(m.progress)),
        priority: 60,
        expandable: true,
    });

    let recent = notifications
        .iter()
        .filter(|n| now_ms.saturating_sub(n.at_ms) <= NOTIFICATION_TTL_MS)
        .max_by_key(|n| n.at_ms)
        .map(|n| Pill {
            kind: PillKind::Notification,
            title: n.summary.clone(),
            subtitle: n.app.clone(),
            progress: None,
            priority: 70,
            expandable: false,
        });

    match (recent, media_pill) {
        (Some(n), Some(m)) if m.priority > n.priority => Some(m),
        (Some(n), _) => Some(n),
        (None, Some(m)) => Some(m),
        (None, None) => None,
    }
}

/// Countdown pill (alarms, timers, the AHIAN countdown).
pub fn countdown(label: &str, seconds_left: u32) -> Pill {
    Pill {
        kind: PillKind::Countdown,
        title: label.to_string(),
        subtitle: format!("{seconds_left}s"),
        progress: Some(clamp_progress(1.0 - (seconds_left as f32 / 9.0))),
        priority: 90,
        expandable: false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn media(playing: bool) -> Media {
        Media {
            title: "Dot Matrix".into(),
            artist: "SMTH".into(),
            playing,
            progress: 0.25,
            source: "player".into(),
        }
    }

    fn note(urgency: u8, at_ms: u64) -> Notification {
        Notification {
            app: "Network".into(),
            summary: "Wi-Fi connected".into(),
            urgency,
            at_ms,
        }
    }

    #[test]
    fn empty_island_collapses() {
        assert_eq!(island(None, &[], 0), None);
        assert_eq!(island(Some(&media(false)), &[], 0), None);
    }

    #[test]
    fn media_shows_when_playing() {
        let pill = island(Some(&media(true)), &[], 0).unwrap();
        assert_eq!(pill.kind, PillKind::Media);
        assert_eq!(pill.progress, Some(0.25));
        assert!(pill.expandable);
    }

    #[test]
    fn fresh_notification_beats_media_until_it_expires() {
        let m = media(true);
        let n = [note(1, 1_000)];
        assert_eq!(
            island(Some(&m), &n, 2_000).unwrap().kind,
            PillKind::Notification
        );
        assert_eq!(
            island(Some(&m), &n, 1_000 + NOTIFICATION_TTL_MS + 1)
                .unwrap()
                .kind,
            PillKind::Media
        );
    }

    #[test]
    fn critical_notification_wins_and_persists_longer() {
        let m = media(true);
        let n = [note(2, 0)];
        let pill = island(Some(&m), &n, 11_000).unwrap();
        assert_eq!(pill.kind, PillKind::Notification);
        assert_eq!(pill.priority, 100);
        assert_eq!(island(Some(&m), &n, 20_000).unwrap().kind, PillKind::Media);
    }

    #[test]
    fn newest_notification_wins() {
        let n = [note(1, 100), note(1, 900)];
        let mut n2 = n.clone();
        n2[1].summary = "Battery low".into();
        assert_eq!(island(None, &n2, 1_000).unwrap().title, "Battery low");
    }

    #[test]
    fn progress_is_clamped() {
        let mut m = media(true);
        m.progress = 5.0;
        assert_eq!(island(Some(&m), &[], 0).unwrap().progress, Some(1.0));
        m.progress = f32::NAN;
        assert_eq!(island(Some(&m), &[], 0).unwrap().progress, Some(0.0));
        m.progress = -1.0;
        assert_eq!(island(Some(&m), &[], 0).unwrap().progress, Some(0.0));
    }

    #[test]
    fn countdown_pill() {
        let p = countdown("AHIAN", 9);
        assert_eq!(p.kind, PillKind::Countdown);
        assert_eq!(p.subtitle, "9s");
        assert_eq!(p.progress, Some(0.0));
        assert_eq!(countdown("AHIAN", 0).progress, Some(1.0));
    }
}
