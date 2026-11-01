"""
hand_v3_layout.py -- in-palm actuator layout for the v3 right hand (numpy only).
================================================================================
PROPOSED DESIGN.  Not fabrication-ready, not FEA-verified, not prototype-tested.

All 20 actuators live INSIDE the palm.  This module owns every coordinate that
the CAD (hand_v3_geometry) and the grasp check (hand_v3_grasp) share, so the
packing / routing can be verified quickly without a CAD kernel.

Frame (same as v2): palm frame, fingers +Y, palmar (flexion) side +Z, thumb +X.
Hand scale SCALE = 1.1 on every kinematic translation (link lengths, roots);
cross-sections, 2.5 mm pins and joint pulleys are NOT scaled.

Actuator: Pololu Micro Metal Gearmotor HPCB 12V 380:1 with 12 CPR encoder,
back connector (item #5226).  Vendor data (pololu.com, read 2026-10-31):
gearbox 10 x 12 mm section, 9 mm long 3 mm D output shaft; encoder versions
10 x 12 x 32 mm; 6-pin JST SH back connector; HPCB 12V 380:1 extrapolated stall
5.0 kg.cm, 0.75 A, 85 rpm no-load; recommended instantaneous torque limit
2.5 kg.cm for 380:1.  Body geometry below is a simplified envelope of those
published dimensions (NOT a vendor STEP) -- verify against Pololu's drawing.

Layout (interior of the palm skeleton):
  * 5 columns (pitch 16.5 mm) x 2 ranks (rear / front) x 2 layers (palmar P /
    dorsal D) = 20 slots.  Motor axes along Y, output shafts toward +Y,
    gearbox faces bolted (2x M1.6) to transverse bulkhead ribs.
  * A 3.5 mm "gallery plate" between the layers carries every tendon strand
    (two sub-planes) and every front-rank encoder cable (lanes).
  * Each pull-pull drum (r = 3 mm) launches its two strands tangentially
    toward the gallery at x = mc +/- 3, on the two drum halves (y +/- 1.35).
  * Columns 1-4 drive little, ring, middle, index (4 joints each).  Column 5
    drives the thumb; its front-rank motors are reversed (drums face -Y) so all
    8 thumb strands run +X to the thenar exits next to the thumb base.
  * Electronics bay = ONE two-sided controller board standing in the palm heel
    (plane XZ), directly behind the rear-rank motor connectors.  Modelled as an
    envelope only (board + component-height keep-outs); size comes from the
    component-area budget in electronics_budget().  The wrist is just a short
    adapter to the xArm flange; the xArm tool cable enters through the heel.
"""
from __future__ import annotations

import math

import numpy as np

import hand_kinematics as hk

SCALE = 1.1
MIRROR = np.diag([-1.0, 1.0, 1.0, 1.0])
SCALE_M = np.diag([SCALE, SCALE, SCALE, 1.0])
SCALE_INV = np.diag([1 / SCALE, 1 / SCALE, 1 / SCALE, 1.0])
FINGERS = ("index", "middle", "ring", "little", "thumb")

# ---- motor envelope (vendor-derived, simplified) -------------------------------
GB_LEN, CAN_LEN, CAP_LEN, ENC_LEN = 9.0, 15.0, 2.0, 6.0   # sum = 32 (vendor body)
BODY_LEN = GB_LEN + CAN_LEN + CAP_LEN + ENC_LEN
MOTOR_W, MOTOR_H = 12.0, 10.0           # X, Z
ENC_OVERHANG = 3.0                      # encoder board past the 10x12 section (+/-X)
SHAFT_LEN, SHAFT_D = 9.0, 3.0
PLUG_LEN = 4.0                          # mated JST SH plug behind the back connector
PLUG_W, PLUG_H = 4.25, 8.0              # plug long side vertical (Z)
RIB_T = 2.0                             # bulkhead rib the gearbox face bolts to
DRUM_R, DRUM_FLANGE_R, DRUM_LEN, DRUM_FLANGE_T = 3.0, 4.0, 7.0, 0.8
STRAND_HALF = 1.35                      # strand wrap position on each drum half
M16_HOLES = (-4.5, 4.5)                 # ASSUMED gearbox-face M1.6 hole x offsets

