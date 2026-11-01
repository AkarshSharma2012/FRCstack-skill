"""
humanoid_layout.py -- joint layout, bracket parameters, poses and quasi-static torque model for the
$700 bus-servo humanoid (16x Waveshare ST3215 + 4x Waveshare SC09).

World frame (zero pose, standing straight): X forward, Y left, Z up, floor at Z = 0 (mm).
Each joint rotates its child link about a fixed world axis through p (zero-pose frame); a link's
posed placement is the product of its ancestor joint transforms.  The servo frame J of every joint
is given by (p, jx, jz) -- see humanoid_brackets for the J-frame definition taken from the vendor STEP.
PROPOSED DESIGN -- not built or tested.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

import humanoid_brackets as hb

# --------------------------------------------------------------------------- vendor facts
ST_MASS_G = 69.0                       # Waveshare ST3215 (waveshare / servodatabase)
ST_STALL_NM = 2.94 * 11.1 / 12.0       # 30 kg.cm @ 12 V, scaled to 3S nominal 11.1 V -> 2.72 N.m
ST_CONT_NM = ST_STALL_NM / 3.0         # ASSUMPTION: sustained hold ~1/3 stall (not published)
ST_KT = 1.08                           # N.m/A  (11 kg.cm/A, retailer datasheet)
SC_MASS_G = 21.0                       # Waveshare SC09
SC_STALL_NM = 2.3 * 0.0980665
SC_RATED_NM = 0.7 * 0.0980665

# --------------------------------------------------------------------------- dimensions (mm)
LEG_Y = 45.0
X_HIP_YR = 20.0
X_ANKLE_ROLL = -12.0
Z_ANKLE_ROLL = 33.0
Z_ANKLE_PITCH = 99.0
Z_KNEE = 219.0
Z_HIP_PITCH = 339.0
Z_HIP_ROLL = 401.0
Z_HIP_YAW = 463.0
Z_PELVIS = 487.0                       # pelvis (torso bottom) plate underside
PELVIS_T = 6.0
Z_TOP = 677.0                          # torso top plate underside
TOP_T = 6.0
TORSO_HX, TORSO_HY, WALL = 45.0, 75.0, 2.4
SHOULDER_Y = 57.5                      # case pokes 1.4 mm through a side-wall window; horn face y 76.125
Z_SHOULDER = 660.0
ARM_PLATE_Y = (76.125, 79.125)
ELBOW_Y = 103.0
Z_ELBOW = 560.0
GRIP_P = (18.0, 118.0, 478.0)          # gripper SC09 shaft-face point (left side; y mirrored)
NECK_PAN_P = (0.0, 0.0, Z_TOP + TOP_T + 22.0)
NECK_TILT_P = (2.0, 11.0, 735.0)
FOOT_X = (-62.0, 78.0)
FOOT_HY = 38.0
SOLE_T = 3.0

LEG_JOINTS = ("hip_yaw", "hip_roll", "hip_pitch", "knee", "ankle_pitch", "ankle_roll")


def _spec():
    t = {}
    for side, s in (("L", 1), ("R", -1)):
        y = LEG_Y * s

        def j(name, **kw):
            kw.setdefault("kind", "st")
            kw.setdefault("mount", "u")
            t[f"{name}_{side}"] = kw
        j("hip_yaw", parent="base", child=f"hip_yaw_{side}", axis=(0, 0, 1), p=(X_HIP_YR, y, Z_HIP_YAW),
          jx=(-1, 0, 0), jz=(0, 0, 1), body="base", bridge=(1, 0, 0), range=(-30, 30))
        j("hip_roll", parent=f"hip_yaw_{side}", child=f"hip_cross_{side}", axis=(1, 0, 0),
          p=(X_HIP_YR, y, Z_HIP_ROLL), jx=(0, 0, -1), jz=(1, 0, 0), body=f"hip_cross_{side}",
          bridge=(0, 0, 1), range=(-25, 25))
        j("hip_pitch", parent=f"hip_cross_{side}", child=f"thigh_{side}", axis=(0, 1, 0),
          p=(0, y, Z_HIP_PITCH), jx=(-1, 0, 0), jz=(0, s, 0), body=f"hip_cross_{side}",
          bridge=(0, 0, -1), range=(-70, 30))
        j("knee", parent=f"thigh_{side}", child=f"shin_{side}", axis=(0, 1, 0), p=(0, y, Z_KNEE),
          jx=(0, 0, 1), jz=(0, s, 0), body=f"thigh_{side}", bridge=(0, 0, -1), range=(0, 100))
        j("ankle_pitch", parent=f"shin_{side}", child=f"ankle_cross_{side}", axis=(0, 1, 0),
          p=(0, y, Z_ANKLE_PITCH), jx=(-1, 0, 0), jz=(0, s, 0), body=f"ankle_cross_{side}",
          bridge=(0, 0, 1), range=(-45, 30))
        j("ankle_roll", parent=f"ankle_cross_{side}", child=f"foot_{side}", axis=(1, 0, 0),
          p=(X_ANKLE_ROLL, y, Z_ANKLE_ROLL), jx=(0, 0, 1), jz=(1, 0, 0), body=f"ankle_cross_{side}",
          bridge=(0, 0, -1), range=(-25, 25))
        j("shoulder", parent="base", child=f"upper_arm_{side}", axis=(0, 1, 0),
          p=(0, SHOULDER_Y * s, Z_SHOULDER), jx=(0, 0, -1), jz=(0, s, 0), body="base", mount="horn",
          range=(-180, 60))
        j("elbow", parent=f"upper_arm_{side}", child=f"forearm_{side}", axis=(0, 1, 0),
          p=(0, ELBOW_Y * s, Z_ELBOW), jx=(0, 0, 1), jz=(0, s, 0), body=f"upper_arm_{side}",
          bridge=(0, 0, -1), range=(-100, 0))
        j("gripper", parent=f"forearm_{side}", child=f"finger_{side}", axis=(0, 1, 0),
          p=(GRIP_P[0], GRIP_P[1] * s, GRIP_P[2]), jx=(0, 0, 1), jz=(0, s, 0), body=f"forearm_{side}",
          kind="sc", mount="sc", range=(0, 28))
    t["neck_pan"] = dict(parent="base", child="neck", axis=(0, 0, 1), p=NECK_PAN_P, jx=(1, 0, 0),
                         jz=(0, 0, 1), body="base", kind="sc", mount="sc", range=(-90, 90))
    t["neck_tilt"] = dict(parent="neck", child="head", axis=(0, 1, 0), p=NECK_TILT_P, jx=(0, 0, -1),
                          jz=(0, 1, 0), body="neck", kind="sc", mount="sc", range=(-30, 30))
    return t


JOINTS = _spec()
LINKS = ["base"] + sorted({j["child"] for j in JOINTS.values()})


def servo_frame(jn) -> np.ndarray:
    j = JOINTS[jn]
    x, z = np.array(j["jx"], float), np.array(j["jz"], float)
    T = np.eye(4)
    T[:3, 0], T[:3, 1], T[:3, 2], T[:3, 3] = x, np.cross(z, x), z, j["p"]
    return T


def bracket_link(jn):
    j = JOINTS[jn]
    return j["child"] if j["body"] == j["parent"] else j["parent"]


def alpha_range(jn):
    """Range of the bracket's rotation relative to the servo case about J z (degrees)."""
    j = JOINTS[jn]
    k = float(np.dot(j["axis"], j["jz"])) * (1 if j["body"] == j["parent"] else -1)
    a, b = sorted((j["range"][0] * k, j["range"][1] * k))
    return np.arange(a, b + 1e-9, 1.0)


