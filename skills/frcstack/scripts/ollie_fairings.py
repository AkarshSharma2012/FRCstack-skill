"""
ollie_fairings.py -- OLLIE v2 bodywork + hands + feet (Yamaha R9-inspired: faceted fairings, central
M-duct with the camera in it, slanted LED eye slits, winglets, belly pan, tail-wing carry handle).

Every panel is a separate printed part (blue / black / white PETG) so it can be printed in its colour,
and panels only touch each other (zero-volume contact).  World mm, zero pose, left side mirrored for R.
PROPOSED DESIGN -- not built or tested.
"""
from __future__ import annotations

import math

import humanoid_brackets as hb
import humanoid_layout as L
import ollie_layout as OL
import ollie_style as S
from humanoid_geometry import W, _ycyl

FAIRING_KEYS = ("fair_",)
BIG = 2000.0
WALL = 1.6                     # PETG fairing wall (4 perimeters of a 0.4 mm nozzle)


def M(views, s):
    """Mirror a 3-view dict for side s (+1 left, -1 right)."""
    out = {}
    for ax, pts in views.items():
        out[ax] = [(s * a, b) for a, b in pts] if ax == "x" else ([(a, s * b) for a, b in pts] if ax == "z" else list(pts))
    return out


def hy(y0, y1, s=1):
    a, b = sorted((s * y0, s * y1))
    return S.box(-BIG, BIG, a, b, -BIG, BIG)


def hx(x0, x1):
    return S.box(x0, x1, -BIG, BIG, -BIG, BIG)


def hz(z0, z1):
    return S.box(-BIG, BIG, -BIG, BIG, z0, z1)


def plan_prism(plan, z0, z1, s):
    return S.prism([(x, s * y) for x, y in plan], "z", z0, z1)


def slot_y(x, zc, y0, y1, s, w=10.0, h=34.0):
    """Stadium slot through a y-normal plate (lightening / vent)."""
    import cadquery as cq
    a, b = sorted((s * y0, s * y1))
    return cq.Workplane("XZ").center(x, zc).slot2D(h, w, 90).extrude(-(b - a)).translate((0, a, 0)).val()


# --------------------------------------------------------------------------- feet
def foot_deck(side, z0, t=3.0):
    """Printed deck on the Al sole plate (inset 3 mm) that ties the ankle block to the heel pod."""
    s = 1 if side == "L" else -1
    w = S.prism([(x, s * y) for x, y in OL.FOOT_PLAN], "z", z0, z0 + t, -3.0)
    return hb.fuse(w, W(-39.0, -36.0, 10, 48, z0, z0 + t, s))


def heel_pod(side, z0):
    s = 1 if side == "L" else -1
    wx, wz = OL.WHEEL_X, OL.WHEEL_Z
    body = hb.fuse(W(-72, -38, 10, 48, z0, 34, s), W(-70, -54, 40, 48, 33.5, 52.5, s),
                   W(-70, -54, 40, 65, 48, 52, s), W(-72, -52, 62, 65, 14, 52.5, s))
    pocket = W(OL.N20_X[0] - 0.2, OL.N20_X[1] + 0.2, 9, 46.2, OL.N20_Z[0] - 0.2, OL.N20_Z[1] + 0.2, s)
    return hb.cut(body, pocket, _ycyl(2.6, wx, 45, 49, wz, s), *[_ycyl(0.9, wx + dx, 45, 49, wz, s) for dx in (-4.5, 4.5)],
                  _ycyl(3.0, wx, 61.5, 66, wz, s))


