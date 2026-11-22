"""SMTH Orbit: a live system observatory.

The whole window is one drawn composition rather than a stack of widgets: a
dot-matrix clock, three orbital gauges, glass telemetry panels and a ticker.
All of it is plain Pillow so the exact frames can be rendered and checked
without a display; `smth-orbit` only supplies a window and a clock.

Data comes straight from /proc and /sys. Nothing here shells out, so the app
stays responsive and works on a machine with no network or desktop tools.
"""
import glob, math, os, random, time
from collections import deque
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

try:
    import smthdot as D
    GLYPHS = D.GLYPHS
except Exception:                                     # pragma: no cover - image always ships it
    GLYPHS = {}

INK = (242, 198, 210)
INK_DIM = (152, 124, 134)
INK_FAINT = (94, 75, 84)
MAROON = (112, 27, 53)
MAROON_LIT = (178, 74, 105)
VOID = (9, 9, 11)
GLASS = (17, 12, 18)

FONT_DIRS = (
    os.environ.get("SMTH_FONT_DIR", "/usr/share/fonts/truetype/smth"),
    "/usr/share/fonts/truetype/dejavu",
)
_FONTS = {}


def font(size, bold=False):
    size = max(7, int(round(size)))
    key = (size, bold)
    if key in _FONTS:
        return _FONTS[key]
    names = ("SpaceMono-Bold.ttf",) if bold else ("SpaceMono-Regular.ttf", "DejaVuSansMono.ttf")
    loaded = None
    for name in names:
        for folder in FONT_DIRS:
            try:
                loaded = ImageFont.truetype(os.path.join(folder, name), size)
                break
            except (OSError, ValueError):
                continue
        if loaded:
            break
    if loaded is None:
        loaded = ImageFont.load_default(size=size)
    _FONTS[key] = loaded
    return loaded


def tracked(draw, xy, text, fnt, fill, tracking=0):
    """Mono text with letter spacing; returns the advance width."""
    x, y = xy
    if not tracking:
        draw.text((x, y), text, font=fnt, fill=fill)
        return draw.textlength(text, font=fnt)
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking
    return x - xy[0]


def ellipsize(draw, text, fnt, width):
    if draw.textlength(text, font=fnt) <= width:
        return text
    cut = text
    while cut and draw.textlength(cut + "…", font=fnt) > width:
        cut = cut[:-1]
    return (cut + "…") if cut else "…"


def dot_text(draw, xy, text, dot, colour=INK, accent=None, halo=None):
    """Draw the shared 5x7 dot alphabet. Returns the advance width."""
    x, y = xy
    for index, ch in enumerate(text.upper()):
        rows = GLYPHS.get(ch)
        if rows is None:
            x += 6 * dot
            continue
        for row in range(7):
            for col in range(5):
                if not (rows[row] >> (4 - col)) & 1:
                    continue
                px = x + (index * 6 + col) * dot
                py = y + row * dot
                colour_now = accent if (accent and (index * 6 + col + row) % 7 == 0) else colour
                r = dot * 0.40
                if halo:
                    draw.ellipse((px - r * 2.2, py - r * 2.2, px + r * 2.2, py + r * 2.2), fill=halo)
                draw.ellipse((px - r, py - r, px + r, py + r), fill=colour_now)
    return (len(text) * 6 - 1) * dot


def dot_width(text, dot):
    return (len(text) * 6 - 1) * dot


def _rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return mask


def _rgba(size, colour=(0, 0, 0, 0)):
    return Image.new("RGBA", (int(size[0]), int(size[1])), colour)


def human_rate(value):
    for unit in ("B/s", "K/s", "M/s", "G/s"):
        if value < 1024 or unit == "G/s":
            return f"{value:.0f} {unit}" if unit == "B/s" else f"{value:.1f} {unit}"
        value /= 1024.0


def human_uptime(seconds):
    seconds = int(max(0, seconds))
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    return f"{days}D {hours:02d}:{minutes:02d}" if days else f"{hours:02d}:{minutes:02d}:{rest % 60:02d}"


# ---------------------------------------------------------------- sampling


def _read(path, default=""):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return default


