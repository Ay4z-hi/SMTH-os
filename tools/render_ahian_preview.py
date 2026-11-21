#!/usr/bin/env python3
"""Render AHIAN takeover frames to PNG so the animation can be reviewed.

This uses the production renderer (``ahian_scene.SceneRenderer``), the same code
the ISO overlay and the Windows launcher run, so a contact sheet here is what
the animation actually looks like.

    python3 tools/render_ahian_preview.py --profile linux --width 1280 --height 800
    python3 tools/render_ahian_preview.py --all --out artifacts/ahian_preview

Writes one PNG per beat plus ``contact-sheet.png`` (a 4-column montage).
"""
import argparse
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
SMTH_LIB = ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth"
sys.path.insert(0, str(SMTH_LIB))

import ahian_scene  # noqa: E402
import ahian_startup_model as M  # noqa: E402

BEATS = (
    (350, "desktop"),
    (1900, "first errors"),
    (4200, "rising"),
    (6900, "overload"),
    (8800, "storm"),
    (9960, "last frame"),
    (10360, "blue opens"),
    (12600, "countdown 6"),
    (17800, "countdown 1"),
    (19340, "line again"),
    (19640, "wallpaper opens"),
    (20120, "brand"),
    (21500, "elements"),
    (23100, "composed"),
    (24900, "hold"),
)


def beats_for(profile):
    fixed = {t: label for t, label in BEATS}
    return tuple(sorted(fixed.items()))


def label_strip(img, text, height=22):
    strip = Image.new("RGB", (img.width, height), (10, 9, 14))
    draw = ImageDraw.Draw(strip)
    draw.text((8, height / 2), text, fill=(220, 210, 240), anchor="lm")
    out = Image.new("RGB", (img.width, img.height + height))
    out.paste(strip, (0, 0))
    out.paste(img, (0, height))
    return out


def sheet(tiles, columns=4, pad=10):
    if not tiles:
        raise SystemExit("no frames rendered")
    tw, th = tiles[0].width, tiles[0].height
    rows = (len(tiles) + columns - 1) // columns
    out = Image.new("RGB", (columns * tw + pad * (columns + 1),
                            rows * th + pad * (rows + 1)), (6, 6, 9))
    for index, tile in enumerate(tiles):
        col, row = index % columns, index // columns
        out.paste(tile, (pad + col * (tw + pad), pad + row * (th + pad)))
    return out


def render(profile, width, height, out_dir, columns=4, times=None):
    scene = M.StartupScene(width, height, profile=profile)
    renderer = ahian_scene.SceneRenderer(scene)
    out_dir.mkdir(parents=True, exist_ok=True)
    tiles = []
    for t, label in (times or beats_for(profile)):
        image = renderer.render(t)
        path = out_dir / f"{profile}-{t:05d}-{label.replace(' ', '-')}.png"
        image.save(path)
        tiles.append(label_strip(image, f"{profile}  {t} ms  {label}  "
                                        f"[{scene.phase(t)}]"))
    montage = sheet(tiles, columns=columns)
    montage.save(out_dir / f"contact-sheet-{profile}.png")
    print(f"{profile}: {len(tiles)} frames -> {out_dir}")
    print(f"  contact sheet: {out_dir / f'contact-sheet-{profile}.png'}")
    return montage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="linux",
                        choices=list(M.PROFILES))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--out", default="artifacts/ahian_preview")
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--time", type=float, default=None,
                        help="render a single frame at this time")
    args = parser.parse_args()
    out_dir = pathlib.Path(args.out)
    if args.time is not None:
        scene = M.StartupScene(args.width, args.height, profile=args.profile)
        image = ahian_scene.SceneRenderer(scene).render(args.time)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{args.profile}-{int(args.time):05d}.png"
        image.save(path)
        print(path)
        return 0
    profiles = list(M.PROFILES) if args.all else [args.profile]
    for profile in profiles:
        render(profile, args.width, args.height, out_dir, columns=args.columns)
    return 0


if __name__ == "__main__":
    sys.exit(main())
