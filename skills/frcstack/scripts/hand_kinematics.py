"""
hand_kinematics.py  --  20-DOF adult-size hand kinematic foundation
====================================================================
DISCLAIMER
----------
All dimensions are agent-selected proposed engineering parameters.
They are NOT measured human anatomy, proven hardware, or fabrication-
ready specifications.  No claims of physical accuracy, collision-
freedom, or mechanical reachability are made.

Coordinate convention
---------------------
- Palm centre  = world XY origin, Z = 0 reference plane
- Palm width   = 90 mm (X), length = 86 mm (Y)
- Fingers extend in +Y; flexion = local +X right-hand rotation.
- All angle inputs are degrees; stored/returned as degrees.

Transform chain (per finger, generic)
--------------------------------------
  base     = T(root) * Rz(base_yaw)        # fixed palm attachment
  carrier  = base   * Rz(q0)               # spread/yaw DOF
  proximal = carrier * T(0,12,0) * Rx(q1)
  middle   = proximal* T(0,L_prox,0) * Rx(q2)
  distal   = middle  * T(0,L_mid,0)  * Rx(q3)
  tip      = distal  * T(0,L_dist,0)

Every joint origin/axis is computed BEFORE its own rotation.
"""

import math, copy, numbers
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CARRIER_LEN = 12  # mm, common to all fingers

_LONG_SEGS = {          # (prox_mm, mid_mm, dist_mm)
    "index":  (38, 25, 18),
    "middle": (42, 27, 20),
    "ring":   (40, 26, 18),
    "little": (30, 20, 16),
}
_LONG_ROOTS = {         # (x, y, z) mm in palm frame
    "index":  (-31, 43, 10),
    "middle": (-10, 43, 10),
    "ring":   ( 11, 43, 10),
    "little": ( 32, 43, 10),
}
_THUMB_ROOT = (-43, -15, 10)
_THUMB_TILT = 55.0          # deg, fixed Rz in palm frame
_THUMB_SEGS = (24, 30, 22)  # (prox, mid, dist) mm

_LONG_LIMITS = {
    "spread":     (-15.0,  15.0),
    "mcp":        (-10.0,  90.0),
    "pip":        (  0.0, 110.0),
    "dip":        (  0.0,  80.0),
}
_THUMB_LIMITS = {
    "yaw":        (-90.0,  35.0),
    "opposition": (-30.0,  90.0),
    "mcp":        (  0.0, 100.0),
    "ip":         (  0.0,  90.0),
}

_FINGER_ORDER = ("index", "middle", "ring", "little", "thumb")

# Generic per-finger table: (root, base_yaw_deg, segs, dof_suffixes, limits)
_FINGER_TABLE = {
    "index":  (_LONG_ROOTS["index"],  0.0,         _LONG_SEGS["index"],  ("spread","mcp","pip","dip"), _LONG_LIMITS),
    "middle": (_LONG_ROOTS["middle"], 0.0,         _LONG_SEGS["middle"], ("spread","mcp","pip","dip"), _LONG_LIMITS),
    "ring":   (_LONG_ROOTS["ring"],   0.0,         _LONG_SEGS["ring"],   ("spread","mcp","pip","dip"), _LONG_LIMITS),
    "little": (_LONG_ROOTS["little"], 0.0,         _LONG_SEGS["little"], ("spread","mcp","pip","dip"), _LONG_LIMITS),
    "thumb":  (_THUMB_ROOT,           _THUMB_TILT, _THUMB_SEGS,          ("yaw","opposition","mcp","ip"), _THUMB_LIMITS),
}

_JOINT_ORDER = [
    "index_spread",  "index_mcp",  "index_pip",  "index_dip",
    "middle_spread", "middle_mcp", "middle_pip", "middle_dip",
    "ring_spread",   "ring_mcp",   "ring_pip",   "ring_dip",
    "little_spread", "little_mcp", "little_pip", "little_dip",
    "thumb_yaw", "thumb_opposition", "thumb_mcp", "thumb_ip",
]

_LINK_SFXS  = ("carrier", "proximal", "middle", "distal")
_JOINT_AXES = ([0,0,1], [1,0,0], [1,0,0], [1,0,0])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _T(x, y, z):
    m = np.eye(4); m[0,3]=x; m[1,3]=y; m[2,3]=z; return m

def _Rx(deg):
    r=math.radians(deg); c,s=math.cos(r),math.sin(r)
    return np.array([[1,0,0,0],[0,c,-s,0],[0,s,c,0],[0,0,0,1]],dtype=float)