# ---- palm envelope --------------------------------------------------------------
PALM_X = 47.0
PALM_Y = (-68.5, 54.0)
PALM_Z = (-24.0, 8.0)
WALL = 2.5
INTERIOR = ((-44.5, 44.5), (PALM_Y[0] + WALL, 40.0), (-21.5, 5.5))
Z_GALLERY = -8.0
GALLERY_T = 3.5
LAYER_ZC = {"P": -1.0, "D": -15.0}      # motor centre heights
SUBPLANE = {"P": Z_GALLERY + 0.8, "D": Z_GALLERY - 0.8}
STRAND_R, STRAND_CH_R = 0.3, 0.5        # 0.6 mm UHMWPE braid, 1.0 mm channel

COL_PITCH = 16.5
COL_X = tuple(COL_PITCH * (i - 2) for i in range(5))      # -33 .. 33
FRONT_SHIFT = 2.5
COL_FINGER = ("little", "ring", "middle", "index", "thumb")
SLOT_JOINT = {                          # (rank, layer) -> joint suffix index
    ("rear", "P"): 0, ("rear", "D"): 1, ("front", "P"): 2, ("front", "D"): 3}

# rank geometry: gearbox face y and direction (+1 output toward +Y)
REAR_GB_FACE = -21.0
FRONT_GB_FACE = 26.0
THUMB_FRONT_GB_FACE = -2.0              # reversed motor (output toward -Y)

# Tendon exits on the palmar face.  Long fingers: P-layer row at y=EXIT_YP, D-layer row at
# y=EXIT_YD (both proximal of the knuckle bosses).  Thumb: two rows proximal of the thumb base.
EXIT_Z = PALM_Z[1]
EXIT_YP, EXIT_YD = 37.0, 39.0
EXIT_DX = {"index": (-6.75, -3.75, 3.75, 6.75), "middle": (-6.75, -3.75, -1.0, 1.5),
           "ring": (-6.75, -3.75, 3.75, 6.75), "little": (-6.75, -3.75, 3.75, 6.75)}
THUMB_EXIT_X = {"P": 42.5, "D": 44.0}
THUMB_EXIT_Y = {"P": (-34.0, -32.0, -30.0, -28.0), "D": (-33.0, -31.0, -29.0, -27.0)}
FAN_Y = (33.8, 34.7, 35.6, 36.5)        # fan-out stations, past the front drum tangents (y<=32.85)
THUMB_DZ = 3.0                          # thumb chain raised so its carrier clears the palm top

# ---- electronics bay (envelope only) / wrist adapter -----------------------------
WRIST_AXIS_Z = -8.0
CABLE_BEND = 3.3                        # free length behind each rear-rank JST plug
PCB_W, PCB_H, PCB_T = 51.5, 25.0, 1.0   # x, z, y (board) -- sized by electronics_budget()
PCB_TOP_H, PCB_BOT_H = 2.5, 1.0         # component keep-out heights (+Y / -Y faces)
PCB_ZC = -8.0
PCB_Y = -57.0 - CABLE_BEND - PCB_TOP_H - PCB_T / 2      # board mid-plane (-63.3)
# Rear-rank plugs end at y = -57; the cage gallery/ribs stop at CAGE_Y0 so the board is free.
CAGE_Y0 = -58.0
PCB_HOLES = ((-23.25, -10.0), (23.25, -10.0), (-23.25, 10.0), (23.25, 10.0))  # x, dz (M2 standoffs)
WRIST_Y = (-79.0, PALM_Y[0])            # collar from adapter to palm heel
ADAPTER_Y = (-86.0, -79.0)              # flange contact face at y = -86
ADAPTER_R = 37.5
TOOL_CABLE_R = 6.0
FLANGE_PCD, FLANGE_HOLES_DEG = 50.0, (45.0, 135.0, 225.0, 315.0)


# ---------------------------------------------------------------------------------
# Kinematics
# ---------------------------------------------------------------------------------
def links(q_deg) -> dict:
    """Right-hand, scaled link frames: S M T M S^-1 (rotations unchanged); thumb chain
    raised by THUMB_DZ (rigid translation, kinematics otherwise identical)."""
    fk = hk.forward_kinematics(q_deg)
    out = {n: SCALE_M @ MIRROR @ T @ MIRROR @ SCALE_INV for n, T in fk["links"].items()}
    for n, T in out.items():
        if n.startswith("thumb_"):
            T[2, 3] += THUMB_DZ
    return out


def segment_lengths() -> dict:
    hd = hk.hand_dimensions()
    return {f: [SCALE * v for v in hd["fingers"][f]["lengths_mm"]] for f in FINGERS}


CARRIER_LEN = SCALE * hk._CARRIER_LEN


def finger_roots() -> dict:
    L = links(hk.pose("open"))
    return {f: L[f"{f}_carrier"][:3, 3].copy() for f in FINGERS}


