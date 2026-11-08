#!/usr/bin/env python3
"""SMTH-Cursor: hollow triangle pointer, violet->cyan outline with a dark edge. Writes Xcursor files."""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw
OUT = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__)); import json
P = json.load(open(os.path.join(HERE, "palette.json"))); hx = lambda h: tuple(int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)); A, B = hx(P["A"]), hx(P["B"])
def render(size):
    S = 8; N = size * S; s = size / 32.0
    pts = [(5 * s * S, 3 * s * S), (5 * s * S, 28 * s * S), (22 * s * S, 21 * s * S)]; loop = pts + [pts[0], pts[1]]
    def mask(w):
        m = Image.new("L", (N, N), 0); ImageDraw.Draw(m).line(loop, fill=255, width=int(w * s * S), joint="curve"); return m
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0)); img.paste(B + (255,), (0, 0), mask(7.0)); img.paste(A + (255,), (0, 0), mask(3.0))   # flat B edge, flat A line, hollow inside
    return img.resize((size, size), Image.LANCZOS), (round(5 * s), round(3 * s))
def xcursor(images):
    hdr = struct.pack("<4sIII", b"Xcur", 16, 0x10000, len(images)); off = 16 + 12 * len(images); toc = chunks = b""
    for size, w, h, xh, yh, px in images:
        chunk = struct.pack("<IIIIIIIII", 36, 0xfffd0002, size, 1, w, h, xh, yh, 50) + px
        toc += struct.pack("<III", 0xfffd0002, size, off + len(chunks)); chunks += chunk
    return hdr + toc + chunks
imgs = []
for size in (24, 32, 48, 64):
    im, (xh, yh) = render(size); a = np.array(im).astype(np.uint32); al = a[..., 3]
    r, g, b = (a[..., i] * al // 255 for i in range(3)); px = ((al << 24) | (r << 16) | (g << 8) | b).astype("<u4").tobytes()
    imgs.append((size, size, size, xh, yh, px))
data = xcursor(imgs); d = os.path.join(OUT, "usr/share/icons/SMTH-Cursor/cursors"); os.makedirs(d, exist_ok=True)
for name in ("left_ptr", "default", "arrow", "top_left_arrow", "left_ptr_watch", "pointer", "hand1", "hand2", "context-menu", "dnd-ask"):
    open(os.path.join(d, name), "wb").write(data)
open(os.path.join(OUT, "usr/share/icons/SMTH-Cursor/index.theme"), "w").write("[Icon Theme]\nName=SMTH-Cursor\nComment=Hollow triangle pointer\nInherits=Adwaita\n")
os.makedirs(os.path.join(OUT, "usr/share/icons/default"), exist_ok=True)
open(os.path.join(OUT, "usr/share/icons/default/index.theme"), "w").write("[Icon Theme]\nInherits=SMTH-Cursor\n")
im, _ = render(96); bg = Image.new("RGBA", (160, 160), (10, 10, 22, 255)); bg.alpha_composite(im, (30, 30)); bg.save("/tmp/cursor_preview.png"); print("cursor ok", len(data))
