#!/usr/bin/env python3
"""SMTH art. Dots use exactly two colours: cyan #19E6D0 and violet #7C5CFF (alternating spiral arms)."""
import math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
FONT = next((f for f in ("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if os.path.exists(f)))
CY, VI = (25, 230, 208), (124, 92, 255)
GOLD = math.pi * (3 - math.sqrt(5))
def shade(c, k): return tuple(int(v * k) for v in c)
def lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def scene(W, H, cx, cy, R, seed=3):
    rng = random.Random(seed); S = 2
    crisp = Image.new("RGB", (W * S, H * S), (0, 0, 0)); d = ImageDraw.Draw(crisp)
    glow = Image.new("RGB", (W, H), (0, 0, 0)); g = ImageDraw.Draw(glow)
    haze = Image.new("RGB", (W, H), (0, 0, 0)); hd = ImageDraw.Draw(haze)
    for k in range(40, 0, -1):
        rr = R * (1.3 + k * 0.13); f = 1 - k / 40
        hd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(int(14 * f), int(8 * f), int(44 * f)))
    haze = haze.filter(ImageFilter.GaussianBlur(R * 0.35))
    for _ in range(int(560 * W / 2560 * 1.0) + 120):
        x, y, b = rng.random() * W, rng.random() * H, rng.random() ** 2
        r = (0.6 + 1.7 * b) * max(W / 2560, 0.5); c = shade(CY if rng.random() < 0.5 else VI, 0.35 + 0.65 * b)
        d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=c)
    tilt, rot = 0.27, -0.22; cs, sn = math.cos(rot), math.sin(rot)
    pts = sorted([(R * (1.45 + 2.95 * math.sqrt((i + 0.5) / 1500)), i * GOLD, i) for i in range(1500)], key=lambda p: math.sin(p[1]))
    for r, a, idx in pts:
        x, s = r * math.cos(a), math.sin(a)
        y = r * s * tilt if s >= 0 else -math.sqrt(max(0.0, r * r - x * x)) * 0.93
        X, Y = cx + x * cs - y * sn, cy + x * sn + y * cs
        tr = (r / R - 1.45) / 2.95; b = 0.62 - 0.38 * math.cos(a)
        rad = max(0.7, (1.0 + 3.6 * b * (1 - 0.55 * tr)) * W / 2560)
        col = CY if idx % 2 else VI                                    # two colours only
        d.ellipse([(X - rad) * S, (Y - rad) * S, (X + rad) * S, (Y + rad) * S], fill=col)
        g.ellipse([X - rad * 2.4, Y - rad * 2.4, X + rad * 2.4, Y + rad * 2.4], fill=shade(col, 0.45))
    for k in range(300):
        a = k / 300 * math.tau; X, Y = cx + 1.08 * R * math.cos(a), cy + 1.08 * R * math.sin(a); r = max(0.8, 1.7 * W / 2560)
        col = CY if k % 2 else VI
        d.ellipse([(X - r) * S, (Y - r) * S, (X + r) * S, (Y + r) * S], fill=col)
        g.ellipse([X - r * 3, Y - r * 3, X + r * 3, Y + r * 3], fill=shade(col, 0.4))
    base = crisp.resize((W, H), Image.LANCZOS)
    out = ImageChops.screen(ImageChops.add(base, haze), glow.filter(ImageFilter.GaussianBlur(max(2, 8 * W / 2560))))
    m = Image.new("L", (W * S, H * S), 0); ImageDraw.Draw(m).ellipse([(cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S], fill=255)
    out.paste((0, 0, 0), (0, 0), m.resize((W, H), Image.LANCZOS)); return out

def gradient(w, h, diag=False):
    x = np.linspace(0, 1, w)[None, :].repeat(h, 0)
    if diag: x = (x + np.linspace(0, 1, h)[:, None].repeat(w, 1)) / 2
    a = np.array(VI)[None, None, :] * (1 - x[..., None]) + np.array(CY)[None, None, :] * x[..., None]
    return Image.fromarray(a.astype("uint8"), "RGB")

def wordmark(px, text="SMTH", tracking=None):
    f = ImageFont.truetype(FONT, px); tracking = px * 0.28 if tracking is None else tracking
    ws = [f.getlength(c) for c in text]; w = int(sum(ws) + tracking * (len(text) - 1)) + 4; h = int(px * 1.4)
    mask = Image.new("L", (w, h), 0); md = ImageDraw.Draw(mask); x = 2
    for c, wc in zip(text, ws): md.text((x, 0), c, font=f, fill=255); x += wc + tracking
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); im.paste(gradient(w, h), (0, 0), mask); return im

def mark(size=512):
    S = 2; N = size * S; m = Image.new("L", (N, N), 0); d = ImageDraw.Draw(m); c = N / 2; R = N * 0.40; th = N * 0.085
    d.ellipse([c - R, c - R, c + R, c + R], fill=255); d.ellipse([c - R + th, c - R + th, c + R - th, c + R - th], fill=0)
    d.pieslice([c - R - 8, c - R - 8, c + R + 8, c + R + 8], -66, -24, fill=0)
    k = N * 0.15; d.ellipse([c - k, c - k, c + k, c + k], fill=255)
    a = math.radians(-45); sx, sy, sr = c + (R - th / 2) * math.cos(a), c + (R - th / 2) * math.sin(a), N * 0.05
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0)); im.paste(gradient(N, N, True), (0, 0), m)
    ImageDraw.Draw(im).ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=CY + (255,))
    return im.resize((size, size), Image.LANCZOS)

