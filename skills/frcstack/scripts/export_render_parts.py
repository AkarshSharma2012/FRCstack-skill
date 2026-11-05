"""
export_render_parts.py -- (CAD venv) export every OLLIE part as a coloured STL per pose + label anchors,
for render_ollie_hq.py (sim venv) to turn into high-quality MuJoCo renders.

Usage:  python export_render_parts.py OUT_DIR
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cadquery as cq
import numpy as np

import build_ollie as B
import ollie_geometry as OG
import ollie_physics as OP

LABELS = {                                   # label text -> part whose centre the leader line points at
    "Camera in the R9-style M-duct": "camera_ov5647",
    "Slanted OLED eyes": "oled_eye_L",
    "Chest V light = mode (walk / skate / crawl)": "light_chevron_acrylic",
    "ESP32 servo driver + Pi Zero 2 W brain": "driver_hat_a_board",
    "3S 5000 mAh LiPo, low in the hips": "battery_3s_5000",
    "Shoulder servo ST3215 (30 kg.cm)": "servo_shoulder_R",
    "CNC 6061 aluminium bracket plates": "hip_pitch_plate_al_R",
    "Aluminium box-tube thigh + shin bones": "thigh_tube_al_R",
    "Knee servo (STS3250 50 kg.cm upgrade fits)": "servo_knee_R",
    "TPU knee pad for crawling": "knee_pad_tpu_L",
    "Hand: 2 fingers + moving thumb": "palm_L",
    "N20 motor heel wheel for skating": "wheel_hub_L",
    "Aluminium foot plate + TPU sole": "foot_plate_al_L",
}


def main(out):
    out = Path(out)
    P = OG.parts()
    mass, comz = OG.link_inertia(P)
    poses = {"stand": ({}, None)}
    q, Tb, _ = OP.skate_pose(mass, comz)
    poses["skate"] = (q, Tb)
    q, Tb, _ = OP.crawl_pose(mass, comz)
    poses["crawl"] = (q, Tb)
    man = {"parts": {}, "labels": {}, "poses": list(poses)}
    for n, p in P.items():
        rgba = list(B.color(n, p.material))
        man["parts"][n] = {"rgba": rgba, "fairing": p.material == "petg" or n.startswith(("light_chevron", "eye_lens")),
                           "material": p.material}
    for pose, (q, Tb) in poses.items():
        d = out / pose
        d.mkdir(parents=True, exist_ok=True)
        shapes = OG.posed(P, q, Tb)
        for n, s in shapes.items():
            cq.exporters.export(s, str(d / f"{n}.stl"), tolerance=0.15, angularTolerance=0.15)
        print("exported", pose, len(shapes), flush=True)
    for text, n in LABELS.items():
        c = P[n].shape.Center()
        man["labels"][text] = [c.x, c.y, c.z]
    mz = sum(mass.values())
    com = sum(mass[k] * np.asarray(comz[k]) for k in mass) / mz
    man["mass_g"] = round(mz)
    man["com_mm"] = [round(float(v), 1) for v in com]
    (out / "manifest.json").write_text(json.dumps(man, indent=1))
    print("wrote", out / "manifest.json")


if __name__ == "__main__":
    main(sys.argv[1])
