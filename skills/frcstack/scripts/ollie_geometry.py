"""
ollie_geometry.py -- OLLIE v2 skeleton + assembly (zero pose, world mm).

Structure (the strong part): every servo U-bracket now has a CNC 3 mm 6061 horn plate and a 4 mm 6061
idler plate (printed bridge between them), thigh and shin bones are 1 x 1.5 in 6061 box tube (FRC stock)
with printed end blocks, an aluminium pelvis plate and two aluminium side frame plates carry the torso.
Bodywork (the look) is in ollie_fairings.py.  PROPOSED DESIGN -- not built or tested.
"""
from __future__ import annotations

import numpy as np

import humanoid_brackets as hb
import humanoid_geometry as G
import ollie_layout as OL
import humanoid_layout as L
import ollie_fairings as F
from humanoid_geometry import W, Part, _ycyl, inJ, servo

OL.apply()
FUSION_LINK = {}                         # wheel parts ride on the foot for statics; Fusion spins them
TUBE = (25.4, 25.4, 1.6)                 # 1 x 1 x 1/16 in 6061 square tube (FRC stock) (x, y, wall)


def _cq():
    import cadquery as cq
    return cq


# --------------------------------------------------------------------------- brackets
def ubracket(jn):
    """(horn plate Al 3 mm, printed bridge, idler plate Al 4 mm, plate envelope) in world coords."""
    phi, R, _ = L.bracket_params(jn)
    hull = hb.plate_hull(phi, R)
    env = hb.prism(hull, hb.HF, hb.Z_HI)
    plate = hb.cut(env, *hb._horn_holes(hb.Z_LO, hb.Z_HI), *hb._bridge_bolts(phi, R, hb.HF - 1, hb.Z_HI + 1, 1.7))
    bridge = hb.prism(hb.bridge_poly(phi, R), hb.Z_IDLER_IN, hb.HF)
    return inJ(jn, plate), inJ(jn, bridge), inJ(jn, hb.bracket_idler(phi, R)), inJ(jn, env)


def bolt_tools(*jns):
    """Insert holes at both bridge ends (idler end + horn-plate end)."""
    out = []
    for jn in jns:
        phi, R, _ = L.bracket_params(jn)
        out += [inJ(jn, t) for t in hb._bridge_bolts(phi, R, hb.Z_IDLER_IN - 0.01, hb.Z_IDLER_IN + 7, 2.0)]
        out += [inJ(jn, t) for t in hb._bridge_bolts(phi, R, hb.HF - 7, hb.HF + 0.01, 2.0)]
    return out


def printed(shape, envs, jns):
    return hb.cut(hb.cut(shape, *bolt_tools(*jns)), *envs)


def box_tube(z0, z1, s, xc=0.0, yc=None):
    tx, ty, t = TUBE
    yc = L.LEG_Y if yc is None else yc
    outer = W(xc - tx / 2, xc + tx / 2, yc - ty / 2, yc + ty / 2, z0, z1, s)
    inner = W(xc - tx / 2 + t, xc + tx / 2 - t, yc - ty / 2 + t, yc + ty / 2 - t, z0 - 1, z1 + 1, s)
    return hb.cut(outer, inner)


def tube_plug(z0, z1, s, yc=None):
    tx, ty, t = TUBE
    yc = L.LEG_Y if yc is None else yc
    return W(-tx / 2 + t, tx / 2 - t, yc - ty / 2 + t, yc + ty / 2 - t, z0, z1, s)


