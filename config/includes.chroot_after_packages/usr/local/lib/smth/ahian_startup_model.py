"""AHIAN desktop reconstruction timeline (shared across all three platforms).

This module is the single source of truth for the AHIAN animated desktop
reveal.  It is deliberately free of GTK, cairo, Pillow and platform APIs so
the geometry and timing can be tested on any machine.  The Linux renderer
(``ahian_startup.py``), the Android ``AhianRevealView`` and the Windows
``AhianConstructionIntro`` implement the same timeline and ordering.

Timeline (9000 ms):

    0.0 - 1.0 s   void       dark field, purple/teal fragments drifting in
    1.0 - 3.0 s   wallpaper  gradient + dot-matrix tiles assemble from fragments
    3.0 - 5.0 s   structure  taskbar segments, widgets and panels draw in
    5.0 - 7.0 s   elements   icons materialise in their real positions, a
                             window frame assembles and dissolves again
    7.0 - 9.0 s   reveal     the reconstruction settles and fades into the live
                             AHIAN desktop that is already running underneath

There are no cursors in this sequence: the desktop reconstructs itself.
"""

from dataclasses import dataclass
import math
import random

# ---- timeline ---------------------------------------------------------------
DURATION_MS = 9000
REDUCED_MS = 600

VOID_END_MS = 1000
WALL_START_MS = 1000
WALL_END_MS = 3000
STRUCT_START_MS = 3000
STRUCT_END_MS = 5000
ELEMENTS_START_MS = 5000
ELEMENTS_END_MS = 7000
REVEAL_START_MS = 7600
FADE_END_MS = DURATION_MS

TILE_SPAN_MS = 1400
TILE_DURATION_MS = 480
PARTICLE_END_MS = 3400
RING_STARTS = (1050, 1400, 1750, 2100)
RING_DURATION_MS = 1250

# ---- AHIAN palette ----------------------------------------------------------
BLACK = (0.0, 0.0, 0.0)
DARK = (0.027, 0.024, 0.050)        # #07060D, the clean dark field
WHITE = (1.0, 1.0, 1.0)
INK = (0.93, 0.90, 1.0)             # #EDE7FF
GREY = (0.55, 0.53, 0.62)
PURPLE = (0.486, 0.302, 1.0)        # AHIAN_A #7C4DFF
TEAL = (0.0, 0.76, 0.66)            # AHIAN_B #00C2A8
TEAL_BRIGHT = (0.20, 0.92, 0.80)    # #33E5CC
PURPLE_SOFT = (0.62, 0.46, 1.0)     # #9E75FF
VIOLET = (0.34, 0.22, 0.62)         # #5738A0
PANEL = (0.082, 0.063, 0.145)       # #150F25, reconstructed panel fill
WALLPAPER_PURPLE = (0.165, 0.090, 0.302)   # deep AHIAN purple
WALLPAPER_TEAL = (0.020, 0.278, 0.251)     # deep AHIAN teal

AHIAN_A = PURPLE
AHIAN_B = TEAL

PARTICLE_COLOURS = (PURPLE, TEAL, PURPLE_SOFT, TEAL_BRIGHT, VIOLET)

PROFILES = ("linux", "android", "windows")


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def ease(value):
    """Smooth, deliberately decelerating ease used by every element."""
    value = clamp(value)
    return 1.0 - (1.0 - value) ** 3


def ease_in_out(value):
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


def lerp(a, b, t):
    return a + (b - a) * t


def mix_colour(a, b, t):
    t = clamp(t)
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t))


def gradient_colour(t):
    """The AHIAN purple-to-teal gradient, top-left to bottom-right."""
    return mix_colour(PURPLE, TEAL, clamp(t))


def wallpaper_colour(t):
    """The deep purple-to-teal wall the fragments resolve into."""
    return mix_colour(WALLPAPER_PURPLE, WALLPAPER_TEAL, clamp(t))


