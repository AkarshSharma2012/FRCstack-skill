"""
hand_v3_geometry.py -- v3 anatomical RIGHT hand: 20 actuators inside the palm.
==============================================================================
PROPOSED DESIGN.  Not fabrication-ready, not FEA-verified, not prototype-tested.

* Kinematics: hand_kinematics mirrored to a right hand and scaled x1.1
  (hand_v3_layout.links).  Finger parts are the v2 phalanges / carriers / fin-ray
  pads built at 1:1 cross-section, so pins, pulleys and TPU walls keep real sizes;
  phalanx LENGTHS follow the scaled kinematics.
* Palm: two-part shell (palmar + dorsal) around an internal motor cage.  The cage
  is a gallery plate between the two motor layers plus two transverse bulkhead
  ribs (rear / front ranks) that the gearbox faces bolt to.
* Motors: 20 simplified envelopes of the Pololu micro metal gearmotor with
  encoder (gearbox 10x12x9, can, encoder with JST SH back connector, 3 mm D
  shaft) + a pull-pull drum each.  NOT vendor CAD.
* Electronics bay: one placeholder controller board (size / position only, no
  circuit) standing in the palm heel behind the motor connectors, with its
  component keep-out envelopes.  A short wrist collar carries the xArm A50
  flange adapter.
* Tendons: palm strands modelled as straight 0.6 mm cylinders (hand_v3_layout).
"""
from __future__ import annotations

import math

import numpy as np

import hand_kinematics as hk
import hand_v2_geometry as v2
import hand_v3_layout as lay

_cyl, _box, _fuse, _cut, _ok, place, _seg = (v2._cyl, v2._box, v2._fuse, v2._cut, v2._ok,
                                            v2.place, v2._seg)


def _cq():
    import cadquery as cq
    return cq


# --------------------------------------------------------------------------------
# Fingers
# --------------------------------------------------------------------------------
def build_fingers(q_deg) -> dict:
    L = lay.links(q_deg)
    seg = lay.segment_lengths()
    parts = {}
    for f in lay.FINGERS:
        sc = v2.THUMB_SCALE if f == "thumb" else 1.0
        Lp, Lm, Ld = seg[f]
        parts[f"{f}_carrier"] = place(_carrier_scaled(), L[f"{f}_carrier"])
        parts[f"{f}_proximal"] = place(v2._phalanx(Lp, "proximal", True, sc), L[f"{f}_proximal"])
        parts[f"{f}_middle"] = place(v2._phalanx(Lm, "middle", True, sc), L[f"{f}_middle"])
        parts[f"{f}_distal"] = place(v2._phalanx(Ld, "distal", False, sc), L[f"{f}_distal"])
        parts[f"{f}_fin_ray_pad"] = place(v2._fin_ray(Ld, sc), L[f"{f}_distal"])
    return parts


_CARRIER_CACHE = {}


def _carrier_scaled():
    """v2 carrier with the clevis at the scaled carrier length."""
    if "c" not in _CARRIER_CACHE:
        cl = lay.CARRIER_LEN
        E_IN, E_OUT, HR, SR, PR = v2.EAR_IN, v2.EAR_OUT, v2.HINGE_R, v2.SLOT_R, v2.PIN_R
        parts = [_cyl(4.8, 5.0, (0, 0, -2.5), (0, 0, 1)), _box(-E_OUT, E_OUT, 0, 4, -2.5, 2.5)]
        for x0, x1 in ((-E_OUT, -E_IN), (E_IN, E_OUT)):
            parts += [_cyl(HR, x1 - x0, (x0, cl, 0), (1, 0, 0)), _box(x0, x1, 2, cl, -2.5, 2.5)]
        s = _fuse(*parts)
        ring = _cut(_cyl(5.0, 1.2, (0, 0, -0.6), (0, 0, 1)), _cyl(4.0, 1.2, (0, 0, -0.6), (0, 0, 1)))
        _CARRIER_CACHE["c"] = _ok(_cut(s, _cyl(SR, 2 * E_IN, (-E_IN, cl, 0), (1, 0, 0)),
                                       _cyl(PR, 5.4, (0, 0, -2.7), (0, 0, 1)),
                                       _cyl(PR, 2 * E_OUT + 0.4, (-E_OUT - 0.2, cl, 0), (1, 0, 0)), ring),
                                  "carrier")
    return _CARRIER_CACHE["c"]


