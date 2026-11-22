"""AHIAN takeover: the cinematic three-act timeline (shared by every platform).

This module is the single source of truth for the AHIAN presentation.  It is
free of GTK, cairo, Pillow, Tk and Android APIs so the geometry, the wording and
the timing can be tested anywhere.  The Linux overlay and the Windows launcher
draw these frames with ``ahian_scene.py``; the Android launcher mirrors the same
values in ``AhianConstructionView.kt``.

The sequence (25.8 s, exactly three acts):

    act 1  0.0 - 10.0 s   error outbreak
           the real SMTH desktop, then custom error windows arrive at
           accelerating intervals over it.  Each window fades and scales in,
           the screen flickers, slices and splits, and the whole scene gets
           progressively noisier.  No two windows are identical and none of
           them line up on a diagonal.

    act 2  10.0 - 19.0 s  blue screen
           the desktop is squeezed to a single bright line and the full-screen
           AH1AN system screen opens from it.  It carries a real 9 second
           countdown, a stop code and a quiet progress arc, with restrained
           glitching and grain.

    act 3  19.0 - 25.8 s  transformation
           the blue screen collapses to a line again and the line opens into
           the flowing cold-glass AHIAN wallpaper.  The dot-matrix SMTH mark
           assembles, then shrinks into a corner watermark while the panel,
           icons, widgets and taskbar arrive in a coordinated stagger.  The
           overlay then fades onto the live, interactive desktop.

``unahian`` stays instant: it cancels the overlay and restores the normal
desktop with no animation at all.
"""

from dataclasses import dataclass
import math

# ---- timeline ---------------------------------------------------------------
DURATION_MS = 25800
REDUCED_MS = 700

OUTBREAK_MS = 10000            # act 1 ends here
BLUE_START_MS = OUTBREAK_MS
BLUE_END_MS = 19000            # act 2 ends here, nine full seconds of countdown
COUNTDOWN_FROM = 9

COLLAPSE_MS = 220              # desktop squeezed to a line
BLUE_OPEN_START_MS = 10220
BLUE_OPEN_MS = 380             # the blue screen opens out of that line
BLUE_CLOSE_MS = 180            # blue screen squeezed back to a line
WALL_OPEN_START_MS = 19180
WALL_OPEN_MS = 430             # the wallpaper opens out of the line

BRAND_START_MS = 19520
BRAND_MS = 980                 # last dot of the wordmark lands here
BRAND_SETTLE_MS = 20600        # mark shrinks into the corner watermark
BRAND_SETTLED_MS = 21600
PANEL_START_MS = 20120
PANEL_MS = 620
ICON_START_MS = 20460
ICON_STEP_MS = 86
ICON_MS = 430
WIDGET_START_MS = 21420
WIDGET_MS = 620
TOAST_START_MS = 22260
TOAST_MS = 320
TOAST_END_MS = 24280
SHIMMER_START_MS = 23600
SHIMMER_MS = 900
FADE_START_MS = 25000
FADE_MS = DURATION_MS - FADE_START_MS

CARD_ENTER_MS = 360            # fade + scale + drift for a new error window
CARD_FLASH_MS = 300

PROFILES = ("linux", "android", "windows")

# ---- palettes ---------------------------------------------------------------
BLACK = (0.0, 0.0, 0.0)
DARK = (0.027, 0.024, 0.050)        # #07060D, the AHIAN void
WHITE = (1.0, 1.0, 1.0)
INK = (0.949, 0.925, 1.0)           # #F2ECFF body ink on AHIAN panels
GREY = (0.596, 0.565, 0.678)        # secondary copy
PURPLE = (0.486, 0.302, 1.0)        # #7C4DFF
TEAL = (0.0, 0.76, 0.66)            # #00C2A8
TEAL_BRIGHT = (0.20, 0.92, 0.80)    # #33E5CC
PURPLE_SOFT = (0.62, 0.46, 1.0)     # #9E75FF
VIOLET = (0.34, 0.22, 0.62)         # #5738A0
PANEL = (0.082, 0.063, 0.145)       # #150F25
WALLPAPER_PURPLE = (0.165, 0.090, 0.302)
WALLPAPER_TEAL = (0.020, 0.278, 0.251)

