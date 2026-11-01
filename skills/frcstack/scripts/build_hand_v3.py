"""
build_hand_v3.py -- build, verify and export the v3 in-palm-actuator right hand.

Usage:  python build_hand_v3.py OUT_DIR [--pose open|grasp] [--grasp-json PATH] [--skip-interference]

Writes OUT_DIR/robotic-hand-v3-<pose>.step (named, coloured assembly) and
OUT_DIR/robotic-hand-v3-<pose>-report.json.   PROPOSED DESIGN, not fabrication-ready.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

import hand_kinematics as hk
import hand_v3_geometry as g
import hand_v3_layout as lay

DENSITY = {"pla": 1.24e-3, "tpu": 1.21e-3, "pcb": 1.85e-3}     # g / mm^3
INFILL = 0.5
MOTOR_G = 11.0          # vendor: micro metal gearmotor with encoder, 11 g (pololu.com)
# Parts that are SUPPOSED to touch / share volume (bolted, pinned, nested envelopes)
ALLOWED = [("motor_", "plug_"), ("motor_", "drum_"), ("motor_", "motor_cage"),
           ("tendon_", "drum_"), ("tendon_", "motor_cage"), ("tendon_", "palm_shell"),
           ("pcb_", "pcb_"), ("pcb_standoffs", "palm_shell"), ("pcb_standoffs", "motor_cage"),
           ("knuckle_bosses", "palm_shell"), ("motor_cage", "palm_shell"),
           ("wrist_adapter", "palm_shell"), ("_fin_ray_pad", "_distal")]


def _allowed(a, b):
    for p, q in ALLOWED:
        if (a.startswith(p) or p in a) and (b.startswith(q) or q in b):
            return True
        if (b.startswith(p) or p in b) and (a.startswith(q) or q in a):
            return True
    return False


def _material(n):
    if "fin_ray" in n:
        return "tpu", (0.12, 0.45, 0.95, 1.0)
    if n.startswith("motor_") and n != "motor_cage":
        return "vendor", (0.55, 0.57, 0.6, 1.0)
    if n.startswith("plug_"):
        return "vendor", (0.95, 0.95, 0.9, 1.0)
    if n.startswith("drum_"):
        return "pla", (0.85, 0.55, 0.1, 1.0)
    if n.startswith("tendon_"):
        return "line", (0.95, 0.2, 0.2, 1.0)
    if n == "pcb_controller_board":
        return "pcb", (0.05, 0.45, 0.15, 1.0)
    if n.startswith("pcb_component"):
        return "envelope", (0.2, 0.75, 0.3, 0.35)
    if n.startswith("palm_shell"):
        return "pla", (0.93, 0.86, 0.80, 1.0)
    return "pla", (0.93, 0.93, 0.9, 1.0)


def interference(parts, tol=1e-3):
    names = list(parts)
    boxes = {n: parts[n].BoundingBox() for n in names}
    hits = []
    for a, b in itertools.combinations(names, 2):
        if _allowed(a, b):
            continue
        A, B = boxes[a], boxes[b]
        if (A.xmax < B.xmin or B.xmax < A.xmin or A.ymax < B.ymin or B.ymax < A.ymin
                or A.zmax < B.zmin or B.zmax < A.zmin):
            continue
        v = parts[a].intersect(parts[b]).Volume()
        if v > tol:
            hits.append({"a": a, "b": b, "volume_mm3": round(v, 3)})
    return hits


def pose_q(name, grasp_json):
    if name == "open":
        return hk.pose("open"), None
    data = json.loads(Path(grasp_json).read_text())["best"]
    return dict(zip(hk._JOINT_ORDER, data["q"])), data


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--pose", default="open", choices=("open", "grasp"))
    ap.add_argument("--grasp-json")
    ap.add_argument("--skip-interference", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    import cadquery as cq
    t0 = time.time()
    q, gdata = pose_q(a.pose, a.grasp_json)
    parts = g.build_hand_v3(q)
    if gdata is not None:
        import hand_v3_grasp as gr
        c = gr.ball_center(gdata["cx"], gdata["cy"])
        parts["ball_reference_150mm"] = cq.Solid.makeSphere(gr.BALL_R, cq.Vector(*c))
    bad = [n for n, s in parts.items() if not s.isValid()]
    if bad:
        raise SystemExit(f"invalid shapes: {bad}")
    print(f"built {len(parts)} parts in {time.time() - t0:.0f}s", flush=True)

    hits = [] if a.skip_interference else interference(
        {k: v for k, v in parts.items() if k != "ball_reference_150mm"})
    print(f"interference checked: {len(hits)} hits", flush=True)

    mass = 0.0
    counts = {}
    for n, s in parts.items():
        m, _ = _material(n)
        counts[m] = counts.get(m, 0) + 1
        if m in ("pla", "tpu"):
            mass += s.Volume() * DENSITY[m] * INFILL
        elif m == "pcb":
            mass += s.Volume() * DENSITY["pcb"]
    mass += MOTOR_G * 20 + 6.0          # motors + placeholder component mass

    asm = cq.Assembly(name="robotic_hand_v3_in_palm")
    for n, s in parts.items():
        _, rgba = _material(n)
        if n == "ball_reference_150mm":
            rgba = (1.0, 0.85, 0.1, 0.35)
        asm.add(s, name=n, color=cq.Color(*rgba))
    step = out / f"robotic-hand-v3-{a.pose}.step"
    asm.export(str(step))

    allp = [v for k, v in parts.items() if k != "ball_reference_150mm"]
    bb = cq.Compound.makeCompound(allp).BoundingBox()
    palm = cq.Compound.makeCompound([parts["palm_shell_palmar"], parts["palm_shell_dorsal"]]).BoundingBox()
    report = {
        "status": "PROPOSED - not fabrication-ready, not FEA-verified, not prototype-tested",
        "pose": a.pose, "hand": "right", "parts": len(parts), "counts_by_material": counts,
        "all_valid": True, "interference_checked": not a.skip_interference, "interference": hits,
        "overall_bbox_mm": [round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)],
        "palm_bbox_mm": [round(palm.xlen, 1), round(palm.ylen, 1), round(palm.zlen, 1)],
        "estimated_mass_g": round(mass),
        "actuators_in_palm": 20,
        "electronics_bay": lay.electronics_budget(),
        "power": lay.power_budget(),
        "grasp": gdata and {k: v for k, v in gdata.items() if k != "q"},
        "build_seconds": round(time.time() - t0, 1),
        "step": str(step), "step_bytes": step.stat().st_size,
    }
    (out / f"robotic-hand-v3-{a.pose}-report.json").write_text(json.dumps(report, indent=2, default=float))
    print(json.dumps({k: report[k] for k in ("parts", "overall_bbox_mm", "palm_bbox_mm",
                                              "estimated_mass_g", "build_seconds", "step_bytes")}))
    print("interference:", json.dumps(hits[:30], indent=1))
    return 0 if not hits else 2


if __name__ == "__main__":
    sys.exit(main())