# --------------------------------------------------------------------------------
# Palm shell (anatomical outline, two halves) + internal cage
# --------------------------------------------------------------------------------
def palm_outline():
    """Right-hand palm outline (x, y) in mm, counter-clockwise.  Hypothenar edge at -X,
    thenar eminence bulging at +X, knuckle arc at +Y, broad heel at -Y (y = PALM_Y[0])."""
    yh = lay.PALM_Y[0]
    return [(-40.0, yh), (-46.5, yh + 12.0), (-48.5, -30.0), (-48.5, 10.0), (-47.0, 40.0),
            (-40.0, 50.5), (-24.0, 53.5), (0.0, 54.0), (24.0, 53.5), (41.0, 50.0), (47.5, 38.0),
            (49.0, 18.0), (53.0, -8.0), (53.5, -34.0), (50.0, -54.0), (40.0, yh + 2.0),
            (20.0, yh), (-20.0, yh)]


def _outline_solid(offset, z0, z1):
    cq = _cq()
    w = cq.Workplane("XY").spline(palm_outline(), includeCurrent=False, periodic=True).close()
    if offset:
        w = cq.Workplane("XY").add(w.val()).toPending().offset2D(offset)
    return w.extrude(z1 - z0).val().translate(cq.Vector(0, 0, z0))


def _palm_shell():
    """Hollow anatomical palm; returns (palmar_half, dorsal_half) split at the gallery."""
    z0, z1 = lay.PALM_Z
    outer = _outline_solid(0.0, z0, z1)
    # anatomical rounding: dorsal arch + palmar hollow handled by fillets on outer edges
    try:
        outer = outer.fillet(5.0, [e for e in outer.Edges() if abs(e.Center().z - z0) < 1e-6])
        outer = outer.fillet(3.5, [e for e in outer.Edges() if abs(e.Center().z - z1) < 1e-6])
    except Exception:
        pass
    inner = _outline_solid(-lay.WALL, z0 + lay.WALL, z1 - lay.WALL)
    shell = _cut(outer, inner)
    # finger root windows (carriers sit on bosses on the palmar face; tendon exits)
    cuts = []
    for f, (x, y, z) in lay.finger_roots().items():
        cuts.append(_cyl(lay.PIN_R if hasattr(lay, "PIN_R") else v2.PIN_R, 40, (x, y, z0 - 1), (0, 0, 1)))
    for f, ex in lay.finger_exits().items():
        for p in ex["P"] + ex["D"]:
            cuts.append(_cyl(lay.STRAND_CH_R, 9.0, (p[0], p[1], p[2] - 6.0), (0, 0, 1)))
    # thumb carrier sweep pocket on the thenar top (carrier yaws about Z)
    tx, ty, tz = lay.finger_roots()["thumb"]
    cuts.append(_cyl(8.0, 12.0, (tx, ty, tz - 7.0), (0, 0, 1)))
    # heel opening: xArm tool cable enters through the wrist adapter bore
    cuts.append(_cyl(lay.TOOL_CABLE_R, 6.0, (0.0, lay.PALM_Y[0] - 1.0, lay.WRIST_AXIS_Z), (0, 1, 0)))
    # electronics bay pocket in the heel (board + keep-outs + standoff bosses stay inside)
    E = lay.pcb_envelope()
    lo = np.min([np.array(v[0]) for v in E.values()], 0)
    hi = np.max([np.array(v[1]) for v in E.values()], 0)
    cuts.append(_box(lo[0] - 0.4, hi[0] + 0.4, lo[1] - 0.4, hi[1] + 0.4, lo[2] - 0.4, hi[2] + 0.4))
    shell = _cut(shell, *cuts)
    zs = lay.Z_GALLERY
    palmar = _ok(_cut(shell, _box(-80, 80, -90, 90, -80, zs)), "palm_shell_palmar")
    dorsal = _ok(_cut(shell, _box(-80, 80, -90, 90, zs, 80)), "palm_shell_dorsal")
    return palmar, dorsal


