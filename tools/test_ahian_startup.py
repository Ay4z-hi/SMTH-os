#!/usr/bin/env python3
"""Tests for the AHIAN takeover timeline.

The takeover is two acts: ten seconds of error windows over the running
desktop, then nine seconds of the AH1AN screen counting down.  At zero the
countdown stops and the overlay closes onto the live AHIAN desktop.  There is
no third act, no rebuilt desktop and no fade onto a rendered replacement.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth"))
import ahian_startup_model as M  # noqa: E402


def test_timeline_is_two_acts_ending_at_zero():
    assert M.OUTBREAK_MS == 10000
    assert M.BLUE_START_MS == 10000
    assert M.BLUE_END_MS == 19000
    assert M.BLUE_END_MS - M.BLUE_START_MS == 9000, "the countdown is nine seconds"
    assert M.DURATION_MS == M.BLUE_END_MS, "the takeover ends exactly at zero"
    scene = M.StartupScene(1920, 1080)
    assert scene.phase(0) == "outbreak"
    assert scene.phase(9999) == "outbreak"
    assert scene.phase(10000) == "blue"
    assert scene.phase(18999) == "blue"
    assert scene.phase(19000) == "done"
    assert scene.frame(M.DURATION_MS).done
    assert scene.frame(18999).done is False
    assert scene.frame(M.DURATION_MS).overlay_alpha == 0


def test_no_desktop_replacement_remains():
    scene = M.StartupScene(1920, 1080)
    for name in ("transform", "icons", "layout", "desktop_dim", "brand_dots"):
        assert not hasattr(scene, name), f"{name} belongs to the removed reveal"
    assert not hasattr(scene.frame(0), "transform")
    assert not hasattr(scene.frame(0), "desktop_dim")
    for banned in ("WALL_OPEN_START_MS", "BRAND_START_MS", "PANEL_START_MS",
                   "ICON_START_MS", "TOAST_START_MS", "FADE_START_MS",
                   "TransformFrame", "IconSpec"):
        assert not hasattr(M, banned), f"{banned} is part of the removed third act"
    source = (ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth/"
                     "ahian_startup_model.py").read_text()
    assert "desktop screenshot" in source


def test_all_twenty_two_windows_arrive_over_the_desktop():
    scene = M.StartupScene(1920, 1080)
    assert len(M.ERRORS) == 22, "all 22 error windows must be shown"
    assert scene.frame(0).cards == ()
    assert scene.frame(120).cards == ()
    assert len(scene.frame(2000).cards) < len(scene.frame(5000).cards)
    assert len(scene.frame(5000).cards) < len(scene.frame(7500).cards)
    assert len(scene.frame(9950).cards) == 22
    assert all(card.alpha > 0 for card in scene.frame(9000).cards)


def test_boxes_arrive_at_varied_accelerating_intervals():
    starts = [spec.start_ms for spec in M.ERRORS]
    assert starts == sorted(starts)
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert max(gaps) > 400, "the first windows are well spaced"
    assert gaps[-1] < 260, "the last windows arrive in a storm"
    assert gaps[0] > gaps[-1], "the outbreak accelerates"
    assert len(set(gaps)) >= 10, "the intervals must vary, not repeat"
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
    scene = M.StartupScene(1920, 1080)
    sizes = [(round(scene.card_size(s)[0]), round(scene.card_size(s)[1]))
             for s in M.ERRORS]
    assert len(set(sizes)) >= 8, "the windows must not all be the same size"
    bands = {}
    for spec, size in zip(M.ERRORS, sizes):
        key = round((spec.cx - spec.cy) * 20)
        bands.setdefault(key, []).append((spec.cx, spec.cy, size))
    for key, group in bands.items():
        assert len(group) <= 3, f"band {key} holds {len(group)} windows"
        if len(group) == 3:
            assert len({item[2] for item in group}) >= 2, (
                f"band {key} repeats one window size three times")
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
    assert len(M.CALM_GLITCH_TABLE) <= 8, "the countdown is calm"


def test_the_tremor_is_small_and_only_during_act_one():
    scene = M.StartupScene(1920, 1080)
    assert scene.frame(0).glitch.dx == 0
    assert abs(scene.frame(9000).glitch.dx) < 4
    assert scene.frame(10500).glitch.dx == 0
    assert scene.frame(10500).glitch.dy == 0


def test_blue_screen_wording_and_countdown():
    scene = M.StartupScene(1920, 1080)
    frame = scene.frame(12000)
    assert frame.blue.head == "AHIAN HAS TAKEN CONTROL"
    assert frame.blue.sub == "AHIAN wants to make your life beautiful."
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
    assert after.blue.open == 0.0
    assert scene.frame(10220).blue.open == 0.0
    assert 0 < scene.frame(10400).blue.open < 1
    assert scene.frame(10600).blue.open == 1.0
    assert scene.frame(18999).blue.open == 1.0


def test_every_platform_shares_the_sequence():
    signatures = set()
    for profile in M.PROFILES:
        scene = M.StartupScene(1280, 720, profile=profile)
        assert scene.profile == profile
        signatures.add((
            scene.frame(0).phase,
            scene.frame(2400).phase,
            scene.frame(12000).phase,
            scene.frame(19000).phase,
            len(scene.errors),
            scene.countdown(10000),
            round(scene.frame(12000).blue.progress, 6),
        ))
    assert len(signatures) == 1, signatures


def test_bounds_at_every_resolution():
    for profile in M.PROFILES:
        for width, height in ((480, 360), (800, 600), (1280, 720), (1920, 1080),
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


def test_reduced_motion_is_one_short_removal():
    scene = M.StartupScene(1920, 1080, reduced=True)
    assert scene.frame(0).reduced
    assert scene.frame(0).cards == ()
    assert scene.frame(0).overlay_alpha == 1.0
    assert scene.frame(M.REDUCED_MS).done
    assert scene.frame(M.REDUCED_MS).overlay_alpha == 0
    assert M.REDUCED_MS <= 800


def test_deterministic():
    a = M.StartupScene(1600, 900)
    b = M.StartupScene(1600, 900)
    assert a.errors == b.errors
    for t in (0, 2500, 7000, 10000, 13000, 18999, 19000):
        assert a.frame(t) == b.frame(t)


def test_flow_colour_is_shared_with_the_desktop():
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
    print("PASS ahian takeover: 22 windows over the live desktop, 9 s countdown, zero reveal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
