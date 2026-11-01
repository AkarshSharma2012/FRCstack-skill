"""
hand_v2_geometry.py -- anatomical RIGHT hand + motorised forearm skeleton (xArm mount).
=====================================================================================
PROPOSED DESIGN.  Not fabrication-ready, not FEA-verified, not prototype-tested.

* Same 20-joint kinematics as hand_kinematics, mirrored to a RIGHT hand by
  conjugation  T' = M T M,  M = diag(-1,1,1)  (proper rotations preserved).
  hand_kinematics' own layout is a LEFT hand (thumb on -X with flexion toward +Z).
* Palmar side = +Z (fingers flex toward +Z).  Fingers +Y.  Forearm toward -Y.
* Lofted elliptical phalanges, clevis/tongue hinges on 2.5 mm steel dowel pins,
  grooved drive pulleys at every joint, Fin Ray-style TPU pads on every fingertip.
* Forearm skeleton: wrist block, two back-to-back actuator spine plates, two CF
  tube "bones" (radius/ulna), elbow mount with xArm adapter, two removable covers.
* 20 manufacturer-sourced XL/XC330 reference bodies (vendor STEP, unscaled,
  SHA-256 checked) screwed to the spine through the case's own through-holes,
  each carrying a printed pull-pull spool on its horn.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np

import hand_kinematics as hk
import hand_tendons as ht

MIRROR = np.diag([-1.0, 1.0, 1.0, 1.0])
FINGERS = ("index", "middle", "ring", "little", "thumb")

# --- finger hardware -------------------------------------------------------
PIN_R = 1.3                 # bore for 2.5 mm h6 steel dowel (print allowance)
TONGUE_HW = 3.0
EAR_IN, EAR_OUT = 3.4, 7.4
HINGE_R = 5.5
SLOT_R = 6.1
BODY_START = 6.4            # child body starts outside the parent's R5.5 ears
SEC = {"proximal": ((7.0, 5.6), (6.2, 5.0)),
       "middle": ((6.4, 5.2), (5.8, 4.6)),
       "distal": ((5.8, 4.8), (4.8, 3.6))}
THUMB_SCALE = 1.1
PAD_BASE_Z = 2.6            # distal palmar flat that carries the fin-ray pad
FIN_T, FIN_RIBS = 0.8, 5    # TPU 85A wall / rib thickness, rib count
FIN_H = (4.4, 1.4)          # fin-ray pad height at root / tip

# --- forearm ----------------------------------------------------------------
ZC = -2.0                   # forearm centre-line height
DY = -12.0                  # shift of the verified cartridge packing toward the elbow
STATIONS = (-80.0, -122.0, -164.0, -206.0, -248.0)   # packing ty (verified disjoint)
COLUMNS = (-14.0, 14.0)                               # packing tx
ROW_TZ = {"radial": 28.0, "ulnar": -28.0}             # vendor back (z=-22.5) sits on spine face x=5.5
SPINE_HALF = 5.5            # actuator back faces at x = +/-5.5
PLATE_Z = (-28.0, 24.0)
PLATE_Y = (-290.0, -62.0)
WRIST_Y = (-66.0, -62.0, -55.0)       # const part, loft end (palm heel)
ELBOW_Y = (-294.0, -286.0)            # bulkhead
ADAPTER_Y = (-304.0, -294.0)
INNER = (47.0, -31.0, 27.0, 12.0)     # shell inner: half-x, z0, z1, corner r
SHELL_T = 2.5
BONE_R, BONE_XZ = 5.0, (40.0, ZC)     # 10 mm CF tube (8 mm ID), clear of cases (x<=34.5)
BONE_Y = (-290.0, -62.5)
SPOOL_R_MIN, SPOOL_R_MAX = 3.0, 3.8   # drum must clear horn M2 heads at R6
FLANGE_PCD, FLANGE_HOLES_DEG = 50.0, (45.0, 135.0, 225.0, 315.0)
DOWEL_DEG = 0.0             # phi 5 positioning hole angle: VERIFY on the flange
ADAPTER_R = 37.5

_VENDOR = (Path(__file__).resolve().parents[3] / ".frcstack" / "vendor"
           / "xl330-20261030" / "XL_XC330-manufacturer.stp")
VENDOR_SHA256 = "e2f7b060801a1d6a21f23bca2554f29a402f7d73b8498cb201c9e6adf3139eb6"
CASE_HOLES = ((8.0, 7.5), (-8.0, 7.5), (8.0, -22.5), (-8.0, -22.5))  # vendor frame, along Z
HORN_TOP = 6.5
TENDON_ENTRY_X = tuple(11.0 + 2.0 * k for k in range(10))
TENDON_Z = (-4.0, 0.0)
RADIAL_JOINTS = ("thumb_yaw", "thumb_opposition", "thumb_mcp", "thumb_ip",
                 "index_spread", "index_mcp", "index_pip", "index_dip",
                 "middle_spread", "middle_mcp")
ULNAR_JOINTS = ("little_spread", "little_mcp", "little_pip", "little_dip",
                "ring_spread", "ring_mcp", "ring_pip", "ring_dip",
                "middle_pip", "middle_dip")


# --- kernel helpers -----------------------------------------------------------
def _cq():
    import cadquery as cq
    return cq


def _ok(s, name):
    if s is None or not s.isValid() or len(s.Solids()) != 1 or not s.Volume() > 0:
        raise ValueError(f"invalid solid {name!r}")
    return s


def place(shape, mat4):
    from OCP.gp import gp_Trsf
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    if abs(np.linalg.det(mat4[:3, :3]) - 1.0) > 1e-9:
        raise ValueError("placement must be a proper rotation")
    t = gp_Trsf()
    t.SetValues(*[float(v) for v in mat4[:3, :].reshape(-1)])
    return _cq().Shape.cast(BRepBuilderAPI_Transform(shape.wrapped, t, True).Shape())


def _fuse(*s):
    out = s[0]
    for o in s[1:]:
        out = out.fuse(o)
    return out.clean()


def _cut(base, *tools):
    out = base
    for t in tools:
        out = out.cut(t)
    return out.clean()


def _cyl(r, h, p, d):
    cq = _cq()
    return cq.Solid.makeCylinder(r, h, cq.Vector(*p), cq.Vector(*d))


def _seg(r, p0, p1):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    n = float(np.linalg.norm(d))
    return _cyl(r, n, tuple(p0), tuple(d / n))


def _box(x0, x1, y0, y1, z0, z1):
    cq = _cq()
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _ell(y, a, b):
    cq = _cq()
    return cq.Wire.makeEllipse(a, b, cq.Vector(0, y, 0), cq.Vector(0, 1, 0), cq.Vector(1, 0, 0))


def rrect_wire(hx, z0, z1, r, y):
    """Rounded rectangle in the plane y=const (x half-width hx, z from z0 to z1)."""
    cq = _cq()
    w = (cq.Workplane("XY").center(0, (z0 + z1) / 2).rect(2 * hx - 2 * r, (z1 - z0) - 2 * r)
         .offset2D(r).val())
    return w.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 90).translate(cq.Vector(0, y, 0))


def _prism(hx, z0, z1, r, y0, y1):
    cq = _cq()
    return cq.Solid.makeLoft([rrect_wire(hx, z0, z1, r, y0), rrect_wire(hx, z0, z1, r, y1)], True)


# --- right-hand kinematics ------------------------------------------------------
def right_links(q_deg) -> dict:
    return {n: MIRROR @ T @ MIRROR for n, T in hk.forward_kinematics(q_deg)["links"].items()}


def right_tips(q_deg) -> dict:
    tips = hk.forward_kinematics(q_deg)["tips_mm"]
    return {f: (MIRROR[:3, :3] @ np.array(p)).tolist() for f, p in tips.items()}


# --- finger links (local: hinge axis X, link along +Y, flexion toward +Z) -----------
def _phalanx(L, kind, fork, sc=1.0):
    (a0, b0), (a1, b1) = [(a * sc, b * sc) for a, b in SEC[kind]]
    if fork:
        y1 = L - BODY_START
        body = _ok(_cq().Solid.makeLoft([_ell(BODY_START, a0, b0),
                                         _ell((BODY_START + y1) / 2, 0.97 * (a0 + a1) / 2, 0.97 * (b0 + b1) / 2),
                                         _ell(y1, a1, b1)], False), "loft")
    else:
        body = _cq().Solid.makeLoft([_ell(BODY_START, a0, b0), _ell((BODY_START + L) / 2, (a0 + a1) / 2, (b0 + b1) / 2),
                                     _ell(L - 3.0, a1, b1), _ell(L - 0.4, a1 * 0.5, b1 * 0.5)], False)
    tongue = _fuse(_cyl(HINGE_R, 2 * TONGUE_HW, (-TONGUE_HW, 0, 0), (1, 0, 0)),
                   _box(-TONGUE_HW, TONGUE_HW, 0, BODY_START + 1.0, -4.4, 4.4))
    groove = _cut(_cyl(HINGE_R + 0.1, 1.2, (-0.6, 0, 0), (1, 0, 0)),
                  _cyl(HINGE_R - 0.8, 1.2, (-0.6, 0, 0), (1, 0, 0)))
    s = _fuse(body, _cut(tongue, groove))
    cuts = [_cyl(PIN_R, 2 * TONGUE_HW + 0.4, (-TONGUE_HW - 0.2, 0, 0), (1, 0, 0))]
    if fork:
        ears = []
        for x0, x1 in ((-EAR_OUT, -EAR_IN), (EAR_IN, EAR_OUT)):
            ears += [_cyl(HINGE_R, x1 - x0, (x0, L, 0), (1, 0, 0)), _box(x0, x1, L - 7.4, L, -4.4, 4.4)]
        s = _fuse(s, *ears)
        cuts += [_cyl(SLOT_R, 2 * EAR_IN, (-EAR_IN, L, 0), (1, 0, 0)),
                 _cyl(PIN_R, 2 * EAR_OUT + 0.4, (-EAR_OUT - 0.2, L, 0), (1, 0, 0))]
        for z in (2.7, -2.7):           # flexor / extensor strand channels
            cuts.append(_cyl(0.7, L + 2.0, (0, -1.0, z), (0, 1, 0)))
    else:
        cuts.append(_box(-10, 10, BODY_START + 1.0, L + 1, PAD_BASE_Z, 10))   # pad land
    return _ok(_cut(s, *cuts), f"{kind}_L{L}")


def _carrier():
    cl = hk._CARRIER_LEN
    parts = [_cyl(4.8, 5.0, (0, 0, -2.5), (0, 0, 1)), _box(-EAR_OUT, EAR_OUT, 0, 4, -2.5, 2.5)]
    for x0, x1 in ((-EAR_OUT, -EAR_IN), (EAR_IN, EAR_OUT)):
        parts += [_cyl(HINGE_R, x1 - x0, (x0, cl, 0), (1, 0, 0)), _box(x0, x1, 2, cl, -2.5, 2.5)]
    s = _fuse(*parts)
    ring = _cut(_cyl(5.0, 1.2, (0, 0, -0.6), (0, 0, 1)), _cyl(4.0, 1.2, (0, 0, -0.6), (0, 0, 1)))
    return _ok(_cut(s, _cyl(SLOT_R, 2 * EAR_IN, (-EAR_IN, cl, 0), (1, 0, 0)),
                    _cyl(PIN_R, 5.4, (0, 0, -2.7), (0, 0, 1)),
                    _cyl(PIN_R, 2 * EAR_OUT + 0.4, (-EAR_OUT - 0.2, cl, 0), (1, 0, 0)), ring), "carrier")


def _fin_ray(L, sc=1.0):
    """Fin Ray-style pad: hollow wedge (TPU 85A) with cross ribs, on the distal land."""
    cq = _cq()
    a1 = SEC["distal"][1][0] * sc
    y0, y1, zb, h0, h1, w = BODY_START + 1.2, L - 1.6, PAD_BASE_Z, FIN_H[0], FIN_H[1], 2 * a1 * 0.92
    t = FIN_T

    def wedge(pts, width):
        return cq.Workplane("YZ").polyline(pts).close().extrude(width).translate((-width / 2, 0, 0)).val()
    outer = wedge([(y0, zb), (y1, zb), (y1, zb + h1), (y0, zb + h0)], w)
    inner = wedge([(y0 + t, zb + t), (y1 - t, zb + t), (y1 - t, zb + h1 - 0.5 * t), (y0 + t, zb + h0 - t)],
                  w - 2 * t)
    pad = _cut(outer, inner)
    ribs = []
    for k in range(1, FIN_RIBS + 1):
        y = y0 + (y1 - y0) * k / (FIN_RIBS + 1)
        top = zb + h0 + (h1 - h0) * (y - y0) / (y1 - y0) - 0.5 * t
        ribs.append(_box(-w / 2 + t, w / 2 - t, y - t / 2, y + t / 2, zb + 0.5 * t, top))
    return _ok(_fuse(pad, *ribs), "fin_ray")


# --- palm ---------------------------------------------------------------------------
def tendon_entries():
    """40 strand entry points (x, z) at the palm heel / wrist, radial side +X."""
    pts = []
    for side in (1, -1):
        for z in TENDON_Z:
            pts += [(side * x, z) for x in TENDON_ENTRY_X]
    return pts


def tendon_channels(links):
    """Straight palm channels (p0, p1) heel -> finger root, monotone (no crossing)."""
    exits = {}
    for f in FINGERS:
        T = links[f"{f}_carrier"]
        x, y = T[0, 3], T[1, 3]
        offs = (-5.4, -3.0, 3.0, 5.4)
        exits[f] = [(48.0, y + o) for o in offs] if f == "thumb" else [(x + o, 50.0) for o in offs]
    out = []
    for z in TENDON_Z:
        ex = [(f, p) for f in FINGERS for p in exits[f]]
        ex.sort(key=lambda fp: (fp[1][0] if fp[0] != "thumb" else 100 - fp[1][1]))
        ent = sorted([x for x, zz in tendon_entries() if zz == z])
        for (f, (xe, ye)), x0 in zip(ex, ent):
            out.append((f, (x0, -55.5, z), (xe, ye, z)))
    return out


def _palm(links):
    cq = _cq()
    s = (cq.Workplane("XY").polyline([(-34, -46), (34, -46), (37, 38), (-37, 38)]).close()
         .offset2D(9, "arc").extrude(17.5).val().translate(cq.Vector(0, 0, -14)))

    def loop(z):
        return [e for e in s.Edges() if abs(e.startPoint().z - z) < 1e-6 and abs(e.endPoint().z - z) < 1e-6]
    s = s.fillet(5.0, loop(-14.0))
    s = s.fillet(2.0, [e for e in s.Edges() if abs(e.startPoint().z - 3.5) < 1e-6
                       and abs(e.endPoint().z - 3.5) < 1e-6])
    s = _fuse(s, _box(-32, 32, -55, -48, -14, 3.5))
    bosses, cuts = [], []
    for f in FINGERS:
        T = links[f"{f}_carrier"]
        bosses.append(_cyl(5.6, 3.7, (T[0, 3], T[1, 3], 3.5), (0, 0, 1)))
        cuts.append(_cyl(PIN_R, 21.4, (T[0, 3], T[1, 3], -14.1), (0, 0, 1)))
    s = _fuse(s, *bosses)
    cuts += [_seg(0.6, p0, p1) for _, p0, p1 in tendon_channels(links)]
    cuts += [_cyl(2.2, 10.0, (x, -55.1, -9.0), (0, 1, 0)) for x in (-20.0, 20.0)]   # M4 to wrist
    s = _cut(s, *cuts)
    # anatomical dorsal arch: z=-14 on the centre line rising to z=-7 at |x|=46
    arch = _cyl(154.6, 200.0, (0, -100.0, 140.6), (0, 1, 0))
    return _ok(s.intersect(arch).clean(), "palm")


def build_hand(q_deg) -> dict:
    links = right_links(q_deg)
    hd = hk.hand_dimensions()
    parts = {"palm": _palm(links)}
    car = _carrier()
    for f in FINGERS:
        sc = THUMB_SCALE if f == "thumb" else 1.0
        Lp, Lm, Ld = hd["fingers"][f]["lengths_mm"]
        parts[f"{f}_carrier"] = place(car, links[f"{f}_carrier"])
        parts[f"{f}_proximal"] = place(_phalanx(Lp, "proximal", True, sc), links[f"{f}_proximal"])
        parts[f"{f}_middle"] = place(_phalanx(Lm, "middle", True, sc), links[f"{f}_middle"])
        parts[f"{f}_distal"] = place(_phalanx(Ld, "distal", False, sc), links[f"{f}_distal"])
        parts[f"{f}_fin_ray_pad"] = place(_fin_ray(Ld, sc), links[f"{f}_distal"])
    return parts


# --- actuators ----------------------------------------------------------------------------
def load_vendor_actuator():
    cq = _cq()
    data = _VENDOR.read_bytes()
    if hashlib.sha256(data).hexdigest() != VENDOR_SHA256:
        raise ValueError("vendor STEP hash mismatch")
    solids = cq.importers.importStep(str(_VENDOR)).val().Solids()
    if len(solids) != 15 or not all(s.isValid() for s in solids):
        raise ValueError("vendor STEP is not the inspected 15 valid solids")
    return cq.Compound.makeCompound(solids)


def _ry90():
    T = np.eye(4)
    T[:3, :3] = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]        # cartridge z -> world x
    return T


def actuator_frames() -> dict:
    """joint name -> 4x4 world frame of its actuator (vendor frame: horn axis +Z)."""
    C = np.eye(4)
    C[1, 3], C[2, 3] = DY, ZC
    C = C @ _ry90()
    out = {}
    for side, names in (("radial", RADIAL_JOINTS), ("ulnar", ULNAR_JOINTS)):
        k = 0
        for ty in STATIONS:
            for tx in COLUMNS:
                T = np.eye(4)
                T[:3, 3] = (tx, ty, ROW_TZ[side])
                if side == "ulnar":
                    T[:3, :3] = np.diag([1.0, -1.0, -1.0])     # Rx(180)
                out[names[k]] = C @ T
                k += 1
    return out


def spool_radii() -> dict:
    r = ht.spool_radii_mm("idler", r_min=SPOOL_R_MIN, r_max=SPOOL_R_MAX)
    return dict(zip(hk._JOINT_ORDER, (float(v) for v in r)))


def _spool(rd):
    """Pull-pull drum on the horn (vendor frame).  4x M2 on R6 into the horn."""
    z = HORN_TOP
    s = _fuse(_cyl(8.0, 1.5, (0, 0, z), (0, 0, 1)), _cyl(rd, 6.0, (0, 0, z + 1.5), (0, 0, 1)),
              _cyl(rd + 1.0, 0.8, (0, 0, z + 4.1), (0, 0, 1)), _cyl(rd + 1.0, 0.8, (0, 0, z + 7.5), (0, 0, 1)))
    cuts = [_cyl(1.1, 1.7, (6 * math.cos(a), 6 * math.sin(a), z - 0.1), (0, 0, 1))
            for a in (0, math.pi / 2, math.pi, 1.5 * math.pi)]
    cuts += [_cyl(0.35, 2 * rd + 2, (-rd - 1, 0, z + 2.8), (1, 0, 0)),
             _cyl(0.35, 2 * rd + 2, (0, -rd - 1, z + 6.2), (0, 1, 0))]     # strand anchors
    return _ok(_cut(s, *cuts), "spool")


# --- forearm structure ---------------------------------------------------------------------
def _sec(y, shrink=0.2):
    hx, z0, z1, r = INNER
    return rrect_wire(hx - shrink, z0 + shrink, z1 - shrink, r - shrink, y)


def _wrist():
    cq = _cq()
    y0, y1, y2 = WRIST_Y
    s = _fuse(cq.Solid.makeLoft([_sec(y0), _sec(y1)], True),
              cq.Solid.makeLoft([_sec(y1), rrect_wire(32.0, -14.0, 3.5, 4.0, y2)], False))
    cuts = [_box(-SPINE_HALF - 0.1, SPINE_HALF + 0.1, y0 - 1, y1, PLATE_Z[0] - 0.1, PLATE_Z[1] + 0.1)]
    cuts += [_cyl(BONE_R + 0.1, y1 - y0 + 1.5, (sx * BONE_XZ[0], y0 - 1, BONE_XZ[1]), (0, 1, 0)) for sx in (1, -1)]
    cuts += [_cyl(0.6, y2 - y0 + 2, (x, y0 - 1, z), (0, 1, 0)) for x, z in tendon_entries()]
    cuts += [_cyl(1.65, 100, (-50, -64.0, z), (1, 0, 0)) for z in (10.0, -18.0)]        # M3 cross bolts
    cuts += [_cyl(2.2, y2 - y0 + 2, (x, y0 - 1, -9.0), (0, 1, 0)) for x in (-20.0, 20.0)]
    cuts += [_cyl(3.6, 4.0, (x, y0 - 0.01, -9.0), (0, 1, 0)) for x in (-20.0, 20.0)]   # M4 heads
    cuts += _shell_pilots(-64.0)
    return _ok(_cut(s, *cuts), "wrist_block")


def _shell_pilots(y):
    hx, z0, z1, _ = INNER
    return [_cyl(1.25, 7.0, (x, y, z), (0, 0, d)) for x in (-30.0, 30.0)
            for z, d in ((z0 - 0.5, 1), (z1 + 0.5, -1))]


def _elbow():
    cq = _cq()
    e0, e1 = ELBOW_Y
    a0, a1 = ADAPTER_Y
    s = _fuse(cq.Solid.makeLoft([_sec(e0), _sec(e1)], True),
              _cyl(ADAPTER_R, a1 - a0, (0, a0, ZC), (0, 1, 0)))
    cuts = [_box(-SPINE_HALF - 0.1, SPINE_HALF + 0.1, PLATE_Y[0], e1 + 0.1, PLATE_Z[0] - 0.1, PLATE_Z[1] + 0.1)]
    cuts += [_cyl(BONE_R + 0.1, BONE_Y[0] - 0.1 - e1 if False else 4.2, (sx * BONE_XZ[0], e1 + 0.1, BONE_XZ[1]),
                  (0, -1, 0)) for sx in (1, -1)]
    for deg in FLANGE_HOLES_DEG:
        x = FLANGE_PCD / 2 * math.cos(math.radians(deg))
        z = ZC + FLANGE_PCD / 2 * math.sin(math.radians(deg))
        cuts += [_cyl(3.3, e1 - a0 + 0.2, (x, a0 - 0.1, z), (0, 1, 0)),          # M6 clearance
                 _cyl(5.5, e1 - (a0 + 6.0) + 0.1, (x, a0 + 6.0, z), (0, 1, 0))]  # head pocket
    dx = FLANGE_PCD / 2 * math.cos(math.radians(DOWEL_DEG))
    dz = ZC + FLANGE_PCD / 2 * math.sin(math.radians(DOWEL_DEG))
    cuts.append(_cyl(2.55, 6.0, (dx, a0 - 0.1, dz), (0, 1, 0)))                  # phi 5 dowel
    cuts += [_cyl(1.65, 100, (-50, -288.0, z), (1, 0, 0)) for z in (6.0, -10.0)]
    cuts += _shell_pilots(-290.0)
    return _ok(_cut(s, *cuts), "elbow_mount")


def _plate(sign, frames):
    x0, x1 = (0.0, SPINE_HALF) if sign > 0 else (-SPINE_HALF, 0.0)
    s = _box(x0, x1, PLATE_Y[0], PLATE_Y[1], PLATE_Z[0], PLATE_Z[1])
    cuts = []
    names = RADIAL_JOINTS if sign > 0 else ULNAR_JOINTS
    for n in names:
        T = frames[n]
        c = T[:3, 3]
        cuts.append(_cyl(9.0, 2 * SPINE_HALF + 0.2, (-SPINE_HALF - 0.1, c[1], c[2]), (1, 0, 0)))
        for hx, hy in CASE_HOLES:
            p = (T @ np.array([hx, hy, 0.0, 1.0]))[:3]
            cuts.append(_cyl(1.1, SPINE_HALF + 0.2, (x0 - 0.1, p[1], p[2]), (1, 0, 0)))
            inner_face = 0.0
            cuts.append(_cyl(2.1, 2.5, (inner_face - (2.5 if sign < 0 else 0), p[1], p[2]), (1, 0, 0)))
    for y in (-64.0, -288.0):
        cuts += [_cyl(1.65, 2 * SPINE_HALF + 0.2, (-SPINE_HALF - 0.1, y, z), (1, 0, 0))
                 for z in ((10.0, -18.0) if y > -100 else (6.0, -10.0))]
    for y in (-101.0, -143.0, -185.0, -227.0, -269.0):                       # spine join bolts
        cuts.append(_cyl(1.65, 2 * SPINE_HALF + 0.2, (-SPINE_HALF - 0.1, y, ZC), (1, 0, 0)))
    return _ok(_cut(s, *cuts), "spine_plate")


def _covers():
    cq = _cq()
    hx, z0, z1, r = INNER
    t = SHELL_T
    y0, y1 = ELBOW_Y[0], WRIST_Y[1]
    mid = (y0 + y1) / 2
    outer = cq.Solid.makeLoft([rrect_wire(hx + t, z0 - t, z1 + t, r + t, y0),
                               rrect_wire(hx + t + 2.5, z0 - t - 1.5, z1 + t + 1.5, r + t + 2, mid),
                               rrect_wire(hx + t, z0 - t, z1 + t, r + t, y1)], False)
    shell = _cut(outer, _prism(hx, z0, z1, r, y0 - 1, y1 + 1))
    holes = []
    for y in (-64.0, -290.0):
        for x in (-30.0, 30.0):
            holes += [_cyl(1.7, 12, (x, y, z0 - 10), (0, 0, 1)), _cyl(1.7, 12, (x, y, z1 - 2), (0, 0, 1))]
    holes.append(_cyl(5.0, 15, (20.0, -280.0, z1 - 2), (0, 0, 1)))      # power/TTL cable port
    shell = _cut(shell, *holes)
    dorsal = _ok(_cut(shell, _box(-80, 80, y0 - 5, y1 + 5, ZC, 80)), "cover_dorsal")
    palmar = _ok(_cut(shell, _box(-80, 80, y0 - 5, y1 + 5, -80, ZC)), "cover_palmar")
    return dorsal, palmar


def build_forearm(include_actuators=True) -> dict:
    frames = actuator_frames()
    parts = {"wrist_block": _wrist(), "elbow_mount": _elbow(),
             "spine_plate_radial": _plate(1, frames), "spine_plate_ulnar": _plate(-1, frames)}
    for sx, nm in ((1, "bone_radius_cf_tube"), (-1, "bone_ulna_cf_tube")):
        tube = _cut(_cyl(BONE_R, BONE_Y[1] - BONE_Y[0], (sx * BONE_XZ[0], BONE_Y[0], BONE_XZ[1]), (0, 1, 0)),
                    _cyl(4.0, BONE_Y[1] - BONE_Y[0] + 2, (sx * BONE_XZ[0], BONE_Y[0] - 1, BONE_XZ[1]), (0, 1, 0)))
        parts[nm] = _ok(tube, nm)
    parts["cover_dorsal"], parts["cover_palmar"] = _covers()
    radii = spool_radii()
    for n, T in frames.items():
        parts[f"spool_{n}"] = place(_spool(radii[n]), T)
    if include_actuators:
        act = load_vendor_actuator()
        for n, T in frames.items():
            parts[f"actuator_{n}"] = place(act, T)
    return parts