def heel_parts(side):
    s = 1 if side == "L" else -1
    wx, wz = OL.WHEEL_X, OL.WHEEL_Z
    hub = hb.cut(_ycyl(OL.HUB_R, wx, 49, 61, wz, s), _ycyl(1.5, wx, 48, 55.5, wz, s), _ycyl(1.5, wx, 57, 62, wz, s),
                 *[_ycyl(3.2, wx + 9.5 * math.cos(a), 48, 62, wz + 9.5 * math.sin(a), s)
                   for a in [k * math.pi / 3 for k in range(6)]])                     # 6-spoke rim (R9 gold)
    tire = hb.cut(_ycyl(OL.WHEEL_R, wx, 49.5, 60.5, wz, s), _ycyl(OL.HUB_R, wx, 49, 61, wz, s))
    n20 = hb.fuse(W(OL.N20_X[0], OL.N20_X[1], 12, 46, OL.N20_Z[0], OL.N20_Z[1], s), _ycyl(1.45, wx, 45.9, 55, wz, s))
    return {f"wheel_hub_{side}": hub, f"tire_tpu_{side}": tire, f"axle_pin_{side}": _ycyl(1.5, wx, 57, 64.5, wz, s),
            f"bearing_mr63zz_{side}": hb.cut(_ycyl(3.0, wx, 62, 64.5, wz, s), _ycyl(1.5, wx, 61.9, 64.6, wz, s)),
            f"n20_motor_{side}": n20}


TOE = {"z": [(12, 10), (82, 10), (87, 21), (87, 47), (70, 80), (12, 80)],
       "y": [(12, 9.2), (89, 9.2), (89, 13), (62, 25), (12, 31)],
       "x": [(10, 9.2), (81, 9.2), (78, 22), (62, 31), (18, 31), (10, 22)]}


def toe_cap(side):
    s = 1 if side == "L" else -1
    sh, _, _ = S.shell(M(TOE, s), 2.0, ("-z",))
    return sh


# --------------------------------------------------------------------------- hands
def hand(side):
    """Two fixed fingers + palm (forearm link), opposable thumb on the SC09 horn (finger link)."""
    s = 1 if side == "L" else -1
    px, py, pz = L.GRIP_P
    fa, fi = f"forearm_{side}", f"finger_{side}"
    palm = W(px - 50, px + 8, 96.0, 118.0, pz - 10, pz - 6, s)
    fingers = []
    for y0, y1 in ((99.0, 109.5), (112.5, 124.6)):
        v = {"y": [(px - 50, pz - 6), (px - 42, pz - 6), (px - 42, pz - 46), (px - 45, pz - 58), (px - 50, pz - 58)],
             "x": [(s * y0, pz - 58), (s * y1, pz - 58), (s * y1, pz - 6), (s * y0, pz - 6)]}
        f = S.carve(v)
        f = hb.cut(f, *[W(px - 51, px - 48.5, y0 - 1, y1 + 1, z - 0.8, z + 0.8, s) for z in (pz - 22, pz - 38)])  # knuckle lines
        fingers.append(f)
    out = {f"palm_{side}": (fa, hb.cut(hb.fuse(palm, *fingers), W(px - 10.2, px + 8.2, 94, 118.2, pz - 8.2, pz + 21, s)))}
    for k, (y0, y1) in enumerate(((100.0, 108.5), (113.5, 123.6))):
        out[f"jaw_pad_tpu_{side}{k}"] = (fa, W(px - 42, px - 40, y0, y1, pz - 44, pz - 14, s))
    out[f"paw_pad_tpu_{side}"] = (fa, W(*OL.paw_box()[:2], *OL.paw_box()[2:4], *OL.paw_box()[4:], s))
    hub = _ycyl(7.0, px, py + 0.6, py + 6.6, pz, s)
    thumb = S.carve({"y": [(px - 4, pz), (px + 5, pz), (px + 5, pz - 40), (px, pz - 58), (px - 4, pz - 58)],
                     "x": [(s * (py + 0.6), pz - 58), (s * (py + 6.6), pz - 58), (s * (py + 6.6), pz), (s * (py + 0.6), pz)]})
    thumb = hb.cut(hb.fuse(hub, thumb), _ycyl(4.2, px, py, py + 3.6, pz, s), _ycyl(1.2, px, py, py + 7, pz, s))
    out[f"finger_{side}"] = (fi, thumb)
    out[f"finger_pad_tpu_{side}"] = (fi, W(px - 6, px - 4, py + 0.6, py + 6.6, pz - 54, pz - 26, s))
    guard = {"y": [(26, 462), (34, 466), (37, 486), (33, 506), (26, 506)],
             "x": [(s * 90, 462), (s * 118, 462), (s * 118, 506), (s * 92, 506)],
             "z": [(26, s * 90), (36, s * 96), (37, s * 112), (33, s * 118), (26, s * 118)]}
    out[f"fair_hand_{side}"] = (fa, S.carve(guard))
    return out