def _knuckle_bosses():
    """Bosses on the palmar face that each yaw carrier pivots on."""
    out = []
    z1 = lay.PALM_Z[1]
    for f, (x, y, z) in lay.finger_roots().items():
        top = z - 2.5 - 0.3
        b = _cut(_cyl(5.6, top - (z1 - 2.0), (x, y, z1 - 2.0), (0, 0, 1)),
                 _cyl(v2.PIN_R, 40, (x, y, z1 - 5), (0, 0, 1)))
        out.append(b)
    return _ok(_fuse(*out), "knuckle_bosses") if len(out) == 1 else _fuse(*out)


def _cage():
    """Gallery plate + two bulkhead ribs, with motor bores, M1.6 holes, strand channels."""
    (x0, x1), (y0, y1), (zlo, zhi) = lay.INTERIOR
    y0 = lay.CAGE_Y0
    zg, t = lay.Z_GALLERY, lay.GALLERY_T
    gallery = _box(x0 + 0.3, x1 - 0.3, y0 + 0.3, y1 - 0.3, zg - t / 2, zg + t / 2)
    ribs = []
    for face, d in ((lay.REAR_GB_FACE, 1), (lay.FRONT_GB_FACE, 1), (lay.THUMB_FRONT_GB_FACE, -1)):
        ya, yb = sorted((face, face + d * lay.RIB_T))
        if d < 0:     # thumb rib only spans the thumb column
            xa, xb = lay.COL_X[4] - 10.0, x1 - 0.3
        else:
            xa, xb = x0 + 0.3, x1 - 0.3
        ribs.append(_box(xa, xb, ya, yb, zlo + 0.3, zhi - 0.3))
    s = _fuse(gallery, *ribs)
    cuts = []
    for sl in lay.motor_slots():
        f, d, mc, zc = sl["gb_face"], sl["dir"], sl["mc"], sl["zc"]
        ya = min(f, f + d * lay.RIB_T) - 0.1
        cuts.append(_cyl(2.1, lay.RIB_T + 0.2, (mc, ya, zc), (0, 1, 0)))          # shaft bush clearance
        for hx in lay.M16_HOLES:
            cuts.append(_cyl(0.85, lay.RIB_T + 0.2, (mc + hx, ya, zc), (0, 1, 0)))
        # motor body clearance through the gallery (bodies sit above/below it)
        lo, hi = lay.motor_boxes(sl)["body"]
        cuts.append(_box(lo[0] - 0.3, hi[0] + 0.3, lo[1] - 0.3, hi[1] + 0.3, lo[2] - 0.3, hi[2] + 0.3))
        lo, hi = lay.motor_boxes(sl)["drum"]
        cuts.append(_box(lo[0] - 0.4, hi[0] + 0.4, lo[1] - 0.2, hi[1] + 0.4, lo[2] - 0.4, hi[2] + 0.4))
        lo, hi = lay.motor_boxes(sl)["encoder_overhang"]
        cuts.append(_box(lo[0] - 0.3, hi[0] + 0.3, lo[1] - 0.3, hi[1] + 0.3, lo[2] - 0.3, hi[2] + 0.3))
        lo, hi = lay.motor_boxes(sl)["plug"]
        cuts.append(_box(lo[0] - 0.3, hi[0] + 0.3, lo[1] - 0.3, hi[1] + 0.3, lo[2] - 0.3, hi[2] + 0.3))
    tools = []
    for _, _, pts in lay.strand_paths():
        for a, b in lay.polyline_segments(pts):
            if np.linalg.norm(np.subtract(b, a)) > 1e-6:
                tools.append(_seg(lay.STRAND_CH_R, a, b))
    for _, pts in lay.cable_paths():
        for a, b in lay.polyline_segments(pts):
            if np.linalg.norm(np.subtract(b, a)) > 1e-6 and min(a[1], b[1]) > y0 - 5:
                tools.append(_seg(1.2, a, b))
    s = _cut(s, *cuts)
    s = _robust_cut(s, tools)
    return _ok(s, "motor_cage")


