#!/usr/bin/env python3
"""Swap SMTH accent colours everywhere in text assets, then regenerate artwork."""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PALETTE = ROOT / "tools/palette.json"
if len(sys.argv) != 3:
    raise SystemExit("usage: tools/recolor.py '#RRGGBB' '#RRGGBB'")

def valid(value):
    return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", value))

new_a, new_b = sys.argv[1].lower(), sys.argv[2].lower()
if not valid(new_a) or not valid(new_b) or new_a == new_b:
    raise SystemExit("A and B must be two different #RRGGBB colours")

old = json.loads(PALETTE.read_text(encoding="utf-8"))
pairs = {old["A"].lower(): new_a, old["B"].lower(): new_b}
skip = {".git", ".github", ".png", ".zip", ".pf2", ".iso", ".woff", ".ttf", ".otf"}
for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in skip for part in path.parts):
        continue
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    updated = source
    for before, after in pairs.items():
        updated = re.sub(re.escape(before), after, updated, flags=re.IGNORECASE)
    if updated != source:
        path.write_text(updated, encoding="utf-8")

PALETTE.write_text(json.dumps({"A": new_a, "B": new_b}, indent=2) + "\n", encoding="utf-8")
subprocess.run([sys.executable, str(ROOT / "tools/gen_tokens.py")], check=True)
subprocess.run([sys.executable, str(ROOT / "tools/gen_assets.py"),
                str(ROOT / "config/includes.chroot_after_packages")], check=True)
subprocess.run([sys.executable, str(ROOT / "tools/gen_cursor.py"),
                str(ROOT / "config/includes.chroot_after_packages")], check=True)
print(f"recoloured to A={new_a} B={new_b}")
