//! `smthd`: the SMTH OS user-session service supervisor and IPC server.
//!
//! Scope on purpose:
//! * supervise the long-lived shell helpers so a crashed `notifd` comes back,
//! * answer geometry, palette and AHIAN queries from `smth-core`,
//! * expose one line-delimited JSON protocol (see `smth_core::ipc`).
//!
//! It does not manage the compositor or replace systemd; see
//! docs/architecture/rust-migration.md for what is deliberately still outside.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use smth_core::ipc::{
    CodecError, LayoutOp, Request, Response, ServiceInfo, ServiceState, PROTOCOL_VERSION,
};
use smth_core::layout::{Layout, Rect};
use std::collections::BTreeMap;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

pub const DEFAULT_SOCKET: &str = "/run/user/1000/smthd.sock";
const MAX_RESTARTS: u32 = 5;
const BACKOFF_BASE: Duration = Duration::from_secs(1);
const BACKOFF_CAP: Duration = Duration::from_secs(30);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServiceSpec {
    pub name: String,
    pub command: Vec<String>,
    #[serde(default = "default_restart")]
    pub restart: bool,
}

fn default_restart() -> bool {
    true
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ServicesFile {
    #[serde(default)]
    pub services: Vec<ServiceSpec>,
}

impl ServicesFile {
    pub fn from_path(path: &Path) -> Result<ServicesFile, String> {
        let text = std::fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
        let file: ServicesFile =
            serde_json::from_str(&text).map_err(|e| format!("{}: {e}", path.display()))?;
        for spec in &file.services {
            if spec.name.trim().is_empty() || spec.command.is_empty() {
                return Err(format!(
                    "{}: service entry needs a name and a command",
                    path.display()
                ));
            }
        }
        Ok(file)
    }

    /// Fallback configuration used when no services file is installed.
    pub fn builtin() -> ServicesFile {
        ServicesFile {
            services: vec![
                ServiceSpec {
                    name: "notifd".into(),
                    command: vec!["/usr/local/bin/smth-notifd".into()],
                    restart: true,
                },
                ServiceSpec {
                    name: "moded".into(),
                    command: vec!["/usr/local/bin/smth-moded".into()],
                    restart: true,
                },
            ],
        }
    }
}

struct Managed {
    spec: ServiceSpec,
    child: Option<Child>,
    state: ServiceState,
    restarts: u32,
    retry_at: Option<Instant>,
    last_error: Option<String>,
}

/// Owns child processes. Dropping the supervisor terminates everything it
/// started, so a crashed daemon does not leave orphaned helpers behind.
#[derive(Default)]
pub struct Supervisor {
    services: BTreeMap<String, Managed>,
}

impl Supervisor {
    pub fn new() -> Supervisor {
        Supervisor {
            services: BTreeMap::new(),
        }
    }

    pub fn with_specs<I: IntoIterator<Item = ServiceSpec>>(specs: I) -> Supervisor {
        let mut s = Supervisor::new();
        for spec in specs {
            s.add(spec);
        }
        s
    }

    pub fn add(&mut self, spec: ServiceSpec) {
        self.services.insert(
            spec.name.clone(),
            Managed {
                spec,
                child: None,
                state: ServiceState::Stopped,
                restarts: 0,
                retry_at: None,
                last_error: None,
            },
        );
    }

    fn spawn(&mut self, name: &str) -> Result<(), String> {
        let managed = self
            .services
            .get_mut(name)
            .ok_or_else(|| format!("unknown service: {name}"))?;
        let mut command = Command::new(&managed.spec.command[0]);
        command
            .args(&managed.spec.command[1..])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        match command.spawn() {
            Ok(child) => {
                managed.child = Some(child);
                managed.state = ServiceState::Running;
                managed.retry_at = None;
                Ok(())
            }
            Err(e) => {
                managed.state = ServiceState::Failed;
                managed.last_error = Some(format!("spawn failed: {e}"));
                Err(managed.last_error.clone().unwrap())
            }
        }
    }

    pub fn start(&mut self, name: &str) -> Result<(), String> {
        if let Some(managed) = self.services.get(name) {
            if managed.child.is_some() {
                return Ok(()); // already running
            }
        }
        self.spawn(name)?;
        if let Some(m) = self.services.get_mut(name) {
            m.restarts = 0;
        }
        Ok(())
    }

    pub fn stop(&mut self, name: &str) -> Result<(), String> {
        let managed = self
            .services
            .get_mut(name)
            .ok_or_else(|| format!("unknown service: {name}"))?;
        if let Some(mut child) = managed.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        managed.state = ServiceState::Stopped;
        managed.retry_at = None;
        Ok(())
    }

    pub fn restart(&mut self, name: &str) -> Result<(), String> {
        self.stop(name)?;
        self.start(name)
    }

    /// Reap exited children and honour restart backoff. Called on a timer.
    pub fn tick(&mut self, now: Instant) {
        let mut respawn: Vec<String> = Vec::new();
        for managed in self.services.values_mut() {
            let exited = match managed.child.as_mut() {
                Some(child) => match child.try_wait() {
                    Ok(Some(status)) => Some(status.code()),
                    Ok(None) => None,
                    Err(e) => {
                        managed.last_error = Some(format!("wait failed: {e}"));
                        Some(None)
                    }
                },
                None => None,
            };
            if let Some(code) = exited {
                managed.child = None;
                managed.restarts = managed.restarts.saturating_add(1);
                managed.last_error = Some(match code {
                    Some(c) => format!("exited with status {c}"),
                    None => "terminated by signal".into(),
                });
                if managed.spec.restart && managed.restarts <= MAX_RESTARTS {
                    managed.state = ServiceState::Backoff;
                    let delay = (BACKOFF_BASE * 2u32.pow(managed.restarts - 1)).min(BACKOFF_CAP);
                    managed.retry_at = Some(now + delay);
                } else {
                    managed.state = ServiceState::Failed;
                }
            }
            if managed.state == ServiceState::Backoff
                && managed.retry_at.is_some_and(|t| now >= t)
                && managed.child.is_none()
            {
                respawn.push(managed.spec.name.clone());
            }
        }
        // Spawning re-borrows the map, so it happens after the iteration.
        for name in respawn {
            let _ = self.spawn(&name);
        }
    }

    pub fn start_all(&mut self) {
        let names: Vec<String> = self.services.keys().cloned().collect();
        for name in names {
            let _ = self.start(&name);
        }
    }

    pub fn infos(&self) -> Vec<ServiceInfo> {
        self.services
            .values()
            .map(|m| ServiceInfo {
                name: m.spec.name.clone(),
                state: m.state.clone(),
                pid: m.child.as_ref().map(|c| c.id()),
                restarts: m.restarts,
                last_error: m.last_error.clone(),
            })
            .collect()
    }
}

impl Drop for Supervisor {
    fn drop(&mut self) {
        for managed in self.services.values_mut() {
            if let Some(mut child) = managed.child.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

/// Palette access without a JSON dependency in callers.
pub fn accent_from_palette(path: Option<&Path>) -> String {
    let Some(path) = path else {
        return "#d71921".into();
    };
    std::fs::read_to_string(path)
        .ok()
        .and_then(|text| serde_json::from_str::<Value>(&text).ok())
        .and_then(|v| v.get("A").and_then(|a| a.as_str()).map(|s| s.to_string()))
        .unwrap_or_else(|| "#d71921".into())
}

/// Shared server state.
pub struct State {
    pub supervisor: Supervisor,
    pub started: Instant,
    pub accent: String,
}

pub fn handle(state: &mut State, request: Request) -> Response {
    match request {
        Request::Ping => Response::Pong {
            protocol: PROTOCOL_VERSION,
            core: smth_core::CORE_VERSION.into(),
        },
        Request::Status => Response::Status {
            uptime_ms: state.started.elapsed().as_millis() as u64,
            services: state.supervisor.infos(),
            core: smth_core::CORE_VERSION.into(),
            protocol: PROTOCOL_VERSION,
        },
        Request::ListServices => Response::Services {
            services: state.supervisor.infos(),
        },
        Request::Start { name } => match state.supervisor.start(&name) {
            Ok(()) => Response::Services {
                services: state.supervisor.infos(),
            },
            Err(message) => Response::Error { message },
        },
        Request::Stop { name } => match state.supervisor.stop(&name) {
            Ok(()) => Response::Services {
                services: state.supervisor.infos(),
            },
            Err(message) => Response::Error { message },
        },
        Request::Restart { name } => match state.supervisor.restart(&name) {
            Ok(()) => Response::Services {
                services: state.supervisor.infos(),
            },
            Err(message) => Response::Error { message },
        },
        Request::Layout {
            screen,
            gap,
            action,
        } => {
            if screen.w == 0 || screen.h == 0 {
                return Response::Error {
                    message: "screen geometry must be non-zero".into(),
                };
            }
            let layout = Layout::new(screen, gap);
            let rect = match action {
                LayoutOp::Cascade {
                    index,
                    width,
                    height,
                } => layout.cascade((width, height), index),
                LayoutOp::Snap(snap) => layout.snap(snap),
                LayoutOp::Split { panes, index } => layout.split(panes, index),
            };
            Response::Rect { rect }
        }
        Request::AhianPlan {
            seed,
            width,
            height,
        } => Response::AhianPlan {
            plan: smth_core::ahian::ahian_plan(
                seed.unwrap_or_else(|| state.started.elapsed().as_millis() as u64 + 1),
                width,
                height,
                &state.accent,
            ),
        },
    }
}

#[cfg(unix)]
pub mod unix {
    use super::*;
    use std::os::unix::fs::PermissionsExt;
    use std::os::unix::net::{UnixListener, UnixStream};

    /// Bind the daemon socket, removing a stale socket file left by a crash.
    pub fn bind(path: &Path) -> std::io::Result<UnixListener> {
        if path.exists() {
            match UnixStream::connect(path) {
                Ok(_) => {
                    return Err(std::io::Error::new(
                        std::io::ErrorKind::AddrInUse,
                        format!("{} is already served by a running smthd", path.display()),
                    ))
                }
                Err(_) => {
                    let _ = std::fs::remove_file(path);
                }
            }
        }
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let listener = UnixListener::bind(path)?;
        // Session-local socket: only the logged-in user may talk to it.
        let _ = std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600));
        Ok(listener)
    }

    pub fn serve(listener: UnixListener, state: Arc<Mutex<State>>) {
        for stream in listener.incoming() {
            match stream {
                Ok(stream) => {
                    let state = Arc::clone(&state);
                    std::thread::spawn(move || handle_connection(stream, state));
                }
                Err(_) => continue,
            }
        }
    }

    fn handle_connection(stream: UnixStream, state: Arc<Mutex<State>>) {
        let reader = match stream.try_clone() {
            Ok(s) => BufReader::new(s),
            Err(_) => return,
        };
        let mut writer = stream;
        for line in reader.lines() {
            let Ok(line) = line else { break };
            if line.trim().is_empty() {
                continue;
            }
            let response = match smth_core::ipc::decode_request(&line) {
                Ok(request) => {
                    let mut guard = match state.lock() {
                        Ok(g) => g,
                        Err(poisoned) => poisoned.into_inner(),
                    };
                    handle(&mut guard, request)
                }
                Err(e) => Response::Error {
                    message: format!("bad request: {e}"),
                },
            };
            match smth_core::ipc::encode(&response) {
                Ok(text) => {
                    if writer.write_all(text.as_bytes()).is_err() {
                        break;
                    }
                    let _ = writer.flush();
                }
                Err(_) => break,
            }
        }
    }

    /// One-shot client used by shell scripts and the CLI binaries.
    pub fn request(path: &Path, request: &Request) -> Result<Response, String> {
        let mut stream = UnixStream::connect(path)
            .map_err(|e| format!("cannot reach smthd at {}: {e}", path.display()))?;
        stream
            .write_all(
                smth_core::ipc::encode(request)
                    .map_err(|e| e.to_string())?
                    .as_bytes(),
            )
            .map_err(|e| e.to_string())?;
        let mut reader = BufReader::new(stream);
        let mut line = String::new();
        reader.read_line(&mut line).map_err(|e| e.to_string())?;
        smth_core::ipc::decode_response(&line).map_err(|e: CodecError| e.to_string())
    }

    pub fn default_socket() -> PathBuf {
        if let Ok(runtime) = std::env::var("XDG_RUNTIME_DIR") {
            return PathBuf::from(runtime).join("smthd.sock");
        }
        if let Ok(path) = std::env::var("SMTHD_SOCKET") {
            return PathBuf::from(path);
        }
        PathBuf::from("/tmp/smthd.sock")
    }
}

#[cfg(not(unix))]
pub mod unix {
    use super::*;
    pub fn default_socket() -> PathBuf {
        PathBuf::from("smthd.sock")
    }
    pub fn request(_path: &Path, _request: &Request) -> Result<Response, String> {
        Err("smthd IPC requires a Unix host".into())
    }
}

/// Convenience for callers that only need a rectangle.
pub fn layout_rect(screen: Rect, gap: u32, action: LayoutOp) -> Rect {
    let layout = Layout::new(screen, gap);
    match action {
        LayoutOp::Cascade {
            index,
            width,
            height,
        } => layout.cascade((width, height), index),
        LayoutOp::Snap(snap) => layout.snap(snap),
        LayoutOp::Split { panes, index } => layout.split(panes, index),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sleep_spec(name: &str, secs: u32) -> ServiceSpec {
        ServiceSpec {
            name: name.into(),
            command: vec!["sleep".into(), secs.to_string()],
            restart: false,
        }
    }

    #[test]
    fn supervisor_starts_and_stops_children() {
        let mut s = Supervisor::with_specs([sleep_spec("sleeper", 30)]);
        s.start("sleeper").expect("start");
        let info = &s.infos()[0];
        assert_eq!(info.state, ServiceState::Running);
        assert!(info.pid.is_some());
        // Starting twice is idempotent.
        s.start("sleeper").unwrap();
        assert_eq!(s.infos()[0].restarts, 0);
        s.stop("sleeper").unwrap();
        assert_eq!(s.infos()[0].state, ServiceState::Stopped);
        assert!(s.infos()[0].pid.is_none());
    }

    #[test]
    fn unknown_services_are_rejected() {
        let mut s = Supervisor::new();
        assert!(s.start("nope").is_err());
        assert!(s.stop("nope").is_err());
        assert!(s.restart("nope").is_err());
    }

    #[test]
    fn spawn_failures_are_reported_not_panicked() {
        let mut s = Supervisor::with_specs([ServiceSpec {
            name: "missing".into(),
            command: vec!["/nonexistent/smth-binary".into()],
            restart: true,
        }]);
        let err = s.start("missing").unwrap_err();
        assert!(err.contains("spawn failed"), "{err}");
        let info = &s.infos()[0];
        assert_eq!(info.state, ServiceState::Failed);
        assert!(info.last_error.is_some());
    }

    #[test]
    fn exited_children_enter_backoff_then_fail() {
        let mut s = Supervisor::with_specs([ServiceSpec {
            name: "quick".into(),
            command: vec!["true".into()],
            restart: true,
        }]);
        s.start("quick").unwrap();
        std::thread::sleep(Duration::from_millis(200));
        s.tick(Instant::now());
        let info = &s.infos()[0];
        assert_eq!(info.state, ServiceState::Backoff);
        assert_eq!(info.restarts, 1);
        assert!(info.last_error.is_some());

        // Drive the backoff clock forward artificially. The fake clock must keep
        // increasing, because each retry is scheduled relative to the time it
        // was observed at. Each restart costs two ticks (observe the exit, then
        // respawn), so loop until the cap is hit.
        let base = Instant::now();
        let mut failed = false;
        for i in 1..=60u32 {
            std::thread::sleep(Duration::from_millis(20));
            s.tick(base + Duration::from_secs(i as u64 * 60));
            if s.infos()[0].state == ServiceState::Failed {
                failed = true;
                break;
            }
        }
        let info = &s.infos()[0];
        assert!(
            failed,
            "restarts must be capped, state stuck at {:?}",
            info.state
        );
        assert!(
            info.restarts > 1,
            "expected repeated restarts, got {}",
            info.restarts
        );
        assert!(info.restarts <= MAX_RESTARTS + 1);
    }

    #[test]
    fn no_restart_policy_marks_failed() {
        let mut s = Supervisor::with_specs([sleep_spec("oneshot", 0)]);
        s.start("oneshot").unwrap();
        std::thread::sleep(Duration::from_millis(150));
        s.tick(Instant::now());
        assert_eq!(s.infos()[0].state, ServiceState::Failed);
    }

    #[test]
    fn requests_are_answered() {
        let mut state = State {
            supervisor: Supervisor::new(),
            started: Instant::now(),
            accent: "#d71921".into(),
        };
        match handle(&mut state, Request::Ping) {
            Response::Pong { protocol, core } => {
                assert_eq!(protocol, PROTOCOL_VERSION);
                assert_eq!(core, smth_core::CORE_VERSION);
            }
            other => panic!("unexpected {other:?}"),
        }
        match handle(&mut state, Request::ListServices) {
            Response::Services { services } => assert!(services.is_empty()),
            other => panic!("unexpected {other:?}"),
        }
        assert!(matches!(
            handle(
                &mut state,
                Request::Start {
                    name: "ghost".into()
                }
            ),
            Response::Error { .. }
        ));
        assert!(matches!(
            handle(
                &mut state,
                Request::Layout {
                    screen: Rect::new(0, 0, 0, 0),
                    gap: 8,
                    action: LayoutOp::Snap(smth_core::layout::Snap::Left)
                }
            ),
            Response::Error { .. }
        ));
        match handle(
            &mut state,
            Request::AhianPlan {
                seed: Some(1),
                width: 1280,
                height: 720,
            },
        ) {
            Response::AhianPlan { plan } => {
                assert_eq!(plan.bsod.message, smth_core::ahian::AHIAN_MESSAGE);
                assert_eq!(plan.bsod.countdown_seconds, 9);
            }
            other => panic!("unexpected {other:?}"),
        }
    }

    #[test]
    fn layout_matches_the_core() {
        let screen = Rect::new(0, 0, 1440, 900);
        let rect = layout_rect(screen, 8, LayoutOp::Split { panes: 2, index: 0 });
        assert_eq!(rect, Layout::new(screen, 8).split(2, 0));
    }

    #[test]
    fn services_file_validation() {
        let path = std::env::temp_dir().join(format!("smthd-services-{}.json", std::process::id()));
        std::fs::write(&path, r#"{"services":[{"name":"a","command":["true"]}]}"#).unwrap();
        let file = ServicesFile::from_path(&path).unwrap();
        assert_eq!(file.services.len(), 1);
        assert!(file.services[0].restart);
        std::fs::write(&path, r#"{"services":[{"name":"","command":["true"]}]}"#).unwrap();
        assert!(ServicesFile::from_path(&path).is_err());
        std::fs::write(&path, r#"{"services":[{"name":"a","command":[]}]}"#).unwrap();
        assert!(ServicesFile::from_path(&path).is_err());
        assert!(ServicesFile::from_path(Path::new("/nonexistent.json")).is_err());
        assert!(!ServicesFile::builtin().services.is_empty());
        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn palette_accent_falls_back() {
        assert_eq!(accent_from_palette(None), "#d71921");
        let path = std::env::temp_dir().join(format!("smthd-palette-{}.json", std::process::id()));
        std::fs::write(
            &path,
            r##"{"A":"#ff0000","B":"#8c8c8c","AHIAN_A":"#7c4dff","AHIAN_B":"#00c2a8"}"##,
        )
        .unwrap();
        assert_eq!(accent_from_palette(Some(&path)), "#ff0000");
        std::fs::write(&path, "not json").unwrap();
        assert_eq!(accent_from_palette(Some(&path)), "#d71921");
        std::fs::remove_file(&path).ok();
    }
}
