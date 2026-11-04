"""
ollie_geometry.py -- every part of OLLIE (walk / skate / crawl humanoid), zero pose, world mm.

Reuses the verified $700 humanoid skeleton (ST3215 joints, solved U-brackets and cradles) and adds:
rounded torso / head / limb shells, heel-wheel pods (N20 encoder gearmotor + MR63ZZ-supported
wheel per foot), TPU knee and paw pads for crawling, a smoked visor face (1.3" OLED + camera)
and a WS2812 mode light bar.  PROPOSED DESIGN -- not built or tested.
"""
from __future__ import annotations

import numpy as np

import humanoid_brackets as hb
import humanoid_geometry as G
import humanoid_layout as L
import ollie_layout as OL
from humanoid_geometry import W, Part, _ycyl, inJ, servo

OL.apply()
G.TUBE_FILLET = 6.0
G.FOOT_FILLET = 12.0
G.STRAP_X = (-22, 55)
R_TORSO = 20.0

# wheel parts ride on the foot for statics; Fusion gets them as their own spinning component
FUSION_LINK = {}


def _cq():
    import cadquery as cq
    return cq


def _rbox(x0, x1, y0, y1, z0, z1, r):
    return G._rz(hb.box(x0, x1, y0, y1, z0, z1), r)


def _rbox_all(x0, x1, y0, y1, z0, z1, r):
    return _cq().Workplane(obj=hb.box(x0, x1, y0, y1, z0, z1)).edges().fillet(r).val()


def _inter(a, b):
    return a.intersect(b).clean()


# --------------------------------------------------------------------------- legs + heel wheels
def heel(side) -> dict:
    s = 1 if side == "L" else -1
    wx, wz = OL.WHEEL_X, OL.WHEEL_Z
    body = hb.fuse(W(-72, -38, 10, 48, 10, 34, s), W(-70, -54, 40, 48, 33.5, 52.5, s),
                   W(-70, -54, 40, 65, 48, 52, s), W(-72, -52, 62, 65, 14, 52.5, s))
    pocket = W(OL.N20_X[0] - 0.2, OL.N20_X[1] + 0.2, 9, 46.2, OL.N20_Z[0] - 0.2, OL.N20_Z[1] + 0.2, s)
    body = hb.cut(body, pocket, _ycyl(2.6, wx, 45, 49, wz, s),
                  *[_ycyl(0.9, wx + dx, 45, 49, wz, s) for dx in (-4.5, 4.5)],
                  _ycyl(3.0, wx, 61.5, 66, wz, s))
    hub = hb.cut(_ycyl(OL.HUB_R, wx, 49, 61, wz, s), _ycyl(1.5, wx, 48, 55.5, wz, s),
                 _ycyl(1.5, wx, 57, 62, wz, s))
    tire = hb.cut(_ycyl(OL.WHEEL_R, wx, 49.5, 60.5, wz, s), _ycyl(OL.HUB_R, wx, 49, 61, wz, s))
    n20 = hb.fuse(W(OL.N20_X[0], OL.N20_X[1], 12, 46, OL.N20_Z[0], OL.N20_Z[1], s),
                  _ycyl(1.45, wx, 45.9, 55, wz, s))
    P = {f"heel_pod_{side}": body,
         f"wheel_hub_{side}": hub,
         f"tire_tpu_{side}": tire,
         f"axle_pin_{side}": _ycyl(1.5, wx, 57, 64.5, wz, s),
         f"bearing_mr63zz_{side}": hb.cut(_ycyl(3.0, wx, 62, 64.5, wz, s), _ycyl(1.5, wx, 61.9, 64.6, wz, s)),
         f"n20_motor_{side}": n20}
    for n in (f"wheel_hub_{side}", f"tire_tpu_{side}", f"axle_pin_{side}"):
        FUSION_LINK[n] = f"wheel_{side}"
    return P


def legs() -> dict:
    out = {}
    for side in "LR":
        s = 1 if side == "L" else -1
        P = G.leg(side)
        h = heel(side)
        link, foot = P[f"foot_{side}"]
        P[f"foot_{side}"] = (link, hb.fuse(foot, h.pop(f"heel_pod_{side}")))
        for n, shp in h.items():
            P[n] = (f"foot_{side}", shp)
        P[f"knee_pad_tpu_{side}"] = (f"shin_{side}", W(12, 20, 32, 57, 140, 195, s))
        out.update(P)
    return out


