#!/usr/bin/env python3
"""Headless tests for the Linux (cairo) and Windows (Tk canvas) renderers.

Neither GTK nor Tk is available on the build host, so this runs the real draw
code against recording surfaces. It catches the failures that compilation
cannot: missing colours, wrong attribute names, exceptions mid-frame, cursor
code creeping back in, and an empty final frame.
"""
import importlib.util
import pathlib
import random
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
SMTH_LIB = ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth"
sys.path.insert(0, str(SMTH_LIB))
import ahian_startup_model as M  # noqa: E402


class FakeCr:
    """Records the cairo calls the Linux renderer makes."""

    class Gradient:
        def __init__(self, *args):
            self.stops = []

        def add_color_stop_rgba(self, *args):
            self.stops.append(args)

    def __init__(self):
        self.ops = []
        self.fills = 0
        self.circles = 0
        self.texts = 0

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.ops.append(name)
            if name == "fill":
                self.fills += 1
            elif name == "arc":
                self.circles += 1
            elif name == "show_text":
                self.texts += 1
        return record


class FakeCairo(types.ModuleType):
    def __init__(self):
        super().__init__("cairo")
        self.LinearGradient = FakeCr.Gradient


class FakeCanvas:
    """Records the Tk canvas items the Windows renderer creates."""

    def __init__(self, width, height):
        self._width = width
        self._height = height
        self.ops = []
        self.texts = []
        self.polygons = 0

    def winfo_width(self):
        return self._width

    def winfo_height(self):
        return self._height

    def delete(self, *_):
        self.ops = []
        self.texts = []

    def create_rectangle(self, *args, **kwargs):
        self.ops.append("rect")

    def create_oval(self, *args, **kwargs):
        self.ops.append("oval")

    def create_line(self, *args, **kwargs):
        self.ops.append("line")

    def create_polygon(self, *args, **kwargs):
        self.polygons += 1
        self.ops.append("polygon")

    def create_text(self, *args, **kwargs):
        self.ops.append("text")
        self.texts.append(str(kwargs.get("text", "")))


def load_windows_launcher():
    tk = types.ModuleType("tkinter")

    class TclError(Exception):
        pass

    tk.TclError = TclError
    for name in ("Tk", "Toplevel", "Canvas", "Frame", "Label", "Button", "Entry",
                 "Text", "StringVar", "Listbox", "Scrollbar", "PhotoImage"):
        setattr(tk, name, object)
    tk.LEFT, tk.RIGHT, tk.TOP, tk.BOTTOM = "left", "right", "top", "bottom"
    tk.X, tk.Y, tk.BOTH, tk.END, tk.NORMAL, tk.DISABLED = "x", "y", "both", "end", "normal", "disabled"
    font = types.ModuleType("tkinter.font")
    font.families = lambda *_: []
    tk.font = font
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.font"] = font
    path = ROOT / "launchers/windows/smth_launcher.py"
    spec = importlib.util.spec_from_file_location("smth_launcher_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def linux_renderer():
    sys.modules["cairo"] = FakeCairo()
    path = SMTH_LIB / "ahian_startup.py"
    spec = importlib.util.spec_from_file_location("ahian_startup_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_linux_draws_every_frame():
    module = linux_renderer()
    assert not hasattr(module.Renderer, "_draw_cursor")
    scene = M.StartupScene(1280, 720, profile="linux")
    renderer = module.Renderer(scene)
    counts = []
    for t in (0, 600, 2000, 3200, 4200, 6000, 8000, 9000):
        renderer.t = t
        cr = FakeCr()
        frame = renderer.draw(cr, 1280, 720)
        assert frame.t_ms == t
        if t > 0:
            assert cr.fills > 0
        counts.append(cr.fills)
    # The assembly gets steadily denser through the structure phase.
    assert counts[0] < counts[2] < counts[5]
    final = FakeCr()
    renderer.t = 6000
    renderer.draw(final, 1280, 720)
    assert final.circles > 200, "wallpaper field and widgets must be drawn"


def test_linux_renderer_has_no_cursor_code():
    source = (SMTH_LIB / "ahian_startup.py").read_text()
    assert "_draw_cursor" not in source
    assert "create_polygon" not in source
    assert "cursors" in source.lower()  # the documented absence, not a drawing


def test_windows_draws_the_same_beats():
    module = load_windows_launcher()
    intro = object.__new__(module.AhianConstructionIntro)
    intro.canvas = FakeCanvas(1280, 720)
    intro.mono = "Courier"
    rng = random.Random(1107)
    intro.fragments = [
        (rng.uniform(0.02, 0.98), rng.uniform(0.02, 0.98),
         rng.uniform(-0.012, 0.012), rng.uniform(-0.020, -0.006),
         rng.choice((module.AHIAN_PURPLE, module.AHIAN_TEAL)))
        for _ in range(36)
    ]
    intro.draw(0.04)
    assert any(op == "oval" for op in intro.canvas.ops), "fragments must be visible"
    intro.draw(0.22)
    assert intro.canvas.ops.count("rect") > 10, "wallpaper tiles must be visible"
    intro.draw(0.45)
    assert any(op == "text" for op in intro.canvas.ops), "taskbar labels must draw"
    intro.draw(0.78)
    for name in ("Files", "Browser", "Terminal", "Settings", "Calculator", "Photos"):
        assert name in intro.canvas.texts, name
    assert intro.canvas.polygons == 0, "no cursors may be drawn"


def test_windows_wallpaper_matches_the_reveal():
    module = load_windows_launcher()
    canvas = FakeCanvas(1280, 720)
    module.paint_ahian_wallpaper(canvas, 1280, 720, tags=("desktop",))
    expected_tiles = module.AHIAN_COLS * module.AHIAN_ROWS
    assert canvas.ops.count("rect") == expected_tiles
    assert canvas.ops.count("oval") == expected_tiles * 9


def test_windows_has_no_cursor_drawing():
    text = (ROOT / "launchers/windows/smth_launcher.py").read_text()
    section = text[text.index("class AhianConstructionIntro:"):]
    assert "create_polygon" not in section
    assert "cursors" in section.lower()  # the documented absence, not a drawing


def main():
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
        except Exception as exc:
            failures += 1
            import traceback
            print(f"FAIL {name}: {exc}")
            traceback.print_exc()
        else:
            print(f"ok   {name}")
    if failures:
        print(f"FAIL ahian renderers: {failures} test(s)")
        return 1
    print("PASS ahian renderers: Linux cairo and Windows Tk draw paths")
    return 0


if __name__ == "__main__":
    sys.exit(main())
