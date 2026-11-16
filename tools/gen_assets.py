#!/usr/bin/env python3
"""SMTH art with exactly two flat colours (tools/palette.json) on black. No gradients, glows or shaded edges."""
import glob, json, math, os, random, shutil, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = sys.argv[1] if len(sys.argv) > 1 else "."
P = json.load(open(os.path.join(HERE, "palette.json"))); hx = lambda h: tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
for _k in ("A", "B", "AHIAN_A", "AHIAN_B"):
    if _k not in P: raise SystemExit(f"palette.json is missing {_k}")
A, B, AA, AB = hx(P["A"]), hx(P["B"]), hx(P["AHIAN_A"]), hx(P["AHIAN_B"])
# Prefer the fonts bundled in the image so generated artwork is reproducible
# without network access and matches the shipped typography.
FONT = next(iter(
    [p for p in (os.path.join(OUT, "usr/share/fonts/truetype/smth/Doto.ttf"),
                 "/usr/share/fonts/truetype/smth/Doto.ttf",
                 "/usr/share/fonts/truetype/inter/InterVariable.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if os.path.exists(p)]
    + sorted(glob.glob("/usr/share/fonts/truetype/*/*.ttf"))), None)

def font(px):
    """Bundled Doto when present, else any usable local font, else PIL's default."""
    if FONT:
        try: return ImageFont.truetype(FONT, px)
        except OSError: pass
    try: return ImageFont.load_default(size=px)
    except TypeError: return ImageFont.load_default()
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
    f = font(px); tracking = px * 0.28 if tracking is None else tracking
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


def wallpaper(kind, W, H):
    """Flat black/A/B wallpaper family. No gradients, alpha, or off-palette pixels."""
    im = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(im)
    rng = random.Random(71)
    def dot(x, y, r, c):
        r = max(1, int(r)); x, y = int(x), int(y)
        d.ellipse((x-r, y-r, x+r, y+r), fill=c)
    def ring(cx, cy, rx, ry, step=2, phase=0):
        for n in range(0, 360, step):
            q = math.radians(n); dot(cx + rx*math.cos(q), cy + ry*math.sin(q), 2, A if ((n//step)+phase)%2 else B)
    if kind == "black-hole":
        im = scene(W, H, W*.66, H*.50, H*.105)
    elif kind == "spiral-galaxy":
        for _ in range(700): dot(rng.randrange(W), rng.randrange(H), 1, A if rng.random()<.5 else B)
        cx, cy = W*.5, H*.5
        for i in range(3200):
            arm = i % 4; r = 8 + (i/3200)**.78 * H*.43
            q = r*.018 + arm*math.tau/4 + rng.uniform(-.10,.10)
            dot(cx+r*math.cos(q), cy+r*.55*math.sin(q), 1+(i%5==0), A if i%2 else B)
        d.ellipse((cx-H*.055,cy-H*.055,cx+H*.055,cy+H*.055), fill=(0,0,0))
    elif kind == "orbit-rings":
        for i in range(12): ring(W*.5,H*.5,H*(.10+i*.055),H*(.035+i*.020),2,i)
        for i in range(260): dot(rng.randrange(W),rng.randrange(H),1,A if i%2 else B)
    elif kind == "dot-topography":
        for y in range(30,H,18):
            for x in range(30,W,18):
                v=math.sin(x*.006)+math.cos(y*.009)+math.sin((x+y)*.003)
                if v > .25: dot(x,y,1+(int(abs(v)*3)), A if (x//18+y//18)%2 else B)
    elif kind == "horizon-grid":
        cy=H*.62
        for y in range(int(cy),H,3):
            d.line((0,y,W,y), fill=A if (y//3)%2 else B, width=1)
        for x in range(-W,W*2,70):
            d.line((W*.5,cy,x,H), fill=A if (x//70)%2 else B, width=1)
        ring(W*.5,cy,H*.11,H*.11,2)
    elif kind == "eclipse":
        cx,cy=W*.5,H*.44; rr=H*.20
        ring(cx,cy,rr*1.25,rr*1.25,1)
        d.ellipse((cx-rr,cy-rr,cx+rr,cy+rr),fill=(0,0,0))
        for i in range(220): dot(rng.randrange(W),rng.randrange(H),1,A if i%2 else B)
    elif kind == "double-helix":
        for y in range(0,H,3):
            q=y/H*math.tau*3
            x1=W*.5+W*.20*math.sin(q); x2=W*.5-W*.20*math.sin(q)
            dot(x1,y,3,A); dot(x2,y,3,B)
            if y%18==0: d.line((int(x1),y,int(x2),y),fill=A if (y//18)%2 else B,width=1)
    else:
        pass
    wm=wordmark(46)
    im.paste(wm,(110,H-170),wm)
    return flat(im,[(0,0,0),A,B])

def ahian_wallpaper(W, H):
    """AHIAN mode wallpaper: purple/teal dot field on black. No gradients."""
    S = 2; im = Image.new("RGB", (W * S, H * S), (0, 0, 0)); d = ImageDraw.Draw(im)
    cx, cy = W * 0.34 * S, H * 0.62 * S
    step = 26 * S
    for y in range(0, H * S, step):
        for x in range(0, W * S, step):
            dist = math.hypot(x - cx, y - cy) / (H * S)
            v = math.sin(dist * 14.0) * 0.5 + 0.5
            v *= max(0.0, 1.0 - dist * 0.55)
            if v < 0.16: continue
            r = (1.4 + 3.2 * v) * S / 1.6
            col = AB if (int(x / step) + int(y / step)) % 2 == 0 else AA
            d.ellipse((x - r, y - r, x + r, y + r), fill=col)
    # A teal horizon band and a purple arc keep the composition intentional.
    band = int(H * 0.68) * S
    for i in range(0, 5):
        d.line((0, band + i * 3 * S, W * S, band + i * 3 * S), fill=AB, width=S)
    arc_r = H * 0.30 * S
    for k in range(0, 2000):
        q = math.pi * 1.05 + k / 2000 * math.pi * 0.9
        px, py = cx + arc_r * math.cos(q), cy + arc_r * math.sin(q)
        d.ellipse((px - 4 * S, py - 4 * S, px + 4 * S, py + 4 * S), fill=AA if k % 3 else AB)
    wm = wordmark(46)
    im.paste(wm, (110 * S, H * S - 260 * S), wm)
    return flat(im.resize((W, H), Image.LANCZOS), [(0, 0, 0), AA, AB])

bg = os.path.join(OUT, "usr/share/backgrounds/smth"); pl = os.path.join(OUT, "usr/share/plymouth/themes/smth"); sh = os.path.join(OUT, "usr/share/smth"); bt = os.path.join(sh, "boot")
for p in (bg, pl, sh, bt): os.makedirs(p, exist_ok=True)
W, H = 2560, 1440; wm = wordmark(46)
for name in ("black-hole", "spiral-galaxy", "orbit-rings", "dot-topography", "horizon-grid", "eclipse", "double-helix", "plain-black"):
    wallpaper(name, W, H).save(os.path.join(bg, name + ".png"), optimize=True)
shutil.copyfile(os.path.join(bg, "black-hole.png"), os.path.join(bg, "wallpaper.png"))
ahian_wallpaper(W, H).save(os.path.join(bg, "ahian-teal.png"), optimize=True)
l = scene(W, H, W * 0.5, H * 0.36, H * 0.07); l.paste(wm, ((W - wm.width) // 2, H - 190), wm); l.save(os.path.join(bg, "lock.png"), optimize=True)
mark(256).save(os.path.join(sh, "mark.png")); logo_full().save(os.path.join(sh, "logo.png")); logo_full().save(os.path.join(pl, "logo.png"))
for i, dm in enumerate((14, 11, 8, 6, 4)): sprite(A, dm).save(os.path.join(pl, f"dot-c{i}.png")); sprite(B, dm).save(os.path.join(pl, f"dot-v{i}.png"))
boot_bg(1280, 720).save(os.path.join(bt, "background.png")); boot_bg(640, 480).save(os.path.join(bt, "splash.png")); print("assets ok", P)