def _Rz(deg):
    r=math.radians(deg); c,s=math.cos(r),math.sin(r)
    return np.array([[c,-s,0,0],[s,c,0,0],[0,0,1,0],[0,0,0,1]],dtype=float)

def _origin(m):  return m[:3,3].tolist()
def _axw(m,ax):  return (m[:3,:3] @ np.array(ax,dtype=float)).tolist()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def hand_dimensions() -> dict:
    """
    Return independent dict of proposed hand geometry constants.

    Keys: palm_width_mm, palm_length_mm, carrier_length_mm, fingers.
    fingers maps each finger name to {root_mm, base_yaw_deg, lengths_mm}.
    lengths_mm = [prox, mid, dist].  Caller mutation cannot affect later calls.
    """
    d = {
        "palm_width_mm":    90,
        "palm_length_mm":   86,
        "carrier_length_mm": _CARRIER_LEN,
        "fingers": {
            f: {
                "root_mm":      list(root),
                "base_yaw_deg": yaw,
                "lengths_mm":   list(segs),
            }
            for f, (root, yaw, segs, _, _lim) in _FINGER_TABLE.items()
        },
    }
    return copy.deepcopy(d)


def joint_specs() -> list:
    """
    Return a list of 20 joint specification dicts (independent deep copies).

    Keys: name, finger, parent_link, child_link, axis_local, limits_deg.
    Chain per finger: palm->carrier->proximal->middle->distal.
    """
    # parent order mirrors _LINK_SFXS: carrier parent=palm, proximal=carrier,
    # middle=proximal, distal=middle.
    specs = []
    for finger in _FINGER_ORDER:
        _root, _yaw, segs, dofs, lims = _FINGER_TABLE[finger]
        parents = ["palm", f"{finger}_carrier", f"{finger}_proximal", f"{finger}_middle"]
        for i, (dof, child_sfx, parent_link, axis) in enumerate(
                zip(dofs, _LINK_SFXS, parents, _JOINT_AXES)):
            specs.append(dict(
                name=f"{finger}_{dof}",
                finger=finger,
                parent_link=parent_link,
                child_link=f"{finger}_{child_sfx}",
                axis_local=list(axis),
                limits_deg=list(lims[dof]),
            ))
    return copy.deepcopy(specs)


def _coerce_angle(v, label):
    """Strict coercion: numbers.Real only, no bool/np.bool_, OverflowError->ValueError."""
    if isinstance(v, (bool, np.bool_)):
        raise TypeError(f"{label}: bool not accepted as angle")
    if isinstance(v, str):
        raise TypeError(f"{label}: str not accepted as angle")
    if not isinstance(v, numbers.Real):
        raise TypeError(f"{label}: expected numeric scalar, got {type(v).__name__}")
    try:
        f = float(v)
    except OverflowError:
        raise ValueError(f"{label}: value overflows float")
    if not math.isfinite(f):
        raise ValueError(f"{label}: non-finite value {v}")
    return f


def _validate_angles(angles_deg):
    """Accept dict(20 keys) or flat list/tuple/1-D ndarray(20). Returns {name:float}."""
    if isinstance(angles_deg, dict):
        if set(angles_deg.keys()) != set(_JOINT_ORDER):
            extra   = set(angles_deg.keys()) - set(_JOINT_ORDER)
            missing = set(_JOINT_ORDER) - set(angles_deg.keys())
            raise ValueError(f"Wrong keys. extra={extra} missing={missing}")
        out = {k: _coerce_angle(v, k) for k, v in angles_deg.items()}
    elif isinstance(angles_deg, (list, tuple, np.ndarray)):
        if isinstance(angles_deg, np.ndarray) and angles_deg.ndim != 1:
            raise ValueError(f"ndarray must be 1-D, got shape {angles_deg.shape}")
        if len(angles_deg) != 20:
            raise ValueError(f"Sequence must have 20 elements, got {len(angles_deg)}")
        out = {name: _coerce_angle(angles_deg[i], f"[{i}]")
               for i, name in enumerate(_JOINT_ORDER)}
    else:
        raise TypeError(f"angles_deg must be dict, list, tuple, or 1-D ndarray; "
                        f"got {type(angles_deg).__name__}")
    # Limit check (no clipping)
    specs_map = {s["name"]: s for s in joint_specs()}
    for name, val in out.items():
        lo, hi = specs_map[name]["limits_deg"]
        if not (lo <= val <= hi):
            raise ValueError(f"Joint '{name}'={val:.3f} outside limits [{lo},{hi}]")
    return out