# The normal SMTH desktop the takeover starts from.
OBSIDIAN = (0.035, 0.035, 0.043)    # #09090B
OBSIDIAN_DEEP = (0.024, 0.022, 0.029)
MAROON = (0.439, 0.106, 0.208)      # #701B35
MAROON_DEEP = (0.118, 0.039, 0.059)
BLUSH = (0.949, 0.776, 0.824)       # #F2C6D2
BLUSH_DIM = (0.400, 0.310, 0.345)

# The AH1AN blue screen.
BLUE_TOP = (0.043, 0.110, 0.259)    # #0B1C42, a deep system blue
BLUE_BOTTOM = (0.078, 0.259, 0.561)  # #14428F
BLUE_INK = (0.949, 0.969, 1.0)      # #F2F7FF
BLUE_DIM = (0.647, 0.769, 0.949)    # #A5C4F2
BLUE_RULE = (0.196, 0.318, 0.541)   # #32518A

AHIAN_A = PURPLE
AHIAN_B = TEAL

# Error-window accents: the first act is still SMTH's maroon world, and the
# AH1AN cards (accent 2) are the only ones already in the new palette.
ACCENTS = (MAROON, BLUSH, PURPLE, TEAL, PURPLE_SOFT, (0.62, 0.20, 0.34))


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def ease(value):
    """Decelerating ease used by every entrance."""
    value = clamp(value)
    return 1.0 - (1.0 - value) ** 3


def ease_in_out(value):
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


def ease_in(value):
    value = clamp(value)
    return value * value


def lerp(a, b, t):
    return a + (b - a) * t


def mix_colour(a, b, t):
    t = clamp(t)
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t))


def gradient_colour(t):
    return mix_colour(PURPLE, TEAL, clamp(t))


def wallpaper_colour(t):
    return mix_colour(WALLPAPER_PURPLE, WALLPAPER_TEAL, clamp(t))


