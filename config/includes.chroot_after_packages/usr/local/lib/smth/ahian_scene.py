"""The AHIAN takeover renderer (shared by the ISO, the EXE and the previews).

One implementation, one look.  ``ahian_startup.py`` draws these frames into a
GTK overlay and the Windows launcher draws the same frames over its live
desktop, so the ISO and the EXE match.  ``tools/render_ahian_preview.py``
writes the very same frames to PNG, which is how the animation is visually
checked without a display attached.

Every frame is RGBA.  Act 1 is transparent except for the error windows and
translucent interference, so the running desktop underneath is never replaced,
dimmed or screenshotted.  Act 2 is the opaque AH1AN screen.  At the countdown's
zero the renderer returns a fully transparent frame and the overlay is removed,
revealing the live AHIAN desktop that was running all along.

Each error window's chrome and shadow are cached, as are the blue screen
background and its dot field, so a steady-state frame is a handful of
composites.
"""
import importlib.util
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

try:
    import ahian_startup_model as _M
except ImportError:
    _HERE = os.path.dirname(os.path.abspath(__file__))
    _SPEC = importlib.util.spec_from_file_location(
        "ahian_startup_model", os.path.join(_HERE, "ahian_startup_model.py"))
    _M = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(_M)

Rect = _M.Rect

# ---- math helpers reused from the model (cold-glass rewrite) ---

def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))

def ease(value):
    value = clamp(value)
    return 1.0 - (1.0 - value) ** 3

def lerp(a, b, t):
    return a + (b - a) * t

def mix_colour(a, b, t):
    t = clamp(t)
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t))

def clamp01(value):
    return max(0.0, min(1.0, value))

def ease_in_out(value):
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)

# ---- cold-glass palette -------------------------------------------------

# The deep cool-grey world the takeover resolves onto.  No purple, no teal.
GLASS_VOID = (0.027, 0.031, 0.043)        # #07080B
GLASS_VOID_DEEP = (0.016, 0.020, 0.027)   # #040507
GLASS_PANEL = (0.055, 0.063, 0.086)       # #0E1016
GLASS_PANEL_RAISED = (0.078, 0.094, 0.133)  # #141822
GLASS_PANEL_ACTIVE = (0.102, 0.118, 0.161)  # #1A1E2A

# Inks: the only bright surface colour is a cool frosted white.
FROST = (0.906, 0.925, 0.961)             # #E7ECF5
FRAME_INK = (0.788, 0.808, 0.859)         # #C9CEDB
GHOST_INK = (0.431, 0.463, 0.525)         # #6E7686
MUTED_INK = (0.612, 0.643, 0.698)         # #9DADB2

# The single status channel. Amber is the AHIAN “attention” colour; red/green
# and a cold blue are used for specific diagnostics so windows read as states,
# not as arbitrary palette entries.
AMBER = (0.941, 0.659, 0.353)             # #F0A85A
AMBER_HOT = (1.0, 0.776, 0.478)           # #FFC67A
AMBER_SOFT = (0.855, 0.616, 0.412)        # #D9A06A
SIGNAL_RED = (0.878, 0.353, 0.353)        # #E05A5A
SIGNAL_GREEN = (0.373, 0.831, 0.627)      # #5FD4A0
BLUE_COLD = (0.310, 0.690, 0.878)         # #4FB0E0
CHROME = (0.604, 0.651, 0.749)            # #9AA6BF
CHROME_DIM = (0.431, 0.463, 0.525)        # ghosted chrome

# The blue screen has its own cold-blue identity (kept blue, retuned).
BLUE_TOP_C = (0.043, 0.110, 0.259)        # #0B1C42  (kept deep)
BLUE_BOTTOM_C = (0.082, 0.216, 0.475)     # #143776  (retuned steel-blue)
BLUE_INK_C = (0.906, 0.925, 0.961)        # #E7ECF5  (frost, not pure white)
BLUE_DIM_C = (0.612, 0.663, 0.776)        # #9FB0C5
BLUE_RULE_C = (0.227, 0.369, 0.561)       # #3A5C8E
BLUE_GLOW = (0.463, 0.725, 0.941)         # #77BCDF

# Status accent lookup for error windows.
STATUS_FAMILY = {
    0: ("alert", AMBER_HOT, AMBER, SIGNAL_RED),
    1: ("io", BLUE_COLD, GLASS_PANEL_RAISED, CHROME),
    2: ("state", AMBER_HOT, AMBER_SOFT, GLASS_PANEL_ACTIVE),
    3: ("mem", SIGNAL_RED, GLASS_PANEL_RAISED, SIGNAL_GREEN),
    4: ("diag", BLUE_COLD, GLASS_PANEL, CHROME),
    5: ("halt", SIGNAL_RED, SIGNAL_GREEN, AMBER),
}

# Compatibility aliases so the existing model-driven code still compiles and
# renders without a rewrite of the whole file.  The new identity lives in the
# *_C / GLASS_* constants above; these aliases only exist so the old code paths
# in the file still find a name.

M = _M

INK = FROST
MUTED = GHOST_INK

MAROON = (0.439, 0.106, 0.208)           # #701B35  (legacy, kept only for compat)
MAROON_DEEP = (0.118, 0.039, 0.059)
BLUSH = (0.949, 0.776, 0.824)            # #F2C6D2  (legacy, kept only for compat)
PURPLE_SOFT = (0.62, 0.46, 1.0)           # #9E75FF  (legacy alias for compat)
TEAL_BRIGHT = (0.20, 0.92, 0.80)         # #33E5CC  (legacy alias for compat)
PURPLE = (0.486, 0.302, 1.0)             # #7C4DFF  (legacy alias for compat)
TEAL = (0.0, 0.76, 0.66)                 # #00C2A8  (legacy alias for compat)
VIOLET = (0.34, 0.22, 0.62)              # #5738A0  (legacy alias for compat)

DIGIT_GLYPHS = _M.DIGIT_GLYPHS




try:                                        # normal import, ISO and tests
    import ahian_startup_model as M
except ImportError:                         # bundled next to a frozen EXE
    _HERE = os.path.dirname(os.path.abspath(__file__))
    _SPEC = importlib.util.spec_from_file_location(
        "ahian_startup_model", os.path.join(_HERE, "ahian_startup_model.py"))
    M = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(M)


def draw_on(layer):
    """ImageDraw that really blends: correct on RGB, harmless elsewhere."""
    try:
        return ImageDraw.Draw(layer, "RGBA")
    except (ValueError, AttributeError):
        return ImageDraw.Draw(layer)


def rgba(colour, alpha=255):
    return (int(colour[0] * 255), int(colour[1] * 255), int(colour[2] * 255),
            max(0, min(255, int(alpha))))


def ink(colour):
    """A model colour (floats) to an 8-bit RGB triple."""
    return (int(colour[0] * 255), int(colour[1] * 255), int(colour[2] * 255))


