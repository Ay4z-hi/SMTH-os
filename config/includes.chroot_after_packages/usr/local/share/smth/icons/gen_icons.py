#!/usr/bin/env python3
"""SMTH icon theme: dark rounded tile, ion-gradient glyph (violet -> cyan)."""
import os, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "SMTH"
P = lambda d: f'<path d="{d}"/>'
C = lambda x, y, r: f'<circle cx="{x}" cy="{y}" r="{r}"/>'
R = lambda x, y, w, h, rx=0: f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"/>'
ICONS = {
 "smth-camera": [P("M3 8h4l2-3h6l2 3h4v12H3z"), C(12, 13.5, 3.8)],
 "smth-gallery": [R(3, 4, 18, 16, 3), P("M3 16l5-5 4 4 3-3 6 6"), C(16, 9, 1.4)],
 "smth-clock": [C(12, 12, 9), P("M12 7v5l3.5 2")],
 "smth-paint": [P("M4 20l1.2-4.6L16 4.6a2 2 0 013 0l.4.4a2 2 0 010 3L8.6 18.8z"), P("M14 7l3 3")],
 "smth-settings": [P("M4 7h9M17 7h3M4 17h3M11 17h9"), C(15, 7, 2), C(9, 17, 2)],
 "smth-files": [P("M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z")],
 "smth-terminal": [R(3, 5, 18, 14, 3), P("M7 10l3 2-3 2M12.5 15H17")],
 "smth-vm": [R(5, 5, 14, 14, 3), R(9, 9, 6, 6, 1), P("M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3")],
 "smth-corelink": [C(7, 12, 3), C(17, 12, 3), P("M10 12h4")],
 "smth-home": [P("M4 11l8-7 8 7v9H4z")],
 "smth-browser": [C(12, 12, 9), P("M3 12h18"), '<ellipse cx="12" cy="12" rx="4" ry="9"/>'],
 "smth-notes": [R(5, 3, 14, 18, 3), P("M9 8h6M9 12h6M9 16h3")],
 "smth-calc": [R(5, 3, 14, 18, 3), R(8, 6, 8, 3, 1), P("M9 13h.01M12 13h.01M15 13h.01M9 17h.01M12 17h.01M15 17h.01")],
 "smth-store": [P("M5 8h14l-1 12H6z"), P("M9 8V6a3 3 0 016 0v2")],
 "smth-player": [C(12, 12, 9), P("M10 8.5v7l6-3.5z")],
}
TPL = ('<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
       '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7C5CFF"/><stop offset="1" stop-color="#19E6D0"/></linearGradient></defs>'
       '<rect x="1.5" y="1.5" width="45" height="45" rx="13" fill="#0A0A14" stroke="url(#g)" stroke-width="1.5" stroke-opacity="0.8"/>'
       '<g transform="translate(12 12)" fill="none" stroke="url(#g)" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{}</g></svg>\n')
d = os.path.join(OUT, "scalable", "apps"); os.makedirs(d, exist_ok=True)
for n, parts in ICONS.items(): open(os.path.join(d, n + ".svg"), "w").write(TPL.format("".join(parts)))
open(os.path.join(OUT, "index.theme"), "w").write("[Icon Theme]\nName=SMTH\nComment=SMTH Ion icons\nInherits=Adwaita,hicolor\nDirectories=scalable/apps\n\n[scalable/apps]\nSize=48\nMinSize=16\nMaxSize=512\nType=Scalable\nContext=Applications\n")
print("icons", len(ICONS))
