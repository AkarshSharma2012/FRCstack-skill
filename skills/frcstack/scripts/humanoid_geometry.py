"""
humanoid_geometry.py -- every printed and purchased part of the $700 humanoid, in the zero pose.

parts() -> {name: Part(link, shape, material, kind)}.  Shapes are in world coordinates of the zero
pose (standing straight); pose them with humanoid_layout.link_transforms(q)[link].
Purchased parts are size/position envelopes from vendor data (the ST3215 vendor STEP is added
separately for export via vendor_st3215()).  PROPOSED DESIGN -- not built or tested.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import humanoid_brackets as hb
import humanoid_layout as L

VENDOR = Path(__file__).resolve().parents[3] / ".frcstack" / "vendor" / "humanoid" / "st3215" / "ST3215.step"
# vendor STEP coordinates -> J frame:  Jx = vx + 25.5,  Jy = -vz,  Jz = vy + 9.025
VENDOR_TO_J = np.array([[1, 0, 0, 25.5], [0, 0, -1, 0], [0, 1, 0, 9.025], [0, 0, 0, 1]], float)


@dataclass
class Part:
    link: str
    shape: object
    material: str       # pla | tpu | vendor | pcb | battery
    kind: str           # printed | purchased


# style knobs (0 / defaults = original $700 humanoid; OLLIE turns the rounding on)
TUBE_FILLET = 0.0
FOOT_FILLET = 0.0
STRAP_X = (-40, 55)


def _rz(s, r):
    """Round the edges parallel to Z (r <= 0: unchanged)."""
    if r <= 0:
        return s
    return _cq().Workplane(obj=s).edges("|Z").fillet(r).val()


def _tube(outer, inner):
    return hb.cut(_rz(outer, TUBE_FILLET), _rz(inner, max(TUBE_FILLET - 3.0, 0.0)))


def _cq():
    import cadquery as cq
    return cq


def place(shape, M):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf
    t = gp_Trsf()
    t.SetValues(*[float(v) for v in np.asarray(M)[:3, :].reshape(-1)])
    return _cq().Shape.cast(BRepBuilderAPI_Transform(shape.wrapped, t, True).Shape())


def inJ(jn, shape):
    return place(shape, L.servo_frame(jn))


def W(x0, x1, y0, y1, z0, z1, s=1):
    a, b = sorted((s * y0, s * y1))
    return hb.box(x0, x1, a, b, z0, z1)


def _one(shape, name):
    shape = shape.clean()
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError(f"{name}: valid={shape.isValid()} solids={len(shape.Solids())}")
    return shape


def _ycyl(r, x, y0, y1, z, s=1):
    cq = _cq()
    a, b = sorted((s * y0, s * y1))
    return cq.Solid.makeCylinder(r, b - a, cq.Vector(x, a, z), cq.Vector(0, 1, 0))


def _xcyl(r, x0, x1, y, z):
    cq = _cq()
    return cq.Solid.makeCylinder(r, x1 - x0, cq.Vector(x0, y, z), cq.Vector(1, 0, 0))


# --------------------------------------------------------------------------- joint hardware
def bracket(jn):
    phi, R, _ = L.bracket_params(jn)
    return inJ(jn, hb.bracket_main(phi, R)), inJ(jn, hb.bracket_idler(phi, R))


def cradle(jn):
    return inJ(jn, hb.cradle(L.bracket_params(jn)[2]))


def servo(jn):
    return inJ(jn, hb.st_envelope() if L.JOINTS[jn]["kind"] == "st" else hb.sc09_envelope())


def vendor_st3215():
    """Vendor ST3215 model (8 solids) in the J frame, for export."""
    cq = _cq()
    comp = cq.importers.importStep(str(VENDOR)).val()
    return place(comp, VENDOR_TO_J)


# --------------------------------------------------------------------------- legs
def leg(side) -> dict:
    s = 1 if side == "L" else -1
    j = {k: f"{k}_{side}" for k in L.LEG_JOINTS}
    P = {}
    xc = {k: L.bracket_params(j[k])[2] for k in L.LEG_JOINTS}

    yaw_m, yaw_i = bracket(j["hip_yaw"])
    roll_m, roll_i = bracket(j["hip_roll"])
    col = W(40.5, 44.5, 33, 57, 417, 484.6, s)
    lap = W(39.5, 40.6, 33, 57, 444.0, 484.6, s)
    gus = W(30, 40.6, 33, 57, 420.5, 432, s)
    P[f"hip_yaw_link_{side}"] = (f"hip_yaw_{side}", _recut(hb.fuse(yaw_m, roll_m, col, lap, gus),
                                                         j["hip_yaw"], j["hip_roll"]))
    P[f"hip_yaw_idler_{side}"] = (f"hip_yaw_{side}", yaw_i)
    P[f"hip_roll_idler_{side}"] = (f"hip_yaw_{side}", roll_i)

    z_roll_end = L.Z_HIP_ROLL - hb.CR_END
    z_pitch_top = L.Z_HIP_PITCH + hb.CR_Y
    x_back = -hb.CR_END
    plate = W(x_back, L.X_HIP_YR + hb.CR_Z[1], 24, 64.03, z_pitch_top + 3.1, z_roll_end + 0.3, s)
    post = W(x_back, -xc["hip_pitch"], 24, 64.03, z_pitch_top - 0.5, z_pitch_top + 3.6, s)
    P[f"hip_cross_{side}"] = (f"hip_cross_{side}",
                              hb.fuse(cradle(j["hip_roll"]), cradle(j["hip_pitch"]), plate, post))

    hp_m, hp_i = bracket(j["hip_pitch"])
    z_hp_bridge = L.Z_HIP_PITCH - L.bracket_params(j["hip_pitch"])[1] - hb.TB
    z_knee_end = L.Z_KNEE + hb.CR_END
    tube = _tube(W(-12, 12, 25.4, 64.0, z_knee_end - 0.5, z_hp_bridge + 0.6, s),
                 W(-9, 9, 28.4, 61.0, z_knee_end - 2, z_hp_bridge + 2, s))
    P[f"thigh_{side}"] = (f"thigh_{side}", _recut(hb.fuse(hp_m, tube, cradle(j["knee"])), j["hip_pitch"]))
    P[f"hip_pitch_idler_{side}"] = (f"thigh_{side}", hp_i)

    kn_m, kn_i = bracket(j["knee"])
    ap_m, ap_i = bracket(j["ankle_pitch"])
    z_kn_bridge = L.Z_KNEE - L.bracket_params(j["knee"])[1] - hb.TB
    z_ap_bridge = L.Z_ANKLE_PITCH + L.bracket_params(j["ankle_pitch"])[1] + hb.TB
    tube = _tube(W(-12, 12, 25.4, 64.0, z_ap_bridge - 0.6, z_kn_bridge + 0.6, s),
                 W(-9, 9, 28.4, 61.0, z_ap_bridge - 2, z_kn_bridge + 2, s))
    P[f"shin_{side}"] = (f"shin_{side}", _recut(hb.fuse(kn_m, tube, ap_m), j["knee"], j["ankle_pitch"]))
    P[f"knee_idler_{side}"] = (f"shin_{side}", kn_i)
    P[f"ankle_pitch_idler_{side}"] = (f"shin_{side}", ap_i)

    z_ar_end = L.Z_ANKLE_ROLL + hb.CR_END
    z_ap_bot = L.Z_ANKLE_PITCH - hb.CR_Y
    conn = W(x_back, -xc["ankle_pitch"], 30.1, 59.9, z_ar_end - 0.5, z_ap_bot + 0.5, s)
    P[f"ankle_cross_{side}"] = (f"ankle_cross_{side}",
                                hb.fuse(cradle(j["ankle_pitch"]), cradle(j["ankle_roll"]), conn))

    ar_m, ar_i = bracket(j["ankle_roll"])
    z_ar_bridge = L.Z_ANKLE_ROLL - L.bracket_params(j["ankle_roll"])[1] - hb.TB
    x0, x1 = L.X_ANKLE_ROLL + hb.Z_IDLER_IN, L.X_ANKLE_ROLL + hb.Z_HI
    foot = _rz(W(L.FOOT_X[0], L.FOOT_X[1], L.LEG_Y - L.FOOT_HY, L.LEG_Y + L.FOOT_HY, L.SOLE_T, 10, s), FOOT_FILLET)
    foot = hb.cut(foot, *[_zhole(x, s * y, 2.6) for x in STRAP_X for y in (20, 70)])   # lightening/strap
    conn = W(x0, x1, 33, 57, 9.5, z_ar_bridge + 0.6, s)
    P[f"foot_{side}"] = (f"foot_{side}", _recut(hb.fuse(ar_m, conn, foot), j["ankle_roll"]))
    P[f"ankle_roll_idler_{side}"] = (f"foot_{side}", ar_i)
    P[f"sole_tpu_{side}"] = (f"foot_{side}", _rz(W(L.FOOT_X[0], L.FOOT_X[1], L.LEG_Y - L.FOOT_HY,
                                                   L.LEG_Y + L.FOOT_HY, 0, L.SOLE_T, s), FOOT_FILLET))
    for k in L.LEG_JOINTS:
        P[f"servo_{k}_{side}"] = (L.JOINTS[j[k]]["body"], servo(j[k]))
    return P


def _zhole(x, y, r):
    return hb.cyl_z(r, -1, 20, x, y)


def _recut(shape, *jns):
    """Re-open the idler bolt / insert holes after structure has been fused onto a bracket."""
    tools = []
    for jn in jns:
        phi, R, _ = L.bracket_params(jn)
        tools += [inJ(jn, t) for t in hb._bridge_bolts(phi, R, hb.Z_IDLER_IN - 0.01, hb.Z_IDLER_IN + 7, 2.0)]
    return hb.cut(shape, *tools)


# --------------------------------------------------------------------------- arms
def arm(side) -> dict:
    s = 1 if side == "L" else -1
    P = {}
    sh, el, gr = f"shoulder_{side}", f"elbow_{side}", f"gripper_{side}"
    # upper arm: horn plate + spacer + elbow cradle (shoulder J frame: x down, z outward)
    zx = L.Z_SHOULDER - (L.Z_ELBOW + L.bracket_params(el)[2])
    hull = hb.hull2d(hb.circle(0, 0, 14.0) + [(0, -hb.CR_Y), (zx, -hb.CR_Y), (zx, hb.CR_Y), (0, hb.CR_Y)])
    plate = hb.cut(hb.prism(hull, hb.HF, hb.HF + 3.0), *hb._horn_holes(hb.HF - 1, hb.HF + 4))
    y_spacer0 = L.SHOULDER_Y + hb.HF + 3.0
    y_cr_in = L.ELBOW_Y + hb.CR_Z[0]
    spacer = W(-hb.CR_Y, hb.CR_Y, y_spacer0 - 0.3, y_cr_in + 0.4, L.Z_ELBOW + L.bracket_params(el)[2],
               L.Z_ELBOW + hb.CR_END, s)
    P[f"upper_arm_{side}"] = (f"upper_arm_{side}", hb.fuse(inJ(sh, plate), spacer, cradle(el)))
    P[f"servo_shoulder_{side}"] = ("base", servo(sh))
    P[f"servo_elbow_{side}"] = (f"upper_arm_{side}", servo(el))

    # forearm: elbow bracket + hollow spine + SC09 holder + palm + fixed jaw
    em, ei = bracket(el)
    px, py, pz = L.GRIP_P
    z_br = L.Z_ELBOW - L.bracket_params(el)[1] - hb.TB
    spine = _tube(W(-12, 12, 83.4, 118.0, pz + 18.0, z_br + 0.6, s),
                  W(-9, 9, 86.4, 115.0, pz + 17, z_br + 2, s))
    holder = W(px - 10, px + 8, 94.0, 118.0, pz - 8, pz + 20.5, s)
    pocket = inJ(gr, hb.fuse(hb.box(-6.0, 17.6, -6.2, 6.2, -22.2, 1.0), hb.cyl_z(4.0, -1, 4)))
    holder = hb.cut(holder, pocket)
    palm = W(px - 50, px + 8, 96.0, 118.0, pz - 10, pz - 6, s)
    jaw = W(px - 50, px - 44, 100.0, 124.6, pz - 58, pz - 6, s)
    P[f"forearm_{side}"] = (f"forearm_{side}", _recut(hb.fuse(em, spine, holder, palm, jaw), el))
    P[f"elbow_idler_{side}"] = (f"forearm_{side}", ei)
    P[f"jaw_pad_tpu_{side}"] = (f"forearm_{side}", _fin_pad(px - 44, +1, 112.0, 124.6, pz - 58, pz - 28, s))
    P[f"servo_gripper_{side}"] = (f"forearm_{side}", servo(gr))
    # finger on the SC09 horn
    hub = _ycyl(7.0, px, py + 0.6, py + 6.6, pz, s)
    bar = W(px - 4, px + 4, py + 0.6, py + 6.6, pz - 58, pz, s)
    finger = hb.cut(hb.fuse(hub, bar), _ycyl(4.2, px, py, py + 3.6, pz, s), _ycyl(1.2, px, py, py + 7, pz, s))
    P[f"finger_{side}"] = (f"finger_{side}", finger)
    P[f"finger_pad_tpu_{side}"] = (f"finger_{side}", _fin_pad(px - 4, -1, py + 0.6, py + 6.6, pz - 58, pz - 30, s))
    return P


def _fin_pad(x_face, direction, y0, y1, z0, z1, s):
    """Fin-ray style TPU pad: hollow wedge 6 mm deep with 3 cross ribs, grows from x_face."""
    d, t = 6.0, 1.0
    xa, xb = sorted((x_face, x_face + direction * d))
    outer = W(xa, xb, y0, y1, z0, z1, s)
    xi0, xi1 = (xa + t, xb) if direction > 0 else (xa, xb - t)
    inner = W(xi0, xi1, y0 + t, y1 - t, z0 + t, z1 - t, s)
    pad = hb.cut(outer, inner)
    ribs = [W(xa, xb, y0, y1, z0 + (z1 - z0) * k / 4 - t / 2, z0 + (z1 - z0) * k / 4 + t / 2, s) for k in (1, 2, 3)]
    return hb.fuse(pad, *ribs)


# --------------------------------------------------------------------------- torso, electronics, head
def torso() -> dict:
    P = {}
    hx, hy, w = L.TORSO_HX, L.TORSO_HY, L.WALL
    z0, z1 = L.Z_PELVIS + L.PELVIS_T, L.Z_TOP
    pelvis = W(-hx, hx, -hy, hy, L.Z_PELVIS, z0)
    risers, rails = [], []
    for side, s in (("L", 1), ("R", -1)):
        jn = f"hip_yaw_{side}"
        xc = L.bracket_params(jn)[2]
        z_cr_top = L.Z_HIP_YAW + hb.CR_Z[1]
        risers.append(hb.fuse(cradle(jn), W(L.X_HIP_YR - hb.CR_END, L.X_HIP_YR - xc, L.LEG_Y - hb.CR_Y,
                                            L.LEG_Y + hb.CR_Y, z_cr_top - 0.5, L.Z_PELVIS + 0.5, s)))
        rails.append(W(21.5, 24.5, -70, 70, z0 - 0.3, z0 + 10) if s > 0 else W(-24.5, -21.5, -70, 70, z0 - 0.3, z0 + 10))
    P["pelvis_plate"] = ("base", hb.fuse(pelvis, *risers, *rails))

    outer = W(-hx + w, hx, -hy, hy, z0, z1)
    inner = W(-hx - 1, hx - w, -hy + w, hy - w, z0 - 1, z1 + 1)
    shell = hb.cut(outer, inner)
    shelf = hb.cut(W(-hx + w, hx - w + 0.3, -hy + w - 0.3, hy - w + 0.3, 540, 543), W(-40, -30, -20, 20, 530, 550),
                   W(-12, 12, -72, -62, 530, 550), W(-12, 12, 62, 72, 530, 550))
    bosses = [hb.cyl_z(2.6, 543, 554, x, y) for x in (-24.5, 24.5) for y in (-29, 29)]
    bosses += [hb.cyl_z(2.6, 543, 549, x, y) for x in (-29, 29) for y in (41.5, 64.5)]
    bosses += [hb.cyl_z(2.6, 543, 549, x, -47) for x in (-12.5, 12.5)]
    body = hb.fuse(shell, shelf, *bosses)
    windows = []
    for side, s in (("L", 1), ("R", -1)):
        windows.append(W(-12.9, 12.9, hy - w - 1, hy + 1, L.Z_SHOULDER - 35.6, L.Z_SHOULDER + 10.6, s))
    P["torso_walls"] = ("base", hb.cut(body, *windows))
    back = W(-hx, -hx + w, -hy + w, hy - w, z0, z1)
    P["torso_back_cover"] = ("base", hb.cut(back, W(-hx - 1, -hx + w + 1, -6.5, 6.5, 603.5, 616.5)))

    top = W(-hx, hx, -hy, hy, z1, z1 + L.TOP_T)
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

    # purchased electronics (vendor envelopes)
    P["battery_3s_5000"] = ("base", W(-21, 21, -68, 68, z0, z0 + 28))
    P["ubec_6v"] = ("base", W(25.0, 42.0, -20, 20, z0, z0 + 9))
    P["driver_hat_a_board"] = ("base", W(-28.5, 28.5, -32.5, 32.5, 554, 555.6))
    P["driver_hat_a_components"] = ("base", W(-26, 26, -30, 30, 555.6, 569))
    P["pi_zero_2w_board"] = ("base", W(-32.5, 32.5, 38, 68, 549, 550.4))
    P["pi_zero_2w_components"] = ("base", W(-31, 31, 39, 67, 550.4, 555))
    P["imu_mpu6050"] = ("base", W(-12.5 + 2, 12.5 - 2, -55, -39, 549, 550.6))
    P["power_switch"] = ("base", hb.fuse(W(-hx - 1.5, -hx, -7.5, 7.5, 599.5, 620.5),
                                         W(-hx, -hx + 18, -6.4, 6.4, 603.6, 616.4)))
    return P


def head() -> dict:
    P = {}
    nx, ny, nz = L.NECK_PAN_P
    tx, ty, tz = L.NECK_TILT_P
    zd0 = nz + 0.6
    disc = hb.cut(hb.cyl_z(22.0, zd0, zd0 + 4.0, nx, ny), hb.cyl_z(3.2, zd0 - 1, zd0 + 3.1, nx, ny))
    holder = W(tx - 8, tx + 8, -13, ty, zd0 + 4.0, tz + 7.8)
    holder = hb.cut(holder, inJ("neck_tilt", hb.box(-6.0, 17.6, -6.2, 6.2, -22.2, 1.0)))
    P["neck_turntable"] = ("neck", hb.fuse(disc, holder))
    P["servo_neck_tilt"] = ("neck", servo("neck_tilt"))

    hx0, hx1, hy, hz0, hz1, w = -36.0, 46.0, 42.0, 712.0, 792.0, 2.4
    shell = hb.cut(W(hx0, hx1, -hy, hy, hz0, hz1), W(hx0 + w, hx1 - w, -hy + w, hy - w, hz0 - 1, hz1 - w))
    shell = hb.cut(shell, _xcyl(5.0, hx1 - w - 1, hx1 + 1, 0, 775),
                   *[W(hx1 - w - 1, hx1 + 1, s * 9.0, s * 31.0, 739.5, 750.5) for s in (1, -1)])
    hubp = hb.fuse(_ycyl(8.0, tx, ty + 1.0, ty + 6.6, tz), W(tx - 8, tx + 8, ty + 1.0, ty + 6.6, tz, hz1 - w + 0.5))
    hubp = hb.cut(hubp, _ycyl(3.2, tx, ty, ty + 4.0, tz))
    P["head_shell"] = ("head", hb.fuse(shell, hubp))
    P["camera_module_3"] = ("head", W(hx1 - w - 11.5, hx1 - w, -12.5, 12.5, 763, 787))
    for side, s in (("L", 1), ("R", -1)):
        P[f"oled_eye_{side}"] = ("head", W(hx1 - w - 3.7, hx1 - w, 6.35, 33.65, 731.1, 758.9, s))
    return P


# --------------------------------------------------------------------------- assembly
MATERIAL = {"tpu": ("tpu_", "sole_tpu"), "pcb": ("_board", "imu_", "camera_", "oled_"),
            "battery": ("battery_",), "vendor": ("servo_", "ubec_", "_components", "power_switch")}


def material(name):
    for m, keys in MATERIAL.items():
        if any(k in name for k in keys):
            return m
    return "pla"


def parts() -> dict:
    raw = {}
    for side in ("L", "R"):
        raw.update(leg(side))
        raw.update(arm(side))
    raw.update(torso())
    raw.update(head())
    out, errs = {}, []
    for n, (link, shape) in raw.items():
        m = material(n)
        try:
            out[n] = Part(link, _one(shape, n), m, "printed" if m in ("pla", "tpu") else "purchased")
        except ValueError as e:
            errs.append(str(e))
    if errs:
        raise ValueError("; ".join(errs))
    return out


def posed(P: dict, q: dict) -> dict:
    Tl = L.link_transforms(q)
    return {n: (p.shape if p.link == "base" else place(p.shape, Tl[p.link])) for n, p in P.items()}


DENSITY = {"pla": 1.24e-3, "tpu": 1.21e-3}
FILL = {"pla": 0.6, "tpu": 0.8}                  # 4 walls + 40 % gyroid -> ~60 % of solid mass
PURCHASED_G = {"servo_neck": L.SC_MASS_G, "servo_gripper": L.SC_MASS_G, "servo_": L.ST_MASS_G,
               "battery_": 346.0, "ubec_": 15.0, "driver_hat_a_board": 82.0, "driver_hat_a_comp": 0.0,
               "pi_zero_2w_board": 11.0, "pi_zero_2w_comp": 0.0, "imu_": 3.0, "camera_": 4.0, "oled_": 3.0,
               "power_switch": 6.0}
HARDWARE_G = {"base": 140.0}                     # wiring, connectors, fasteners (estimate)
SERVO_HW_G = 8.0                                 # screws + horn hardware per joint


def mass_g(name, part) -> float:
    if part.material in DENSITY:
        return part.shape.Volume() * DENSITY[part.material] * FILL[part.material]
    for k, g in PURCHASED_G.items():
        if name.startswith(k) or k in name:
            return g + (SERVO_HW_G if k.startswith("servo") else 0.0)
    raise KeyError(name)


def link_inertia(P: dict):
    mass, mom = {}, {}
    for n, p in P.items():
        m = mass_g(n, p)
        c = p.shape.Center()
        mass[p.link] = mass.get(p.link, 0.0) + m
        mom[p.link] = mom.get(p.link, np.zeros(3)) + m * np.array([c.x, c.y, c.z])
    for ln, g in HARDWARE_G.items():
        mass[ln] += g
        mom[ln] += g * np.array([0.0, 0.0, 560.0])
    return mass, {ln: mom[ln] / mass[ln] for ln in mass}
