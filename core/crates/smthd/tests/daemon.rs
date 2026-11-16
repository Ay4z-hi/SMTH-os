//! End-to-end test: start the real `smthd` binary, talk to it over its Unix
//! socket, and verify the protocol, geometry and AHIAN plan end to end.

#![cfg(unix)]

use smth_core::ipc::{LayoutOp, Request, Response};
use smth_core::layout::Rect;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicU32, Ordering};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

/// Tests run in parallel threads of one process, so a socket path keyed only on
/// the pid is shared between them and the two tests fight over it.
static SOCKET_SEQ: AtomicU32 = AtomicU32::new(0);

fn socket_path() -> PathBuf {
    let seq = SOCKET_SEQ.fetch_add(1, Ordering::SeqCst);
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    std::env::temp_dir().join(format!(
        "smthd-test-{}-{now}-{seq}.sock",
        std::process::id()
    ))
}

struct Daemon {
    child: Child,
    socket: PathBuf,
}

impl Daemon {
    fn start() -> Daemon {
        let socket = socket_path();
        let child = Command::new(env!("CARGO_BIN_EXE_smthd"))
            .arg("--socket")
            .arg(&socket)
            .arg("--no-supervise")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .expect("spawn smthd");
        let daemon = Daemon { child, socket };
        let deadline = Instant::now() + Duration::from_secs(10);
        while Instant::now() < deadline {
            if UnixStream::connect(&daemon.socket).is_ok() {
                return daemon;
            }
            std::thread::sleep(Duration::from_millis(25));
        }
        panic!("smthd did not start listening");
    }

    fn call(&self, request: Request) -> Response {
        let mut stream = UnixStream::connect(&self.socket).expect("connect");
        stream
            .write_all(smth_core::ipc::encode(&request).unwrap().as_bytes())
            .expect("write");
        let mut reader = BufReader::new(stream);
        let mut line = String::new();
        reader.read_line(&mut line).expect("read");
        smth_core::ipc::decode_response(&line).expect("decode")
    }
}

impl Drop for Daemon {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
        let _ = std::fs::remove_file(&self.socket);
    }
}

#[test]
fn daemon_serves_the_protocol_over_a_socket() {
    let daemon = Daemon::start();

    match daemon.call(Request::Ping) {
        Response::Pong { protocol, core } => {
            assert_eq!(protocol, smth_core::ipc::PROTOCOL_VERSION);
            assert_eq!(core, smth_core::CORE_VERSION);
        }
        other => panic!("expected pong, got {other:?}"),
    }

    match daemon.call(Request::Status) {
        Response::Status {
            protocol, services, ..
        } => {
            assert_eq!(protocol, smth_core::ipc::PROTOCOL_VERSION);
            assert!(
                services.is_empty(),
                "--no-supervise must not start services"
            );
        }
        other => panic!("expected status, got {other:?}"),
    }

    // Geometry is computed by the shared core, not by the caller.
    let screen = Rect::new(0, 0, 1600, 900);
    match daemon.call(Request::Layout {
        screen,
        gap: 8,
        action: LayoutOp::Snap(smth_core::layout::Snap::Right),
    }) {
        Response::Rect { rect } => {
            assert!(screen.contains(&rect));
            assert_eq!(rect.right(), screen.right());
        }
        other => panic!("expected rect, got {other:?}"),
    }

    match daemon.call(Request::Layout {
        screen,
        gap: 8,
        action: LayoutOp::Split { panes: 2, index: 1 },
    }) {
        Response::Rect { rect } => assert!(screen.contains(&rect)),
        other => panic!("expected rect, got {other:?}"),
    }

    match daemon.call(Request::AhianPlan {
        seed: Some(5),
        width: 1280,
        height: 720,
    }) {
        Response::AhianPlan { plan } => {
            assert_eq!(plan.bsod.message, "wants to make your life beautiful");
            assert_eq!(plan.bsod.countdown_seconds, 9);
            assert!(!plan.dialogs.is_empty());
        }
        other => panic!("expected a plan, got {other:?}"),
    }

    // Unknown services must produce a structured error, not a dropped socket.
    match daemon.call(Request::Start {
        name: "ghost".into(),
    }) {
        Response::Error { message } => assert!(message.contains("unknown service")),
        other => panic!("expected an error, got {other:?}"),
    }

    // Bad input must be reported without killing the connection loop.
    let mut stream = UnixStream::connect(&daemon.socket).unwrap();
    stream.write_all(b"{\"op\":\"nope\"}\n").unwrap();
    let mut line = String::new();
    BufReader::new(stream).read_line(&mut line).unwrap();
    assert!(line.contains("\"result\":\"error\""), "{line}");

    // The daemon is still alive after the bad request.
    assert!(matches!(daemon.call(Request::Ping), Response::Pong { .. }));
}

#[test]
fn second_daemon_on_the_same_socket_is_refused() {
    let daemon = Daemon::start();
    let output = Command::new(env!("CARGO_BIN_EXE_smthd"))
        .arg("--socket")
        .arg(&daemon.socket)
        .arg("--no-supervise")
        .output()
        .expect("run second daemon");
    assert!(
        !output.status.success(),
        "a second daemon must not steal the socket"
    );
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("already served"), "stderr was: {stderr}");
    // The original daemon must still be the one serving the socket.
    assert!(matches!(daemon.call(Request::Ping), Response::Pong { .. }));
}
