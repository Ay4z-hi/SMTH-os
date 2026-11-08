"""SMTH dot drawing helpers (cairo). Ion palette: violet -> cyan."""
import json, math, os
GLYPHS = {
 " ": (0,0,0,0,0,0,0), "0": (14,17,19,21,25,17,14), "1": (4,12,4,4,4,4,14), "2": (14,17,1,2,4,8,31),
 "3": (30,1,1,14,1,1,30), "4": (2,6,10,18,31,2,2), "5": (31,16,30,1,1,17,14), "6": (6,8,16,30,17,17,14),
 "7": (31,1,2,4,8,8,8), "8": (14,17,17,14,17,17,14), "9": (14,17,17,15,1,2,12), ":": (0,4,4,0,4,4,0),
 ".": (0,0,0,0,0,12,12), "-": (0,0,0,31,0,0,0), "/": (1,1,2,4,8,16,16), "%": (24,25,2,4,8,19,3),
 "+": (0,4,4,31,4,4,0), "*": (0,21,14,31,14,21,0), "(": (2,4,8,8,8,4,2), ")": (8,4,2,2,2,4,8), "=": (0,0,31,0,31,0,0),
 "A": (14,17,17,31,17,17,17), "B": (30,17,17,30,17,17,30), "C": (14,17,16,16,16,17,14), "D": (30,17,17,17,17,17,30),
 "E": (31,16,16,30,16,16,31), "F": (31,16,16,30,16,16,16), "G": (14,17,16,23,17,17,15), "H": (17,17,17,31,17,17,17),
 "I": (14,4,4,4,4,4,14), "J": (7,2,2,2,2,18,12), "K": (17,18,20,24,20,18,17), "L": (16,16,16,16,16,16,31),
 "M": (17,27,21,21,17,17,17), "N": (17,25,21,19,17,17,17), "O": (14,17,17,17,17,17,14), "P": (30,17,17,30,16,16,16),
 "Q": (14,17,17,17,21,18,13), "R": (30,17,17,30,20,18,17), "S": (15,16,16,14,1,1,30), "T": (31,4,4,4,4,4,4),
 "U": (17,17,17,17,17,17,14), "V": (17,17,17,17,17,10,4), "W": (17,17,17,21,21,27,17), "X": (17,17,10,4,10,17,17),
 "Y": (17,17,10,4,4,4,4), "Z": (31,1,2,4,8,16,31),
}
def _rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
try:
    _P = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "palette.json"))); ACCENT, VIOLET = _rgb(_P["A"]), _rgb(_P["B"])
except Exception:
    ACCENT, VIOLET = (1.0, 0.478, 0.0), (0.184, 0.42, 1.0)
RED = ACCENT                     # old name kept so older apps still work
TAU = math.tau

def lerp(a, b, t): return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
def text_width(text, dot): return (len(text) * 6 - 1) * dot

def draw_text(cr, text, x, y, dot, on=None, off=None):
    for i, ch in enumerate(text.upper()):
        rows = GLYPHS.get(ch, GLYPHS[" "])
        for r in range(7):
            for c in range(5):
                lit = (rows[r] >> (4 - c)) & 1
                col = ((ACCENT if (i * 6 + c) % 2 == 0 else VIOLET) if on is None else on) if lit else off
                if col is None: continue
                cr.set_source_rgb(*col); cr.arc(x + (i * 6 + c) * dot + dot / 2, y + r * dot + dot / 2, dot * 0.38, 0, TAU); cr.fill()

def dot_ring(cr, cx, cy, radius, frac, n=30, dot=3.4, phase=0.0, neon=False):
    lit = round(max(0.0, min(1.0, frac)) * n)
    for k in range(n):
        a = -math.pi / 2 + TAU * k / n + phase; x, y = cx + radius * math.cos(a), cy + radius * math.sin(a)
        if k < lit: cr.set_source_rgb(*(ACCENT if k % 2 == 0 else VIOLET)); r = dot
        else: cr.set_source_rgb(*VIOLET); r = dot * 0.35          # unlit = tiny dot, still only two colours
        cr.arc(x, y, r, 0, TAU); cr.fill()

def dot_label(text, dot=3.0, on=None, off=None):
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    a = Gtk.DrawingArea(); a.set_content_width(int(text_width(text, dot)) + 2); a.set_content_height(int(dot * 7) + 2)
    a.set_draw_func(lambda _a, cr, w, h: draw_text(cr, text, 1, 1, dot, on, off)); return a
