#!/usr/bin/env python3
"""Checks for the flowing AHIAN wallpaper shared by every platform."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "config/includes.chroot_after_packages/usr/local/lib/smth"))

import ahian_startup_model as M  # noqa: E402


def within(colour):
    return all(0.0 <= channel <= 1.0 for channel in colour)


def main():
    # Deep purple at the top-left, teal toward the bottom-right.
    start = M.flow_colour(0.0, 0.0, 0.0)
    end = M.flow_colour(1.0, 1.0, 0.0)
    assert start[2] > start[0] > start[1], start
    assert end[1] > end[2] > end[0], end
    # One full phase is one cycle: the reveal's last frame equals live phase 0.
    for u, v in ((0.0, 0.0), (0.23, 0.81), (0.5, 0.5), (1.0, 1.0)):
        a, b = M.flow_colour(u, v, 1.0), M.flow_colour(u, v, 0.0)
        assert all(abs(x - y) < 1e-9 for x, y in zip(a, b)), (a, b)
    # Deterministic and always inside the displayable range.
    samples = [M.flow_colour(x / 20, y / 20, 0.37) for x in range(21) for y in range(21)]
    assert samples == [M.flow_colour(x / 20, y / 20, 0.37) for x in range(21) for y in range(21)]
    assert all(within(colour) for colour in samples)
    # The flow must actually vary across the sheet, not collapse to one colour.
    assert len({tuple(round(c, 3) for c in colour) for colour in samples}) > 40
    print("PASS ahian flow: purple-teal ramp, one-cycle phase, bounded deterministic samples")


if __name__ == "__main__":
    main()