def arms() -> dict:
    out = {}
    for side in "LR":
        s = 1 if side == "L" else -1
        P = G.arm(side)
        px, _, pz = L.GRIP_P
        P[f"paw_pad_tpu_{side}"] = (f"forearm_{side}", W(px - 52, px - 42, 98, 126, pz - 62, pz - 58, s))
        out.update(P)
    return out


# --------------------------------------------------------------------------- torso
def torso() -> dict:
    P = {}
    hx, hy, w = L.TORSO_HX, L.TORSO_HY, L.WALL
    z0, z1 = L.Z_PELVIS + L.PELVIS_T, L.Z_TOP
    pelvis = _rbox(-hx, hx, -hy, hy, L.Z_PELVIS, z0, R_TORSO)
    risers, rails = [], []
    for side, s in (("L", 1), ("R", -1)):
        jn = f"hip_yaw_{side}"
        xc = L.bracket_params(jn)[2]
        z_cr_top = L.Z_HIP_YAW + hb.CR_Z[1]
        risers.append(hb.fuse(G.cradle(jn), W(L.X_HIP_YR - hb.CR_END, L.X_HIP_YR - xc, L.LEG_Y - hb.CR_Y,
                                              L.LEG_Y + hb.CR_Y, z_cr_top - 0.5, L.Z_PELVIS + 0.5, s)))
        rails.append(W(21.5, 24.5, -70, 70, z0 - 0.3, z0 + 10, s))
    P["pelvis_plate"] = ("base", hb.fuse(pelvis, *risers, *rails))

    outer = _rbox(-hx, hx, -hy, hy, z0, z1, R_TORSO)
    shell = hb.cut(outer, _rbox(-hx + w, hx - w, -hy + w, hy - w, z0 - 1, z1 + 1, R_TORSO - w))
    walls = _inter(shell, hb.box(-hx + w, hx + 1, -hy - 1, hy + 1, z0 - 1, z1 + 1))
    back = _inter(shell, hb.box(-hx - 1, -hx + w, -hy - 1, hy + 1, z0 - 1, z1 + 1))
    shelf = _inter(W(-hx + w, hx - w + 0.3, -hy + w - 0.3, hy - w + 0.3, 540, 543), outer)
    shelf = hb.cut(shelf, W(-40, -30, -20, 20, 530, 550), W(-12, 12, -72, -62, 530, 550),
                   W(-12, 12, 62, 72, 530, 550))
    bosses = [hb.cyl_z(2.6, 543, 554, x, y) for x in (-24.5, 24.5) for y in (-29, 29)]
    bosses += [hb.cyl_z(2.6, 543, 549, x, y) for x in (-29, 29) for y in (41.5, 64.5)]
    bosses += [hb.cyl_z(2.6, 543, 549, x, -47) for x in (-12.5, 12.5)]
    body = hb.fuse(walls, shelf, *bosses)
    cuts = [W(-12.9, 12.9, hy - w - 1, hy + 1, L.Z_SHOULDER - 35.6, L.Z_SHOULDER + 10.6, s) for s in (1, -1)]
    cuts.append(W(hx - w - 1, hx + 1, -27, 27, 625, 635))                       # light-bar window
    P["torso_shell"] = ("base", hb.cut(body, *cuts))

    handle = hb.fuse(W(-75, -44.5, -42, -34, 640, 652), W(-75, -44.5, 34, 42, 640, 652),
                     W(-75, -67, -42, 42, 640, 652))
    back = hb.cut(back, W(-hx - 1, -hx + w + 1, -6.5, 6.5, 603.5, 616.5))
    P["torso_back_cover"] = ("base", hb.fuse(back, handle))
    P["light_diffuser"] = ("base", W(hx - w, hx - 0.6, -27, 27, 625, 635))

    top = _rbox(-hx, hx, -hy, hy, z1, z1 + L.TOP_T, R_TORSO)
    hangers = []
    for side, s in (("L", 1), ("R", -1)):
        y_rear = L.SHOULDER_Y + hb.CASE_Z[0]
        h = W(-hb.CR_Y, hb.CR_Y, y_rear - 2.5, y_rear, L.Z_SHOULDER - 38.0, z1 + 0.5, s)
        h = hb.cut(h, _ycyl(10.5, 0, y_rear - 3, y_rear + 1, L.Z_SHOULDER, s),
                   *[_ycyl(1.1, x, y_rear - 3, y_rear + 1, L.Z_SHOULDER - 32.8, s) for x in (-10.2, 10.2)])
        hangers.append(h)
    nx, ny, nz = L.NECK_PAN_P
    nholder = hb.cut(W(nx - 7.8, nx + 19.4, -8, 8, z1 + L.TOP_T - 0.5, nz - 5),
                     inJ("neck_pan", hb.box(-6.0, 17.6, -6.2, 6.2, -22.2, 1.0)))
    top = hb.cut(hb.fuse(top, *hangers, nholder), W(nx + 20, nx + 30, -6, 6, z1 - 1, z1 + 8))
    P["torso_top_plate"] = ("base", top)
    P["servo_neck_pan"] = ("base", servo("neck_pan"))

    # purchased electronics (vendor dimensions, envelopes)
    P["battery_3s_5000"] = ("base", W(-21, 21, -68, 68, z0, z0 + 28))
    P["ubec_6v_5a"] = ("base", W(25.0, 42.0, -20, 20, z0, z0 + 9))
    P["driver_hat_a_board"] = ("base", W(-28.5, 28.5, -32.5, 32.5, 554, 555.6))
    P["driver_hat_a_components"] = ("base", W(-26, 26, -30, 30, 555.6, 569))
    P["pi_zero_2w_board"] = ("base", W(-32.5, 32.5, 38, 68, 549, 550.4))
    P["pi_zero_2w_components"] = ("base", W(-31, 31, 39, 67, 550.4, 555))
    P["imu_mpu6050"] = ("base", W(-10.5, 10.5, -55, -39, 549, 550.6))
    P["drv8833_wheel_driver"] = ("base", W(-35, -22.3, -60, -40, 543, 546))
    P["led_stick_ws2812_8"] = ("base", W(hx - w - 3.2, hx - w, -25.5, 25.5, 625, 635))
    P["power_switch"] = ("base", hb.fuse(W(-hx - 1.5, -hx, -7.5, 7.5, 599.5, 620.5),
                                         W(-hx, -hx + 18, -6.4, 6.4, 603.6, 616.4)))
    return P


