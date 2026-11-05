"""Dump OLLIE part bounding boxes + link masses/COM (design input).  Usage: _dump_v1.py OUT_JSON"""
import json
import sys
import time

import ollie_geometry as OG
import humanoid_layout as L

t = time.time()
P = OG.parts()
mass, comz = OG.link_inertia(P)
out = {"parts": {}, "links": {}}
for n, p in sorted(P.items()):
    bb = p.shape.BoundingBox()
    out["parts"][n] = [p.link, p.material, round(OG.mass_g(n, p), 1),
                       [round(v, 1) for v in (bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zmin, bb.zmax)]]
for ln in sorted(mass):
    out["links"][ln] = [round(mass[ln], 1), [round(float(v), 1) for v in comz[ln]]]
tot = sum(mass.values())
out["total_g"] = round(tot, 1)
out["bracket_R"] = {jn: L.bracket_params(jn)[1:] for jn in L.JOINTS if L.JOINTS[jn]["mount"] == "u"}
open(sys.argv[1], "w").write(json.dumps(out, indent=0))
print("parts", len(P), "total", round(tot), "s", round(time.time() - t))
for n in sorted(P):
    if n.endswith("_L") or "_" not in n[-2:]:
        b = out["parts"][n]
        print(f"{n:28s} {b[0]:14s} {b[1]:7s} {b[2]:7.1f}  " + " ".join(f"{v:7.1f}" for v in b[3]))
print(out["bracket_R"])
