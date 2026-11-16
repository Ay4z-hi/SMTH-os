//! `smthctl-core`: talk to `smthd` from shell scripts and GTK apps.
//!
//! Prints JSON on stdout and exits non-zero with a message on stderr, so it is
//! safe to use from `sh` without parsing quirks.
//!
//! Usage:
//!   smthctl-core ping
//!   smthctl-core status
//!   smthctl-core services
//!   smthctl-core start NAME | stop NAME | restart NAME
//!   smthctl-core layout snap left|right|top|bottom|maximize|center
//!   smthctl-core layout split PANES INDEX
//!   smthctl-core layout cascade INDEX WIDTH HEIGHT
//!   smthctl-core ahian [SEED]
//!
//! Common: --socket PATH, --screen WxH (default from SMTH_SCREEN_W/H or 1920x1080)

use smth_core::ipc::{LayoutOp, Request};
use smth_core::layout::{Rect, Snap};
use std::path::{Path, PathBuf};

fn fail(message: impl AsRef<str>) -> ! {
    eprintln!("smthctl-core: {}", message.as_ref());
    std::process::exit(1);
}

fn socket(args: &[String]) -> PathBuf {
    args.iter()
        .position(|a| a == "--socket")
        .and_then(|i| args.get(i + 1))
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            std::env::var("SMTHD_SOCKET")
                .map(PathBuf::from)
                .unwrap_or_else(|_| smthd::unix::default_socket())
        })
}

fn screen(args: &[String]) -> Rect {
    if let Some(i) = args.iter().position(|a| a == "--screen") {
        if let Some(value) = args.get(i + 1) {
            let mut parts = value.split(['x', 'X']);
            if let (Some(w), Some(h)) = (parts.next(), parts.next()) {
                if let (Ok(w), Ok(h)) = (w.parse(), h.parse()) {
                    return Rect::new(0, 0, w, h);
                }
            }
            fail(format!("bad --screen value: {value}"));
        }
    }
    let w = std::env::var("SMTH_SCREEN_W")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(1920);
    let h = std::env::var("SMTH_SCREEN_H")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(1080);
    Rect::new(0, 0, w, h)
}

fn positionals(args: &[String]) -> Vec<String> {
    let mut out = Vec::new();
    let mut skip = false;
    for (i, a) in args.iter().enumerate() {
        if skip {
            skip = false;
            continue;
        }
        if ["--socket", "--screen"].contains(&a.as_str()) && args.get(i + 1).is_some() {
            skip = true;
            continue;
        }
        if !a.starts_with("--") {
            out.push(a.clone());
        }
    }
    out
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let pos = positionals(&args);
    let Some(command) = pos.first().cloned() else {
        fail("usage: smthctl-core <ping|status|services|start|stop|restart|layout|ahian>");
    };
    let request = match command.as_str() {
        "ping" => Request::Ping,
        "status" => Request::Status,
        "services" | "list" => Request::ListServices,
        "start" => Request::Start {
            name: pos
                .get(1)
                .cloned()
                .unwrap_or_else(|| fail("start needs a service name")),
        },
        "stop" => Request::Stop {
            name: pos
                .get(1)
                .cloned()
                .unwrap_or_else(|| fail("stop needs a service name")),
        },
        "restart" => Request::Restart {
            name: pos
                .get(1)
                .cloned()
                .unwrap_or_else(|| fail("restart needs a service name")),
        },
        "layout" => {
            let kind = pos
                .get(1)
                .cloned()
                .unwrap_or_else(|| fail("layout needs snap|split|cascade"));
            let action = match kind.as_str() {
                "snap" => {
                    let snap = match pos.get(2).map(|s| s.as_str()) {
                        Some("left") => Snap::Left,
                        Some("right") => Snap::Right,
                        Some("top") => Snap::Top,
                        Some("bottom") => Snap::Bottom,
                        Some("maximize") | Some("max") => Snap::Maximize,
                        Some("center") => Snap::Center,
                        other => fail(format!("unknown snap target: {other:?}")),
                    };
                    LayoutOp::Snap(snap)
                }
                "split" => {
                    let panes = pos.get(2).and_then(|v| v.parse().ok()).unwrap_or(2u8);
                    let index = pos.get(3).and_then(|v| v.parse().ok()).unwrap_or(0u8);
                    if panes == 0 || index >= panes {
                        fail("split needs 1..=4 panes and an index below it");
                    }
                    LayoutOp::Split { panes, index }
                }
                "cascade" => {
                    let index = pos.get(2).and_then(|v| v.parse().ok()).unwrap_or(0usize);
                    let width = pos.get(3).and_then(|v| v.parse().ok()).unwrap_or(960u32);
                    let height = pos.get(4).and_then(|v| v.parse().ok()).unwrap_or(640u32);
                    LayoutOp::Cascade {
                        index,
                        width,
                        height,
                    }
                }
                other => fail(format!("unknown layout kind: {other}")),
            };
            Request::Layout {
                screen: screen(&args),
                gap: 8,
                action,
            }
        }
        "ahian" => {
            let seed = pos.get(1).and_then(|v| v.parse().ok());
            let rect = screen(&args);
            Request::AhianPlan {
                seed,
                width: rect.w,
                height: rect.h,
            }
        }
        "--help" | "-h" | "help" => {
            println!("usage: smthctl-core <ping|status|services|start|stop|restart|layout|ahian> [--socket PATH] [--screen WxH]");
            return;
        }
        other => fail(format!("unknown command: {other}")),
    };

    let path: &Path = &socket(&args);
    match smthd::unix::request(path, &request) {
        Ok(response) => {
            let text =
                serde_json::to_string_pretty(&response).unwrap_or_else(|e| fail(e.to_string()));
            println!("{text}");
            if matches!(response, smth_core::ipc::Response::Error { .. }) {
                std::process::exit(1);
            }
        }
        Err(e) => fail(e),
    }
}