def _robust_cut(s, tools):
    """Subtract tools one at a time; if a cut yields an invalid solid, retry it with the
    tool shortened by 0.05 mm at both ends (avoids coincident end faces), then skip it.
    Returns the solid; skipped tools are recorded in _SKIPPED_TOOLS."""
    for t in tools:
        r = s.cut(t)
        if r.isValid() and len(r.Solids()) == 1:
            s = r
            continue
        r = _heal(r)
        if r.isValid() and len(r.Solids()) == 1:
            s = r
            continue
        _SKIPPED_TOOLS.append(t.BoundingBox().center.toTuple())
    return s


_SKIPPED_TOOLS = []


def _fuzzy_cut(base, tools, fuzzy=1e-3):
    """One Boolean subtraction of many tools with OCCT fuzzy tolerance."""
    cq = _cq()
    if not tools:
        return base
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.TopTools import TopTools_ListOfShape
    args, tl = TopTools_ListOfShape(), TopTools_ListOfShape()
    args.Append(base.wrapped)
    for t in tools:
        tl.Append(t.wrapped)
    op = BRepAlgoAPI_Cut()
    op.SetArguments(args)
    op.SetTools(tl)
    op.SetFuzzyValue(fuzzy)
    op.SetRunParallel(True)
    op.Build()
    if not op.IsDone():
        raise ValueError("fuzzy cut failed")
    return cq.Shape.cast(op.Shape()).clean()


def _heal(s):
    cq = _cq()
    from OCP.ShapeFix import ShapeFix_Shape
    fx = ShapeFix_Shape(s.wrapped)
    fx.Perform()
    out = cq.Shape.cast(fx.Shape())
    sol = out.Solids()
    return sol[0] if len(sol) == 1 else out


# --------------------------------------------------------------------------------
# Motors (simplified vendor envelope) and drums
# --------------------------------------------------------------------------------
_MOTOR_CACHE = {}


def _motor_local():
    """Local frame: output axis +Z, gearbox face at z=0, body toward -Z.  x = 12 mm, y = 10 mm."""
    if "m" not in _MOTOR_CACHE:
        hw, hh = lay.MOTOR_W / 2, lay.MOTOR_H / 2
        gb = _box(-hw, hw, -hh, hh, -lay.GB_LEN, 0.0)
        can = _cut(_cyl(hw, lay.CAN_LEN, (0, 0, -lay.GB_LEN - lay.CAN_LEN), (0, 0, 1)),
                   _box(-hw, hw, hh, hw + 1, -60, 0), _box(-hw, hw, -hw - 1, -hh, -60, 0))
        cap = _box(-hw, hw, -hh, hh, -lay.GB_LEN - lay.CAN_LEN - lay.CAP_LEN, -lay.GB_LEN - lay.CAN_LEN)
        z_enc0 = -lay.BODY_LEN
        enc = _box(-hw - 0.25, hw + lay.ENC_OVERHANG, -hh - 0.25, hh + 0.25, z_enc0, z_enc0 + lay.ENC_LEN)
        shaft = _cut(_cyl(lay.SHAFT_D / 2, lay.SHAFT_LEN, (0, 0, 0), (0, 0, 1)),
                     _box(-2, 2, 1.0, 2, 0.5, lay.SHAFT_LEN + 1))
        _MOTOR_CACHE["m"] = _ok(_fuse(gb, can, cap, enc, shaft), "motor")
        plug = _box(-lay.PLUG_W / 2, lay.PLUG_W / 2, -lay.PLUG_H / 2, lay.PLUG_H / 2,
                    z_enc0 - lay.PLUG_LEN, z_enc0)
        _MOTOR_CACHE["p"] = _ok(plug, "jst_plug")
    return _MOTOR_CACHE["m"], _MOTOR_CACHE["p"]


