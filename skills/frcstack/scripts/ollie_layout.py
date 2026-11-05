"""
ollie_layout.py -- OLLIE v2 layout (walk / skate / crawl humanoid) on the bus-servo skeleton.

v2 vs v1: human proportions (thigh 140, shin 140, upper arm 120, forearm 100 mm; hips at 46 % of height),
an aluminium pelvis plate (PELVIS_T 4), a longer pointed foot with the inner toe forward, and the
crawl / skate contact geometry defined here so CAD, statics and the MuJoCo export all agree.
Importing this module installs the v2 dimensions into humanoid_layout (idempotent).
All dimensions mm, zero pose = standing straight, X forward, Y left, Z up.  PROPOSED DESIGN.
"""
from __future__ import annotations

import math

import humanoid_layout as L

VERSION = "v2"
DIMS = dict(Z_KNEE=239.0, Z_HIP_PITCH=379.0, Z_HIP_ROLL=441.0, Z_HIP_YAW=503.0, Z_PELVIS=527.0, PELVIS_T=6.0,
            Z_TOP=715.0, Z_SHOULDER=698.0, Z_ELBOW=578.0, GRIP_P=(18.0, 118.0, 478.0),
            NECK_PAN_P=(0.0, 0.0, 743.0), NECK_TILT_P=(2.0, 11.0, 786.0))
RANGES = {
    **{f"hip_pitch_{s}": (-90, 30) for s in "LR"},
    **{f"knee_{s}": (0, 120) for s in "LR"},
    "neck_tilt": (-45, 30),
}
FOOT_X = (-40.0, 90.0)
AL_T = 3.2                               # 1/8 in 6061-T6 sheet (CNC routed): bracket plates, foot + shoulder plates
# left-foot plan (x, y): inner toe forward like a human foot, outer toe corner cut
FOOT_PLAN = [(-40.0, 7.0), (82.0, 7.0), (90.0, 20.0), (90.0, 48.0), (72.0, 83.0), (-40.0, 83.0)]

# crawl contacts (left side; mirror y for the right)
KNEE_PAD = (23.0, 30.0, 28.0, 62.0, -74.0, -8.0)         # x0 x1 y0 y1, z relative to the knee axis (TPU)


def paw_box():
    px, _, pz = L.GRIP_P
    return (px - 52, px - 42, 98.0, 126.0, pz - 68, pz - 58)


# heel wheel (left foot, zero pose).  Supported on BOTH sides: the N20 shaft drives the inner hub face,
# an MR63ZZ bearing in the outer fork plate carries the outer face.
WHEEL_X, WHEEL_Z, WHEEL_R = -62.0, 24.0, 22.0
WHEEL_Y = (49.0, 61.0)
HUB_R = 16.0
N20_Y = (12.0, 46.0)
N20_X = (WHEEL_X - 6.0, WHEEL_X + 6.0)
N20_Z = (WHEEL_Z - 5.0, WHEEL_Z + 5.0)
N20_MASS_G = 10.5
N20_STALL_NM = 2.0 * 0.0980665           # Pololu #5192: 2.0 kg.cm extrapolated stall @ 6 V
N20_RPM = 220.0                          # Pololu #5192: 220 rpm no-load @ 6 V
SKATE_TILT = -15.0                       # foot pitch in skate mode (negative = toes up)

WHEEL_JOINTS = {
    f"wheel_{s}": dict(parent=f"foot_{s}", child=f"wheel_{s}", axis=(0, 1, 0),
                       p=(WHEEL_X, sign * sum(WHEEL_Y) / 2, WHEEL_Z), kind="n20", range=None)
    for s, sign in (("L", 1), ("R", -1))
}

# optional strength upgrade: Feetech STS3250 (50 kg.cm @ 12 V, same 45.2 x 24.7 x 35 mm case and horn as
# the ST3215, so it bolts into the same brackets) on the hip-roll, hip-pitch and knee joints
STS3250_STALL_NM = 50 * 0.0980665 * 11.1 / 12.0
STRONG_JOINTS = tuple(f"{j}_{s}" for j in ("hip_roll", "hip_pitch", "knee") for s in "LR")


def stall_nm(jn, strong=False) -> float:
    j = L.JOINTS[jn]
    if j["kind"] == "sc":
        return L.SC_STALL_NM
    return STS3250_STALL_NM if strong and jn in STRONG_JOINTS else L.ST_STALL_NM


_applied = False


def apply():
    """Install the v2 dimensions and OLLIE ranges into humanoid_layout (idempotent)."""
    global _applied
    if _applied:
        return
    for k, v in DIMS.items():
        setattr(L, k, v)
    new = L._spec()
    L.JOINTS.clear()
    L.JOINTS.update(new)
    L.configure(RANGES, FOOT_X)
    L.descendants.cache_clear()
    _applied = True


def skate_speed_mps() -> float:
    return N20_RPM / 60.0 * 2 * math.pi * WHEEL_R * 1e-3


apply()
