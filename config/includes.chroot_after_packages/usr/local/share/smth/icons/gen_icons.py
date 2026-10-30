#!/usr/bin/env python3
"""Generate the SMTH icon theme: 24-grid, 1.5px white strokes, square caps, mitered joins."""
import os, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "SMTH"
R = lambda x, y, w, h: f'<rect x="{x}" y="{y}" width="{w}" height="{h}"/>'
C = lambda x, y, r: f'<circle cx="{x}" cy="{y}" r="{r}"/>'
P = lambda d: f'<path d="{d}"/>'
ICONS = {
 "smth-camera":   [P("M3 7h4l2-3h6l2 3h4v13H3z"), C(12, 13, 4)],
 "smth-gallery":  [R(3, 4, 18, 16), P("M3 16l6-6 5 5 3-3 4 4"), C(16.5, 8.5, 1.5)],
 "smth-clock":    [C(12, 12, 9), P("M12 7v5l3 3")],
 "smth-paint":    [P("M4 20l1-5L16 4l4 4L9 19z"), P("M14 6l4 4")],
 "smth-settings": [P("M4 7h10M18 7h2M4 17h2M10 17h10"), C(16, 7, 2), C(8, 17, 2)],
 "smth-files":    [P("M3 6h7l2 2h9v12H3z")],
 "smth-terminal": [R(3, 5, 18, 14), P("M7 10l3 2-3 2M12 15h5")],
 "smth-vm":       [R(4, 4, 16, 16), R(9, 9, 6, 6), P("M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2")],
 "smth-corelink": [C(7, 12, 3), C(17, 12, 3), P("M10 12h4")],
 "smth-home":     [P("M4 11l8-7 8 7v9H4z")],
}
TPL = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
       'stroke="#FFFFFF" stroke-width="1.5" stroke-linecap="square" stroke-linejoin="miter">{}</svg>\n')
d = os.path.join(OUT, "scalable", "apps"); os.makedirs(d, exist_ok=True)
for name, parts in ICONS.items():
    open(os.path.join(d, name + ".svg"), "w").write(TPL.format("".join(parts)))
open(os.path.join(OUT, "index.theme"), "w").write(
"""[Icon Theme]
Name=SMTH
Comment=Dot Matrix Minimalist icons
Inherits=Adwaita,hicolor
Directories=scalable/apps

[scalable/apps]
Size=24
MinSize=16
MaxSize=512
Type=Scalable
Context=Applications
""")
print(f"wrote {len(ICONS)} icons to {OUT}")
