#!/usr/bin/env python3
"""Cross-platform icon container geometry.

The glass tile behind a desktop or launcher icon has one job: hold the icon and
its label without clipping, and never touch the neighbouring tile.  These
checks read the real numbers out of the three implementations and exercise them
at portrait, landscape and desktop widths.
"""
import importlib.util
import pathlib
import re
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
INC = ROOT / "config/includes.chroot_after_packages"
ANDROID = ROOT / "launchers/android/app/src/main/kotlin/os/smth/launcher/MainActivity.kt"
WINDOWS = ROOT / "launchers/windows/smth_launcher.py"


def nums(pattern, text):
    match = re.search(pattern, text, re.S)
    assert match, pattern
    return tuple(float(group) for group in match.groups())


def test_linux_desktop_tiles_fit_their_cells():
    home = (INC / "usr/local/lib/smth/home.py").read_text()
    cell_w, cell_h, grid_x, grid_y = nums(
        r"CELL_W, CELL_H, GRID_X, GRID_Y = ([\d.]+), ([\d.]+), ([\d.]+), ([\d.]+)",
        home)
    icon_w, icon_h = nums(r"ICON_W, ICON_H = ([\d.]+), ([\d.]+)", home)
    min_w, min_h = nums(r"min-width: (\d+)px;\n  min-height: (\d+)px;", home)
    radius = nums(r"\.home button\.app \{.*?border-radius: (\d+)px", home)[0]
    pixel = nums(r"img\.set_pixel_size\((\d+)\)", home)[0]
    pad_v, pad_h = nums(r"padding: (\d+)px (\d+)px", home)

    # The tile is the 80 x 64 box the grid math already uses.
    assert (min_w, min_h) == (icon_w, icon_h) == (80.0, 64.0)
    assert pad_h * 2 + pixel <= min_w, "the image plus padding must fit the tile"
    assert pad_v * 2 + pixel + 14 <= min_h, "image, padding and label must fit"
    assert radius * 2 <= min(min_w, min_h), "the radius cannot exceed the tile"
    assert cell_w - icon_w >= 20 and cell_h - icon_h >= 20, "a 20 px gutter"

    # The grid never puts two tiles in one cell, and two columns hold all
    # fourteen desktop apps at the smallest supported screen.
    for width, height in ((800, 600), (1280, 800), (1920, 1080), (2560, 1080)):
        cols = max(1, int(max(1, width - grid_x - icon_w) // cell_w) + 1)
        rows = max(1, int(max(1, height - grid_y - icon_h) // cell_h) + 1)
        assert cols * rows >= 14, (width, height, cols, rows)
        assert cols >= 2, (width, height, cols)


def test_linux_launcher_pins_fit():
    launcher = (INC / "usr/local/lib/smth/launcher.py").read_text()
    width, height = nums(r"b\.set_size_request\((\d+), (\d+)\)", launcher)
    icon = nums(r"img\.set_pixel_size\((\d+)\)", launcher)[0]
    pad = nums(r"button\.pin \{.*?padding: (\d+)px", launcher)[0]
    radius = nums(r"button\.pin \{.*?border-radius: (\d+)px", launcher)[0]
    assert (width, height) == (56.0, 54.0)
    assert icon + pad * 2 <= width
    assert icon + pad * 2 + 14 <= height
    assert radius * 2 <= min(width, height)


def load_windows_launcher():
    tk = types.ModuleType("tkinter")
    tk.TclError = Exception
    for name in ("Tk", "Toplevel", "Canvas", "Frame", "PhotoImage", "Label",
                 "Button", "Entry", "Text", "StringVar", "Listbox", "Scrollbar"):
        setattr(tk, name, object)
    tk.LEFT = tk.RIGHT = tk.TOP = tk.BOTTOM = "x"
    tk.X = tk.Y = tk.BOTH = tk.END = "x"
    tk.NORMAL = tk.DISABLED = "normal"
    font = types.ModuleType("tkinter.font")
    font.families = lambda *_: []
    tk.font = font
    sys.modules.setdefault("tkinter", tk)
    sys.modules.setdefault("tkinter.font", font)
    spec = importlib.util.spec_from_file_location(
        "icon_launcher_under_test", WINDOWS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_windows_tiles_fit_at_every_window_size():
    module = load_windows_launcher()
    source = WINDOWS.read_text()
    tile, _, radius = nums(
        r"glass_photo\((\d+), (\d+), (\d+)\)\n            if photo", source)
    glyph = nums(r"draw_glyph\(c, glyph, x \+ (\d+), y \+ (\d+), (\d+)", source)[2]
    assert (tile, radius) == (52.0, 15.0), "the old tile was 58 px at radius 17"
    assert glyph < tile, "the glyph must fit inside the glass"

    class Canvas:
        def __init__(self, width, height):
            self._w, self._h = width, height

        def winfo_width(self):
            return self._w

        def winfo_height(self):
            return self._h

    for width, height in ((820, 560), (1100, 700), (1280, 800), (1920, 1080),
                          (2560, 1080), (1080, 1920)):
        obj = object.__new__(module.SMTHLauncher)
        obj.canvas = Canvas(width, height)
        obj.shortcut_positions = {}
        cell_w, cell_h, origin_x, origin_y, cols, rows = obj._grid_metrics()
        assert cell_w - 80 >= 20, (width, cell_w)
        assert cell_h - 64 >= 20, (height, cell_h)
        assert cell_w > tile and cell_h > 64
        assert cols >= 2 and rows >= 2, (width, height, cols, rows)
        # Six desktop shortcuts all land in different cells with a real gutter.
        cells = set()
        for name in ("Files", "Browser", "Terminal", "Settings", "Calculator", "Photos"):
            x, y = obj.snap_shortcut(name, origin_x + 3, origin_y + 3)
            cell = (round((x - origin_x) / cell_w), round((y - origin_y) / cell_h))
            assert cell not in cells
            cells.add(cell)
            obj.shortcut_positions[name] = (x, y)
            assert x + 80 <= origin_x + (cols - 1) * cell_w + 80
            assert x + 80 <= width


def test_android_tiles_fit_portrait_and_landscape():
    source = ANDROID.read_text()
    desktop = source[source.index("private fun rebuildDesktop()"):
                     source.index("private fun snapDesktopCell")]
    icon_block = source[source.index("private fun desktopIcon("):
                        source.index("/** Resolve a dropped shortcut")]
    start_pinned = source[source.index("private fun rebuildStartPinned()"):
                          source.index("private fun gridColumns")]
    all_apps = source[source.index("private fun renderAll()"):
                      source.index("// ---- data")]

    cell_w, cell_h = nums(r"val cellW = dp\((\d+)\)\n        val cellH = dp\((\d+)\)",
                          desktop)
    origin = nums(r"val originX = dp\((\d+)\)", desktop)[0]
    tile_w, tile_h = nums(r"FrameLayout\.LayoutParams\(dp\((\d+)\), dp\((\d+)\)\)\.apply",
                          desktop)
    icon = nums(r"LinearLayout\.LayoutParams\(dp\((\d+)\), dp\((\d+)\)\)\)", icon_block)[0]
    label_w = nums(r"LinearLayout\.LayoutParams\(dp\((\d+)\), ViewGroup\.LayoutParams\.WRAP_CONTENT\)",
                   icon_block)[0]
    start_tile = nums(
        r"pinnedBox\.addView\(item, LinearLayout\.LayoutParams\(dp\((\d+)\), dp\((\d+)\)\)\)",
        start_pinned)
    all_width = nums(r"val width = dp\((\d+)\)\n        shown", all_apps)[0]
    all_tile = nums(r"height = dp\((\d+)\)\n                columnSpec", all_apps)[0]

    assert (cell_w, cell_h, origin) == (88.0, 78.0, 12.0)
    assert (tile_w, tile_h) == (80.0, 70.0)
    assert tile_w < cell_w and tile_h < cell_h, "the tile is smaller than its cell"
    assert cell_w - tile_w >= 8 and cell_h - tile_h >= 8, "a real gutter"
    assert icon == 28.0 and icon + 6 <= tile_w
    assert label_w <= tile_w - 6, "the label cannot be wider than the tile"
    assert start_tile == (56.0, 54.0), "launcher pinned tiles are compact"
    assert all_width <= 56.0 and all_tile <= 54.0
    assert "glassTile(13f)" in source
    assert "dp(96)" not in desktop and "dp(32)" not in icon_block

    # Every Android width from a small phone to a desktop window keeps a
    # whole number of non-overlapping cells.
    for width_dp in (320, 360, 411, 600, 800, 1280):
        cols = max(1, (width_dp - origin) // cell_w)
        assert cols >= 1
        assert cols * cell_w + origin <= width_dp or cols == 1
        assert cols * tile_w + (cols - 1) * (cell_w - tile_w) <= width_dp


def main():
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
        except Exception as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
        else:
            print(f"ok   {name}")
    if failures:
        print(f"FAIL icon containers: {failures} test(s)")
        return 1
    print("PASS icon containers: Linux, Windows and Android fit at every size")
    return 0


if __name__ == "__main__":
    sys.exit(main())
