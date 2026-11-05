"""Crawl v2 forward-gait search: signed forward progress along the heading, stability, low profile."""
import itertools
import math
import sys

import mujoco
import numpy as np

import ollie_ctrl as C
import sim_ollie as S

xml, part = sys.argv[1], int(sys.argv[2])
S.load_poses(xml)


def run(g, T=10.0):
    sim = C.Sim(xml)
    m, d = sim.m, sim.d
    b = math.radians(S.CRAWL_PITCH)
    sim.set_pose((0.0, 0, 0.0), np.array([math.cos(b / 2), 0, math.sin(b / 2), 0]), S.CRAWL)
    sim.drop(["knee_pad_L", "knee_pad_R", "paw_L", "paw_R"], gap=0.0005)
    S.ctrl_targets(sim, S.CRAWL)
    for _ in range(int(0.8 / m.opt.timestep)):
        mujoco.mj_step(m, d)
    t0, c0, tilt = d.time, sim.com().copy(), 0.0
    while d.time - t0 < T:
        q = S.crawl_targets(g, d.time - t0)
        st = S.side_tilt(sim)
        q["hip_roll_L"] = q["hip_roll_R"] = math.degrees(0.4 * st)
        S.ctrl_targets(sim, q)
        mujoco.mj_step(m, d)
        tilt = max(tilt, abs(math.degrees(st)))
        if tilt > 25 or sim.com()[2] < 0.07:
            return False, round(float(sim.com()[0] - c0[0]), 3), round(tilt, 1)
    return True, round(float(sim.com()[0] - c0[0]), 3), round(tilt, 1)


grid = list(itertools.product((1.0, 1.4), (14.0, 22.0, -14.0, -22.0), (12.0, 20.0), (16.0, -16.0, 24.0, -24.0),
                              (12.0,)))[part::2]
for per, hip, kn, sh, el in grid:
    g = dict(period=per, hip=hip, knee=kn, sh=sh, el=el)
    print(run(g), g, flush=True)
