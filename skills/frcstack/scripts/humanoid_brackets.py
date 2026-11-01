"""
humanoid_brackets.py -- clearance solver and J-frame builders for ST3215 U-brackets, idler plates,
case cradles and the simplified servo envelopes used for interference checks.

J frame (derived from the vendor ST3215 STEP): origin on the output axis mid-way between the horn
faces, z = output axis (towards the splined horn), x = along the case away from the axis.
Case x[-10.11, 35.11]  y[-12.36, 12.36]  z[-18.475, 16.525]; rear boss r3.4 to z = -19.175;
horn (front) and idler (rear) discs r9.6 with faces at z = +-18.625, 4x M3 on a 14 mm PCD.
Vendor M2 case holes at x = 29.0 (front face) and x = 32.8 (rear face), y = +-10.2.

U-bracket = MAIN part (front plate on the splined horn + bridge) + IDLER part (rear plate with a
1 mm spacer ring, bolted to the bridge end with 2x M3 into heat-set inserts) so the servo can be
slid in before the idler plate is fitted.  The bridge sits at radius R in direction phi (J x-y).
Cradle = C-clamp over the far end of the case (front/rear plates + end wall with a cable window),
4x M2 into the vendor tapped holes.
PROPOSED DESIGN -- not built or tested.
"""
from __future__ import annotations

import math

import numpy as np

HF = 18.625
T = 3.0
TB = 4.0
ARM_R = 12.0
BRIDGE_HW = 12.0
CASE_X = (-10.11, 35.11)
CASE_Y = 12.36
CASE_Z = (-18.475, 16.525)
CR_W = 2.5
CR_END = CASE_X[1] + 3.0
CR_Y = CASE_Y + CR_W
CR_Z = (CASE_Z[0] - CR_W, CASE_Z[1] + CR_W)
MARGIN = 1.0
Z_IDLER_IN = -HF - 1.0           # idler plate inner face (spacer ring between it and the idler disc)
Z_LO = Z_IDLER_IN - T
Z_HI = HF + T


# --------------------------------------------------------------------------- 2-D helpers
def _cross2(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def hull2d(P):
    P = np.asarray(P, float)
    P = P[np.lexsort((P[:, 1], P[:, 0]))]

    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and _cross2(h[-1] - h[-2], p - h[-2]) <= 1e-12:
                h.pop()
            h.append(p)
        return h
    lo, hi = half(P), half(P[::-1])
    return np.array(lo[:-1] + hi[:-1])


def circle(cx, cy, r, n=48):
    return [(cx + r * math.cos(t), cy + r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, n, endpoint=False)]


def _rect(x0, x1, y0, y1):
    return np.array([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], float)


def _rot2(P, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.asarray(P) @ np.array([[c, s], [-s, c]])


def _overlap(P, Q) -> bool:
    for poly in (P, Q):
        n = len(poly)
        for i in range(n):
            e = poly[(i + 1) % n] - poly[i]
            ax = np.array([-e[1], e[0]])
            a, b = P @ ax, Q @ ax
            if a.max() <= b.min() + 1e-9 or b.max() <= a.min() + 1e-9:
                return False
    return True


def bridge_poly(phi, R):
    u = np.array([math.cos(math.radians(phi)), math.sin(math.radians(phi))])
    v = np.array([-u[1], u[0]])
    return np.array([R * u - BRIDGE_HW * v, (R + TB) * u - BRIDGE_HW * v,
                     (R + TB) * u + BRIDGE_HW * v, R * u + BRIDGE_HW * v])


def plate_hull(phi, R):
    return hull2d(circle(0, 0, ARM_R) + list(bridge_poly(phi, R)))


def _dense(hull, step=0.5):
    out = []
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        k = max(2, int(np.linalg.norm(b - a) / step))
        out += [a + (b - a) * t for t in np.linspace(0, 1, k, endpoint=False)]
    return np.array(out)


def solve(phi, alphas, r_min=14.0):
    """Smallest bridge radius R and cradle start xc so the bracket clears case + cradle for all alphas
    (alpha = rotation of the bracket relative to the case about J z, degrees)."""
    alphas = list(alphas)
    for R in np.arange(r_min, 60.0, 0.5):
        dense = _dense(plate_hull(phi, R))
        xc = 13.5
        for a in alphas:
            P = _rot2(dense, a)
            m = np.abs(P[:, 1]) <= CR_Y + MARGIN
            if m.any():
                xc = max(xc, P[m, 0].max() + 1.5)
        if xc > 27.0:
            continue
        keep = [_rect(CASE_X[0] - MARGIN, CR_END + MARGIN, -CASE_Y - MARGIN, CASE_Y + MARGIN),
                _rect(xc - MARGIN, CR_END + MARGIN, -CR_Y - MARGIN, CR_Y + MARGIN)]
        b = bridge_poly(phi, R)
        if not any(_overlap(_rot2(b, a), c) for a in alphas for c in keep):
            return float(R), float(xc)
    raise ValueError(f"no clear bracket for phi={phi}")


# --------------------------------------------------------------------------- 3-D primitives
def _cq():
    import cadquery as cq
    return cq


def prism(P2, z0, z1):
    """Extrude a 2-D polygon (J x-y) between z0 and z1."""
    cq = _cq()
    w = cq.Wire.makePolygon([cq.Vector(float(x), float(y), z0) for x, y in P2], close=True)
    return cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), cq.Vector(0, 0, z1 - z0))