# --------------------------------------------------------------------------- legs
def leg(side) -> dict:
    s = 1 if side == "L" else -1
    j = {k: f"{k}_{side}" for k in L.LEG_JOINTS}
    xc = {k: L.bracket_params(j[k])[2] for k in L.LEG_JOINTS}
    B = {k: ubracket(j[k]) for k in L.LEG_JOINTS}
    P = {}
    for k, (pl, _, idl, _) in B.items():
        lk = L.bracket_link(j[k])
        P[f"{k}_plate_al_{side}"] = (lk, pl)
        P[f"{k}_idler_al_{side}"] = (lk, idl)
    zr, zy = L.Z_HIP_ROLL, L.Z_HIP_YAW
    col = W(40.5, 44.5, 33, 57, zr + 16, zy + 21.6, s)
    lap = W(39.5, 40.6, 33, 57, zy - 19, zy + 21.6, s)
    gus = W(30, 40.6, 33, 57, zr + 19.5, zr + 31, s)
    P[f"hip_yaw_link_{side}"] = (f"hip_yaw_{side}", printed(hb.fuse(B["hip_yaw"][1], B["hip_roll"][1], col, lap, gus),
                                                             [B["hip_yaw"][3], B["hip_roll"][3]],
                                                             (j["hip_yaw"], j["hip_roll"])))
    z_roll_end = L.Z_HIP_ROLL - hb.CR_END
    z_pitch_top = L.Z_HIP_PITCH + hb.CR_Y
    x_back = -hb.CR_END
    plate = W(x_back, L.X_HIP_YR + hb.CR_Z[1], 24, 64.03, z_pitch_top + 3.1, z_roll_end + 0.3, s)
    post = W(x_back, -xc["hip_pitch"], 24, 64.03, z_pitch_top - 0.5, z_pitch_top + 3.6, s)
    P[f"hip_cross_{side}"] = (f"hip_cross_{side}", hb.fuse(G.cradle(j["hip_roll"]), G.cradle(j["hip_pitch"]), plate, post))

    # thigh: printed hip block (bridge + plug) / Al box tube / printed knee cradle block (+ plug)
    z_hp_bridge = L.Z_HIP_PITCH - L.bracket_params(j["hip_pitch"])[1] - hb.TB
    z_knee_end = L.Z_KNEE + hb.CR_END
    P[f"thigh_tube_al_{side}"] = (f"thigh_{side}", box_tube(z_knee_end, z_hp_bridge, s))
    P[f"thigh_hip_block_{side}"] = (f"thigh_{side}", printed(hb.fuse(B["hip_pitch"][1], tube_plug(z_hp_bridge - 14, z_hp_bridge + 0.6, s)),
                                                             [B["hip_pitch"][3]], (j["hip_pitch"],)))
    P[f"thigh_knee_block_{side}"] = (f"thigh_{side}", hb.fuse(G.cradle(j["knee"]), tube_plug(z_knee_end - 0.5, z_knee_end + 14, s)))

    z_kn_bridge = L.Z_KNEE - L.bracket_params(j["knee"])[1] - hb.TB
    z_ap_bridge = L.Z_ANKLE_PITCH + L.bracket_params(j["ankle_pitch"])[1] + hb.TB
    P[f"shin_tube_al_{side}"] = (f"shin_{side}", box_tube(z_ap_bridge, z_kn_bridge, s))
    P[f"shin_knee_block_{side}"] = (f"shin_{side}", printed(hb.fuse(B["knee"][1], tube_plug(z_kn_bridge - 14, z_kn_bridge + 0.6, s)),
                                                            [B["knee"][3]], (j["knee"],)))
    P[f"shin_ankle_block_{side}"] = (f"shin_{side}", printed(hb.fuse(B["ankle_pitch"][1], tube_plug(z_ap_bridge - 0.6, z_ap_bridge + 14, s)),
                                                             [B["ankle_pitch"][3]], (j["ankle_pitch"],)))

    z_ar_end = L.Z_ANKLE_ROLL + hb.CR_END
    z_ap_bot = L.Z_ANKLE_PITCH - hb.CR_Y
    conn = W(x_back, -xc["ankle_pitch"], 30.1, 59.9, z_ar_end - 0.5, z_ap_bot + 0.5, s)
    P[f"ankle_cross_{side}"] = (f"ankle_cross_{side}", hb.fuse(G.cradle(j["ankle_pitch"]), G.cradle(j["ankle_roll"]), conn))

    # foot: Al sole plate (pointed plan) + printed ankle/heel block + TPU sole
    z_plate = L.SOLE_T + OL.AL_T
    z_ar_bridge = L.Z_ANKLE_ROLL - L.bracket_params(j["ankle_roll"])[1] - hb.TB
    x0, x1 = L.X_ANKLE_ROLL + hb.Z_IDLER_IN, L.X_ANKLE_ROLL + hb.Z_HI
    conn = W(x0, x1, 33, 57, z_plate, z_ar_bridge + 0.6, s)
    pod = F.heel_pod(side, z_plate)
    deck = F.foot_deck(side, z_plate)
    P[f"foot_{side}"] = (f"foot_{side}", printed(hb.fuse(B["ankle_roll"][1], conn, pod, deck), [B["ankle_roll"][3]], (j["ankle_roll"],)))
    plate = hb.cut(F.plan_prism(OL.FOOT_PLAN, L.SOLE_T, z_plate, s), *[G._zhole(x, s * y, 1.7) for x in (-25, 60) for y in (20, 70)])
    P[f"foot_plate_al_{side}"] = (f"foot_{side}", plate)
    P[f"sole_tpu_{side}"] = (f"foot_{side}", F.plan_prism(OL.FOOT_PLAN, 0.0, L.SOLE_T, s))
    for n, shp in F.heel_parts(side).items():
        P[n] = (f"foot_{side}", shp)
    for k in L.LEG_JOINTS:
        P[f"servo_{k}_{side}"] = (L.JOINTS[j[k]]["body"], servo(j[k]))
    return P


