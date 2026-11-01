"""render_hand_v3.py -- shaded preview of the v3 in-palm hand (two views + cutaway).

Usage: python render_hand_v3.py OUT_PNG [--pose open|grasp] [--grasp-json PATH]"""
import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

import hand_kinematics as hk  # noqa: E402
import hand_v3_geometry as g  # noqa: E402


def _col(k):
    if "fin_ray" in k:
        return (0.2, 0.45, 0.95)
    if k.startswith("motor_") and k != "motor_cage":
        return (0.55, 0.57, 0.62)
    if k.startswith("drum_"):
        return (0.85, 0.55, 0.1)
    if k.startswith("tendon_"):
        return (0.9, 0.15, 0.15)
    if k.startswith("pcb_controller"):
        return (0.05, 0.5, 0.15)
    if k.startswith("pcb_component"):
        return (0.3, 0.8, 0.35)
    if k == "ball_reference_150mm":
        return (1.0, 0.85, 0.1)
    if k.startswith("palm_shell"):
        return (0.93, 0.84, 0.76)
    return (0.92, 0.92, 0.88)


def mesh(parts):
    light = np.array([0.4, -0.5, 0.75]) / np.linalg.norm([0.4, -0.5, 0.75])
    out = {}
    for k, s in parts.items():
        v, t = s.tessellate(0.5, 0.4)
        if not t:
            continue
        V = np.array([p.toTuple() for p in v])
        tris = V[np.array(t)]
        n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        lum = 0.35 + 0.65 * np.abs(n @ light)
        out[k] = (tris, np.clip(lum[:, None] * np.array(_col(k)), 0, 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_png")
    ap.add_argument("--pose", default="open")
    ap.add_argument("--grasp-json")
    a = ap.parse_args()
    if a.pose == "grasp":
        d = json.loads(Path(a.grasp_json).read_text())["best"]
        q = dict(zip(hk._JOINT_ORDER, d["q"]))
    else:
        q, d = hk.pose("open"), None
    parts = g.build_hand_v3(q)
    if d is not None:
        import cadquery as cq
        import hand_v3_grasp as gr
        parts["ball_reference_150mm"] = cq.Solid.makeSphere(gr.BALL_R, cq.Vector(*gr.ball_center(d["cx"], d["cy"])))
    full = mesh(parts)
    cut = {k: v for k, v in full.items() if k not in ("palm_shell_palmar", "palm_shell_dorsal",
                                                      "ball_reference_150mm")}
    views = [("Palmar side", full, (-60, 250)), ("Back of hand", full, (55, -70)),
             ("Inside the palm (shell hidden)", cut, (70, -90))]
    fig = plt.figure(figsize=(18, 6.5))
    for i, (title, m, (el, az)) in enumerate(views):
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        for k, (tris, cols) in m.items():
            alpha = 0.35 if k == "ball_reference_150mm" else 1.0
            ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, linewidths=0, alpha=alpha))
        r = 130 if d is not None else 100
        ax.set_xlim(-r, r)
        ax.set_ylim(-100, 160)
        ax.set_zlim(-r, r)
        ax.set_box_aspect((2 * r, 260, 2 * r))
        ax.view_init(el, az)
        ax.set_axis_off()
        ax.set_title(title)
    plt.tight_layout()
    plt.savefig(a.out_png, dpi=90)
    print("wrote", a.out_png)


if __name__ == "__main__":
    main()
