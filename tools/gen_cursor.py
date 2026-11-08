#!/usr/bin/env python3
"""SMTH-Cursor: hollow triangle pointer, violet->cyan outline with a dark edge. Writes Xcursor files."""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw
OUT = sys.argv[1]
VI, CY = np.array((124, 92, 255)), np.array((25, 230, 208))
def render(size):
    S = 8; N = size * S; s = size / 32.0
    pts = [(5 * s * S, 3 * s * S), (5 * s * S, 28 * s * S), (22 * s * S, 21 * s * S)]; loop = pts + [pts[0], pts[1]]
    def mask(w):
        m = Image.new("L", (N, N), 0); ImageDraw.Draw(m).line(loop, fill=255, width=int(w * s * S), joint="curve"); return m
    outer, inner = mask(7.5), mask(3.6)
    t = np.linspace(0, 1, N)[:, None, None].repeat(N, 1)
    grad = Image.fromarray((VI * (1 - t) + CY * t).astype("uint8"), "RGB")
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0)); img.paste((6, 6, 16, 235), (0, 0), outer); img.paste(grad, (0, 0), inner)
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