def forward_kinematics(angles_deg) -> dict:
    """
    Compute FK for all 20 DOFs.

    Parameters
    ----------
    angles_deg : dict (20 keys) or flat list/tuple/1-D ndarray (20 elements).

    Returns
    -------
    dict: links (palm + 20 transforms), joints (origin_mm + axis_world),
          tips_mm (per finger), angles_deg (independent copy).
    """
    ang = _validate_angles(angles_deg)
    links  = {"palm": np.eye(4)}
    joints = {}
    tips   = {}

    rot_fns = [_Rz, _Rx, _Rx, _Rx]

    for finger in _FINGER_ORDER:
        root, base_yaw, segs, dofs, _lim = _FINGER_TABLE[finger]
        seg_lengths = (_CARRIER_LEN,) + segs   # (8, prox, mid, dist)

        T_prev = _T(*root) @ _Rz(base_yaw)     # fixed base before joint0

        for i, (dof, child_sfx, axis) in enumerate(zip(dofs, _LINK_SFXS, _JOINT_AXES)):
            # joint origin is current T_prev (already offset from previous step)
            jname = f"{finger}_{dof}"
            joints[jname] = {
                "origin_mm":  _origin(T_prev),
                "axis_world": _axw(T_prev, axis),
            }
            q = ang[jname]
            T_link = T_prev @ rot_fns[i](q)
            links[f"{finger}_{child_sfx}"] = T_link

            # advance T_prev by this link's segment length (ready for next joint)
            if i < len(segs):   # segs has 3 elements; seg_lengths[i] used below
                T_prev = T_link @ _T(0, seg_lengths[i], 0)
            # Note: after distal (i=3), T_prev not reused; tip computed separately

        # tip = distal @ T(0, Ldist, 0)  i.e. T_link @ T(0, segs[2], 0)
        tips[finger] = _origin(T_link @ _T(0, segs[2], 0))

    return {
        "links":      links,
        "joints":     joints,
        "tips_mm":    tips,
        "angles_deg": copy.deepcopy(ang),
    }


def pose(name: str) -> dict:
    """
    Return a fresh dict of 20 joint angles (degrees) for a named pose.
    Poses: open, partial, closed.
    NOTE: poses are design targets; reachability is NOT validated.
    """
    _POSES = {
        "open": {j: 0.0 for j in _JOINT_ORDER},
        "partial": {
            **{f"{f}_spread": 0.0  for f in ("index","middle","ring","little")},
            **{f"{f}_mcp":   35.0  for f in ("index","middle","ring","little")},
            **{f"{f}_pip":   45.0  for f in ("index","middle","ring","little")},
            **{f"{f}_dip":   20.0  for f in ("index","middle","ring","little")},
            "thumb_yaw": -35.0, "thumb_opposition": 25.0,
            "thumb_mcp": 30.0,  "thumb_ip": 20.0,
        },
        "closed": {
            **{f"{f}_spread": 0.0  for f in ("index","middle","ring","little")},
            **{f"{f}_mcp":   70.0  for f in ("index","middle","ring","little")},
            **{f"{f}_pip":   90.0  for f in ("index","middle","ring","little")},
            **{f"{f}_dip":   60.0  for f in ("index","middle","ring","little")},
            "thumb_yaw": -50.0, "thumb_opposition": 45.0,
            "thumb_mcp": 60.0,  "thumb_ip": 45.0,
        },
        # Thumb-index pad pinch.  Found by constrained search (capsule clearance
        # proxy) then checked with exact B-rep all-pair Booleans: 0 interference,
        # tip gap ~10.5 mm, each distal pad normal within ~12 deg of the pinch
        # line.  Other fingers stay open.  Sampled pose, NOT a grasp-force test.
        "pinch": {
            **{j: 0.0 for j in _JOINT_ORDER},
            "index_spread": -12.0, "index_mcp": 28.0, "index_pip": 81.0, "index_dip": 77.0,
            "thumb_yaw": -67.0, "thumb_opposition": 20.0,
            "thumb_mcp": 3.0, "thumb_ip": 3.0,
        },
    }
    if name not in _POSES:
        raise ValueError(f"Unknown pose '{name}'. Available: {list(_POSES.keys())}")
    return dict(_POSES[name])