@lru_cache(maxsize=None)
def bracket_params(jn):
    """(phi, R, xc) for a U-bracket joint; (None, None, 13.5) for horn / SC09 mounts."""
    j = JOINTS[jn]
    if j["mount"] != "u":
        return None, None, 13.5
    T = servo_frame(jn)
    d = np.array(j["bridge"], float)
    phi = math.degrees(math.atan2(d @ T[:3, 1], d @ T[:3, 0]))
    R, xc = hb.solve(phi, alpha_range(jn))
    return phi, R, xc


# --------------------------------------------------------------------------- kinematics
def rot(axis, deg) -> np.ndarray:
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def joint_tf(jn, deg) -> np.ndarray:
    p = np.asarray(JOINTS[jn]["p"], float)
    T = np.eye(4)
    T[:3, :3] = rot(JOINTS[jn]["axis"], deg)
    T[:3, 3] = p - T[:3, :3] @ p
    return T


_CHILD_JOINT = {j["child"]: n for n, j in JOINTS.items()}


def link_transforms(q: dict) -> dict:
    out = {"base": np.eye(4)}

    def tf(ln):
        if ln not in out:
            jn = _CHILD_JOINT[ln]
            out[ln] = tf(JOINTS[jn]["parent"]) @ joint_tf(jn, q.get(jn, 0.0))
        return out[ln]
    for ln in LINKS:
        tf(ln)
    return out


def both(**kw) -> dict:
    return {f"{k}_{s}": v for k, v in kw.items() for s in ("L", "R")}


def in_range(q) -> list:
    bad = []
    for jn, v in q.items():
        lo, hi = sorted(JOINTS[jn]["range"])
        if not lo - 1e-6 <= v <= hi + 1e-6:
            bad.append((jn, v))
    return bad


def lift(side, hip=-40.0, knee=80.0):
    return {f"hip_pitch_{side}": hip, f"knee_{side}": knee, f"ankle_pitch_{side}": -(hip + knee)}


