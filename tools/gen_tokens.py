#!/usr/bin/env python3
"""Generate runtime palette and GTK/CSS tokens from the single source: tools/palette.json.

Keys: A/B (core accents) and AHIAN_A/AHIAN_B (AHIAN-mode accents). Typography is
bundled offline in usr/share/fonts/truetype/smth, so the token file also records
the font families the shell must use.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PALETTE = ROOT / "tools" / "palette.json"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config/includes.chroot_after_packages"
KEYS = ("A", "B", "AHIAN_A", "AHIAN_B")
p = json.loads(PALETTE.read_text(encoding="utf-8"))

def valid(value):
    return (isinstance(value, str) and len(value) == 7 and value[0] == "#"
            and all(c in "0123456789abcdefABCDEF" for c in value[1:]))

if set(p) != set(KEYS) or not all(valid(p[k]) for k in KEYS):
    raise SystemExit("palette.json must contain exactly A, B, AHIAN_A and AHIAN_B as #RRGGBB")

a, b, aa, ab = (p[k].lower() for k in KEYS)
lib = OUT / "usr/local/lib/smth"
gtk = OUT / "etc/skel/.config/gtk-4.0"
lib.mkdir(parents=True, exist_ok=True)
gtk.mkdir(parents=True, exist_ok=True)
(lib / "palette.json").write_text(
    json.dumps({"A": a, "B": b, "AHIAN_A": aa, "AHIAN_B": ab}, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
(gtk / "smth-tokens.css").write_text(
    "/* Generated from tools/palette.json. Do not edit. */\n"
    "@define-color smth_black #000000;\n"
    "@define-color smth_white #ffffff;\n"
    "@define-color smth_grey #f2c6d2;\n"
    f"@define-color smth_a {a};\n"
    f"@define-color smth_b {b};\n"
    f"@define-color smth_ahian_a {aa};\n"
    f"@define-color smth_ahian_b {ab};\n"
    "@define-color accent_bg_color @smth_a;\n"
    "@define-color accent_color @smth_a;\n",
    encoding="utf-8",
)
(gtk / "smth-typography.css").write_text(
    "/* Generated from tools/palette.json. Bundled offline: no network fonts. */\n"
    "* { font-family: \"Space Mono\", \"Doto\", \"DotGothic16\", monospace; }\n"
    "h1, h2, h3, .title-1, .title-2, .title-3, .heading { font-family: \"Doto\", \"Space Mono\", monospace; }\n",
    encoding="utf-8",
)
print(f"tokens generated: A={a} B={b} AHIAN_A={aa} AHIAN_B={ab}")
