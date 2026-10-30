"""
parts_geometry.py - Generate parametric FRC part geometry via CadQuery.

Public API:
    generate_part(kind, parameters) -> (cadquery.Shape, float)
    Returns a CadQuery solid and analytic volume in mm^3.
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
# Validation helpers
# ---------------------------------------------------------------------------
_DIM_MIN = 0.01
_DIM_MAX = 10_000.0
_XY_BOUND = 10_000.0

def _require_keys(params: dict, required: set, kind: str):
    missing = required - params.keys()
    extra   = params.keys() - required
    if missing:
        raise ValueError(f"{kind}: missing parameters: {missing}")
    if extra:
        raise ValueError(f"{kind}: unexpected parameters: {extra}")


def _num(value: Any, name: str) -> float:
    if isinstance(value, bool) or isinstance(value, str):
        raise TypeError(f"{name}: must be numeric (int or float), got {type(value).__name__}")
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name}: must be numeric (int or float), got {type(value).__name__}")
    try:
        f = float(value)
    except OverflowError as error:
        raise ValueError(f"{name}: number exceeds finite float range") from error
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


def _xy_coord(value: Any, name: str) -> float:
    f = _num(value, name)
    if not (-_XY_BOUND <= f <= _XY_BOUND):
        raise ValueError(f"{name}: must be in [-{_XY_BOUND}, {_XY_BOUND}], got {f}")
    return f


# ---------------------------------------------------------------------------
# Geometry builders
# ---------------------------------------------------------------------------

def _rect_tube(p: dict):
    _require_keys(p, {"width_mm", "height_mm", "wall_mm", "length_mm"}, "rect_tube")
    w  = _pos_dim(p["width_mm"],  "width_mm")
    h  = _pos_dim(p["height_mm"], "height_mm")
    t  = _pos_dim(p["wall_mm"],   "wall_mm")
    L  = _pos_dim(p["length_mm"], "length_mm")

    min_dim = min(w, h)
    if 2.0 * t >= min_dim:
        raise ValueError(
            f"rect_tube: wall_mm ({t}) too thick for width/height ({w}/{h}); "
            f"2*wall must be < min(width, height)"
        )

    cq = _cadquery()
    outer = (
        cq.Workplane("XY")
        .box(w, h, L, centered=(True, True, False))
    )
    inner = (
        cq.Workplane("XY")
        .box(w - 2*t, h - 2*t, L, centered=(True, True, False))
    )
    solid = outer.cut(inner).val()

    inner_w = w - 2*t
    inner_h = h - 2*t
    vol = (w * h - inner_w * inner_h) * L
    return solid, vol


def _round_tube(p: dict):
    _require_keys(p, {"outer_diameter_mm", "inner_diameter_mm", "length_mm"}, "round_tube")
    OD = _pos_dim(p["outer_diameter_mm"], "outer_diameter_mm")
    ID = _pos_dim(p["inner_diameter_mm"], "inner_diameter_mm")
    L  = _pos_dim(p["length_mm"],         "length_mm")

    if ID >= OD:
        raise ValueError(
            f"round_tube: inner_diameter_mm ({ID}) must be < outer_diameter_mm ({OD})"
        )

    cq = _cadquery()
    OR, IR = OD / 2.0, ID / 2.0
    outer = cq.Workplane("XY").circle(OR).extrude(L)
    inner = cq.Workplane("XY").circle(IR).extrude(L)
    solid = outer.cut(inner).val()

    vol = math.pi * (OR**2 - IR**2) * L
    return solid, vol


def _plate(p: dict):
    _require_keys(p, {"width_mm", "height_mm", "thickness_mm", "holes"}, "plate")

    w = _pos_dim(p["width_mm"],     "width_mm")
    h = _pos_dim(p["height_mm"],    "height_mm")
    t = _pos_dim(p["thickness_mm"], "thickness_mm")

    holes = p["holes"]
    if not isinstance(holes, list):
        raise TypeError("plate: 'holes' must be a list")
    if len(holes) > 64:
        raise ValueError(f"plate: at most 64 holes allowed, got {len(holes)}")

    parsed_holes = []
    for i, hole in enumerate(holes):
        if not isinstance(hole, dict):
            raise TypeError(f"plate: holes[{i}] must be a dict with x_mm, y_mm, diameter_mm")
        _require_keys(hole, {"x_mm", "y_mm", "diameter_mm"}, f"holes[{i}]")
        hx = _xy_coord(hole["x_mm"], f"holes[{i}].x_mm")
        hy = _xy_coord(hole["y_mm"], f"holes[{i}].y_mm")
        hd = _pos_dim(hole["diameter_mm"], f"holes[{i}].diameter_mm")
        hr = hd / 2.0

        # breakout check: hole circle must fit within plate extents (centered plate)
        if abs(hx) + hr >= w / 2.0:
            raise ValueError(f"plate: holes[{i}] breaks out in X (x={hx}, r={hr}, half-width={w/2})")
        if abs(hy) + hr >= h / 2.0:
            raise ValueError(f"plate: holes[{i}] breaks out in Y (y={hy}, r={hr}, half-height={h/2})")

        parsed_holes.append((hx, hy, hr))

    # overlap / tangency check between holes
    for i in range(len(parsed_holes)):
        for j in range(i + 1, len(parsed_holes)):
            x1, y1, r1 = parsed_holes[i]
            x2, y2, r2 = parsed_holes[j]
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist <= r1 + r2:
                raise ValueError(
                    f"plate: holes[{i}] and holes[{j}] overlap or are tangent "
                    f"(center distance {dist:.4f} <= {r1+r2:.4f})"
                )

    cq = _cadquery()
    solid = cq.Workplane("XY").box(w, h, t, centered=(True, True, False))
    for hx, hy, hr in parsed_holes:
        cyl = cq.Workplane("XY").transformed(offset=cq.Vector(hx, hy, 0)).circle(hr).extrude(t)
        solid = solid.cut(cyl)

    solid = solid.val()

    hole_vol = sum(math.pi * hr**2 * t for _, _, hr in parsed_holes)
    vol = w * h * t - hole_vol
    return solid, vol


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_BUILDERS = {
    "rect_tube":  _rect_tube,
    "round_tube": _round_tube,
    "plate":      _plate,
}

_VOL_TOL_REL = 1e-8   # Analytic vs BRep volume; absolute floor is 1e-5 mm^3.


def generate_part(kind: str, parameters: dict):
    """
    Generate a parametric FRC part.

    Parameters
    ----------
    kind : str
        One of 'rect_tube', 'round_tube', 'plate'.
    parameters : dict
        Kind-specific parameter dict (see module docstring).

    Returns
    -------
    shape : cadquery.occ_impl.shapes.Shape
        A single valid solid with positive volume.
    analytic_volume_mm3 : float
        Independent analytic volume in mm^3.

    Raises
    ------
    ValueError  -- invalid or out-of-range parameters
    TypeError   -- wrong type for a parameter
    """
    if not isinstance(kind, str):
        raise TypeError(f"kind must be str, got {type(kind).__name__}")
    if kind not in _BUILDERS:
        raise ValueError(f"Unknown part kind '{kind}'. Must be one of: {sorted(_BUILDERS)}")
    if not isinstance(parameters, dict):
        raise TypeError(f"parameters must be dict, got {type(parameters).__name__}")

    shape, analytic_vol = _BUILDERS[kind](parameters)

    if not math.isfinite(analytic_vol) or analytic_vol <= 0.0:
        raise ValueError(f"Analytic volume is non-positive: {analytic_vol}")

    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("Expected one valid solid")
    actual_volume = shape.Volume()
    if not math.isfinite(actual_volume) or actual_volume <= 0:
        raise ValueError("Generated volume must be positive and finite")
    if not math.isclose(actual_volume, analytic_vol, rel_tol=_VOL_TOL_REL, abs_tol=1e-5):
        raise ValueError("Generated BRep volume disagrees with independent analytic volume")

    return shape, analytic_vol