def _cpu_totals():
    parts = _read("/proc/stat").splitlines()
    total = idle = 0
    cores = []
    for line in parts:
        if not line.startswith("cpu"):
            continue
        fields = [int(v) for v in line.split()[1:] if v.isdigit()]
        if len(fields) < 4:
            continue
        busy = sum(fields) - fields[3] - (fields[4] if len(fields) > 4 else 0)
        if line[3:4].isdigit():
            cores.append((busy, sum(fields)))
        else:
            total += sum(fields)
            idle += fields[3] + (fields[4] if len(fields) > 4 else 0)
    return total, idle, cores


def _net_totals():
    rx = tx = 0
    for line in _read("/proc/net/dev").splitlines()[2:]:
        if ":" not in line:
            continue
        name, data = line.split(":", 1)
        if name.strip() in ("lo",):
            continue
        fields = data.split()
        if len(fields) >= 9:
            rx += int(fields[0])
            tx += int(fields[8])
    return rx, tx


def _battery():
    for path in glob.glob("/sys/class/power_supply/BAT*/capacity"):
        try:
            return int(_read(path).strip()) / 100.0
        except ValueError:
            continue
    return None


def _temperature():
    temps = []
    for path in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            value = int(_read(path).strip())
        except ValueError:
            continue
        temps.append(value / 1000.0 if value > 1000 else float(value))
    return max(temps) if temps else None


def _mem():
    total = available = 0
    for line in _read("/proc/meminfo").splitlines():
        if line.startswith("MemTotal:"):
            total = int(line.split()[1])
        elif line.startswith("MemAvailable:"):
            available = int(line.split()[1])
    return 0.0 if not total else 1.0 - available / total


def _disk():
    try:
        stat = os.statvfs("/")
        return 1.0 - stat.f_bavail / max(1, stat.f_blocks)
    except OSError:
        return 0.0


class Sampler:
    """Cheap, cached /proc sampling. Reads at most once a second."""

    def __init__(self):
        self.started = time.time()
        self.prev = _cpu_totals()
        self.prev_cores = self.prev[2]
        self.prev_net = _net_totals()
        self.prev_time = time.monotonic()
        self.sample = {}
        self.procs = []
        self.proc_prev = {}
        self.proc_time = 0.0
        self.at = 0.0

    def read(self):
        now = time.monotonic()
        if self.sample and now - self.at < 0.9:
            return self.sample
        total, idle, cores = _cpu_totals()
        ptotal, pidle, pcores = self.prev
        busy = max(0, (total - ptotal) - (idle - pidle))
        span = max(1, total - ptotal)
        cpu = min(1.0, busy / span)
        per_core = []
        for (cb, ct), (pb, pt) in zip(cores, pcores):
            per_core.append(min(1.0, max(0.0, (cb - pb) / max(1, ct - pt))))
        self.prev = (total, idle, cores)
        rx, tx = _net_totals()
        elapsed = max(0.001, now - self.prev_time)
        rx_rate = max(0.0, (rx - self.prev_net[0]) / elapsed)
        tx_rate = max(0.0, (tx - self.prev_net[1]) / elapsed)
        self.prev_net = (rx, tx)
        self.prev_time = now
        if now - self.proc_time > 2.0:
            self.proc_time = now
            cores_n = max(1, len(per_core) or (os.cpu_count() or 1))
            seen, ranked = {}, []
            tick_span = max(1, total - ptotal)
            for entry in glob.glob("/proc/[0-9]*/stat"):
                try:
                    raw = _read(entry)
                    open_paren = raw.index("(")
                    close_paren = raw.rindex(")")
                    name = raw[open_paren + 1:close_paren][:24] or "?"
                    fields = raw[close_paren + 2:].split()
                    ticks = int(fields[11]) + int(fields[12])
                except (OSError, ValueError, IndexError):
                    continue
                pid = os.path.basename(os.path.dirname(entry))
                seen[pid] = (name, ticks)
                before = self.proc_prev.get(pid, (name, ticks))[1]
                share = max(0, ticks - before) / tick_span * cores_n
                ranked.append((share, name))
            self.proc_prev = seen
            merged = {}
            for share, name in ranked:
                merged[name] = max(merged.get(name, 0.0), share)
            self.procs = sorted(merged.items(), key=lambda item: -item[1])[:4]
        self.sample = {
            "cpu": cpu,
            "cores": per_core[:8] or [cpu],
            "core_count": len(per_core) or (os.cpu_count() or 1),
            "mem": _mem(),
            "disk": _disk(),
            "rx": rx_rate,
            "tx": tx_rate,
            "load": os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0,
            "uptime": time.time() - self.started if not os.path.exists("/proc/uptime")
            else float(_read("/proc/uptime", "0 0").split()[0]),
            "battery": _battery(),
            "temp": _temperature(),
            "procs": self.procs,
            "kernel": os.uname().release.split("-")[0] if hasattr(os, "uname") else "",
            "host": os.uname().nodename if hasattr(os, "uname") else "SMTH",
            "threads": len(glob.glob("/proc/[0-9]*/task/*")) or 0,
        }
        self.at = now
        return self.sample


