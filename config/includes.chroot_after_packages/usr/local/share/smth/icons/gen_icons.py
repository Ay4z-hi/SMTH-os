#!/usr/bin/env python3
"""SMTH icon theme: one rounded glass tile per app.

The tile is a squircle with a maroon-to-obsidian gradient, a top sheen and a
blush hairline; the glyph stays a single-colour line drawing so the set reads
as one family at 18, 24 and 32 pixels. Palette comes from palette.json.
"""
import json, os, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "SMTH"
try: P = json.load(open("/usr/local/lib/smth/palette.json"))
except Exception: P = {"A": "#701b35", "B": "#f2c6d2"}
Pth = lambda d: f'<path d="{d}"/>'; Ci = lambda x, y, r: f'<circle cx="{x}" cy="{y}" r="{r}"/>'; Re = lambda x, y, w, h, rx=0: f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"/>'
ICONS = {
 "smth-camera": [Pth("M3 8h4l2-3h6l2 3h4v12H3z"), Ci(12, 13.5, 3.8)], "smth-gallery": [Re(3, 4, 18, 16, 3), Pth("M3 16l5-5 4 4 3-3 6 6"), Ci(16, 9, 1.4)],
 "smth-clock": [Ci(12, 12, 9), Pth("M12 7v5l3.5 2")], "smth-paint": [Pth("M4 20l1.2-4.6L16 4.6a2 2 0 013 0l.4.4a2 2 0 010 3L8.6 18.8z"), Pth("M14 7l3 3")],
 "smth-settings": [Pth("M4 7h9M17 7h3M4 17h3M11 17h9"), Ci(15, 7, 2), Ci(9, 17, 2)], "smth-files": [Pth("M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z")],
 "smth-terminal": [Re(3, 5, 18, 14, 3), Pth("M7 10l3 2-3 2M12.5 15H17")], "smth-vm": [Re(5, 5, 14, 14, 3), Re(9, 9, 6, 6, 1), Pth("M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3")],
 "smth-corelink": [Ci(7, 12, 3), Ci(17, 12, 3), Pth("M10 12h4")], "smth-home": [Pth("M4 11l8-7 8 7v9H4z")],
 "smth-browser": [Ci(12, 12, 9), Pth("M3 12h18"), '<ellipse cx="12" cy="12" rx="4" ry="9"/>'], "smth-notes": [Re(5, 3, 14, 18, 3), Pth("M9 8h6M9 12h6M9 16h3")],
 "smth-calc": [Re(5, 3, 14, 18, 3), Re(8, 6, 8, 3, 1), Pth("M9 13h.01M12 13h.01M15 13h.01M9 17h.01M12 17h.01M15 17h.01")],
 "smth-store": [Pth("M5 8h14l-1 12H6z"), Pth("M9 8V6a3 3 0 016 0v2")], "smth-player": [Ci(12, 12, 9), Pth("M10 8.5v7l6-3.5z")],
 "smth-orbit": [Ci(12, 12, 8.6), Ci(12, 12, 2.6), Ci(18.6, 5.4, 1.7), Pth("M4.2 12h2.4M17.4 12h2.4M12 3.4v2.4M12 18.2v2.4")],
}
TPL = ('<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
       '<defs>'
       '<linearGradient id="glass" x1="0" y1="0" x2="0.38" y2="1">'
       '<stop offset="0" stop-color="#331826"/><stop offset="0.55" stop-color="#150f17"/><stop offset="1" stop-color="#08070a"/>'
       '</linearGradient>'
       '<linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1">'
       '<stop offset="0" stop-color="#ffffff" stop-opacity="0.15"/><stop offset="0.58" stop-color="#ffffff" stop-opacity="0"/>'
       '</linearGradient>'
       '</defs>'
       '<rect x="1.25" y="1.25" width="45.5" height="45.5" rx="15" fill="url(#glass)" stroke="%s" stroke-opacity="0.34" stroke-width="1.4"/>'
       '<rect x="2.9" y="2.9" width="42.2" height="42.2" rx="13.6" fill="url(#sheen)"/>'
       '<g transform="translate(12 12)" fill="none" stroke="%s" stroke-opacity="0.94" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round">{}</g>'
       '</svg>\n') % (P["B"], P["B"])
d = os.path.join(OUT, "scalable", "apps"); os.makedirs(d, exist_ok=True)
for n, parts in ICONS.items(): open(os.path.join(d, n + ".svg"), "w").write(TPL.format("".join(parts)))
open(os.path.join(OUT, "index.theme"), "w").write("[Icon Theme]\nName=SMTH\nComment=SMTH icons\nInherits=Adwaita,hicolor\nDirectories=scalable/apps\n\n[scalable/apps]\nSize=48\nMinSize=16\nMaxSize=512\nType=Scalable\nContext=Applications\n")
print("icons", len(ICONS))
