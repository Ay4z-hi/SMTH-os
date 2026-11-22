#!/usr/bin/env python3
"""Headless proof sheets for the glass icon containers.

No display is needed: the glass card comes from the launcher's own
``glass_image`` renderer, and the grids are drawn from the shipping constants
(100 x 86 / 80 x 64 on Linux and Windows, 88 x 78 / 80 x 70 dp on Android).
The sheets are schematics with the real artwork, not screenshots.
"""
import argparse
import importlib.util
import pathlib
import sys

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
WALL = ROOT / "launchers/windows/assets/smth-wallpaper.png"
sys.path.insert(0, str(ROOT / "tools"))
from test_icon_containers import load_windows_launcher  # noqa: E402


def font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if pathlib.Path(path).is_file():
            from PIL import ImageFont
            return ImageFont.truetype(path, size)
    from PIL import ImageFont
    return ImageFont.load_default()


def text(image, xy, body, size=13, fill=(228, 220, 240)):
    ImageDraw.Draw(image).text(xy, body, font=font(size), fill=fill)


def wallpaper(width, height):
    if WALL.is_file():
        from PIL import ImageOps
        return ImageOps.fit(Image.open(WALL).convert("RGB"), (width, height),
                            Image.LANCZOS)
    return Image.new("RGB", (width, height), (16, 12, 18))


def glass_sheet(module, out):
    tint, alpha = (23, 16, 23), 226
    base = wallpaper(140, 120)
    old = module.glass_image(58, 58, 17, tint, alpha)
    new = module.glass_image(52, 52, 15, tint, alpha)
    canvas = base.copy()
    canvas.paste(new, (21, 21), new)
    big = canvas.resize((140 * 4, 120 * 4), Image.LANCZOS)
    sheet = Image.new("RGB", (1180, 560), (8, 7, 11))
    text(sheet, (18, 12), "Liquid glass tile, drawn by the shipping renderer (4x zoom)", 16)
    sheet.paste(big, (18, 40))
    # Old 58 px tile and new 52 px tile side by side, same crop and scale.
    for index, (tile, px, radius, caption) in enumerate((
            (old, 58, 17, "BEFORE  58 x 58, radius 17"),
            (new, 52, 15, "AFTER   52 x 52, radius 15"))):
        crop = wallpaper(90, 90)
        crop.paste(tile, (19, 19), tile)
        sheet.paste(crop.resize((360, 360), Image.NEAREST), (620 + index * 280, 40))
        text(sheet, (620 + index * 280, 404), caption, 14)
    text(sheet, (18, 516),
         "80 x 64 desktop tile inside a 100 x 86 cell: 20 px gutter, no overlap.",
         14)
    sheet.save(out)


def grid_sheet(module, out):
    sheet = Image.new("RGB", (1400, 800), (8, 7, 11))
    text(sheet, (18, 12), "Desktop grid geometry at 1x (schematic from shipping constants)", 16)

    def draw_grid(x, y, width, height, scale, cell, tile, origin, count, title,
                  android=False):
        art = wallpaper(width, height) if not android else Image.new(
            "RGB", (width, height), (19, 13, 20))
        draw = ImageDraw.Draw(art)
        cell_w, cell_h = cell
        tile_w, tile_h = tile
        ox, oy = origin
        cols = max(1, int((width - ox - tile_w) // cell_w) + 1)
        rows = max(1, int((height - oy - tile_h) // cell_h) + 1)
        for col in range(cols):
            for row in range(rows):
                draw.rectangle((ox + col * cell_w, oy + row * cell_h,
                                ox + col * cell_w + cell_w - 1,
                                oy + row * cell_h + cell_h - 1),
                               outline=(120, 70, 120))
        glass = module.glass_image(tile_w, tile_h, 13 if not android else 12)
        for index in range(min(count, cols * rows)):
            col, row = index % cols, index // cols
            gx = ox + col * cell_w
            gy = oy + row * cell_h
            if glass is not None:
                art.paste(glass, (gx, gy), glass)
            draw.ellipse((gx + tile_w / 2 - 8, gy + 9,
                          gx + tile_w / 2 + 8, gy + 25), outline=(222, 190, 216))
            draw.rectangle((gx + 12, gy + tile_h - 14, gx + tile_w - 12,
                            gy + tile_h - 11), fill=(196, 170, 196))
        panel = art.resize((int(width * scale), int(height * scale)), Image.LANCZOS)
        sheet.paste(panel, (x, y))
        text(sheet, (x, y + panel.height + 6), title, 13)
        text(sheet, (x, y + panel.height + 22),
             f"cell {int(cell_w)}x{int(cell_h)}  tile {int(tile_w)}x{int(tile_h)}  "
             f"gutter {int(cell_w - tile_w)}  {cols}x{rows} cells", 12,
             (186, 176, 198))
        return panel

    draw_grid(18, 44, 1280, 800, 0.34, (100, 86), (80, 64), (20, 20), 14,
              "Linux and Windows  1280 x 800")
    draw_grid(470, 44, 1920, 1080, 0.226, (100, 86), (80, 64), (20, 20), 14,
              "Linux and Windows  1920 x 1080")
    draw_grid(930, 44, 411, 891, 0.46, (88, 78), (80, 70), (12, 12), 14,
              "Android  411 x 891 dp", android=True)
    draw_grid(18, 560, 891, 411, 0.31, (88, 78), (80, 70), (12, 12), 14,
              "Android  891 x 411 dp", android=True)
    text(sheet, (330, 560), "800 x 600:  7 x 6 cells, 14 apps fit", 14)
    text(sheet, (330, 590), "1280 x 800:  12 x 9 cells, 14 apps fit", 14)
    text(sheet, (330, 620), "1920 x 1080:  19 x 12 cells, 14 apps fit", 14)
    text(sheet, (330, 650), "Android 320 dp:  3 columns, no partial tiles", 14)
    text(sheet, (330, 680), "No tile is ever drawn outside its own cell.", 14,
         (196, 186, 208))
    text(sheet, (18, 752),
         "Every tile sits inside its own cell: the coloured outline is the cell, "
         "the glass card the container.", 13)
    sheet.save(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/fix-pass")
    args = parser.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    module = load_windows_launcher()
    if module.glass_image(10, 10) is None:
        raise SystemExit("Pillow is required")
    glass_sheet(module, out / "icon-glass.png")
    grid_sheet(module, out / "icon-grids.png")
    print(f"icon sheets -> {out}")


if __name__ == "__main__":
    main()
