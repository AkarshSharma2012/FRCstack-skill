"""concept_sketch_ollie.py -- concept sheet for the walk / skate / crawl humanoid ("OLLIE").

Usage: python concept_sketch_ollie.py OUT_PNG
Pure 2-D illustration (matplotlib).  Proportions follow the current humanoid CAD skeleton
(120 mm thigh / shin, 20 servos); the shells, heel wheels and pads are the proposed new form.
"""
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402
from scipy.spatial import ConvexHull  # noqa: E402

BG = "#FAF9F6"
SHELL, SHELL2, SHELL_F = "#F6F3EE", "#E3DFD8", "#D9D5CE"
JOINT, JOINT_F = "#30343B", "#4B5058"
VISOR, GLOW, ACC = "#14161B", "#7FE3FF", "#FF6B2C"
LINE, TIRE, GRAY = "#2A2D33", "#23262C", "#8A8F98"
THIGH = SHIN = 120.0
UA, FA, PAW = 100.0, 88.0, 38.0


def R(d):
    t = np.radians(d)
    c, s = np.cos(t), np.sin(t)
    return np.array([[c, -s], [s, c]])


def down(a):
    t = np.radians(a)
    return np.array([np.sin(t), -np.cos(t)])


def fwd(a):
    t = np.radians(a)
    return np.array([np.cos(t), np.sin(t)])


def circle(c, r, n=48):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.c_[c[0] + r * np.cos(t), c[1] + r * np.sin(t)]


def hull(circles):
    P = np.vstack([circle(c, r) for c, r in circles])
    return P[ConvexHull(P).vertices]


def capsule(p0, p1, r0, r1=None):
    return hull([(np.asarray(p0, float), r0), (np.asarray(p1, float), r0 if r1 is None else r1)])


def squircle(c, w, h, n=4.0, ang=0.0, taper=0.0, k=120):
    t = np.linspace(0, 2 * np.pi, k, endpoint=False)
    x = np.sign(np.cos(t)) * np.abs(np.cos(t)) ** (2 / n) * w / 2
    y = np.sign(np.sin(t)) * np.abs(np.sin(t)) ** (2 / n) * h / 2
    x = x * (1 + taper * y / (h / 2))
    return (R(ang) @ np.c_[x, y].T).T + np.asarray(c, float)


class Canvas:
    def __init__(self):
        self.items, self.contacts = [], []

    def add(self, pts, fc, z, ec=LINE, lw=1.5, alpha=1.0, contact=False, clip=None, name=None):
        pts = np.asarray(pts, float)
        self.items.append(dict(pts=pts, fc=fc, z=z, ec=ec, lw=lw, alpha=alpha, clip=clip, name=name))
        if contact:
            self.contacts.append(pts[np.argmin(pts[:, 1])])
        return pts

    def line(self, pts, color, z, lw=1.2, alpha=1.0):
        self.items.append(dict(line=np.asarray(pts, float), fc=color, z=z, lw=lw, alpha=alpha))

    def draw(self, ax, center=True):
        g = min(p[1] for p in self.contacts)
        allp = np.vstack([i["pts"] for i in self.items if "pts" in i])
        dx = -(allp[:, 0].min() + allp[:, 0].max()) / 2 if center else 0.0
        off = np.array([dx, -g])
        patches = {}
        for it in sorted(self.items, key=lambda i: i["z"]):
            if "line" in it:
                P = it["line"] + off
                ax.plot(P[:, 0], P[:, 1], color=it["fc"], lw=it["lw"], alpha=it["alpha"], zorder=it["z"],
                        solid_capstyle="round")
                continue
            p = Polygon(it["pts"] + off, closed=True, fc=it["fc"], ec=it["ec"], lw=it["lw"], alpha=it["alpha"],
                        zorder=it["z"], joinstyle="round")
            ax.add_patch(p)
            if it["name"]:
                patches[it["name"]] = p
            if it["clip"]:
                p.set_clip_path(patches[it["clip"]])
        xs = [c[0] + dx for c in self.contacts]
        ax.add_patch(Polygon(squircle(((min(xs) + max(xs)) / 2, 0), max(xs) - min(xs) + 150, 18, n=2),
                             fc="black", ec="none", alpha=0.09, zorder=0.5))
        ax.axhline(0, color="#CFCBC4", lw=1.3, zorder=0.4)
        top = allp[:, 1].max() - g
        return off, top


