#!/usr/bin/env python3
"""Palette contract, generated-art pixel and offline-font tests.

Contract (see docs/architecture/phase-0.md):
* core UI and core artwork use #000000, white text, grey #8c8c8c and the red accent A;
* AHIAN artwork uses only black and the purple/teal pair, never the core pair;
* the required fonts are bundled in the image (no network fetch at runtime).
"""
import json, pathlib, sys
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
p = json.loads((ROOT / "tools/palette.json").read_text())
assert set(p) == {"A", "B", "AHIAN_A", "AHIAN_B"}, "palette.json is the only palette source"

def rgb(h): return tuple(int(h[i:i+2], 16) for i in (1, 3, 5))

BLACK = (0, 0, 0)
core_allowed = {BLACK, rgb(p["A"]), rgb(p["B"])}
ahian_allowed = {BLACK, rgb(p["AHIAN_A"]), rgb(p["AHIAN_B"])}

base = ROOT / "config/includes.chroot_after_packages"
bg = base / "usr/share/backgrounds/smth"
ahian_files = {bg / "ahian-teal.png"}
targets = sorted(bg.glob("*.png"))
targets += [base / "usr/share/smth/mark.png", base / "usr/share/smth/logo.png"]
targets += sorted((base / "usr/share/smth/boot").glob("*.png"))
targets += sorted((base / "usr/share/plymouth/themes/smth").glob("*.png"))

missing = [str(x.relative_to(ROOT)) for x in targets if not x.exists()]
if missing:
    raise SystemExit("missing generated artwork: " + ", ".join(missing))

# The official SMTH logo is a shaded 3D brand asset (transparent PNG) and is
# exempt from the flat palette contract; only its existence is checked.
logo_exemptions = {
    base / "usr/share/smth/mark.png",
    base / "usr/share/smth/logo.png",
    base / "usr/share/smth/startup-logo.png",
    base / "usr/share/plymouth/themes/smth/logo.png",
}
for path in targets:
    if path in logo_exemptions:
        print(f"PASS official logo asset present: {path.relative_to(ROOT)}")
        continue
    allowed = ahian_allowed if path in ahian_files else core_allowed
    colours = set(Image.open(path).convert("RGB").getdata())
    extra = colours - allowed
    if extra:
        raise SystemExit(f"{path.relative_to(ROOT)} contains off-palette pixels: {sorted(extra)[:8]}")
    print(f"PASS pixel palette: {path.relative_to(ROOT)} ({len(colours)} colours)")

# Required offline fonts, with their licenses, must actually ship.
font_dir = base / "usr/share/fonts/truetype/smth"
required = ["SpaceMono-Regular.ttf", "SpaceMono-Bold.ttf", "Doto.ttf", "DotGothic16-Regular.ttf"]
for name in required:
    f = font_dir / name
    if not f.is_file() or f.stat().st_size < 20_000:
        raise SystemExit(f"missing bundled font: {f.relative_to(ROOT)}")
for name in ["OFL-SpaceMono.txt", "OFL-Doto.txt", "OFL-DotGothic16.txt"]:
    if not (font_dir / name).is_file():
        raise SystemExit(f"missing license for bundled font: {name}")
print(f"PASS bundled fonts: {len(required)} files + licenses")

# AHIAN wallpaper must exist for the Rust plan's hard-coded path.
if not (bg / "ahian-teal.png").is_file():
    raise SystemExit("AHIAN wallpaper is missing: usr/share/backgrounds/smth/ahian-teal.png")

print("PASS palette contract")
