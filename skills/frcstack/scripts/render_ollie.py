"""render_ollie.py -- shaded preview of OLLIE: front, 3/4, skate and crawl.

Usage: python render_ollie.py OUT_PNG"""
import argparse

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

import build_ollie as B  # noqa: E402
import ollie_geometry as OG  # noqa: E402
import ollie_physics as OP  # noqa: E402


def mesh(P, shapes):
    light = np.array([0.6, -0.35, 0.72]) / np.linalg.norm([0.6, -0.35, 0.72])
    out = []
    for n, s in shapes.items():
        v, t = s.tessellate(0.6, 0.4)
        if not t:
            continue
        V = np.array([p.toTuple() for p in v])
        tris = V[np.array(t)]
        nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
        lum = 0.32 + 0.68 * np.abs(nrm @ light)
        col = np.array(B.color(n, P[n].material)[:3])
        out.append((tris, np.clip(lum[:, None] * col, 0, 1)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_png")
    a = ap.parse_args()
    P = OG.parts()
    mass, comz = OG.link_inertia(P)
    stand = mesh(P, OG.posed(P, {}))
    q, Tb, _ = OP.skate_pose(mass, comz)
    skate = mesh(P, OG.posed(P, q, Tb))
    q, Tb, _ = OP.crawl_pose(mass, comz)
    crawl = mesh(P, OG.posed(P, q, Tb))
    views = [("Front", stand, (6, 0), 0), ("3/4", stand, (14, -35), 0), ("Side", stand, (8, -90), 0),
             ("Back 3/4", stand, (14, -150), 0), ("Skate", skate, (10, -60), 0), ("Crawl", crawl, (16, -55), 150)]
    fig = plt.figure(figsize=(27, 9), facecolor="#F4F5F7")
    for i, (title, m, (el, az), dx) in enumerate(views):
        ax = fig.add_subplot(1, 6, i + 1, projection="3d")
        ax.set_facecolor("#F4F5F7")
        for tris, cols in m:
            ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, linewidths=0))
        allv = np.vstack([t.reshape(-1, 3) for t, _ in m])
        cx = (allv[:, 0].min() + allv[:, 0].max()) / 2 if title == "Crawl" else dx
        ax.set_xlim(-210 + cx, 210 + cx)
        ax.set_ylim(-210, 210)
        ax.set_zlim(0, 860)
        ax.set_box_aspect((420, 420, 860))
        ax.view_init(el, az)
        ax.set_axis_off()
        ax.set_title(title, fontsize=15)
    plt.tight_layout()
    plt.savefig(a.out_png, dpi=90, facecolor="#F4F5F7")
    print("wrote", a.out_png)


if __name__ == "__main__":
    main()