def flow_colour(u, v, phase=0.0):
    """A paced flowing-gradient sample for the live AHIAN wallpaper.

    ``u``/``v`` are normalised screen coordinates and ``phase`` completes one
    full cycle at 1.0, so the final reveal frame (phase 1.0) is identical to
    the live desktop (phase 0.0).  Two slow diagonal waves bend a purple to
    teal ramp, and a narrow band lifts it toward the bright AHIAN inks.  The
    result is deliberately low contrast: it is a wallpaper, not a light show.
    """
    u = clamp(u)
    v = clamp(v)
    angle = (u * 1.0 + v * 0.62) * math.tau
    wave = math.sin(angle + phase * math.tau) * 0.075
    wave += math.sin((u * 1.7 - v * 1.1) * math.tau - phase * math.tau * 2) * 0.035
    band = 0.5 + 0.5 * math.sin((u * 0.8 - v * 0.55) * math.tau - phase * math.tau)
    wall = mix_colour(WALLPAPER_PURPLE, WALLPAPER_TEAL,
                      ease_in_out(clamp(u * 0.58 + v * 0.42 + wave)))
    accent = mix_colour(PURPLE_SOFT, TEAL_BRIGHT, clamp(u * 0.7 + v * 0.3))
    return mix_colour(wall, accent, 0.035 + 0.075 * band)


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self):
        return self.x + self.w

    @property
    def bottom(self):
        return self.y + self.h

    def inset(self, amount):
        return Rect(self.x - amount, self.y - amount,
                    self.w + amount * 2, self.h + amount * 2)

    def clamp_into(self, width, height):
        x = clamp(self.x, 0, max(0, width - self.w))
        y = clamp(self.y, 0, max(0, height - self.h))
        w = min(self.w, width)
        h = min(self.h, height)
        return Rect(x, y, w, h)

    def centre(self):
        return (self.x + self.w / 2, self.y + self.h / 2)


# ---- scene specs ------------------------------------------------------------
@dataclass(frozen=True)
class ParticleSpec:
    x: float          # normalized origin
    y: float
    vx: float         # normalized drift per second
    vy: float
    size: float       # normalized radius
    phase: float
    colour: tuple
    layer: int


@dataclass(frozen=True)
class TileSpec:
    key: str
    rect: Rect
    start_ms: int
    duration_ms: int
    mix: float        # 0 purple .. 1 teal
    dots: int


@dataclass(frozen=True)
class RingSpec:
    start_ms: int
    duration_ms: int
    mix: float


@dataclass(frozen=True)
class SegmentSpec:
    key: str
    rect: Rect
    start_ms: int
    duration_ms: int
    accent: tuple


@dataclass(frozen=True)
class ElementSpec:
    key: str
    label: str
    kind: str
    rect: Rect
    start_ms: int
    duration_ms: int
    accent: tuple
    end_ms: int = 0   # 0 = stays for the final frame


@dataclass(frozen=True)
class ParticleFrame:
    x: float
    y: float
    r: float
    alpha: float
    colour: tuple


@dataclass(frozen=True)
class TileFrame:
    spec: TileSpec
    progress: float
    alpha: float
    scale: float


@dataclass(frozen=True)
class RingFrame:
    x: float
    y: float
    r: float
    alpha: float
    colour: tuple


@dataclass(frozen=True)
class SegmentFrame:
    spec: SegmentSpec
    progress: float


@dataclass(frozen=True)
class ElementFrame:
    spec: ElementSpec
    progress: float
    alpha: float


@dataclass(frozen=True)
class Frame:
    t_ms: float
    phase: str
    particles: tuple
    tiles: tuple
    rings: tuple
    segments: tuple
    items: tuple
    wallpaper_alpha: float
    overlay_alpha: float
    done: bool
    reduced: bool


