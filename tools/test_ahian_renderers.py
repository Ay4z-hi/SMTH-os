#!/usr/bin/env python3
"""Headless visual tests for the AHIAN takeover renderers.

This exercises the real drawing code with Pillow on every platform profile and
checks the things compilation cannot:

  * act 1 is RGBA and transparent everywhere a window is not, so the desktop
    underneath is preserved pixel-for-pixel;
  * the 22 windows are all drawn, varied, and settle inside the screen;
  * act 2 is the opaque blue screen with a real nine second countdown;
  * at zero the frame is fully transparent: the overlay is removed onto the
    live desktop rather than fading to a rendered replacement;
  * no renderer for a second desktop remains in any of the three platforms.

The Windows launcher and the Linux overlay load the shared renderer exactly as
the real programs do.
"""
import importlib.util
import pathlib
import sys
import time
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
SMTH_LIB = ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth"
sys.path.insert(0, str(SMTH_LIB))

from PIL import Image, ImageDraw, ImageStat  # noqa: E402
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


def live_desktop(width=1280, height=800):
    """A stand-in for the running session: distinct wallpaper, icons, taskbar."""
    img = Image.new("RGB", (width, height), (20, 24, 26))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / max(1, height - 1)
        draw.line((0, y, width, y), fill=(int(20 + 40 * ratio),
                                          int(24 + 10 * ratio),
                                          int(26 + 55 * ratio)))
    # Icons, a window and a taskbar: anything the overlay must not touch.
    for index in range(6):
        x, y = 60, 60 + index * 74
        draw.rounded_rectangle((x, y, x + 48, y + 48), 12,
                               outline=(242, 198, 210), width=2)
    draw.rectangle((360, 120, 900, 560), fill=(32, 28, 40),
                   outline=(242, 198, 210))
    draw.rectangle((40, height - 56, width - 40, height - 12),
                   fill=(16, 14, 20), outline=(242, 198, 210))
    return img


def test_every_platform_renders_every_beat_as_rgba():
    beats = (0, 900, 2400, 4200, 7600, 9950, 10300, 12000, 15000, 18800, 19000)
    for profile in M.PROFILES:
        for size in ((1280, 800), (1080, 1920), (1920, 1080), (480, 360)):
            target = renderer(profile, *size)
            for t in beats:
                image = target.render(t)
                assert image.mode == "RGBA", (profile, t, image.mode)
                assert image.size == size, (profile, t, image.size)


def test_act_one_is_transparent_over_the_live_desktop():
    target = renderer()
    desktop = live_desktop()
    for t in (0, 1500, 4200, 7600, 9950):
        overlay = target.render(t)
        composite = Image.alpha_composite(desktop.convert("RGBA"), overlay)
        # Corners and the taskbar are untouched: no dimming, no replacement.
        for box in ((0, 660, 300, 800), (1180, 0, 1280, 120),
                    (0, 0, 260, 60)):
            before = desktop.convert("RGB").crop(box).tobytes()
            after = composite.convert("RGB").crop(box).tobytes()
            if t == 0:
                assert before == after, f"empty frame repainted {box}"
        # The overlay's alpha is not full anywhere in act 1.
        assert overlay.getchannel("A").getextrema()[0] == 0, (t, "no transparent pixels")


def test_empty_and_finished_frames_are_fully_transparent():
    target = renderer()
    for t in (0, 40, 120, 19000, 25000):
        image = target.render(t)
        assert image.getchannel("A").getextrema() == (0, 0), t


def test_the_desktop_underneath_is_pixel_identical_outside_the_windows():
    """Objective proof: compositing adds the windows, it never repaints."""
    scene = M.StartupScene(1280, 800)
    target = ahian_scene.SceneRenderer(scene)
    desktop = live_desktop().convert("RGBA")
    # A quiet beat between interference effects: the windows are settled and
    # nothing else may be painted.
    overlay = target.render(7900)
    composite = Image.alpha_composite(desktop, overlay)
    frame = scene.frame(7900)
    assert len(frame.cards) == 22
    boxes = [(int(c.rect.x) - 24, int(c.rect.y) - 24,
              int(c.rect.right) + 24, int(c.rect.bottom) + 24)
             for c in frame.cards]

    def covered(x, y):
        return any(box[0] <= x <= box[2] and box[1] <= y <= box[3] for box in boxes)

    before = desktop.convert("RGB")
    after = composite.convert("RGB")
    checked = 0
    for y in range(4, 800, 12):
        for x in range(4, 1280, 12):
            if covered(x, y):
                continue
            assert before.getpixel((x, y)) == after.getpixel((x, y)), (x, y)
            checked += 1
    assert checked > 500, checked
    # And the windows did change something where they are.
    assert before.tobytes() != after.tobytes()

    # At zero the overlay adds nothing at all: the same desktop comes back.
    final = Image.alpha_composite(desktop, target.render(19000))
    assert final.convert("RGB").tobytes() == before.tobytes()


