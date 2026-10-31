"""
hand_tendons.py  --  Pull-pull tendon actuation model for the proposed 20-DOF hand.
===================================================================================
ANALYTICAL MODEL ONLY.  No FEA, no friction measurement, no prototype.

Architecture (agent design choice, documented in .implementation):
  * One forearm actuator per joint (20 total) drives ONE closed pull-pull loop:
    flexor strand + extensor strand wrapped in opposite senses on one spool drum.
    The loop is pre-tensioned by an in-line tensioner, so each actuator drives
    its joint in BOTH directions (no return spring needed).
  * Loop j terminates on the drive pulley of joint j (on the child link).
  * Loop j crosses every joint PROXIMAL to j in the same finger chain.  Each
    crossing contributes c_ij * q_i of spool displacement.  Two routing variants:
      - "idler":   crossing on an idler coaxial with joint i  -> c_ij = r_i
      - "sheath":  crossing inside a Bowden sheath on the axis -> c_ij ~ 0
  * Linear small-strain model:   R_s * theta = M q     (theta actuator rad, q joint rad)
    M is block lower-triangular per finger with M_jj = r_j > 0, so
    det(M) = prod(r_j) != 0  -> rank 20 independent of crossing routing.
  * Statics (lossless):  tau = M^T dT,  actuator torque u = R_s dT
                         -> u = R_s * M^-T tau.  Capstan friction applied as a
    per-loop efficiency eta_j = exp(-mu * total_wrap_j), so u_j /= eta_j.

Manufacturer data (https://emanual.robotis.com/docs/en/dxl/x/xl330-m288/,
read 2026-10-31): stall torque 0.52 N.m at 5.0 V / 1.47 A; no-load 103 rpm at
5.0 V; 4096 pulse/rev; position mode 0..360 deg; extended multi-turn mode.
The page publishes NO continuous torque rating; ALLOWABLE_FRACTION below is an
explicit design assumption, not a vendor figure.
"""
from __future__ import annotations

import math
import numpy as np

from hand_kinematics import _JOINT_ORDER, joint_specs, forward_kinematics

# ---------------------------------------------------------------------------
# Design parameters (agent-selected, all explicit)
# ---------------------------------------------------------------------------
XL330_STALL_NM_5V = 0.52          # vendor
XL330_NO_LOAD_RPM_5V = 103.0      # vendor
XL330_STALL_A_5V = 1.47           # vendor
ALLOWABLE_FRACTION = 0.30         # ASSUMPTION: sustained torque <= 30 % of stall
# Per-actuator spool radius is SIZED so the worst-case span uses ~TARGET_SPAN of
# the single-turn absolute position range (0..360 deg), clamped to a printable
# drum.  Smaller drums trade travel for line tension / fingertip force.
TARGET_SPAN_DEG = 300.0
SPOOL_R_MIN_MM = 3.0              # ASSUMPTION: >= ~10x 0.3 mm line dia, printable hub
SPOOL_R_MAX_MM = 9.0              # drum flange must clear M2 heads on 12 mm PCD
MU_GUIDE = 0.15                   # ASSUMPTION: UHMWPE line sliding on PTFE-lined guides
MU_SHEATH = 0.15                  # ASSUMPTION: same pair inside PTFE sheath
ETA_IDLER = 0.97                  # ASSUMPTION: rolling idler on steel pin, per crossing
FOREARM_ROUTING_WRAP_RAD = math.pi  # ASSUMPTION: two 90 deg sliding bends forearm->palm
SAFETY_FACTOR_LINE = 3.0          # ASSUMPTION: line break load / working tension

# Drive-pulley radii (mm).  Tongue cylinder is R5.5, so a 1.0-2.5 mm deep groove
# gives these radii without breaking through the R1.2 pin bore.
PULLEY_R_MM = {
    "spread": 4.0, "mcp": 4.5, "pip": 4.0, "dip": 3.5,
    "yaw": 4.0, "opposition": 4.5, "ip": 3.5,
}
_THUMB_PULLEY = {"yaw": 4.0, "opposition": 4.5, "mcp": 4.0, "ip": 3.5}

ROUTINGS = ("idler", "sheath")


def _pulley_radius(name: str) -> float:
    finger, dof = name.split("_", 1)
    if finger == "thumb":
        return _THUMB_PULLEY[dof]
    return PULLEY_R_MM[dof]


def _chain() -> dict:
    """finger -> ordered list of joint names (proximal -> distal)."""
    out: dict = {}
    for s in joint_specs():
        out.setdefault(s["finger"], []).append(s["name"])
    return out


