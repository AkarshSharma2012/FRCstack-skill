"""render_humanoid.py -- shaded preview of the humanoid (front, side, 3/4, single-support).

Usage: python render_humanoid.py OUT_PNG"""
import argparse

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

import build_humanoid as B  # noqa: E402
import humanoid_geometry as G  # noqa: E402
import humanoid_layout as L  # noqa: E402


def mesh(P, shapes):
    light = np.array([0.5, -0.4, 0.75]) / np.linalg.norm([0.5, -0.4, 0.75])
    out = []
    for n, s in shapes.items():
        v, t = s.tessellate(0.8, 0.5)
        if not t:
            continue
        V = np.array([p.toTuple() for p in v])
        tris = V[np.array(t)]
        nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
        lum = 0.35 + 0.65 * np.abs(nrm @ light)
        col = np.array(B.color(n, P[n].material)[:3])
        out.append((tris, np.clip(lum[:, None] * col, 0, 1)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_png")
    a = ap.parse_args()
    P = G.parts()
    mass, com = G.link_inertia(P)
    roll = L.balance_roll(mass, com)
    stand = mesh(P, G.posed(P, {}))
    ss = mesh(P, G.posed(P, L.poses(roll)["single_support_left"][0]))
    views = [("Front", stand, (5, 0)), ("Side", stand, (5, -90)), ("3/4 view", stand, (20, -35)),
             ("Standing on one leg", ss, (12, -20))]
    fig = plt.figure(figsize=(20, 8))
    for i, (title, m, (el, az)) in enumerate(views):
        ax = fig.add_subplot(1, 4, i + 1, projection="3d")
        for tris, cols in m:
            ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, linewidths=0))
        ax.set_xlim(-200, 200)
        ax.set_ylim(-200, 200)
        ax.set_zlim(0, 800)
        ax.set_box_aspect((400, 400, 800))
        ax.view_init(el, az)
        ax.set_axis_off()
        ax.set_title(title, fontsize=14)
    plt.tight_layout()
    plt.savefig(a.out_png, dpi=80)
    print("wrote", a.out_png)


if __name__ == "__main__":
    main()
