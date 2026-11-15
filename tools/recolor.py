#!/usr/bin/env python3
"""python3 tools/recolor.py "#NEWA" "#NEWB"  -> swaps the two palette colours in every text file and regenerates the art."""
import json, os, re, subprocess, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); pj = os.path.join(root, "tools", "palette.json"); old = json.load(open(pj))
core = lambda h: h.lstrip("#").lower(); pairs = {core(old["A"]): core(sys.argv[1]), core(old["B"]): core(sys.argv[2])}
for d, _, fs in os.walk(root):
    for f in fs:
        p = os.path.join(d, f)
        if p.endswith((".png", ".zip", ".pf2")): continue
        try: s = open(p, encoding="utf-8").read()
        except Exception: continue
        t = s
        for o, n in pairs.items(): t = re.sub(o, "@@" + n + "@@", t, flags=re.I)
        t = re.sub(r"@@([0-9a-f]{6})@@", r"\1", t)
        if t != s: open(p, "w", encoding="utf-8").write(t)
inc = os.path.join(root, "config/includes.chroot_after_packages")
for g in ("gen_assets.py", "gen_cursor.py"): subprocess.run([sys.executable, os.path.join(root, "tools", g), inc], check=True)
print("recoloured to", sys.argv[1], sys.argv[2])