def _crossing_coeff(crossed: str, routing: str) -> float:
    """Spool displacement per rad of a crossed proximal joint (mm/rad)."""
    if routing == "idler":
        return _pulley_radius(crossed)
    if routing == "sheath":
        # Spread/yaw axes are vertical: a strand passing through the axis has
        # zero first-order length change.  Flexion crossings inside an on-axis
        # sheath likewise ~0 (second-order sheath bending ignored).
        return 0.0
    raise ValueError(f"unknown routing {routing!r}; expected one of {ROUTINGS}")


def coupling_matrix(routing: str = "idler") -> np.ndarray:
    """M (20x20, mm/rad): spool arc length = M @ q.  Row = actuator/loop, col = joint."""
    idx = {n: i for i, n in enumerate(_JOINT_ORDER)}
    M = np.zeros((20, 20))
    for joints in _chain().values():
        for k, j in enumerate(joints):
            M[idx[j], idx[j]] = _pulley_radius(j)
            for crossed in joints[:k]:
                M[idx[j], idx[crossed]] = _crossing_coeff(crossed, routing)
    return M


def actuation_rank(routing: str = "idler") -> dict:
    M = coupling_matrix(routing)
    sv = np.linalg.svd(M, compute_uv=False)
    tol = sv.max() * 20 * np.finfo(float).eps
    return {
        "routing": routing,
        "rank": int((sv > tol).sum()),
        "sigma_min_mm_per_rad": float(sv.min()),
        "sigma_max_mm_per_rad": float(sv.max()),
        "condition_number": float(sv.max() / sv.min()),
        "lower_triangular_per_finger": bool(_is_chain_lower_triangular(M)),
    }


def _is_chain_lower_triangular(M: np.ndarray) -> bool:
    """No loop may depend on a joint distal to its own, nor on another finger."""
    idx = {n: i for i, n in enumerate(_JOINT_ORDER)}
    chains = _chain()
    finger_of = {j: f for f, js in chains.items() for j in js}
    for r_name, r in idx.items():
        own = chains[finger_of[r_name]]
        allowed = set(own[: own.index(r_name) + 1])
        for c_name, c in idx.items():
            if c_name not in allowed and abs(M[r, c]) > 0:
                return False
    return True


def _strand_travel_mm(M: np.ndarray) -> np.ndarray:
    """Worst-case strand travel per loop over the joint-limit box (mm)."""
    lims = {s["name"]: s["limits_deg"] for s in joint_specs()}
    lo = np.radians([lims[n][0] for n in _JOINT_ORDER])
    hi = np.radians([lims[n][1] for n in _JOINT_ORDER])
    smax = np.where(M >= 0, M * hi, M * lo).sum(axis=1)
    smin = np.where(M >= 0, M * lo, M * hi).sum(axis=1)
    return smax - smin


def spool_radii_mm(routing: str = "idler") -> np.ndarray:
    """Per-actuator drum radius sized to TARGET_SPAN_DEG, clamped to printable range."""
    travel = _strand_travel_mm(coupling_matrix(routing))
    r = travel / math.radians(TARGET_SPAN_DEG)
    return np.clip(r, SPOOL_R_MIN_MM, SPOOL_R_MAX_MM)


def actuator_angles_deg(q_deg, routing: str = "idler") -> np.ndarray:
    """Actuator angles (deg) that realise joint angles q_deg (dict or seq of 20)."""
    q = _as_vec(q_deg)
    return np.degrees(coupling_matrix(routing) @ np.radians(q) / spool_radii_mm(routing))


def joint_angles_deg(theta_deg, routing: str = "idler") -> np.ndarray:
    """Inverse map (decoupling controller): joint angles from actuator angles."""
    th = np.radians(np.asarray(theta_deg, dtype=float))
    if th.shape != (20,):
        raise ValueError("expected 20 actuator angles")
    return np.degrees(np.linalg.solve(coupling_matrix(routing), spool_radii_mm(routing) * th))


def _as_vec(q_deg) -> np.ndarray:
    if isinstance(q_deg, dict):
        return np.array([float(q_deg[n]) for n in _JOINT_ORDER])
    v = np.asarray(q_deg, dtype=float)
    if v.shape != (20,):
        raise ValueError("expected 20 joint angles")
    return v


