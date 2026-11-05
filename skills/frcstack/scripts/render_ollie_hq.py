"""
render_ollie_hq.py -- (sim venv) high-quality renders of OLLIE v2 with MuJoCo + a labelled callout sheet.

Usage:  python render_ollie_hq.py RENDER_DIR OUT_DIR
Reads RENDER_DIR/{stand,skate,crawl}/*.stl + manifest.json (from export_render_parts.py).
Writes OUT_DIR/ollie-v2-hero.png, -front.png, -side.png, -back.png, -skate.png, -crawl.png, -xray.png,
-callouts.png and -turntable.mp4.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080


def scene(rdir, pose, xray=False):
    man = json.loads((rdir / "manifest.json").read_text())
    assets, geoms = [], []
    for n, info in man["parts"].items():
        f = rdir / pose / f"{n}.stl"
        if not f.exists():
            continue
        r, g, b, a = info["rgba"]
        if xray and info["fairing"]:
            a = 0.12
        spec = 0.6 if info["material"] in ("al", "vendor") else 0.35
        assets.append(f'<mesh name="m_{n}" file="{f.as_posix()}" scale="0.001 0.001 0.001"/>')
        assets.append(f'<material name="c_{n}" rgba="{r} {g} {b} {a}" specular="{spec}" shininess="0.6" reflectance="0.02"/>')
        geoms.append(f'<geom type="mesh" mesh="m_{n}" material="c_{n}" contype="0" conaffinity="0"/>')
    xml = f"""<mujoco><compiler/><visual><global offwidth="{W}" offheight="{H}"/><quality shadowsize="8192" offsamples="8"/>
