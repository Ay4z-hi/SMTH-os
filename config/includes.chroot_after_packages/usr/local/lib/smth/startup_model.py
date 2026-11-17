"""SMTH OS startup construction timeline.

This module is deliberately free of GTK, cairo and Pillow so the geometry and
timing can be tested on any machine.  `startup.py` renders the same model with
GTK4/cairo.

The animation is a set of real, resolution-independent UI constructions, not a
video: a logo reveal, independent cursors, selection boxes, and a desktop being
assembled.  The final frame fades to reveal the live labwc/Waybar desktop that
is already running underneath.
"""
from dataclasses import dataclass
import math

# ---- timeline ---------------------------------------------------------------
DURATION_MS = 9600
REDUCED_MS = 760
LOGO_END_MS = 850
LOGO_FADE_END_MS = 1400
CURSOR_START_MS = 900
CONSTRUCT_START_MS = 1900
CONSTRUCT_END_MS = 7800
REVEAL_END_MS = 8600
FADE_END_MS = DURATION_MS

# ---- startup-only accents ---------------------------------------------------
# The core desktop stays black/white/grey + red; these are the construction
# accents the brief asks for and are not used by normal desktop surfaces.
BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)
GREY = (0.55, 0.55, 0.55)
RED = (0.843, 0.098, 0.129)      # #d71921
BLUE = (0.184, 0.420, 1.0)       # electric blue #2f6bff
CYAN = (0.0, 0.76, 0.66)         # #00c2a8
PURPLE = (0.486, 0.302, 1.0)     # #7c4dff
AMBER = (1.0, 0.68, 0.16)        # #ffad29

CURSOR_COLOURS = (RED, BLUE, CYAN, PURPLE, WHITE, GREY, AMBER)


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def ease(value):
    """Smooth, slightly decelerating ease used by every element."""
    value = clamp(value)
    return 1.0 - (1.0 - value) ** 3


def lerp(a, b, t):
    return a + (b - a) * t


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

    def contains(self, other):
        return (other.x >= self.x - 0.5 and other.y >= self.y - 0.5
                and other.right <= self.right + 0.5
                and other.bottom <= self.bottom + 0.5)

    def centre(self):
        return (self.x + self.w / 2, self.y + self.h / 2)


@dataclass(frozen=True)
class BuildItem:
    key: str
    label: str
    rect: Rect
    start_ms: int
    duration_ms: int
    kind: str
    accent: tuple


@dataclass(frozen=True)
class SelectionBox:
    key: str
    label: str
    rect: Rect
    start_ms: int
    duration_ms: int
    colour: tuple


@dataclass(frozen=True)
class CursorSpec:
    key: str
    colour: tuple
    points: tuple          # normalized (x, y) points, 0..1
    start_ms: int
    end_ms: int
    clicks: tuple = ()

    def position(self, t_ms, width, height):
        span = max(1, self.end_ms - self.start_ms)
        p = clamp((t_ms - self.start_ms) / span)
        if p <= 0 or p >= 1:
            return (self.points[0][0] * width, self.points[0][1] * height)
        seg = p * (len(self.points) - 1)
        index = min(len(self.points) - 2, int(seg))
        local = ease(seg - index)
        ax, ay = self.points[index]
        bx, by = self.points[index + 1]
        # A small independent wander keeps each cursor from looking scripted.
        phase = (sum(ord(c) for c in self.key) % 17) * 0.37
        wobble = math.sin(p * math.tau * 2.2 + phase) * 3.2
        return (lerp(ax, bx, local) * width + wobble,
                lerp(ay, by, local) * height - wobble * 0.6)


@dataclass(frozen=True)
class CursorFrame:
    spec: CursorSpec
    x: float
    y: float
    alpha: float
    trail: tuple
    click: float


@dataclass(frozen=True)
class BoxFrame:
    spec: SelectionBox
    progress: float
    alpha: float


@dataclass(frozen=True)
class ItemFrame:
    spec: BuildItem
    progress: float
    alpha: float


@dataclass(frozen=True)
class Frame:
    t_ms: float
    phase: str
    logo_alpha: float
    logo_reveal: float
    logo_scale: float
    cursors: tuple
    boxes: tuple
    items: tuple
    overlay_alpha: float
    done: bool
    reduced: bool