# --------------------------------------------------------------------------- head
def head() -> dict:
    P = {}
    nx, ny, nz = L.NECK_PAN_P
    tx, ty, tz = L.JOINTS["neck_tilt"]["p"]
    zd0 = nz + 0.6
    disc = hb.cut(hb.cyl_z(22.0, zd0, zd0 + 4.0, nx, ny), hb.cyl_z(3.2, zd0 - 1, zd0 + 3.1, nx, ny))
    holder = hb.cut(W(tx - 8, tx + 8, -13, ty, zd0 + 4.0, tz + 7.8),
                    inJ("neck_tilt", hb.box(-6.0, 17.6, -6.2, 6.2, -22.2, 1.0)))
    P["neck_turntable"] = ("neck", hb.fuse(disc, holder))
    P["servo_neck_tilt"] = ("neck", servo("neck_tilt"))

    hx0, hx1, hy, hz0, hz1, w = -36.0, 50.0, 52.0, tz - 20, tz + 60, 2.4
    outer = _rbox_all(hx0, hx1, -hy, hy, hz0, hz1, 14.0)
    inner = _rbox_all(hx0 + w, hx1 - w, -hy + w, hy - w, hz0 - 20, hz1 - w, 11.6)
    shell = hb.cut(outer, inner)
    win = G._rz(hb.box(-1, 1, -34, 34, tz - 8, tz + 44), 0)
    window = _cq().Workplane(obj=hb.box(hx1 - w - 1, hx1 + 1, -34, 34, tz - 8, tz + 44)).edges("|X").fillet(8).val()
    shell = hb.cut(shell, window)
    hubp = hb.fuse(_ycyl(8.0, tx, ty + 1.0, ty + 6.6, tz), W(tx - 8, tx + 8, ty + 1.0, ty + 6.6, tz, hz1 - w + 0.5))
    hubp = hb.cut(hubp, _ycyl(3.2, tx, ty, ty + 4.0, tz))
    pods = [_ycyl(15.0, tx, s * (hy - 1), s * (hy + 5), tz, 1) for s in (1, -1)]
    P["head_shell"] = ("head", hb.fuse(shell, hubp, *pods))
    for side, s in (("L", 1), ("R", -1)):
        P[f"ear_cap_{side}"] = ("head", _ycyl(8.0, tx, hy + 5, hy + 7, tz, s))
    flange = _cq().Workplane(obj=hb.box(hx1 - w - 1, hx1 - w, -36, 36, tz - 10, tz + 46)).edges("|X").fillet(9).val()
    plug = _inter(window, hb.box(hx1 - w - 0.3, hx1, -40, 40, tz - 20, tz + 60))
    visor = hb.fuse(flange, plug)
    P["visor_smoked_acrylic"] = ("head", visor)
    P["oled_face_1in3"] = ("head", W(hx1 - w - 1 - 3.7, hx1 - w - 1, -17.7, 17.7, tz + 10, tz + 43.5))
    P["camera_module_3"] = ("head", W(hx1 - w - 1 - 11.5, hx1 - w - 1, -12.5, 12.5, tz - 15, tz + 9))
    del win
    return P


