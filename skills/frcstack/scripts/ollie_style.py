"""
ollie_style.py -- faceted 'fairing' modelling helpers for OLLIE v2.

Shapes are made by three-view carving: a silhouette in each view is extruded through the part and the
extrusions are intersected, which gives the sharp, faceted bodywork of a sport bike fairing.  Every
face comes from one silhouette, so insetting each silhouette by t gives a wall of thickness t.
Views: 'x' = front (y, z) extruded along X, 'y' = side (x, z) along Y, 'z' = top (x, y) along Z.
"""
from __future__ import annotations

import cadquery as cq

_AX = {"x": 0, "y": 1, "z": 2}
BIG = 3000.0


def _v(p, axis, a):
    u, w = float(p[0]), float(p[1])
    return {"x": cq.Vector(a, u, w), "y": cq.Vector(u, a, w), "z": cq.Vector(u, w, a)}[axis]


def _area(w):
    return cq.Face.makeFromWires(w).Area()


def _offset(wire, d):
    if not d:
        return wire
    a0 = _area(wire)
    cands = []
    for sd in (abs(d), -abs(d)):
        for kind in ("intersection", "arc"):
            try:
                ws = wire.offset2D(sd, kind)
            except Exception:  # noqa: BLE001  (OCC offset can fail on sharp notches)
                continue
            cands += [w for w in ws if w.isValid()]
            if ws:
                break
    want = [w for w in cands if (_area(w) < a0) == (d < 0)]
    if not want:
        raise ValueError(f"offset {d} failed")
    want.sort(key=_area)
    return want[-1] if d < 0 else want[0]


def prism(pts, axis, a0, a1, off=0.0):
    """Polygon (2-D in the view plane) extruded along axis from a0 to a1; off > 0 grows, < 0 insets."""
    w = cq.Wire.makePolygon([_v(p, axis, a0) for p in pts], close=True)
    w = _offset(w, off)
    d = [0.0, 0.0, 0.0]
    d[_AX[axis]] = a1 - a0
    return cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), cq.Vector(*d))


def carve(views: dict, off=0.0):
    out = None
    for axis, pts in views.items():
        s = prism(pts, axis, -BIG, BIG, off)
        out = s if out is None else out.intersect(s)
    return out.clean()


def shell(views: dict, t, open_axes=()):
    """Hollow carve with wall t.  open_axes e.g. ('-z', '+z') removes that end wall."""
    outer = carve(views)
    inner = carve(views, -t)
    out = outer.cut(inner)
    for oa in open_axes:
        d = [0.0, 0.0, 0.0]
        d[_AX[oa[1]]] = (t + 1.0) * (1 if oa[0] == "+" else -1)
        out = out.cut(inner.translate(cq.Vector(*d)))
    return out.clean(), outer, inner


def split(shape, region):
    """(inside, outside) of a region solid -- used for paint splits, so the halves only touch."""
    return shape.intersect(region).clean(), shape.cut(region).clean()


def plug(hole_prism_pts, axis, a0, a1, wall, inset=0.3):
    """The piece of a wall (solid) that fills a cut-out, inset so it only sits in the opening."""
    return prism(hole_prism_pts, axis, a0, a1, -inset).intersect(wall).clean()


def mirror_y(shape):
    return shape.mirror("XZ")


def fuse(*s):
    out = s[0]
    for o in s[1:]:
        out = out.fuse(o)
    return out.clean()


def cut(base, *tools):
    out = base
    for t in tools:
        out = out.cut(t)
    return out.clean()


def box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))