def joint_frames(q_deg) -> dict:
    """joint name -> (origin, axis) in world, for torque mapping."""
    L = links(q_deg)
    out = {}
    for f in FINGERS:
        names = [s["name"] for s in hk.joint_specs() if s["finger"] == f]
        for n, sfx, ax in zip(names, ("carrier", "proximal", "middle", "distal"),
                              ((0, 0, 1), (1, 0, 0), (1, 0, 0), (1, 0, 0))):
            T = L[f"{f}_{sfx}"]
            out[n] = (T[:3, 3].copy(), T[:3, :3] @ np.array(ax, float))
    return out


# ---------------------------------------------------------------------------------
# Actuator slots
# ---------------------------------------------------------------------------------
def _joint_name(finger, k):
    return [s["name"] for s in hk.joint_specs() if s["finger"] == finger][k]


def motor_slots() -> list:
    """List of dicts: joint, column, rank, layer, mc (x), zc, gb_face, dir (+1/-1),
    frame (4x4: motor local z = output axis, local origin on gearbox face)."""
    slots = []
    for c, xc in enumerate(COL_X):
        finger = COL_FINGER[c]
        for rank in ("rear", "front"):
            for layer in ("P", "D"):
                if rank == "rear":
                    mc, face, d = xc, REAR_GB_FACE, 1
                elif finger == "thumb":
                    mc, face, d = xc + FRONT_SHIFT, THUMB_FRONT_GB_FACE, -1
                else:
                    mc, face, d = xc + FRONT_SHIFT, FRONT_GB_FACE, 1
                zc = LAYER_ZC[layer]
                T = np.eye(4)
                # local z (output) -> world +/-Y, local x -> world +/-X, local y -> world -Z
                T[:3, :3] = np.column_stack(([d, 0, 0], [0, 0, -1], [0, d, 0]))
                T[:3, 3] = (mc, face, zc)
                slots.append(dict(joint=_joint_name(finger, SLOT_JOINT[(rank, layer)]),
                                  column=c, finger=finger, rank=rank, layer=layer,
                                  mc=mc, zc=zc, gb_face=face, dir=d, frame=T))
    return slots


def motor_boxes(slot) -> dict:
    """Axis-aligned world boxes (lo, hi) of every rigid motor-related volume."""
    d, mc, zc, f = slot["dir"], slot["mc"], slot["zc"], slot["gb_face"]
    hw, hh = MOTOR_W / 2, MOTOR_H / 2

    def ybox(a, b):
        return (min(f + d * a, f + d * b), max(f + d * a, f + d * b))
    boxes = {}
    y0, y1 = ybox(-BODY_LEN, 0.0)
    boxes["body"] = ((mc - hw, y0, zc - hh), (mc + hw, y1, zc + hh))
    ov = ENC_OVERHANG
    ex = (mc + hw, mc + hw + ov) if slot["rank"] == "rear" else (mc - hw - ov, mc - hw)
    ey0, ey1 = ybox(-BODY_LEN, -BODY_LEN + ENC_LEN)
    boxes["encoder_overhang"] = ((ex[0], ey0, zc - hh - 0.25), (ex[1], ey1, zc + hh + 0.25))
    py0, py1 = ybox(-BODY_LEN - PLUG_LEN, -BODY_LEN)
    boxes["plug"] = ((mc - PLUG_W / 2, py0, zc - PLUG_H / 2), (mc + PLUG_W / 2, py1, zc + PLUG_H / 2))
    dy0, dy1 = ybox(RIB_T, RIB_T + DRUM_LEN)
    r = DRUM_FLANGE_R
    boxes["drum"] = ((mc - r, dy0, zc - r), (mc + r, dy1, zc + r))
    return boxes


def drum_center_y(slot) -> float:
    return slot["gb_face"] + slot["dir"] * (RIB_T + DRUM_LEN / 2)


# ---------------------------------------------------------------------------------
# Tendon strand paths (palm portion: drum tangent -> palm exit hole)
# ---------------------------------------------------------------------------------
def finger_exits() -> dict:
    """Palmar-face exit points, 4 per layer per finger.  Long fingers exit just proximal of
    their knuckle boss (two rows); thumb strands exit in two rows on the thenar pad."""
    roots = finger_roots()
    out = {}
    for f in FINGERS:
        x = roots[f][0]
        if f == "thumb":
            out[f] = {L: [(THUMB_EXIT_X[L], y, EXIT_Z) for y in THUMB_EXIT_Y[L]] for L in ("P", "D")}
        else:
            out[f] = {"P": [(x + dx, EXIT_YP, EXIT_Z) for dx in EXIT_DX[f]],
                      "D": [(x + dx, EXIT_YD, EXIT_Z) for dx in EXIT_DX[f]]}
    return out