def poses(single_support_roll=None) -> dict:
    """name -> (q, support).  support None = kinematic-only (not a standing pose)."""
    crouch = both(hip_pitch=-20, knee=40, ankle_pitch=-20)
    r = single_support_roll if single_support_roll is not None else 0.0
    ss = dict(crouch)
    ss.update(both(hip_roll=r, ankle_roll=-r))
    ss.update(lift("R", -45, 80))
    leg_a = {"hip_yaw": 30, "hip_roll": 25, "hip_pitch": -70, "knee": 100, "ankle_pitch": -30, "ankle_roll": -25}
    leg_b = {"hip_yaw": -30, "hip_roll": 25, "hip_pitch": 30, "knee": 0, "ankle_pitch": 30, "ankle_roll": 25}
    ext = {}
    for name, side, leg, arm, neck in (("extremes_a", "L", leg_a, (-180, -100, 28), (90, 30)),
                                       ("extremes_b", "R", leg_b, (60, 0, 0), (-90, -30))):
        q = {}
        s = 1 if side == "L" else -1
        for k, v in leg.items():
            q[f"{k}_{side}"] = v if k in ("hip_pitch", "knee", "ankle_pitch") else s * v
        if name == "extremes_b":          # swing leg lifted before a backward extension
            q.update(lift("L", -45, 80))
        q.update(both(shoulder=arm[0], elbow=arm[1], gripper=arm[2]))
        q.update(neck_pan=neck[0], neck_tilt=neck[1])
        ext[name] = (q, None)
    return {
        "stand": ({}, "both"),
        "crouch": (crouch, "both"),
        "single_support_left": (ss, "L"),
        "squat": (both(hip_pitch=-45, knee=90, ankle_pitch=-45), "both"),
        "arms_forward_grip": (dict(crouch, **both(shoulder=-90, elbow=-30, gripper=20), neck_pan=30,
                                   neck_tilt=20), "both"),
        **ext,
    }


def balance_roll(link_mass, link_com, step=0.25) -> float:
    """Hip/ankle roll (deg) that puts the COM over the centre of the left (support) foot."""
    best = None
    for r in np.arange(-25.0, 25.0 + 1e-9, step):
        q, _ = poses(r)["single_support_left"]
        C, _, Tl = com(q, link_mass, link_com)
        err = abs(C[1] - sole_points(Tl, "L")[:, 1].mean())
        if best is None or err < best[0]:
            best = (err, float(r))
    return best[1]


# --------------------------------------------------------------------------- statics
@lru_cache(maxsize=None)
def descendants(jn) -> frozenset:
    out = set()
    for ln in LINKS[1:]:
        cur = ln
        while cur != "base":
            if _CHILD_JOINT[cur] == jn:
                out.add(ln)
                break
            cur = JOINTS[_CHILD_JOINT[cur]]["parent"]
    return frozenset(out)


def sole_points(Tl, side) -> np.ndarray:
    s = 1 if side == "L" else -1
    pts = [(x, s * LEG_Y + dy, 0.0) for x in FOOT_X for dy in (-FOOT_HY, FOOT_HY)]
    return np.array([(Tl[f"foot_{side}"] @ np.array([*p, 1.0]))[:3] for p in pts])


def com(q, link_mass, link_com):
    Tl = link_transforms(q)
    c = {ln: (Tl[ln] @ np.array([*link_com[ln], 1.0]))[:3] for ln in link_mass}
    M = sum(link_mass.values())
    return sum(link_mass[ln] * c[ln] for ln in link_mass) / M, c, Tl


def support_margin(C, Tl, feet) -> float:
    """Signed distance (mm) of the COM ground projection inside the support polygon (>0 = inside)."""
    from scipy.spatial import ConvexHull  # noqa: PLC0415
    pts = np.vstack([sole_points(Tl, k)[:, :2] for k in feet])
    h = ConvexHull(pts)
    return float(min(-(eq[:2] @ C[:2] + eq[2]) for eq in h.equations))


def statics(q, support, link_mass, link_com, g=9.81) -> dict:
    """Quasi-static joint torques (N.m) with the ground reaction at the COM projection.
    support: 'L', 'R' or 'both' (double support split by the lever rule along Y)."""
    C, c, Tl = com(q, link_mass, link_com)
    M = sum(link_mass.values()) * 1e-3
    feet = ("L", "R") if support == "both" else (support,)
    fy = {k: sole_points(Tl, k)[:, 1].mean() for k in feet}
    if len(feet) == 2:
        w = float(np.clip((C[1] - fy["R"]) / (fy["L"] - fy["R"]), 0, 1))
        frac = {"L": w, "R": 1 - w}
    else:
        frac = {feet[0]: 1.0}
    cop = {k: np.array([C[0], C[1] if len(feet) == 1 else fy[k], sole_points(Tl, k)[:, 2].mean()])
           for k in feet}
    tau = {}
    for jn, j in JOINTS.items():
        T = Tl[j["parent"]]
        p = (T @ np.array([*j["p"], 1.0]))[:3]
        a = T[:3, :3] @ np.asarray(j["axis"], float)
        kids = descendants(jn)
        t = sum(a @ np.cross((c[ln] - p) * 1e-3, [0, 0, -link_mass[ln] * 1e-3 * g]) for ln in kids)
        for k in feet:
            if f"foot_{k}" in kids:
                t += a @ np.cross((cop[k] - p) * 1e-3, [0, 0, frac[k] * M * g])
        tau[jn] = float(t)
    return {"torque_nm": tau, "com_mm": [round(v, 1) for v in C], "mass_g": round(M * 1e3),
            "support_margin_mm": round(support_margin(C, Tl, feet), 1), "support": support}
