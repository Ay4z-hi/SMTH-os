#!/usr/bin/env python3
"""Tests for the AHIAN desktop reconstruction timeline."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth"))
import ahian_startup_model as M  # noqa: E402


def test_timeline():
    assert 8000 <= M.DURATION_MS <= 12000, M.DURATION_MS
    assert M.LOGO_END_MS == M.LOGO_FADE_END_MS == 0
    assert M.CURSOR_START_MS < M.CONSTRUCT_START_MS
    assert M.CONSTRUCT_START_MS < M.CONSTRUCT_END_MS < M.FADE_END_MS
    scene = M.StartupScene(1920, 1080)
    assert scene.frame(0).phase == "cursors"
    assert scene.frame(1100).phase == "construct"
    assert scene.frame(4000).phase == "construct"
    assert scene.frame(M.CONSTRUCT_END_MS + 10).phase == "settle"
    assert scene.frame(M.REVEAL_END_MS + 10).phase == "fade"
    assert scene.frame(M.DURATION_MS).done
    assert scene.frame(M.DURATION_MS).overlay_alpha == 0
    assert not scene.frame(0).done


def test_cursors_are_independent_and_visible():
    scene = M.StartupScene(1920, 1080)
    assert len(scene.cursors) >= 6
    assert len({c.key for c in scene.cursors}) == len(scene.cursors)
    assert len({c.colour for c in scene.cursors}) >= 5
    mid = scene.frame(4200)
    assert len(mid.cursors) == len(scene.cursors)
    points = {(round(c.x), round(c.y)) for c in mid.cursors}
    assert len(points) == len(mid.cursors)
    for c in mid.cursors:
        assert c.alpha > 0.5
        assert -10 <= c.x <= scene.width + 10
        assert -10 <= c.y <= scene.height + 10
        assert len(c.trail) == 3
    assert any(c.click > 0 for c in mid.cursors)
    # A completed cursor must travel to its exit point, not teleport back to entry.
    for spec in scene.cursors:
        x, y = spec.position(spec.end_ms, scene.width, scene.height)
        assert x < 0 or x > scene.width or y < 0 or y > scene.height
    assert scene.frame(500).cursors


def test_selection_boxes():
    scene = M.StartupScene(1920, 1080)
    assert len(scene.boxes) >= 5
    frame = scene.frame(5400)
    assert len(frame.boxes) == len(scene.boxes)
    labels = {b.spec.label for b in frame.boxes}
    assert {"TASKBAR", "WINDOW", "APP GRID", "DOCK"} <= labels
    for b in frame.boxes:
        r = b.spec.rect
        assert 0 <= r.x <= scene.width and 0 <= r.y <= scene.height
        assert r.right <= scene.width + 0.5 and r.bottom <= scene.height + 0.5
        assert 0 < b.progress <= 1
        assert b.alpha > 0.5
    assert all(b.alpha < 0.1 for b in scene.frame(M.REVEAL_END_MS).boxes)


def test_construction_items():
    scene = M.StartupScene(1920, 1080)
    kinds = {i.kind for i in scene.items}
    assert {"status", "grid", "window", "clock", "rings", "dock", "icon"} <= kinds
    icons = [i for i in scene.items if i.kind == "icon"]
    assert len(icons) == 12
    frame = scene.frame(6000)
    assert len(frame.items) == len(scene.items)
    for item in frame.items:
        assert 0 < item.progress <= 1
    assert len(scene.frame(M.CONSTRUCT_START_MS - 1).items) == 0
    assert len(scene.frame(M.CONSTRUCT_END_MS).items) == len(scene.items)


def test_resolutions_and_bounds():
    for width, height in ((800, 600), (1280, 720), (1920, 1080), (2560, 1080), (1080, 1920)):
        scene = M.StartupScene(width, height)
        assert scene.width == max(640, width)
        assert scene.height == max(480, height)
        frame = scene.frame(5000)
        for box in frame.boxes:
            r = box.spec.rect
            assert -0.6 <= r.x and -0.6 <= r.y
            assert r.right <= scene.width + 0.6
            assert r.bottom <= scene.height + 0.6
        for item in frame.items:
            r = item.spec.rect
            assert -0.6 <= r.x and -0.6 <= r.y
            assert r.right <= scene.width + 0.6
            assert r.bottom <= scene.height + 0.6
        assert scene.portrait == (height >= width * 0.95)


def test_reduced_motion():
    scene = M.StartupScene(1920, 1080, reduced=True)
    assert scene.cursors == ()
    assert scene.boxes == ()
    assert scene.items == ()
    assert scene.frame(0).reduced
    assert scene.frame(M.REDUCED_MS).done
    assert M.REDUCED_MS < 1500


def test_deterministic():
    a = M.StartupScene(1600, 900)
    b = M.StartupScene(1600, 900)
    assert a.layout == b.layout
    assert a.items == b.items
    assert a.boxes == b.boxes
    assert a.frame(4300) == b.frame(4300)


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
        print(f"FAIL ahian startup: {failures} test(s)")
        return 1
    print("PASS ahian startup: timeline, cursors, boxes, items, resolutions and reduced motion")
    return 0


if __name__ == "__main__":
    sys.exit(main())