#!/usr/bin/env python3
"""Tests for the AHIAN takeover timeline.

The animation is three acts and must stay that way: a ten second error outbreak,
a nine second countdown on the AH1AN system screen, then the desktop upgrade.
These tests pin the timing, the wording, the variety of the error windows (no
staircase, no clones), the bounds at every resolution and the fallbacks.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth"))
import ahian_startup_model as M  # noqa: E402


def test_timeline_is_three_acts():
    assert M.OUTBREAK_MS == 10000
    assert M.BLUE_START_MS == 10000
    assert M.BLUE_END_MS == 19000
    assert M.BLUE_END_MS - M.BLUE_START_MS == 9000, "the countdown is nine seconds"
    assert M.WALL_OPEN_START_MS >= M.BLUE_END_MS
    assert M.WALL_OPEN_START_MS < M.BRAND_START_MS < M.WALL_OPEN_START_MS + M.WALL_OPEN_MS + 600
    assert M.BRAND_START_MS < M.PANEL_START_MS < M.FADE_START_MS < M.DURATION_MS
    scene = M.StartupScene(1920, 1080)
    assert scene.phase(0) == "outbreak"
    assert scene.phase(9999) == "outbreak"
    assert scene.phase(10000) == "blue"
    assert scene.phase(18999) == "blue"
    assert scene.phase(19000) == "transform"
    assert scene.phase(M.FADE_START_MS) == "reveal"
    assert scene.phase(M.DURATION_MS) == "done"
    assert scene.frame(M.DURATION_MS).done
    assert scene.frame(M.DURATION_MS).overlay_alpha == 0


def test_the_sequence_no_longer_reconstructs_tile_by_tile():
    scene = M.StartupScene(1920, 1080)
    # The old reveal assembled a dotted wallpaper from tiles. Nothing in the
    # new scene may claim to be a tile, a particle or a cursor.
    for name in ("tiles", "particles", "rings", "segments", "cursors"):
        assert not hasattr(scene, name), name
    frame = scene.frame(6000)
    assert not hasattr(frame, "tiles")
    assert not hasattr(frame, "particles")


def test_outbreak_starts_on_the_desktop_and_builds():
    scene = M.StartupScene(1920, 1080)
    assert scene.frame(0).cards == ()
    assert scene.frame(120).cards == ()
    assert len(scene.frame(2000).cards) < len(scene.frame(5000).cards)
    assert len(scene.frame(5000).cards) < len(scene.frame(7500).cards)
    assert len(scene.frame(7500).cards) == len(scene.frame(9900).cards)
    # The desktop is still the thing underneath for the whole act.
    assert scene.frame(9000).desktop_dim > 0.2
    assert all(card.alpha > 0 for card in scene.frame(9000).cards)


def test_boxes_arrive_at_varied_accelerating_intervals():
    starts = [spec.start_ms for spec in M.ERRORS]
    assert starts == sorted(starts)
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert max(gaps) > 400, "the first windows are well spaced"
    assert gaps[-1] < 260, "the last windows arrive in a storm"
    assert gaps[0] > gaps[-1], "the outbreak accelerates"
    assert len(set(gaps)) >= 10, "the intervals must vary, not repeat"
    # No two windows appear at the same moment.
    assert len(set(starts)) == len(starts)


def test_error_messages_are_written_and_varied():
    titles = [spec.title for spec in M.ERRORS]
    for required in ("SYSTEM FAILURE", "DESKTOP CORRUPTED", "REALITY NOT FOUND",
                     "AHIAN INITIALIZATION"):
        assert required in titles, required
    assert len(set(titles)) >= 8
    assert len(set(spec.body for spec in M.ERRORS)) == len(M.ERRORS)
    codes = [spec.code for spec in M.ERRORS]
    assert len(set(codes)) >= 8
    assert all(spec.code.startswith("0x") for spec in M.ERRORS)


def test_windows_are_not_clones_on_a_staircase():
    """No identical boxes, and no diagonal march of equally sized panels."""
    scene = M.StartupScene(1920, 1080)
    sizes = [(round(scene.card_size(s)[0]), round(scene.card_size(s)[1]))
             for s in M.ERRORS]
    assert len(set(sizes)) >= 8, "the windows must not all be the same size"
    # Diagonals: cx - cy bands. A staircase repeats the same band with evenly
    # spaced centres; allow at most three per band and require size variety.
    bands = {}
    for spec, size in zip(M.ERRORS, sizes):
        key = round((spec.cx - spec.cy) * 20)
        bands.setdefault(key, []).append((spec.cx, spec.cy, size))
    for key, group in bands.items():
        assert len(group) <= 3, f"band {key} holds {len(group)} windows"
        if len(group) == 3:
            assert len({item[2] for item in group}) >= 2, (
                f"band {key} repeats one window size three times")
    # Horizontal and vertical spread across the whole screen.
    xs = [spec.cx for spec in M.ERRORS]
    ys = [spec.cy for spec in M.ERRORS]
    assert min(xs) < 0.15 and max(xs) > 0.85
    assert min(ys) < 0.20 and max(ys) > 0.80


def test_cards_fade_and_scale_in():
    scene = M.StartupScene(1920, 1080)
    spec = M.ERRORS[2]
    start = spec.start_ms
    fresh = next(c for c in scene.frame(start + 20).cards if c.spec.start_ms == start)
    settled = next(c for c in scene.frame(start + 600).cards if c.spec.start_ms == start)
    assert 0 < fresh.alpha < 1 and fresh.progress < 1
    assert settled.alpha == 1 and settled.progress == 1
    assert fresh.rect.w > settled.rect.w, "a window settles down from slightly larger"
    assert fresh.rect.y != settled.rect.y, "and drifts up into place"
    assert fresh.flash > 0, "a new window flashes its accent once"


def test_glitches_are_sparse_then_dense_and_stop_at_the_blue_screen():
    early = [event for event in M.GLITCH_TABLE if event[0] < 3000]
    late = [event for event in M.GLITCH_TABLE if event[0] >= 8000]
    assert len(early) < len(late), "effects build with the outbreak"
    assert len(M.GLITCH_TABLE) < 40, "effects stay occasional, not a strobe"
    scene = M.StartupScene(1920, 1080)
    assert any(scene.frame(t).glitch.flash > 0 for t in range(1360, 1420, 10))
    assert scene.frame(10500).glitch.split == 0 or scene.frame(10500).glitch.split < 3
    assert len(M.CALM_GLITCH_TABLE) <= 8, "the countdown is calm"


def test_blue_screen_wording_and_countdown():
    scene = M.StartupScene(1920, 1080)
    frame = scene.frame(12000)
    assert frame.blue.head == "AHIAN HAS TAKEN CONTROL"
    assert frame.blue.sub == "AHIAN wants to make your life beautiful."
    # A real nine second countdown: 9 at the first frame, 0 at the last.
    assert scene.countdown(10000) == 9
    assert scene.countdown(10999) == 9
    assert scene.countdown(11000) == 8
    assert scene.countdown(18500) == 1
    assert scene.countdown(18999) == 1
    assert scene.countdown(19000) == 0
    values = [scene.countdown(t) for t in range(10000, 19001, 100)]
    assert values == sorted(values, reverse=True)
    assert set(values) == set(range(0, 10))
    assert scene.frame(12000).blue.progress > 0.1


def test_blue_screen_interrupts_the_outbreak():
    scene = M.StartupScene(1920, 1080)
    before = scene.frame(9990)
    assert before.cards
    after = scene.frame(10000)
    assert after.cards == (), "the windows are gone the instant the screen cuts"
    assert after.phase == "blue"
    # It opens from a line, then holds full screen.
    assert scene.frame(10200).blue.open < 0.2
    assert scene.frame(10600).blue.open == 1.0
    assert scene.frame(12000).blue.alpha > 0.9


def test_transformation_order():
    scene = M.StartupScene(1920, 1080)
    assert scene.frame(19100).transform.open == 0
    assert 0 < scene.frame(19400).transform.open < 1
    assert scene.frame(19700).transform.open == 1.0
    assert scene.frame(19700).transform.wallpaper == 1.0
    # The wordmark assembles, holds, then dissolves as the desktop takes over.
    assert scene.frame(19500).transform.brand < 0.3
    assert scene.frame(20300).transform.brand_alpha > 0.8
    assert scene.frame(22000).transform.brand_alpha == 0
    # Panel, then icons, then widgets: one coordinated stagger.
    assert scene.frame(20200).transform.panel > 0
    assert scene.frame(20200).transform.icons[0] == 0
    assert scene.frame(21000).transform.icons[0] == 1
    assert scene.frame(21000).transform.icons[-1] < 1
    assert scene.frame(21600).transform.icons[-1] > 0.5
    assert scene.frame(22100).transform.widgets == 1
    # Staggered, never simultaneous.
    starts = [M.ICON_START_MS + i * M.ICON_STEP_MS for i in range(len(scene.icons))]
    assert len(set(starts)) == len(starts)
    assert starts == sorted(starts)


def test_toast_crosses_the_end_of_the_transformation():
    scene = M.StartupScene(1920, 1080)
    assert scene.frame(22000).transform.toast == 0
    assert scene.frame(22600).transform.toast > 0.5
    assert scene.frame(M.TOAST_END_MS + 500).transform.toast < 0.2


def test_reveal_fades_once_to_the_live_desktop():
    scene = M.StartupScene(1920, 1080)
    assert scene.frame(M.FADE_START_MS - 1).overlay_alpha == 1.0
    middle = scene.frame((M.FADE_START_MS + M.DURATION_MS) // 2)
    assert 0 < middle.overlay_alpha < 1
    assert scene.frame(M.DURATION_MS).overlay_alpha == 0
    # The final frame is the whole AHIAN desktop, fully assembled.
    final = scene.frame(M.FADE_START_MS)
    assert len(final.transform.icons) == len(scene.icons)
    assert all(value == 1.0 for value in final.transform.icons)
    assert final.transform.panel == 1.0 and final.transform.widgets == 1.0


def test_every_platform_shares_the_sequence():
    signatures = {}
    for profile in M.PROFILES:
        scene = M.StartupScene(1280, 720, profile=profile)
        assert scene.profile == profile
        signatures[profile] = (
            scene.frame(0).phase,
            scene.frame(2400).phase,
            scene.frame(12000).phase,
            scene.frame(22000).phase,
            len(scene.errors),
            scene.countdown(10000),
            round(scene.frame(12000).blue.progress, 6),
        )
        assert len(scene.icons) == (12 if profile == "linux" else 6)
    assert len(set(signatures.values())) == 1, signatures


def test_bounds_at_every_resolution():
    for profile in M.PROFILES:
        for width, height in ((800, 600), (1280, 720), (1920, 1080),
                              (2560, 1080), (1080, 1920), (1440, 3200)):
            scene = M.StartupScene(width, height, profile=profile)
            assert scene.width >= 480 and scene.height >= 360
            assert scene.portrait == (height >= width * 0.95)
            for spec in scene.errors:
                rect = scene.card_rect(spec)
                assert rect.x >= -0.5 and rect.y >= -0.5, (profile, spec.key)
                assert rect.right <= scene.width + 0.5, (profile, spec.key)
                assert rect.bottom <= scene.height + 0.5, (profile, spec.key)
                assert rect.w > 0 and rect.h > 0
            for icon in scene.icons:
                assert icon.rect.right <= scene.width + 0.5
                assert icon.rect.bottom <= scene.height + 0.5
                assert icon.label and icon.glyph


def test_reduced_motion_is_one_short_fade():
    scene = M.StartupScene(1920, 1080, reduced=True)
    assert scene.frame(0).reduced
    assert scene.frame(0).cards == ()
    assert scene.frame(0).overlay_alpha == 1.0
    assert scene.frame(M.REDUCED_MS).done
    assert scene.frame(M.REDUCED_MS).overlay_alpha == 0
    assert M.REDUCED_MS <= 800
    # The finished desktop is what fades out.
    final = scene.frame(M.REDUCED_MS - 1)
    assert all(value == 1.0 for value in final.transform.icons)


def test_deterministic():
    a = M.StartupScene(1600, 900)
    b = M.StartupScene(1600, 900)
    assert a.layout == b.layout
    assert a.errors == b.errors
    for t in (0, 2500, 7000, 10000, 13000, 19500, 22000, 25000):
        assert a.frame(t) == b.frame(t)


def test_flow_colour_is_shared_with_the_desktop():
    # home.py samples this for the live wallpaper, so it must stay stable.
    top_left = M.flow_colour(0.05, 0.05, 0.0)
    bottom_right = M.flow_colour(0.95, 0.95, 0.0)
    assert top_left[2] > top_left[1], "purple at the top left"
    assert bottom_right[1] > bottom_right[0], "teal at the bottom right"
    assert M.flow_colour(0.3, 0.4, 1.0) == M.flow_colour(0.3, 0.4, 0.0)


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
        print(f"FAIL ahian takeover: {failures} test(s)")
        return 1
    print("PASS ahian takeover: 10 s outbreak, 9 s countdown, desktop upgrade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