class StartupScene:
    """Resolution-independent scene. Create one per display size."""

    def __init__(self, width, height, reduced=False):
        self.width = max(640.0, float(width))
        self.height = max(480.0, float(height))
        self.reduced = bool(reduced)
        self.portrait = self.height >= self.width * 0.95
        self.layout = self._layout()
        self.items = self._items()
        self.boxes = self._boxes()
        self.cursors = () if self.reduced else self._cursors()

    # ---- layout -------------------------------------------------------------
    def _layout(self):
        w, h = self.width, self.height
        margin = max(14.0, w * 0.025)
        if self.portrait:
            status = Rect(0, 0, w, 34)
            dock = Rect(margin, h - 78, w - 2 * margin, 64)
            grid = Rect(margin, 54, w - 2 * margin, h * 0.46)
            window = Rect(margin * 1.8, h * 0.28, w - margin * 3.6, h * 0.30)
            clock = Rect(margin, h - 176, min(230.0, w - 2 * margin), 86)
            rings = Rect(margin, h - 262, min(230.0, w - 2 * margin), 80)
        else:
            status = Rect(margin, h - 60, w - 2 * margin, 48)
            dock = Rect(w * 0.5 - min(260.0, w * 0.24), h - 124,
                        min(520.0, w * 0.48), 52)
            grid = Rect(44, 44, min(430.0, w * 0.32), h - 210)
            window = Rect(w * 0.37, h * 0.17, w * 0.56, h * 0.58)
            clock = Rect(w * 0.055, h * 0.60, min(300.0, w * 0.25), h * 0.22)
            rings = Rect(w * 0.055, h * 0.46, min(300.0, w * 0.25), h * 0.12)

        cols = 3
        icon_w = max(58.0, min(88.0, (grid.w - 24) / cols - 12))
        icon_h = max(62.0, min(92.0, icon_w * 1.08))
        icons = []
        for i in range(12):
            col, row = i % cols, i // cols
            x = grid.x + 12 + col * (icon_w + 12)
            y = grid.y + 14 + row * (icon_h + 14)
            icons.append(Rect(x, y, icon_w, icon_h))
        return {
            "status": status,
            "dock": dock,
            "grid": grid,
            "window": window,
            "clock": clock,
            "rings": rings,
            "icons": tuple(icons),
            "margin": margin,
        }

    # ---- construction -------------------------------------------------------
    def _items(self):
        lay = self.layout
        if self.reduced:
            return ()
        items = [
            BuildItem("status", "TASKBAR", lay["status"], 2050, 650, "status", BLUE),
            BuildItem("grid", "APPS", lay["grid"], 2400, 700, "grid", CYAN),
            BuildItem("window", "WINDOW", lay["window"], 2900, 950, "window", PURPLE),
            BuildItem("rings", "WIDGETS", lay["rings"], 4550, 520, "rings", CYAN),
            BuildItem("clock", "CLOCK", lay["clock"], 4700, 520, "clock", WHITE),
            BuildItem("dock", "DOCK", lay["dock"], 5300, 560, "dock", RED),
        ]
        for i, rect in enumerate(lay["icons"]):
            items.append(BuildItem(f"icon-{i}", f"APP {i + 1:02d}", rect,
                                   3350 + i * 135, 330, "icon",
                                   CURSOR_COLOURS[i % len(CURSOR_COLOURS)]))
        return tuple(items)

    def _boxes(self):
        if self.reduced:
            return ()
        lay = self.layout
        boxes = [
            SelectionBox("box-status", "TASKBAR", lay["status"].inset(7), 1950, 700, BLUE),
            SelectionBox("box-grid", "APP GRID", lay["grid"].inset(7), 2280, 750, CYAN),
            SelectionBox("box-window", "WINDOW", lay["window"].inset(8), 2780, 850, PURPLE),
            SelectionBox("box-widgets", "WIDGETS", lay["rings"].inset(7), 4420, 620, CYAN),
            SelectionBox("box-clock", "CLOCK", lay["clock"].inset(7), 4600, 620, BLUE),
            SelectionBox("box-dock", "DOCK", lay["dock"].inset(7), 5150, 700, RED),
        ]
        return tuple(SelectionBox(b.key, b.label,
                                  b.rect.clamp_into(self.width, self.height),
                                  b.start_ms, b.duration_ms, b.colour)
                     for b in boxes)

    def _cursors(self):
        lay = self.layout

        def n(rect, fx, fy):
            return ((rect.x + rect.w * fx) / self.width,
                    (rect.y + rect.h * fy) / self.height)

        task = lay["status"]
        win = lay["window"]
        grid = lay["grid"]
        clock = lay["clock"]
        dock = lay["dock"]
        icons = lay["icons"]
        paths = [
            ("ARCH", RED, (n(task, 0.05, 0.0), n(task, 0.38, 0.55),
                           n(win, 0.02, 0.02), n(win, 0.35, 0.25),
                           n(win, 0.85, 0.8))),
            ("UI", BLUE, ((0.52, -0.05), n(win, 0.5, 0.08),
                          n(win, 0.08, 0.3), n(win, 0.9, 0.62),
                          n(task, 0.7, 0.5))),
            ("LAYOUT", CYAN, ((1.04, 0.18), n(win, 0.95, 0.35),
                              n(grid, 0.7, 0.25), n(icons[5], 0.5, 0.5),
                              n(win, 0.3, 0.55))),
            ("TYPE", PURPLE, ((-0.04, 0.45), n(clock, 0.85, 0.25),
                              n(clock, 0.25, 0.7), n(task, 0.2, 0.5),
                              n(win, 0.55, 0.85))),
            ("DOT", WHITE, ((0.7, -0.04), n(icons[2], 0.5, 0.4),
                            n(icons[9], 0.45, 0.5), n(dock, 0.35, 0.5),
                            n(grid, 0.2, 0.85))),
            ("GRID", GREY, ((-0.04, 0.9), n(grid, 0.5, 0.75),
                            n(icons[8], 0.55, 0.4), n(win, 0.18, 0.75),
                            n(win, 0.48, 0.35))),
            ("SYNC", AMBER, ((1.04, 0.95), n(dock, 0.7, 0.5),
                             n(task, 0.9, 0.5), n(win, 0.7, 0.2),
                             (0.55, -0.05))),
        ]
        cursors = []
        for i, (key, colour, points) in enumerate(paths):
            start = CURSOR_START_MS + i * 70
            cursors.append(CursorSpec(
                key=key,
                colour=colour,
                points=tuple(points),
                start_ms=start,
                end_ms=CONSTRUCT_END_MS - 80 + i * 25,
                clicks=(start + 900 + i * 310, 4750 + i * 210),
            ))
        return tuple(cursors)

    # ---- frame --------------------------------------------------------------
    def phase(self, t_ms):
        if self.reduced:
            return "reduced" if t_ms < REDUCED_MS else "done"
        if t_ms < LOGO_END_MS:
            return "logo"
        if t_ms < CONSTRUCT_START_MS:
            return "cursors"
        if t_ms < CONSTRUCT_END_MS:
            return "construct"
        if t_ms < REVEAL_END_MS:
            return "settle"
        if t_ms < FADE_END_MS:
            return "fade"
        return "done"

    def logo_state(self, t_ms):
        if self.reduced:
            alpha = 1.0 if t_ms < 430 else max(0.0, 1 - (t_ms - 430) / 330)
            reveal = clamp(t_ms / 420)
            return alpha, reveal, 0.94 + 0.06 * ease(reveal)
        if t_ms < 520:
            alpha = ease(t_ms / 520)
            reveal = clamp(t_ms / 560)
        elif t_ms < LOGO_END_MS:
            alpha = 1.0
            reveal = 1.0
        elif t_ms < LOGO_FADE_END_MS:
            alpha = 1 - ease((t_ms - LOGO_END_MS) / (LOGO_FADE_END_MS - LOGO_END_MS))
            reveal = 1.0
        else:
            alpha = 0.0
            reveal = 1.0
        return alpha, reveal, 0.92 + 0.08 * ease(reveal)

    def cursor_frames(self, t_ms):
        out = []
        for spec in self.cursors:
            if t_ms < spec.start_ms - 120 or t_ms > spec.end_ms + 220:
                continue
            fade_in = ease((t_ms - (spec.start_ms - 120)) / 220) if t_ms < spec.start_ms + 100 else 1.0
            fade_out = 1.0
            if t_ms > spec.end_ms - 280:
                fade_out = max(0.0, 1 - (t_ms - (spec.end_ms - 280)) / 500)
            alpha = clamp(fade_in * fade_out)
            x, y = spec.position(t_ms, self.width, self.height)
            trail = tuple(spec.position(max(spec.start_ms, t_ms - d), self.width, self.height)
                          for d in (36, 72, 112))
            click = 0.0
            for at in spec.clicks:
                delta = abs(t_ms - at)
                if delta < 240:
                    click = max(click, 1 - delta / 240)
            out.append(CursorFrame(spec, x, y, alpha, trail, click))
        return tuple(out)

    def frame(self, t_ms):
        if self.reduced:
            t_ms = clamp(t_ms, 0, REDUCED_MS)
            alpha, reveal, scale = self.logo_state(t_ms)
            overlay = 1.0 if t_ms < 430 else max(0.0, 1 - (t_ms - 430) / 330)
            return Frame(t_ms, self.phase(t_ms), alpha, reveal, scale, (), (), (),
                         overlay, t_ms >= REDUCED_MS, True)

        t_ms = clamp(t_ms, 0, FADE_END_MS)
        logo_alpha, logo_reveal, logo_scale = self.logo_state(t_ms)
        boxes = []
        for spec in self.boxes:
            progress = clamp((t_ms - spec.start_ms) / spec.duration_ms)
            if progress <= 0:
                continue
            alpha = 1.0
            if t_ms > CONSTRUCT_END_MS:
                alpha = max(0.0, 1 - (t_ms - CONSTRUCT_END_MS) / 520)
            boxes.append(BoxFrame(spec, progress, alpha))
        items = []
        for spec in self.items:
            progress = clamp((t_ms - spec.start_ms) / spec.duration_ms)
            if progress <= 0:
                continue
            items.append(ItemFrame(spec, progress, 1.0))
        fade_start = FADE_END_MS - 1000
        overlay = 1.0 if t_ms < fade_start else max(0.0, 1 - (t_ms - fade_start) / 1000)
        return Frame(
            t_ms=t_ms,
            phase=self.phase(t_ms),
            logo_alpha=logo_alpha,
            logo_reveal=logo_reveal,
            logo_scale=logo_scale,
            cursors=self.cursor_frames(t_ms),
            boxes=tuple(boxes),
            items=tuple(items),
            overlay_alpha=overlay,
            done=t_ms >= FADE_END_MS,
            reduced=False,
        )