def flow_colour(u, v, phase=0.0):
    """The live AHIAN flowing gradient, sampled by the desktop and the reveal.

    Two slow diagonal waves bend a purple to teal ramp and a narrow band lifts
    it toward the bright AHIAN inks.  ``phase`` completes one cycle at 1.0.
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


def ui_scale(width, height):
    """One uniform metric for every piece of type and padding."""
    if height >= width * 0.95:                   # portrait phone
        return clamp(min(width / 900.0, height / 1600.0), 0.72, 2.6)
    return clamp(min(width / 1280.0, height / 800.0), 0.72, 2.4)


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

    def centre(self):
        return (self.x + self.w / 2, self.y + self.h / 2)

    def moved(self, dx, dy):
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def scaled(self, factor):
        cx, cy = self.centre()
        w, h = self.w * factor, self.h * factor
        return Rect(cx - w / 2, cy - h / 2, w, h)

    def clamp_into(self, width, height):
        w = min(self.w, width)
        h = min(self.h, height)
        x = clamp(self.x, 0, max(0, width - w))
        y = clamp(self.y, 0, max(0, height - h))
        return Rect(x, y, w, h)


# ---- act 1: error windows ---------------------------------------------------
# (title, body, code, cx, cy, wf, hf, accent, start_ms)
# Every window has its own size, wording, accent and anchor.  The anchors are
# deliberately scattered across all quadrants: no two windows share a
# diagonal, and the intervals accelerate from 700 ms to a 130 ms storm.
ERROR_TABLE = (
    ("SYSTEM FAILURE", "display pipeline stopped responding", "0x00A1",
     0.235, 0.245, 0.245, 0.190, 0, 700),
    ("DESKTOP CORRUPTED", "surface buffer 3 returned an invalid state", "0x00B4",
     0.715, 0.168, 0.230, 0.155, 1, 1180),
    ("REALITY NOT FOUND", "the compositor could not resolve a scene", "0x00C9",
     0.435, 0.470, 0.265, 0.185, 2, 1620),
    ("SIGNAL LOST", "input device 0 is no longer present", "0x00D2",
     0.845, 0.350, 0.205, 0.150, 0, 2010),
    ("MEMORY MISALIGNED", "block 0x7F3A exceeds its bounds", "0x00E0",
     0.165, 0.630, 0.250, 0.175, 3, 2360),
    ("WRITE PROTECTED", "cannot persist session state", "0x00E8",
     0.560, 0.665, 0.215, 0.150, 1, 2670),
    ("RECURSION LIMIT", "the desktop rebuilt itself faster than it renders",
     "0x00F1", 0.855, 0.705, 0.235, 0.165, 0, 2950),
    ("TRUST BOUNDARY", "unrecognised aesthetic signature", "0x00F7",
     0.120, 0.415, 0.210, 0.150, 4, 3200),
    ("DISPLAY DRIVER HALTED", "falling back to software compositing", "0x0104",
     0.468, 0.218, 0.240, 0.160, 0, 3420),
    ("AHIAN INITIALIZATION", "waiting for the user to look away", "0xA11A",
     0.740, 0.500, 0.250, 0.205, 2, 3620),
    ("SESSION STATE LOST", "session 3 has no resting state", "0x0112",
     0.305, 0.315, 0.200, 0.150, 1, 3800),
    ("UNKNOWN PROCESS", "pid 1 is drawing outside the frame", "0x0118",
     0.625, 0.720, 0.215, 0.150, 3, 3960),
    ("PANEL UNRESPONSIVE", "the bar stopped greeting you", "0x011E",
     0.080, 0.790, 0.230, 0.150, 0, 4110),
    ("FACTORY COLOURS", "maroon rejected by the incoming palette", "0x0125",
     0.895, 0.150, 0.215, 0.150, 2, 4250),
    ("CLOCK OUT OF SYNC", "one second is missing", "0x012B",
     0.395, 0.815, 0.200, 0.145, 4, 6050),
    ("INDEX REBUILD", "every icon is being re-sorted", "0x0133",
     0.680, 0.300, 0.190, 0.145, 1, 6280),
    ("DESKTOP CORRUPTED", "the second pass could not repair the first", "0x0139",
     0.195, 0.155, 0.220, 0.150, 5, 6500),
    ("REALITY NOT FOUND", "retrying with a nicer one", "0x0140",
     0.520, 0.555, 0.200, 0.145, 2, 6700),
    ("AHIAN INITIALIZATION", "aesthetics 84% loaded", "0xA11A",
     0.820, 0.590, 0.210, 0.185, 3, 6880),
    ("SYSTEM FAILURE", "this is not an error any more", "0x014A",
     0.300, 0.505, 0.185, 0.140, 0, 7040),
    ("REALITY NOT FOUND", "searching a warmer universe", "0x0152",
     0.700, 0.830, 0.195, 0.145, 2, 7190),
    ("AHIAN INITIALIZATION", "do not look away", "0xA11A",
     0.455, 0.365, 0.225, 0.185, 2, 7330),
)

# Act 1 screen effects: (start_ms, duration_ms, kind, amount).
# "flash" lifts the frame, "split" separates the colour channels, "slice"
# displaces one horizontal band, "noise" grains the frame and "scan" sweeps a
# soft line down the screen.  They are sparse at first, denser near the end.
GLITCH_TABLE = (
    (1350, 70, "flash", 0.16),
    (2180, 110, "split", 2.5),
    (2960, 90, "slice", 14.0),
    (3520, 60, "flash", 0.22),
    (4020, 120, "noise", 0.35),
    (4460, 100, "split", 4.0),
    (4980, 80, "slice", 26.0),
    (5320, 90, "flash", 0.30),
    (5620, 130, "noise", 0.55),
    (5980, 110, "split", 7.0),
    (6300, 70, "scan", 0.9),
    (6620, 140, "slice", 38.0),
    (6900, 90, "flash", 0.42),
    (7180, 150, "noise", 0.75),
    (7460, 120, "split", 10.0),
    (7720, 90, "slice", 52.0),
    (7960, 70, "flash", 0.55),
    (8180, 140, "scan", 1.0),
    (8420, 160, "noise", 0.95),
    (8680, 120, "split", 13.0),
    (8930, 100, "slice", 66.0),
    (9180, 90, "flash", 0.62),
    (9420, 150, "noise", 1.1),
    (9660, 110, "split", 16.0),
    (9840, 120, "slice", 80.0),
)

# Act 2 and 3 effects, deliberately restrained.
CALM_GLITCH_TABLE = (
    (400, 90, "split", 2.0),
    (2450, 120, "slice", 10.0),
    (3600, 80, "scan", 0.8),
    (5200, 90, "split", 2.4),
    (6900, 130, "noise", 0.45),
    (8200, 100, "slice", 8.0),
    (8600, 90, "split", 2.2),
)


# The 5x7 dot glyphs used for the SMTH wordmark and the desktop clock.
BRAND_GLYPHS = {
    "S": (15, 16, 16, 14, 1, 1, 30),
    "M": (17, 27, 21, 21, 17, 17, 17),
    "T": (31, 4, 4, 4, 4, 4, 4),
    "H": (17, 17, 17, 31, 17, 17, 17),
    "A": (14, 17, 17, 31, 17, 17, 17),
    "I": (14, 4, 4, 4, 4, 4, 14),
    "N": (17, 25, 21, 19, 17, 17, 17),
    " ": (0, 0, 0, 0, 0, 0, 0),
}
DIGIT_GLYPHS = {
    "0": (14, 17, 19, 21, 25, 17, 14), "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 2, 4, 8, 31), "3": (30, 1, 1, 14, 1, 1, 30),
    "4": (2, 6, 10, 18, 31, 2, 2), "5": (31, 16, 30, 1, 1, 17, 14),
    "6": (6, 8, 16, 30, 17, 17, 14), "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14), "9": (14, 17, 17, 15, 1, 2, 12),
    ":": (0, 4, 4, 0, 4, 4, 0), " ": (0, 0, 0, 0, 0, 0, 0),
}


def glyph_dots(text, glyphs, spacing=6):
    """(col, row, order) for every lit dot, laid out on a 5x7 grid."""
    dots = []
    for index, char in enumerate(text.upper()):
        rows = glyphs.get(char, glyphs.get(" "))
        for row in range(7):
            bits = rows[row]
            for col in range(5):
                if bits >> (4 - col) & 1:
                    x = index * spacing + col
                    dots.append((x, row))
    return tuple(dots)


# ---- scene specs ------------------------------------------------------------
@dataclass(frozen=True)
class ErrorSpec:
    key: str
    title: str
    body: str
    code: str
    cx: float
    cy: float
    wf: float
    hf: float
    accent: int
    start_ms: int

    @property
    def is_ahian(self):
        return self.code == "0xA11A"


ERRORS = tuple(
    ErrorSpec(key=f"err-{index:02d}", title=row[0], body=row[1], code=row[2],
              cx=row[3], cy=row[4], wf=row[5], hf=row[6], accent=row[7],
              start_ms=row[8])
    for index, row in enumerate(ERROR_TABLE))


@dataclass(frozen=True)
class IconSpec:
    key: str
    label: str
    glyph: str
    rect: Rect
    accent: tuple


@dataclass(frozen=True)
class CardFrame:
    spec: ErrorSpec
    rect: Rect
    progress: float
    alpha: float
    flash: float


@dataclass(frozen=True)
class GlitchFrame:
    dx: float = 0.0
    dy: float = 0.0
    brightness: float = 1.0
    flash: float = 0.0
    split: float = 0.0
    slice_y: float = -1.0
    slice_shift: float = 0.0
    noise: float = 0.0
    scan_y: float = -1.0

    @property
    def active(self):
        return (self.split or self.flash or self.noise or self.slice_y >= 0
                or self.scan_y >= 0 or self.brightness != 1.0
                or abs(self.dx) > 0.01 or abs(self.dy) > 0.01)


@dataclass(frozen=True)
class BlueFrame:
    open: float
    alpha: float
    countdown: int
    tick: float
    progress: float
    head: str
    sub: str
    accent: tuple


@dataclass(frozen=True)
class TransformFrame:
    open: float
    wallpaper: float
    brand: float
    brand_alpha: float
    brand_scale: float
    brand_x: float
    brand_y: float
    panel: float
    icons: tuple
    widgets: float
    toast: float
    shimmer: float
    phase: float


@dataclass(frozen=True)
class Frame:
    t_ms: float
    phase: str
    cards: tuple
    glitch: GlitchFrame
    blue: BlueFrame
    transform: TransformFrame
    desktop_dim: float
    overlay_alpha: float
    done: bool
    reduced: bool


# ---- layout -----------------------------------------------------------------
class StartupScene:
    """Resolution-independent AHIAN takeover scene."""

    def __init__(self, width, height, reduced=False, profile="linux"):
        if profile not in PROFILES:
            raise ValueError(f"unknown profile {profile!r}")
        self.profile = profile
        self.width = max(480.0, float(width))
        self.height = max(360.0, float(height))
        self.reduced = bool(reduced)
        self.portrait = self.height >= self.width * 0.95
        self.u = ui_scale(self.width, self.height)
        self.layout = self._layout()
        self.icons = self.layout["icons"]
        self.errors = self._errors()
        self.glitches = GLITCH_TABLE
        self.calm_glitches = CALM_GLITCH_TABLE
        self.brand_dots = glyph_dots("SMTH", BRAND_GLYPHS)
        self.brand_columns = 23

    # ---- layout -------------------------------------------------------------
    def _layout(self):
        w, h, u = self.width, self.height, self.u
        if self.profile == "linux":
            bar = Rect(0, 0, w, 38 * u)
            clock = Rect(30 * u, h - 142 * u, 96 * u, 62 * u)
            rings = Rect(w - 30 * u - 236 * u, h - 156 * u, 236 * u, 78 * u)
            cols, rows = 2, 7
            cell_w, cell_h = 112 * u, 90 * u
            origin = (24 * u, 24 * u)
            labels = ("FILES", "BROWSER", "STORE", "CAMERA", "GALLERY", "PAINT",
                      "NOTES", "CALC", "PLAYER", "CLOCK", "TERMINAL", "SETTINGS")
            glyphs = ("folder", "globe", "bag", "camera", "photo", "brush",
                      "note", "calc", "play", "clock", "terminal", "gear")
        elif self.profile == "android":
            bar = Rect(12 * u, h - 66 * u, w - 24 * u, 52 * u)
            clock = Rect(bar.right - 118 * u, bar.y + 12 * u, 104 * u, 30 * u)
            rings = None
            cols, rows = 1, 6
            cell_w, cell_h = 108 * u, 78 * u
            origin = (16 * u, 22 * u)
            labels = ("TERMINAL", "CHROME", "PHONE", "MESSAGES", "CAMERA", "SETTINGS")
            glyphs = ("terminal", "globe", "phone", "chat", "camera", "gear")
        else:
            bar = Rect(0, h - 48 * u, w, 48 * u)
            clock = Rect(w - 140 * u, h - 44 * u, 124 * u, 34 * u)
            rings = None
            cols, rows = 1, 6
            cell_w, cell_h = 112 * u, 86 * u
            origin = (24 * u, 24 * u)
            labels = ("FILES", "BROWSER", "TERMINAL", "SETTINGS", "CALC", "PHOTOS")
            glyphs = ("folder", "globe", "terminal", "gear", "calc", "photo")

        icons = []
        for index in range(min(cols * rows, len(labels))):
            col, row = index // rows, index % rows
            rect = Rect(origin[0] + col * cell_w,
                        origin[1] + row * cell_h,
                        96 * u, 78 * u).clamp_into(w, h)
            icons.append(IconSpec(
                key=f"icon-{index}",
                label=labels[index % len(labels)],
                glyph=glyphs[index % len(glyphs)],
                rect=rect,
                accent=(MAROON, BLUSH, PURPLE, TEAL, PURPLE_SOFT, MAROON_DEEP)[index % 6],
            ))
        return {
            "bar": bar,
            "clock": clock,
            "rings": rings,
            "icons": tuple(icons),
            "margin": 24 * u,
            "unit": u,
        }

    # ---- act 2 layout anchors ----------------------------------------------
    def blue_layout(self):
        """Composition anchors for the AH1AN screen, in pixels."""
        w, h, u = self.width, self.height, self.u
        pad = 0.075 * w
        head_size = min(0.066 * h, 0.036 * w)
        return {
            "pad": pad,
            "mark": Rect(pad, 0.115 * h, 74 * u, 22 * u),
            "headline": (pad, 0.300 * h),
            "headline_size": head_size,
            "subline": (pad, 0.300 * h + head_size * 1.55),
            "subline_size": head_size * 0.40,
            "rule": Rect(pad, 0.300 * h + head_size * 2.35,
                         min(w - 2 * pad, 0.46 * w), max(1.0, 1.6 * u)),
            "count_y": (0.500 if self.portrait else 0.605) * h,
            "bar": Rect(pad, 0.780 * h, min(w - 2 * pad, 0.36 * w), max(2.0, 2.6 * u)),
            "meta_y": (0.840 if self.portrait else 0.870) * h,
        }

    # ---- act 1 cards --------------------------------------------------------
    def _errors(self):
        return ERRORS

    def card_size(self, spec):
        """The pixel size of one error window.

        Windows are content-sized: a title bar, one title, up to two body
        lines and a footer.  The table's ``hf`` is only a hint kept for the
        data contract; stretching a card to it used to leave dead space under
        the copy.  A small deterministic nudge by accent family keeps the
        cascade from reading as one repeated rectangle.
        """
        u = self.u
        height = (100 + 6 * (spec.accent % 3) + (10 if spec.is_ahian else 0)) * u
        return (max(spec.wf * self.width, 292 * u), height)

    def card_rect(self, spec):
        w, h = self.card_size(spec)
        x = spec.cx * self.width - w / 2
        y = spec.cy * self.height - h / 2
        return Rect(x, y, w, h).clamp_into(self.width, self.height)

    # ---- phases -------------------------------------------------------------
    def phase(self, t_ms):
        if self.reduced:
            return "reduced" if t_ms < REDUCED_MS else "done"
        if t_ms < BLUE_START_MS:
            return "outbreak"
        if t_ms < BLUE_END_MS:
            return "blue"
        if t_ms < FADE_START_MS:
            return "transform"
        if t_ms < DURATION_MS:
            return "reveal"
        return "done"

    def countdown(self, t_ms):
        remaining = BLUE_END_MS - max(t_ms, BLUE_START_MS)
        return int(clamp(math.ceil(remaining / 1000.0), 0, COUNTDOWN_FROM))

    def _cards(self, t_ms):
        out = []
        for spec in self.errors:
            if t_ms < spec.start_ms:
                continue
            progress = ease(clamp((t_ms - spec.start_ms) / CARD_ENTER_MS))
            flash = clamp(1.0 - (t_ms - spec.start_ms) / CARD_FLASH_MS)
            rect = self.card_rect(spec)
            # Entrances settle from 3% larger, and drift up by a few pixels.
            scale = 1.0 + 0.035 * (1.0 - progress)
            drift = (1.0 - progress) * 9.0 * self.u
            out.append(CardFrame(
                spec=spec,
                rect=rect.scaled(scale).moved(0, drift),
                progress=progress,
                alpha=progress,
                flash=flash,
            ))
        return tuple(out)

    # ---- act 1 glitches -----------------------------------------------------
    def _glitch(self, t_ms):
        if self.reduced:
            return GlitchFrame()
        # A slow building tremor, then nothing once the screen goes blue.
        shake = 0.0
        if t_ms < BLUE_START_MS:
            shake = 2.4 * self.u * ease_in(clamp((t_ms - 2600) / 7200))
        dx = math.sin(t_ms / 46.0) * shake
        dy = math.cos(t_ms / 61.0) * shake * 0.55
        state = {
            "dx": dx, "dy": dy, "brightness": 1.0, "flash": 0.0, "split": 0.0,
            "slice_y": -1.0, "slice_shift": 0.0, "noise": 0.0, "scan_y": -1.0,
        }
        table = self.glitches if t_ms < BLUE_START_MS else self.calm_glitches
        offset = 0 if t_ms < BLUE_START_MS else BLUE_START_MS
        for start, duration, kind, amount in table:
            start += offset
            if not start <= t_ms < start + duration:
                continue
            local = (t_ms - start) / duration
            env = math.sin(local * math.pi)
            if kind == "flash":
                state["flash"] = max(state["flash"], amount * env)
                state["brightness"] = max(state["brightness"], 1.0 + amount * 0.10)
            elif kind == "split":
                state["split"] = max(state["split"], amount * env)
            elif kind == "slice":
                state["slice_y"] = ((t_ms * 0.37) % 0.72) + 0.14
                state["slice_shift"] = amount * env * (1 if int(t_ms) % 2 else -1)
            elif kind == "noise":
                state["noise"] = max(state["noise"], amount * env)
            elif kind == "scan":
                state["scan_y"] = local
        # Persistent grain rises through the outbreak and rests low after it.
        if t_ms < BLUE_START_MS:
            state["noise"] = min(1.2, state["noise"] + 0.10 * ease(clamp(t_ms / 9000)))
        else:
            state["noise"] = min(1.0, state["noise"] + 0.06)
        return GlitchFrame(**state)

    # ---- act 2 --------------------------------------------------------------
    def _blue(self, t_ms):
        if t_ms < BLUE_OPEN_START_MS:
            opened = 0.0
        elif t_ms < BLUE_OPEN_START_MS + BLUE_OPEN_MS:
            opened = ease_in_out((t_ms - BLUE_OPEN_START_MS) / BLUE_OPEN_MS)
        else:
            opened = 1.0
        if t_ms >= BLUE_END_MS:
            opened = 0.0
        elif t_ms >= BLUE_END_MS - BLUE_CLOSE_MS:
            closed = (t_ms - (BLUE_END_MS - BLUE_CLOSE_MS)) / BLUE_CLOSE_MS
            opened = 1.0 - ease_in_out(closed)
        countdown = self.countdown(t_ms)
        since_tick = (BLUE_END_MS - t_ms) / 1000.0
        tick = clamp(1.0 - (since_tick - int(since_tick)) / 0.28) if opened else 0.0
        head = "AHIAN HAS TAKEN CONTROL"
        sub = "AHIAN wants to make your life beautiful."
        return BlueFrame(
            open=opened,
            alpha=ease(clamp((t_ms - BLUE_OPEN_START_MS) / 300.0)),
            countdown=countdown,
            tick=tick,
            progress=clamp((t_ms - BLUE_START_MS) / (BLUE_END_MS - BLUE_START_MS)),
            head=head,
            sub=sub,
            accent=TEAL_BRIGHT,
        )

    # ---- act 3 --------------------------------------------------------------
    def wallpaper_phase(self, t_ms):
        """Live-wallpaper phase so the reveal resolves onto the running desktop."""
        return ((BLUE_END_MS - t_ms) / 1000.0 * 0.022) % 1.0

    def _transform(self, t_ms):
        u = self.u
        if t_ms < WALL_OPEN_START_MS:
            opened = 0.0
        elif t_ms < WALL_OPEN_START_MS + WALL_OPEN_MS:
            opened = ease_in_out((t_ms - WALL_OPEN_START_MS) / WALL_OPEN_MS)
        else:
            opened = 1.0
        brand = clamp((t_ms - BRAND_START_MS) / (BRAND_MS + 240.0))
        settle = ease_in_out(clamp(
            (t_ms - BRAND_SETTLE_MS) / (BRAND_SETTLED_MS - BRAND_SETTLE_MS)))
        # The wordmark is the introduction, not decoration: it assembles dead
        # centre, holds, then dissolves upward as the icons take over.
        brand_alpha = 1.0 - settle
        brand_scale = 1.0 - 0.06 * settle
        brand_x = 0.5
        brand_y = lerp(0.44, 0.395, settle)
        panel = ease(clamp((t_ms - PANEL_START_MS) / PANEL_MS))
        icons = tuple(
            ease(clamp((t_ms - (ICON_START_MS + i * ICON_STEP_MS)) / ICON_MS))
            for i in range(len(self.icons)))
        widgets = ease(clamp((t_ms - WIDGET_START_MS) / WIDGET_MS))
        toast_in = ease(clamp((t_ms - TOAST_START_MS) / TOAST_MS))
        toast_out = clamp((t_ms - TOAST_END_MS) / 420.0)
        toast = toast_in * (1.0 - toast_out)
        shimmer = clamp((t_ms - SHIMMER_START_MS) / SHIMMER_MS)
        if t_ms < SHIMMER_START_MS:
            shimmer = 0.0
        return TransformFrame(
            open=opened,
            wallpaper=opened,
            brand=brand,
            brand_alpha=brand_alpha,
            brand_scale=brand_scale,
            brand_x=brand_x,
            brand_y=brand_y,
            panel=panel,
            icons=icons,
            widgets=widgets,
            toast=toast,
            shimmer=shimmer,
            phase=self.wallpaper_phase(t_ms),
        )

    # ---- frame --------------------------------------------------------------
    def frame(self, t_ms):
        phase = self.phase(t_ms)
        if self.reduced:
            t_ms = clamp(t_ms, 0, REDUCED_MS)
            overlay = 1.0 - t_ms / REDUCED_MS
            return Frame(
                t_ms=t_ms, phase=phase, cards=(), glitch=GlitchFrame(),
                blue=BlueFrame(0.0, 0.0, 0, 0.0, 0.0, "", "", TEAL_BRIGHT),
                transform=TransformFrame(
                    open=1.0, wallpaper=1.0, brand=1.0, brand_alpha=0.22,
                    brand_scale=0.30, brand_x=0.115, brand_y=0.155,
                    panel=1.0, icons=tuple(1.0 for _ in self.icons),
                    widgets=1.0, toast=0.0, shimmer=0.0, phase=0.0),
                desktop_dim=0.0, overlay_alpha=overlay,
                done=t_ms >= REDUCED_MS, reduced=True,
            )

        t_ms = clamp(t_ms, 0, DURATION_MS)
        collapse = 0.0
        if BLUE_START_MS <= t_ms < BLUE_OPEN_START_MS:
            collapse = ease_in((t_ms - BLUE_START_MS) / COLLAPSE_MS)
        if t_ms >= BLUE_END_MS - BLUE_CLOSE_MS:
            collapse = max(collapse, 0.0)
        if FADE_START_MS <= t_ms:
            overlay = clamp(1.0 - (t_ms - FADE_START_MS) / FADE_MS)
        else:
            overlay = 1.0
        return Frame(
            t_ms=t_ms,
            phase=phase,
            cards=self._cards(t_ms) if t_ms < BLUE_START_MS else (),
            glitch=self._glitch(t_ms),
            blue=self._blue(t_ms),
            transform=self._transform(t_ms),
            desktop_dim=ease(clamp(t_ms / OUTBREAK_MS)) * 0.46,
            overlay_alpha=overlay,
            done=t_ms >= DURATION_MS,
            reduced=False,
        )


# Backwards/alias names.
AhianScene = StartupScene
AhianStartupScene = StartupScene
Scene = StartupScene
AhianStartupModel = StartupScene


if __name__ == "__main__":
    import sys
    if "--print-plan" in sys.argv:
        scene = StartupScene(1920, 1080)
        for t in (0, 2400, 5200, 8600, 12000, 15000, 18600, 19800, 22000, 25000):
            frame = scene.frame(t)
            print(f"{t:>6} ms  {frame.phase:<9} cards={len(frame.cards):>2} "
                  f"count={frame.blue.countdown} open={frame.transform.open:.2f} "
                  f"icon={max(frame.transform.icons or (0,)):.2f}")
        print(f"duration={DURATION_MS}ms")
        sys.exit(0)
