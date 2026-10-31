"""
hand_geometry.py  --  Mechanical solids for the proposed 20-DOF hand.
======================================================================
DISCLAIMER: All dimensions are proposed design targets only.
Not fabrication-ready, not collision-free guaranteed, not FEA-verified.
kind = 'proposed_20dof_hand_not_fabrication_ready'
"""
import importlib, math
import numpy as np

# ---------------------------------------------------------------------------
# Lazy kernel import
# ---------------------------------------------------------------------------

def _cq():
    try:
        return importlib.import_module("cadquery")
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Primitive helpers (all return CadQuery Shape/Solid objects)
# ---------------------------------------------------------------------------

def _box(cq, cx, cy, cz, dx, dy, dz):
    """Box centered at (cx,cy,cz) with full dims dx,dy,dz."""
    s = cq.Workplane("XY").box(dx, dy, dz).val()
    return s.translate(cq.Vector(cx, cy, cz))


def _cyl_z(cq, cx, cy, z0, z1, r):
    return cq.Solid.makeCylinder(r, z1 - z0,
                                 cq.Vector(cx, cy, z0), cq.Vector(0, 0, 1))


def _cyl_x(cq, x0, x1, cy, cz, r):
    return cq.Solid.makeCylinder(r, x1 - x0,
                                 cq.Vector(x0, cy, cz), cq.Vector(1, 0, 0))


def _fuse(cq, *solids):
    s = solids[0]
    for o in solids[1:]:
        s = s.fuse(o)
    return s


def _cut(cq, base, *tools):
    s = base
    for t in tools:
        s = s.cut(t)
    return s


def _check(solid, name):
    if (solid is None or not solid.isValid() or len(solid.Solids()) != 1
            or not math.isfinite(solid.Volume()) or solid.Volume() <= 0):
        raise ValueError(f"Invalid solid '{name}': isValid={getattr(solid,'isValid',lambda:None)()}"
                         f" Volume={getattr(solid,'Volume',lambda:0)():.4f}")
    return solid


# ---------------------------------------------------------------------------
# Palm
# ---------------------------------------------------------------------------

def _make_palm(cq, hd):
    pw, pl, thick = hd["palm_width_mm"], hd["palm_length_mm"], 6.0
    r_corner = 8.0
    # Rounded-rectangle extrusion: inner rect offset outward by r_corner
    palm = (cq.Workplane("XY")
            .rect(pw - 2 * r_corner, pl - 2 * r_corner)
            .offset2D(r_corner, "arc")
            .extrude(thick)
            .val()
            .translate(cq.Vector(0, 0, -thick)))   # z: -6 to 0

    # Fuse unbored bosses with plate first, then bore through entire palm+boss Z
    boss_r, boss_top, bore_r = 3.0, 7.7, 1.2
    unbored_bosses = []
    for fdata in hd["fingers"].values():
        rx, ry = fdata["root_mm"][0], fdata["root_mm"][1]
        unbored_bosses.append(_cyl_z(cq, rx, ry, 0.0, boss_top, boss_r))

    fused = _fuse(cq, palm, *unbored_bosses)

    # Bore through whole palm+boss: Z[-6.1, 7.8]
    bore_cuts = []
    for fdata in hd["fingers"].values():
        rx, ry = fdata["root_mm"][0], fdata["root_mm"][1]
        bore_cuts.append(_cyl_z(cq, rx, ry, -6.1, 7.8, bore_r))

    return _check(_cut(cq, fused, *bore_cuts), "palm")


# ---------------------------------------------------------------------------
# Carrier  (local origin = yaw joint centre)
# ---------------------------------------------------------------------------

def _make_carrier(cq, cl):
    """cl = carrier_length_mm (must be >= 11).

    Geometry (all Z in [-2,2]):
      - Yaw post: R5, z[-2,2]
      - Central bridge: x[-8,8], y[0,5], z[-2,2]
      - Fork ears: R6 cylinders axis-X at Y=cl, x[-8,-3.4] and [3.4,8]
      - Outboard connectors: x[-8,-3.4] and [3.4,8], y[cl-8,cl-3], z[-2,2]
        (connect bridge to ears, bypassing central child tongue x[-3,3])
      - Yaw bore: R1.2 through Z at origin
      - Fork bore: R1.2 through X at Y=cl
    """
    if cl < 11:
        raise ValueError(f"carrier_length_mm must be >= 11, got {cl}")
    post   = _cyl_z(cq, 0, 0, -2.0, 2.0, 5.0)
    bridge = _box(cq, 0, 2.5, 0, 16.0, 5.0, 4.0)    # x[-8,8] y[0,5] z[-2,2]
    # Fork ears: axis X, radius 6, centred at (Y=cl, Z=0)
    ear1 = _cyl_x(cq, -8.0, -3.4, cl, 0.0, 6.0)
    ear2 = _cyl_x(cq,  3.4,  8.0, cl, 0.0, 6.0)
    # Outboard connectors bypass central child tongue (x[-3,3])
    # x[-8,-3.4] and [3.4,8], y[cl-8, cl-3], z[-2,2]
    cx1 = (-8.0 + (-3.4)) / 2   # = -5.7
    cx2 = ( 3.4 +   8.0)  / 2   # =  5.7
    cdx = 8.0 - 3.4               # = 4.6
    cy_con = cl - 5.5              # centre of [cl-8, cl-3] = cl-8+2.5 = cl-5.5
    con1 = _box(cq, cx1, cy_con, 0, cdx, 5.0, 4.0)
    con2 = _box(cq, cx2, cy_con, 0, cdx, 5.0, 4.0)
    solid = _fuse(cq, post, bridge, ear1, ear2, con1, con2)
    # Bores
    bz = _cyl_z(cq, 0, 0, -2.1, 2.1, 1.2)           # yaw bore Z through (0,0)
    bx = _cyl_x(cq, -8.1, 8.1, cl, 0.0, 1.2)        # fork bore X at Y=cl
    return _check(_cut(cq, solid, bz, bx), "carrier")


