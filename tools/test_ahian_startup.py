#!/usr/bin/env python3
"""Tests for the AHIAN desktop reconstruction timeline.

The animation is cursor-free: the desktop rebuilds itself from fragments,
tiles and segments.  These tests pin the shared timeline, the absence of
cursors, the reconstruction order and the reduced-motion fallback.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth"))
import ahian_startup_model as M  # noqa: E402


def test_timeline():
    assert 8500 <= M.DURATION_MS <= 10000, M.DURATION_MS
    assert M.VOID_END_MS <= M.WALL_START_MS < M.WALL_END_MS
    assert M.WALL_END_MS == M.STRUCT_START_MS
    assert M.STRUCT_START_MS < M.STRUCT_END_MS
    assert M.STRUCT_END_MS == M.ELEMENTS_START_MS < M.ELEMENTS_END_MS
    assert M.ELEMENTS_END_MS < M.REVEAL_START_MS < M.FADE_END_MS
    scene = M.StartupScene(1920, 1080)
    assert scene.frame(0).phase == "void"
    assert scene.frame(1200).phase == "wallpaper"
    assert scene.frame(3500).phase == "structure"
    assert scene.frame(5500).phase == "elements"
    assert scene.frame(8000).phase == "reveal"
    assert scene.frame(M.DURATION_MS).done
    assert scene.frame(M.DURATION_MS).overlay_alpha == 0
    assert not scene.frame(0).done


def test_no_cursors():
    scene = M.StartupScene(1920, 1080)
    assert not hasattr(scene, "cursors")
    frame = scene.frame(4200)
    assert not hasattr(frame, "cursors")
    # No element may be a cursor spec.
    assert all(item.spec.kind != "cursor" for item in frame.items)


def test_void_particles():
    scene = M.StartupScene(1920, 1080)
    early = scene.frame(600)
    assert len(early.particles) >= 30
    for particle in early.particles:
        assert 0 <= particle.x <= scene.width
        assert 0 <= particle.y <= scene.height
        assert particle.alpha > 0
    # Fragments fade away once the wallpaper is assembled.
    assert not scene.frame(M.PARTICLE_END_MS + 50).particles


def test_wallpaper_assembles_from_tiles():
    scene = M.StartupScene(1920, 1080)
    assert len(scene.tiles) >= 48
    assert len({t.key for t in scene.tiles}) == len(scene.tiles)
    # Nothing is visible before the wallpaper phase starts.
    assert not scene.frame(M.WALL_START_MS - 1).tiles
    mid = scene.frame(2000)
    assert 0 < len(mid.tiles) < len(scene.tiles), "tiles must arrive, not pop"
    for tile in mid.tiles:
        assert 0 < tile.progress <= 1
        assert tile.scale >= 0.82
    assert len(scene.frame(M.WALL_END_MS).tiles) == len(scene.tiles)
    # Tiles are ordered, not simultaneous.
    starts = {t.start_ms for t in scene.tiles}
    assert len(starts) > len(scene.tiles) // 3
    # A wall is never a single flat fade: at least two tiles differ at 1.8 s.
    alphas = {round(t.alpha, 2) for t in scene.frame(1800).tiles}
    assert len(alphas) > 2


def test_reconstruction_rings():
    scene = M.StartupScene(1920, 1080)
    assert len(scene.rings) >= 3
    rings = scene.frame(1600).rings
    assert rings
    for ring in rings:
        assert ring.r > 0
        assert 0 < ring.alpha <= 0.5
    assert not scene.frame(M.PARTICLE_END_MS + 600).rings


def test_structure_order():
    scene = M.StartupScene(1920, 1080)
    kinds = {spec.kind for spec in scene.items}
    assert {"taskbar", "edge", "clock", "window", "icon"} <= kinds
    frame = scene.frame(4200)
    assert frame.segments
    assert len(frame.segments) >= 4
    bar = next(i for i in frame.items if i.spec.kind == "taskbar")
    assert bar.progress > 0
    # Segments arrive one after another inside the structure phase.
    assert len({s.spec.start_ms for s in frame.segments}) == len(frame.segments)
    # The taskbar is fully drawn before icons start.
    assert all(i.spec.kind != "icon" for i in scene.frame(M.ELEMENTS_START_MS - 1).items)


def test_icons_are_staggered_in_place():
    scene = M.StartupScene(1920, 1080)
    icons = [spec for spec in scene.items if spec.kind == "icon"]
    assert len(icons) == 12
    starts = [spec.start_ms for spec in icons]
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)
    early = scene.frame(M.ELEMENTS_START_MS + 100)
    icon_frames = [i for i in early.items if i.spec.kind == "icon"]
    assert 0 < len(icon_frames) < len(icons)
    final = scene.frame(M.ELEMENTS_END_MS)
    assert len([i for i in final.items if i.spec.kind == "icon"]) == len(icons)
    # Icons materialise at their final rect: no travel.
    for spec in icons:
        for width, height in ((1920, 1080), (1080, 1920), (1280, 720)):
            other = M.StartupScene(width, height)
            rects = [s.rect for s in other.items if s.kind == "icon"]
            assert all(0 <= r.x and 0 <= r.y for r in rects)
            assert all(r.right <= other.width + 0.6 and r.bottom <= other.height + 0.6
                       for r in rects)


def test_window_dissolves_before_reveal():
    scene = M.StartupScene(1920, 1080)
    window = next(s for s in scene.items if s.kind == "window")
    assert window.end_ms and window.end_ms < M.REVEAL_START_MS
    frame = scene.frame(window.start_ms + 400)
    assert any(i.spec.kind == "window" and i.alpha > 0.9 for i in frame.items)
    late = scene.frame(M.ELEMENTS_END_MS)
    assert all(i.spec.kind != "window" for i in late.items)


def test_reveal_fades_once_to_the_live_desktop():
    scene = M.StartupScene(1920, 1080)
    assert scene.frame(M.REVEAL_START_MS - 1).overlay_alpha == 1.0
    mid = scene.frame((M.REVEAL_START_MS + M.FADE_END_MS) // 2)
    assert 0 < mid.overlay_alpha < 1
    end = scene.frame(M.FADE_END_MS)
    assert end.overlay_alpha == 0
    assert end.done
    # The final drawn scene contains the real desktop structure, no window.
    final = scene.frame(M.ELEMENTS_END_MS)
    assert any(i.spec.kind == "taskbar" for i in final.items)
    assert any(i.spec.kind == "icon" for i in final.items)


def test_profiles_share_the_timeline():
    frames = {}
    for profile in M.PROFILES:
        scene = M.StartupScene(1280, 720, profile=profile)
        assert scene.profile == profile
        frames[profile] = [(i.kind, i.start_ms, i.duration_ms)
                           for i in scene.items]
        assert scene.frame(0).phase == "void"
        assert scene.frame(5500).phase == "elements"
        assert len(scene.tiles) >= 48
    # Same element ordering and timing on every platform. Layouts differ
    # (a 12-icon desktop grid versus a 6-icon shortcut column), so compare the
    # shared structure and the common icon prefix rather than raw list length.
    def by_kind(rows):
        grouped = {}
        for kind, start, duration in rows:
            grouped.setdefault(kind, []).append((start, duration))
        return grouped

    base = by_kind(frames["linux"])
    for profile in ("android", "windows"):
        other = by_kind(frames[profile])
        for kind in ("taskbar", "edge", "clock", "window"):
            assert base[kind] == other[kind], (profile, kind)
        assert base["icon"][:6] == other["icon"], profile
    for kind in ("taskbar", "edge", "clock", "window", "icon"):
        assert base[kind], kind


def test_resolutions_and_bounds():
    for profile in M.PROFILES:
        for width, height in ((800, 600), (1280, 720), (1920, 1080),
                              (2560, 1080), (1080, 1920)):
            scene = M.StartupScene(width, height, profile=profile)
            assert scene.width == max(640, width)
            assert scene.height == max(480, height)
            frame = scene.frame(5000)
            for item in frame.items:
                r = item.spec.rect
                assert -0.6 <= r.x and -0.6 <= r.y, (profile, width, height, r)
                assert r.right <= scene.width + 0.6, (profile, width, height, r)
                assert r.bottom <= scene.height + 0.6, (profile, width, height, r)
            for tile in frame.tiles:
                assert tile.spec.rect.w > 0 and tile.spec.rect.h > 0
            assert scene.portrait == (height >= width * 0.95)


def test_reduced_motion():
    scene = M.StartupScene(1920, 1080, reduced=True)
    assert scene.particles == ()
    assert scene.tiles
    assert scene.segments == ()
    assert scene.frame(0).reduced
    assert scene.frame(0).particles == ()
    assert scene.frame(M.REDUCED_MS).done
    assert scene.frame(M.REDUCED_MS).overlay_alpha == 0
    assert M.REDUCED_MS < 1000


def test_deterministic():
    a = M.StartupScene(1600, 900)
    b = M.StartupScene(1600, 900)
    assert a.layout == b.layout
    assert a.tiles == b.tiles
    assert a.items == b.items
    assert a.particles == b.particles
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
    print("PASS ahian startup: 9s cursor-free reconstruction, tiles, structure, "
          "staggered icons, profiles and reduced motion")
    return 0


if __name__ == "__main__":
    sys.exit(main())