# --------------------------------------------------------------------------- torso
Z0 = 533.0                                             # torso shell bottom = pelvis plate top
TORSO = {"x": [(-75.5, Z0), (75.5, Z0), (75.5, 712), (68, 732), (34, 741.5), (-34, 741.5), (-68, 732), (-75.5, 712)],
         "y": [(-56, Z0), (56, Z0), (66, 580), (80, 650), (78, 690), (60, 724), (30, 741.5), (-40, 741.5),
               (-62, 722), (-68, 650), (-62, 580)],
         "z": [(-62, -58), (-48, -75.5), (50, -75.5), (80, -36), (86, 0), (80, 36), (50, 75.5), (-48, 75.5),
               (-62, 58), (-70, 0)]}
CHEVRON = [(-44, 693), (-40, 699), (0, 675), (40, 699), (44, 693), (0, 667)]
STRIPE = [(10, 580), (10, 592), (62, 634), (62, 622)]


def torso_fairings():
    sh, outer, inner = S.shell(TORSO, WALL, ("-z",))
    chev = S.prism(CHEVRON, "x", 30, 120)
    P = {"light_chevron_acrylic": S.prism(CHEVRON, "x", 30, 120, -0.3).intersect(sh).clean(),
         "led_strip_ws2812": S.prism(CHEVRON, "x", 30, 120, -1.5).intersect(S.cut(S.carve(TORSO, -3.0), S.carve(TORSO, -6.0))).clean()}
    cuts = [chev, S.cut(hb.cyl_z(26.0, 700, 760), hz(-BIG, 690)),
            W(-80, -55, -6.5, 6.5, 603, 617)]
    for s in (1, -1):
        cuts.append(W(-14.5, 14.5, 60, 80, 659, 712, s))
        for k in range(3):
            g = S.prism([(-44 + 9 * k, 590), (-39 + 9 * k, 590), (-33 + 9 * k, 628), (-38 + 9 * k, 628)], "y", -BIG, BIG)
            cuts.append(g.intersect(hy(60, 90, s)))
    sh = S.cut(sh, *cuts)
    upper = S.cut(sh, hz(-BIG, 575))
    P["fair_waist"] = sh.intersect(hz(-BIG, 575)).clean()
    P["fair_back"] = upper.intersect(hx(-BIG, -20)).clean()
    front = S.cut(upper, hx(-BIG, -20))
    P["fair_keel"] = front.intersect(hy(-16, 16)).clean()
    stripe = S.prism(STRIPE, "y", -BIG, BIG)
    for side, s in (("L", 1), ("R", -1)):
        chest = front.intersect(hy(16, 200, s)).clean()
        band = stripe.intersect(hy(48, 200, s))
        P[f"fair_chest_{side}"] = S.cut(chest, band)
        P[f"fair_stripe_{side}"] = chest.intersect(band).clean()
    wing = S.fuse(S.prism([(-104, 700), (-84, 700), (-80, 712), (-98, 715)], "y", -56, 56),
                  *[W(-92, -50, 38, 46, 688, 701, s) for s in (1, -1)])
    P["fair_tailwing"] = S.cut(wing, outer)
    P["fair_bellypan"] = S.shell({"x": [(-16, 527), (16, 527), (10, 488), (-10, 488)],
                                  "y": [(4, 527), (58, 527), (50, 502), (30, 488), (12, 492)],
                                  "z": [(4, -16), (58, -16), (58, 16), (4, 16)]}, WALL, ("+z",))[0]
    P["power_switch"] = hb.fuse(W(-67.5, -65.8, -7.5, 7.5, 599.5, 620.5), W(-65.8, -47, -6.4, 6.4, 603.6, 616.4))
    return {n: ("base", v) for n, v in P.items()}