# --------------------------------------------------------------------------- arms
def arm(side) -> dict:
    s = 1 if side == "L" else -1
    P = {}
    sh, el, gr = f"shoulder_{side}", f"elbow_{side}", f"gripper_{side}"
    zx = L.Z_SHOULDER - (L.Z_ELBOW + L.bracket_params(el)[2])
    hull = hb.hull2d(hb.circle(0, 0, 14.0) + [(0, -hb.CR_Y), (zx, -hb.CR_Y), (zx, hb.CR_Y), (0, hb.CR_Y)])
    P[f"shoulder_plate_al_{side}"] = (f"upper_arm_{side}", inJ(sh, hb.cut(hb.prism(hull, hb.HF, hb.HF + 3.0), *hb._horn_holes(hb.HF - 1, hb.HF + 4))))
    y_spacer0 = L.SHOULDER_Y + hb.HF + 3.0
    y_cr_in = L.ELBOW_Y + hb.CR_Z[0]
    spacer = W(-hb.CR_Y, hb.CR_Y, y_spacer0, y_cr_in + 0.4, L.Z_ELBOW + L.bracket_params(el)[2], L.Z_ELBOW + hb.CR_END, s)
    P[f"upper_arm_{side}"] = (f"upper_arm_{side}", hb.fuse(spacer, G.cradle(el)))
    P[f"servo_shoulder_{side}"] = ("base", servo(sh))
    P[f"servo_elbow_{side}"] = (f"upper_arm_{side}", servo(el))

    pl, br, idl, env = ubracket(el)
    P[f"elbow_plate_al_{side}"] = (f"forearm_{side}", pl)
    P[f"elbow_idler_al_{side}"] = (f"forearm_{side}", idl)
    px, py, pz = L.GRIP_P
    z_br = L.Z_ELBOW - L.bracket_params(el)[1] - hb.TB
    spine = G._tube(W(-12, 12, 83.4, 118.0, pz + 18.0, z_br + 0.6, s), W(-9, 9, 86.4, 115.0, pz + 17, z_br + 2, s))
    holder = W(px - 10, px + 8, 94.0, 118.0, pz - 8, pz + 20.5, s)
    pocket = inJ(gr, hb.fuse(hb.box(-6.0, 17.6, -6.2, 6.2, -22.2, 1.0), hb.cyl_z(4.0, -1, 4)))
    holder = hb.cut(holder, pocket)
    P[f"forearm_{side}"] = (f"forearm_{side}", printed(hb.fuse(br, spine, holder), [env], (el,)))
    P[f"servo_gripper_{side}"] = (f"forearm_{side}", servo(gr))
    for n, (ln, shp) in F.hand(side).items():
        P[n] = (ln, shp)
    return P