def travel_report(routing: str = "idler") -> dict:
    """Worst-case actuator rotation span over the full joint-limit box."""
    M = coupling_matrix(routing)
    travel = _strand_travel_mm(M)
    radii = spool_radii_mm(routing)
    span = np.degrees(travel / radii)
    rows = {n: {"strand_travel_mm": float(travel[i]), "spool_radius_mm": float(radii[i]),
                "span_deg": float(span[i])} for i, n in enumerate(_JOINT_ORDER)}
    return {"routing": routing, "per_actuator": rows,
            "max_span_deg": float(span.max()),
            "fits_single_turn_position_mode": bool(span.max() < 360.0)}


def loop_efficiency(routing: str = "idler") -> np.ndarray:
    """Worst-case one-way strand efficiency per loop (sliding capstan + idlers).

    Forearm guides slide (capstan, MU_GUIDE).  'idler' crossings roll (ETA_IDLER
    each).  'sheath' crossings slide through a sheath bent by up to the crossed
    joint's full range (capstan, MU_SHEATH, conservative).  The drive pulley is
    fixed to the child link (strand anchored, no slip, no loss)."""
    lims = {s["name"]: s["limits_deg"] for s in joint_specs()}
    out = []
    for n in _JOINT_ORDER:
        joints = _chain()[n.split("_", 1)[0]]
        crossed = joints[: joints.index(n)]
        eta = math.exp(-MU_GUIDE * FOREARM_ROUTING_WRAP_RAD)
        for c in crossed:
            if routing == "idler":
                eta *= ETA_IDLER
            else:
                bend = math.radians(max(abs(v) for v in lims[c]))
                eta *= math.exp(-MU_SHEATH * bend)
        out.append(eta)
    return np.array(out)


def joint_torques_for_tip_force(q_deg, finger: str, force_n) -> np.ndarray:
    """tau (N.m, 20) needed to resist an external force F (N, world) at a fingertip.

    Uses FK joint origins/axes from hand_kinematics (independent of tendon model):
    tau_i = a_i . ((p_tip - o_i) x F) for joints in that finger, 0 elsewhere."""
    fk = forward_kinematics(dict(zip(_JOINT_ORDER, _as_vec(q_deg))))
    tip = np.array(fk["tips_mm"][finger]) / 1000.0
    F = np.asarray(force_n, dtype=float)
    tau = np.zeros(20)
    for i, n in enumerate(_JOINT_ORDER):
        if not n.startswith(finger + "_"):
            continue
        o = np.array(fk["joints"][n]["origin_mm"]) / 1000.0
        a = np.array(fk["joints"][n]["axis_world"])
        tau[i] = a @ np.cross(tip - o, F)
    return tau


def actuator_load(tau_nm: np.ndarray, routing: str = "idler") -> dict:
    """Tension differences (N) and actuator torques (N.m) incl. capstan losses."""
    M_m = coupling_matrix(routing) / 1000.0          # m/rad
    dT = np.linalg.solve(M_m.T, tau_nm)              # N
    u = spool_radii_mm(routing) / 1000.0 * dT / loop_efficiency(routing)
    return {"tension_diff_n": dT, "actuator_torque_nm": u}


def max_tip_force(q_deg, finger: str, direction, routing: str = "idler",
                  stall_nm: float = XL330_STALL_NM_5V) -> dict:
    """Largest |F| along `direction` that keeps every actuator within the allowable."""
    d = np.asarray(direction, dtype=float)
    d = d / np.linalg.norm(d)
    unit = actuator_load(joint_torques_for_tip_force(q_deg, finger, d), routing)
    peak = np.max(np.abs(unit["actuator_torque_nm"]))
    allow = ALLOWABLE_FRACTION * stall_nm
    f = allow / peak if peak > 0 else math.inf
    t_peak = float(np.max(np.abs(unit["tension_diff_n"])) * f)
    i = int(np.argmax(np.abs(unit["actuator_torque_nm"])))
    return {"finger": finger, "routing": routing,
            "allowable_actuator_torque_nm": allow,
            "max_force_n": float(f),
            "limiting_actuator": _JOINT_ORDER[i],
            "peak_tension_diff_n": t_peak,
            # Pull-pull loop: strands carry T0 +/- dT/2.  Keeping the slack side
            # >= 0 needs T0 >= |dT|/2, so the tight side reaches |dT|.
            "min_preload_n": t_peak / 2.0,
            "line_break_load_required_n": SAFETY_FACTOR_LINE * t_peak}


def summary(routing: str = "idler") -> dict:
    """Compact report used in the design doc."""
    return {
        "rank": actuation_rank(routing),
        "travel": {k: v for k, v in travel_report(routing).items() if k != "per_actuator"},
        "efficiency_min": float(loop_efficiency(routing).min()),
    }