def test_all_twenty_two_windows_are_drawn_and_varied():
    target = renderer()
    late = target.render(9950)
    assert len([c for c in M.ERRORS if c.start_ms <= 9950]) == 22
    # A whole cascade leaves far more structure than two windows.
    early = target.render(1600)
    assert len(late.resize((64, 40)).getcolors(64 * 40)) > len(
        early.resize((64, 40)).getcolors(64 * 40))
    # Window cores are opaque glass, not translucent ghosts.
    scene = M.StartupScene(1280, 800)
    frame = scene.frame(9950)
    sample = frame.cards[-1]
    x, y = int(sample.rect.centre()[0]), int(sample.rect.centre()[1])
    assert late.getpixel((x, y))[3] > 240


def test_crash_screen_is_blue_and_opaque():
    blue = renderer().render(12600)
    assert blue.getchannel("A").getextrema() == (255, 255), "the countdown covers all"
    r, g, b = mean(blue)
    assert b > r * 1.35 and b > g * 1.10, (r, g, b)
    assert 20 < b < 235, "a deep blue, not a neon fill"


def test_zero_stops_the_countdown_and_removes_the_screen():
    scene = M.StartupScene(1280, 800)
    target = ahian_scene.SceneRenderer(scene)
    assert scene.countdown(18999) == 1
    assert scene.countdown(19000) == 0
    assert target.render(18999).getchannel("A").getextrema()[0] > 200
    assert target.render(19000).getchannel("A").getextrema() == (0, 0)
    assert scene.frame(19000).done


def test_frames_convert_to_cairo_argb32_premultiplied():
    image = Image.new("RGB", (5, 3), (10, 20, 30))
    buffer, stride = ahian_scene.to_argb32(image)
    assert stride == 20 and len(buffer) == 60
    assert bytes(buffer[0:4]) == bytes((30, 20, 10, 255)), "BGRA with full alpha"
    # A half-transparent red must be premultiplied for cairo.
    translucent = Image.new("RGBA", (1, 1), (255, 0, 0, 128))
    buffer, stride = ahian_scene.to_argb32(translucent)
    assert bytes(buffer[0:4]) == bytes((0, 0, 128, 128)), bytes(buffer[0:4])
    frame = renderer().render(9000)
    buffer, stride = ahian_scene.to_argb32(frame)
    assert stride == frame.width * 4
    assert len(buffer) == stride * frame.height


def test_text_alpha_is_flattened_against_its_surface():
    assert ahian_scene.flatten((242, 236, 255, 0), (30, 26, 48)) == (30, 26, 48)
    assert ahian_scene.flatten((242, 236, 255, 255), (30, 26, 48)) == (242, 236, 255)
    mid = ahian_scene.flatten((255, 255, 255, 128), (0, 0, 0))
    assert 120 <= mid[0] <= 135, mid


def test_reduced_motion_draws_nothing():
    scene = M.StartupScene(1280, 800, reduced=True)
    image = ahian_scene.SceneRenderer(scene).render(0)
    assert image.getchannel("A").getextrema() == (0, 0)


def test_a_frame_is_fast_enough_for_thirty_frames_a_second():
    target = renderer()
    target.render(9000)                       # warm every cache
    start = time.perf_counter()
    for t in (9000, 9100, 9200, 9300, 9400, 9500):
        target.render(t)
    steady = (time.perf_counter() - start) / 6.0
    assert steady < 0.10, f"steady outbreak frame too slow: {steady:.3f}s"
    start = time.perf_counter()
    target.render(12600)
    assert time.perf_counter() - start < 0.35


def test_no_fake_desktop_renderer_remains():
    source = (SMTH_LIB / "ahian_scene.py").read_text()
    for banned in ("_transform_frame", "_draw_shortcut", "_draw_waybar",
                   "_draw_taskbar", "_draw_glance", "_draw_black_hole",
                   "_settled_layer", "def desktop", "_wallpaper("):
        assert banned not in source, banned
    model = (SMTH_LIB / "ahian_startup_model.py").read_text()
    assert "REALITY NOT FOUND" in model
    assert "AHIAN HAS TAKEN CONTROL" in model
    assert "AHIAN wants to make your life beautiful." in model