# ---------------------------------------------------------------------------
# Phalange  (proximal / middle / distal)
# ---------------------------------------------------------------------------

def _make_phalange(cq, L, is_distal):
    # Tongue at joint origin (Y=0)
    tcyl = _cyl_x(cq, -3.0,  3.0, 0.0, 0.0, 5.5)   # radius 5.5 x[-3,3]
    tbox = _box(cq, 0, 4.5, 0, 6.0, 9.0, 9.0)        # x[-3,3] y[0,9] z[-4.5,4.5]
    tongue = _fuse(cq, tcyl, tbox)

    # Main bar: starts y=6.4 to leave 0.4mm radial clearance against R6 parent fork
    by0, by1 = 6.4, L - 8.0
    bar = _box(cq, 0, (by0 + by1) / 2, 0, 11.0, by1 - by0, 9.0)
    solid = _fuse(cq, tongue, bar)

    if not is_distal:
        # Far fork: central bridge y[L-10, L-7], outboard connectors y[L-9, L-3]
        # outside child tongue x[-3,3], z[-4.5,4.5]
        cb  = _box(cq, 0, L - 8.5, 0, 16.0, 3.0, 9.0)         # y[L-10, L-7]
        fcon1 = _box(cq, -5.7, L - 6.0, 0, 4.6, 6.0, 9.0)     # x[-8,-3.4] y[L-9,L-3]
        fcon2 = _box(cq,  5.7, L - 6.0, 0, 4.6, 6.0, 9.0)     # x[3.4,8] y[L-9,L-3]
        ce1 = _cyl_x(cq, -8.0, -3.4, L, 0.0, 6.0)
        ce2 = _cyl_x(cq,  3.4,  8.0, L, 0.0, 6.0)
        solid = _fuse(cq, solid, cb, fcon1, fcon2, ce1, ce2)
        bxd = _cyl_x(cq, -8.1, 8.1, L, 0.0, 1.2)
        solid = _cut(cq, solid, bxd)
    else:
        # Rounded distal tip
        tip = _cyl_x(cq, -5.5, 5.5, L - 5.0, 0.0, 5.0)
        solid = _fuse(cq, solid, tip)

    # Root bore (through tongue along X)
    bxr = _cyl_x(cq, -3.1, 3.1, 0.0, 0.0, 1.2)
    return _check(_cut(cq, solid, bxr),
                  f"phal_L{L}_{'dist' if is_distal else 'prox'}")


# ---------------------------------------------------------------------------
# Transform a local solid into world frame via FK 4x4 matrix
# ---------------------------------------------------------------------------

def _place(cq, solid, mat4):
    from OCP.gp import gp_Trsf
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    transform = gp_Trsf()
    transform.SetValues(*[float(v) for v in mat4[:3, :].reshape(-1)])
    return cq.Shape.cast(BRepBuilderAPI_Transform(solid.wrapped, transform, True).Shape())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_hand(angles_deg) -> dict:
    """
    Build all 21 hand solids placed in world frame.

    Parameters
    ----------
    angles_deg : dict (20 keys) or list/tuple/ndarray (20 elements).
        Validated strictly by forward_kinematics; no defaults.

    Returns
    -------
    dict with keys:
        parts         : dict {name -> CadQuery solid}  palm + 20 link names
        kinematics    : FK result dict
        clearances_mm : design-target clearance values
        kind          : 'proposed_20dof_hand_not_fabrication_ready'
    """
    _cqm = _cq()
    if _cqm is None:
        raise ImportError("cadquery is required for build_hand")

    # Import here to avoid circular at module level
    from hand_kinematics import (
        hand_dimensions, forward_kinematics)

    hd = hand_dimensions()
    fk = forward_kinematics(angles_deg)   # raises on invalid angles
    links = fk["links"]
    cl = hd["carrier_length_mm"]

    parts = {}
    parts["palm"] = _place(_cqm, _make_palm(_cqm, hd), links["palm"])

    _SFXS = ("carrier", "proximal", "middle", "distal")
    for fname, fdata in hd["fingers"].items():
        segs = fdata["lengths_mm"]   # [prox, mid, dist]
        for i, sfx in enumerate(_SFXS):
            lname = f"{fname}_{sfx}"
            mat   = links[lname]
            if sfx == "carrier":
                local = _make_carrier(_cqm, cl)
            else:
                seg_i   = i - 1          # 0=proximal,1=middle,2=distal
                L       = segs[seg_i]
                local   = _make_phalange(_cqm, L, sfx == "distal")
            parts[lname] = _place(_cqm, local, mat)

    clearances = {
        "carrier_yaw_axial_gap_mm": 0.3,
        "tongue_side_clearance_mm": 0.4,
        "bore_nominal_diam_mm":     2.4,
    }
    return {
        "parts":        parts,
        "kinematics":   fk,
        "clearances_mm": clearances,
        "kind":         "proposed_20dof_hand_not_fabrication_ready",
    }