# --------------------------------------------------------------------------- head
def head_views():
    tz = L.NECK_TILT_P[2]
    return {"x": [(-62, tz - 12), (62, tz - 12), (66, tz + 10), (58, tz + 32), (32, tz + 42), (-32, tz + 42),
                  (-58, tz + 32), (-66, tz + 10)],
            "y": [(-34, tz - 12), (40, tz - 12), (66, tz), (70, tz + 12), (52, tz + 32), (14, tz + 42), (-32, tz + 38),
                  (-44, tz + 16), (-44, tz)],
            "z": [(-44, -50), (-24, -62), (46, -62), (66, -30), (72, 0), (66, 30), (46, 62), (-24, 62), (-44, 50)]}


def head_parts():
    tx, ty, tz = L.NECK_TILT_P
    V = head_views()
    sh, outer, inner = S.shell(V, WALL, ("-z",))
    duct = [(-22, tz - 8), (22, tz - 8), (26, tz + 8), (14, tz + 14), (0, tz + 6), (-14, tz + 14), (-26, tz + 8)]
    eye = [(18, tz + 16), (50, tz + 25), (52, tz + 21), (20, tz + 10)]
    P = {}
    cuts = [S.prism(duct, "x", 30, 120)]
    for side, s in (("L", 1), ("R", -1)):
        e = [(s * y, z) for y, z in eye]
        cuts.append(S.prism(e, "x", 30, 120))
        P[f"eye_lens_acrylic_{side}"] = S.prism(e, "x", 30, 120, -0.3).intersect(sh).clean()
        P[f"oled_eye_{side}"] = S.cut(S.prism(e, "x", 30, 120, 1.5).intersect(S.cut(S.carve(V, -3.4), S.carve(V, -7.0))),
                                     S.prism(duct, "x", 30, 120, 1.5))
        wv = {"x": [(s * 58, tz - 4), (s * 78, tz - 11), (s * 78, tz - 7), (s * 60, tz + 2)],
              "z": [(24, s * 50), (58, s * 50), (58, s * 64), (42, s * 80), (24, s * 80)]}
        P[f"fair_head_wing_{side}"] = S.cut(S.carve(wv), outer)
    sh = S.cut(sh, *cuts)
    hubp = hb.fuse(_ycyl(8.0, tx, ty + 1.0, ty + 6.6, tz), W(tx - 8, tx + 8, ty + 1.0, ty + 6.6, tz, tz + 38.6))
    hubp = hb.cut(hubp, _ycyl(3.2, tx, ty, ty + 4.0, tz))
    P["fair_head_rear"] = sh.intersect(hx(-BIG, -24)).clean()
    P["fair_head"] = S.fuse(S.cut(sh, hx(-BIG, -24)), hubp)
    xf = 52.0
    cup = S.prism(duct, "x", xf, 120).intersect(S.carve(V, -WALL))
    cup = S.cut(cup, S.prism(duct, "x", xf + 2, 120, -2.0), hb.cyl_z(0.1, 0, 0.1))
    cup = S.cut(cup, S.prism([(-4, tz), (4, tz), (4, tz + 8), (-4, tz + 8)], "x", xf - 1, xf + 3))
    P["fair_head_duct"] = cup
    P["camera_ov5647"] = W(xf - 8, xf, -12.5, 12.5, tz - 9, tz + 15)
    P["fair_head_crest"] = S.cut(S.prism([(-30, tz + 37), (20, tz + 41), (48, tz + 32), (52, tz + 35), (22, tz + 47),
                                          (-28, tz + 44)], "y", -5, 5), outer)
    return P


# --------------------------------------------------------------------------- limbs
SHOULDER = {"x": [(79.1, 618), (79.1, 734), (96, 748), (124, 742), (142, 716), (146, 650), (134, 618)],
            "y": [(-36, 618), (36, 618), (42, 660), (36, 724), (16, 748), (-16, 748), (-36, 724), (-42, 660)],
            "z": [(-40, 79.1), (40, 79.1), (44, 104), (34, 146), (-34, 146), (-44, 104)]}
