"""Skate gain sweep with a ramped speed command: 60 s profile with speed-ups, stop, reverse.
Target: never falls at up to vmax, toes never touch."""
import itertools
import math
import sys

import mujoco

import ollie_ctrl as C
import sim_ollie as S

PROFILE = [(0, 1.0), (10, 0.5), (18, 0.0), (26, -0.5), (34, 1.0), (44, 0.0), (52, 1.0)]


def profile(t, vmax):
    v = 0.0
    for t0, f in PROFILE:
        if t >= t0:
            v = f * vmax
    return v


def run(xml, g, T=60.0, vmax=0.25):
    sim = C.Sim(xml)
    p0, _, ctrl0 = S.skate_setup(sim)
    sim.d.time = 0.0
    st, m, d = {}, sim.m, sim.d
    err, n, thm, toe = 0.0, 0, 0.0, 0.0
    while d.time < T:
        t = d.time
        v = profile(t, vmax)
        th = S.skate_step(sim, p0, ctrl0, v, g, state=st)
        mujoco.mj_step(m, d)
        thm = max(thm, abs(th))
        if sim.lowest(["sole_L", "sole_R"]) < 0.0008:
            toe += m.opt.timestep
        if abs(th) > 0.5 or sim.com()[2] < 0.2:
            return False, round(t, 1), 0.0, 0.0, 0.0
        err += abs(d.qvel[0] - st.get("v_ref", v))
        n += 1
    return True, T, round(float(err / n), 3), round(math.degrees(thm), 1), round(toe, 2)


def main(xml):
    rows = []
    vmax = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
    for kth, kd, kv, kvi, am in itertools.product((12, 16, 20), (0.3,), (0.2, 0.3, 0.4), (0.2, 0.3, 0.5),
                                                  (0.05, 0.1)):
        g = dict(k_th=kth, k_dth=kd, k_v=kv, k_vi=kvi, k_x=0.0, a_max=am)
        r = run(xml, g, vmax=vmax)
        rows.append((r, g))
        print(r, g, flush=True)
    ok = sorted([x for x in rows if x[0][0]], key=lambda x: x[0][2])
    print("BEST")
    for r, g in ok[:6]:
        print(r, g)


if __name__ == "__main__":
    main(sys.argv[1])