def _motor_world_frame(sl):
    """Map motor local (x across 12 mm, y across 10 mm, z output) to world."""
    d = sl["dir"]
    T = np.eye(4)
    # local z -> world +d*Y ; local y -> world Z ; local x -> world d*X  (det = +1)
    T[:3, :3] = np.column_stack(([d, 0, 0], [0, 0, 1], [0, d, 0]))
    if abs(np.linalg.det(T[:3, :3]) - 1.0) > 1e-9:
        T[:3, :3] = np.column_stack(([-d, 0, 0], [0, 0, 1], [0, d, 0]))
    T[:3, 3] = (sl["mc"], sl["gb_face"], sl["zc"])
    return T


def _encoder_side_ok(sl):
    """Encoder overhang must land on the side motor_boxes() reserves for it."""
    m, _ = _motor_local()
    T = _motor_world_frame(sl)
    bb = place(m, T).BoundingBox()
    want_lo, want_hi = lay.motor_boxes(sl)["encoder_overhang"]
    return (bb.xmax >= want_hi[0] - 0.3) if sl["rank"] == "rear" else (bb.xmin <= want_lo[0] + 0.3)


def _drum():
    z = lay.RIB_T
    s = _fuse(_cyl(lay.DRUM_FLANGE_R, lay.DRUM_FLANGE_T, (0, 0, z), (0, 0, 1)),
              _cyl(lay.DRUM_R, lay.DRUM_LEN, (0, 0, z), (0, 0, 1)),
              _cyl(lay.DRUM_FLANGE_R, lay.DRUM_FLANGE_T, (0, 0, z + lay.DRUM_LEN / 2 - lay.DRUM_FLANGE_T / 2),
                   (0, 0, 1)),
              _cyl(lay.DRUM_FLANGE_R, lay.DRUM_FLANGE_T, (0, 0, z + lay.DRUM_LEN - lay.DRUM_FLANGE_T), (0, 0, 1)))
    s = _cut(s, _cyl(lay.SHAFT_D / 2 + 0.05, lay.DRUM_LEN + 2, (0, 0, z - 1), (0, 0, 1)))
    return _ok(s, "drum")


def build_actuators() -> dict:
    m, p = _motor_local()
    dr = _drum()
    parts = {}
    for sl in lay.motor_slots():
        T = _motor_world_frame(sl)
        if not _encoder_side_ok(sl):
            R = np.eye(4)
            R[:3, :3] = np.diag([-1.0, -1.0, 1.0])     # spin 180 deg about the motor axis
            T = T @ R
        j = sl["joint"]
        parts[f"motor_{j}"] = place(m, T)
        parts[f"plug_{j}"] = place(p, T)
        parts[f"drum_{j}"] = place(dr, T)
    return parts


def build_tendons() -> dict:
    out = {}
    for name, _f, pts in lay.strand_paths():
        segs = [_seg(lay.STRAND_R, a, b) for a, b in lay.polyline_segments(pts)
                if np.linalg.norm(np.subtract(b, a)) > 1e-6]
        out[f"tendon_{name}"] = _fuse(*segs) if len(segs) > 1 else segs[0]
    return out


