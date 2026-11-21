#!/usr/bin/env python3
"""Headless visual tests for the AHIAN takeover renderers.

This exercises the real drawing code with Pillow on every platform profile and
checks the things compilation cannot: that frames actually render, that each act
looks different, that the crash screen is blue, that the finished desktop is the
AHIAN palette, that text is never ghosted, and that a frame is fast enough for a
30 fps reveal.  The Windows launcher and the Linux overlay are loaded from their
real sources; the shared renderer is the exact code both of them run.
"""
import importlib.util
import pathlib
import sys
import time
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
SMTH_LIB = ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth"
sys.path.insert(0, str(SMTH_LIB))

from PIL import Image, ImageStat  # noqa: E402
import ahian_scene  # noqa: E402
import ahian_startup_model as M  # noqa: E402

CACHE = {}


def renderer(profile="linux", width=1280, height=800):
    key = (profile, width, height)
    if key not in CACHE:
        scene = M.StartupScene(width, height, profile=profile)
        CACHE[key] = ahian_scene.SceneRenderer(scene)
    return CACHE[key]


def mean(image, box=None):
    region = (image.crop(box) if box else image).convert("RGB")
    return tuple(ImageStat.Stat(region).mean)


def test_every_platform_renders_every_act():
    beats = (0, 900, 2400, 4200, 7600, 9950, 10300, 12000, 15000, 18800,
             19250, 19700, 20300, 21500, 23000, 24800, 25700)
    for profile in M.PROFILES:
        for size in ((1280, 800), (1080, 1920), (1920, 1080)):
            target = renderer(profile, *size)
            for t in beats:
                image = target.render(t)
                assert image.mode == "RGB", (profile, t, image.mode)
                assert image.size == size, (profile, t, image.size)
                # Every frame is a real picture, not a black or white plate.
                palette = image.resize((24, 24)).getcolors(24 * 24)
                assert palette is not None and len(palette) > 6, (profile, t)


def test_acts_look_different():
    target = renderer()
    desktop = target.render(350)
    outbreak = target.render(7600)
    blue = target.render(12600)
    final = target.render(24000)
    assert desktop.tobytes() != outbreak.tobytes()
    assert outbreak.tobytes() != blue.tobytes()
    assert blue.tobytes() != final.tobytes()


def test_crash_screen_is_blue_and_reads_as_a_crash_screen():
    blue = renderer().render(12600)
    r, g, b = mean(blue)
    assert b > r * 1.35 and b > g * 1.10, (r, g, b)
    assert 20 < b < 235, "a deep blue, not a neon fill"


def test_the_ahian_desktop_is_purple_teal_not_blue():
    final = renderer().render(24000)
    left = mean(final, (0, 0, 400, 800))
    right = mean(final, (880, 0, 1280, 800))
    r, g, b = mean(final)
    assert b > 40 and g > 40, (r, g, b)
    assert left[2] > left[1] * 1.4, "purple on the left"
    assert right[1] > right[0] * 1.8, "green-led teal on the right"
    assert right[2] < right[1] * 1.25, "and not a blue screen"


def test_outbreak_backdrop_is_the_smth_desktop():
    desktop = renderer().render(200)
    r, g, b = mean(desktop, (0, 120, 1280, 800))
    assert r > g, "obsidian with a maroon cast, not purple"
    assert r < 90 and g < 80 and b < 90, "the desktop stays dark"


def test_error_windows_are_drawn_bigger_than_nothing_and_varied():
    target = renderer()
    early = target.render(1600)
    late = target.render(9000)
    assert early.tobytes() != late.tobytes()
    # A dozen windows leave far more structure on screen than two.
    assert len(late.resize((64, 40)).getcolors(64 * 40)) > len(
        early.resize((64, 40)).getcolors(64 * 40))


def test_frames_convert_to_cairo_argb32():
    """The GTK overlay hands cairo a raw buffer; byte order and stride matter."""
    image = Image.new("RGB", (5, 3), (10, 20, 30))
    buffer, stride = ahian_scene.to_argb32(image)
    assert stride == 20 and len(buffer) == 60
    assert bytes(buffer[0:4]) == bytes((30, 20, 10, 255)), "BGRA with full alpha"
    frame = renderer().render(23000)
    buffer, stride = ahian_scene.to_argb32(frame)
    assert stride == frame.width * 4
    assert len(buffer) == stride * frame.height


def test_text_alpha_is_flattened_against_its_surface():
    # Pillow renders glyphs with alpha 0 almost white, so put_text pre-blends.
    assert ahian_scene.flatten((242, 236, 255, 0), (30, 26, 48)) == (30, 26, 48)
    assert ahian_scene.flatten((242, 236, 255, 255), (30, 26, 48)) == (242, 236, 255)
    mid = ahian_scene.flatten((255, 255, 255, 128), (0, 0, 0))
    assert 120 <= mid[0] <= 135, mid