# --------------------------------------------------------------------------- assembly
VENDOR_KEYS = ("servo_", "ubec_", "_components", "power_switch", "n20_", "bearing_", "axle_pin",
               "drv8833", "led_stick")
PCB_KEYS = ("_board", "imu_", "camera_", "oled_")


def material(name):
    if "tpu" in name:
        return "tpu"
    if name.startswith("visor"):
        return "acrylic"
    if name.startswith("battery"):
        return "battery"
    if any(k in name for k in PCB_KEYS):
        return "pcb"
    if any(k in name for k in VENDOR_KEYS):
        return "vendor"
    return "pla"


def parts() -> dict:
    raw = {}
    raw.update(legs())
    raw.update(arms())
    raw.update(torso())
    raw.update(head())
    out, errs = {}, []
    for n, (link, shape) in raw.items():
        m = material(n)
        try:
            out[n] = Part(link, G._one(shape, n), m, "printed" if m in ("pla", "tpu") else "purchased")
        except ValueError as e:
            errs.append(str(e))
    if errs:
        raise ValueError("; ".join(errs))
    return out


def fusion_link(name, part):
    return FUSION_LINK.get(name, part.link)


MASS_G = {"n20_": OL.N20_MASS_G, "bearing_": 1.0, "axle_pin": 0.5, "drv8833": 2.0, "led_stick": 3.0,
          "oled_face": 6.0, "ubec_6v_5a": 18.0, "camera_": 4.0}
DENS = {"pla": 1.24e-3 * 0.6, "tpu": 1.21e-3 * 0.8, "acrylic": 1.18e-3}


def mass_g(name, part) -> float:
    if part.material in DENS:
        return part.shape.Volume() * DENS[part.material]
    for k, g in MASS_G.items():
        if k in name:
            return g
    return G.mass_g(name, part)


def link_inertia(P: dict):
    mass, mom = {}, {}
    for n, p in P.items():
        m = mass_g(n, p)
        c = p.shape.Center()
        mass[p.link] = mass.get(p.link, 0.0) + m
        mom[p.link] = mom.get(p.link, np.zeros(3)) + m * np.array([c.x, c.y, c.z])
    mass["base"] += 160.0                       # wiring, connectors, fasteners (estimate)
    mom["base"] += 160.0 * np.array([0.0, 0.0, 560.0])
    return mass, {ln: mom[ln] / mass[ln] for ln in mass}


def posed(P: dict, q: dict, Tb=None) -> dict:
    import ollie_physics as OP
    Tl = OP.transforms(q, np.eye(4) if Tb is None else Tb)
    return {n: G.place(p.shape, Tl[p.link]) for n, p in P.items()}
