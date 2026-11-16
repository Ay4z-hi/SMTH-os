//! `smthd` entry point.
//!
//! Usage:
//!   smthd [--socket PATH] [--config FILE] [--palette FILE] [--no-supervise]

use smthd::unix::{bind, serve};
use smthd::{accent_from_palette, ServicesFile, State, Supervisor};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

fn arg_value(args: &[String], flag: &str) -> Option<String> {
    args.iter()
        .position(|a| a == flag)
        .and_then(|i| args.get(i + 1))
        .cloned()
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!("usage: smthd [--socket PATH] [--config FILE] [--palette FILE] [--no-supervise]");
        return;
    }
    let socket = arg_value(&args, "--socket")
        .map(PathBuf::from)
        .unwrap_or_else(smthd::unix::default_socket);
    let palette = arg_value(&args, "--palette").map(PathBuf::from);
    let supervise = !args.iter().any(|a| a == "--no-supervise");

    let services = match arg_value(&args, "--config") {
        Some(config) => match ServicesFile::from_path(&PathBuf::from(&config)) {
            Ok(file) => file,
            Err(e) => {
                eprintln!("smthd: {e}");
                std::process::exit(2);
            }
        },
        None => ServicesFile::builtin(),
    };

    let mut supervisor = Supervisor::new();
    if supervise {
        for spec in services.services {
            supervisor.add(spec);
        }
        supervisor.start_all();
    }

    let state = Arc::new(Mutex::new(State {
        supervisor,
        started: Instant::now(),
        accent: accent_from_palette(palette.as_deref()),
    }));

    let listener = match bind(&socket) {
        Ok(l) => l,
        Err(e) => {
            eprintln!("smthd: {}", e);
            std::process::exit(1);
        }
    };
    println!(
        "smthd: listening on {} (core {})",
        socket.display(),
        smth_core::CORE_VERSION
    );

    // Reap children and honour restart backoff.
    let ticker = Arc::clone(&state);
    std::thread::spawn(move || loop {
        std::thread::sleep(Duration::from_millis(250));
        let mut guard = match ticker.lock() {
            Ok(g) => g,
            Err(poisoned) => poisoned.into_inner(),
        };
        guard.supervisor.tick(Instant::now());
    });

    serve(listener, state);
}