# ------------------------------------------------------------------------------- side view
def side(p):
    c = Canvas()
    hip = np.zeros(2)
    ta = p["torso"]
    Rt = R(-ta)

    def T(q):
        return hip + Rt @ np.asarray(q, float)
    cont = p["contacts"]
    for k, (z0, sh, jt) in {"far": (10, SHELL_F, JOINT_F), "near": (30, SHELL, JOINT)}.items():
        a, flex, fa = p[k + "_leg"]
        knee = hip + THIGH * down(a)
        b = a - flex
        ank = knee + SHIN * down(b)
        c.add(capsule(hip, knee, 24, 19), sh, z0 + 1)
        c.add(capsule(knee, ank, 19, 15), sh, z0 + 1)
        bis = fwd(a) + fwd(b)
        bis /= np.linalg.norm(bis)
        c.add(circle(hip, 25), jt, z0 + 2)
        c.add(circle(knee, 20), jt, z0 + 2)
        c.add(circle(knee + 13 * bis, 13), ACC, z0 + 2.2, contact="knee" in cont)
        c.add(circle(ank, 14), jt, z0 + 2)
        Rf = R(fa)

        def F(q):
            return ank + Rf @ np.asarray(q, float)
        c.add(circle(F((-44, -38.5)), 21), TIRE, z0 + 3.5, contact="wheel" in cont)
        c.add(circle(F((-44, -38.5)), 9), ACC, z0 + 3.6)
        c.add(circle(F((-44, -38.5)), 3), SHELL, z0 + 3.7, lw=0.8)
        foot = hull([(F((-22, -42)), 20), (F((85, -45)), 17), (F((5, -12)), 26)])
        c.add(foot, sh, z0 + 4, contact="sole" in cont)
        c.add(capsule(F((-20, -57)), F((84, -57)), 5), TIRE, z0 + 4.5, contact="sole" in cont)
        c.add(capsule(F((60, -30)), F((88, -36)), 5), ACC, z0 + 4.6, ec="none")
    ground = min(q[1] for q in c.contacts) if c.contacts else None

    for k, (z0, sh, jt) in {"far": (15, SHELL_F, JOINT_F), "near": (40, SHELL, JOINT)}.items():
        sa, e = p[k + "_arm"]
        S = T((10, 178))
        if "paw" in cont:                       # solve the arm so the paw rests on the ground
            best = None
            for sa_ in np.arange(0, 75, 1.0):
                for e_ in np.arange(-10, 110, 1.0):
                    E_ = S + UA * down(sa_)
                    W_ = E_ + FA * down(sa_ + e_)
                    err = abs(capsule(W_, W_ + PAW * down(sa_ + e_), 21)[:, 1].min() - ground)
                    score = err * 10 + (W_[0] - S[0]) * 0.02 + abs(e_ - e) * 0.05
                    if best is None or score < best[0]:
                        best = (score, sa_, e_)
            sa, e = best[1], best[2]
        E = S + UA * down(sa)
        W = E + FA * down(sa + e)
        tip = W + PAW * down(sa + e)
        c.add(capsule(S, E, 17, 15), sh, z0 + 1)
        c.add(capsule(E, W, 15, 14), sh, z0 + 1)
        c.add(circle(S, 24), jt, z0 + 2)
        c.add(circle(S, 8), ACC, z0 + 2.1, ec="none")
        c.add(circle(E, 14), jt, z0 + 2)
        c.add(capsule(W, tip, 21), SHELL2 if k == "near" else SHELL_F, z0 + 3, contact="paw" in cont)
        nf = fwd(sa + e)
        c.add(capsule(W + 14 * nf, tip + 14 * nf, 5), ACC, z0 + 3.2, ec="none")

    # torso
    c.line([T(q) for q in ((-66, 222), (-90, 210), (-92, 160), (-70, 148))], JOINT, 21, lw=5)   # carry handle
    c.add(capsule(T((-34, 4)), T((34, 4)), 22), JOINT, 19)
    c.add([T(q) for q in squircle((0, 118), 150, 250, n=2.6, taper=0.12)], SHELL, 22)
    c.add([T(q) for q in squircle((0, 40), 132, 60, n=2.4)], SHELL2, 22.5, lw=1.0)
    c.add([T(q) for q in squircle((-30, 172), 30, 90, n=2)], "white", 23, ec="none", alpha=0.55)
    c.add(capsule(T((72, 138)), T((72, 168)), 11), GLOW, 23.8, ec="none", alpha=0.25)
    c.add(capsule(T((72, 138)), T((72, 168)), 4.5), GLOW, 24, ec="none")
    # head
    ht = ta + p["head"]
    Rh = R(-ht)
    Hc = T((0, 236)) + Rh @ np.array([8.0, 66.0])

    def H(q):
        return Hc + Rh @ np.asarray(q, float)
    c.add(capsule(T((0, 222)), H((0, -40)), 15), JOINT, 49)
    c.add([H(q) for q in squircle((0, 0), 128, 110, n=3.6)], SHELL, 50, name="head")
    c.add([H(q) for q in squircle((40, 4), 96, 70, n=3.2)], VISOR, 51, clip="head", ec="none")
    c.add(capsule(H((55, -6)), H((55, 14)), 13), GLOW, 52.9, ec="none", alpha=0.28)
    c.add(capsule(H((55, -6)), H((55, 14)), 6.5), GLOW, 53, ec="none")
    c.add(circle(H((-8, -2)), 19), SHELL2, 52)
    c.add(circle(H((-8, -2)), 10), ACC, 52.1, ec="none")
    c.add(circle(H((-8, -2)), 4), JOINT, 52.2, ec="none")
    c.add([H(q) for q in squircle((-26, 34), 50, 18, n=2)], "white", 52.5, ec="none", alpha=0.6)
    for y in p.get("speed", []):
        c.line([(-190, y), (-120, y)], GRAY, 1, lw=2.4, alpha=0.6)
    return c