def logo_full(mark_px=240, word_px=58):
    mk, wm = mark(mark_px), wordmark(word_px); W = max(mk.width, wm.width); im = Image.new("RGBA", (W, mk.height + wm.height + 18), (0, 0, 0, 0))
    im.alpha_composite(mk, ((W - mk.width) // 2, 0)); im.alpha_composite(wm, ((W - wm.width) // 2, mk.height + 18)); return im

def sprite(color, a):
    S = 4; im = Image.new("RGBA", (16 * S, 16 * S), (0, 0, 0, 0)); ImageDraw.Draw(im).ellipse([S, S, 15 * S, 15 * S], fill=color + (a,))
    return im.resize((16, 16), Image.LANCZOS)

def boot_bg(W, H):
    im = scene(W, H, W * 0.5, H * 0.27, H * 0.055); wm = wordmark(max(18, H // 16)); im.paste(wm, ((W - wm.width) // 2, int(H * 0.45)), wm); return im

bg = os.path.join(OUT, "usr/share/backgrounds/smth"); pl = os.path.join(OUT, "usr/share/plymouth/themes/smth"); sh = os.path.join(OUT, "usr/share/smth"); bt = os.path.join(sh, "boot")
for p in (bg, pl, sh, bt): os.makedirs(p, exist_ok=True)
W, H = 2560, 1440; wm = wordmark(46)
wall = scene(W, H, W * 0.66, H * 0.50, H * 0.105); wall.paste(wm, (110, H - 170), wm); wall.save(os.path.join(bg, "wallpaper.png"), optimize=True)
lock = scene(W, H, W * 0.5, H * 0.36, H * 0.07); lock.paste(wm, ((W - wm.width) // 2, H - 190), wm); lock.save(os.path.join(bg, "lock.png"), optimize=True)
mark(256).save(os.path.join(sh, "mark.png")); logo_full().save(os.path.join(sh, "logo.png")); logo_full().save(os.path.join(pl, "logo.png"))
for i, a in enumerate((255, 170, 105, 62, 34)):
    sprite(CY, a).save(os.path.join(pl, f"dot-c{i}.png")); sprite(VI, a).save(os.path.join(pl, f"dot-v{i}.png"))
boot_bg(1280, 720).save(os.path.join(bt, "background.png")); boot_bg(640, 480).save(os.path.join(bt, "splash.png"))
print("assets ok")
