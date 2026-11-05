"""
export_ollie_mjcf.py -- turn the OLLIE CAD into a MuJoCo model (runs in the CAD venv).

Usage:  python export_ollie_mjcf.py OUT_DIR

Writes OUT_DIR/meshes/<link>.stl (one visual mesh per moving link, zero pose, metres) and
OUT_DIR/ollie.xml (MJCF):
  * kinematic tree from humanoid_layout.JOINTS (+ the two heel wheels), joint axes/points from the CAD
  * link masses + COMs from the CAD part volumes (ollie_geometry.link_inertia), inertia from the mesh
  * ST3215 joints: position actuators, force limit = stall torque at 11.1 V; SC09: 0.23 N.m;
    heel wheels: velocity actuators limited to the N20 stall torque
  * collision geometry: soles, tires, knee + paw pads as boxes / cylinders (the parts that touch the
    floor), plus the visual meshes for self-collision between non-adjacent links
PROPOSED DESIGN -- a physics model of the CAD, not a validated digital twin.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

import humanoid_layout as L
import ollie_geometry as OG
import ollie_layout as OL

ACCENT = {"base": "shell", "head": "shell", "neck": "dark", "thigh": "shell", "shin": "shell",
          "upper_arm": "shell", "forearm": "shell", "foot": "shell", "hip_yaw": "dark", "hip_cross": "dark",
          "ankle_cross": "dark", "finger": "dark", "wheel": "tire"}


def _fmt(v):
    return " ".join(f"{x:.6g}" for x in v)


def link_material(ln):
    for k, m in ACCENT.items():
        if ln.startswith(k):
            return m
    return "shell"


def export_meshes(P, out):
    import cadquery as cq
    from OCP.StlAPI import StlAPI_Writer  # noqa: F401  (ensures OCP present)
    groups = {}
    for n, p in P.items():
        groups.setdefault(OG.fusion_link(n, p), []).append(p.shape)
    (out / "meshes").mkdir(parents=True, exist_ok=True)
    for ln, shapes in groups.items():
        comp = cq.Compound.makeCompound(shapes)
        path = out / "meshes" / f"{ln}.stl"
        cq.exporters.export(comp, str(path), tolerance=0.4, angularTolerance=0.35)
    return sorted(groups)


def tree():
    joints = {**{k: dict(v) for k, v in L.JOINTS.items()}, **{k: dict(v) for k, v in OL.WHEEL_JOINTS.items()}}
    children = {}
    for jn, j in joints.items():
        children.setdefault(j["parent"], []).append(jn)
    return joints, children


def body_xml(ln, origin, joints, children, mass, comz, depth):
    pad = "  " * depth
    out = []
    jn = next((k for k, j in joints.items() if j["child"] == ln), None)
    pos = np.zeros(3) if jn is None else (np.array(joints[jn]["p"]) - origin) * 1e-3
    here = origin if jn is None else np.array(joints[jn]["p"], float)
    out.append(f'{pad}<body name="{ln}" pos="{_fmt(pos)}">')
    if jn is None:
        out.append(f'{pad}  <freejoint name="root"/>')
    else:
        j = joints[jn]
        kind = j["kind"]
        if kind == "n20":
            out.append(f'{pad}  <joint name="{jn}" type="hinge" axis="{_fmt(j["axis"])}" damping="0.002" armature="0.0005"/>')
        else:
            lo, hi = sorted(j["range"])
            arm = 0.01 if kind == "st" else 0.002
            out.append(f'{pad}  <joint name="{jn}" type="hinge" axis="{_fmt(j["axis"])}" range="{lo} {hi}" '
                       f'damping="0.6" armature="{arm}" frictionloss="0.03" limited="true"/>')
    m = max(mass.get(ln, 0.0), 1.0) * 1e-3
    com = (np.array(comz.get(ln, here)) - here) * 1e-3
    out.append(f'{pad}  <inertial pos="{_fmt(com)}" mass="{m:.5g}" diaginertia="{_fmt(_inertia_guess(ln, m))}"/>')
    off = (-here) * 1e-3
    out.append(f'{pad}  <geom name="vis_{ln}" type="mesh" mesh="{ln}" pos="{_fmt(off)}" material="{link_material(ln)}" '
               f'class="visual"/>')
    for g in contact_geoms(ln, here):
        out.append(f"{pad}  {g}")
    for c in children.get(ln, []):
        out += body_xml(joints[c]["child"], here, joints, children, mass, comz, depth + 1)
    out.append(f"{pad}</body>")
    return out


def _inertia_guess(ln, m):
    size = {"base": (0.09, 0.15, 0.22), "head": (0.08, 0.13, 0.05)}.get(ln, (0.05, 0.05, 0.12))
    a, b, c = size
    return (m * (b * b + c * c) / 12, m * (a * a + c * c) / 12, m * (a * a + b * b) / 12)


def contact_geoms(ln, here):
    """Floor-contact primitives (positions relative to the body frame = joint point)."""
    g = []

    def box(name, x0, x1, y0, y1, z0, z1, cls="contact"):
        c = (np.array([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]) - here) * 1e-3
        h = np.abs(np.array([x1 - x0, y1 - y0, z1 - z0])) / 2 * 1e-3
        g.append(f'<geom name="{name}" type="box" pos="{_fmt(c)}" size="{_fmt(h)}" class="{cls}"/>')
    for side, s in (("L", 1), ("R", -1)):
        ys = sorted((s * (L.LEG_Y - L.FOOT_HY), s * (L.LEG_Y + L.FOOT_HY)))
        if ln == f"foot_{side}":
            box(f"sole_{side}", L.FOOT_X[0], L.FOOT_X[1], ys[0], ys[1], 0.0, L.SOLE_T)
        if ln == f"wheel_{side}":
            c = (np.array([OL.WHEEL_X, s * 55.0, OL.WHEEL_Z]) - here) * 1e-3
            g.append(f'<geom name="tire_{side}" type="cylinder" pos="{_fmt(c)}" size="{OL.WHEEL_R * 1e-3:.4f} 0.0055" '
                     f'euler="90 0 0" class="contact" friction="1.2 0.02 0.002"/>')
        if ln == f"shin_{side}":
            k, zk = OL.KNEE_PAD, L.Z_KNEE
            yk = sorted((s * k[2], s * k[3]))
            box(f"knee_pad_{side}", k[0], k[1], yk[0], yk[1], zk + k[4], zk + k[5])
        if ln == f"forearm_{side}":
            b = OL.paw_box()
            yp = sorted((s * b[2], s * b[3]))
            box(f"paw_{side}", b[0], b[1], yp[0], yp[1], b[4], b[5])
    if ln == "base":
        box("torso_bump", -62, 80, -75, 75, L.Z_PELVIS, L.Z_TOP + 26, cls="bumper")
    if ln == "head":
        tz = L.JOINTS["neck_tilt"]["p"][2]
        box("head_bump", -44, 72, -62, 62, tz - 12, tz + 42, cls="bumper")
    return g


def actuators(joints):
    out = []
    for jn, j in joints.items():
        if j["kind"] == "st":
            f = L.ST_STALL_NM
            out.append(f'<position name="act_{jn}" joint="{jn}" kp="18" kv="0.4" forcerange="-{f:.3f} {f:.3f}" '
                       f'ctrlrange="{min(j["range"]) * math.pi / 180:.4f} {max(j["range"]) * math.pi / 180:.4f}"/>')
        elif j["kind"] == "sc":
            f = L.SC_STALL_NM
            out.append(f'<position name="act_{jn}" joint="{jn}" kp="2" kv="0.05" forcerange="-{f:.3f} {f:.3f}" '
                       f'ctrlrange="{min(j["range"]) * math.pi / 180:.4f} {max(j["range"]) * math.pi / 180:.4f}"/>')
        else:
            f = OL.N20_STALL_NM
            w = OL.N20_RPM * 2 * math.pi / 60
            out.append(f'<velocity name="act_{jn}" joint="{jn}" kv="0.02" forcerange="-{f:.3f} {f:.3f}" '
                       f'ctrlrange="-{w:.2f} {w:.2f}"/>')
    return out


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    P = OG.parts()
    mass, comz = OG.link_inertia(P)
    # wheel parts carry their own mass in the sim
    wmass, wcom = {}, {}
    for n, p in P.items():
        ln = OG.fusion_link(n, p)
        if ln.startswith("wheel_"):
            m = OG.mass_g(n, p)
            c = p.shape.Center()
            wmass[ln] = wmass.get(ln, 0) + m
            wcom.setdefault(ln, np.zeros(3))
            wcom[ln] = wcom[ln] + m * np.array([c.x, c.y, c.z])
            mass[p.link] -= m
    for ln in wmass:
        mass[ln] = wmass[ln]
        comz[ln] = wcom[ln] / wmass[ln]
    links = export_meshes(P, out)
    joints, children = tree()
    excl = [f'<exclude body1="{j["parent"]}" body2="{j["child"]}"/>' for j in joints.values()]
    xml = [
        '<mujoco model="OLLIE">',
        '  <compiler angle="degree" meshdir="meshes" autolimits="true"/>',
        '  <option timestep="0.002" iterations="50" solver="Newton" integrator="implicitfast"/>',
        '  <size memory="64M"/>',
        '  <visual><global offwidth="1920" offheight="1080"/><quality shadowsize="4096"/>'
        '<headlight ambient="0.35 0.35 0.35" diffuse="0.6 0.6 0.6"/></visual>',
        '  <default>',
        '    <default class="visual"><geom contype="0" conaffinity="0" group="1"/></default>',
        '    <default class="contact"><geom contype="1" conaffinity="1" group="3" rgba="1 .4 .2 .0" '
        'friction="1.0 0.02 0.002" solref="0.004 1" solimp="0.95 0.99 0.001"/></default>',
        '    <default class="bumper"><geom contype="1" conaffinity="1" group="3" rgba="0 0 0 0"/></default>',
        '  </default>',
        '  <asset>',
        '    <texture name="grid" type="2d" builtin="checker" rgb1=".93 .92 .9" rgb2=".86 .85 .83" width="512" height="512"/>',
        '    <material name="floor" texture="grid" texrepeat="8 8" reflectance="0.05"/>',
        '    <material name="shell" rgba="0.95 0.94 0.92 1" specular="0.3"/>',
        '    <material name="dark" rgba="0.17 0.18 0.21 1" specular="0.2"/>',
        '    <material name="tire" rgba="0.13 0.14 0.16 1"/>',
        '    <material name="orange" rgba="1 0.42 0.17 1"/>',
    ]
    xml += [f'    <mesh name="{ln}" file="{ln}.stl" scale="0.001 0.001 0.001"/>' for ln in links]
    xml += ['  </asset>', '  <worldbody>',
            '    <light pos="0.6 -0.6 2.0" dir="-0.3 0.3 -1" diffuse="0.8 0.8 0.8" castshadow="true"/>',
            '    <geom name="floor" type="plane" size="6 6 0.05" material="floor" contype="1" conaffinity="1"/>',
            '    <geom name="table_top" type="box" pos="1.9 0 0.465" size="0.3 0.45 0.015" rgba=".55 .42 .3 1"/>',
            '    <geom name="table_leg1" type="box" pos="1.62 0.42 0.225" size="0.015 0.015 0.225" rgba=".45 .34 .24 1"/>',
            '    <geom name="table_leg2" type="box" pos="1.62 -0.42 0.225" size="0.015 0.015 0.225" rgba=".45 .34 .24 1"/>',
            '    <geom name="table_leg3" type="box" pos="2.18 0.42 0.225" size="0.015 0.015 0.225" rgba=".45 .34 .24 1"/>',
            '    <geom name="table_leg4" type="box" pos="2.18 -0.42 0.225" size="0.015 0.015 0.225" rgba=".45 .34 .24 1"/>']
    body = body_xml("base", np.zeros(3), joints, children, mass, comz, 2)
    body[0] = body[0].replace('pos="0 0 0"', 'pos="0 0 0.002"')
    xml += body
    xml += ['  </worldbody>', '  <contact>'] + [f"    {e}" for e in excl] + ['  </contact>', '  <actuator>']
    xml += [f"    {a}" for a in actuators(joints)]
    xml += ['  </actuator>', '</mujoco>']
    (out / "ollie.xml").write_text("\n".join(xml))
    import json
    import ollie_physics as OP
    poses = {}
    q, Tb, _ = OP.skate_pose(mass, comz)
    poses["skate"] = {k: round(float(v), 2) for k, v in q.items()}
    q, Tb, beta = OP.crawl_pose(mass, comz)
    poses["crawl"] = {k: round(float(v), 2) for k, v in q.items()}
    poses["crawl_pitch_deg"] = float(beta)
    (out / "poses.json").write_text(json.dumps(poses, indent=1))
    print("wrote", out / "ollie.xml", "links", len(links), "mass g", round(sum(mass.values())))


if __name__ == "__main__":
    main(sys.argv[1])