FONT_NAMES = (
    # Cold-glass identity uses a true monospace for codes/status and a clean
    # sans for brand copy/headlines. These are the fonts that actually exist in
    # this environment and on the target installs.
    "DejaVuSansMono-Bold.ttf",
    "DejaVuSansMono.ttf",
    "DejaVuSans-Bold.ttf",
    "DejaVuSans.ttf",
    "DejaVuSansDisplay.ttf",
    "DejaVuSansMono-BoldOblique.ttf",
    "DejaVuSansMono-Oblique.ttf",
    "DejaVuSans-BoldOblique.ttf",
    "DejaVuSans-Oblique.ttf",
    "DejaVuSerif-Bold.ttf",
    "DejaVuSerif.ttf",
    "DejaVuSerifDisplay.ttf",
    "DejaVuSansMono.ttf",
    "DejaVuSansMono-Bold.ttf",
    "cmtt10.ttf",
    "SpaceMono-Regular.ttf",
    "DejaVuSansMono.ttf",
    "consola.ttf",
    "LiberationMono-Regular.ttf",
    "Menlo.ttc",
    "Courier New.ttf",
)

# Where the cold-glass fonts actually live in this environment.
FONT_DIRS = (
    "/opt/freestyle/python/lib/python3.12/site-packages/matplotlib/mpl-data/fonts/ttf",
    "/opt/freestyle/python/lib/python3.12/site-packages/matplotlib/mpl-data/fonts/ttf",
)



class Fonts:
    """A small curated font rack for the cold-glass AHIAN identity.

    ``get(size, family, weight)`` returns a font for the given role.  Families:

    * ``mono``  — DejaVu Sans Mono, for codes, status and dot-matrix readout.
    * ``sans``  — DejaVu Sans, for card body and blue-screen sub copy.
    * ``display`` — DejaVu Sans Display / DejaVu Serif Display for the blue
      screen headline and the brand mark when a more “celestial” voice is wanted.
    * ``dot``   — a monospace for the dot-matrix SMTH mark and clock.

    Weight is ``"regular"`` or ``"bold"``.
    """

    MONO = "mono"
    SANS = "sans"
    DISPLAY = "display"
    DOT = "dot"

    def __init__(self, directories=()):
        self.directories = [d for d in directories if d] + list(FONT_DIRS)
        self._cache = {}

    def _candidate_paths(self, family, weight):
        if family == self.MONO:
            if weight == "bold":
                return ("DejaVuSansMono-Bold.ttf", "DejaVuSansMono.ttf",
                        "cmtt10.ttf")
            return ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf",
                    "cmtt10.ttf")
        if family == self.SANS:
            if weight == "bold":
                return ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf",
                        "DejaVuSans-BoldOblique.ttf")
            return ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf",
                    "DejaVuSans-Oblique.ttf")
        if family == self.DISPLAY:
            if weight == "bold":
                return ("DejaVuSansDisplay.ttf", "DejaVuSans-Bold.ttf",
                        "DejaVuSerif-Bold.ttf", "DejaVuSerifDisplay.ttf")
            return ("DejaVuSansDisplay.ttf", "DejaVuSerifDisplay.ttf",
                    "DejaVuSans.ttf", "DejaVuSerif.ttf")
        # ``dot`` is visually a monospace but we keep it distinct so the SMTH
        # mark and clock can be tuned independently of code readout.
        if weight == "bold":
            return ("DejaVuSansMono-Bold.ttf", "DejaVuSansMono.ttf",
                    "DejaVuSans-Bold.ttf")
        return ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf",
                "DejaVuSans.ttf")

    def _find(self, name):
        for root in self.directories:
            candidate = os.path.join(root, name)
            if os.path.isfile(candidate):
                return candidate
        for root in self.directories:
            if not os.path.isdir(root):
                continue
            for base, _dirs, files in os.walk(root):
                if name in files:
                    return os.path.join(base, name)
        # Fall back to the broader search the old code already did.
        for root in [
            "/usr/share/fonts/truetype/dejavu",
            "/usr/share/fonts/truetype/space-mono",
            "/usr/share/fonts/truetype",
            "/usr/share/fonts/truetype/msttcorefonts",
            "/usr/share/fonts",
            "C:/Windows/Fonts",
            os.path.expanduser("~/Library/Fonts"),
            "/System/Library/Fonts",
        ]:
            candidate = os.path.join(root, name)
            if os.path.isfile(candidate):
                return candidate
        for root in [
            "/usr/share/fonts/truetype/dejavu",
            "/usr/share/fonts/truetype/space-mono",
            "/usr/share/fonts/truetype",
            "/usr/share/fonts/truetype/msttcorefonts",
            "/usr/share/fonts",
            "C:/Windows/Fonts",
            os.path.expanduser("~/Library/Fonts"),
            "/System/Library/Fonts",
        ]:
            if not os.path.isdir(root):
                continue
            for base, _dirs, files in os.walk(root):
                if name in files:
                    return os.path.join(base, name)
        return None

    def get(self, size, family=None, weight="regular"):
        # Backward compatible: ``get(size)`` still returns a default sans.
        if family is None:
            family, weight = self.SANS, "regular"
        key = (size, family, weight)
        font = self._cache.get(key)
        if font is None:
            path = None
            for candidate in self._candidate_paths(family, weight):
                path = self._find(candidate)
                if path:
                    break
            try:
                font = (
                    ImageFont.truetype(path, max(6, int(round(size))))
                    if path
                    else None
                )
            except (OSError, TypeError):
                font = None
            if font is None:
                try:
                    font = ImageFont.load_default(
                        max(6, int(round(size))))
                except TypeError:                       # Pillow < 10.1
                    font = ImageFont.load_default()
            self._cache[key] = font
        return font


def clamp01(value):
    return max(0.0, min(1.0, value))


def measure(font, text, tracking=0.0):
    if not text:
        return 0.0
    return sum(font.getlength(ch) for ch in text) + tracking * max(0, len(text) - 1)


def to_argb32(image):
    """Return ``(buffer, stride)``: the frame as cairo ARGB32 (premultiplied BGRA).

    A cairo ImageSurface points straight at this buffer, so the caller must keep
    it alive for as long as the surface is in use.  Overlay frames are mostly
    transparent, so the colour channels are premultiplied by alpha or the
    compositor would show the window cards as bright fringes.
    """
    rgba = image.convert("RGBA")
    if rgba.getchannel("A").getextrema()[0] < 255:
        r, g, b, a = rgba.split()
        rgba = Image.merge("RGBA", (ImageChops.multiply(r, a),
                                    ImageChops.multiply(g, a),
                                    ImageChops.multiply(b, a), a))
    return bytearray(rgba.tobytes("raw", "BGRA")), rgba.width * 4


