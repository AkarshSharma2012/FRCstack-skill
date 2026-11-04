"""
ollie_physics.py -- base-pose kinematics, multi-contact statics and mode-pose solvers for OLLIE.

Contacts are modelled as frictional points with vertical reaction forces (quasi-static).  For more
than three contacts the reaction split is the minimum-norm non-negative solution of force and
moment balance (statically indeterminate - a modelling assumption).  Skate mode is a two-wheel
inverted pendulum: the solver finds the equilibrium crouch and reports how much lean the N20 wheel
motors can recover.  PROPOSED DESIGN -- quasi-static model, no dynamics simulation.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize

import humanoid_layout as L
import ollie_layout as OL

G = 9.81


def link_of(link):
    return link.replace("wheel_", "foot_")


def base_tf(beta=0.0, z0=0.0, x0=0.0) -> np.ndarray:
    T = np.eye(4)
    T[:3, :3] = L.rot((0, 1, 0), beta)
    T[:3, 3] = (x0, 0.0, z0)
    return T


def transforms(q, Tb) -> dict:
    Tl = {ln: Tb @ T for ln, T in L.link_transforms(q).items()}
    for s in "LR":
        Tl[f"wheel_{s}"] = Tl[f"foot_{s}"]
    return Tl


def _h(P):
    P = np.atleast_2d(np.asarray(P, float))
    return np.c_[P, np.ones(len(P))]


# --------------------------------------------------------------------------- contact point sets
def _box_pts(x0, x1, y0, y1, z0, z1, s):
    ys = sorted((s * y0, s * y1))
    return [(x, y, z) for x in (x0, x1) for y in ys for z in (z0, z1)]


def contact_sets() -> dict:
    """name -> (link, zero-pose points).  Geometry mirrors ollie_geometry."""
    out = {}
    for side, s in (("L", 1), ("R", -1)):
        out[f"sole_{side}"] = (f"foot_{side}", [(x, s * L.LEG_Y + dy, 0.0) for x in L.FOOT_X
                                                 for dy in (-L.FOOT_HY, L.FOOT_HY)])
        t = np.linspace(0, 2 * math.pi, 72, endpoint=False)
        out[f"wheel_{side}"] = (f"wheel_{side}", [(OL.WHEEL_X + OL.WHEEL_R * math.cos(a), s * y,
                                                   OL.WHEEL_Z + OL.WHEEL_R * math.sin(a))
                                                  for a in t for y in (49.5, 60.5)])
        out[f"knee_{side}"] = (f"shin_{side}", _box_pts(25, 26, 32, 57, 140, 195, s))
        px, py, pz = L.GRIP_P
        out[f"paw_{side}"] = (f"forearm_{side}", _box_pts(px - 52, px - 42, 98, 126, pz - 68, pz - 67, s))
    return out


CONTACTS = contact_sets()


def world_pts(name, Tl):
    link, P = CONTACTS[name]
    return (Tl[link] @ _h(P).T).T[:, :3]


def lowest(name, Tl):
    P = world_pts(name, Tl)
    return P[np.argmin(P[:, 2])]


def ground_pts(name, Tl, tol=1.0):
    """All points of a contact set within tol of its lowest point (flat contacts spread the load)."""
    P = world_pts(name, Tl)
    return P[P[:, 2] <= P[:, 2].min() + tol]


# --------------------------------------------------------------------------- statics
def com(Tl, mass, comz):
    c = {ln: (Tl[ln] @ np.array([*comz[ln], 1.0]))[:3] for ln in mass}
    M = sum(mass.values())
    return sum(mass[ln] * c[ln] for ln in mass) / M, c


def reactions(points, C, Mg):
    """Min-norm non-negative vertical forces with force + moment balance about the COM."""
    P = np.asarray(points)
    A = np.vstack([np.ones(len(P)), P[:, 0] - C[0], P[:, 1] - C[1]])
    b = np.array([Mg, 0.0, 0.0])
    x0 = np.full(len(P), Mg / len(P))
    r = minimize(lambda f: f @ f, x0, jac=lambda f: 2 * f, method="SLSQP",
                 constraints=[{"type": "eq", "fun": lambda f: A @ f - b, "jac": lambda f: A}],
                 bounds=[(0, None)] * len(P))
    resid = float(np.linalg.norm(A @ r.x - b))
    return r.x, resid


def support_margin(points, C) -> float:
    from scipy.spatial import ConvexHull  # noqa: PLC0415
    P = np.asarray(points)[:, :2]
    if len(P) < 3 or np.linalg.matrix_rank(P - P.mean(0)) < 2:
        d = P[-1] - P[0]
        n = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-12)
        return -abs(float(n @ (C[:2] - P[0])))          # line contact: distance off the line
    h = ConvexHull(P)
    return float(min(-(eq[:2] @ C[:2] + eq[2]) for eq in h.equations))


def statics(q, Tb, contacts, mass, comz) -> dict:
    """contacts: list of contact-set names touching the ground (z = 0)."""
    Tl = transforms(q, Tb)
    C, c = com(Tl, mass, comz)
    Mg = sum(mass.values()) * 1e-3 * G
    pts, links = [], []
    for name in contacts:
        for p in ground_pts(name, Tl):
            pts.append(p)
            links.append(link_of(CONTACTS[name][0]))
    f, resid = reactions(pts, C, Mg)
    per = {}
    for name in contacts:
        per[name] = 0.0
    k = 0
    for name in contacts:
        n = len(ground_pts(name, Tl))
        per[name] = float(sum(f[k:k + n]))
        k += n
    tau = {}
    for jn, j in L.JOINTS.items():
        T = Tl[j["parent"]]
        p = (T @ np.array([*j["p"], 1.0]))[:3]
        a = T[:3, :3] @ np.asarray(j["axis"], float)
        kids = L.descendants(jn)
        t = sum(a @ np.cross((c[ln] - p) * 1e-3, [0, 0, -mass[ln] * 1e-3 * G]) for ln in kids if ln in mass)
        for pt, ln, fi in zip(pts, links, f):
            if ln in kids:
                t += a @ np.cross((pt - p) * 1e-3, [0, 0, fi])
        tau[jn] = float(t)
    return {"torque_nm": tau, "com_mm": [round(float(v), 1) for v in C],
            "contacts": {n: round(v, 2) for n, v in per.items()},
            "balance_residual_n": round(resid, 4),
            "support_margin_mm": round(support_margin(pts, C), 1)}


# --------------------------------------------------------------------------- mode solvers
def skate_pose(mass, comz, knee=40.0):
    """Equilibrium crouch on the heel wheels: foot pitched SKATE_TILT, COM over the wheel contacts."""
    best = None
    for h in np.arange(-60.0, 30.01, 0.25):
        a = OL.SKATE_TILT - h - knee
        q = L.both(hip_pitch=h, knee=knee, ankle_pitch=a)
        if L.in_range(q):
            continue
        Tl = transforms(q, np.eye(4))
        C, _ = com(Tl, mass, comz)
        wx = np.mean([lowest(f"wheel_{s}", Tl)[0] for s in "LR"])
        err = abs(C[0] - wx)
        if best is None or err < best[0]:
            best = (err, q)
    q = best[1]
    Tl = transforms(q, np.eye(4))
    zmin = min(lowest(f"wheel_{s}", Tl)[2] for s in "LR")
    return q, base_tf(0.0, -zmin), best[0]


def crawl_pose(mass, comz):
    """Hands-and-knees: knee guards + paw pads on the ground, torso pitched forward."""
    best = None
    for beta in np.arange(55.0, 86.0, 1.0):
        Tb = base_tf(beta)
        arm_tab = []
        for v in np.arange(-25.0, 25.01, 2.5):
            for e in np.arange(-60.0, 0.01, 5.0):
                q = L.both(shoulder=v - beta, elbow=e)
                if L.in_range(q):
                    continue
                Tl = transforms(q, Tb)
                pz = min(lowest(f"paw_{s}", Tl)[2] for s in "LR")
                arm_tab.append((pz, abs(v) + abs(e) * 0.2, v, e))
        for t in np.arange(-15.0, 15.01, 2.5):
            for u in (95.0, 100.0, 105.0, 110.0):
                h, k = t - beta, u - t
                ql = L.both(hip_pitch=h, knee=k, ankle_pitch=30.0)
                if L.in_range(ql):
                    continue
                Tl = transforms(ql, Tb)
                kz = min(lowest(f"knee_{s}", Tl)[2] for s in "LR")
                cands = [a for a in arm_tab if abs(a[0] - kz) < 1.0]
                if not cands:
                    continue
                _, cost, v, e = min(cands, key=lambda a: a[1])
                q = dict(ql, **L.both(shoulder=v - beta, elbow=e, gripper=28.0), neck_tilt=-45.0)
                Tl = transforms(q, Tb)
                C, _ = com(Tl, mass, comz)
                pts = [lowest(n, Tl) for n in ("knee_L", "knee_R", "paw_L", "paw_R")]
                m = support_margin(pts, C)
                score = -m + 0.3 * cost + 0.2 * abs(t)
                if best is None or score < best[0]:
                    best = (score, q, beta, kz)
    _, q, beta, kz = best
    return q, base_tf(beta, -kz), beta


def pendulum(q, Tb, mass, comz, use_frac=0.5) -> dict:
    """Skate balance capacity: max lean the wheels can recover and top speed."""
    Tl = transforms(q, Tb)
    C, _ = com(Tl, mass, comz)
    axle = np.mean([(Tl[f"wheel_{s}"] @ np.array([OL.WHEEL_X, (1 if s == 'L' else -1) * 55.0, OL.WHEEL_Z, 1]))[:3]
                    for s in "LR"], axis=0)
    M = sum(mass.values()) * 1e-3
    F = 2 * use_frac * OL.N20_STALL_NM / (OL.WHEEL_R * 1e-3)
    a = F / M
    Lc = (C[2] - axle[2]) * 1e-3
    return {"com_height_above_axle_mm": round(Lc * 1e3, 1), "mass_kg": round(M, 3),
            "wheel_force_n_at_50pct_stall": round(F, 2), "max_accel_mps2": round(a, 2),
            "max_recoverable_lean_deg": round(math.degrees(math.atan(a / G)), 1),
            "pendulum_time_constant_s": round(math.sqrt(Lc / G), 3),
            "top_speed_mps": round(OL.skate_speed_mps(), 2)}
