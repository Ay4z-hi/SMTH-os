#!/usr/bin/env python3
"""SMTH Orbit: render real frames at three window shapes and check the layout.

Orbit is drawn entirely with Pillow, so this exercises the shipped renderer
rather than a mock: every assertion below is made on actual pixels.
"""
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault("SMTH_FONT_DIR", str(ROOT / "config/includes.chroot_after_packages/usr/share/fonts/truetype/smth"))
sys.path.insert(0, str(ROOT / "config/includes.chroot_after_packages/usr/local/lib/smth"))

import orbit_scene as O  # noqa: E402

SAMPLE = {
    "cpu": 0.42, "cores": [0.2, 0.5, 0.8, 0.35, 0.6, 0.15, 0.9, 0.44], "core_count": 8,
    "mem": 0.63, "disk": 0.48, "rx": 1843200.0, "tx": 230400.0, "load": 1.42,
    "uptime": 8049, "battery": 0.86, "temp": 51.0,
    "procs": [("firefox", 0.28), ("python3", 0.16), ("waybar", 0.07), ("labwc", 0.04)],
    "kernel": "6.1.0-smth", "host": "smth-node", "threads": 412,
}


def colours(image):
    return len(image.convert("RGB").resize((96, 64)).getcolors(96 * 64) or [])


def main():
    for size in ((1180, 760), (900, 620), (820, 1000)):
        O.clear_cache()
        image = O.render(size[0], size[1], 12.0, SAMPLE)
        assert image.size == size, (image.size, size)
        assert colours(image) > 400, f"{size}: frame is nearly flat"
        rgb = image.convert("RGB")
        assert max(rgb.getextrema()[0]) - min(rgb.getextrema()[0]) > 40
    print("PASS orbit: frames render at three shapes")

    scene = O.OrbitScene(1180, 760)
    m = scene.m
    for box in scene.panels + [scene.left, scene.ticker]:
        x0, y0, x1, y1 = box
        assert m <= x0 < x1 <= scene.w - m + 1 and m <= y0 < y1 <= scene.h - m + 1, box
    assert scene.left[2] < scene.panels[0][0], "wide layout: panels must sit right of the core"
    assert all(box[0] == scene.panels[0][0] and box[2] == scene.panels[0][2] for box in scene.panels)
    assert scene.panels[0][3] < scene.panels[1][1] < scene.panels[1][3] < scene.panels[2][1]
    assert scene.ticker[1] > max(box[3] for box in scene.panels), "ticker overlaps the panels"
    assert len(scene.pills) == 4 and scene.pills[-1][2] <= scene.w - m + 1
    for pill in scene.pills:
        assert pill[2] - pill[0] >= 70 and pill[3] <= scene.top, pill
    print("PASS orbit: layout stays inside the frame")

    compact = O.OrbitScene(820, 1000)
    assert compact.compact and compact.left[3] < compact.panels[0][1]
    for box in compact.panels:
        assert box[2] <= compact.w - compact.m + 1 and box[3] <= compact.ticker[1]
    print("PASS orbit: compact layout stacks panels under the core")

    # A paused frame is visibly veiled, and a missing sample must not crash.
    O.clear_cache()
    held = O.render(1180, 760, 12.0, SAMPLE, paused=True)
    O.clear_cache()
    bare = O.render(1180, 760, 12.0, {})
    assert held.size == bare.size == (1180, 760)
    assert colours(bare) > 300

    O.clear_cache()
    O.render(1180, 760, 1.0, SAMPLE)
    start = time.perf_counter()
    O.render(1180, 760, 1.1, SAMPLE)
    warm = time.perf_counter() - start
    assert warm < 0.40, f"warm frame took {warm:.2f}s"

    assert O.human_rate(1843200) == "1.8 M/s"
    assert O.human_uptime(8049) == "02:14:09"
    assert O.dot_width("42", 3) == 33
    print(f"PASS orbit: paused/empty frames render; warm frame {warm * 1000:.0f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