def flatten(fill, backdrop):
    """Make a text colour opaque against its surface.

    Pillow draws glyphs without honouring small alpha values (alpha 0 renders
    almost white), so every text colour is pre-blended with what is behind it.
    """
    if len(fill) < 4 or fill[3] >= 250:
        return fill[:3] if len(fill) >= 3 else fill
    alpha = max(0, min(255, fill[3])) / 255.0
    return tuple(int(backdrop[i] + (fill[i] - backdrop[i]) * alpha) for i in range(3))


def put_text(draw, xy, text, font, fill, tracking=0.0, bold=False, anchor="left"):
    """Type with real letter spacing, an optional faux bold, and cold-glass safe alpha."""
    fill = flatten(fill, getattr(draw, "backdrop", (10, 11, 14)))
    width = measure(font, text, tracking)
    x, baseline = xy
    if anchor == "right":
        x -= width
    elif anchor == "center":
        x -= width / 2
    for ch in text:
        draw.text((x, baseline), ch, font=font, fill=fill, anchor="ls")
        if bold:
            draw.text((x + max(0.6, font.size * 0.035), baseline), ch,
                      font=font, fill=fill, anchor="ls")
        x += font.getlength(ch) + tracking
    return width


def wrap(font, text, tracking, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and measure(font, candidate, tracking) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


# ---- cold-glass palette (new AHIAN identity) -----------------------------

# The deep cool-grey world the takeover resolves onto.  No purple, no teal.
GLASS_VOID = (0.027, 0.031, 0.043)        # #07080B
GLASS_VOID_DEEP = (0.016, 0.020, 0.027)   # #040507
GLASS_PANEL = (0.055, 0.063, 0.086)       # #0E1016
GLASS_PANEL_RAISED = (0.078, 0.094, 0.133)  # #141822
GLASS_PANEL_ACTIVE = (0.102, 0.118, 0.161)  # #1A1E2A

# Inks: the only bright surface colour is a cool frosted white.
FROST = (0.906, 0.925, 0.961)             # #E7ECF5
FRAME_INK = (0.788, 0.808, 0.859)         # #C9CEDB
GHOST_INK = (0.431, 0.463, 0.525)         # #6E7686
MUTED_INK = (0.612, 0.643, 0.698)         # #9DAD B2

# The single status channel. Amber is the AHIAN “attention” colour; red/green
# and a cold blue are used for specific diagnostics so windows read as states,
# not as arbitrary palette entries.
AMBER = (0.941, 0.659, 0.353)             # #F0A85A
AMBER_HOT = (1.0, 0.776, 0.478)           # #FFC67A
AMBER_SOFT = (0.855, 0.616, 0.412)        # #D9A06A
SIGNAL_RED = (0.878, 0.353, 0.353)        # #E05A5A
SIGNAL_GREEN = (0.373, 0.831, 0.627)      # #5FD4A0
BLUE_COLD = (0.310, 0.690, 0.878)         # #4FB0E0
CHROME = (0.604, 0.651, 0.749)            # #9AA6BF
CHROME_DIM = (0.431, 0.463, 0.525)        # ghosted chrome
DEEP_BLUE = (0.102, 0.161, 0.227)         # #1A2A3A

# The blue screen has its own cold-blue identity (kept blue, retuned).
BLUE_TOP_C = (0.043, 0.110, 0.259)        # #0B1C42  (kept deep)
BLUE_BOTTOM_C = (0.082, 0.216, 0.475)     # #143776  (retuned steel-blue)
BLUE_INK_C = (0.906, 0.925, 0.961)        # #E7ECF5  (frost, not pure white)
BLUE_DIM_C = (0.612, 0.663, 0.776)        # #9FB0C5
BLUE_RULE_C = (0.227, 0.369, 0.561)       # #3A5C8E
BLUE_GLOW = (0.463, 0.725, 0.941)         # #77BCDF

# Status accent lookup for error windows.  The model's ACCENTS tuple is no
# longer used for card chrome; cards now derive their accent from their code
# and from a deterministic status family.
STATUS_FAMILY = {
    0: ("alert", AMBER_HOT, AMBER, SIGNAL_RED),
    1: ("io", BLUE_COLD, GLASS_PANEL_RAISED, CHROME),
    2: ("state", AMBER_HOT, AMBER_SOFT, GLASS_PANEL_ACTIVE),
    3: ("mem", SIGNAL_RED, GLASS_PANEL_RAISED, SIGNAL_GREEN),
    4: ("diag", BLUE_COLD, GLASS_PANEL, CHROME),
    5: ("halt", SIGNAL_RED, SIGNAL_GREEN, AMBER),
}


def status_accent(spec):
    """A small, coherent status palette for one error window.

    Returns (rail, border, glow, ink, muted) in 0-1 float triplets.
    """
    family, a, b, c = STATUS_FAMILY[spec.accent % len(STATUS_FAMILY)]
    return {
        "rail": a,
        "border": mix_colour(a, GLASS_PANEL_RAISED, 0.35),
        "glow": mix_colour(a, GLASS_VOID_DEEP, 0.25),
        "ink": FROST,
        "muted": GHOST_INK,
        "chrome": CHROME,
    }


def glass_fill(top, bottom, alpha=0.96):
    """A vertical glass panel gradient as an RGB image."""
    if top == bottom:
        img = Image.new("RGB", (2, 2), ink(mid(top, bottom)))
    else:
        img = Image.new("RGB", (2, 4))
        d = ImageDraw.Draw(img)
        for y in range(4):
            t = y / 3.0
            d.line((0, y, 2, y), fill=ink(mix_colour(top, bottom, t)))
    if alpha < 0.999:
        img = img.convert("RGBA")
        img.putalpha(int(alpha * 255))
        img = img.convert("RGB")
    return img.resize((2, 2), Image.BILINEAR)


def mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)


