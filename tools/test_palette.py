#!/usr/bin/env python3
"""P0 palette contract and generated-art pixel tests."""
import json, pathlib, sys
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parents[1]
p = json.loads((ROOT / "tools/palette.json").read_text())
assert set(p) == {"A", "B"}, "palette.json must be the only two accent colours"
def rgb(h): return tuple(int(h[i:i+2], 16) for i in (1, 3, 5))
allowed = {(0, 0, 0), rgb(p["A"]), rgb(p["B"])}
base = ROOT / "config/includes.chroot_after_packages"
targets = sorted((base / "usr/share/backgrounds/smth").glob("*.png"))
targets += [base / "usr/share/smth/mark.png", base / "usr/share/smth/logo.png"]
targets += sorted((base / "usr/share/smth/boot").glob("*.png"))
targets += sorted((base / "usr/share/plymouth/themes/smth").glob("*.png"))
missing = [str(x.relative_to(ROOT)) for x in targets if not x.exists()]
if missing: raise SystemExit("missing generated artwork: " + ", ".join(missing))
for path in targets:
    im = Image.open(path).convert("RGB")
    colours = set(im.getdata())
    extra = colours - allowed
    if extra:
        sample = sorted(extra)[:8]
        raise SystemExit(f"{path.relative_to(ROOT)} contains off-palette pixels: {sample}")
    print(f"PASS pixel palette: {path.relative_to(ROOT)} ({len(colours)} colours)")
print("PASS palette contract")
