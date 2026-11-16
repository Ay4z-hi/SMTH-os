//! Line-delimited JSON protocol between `smthd` and its clients (shell scripts,
//! GTK apps, and launcher bridges).
//!
//! One request object per line, one response object per line, UTF-8. The
//! protocol is versioned so an ISO that ships mismatched binaries fails loudly
//! instead of silently misbehaving.

use crate::ahian::AhianPlan;
use crate::layout::{Rect, Snap};
use serde::{Deserialize, Serialize};
use std::io::{BufRead, Write};

pub const PROTOCOL_VERSION: u32 = 1;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ServiceState {
    Stopped,
    Running,
    Backoff,
    Failed,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ServiceInfo {
    pub name: String,
    pub state: ServiceState,
    pub pid: Option<u32>,
    pub restarts: u32,
    pub last_error: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LayoutOp {
    Cascade {
        index: usize,
        width: u32,
        height: u32,
    },
    Snap(Snap),
    Split {
        panes: u8,
        index: u8,
    },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum Request {
    Ping,
    Status,
    ListServices,
    Start {
        name: String,
    },
    Stop {
        name: String,
    },
    Restart {
        name: String,
    },
    Layout {
        screen: Rect,
        gap: u32,
        action: LayoutOp,
    },
    AhianPlan {
        seed: Option<u64>,
        width: u32,
        height: u32,
    },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "result", rename_all = "snake_case")]
pub enum Response {
    Pong {
        protocol: u32,
        core: String,
    },
    Status {
        uptime_ms: u64,
        services: Vec<ServiceInfo>,
        core: String,
        protocol: u32,
    },
    Services {
        services: Vec<ServiceInfo>,
    },
    Rect {
        rect: Rect,
    },
    AhianPlan {
        plan: AhianPlan,
    },
    Error {
        message: String,
    },
}

#[derive(Debug)]
pub enum CodecError {
    Io(std::io::Error),
    Json(String),
    Disconnected,
}

impl std::fmt::Display for CodecError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CodecError::Io(e) => write!(f, "ipc io error: {e}"),
            CodecError::Json(e) => write!(f, "ipc protocol error: {e}"),
            CodecError::Disconnected => write!(f, "ipc peer disconnected"),
        }
    }
}

impl std::error::Error for CodecError {}

impl From<std::io::Error> for CodecError {
    fn from(e: std::io::Error) -> Self {
        CodecError::Io(e)
    }
}

pub fn encode<T: Serialize>(value: &T) -> Result<String, CodecError> {
    let mut line = serde_json::to_string(value).map_err(|e| CodecError::Json(e.to_string()))?;
    line.push('\n');
    Ok(line)
}

pub fn decode_request(line: &str) -> Result<Request, CodecError> {
    serde_json::from_str(line.trim()).map_err(|e| CodecError::Json(e.to_string()))
}

pub fn decode_response(line: &str) -> Result<Response, CodecError> {
    serde_json::from_str(line.trim()).map_err(|e| CodecError::Json(e.to_string()))
}

/// Write one request and flush it.
pub fn send<W: Write>(writer: &mut W, request: &Request) -> Result<(), CodecError> {
    writer.write_all(encode(request)?.as_bytes())?;
    writer.flush()?;
    Ok(())
}

/// Read one response line.
pub fn receive<R: BufRead>(reader: &mut R) -> Result<Response, CodecError> {
    let mut line = String::new();
    if reader.read_line(&mut line)? == 0 {
        return Err(CodecError::Disconnected);
    }
    decode_response(&line)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn requests_roundtrip() {
        let cases = vec![
            Request::Ping,
            Request::Status,
            Request::ListServices,
            Request::Start {
                name: "notifd".into(),
            },
            Request::Stop {
                name: "moded".into(),
            },
            Request::Restart {
                name: "home".into(),
            },
            Request::Layout {
                screen: Rect::new(0, 0, 1920, 1080),
                gap: 8,
                action: LayoutOp::Split { panes: 2, index: 1 },
            },
            Request::Layout {
                screen: Rect::new(0, 0, 800, 600),
                gap: 4,
                action: LayoutOp::Cascade {
                    index: 5,
                    width: 640,
                    height: 480,
                },
            },
            Request::Layout {
                screen: Rect::new(0, 0, 800, 600),
                gap: 4,
                action: LayoutOp::Snap(Snap::Right),
            },
            Request::AhianPlan {
                seed: Some(7),
                width: 1280,
                height: 720,
            },
        ];
        for req in cases {
            let text = encode(&req).unwrap();
            assert!(text.ends_with('\n'));
            assert_eq!(decode_request(&text).unwrap(), req);
        }
    }

    #[test]
    fn responses_roundtrip_and_reject_garbage() {
        let resp = Response::Pong {
            protocol: PROTOCOL_VERSION,
            core: crate::CORE_VERSION.into(),
        };
        assert_eq!(decode_response(&encode(&resp).unwrap()).unwrap(), resp);
        assert!(decode_response("{\"result\":\"nope\"}").is_err());
        assert!(decode_request("{not json").is_err());
        assert!(decode_request("\"just a string\"").is_err());
    }

    #[test]
    fn stream_helpers_detect_disconnect() {
        let mut buf = Vec::new();
        send(&mut buf, &Request::Ping).unwrap();
        assert_eq!(
            decode_request(std::str::from_utf8(&buf).unwrap()).unwrap(),
            Request::Ping
        );
        let mut empty: &[u8] = b"";
        assert!(matches!(receive(&mut empty), Err(CodecError::Disconnected)));
        let mut one = &b"{\"result\":\"pong\",\"protocol\":1,\"core\":\"0.1.0\"}\n"[..];
        assert!(matches!(receive(&mut one), Ok(Response::Pong { .. })));
    }

    #[test]
    fn wire_format_is_stable() {
        // The launchers and shell scripts parse this, so pin the shape.
        assert_eq!(
            encode(&Request::Start { name: "x".into() }).unwrap(),
            "{\"op\":\"start\",\"name\":\"x\"}\n"
        );
        assert!(encode(&Request::Ping).unwrap().contains("\"op\":\"ping\""));
    }
}