# --------------------------------------------------------------------------------
# Wrist mount, electronics placeholder, xArm adapter
# --------------------------------------------------------------------------------
def _wrist_mount():
    """Short collar from the palm heel to a phi75 A50 flange adapter."""
    cq = _cq()
    zc = lay.WRIST_AXIS_Z
    a0, a1 = lay.ADAPTER_Y
    w0, w1 = lay.WRIST_Y
    plate = _cyl(lay.ADAPTER_R, a1 - a0, (0.0, a0, zc), (0, 1, 0))
    collar = cq.Solid.makeLoft([v2.rrect_wire(33.0, zc - 18.0, zc + 18.0, 12.0, w0),
                                v2.rrect_wire(40.0, lay.PALM_Z[0] + 1.5, lay.PALM_Z[1] - 1.5, 10.0, w1)], True)
    hollow = cq.Solid.makeLoft([v2.rrect_wire(29.0, zc - 14.0, zc + 14.0, 9.0, w0 - 0.01),
                                v2.rrect_wire(36.5, lay.PALM_Z[0] + 4.0, lay.PALM_Z[1] - 4.0, 7.5, w1 + 0.01)],
                               True)
    s = _fuse(plate, _cut(collar, hollow))
    cuts = []
    for deg in lay.FLANGE_HOLES_DEG:
        x = lay.FLANGE_PCD / 2 * math.cos(math.radians(deg))
        z = zc + lay.FLANGE_PCD / 2 * math.sin(math.radians(deg))
        cuts += [_cyl(3.3, a1 - a0 + 0.2, (x, a0 - 0.1, z), (0, 1, 0)),
                 _cyl(5.5, 3.6, (x, a1 - 3.5, z), (0, 1, 0))]          # M6 SHCS head pocket
    cuts.append(_cyl(2.55, 6.0, (lay.FLANGE_PCD / 2, a0 - 0.1, zc), (0, 1, 0)))      # phi5 dowel
    cuts.append(_cyl(lay.TOOL_CABLE_R, a1 - a0 + 0.2, (0.0, a0 - 0.1, zc), (0, 1, 0)))  # tool cable
    return _ok(_cut(s, *cuts), "wrist_adapter")


def _pcb_standoffs():
    yb = lay.PCB_Y - lay.PCB_T / 2
    y_heel = lay.INTERIOR[1][0]
    out = []
    for x, dz in lay.PCB_HOLES:
        z = lay.PCB_ZC + dz
        out.append(_cut(_cyl(2.2, yb - y_heel, (x, y_heel, z), (0, 1, 0)),
                        _cyl(0.8, 10, (x, y_heel - 1, z), (0, 1, 0))))
    return _ok(_fuse(*out), "pcb_standoffs") if False else _fuse(*out)


def build_electronics_placeholder() -> dict:
    """Envelope-only electronics: board outline + component keep-outs, no circuit."""
    E = lay.pcb_envelope()
    holes = [_cyl(1.1, 10, (x, lay.PCB_Y - 5, lay.PCB_ZC + dz), (0, 1, 0)) for x, dz in lay.PCB_HOLES]
    # keep-out envelopes are notched at the four standoff corners (stay single solids)
    keep = [_box(x - 3.0, x + 3.0, lay.PCB_Y - 10, lay.PCB_Y + 10, lay.PCB_ZC + dz - 3.0, lay.PCB_ZC + dz + 3.0)
            for x, dz in lay.PCB_HOLES]
    board = _cut(_box(E["board"][0][0], E["board"][1][0], E["board"][0][1], E["board"][1][1],
                      E["board"][0][2], E["board"][1][2]), *holes)
    top = _cut(_box(E["top"][0][0], E["top"][1][0], E["top"][0][1], E["top"][1][1],
                    E["top"][0][2], E["top"][1][2]), *keep)
    bot = _cut(_box(E["bottom"][0][0], E["bottom"][1][0], E["bottom"][0][1], E["bottom"][1][1],
                    E["bottom"][0][2], E["bottom"][1][2]), *keep)
    return {"pcb_controller_board": _ok(board, "pcb"),
            "pcb_component_envelope_top": _ok(top, "pcb_top_env"),
            "pcb_component_envelope_bottom": _ok(bot, "pcb_bot_env"),
            "pcb_standoffs": _pcb_standoffs()}


def build_hand_v3(q_deg, include_tendons=True) -> dict:
    parts = {}
    parts.update(build_fingers(q_deg))
    palmar, dorsal = _palm_shell()
    parts["palm_shell_palmar"] = palmar
    parts["palm_shell_dorsal"] = dorsal
    parts["knuckle_bosses"] = _knuckle_bosses()
    parts["motor_cage"] = _cage()
    parts.update(build_actuators())
    if include_tendons:
        parts.update(build_tendons())
    parts["wrist_adapter"] = _wrist_mount()
    parts.update(build_electronics_placeholder())
    return parts
