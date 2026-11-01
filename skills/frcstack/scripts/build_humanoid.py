"""
build_humanoid.py -- build, verify and export the $700 bus-servo humanoid.

Usage:  python build_humanoid.py OUT_DIR [--no-vendor] [--skip-interference]

Writes OUT_DIR/humanoid-700-<pose>.step (named, coloured assembly; ST3215s are the vendor model),
OUT_DIR/humanoid-700-report.json (interference per pose, joint torques, COM margins, mass, BOM
counts) and OUT_DIR/humanoid-700-print-list.csv.   PROPOSED DESIGN -- not built or tested.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
import time
from pathlib import Path

import humanoid_geometry as G
import humanoid_layout as L

TOL_MM3 = 0.5
COLORS = {"pla": (0.92, 0.92, 0.9, 1.0), "tpu": (0.15, 0.45, 0.95, 1.0), "vendor": (0.18, 0.18, 0.2, 1.0),
          "pcb": (0.05, 0.45, 0.15, 1.0), "battery": (0.85, 0.2, 0.15, 1.0)}
ACCENT = ("torso_walls", "torso_back_cover", "head_shell", "thigh_", "shin_", "upper_arm_", "forearm_")


def color(name, mat):
    if mat == "pla" and any(name.startswith(a) for a in ACCENT):
        return (0.98, 0.55, 0.1, 1.0)
    return COLORS[mat]


def interference(shapes) -> list:
    names = list(shapes)
    bb = {n: shapes[n].BoundingBox() for n in names}
    hits = []
    for a, b in itertools.combinations(names, 2):
        A, B = bb[a], bb[b]
        if (A.xmax < B.xmin or B.xmax < A.xmin or A.ymax < B.ymin or B.ymax < A.ymin
                or A.zmax < B.zmin or B.zmax < A.zmin):
            continue
        v = shapes[a].intersect(shapes[b]).Volume()
        if v > TOL_MM3:
            hits.append({"a": a, "b": b, "volume_mm3": round(v, 2)})
    return hits


def check_poses(P, mass, com, skip_interf):
    roll = L.balance_roll(mass, com)
    out = {}
    for name, (q, sup) in L.poses(roll).items():
        t0 = time.time()
        rec = {"q_deg": {k: round(v, 2) for k, v in q.items()}, "out_of_range": L.in_range(q)}
        if sup:
            s = L.statics(q, sup, mass, com)
            st = {k: v for k, v in s["torque_nm"].items() if L.JOINTS[k]["kind"] == "st"}
            sc = {k: v for k, v in s["torque_nm"].items() if L.JOINTS[k]["kind"] == "sc"}
            worst = max(st, key=lambda k: abs(st[k]))
            rec.update(support=sup, com_mm=s["com_mm"], support_margin_mm=s["support_margin_mm"],
                       torque_nm={k: round(v, 3) for k, v in s["torque_nm"].items()},
                       worst_st3215=worst, worst_st3215_nm=round(abs(st[worst]), 3),
                       worst_frac_of_stall=round(abs(st[worst]) / L.ST_STALL_NM, 3),
                       worst_sc09_frac_of_stall=round(max(abs(v) for v in sc.values()) / L.SC_STALL_NM, 3))
        if not skip_interf:
            rec["interference"] = interference(G.posed(P, q))
        rec["seconds"] = round(time.time() - t0, 1)
        out[name] = rec
        print(f"pose {name}: margin {rec.get('support_margin_mm')} worst {rec.get('worst_st3215')} "
              f"{rec.get('worst_st3215_nm')} N.m, hits {len(rec.get('interference', []))}", flush=True)
    return roll, out


def export(P, q, path, vendor):
    import cadquery as cq
    shapes = G.posed(P, q)
    Tl = L.link_transforms(q)
    asm = cq.Assembly(name="humanoid_700")
    v = G.vendor_st3215() if vendor else None
    for n, p in P.items():
        if vendor and n.startswith("servo_") and "gripper" not in n and "neck" not in n:
            jn = n[len("servo_"):]
            M = Tl[L.JOINTS[jn]["body"]] @ L.servo_frame(jn)
            asm.add(G.place(v, M), name=n, color=cq.Color(*COLORS["vendor"]))
        else:
            asm.add(shapes[n], name=n, color=cq.Color(*color(n, p.material)))
    asm.export(str(path))
    return path.stat().st_size


def print_list(P, mass_fn, path):
    rows = []
    for n, p in sorted(P.items()):
        if p.kind != "printed":
            continue
        bb = p.shape.BoundingBox()
        rows.append([n, p.material.upper(), round(mass_fn(n, p), 1),
                     f"{bb.xlen:.0f} x {bb.ylen:.0f} x {bb.zlen:.0f}"])
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["part", "material", "est_mass_g", "bbox_mm"])
        w.writerows(rows)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--no-vendor", action="store_true")
    ap.add_argument("--skip-interference", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    P = G.parts()
    print(f"built {len(P)} parts in {time.time() - t0:.0f}s", flush=True)
    mass, com = G.link_inertia(P)
    roll, poses = check_poses(P, mass, com, a.skip_interference)

    steps = {}
    for pose in ("stand", "single_support_left"):
        q = L.poses(roll)[pose][0]
        path = out / f"humanoid-700-{pose.replace('_', '-')}.step"
        steps[pose] = {"path": str(path), "bytes": export(P, q, path, not a.no_vendor)}
        print("wrote", path, flush=True)
    rows = print_list(P, G.mass_g, out / "humanoid-700-print-list.csv")

    import cadquery as cq
    bb = cq.Compound.makeCompound([p.shape for p in P.values()]).BoundingBox()
    hits = sum(len(r.get("interference", [])) for r in poses.values())
    report = {
        "status": "PROPOSED - not fabrication-ready, not FEA-verified, not prototype-tested",
        "parts": len(P), "printed_parts": len(rows),
        "purchased_parts_modelled": sum(p.kind == "purchased" for p in P.values()),
        "all_valid_single_solids": True,
        "overall_bbox_mm": [round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)],
        "estimated_mass_g": round(sum(mass.values())),
        "printed_mass_g": round(sum(r[2] for r in rows)),
        "link_mass_g": {k: round(v) for k, v in mass.items()},
        "st3215_stall_nm_at_11v1": round(L.ST_STALL_NM, 3),
        "single_support_roll_deg": roll,
        "brackets": {jn: [round(v, 1) for v in L.bracket_params(jn)] for jn in L.JOINTS
                     if L.JOINTS[jn]["mount"] == "u"},
        "poses": poses, "interference_total": hits, "steps": steps,
        "build_seconds": round(time.time() - t0, 1),
    }
    (out / "humanoid-700-report.json").write_text(json.dumps(report, indent=2, default=float))
    print(json.dumps({k: report[k] for k in ("parts", "printed_parts", "overall_bbox_mm", "estimated_mass_g",
                                              "single_support_roll_deg", "interference_total", "build_seconds")}))
    for n, r in poses.items():
        for h in r.get("interference", [])[:20]:
            print(" HIT", n, h)
    return 0 if hits == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