# ------------------------------------------------------------------ scene


class OrbitScene:
    def __init__(self, width, height):
        self.w = max(480, int(width))
        self.h = max(360, int(height))
        self.s = max(0.70, min(1.35, min(self.w / 1180.0, self.h / 760.0)))
        self.compact = self.w < 980 or self.h / self.w > 1.22
        self._layout()
        self.bg = self._background()
        self.blur = self.bg.filter(ImageFilter.GaussianBlur(22))
        self.rx_hist = deque([0.0] * 44, maxlen=44)
        self.tx_hist = deque([0.0] * 44, maxlen=44)
        self.base = self._chrome()
        self.halo = self._halo()
        self.ticker_cache = None
        self.phase = 0.0

    # -- geometry ----------------------------------------------------
    def _layout(self):
        s = self.s
        self.m = round(28 * s)
        self.gap = round(18 * s)
        self.top_h = round(66 * s)
        self.ticker_h = round(58 * s)
        self.top = self.m + self.top_h
        self.ticker = (self.m, self.h - self.m - self.ticker_h, self.w - self.m, self.h - self.m)
        inner_top = self.top
        inner_bottom = self.ticker[1] - self.gap
        self.left = (self.m, inner_top, self.m + round((self.w - 2 * self.m - self.gap) * 0.61), inner_bottom) \
            if not self.compact else (self.m, inner_top, self.w - self.m, inner_top + round((inner_bottom - inner_top) * 0.55))
        if not self.compact:
            rx0 = self.left[2] + self.gap
            rx1 = self.w - self.m
            height = inner_bottom - inner_top
            gap = round(12 * s)
            h1 = round(height * 0.40)
            h2 = round(height * 0.34)
            self.panels = [
                (rx0, inner_top, rx1, inner_top + h1),
                (rx0, inner_top + h1 + gap, rx1, inner_top + h1 + gap + h2),
                (rx0, inner_top + h1 + h2 + 2 * gap, rx1, inner_bottom),
            ]
        else:
            y0 = self.left[3] + self.gap
            width = (self.w - 2 * self.m - 2 * self.gap) // 3
            self.panels = [
                (self.m, y0, self.m + width, inner_bottom),
                (self.m + width + self.gap, y0, self.m + 2 * width + self.gap, inner_bottom),
                (self.m + 2 * (width + self.gap), y0, self.w - self.m, inner_bottom),
            ]
        self.radius = round(22 * s)
        pill_y = self.m + round(9 * s)
        pill_h = round(34 * s)
        pill_w = round(112 * s)
        right = self.w - self.m
        self.pills = []
        for index in range(4):
            x1 = right - index * (pill_w + round(8 * s))
            self.pills.append((x1 - pill_w, pill_y, x1, pill_y + pill_h))
        self.pills.reverse()

    # -- painting helpers -------------------------------------------
    def _core_geometry(self):
        x0, y0, x1, y1 = self.left
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + 2 * self.s
        span = min((x1 - x0) * 0.40, (y1 - y0) * 0.405)
        return cx, cy, span

    def _halo(self):
        """The core bloom is static, so it is blurred once and reused."""
        s = self.s
        cx, cy, span = self._core_geometry()
        halo = _rgba((self.w, self.h))
        draw = ImageDraw.Draw(halo)
        draw.ellipse((cx - span * 1.55, cy - span * 1.55, cx + span * 1.55, cy + span * 1.55),
                     fill=(112, 27, 53, 84))
        draw.ellipse((cx - span * 0.86, cy - span * 0.86, cx + span * 0.86, cy + span * 0.86),
                     fill=(178, 74, 105, 36))
        return halo.filter(ImageFilter.GaussianBlur(58 * s))

    def _background(self):
        w, h, s = self.w, self.h, self.s
        img = Image.new("RGB", (w, h), VOID)
        px = img.load()
        for y in range(h):
            fy = y / max(1, h - 1)
            for x in range(0, w, 2):
                fx = x / max(1, w - 1)
                glow = max(0.0, 1.0 - math.hypot(fx - 0.14, fy - 0.02) * 1.45)
                under = max(0.0, 1.0 - math.hypot(fx - 1.04, fy - 1.02) * 1.20)
                r = 7 + 21 * glow * glow + 6 * under
                g = 7 + 3 * glow + 4 * under
                b = 9 + 13 * glow * glow + 7 * under
                px[x, y] = (int(r), int(g), int(b))
                px[min(w - 1, x + 1), y] = (int(r), int(g), int(b))
        glow_layer = _rgba((w, h))
        gd = ImageDraw.Draw(glow_layer)
        gd.ellipse((-w * 0.36, -h * 0.52, w * 0.44, h * 0.58), fill=(112, 27, 53, 52))
        gd.ellipse((w * 0.68, h * 0.62, w * 1.18, h * 1.30), fill=(242, 198, 210, 12))
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(110 * s))
        img = Image.alpha_composite(img.convert("RGBA"), glow_layer)
        grid = _rgba((w, h))
        draw = ImageDraw.Draw(grid)
        step = max(22, round(30 * s))
        for yy in range(self.m, h - self.m, step):
            for xx in range(self.m, w - self.m, step):
                draw.ellipse((xx, yy, xx + 1.4, yy + 1.4), fill=(242, 198, 210, 26))
        img = Image.alpha_composite(img, grid)
        rng = random.Random(11)
        stars = ImageDraw.Draw(img)
        for _ in range(70):
            x, y = rng.randrange(w), rng.randrange(h)
            a = rng.randrange(30, 120)
            r = 0.6 + rng.random() * 1.2
            stars.ellipse((x, y, x + r, y + r), fill=(242, 198, 210, a))
        vignette = _rgba((w, h))
        vd = ImageDraw.Draw(vignette)
        for i in range(28):
            t = i / 27.0
            vd.rectangle((0, 0, w - 1, h - 1), outline=(0, 0, 0, int(36 * (1 - t))), width=int(2 + 10 * (1 - t)))
        return Image.alpha_composite(img, vignette)

    def _glass(self, canvas, box, radius=None, tint=GLASS, alpha=232):
        radius = radius or self.radius
        x0, y0, x1, y1 = [int(v) for v in box]
        w, h = max(4, x1 - x0), max(4, y1 - y0)
        shadow = _rgba(canvas.size)
        ImageDraw.Draw(shadow).rounded_rectangle((x0, y0 + max(6, self.s * 10), x1, y1 + max(6, self.s * 10)),
                                                radius, fill=(0, 0, 0, 120))
        canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(max(8, self.s * 16))))
        crop = self.blur.crop((x0, y0, x1, y1)).convert("RGB")
        tinted = Image.blend(crop, Image.new("RGB", (w, h), tint), 0.44).convert("RGBA")
        tinted.putalpha(alpha)
        sheen = _rgba((w, h))
        sd = ImageDraw.Draw(sheen)
        sheen_h = int(h * 0.52)
        for i in range(sheen_h):
            a = int(22 * (1 - i / max(1, sheen_h)))
            if a:
                sd.line((0, i, w, i), fill=(255, 255, 255, a))
        mask = _rounded_mask((w, h), radius)
        sheen.putalpha(Image.composite(sheen.split()[3], Image.new("L", (w, h), 0), mask))
        tinted = Image.alpha_composite(tinted, sheen)
        border = ImageDraw.Draw(tinted)
        border.rounded_rectangle((0, 0, w - 1, h - 1), radius, outline=(242, 198, 210, 60), width=1)
        border.rounded_rectangle((1, 1, w - 2, h - 2), radius - 1, outline=(255, 255, 255, 18), width=1)
        canvas.paste(tinted, (x0, y0), mask)

    def _chrome(self):
        s = self.s
        img = self.bg.copy()
        self._glass(img, self.ticker, radius=round(20 * s))
        for box in self.panels:
            self._glass(img, box)
        for box in self.pills:
            self._glass(img, box, radius=round(999 * s), alpha=214)
        draw = ImageDraw.Draw(img)
        # masthead
        title = "SMTH ORBIT"
        tracked(draw, (self.m, self.m - 2 * s), title, font(24 * s, bold=True), INK, 4 * s)
        tracked(draw, (self.m, self.m + 32 * s), "SYSTEM OBSERVATORY", font(9.5 * s), INK_DIM, 2.4 * s)
        # static panel headings and hairlines
        labels = ("TOP PROCESSES", "THROUGHPUT", "CORES")
        for box, label in zip(self.panels, labels):
            x0, y0, x1, y1 = box
            pad = round(18 * s)
            tracked(draw, (x0 + pad, y0 + pad * 0.62), label, font(9.5 * s), INK_DIM, 2.2 * s)
            draw.line((x0 + pad, y0 + pad * 1.72, x1 - pad, y0 + pad * 1.72), fill=(242, 198, 210, 28), width=1)
        # pill labels
        pill_labels = ("UPTIME", "LOAD", "TEMP", "POWER")
        for box, label in zip(self.pills, pill_labels):
            x0, y0, x1, y1 = box
            tracked(draw, (x0 + 12 * s, y0 + 7 * s), label, font(7.5 * s), INK_DIM, 1.6 * s)
        # ticker hints
        hint = "SPACE HOLD   F FULL   ESC CLOSE"
        hw = draw.textlength(hint, font=font(8.5 * s))
        draw.text((self.ticker[2] - round(18 * s) - hw, self.ticker[1] + (self.ticker_h - 12 * s) / 2),
                  hint, font=font(8.5 * s), fill=INK_DIM)
        draw.line((self.ticker[2] - round(18 * s) - hw - 16 * s, self.ticker[1] + 14 * s,
                   self.ticker[2] - round(18 * s) - hw - 16 * s, self.ticker[3] - 14 * s),
                  fill=(242, 198, 210, 40), width=1)
        return img

    # -- live frame ---------------------------------------------------
    def frame(self, t, sample, paused=False):
        s = self.s
        img = self.base.copy()
        layer = _rgba(img.size)
        draw = ImageDraw.Draw(layer)
        cpu = float(sample.get("cpu", 0.0))
        rx_now = float(sample.get("rx", 0.0))
        tx_now = float(sample.get("tx", 0.0))
        if rx_now > 0 and not any(self.rx_hist):          # a believable trace on the first frame
            self.rx_hist = deque([rx_now * (0.42 + 0.34 * abs(math.sin(i * 0.63))) for i in range(44)], maxlen=44)
        if tx_now > 0 and not any(self.tx_hist):
            self.tx_hist = deque([tx_now * (0.55 + 0.30 * abs(math.cos(i * 0.51))) for i in range(44)], maxlen=44)
        self.rx_hist.append(rx_now)
        self.tx_hist.append(tx_now)

        self._core(img, layer, t, sample, cpu)
        self._processes(draw, sample)
        self._throughput(draw, sample)
        self._cores(draw, sample)
        self._pills(draw, sample)
        self._ticker(img, draw, t, sample, paused)
        img = Image.alpha_composite(img, layer)
        if paused:
            img = Image.alpha_composite(img, _rgba(img.size, (5, 4, 6, 110)))
            hold = _rgba(img.size)
            label = "HOLD"
            dw = dot_width(label, 5 * s)
            dot_text(ImageDraw.Draw(hold), ((self.left[0] + self.left[2]) / 2 - dw / 2,
                                            (self.left[1] + self.left[3]) / 2 + 96 * s),
                     label, 5 * s, INK, accent=MAROON_LIT)
            img = Image.alpha_composite(img, hold)
        return img.convert("RGB")

    def _core(self, img, layer, t, sample, cpu):
        s = self.s
        x0, y0, x1, y1 = self.left
        cx, cy, span = self._core_geometry()
        img.alpha_composite(self.halo)
        draw = ImageDraw.Draw(layer)
        values = (cpu, float(sample.get("mem", 0.0)), float(sample.get("disk", 0.0)))
        radii = (span, span * 0.755, span * 0.515)
        for ring, (value, radius) in enumerate(zip(values, radii)):
            lit = int(round(max(0.0, min(1.0, value)) * 96))
            for k in range(96):
                angle = -math.pi / 2 + math.tau * k / 96
                px = cx + radius * math.cos(angle)
                py = cy + radius * math.sin(angle)
                if k < lit:
                    draw.ellipse((px - 1.8 * s, py - 1.8 * s, px + 1.8 * s, py + 1.8 * s),
                                 fill=INK if ring == 0 else (222, 176, 190))
                else:
                    draw.ellipse((px - 0.9 * s, py - 0.9 * s, px + 0.9 * s, py + 0.9 * s),
                                 fill=(242, 198, 210, 62))
            # one live orbiter per ring with a short comet trail
            speed = (0.34, 0.22, 0.14)[ring]
            base_angle = t * speed + ring * 2.1
            for trail in range(7, -1, -1):
                angle = base_angle - trail * 0.035
                px = cx + radius * math.cos(angle)
                py = cy + radius * math.sin(angle)
                alpha = int(210 * (1 - trail / 9.0))
                dot = (1.0 + 1.4 * (1 - trail / 8.0)) * s
                draw.ellipse((px - dot, py - dot, px + dot, py + dot),
                             fill=(255, 236, 243, alpha) if trail == 0 else (178, 74, 105, alpha // 3))
            # dust riding the ring, for a sense of orbit rather than a static dial
            for dust in range(9):
                angle = t * (0.05 + 0.012 * dust) + dust * 0.7 + ring
                px = cx + (radius + (6 + dust * 3) * s) * math.cos(angle)
                py = cy + (radius + (6 + dust * 3) * s) * math.sin(angle)
                draw.ellipse((px, py, px + 1.2 * s, py + 1.2 * s), fill=(242, 198, 210, 70))
        # rotating scan line and outer ticks
        sweep = t * 0.30
        draw.line((cx, cy, cx + span * 1.135 * math.cos(sweep), cy + span * 1.135 * math.sin(sweep)),
                  fill=(242, 198, 210, 40), width=max(1, int(1 * s)))
        for k in range(72):
            angle = math.tau * k / 72
            long = k % 6 == 0
            r0 = span * 1.19
            r1 = r0 + (7 if long else 3.5) * s
            draw.line((cx + r0 * math.cos(angle), cy + r0 * math.sin(angle),
                       cx + r1 * math.cos(angle), cy + r1 * math.sin(angle)),
                      fill=(242, 198, 210, 56 if long else 30), width=1)
        # the readout: a glowing dot-matrix percentage, the loudest thing on screen
        pct = f"{round(cpu * 100):02d}"
        dot = min(8.6 * s, span * 0.20)
        pct_w = dot_width(pct, dot)
        nx, ny = cx - pct_w / 2, cy - 3.5 * dot
        pad = int(24 * s)
        glow = _rgba((int(pct_w + 2 * pad), int(7 * dot + 2 * pad)))
        dot_text(ImageDraw.Draw(glow), (pad, pad), pct, dot, (242, 198, 210, 120))
        blur = glow.filter(ImageFilter.GaussianBlur(max(4.0, 7 * s)))
        img.paste(blur, (int(nx - pad), int(ny - pad)), blur)
        draw = ImageDraw.Draw(layer)
        dot_text(draw, (nx, ny), pct, dot, INK)
        tracked(draw, (cx - 26 * s, cy + 4.35 * dot), "PROCESSOR", font(7.5 * s), INK_DIM, 2.0 * s)
        tracked(draw, (cx - 40 * s, cy + 4.35 * dot + 13 * s),
                f"{sample.get('core_count', 1)} CORES", font(7.5 * s), INK_FAINT, 1.6 * s)
        # one quiet legend instead of labels crowding the rings
        legend = (("CPU", values[0]), ("MEM", values[1]), ("SSD", values[2]))
        widths = [24 * s + draw.textlength(f"{name} {round(v * 100)}", font=font(9 * s))
                  for name, v in legend]
        lx = (x0 + x1) / 2 - (sum(widths) + 34 * s * (len(widths) - 1)) / 2
        ly = min(y1 - 24 * s, cy + span + 22 * s)
        for (name, value), width in zip(legend, widths):
            draw.ellipse((lx, ly + 4 * s, lx + 5 * s, ly + 9 * s), fill=INK if name == "CPU" else MAROON_LIT)
            tracked(draw, (lx + 12 * s, ly), f"{name} {round(value * 100)}", font(9.5 * s), (203, 166, 180), 1.2 * s)
            lx += width + 34 * s

    def _processes(self, draw, sample):
        s = self.s
        x0, y0, x1, y1 = self.panels[0]
        pad = round(18 * s)
        top = y0 + pad * 2.5
        rows = (sample.get("procs") or [("idle", 0.0)])[:4]
        row_h = max(18 * s, (y1 - top - pad * 0.6) / 4)
        for index, (name, share) in enumerate(rows):
            y = top + index * row_h
            label = ellipsize(draw, name.upper()[:18], font(10 * s), (x1 - x0) - pad * 2 - 74 * s)
            draw.text((x0 + pad, y), label, font=font(10 * s), fill=INK if index == 0 else (206, 168, 180))
            dots_x0 = x0 + pad + 108 * s
            dots_x1 = x1 - pad - 44 * s
            count = max(4, int((dots_x1 - dots_x0) / (5 * s)))
            lit = int(max(0.0, min(1.0, share)) * count)
            for k in range(count):
                dx = dots_x0 + k * 5 * s
                draw.ellipse((dx, y + 6 * s, dx + 1.6 * s, y + 7.6 * s),
                             fill=(242, 198, 210, 120) if k < lit else (242, 198, 210, 26))
            value = f"{share * 100:.0f}%"
            draw.text((x1 - pad - draw.textlength(value, font=font(9 * s)), y - 1 * s),
                      value, font=font(9 * s), fill=INK_DIM)
        if not sample.get("procs"):
            draw.text((x0 + pad, top), "SAMPLING…", font=font(9 * s), fill=INK_FAINT)

    def _throughput(self, draw, sample):
        s = self.s
        x0, y0, x1, y1 = self.panels[1]
        pad = round(18 * s)
        chart_top = y0 + pad * 2.5
        chart_bottom = y1 - pad * 2.2
        width = x1 - x0 - pad * 2
        # grid
        for k in range(4):
            y = chart_top + (chart_bottom - chart_top) * k / 3
            draw.line((x0 + pad, y, x1 - pad, y), fill=(242, 198, 210, 18), width=1)
        peak = max(1.0, max(self.rx_hist), max(self.tx_hist))
        for hist, colour in ((self.rx_hist, INK), (self.tx_hist, MAROON_LIT)):
            points = []
            for index, value in enumerate(hist):
                px = x0 + pad + width * index / (len(hist) - 1)
                py = chart_bottom - (chart_bottom - chart_top) * min(1.0, value / peak * 0.94)
                points.append((px, py))
            if hist is self.rx_hist and len(points) > 2:
                area = list(points) + [(points[-1][0], chart_bottom), (points[0][0], chart_bottom)]
                draw.polygon(area, fill=(242, 198, 210, 34))
            draw.line(points, fill=colour + (200,), width=max(1, int(1.5 * s)), joint="curve")
        rx, tx = self.rx_hist[-1], self.tx_hist[-1]
        draw.text((x0 + pad, chart_top - 16 * s), f"RX {human_rate(rx)}", font=font(9 * s), fill=INK)
        label = f"TX {human_rate(tx)}"
        draw.text((x1 - pad - draw.textlength(label, font=font(9 * s)), chart_top - 16 * s),
                  label, font=font(9 * s), fill=MAROON_LIT)
        peak_label = f"PEAK {human_rate(peak)}"
        draw.text((x0 + pad, chart_bottom + 5 * s), peak_label, font=font(7 * s), fill=INK_FAINT)

    def _cores(self, draw, sample):
        s = self.s
        x0, y0, x1, y1 = self.panels[2]
        pad = round(18 * s)
        top = y0 + pad * 2.4
        bottom = y1 - pad * 1.4
        cores = list(sample.get("cores") or [0.0])[:8]
        count = max(1, len(cores))
        gap = 6 * s
        width = (x1 - x0 - pad * 2 - gap * (count - 1)) / count
        for index, value in enumerate(cores):
            bx = x0 + pad + index * (width + gap)
            draw.rounded_rectangle((bx, top, bx + width, bottom), radius=width / 2,
                                   fill=(255, 255, 255, 14), outline=(242, 198, 210, 44), width=1)
            for tick in (0.25, 0.5, 0.75):
                ty = bottom - (bottom - top) * tick
                draw.line((bx + 3 * s, ty, bx + width - 3 * s, ty), fill=(242, 198, 210, 24), width=1)
            filled = max(3.0, (bottom - top - 3) * max(0.03, min(1.0, value)))
            draw.rounded_rectangle((bx + 1.4, bottom - filled, bx + width - 1.4, bottom - 1.4),
                                   radius=width / 2,
                                   fill=(242, 198, 210, 210) if value < 0.8 else (178, 74, 105, 235))
            draw.text((bx + width / 2 - 4 * s, bottom + 4 * s), str(index), font=font(7 * s), fill=INK_FAINT)

    def _pills(self, draw, sample):
        s = self.s
        battery = sample.get("battery")
        temp = sample.get("temp")
        values = (
            human_uptime(sample.get("uptime", 0)),
            f"{sample.get('load', 0):.2f}",
            f"{temp:.0f}°C" if temp is not None else "—",
            f"{round(battery * 100)}%" if battery is not None else "AC",
        )
        for box, value in zip(self.pills, values):
            x0, y0, x1, y1 = box
            fnt = font(14 * s, bold=True)
            w = draw.textlength(value, font=fnt)
            draw.text(((x0 + x1) / 2 - w / 2, y0 + 13 * s), value, font=fnt, fill=INK)

    def _ticker(self, img, draw, t, sample, paused):
        s = self.s
        x0, y0, x1, y1 = self.ticker
        text = (f"{sample.get('kernel', '')} / {sample.get('host', '')} / "
                f"{sample.get('threads', 0)} THREADS / ALL SUBSYSTEMS NOMINAL / "
                "SPACE HOLD / F FULLSCREEN / ESC CLOSE / ").upper()
        dot = max(1.8, 3.1 * s)
        width = dot_width(text, dot)
        clip_w = max(80, (x1 - x0) - round(250 * s))
        height = y1 - y0
        key = (text, dot, height)
        if not self.ticker_cache or self.ticker_cache[0] != key:
            strip = _rgba((width * 2 + int(90 * s), height))
            sd = ImageDraw.Draw(strip)
            for x in (0, width + 90 * s):
                dot_text(sd, (x, height / 2 - 3.5 * dot), text, dot, INK_DIM)
            self.ticker_cache = (key, strip)
        strip = self.ticker_cache[1]
        clip_w = min(clip_w, strip.width)
        offset = int((t * 26 * s) % max(1, width + int(90 * s)))
        offset = min(offset, max(0, strip.width - clip_w))
        clip = strip.crop((offset, 0, offset + clip_w, height)).copy()
        fade = Image.new("L", (clip.width, 1))
        fade.putdata([min(255, int(255 * min(1.0, x / (36 * s), (clip.width - x) / (36 * s))))
                      for x in range(clip.width)])
        clip.putalpha(ImageChops.multiply(clip.getchannel("A"), fade.resize(clip.size)))
        img.paste(clip, (x0, y0), clip.getchannel("A"))
        pulse = 0.55 + 0.45 * math.sin(t * 2.0)
        draw.ellipse((x0 + 12 * s, y0 + (y1 - y0) / 2 - 2.4 * s,
                      x0 + 12 * s + 4.8 * s, y0 + (y1 - y0) / 2 + 2.4 * s),
                     fill=(242, 198, 210, int(255 * pulse)))


_SCENES = {}


def render(width, height, t, sample, paused=False):
    """Render one frame, reusing the cached chrome for this window size."""
    key = (int(width), int(height))
    scene = _SCENES.get(key)
    if scene is None:
        scene = OrbitScene(width, height)
        _SCENES[key] = scene
    return scene.frame(t, sample, paused)


def clear_cache():
    _SCENES.clear()