# ------------------------------------------------------------------------------- front view
def front():
    c = Canvas()
    for s in (1, -1):
        x = 48 * s
        c.add(squircle((x + 4 * s, 24), 76, 48, n=3.2), SHELL, 14, contact=True)
        c.add(capsule((x + 4 * s - 28, 5), (x + 4 * s + 28, 5), 5), TIRE, 14.5, contact=True)
        c.add(capsule((x + 4 * s - 18, 34), (x + 4 * s + 18, 34), 4.5), ACC, 14.6, ec="none")
        c.add(circle((x, 64), 15), JOINT, 13)
        c.add(capsule((x, 64), (x, 182), 17, 19), SHELL, 11)
        c.add(circle((x, 182), 21), JOINT, 12)
        c.add(circle((x, 182), 11), ACC, 12.1, ec="none")
        c.add(capsule((x, 182), (x, 300), 20, 24), SHELL, 11)
        c.add(circle((x, 302), 25), JOINT, 12)
        S, E, W, tip = (108 * s, 528), (117 * s, 430), (121 * s, 345), (122 * s, 305)
        c.add(capsule(S, E, 17, 15), SHELL, 24)
        c.add(capsule(E, W, 15, 14), SHELL, 24)
        c.add(circle(S, 25), JOINT, 25)
        c.add(circle(S, 8), ACC, 25.1, ec="none")
        c.add(circle(E, 14), JOINT, 25)
        c.add(capsule(W, tip, 22), SHELL2, 26)
        c.add(capsule((109 * s, 338), (110 * s, 308), 5), ACC, 26.1, ec="none")
        c.add(circle((78 * s, 652), 19), SHELL2, 29)
        c.add(circle((78 * s, 652), 10), ACC, 29.1, ec="none")
        c.add(capsule((27 * s, 645), (27 * s, 665), 15), GLOW, 32.9, ec="none", alpha=0.28)
        c.add(capsule((27 * s, 645), (27 * s, 665), 8), GLOW, 33, ec="none")
    c.add(capsule((-40, 314), (40, 314), 24), JOINT, 15)
    c.add(squircle((0, 445), 196, 250, n=2.6, taper=0.16), SHELL, 20)
    c.add(squircle((0, 368), 150, 64, n=2.4), SHELL2, 20.5, lw=1.0)
    c.add(squircle((-50, 495), 34, 84, n=2), "white", 21, ec="none", alpha=0.55)
    c.add(capsule((-28, 500), (28, 500), 11), GLOW, 21.9, ec="none", alpha=0.25)
    c.add(capsule((-28, 500), (28, 500), 5), GLOW, 22, ec="none")
    c.add(capsule((0, 566), (0, 600), 16), JOINT, 19)
    c.add(squircle((0, 652), 156, 120, n=3.6), SHELL, 30)
    c.add(squircle((0, 654), 122, 66, n=3.4), VISOR, 31, ec="none")
    c.add(capsule((-46, 678), (-22, 681), 2.5), "white", 31.5, ec="none", alpha=0.35)
    c.add(squircle((-38, 694), 44, 14, n=2), "white", 31.6, ec="none", alpha=0.6)
    return c


