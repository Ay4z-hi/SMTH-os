#!/usr/bin/env python3
"""Render the SMTH startup logo fade to PNG for review.

Uses the shared ``startup_model`` timing and the shipped logo, so the frames are
the same alpha curve the GTK overlay draws: black, the wordmark, nothing else.
"""
import argparse
import pathlib
import sys

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
SMTH_LIB = ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth"
sys.path.insert(0, str(SMTH_LIB))
import startup_model as M  # noqa: E402

LOGO = ROOT / "config/includes.chroot_after_packages/usr/share/smth/logo.png"
BEATS = (0, 160, 320, 620, 980, 1160, 1360, 1500, 1560)


def label_strip(img, text, height=22):
    strip = Image.new("RGB", (img.width, height), (10, 9, 14))
    ImageDraw.Draw(strip).text((8, height / 2), text,
                               fill=(220, 210, 240), anchor="lm")
    out = Image.new("RGB", (img.width, img.height + height))
    out.paste(strip, (0, 0))
    out.paste(img, (0, height))
    return out


def frame(scene, t, logo):
    canvas = Image.new("RGBA", (int(scene.width), int(scene.height)),
                       (0, 0, 0, 255))
    state = scene.frame(t)
    if state.logo_alpha > 0.001 and logo is not None:
        target = min(scene.width * 0.24, scene.height * 0.23, 220.0)
        art = logo.copy()
        art.thumbnail((int(target), int(target)), Image.LANCZOS)
        if art.width > 1 and art.height > 1:
            art.putalpha(art.getchannel("A").point(
                lambda value: int(value * state.logo_alpha)))
            x = int(scene.width / 2 - art.width / 2)
            y = int(scene.height / 2 - art.height / 2)
            canvas.alpha_composite(art, (x, y))
    return canvas.convert("RGB")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--out", default="artifacts/startup_preview")
    args = parser.parse_args()
    scene = M.StartupScene(args.width, args.height)
    logo = Image.open(LOGO).convert("RGBA") if LOGO.is_file() else None
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tiles = []
    for t in BEATS:
        image = frame(scene, t, logo)
        image.save(out / f"startup-{t:04d}.png")
        state = scene.frame(t)
        tiles.append(label_strip(
            image, f"{t} ms  {state.phase}  logo alpha {state.logo_alpha:.2f}"))
    columns, pad = 3, 10
    tw, th = tiles[0].size
    rows = (len(tiles) + columns - 1) // columns
    montage = Image.new("RGB", (columns * tw + pad * (columns + 1),
                                rows * th + pad * (rows + 1)), (6, 6, 9))
    for index, tile in enumerate(tiles):
        montage.paste(tile, (pad + (index % columns) * (tw + pad),
                             pad + (index // columns) * (th + pad)))
    montage.save(out / "contact-sheet.png")
    print(f"startup: {len(tiles)} frames -> {out / 'contact-sheet.png'}")


if __name__ == "__main__":
    main()
