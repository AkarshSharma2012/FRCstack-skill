"""Crawl v2: forward progress and heading over time (does it turn?)."""
import math
import sys

import mujoco
import numpy as np

import ollie_ctrl as C
import sim_ollie as S

xml = sys.argv[1]
S.load_poses(xml)
k_yaw = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
sim = C.Sim(xml)
m, d = sim.m, sim.d
b = math.radians(S.CRAWL_PITCH)
sim.set_pose((1.2, 0, 0.0), np.array([math.cos(b / 2), 0, math.sin(b / 2), 0]), S.CRAWL)
sim.drop(["knee_pad_L", "knee_pad_R", "paw_L", "paw_R"], gap=0.0005)
S.ctrl_targets(sim, S.CRAWL)
for _ in range(int(0.8 / m.opt.timestep)):
    mujoco.mj_step(m, d)
t0, x0, nxt = d.time, sim.com()[0], 0.0
while d.time - t0 < 24:
    tt = d.time - t0
    q = S.crawl_targets(S.CRAWL_GAIT, tt)
    st = S.side_tilt(sim)
    q["hip_roll_L"] = q["hip_roll_R"] = math.degrees(0.4 * st)
    R = d.xmat[sim.base].reshape(3, 3)
    head = math.atan2(R[1, 2], R[0, 2])          # body z axis points forward when crawling
    if k_yaw:
        q["hip_yaw_L"] = q["hip_yaw_R"] = math.degrees(float(np.clip(k_yaw * head, -0.4, 0.4)))
    S.ctrl_targets(sim, q)
    mujoco.mj_step(m, d)
    if tt >= nxt:
        c = sim.com()
        print(f"t {tt:5.1f} dx {c[0] - x0:+.3f} y {c[1]:+.3f} heading {math.degrees(head):+7.1f} tilt {math.degrees(st):+5.1f}")
        nxt += 2.0
