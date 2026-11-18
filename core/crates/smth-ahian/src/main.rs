//! `smth-ahian`: the single source of truth for the AHIAN easter egg timeline.
//!
//! The Python/GTK front end (`/usr/local/bin/ahian`) executes the plan printed
//! here. Keeping the timeline in Rust means the terminal output, the dialog
//! storm, the blue screen, the countdown and `unahian` cannot drift apart, and
//! the timings are unit-tested.
//!
//! Usage:
//!   smth-ahian plan [SEED] [WIDTHxHEIGHT]
//!   smth-ahian unplan
//!   smth-ahian errors [SEED]        # plain lines, for the terminal

use smth_core::ahian::{self, AHIAN_MESSAGE, COUNTDOWN_SECONDS, UNAHIAN_MESSAGE};
use smth_core::palette::Palette;
use std::path::PathBuf;

const PALETTE_PATHS: [&str; 2] = ["/usr/local/lib/smth/palette.json", "tools/palette.json"];

fn palette() -> Palette {
    for path in PALETTE_PATHS {
        if let Ok(text) = std::fs::read_to_string(PathBuf::from(path)) {
            if let Ok(p) = Palette::from_json(&text) {
                return p;
            }
        }
    }
    Palette::from_json(r##"{"A":"#701b35","B":"#f2c6d2","AHIAN_A":"#7c4dff","AHIAN_B":"#00c2a8"}"##)
        .expect("built-in palette is valid")
}

fn screen(arg: Option<&String>) -> (u32, u32) {
    arg.and_then(|v| {
        let mut parts = v.split(['x', 'X']);
        let w = parts.next()?.parse().ok()?;
        let h = parts.next()?.parse().ok()?;
        Some((w, h))
    })
    .unwrap_or((1920, 1080))
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let palette = palette();
    match args.first().map(|s| s.as_str()) {
        Some("plan") => {
            let seed = args.get(1).and_then(|v| v.parse().ok()).unwrap_or(2026);
            let (w, h) = screen(args.get(2));
            let plan = ahian::ahian_plan(seed, w, h, &palette.raw_a);
            match serde_json::to_string_pretty(&plan) {
                Ok(text) => println!("{text}"),
                Err(e) => {
                    eprintln!("smth-ahian: {e}");
                    std::process::exit(1);
                }
            }
        }
        Some("unplan") => {
            let plan = ahian::unahian_plan(&palette.raw_a);
            match serde_json::to_string_pretty(&plan) {
                Ok(text) => println!("{text}"),
                Err(e) => {
                    eprintln!("smth-ahian: {e}");
                    std::process::exit(1);
                }
            }
        }
        Some("errors") => {
            let seed = args.get(1).and_then(|v| v.parse().ok()).unwrap_or(2026);
            let plan = ahian::ahian_plan(seed, 1920, 1080, &palette.raw_a);
            for line in plan.errors {
                println!("{}", line.text);
            }
        }
        Some("version") => println!(
            "smth-ahian {} (core {}) ahian_a={} ahian_b={}",
            env!("CARGO_PKG_VERSION"),
            smth_core::CORE_VERSION,
            palette.raw_ahian_a,
            palette.raw_ahian_b
        ),
        _ => {
            println!(
                "usage: smth-ahian plan [SEED] [WIDTHxHEIGHT] | unplan | errors [SEED] | version"
            );
            println!("ahian message: {AHIAN_MESSAGE}");
            println!("countdown: {COUNTDOWN_SECONDS}s");
            println!("unahian message: {UNAHIAN_MESSAGE}");
        }
    }
}
