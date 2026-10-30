"""
frame_geometry.py - Proposed rectangular chassis frame layout via CadQuery.

Public API
----------
build_frame(parameters: dict) -> dict
    keys: parts, cut_list, expected_volume_mm3, parameters

NOTE: This is a proposed rectangular chassis foundation.  Outer dimensions are
motivated by published 635 x 812.8 mm and 2x1x0.0625 in stock references.
Corner chamfers, custom split rails, module mounts, and hole patterns are NOT
implemented or claimed verified.
"""

import math
from typing import Any

# ---------------------------------------------------------------------------
# Lazy CadQuery import
# ---------------------------------------------------------------------------
_cq = None


def _cadquery():
    global _cq
    if _cq is None:
        import cadquery as cq
        _cq = cq
    return _cq


# ---------------------------------------------------------------------------
# Validation helpers (same conventions as parts_geometry.py)
# ---------------------------------------------------------------------------
_DIM_MIN = 0.01
_DIM_MAX = 10_000.0

_REQUIRED_KEYS = frozenset({
    "width_mm", "length_mm", "stock_width_mm", "stock_height_mm",
    "wall_mm", "crossbar_spacing_mm",
})


def _num(value: Any, name: str) -> float:
    if isinstance(value, bool) or isinstance(value, str):
        raise TypeError(
            f"{name}: must be numeric (int or float), got {type(value).__name__}"
        )
    if not isinstance(value, (int, float)):
        raise TypeError(
            f"{name}: must be numeric (int or float), got {type(value).__name__}"
        )
    try:
        f = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name}: number exceeds finite float range") from exc
    if not math.isfinite(f):
        raise ValueError(f"{name}: must be finite, got {value}")
    return f


def _pos_dim(value: Any, name: str) -> float:
    f = _num(value, name)
    if not (_DIM_MIN <= f <= _DIM_MAX):
        raise ValueError(
            f"{name}: must be in [{_DIM_MIN}, {_DIM_MAX}], got {f}"
        )
    return f


def _validate(params: dict):
    """
    Validate all six required parameters and return (W, L, b, h, t, sp).

    W   = width_mm            outer chassis width  (X)
    L   = length_mm           outer chassis length (Y)
    b   = stock_width_mm      tube cross-section narrow dim
    h   = stock_height_mm     tube cross-section tall dim
    t   = wall_mm             wall thickness
    sp  = crossbar_spacing_mm center-to-center Y spacing of the two crossbars
    """
    if not isinstance(params, dict):
        raise TypeError(
            f"parameters must be dict, got {type(params).__name__}"
        )
    missing = _REQUIRED_KEYS - params.keys()
    extra   = params.keys() - _REQUIRED_KEYS
    if missing:
        raise ValueError(f"build_frame: missing parameters: {sorted(missing)}")
    if extra:
        raise ValueError(f"build_frame: unexpected parameters: {sorted(extra)}")

    W  = _pos_dim(params["width_mm"],            "width_mm")
    L  = _pos_dim(params["length_mm"],            "length_mm")
    b  = _pos_dim(params["stock_width_mm"],       "stock_width_mm")
    h  = _pos_dim(params["stock_height_mm"],      "stock_height_mm")
    t  = _pos_dim(params["wall_mm"],              "wall_mm")
    sp = _pos_dim(params["crossbar_spacing_mm"],  "crossbar_spacing_mm")

    # Structural guards (exact conditions from spec)
    if 2.0 * t >= b:
        raise ValueError(
            f"2*wall_mm ({2*t}) must be < stock_width_mm ({b})"
        )
    if 2.0 * t >= h:
        raise ValueError(
            f"2*wall_mm ({2*t}) must be < stock_height_mm ({h})"
        )
    if W <= 2.0 * b:
        raise ValueError(
            f"width_mm ({W}) must be > 2*stock_width_mm ({2*b})"
        )
    if L <= 3.0 * b:
        raise ValueError(
            f"length_mm ({L}) must be > 3*stock_width_mm ({3*b})"
        )
    if sp <= b:
        raise ValueError(
            f"crossbar_spacing_mm ({sp}) must be > stock_width_mm ({b})"
        )
    if sp >= L - 3.0 * b:
        raise ValueError(
            f"crossbar_spacing_mm ({sp}) must be < length_mm - 3*stock_width_mm "
            f"({L - 3.0*b:.6g})"
        )

    return W, L, b, h, t, sp


# ---------------------------------------------------------------------------
# Geometry helper
# ---------------------------------------------------------------------------