<headlight ambient="0.32 0.32 0.34" diffuse="0.45 0.45 0.47" specular="0.1 0.1 0.1"/></visual>
<asset><texture name="sky" type="skybox" builtin="gradient" rgb1="0.93 0.94 0.96" rgb2="0.78 0.8 0.84" width="512" height="512"/>
<texture name="fl" type="2d" builtin="checker" rgb1="0.86 0.87 0.89" rgb2="0.82 0.83 0.85" width="512" height="512"/>
<material name="floor" texture="fl" texrepeat="12 12" reflectance="0.12"/>{''.join(assets)}</asset>
<worldbody><light pos="1.2 -1.0 2.4" dir="-0.45 0.4 -1" diffuse="0.75 0.75 0.75" castshadow="true"/>
<light pos="-1.2 1.2 1.6" dir="0.5 -0.5 -0.6" diffuse="0.3 0.32 0.36" castshadow="false"/>
<geom type="plane" size="5 5 0.1" material="floor"/>{''.join(geoms)}</worldbody></mujoco>"""
    m = mujoco.MjModel.from_xml_string(xml)
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    return m, d, man


def shot(m, d, r, lookat, dist, az, el):
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = lookat
    cam.distance, cam.azimuth, cam.elevation = dist, az, el
    r.update_scene(d, cam)
    return r.render().copy(), cam


def font(sz, bold=False):
    for f in (("segoeuib.ttf" if bold else "segoeui.ttf"), "arial.ttf"):
        try:
            return ImageFont.truetype(f, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def caption(img, title, sub=None):
    im = Image.fromarray(img)
    dr = ImageDraw.Draw(im, "RGBA")
    dr.rectangle([0, H - 96, W, H], fill=(14, 22, 52, 215))
    dr.rectangle([0, H - 96, 12, H], fill=(30, 80, 220))
    dr.text((36, H - 88), title, font=font(40, True), fill=(255, 255, 255))
    if sub:
        dr.text((38, H - 40), sub, font=font(24), fill=(200, 210, 230))
    return im


def project(cam, p, fovy=45.0):
    """World point (m) -> pixel for a MuJoCo free camera."""
    az, el = math.radians(cam.azimuth), math.radians(cam.elevation)
    fwd = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    eye = np.array(cam.lookat) - cam.distance * fwd
    right = np.cross(fwd, [0, 0, 1])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    v = np.asarray(p) - eye
    z = v @ fwd
    f = (H / 2) / math.tan(math.radians(fovy) / 2)
    return W / 2 + f * (v @ right) / z, H / 2 - f * (v @ up) / z


def callouts(img, cam, labels):
    im = Image.fromarray(img)
    dr = ImageDraw.Draw(im, "RGBA")
    ft = font(26, True)
    items = sorted(((t, project(cam, np.array(p) * 1e-3)) for t, p in labels.items()), key=lambda kv: kv[1][1])
    left = [kv for kv in items if kv[1][0] < W / 2]
    right = [kv for kv in items if kv[1][0] >= W / 2]
    for side, group in (("L", left), ("R", right)):
        n = len(group)
        for i, (t, (px, py)) in enumerate(group):
            ty = 120 + i * (H - 260) / max(n - 1, 1)
            tw = dr.textlength(t, font=ft)
            tx = 40 if side == "L" else W - 40 - tw
            ax = tx + tw + 14 if side == "L" else tx - 14
            dr.line([(ax, ty + 16), (px, py)], fill=(30, 80, 220, 255), width=3)
            dr.ellipse([px - 7, py - 7, px + 7, py + 7], fill=(255, 255, 255), outline=(30, 80, 220), width=3)
            dr.rounded_rectangle([tx - 10, ty - 4, tx + tw + 10, ty + 38], 8, fill=(255, 255, 255, 235),
                                 outline=(30, 80, 220), width=2)
            dr.text((tx, ty), t, font=ft, fill=(14, 22, 52))
    return im


def main(rdir, out):
    rdir, out = Path(rdir), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    m, d, man = scene(rdir, "stand")
    r = mujoco.Renderer(m, H, W)
    sub = f"OLLIE v2  |  83 cm  |  {man['mass_g'] / 1000:.1f} kg  |  166 parts  |  $700 parts budget  |  CAD, not built yet"
    look = (0.0, 0.0, 0.43)
    for name, az, el, dist, title in (("hero", 215, -10, 1.75, "OLLIE v2: walk / skate / crawl humanoid"),
                                      ("front", 180, -4, 1.9, "Front"), ("side", 270, -4, 1.9, "Side"),
                                      ("back", 35, -10, 1.9, "Back: tail-wing carry handle")):
        img, _ = shot(m, d, r, look, dist, az, el)
        caption(img, title, sub).save(out / f"ollie-v2-{name}.png")
        print("wrote", name, flush=True)
    frames = []
    for k in range(240):
        img, _ = shot(m, d, r, look, 1.85, 180 + k * 1.5, -8)
        frames.append(img)
    r.close()
    import imageio.v2 as imageio
    imageio.mimwrite(out / "ollie-v2-turntable.mp4", frames, fps=30, quality=8, macro_block_size=8)
    print("wrote turntable", flush=True)

    mx, dx, man = scene(rdir, "stand", xray=True)
    r = mujoco.Renderer(mx, H, W)
    img, cam = shot(mx, dx, r, (0.0, 0.0, 0.42), 1.55, 200, -8)
    caption(img, "X-ray: what's inside", "fairings see-through  |  silver = CNC 6061 aluminium  |  dark = printed PLA+ / servos").save(
        out / "ollie-v2-xray.png")
    callouts(img, cam, man["labels"]).save(out / "ollie-v2-callouts.png")
    r.close()
    print("wrote xray + callouts", flush=True)

    for pose, title, look, dist, az in (("skate", "Skate: toes up, balancing on the heel wheels", (0, 0, 0.36), 1.7, 215),
                                        ("crawl", "Crawl: hands and knees, body under 30 cm", None, 1.5, 230)):
        mp, dp, _ = scene(rdir, pose)
        r = mujoco.Renderer(mp, H, W)
        if look is None:
            pts = np.array([dp.geom_xpos[i] for i in range(1, mp.ngeom)])
            look = (float(np.mean(pts[:, 0])), 0.0, 0.17)
        img, _ = shot(mp, dp, r, look, dist, az, -10)
        caption(img, title, sub).save(out / f"ollie-v2-{pose}.png")
        r.close()
        print("wrote", pose, flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
