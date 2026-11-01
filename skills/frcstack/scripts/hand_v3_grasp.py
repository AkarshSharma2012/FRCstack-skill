"""
hand_v3_grasp.py -- can the v3 hand hold a 5.91 in (150.1 mm) ball?  (numpy + scipy)
=====================================================================================
ANALYTICAL CHECK ONLY.  Rigid-body statics with linearised Coulomb friction cones,
capsule contact geometry and the pull-pull tendon model.  No FEA, no foam
compliance model beyond an allowed contact interference, no prototype test.

Procedure
  1. Ball (R = 75.06 mm, 0.227 kg = REBUILT FUEL upper weight) rests on the TPU
     palm pad; its centre (cx, cy) is searched.
  2. Every finger closes like an adaptive tendon hand: MCP until any link of the
     finger touches the ball, then PIP, then DIP (thumb: yaw + opposition are
     searched, then MCP, IP).  Contact = capsule distance <= 0.
  3. For each gravity direction (palm up/down, fingers up/down, thumb up/down)
     an LP finds contact forces inside 8-sided friction cones that balance
     SAFETY_G x weight with zero net moment, minimising the worst actuator
     torque utilisation u_j / U_ALLOW (tendon model M^-T, drum 3 mm, eta).
     Pass <=> utilisation <= 1.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import linprog

import hand_kinematics as hk
import hand_tendons as ht
import hand_v3_layout as lay

BALL_D = 5.91 * 25.4
BALL_R = BALL_D / 2
BALL_KG = 0.227
SAFETY_G = 2.0                  # hold 2 g (xArm accelerations)
MU_PAD, MU_RIGID = 0.5, 0.3     # ASSUMED: TPU 85A / PLA on PU foam (conservative)
DRUM_R_M = lay.DRUM_R / 1000.0
U_ALLOW = 0.10                  # N.m sustained, HPCB 12V 380:1 (~30 % stall current)
PALM_PAD_TOP = lay.PALM_Z[1] + 2.5
PALM_PAD = ((-40.0, 36.0), (-55.0, 38.0))      # x, y footprint of the TPU palm pad

# capsule radii (local link frame): rigid body ~ half-thickness of v2 sections
R_LINK = {"carrier": 4.5, "proximal": 5.3, "middle": 4.9, "distal": 4.2}
PAD = dict(y0=7.6, dy1=1.6, z0=7.0, z1=4.0, r=0.4)   # fin-ray outer skin line


def _seg_point(p, a, b):
    ab = b - a
    t = np.clip((p - a) @ ab / (ab @ ab), 0.0, 1.0)
    q = a + t * ab
    return q, float(np.linalg.norm(p - q))


def link_capsules(Ls, finger):
    """[(link, kind, a, b, r, mu)] world capsules for one finger."""
    seg = lay.segment_lengths()[finger]
    sc = 1.1 if finger == "thumb" else 1.0
    out = []
    for name, L in (("carrier", lay.CARRIER_LEN), ("proximal", seg[0]), ("middle", seg[1]), ("distal", seg[2])):
        T = Ls[f"{finger}_{name}"]
        a = T[:3, 3]
        b = (T @ np.array([0.0, L, 0.0, 1.0]))[:3]
        out.append((name, "rigid", a, b, R_LINK[name] * sc, MU_RIGID))
        if name == "distal":
            pa = (T @ np.array([0.0, PAD["y0"], PAD["z0"] * sc - PAD["r"], 1.0]))[:3]
            pb = (T @ np.array([0.0, L - PAD["dy1"], PAD["z1"] * sc - PAD["r"], 1.0]))[:3]
            out.append(("distal", "pad", pa, pb, PAD["r"], MU_PAD))
    return out


def ball_center(cx, cy, squeeze=1.0):
    return np.array([cx, cy, PALM_PAD_TOP + BALL_R - squeeze])


def _finger_contacts(Ls, finger, c):
    hits = []
    for link, kind, a, b, r, mu in link_capsules(Ls, finger):
        q, d = _seg_point(c, a, b)
        gap = d - BALL_R - r
        hits.append((link, kind, gap, q, mu))
    return hits


def _q_dict(q):
    return dict(zip(hk._JOINT_ORDER, q))


def close_finger(q, finger, c, step=0.5):
    """Sequential adaptive closing; returns q (updated) and contacts."""
    names = [s["name"] for s in hk.joint_specs() if s["finger"] == finger]
    lims = {s["name"]: s["limits_deg"] for s in hk.joint_specs()}
    idx = {n: i for i, n in enumerate(hk._JOINT_ORDER)}
    links_after = {1: ("proximal", "middle", "distal"), 2: ("middle", "distal"), 3: ("distal",)}
    q = list(q)
    for k in (1, 2, 3):
        j = idx[names[k]]
        lo, hi = lims[names[k]]
        while True:
            Ls = lay.links(_q_dict(q))
            gaps = [g for link, kind, g, _, _ in _finger_contacts(Ls, finger, c) if link in links_after[k]]
            if min(gaps) <= 0.0 or q[j] + step > hi:
                break
            q[j] += step
    Ls = lay.links(_q_dict(q))
    contacts = [(link, kind, g, p, mu) for link, kind, g, p, mu in _finger_contacts(Ls, finger, c)
                if g <= 0.6]
    return q, contacts


def _cone(n, mu, k=8):
    n = n / np.linalg.norm(n)
    t1 = np.cross(n, [1.0, 0, 0])
    if np.linalg.norm(t1) < 1e-6:
        t1 = np.cross(n, [0, 1.0, 0])
    t1 /= np.linalg.norm(t1)
    t2 = np.cross(n, t1)
    return [n + mu * (math.cos(a) * t1 + math.sin(a) * t2) for a in np.linspace(0, 2 * math.pi, k, endpoint=False)]


def joint_torque_map(q, finger, link, p):
    """3x20 J^T-like map: tau = A @ F where F is the force ON the finger at p (N, world mm)."""
    jf = lay.joint_frames(_q_dict(q))
    names = [s["name"] for s in hk.joint_specs() if s["finger"] == finger]
    order = ("carrier", "proximal", "middle", "distal")
    upto = order.index(link)
    A = np.zeros((20, 3))
    for k, n in enumerate(names[: upto + 1]):
        o, ax = jf[n]
        r = (np.asarray(p) - o) / 1000.0
        # tau = ax . (r x F)  =  (ax x r) . F ... careful: a.(r x F) = F.(a x r)
        A[hk._JOINT_ORDER.index(n)] = np.cross(ax, r)
    return A


def actuator_map():
    """u = Umap @ tau  (N.m), tendon model with 3 mm drums and loop efficiency."""
    M = ht.coupling_matrix("idler") / 1000.0
    eta = ht.loop_efficiency("idler")
    return (DRUM_R_M * np.linalg.inv(M.T)) / eta[:, None]


def equilibrium_lp(q, contacts, c, gdir):
    """contacts: [(finger, link, kind, p, mu)]  incl. palm (finger='palm').
    Returns minimal worst-case utilisation (inf if infeasible)."""
    W = SAFETY_G * BALL_KG * 9.81 * np.asarray(gdir, float) / np.linalg.norm(gdir)
    cols, tau_cols = [], []
    Umap = actuator_map()
    for finger, link, kind, p, mu in contacts:
        n = c - np.asarray(p)
        n /= np.linalg.norm(n)
        A = None if finger == "palm" else joint_torque_map(q, finger, link, p)
        for e in _cone(n, mu):
            cols.append(np.concatenate([e, np.cross((np.asarray(p) - c) / 1000.0, e)]))
            # force on finger is -e (reaction); actuators must hold it
            tau_cols.append(np.zeros(20) if A is None else Umap @ (A @ (-e)))
    if not cols:
        return math.inf, None
    G = np.array(cols).T                      # 6 x m
    U = np.array(tau_cols).T / U_ALLOW        # 20 x m (utilisation per unit lambda)
    m = G.shape[1]
    # variables: lambda (m), s (1).  minimise s ;  -s <= U lambda <= s
    cvec = np.zeros(m + 1)
    cvec[-1] = 1.0
    A_ub = np.vstack([np.hstack([U, -np.ones((20, 1))]), np.hstack([-U, -np.ones((20, 1))])])
    b_ub = np.zeros(40)
    A_eq = np.hstack([G, np.zeros((6, 1))])
    b_eq = -np.concatenate([W, np.zeros(3)])
    res = linprog(cvec, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                  bounds=[(0, None)] * (m + 1), method="highs")
    if not res.success:
        return math.inf, None
    return float(res.x[-1]), res.x[:-1]


GRAVITY = {"palm_up": (0, 0, -1), "palm_down": (0, 0, 1), "fingers_up": (0, -1, 0),
           "fingers_down": (0, 1, 0), "thumb_up": (-1, 0, 0), "thumb_down": (1, 0, 0)}


def grasp(cx, cy, spreads=(0.0, 0.0, 0.0, 0.0), thumb=(0.0, 0.0), squeeze=1.0):
    c = ball_center(cx, cy, squeeze)
    q = [0.0] * 20
    for f, s in zip(("index", "middle", "ring", "little"), spreads):
        q[hk._JOINT_ORDER.index(f"{f}_spread")] = s
    q[hk._JOINT_ORDER.index("thumb_yaw")] = thumb[0]
    q[hk._JOINT_ORDER.index("thumb_opposition")] = thumb[1]
    contacts = []
    # palm contact
    contacts.append(("palm", "palm", "pad", np.array([cx, cy, PALM_PAD_TOP - squeeze * 0]), MU_PAD))
    for f in lay.FINGERS:
        q, cs = close_finger(q, f, c)
        contacts += [(f, link, kind, p, mu) for link, kind, g, p, mu in cs]
    return q, contacts, c


def evaluate(q, contacts, c):
    return {k: equilibrium_lp(q, contacts, c, g)[0] for k, g in GRAVITY.items()}


def self_collision(q, c, tol=0.0):
    """Min gap between capsules of different fingers and between links and the palm top."""
    Ls = lay.links(_q_dict(q))
    caps = {f: link_capsules(Ls, f) for f in lay.FINGERS}
    worst = math.inf
    fs = list(lay.FINGERS)
    for i in range(len(fs)):
        for j in range(i + 1, len(fs)):
            for _, _, a, b, r, _ in caps[fs[i]]:
                for _, _, a2, b2, r2, _ in caps[fs[j]]:
                    d = lay.seg_seg_dist(a, b, a2, b2) - r - r2
                    worst = min(worst, d)
    return worst
