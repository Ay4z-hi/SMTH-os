#!/usr/bin/env python3
"""Checks the Windows launcher's invisible desktop grid and collision rule."""
import importlib.util
import os
import sys
import types

# The grid helpers do not touch a display, but the launcher imports Tk at module
# scope. Stub just enough for import on a headless host.
tk = types.ModuleType("tkinter")
tk.TclError = Exception
for _name in ("Tk", "Toplevel", "Canvas", "Frame", "PhotoImage", "Label"):
    setattr(tk, _name, object)
font = types.ModuleType("tkinter.font")
font.families = lambda *_args, **_kwargs: []
font.Font = object
sys.modules.setdefault("tkinter", tk)
sys.modules.setdefault("tkinter.font", font)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.join(ROOT, "launchers/windows/smth_launcher.py")

spec = importlib.util.spec_from_file_location("smth_windows_launcher", LAUNCHER)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class FakeCanvas:
    def __init__(self, width, height):
        self._w = width
        self._h = height

    def winfo_width(self):
        return self._w

    def winfo_height(self):
        return self._h


def launcher_for(width=1280, height=800):
    obj = object.__new__(launcher.SMTHLauncher)
    obj.canvas = FakeCanvas(width, height)
    obj.shortcut_positions = {}
    return obj


def main():
    grid = launcher_for()
    cell_w, cell_h, origin_x, origin_y, cols, rows = grid._grid_metrics()
    assert (cell_w, cell_h, origin_x, origin_y) == (100, 86, 20, 20)
    assert cols >= 3 and rows >= 3
    # The 80 x 64 glass tile fits the 100 x 86 cell with a 20 px gutter.
    assert cell_w - 80 >= 20 and cell_h - 64 >= 22

    # A near-miss inside the first cell resolves to that cell's origin.
    assert grid.snap_shortcut("Files", 61, 58) == (origin_x, origin_y)

    # Dropping onto an occupied cell skips to the next free one instead of
    # sharing the box; the returned point is itself a cell origin.
    grid.shortcut_positions = {"Files": (origin_x, origin_y)}
    x, y = grid.snap_shortcut("Browser", origin_x + 2, origin_y + 2)
    assert (x, y) != (origin_x, origin_y)
    assert (x - origin_x) % cell_w == 0 and (y - origin_y) % cell_h == 0
    assert 0 <= (x - origin_x) // cell_w < cols
    assert 0 <= (y - origin_y) // cell_h < rows

    # Adjacent cells never overlap the tile: origin + tile <= next origin.
    assert origin_x + 80 <= origin_x + cell_w
    assert origin_y + 64 <= origin_y + cell_h

    # Every shortcut gets a distinct cell.
    positions = {"Files": (origin_x, origin_y)}
    grid.shortcut_positions = positions
    cells = {(0, 0)}
    for name in ("Browser", "Terminal", "Settings", "Calculator", "Photos"):
        x, y = grid.snap_shortcut(name, origin_x + 4, origin_y + 4)
        cell = ((x - origin_x) // cell_w, (y - origin_y) // cell_h)
        assert cell not in cells, (name, cell)
        cells.add(cell)
        positions[name] = (x, y)

    # Out-of-bounds drops are clamped back into a real cell.
    edge = launcher_for(800, 600)
    x, y = edge.snap_shortcut("Files", 99999, 99999)
    _, _, ox, oy, ecols, erows = edge._grid_metrics()
    assert ox <= x <= ox + (ecols - 1) * cell_w
    assert oy <= y <= oy + (erows - 1) * cell_h

    print("PASS desktop grid: cell origins, no occupied-cell reuse, bounds clamp")


if __name__ == "__main__":
    main()