# --------------------------------------------------------------------------- torso frame + electronics
def torso() -> dict:
    P = {}
    z0, z1 = L.Z_PELVIS + L.PELVIS_T, L.Z_TOP
    dz = z0 - 493.0                                       # v1 electronics heights were set for z0 = 493
    P["pelvis_plate"] = ("base", G._rz(W(-45, 45, -75, 75, L.Z_PELVIS, z0), 14))
    for side, s in (("L", 1), ("R", -1)):
        jn = f"hip_yaw_{side}"
        xc = L.bracket_params(jn)[2]
        z_cr_top = L.Z_HIP_YAW + hb.CR_Z[1]
        P[f"hip_yaw_mount_{side}"] = ("base", hb.fuse(G.cradle(jn), W(L.X_HIP_YR - hb.CR_END, L.X_HIP_YR - xc, L.LEG_Y - hb.CR_Y,
                                                                     L.LEG_Y + hb.CR_Y, z_cr_top - 0.5, L.Z_PELVIS, s)))
        frame = W(-32, 32, 69.6, 72.8, z0, z1 - 7, s)
        frame = hb.cut(frame, W(-13.6, 13.6, 60, 80, L.Z_SHOULDER - 38, z1 + 1, s),
                       *[F.slot_y(x, zc, 60, 80, s) for x, zc in ((-16, 590), (16, 590), (-16, 640), (16, 640))])
        P[f"side_frame_al_{side}"] = ("base", frame)
    P["battery_rail_L"] = ("base", W(21.5, 24.5, -66, 66, z0, z0 + 10))
    P["battery_rail_R"] = ("base", W(-24.5, -21.5, -66, 66, z0, z0 + 10))
    shelf = W(-40, 40, -68.9, 68.9, 540 + dz, 543 + dz)
    shelf = hb.cut(shelf, W(-40, -30, -20, 20, 530 + dz, 550 + dz), W(-12, 12, -72, -62, 530 + dz, 550 + dz),
                   W(-12, 12, 62, 72, 530 + dz, 550 + dz))
    bosses = [hb.cyl_z(2.6, 543 + dz, 554 + dz, x, y) for x in (-24.5, 24.5) for y in (-29, 29)]
    bosses += [hb.cyl_z(2.6, 543 + dz, 549 + dz, x, y) for x in (-29, 29) for y in (41.5, 64.5)]
    bosses += [hb.cyl_z(2.6, 543 + dz, 549 + dz, x, -47) for x in (-12.5, 12.5)]
    P["electronics_shelf"] = ("base", hb.fuse(shelf, *bosses))
    top = W(-45, 45, -68.6, 68.6, z1, z1 + L.TOP_T)
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
    top = hb.cut(hb.fuse(G._rz(top, 10), *hangers, nholder), W(nx + 20, nx + 30, -6, 6, z1 - 1, z1 + 8))
    P["torso_top_plate"] = ("base", top)
    P["servo_neck_pan"] = ("base", servo("neck_pan"))
    P["battery_3s_5000"] = ("base", W(-21, 21, -68, 68, z0, z0 + 28))
    P["ubec_6v_5a"] = ("base", W(25.0, 42.0, -20, 20, z0, z0 + 9))
    P["driver_hat_a_board"] = ("base", W(-28.5, 28.5, -32.5, 32.5, 554 + dz, 555.6 + dz))
    P["driver_hat_a_components"] = ("base", W(-26, 26, -30, 30, 555.6 + dz, 569 + dz))
    P["pi_zero_2w_board"] = ("base", W(-32.5, 32.5, 38, 68, 549 + dz, 550.4 + dz))
    P["pi_zero_2w_components"] = ("base", W(-31, 31, 39, 67, 550.4 + dz, 555 + dz))
    P["imu_mpu6050"] = ("base", W(-10.5, 10.5, -55, -39, 549 + dz, 550.6 + dz))
    P["drv8833_wheel_driver"] = ("base", W(-35, -22.3, -60, -40, 543 + dz, 546 + dz))
    P.update(F.torso_fairings())
    return P


