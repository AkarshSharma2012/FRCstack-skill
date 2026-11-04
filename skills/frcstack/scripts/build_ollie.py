"""
build_ollie.py -- build, verify and export OLLIE (walk / skate / crawl humanoid) for Fusion 360.

Usage:  python build_ollie.py OUT_DIR [--no-vendor] [--skip-interference]

Writes:
  ollie-stand.step / ollie-skate.step / ollie-crawl.step   nested assemblies, one component per
                                                          moving link (ST3215 = vendor model)
  ollie-joints.json      joint axes, parents/children and limits (read by the Fusion joint script)
  ollie-report.json      interference + ground penetration per pose, torques, balance, skate physics
  ollie-print-list.csv   every printed part with material, mass and size
PROPOSED DESIGN -- not built or tested.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

import build_humanoid as BH
import humanoid_geometry as G
import humanoid_layout as L
import ollie_geometry as OG
import ollie_layout as OL
import ollie_physics as OP

COLORS = dict(BH.COLORS, acrylic=(0.08, 0.09, 0.11, 0.85))
SHELL = ("torso_shell", "torso_back_cover", "torso_top_plate", "head_shell", "thigh_", "shin_",
         "upper_arm_", "forearm_", "foot_", "neck_turntable")
ORANGE = ("tpu", "ear_cap", "wheel_hub")


def color(name, mat):
    if any(k in name for k in ORANGE):
        return (1.0, 0.42, 0.17, 1.0) if "tire" not in name else (0.14, 0.15, 0.17, 1.0)
    if name == "light_diffuser":
        return (0.5, 0.89, 1.0, 1.0)
    if mat == "pla" and any(name.startswith(k) for k in SHELL):
        return (0.96, 0.95, 0.93, 1.0)
    if mat == "pla":
        return (0.19, 0.2, 0.23, 1.0)
    return COLORS[mat]


def ground_hits(shapes, allowed):
    slab = G.hb.box(-2000, 2000, -2000, 2000, -100, -0.3)
    out = []
    for n, s in shapes.items():
        if any(k in n for k in allowed):
            continue
        bb = s.BoundingBox()
        if bb.zmin > -0.3:
            continue
        v = s.intersect(slab).Volume()
        if v > 0.5:
            out.append({"part": n, "volume_mm3": round(v, 1)})
    return out


def poses(mass, comz):
    roll = L.balance_roll(mass, comz)
    base = L.poses(roll)
    I4 = np.eye(4)
    out = {
        "stand": (base["stand"][0], I4, ["sole_L", "sole_R"]),
        "crouch": (base["crouch"][0], I4, ["sole_L", "sole_R"]),
        "walk_single_support": (base["single_support_left"][0], I4, ["sole_L"]),
        "squat": (base["squat"][0], I4, ["sole_L", "sole_R"]),
        "arms_forward_grip": (base["arms_forward_grip"][0], I4, ["sole_L", "sole_R"]),
    }
    q, Tb, _ = OP.skate_pose(mass, comz)
    out["skate"] = (q, Tb, ["wheel_L", "wheel_R"])
    q, Tb, _ = OP.crawl_pose(mass, comz)
    out["crawl"] = (q, Tb, ["knee_L", "knee_R", "paw_L", "paw_R"])
    out["extremes_a"] = (base["extremes_a"][0], I4, None)
    out["extremes_b"] = (base["extremes_b"][0], I4, None)
    deep = L.both(hip_pitch=-90, knee=120, ankle_pitch=-30, shoulder=-180, elbow=-100, gripper=28)
    deep.update(neck_tilt=-45, neck_pan=-90)
    out["extremes_crawl_depth"] = (deep, I4, None)
    return roll, out


GROUND_OK = {"stand": ("sole_tpu",), "crouch": ("sole_tpu",), "walk_single_support": ("sole_tpu",),
             "squat": ("sole_tpu",), "arms_forward_grip": ("sole_tpu",), "skate": ("tire_tpu",),
             "crawl": ("knee_pad_tpu", "paw_pad_tpu")}


def check(P, mass, comz, skip):
    roll, ps = poses(mass, comz)
    rep = {}
    for name, (q, Tb, contacts) in ps.items():
        t0 = time.time()
        r = {"q_deg": {k: round(float(v), 2) for k, v in q.items()}, "out_of_range": L.in_range(q),
             "base_pitch_deg": round(float(np.degrees(np.arctan2(Tb[0, 2], Tb[0, 0]))), 1),
             "base_height_mm": round(float(Tb[2, 3]), 1)}
        if contacts:
            s = OP.statics(q, Tb, contacts, mass, comz)
            st = {k: v for k, v in s["torque_nm"].items() if L.JOINTS[k]["kind"] == "st"}
            sc = {k: v for k, v in s["torque_nm"].items() if L.JOINTS[k]["kind"] == "sc"}
            w = max(st, key=lambda k: abs(st[k]))
            r.update(contacts=s["contacts"], com_mm=s["com_mm"], support_margin_mm=s["support_margin_mm"],
                     balance_residual_n=s["balance_residual_n"], worst_st3215=w,
                     worst_st3215_nm=round(abs(st[w]), 3), worst_frac_of_stall=round(abs(st[w]) / L.ST_STALL_NM, 3),
                     worst_sc09_frac_of_stall=round(max(abs(v) for v in sc.values()) / L.SC_STALL_NM, 3),
                     torque_nm={k: round(v, 3) for k, v in s["torque_nm"].items()})
        if name == "skate":
            r["skate_physics"] = OP.pendulum(q, Tb, mass, comz)
        if not skip:
            shapes = OG.posed(P, q, Tb)
            r["interference"] = BH.interference(shapes)
            if name in GROUND_OK:
                r["ground_penetration"] = ground_hits(shapes, GROUND_OK[name])
        r["seconds"] = round(time.time() - t0, 1)
        rep[name] = r
        print(f"pose {name}: margin {r.get('support_margin_mm')} worst {r.get('worst_st3215')} "
              f"{r.get('worst_frac_of_stall')} hits {len(r.get('interference', []))} "
              f"ground {len(r.get('ground_penetration', []))}", flush=True)
    return roll, ps, rep


def export(P, q, Tb, path, vendor):
    import cadquery as cq
    Tl = OP.transforms(q, Tb)
    v = G.vendor_st3215() if vendor else None
    links = {}
    for n, p in P.items():
        links.setdefault(OG.fusion_link(n, p), []).append(n)
    top = cq.Assembly(name="OLLIE")
    for ln in sorted(links):
        sub = cq.Assembly(name=f"link_{ln}")         # prefix: link names must not clash with part names
        for n in links[ln]:
            p = P[n]
            T = Tl[OG.fusion_link(n, p)]
            if vendor and n.startswith("servo_") and "gripper" not in n and "neck" not in n:
                jn = n[len("servo_"):]
                sub.add(G.place(v, T @ L.servo_frame(jn)), name=n, color=cq.Color(*COLORS["vendor"]))
            else:
                sub.add(G.place(p.shape, T), name=n, color=cq.Color(*color(n, p.material)))
        top.add(sub, name=f"link_{ln}")
    top.export(str(path))
    return path.stat().st_size


def joints_json(path):
    rows = []
    for jn, j in {**L.JOINTS, **OL.WHEEL_JOINTS}.items():
        rows.append({"name": jn, "parent": f"link_{j['parent']}", "child": f"link_{j['child']}",
                     "point_mm": list(map(float, j["p"])),
                     "axis": list(map(float, j["axis"])),
                     "range_deg": list(j["range"]) if j["range"] else None,
                     "actuator": {"st": "Waveshare ST3215", "sc": "Waveshare SC09", "n20": "N20 150:1 encoder"}[j["kind"]]})
    path.write_text(json.dumps({"units": "mm", "ground": "link_base", "zero_pose": "standing (ollie-stand.step)",
                                "joints": rows}, indent=2))
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
    P = OG.parts()
    print(f"built {len(P)} parts in {time.time() - t0:.0f}s", flush=True)
    mass, comz = OG.link_inertia(P)
    roll, ps, rep = check(P, mass, comz, a.skip_interference)
    steps = {}
    for pose in ("stand", "skate", "crawl"):
        q, Tb, _ = ps[pose]
        path = out / f"ollie-{pose}.step"
        steps[pose] = export(P, q, Tb, path, not a.no_vendor and pose == "stand")
        print("wrote", path, flush=True)
    jrows = joints_json(out / "ollie-joints.json")
    rows = []
    for n, p in sorted(P.items()):
        if p.kind == "printed":
            bb = p.shape.BoundingBox()
            rows.append([n, p.material.upper(), round(OG.mass_g(n, p), 1), f"{bb.xlen:.0f} x {bb.ylen:.0f} x {bb.zlen:.0f}"])
    with (out / "ollie-print-list.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["part", "material", "est_mass_g", "bbox_mm"])
        w.writerows(rows)
    import cadquery as cq
    bb = cq.Compound.makeCompound([p.shape for p in P.values()]).BoundingBox()
    hits = sum(len(r.get("interference", [])) + len(r.get("ground_penetration", [])) for r in rep.values())
    report = {
        "status": "PROPOSED - not fabrication-ready, not FEA-verified, not prototype-tested",
        "parts": len(P), "printed_parts": len(rows), "purchased_parts": len(P) - len(rows),
        "joints": len(jrows), "overall_bbox_mm": [round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1)],
        "estimated_mass_g": round(sum(mass.values())), "printed_mass_g": round(sum(r[2] for r in rows)),
        "walk_single_support_roll_deg": roll, "poses": rep, "problems_total": hits,
        "step_bytes": steps, "build_seconds": round(time.time() - t0, 1)}
    (out / "ollie-report.json").write_text(json.dumps(report, indent=2, default=float))
    print(json.dumps({k: report[k] for k in ("parts", "printed_parts", "joints", "overall_bbox_mm",
                                              "estimated_mass_g", "problems_total", "build_seconds")}))
    for n, r in rep.items():
        for h in r.get("interference", [])[:15] + r.get("ground_penetration", [])[:10]:
            print(" HIT", n, h)
    return 0 if hits == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