def cyl_z(r, z0, z1, x=0.0, y=0.0):
    cq = _cq()
    return cq.Solid.makeCylinder(r, z1 - z0, cq.Vector(x, y, z0), cq.Vector(0, 0, 1))


def box(x0, x1, y0, y1, z0, z1):
    cq = _cq()
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


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


def _horn_holes(z0, z1):
    out = [cyl_z(4.0, z0 - 1, z1 + 1)]
    for k in range(4):
        t = math.pi / 4 + k * math.pi / 2
        out.append(cyl_z(1.7, z0 - 1, z1 + 1, 7 * math.cos(t), 7 * math.sin(t)))
    return out


def _bridge_bolts(phi, R, z0, z1, r):
    u = np.array([math.cos(math.radians(phi)), math.sin(math.radians(phi))])
    v = np.array([-u[1], u[0]])
    c = (R + TB / 2) * u
    return [cyl_z(r, z0, z1, *(c + k * 7.0 * v)) for k in (-1, 1)]


# --------------------------------------------------------------------------- 3-D builders (J frame)
def bracket_main(phi, R):
    hull = plate_hull(phi, R)
    s = fuse(prism(hull, HF, Z_HI), prism(bridge_poly(phi, R), Z_IDLER_IN, Z_HI))
    return cut(s, *_horn_holes(Z_LO, Z_HI), *_bridge_bolts(phi, R, Z_IDLER_IN, Z_IDLER_IN + 7, 2.0))


def bracket_idler(phi, R):
    s = fuse(prism(plate_hull(phi, R), Z_LO, Z_IDLER_IN),
             cyl_z(9.0, Z_IDLER_IN, -HF).cut(cyl_z(4.5, Z_IDLER_IN, -HF)))
    return cut(s, *_horn_holes(Z_LO, Z_HI), *_bridge_bolts(phi, R, Z_LO - 1, Z_IDLER_IN + 1, 1.7))


def bridge_face(phi, R):
    """2-D footprint (J x-y) of the bridge outer face, for joining structure to it."""
    return bridge_poly(phi, R)


def cradle(xc):
    front = box(xc, CR_END, -CR_Y, CR_Y, CASE_Z[1], CR_Z[1])
    rear = box(xc, CR_END, -CR_Y, CR_Y, CR_Z[0], CASE_Z[0])
    end = box(CASE_X[1], CR_END, -CR_Y, CR_Y, CR_Z[0], CR_Z[1])
    s = cut(fuse(front, rear, end), box(CASE_X[1] - 1, CR_END + 1, -9.0, 9.0, -12.0, 10.0))
    holes = [cyl_z(1.1, CR_Z[0] - 1, CR_Z[1] + 1, x, y) for x in (29.0, 32.8) if x - 2.5 > xc
             for y in (-10.2, 10.2)]
    return cut(s, *holes) if holes else s


def st_envelope():
    s = box(CASE_X[0], CASE_X[1], -CASE_Y, CASE_Y, CASE_Z[0], CASE_Z[1])
    s = fuse(s, cyl_z(9.6, CASE_Z[1] - 0.2, HF), cyl_z(9.6, -HF, CASE_Z[0] + 0.2))
    return fuse(s, cyl_z(3.4, -HF - 0.55, -HF + 0.2))


# SC09 (Waveshare, 23.2 x 12.0 x 25.5 mm, 21 g).  APPROXIMATE envelope, no vendor CAD available:
# J frame origin on the output shaft at the top face, z = shaft, body x[-5.8, 17.4] y+-6 z[-22, 0].
SC_BODY = (-5.8, 17.4, -6.0, 6.0, -22.0, 0.0)
SC_SHAFT = (3.0, 3.5)


def sc09_envelope():
    return fuse(box(*SC_BODY), cyl_z(SC_SHAFT[0], -0.2, SC_SHAFT[1]))
