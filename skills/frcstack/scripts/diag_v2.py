"""v2 diagnosis: time series of walk / crawl -- when and how does it fall, which joints saturate."""
import math
import sys

import mujoco
import numpy as np

import ollie_ctrl as C
import sim_ollie as S

xml = sys.argv[1]
mode = sys.argv[2]
S.load_poses(xml)


def report(sim, t0, nxt, peak_t):
    d = sim.d
    roll, pitch = sim.rpy()
    c = sim.com()
    sat = sorted(n for n, i in sim.act.items()
                 if not n.startswith("wheel") and abs(d.actuator_force[i]) > 0.97 * sim.m.actuator_forcerange[i, 1])
    print(f"t {d.time - t0:5.2f} com {c[0]:+.3f} {c[1]:+.3f} {c[2]:.3f} roll {math.degrees(roll):+6.1f} "
          f"pitch {math.degrees(pitch):+6.1f} sat {sat}")


if mode == "walk":
    sim = C.Sim(xml)
    plan, err = C.walk_plan(sim, steps=6, dt=0.02, step_len=0.06, lift=0.03, t_shift=1.2, t_swing=0.9)
    print("ik err mm", round(err * 1e3, 2), "plan s", plan[-1][0])
    _, q0, _, b0 = plan[0]
    sim.set_pose((b0[0], b0[1], 0.0), (1, 0, 0, 0), q0)
    sim.drop(["sole_L", "sole_R"])
    m, d = sim.m, sim.d
    S.ctrl_targets(sim, q0)
    for _ in range(int(0.6 / m.opt.timestep)):
        mujoco.mj_step(m, d)
    t0, nxt = d.time, 0.0
    while d.time - t0 < plan[-1][0] + 1:
        tt = d.time - t0
        i = min(int(tt / 0.02), len(plan) - 1)
        q = dict(plan[i][1])
        roll, pitch = sim.rpy()
        w = d.qvel[3:6]
        for s in "LR":
            q[f"ankle_pitch_{s}"] += math.degrees(0.8 * pitch + 0.08 * w[1])
            q[f"ankle_roll_{s}"] += math.degrees(0.6 * roll + 0.06 * w[0])
        S.ctrl_targets(sim, q)
        mujoco.mj_step(m, d)
        if tt >= nxt:
            print(f"[{plan[i][2]:>4}]", end=" ")
            report(sim, t0, nxt, 0)
            nxt += 0.25
        if abs(roll) > 0.6 or abs(pitch) > 0.6:
            report(sim, t0, nxt, 0)
            print("FELL")
            break
else:
    sim = C.Sim(xml)
    m, d = sim.m, sim.d
    beta = math.radians(S.CRAWL_PITCH)
    sim.set_pose((1.3, 0, 0.0), np.array([math.cos(beta / 2), 0, math.sin(beta / 2), 0]), S.CRAWL)
    sim.drop(["knee_pad_L", "knee_pad_R", "paw_L", "paw_R"], gap=0.0005)
    lows = {n: sim.lowest([n]) for n in ("knee_pad_L", "knee_pad_R", "paw_L", "paw_R")}
    print("initial lowest", {k: round(v * 1e3, 1) for k, v in lows.items()})
    S.ctrl_targets(sim, S.CRAWL)
    t0, nxt = d.time, 0.0
    while d.time - t0 < 3.0:
        mujoco.mj_step(m, d)
        if d.time - t0 >= nxt:
            report(sim, t0, nxt, 0)
            hits = {mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) for i in range(d.ncon)
                    for g in (d.contact[i].geom1, d.contact[i].geom2)} - {"floor", None}
            print("     contacts", sorted(hits))
            nxt += 0.25
