"""Walk diagnostic: per-0.25 s trace of COM vs stance foot, roll/pitch, contacts and saturated joints."""
import math
import sys

import mujoco
import numpy as np

import ollie_ctrl as C
import sim_ollie as S


def main(xml, fb=1.0, lift=0.03, ts=1.2, tw=1.1):
    sim = C.Sim(xml)
    plan, err = C.walk_plan(sim, steps=4, dt=0.02, step_len=0.05, lift=lift, t_shift=ts, t_swing=tw)
    _, q0, _, b0 = plan[0]
    sim.set_pose((b0[0], b0[1], 0.0), (1, 0, 0, 0), q0)
    sim.drop(["sole_L", "sole_R"])
    m, d = sim.m, sim.d
    S.ctrl_targets(sim, q0)
    for _ in range(300):
        mujoco.mj_step(m, d)
    gn = lambda g: mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g)  # noqa: E731
    t0 = d.time
    k = 0
    while d.time - t0 < plan[-1][0] + 1:
        tt = d.time - t0
        i = min(int(tt / 0.02), len(plan) - 1)
        q = dict(plan[i][1])
        roll, pitch = sim.rpy()
        w = d.qvel[3:6]
        for s in "LR":
            q[f"ankle_pitch_{s}"] += fb * math.degrees(0.8 * pitch + 0.08 * w[1])
            q[f"ankle_roll_{s}"] += fb * math.degrees(0.6 * roll + 0.06 * w[0])
        S.ctrl_targets(sim, q)
        mujoco.mj_step(m, d)
        if k % 250 == 0:
            cons = sorted({gn(c.geom1) if gn(c.geom1) != "floor" else gn(c.geom2) for c in d.contact[:d.ncon]})
            sat = [n for n, a in sim.act.items() if abs(d.actuator_force[a]) > 0.98 * m.actuator_forcerange[a, 1]]
            c = sim.com()
            print(f"t {tt:5.2f} plan {plan[i][2]:4s} com ({c[0]:.3f},{c[1]:.3f},{c[2]:.3f}) planbase ({plan[i][3][0]:.3f},"
                  f"{plan[i][3][1]:.3f}) base ({d.qpos[0]:.3f},{d.qpos[1]:.3f}) r {math.degrees(roll):5.1f} "
                  f"p {math.degrees(pitch):5.1f} {cons} sat {sat}")
        k += 1


if __name__ == "__main__":
    a = [float(v) for v in sys.argv[2:]]
    main(sys.argv[1], *a)
