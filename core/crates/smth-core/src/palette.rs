//! Palette contract.
//!
//! `tools/palette.json` remains the only palette source for the repository.
//! This module is the runtime parser so the shell, the Rust daemon and the
//! launchers agree on the exact same values and validation rules.
//!
//! Contract:
//! * `A` / `B` are the accent pair used by the core UI and the dot artwork.
//! * `AHIAN_A` / `AHIAN_B` are the purple/teal pair used only by AHIAN mode.
//! * Every value must be `#rrggbb`.

use serde::{Deserialize, Serialize};
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PaletteError {
    Json(String),
    Missing(&'static str),
    BadHex(&'static str, String),
}

impl fmt::Display for PaletteError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            PaletteError::Json(e) => write!(f, "palette is not valid JSON: {e}"),
            PaletteError::Missing(k) => write!(f, "palette is missing required key {k}"),
            PaletteError::BadHex(k, v) => write!(f, "palette key {k} is not #rrggbb: {v}"),
        }
    }
}

impl std::error::Error for PaletteError {}

/// A parsed `#rrggbb` colour.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Rgb {
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

impl Rgb {
    pub fn parse(value: &str) -> Option<Rgb> {
        let hex = value.strip_prefix('#')?;
        if hex.len() != 6 || !hex.chars().all(|c| c.is_ascii_hexdigit()) {
            return None;
        }
        Some(Rgb {
            r: u8::from_str_radix(&hex[0..2], 16).ok()?,
            g: u8::from_str_radix(&hex[2..4], 16).ok()?,
            b: u8::from_str_radix(&hex[4..6], 16).ok()?,
        })
    }

    pub fn to_hex(self) -> String {
        format!("#{:02x}{:02x}{:02x}", self.r, self.g, self.b)
    }

    /// Relative luminance (sRGB, 0.0..=1.0), used to keep generated UI text
    /// readable without introducing extra palette colours.
    pub fn luminance(self) -> f64 {
        let f = |c: u8| {
            let c = c as f64 / 255.0;
            if c <= 0.039_28 {
                c / 12.92
            } else {
                ((c + 0.055) / 1.055).powf(2.4)
            }
        };
        0.2126 * f(self.r) + 0.7152 * f(self.g) + 0.0722 * f(self.b)
    }

    /// Whether white or black text is more legible on this colour.
    ///
    /// 0.179 is the WCAG crossover point where black and white text have equal
    /// contrast; above it black wins, below it white wins.
    pub fn prefers_black_text(self) -> bool {
        self.luminance() > 0.179
    }
}

/// The four-colour contract: two core accents, two AHIAN accents.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Palette {
    pub a: Rgb,
    pub b: Rgb,
    pub ahian_a: Rgb,
    pub ahian_b: Rgb,
    /// Raw hex strings in canonical lowercase, for CSS/token generation.
    pub raw_a: String,
    pub raw_b: String,
    pub raw_ahian_a: String,
    pub raw_ahian_b: String,
}

impl Palette {
    pub fn from_json(text: &str) -> Result<Palette, PaletteError> {
        let value: serde_json::Value =
            serde_json::from_str(text).map_err(|e| PaletteError::Json(e.to_string()))?;
        let obj = value
            .as_object()
            .ok_or_else(|| PaletteError::Json("expected an object".into()))?;
        let get = |key: &'static str| -> Result<(Rgb, String), PaletteError> {
            let raw = obj
                .get(key)
                .and_then(|v| v.as_str())
                .ok_or(PaletteError::Missing(key))?;
            let rgb = Rgb::parse(raw).ok_or_else(|| PaletteError::BadHex(key, raw.to_string()))?;
            Ok((rgb, rgb.to_hex()))
        };
        let (a, raw_a) = get("A")?;
        let (b, raw_b) = get("B")?;
        let (ahian_a, raw_ahian_a) = get("AHIAN_A")?;
        let (ahian_b, raw_ahian_b) = get("AHIAN_B")?;
        Ok(Palette {
            a,
            b,
            ahian_a,
            ahian_b,
            raw_a,
            raw_b,
            raw_ahian_a,
            raw_ahian_b,
        })
    }

    /// The core accent pair, in the order used by dot artwork.
    pub fn core_pair(&self) -> [Rgb; 2] {
        [self.a, self.b]
    }

    /// The AHIAN pair, used only while AHIAN mode is active.
    pub fn ahian_pair(&self) -> [Rgb; 2] {
        [self.ahian_a, self.ahian_b]
    }

    /// GTK token block generated into `smth-tokens.css`.
    pub fn tokens_css(&self) -> String {
        format!(
            "/* Generated from tools/palette.json. Do not edit. */\n\
             @define-color smth_black #000000;\n\
             @define-color smth_white #ffffff;\n\
             @define-color smth_grey #8c8c8c;\n\
             @define-color smth_a {};\n\
             @define-color smth_b {};\n\
             @define-color smth_ahian_a {};\n\
             @define-color smth_ahian_b {};\n",
            self.raw_a, self.raw_b, self.raw_ahian_a, self.raw_ahian_b
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const JSON: &str = r##"{"A":"#d71921","B":"#8c8c8c","AHIAN_A":"#7c4dff","AHIAN_B":"#00c2a8"}"##;

    #[test]
    fn parses_the_contract() {
        let p = Palette::from_json(JSON).expect("valid palette");
        assert_eq!(
            p.a,
            Rgb {
                r: 0xd7,
                g: 0x19,
                b: 0x21
            }
        );
        assert_eq!(
            p.ahian_b,
            Rgb {
                r: 0x00,
                g: 0xc2,
                b: 0xa8
            }
        );
        assert_eq!(p.core_pair(), [p.a, p.b]);
        assert!(p
            .tokens_css()
            .contains("@define-color smth_ahian_b #00c2a8;"));
    }

    #[test]
    fn rejects_bad_values() {
        assert!(matches!(
            Palette::from_json(r##"{"A":"#12345"}"##),
            Err(PaletteError::BadHex("A", _))
        ));
        assert!(matches!(
            Palette::from_json(r##"{"A":"#d71921","B":"#8c8c8c","AHIAN_A":"#7c4dff"}"##),
            Err(PaletteError::Missing("AHIAN_B"))
        ));
        assert!(matches!(
            Palette::from_json("not json"),
            Err(PaletteError::Json(_))
        ));
        assert!(Palette::from_json("[]").is_err());
    }

    #[test]
    fn normalises_case() {
        let p = Palette::from_json(
            r##"{"A":"#D71921","B":"#8C8C8C","AHIAN_A":"#7C4DFF","AHIAN_B":"#00C2A8"}"##,
        )
        .unwrap();
        assert_eq!(p.raw_a, "#d71921");
        assert_eq!(p.raw_ahian_a, "#7c4dff");
    }

    #[test]
    fn contrast_rule() {
        assert!(Rgb::parse("#ffffff").unwrap().prefers_black_text());
        assert!(!Rgb::parse("#000000").unwrap().prefers_black_text());
        assert!(!Rgb::parse("#d71921").unwrap().prefers_black_text());
        assert!(Rgb::parse("#8c8c8c").unwrap().prefers_black_text());
        assert!(Rgb::parse("#d7192").is_none());
        assert!(Rgb::parse("d71921").is_none());
        assert!(Rgb::parse("#gggggg").is_none());
    }
}
