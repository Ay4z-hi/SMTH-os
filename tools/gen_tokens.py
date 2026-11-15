#!/usr/bin/env python3
"""Generate runtime palette and GTK/CSS tokens from the single source: tools/palette.json."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PALETTE = ROOT / "tools" / "palette.json"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "config/includes.chroot_after_packages"
p = json.loads(PALETTE.read_text(encoding="utf-8"))

def valid(value):
    return (isinstance(value, str) and len(value) == 7 and value[0] == "#"
            and all(c in "0123456789abcdefABCDEF" for c in value[1:]))

if set(p) != {"A", "B"} or not all(valid(p[k]) for k in ("A", "B")):
    raise SystemExit("palette.json must contain only A and B as #RRGGBB")

a, b = p["A"].lower(), p["B"].lower()
lib = OUT / "usr/local/lib/smth"
gtk = OUT / "etc/skel/.config/gtk-4.0"
lib.mkdir(parents=True, exist_ok=True)
gtk.mkdir(parents=True, exist_ok=True)
(lib / "palette.json").write_text(
    json.dumps({"A": a, "B": b}, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
(gtk / "smth-tokens.css").write_text(
    "/* Generated from tools/palette.json. Do not edit. */\n"
    "@define-color smth_black #000000;\n"
    "@define-color smth_white #ffffff;\n"
    f"@define-color smth_a {a};\n"
    f"@define-color smth_b {b};\n",
    encoding="utf-8",
)
print(f"tokens generated: A={a} B={b}")