class SceneRenderer:
    """Draws any frame of the AHIAN takeover at the scene's resolution."""

    CARD_HEADERS = ("SMTH SYSTEM", "SURFACE", "AHIAN WATCH", "COMPOSITOR",
                    "SESSION", "INDEX", "INPUT", "STORE", "DISPLAY",
                    "MEMORY", "DRIVER", "SIGNAL")

    def __init__(self, scene, font_dirs=(), wallpaper=None):
        self.scene = scene
        self.w = int(scene.width)
        self.h = int(scene.height)
        self.u = scene.u
        self.fonts = Fonts(font_dirs)
        self.wallpaper_source = wallpaper
        self._cards = {}
        self._shadows = {}
        self._base_alpha = {}
        self._blue_bg = None
        self._blue_grid = None
        self._noise = None
        self._vignette_cache = None
        self._bg = (10, 11, 14)

    # ---- helpers ------------------------------------------------------------
    def px(self, value):
        return value * self.u

    def _d(self, image):
        draw = draw_on(image)
        draw.backdrop = self._bg
        return draw

    def _gradient(self, top, bottom, height=128):
        small = Image.new("RGB", (2, height))
        draw = draw_on(small)
        for y in range(height):
            ratio = y / max(1, height - 1)
            draw.line((0, y, 2, y), fill=tuple(
                int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)))
        return small.resize((self.w, self.h), Image.BILINEAR)

    def _blurred_bloom(self, centre, radius, colour, alpha):
        """A soft radial light: one ellipse, heavily blurred, scaled up.

        Building it small and blurring there keeps the falloff perfectly
        smooth: no visible edge, no banding, and it costs almost nothing.
        """
        small_w = max(24, self.w // 6)
        small_h = max(16, self.h // 6)
        small = Image.new("L", (small_w, small_h), 0)
        draw = ImageDraw.Draw(small)
        cx = centre[0] * small_w
        cy = centre[1] * small_h
        rx = max(1.0, radius[0] * small_w)
        ry = max(1.0, radius[1] * small_h)
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
        mask = small.filter(
            ImageFilter.GaussianBlur(max(2.0, small_w * 0.10))
        ).resize((self.w, self.h), Image.BICUBIC)
        layer = Image.new("RGBA", (self.w, self.h), rgba(colour, 255))
        layer.putalpha(mask.point(lambda v, a=alpha: int(v * a / 255.0)))
        return layer

    def _blurred_bloom_rgb(self, centre, radius, colour, alpha):
        """Same bloom, returned as RGB so it can be alpha_composited directly."""
        return self._blurred_bloom(centre, radius, colour, alpha).convert("RGB")

    def _paste(self, base, sprite, xy):
        if getattr(sprite, "mode", None) != "RGBA":
            sprite = sprite.convert("RGBA")
        base.paste(sprite, (int(round(xy[0])), int(round(xy[1]))), sprite)

    # ---- cold glass helpers ------------------------------------------------
    def _glass_panel(self, rect, status="amber", progress=1.0, raised=False,
                     glow=False, active=False, rail=True, highlight=True,
                     shine=True):
        """One liquid-glass tile: a deep cold panel with a status rail, a
        hard inner frame, a top highlight and a soft shadow underlay.

        ``status`` is one of ``"amber"``, ``"red"``, ``"green"``, ``"blue"``,
        ``"chrome"``.
        """
        p = min(1.0, max(0.0, progress))
        accents = {
            "amber": (AMBER_HOT, AMBER_SOFT, AMBER, CHROME, FROST),
            "red": (SIGNAL_RED, mix_colour(SIGNAL_RED, GLASS_PANEL, 0.5),
                    SIGNAL_RED, CHROME, FROST),
            "green": (SIGNAL_GREEN, mix_colour(SIGNAL_GREEN, GLASS_PANEL, 0.5),
                      SIGNAL_GREEN, CHROME, FROST),
            "blue": (BLUE_COLD, mix_colour(BLUE_COLD, GLASS_PANEL, 0.5),
                     BLUE_COLD, CHROME, FROST),
            "chrome": (CHROME, mix_colour(CHROME, GLASS_PANEL, 0.4),
                       CHROME, CHROME, FROST),
        }
        track, border, rail_c, edge, highlight = accents.get(
            status, accents["amber"])
        base = GLASS_PANEL_ACTIVE if active else (GLASS_PANEL_RAISED if raised
                                                   else GLASS_PANEL)
        # Body: gentle vertical gradient into the void.
        w = max(2, int(rect.w))
        h = max(2, int(rect.h))
        img = Image.new("RGB", (w, h))
        d = ImageDraw.Draw(img)
        for y in range(h):
            t = y / max(1, h - 1)
            c = mix_colour(base, GLASS_VOID_DEEP, t)
            d.line((0, y, w - 1, y), fill=ink(c))
        # Faint vertical glaze: panel feels like glass, not flat paint.
        glaze = Image.new("RGBA", (w, h), rgba((0.14, 0.16, 0.22), 4))
        img = Image.alpha_composite(img.convert("RGBA"), glaze).convert("RGB")
        draw = self._d(img)
        inset = max(1, int(self.px(0.7)))
        # Bottom shadow stroke: anchors the glass panel in space.
        draw.line((0, h - 1, w, h - 1), fill=rgba(GLASS_VOID_DEEP, 255),
                  width=max(1, int(self.px(0.8))))
        # Soft outer shadow underlay: so stacked panels read in depth.
        if raised or glow:
            shadow = Image.new("RGBA", (w + max(8, int(self.px(6))),
                                         h + max(8, int(self.px(6)))),
                               (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle(
                (int(self.px(3)), int(self.px(4)), w + int(self.px(3)),
                 h + int(self.px(4))),
                radius=max(1, int(self.px(3))),
                fill=(0, 0, 0, 96))
            shadow = shadow.filter(ImageFilter.GaussianBlur(self.px(5)))
            return img, shadow, (int(inset), int(self.px(6)))
        # Hard inner frame — the cut-glass edge.
        if p > 0.02:
            draw.rectangle(
                (inset, inset, w - inset, h - inset),
                outline=rgba(edge, int(55 + 40 * p)),
                width=max(1, int(self.px(0.6))))
        # Soft inner frame, status-tinted, one pixel in.
        if p > 0.02 and rail:
            inner = max(1, int(self.px(1.2)))
            draw.rectangle(
                (inset + inner, inset + inner, w - inset - inner,
                 h - inset - inner),
                outline=rgba(border, int(45 * p)),
                width=max(1, int(self.px(0.5))))
        # Top highlight: only the top ~14% of the panel catches light.
        if p > 0.02 and highlight:
            hl_h = max(1, int(h * 0.14))
            draw.line((inset, inset, w - inset, inset),
                      fill=rgba(highlight, int(55 * p)),
                      width=max(1, int(self.px(0.5))))
        # Status rail along the top edge.
        if p > 0.02 and rail:
            rail_h = max(1, int(self.px(1.2)))
            draw.rectangle(
                (inset, inset, w - inset, inset + rail_h),
                fill=rgba(rail_c, int(70 * p)))
        # Glass shine: a subtle diagonal specular on raised panels.
        if shine and raised and p > 0.02:
            shine_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shine_img)
            sw = max(2, int(w * 0.10))
            sh = max(2, int(h * 0.30))
            sd.polygon([(0, 0), (sw, 0), (sw - sh, h), (-sh, h)],
                       fill=rgba(FROST, int(9 * p)))
            img = Image.alpha_composite(img.convert("RGBA"), shine_img).convert("RGB")
        return img

    def _dot_matrix(self, draw, text, x, baseline, dot, colour, glyphs=None,
                    tracking=1):
        """Dot-matrix type: the SMTH identity, identical on every platform."""
        glyphs = glyphs or _M.BRAND_GLYPHS
        spacing = 5 + tracking
        for index, char in enumerate(text.upper()):
            rows = glyphs.get(char, glyphs.get(" "))
            for row in range(7):
                bits = rows[row]
                for col in range(5):
                    if bits >> (4 - col) & 1:
                        cx = x + (index * spacing + col) * dot
                        cy = baseline - (6 - row) * dot - dot * 0.5
                        draw.ellipse((cx - dot * 0.38, cy - dot * 0.38,
                                      cx + dot * 0.38, cy + dot * 0.38), fill=colour)
        return len(text) * spacing * dot

    # ---- glyphs -------------------------------------------------------------
    def _card_palette(self, spec):
        family, accent, soft, chrome = STATUS_FAMILY[
            spec.accent % len(STATUS_FAMILY)]
        return {
            "status": {"alert": "amber", "io": "blue", "state": "amber",
                       "mem": "red", "diag": "blue", "halt": "red"}.get(
                           family, "amber"),
            "accent": accent,
            "soft": soft,
            "ink": FROST,
            "muted": MUTED_INK,
            "ghost": GHOST_INK,
        }

    def _card_face(self, img, spec, pal):
        """Chrome and copy for one error window, drawn on its glass body."""
        w, h = img.size
        u, px = self.u, self.px
        ahian = spec.is_ahian
        readout = (not ahian) and spec.accent % 2 == 1
        accent = pal["accent"]
        draw = self._d(img)
        draw.backdrop = ink(GLASS_PANEL)
        pad = px(15)
        right = w - px(13)
        bar_h = px(24)

        def mono(size, weight="regular"):
            return self.fonts.get(size * u, family=self.fonts.MONO,
                                  weight=weight)

        def sans(size, weight="regular"):
            return self.fonts.get(size * u, family=self.fonts.SANS,
                                  weight=weight)

        # ---- title bar (dialogs) or a diagnostic header (readouts)
        if readout:
            tag_font = mono(7.0, "bold")
            put_text(draw, (pad, px(14)), "DIAGNOSTIC READOUT", tag_font,
                     rgba(mix_colour(accent, FROST, 0.25), 230),
                     tracking=px(1.4))
            put_text(draw, (right, px(14)), spec.code, mono(8.0, "bold"),
                     rgba(accent, 245), tracking=px(0.6), anchor="right")
            draw.line((pad, px(20), right, px(20)), fill=rgba(FROST, 26),
                      width=max(1, int(px(0.6))))
            title_y = px(38)
            body_y = px(54)
        else:
            bar_fill = ((0.130, 0.110, 0.080) if ahian
                        else (0.100, 0.112, 0.146))
            draw.rectangle((0, 0, w, bar_h), fill=ink(bar_fill))
            draw.line((0, bar_h, w, bar_h), fill=rgba((0, 0, 0), 120),
                      width=max(1, int(px(0.7))))
            draw.line((0, bar_h + 1, w, bar_h + 1), fill=rgba(FROST, 14),
                      width=1)
            # Status lozenge: the same mark on every SMTH window.
            glyph = px(3.2)
            gx, gy = pad + glyph, bar_h / 2
            draw.polygon([(gx, gy - glyph), (gx + glyph, gy),
                          (gx, gy + glyph), (gx - glyph, gy)],
                         fill=rgba(accent, 245))
            label_font = mono(6.9, "bold")
            name = "AH1AN" if ahian else "SMTH OS"
            put_text(draw, (pad + px(11), bar_h / 2 + px(2.5)), name,
                     label_font, rgba(FROST, 245), tracking=px(1.2))
            tag_x = (pad + px(11) + measure(label_font, name, px(1.2))
                     + px(9))
            put_text(draw, (tag_x, bar_h / 2 + px(2.5)), "SYSTEM",
                     label_font, rgba(GHOST_INK, 215), tracking=px(1.2))
            cy = bar_h / 2
            if ahian:
                put_text(draw, (right, cy + px(2.5)), "0xA11A",
                         mono(8.0, "bold"), rgba(accent, 240),
                         tracking=px(0.8), anchor="right")
            else:
                # Window controls: minimise, maximise, close.
                draw.line((right - px(38), cy, right - px(32), cy),
                          fill=rgba(CHROME, 195), width=1)
                draw.rectangle((right - px(23), cy - px(2.4),
                                right - px(18), cy + px(2.4)),
                               outline=rgba(CHROME, 195), width=1)
                draw.line((right - px(10), cy - px(2.6),
                           right - px(5), cy + px(2.6)),
                          fill=rgba(CHROME, 215), width=1)
                draw.line((right - px(10), cy + px(2.6),
                           right - px(5), cy - px(2.6)),
                          fill=rgba(CHROME, 215), width=1)
            title_y = bar_h + px(23)
            body_y = bar_h + px(39) + (px(2) if ahian else 0)

        # ---- title: the loudest voice on the window
        title = spec.title
        size = 13.2
        while size > 9.0:
            candidate = sans(size, "bold")
            if measure(candidate, title, px(0.5)) <= right - pad:
                break
            size -= 0.4
        put_text(draw, (pad, title_y), title, sans(size, "bold"),
                 rgba(FROST, 255), tracking=px(0.5), bold=True)

        # ---- body: at most two quiet lines
        body_font = sans(9.5)
        body_y = body_y
        for line in wrap(body_font, spec.body, 0.0, right - pad - px(2))[:2]:
            put_text(draw, (pad, body_y), line, body_font,
                     rgba(pal["muted"], 245), tracking=px(0.15))
            body_y += px(13.6)

        # ---- AH1AN progress rail
        footer_y = h - px(11)
        if ahian:
            track_y = footer_y - px(15)
            draw.line((pad, track_y, right, track_y), fill=rgba(FROST, 26),
                      width=max(1, int(px(1.5))))
            lit = pad + (right - pad) * 0.62
            draw.line((pad, track_y, lit, track_y), fill=rgba(accent, 240),
                      width=max(1, int(px(1.7))))

        # ---- footer: state on the left, stop code on the right
        draw.line((pad, footer_y - px(8), right, footer_y - px(8)),
                  fill=rgba(FROST, 22), width=max(1, int(px(0.6))))
        state = ("AESTHETIC SUBSYSTEM" if ahian
                 else ("RETRYING" if spec.accent % 2
                       else "NO RESPONSE"))
        put_text(draw, (pad, footer_y), state, mono(6.9),
                 rgba(GHOST_INK, 240), tracking=px(1.2))
        put_text(draw, (right, footer_y), spec.code, mono(8.0, "bold"),
                 rgba(accent, 245), tracking=px(0.7), anchor="right")

    def _card_sprite(self, spec):
        self._bg = ink(GLASS_PANEL)
        sprite = self._cards.get(spec.key)
        if sprite is not None:
            return sprite
        w, h = self.scene.card_size(spec)
        w, h = max(2, int(round(w))), max(2, int(round(h)))
        u, px = self.u, self.px
        pal = self._card_palette(spec)
        ahian = spec.is_ahian
        # A glass sheet: deep, cool, lit from above.
        top = (0.088, 0.098, 0.128) if not ahian else (0.106, 0.096, 0.076)
        bottom = (0.030, 0.035, 0.048) if not ahian else (0.041, 0.036, 0.029)
        img = Image.new("RGB", (w, h))
        body_draw = ImageDraw.Draw(img)
        for y in range(h):
            t = (y / max(1, h - 1)) ** 0.9
            body_draw.line((0, y, w - 1, y),
                           fill=ink(mix_colour(top, bottom, t)))
        # Status rail down the left edge: the one saturated surface.
        rail_w = max(2, int(px(2.6)))
        body_draw.rectangle(
            (0, 0, rail_w, h),
            fill=ink(mix_colour(pal["accent"], top, 0.12)))
        self._card_face(img, spec, pal)

        # Round the sheet, then cut a frost hairline along its edge.
        sprite = img.convert("RGBA")
        radius = max(2, int(px(9)))
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, w - 1, h - 1), radius=radius, fill=255)
        sprite.putalpha(mask)
        edge = draw_on(sprite)
        edge.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius,
                               outline=rgba(FROST, 42), width=1)
        edge.line((rail_w + 1, 1, rail_w + 1, h - 2),
                  fill=rgba(FROST, 12), width=1)

        # A soft shadow makes each window sit above the buried desktop.
        shadow = Image.new("RGBA", (w + int(px(30)), h + int(px(34))),
                           (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (int(px(8)), int(px(11)), w + int(px(8)), h + int(px(11))),
            radius=max(2, int(px(10))), fill=(0, 0, 0, 150))
        shadow = shadow.filter(ImageFilter.GaussianBlur(px(9)))

        self._shadows[spec.key] = shadow
        self._cards[spec.key] = sprite
        self._base_alpha[spec.key] = sprite.getchannel("A")
        return sprite

    def _blue_background(self):
        if self._blue_bg is not None:
            return self._blue_bg
        w, h = self.w, self.h
        # Cold console: a deep navy to steel-blue vertical gradient. Still blue,
        # still a crash screen, but colder and more instrument-like.
        base = self._gradient(ink(BLUE_TOP_C), ink(BLUE_BOTTOM_C))
        base = Image.alpha_composite(base.convert("RGBA"), self._blurred_bloom(
            (-0.06, -0.12), (0.68, 0.68), (0.36, 0.56, 0.94), 14)).convert("RGB")
        base = Image.alpha_composite(base.convert("RGBA"), self._blurred_bloom(
            (1.06, 1.08), (0.52, 0.48), (0.22, 0.34, 0.66), 18)).convert("RGB")
        # A single quiet cool glow across the upper third.
        base = Image.alpha_composite(base.convert("RGBA"), self._blurred_bloom(
            (0.34, -0.06), (0.92, 0.50), (0.52, 0.70, 0.94), 30)).convert("RGB")
        # Vignette, so the corners settle into black.
        vign = Image.new("L", (max(16, w // 12), max(10, h // 12)), 0)
        vdraw = ImageDraw.Draw(vign)
        vw, vh = vign.size
        for i in range(10):
            k = (i + 1) / 10.0
            vdraw.rectangle((-vw * k * 0.2, -vh * k * 0.2,
                             vw + vw * k * 0.2, vh + vh * k * 0.2),
                            outline=int(230 * (1 - k) ** 2.0))
        mask = vign.resize((w, h), Image.BICUBIC).filter(
            ImageFilter.GaussianBlur(self.px(40)))
        dark = Image.new("RGBA", (w, h), (2, 4, 12, 255))
        dark.putalpha(mask)
        base = Image.alpha_composite(base.convert("RGBA"), dark).convert("RGB")
        self._blue_bg = base
        return base

    def _blue_grid_layer(self):
        """Dot field and orbit lines for the AH1AN screen, built once."""
        if self._blue_grid is not None:
            return self._blue_grid
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        step = max(18, int(self.px(28)))
        radius = max(0.6, self.px(0.7))
        for y in range(step, self.h, step):
            for x in range(step, self.w, step):
                draw.ellipse((x - radius, y - radius,
                              x + radius, y + radius),
                             fill=rgba(BLUE_GLOW, 16))
        # Two very faint orbits: the field has a centre without a panel.
        cx, cy = self.w * 0.86, self.h * 0.34
        for scale, alpha in ((0.62, 20), (0.40, 13)):
            reach = self.h * scale
            draw.ellipse((cx - reach, cy - reach, cx + reach, cy + reach),
                         outline=rgba(BLUE_GLOW, alpha),
                         width=max(1, int(self.px(1.0))))
        self._blue_grid = layer
        return layer

    def _blue_screen(self, frame):
        """The AH1AN system screen: a full-bleed crash field, no floating panel.

        Everything is anchored to one content column so the headline, the
        countdown and the stop code read as a single composed screen.
        """
        self._bg = (11, 21, 36)
        blue = frame.blue
        w, h, u = self.w, self.h, self.u
        portrait = self.scene.portrait
        img = Image.alpha_composite(
            self._blue_background().convert("RGBA"),
            self._blue_grid_layer()).convert("RGB")
        draw = self._d(img)

        pad = max(self.px(34), 0.072 * w)
        left, right = pad, w - pad
        if right - left > self.px(1160):
            left = (w - self.px(1160)) / 2
            right = left + self.px(1160)

        # ---- brand row
        top = h * (0.075 if not portrait else 0.055)
        self._dot_matrix(draw, "SMTH", left, top, self.px(2.0),
                         rgba(BLUE_INK_C, 245))
        brand_font = self.fonts.get(10.4 * u, family=self.fonts.SANS,
                                    weight="bold")
        put_text(draw, (left + self.px(84), top - self.px(2)), "SMTH OS",
                 brand_font, rgba(BLUE_INK_C, 250),
                 tracking=self.px(0.8), bold=True)
        meta_font = self.fonts.get(7.4 * u, family=self.fonts.MONO)
        put_text(draw, (left + self.px(84), top + self.px(13)),
                 "KERNEL EVENT  ·  SESSION 03", meta_font,
                 rgba(BLUE_DIM_C, 200), tracking=self.px(1.3))
        put_text(draw, (right, top - self.px(2)), "AH1AN",
                 self.fonts.get(9.0 * u, family=self.fonts.MONO,
                                weight="bold"),
                 rgba(BLUE_GLOW, 245), tracking=self.px(3.0),
                 anchor="right")
        put_text(draw, (right, top + self.px(13)),
                 "AESTHETIC SUBSYSTEM ONLINE", meta_font,
                 rgba(BLUE_DIM_C, 175), tracking=self.px(1.1),
                 anchor="right")

        # ---- headline: two deliberate lines, never a reflowed paragraph
        size = min(0.092 * h, 0.072 * w)
        words = blue.head.split()
        lines = ([" ".join(words[:2]), " ".join(words[2:])]
                 if len(words) > 2 else [blue.head])
        while size > 0.040 * h:
            head_font = self.fonts.get(size, family=self.fonts.SANS,
                                       weight="bold")
            if max(measure(head_font, line, self.px(0.4))
                   for line in lines) <= right - left:
                break
            size *= 0.94
        head_font = self.fonts.get(size, family=self.fonts.SANS, weight="bold")
        head_y = h * (0.300 if not portrait else 0.245)
        for index, line in enumerate(lines):
            put_text(draw, (left, head_y + index * size * 1.04), line,
                     head_font, rgba(BLUE_INK_C, 255),
                     tracking=self.px(0.4), bold=True)
        sub_size = max(self.px(13), size * 0.28)
        sub_font = self.fonts.get(sub_size, family=self.fonts.SANS)
        sub_y = head_y + len(lines) * size * 1.04 + sub_size * 0.55
        put_text(draw, (left, sub_y), blue.sub, sub_font,
                 rgba(BLUE_DIM_C, 240), tracking=self.px(0.15))

        # ---- countdown: the hero of act two.  A large ring sits opposite the
        # headline in landscape, and below it in portrait, so neither half of
        # the screen is empty.
        progress = blue.progress
        if portrait:
            ring_cx = (left + right) / 2
            ring_cy = h * 0.560
            radius = min(0.105 * h, 0.200 * (right - left))
        else:
            ring_cx = left + (right - left) * 0.700
            ring_cy = h * 0.610
            radius = min(0.120 * h, 0.110 * (right - left))
        draw.ellipse((ring_cx - radius, ring_cy - radius,
                      ring_cx + radius, ring_cy + radius),
                     outline=rgba(BLUE_RULE_C, 235),
                     width=max(2, int(self.px(1.6))))
        sweep = 360.0 * (1.0 - progress)
        if sweep > 0.5:
            draw.arc((ring_cx - radius, ring_cy - radius,
                      ring_cx + radius, ring_cy + radius),
                     270, 270 + sweep, fill=rgba(BLUE_GLOW, 250),
                     width=max(2, int(self.px(3.2))))
        caption_font = self.fonts.get(7.6 * u, family=self.fonts.MONO)
        put_text(draw, (ring_cx, ring_cy - radius - self.px(20)), "COUNTDOWN",
                 caption_font, rgba(BLUE_GLOW, 225),
                 tracking=self.px(3.2), anchor="center")
        number_size = radius * 1.18
        number_font = self.fonts.get(number_size * (1.0 + 0.05 * blue.tick),
                                     family=self.fonts.MONO, weight="bold")
        put_text(draw, (ring_cx, ring_cy + number_size * 0.34),
                 str(blue.countdown), number_font, rgba(BLUE_INK_C, 255),
                 bold=True, anchor="center")
        put_text(draw, (ring_cx, ring_cy + radius + self.px(26)),
                 "AHIAN IS REBUILDING YOUR REALITY", caption_font,
                 rgba(BLUE_DIM_C, 215), tracking=self.px(1.8),
                 anchor="center")
        bar_w = radius * 2.10
        bar_y = ring_cy + radius + self.px(38)
        bar_h = max(2, int(self.px(3.0)))
        draw.rounded_rectangle((ring_cx - bar_w / 2, bar_y,
                                ring_cx + bar_w / 2, bar_y + bar_h),
                               radius=self.px(2),
                               fill=rgba((0.16, 0.24, 0.36), 255))
        fill_to = ring_cx - bar_w / 2 + bar_w * progress
        if fill_to > ring_cx - bar_w / 2 + 1:
            draw.rounded_rectangle((ring_cx - bar_w / 2, bar_y,
                                    fill_to, bar_y + bar_h),
                                   radius=self.px(2),
                                   fill=rgba(BLUE_GLOW, 250))
        put_text(draw, (ring_cx + bar_w / 2 + self.px(12),
                        bar_y + self.px(3.2)),
                 f"{int(round(progress * 100)):d}%",
                 self.fonts.get(7.8 * u, family=self.fonts.MONO),
                 rgba(BLUE_DIM_C, 225), tracking=self.px(0.8))

        # ---- footer: nine segments, then the stop code
        rule_y = h * (0.845 if not portrait else 0.800)
        draw.line((left, rule_y, right, rule_y),
                  fill=rgba(BLUE_RULE_C, 200), width=1)
        gap = self.px(6)
        seg_w = (right - left - gap * 8) / 9.0
        for i in range(9):
            x = left + i * (seg_w + gap)
            on = progress >= (i + 1) / 9.0 - 0.001
            draw.rectangle((x, rule_y + self.px(8),
                            x + seg_w, rule_y + self.px(11.4)),
                           fill=rgba(BLUE_GLOW if on
                                     else mix_colour(BLUE_RULE_C, BLUE_GLOW, 0.18),
                                     245 if on else 210))
        meta_y = rule_y + self.px(33)
        put_text(draw, (left, meta_y), "STOP CODE: AH1AN_ASCENSION",
                 meta_font, rgba(BLUE_DIM_C, 220),
                 tracking=self.px(1.5))
        put_text(draw, (left, meta_y + self.px(15)),
                 "0x0000A11A  ·  MODE: AHIAN",
                 self.fonts.get(7.6 * u, family=self.fonts.MONO),
                 rgba(BLUE_DIM_C, 165), tracking=self.px(1.2))
        pulse = 0.55 + 0.45 * math.sin(frame.t_ms / 280.0)
        dot_r = self.px(2.6)
        dot_x = right - self.px(5)
        draw.ellipse((dot_x - dot_r, meta_y - dot_r * 1.6,
                      dot_x + dot_r, meta_y - dot_r * 1.6 + dot_r * 2),
                     fill=rgba(AMBER_HOT, int(90 + 140 * pulse)))
        put_text(draw, (right - self.px(16), meta_y), "DO NOT POWER OFF",
                 meta_font, rgba(BLUE_DIM_C, 210),
                 tracking=self.px(1.5), anchor="right")
        put_text(draw, (right, meta_y + self.px(15)), "AHIAN / 9.0 SEC",
                 self.fonts.get(7.6 * u, family=self.fonts.MONO),
                 rgba(BLUE_DIM_C, 150), tracking=self.px(1.2),
                 anchor="right")
        return img

    # ---- act 3 --------------------------------------------------------------
    def _vignette_layer(self):
        if self._vignette_cache is not None:
            return self._vignette_cache
        w, h = self.w, self.h
        small = Image.new("L", (max(16, w // 12), max(10, h // 12)), 0)
        ImageDraw.Draw(small).rectangle((0, 0, small.width, small.height), fill=255)
        inner = Image.new("L", small.size, 255)
        ImageDraw.Draw(inner).rounded_rectangle(
            (small.width * 0.06, small.height * 0.06,
             small.width * 0.94, small.height * 0.94),
            radius=small.width * 0.1, fill=0)
        mask = ImageChops.subtract(inner, small).resize(
            (w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(self.px(46)))
        layer = Image.new("RGBA", (w, h), (4, 2, 12, 255))
        layer.putalpha(mask.point(lambda v: int(v * 0.66)))
        self._vignette_cache = layer
        return layer

    # ---- act 1: windows over the live desktop -------------------------------
    def _compose_card(self, layer, card, dx=0.0, dy=0.0):
        """Alpha-composite one error window onto the transparent overlay.

        Nothing else is painted: the live desktop shows through every pixel a
        window does not cover.
        """
        sprite = self._card_sprite(card.spec)
        shadow = self._shadows[card.spec.key]
        if card.alpha < 0.999:
            sprite = sprite.copy()
            sprite.putalpha(self._base_alpha[card.spec.key].point(
                lambda v, a=card.alpha: int(v * a)))
        x = int(round(card.rect.x + dx))
        y = int(round(card.rect.y + dy))
        sw = shadow.width - sprite.width
        sh = shadow.height - sprite.height
        layer.alpha_composite(shadow, (int(x - sw / 2), int(y - sh / 2)))
        layer.alpha_composite(sprite, (x, y))
        if card.flash > 0.02:
            w, h = sprite.size
            flash = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(flash)
            pal = self._card_palette(card.spec)
            draw.rounded_rectangle(
                (0, 0, w - 1, h - 1), radius=max(1, int(self.px(9))),
                outline=rgba(pal["accent"], int(170 * card.flash)),
                width=max(1, int(self.px(1.3))))
            draw.rectangle(
                (self.px(1), self.px(1), w - self.px(1),
                 self.px(1) + max(1, int(h * 0.10))),
                fill=rgba(FROST, int(90 * card.flash)))
            layer.alpha_composite(flash, (x, y))

    def _outbreak(self, frame):
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        g = frame.glitch
        # The tremor moves the windows, never the desktop behind them.
        for card in frame.cards:
            self._compose_card(layer, card, g.dx, g.dy)
        return layer

    # ---- overlay-safe screen effects ----------------------------------------
    def _grain(self):
        if self._noise is None:
            noise = Image.effect_noise((self.w, self.h), 26)
            white = Image.new("L", (self.w, self.h), 255)
            alpha = noise.point(lambda v: int(v * 0.14))
            self._noise = Image.merge("RGBA", (white, white, white, alpha))
        return self._noise

    def _glitch(self, img, frame):
        """Translucent interference: it tints the overlay, never the desktop.

        The old renderer sliced and colour-shifted frame pixels, which only
        worked because it also painted a copy of the desktop.  Those effects are
        replaced with light and grain that composite over the live session.
        """
        g = frame.glitch
        if not g.active:
            return img
        out = img
        if g.noise > 0.03:
            alpha = min(46, int(10 + 30 * g.noise))
            grain = self._grain()
            if alpha < 40:
                grain = grain.copy()
                grain.putalpha(grain.getchannel("A").point(
                    lambda v, k=alpha / 46.0: int(v * k)))
            offset = (int(frame.t_ms * 7) % self.w,
                      int(frame.t_ms * 5) % self.h)
            out.alpha_composite(ImageChops.offset(grain, *offset))
        effects = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(effects)
        if g.flash > 0.01:
            draw.rectangle((0, 0, self.w, self.h),
                           fill=rgba((0.86, 0.90, 0.96), min(0.16, 0.40 * g.flash)))
        if g.split > 0.5:
            band = (int(self.h * 0.30), int(self.h * 0.64))
            shift = max(2, int(g.split))
            draw.rectangle((-shift, band[0], self.w - shift, band[1]),
                           fill=rgba((1.0, 0.24, 0.30), 0.05))
            draw.rectangle((shift, band[0], self.w + shift, band[1]),
                           fill=rgba((0.25, 0.90, 1.0), 0.05))
        if g.slice_y >= 0:
            y0 = int(self.h * M.clamp(g.slice_y - 0.05))
            y1 = int(self.h * M.clamp(g.slice_y + 0.05))
            draw.rectangle((0, y0, self.w, max(y0 + 1, y1)),
                           fill=rgba((0.70, 0.80, 0.95), 0.05))
            draw.rectangle((0, y0, self.w, y0 + max(1, int(self.px(1.4)))),
                           fill=rgba((0.80, 0.90, 1.0), 0.16))
        if g.scan_y >= 0:
            y = g.scan_y * self.h
            draw.rectangle((0, y - self.px(26), self.w, y + self.px(26)),
                           fill=(180, 215, 240, 16))
            draw.rectangle((0, y, self.w, y + max(1, self.px(1.6))),
                           fill=(220, 232, 250, 58))
        if effects.getbbox() is not None:
            out = Image.alpha_composite(out, effects)
        return out

    # ---- act 2: the blue screen and the cut to the live desktop -------------
    def _beam(self):
        """The line the AH1AN screen opens from: a few pixels of light."""
        out = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw = draw_on(out)
        y = self.h / 2
        glow = max(1, int(self.px(8)))
        draw.rectangle((0, y - glow, self.w, y - 1), fill=(150, 190, 225, 42))
        draw.rectangle((0, y - 1, self.w, y + 1), fill=(200, 224, 248, 230))
        draw.rectangle((0, y + 1, self.w, y + glow), fill=(150, 190, 225, 42))
        return out

    def _squeeze(self, img, opened, edge):
        """Clip a full-screen frame to a growing horizontal band (CRT open)."""
        opened = clamp(opened)
        if opened >= 0.999:
            return img
        band_h = max(2, int(self.h * opened))
        top = (self.h - band_h) // 2
        out = Image.new("RGBA", img.size, (0, 0, 0, 0))
        out.paste(img.crop((0, top, self.w, top + band_h)), (0, top))
        draw = draw_on(out)
        glow = max(1, int(self.px(2.2)))
        draw.rectangle((0, top - glow, self.w, top), fill=edge)
        draw.rectangle((0, top + band_h, self.w, top + band_h + glow), fill=edge)
        draw.rectangle((0, top + band_h // 2 - 1, self.w,
                        top + band_h // 2 + 1), fill=edge)
        return out

    # ---- entry point --------------------------------------------------------
    def render(self, t_ms):
        """An RGBA overlay frame.  Transparent wherever the live desktop shows."""
        frame = self.scene.frame(t_ms)
        if frame.reduced:
            return Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        if frame.phase == "outbreak":
            return self._glitch(self._outbreak(frame), frame)
        if frame.phase == "blue":
            if frame.blue.open <= 0.0:
                return self._beam()
            blue = self._blue_screen(frame).convert("RGBA")
            return self._glitch(
                self._squeeze(blue, frame.blue.open, (150, 190, 225)), frame)
        # Zero: the overlay is gone and the running AHIAN desktop is revealed
        # by removing it.  There is no rendered replacement underneath.
        return Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))


if __name__ == "__main__":
    import sys
    t = float(sys.argv[1]) if len(sys.argv) > 1 else 4200.0
    profile = sys.argv[2] if len(sys.argv) > 2 else "linux"
    out = sys.argv[3] if len(sys.argv) > 3 else "/tmp/ahian-frame.png"
    scene = M.StartupScene(1280, 800, profile=profile)
    SceneRenderer(scene).render(t).save(out)
    print(out)
