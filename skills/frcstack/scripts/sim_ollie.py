"""
sim_ollie.py -- MuJoCo demo of OLLIE (sim venv): walk -> skate -> crawl under a table.

Usage:  python sim_ollie.py MODEL_XML OUT_DIR [--no-video] [--only walk|skate|crawl]

Each mode is its own physics run (fresh start) so the video shows the three abilities cleanly; the
JSON log records what the physics actually did: falls, distance, speed, peak joint torque vs stall.
Controllers (model-based, no learned policy yet):
  walk   quasi-static IK plan (COM moved over the stance foot before every lift) + ankle/hip feedback
  skate  LQR on the full model linearised at the toes-up crouch, balancing on the heel wheels
  crawl  hands-and-knees pose, diagonal-pair crawl gait, passes under a 36 cm table
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import mujoco
import numpy as np

import ollie_ctrl as C

FPS = 30
CROUCH = {f"{j}_{s}": v for s in "LR" for j, v in (("hip_pitch", -15.0), ("knee", 30.0), ("ankle_pitch", -15.0))}


def lerp(a, b, t):
    t = min(max(t, 0.0), 1.0)
    t = t * t * (3 - 2 * t)
    return {k: a.get(k, 0.0) * (1 - t) + b.get(k, 0.0) * t for k in set(a) | set(b)}


class Recorder:
    """Streams rendered frames straight to an MP4 (video = output path) so long clips do not fill memory."""

    def __init__(self, sim, video, h=720, w=1280):
        self.sim, self.video = sim, video
        self.n = 0
        if video:
            import imageio.v2 as imageio
            self.r = mujoco.Renderer(sim.m, h, w)
            self.cam = mujoco.MjvCamera()
            self.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
            self.w = imageio.get_writer(str(video), fps=FPS, quality=8, macro_block_size=8)

    def shot(self, lookat, dist=1.5, elev=-10, az=130):
        if not self.video:
            return
        self.cam.lookat[:] = lookat
        self.cam.distance, self.cam.elevation, self.cam.azimuth = dist, elev, az
        self.r.update_scene(self.sim.d, self.cam)
        self.w.append_data(self.r.render())
        self.n += 1

    def close(self):
        if self.video:
            self.w.close()
            self.r.close()
        return self.n


def ctrl_targets(sim, q):
    for n, i in sim.act.items():
        if n in q and not n.startswith("wheel"):
            lo, hi = sim.m.actuator_ctrlrange[i]
            sim.d.ctrl[i] = float(np.clip(math.radians(q[n]), lo, hi))


def track(sim, peak):
    for n, i in sim.act.items():
        peak[n] = max(peak.get(n, 0.0), abs(float(sim.d.actuator_force[i])))


def summarize(sim, name, t0, p0, peak, fell, extra=None):
    p1 = sim.com()
    st = {n: v for n, v in peak.items() if not n.startswith("wheel")}
    worst = max(st, key=st.get)
    out = {"duration_s": round(sim.d.time - t0, 2), "fell": fell,
           "distance_m": round(float(np.hypot(p1[0] - p0[0], p1[1] - p0[1])), 3),
           "avg_speed_mps": round(float(np.hypot(p1[0] - p0[0], p1[1] - p0[1]) / max(sim.d.time - t0, 1e-6)), 3),
           "worst_joint": worst, "worst_joint_peak_nm": round(st[worst], 3),
           "worst_frac_of_force_limit": round(st[worst] / sim.m.actuator_forcerange[sim.act[worst], 1], 3)}
    out.update(extra or {})
    return out


# --------------------------------------------------------------------------- walk
def run_walk(xml, rec_video, steps=6, step_len=0.06):
    sim = C.Sim(xml)
    plan, ik_err = C.walk_plan(sim, steps=steps, dt=0.02, step_len=step_len, lift=0.03, t_shift=1.2, t_swing=0.9)
    _, q0, _, b0 = plan[0]
    sim.set_pose((b0[0], b0[1], 0.0), (1, 0, 0, 0), q0)
    sim.drop(["sole_L", "sole_R"])
    rec = Recorder(sim, rec_video)
    m, d = sim.m, sim.d
    ctrl_targets(sim, q0)
    for _ in range(int(0.6 / m.opt.timestep)):
        mujoco.mj_step(m, d)
    t0, p0, peak, fell = d.time, sim.com(), {}, False
    T = plan[-1][0] + 1.0
    k = 0
    while d.time - t0 < T:
        tt = d.time - t0
        i = min(int(tt / 0.02), len(plan) - 1)
        q = dict(plan[i][1])
        roll, pitch = sim.rpy()
        w = d.qvel[3:6]
        for s in "LR":                                     # ankle strategy: keep the torso upright
            q[f"ankle_pitch_{s}"] += math.degrees(0.8 * pitch + 0.08 * w[1])
            q[f"ankle_roll_{s}"] += math.degrees(0.6 * roll + 0.06 * w[0])
        ctrl_targets(sim, q)
        mujoco.mj_step(m, d)
        track(sim, peak)
        if abs(roll) > 0.6 or abs(pitch) > 0.6 or sim.com()[2] < 0.25:
            fell = True
        if k % int(1 / (FPS * m.opt.timestep)) == 0:
            c = sim.com()
            rec.shot((c[0], c[1], 0.36), dist=1.55, elev=-8, az=125)
        k += 1
    return summarize(sim, "walk", t0, p0, peak, fell, {"steps": steps, "step_len_m": step_len,
                                                       "ik_max_err_mm": round(ik_err * 1e3, 3)}), rec.close()


# --------------------------------------------------------------------------- skate
SKATE = {f"{j}_{s}": v for s in "LR" for j, v in (("hip_pitch", -35.25), ("knee", 40.0), ("ankle_pitch", -19.75))}


def skate_setup(sim):
    """Toes-up crouch resting on the heel wheels with the COM over the axles.  Returns (pitch0, qref, ctrl0)."""
    m, d = sim.m, sim.d
    q = dict(SKATE, gripper_L=0.0, gripper_R=0.0)
    best = None
    for pitch in np.linspace(-0.3, 0.3, 601):
        quat = np.array([math.cos(pitch / 2), 0, math.sin(pitch / 2), 0])
        sim.set_pose((0, 0, 0.0), quat, q)
        sim.drop(["tire_L", "tire_R"], gap=0.0)
        wx = np.mean([d.geom_xpos[sim.gid(f"tire_{s}")][0] for s in "LR"])
        err = abs(sim.com()[0] - wx)
        if best is None or err < best[0]:
            best = (err, pitch)
    p0 = best[1]
    quat = np.array([math.cos(p0 / 2), 0, math.sin(p0 / 2), 0])
    sim.set_pose((0, 0, 0.0), quat, q)
    sim.drop(["tire_L", "tire_R"], gap=0.0)
    ctrl0 = np.zeros(m.nu)
    for n, i in sim.act.items():
        if not n.startswith("wheel"):
            ctrl0[i] = d.qpos[sim.qadr[n]]
    return p0, d.qpos.copy(), ctrl0


# found by diag_skate_long.py: 60 s runs with speed-ups, stop and reverse, up to 0.30 m/s, plus a 120 s run
SKATE_GAINS = dict(k_th=12.0, k_dth=0.3, k_v=0.4, k_vi=0.5, k_x=0.0, a_max=0.05)
SKATE_V_MAX = 0.30            # 0.35 m/s falls: the N20s run out of spare torque for balance


def skate_step(sim, p0, ctrl0, v_cmd, g, x_ref=None, state=None):
    """Inverted-pendulum balance on the heel wheels: wheel torque from lean, lean rate, speed error and its
    integral (the integral finds the true balance lean, so commanded speed is held without drift)."""
    m, d = sim.m, sim.d
    _, pitch = sim.rpy()
    th = pitch - p0
    dth = d.qvel[4]
    vx = d.qvel[0]
    v_cmd = float(np.clip(v_cmd, -SKATE_V_MAX, SKATE_V_MAX))
    if state is not None and g.get("a_max"):
        # ramp the speed command: the N20s have little spare torque, a step in speed tips OLLIE over
        vr = state.get("v_ref", 0.0)
        step = g["a_max"] * m.opt.timestep
        state["v_ref"] = vr + float(np.clip(v_cmd - vr, -step, step))
        v_cmd = state["v_ref"]
    ev = vx - v_cmd
    if state is not None:
        state["iv"] = float(np.clip(state.get("iv", 0.0) + ev * m.opt.timestep, -0.5, 0.5))
    tau = g["k_th"] * th + g["k_dth"] * dth + g["k_v"] * ev + g.get("k_vi", 0.0) * (state or {}).get("iv", 0.0)
    if x_ref is not None:
        tau += g["k_x"] * (d.qpos[0] - x_ref)
    d.ctrl[:] = ctrl0
    for s in "LR":
        i = sim.act[f"wheel_{s}"]
        stall = m.actuator_gainprm[i, 0]
        w = d.qvel[sim.vadr[f"wheel_{s}"]]
        duty = (tau - m.actuator_biasprm[i, 2] * w) / stall      # feed-forward the back-EMF
        d.ctrl[i] = float(np.clip(duty, -1.0, 1.0))
    return th


def run_skate(xml, rec_video, seconds=12.0, cruise=0.30, gains=None):
    """Leg servos hold the toes-up crouch; the two N20 heel motors balance the robot like a Segway."""
    sim = C.Sim(xml)
    m, d = sim.m, sim.d
    p0, qref, ctrl0 = skate_setup(sim)
    clearance0 = sim.lowest(["sole_L", "sole_R"])
    g = dict(SKATE_GAINS, **(gains or {}))
    rec = Recorder(sim, rec_video)
    t0, p0c, peak, fell, toe, th_max = d.time, sim.com(), {}, False, 0.0, 0.0
    st = {}
    vmax = 0.0
    k = 0
    while d.time - t0 < seconds:
        tt = d.time - t0
        v_cmd = cruise if tt < seconds - 5.0 else 0.0
        th = skate_step(sim, p0, ctrl0, v_cmd, g, state=st)
        mujoco.mj_step(m, d)
        vmax = max(vmax, d.qvel[0])
        track(sim, peak)
        th_max = max(th_max, abs(th))
        if sim.lowest(["sole_L", "sole_R"]) < 0.0008:
            toe += m.opt.timestep
        if abs(th) > 0.6 or sim.com()[2] < 0.2:
            fell = True
        if k % int(1 / (FPS * m.opt.timestep)) == 0:
            c = sim.com()
            rec.shot((c[0], c[1], 0.34), dist=1.7, elev=-8, az=110)
        k += 1
    return summarize(sim, "skate", t0, p0c, peak, fell, {
        "balance_pitch_deg": round(math.degrees(p0), 2), "toe_clearance_at_balance_mm": round(clearance0 * 1e3, 1),
        "cruise_cmd_mps": cruise, "peak_speed_mps": round(vmax, 3), "toe_touch_s": round(toe, 2),
        "max_lean_deg": round(math.degrees(th_max), 1),
        "wheel_peak_nm": round(max(peak.get("wheel_L", 0), peak.get("wheel_R", 0)), 3), "gains": g}), rec.close()


def _lqr_skate_unused(xml, rec_video, seconds=8.0, cruise=0.30, weights=None):
    """Joints held at the toes-up crouch by their servos; the two heel-wheel motors balance the robot
    (wheel-only LQR on the full linearised model = a two-wheeled inverted pendulum)."""
    sim = C.Sim(xml)
    m, d = sim.m, sim.d
    q = dict(SKATE, gripper_L=0.0, gripper_R=0.0)
    best = None
    for pitch in np.linspace(-0.3, 0.3, 601):
        quat = np.array([math.cos(pitch / 2), 0, math.sin(pitch / 2), 0])
        sim.set_pose((0, 0, 0.0), quat, q)
        sim.drop(["tire_L", "tire_R"], gap=0.0)
        wx = np.mean([d.geom_xpos[sim.gid(f"tire_{s}")][0] for s in "LR"])
        err = abs(sim.com()[0] - wx)
        if best is None or err < best[0]:
            best = (err, pitch)
    pitch0 = best[1]
    quat = np.array([math.cos(pitch0 / 2), 0, math.sin(pitch0 / 2), 0])
    sim.set_pose((0, 0, 0.0), quat, q)
    sim.drop(["tire_L", "tire_R"], gap=0.0)
    clearance0 = sim.lowest(["sole_L", "sole_R"])
    qref = d.qpos.copy()
    ctrl0 = np.zeros(m.nu)
    for n, i in sim.act.items():
        if not n.startswith("wheel"):
            ctrl0[i] = d.qpos[sim.qadr[n]]
    w = dict(q_base=(1e-3, 1e-3, 1, 30, 400, 30), q_joint=1.0, q_wheel=1e-3, q_vel=0.2, r_act=1.0, r_wheel=0.05)
    w.update(weights or {})
    K, idx = C.lqr_gain(sim, ctrl0, inputs=["wheel_L", "wheel_R"], **w)
    rec = Recorder(sim, rec_video)
    t0, p0, peak, fell, toe = d.time, sim.com(), {}, False, 0.0
    wadr = [sim.qadr[f"wheel_{s}"] for s in "LR"]
    lo, hi = m.actuator_ctrlrange[idx, 0], m.actuator_ctrlrange[idx, 1]
    k = 0
    while d.time - t0 < seconds:
        tt = d.time - t0
        v_cmd = cruise * min(1.0, tt / 2.0) * (1.0 if tt < seconds - 1.8 else max(0.0, (seconds - tt) / 1.8))
        ref = qref.copy()
        ref[0], ref[1] = d.qpos[0], d.qpos[1]
        for a in wadr:
            ref[a] = d.qpos[a]
        x = C.state_error(sim, ref)
        x[m.nv + 0] -= v_cmd
        for s in "LR":
            x[m.nv + sim.vadr[f"wheel_{s}"]] -= v_cmd / OLW_R
        u = np.clip(-K @ x + v_cmd / OLW_R, lo, hi)
        d.ctrl[:] = ctrl0
        d.ctrl[idx] = u
        mujoco.mj_step(m, d)
        track(sim, peak)
        _, pitch = sim.rpy()
        if sim.lowest(["sole_L", "sole_R"]) < 0.0005:
            toe += m.opt.timestep
        if abs(pitch - pitch0) > 0.6 or sim.com()[2] < 0.2:
            fell = True
        if k % int(1 / (FPS * m.opt.timestep)) == 0:
            c = sim.com()
            rec.shot((c[0], c[1], 0.34), dist=1.7, elev=-8, az=110)
        k += 1
    vmax = float(np.mean([abs(d.qvel[sim.vadr[f"wheel_{s}"]]) for s in "LR"]) * OLW_R)
    return summarize(sim, "skate", t0, p0, peak, fell, {
        "balance_pitch_deg": round(math.degrees(pitch0), 2), "toe_clearance_at_balance_mm": round(clearance0 * 1e3, 1),
        "cruise_cmd_mps": cruise, "toe_touch_s": round(toe, 2), "final_wheel_surface_speed_mps": round(vmax, 3),
        "wheel_peak_nm": round(max(peak.get("wheel_L", 0), peak.get("wheel_R", 0)), 3)}), rec.frames


OLW_R = 0.022


def _unused_skate(xml, rec_video, seconds=8.0, cruise=0.30):
    sim = C.Sim(xml)
    m, d = sim.m, sim.d
    q = dict(SKATE, gripper_L=0.0, gripper_R=0.0)
    sim.set_pose((0, 0, 0.0), (1, 0, 0, 0), q)
    # tilt the whole robot so it rests on the heel wheels (foot toes-up 15 deg), then find the balance pitch
    best = None
    for pitch in np.linspace(-0.6, 0.6, 241):
        quat = np.array([math.cos(pitch / 2), 0, math.sin(pitch / 2), 0])
        sim.set_pose((0, 0, 0.0), quat, q)
        sim.drop(["tire_L", "tire_R"], gap=0.0)
        if sim.lowest(["sole_L", "sole_R"]) < 0.004:
            continue
        wx = np.mean([d.geom_xpos[sim.gid(f"tire_{s}")][0] for s in "LR"])
        err = abs(sim.com()[0] - wx)
        if best is None or err < best[0]:
            best = (err, pitch)
    pitch0 = best[1]
    quat = np.array([math.cos(pitch0 / 2), 0, math.sin(pitch0 / 2), 0])
    sim.set_pose((0, 0, 0.0), quat, q)
    sim.drop(["tire_L", "tire_R"], gap=0.0)
    mujoco.mj_forward(m, d)
    qref = d.qpos.copy()
    ctrl0, _ = C.equilibrium_ctrl(sim, q)
    K = C.lqr_gain(sim, ctrl0, q_base=(1, 1, 50, 200, 500, 50), q_joint=8.0, q_wheel=0.05, q_vel=0.3,
                   r_act=2.0, r_wheel=0.05)
    rec = Recorder(sim, rec_video)
    t0, p0, peak, fell = d.time, sim.com(), {}, False
    wid = [sim.act[f"wheel_{s}"] for s in "LR"]
    wadr = [sim.qadr[f"wheel_{s}"] for s in "LR"]
    k = 0
    while d.time - t0 < seconds:
        tt = d.time - t0
        v_cmd = cruise * min(1.0, tt / 2.0) * (1.0 if tt < seconds - 1.8 else max(0.0, (seconds - tt) / 1.8))
        ref = qref.copy()
        ref[0] = d.qpos[0]                                   # free to travel along x
        ref[1] = qref[1]
        for a in wadr:
            ref[a] = d.qpos[a]                               # wheel angle is free
        x = C.state_error(sim, ref)
        x[m.nv + 0] -= v_cmd                                 # track forward speed
        for s, a in zip("LR", wadr):
            x[m.nv + sim.vadr[f"wheel_{s}"]] -= v_cmd / (0.022)
        u = ctrl0 - K @ x
        lo, hi = m.actuator_ctrlrange[:, 0], m.actuator_ctrlrange[:, 1]
        d.ctrl[:] = np.clip(u, lo, hi)
        mujoco.mj_step(m, d)
        track(sim, peak)
        _, pitch = sim.rpy()
        if abs(pitch - pitch0) > 0.5 or sim.lowest(["sole_L", "sole_R"]) < -0.002 or sim.com()[2] < 0.2:
            fell = True
        if k % int(1 / (FPS * m.opt.timestep)) == 0:
            c = sim.com()
            rec.shot((c[0], c[1], 0.34), dist=1.7, elev=-8, az=110)
        k += 1
    vmax = float(max(abs(d.qvel[sim.vadr[f"wheel_{s}"]]) for s in "LR") * 0.022)
    return summarize(sim, "skate", t0, p0, peak, fell, {"balance_pitch_deg": round(math.degrees(pitch0), 1),
                                                         "cruise_cmd_mps": cruise, "final_wheel_speed_mps": round(vmax, 3)}), rec.frames


# --------------------------------------------------------------------------- crawl
CRAWL = {**{f"{j}_{s}": v for s in "LR" for j, v in (("hip_pitch", -61.5), ("knee", 102.5), ("ankle_pitch", 30.0),
                                                       ("shoulder", -69.0), ("elbow", 0.0), ("gripper", 28.0))},
         "neck_tilt": -45.0}


CRAWL_GAIT = dict(period=1.0, hip=14.0, knee=8.0, shoulder=16.0, elbow=12.0)   # found by diag_crawl.py sweep


def run_crawl(xml, rec_video, seconds=18.0, gait=None, start_x=1.30):
    sim = C.Sim(xml)
    m, d = sim.m, sim.d
    gt = dict(CRAWL_GAIT, **(gait or {}))
    beta = math.radians(69.0)
    quat = np.array([math.cos(beta / 2), 0, math.sin(beta / 2), 0])
    sim.set_pose((start_x, 0, 0.0), quat, CRAWL)
    sim.drop(["knee_pad_L", "knee_pad_R", "paw_L", "paw_R"], gap=0.0005)
    ctrl_targets(sim, CRAWL)
    for _ in range(int(0.8 / m.opt.timestep)):
        mujoco.mj_step(m, d)
    rec = Recorder(sim, rec_video)
    t0, p0, peak, fell = d.time, sim.com(), {}, False
    period = gt["period"]
    max_top = 0.0
    k = 0
    table_hit = False
    tb = [sim.gid(n) for n in ("table_top",)]
    while d.time - t0 < seconds:
        tt = d.time - t0
        ph = 2 * math.pi * tt / period
        amp = min(1.0, tt / 1.0)
        a, b = math.sin(ph), math.sin(ph + math.pi)
        q = dict(CRAWL)
        # diagonal pairs: left knee + right paw, then right knee + left paw; lift on the forward half
        q["hip_pitch_L"] += amp * gt["hip"] * a
        q["hip_pitch_R"] += amp * gt["hip"] * b
        q["knee_L"] -= amp * gt["knee"] * max(0.0, math.cos(ph))
        q["knee_R"] -= amp * gt["knee"] * max(0.0, math.cos(ph + math.pi))
        q["shoulder_L"] -= amp * gt["shoulder"] * b
        q["shoulder_R"] -= amp * gt["shoulder"] * a
        q["elbow_L"] -= amp * gt["elbow"] * max(0.0, math.cos(ph + math.pi))
        q["elbow_R"] -= amp * gt["elbow"] * max(0.0, math.cos(ph))
        roll, pitch = sim.rpy()
        q["hip_roll_L"] = q.get("hip_roll_L", 0.0) - math.degrees(0.4 * roll)
        q["hip_roll_R"] = q.get("hip_roll_R", 0.0) - math.degrees(0.4 * roll)
        ctrl_targets(sim, q)
        mujoco.mj_step(m, d)
        track(sim, peak)
        for i in range(d.ncon):
            c = d.contact[i]
            if c.geom1 in tb or c.geom2 in tb:
                table_hit = True
        top = max(d.geom_xpos[g][2] for g in range(m.ngeom) if m.geom_bodyid[g] > 0)
        max_top = max(max_top, top)
        if abs(roll) > 0.8:
            fell = True
        if k % int(1 / (FPS * m.opt.timestep)) == 0:
            c = sim.com()
            rec.shot((c[0], c[1], 0.2), dist=1.5, elev=-6, az=100)
        k += 1
    x_end = sim.com()[0]
    under = [g for g in range(m.ngeom) if m.geom_bodyid[g] > 0]
    return summarize(sim, "crawl", t0, p0, peak, fell, {
        "start_x_m": round(float(p0[0]), 3), "end_x_m": round(float(x_end), 3),
        "passed_under_table": bool(x_end > 1.9 and not table_hit), "touched_table": table_hit,
        "max_body_height_m": round(float(max_top), 3), "table_underside_m": 0.345, "gait": gt}), rec.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xml")
    ap.add_argument("out_dir")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--only")
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runs = {"walk": run_walk, "skate": run_skate, "crawl": run_crawl}
    log = {}
    for name, fn in runs.items():
        if a.only and a.only != name:
            continue
        res, nframes = fn(a.xml, None if a.no_video else out / f"clip_{name}.mp4")
        res["video_frames"] = nframes
        log[name] = res
        print(name, json.dumps(res), flush=True)
    (out / ("sim-log.json" if not a.only else f"sim-log-{a.only}.json")).write_text(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
