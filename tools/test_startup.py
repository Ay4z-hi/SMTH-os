#!/usr/bin/env python3
"""Tests for the SMTH startup gesture.

The startup is one thing only: the logo fades in and out.  These tests pin the
timeline, the logo's alpha curve and the absence of every reconstruction
element (cursors, selection boxes, panels, tiles) that used to exist.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIB = ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth"
sys.path.insert(0, str(LIB))
import startup_model as M  # noqa: E402


def test_timeline_is_a_single_logo_fade():
    assert M.DURATION_MS == M.LOGO_OUT_MS
    assert M.DURATION_MS <= 2000, "the startup must not become a scene of its own"
    assert M.LOGO_IN_MS < M.LOGO_HOLD_MS < M.LOGO_OUT_MS
    scene = M.StartupScene(1920, 1080)
    assert scene.frame(0).phase == "logo-in"
    assert scene.frame(M.LOGO_IN_MS + 40).phase == "logo-hold"
    assert scene.frame(M.LOGO_HOLD_MS + 40).phase == "logo-out"
    assert scene.frame(M.DURATION_MS).phase == "done"
    assert scene.frame(M.DURATION_MS).done
    assert not scene.frame(0).done
    # No overlay fade on top of the logo fade: the window is simply removed.
    assert scene.frame(0).overlay_alpha == 1.0
    assert scene.frame(M.DURATION_MS - 1).overlay_alpha == 1.0


def test_logo_alpha_curve():
    scene = M.StartupScene(1280, 720)
    assert scene.frame(0).logo_alpha == 0.0
    assert scene.frame(M.LOGO_IN_MS).logo_alpha > 0.99
    assert scene.frame(M.LOGO_HOLD_MS - 1).logo_alpha == 1.0
    assert scene.frame(M.LOGO_OUT_MS).logo_alpha == 0.0
    middle = scene.frame((M.LOGO_HOLD_MS + M.LOGO_OUT_MS) // 2)
    assert 0.1 < middle.logo_alpha < 0.9
    # Reveal and scale are already settled while the logo holds.
    assert 0.99 <= scene.frame(M.LOGO_HOLD_MS - 1).logo_reveal <= 1.0
    assert 0.99 <= scene.frame(M.LOGO_HOLD_MS - 1).logo_scale <= 1.0


def test_no_reconstruction_model_remains():
    for name in ("cursors", "items", "boxes", "CursorSpec", "CursorFrame",
                 "BuildItem", "ItemFrame", "SelectionBox", "BoxFrame"):
        assert not hasattr(M, name), f"{name} belongs to the removed reconstruction"
    source = (LIB / "startup_model.py").read_text()
    for banned in ("CursorSpec", "SelectionBox", "BuildItem", "CONSTRUCT_START_MS",
                   "CURSOR_START_MS"):
        assert banned not in source, banned


def test_renderer_draws_nothing_but_the_logo():
    source = (LIB / "startup.py").read_text()
    for banned in ("_draw_cursor", "_draw_box", "_draw_items", "_draw_window",
                   "_draw_status", "_draw_grid", "_draw_icon", "_draw_clock",
                   "_draw_rings", "_draw_dock", "_draw_dot_field"):
        assert banned not in source, f"{banned} is part of the removed animation"
    # Only the logo and the black plate are mentioned in the draw method.
    draw = source[source.index("def draw(self, cr, w, h):"):]
    assert "_draw_logo" in draw
    assert "set_source_rgb(0, 0, 0)" in draw


def test_resolutions_and_reduced_motion():
    for width, height in ((800, 600), (1280, 720), (1920, 1080),
                          (2560, 1080), (1080, 1920), (1440, 3200)):
        scene = M.StartupScene(width, height)
        assert scene.width == max(640, width)
        assert scene.height == max(480, height)
        assert scene.portrait == (height >= width * 0.95)
    reduced = M.StartupScene(1920, 1080, reduced=True)
    assert reduced.frame(0).reduced
    assert reduced.frame(0).logo_alpha == 0.0
    assert reduced.frame(400).logo_alpha == 1.0
    assert reduced.frame(M.REDUCED_MS).done
    assert M.REDUCED_MS <= 800


def test_deterministic():
    a = M.StartupScene(1600, 900)
    b = M.StartupScene(1600, 900)
    for t in (0, 300, 700, 1100, 1500):
        assert a.frame(t) == b.frame(t)


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
        print(f"FAIL startup: {failures} test(s)")
        return 1
    print("PASS startup: logo fade in, hold, fade out, nothing else")
    return 0


if __name__ == "__main__":
    sys.exit(main())
