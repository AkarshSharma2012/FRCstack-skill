"""render_hand_v2.py -- shaded matplotlib preview of the v2 hand + forearm.

Usage: python render_hand_v2.py OUT_PNG [--pose partial]"""
import argparse

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

import hand_kinematics as hk  # noqa: E402
import hand_v2_geometry as g  # noqa: E402


def _col(k):
    if "fin_ray" in k:
        return (0.2, 0.45, 0.95)
    if k.startswith("actuator"):
        return (0.25, 0.25, 0.28)
    if k.startswith("spool"):
        return (0.85, 0.55, 0.1)
    if "cf_tube" in k:
        return (0.1, 0.1, 0.1)
    return (0.9, 0.9, 0.86)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_png")
    ap.add_argument("--pose", default="partial")
    ap.add_argument("--hand-only", action="store_true")
    a = ap.parse_args()
    parts = dict(g.build_hand(hk.pose(a.pose)))
    if not a.hand_only:
        parts.update(g.build_forearm(True))
    parts = {k: v for k, v in parts.items() if not k.startswith("cover")}
    mesh = {}
    light = np.array([0.4, -0.5, 0.75]) / np.linalg.norm([0.4, -0.5, 0.75])
    for k, s in parts.items():
        v, t = s.tessellate(0.6, 0.5)
        V = np.array([p.toTuple() for p in v])
        tris = V[np.array(t)]
        n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        lum = 0.35 + 0.65 * np.abs(n @ light)
        mesh[k] = (tris, np.clip(lum[:, None] * np.array(_col(k)), 0, 1))
    fig = plt.figure(figsize=(15, 7.5))
    for i, (el, az) in enumerate(((28, -55), (-35, 235))):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        for k, (tris, cols) in mesh.items():
            ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, linewidths=0))
        if a.hand_only:
            ax.set_xlim(-80, 80)
            ax.set_ylim(-60, 140)
            ax.set_zlim(-80, 80)
            ax.set_box_aspect((160, 200, 160))
        else:
            ax.set_xlim(-110, 110)
            ax.set_ylim(-310, 110)
            ax.set_zlim(-110, 110)
            ax.set_box_aspect((220, 420, 220))
        ax.view_init(el, az)
        ax.set_axis_off()
    plt.tight_layout()
    plt.savefig(a.out_png, dpi=90)
    print("wrote", a.out_png)


if __name__ == "__main__":
    main()
