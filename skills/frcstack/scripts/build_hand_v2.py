"""
build_hand_v2.py -- build, verify and export the v2 anatomical hand + forearm.

Usage:  python build_hand_v2.py OUT_DIR [--pose open|partial|closed] [--no-actuators]

Writes OUT_DIR/robotic-hand-v2-xarm.step (named, coloured assembly) and
OUT_DIR/robotic-hand-v2-report.json (validity, interference, mass estimate).
PROPOSED DESIGN.  Not fabrication-ready.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import hand_kinematics as hk
import hand_v2_geometry as g

DENSITY = {"pla": 1.24e-3, "tpu": 1.21e-3, "cf": 1.55e-3}   # g / mm^3 (solid)
INFILL = 0.45                                                 # printed-part effective fill
ACTUATOR_G = 18.0                                             # vendor XL330 mass
# Expected contacts: pinned or bolted joints sharing a face/pin.  Allowed overlap volume 0.
INTENDED_TOUCH = {("palm", "_carrier"), ("_carrier", "_proximal"), ("_proximal", "_middle"),
                  ("_middle", "_distal"), ("_distal", "_fin_ray_pad")}


def _material(name):
    if "fin_ray" in name:
        return "tpu", (0.12, 0.45, 0.95, 1.0)
    if "cf_tube" in name:
        return "cf", (0.1, 0.1, 0.1, 1.0)
    if name.startswith("actuator_"):
        return "vendor", (0.2, 0.2, 0.22, 1.0)
    if name.startswith("spool_"):
        return "pla", (0.85, 0.55, 0.1, 1.0)
    if name.startswith("cover_"):
        return "pla", (0.95, 0.95, 0.95, 0.35)
    return "pla", (0.93, 0.93, 0.9, 1.0)


def interference(parts, tol=1e-3):
    """Pairwise boolean-common volume with a bounding-box prefilter."""
    names = list(parts)
    boxes = {n: parts[n].BoundingBox() for n in names}
    hits = []
    for a, b in itertools.combinations(names, 2):
        A, B = boxes[a], boxes[b]
        if (A.xmax < B.xmin or B.xmax < A.xmin or A.ymax < B.ymin or B.ymax < A.ymin
                or A.zmax < B.zmin or B.zmax < A.zmin):
            continue
        v = parts[a].intersect(parts[b]).Volume()
        if v > tol:
            hits.append({"a": a, "b": b, "volume_mm3": round(v, 3)})
    return hits


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--pose", default="open", choices=("open", "partial", "closed"))
    ap.add_argument("--no-actuators", action="store_true")
    ap.add_argument("--skip-interference", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    import cadquery as cq
    t0 = time.time()
    q = hk.pose(a.pose)
    parts = {**g.build_hand(q), **g.build_forearm(include_actuators=not a.no_actuators)}
    bad = [n for n, s in parts.items() if not s.isValid()]
    if bad:
        raise SystemExit(f"invalid shapes: {bad}")

    hits = [] if a.skip_interference else interference(parts)

    mass, counts = 0.0, {}
    for n, s in parts.items():
        m, _ = _material(n)
        counts[m] = counts.get(m, 0) + 1
        if m == "vendor":
            continue
        fill = 1.0 if m == "cf" else INFILL
        mass += s.Volume() * DENSITY[m] * fill
    n_act = counts.get("vendor", 0)
    mass += n_act * ACTUATOR_G if n_act else 20 * ACTUATOR_G

    asm = cq.Assembly(name="robotic_hand_v2_xarm")
    for n, s in parts.items():
        _, rgba = _material(n)
        asm.add(s, name=n, color=cq.Color(*rgba))
    step = out / "robotic-hand-v2-xarm.step"
    asm.save(str(step), exportType="STEP")

    bb = cq.Compound.makeCompound(list(parts.values())).BoundingBox()
    report = {
        "status": "PROPOSED - not fabrication-ready, not FEA-verified, not prototype-tested",
        "pose": a.pose, "hand": "right",
        "parts": len(parts), "counts_by_material": counts,
        "all_valid": True,
        "interference": hits, "interference_checked": not a.skip_interference,
        "overall_bbox_mm": [round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)],
        "estimated_mass_g": round(mass, 0),
        "xarm_mount": "DIN ISO 9409-1-A50 subset: 4x M6 clearance on PCD 50, phi 5 dowel; verify on flange",
        "spool_radii_mm": {k: round(v, 2) for k, v in g.spool_radii().items()},
        "build_seconds": round(time.time() - t0, 1),
        "step": str(step), "step_bytes": step.stat().st_size,
    }
    (out / "robotic-hand-v2-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("parts", "overall_bbox_mm", "estimated_mass_g",
                                              "build_seconds", "step_bytes")}))
    print("interference:", json.dumps(hits, indent=1))
    return 0 if not hits else 2


if __name__ == "__main__":
    sys.exit(main())