def strand_paths() -> list:
    """40 polylines [(name, finger, [points])], straight segments only.

    Every strand leaves its drum tangentially, drops (or rises) to its layer's sub-plane
    in the gallery, runs along +Y in a private lane, changes lane once at a staggered
    jog station (so no two strands share a jog), then rises to its exit hole.  Long-finger
    strands keep their own column; thumb strands run +X to the thenar side.
    Lane x positions are the drum tangent x positions, which are unique per layer."""
    exits = finger_exits()
    groups = {}
    for s in motor_slots():
        yd = drum_center_y(s)
        z = SUBPLANE[s["layer"]]
        for k, sx in enumerate((-1, 1)):
            x = s["mc"] + sx * DRUM_R
            y = yd + (sx * STRAND_HALF) * s["dir"]
            groups.setdefault((s["finger"], s["layer"]), []).append(
                (f"{s['joint']}_{'ab'[k]}", s, x, y, z))
    out = []
    for (f, L), items in groups.items():
        ex = exits[f][L]
        if f == "thumb":
            items.sort(key=lambda it: it[2])                       # by lane x
            for j, ((n, s, x, y, z), e) in enumerate(zip(items, sorted(ex, key=lambda p: p[1]))):
                pts = [(x, y, s["zc"]), (x, y, z)]
                ylane = e[1]
                pts += [(x, ylane, z), (e[0], ylane, z), e]
                out.append((n, f, pts))
        else:
            # planar channel routing: lanes run +Y, then each strand changes lane once at its
            # own fan-out station.  Right-movers go first starting from the rightmost lane,
            # left-movers starting from the leftmost, so no jog crosses a lane still in use.
            items.sort(key=lambda it: it[2])
            pairs = list(zip(items, sorted(ex, key=lambda p: p[0])))
            right = sorted([p for p in pairs if p[1][0] >= p[0][2]], key=lambda p: -p[0][2])
            left = sorted([p for p in pairs if p[1][0] < p[0][2]], key=lambda p: p[0][2])
            for st, ((n, s, x, y, z), e) in zip(FAN_Y, right + left):
                pts = [(x, y, s["zc"]), (x, y, z), (x, st, z), (e[0], st, z), (e[0], e[1], z), e]
                out.append((n, f, pts))
    return out


# ---------------------------------------------------------------------------------
# Encoder cable passages (motor back connector -> heel board).  Used only to cut
# channels in the cage; individual wires are NOT modelled.
# ---------------------------------------------------------------------------------
def pcb_top_face_y() -> float:
    return PCB_Y + PCB_T / 2 + PCB_TOP_H


def cable_lane_x(slot) -> float:
    return COL_X[slot["column"]] + (-9.5 if slot["layer"] == "P" else -7.0)


def cable_paths() -> list:
    """20 polylines [(joint, [points])] from plug end to the board's top keep-out face."""
    y_board = pcb_top_face_y()
    out = []
    for s in motor_slots():
        d, mc, zc, f = s["dir"], s["mc"], s["zc"], s["gb_face"]
        y_plug_end = f - d * (BODY_LEN + PLUG_LEN)
        if s["rank"] == "rear":
            pts = [(mc, y_plug_end, zc), (mc, y_board, zc)]
        else:
            lane = cable_lane_x(s)
            y_turn = y_plug_end - 0.5 if d > 0 else y_plug_end + 2.5
            pts = [(mc, y_plug_end, zc), (mc, y_turn, zc), (lane, y_turn, zc),
                   (lane, y_turn, Z_GALLERY), (lane, y_board, Z_GALLERY)]
        out.append((s["joint"], pts))
    return out


def pcb_envelope():
    """Axis-aligned boxes (lo, hi): board, top keep-out, bottom keep-out."""
    x0, x1 = -PCB_W / 2, PCB_W / 2
    z0, z1 = PCB_ZC - PCB_H / 2, PCB_ZC + PCB_H / 2
    yb0, yb1 = PCB_Y - PCB_T / 2, PCB_Y + PCB_T / 2
    return {"board": ((x0, yb0, z0), (x1, yb1, z1)),
            "top": ((x0 + 0.5, yb1, z0 + 0.5), (x1 - 0.5, yb1 + PCB_TOP_H, z1 - 0.5)),
            "bottom": ((x0 + 0.5, yb0 - PCB_BOT_H, z0 + 0.5), (x1 - 0.5, yb0, z1 - 0.5))}