def test_no_ghost_caption_once_the_wordmark_has_dissolved():
    target = renderer()
    plain = target.render(20700)
    late = target.render(23200)
    # The caption region in the middle of the screen must be background, not text.
    region = late.crop((560, 420, 720, 455))
    r, g, b = mean(region)
    assert abs(r - g) + abs(g - b) < 90, (r, g, b)


def test_reduced_motion_renders_the_finished_desktop():
    scene = M.StartupScene(1280, 800, reduced=True)
    image = ahian_scene.SceneRenderer(scene).render(0)
    r, g, b = mean(image)
    assert b > 30 and g > 30
    icony = image.crop((0, 0, 140, 640))
    assert len(icony.resize((20, 20)).getcolors(400)) > 10


def test_a_frame_is_fast_enough_for_thirty_frames_a_second():
    target = renderer()
    target.render(7000)                       # warm every cache
    start = time.perf_counter()
    for t in (7100, 7300, 7500, 7700, 7900, 8100):
        target.render(t)
    steady = (time.perf_counter() - start) / 6.0
    assert steady < 0.09, f"steady outbreak frame too slow: {steady:.3f}s"
    start = time.perf_counter()
    target.render(12600)
    assert time.perf_counter() - start < 0.35


def test_no_cursor_or_tile_reconstruction_code():
    source = (SMTH_LIB / "ahian_scene.py").read_text()
    for banned in ("_draw_cursor", "TileSpec", "particles"):
        assert banned not in source, banned
    model = (SMTH_LIB / "ahian_startup_model.py").read_text()
    assert "REALITY NOT FOUND" in model
    assert "AHIAN HAS TAKEN CONTROL" in model
    assert "AHIAN wants to make your life beautiful." in model


def test_linux_overlay_uses_the_shared_renderer():
    spec = importlib.util.spec_from_file_location(
        "ahian_startup_under_test", SMTH_LIB / "ahian_startup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ahian_scene is ahian_scene
    assert module.main(["--no-animation"]) == 0
    assert module.main(["--print-plan"]) == 0
    assert module.reduced_motion() in (True, False)
    # No GTK here: run() must decline cleanly instead of raising.
    assert module.run() == 0


def load_windows_launcher():
    tk = types.ModuleType("tkinter")

    class TclError(Exception):
        pass

    tk.TclError = TclError
    for name in ("Tk", "Toplevel", "Canvas", "Frame", "Label", "Button", "Entry",
                 "Text", "StringVar", "Listbox", "Scrollbar", "PhotoImage"):
        setattr(tk, name, object)
    tk.LEFT, tk.RIGHT, tk.TOP, tk.BOTTOM = "left", "right", "top", "bottom"
    tk.X, tk.Y, tk.BOTH, tk.END = "x", "y", "both", "end"
    tk.NORMAL, tk.DISABLED = "normal", "disabled"
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


def test_windows_launcher_uses_the_shared_renderer():
    module = load_windows_launcher()
    scene_module = module._load_ahian_scene()
    assert scene_module is not None, "the shared renderer must be reachable"
    assert scene_module.M.DURATION_MS == M.DURATION_MS
    assert scene_module.SceneRenderer is ahian_scene.SceneRenderer
    # The class and the terminal now exist when the EXE starts: main() used to
    # run halfway down the file, before either was defined.
    assert hasattr(module, "AhianConstructionIntro")
    assert hasattr(module, "TerminalWindow")


def test_windows_intro_degrades_without_a_renderer():
    module = load_windows_launcher()

    class Parent:
        def __init__(self):
            self.revealed = 0
            self.root = None

        def finish_reveal(self):
            self.revealed += 1

    parent = Parent()
    intro = object.__new__(module.AhianConstructionIntro)
    intro.parent = parent
    intro.closed = True
    intro.module = None
    intro.image_tk = None
    intro._reveal()
    assert parent.revealed == 1


def test_android_view_matches_the_shared_timeline():
    source = (ROOT / "launchers/android/app/src/main/kotlin/os/smth/launcher/"
                     "AhianConstructionView.kt").read_text()
    assert "DURATION_MS = 25800L" in source
    assert "BLUE_START = 10000f" in source
    assert "BLUE_END = 19000f" in source
    assert "COUNTDOWN_FROM = 9" in source
    assert "AHIAN HAS TAKEN CONTROL" in source
    assert "AHIAN wants to make your life beautiful." in source
    # Every window from the shared table is present, with the same timing.
    for spec in M.ERRORS:
        assert f'"{spec.title}"' in source, spec.title
        assert f"{spec.start_ms}f" in source, spec.start_ms
    # And the old reconstruction is gone.
    for banned in ("TileSpec", "drawFragments", "drawRings"):
        assert banned not in source, banned


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
            traceback.print_exc(limit=2)
        else:
            print(f"ok   {name}")
    if failures:
        print(f"FAIL ahian renderers: {failures} test(s)")
        return 1
    print("PASS ahian renderers: shared frames, three acts, all three platforms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