POSES = {
    "walk": dict(torso=4, head=-4, near_leg=(14, 4, 0), far_leg=(-12, 0.3, 0), near_arm=(-18, 18),
                 far_arm=(16, 22), contacts={"sole"}),
    "skate": dict(torso=16, head=-16, near_leg=(32, 43, 16), far_leg=(26, 47.5, 16), near_arm=(-40, 25),
                  far_arm=(-28, 30), contacts={"wheel"}, speed=(160, 250, 340, 430)),
    "crawl": dict(torso=82, head=-78, near_leg=(4, 98, 175), far_leg=(0, 96, 172), near_arm=(30, 40),
                  far_arm=(24, 40), contacts={"knee", "paw"}),
}


def callout(ax, xy, txt, xt, yt, ha):
    ax.annotate(txt, xy=xy, xytext=(xt, yt), fontsize=9.2, color=LINE, ha=ha, va="center", zorder=60,
                arrowprops=dict(arrowstyle="-", color=GRAY, lw=0.9, shrinkA=3, shrinkB=2))
    ax.plot(*xy, "o", ms=3.5, color=ACC, zorder=61)


def main(out):
    fig = plt.figure(figsize=(20, 11.5), facecolor=BG)
    hero = fig.add_axes([0.0, 0.25, 0.32, 0.72])
    hero.set_xlim(-470, 470)
    hero.set_ylim(-60, 890)
    front().draw(hero, center=False)
    hero.text(0.5, 0.975, "OLLIE", transform=hero.transAxes, ha="center", va="top", fontsize=30,
              fontweight="bold", color=LINE)
    hero.text(0.5, 0.915, "walks  \u00b7  skates  \u00b7  crawls", transform=hero.transAxes, ha="center", va="top",
              fontsize=12.5, color=GRAY)
    hero.text(0.5, 0.875, "one RL policy picks the mode", transform=hero.transAxes, ha="center", va="top",
              fontsize=11, color=ACC)
    callout(hero, (-27, 655), "Smoked visor face:\nOLED eyes show\nmood + mode", -165, 655, "right")
    callout(hero, (78, 652), "Ear pods cover the\nneck servos", 165, 655, "left")
    callout(hero, (20, 500), "Light bar: blue walk,\norange skate,\nwhite crawl", 165, 520, "left")
    callout(hero, (-60, 420), "Soft printed shell +\nTPU bumpers over the\nsame 20-servo skeleton", -165, 440, "right")
    callout(hero, (122, 315), "Mitten hand: gripper\n+ crawling paw in one", 165, 330, "left")
    callout(hero, (-48, 182), "Orange = every part\nthat touches the world\n(knees, paws, wheels)", -165, 210, "right")
    callout(hero, (52, 24), "Heel wheels inside the\nfoot shell (N20 motors)", 165, 95, "left")
    hero.set_axis_off()

    titles = {"walk": ("1  WALK", "steps, cables, door sills"),
              "skate": ("2  SKATE", "toes up, rolls on heel wheels \u00b7 ~0.5 m/s"),
              "crawl": ("3  CRAWL", "drops to ~30 cm \u00b7 under tables + chairs")}
    tops = {}
    for i, name in enumerate(("walk", "skate", "crawl")):
        ax = fig.add_axes([0.33 + i * 0.224, 0.25, 0.22, 0.72])
        ax.set_xlim(-300, 300)
        ax.set_ylim(-60, 890)
        _, tops[name] = side(POSES[name]).draw(ax)
        ax.text(0.5, 0.975, titles[name][0], transform=ax.transAxes, ha="center", va="top", fontsize=17,
                fontweight="bold", color=LINE)
        ax.text(0.5, 0.925, titles[name][1], transform=ax.transAxes, ha="center", va="top", fontsize=10.5,
                color=GRAY)
        ax.set_axis_off()
    for i in range(2):
        fig.text(0.33 + 0.224 * (i + 1) - 0.002, 0.55, "\u21c4", ha="center", va="center", fontsize=26, color=ACC)

    cols = [
        ("Design language", [
            "Rounded soft-shell body over the existing ST3215 skeleton:",
            "  no bare brackets, nothing that reads as 'metal skeleton'.",
            "Oversized helmet head + smoked visor: two glowing eyes",
            "  do all the expression (friendly, not uncanny).",
            "Warm white + graphite joints + ONE signal-orange accent.",
            "Carry handle on the back = tether point for RL training.",
        ]),
        ("Why this shape fits the job", [
            "Heelys-style heel wheels: lift the toes and it rolls",
            "  ~15-20x faster than it walks on flat floors.",
            "Round shells + orange knee/paw pads take the hits when",
            "  it falls, kneels or crawls.",
            "Mitten hands double as front feet in crawl mode.",
            f"Crawl height ~{tops['crawl'] / 10:.0f} cm vs ~{tops['walk'] / 10:.0f} cm standing.",
        ]),
        ("Inspired by (not copied)", [
            "Disney BDX droids: expressive head, RL-trained motion",
            "Ascento / Swiss-Mile: wheels on legs",
            "Heelys shoes: heel-wheel skating",
            "1X NEO, Figure 03: soft covered bodies",
            "Electric Atlas: clean, rounded joints",
        ]),
    ]
    for i, (head, lines) in enumerate(cols):
        x = 0.04 + i * 0.32
        fig.text(x, 0.215, head, fontsize=13, fontweight="bold", color=LINE, va="top")
        fig.text(x, 0.185, "\n".join(lines), fontsize=10, color=LINE, va="top", linespacing=1.5)
    fig.text(0.985, 0.012, "Concept sketch v1 \u00b7 proportions match the current CAD skeleton \u00b7 adds 4 N20 wheel "
             "motors (~$30) \u00b7 not final", fontsize=8.5, color=GRAY, ha="right")
    for k, col in enumerate((SHELL, JOINT, ACC, VISOR, GLOW)):
        fig.patches.append(matplotlib.patches.Rectangle((0.04 + k * 0.022, 0.012), 0.018, 0.02, fc=col, ec=LINE,
                                                         lw=0.8, transform=fig.transFigure, figure=fig))
    fig.text(0.04 + 5 * 0.022 + 0.004, 0.022, "palette: warm white \u00b7 graphite \u00b7 signal orange \u00b7 visor \u00b7 eye glow",
             fontsize=8.5, color=GRAY, va="center")
    fig.savefig(out, dpi=110, facecolor=BG)
    print("wrote", out, "crawl top mm", round(tops["crawl"]), "stand top mm", round(tops["walk"]))


if __name__ == "__main__":
    main(sys.argv[1])