class StartupScene:
    """Resolution-independent AHIAN reconstruction scene."""

    def __init__(self, width, height, reduced=False, profile="linux"):
        if profile not in PROFILES:
            raise ValueError(f"unknown profile {profile!r}")
        self.profile = profile
        self.width = max(640.0, float(width))
        self.height = max(480.0, float(height))
        self.reduced = bool(reduced)
        self.portrait = self.height >= self.width * 0.95
        self.layout = self._layout()
        self.tiles = self._tiles()
        self.particles = () if self.reduced else self._particles()
        self.rings = () if self.reduced else tuple(
            RingSpec(start, RING_DURATION_MS, (i / 3.0))
            for i, start in enumerate(RING_STARTS))
        self.segments = () if self.reduced else self._segments()
        self.items = () if self.reduced else self._items()

    # ---- layout -------------------------------------------------------------
    def _layout(self):
        w, h = self.width, self.height
        margin = max(12.0, w * 0.018)
        if self.profile == "linux":
            # Mirrors home.py: Waybar across the top, shortcuts flowing in the
            # top-left, clock bottom-left and glance rings bottom-right.
            bar = Rect(0, 0, w, 38)
            clock = Rect(margin + 10, h - 104, min(240.0, w * 0.24), 46)
            rings = Rect(w - margin - 250, h - 116, 236, 84)
            window = Rect(w * 0.40, h * 0.20, w * 0.52, h * 0.50)
            if self.portrait:
                cols, rows = 2, 6
            elif w >= 1100:
                cols, rows = 4, 3
            else:
                cols, rows = 3, 4
            icon_w, icon_h = 78.0, 82.0
            icon_x, icon_y = margin + 8, bar.h + 14
            gap_x, gap_y = 10.0, 8.0
        elif self.profile == "android":
            # Mirrors MainActivity: wallpaper, shortcut column top-left and a
            # floating taskbar 46 dp tall with 12 dp side margins.
            bar = Rect(margin, h - 56, w - 2 * margin, 46)
            clock = Rect(bar.right - 116, bar.y + 9, 104, 28)
            rings = None
            window = Rect(w * 0.28, h * 0.18, w * 0.44, h * 0.50)
            cols, rows = 1, 6
            icon_w, icon_h = 92.0, 62.0
            icon_x, icon_y = margin + 8, 18.0
            gap_x, gap_y = 0.0, 4.0
        else:  # windows
            # Mirrors smth_launcher.py: shortcuts at x=44, taskbar 48 px bottom.
            bar = Rect(0, h - 49, w, 48)
            clock = Rect(w - 124, h - 44, 108, 32)
            rings = None
            window = Rect(w * 0.29, h * 0.17, w * 0.44, h * 0.52)
            cols, rows = 1, 6
            icon_w, icon_h = 128.0, 60.0
            icon_x, icon_y = 20.0, 26.0
            gap_x, gap_y = 0.0, 14.0

        icons = []
        for i in range(cols * rows):
            col, row = i % cols, i // cols
            x = icon_x + col * (icon_w + gap_x)
            y = icon_y + row * (icon_h + gap_y)
            icons.append(Rect(x, y, icon_w, icon_h).clamp_into(w, h))
        return {
            "bar": bar,
            "clock": clock,
            "rings": rings,
            "window": window,
            "icons": tuple(icons),
            "icon_cols": cols,
            "icon_rows": rows,
            "focus": (w * (0.5 if self.profile != "linux" else 0.64), h * 0.48),
            "margin": margin,
        }

    # ---- wallpaper fragments ------------------------------------------------
    def _tiles(self):
        w, h = self.width, self.height
        cols = int(clamp(round(w / 72.0), 10, 18))
        rows = int(clamp(round(h / 90.0), 6, 12))
        tile_w = w / cols
        tile_h = h / rows
        tiles = []
        for row in range(rows):
            for col in range(cols):
                order = (col / max(1, cols - 1)) * 0.58 + (row / max(1, rows - 1)) * 0.42
                start = WALL_START_MS + int(TILE_SPAN_MS * order)
                rect = Rect(col * tile_w, row * tile_h,
                            tile_w + 0.6, tile_h + 0.6)
                # Dot-matrix density: 3x3 inside every tile, 4x4 on larger ones.
                dots = 4 if min(tile_w, tile_h) > 96 else 3
                tiles.append(TileSpec(
                    key=f"tile-{row}-{col}",
                    rect=rect,
                    start_ms=start,
                    duration_ms=TILE_DURATION_MS,
                    # Colour is a pure left-to-right purple-to-teal gradient so
                    # neighbouring fragments in a column match exactly and the
                    # assembled wall has no visible tile seams.
                    mix=col / max(1, cols - 1),
                    dots=dots,
                ))
        return tuple(tiles)

    def _particles(self):
        rng = random.Random(1107)
        out = []
        for i in range(42):
            out.append(ParticleSpec(
                x=rng.uniform(0.02, 0.98),
                y=rng.uniform(0.02, 0.98),
                vx=rng.uniform(-0.012, 0.012),
                vy=rng.uniform(-0.020, -0.006),
                size=rng.uniform(0.0016, 0.0048),
                phase=rng.uniform(0.0, math.tau),
                colour=PARTICLE_COLOURS[i % len(PARTICLE_COLOURS)],
                layer=i % 3,
            ))
        return tuple(out)

    # ---- structure ----------------------------------------------------------
    def _segments(self):
        bar = self.layout["bar"]
        accents = (PURPLE, PURPLE_SOFT, TEAL, TEAL_BRIGHT, PURPLE, TEAL)
        fractions = (0.085, 0.095, 0.095, 0.095, 0.11, 0.16)
        segments = []
        cursor = bar.x + 8
        usable = bar.w - 16
        for i, frac in enumerate(fractions):
            width = max(18.0, usable * frac)
            rect = Rect(cursor, bar.y + 8, width, max(6.0, bar.h - 16))
            segments.append(SegmentSpec(
                key=f"segment-{i}",
                rect=rect.clamp_into(self.width, self.height),
                start_ms=STRUCT_START_MS + i * 110,
                duration_ms=360,
                accent=accents[i],
            ))
            cursor += width + 8
        return tuple(segments)

    def _items(self):
        lay = self.layout
        items = [
            ElementSpec("bar", "TASKBAR", "taskbar", lay["bar"],
                        STRUCT_START_MS, 620, TEAL),
            ElementSpec("bar-edge", "TASKBAR", "edge",
                        Rect(lay["bar"].x, lay["bar"].bottom - 1, lay["bar"].w, 1),
                        STRUCT_START_MS + 180, 520, TEAL_BRIGHT),
            ElementSpec("clock", "CLOCK", "clock", lay["clock"],
                        STRUCT_START_MS + 420, 560, PURPLE_SOFT),
            ElementSpec("window", "WINDOW", "window", lay["window"],
                        ELEMENTS_START_MS + 280, 900, PURPLE,
                        end_ms=6500),
        ]
        if lay["rings"] is not None:
            items.append(ElementSpec("rings", "WIDGETS", "rings", lay["rings"],
                                     STRUCT_START_MS + 620, 620, TEAL))
        for i, rect in enumerate(lay["icons"]):
            items.append(ElementSpec(
                f"icon-{i}", f"APP {i + 1:02d}", "icon", rect,
                ELEMENTS_START_MS + i * 140, 380,
                (PURPLE, TEAL, PURPLE_SOFT, TEAL_BRIGHT, VIOLET,
                 PURPLE)[i % 6]))
        return tuple(items)

    # ---- frame --------------------------------------------------------------
    def phase(self, t_ms):
        if self.reduced:
            return "reduced" if t_ms < REDUCED_MS else "done"
        if t_ms < VOID_END_MS:
            return "void"
        if t_ms < WALL_END_MS:
            return "wallpaper"
        if t_ms < STRUCT_END_MS:
            return "structure"
        if t_ms < ELEMENTS_END_MS:
            return "elements"
        if t_ms < FADE_END_MS:
            return "reveal"
        return "done"

    def _particle_frames(self, t_ms):
        if t_ms > PARTICLE_END_MS or not self.particles:
            return ()
        fade_in = clamp(t_ms / 420.0)
        fade_out = clamp((PARTICLE_END_MS - t_ms) / 900.0)
        alpha = clamp(fade_in * fade_out)
        if alpha <= 0:
            return ()
        out = []
        seconds = t_ms / 1000.0
        for spec in self.particles:
            x = (spec.x + spec.vx * seconds
                 + 0.004 * math.sin(seconds * 1.7 + spec.phase)) % 1.0
            y = (spec.y + spec.vy * seconds) % 1.0
            pulse = 0.55 + 0.45 * math.sin(seconds * 2.4 + spec.phase)
            out.append(ParticleFrame(
                x=x * self.width,
                y=y * self.height,
                r=max(0.8, spec.size * min(self.width, self.height)),
                alpha=alpha * (0.24 + 0.34 * pulse) * (0.6 + 0.4 * spec.layer / 2),
                colour=spec.colour,
            ))
        return tuple(out)

    def _tile_frames(self, t_ms):
        out = []
        for spec in self.tiles:
            progress = clamp((t_ms - spec.start_ms) / spec.duration_ms)
            if progress <= 0:
                continue
            out.append(TileFrame(
                spec=spec,
                progress=progress,
                alpha=ease(progress),
                scale=0.82 + 0.18 * ease(progress),
            ))
        return tuple(out)

    def _ring_frames(self, t_ms):
        out = []
        cx, cy = self.layout["focus"]
        base = min(self.width, self.height)
        for spec in self.rings:
            progress = clamp((t_ms - spec.start_ms) / spec.duration_ms)
            if progress <= 0 or progress >= 1:
                continue
            out.append(RingFrame(
                x=cx, y=cy,
                r=base * (0.05 + 0.42 * ease_in_out(progress)),
                alpha=(1.0 - progress) * 0.42,
                colour=mix_colour(PURPLE, TEAL, spec.mix),
            ))
        return tuple(out)

    def _segment_frames(self, t_ms):
        out = []
        for spec in self.segments:
            progress = clamp((t_ms - spec.start_ms) / spec.duration_ms)
            if progress > 0:
                out.append(SegmentFrame(spec=spec, progress=ease(progress)))
        return tuple(out)

    def _item_frames(self, t_ms):
        out = []
        for spec in self.items:
            progress = clamp((t_ms - spec.start_ms) / spec.duration_ms)
            if progress <= 0:
                continue
            alpha = 1.0
            if spec.end_ms and t_ms > spec.end_ms:
                alpha = clamp(1.0 - (t_ms - spec.end_ms) / 420.0)
                if alpha <= 0:
                    continue
            out.append(ElementFrame(spec=spec, progress=progress, alpha=alpha))
        return tuple(out)

    def frame(self, t_ms):
        if self.reduced:
            t_ms = clamp(t_ms, 0, REDUCED_MS)
            overlay = clamp(1.0 - t_ms / REDUCED_MS)
            final_tiles = tuple(
                TileFrame(spec, 1.0, 1.0, 1.0) for spec in self.tiles)
            final_items = tuple(
                ElementFrame(spec, 1.0, 1.0)
                for spec in self._final_items())
            return Frame(
                t_ms=t_ms,
                phase=self.phase(t_ms),
                particles=(),
                tiles=final_tiles,
                rings=(),
                segments=(),
                items=final_items,
                wallpaper_alpha=1.0,
                overlay_alpha=overlay,
                done=t_ms >= REDUCED_MS,
                reduced=True,
            )

        t_ms = clamp(t_ms, 0, FADE_END_MS)
        if t_ms < REVEAL_START_MS:
            overlay = 1.0
        else:
            overlay = clamp(1.0 - (t_ms - REVEAL_START_MS)
                            / (FADE_END_MS - REVEAL_START_MS))
        wallpaper_alpha = ease(clamp(
            (t_ms - WALL_START_MS) / max(1, WALL_END_MS - WALL_START_MS)))
        return Frame(
            t_ms=t_ms,
            phase=self.phase(t_ms),
            particles=self._particle_frames(t_ms),
            tiles=self._tile_frames(t_ms),
            rings=self._ring_frames(t_ms),
            segments=self._segment_frames(t_ms),
            items=self._item_frames(t_ms),
            wallpaper_alpha=wallpaper_alpha,
            overlay_alpha=overlay,
            done=t_ms >= FADE_END_MS,
            reduced=False,
        )

    def _final_items(self):
        """Items that remain in the final frame (no transient window)."""
        return tuple(spec for spec in self.items if not spec.end_ms)


# Backwards/alias names for compatibility with normal startup naming.
AhianScene = StartupScene
AhianStartupScene = StartupScene
Scene = StartupScene
AhianStartupModel = StartupScene


# Allow `python ahian_startup_model.py --print-plan`
if __name__ == "__main__":
    import sys
    if "--print-plan" in sys.argv:
        scene = StartupScene(1920, 1080)
        frame = scene.frame(5500)
        print(f"phase={frame.phase} particles={len(frame.particles)} "
              f"tiles={len(frame.tiles)} segments={len(frame.segments)} "
              f"items={len(frame.items)} duration={DURATION_MS}ms")
        sys.exit(0)
