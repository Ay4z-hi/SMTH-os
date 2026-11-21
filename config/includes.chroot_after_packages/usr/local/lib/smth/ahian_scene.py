"""The AHIAN takeover renderer (shared by the ISO, the EXE and the previews).

One implementation, one look.  ``ahian_startup.py`` draws these frames into a
GTK overlay and the Windows launcher draws the same frames into a Tk window, so
the ISO and the EXE are pixel-identical.  ``tools/render_ahian_preview.py``
writes the very same frames to PNG, which is how the animation is visually
checked without a display attached.

Pillow's ``ImageDraw`` only alpha-blends when the target is RGB, so every scene
is composed in RGB and cards are pasted with their own alpha channel.  The
desktop base, the dimmed bases, each error window's chrome and shadow, the
settled-window layer, the blue screen background and the flowing wallpaper are
all cached, so a steady-state frame is a handful of composites.
"""
import importlib.util
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

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


FONT_NAMES = ("SpaceMono-Regular.ttf", "DejaVuSansMono.ttf", "consola.ttf",
              "LiberationMono-Regular.ttf", "Menlo.ttc", "Courier New.ttf")


class Fonts:
    """Space Mono everywhere, with a same-metrics fallback."""

    def __init__(self, directories=()):
        self.directories = [d for d in directories if d]
        self.path = None
        for name in FONT_NAMES:
            found = self._find(name)
            if found:
                self.path = found
                break
        self._cache = {}

    def _find(self, name):
        roots = list(self.directories) + [
            "/usr/share/fonts/truetype/dejavu",
            "/usr/share/fonts/truetype/space-mono",
            "/usr/share/fonts/truetype",
            "/usr/share/fonts/truetype/msttcorefonts",
            "/usr/share/fonts",
            "C:/Windows/Fonts",
            os.path.expanduser("~/Library/Fonts"),
            "/System/Library/Fonts",
        ]
        for root in roots:
            candidate = os.path.join(root, name)
            if os.path.isfile(candidate):
                return candidate
        for root in roots:
            if not os.path.isdir(root):
                continue
            for base, _dirs, files in os.walk(root):
                if name in files:
                    return os.path.join(base, name)
        return None

    def get(self, size):
        size = max(6, int(round(size)))
        font = self._cache.get(size)
        if font is None:
            try:
                font = ImageFont.truetype(self.path, size) if self.path else None
            except OSError:
                font = None
            if font is None:
                try:
                    font = ImageFont.load_default(size)
                except TypeError:                       # Pillow < 10.1
                    font = ImageFont.load_default()
            self._cache[size] = font
        return font


def clamp01(value):
    return max(0.0, min(1.0, value))


def measure(font, text, tracking=0.0):
    if not text:
        return 0.0
    return sum(font.getlength(ch) for ch in text) + tracking * max(0, len(text) - 1)


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
    """Monospaced type with real letter spacing and an optional faux bold."""
    fill = flatten(fill, getattr(draw, "backdrop", (18, 15, 26)))
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


