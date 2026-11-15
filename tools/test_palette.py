#!/usr/bin/env python3
"""P0 palette contract and generated-art pixel tests."""
import json, pathlib, sys
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parents[1]
p = json.loads((ROOT / "tools/palette.json").read_text())
assert set(p) == {"A", "B"}, "palette.json must be the only two accent colours"
def rgb(h): return tuple(int(h[i:i+2], 16) for i in (1, 3, 5))
allowed = {(0, 0, 0), rgb(p["A"]), rgb(p["B"])}
targets = [
 ROOT / "config/includes.chroot_after_packages/usr/share/backgrounds/smth/wallpaper.png",
 ROOT / "config/includes.chroot_after_packages/usr/share/backgrounds/smth/lock.png",
 ROOT / "config/includes.chroot_after_packages/usr/share/smth/mark.png",
 ROOT / "config/includes.chroot_after_packages/usr/share/smth/logo.png",
]
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
