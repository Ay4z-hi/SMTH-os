#!/usr/bin/env python3
"""SMTH art with exactly two flat colours (tools/palette.json) on black. No gradients, glows or shaded edges."""
import json, math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = sys.argv[1] if len(sys.argv) > 1 else "."
P = json.load(open(os.path.join(HERE, "palette.json"))); hx = lambda h: tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
A, B = hx(P["A"]), hx(P["B"])
FONT = next(f for f in ("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if os.path.exists(f))
GOLD = math.pi * (3 - math.sqrt(5))

def flat(img, pal):                                  # snap every pixel to the nearest palette colour (no in-between shades)
    a = np.asarray(img.convert("RGB")).astype(np.int32); pal = np.array(pal, dtype=np.int32); out = np.empty(a.shape, dtype=np.uint8)
    for y in range(0, a.shape[0], 128):
        d = ((a[y:y + 128, :, None, :] - pal[None, None]) ** 2).sum(-1); out[y:y + 128] = pal[d.argmin(-1)]
    return Image.fromarray(out, "RGB")

def scene(W, H, cx, cy, R, seed=3):
    rng = random.Random(seed); S = 3; k = W / 2560
    im = Image.new("RGB", (W * S, H * S), (0, 0, 0)); d = ImageDraw.Draw(im)
    def dot(x, y, r, c): d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=c)
    for _ in range(int(560 * k) + 140):
        dot(rng.random() * W, rng.random() * H, max(0.95, (0.6 + 1.6 * rng.random() ** 2) * k * 1.2), A if rng.random() < .5 else B)
    cs, sn = math.cos(-0.22), math.sin(-0.22)
    pts = sorted([(R * (1.45 + 2.95 * math.sqrt((i + 0.5) / 1500)), i * GOLD, i) for i in range(1500)], key=lambda p: math.sin(p[1]))
    for r, a, i in pts:
        x, s = r * math.cos(a), math.sin(a); y = r * s * 0.27 if s >= 0 else -math.sqrt(max(0.0, r * r - x * x)) * 0.93
        tr = (r / R - 1.45) / 2.95; b = 0.62 - 0.38 * math.cos(a)
        dot(cx + x * cs - y * sn, cy + x * sn + y * cs, max(1.0, (1.0 + 3.6 * b * (1 - 0.55 * tr)) * k * 1.45), B if i % 2 else A)
    for j in range(300):
        a = j / 300 * math.tau; dot(cx + 1.08 * R * math.cos(a), cy + 1.08 * R * math.sin(a), max(1.0, 1.7 * k * 1.1), A if j % 2 else B)
    d.ellipse([(cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S], fill=(0, 0, 0))     # event horizon
    return flat(im.resize((W, H), Image.LANCZOS), [(0, 0, 0), A, B])

def wordmark(px, text="SMTH", tracking=None):
    f = ImageFont.truetype(FONT, px); tracking = px * 0.28 if tracking is None else tracking
    ws = [f.getlength(c) for c in text]; w = int(sum(ws) + tracking * (len(text) - 1)) + 4; h = int(px * 1.4)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); x = 2
    for i, (c, wc) in enumerate(zip(text, ws)):
        m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).text((x, 0), c, font=f, fill=255)
        im.paste(A if i % 2 == 0 else B, (0, 0), m.point(lambda v: 255 if v > 127 else 0)); x += wc + tracking
    return im

def mark(size=512):
    S = 4; N = size * S; c = N / 2; R = N * 0.40; th = N * 0.085
    def mk(fn): m = Image.new("L", (N, N), 0); fn(ImageDraw.Draw(m)); return m.resize((size, size), Image.LANCZOS).point(lambda v: 255 if v > 127 else 0)
    ring = mk(lambda d: (d.ellipse([c - R, c - R, c + R, c + R], fill=255), d.ellipse([c - R + th, c - R + th, c + R - th, c + R - th], fill=0), d.pieslice([c - R - 8, c - R - 8, c + R + 8, c + R + 8], -66, -24, fill=0)))
    k = N * 0.15; a = math.radians(-45); sx, sy, sr = c + (R - th / 2) * math.cos(a), c + (R - th / 2) * math.sin(a), N * 0.05
    core = mk(lambda d: (d.ellipse([c - k, c - k, c + k, c + k], fill=255), d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=255)))
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); im.paste(A, (0, 0), ring); im.paste(B, (0, 0), core); return im

def logo_full(mark_px=240, word_px=58):
    mk, wm = mark(mark_px), wordmark(word_px); W = max(mk.width, wm.width); im = Image.new("RGBA", (W, mk.height + wm.height + 18), (0, 0, 0, 0))
    im.alpha_composite(mk, ((W - mk.width) // 2, 0)); im.alpha_composite(wm, ((W - wm.width) // 2, mk.height + 18)); return im

def sprite(color, diam):                              # spinner trail = dot SIZE, not transparency
    S = 8; im = Image.new("L", (16 * S, 16 * S), 0); o = (16 - diam) / 2 * S; ImageDraw.Draw(im).ellipse([o, o, o + diam * S, o + diam * S], fill=255)
    out = Image.new("RGBA", (16, 16), (0, 0, 0, 0)); out.paste(color, (0, 0), im.resize((16, 16), Image.LANCZOS).point(lambda v: 255 if v > 127 else 0)); return out

def boot_bg(W, H):
    im = scene(W, H, W * 0.5, H * 0.27, H * 0.055); wm = wordmark(max(18, H // 16)); im.paste(wm, ((W - wm.width) // 2, int(H * 0.45)), wm); return im

bg = os.path.join(OUT, "usr/share/backgrounds/smth"); pl = os.path.join(OUT, "usr/share/plymouth/themes/smth"); sh = os.path.join(OUT, "usr/share/smth"); bt = os.path.join(sh, "boot")
for p in (bg, pl, sh, bt): os.makedirs(p, exist_ok=True)
W, H = 2560, 1440; wm = wordmark(46)
w = scene(W, H, W * 0.66, H * 0.50, H * 0.105); w.paste(wm, (110, H - 170), wm); w.save(os.path.join(bg, "wallpaper.png"), optimize=True)
l = scene(W, H, W * 0.5, H * 0.36, H * 0.07); l.paste(wm, ((W - wm.width) // 2, H - 190), wm); l.save(os.path.join(bg, "lock.png"), optimize=True)
mark(256).save(os.path.join(sh, "mark.png")); logo_full().save(os.path.join(sh, "logo.png")); logo_full().save(os.path.join(pl, "logo.png"))
for i, dm in enumerate((14, 11, 8, 6, 4)): sprite(A, dm).save(os.path.join(pl, f"dot-c{i}.png")); sprite(B, dm).save(os.path.join(pl, f"dot-v{i}.png"))
boot_bg(1280, 720).save(os.path.join(bt, "background.png")); boot_bg(640, 480).save(os.path.join(bt, "splash.png")); print("assets ok", P)