class SceneRenderer:
    """Draws any frame of the AHIAN takeover at the scene's resolution."""

    CARD_HEADERS = ("SMTH SYSTEM", "SURFACE", "AHIAN WATCH", "COMPOSITOR",
                    "SESSION", "INDEX")

    def __init__(self, scene, font_dirs=(), wallpaper=None):
        self.scene = scene
        self.w = int(scene.width)
        self.h = int(scene.height)
        self.u = scene.u
        self.fonts = Fonts(font_dirs)
        self.wallpaper_source = wallpaper
        self._desktop = None
        self._dim = {}
        self._cards = {}
        self._shadows = {}
        self._base_alpha = {}
        self._settled = None
        self._settled_key = None
        self._blue_bg = None
        self._wall = {}
        self._noise = None
        self._vignette_cache = None
        self._bg = (18, 15, 26)

    # ---- helpers ------------------------------------------------------------
    def px(self, value):
        return value * self.u

    def _d(self, image):
        draw = draw_on(image)
        draw.backdrop = self._bg
        return draw

    def _gradient(self, top, bottom):
        small = Image.new("RGB", (2, 128))
        draw = draw_on(small)
        for y in range(128):
            ratio = y / 127.0
            draw.line((0, y, 2, y), fill=tuple(
                int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)))
        return small.resize((self.w, self.h), Image.BILINEAR)

    def _blurred_bloom(self, centre, radius, colour, alpha):
        """A soft radial light: one ellipse, heavily blurred, scaled up.

        Building it small and blurring there keeps the falloff perfectly
        smooth: no visible edge, no banding, and it costs almost nothing.
        """
        small = Image.new("L", (max(24, self.w // 6), max(16, self.h // 6)), 0)
        draw = ImageDraw.Draw(small)
        cx = centre[0] * small.width
        cy = centre[1] * small.height
        rx = max(1.0, radius[0] * small.width)
        ry = max(1.0, radius[1] * small.height)
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
        mask = small.filter(
            ImageFilter.GaussianBlur(max(2.0, small.width * 0.10))
        ).resize((self.w, self.h), Image.BICUBIC)
        layer = Image.new("RGBA", (self.w, self.h), rgba(colour, 255))
        layer.putalpha(mask.point(lambda v, a=alpha: int(v * a / 255.0)))
        return layer

    def _paste(self, base, sprite, xy):
        base.paste(sprite, (int(round(xy[0])), int(round(xy[1]))), sprite)

    def _dot_matrix(self, draw, text, x, baseline, dot, colour, glyphs=None,
                    tracking=1):
        """Dot-matrix type: the SMTH identity, identical on every platform."""
        glyphs = glyphs or M.BRAND_GLYPHS
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
    def _glyph(self, draw, name, cx, cy, size, colour, width=None):
        """One coherent line-icon language, drawn from primitives."""
        s = size / 2.0
        width = width or max(1, int(size * 0.09))

        def line(x0, y0, x1, y1):
            draw.line((cx + x0 * s, cy + y0 * s, cx + x1 * s, cy + y1 * s),
                      fill=colour, width=width)

        def box(x0, y0, x1, y1):
            draw.rectangle((cx + x0 * s, cy + y0 * s, cx + x1 * s, cy + y1 * s),
                           outline=colour, width=width)

        if name == "folder":
            draw.line([(cx - s * 0.82, cy - s * 0.40), (cx - s * 0.22, cy - s * 0.40),
                       (cx - s * 0.08, cy - s * 0.62), (cx + s * 0.82, cy - s * 0.62)],
                      fill=colour, width=width)
            box(-0.82, -0.38, 0.82, 0.62)
        elif name == "globe":
            draw.ellipse((cx - s * 0.72, cy - s * 0.72, cx + s * 0.72, cy + s * 0.72),
                         outline=colour, width=width)
            line(0, -0.72, 0, 0.72)
            draw.arc((cx - s * 0.72, cy - s * 0.42, cx + s * 0.72, cy + s * 0.42),
                     0, 360, fill=colour, width=max(1, width - 1))
        elif name == "terminal":
            box(-0.82, -0.62, 0.82, 0.62)
            line(-0.5, -0.28, -0.16, 0.0)
            line(-0.16, 0.0, -0.5, 0.28)
            line(0.10, 0.30, 0.52, 0.30)
        elif name == "gear":
            draw.ellipse((cx - s * 0.32, cy - s * 0.32, cx + s * 0.32, cy + s * 0.32),
                         outline=colour, width=width)
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                           (-0.72, -0.72), (0.72, 0.72), (-0.72, 0.72), (0.72, -0.72)):
                line(dx * 0.44, dy * 0.44, dx * 0.72, dy * 0.72)
        elif name == "calc":
            box(-0.62, -0.78, 0.62, 0.78)
            draw.rectangle((cx - s * 0.40, cy - s * 0.60, cx + s * 0.40, cy - s * 0.28),
                           fill=colour)
            for row in range(2):
                for col in range(3):
                    x = -0.36 + col * 0.36
                    y = 0.02 + row * 0.34
                    draw.rectangle((cx + (x - 0.08) * s, cy + (y - 0.08) * s,
                                    cx + (x + 0.08) * s, cy + (y + 0.08) * s), fill=colour)
        elif name == "photo":
            box(-0.82, -0.62, 0.82, 0.62)
            draw.ellipse((cx + s * 0.24, cy - s * 0.46, cx + s * 0.50, cy - s * 0.20),
                         outline=colour, width=width)
            line(-0.68, 0.5, -0.16, -0.10)
            line(-0.16, -0.10, 0.14, 0.22)
            line(0.14, 0.22, 0.34, 0.04)
            line(0.34, 0.04, 0.68, 0.5)
        elif name == "note":
            box(-0.66, -0.78, 0.66, 0.78)
            for i in range(3):
                line(-0.36, -0.30 + i * 0.32, 0.36, -0.30 + i * 0.32)
        elif name == "clock":
            draw.ellipse((cx - s * 0.74, cy - s * 0.74, cx + s * 0.74, cy + s * 0.74),
                         outline=colour, width=width)
            line(0, 0, 0, -0.44)
            line(0, 0, 0.30, 0.14)
        elif name == "camera":
            box(-0.82, -0.44, 0.82, 0.54)
            draw.rectangle((cx - s * 0.24, cy - s * 0.62, cx + s * 0.24, cy - s * 0.44),
                           outline=colour, width=width)
            draw.ellipse((cx - s * 0.26, cy - s * 0.20, cx + s * 0.26, cy + s * 0.32),
                         outline=colour, width=width)
        elif name == "phone":
            draw.rounded_rectangle((cx - s * 0.42, cy - s * 0.78, cx + s * 0.42,
                                    cy + s * 0.78),
                                   radius=max(2, int(s * 0.16)), outline=colour,
                                   width=width)
            line(-0.16, 0.56, 0.16, 0.56)
        elif name == "chat":
            draw.rounded_rectangle((cx - s * 0.78, cy - s * 0.62, cx + s * 0.78,
                                    cy + s * 0.32),
                                   radius=max(2, int(s * 0.18)), outline=colour,
                                   width=width)
            draw.line([(cx - s * 0.24, cy + s * 0.32), (cx - s * 0.34, cy + s * 0.62),
                       (cx + s * 0.06, cy + s * 0.32)], fill=colour, width=width)
        elif name == "bag":
            box(-0.72, -0.44, 0.72, 0.72)
            draw.arc((cx - s * 0.34, cy - s * 0.86, cx + s * 0.34, cy - s * 0.12),
                     180, 360, fill=colour, width=width)
        elif name == "brush":
            line(-0.6, 0.6, 0.24, -0.24)
            draw.polygon([(cx + s * 0.22, cy - s * 0.22), (cx + s * 0.60, cy - s * 0.70),
                          (cx + s * 0.70, cy - s * 0.54), (cx + s * 0.34, cy - s * 0.12)],
                         outline=colour, width=width)
        elif name == "play":
            draw.polygon([(cx - s * 0.4, cy - s * 0.62), (cx + s * 0.62, cy),
                          (cx - s * 0.4, cy + s * 0.62)], outline=colour, width=width)
        else:
            box(-0.7, -0.7, 0.7, 0.7)

    # ---- act 0: the real desktop -------------------------------------------
    def desktop(self):
        self._bg = (16, 13, 20)
        if self._desktop is not None:
            return self._desktop
        w, h, u = self.w, self.h, self.u
        img = self._gradient(ink(M.OBSIDIAN), (26, 17, 27))
        # Two broad maroon washes: the SMTH wallpaper, soft rather than graphic.
        img = Image.alpha_composite(
            img.convert("RGBA"),
            self._blurred_bloom((0.06, 0.92), (0.55, 0.46), M.MAROON, 26)).convert("RGB")
        img = Image.alpha_composite(
            img.convert("RGBA"),
            self._blurred_bloom((1.02, 0.05), (0.46, 0.40), M.MAROON_DEEP, 60)).convert("RGB")
        draw = self._d(img)
        step = max(18, int(self.px(26)))
        radius = max(0.8, self.px(1.0))
        for y in range(step, h, step):
            for x in range(step, w, step):
                draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                             fill=rgba(M.BLUSH, 10))
        for spec in self.scene.icons:
            self._draw_shortcut(img, spec)
        bar = self.scene.layout["bar"]
        if self.scene.profile == "linux":
            self._draw_waybar(img, bar, 1.0)
            self._draw_clock_widget(img, self.scene.layout["clock"], 1.0)
            if self.scene.layout["rings"] is not None:
                self._draw_glance(img, self.scene.layout["rings"], 1.0)
        else:
            self._draw_taskbar(img, bar, 1.0)
        self._desktop = img
        return img

    def _accents(self, ahian):
        if ahian:
            return {
                "tile": rgba((0.055, 0.045, 0.100), 205),
                "border": rgba(M.PURPLE_SOFT, 80),
                "glyph": rgba(M.INK, 238),
                "label": rgba(M.INK, 205),
                "bar": rgba((0.055, 0.047, 0.086), 236),
                "bar_edge": rgba(M.TEAL, 60),
                "ink": rgba(M.INK, 228),
                "muted": rgba(M.INK, 150),
            }
        return {
            "tile": rgba(M.OBSIDIAN_DEEP, 210),
            "border": rgba(M.BLUSH, 26),
            "glyph": rgba(M.BLUSH, 232),
            "label": rgba(M.BLUSH, 185),
            "bar": rgba((0.031, 0.028, 0.039), 240),
            "bar_edge": rgba(M.MAROON, 170),
            "ink": rgba(M.BLUSH, 215),
            "muted": rgba(M.BLUSH, 130),
        }

    def _rim(self, img, y, alpha=210):
        """A purple-to-teal hairline: the AHIAN accent on every bar."""
        draw = self._d(img)
        segments = 24
        for i in range(segments):
            x0 = self.w * i / segments
            x1 = self.w * (i + 1) / segments + 1
            colour = M.mix_colour(M.PURPLE, M.TEAL, i / (segments - 1.0))
            draw.rectangle((x0, y, x1, y + max(1.0, self.px(1.1))),
                           fill=rgba(colour, alpha))

    def _draw_shortcut(self, img, spec, progress=1.0, ahian=False):
        self._bg = (30, 26, 48) if ahian else (16, 13, 20)
        if progress <= 0.005:
            return
        draw = self._d(img)
        palette = self._accents(ahian)
        p = min(1.0, progress)
        rect = spec.rect
        cx = rect.x + rect.w / 2
        top = rect.y + (1.0 - p) * self.px(16)
        size = self.px(50) * (0.9 + 0.1 * p)
        accent = (M.PURPLE_SOFT, M.TEAL_BRIGHT, M.PURPLE,
                  M.TEAL)[int(spec.key.split("-")[1]) % 4] if ahian else None
        draw.rounded_rectangle((cx - size / 2, top, cx + size / 2, top + size),
                               radius=self.px(13),
                               fill=palette["tile"],
                               outline=rgba(accent, int(90 * p)) if ahian
                               else rgba(M.BLUSH, int(26 * p)), width=1)
        self._glyph(draw, spec.glyph, cx, top + size / 2, size * 0.52,
                    palette["glyph"] if p > 0.999
                    else rgba((M.INK if ahian else M.BLUSH), int(232 * p)))
        put_text(draw, (cx, top + size + self.px(15)), spec.label,
                 self.fonts.get(8.6 * self.u),
                 palette["label"] if p > 0.999
                 else rgba((M.INK if ahian else M.BLUSH), int(190 * p)),
                 tracking=self.px(1.0), anchor="center")

    def _draw_waybar(self, img, bar, progress, ahian=False):
        self._bg = (9, 8, 12)
        if progress <= 0.005:
            return
        draw = self._d(img)
        u = self.u
        palette = self._accents(ahian)
        height = bar.h * progress
        draw.rectangle((0, 0, self.w, height), fill=palette["bar"])
        if ahian:
            self._rim(img, height - self.px(1.2), 220)
        else:
            draw.line((0, height, self.w, height), fill=palette["bar_edge"],
                      width=max(1, int(u)))
        self._dot_matrix(draw, "SMTH", self.px(20), height / 2 + self.px(9),
                         self.px(2.0), rgba(M.INK if ahian else M.BLUSH,
                                            220 if ahian else 215))
        font = self.fonts.get(9.2 * u)
        x = self.px(112)
        for label in ("FILES", "BROWSER", "STORE", "SETTINGS"):
            put_text(draw, (x, height / 2 + self.px(3.2)), label, font,
                     palette["muted"], tracking=self.px(1.4))
            x += measure(font, label, self.px(1.4)) + self.px(20)
        right = self.w - self.px(18)
        time_font = self.fonts.get(10.0 * u)
        put_text(draw, (right, height / 2 + self.px(3.4)), "09:41", time_font,
                 palette["ink"], tracking=self.px(0.6), anchor="right")
        right -= measure(time_font, "09:41", self.px(0.6)) + self.px(28)
        for i in range(3):
            cx = right - self.px(30) + i * self.px(10)
            draw.ellipse((cx - self.px(2.0), height / 2 - self.px(2.0),
                          cx + self.px(2.0), height / 2 + self.px(2.0)),
                         fill=rgba(M.TEAL_BRIGHT if ahian else M.BLUSH,
                                   175 if ahian else 165))

    def _draw_taskbar(self, img, bar, progress, ahian=False):
        self._bg = (10, 9, 14)
        if progress <= 0.005:
            return
        draw = self._d(img)
        u = self.u
        palette = self._accents(ahian)
        rise = (1.0 - progress) * bar.h * 1.5
        left, top = bar.x + self.px(12), bar.y + rise
        right, bottom = bar.right - self.px(12), bar.bottom + rise
        p = min(1.0, progress)
        draw.rounded_rectangle((left, top + self.px(4), right, bottom + self.px(4)),
                               radius=self.px(16), fill=(0, 0, 0, 90))
        draw.rounded_rectangle((left, top, right, bottom), radius=self.px(16),
                               fill=palette["bar"], outline=palette["bar_edge"],
                               width=1)
        cy = (top + bottom) / 2
        cx = left + self.px(32)
        draw.rounded_rectangle((cx - self.px(17), cy - self.px(17),
                                cx + self.px(17), cy + self.px(17)),
                               radius=self.px(10),
                               fill=rgba(M.PURPLE if ahian else M.MAROON,
                                         int(225 * p)))
        self._dot_matrix(draw, "S", cx - self.px(9), cy + self.px(7), self.px(1.9),
                         rgba(M.INK if ahian else M.BLUSH, int(245 * p)))
        time_font = self.fonts.get(10.0 * u)
        put_text(draw, (right - self.px(18), cy + self.px(3.4)), "09:41", time_font,
                 palette["ink"], tracking=self.px(0.6), anchor="right")
        avail = right - self.px(18) - measure(time_font, "09:41", self.px(0.6)) - self.px(26)
        for index, glyph in enumerate(("globe", "terminal", "folder")):
            gx = left + self.px(84) + index * self.px(54)
            if gx > avail - self.px(20):
                break
            self._glyph(draw, glyph, gx, cy, self.px(23),
                        rgba(M.INK if ahian else M.BLUSH, int(215 * p)))

    def _draw_clock_widget(self, img, rect, progress, ahian=False):
        self._bg = (28, 24, 46) if ahian else (16, 13, 20)
        if progress <= 0.005:
            return
        draw = self._d(img)
        rise = (1.0 - progress) * self.px(14)
        p = min(1.0, progress)
        text = "09:41"
        if ahian:
            # Neon dot matrix: alternating AHIAN inks, exactly like the live
            # desktop's clock.
            spacing = self.px(3.4)
            glyphs = M.DIGIT_GLYPHS
            for index, char in enumerate(text):
                rows = glyphs.get(char, glyphs.get(" "))
                for row in range(7):
                    for col in range(5):
                        if rows[row] >> (4 - col) & 1:
                            x = rect.x + (index * 6 + col) * spacing
                            y = rect.y + self.px(30) + rise - (6 - row) * spacing
                            colour = (M.PURPLE_SOFT if (index * 6 + col) % 2 == 0
                                      else M.TEAL_BRIGHT)
                            r = spacing * 0.38
                            draw.ellipse((x - r, y - r, x + r, y + r),
                                         fill=rgba(colour, int(250 * p)))
        else:
            self._dot_matrix(draw, text, rect.x, rect.y + self.px(30) + rise,
                             self.px(3.4), rgba(M.BLUSH, int(240 * p)),
                             glyphs=M.DIGIT_GLYPHS)
        put_text(draw, (rect.x, rect.y + self.px(58) + rise), "FRIDAY 21 NOVEMBER",
                 self.fonts.get(8.0 * self.u),
                 rgba(M.INK if ahian else M.BLUSH, int((160 if ahian else 125) * p)),
                 tracking=self.px(1.6))

    def _draw_glance(self, img, rect, progress, ahian=False):
        self._bg = (15, 13, 24)
        if progress <= 0.005:
            return
        draw = self._d(img)
        u = self.u
        rise = (1.0 - progress) * self.px(16)
        p = min(1.0, progress)
        box = (rect.x, rect.y + rise, rect.right, rect.bottom + rise)
        draw.rounded_rectangle((box[0], box[1] + self.px(3), box[2], box[3] + self.px(3)),
                               radius=self.px(18), fill=(0, 0, 0, 70))
        draw.rounded_rectangle(box, radius=self.px(18),
                               fill=rgba((0.055, 0.047, 0.086) if ahian
                                         else (0.05, 0.043, 0.062), int(185 * p)),
                               outline=rgba(M.TEAL if ahian else M.BLUSH,
                                            int((50 if ahian else 34) * p)), width=1)
        for index, (label, value) in enumerate(zip(("CPU", "RAM", "SSD"),
                                                   (0.62, 0.44, 0.71))):
            cx = box[0] + self.px(44) + index * self.px(80)
            cy = (box[1] + box[3]) / 2 - self.px(4)
            radius = self.px(19)
            total = 26
            lit = int(total * value)
            for k in range(total):
                angle = -math.pi / 2 + math.tau * k / total
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                r = self.px(2.1) if k < lit else self.px(0.9)
                if ahian:
                    if k < lit:
                        colour = M.PURPLE_SOFT if k % 2 == 0 else M.TEAL_BRIGHT
                        alpha = 220
                    else:
                        colour = M.VIOLET
                        alpha = 80
                else:
                    colour = M.BLUSH if (k < lit and k % 2 == 0) else M.MAROON
                    alpha = 215 if k < lit else 70
                draw.ellipse((x - r, y - r, x + r, y + r),
                             fill=rgba(colour, int(alpha * p)))
            put_text(draw, (cx, cy + radius + self.px(14)), label,
                     self.fonts.get(7.4 * u),
                     rgba(M.INK if ahian else M.BLUSH, int((190 if ahian else 150) * p)),
                     tracking=self.px(1.2), anchor="center")

    # ---- act 1 --------------------------------------------------------------
    def _dimmed(self, index):
        cached = self._dim.get(index)
        if cached is None:
            cached = Image.blend(self.desktop(),
                                 Image.new("RGB", (self.w, self.h), (4, 4, 7)),
                                 index / 12.0)
            self._dim[index] = cached
        return cached

    def _card_sprite(self, spec):
        self._bg = ink(M.PANEL)
        sprite = self._cards.get(spec.key)
        if sprite is not None:
            return sprite
        w, h = self.scene.card_size(spec)
        w, h = int(round(w)), int(round(h))
        u = self.u
        accent = M.ACCENTS[spec.accent % len(M.ACCENTS)]
        body = Image.new("RGB", (w, h), ink(M.PANEL))
        draw = self._d(body)
        draw.line((u * 12, u * 1.2, w - u * 12, u * 1.2), fill=(255, 255, 255, 26),
                  width=max(1, int(u * 0.7)))
        draw.rounded_rectangle((0, u * 16, u * 3.2, h - u * 16), radius=u * 1.6,
                               fill=rgba(accent, 232))

        # Corner brackets in the accent: a technical readout, not a popup.
        bracket = u * 11
        for (bx, by, dx, dy) in ((u * 7, u * 7, 1, 1), (w - u * 7, u * 7, -1, 1),
                                 (u * 7, h - u * 7, 1, -1),
                                 (w - u * 7, h - u * 7, -1, -1)):
            draw.line((bx, by, bx + bracket * dx, by), fill=rgba(accent, 70),
                      width=max(1, int(u * 0.6)))
            draw.line((bx, by, bx, by + bracket * dy), fill=rgba(accent, 70),
                      width=max(1, int(u * 0.6)))

        left = u * 19
        head_font = self.fonts.get(7.8 * u)
        draw.rectangle((left, u * 15, left + u * 5, u * 20), fill=rgba(accent, 235))
        put_text(draw, (left + u * 11, u * 20.5),
                 self.CARD_HEADERS[spec.accent % len(self.CARD_HEADERS)],
                 head_font, (198, 188, 216, 160), tracking=u * 1.15)

        title_font = self.fonts.get(13.4 * u)
        title_colour = (rgba((0.88, 1.0, 0.98), 250) if spec.is_ahian
                        else (247, 242, 255, 252))
        put_text(draw, (left, u * 44), spec.title, title_font, title_colour,
                 tracking=u * 0.55, bold=True)

        body_font = self.fonts.get(9.8 * u)
        body_y = u * 62
        for line in wrap(body_font, spec.body, 0, w - left - u * 22)[:2]:
            put_text(draw, (left, body_y), line, body_font, (174, 166, 194, 235))
            body_y += u * 13.5

        if spec.is_ahian:
            track = (left, body_y + u * 2, w - u * 22, body_y + u * 5.2)
            draw.rounded_rectangle(track, radius=u * 1.6, fill=(255, 255, 255, 34))
            filled = track[0] + (track[2] - track[0]) * 0.62
            draw.rounded_rectangle((track[0], track[1], filled, track[3]),
                                   radius=u * 1.6,
                                   fill=rgba(M.mix_colour(M.PURPLE, M.TEAL, 0.7), 235))

        footer_y = h - u * 13
        put_text(draw, (left, footer_y), "NO RESPONSE", self.fonts.get(7.8 * u),
                 (152, 142, 170, 175), tracking=u * 1.1)
        put_text(draw, (w - u * 19, footer_y), spec.code, self.fonts.get(8.4 * u),
                 rgba(accent, 240), tracking=u * 0.8, anchor="right")

        sprite = body.convert("RGBA")
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=u * 10,
                                               fill=255)
        sprite.putalpha(mask)

        shadow = Image.new("RGBA", (w + int(u * 44), h + int(u * 44)), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (u * 18, u * 24, w + u * 18, h + u * 24), radius=u * 12,
            fill=(0, 0, 0, 132))
        self._shadows[spec.key] = shadow.filter(ImageFilter.GaussianBlur(u * 11))
        self._cards[spec.key] = sprite
        self._base_alpha[spec.key] = sprite.getchannel("A")
        return sprite

    def _card_shadow(self, spec):
        self._card_sprite(spec)
        return self._shadows[spec.key]

    def _settled_layer(self, cards):
        key = tuple(c.spec.key for c in cards)
        if key == self._settled_key and self._settled is not None:
            return self._settled
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        for card in cards:
            shadow = self._card_shadow(card.spec)
            layer.alpha_composite(shadow, (int(card.rect.x - self.px(16)),
                                           int(card.rect.y - self.px(20))))
            layer.alpha_composite(self._card_sprite(card.spec),
                                  (int(card.rect.x), int(card.rect.y)))
        self._settled = layer
        self._settled_key = key
        return layer

    def _paste_card(self, img, card):
        sprite = self._card_sprite(card.spec)
        shadow = self._card_shadow(card.spec)
        if card.alpha < 0.999:
            sprite = sprite.copy()
            sprite.putalpha(self._base_alpha[card.spec.key].point(
                lambda v, a=card.alpha: int(v * a)))
        if (abs(card.rect.w - sprite.width) > 1
                or abs(card.rect.h - sprite.height) > 1):
            size = (max(1, int(card.rect.w)), max(1, int(card.rect.h)))
            sprite = sprite.resize(size, Image.BILINEAR)
        self._paste(img, shadow, (card.rect.x - self.px(16), card.rect.y - self.px(20)))
        self._paste(img, sprite, (card.rect.x, card.rect.y))
        if card.flash > 0.02:
            draw = self._d(img)
            accent = M.ACCENTS[card.spec.accent % len(M.ACCENTS)]
            draw.rounded_rectangle(
                (card.rect.x, card.rect.y, card.rect.right, card.rect.bottom),
                radius=self.px(10), outline=rgba(accent, 170 * card.flash),
                width=max(1, int(self.px(1.4))))

    def _outbreak(self, frame):
        index = max(0, min(12, int(round(frame.desktop_dim / 0.46 * 12))))
        img = self._dimmed(index).copy()
        settled = [c for c in frame.cards if c.progress >= 0.999]
        if settled:
            self._paste(img, self._settled_layer(settled), (0, 0))
        for card in frame.cards:
            if card.progress < 0.999:
                self._paste_card(img, card)
        return img

    # ---- act 2 --------------------------------------------------------------
    def _blue_background(self):
        if self._blue_bg is not None:
            return self._blue_bg
        w, h = self.w, self.h
        base = self._gradient(ink(M.BLUE_TOP), ink(M.BLUE_BOTTOM))
        base = Image.alpha_composite(base.convert("RGBA"), self._blurred_bloom(
            (-0.05, -0.10), (0.70, 0.70), (0.38, 0.62, 1.0), 12)).convert("RGB")
        base = Image.alpha_composite(base.convert("RGBA"), self._blurred_bloom(
            (0.92, 1.05), (0.55, 0.50), (0.42, 0.26, 0.86), 16)).convert("RGB")
        # A single quiet light across the upper third.
        base = Image.alpha_composite(base.convert("RGBA"), self._blurred_bloom(
            (0.35, -0.05), (0.95, 0.52), (0.52, 0.70, 1.0), 26)).convert("RGB")
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

    def _blue_screen(self, frame):
        self._bg = (24, 60, 118)
        blue = frame.blue
        w, h, u = self.w, self.h, self.u
        img = self._blue_background().copy()
        draw = self._d(img)
        layout = self.scene.blue_layout()
        pad = layout["pad"]

        # ---- header
        self._dot_matrix(draw, "SMTH", pad, self.px(46), max(1.4, self.px(1.75)),
                         rgba(M.BLUE_INK, 240))
        put_text(draw, (pad + self.px(98), self.px(38)), "SMTH OS",
                 self.fonts.get(11.0 * u), rgba(M.BLUE_INK, 250),
                 tracking=self.px(1.2), bold=True)
        meta_font = self.fonts.get(8.2 * u)
        put_text(draw, (pad + self.px(98), self.px(50)),
                 "SESSION 03  ·  KERNEL EVENT", meta_font,
                 rgba(M.BLUE_DIM, 175), tracking=self.px(1.4))
        right = w - pad
        put_text(draw, (right, self.px(38)), "AH1AN", meta_font,
                 rgba(M.TEAL_BRIGHT, 215), tracking=self.px(2.2), anchor="right")
        put_text(draw, (right, self.px(50)), "AESTHETIC SUBSYSTEM ONLINE", meta_font,
                 rgba(M.BLUE_DIM, 145), tracking=self.px(1.2), anchor="right")

        # ---- headline
        size = layout["headline_size"]
        head = self.fonts.get(size)
        tracking = self.px(0.9)
        max_w = w - pad * 2
        lines = wrap(head, blue.head, tracking, max_w)[:2]
        if len(lines) > 1 and measure(head, lines[0], tracking) < measure(
                head, lines[1], tracking) * 0.6:
            lines = (wrap(head, blue.head, tracking, max_w * 1.2) or lines)[:2]
        y = layout["headline"][1]
        for line in lines:
            put_text(draw, (pad, y), line, head, rgba(M.BLUE_INK, 255),
                     tracking=tracking, bold=True)
            y += size * 1.16
        sub = self.fonts.get(layout["subline_size"])
        put_text(draw, (pad, y + size * 0.20), blue.sub, sub,
                 rgba(M.BLUE_DIM, 240), tracking=self.px(0.4))
        rule_y = y + size * 0.78
        rule_w = min(w - 2 * pad, 0.46 * w)
        draw.line((pad, rule_y, pad + rule_w, rule_y),
                  fill=rgba(M.BLUE_RULE, 235), width=max(1, int(self.px(1.2))))
        draw.line((pad, rule_y, pad + self.px(56), rule_y),
                  fill=rgba(M.TEAL_BRIGHT, 245), width=max(2, int(self.px(2.2))))

        # ---- countdown
        cy = layout["count_y"] + self.px(52)
        radius = self.px(44)
        cx = pad + radius
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                     outline=rgba(M.BLUE_RULE, 220), width=max(1, int(self.px(1.4))))
        sweep = 360.0 * (1.0 - blue.progress)
        if sweep > 0.5:
            draw.arc((cx - radius, cy - radius, cx + radius, cy + radius),
                     270, 270 + sweep, fill=rgba(M.TEAL_BRIGHT, 250),
                     width=max(2, int(self.px(2.6))))
        number_font = self.fonts.get(self.px(40) * (1.0 + 0.06 * blue.tick))
        put_text(draw, (cx, cy + self.px(15)), str(blue.countdown), number_font,
                 rgba(M.BLUE_INK, 255), bold=True, anchor="center")
        label_font = self.fonts.get(8.6 * u)
        text_x = cx + radius + self.px(26)
        put_text(draw, (text_x, cy - self.px(23)), "RECONFIGURING DESKTOP",
                 label_font, rgba(M.BLUE_DIM, 210), tracking=self.px(2.4))
        put_text(draw, (text_x, cy - self.px(7)),
                 "AHIAN is rebuilding your reality", self.fonts.get(11.4 * u),
                 rgba(M.BLUE_INK, 240), tracking=self.px(0.4))
        bar = (text_x, cy + self.px(10),
               text_x + min(w - text_x - pad, self.px(330)), cy + self.px(13.6))
        draw.rounded_rectangle(bar, radius=self.px(2), fill=(210, 235, 255, 46))
        fill_to = bar[0] + (bar[2] - bar[0]) * blue.progress
        if fill_to > bar[0] + 1:
            draw.rounded_rectangle((bar[0], bar[1], fill_to, bar[3]),
                                   radius=self.px(2), fill=rgba(M.TEAL_BRIGHT, 245))
        for i in range(M.COUNTDOWN_FROM):
            x = bar[0] + i * self.px(14)
            on = blue.progress >= (i + 1) / float(M.COUNTDOWN_FROM)
            draw.rectangle((x, cy + self.px(22), x + self.px(8), cy + self.px(26)),
                           fill=rgba(M.TEAL_BRIGHT if on else (0.30, 0.42, 0.62),
                                     235 if on else 150))
        put_text(draw, (bar[2] + self.px(14), cy + self.px(14)),
                 f"{int(round(blue.progress * 100)):d}%", self.fonts.get(8.0 * u),
                 rgba(M.BLUE_DIM, 215), tracking=self.px(0.8))

        # ---- footer
        meta_y = layout["meta_y"]
        put_text(draw, (pad, meta_y), "STOP CODE: AH1AN_ASCENSION", label_font,
                 rgba(M.BLUE_DIM, 210), tracking=self.px(1.6))
        put_text(draw, (pad, meta_y + self.px(17)), "0x0000AH1A  ·  MODE: AHIAN",
                 self.fonts.get(8.2 * u), rgba(M.BLUE_DIM, 145),
                 tracking=self.px(1.4))
        pulse = 0.55 + 0.45 * math.sin(frame.t_ms / 260.0)
        dot_r = self.px(3.4)
        dx = right - self.px(4)
        draw.ellipse((dx - dot_r, meta_y - dot_r * 2.7, dx + dot_r,
                      meta_y - dot_r * 0.7),
                     fill=rgba(M.TEAL_BRIGHT, int(120 + 120 * pulse)))
        put_text(draw, (dx - self.px(14), meta_y), "DO NOT POWER OFF", label_font,
                 rgba(M.BLUE_DIM, 175), tracking=self.px(1.6), anchor="right")
        put_text(draw, (right, meta_y + self.px(17)), "AHIAN / 9.0 SEC",
                 self.fonts.get(8.2 * u), rgba(M.BLUE_DIM, 135),
                 tracking=self.px(1.4), anchor="right")
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

    def _wallpaper(self, phase):
        bucket = int(phase * 24) % 24
        cached = self._wall.get(bucket)
        if cached is not None:
            return cached
        w, h = self.w, self.h
        low = (max(32, w // 4), max(24, h // 4))
        small = Image.new("RGB", low)
        draw = draw_on(small)
        for y in range(low[1]):
            v = (y + 0.5) / low[1]
            for x in range(low[0]):
                uu = (x + 0.5) / low[0]
                draw.point((x, y), fill=ink(M.flow_colour(uu, v, phase)))
        img = small.resize((w, h), Image.BICUBIC)
        img = Image.alpha_composite(img.convert("RGBA"), self._blurred_bloom(
            (0.10, 0.16), (0.52, 0.62), M.PURPLE, 74)).convert("RGB")
        img = Image.alpha_composite(img.convert("RGBA"), self._blurred_bloom(
            (1.02, 1.04), (0.55, 0.58), M.TEAL, 58)).convert("RGB")
        for i, colour in enumerate((M.PURPLE_SOFT, M.TEAL_BRIGHT)):
            img = Image.alpha_composite(img.convert("RGBA"), self._blurred_bloom(
                (0.5, 0.34 + 0.26 * i), (0.72, 0.30), colour, 14)).convert("RGB")
        draw = self._d(img)
        step = max(20, int(self.px(34)))
        radius = max(0.9, self.px(1.0))
        for y in range(step, h, step):
            for x in range(step, w, step):
                draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                             fill=(237, 231, 255, 14))
        img = Image.alpha_composite(img.convert("RGBA"), self._vignette_layer()).convert("RGB")
        self._wall[bucket] = img
        return img

    def _draw_black_hole(self, img, t_ms, alpha):
        """The live AHIAN desktop's dot disk, so the fade uncovers the same scene.

        Mirrors home.py: a Keplerian dot disk (inner dots orbit faster), a void
        and a teal orbit ring.  Stars drift slowly behind it.
        """
        if alpha <= 0.01:
            return
        self._bg = (34, 26, 64)
        draw = self._d(img)
        w, h = self.w, self.h
        scale = h / 1080.0
        cx, cy, R = w * 0.66, h * 0.50, h * 0.105
        seconds = t_ms / 1000.0
        # Stars, deterministic and very quiet.
        for i in range(56):
            sx = ((i * 0.618034 + 0.13) % 1.0) * w
            sy = ((i * 0.381966 + 0.37) % 1.0) * h
            twinkle = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(seconds * 1.4 + i))
            radius = max(0.7, (0.7 + 0.9 * ((i * 7) % 10) / 10.0) * scale)
            draw.ellipse((sx - radius, sy - radius, sx + radius, sy + radius),
                         fill=rgba(M.TEAL if i % 2 else M.VIOLET,
                                   int(58 * twinkle * alpha)))
        cs, sn, tilt = math.cos(-0.22), math.sin(-0.22), 0.27
        gold = math.pi * (3 - math.sqrt(5))
        for i in range(430):
            rr = 1.45 + 2.95 * math.sqrt((i + 0.5) / 430)
            angle = i * gold + 0.55 * (1.45 / rr) ** 1.5 * seconds
            r = rr * R
            x = r * math.cos(angle)
            s = math.sin(angle)
            y = r * s * tilt if s >= 0 else -math.sqrt(max(0.0, r * r - x * x)) * 0.93
            tr = (rr - 1.45) / 2.95
            bright = 0.62 - 0.38 * math.cos(angle)
            radius = max(1.0, (1.0 + 3.4 * bright * (1 - 0.55 * tr)) * scale * 0.9)
            px, py = cx + x * cs - y * sn, cy + x * sn + y * cs
            draw.ellipse((px - radius, py - radius, px + radius, py + radius),
                         fill=rgba(M.TEAL if i % 2 else M.PURPLE_SOFT,
                                   int(208 * bright * alpha)))
        draw.ellipse((cx - R, cy - R, cx + R, cy + R),
                     fill=rgba((0.020, 0.014, 0.040), int(255 * alpha)))
        pulse = 0.65 + 0.35 * math.sin(seconds * 2.2)
        ring = max(1.0, (1.2 + 1.8 * pulse) * scale)
        draw.ellipse((cx - R * 1.08, cy - R * 1.08, cx + R * 1.08, cy + R * 1.08),
                     outline=rgba(M.TEAL_BRIGHT, int(235 * alpha)), width=int(ring) or 1)

    def _brand(self, img, frame):
        self._bg = (34, 26, 64)
        tr = frame.transform
        if tr.brand <= 0 or tr.brand_alpha <= 0.02:
            return
        draw = self._d(img)
        u = self.u
        mark_w = min(0.42 * self.w, 0.50 * self.h * (23 / 7.0))
        spacing = mark_w / 23.0 * tr.brand_scale
        dot = spacing * 0.30
        cx = tr.brand_x * self.w
        cy = tr.brand_y * self.h
        origin_x = cx - (23 * spacing) / 2
        origin_y = cy - (7 * spacing) / 2
        for (col, row) in self.scene.brand_dots:
            order = (col / 22.0) * 0.62 + (row / 6.0) * 0.38
            start = M.BRAND_START_MS + order * (M.BRAND_MS - 260)
            progress = M.clamp((frame.t_ms - start) / 260.0)
            if progress <= 0:
                continue
            radius = dot * (1.16 - 0.16 * M.ease(progress))
            x = origin_x + (col + 0.5) * spacing
            y = origin_y + (row + 0.5) * spacing
            alpha = int(255 * tr.brand_alpha * progress)
            colour = M.mix_colour(M.PURPLE_SOFT, M.TEAL_BRIGHT,
                                  col / 22.0 * 0.7 + row / 6.0 * 0.3)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                         fill=rgba(colour, alpha))
        rule_w = mark_w * 0.74 * M.ease(tr.brand)
        rule_y = cy + (7 * spacing) / 2 + self.px(26)
        draw.line((cx - rule_w / 2, rule_y, cx + rule_w / 2, rule_y),
                  fill=rgba(M.TEAL_BRIGHT, int(210 * tr.brand_alpha)), width=1)
        if tr.brand > 0.35 and tr.brand_alpha > 0.25:
            put_text(draw, (cx, rule_y + self.px(21)), "A H I A N",
                     self.fonts.get(8.6 * u),
                     rgba(M.INK, int(165 * tr.brand_alpha)),
                     tracking=self.px(3.0), anchor="center")

    def _transform_frame(self, frame):
        self._bg = (34, 26, 64)
        tr = frame.transform
        img = self._wallpaper(tr.phase).copy()
        hole = M.ease(clamp01((frame.t_ms - 21200.0) / 1150.0))
        self._draw_black_hole(img, frame.t_ms, hole)
        self._brand(img, frame)
        for spec, progress in zip(self.scene.icons, tr.icons):
            self._draw_shortcut(img, spec, progress, ahian=True)
        if self.scene.profile == "linux":
            self._draw_clock_widget(img, self.scene.layout["clock"], tr.widgets,
                                    ahian=True)
            if self.scene.layout["rings"] is not None:
                self._draw_glance(img, self.scene.layout["rings"], tr.widgets,
                                  ahian=True)
            self._draw_waybar(img, self.scene.layout["bar"], tr.panel, ahian=True)
        else:
            self._draw_taskbar(img, self.scene.layout["bar"], tr.panel, ahian=True)
        self._toast(img, tr.toast)
        self._shimmer(img, tr.shimmer)
        return img

    def _toast(self, img, progress):
        self._bg = (12, 10, 17)
        if progress <= 0.01:
            return
        draw = self._d(img)
        u = self.u
        text = "AHIAN  ·  UPGRADE COMPLETE"
        font = self.fonts.get(8.8 * u)
        width = measure(font, text, self.px(1.6)) + self.px(64)
        height = self.px(34)
        x = (self.w - width) / 2
        y = self.h - (self.px(124) if self.scene.profile == "linux" else self.px(122))
        y += (1.0 - progress) * self.px(12)
        draw.rounded_rectangle((x, y + self.px(3), x + width, y + height + self.px(3)),
                               radius=height / 2, fill=(0, 0, 0, int(90 * progress)))
        draw.rounded_rectangle((x, y, x + width, y + height), radius=height / 2,
                               fill=rgba((0.043, 0.039, 0.061), int(238 * progress)),
                               outline=rgba(M.TEAL, int(110 * progress)), width=1)
        dot = self.px(3.4)
        draw.ellipse((x + self.px(22) - dot, y + height / 2 - dot,
                      x + self.px(22) + dot, y + height / 2 + dot),
                     fill=rgba(M.TEAL_BRIGHT, int(255 * progress)))
        put_text(draw, (x + self.px(36), y + height / 2 + self.px(3.2)), text,
                 font, rgba(M.INK, int(240 * progress)), tracking=self.px(1.6))

    def _shimmer(self, img, progress):
        if progress <= 0 or progress >= 1:
            return
        draw = self._d(img)
        x = -self.w * 0.45 + progress * self.w * 1.9
        band = self.w * 0.20
        env = math.sin(progress * math.pi)
        skew = self.h * 0.45
        draw.polygon([(x, 0), (x + band, 0), (x + band - skew, self.h),
                      (x - skew, self.h)], fill=(255, 255, 255, int(18 * env)))
        draw.polygon([(x + band * 0.7, 0), (x + band * 0.78, 0),
                      (x + band * 0.78 - skew, self.h), (x + band * 0.7 - skew, self.h)],
                     fill=(255, 255, 255, int(26 * env)))

    # ---- shared post effects ------------------------------------------------
    def _glitch(self, img, frame, extra_flash=0.0):
        glitch = frame.glitch
        if not glitch.active and extra_flash <= 0.001:
            return img
        if abs(glitch.brightness - 1.0) > 0.002:
            img = ImageEnhance.Brightness(img).enhance(glitch.brightness)
        if glitch.split > 0.4:
            r, g, b = img.split()
            shift = int(round(glitch.split))
            r = ImageChops.offset(r, shift, 0)
            b = ImageChops.offset(b, -shift, 0)
            img = Image.merge("RGB", (r, g, b))
        if glitch.slice_y >= 0:
            y0 = int(self.h * M.clamp(glitch.slice_y - 0.05))
            y1 = int(self.h * M.clamp(glitch.slice_y + 0.05))
            if y1 > y0 + 2:
                img.paste(img.crop((0, y0, self.w, y1)),
                          (int(glitch.slice_shift), y0))
        if glitch.noise > 0.02 or extra_flash > 0.001:
            if self._noise is None:
                self._noise = Image.effect_noise((self.w, self.h), 28)
            grain = ImageChops.offset(self._noise, int(frame.t_ms * 7) % self.w,
                                      int(frame.t_ms * 5) % self.h)
            img = Image.blend(img, Image.merge("RGB", (grain, grain, grain)),
                              min(0.17, 0.045 + 0.055 * glitch.noise))
        if glitch.flash > 0.01 or extra_flash > 0.001:
            img = Image.blend(img, Image.new("RGB", img.size, (226, 240, 255)),
                              min(0.82, glitch.flash + extra_flash))
        if glitch.scan_y >= 0:
            draw = self._d(img)
            y = glitch.scan_y * self.h
            draw.rectangle((0, y - self.px(26), self.w, y + self.px(26)),
                           fill=(180, 225, 255, 18))
            draw.rectangle((0, y, self.w, y + max(1, self.px(1.6))),
                           fill=(235, 248, 255, 70))
        return img

    def _squeeze(self, img, opened, edge):
        if opened >= 0.999:
            return img
        band_h = max(2, int(self.h * opened))
        top = (self.h - band_h) // 2
        out = Image.new("RGB", img.size, (3, 4, 9))
        out.paste(img.crop((0, top, self.w, top + band_h)), (0, top))
        draw = draw_on(out)
        glow = max(1, int(self.px(2.2)))
        draw.rectangle((0, top - glow, self.w, top), fill=edge)
        draw.rectangle((0, top + band_h, self.w, top + band_h + glow), fill=edge)
        draw.rectangle((0, top + band_h // 2 - 1, self.w, top + band_h // 2 + 1),
                       fill=edge)
        return out

    # ---- entry point --------------------------------------------------------
    def render(self, t_ms):
        frame = self.scene.frame(t_ms)
        if frame.reduced:
            return self._transform_frame(self.scene.frame(M.FADE_START_MS + 90))

        if frame.phase == "outbreak":
            return self._glitch(self._outbreak(frame), frame)

        if frame.phase == "blue":
            if frame.blue.open <= 0.0:
                last = self._outbreak(self.scene.frame(M.BLUE_START_MS))
                squeeze = 1.0 - M.clamp(
                    (frame.t_ms - M.BLUE_START_MS) / max(1.0, M.COLLAPSE_MS))
                return self._glitch(self._squeeze(last, squeeze, (206, 232, 255)),
                                    frame)
            blue = self._squeeze(self._blue_screen(frame), frame.blue.open,
                                 (215, 240, 255))
            return self._glitch(blue, frame)

        transform = frame.transform
        if transform.open <= 0.0:
            blue = self._blue_screen(self.scene.frame(M.BLUE_END_MS - 40))
            squeeze = 1.0 - M.clamp(
                (frame.t_ms - M.BLUE_END_MS) / max(1.0, M.BLUE_CLOSE_MS))
            return self._glitch(self._squeeze(blue, squeeze, (215, 240, 255)), frame)
        img = self._squeeze(self._transform_frame(frame), transform.open,
                            (170, 255, 240))
        opened_at = M.WALL_OPEN_START_MS + M.WALL_OPEN_MS
        bloom = M.clamp(1.0 - (frame.t_ms - opened_at) / 280.0)
        if frame.t_ms >= opened_at and bloom > 0.01:
            img = Image.blend(img, Image.new("RGB", img.size, (198, 255, 248)),
                              0.24 * bloom)
        return self._glitch(img, frame)


if __name__ == "__main__":
    import sys
    t = float(sys.argv[1]) if len(sys.argv) > 1 else 4200.0
    profile = sys.argv[2] if len(sys.argv) > 2 else "linux"
    out = sys.argv[3] if len(sys.argv) > 3 else "/tmp/ahian-frame.png"
    scene = M.StartupScene(1280, 800, profile=profile)
    SceneRenderer(scene).render(t).save(out)
    print(out)