def _hollow_tube(cq, cx: float, cy: float, cz_center: float,
                 dx: float, dy: float, dz: float,
                 wall: float, long_axis: str):
    """
    Return a single hollow rectangular tube CadQuery solid.

    cx, cy, cz_center : center of the outer bounding box
    dx, dy, dz        : outer dimensions along X, Y, Z
    wall              : wall thickness (applied to the two transverse faces)
    long_axis         : 'X' or 'Y' -- bore runs through this axis; bore extends
                        2 mm beyond each end face to ensure open tube ends
    """
    eps = 2.0  # mm -- bore overrun to guarantee open ends

    outer = (
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(cx, cy, cz_center))
        .box(dx, dy, dz, centered=(True, True, True))
    )

    if long_axis == 'Y':
        # Hollow cross-section is in X-Z plane; bore extends in Y
        ix, iy, iz = dx - 2.0 * wall, dy + eps, dz - 2.0 * wall
    else:  # 'X'
        # Hollow cross-section is in Y-Z plane; bore extends in X
        ix, iy, iz = dx + eps, dy - 2.0 * wall, dz - 2.0 * wall

    inner = (
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(cx, cy, cz_center))
        .box(ix, iy, iz, centered=(True, True, True))
    )

    return outer.cut(inner).val()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_frame(parameters: dict) -> dict:
    """
    Build a proposed rectangular chassis with six hollow rectangular tube rails.

    Coordinate convention
    ---------------------
    X = width direction, Y = length direction.
    Bottom face at Z = 0, top face at Z = stock_height_mm.
    Frame is centred at (0, 0) in XY.

    Rails
    -----
    left_rail      : outer X edge [-W/2, -W/2+b], full Y span [-L/2, L/2]
    right_rail     : outer X edge [W/2-b, W/2],   full Y span [-L/2, L/2]
    front_rail     : outer Y edge [-L/2, -L/2+b], X span between inner side faces
    rear_rail      : outer Y edge [L/2-b, L/2],   X span between inner side faces
    crossbar_front : centred at Y = -spacing/2, same X span as end rails
    crossbar_rear  : centred at Y = +spacing/2, same X span as end rails

    Butt-joint convention: end rails and crossbars span the clear X distance
    between the inner faces of the side rails (W - 2b).  No positive-volume
    overlap occurs.

    Parameters (all required, all int/float mm, no defaults)
    ----------
    width_mm, length_mm, stock_width_mm, stock_height_mm,
    wall_mm, crossbar_spacing_mm

    Returns
    -------
    dict
        parts               : {name: cadquery Shape solid}  -- six entries
        cut_list            : [{name, length_mm}]           -- six entries
        expected_volume_mm3 : float, analytic total material volume
        parameters          : dict of validated numeric values (echo)
    """
    W, L, b, h, t, sp = _validate(parameters)
    cq = _cadquery()

    cz         = h / 2.0       # Z-centre for all rails (bottom=0, top=h)
    inner_span = W - 2.0 * b   # X length of all cross-members

    # ------------------------------------------------------------------
    # Side rails  (long axis Y, tube cross-section b x h in XZ)
    # ------------------------------------------------------------------
    left_rail  = _hollow_tube(cq, -(W / 2.0 - b / 2.0), 0.0, cz,
                              b, L, h, t, 'Y')
    right_rail = _hollow_tube(cq,  (W / 2.0 - b / 2.0), 0.0, cz,
                              b, L, h, t, 'Y')

    # ------------------------------------------------------------------
    # Front / rear end rails  (long axis X, butt-jointed between side rails)
    # ------------------------------------------------------------------
    front_rail = _hollow_tube(cq, 0.0, -(L / 2.0 - b / 2.0), cz,
                              inner_span, b, h, t, 'X')
    rear_rail  = _hollow_tube(cq, 0.0,  (L / 2.0 - b / 2.0), cz,
                              inner_span, b, h, t, 'X')

    # ------------------------------------------------------------------
    # Interior crossbars  (long axis X, symmetric about Y = 0)
    # ------------------------------------------------------------------
    crossbar_front = _hollow_tube(cq, 0.0, -sp / 2.0, cz,
                                  inner_span, b, h, t, 'X')
    crossbar_rear  = _hollow_tube(cq, 0.0,  sp / 2.0, cz,
                                  inner_span, b, h, t, 'X')

    parts = {
        "left_rail":      left_rail,
        "right_rail":     right_rail,
        "front_rail":     front_rail,
        "rear_rail":      rear_rail,
        "crossbar_front": crossbar_front,
        "crossbar_rear":  crossbar_rear,
    }

    # ------------------------------------------------------------------
    # Analytic volume
    # Cross-section area = b*h - (b-2t)*(h-2t)  (same formula for all rails)
    # Total cut length   = 2L + 4*(W-2b)
    # ------------------------------------------------------------------
    cs_area = b * h - (b - 2.0 * t) * (h - 2.0 * t)
    total_vol = cs_area * (2.0 * L + 4.0 * inner_span)

    cut_list = [
        {"name": "left_rail",      "length_mm": L},
        {"name": "right_rail",     "length_mm": L},
        {"name": "front_rail",     "length_mm": inner_span},
        {"name": "rear_rail",      "length_mm": inner_span},
        {"name": "crossbar_front", "length_mm": inner_span},
        {"name": "crossbar_rear",  "length_mm": inner_span},
    ]

    return {
        "parts":               parts,
        "cut_list":            cut_list,
        "expected_volume_mm3": total_vol,
        "parameters": {
            "width_mm":            W,
            "length_mm":           L,
            "stock_width_mm":      b,
            "stock_height_mm":     h,
            "wall_mm":             t,
            "crossbar_spacing_mm": sp,
        },
    }