# --------------------------------------------------------------------------- head
def head() -> dict:
    P = {}
    nx, ny, nz = L.NECK_PAN_P
    tx, ty, tz = L.NECK_TILT_P
    zd0 = nz + 0.6
    disc = hb.cut(hb.cyl_z(22.0, zd0, zd0 + 4.0, nx, ny), hb.cyl_z(3.2, zd0 - 1, zd0 + 3.1, nx, ny))
    holder = hb.cut(W(tx - 8, tx + 8, -13, ty, zd0 + 4.0, tz + 7.8), inJ("neck_tilt", hb.box(-6.0, 17.6, -6.2, 6.2, -22.2, 1.0)))
    P["neck_turntable"] = ("neck", hb.fuse(disc, holder))
    P["servo_neck_tilt"] = ("neck", servo("neck_tilt"))
    collar = F.S.prism(F.octagon(0, 0, 29.0), "z", zd0 + 5.0, zd0 + 18.0)
    P["fair_neck_collar"] = ("neck", hb.cut(collar, F.S.prism(F.octagon(0, 0, 27.4), "z", zd0, zd0 + 20.0)))
    P.update({n: ("head", s) for n, s in F.head_parts().items()})
    return P


# --------------------------------------------------------------------------- assembly
VENDOR_KEYS = ("servo_", "ubec_", "_components", "power_switch", "n20_", "bearing_", "axle_pin", "drv8833", "led_")
PCB_KEYS = ("_board", "imu_", "camera_", "oled_")


def material(name):
    if "_al" in name:
        return "al"
    if "tpu" in name:
        return "tpu"
    if "acrylic" in name or "visor" in name:
        return "acrylic"
    if name.startswith("battery_3s"):
        return "battery"
    if any(k in name for k in PCB_KEYS):
        return "pcb"
    if any(k in name for k in VENDOR_KEYS):
        return "vendor"
    if any(name.startswith(k) for k in F.FAIRING_KEYS):
        return "petg"
    return "pla"


def parts() -> dict:
    raw = {}
    for side in "LR":
        raw.update(leg(side))
        raw.update(arm(side))
    raw.update(torso())
    raw.update(head())
    for n in list(raw):
        if n.startswith(("wheel_hub", "tire_tpu", "axle_pin")):
            FUSION_LINK[n] = "wheel_" + n[-1]
    raw.update(F.limb_fairings())
    for n in [k for k in raw if k.startswith(F.FAIRING_KEYS)]:     # a cut-out can split a panel: print as pieces
        link, shp = raw[n]
        sol = sorted(shp.clean().Solids(), key=lambda q: -q.Volume())
        if len(sol) > 1:
            del raw[n]
            for i, q in enumerate(sol):
                if q.Volume() > 20.0:
                    raw[f"{n}_{'abcdefgh'[i]}"] = (link, q)
    out, errs = {}, []
    for n, (link, shape) in raw.items():
        m = material(n)
        try:
            out[n] = Part(link, G._one(shape, n), m, "printed" if m in ("pla", "tpu", "petg") else
                          ("machined" if m == "al" else "purchased"))
        except ValueError as e:
            errs.append(str(e))
    if errs:
        raise ValueError("; ".join(errs))
    return out


def fusion_link(name, part):
    return FUSION_LINK.get(name, part.link)


MASS_G = {"n20_": OL.N20_MASS_G, "bearing_": 1.0, "axle_pin": 0.5, "drv8833": 2.0, "led_": 3.0, "oled_eye": 2.0,
          "ubec_6v_5a": 18.0, "camera_": 4.0, "power_switch": 6.0}
DENS = {"pla": 1.24e-3 * 0.6, "tpu": 1.21e-3 * 0.8, "acrylic": 1.18e-3, "petg": 1.27e-3 * 0.95, "al": 2.70e-3}


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
    hw = 200.0                                  # wiring, connectors, fasteners (estimate)
    mass["base"] += hw
    mom["base"] += hw * np.array([0.0, 0.0, L.Z_PELVIS + 70.0])
    return mass, {ln: mom[ln] / mass[ln] for ln in mass}


def posed(P: dict, q: dict, Tb=None) -> dict:
    import ollie_physics as OP
    Tl = OP.transforms(q, np.eye(4) if Tb is None else Tb)
    return {n: G.place(p.shape, Tl[p.link]) for n, p in P.items()}