def electronics_budget() -> dict:
    """Footprint budget (mm^2, incl. local passives) that sizes the heel board.

    Envelope estimate only -- no schematic or layout exists.  Parts are typical
    packages chosen for density; final selection is open."""
    items = [
        ("2-ch brushed H-bridge, 4x4 mm QFN (DRV8833-class) + caps", 10, 42.0),
        ("MCU, 10x10 mm QFN-80 (RP2350B-class) + flash, crystal, decoupling", 2, 256.0),
        ("24 V -> 12 V synchronous buck, 3 A, 4x4 mm inductor", 1, 120.0),
        ("3.3 V regulator", 1, 36.0),
        ("RS-485 transceiver + TVS (xArm tool Modbus RTU)", 1, 35.0),
        ("xArm tool-cable solder pads (8 wires)", 1, 50.0),
        ("motor pigtail solder pads (6 wires each, 1.25 mm pitch)", 20, 22.5),
        ("current-sense resistors / misc", 1, 120.0),
    ]
    parts = sum(n * a for _, n, a in items)
    routed = parts * 1.3
    avail = 2 * (PCB_W - 2.0) * (PCB_H - 2.0)
    return {"items": [dict(item=i, qty=n, mm2_each=a) for i, n, a in items],
            "component_area_mm2": parts, "with_30pct_routing_mm2": round(routed, 1),
            "usable_two_sided_area_mm2": round(avail, 1), "fits": routed <= avail,
            "board_mm": [PCB_W, PCB_H, PCB_T],
            "bay_envelope_mm": [PCB_W, PCB_H, round(PCB_T + PCB_TOP_H + PCB_BOT_H, 2)],
            "bay_volume_cm3": round(PCB_W * PCB_H * (PCB_T + PCB_TOP_H + PCB_BOT_H) / 1000, 2)}


# ---------------------------------------------------------------------------------
# Geometry checks (segment / box)
# ---------------------------------------------------------------------------------
def seg_seg_dist(p0, p1, q0, q1) -> float:
    p0, p1, q0, q1 = (np.asarray(v, float) for v in (p0, p1, q0, q1))
    u, v, w = p1 - p0, q1 - q0, p0 - q0
    a, b, c, d, e = u @ u, u @ v, v @ v, u @ w, v @ w
    D = a * c - b * b
    sN, sD, tN, tD = 0.0, D, 0.0, D
    if D < 1e-12:
        sN, sD, tN, tD = 0.0, 1.0, e, c
    else:
        sN, tN = b * e - c * d, a * e - b * d
        if sN < 0:
            sN, tN, tD = 0.0, e, c
        elif sN > sD:
            sN, tN, tD = sD, e + b, c
    if tN < 0:
        tN = 0.0
        sN, sD = (0.0, sD) if -d < 0 else ((sD, sD) if -d > a else (-d, a))
    elif tN > tD:
        tN = tD
        sN, sD = (0.0, sD) if -d + b < 0 else ((sD, sD) if -d + b > a else (-d + b, a))
    sc = 0.0 if abs(sN) < 1e-12 else sN / sD
    tc = 0.0 if abs(tN) < 1e-12 else tN / tD
    return float(np.linalg.norm(w + sc * u - tc * v))


def seg_box_dist(p0, p1, lo, hi, n=60) -> float:
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    best = math.inf
    for t in np.linspace(0, 1, n):
        p = p0 + t * (p1 - p0)
        q = np.clip(p, lo, hi)
        best = min(best, float(np.linalg.norm(p - q)))
    return best


def polyline_segments(pts):
    return list(zip(pts[:-1], pts[1:]))


def power_budget() -> dict:
    """xArm tool I/O 24 V / 1.8 A (vendor manual V2.3.0)."""
    tool_w = 24.0 * 1.8
    buck_eff = 0.90
    logic_w = 1.0
    motor_w_avail = tool_w * buck_eff - logic_w
    i12_avail = motor_w_avail / 12.0
    return {"tool_supply_w": tool_w, "buck_efficiency_assumed": buck_eff,
            "logic_w_assumed": logic_w, "motor_bus_12v_a_available": round(i12_avail, 3),
            "per_motor_current_limit_a": 0.25,
            "all_20_at_limit_a": 20 * 0.25,
            "firmware_total_current_cap_a": round(min(i12_avail, 3.0), 2)}
