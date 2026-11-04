"""
ollie_layout.py -- OLLIE (walk / skate / crawl humanoid) layout on top of the humanoid skeleton.

Changes vs the $700 humanoid: deeper hip flexion and knee bend for crawling, more neck tilt so the
head can look forward while crawling, a shorter sole (x -40..78) so the heel wheels can touch down,
and one N20-driven heel wheel per foot (skate mode, balanced like a two-wheeled robot).
All dimensions mm, zero pose = standing straight, X forward, Y left, Z up.  PROPOSED DESIGN.
"""
from __future__ import annotations

import humanoid_layout as L

RANGES = {
    **{f"hip_pitch_{s}": (-90, 30) for s in "LR"},
    **{f"knee_{s}": (0, 120) for s in "LR"},
    "neck_tilt": (-45, 30),
}
FOOT_X = (-40.0, 78.0)

# heel wheel (left foot, zero pose; mirror y for the right foot).  Supported on BOTH sides: the N20
# shaft drives the inner hub face, an MR63ZZ bearing in the outer fork plate carries the outer face.
WHEEL_X, WHEEL_Z, WHEEL_R = -62.0, 24.0, 22.0
WHEEL_Y = (49.0, 61.0)                   # hub faces (tire 49.5..60.5)
HUB_R = 16.0
# N20-size micro metal gearmotor with back encoder (e.g. Pololu #5192, 150:1 HPCB 6 V): 10 x 12 mm
# gearbox, 9 mm long 3 mm D shaft, ~34 mm body incl. encoder.
N20_Y = (12.0, 46.0)
N20_X = (WHEEL_X - 6.0, WHEEL_X + 6.0)
N20_Z = (WHEEL_Z - 5.0, WHEEL_Z + 5.0)
N20_SHAFT = (1.5, 46.0, 55.0)            # radius, y0, y1
FORK_Y = (62.0, 65.0)
N20_MASS_G = 10.5
N20_STALL_NM = 2.0 * 0.0980665           # Pololu #5192: 2.0 kg.cm extrapolated stall @ 6 V
N20_RPM = 220.0                          # Pololu #5192: 220 rpm no-load @ 6 V
SKATE_TILT = -15.0                       # foot pitch in skate mode (negative = toes up)

WHEEL_JOINTS = {
    f"wheel_{s}": dict(parent=f"foot_{s}", child=f"wheel_{s}", axis=(0, 1, 0),
                       p=(WHEEL_X, sign * sum(WHEEL_Y) / 2, WHEEL_Z), kind="n20", range=None)
    for s, sign in (("L", 1), ("R", -1))
}

_prev = None
NECK_TILT_P = (2.0, 11.0, 748.0)         # raised so the helmet clears the pan disc over the tilt range


def apply():
    """Install OLLIE ranges into humanoid_layout (idempotent)."""
    global _prev
    if _prev is None:
        _prev = L.configure(RANGES, FOOT_X)
        _prev["tilt_p"] = L.JOINTS["neck_tilt"]["p"]
        L.JOINTS["neck_tilt"]["p"] = NECK_TILT_P


def revert():
    global _prev
    if _prev is not None:
        L.JOINTS["neck_tilt"]["p"] = _prev["tilt_p"]
        L.restore(_prev)
        _prev = None


def skate_speed_mps() -> float:
    import math
    return N20_RPM / 60.0 * 2 * math.pi * WHEEL_R * 1e-3