WINGLET = {"y": [(34, 634), (64, 624), (68, 630), (40, 650)], "x": [(100, 600), (138, 600), (138, 700), (100, 700)]}
FOREARM = {"x": [(78, 500), (127, 500), (129, 524), (124, 548), (81, 548), (78, 524)],
           "y": [(-18, 500), (22, 500), (26, 518), (20, 548), (-16, 548), (-20, 522)],
           "z": [(-20, 78), (22, 78), (26, 100), (22, 128), (-18, 128), (-22, 100)]}
THIGH = {"x": [(20, 293), (73, 293), (73, 322), (68, 337), (24, 337), (19, 322)],
         "y": [(-22, 293), (24, 293), (30, 305), (30, 322), (22, 337), (-26, 337), (-26, 300)],
         "z": [(-26, 24), (24, 19), (30, 30), (30, 62), (24, 73), (-26, 73)]}
SHIN = {"x": [(20, 137), (72, 137), (73, 180), (70, 205), (22, 205), (19, 180)],
        "y": [(-20, 137), (18, 137), (23, 160), (23, 205), (-14, 205), (-20, 190)],
        "z": [(-20, 24), (18, 19), (23, 28), (23, 64), (18, 73), (-20, 73)]}


def octagon(cx, cz, r):
    return [(cx + r * math.cos(a), cz + r * math.sin(a)) for a in [math.pi / 8 + k * math.pi / 4 for k in range(8)]]


def limb_fairings():
    out = {}
    for side, s in (("L", 1), ("R", -1)):
        ua, fa, th, sn, ft = (f"{k}_{side}" for k in ("upper_arm", "forearm", "thigh", "shin", "foot"))
        sh, outer, _ = S.shell(M(SHOULDER, s), WALL, ("-y" if s > 0 else "+y", "-z"))
        sh = S.cut(sh, W(-16, 16, 75, 79.4, 590, 720, s))
        out[f"fair_shoulder_{side}"] = (ua, sh)
        out[f"fair_winglet_{side}"] = (ua, S.cut(S.carve(M(WINGLET, s)), outer))
        out[f"fair_forearm_{side}"] = (fa, S.shell(M(FOREARM, s), WALL, ("-z", "+z"))[0])
        sh, outer, _ = S.shell(M(THIGH, s), WALL, ("-z", "+z"))
        band = S.prism([(-26, 298), (-26, 309), (30, 329), (30, 318)], "y", -BIG, BIG).intersect(hy(60, 200, s))
        out[f"fair_thigh_{side}"] = (th, S.cut(sh, band))
        out[f"fair_thigh_stripe_{side}"] = (th, sh.intersect(band).clean())
        zh = L.Z_HIP_PITCH
        cap = S.prism(octagon(0, zh, 44), "y", 67.2 * s, 70.2 * s)
        cap = cap.intersect(S.prism([(s * 60, zh - 60), (s * 70.2, zh - 60), (s * 70.2, zh + 60), (s * 60, zh + 60)], "x", -BIG, BIG))
        out[f"fair_hipcap_{side}"] = (th, S.cut(cap, S.prism(octagon(0, zh, 9), "y", -BIG, BIG)))
        sh, _, _ = S.shell(M(SHIN, s), WALL, ("-z", "+z"))
        k = OL.KNEE_PAD
        zk = L.Z_KNEE
        pad = W(k[0], k[1], k[2], k[3], zk + k[4], zk + k[5], s)
        sh = S.cut(sh, pad)
        out[f"fair_shin_cuff_{side}"] = (sn, sh.intersect(hz(-BIG, 150)).clean())
        out[f"fair_shin_{side}"] = (sn, S.cut(sh, hz(-BIG, 150)))
        out[f"knee_pad_tpu_{side}"] = (sn, S.cut(pad, S.prism([(k[1] - 4, zk + k[5]), (k[1] + 1, zk + k[5]), (k[1] + 1, zk + k[5] - 6)],
                                                              "y", -BIG, BIG)))
        out[f"fair_toe_{side}"] = (ft, toe_cap(side))
    return out