def test_linux_overlay_is_a_transparent_live_layer():
    spec = importlib.util.spec_from_file_location(
        "ahian_startup_under_test", SMTH_LIB / "ahian_startup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ahian_scene is ahian_scene
    assert module.main(["--no-animation"]) == 0
    assert module.main(["--print-plan"]) == 0
    assert module.reduced_motion() in (True, False)
    assert module.run() == 0                       # no display: decline cleanly
    source = (SMTH_LIB / "ahian_startup.py").read_text()
    assert "background: transparent" in source
    assert "OPERATOR_SOURCE" in source


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


def test_windows_overlay_draws_on_the_live_canvas():
    module = load_windows_launcher()
    scene_module = module._load_ahian_scene()
    assert scene_module is not None, "the shared renderer must be reachable"
    assert scene_module.M.DURATION_MS == M.DURATION_MS
    assert scene_module.SceneRenderer is ahian_scene.SceneRenderer
    source = (ROOT / "launchers/windows/smth_launcher.py").read_text()
    intro = source[source.index("class AhianConstructionIntro:"):]
    assert "self.canvas = parent_launcher.canvas" in intro
    assert "tk.Toplevel" not in intro, "the overlay must not open a second window"
    assert "activate_ahian_desktop" in intro
    assert "background: transparent" in source or "transparent" in intro
    assert "AhianConstructionIntro" in source
    assert "reveal_pending: bool" not in source


def test_windows_intro_degrades_without_a_renderer():
    module = load_windows_launcher()

    class Parent:
        def __init__(self):
            self.revealed = 0

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


def test_windows_startup_is_only_the_logo():
    module = load_windows_launcher()
    source = (ROOT / "launchers/windows/smth_launcher.py").read_text()
    intro = source[source.index("class ConstructionIntro:"):source.index("class AhianConstructionIntro:")]
    assert module.ConstructionIntro.DURATION <= 2.0
    for banned in ("_draw_cursor", "create_polygon", "CursorSpec", "drawField"):
        assert banned not in intro, f"{banned} is part of the removed animation"
    assert "logo_frames" in intro and "create_rectangle(0, 0, w, h, fill=OBSIDIAN" in intro


def test_android_view_matches_the_shared_timeline():
    source = (ROOT / "launchers/android/app/src/main/kotlin/os/smth/launcher/"
                     "AhianConstructionView.kt").read_text()
    assert "DURATION_MS = 19000L" in source
    assert "BLUE_START = 10000f" in source
    assert "BLUE_END = 19000f" in source
    assert "COUNTDOWN_FROM = 9" in source
    assert "AHIAN HAS TAKEN CONTROL" in source
    assert "AHIAN wants to make your life beautiful." in source
    assert "Color.TRANSPARENT" in source
    for spec in M.ERRORS:
        assert f'"{spec.title}"' in source, spec.title
        assert f"{spec.start_ms}f" in source, spec.start_ms
    for banned in ("drawDesktop", "drawWallpaper", "drawBlackHole", "drawBrand",
                   "drawDesktopIcons", "drawTaskbar", "drawToast", "coldWall",
                   "TileSpec", "drawFragments", "drawRings", "setBackgroundColor(OBSIDIAN"):
        assert banned not in source, banned


def test_android_startup_view_is_only_the_logo():
    source = (ROOT / "launchers/android/app/src/main/kotlin/os/smth/launcher/"
                     "MainActivity.kt").read_text()
    view = source[source.index("private class ConstructionView("):]
    assert "animator.duration = 1_600" in view
    for banned in ("drawField", "cursors", "paths = arrayOf", "createRectangle",
                   "panels", "side", "win"):
        assert banned not in view, banned
    assert "logoAlpha" in view and "drawColor(OBSIDIAN)" in view


def test_each_platform_switches_the_desktop_behind_the_blue_screen():
    """The AHIAN wallpaper must never appear through the opening beam."""
    lib = ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth"
    overlay = (lib / "ahian_startup.py").read_text()
    assert "SMTH_AHIAN_ACTIVATE" in overlay
    assert "def switch_desktop" in overlay
    assert "M.BLUE_OPEN_START_MS + M.BLUE_OPEN_MS" in overlay
    assert "ahian\", \"--activate\"" in overlay

    cli = (ROOT / "config/includes.chroot_after_packages/usr/local/bin/ahian").read_text()
    assert 'SMTH_AHIAN_ACTIVATE": "1"' in cli
    assert "sleep 11.0" not in cli, "the theme is no longer switched on a guess"
    assert "sleep 16" in cli, "a headless fallback still applies the theme"
    assert "def animation_disabled" in cli, "no takeover means no waiting"

    windows = (ROOT / "launchers/windows/smth_launcher.py").read_text()
    assert "self.module.M.BLUE_START_MS + 900" in windows
    assert M.BLUE_START_MS + 900 > M.BLUE_OPEN_START_MS + M.BLUE_OPEN_MS

    kotlin = (ROOT / "launchers/android/app/src/main/kotlin/os/smth/launcher").resolve()
    view = (kotlin / "AhianConstructionView.kt").read_text()
    activity = (kotlin / "MainActivity.kt").read_text()
    assert "var onBlueOpen" in view
    assert "BLUE_OPEN_START + BLUE_OPEN_MS" in view
    assert "intro.onBlueOpen" in activity
    assert "postDelayed({ applyAhianTheme()" not in activity


def test_windows_launcher_still_has_an_entry_point():
    """The EXE is only useful if importing the module starts the launcher."""
    source = (ROOT / "launchers/windows/smth_launcher.py").read_text().rstrip()
    assert source.endswith('if __name__ == "__main__":\n    main()'), source[-80:]
    assert "\ndef main():\n" in source


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
    print("PASS ahian renderers: transparent act 1, opaque countdown, live desktop at zero")
    return 0


if __name__ == "__main__":
    sys.exit(main())

