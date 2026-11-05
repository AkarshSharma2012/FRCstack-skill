"""
live_ollie.py -- interactive, real-time MuJoCo window for OLLIE (sim venv).

Usage:  python live_ollie.py [MODEL_XML] [--mode walk|skate|crawl] [--close-after S] [--headless S]

Keys (click the 3D view first):
  1 walk    2 skate    3 crawl    A auto-tour (walk -> skate -> crawl, loops)
  R restart mode    P pause    F camera follow on/off
  UP / DOWN  skate speed +/- 0.1 m/s (skate mode)
Mouse: drag to orbit, right-drag to pan, scroll to zoom.
Push OLLIE: double-click a body part, then Ctrl + right-drag to shove it.

Uses the same controllers as sim_ollie.py (same physics as the demo video).
"""
from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import mujoco
import numpy as np

import ollie_ctrl as C
import sim_ollie as S

HERE = Path(__file__).resolve().parent
DEFAULT_XML = HERE.parents[2] / ".frcstack" / "out" / "ollie-sim-v2" / "ollie.xml"
MODES = ("walk", "skate", "crawl")
TOUR_S = {"walk": 30.0, "skate": 12.0, "crawl": 22.0}
KEY = {49: "walk", 50: "skate", 51: "crawl"}
K_R, K_P, K_F, K_A, K_UP, K_DOWN = 82, 80, 70, 65, 265, 264


class Walk:
    name, cam = "walk", dict(z=0.36, dist=1.55, elev=-8, az=125)

    def __init__(self, sim):
        import hashlib
        import pickle
        key = hashlib.md5(Path(sim.xml).read_bytes() + b"walk12-0.07-0.03-1.6-0.9").hexdigest()[:10]
        cache = Path(sim.xml).with_name(f"walk_plan_{key}.pkl")
        if cache.exists():
            self.plan = pickle.loads(cache.read_bytes())
            return
        print("planning walk (first run only, ~30 s) ...", flush=True)
        self.plan, _ = C.walk_plan(sim, steps=12, dt=0.02, step_len=0.07, lift=0.03, t_shift=1.6, t_swing=0.9)
        cache.write_bytes(pickle.dumps(self.plan))

    def reset(self, sim):
        _, q0, _, b0 = self.plan[0]
        sim.set_pose((b0[0], b0[1], 0.0), (1, 0, 0, 0), q0)
        sim.drop(["sole_L", "sole_R"])
        S.ctrl_targets(sim, q0)
        self.settle = 0.6
        self.t0 = None

    def step(self, sim):
        d = sim.d
        if d.time < self.settle:
            return "settling"
        if self.t0 is None:
            self.t0 = d.time
        tt = d.time - self.t0
        i = min(int(tt / 0.02), len(self.plan) - 1)
        q = dict(self.plan[i][1])
        roll, pitch = sim.rpy()
        w = d.qvel[3:6]
        for s in "LR":
            q[f"ankle_pitch_{s}"] += math.degrees(0.8 * pitch + 0.08 * w[1])
            q[f"ankle_roll_{s}"] += math.degrees(0.6 * roll + 0.06 * w[0])
        S.ctrl_targets(sim, q)
        return "walking" if i < len(self.plan) - 1 else "done, standing"


class Skate:
    name, cam = "skate", dict(z=0.34, dist=1.7, elev=-8, az=110)
    v_set = 0.30

    def __init__(self, sim):
        pass

    def reset(self, sim):
        self.p0, _, self.ctrl0 = S.skate_setup(sim)
        sim.d.time = 0.0
        self.st = {}

    def step(self, sim):
        S.skate_step(sim, self.p0, self.ctrl0, self.v_set, S.SKATE_GAINS, state=self.st)
        return f"speed target {self.st.get('v_ref', 0.0):+.2f} m/s"


class Crawl:
    name, cam = "crawl", dict(z=0.2, dist=1.5, elev=-6, az=100)

    def __init__(self, sim):
        self.gt = dict(S.CRAWL_GAIT)

    def reset(self, sim):
        beta = math.radians(S.CRAWL_PITCH)
        quat = np.array([math.cos(beta / 2), 0, math.sin(beta / 2), 0])
        sim.set_pose((1.30, 0, 0.0), quat, S.CRAWL)
        sim.drop(["knee_pad_L", "knee_pad_R", "paw_L", "paw_R"], gap=0.0005)
        S.ctrl_targets(sim, S.CRAWL)
        self.settle = 0.8
        self.t0 = None
        self.table = sim.gid("table_top")
        self.hit = False

    def step(self, sim):
        d = sim.d
        if d.time < self.settle:
            return "settling"
        if self.t0 is None:
            self.t0 = d.time
        gt, tt = self.gt, d.time - self.t0
        q = S.crawl_targets(gt, tt)
        st = S.side_tilt(sim)
        q["hip_roll_L"] = q["hip_roll_R"] = math.degrees(0.4 * st)
        S.ctrl_targets(sim, q)
        for i in range(d.ncon):
            c = d.contact[i]
            if self.table in (c.geom1, c.geom2):
                self.hit = True
        where = "under the table" if 1.5 < sim.com()[0] < 2.3 else ("past the table" if sim.com()[0] >= 2.3 else "")
        return ("TOUCHED TABLE  " if self.hit else "") + where


class Live:
    def __init__(self, xml):
        self.sim = C.Sim(str(xml))
        self.sim.xml = str(xml)
        S.load_poses(xml)
        self.ctl = {"walk": Walk(self.sim), "skate": Skate(self.sim), "crawl": Crawl(self.sim)}
        self.mode, self.pending, self.paused, self.follow, self.tour = "walk", None, False, True, False

    def start(self, mode):
        m, d = self.sim.m, self.sim.d
        mujoco.mj_resetData(m, d)
        self.mode = mode
        self.ctl[mode].reset(self.sim)
        d.time = 0.0
        self.p0 = self.sim.com()
        self.peak = {}
        self.fell = False
        self.status = ""

    def key(self, k):
        if k in KEY:
            self.tour, self.pending = False, KEY[k]
        elif k == K_A:
            self.tour, self.pending = True, "walk"
        elif k == K_R:
            self.pending = self.mode
        elif k == K_P:
            self.paused = not self.paused
        elif k == K_F:
            self.follow = not self.follow
        elif k in (K_UP, K_DOWN):
            Skate.v_set = round(float(np.clip(Skate.v_set + (0.1 if k == K_UP else -0.1), -S.SKATE_V_MAX,
                                              S.SKATE_V_MAX)), 2)

    def advance(self, dt_wall):
        """Step physics by dt_wall seconds of sim time."""
        sim = self.sim
        m, d = sim.m, sim.d
        n = int(dt_wall / m.opt.timestep)
        if n <= 0:
            return
        for _ in range(n):
            self.status = self.ctl[self.mode].step(sim)
            mujoco.mj_step(m, d)
        S.track(sim, self.peak)
        roll, pitch = sim.rpy()
        if self.mode == "walk" and (abs(roll) > 0.6 or abs(pitch) > 0.6 or sim.com()[2] < 0.25):
            self.fell = True
        if self.mode == "skate" and (sim.com()[2] < 0.2 or abs(pitch - self.ctl["skate"].p0) > 0.5):
            self.fell = True
        if self.mode == "crawl" and (abs(S.side_tilt(sim)) > math.radians(25) or sim.com()[2] < 0.08):
            self.fell = True
        if self.tour and d.time > TOUR_S[self.mode]:
            self.pending = MODES[(MODES.index(self.mode) + 1) % 3]

    def hud(self):
        sim = self.sim
        c = sim.com()
        dist = float(np.hypot(c[0] - self.p0[0], c[1] - self.p0[1]))
        st = {n: v for n, v in self.peak.items() if not n.startswith("wheel")}
        lim = sim.m.actuator_forcerange
        worst = max(st, key=lambda n: st[n] / lim[sim.act[n], 1]) if st else None
        load = f"{worst} {100 * st[worst] / lim[sim.act[worst], 1]:.0f}% of stall" if worst else "-"
        roll, pitch = sim.rpy()
        left = "\n".join(["OLLIE live", "mode", "time", "distance", "speed", "tilt (roll/pitch)", "peak servo load",
                          "status", "", "keys"])
        right = "\n".join([
            "MuJoCo physics" + ("   PAUSED" if self.paused else "") + ("   auto-tour" if self.tour else ""),
            self.mode.upper() + (f"  (set {Skate.v_set:+.1f} m/s)" if self.mode == "skate" else ""),
            f"{sim.d.time:5.1f} s", f"{dist:.2f} m", f"{abs(sim.d.qvel[0]):.2f} m/s",
            f"{math.degrees(roll):+.1f} / {math.degrees(pitch):+.1f} deg", load,
            ("FELL  " if self.fell else "") + (self.status or ""), "",
            "1 walk 2 skate 3 crawl A tour R restart P pause F follow UP/DN speed"])
        return left, right


def run_viewer(live, close_after=None):
    import mujoco.viewer
    sim = live.sim
    live.start(live.mode)
    with mujoco.viewer.launch_passive(sim.m, sim.d, key_callback=live.key) as v:
        print("window open", flush=True)
        v.cam.distance, v.cam.elevation, v.cam.azimuth = 1.6, -10, 125
        t_open = time.perf_counter()
        lag = 0.0                 # sim seconds still owed to the wall clock
        last = time.perf_counter()
        while v.is_running():
            now = time.perf_counter()
            lag = min(lag + (now - last), 0.15)   # if the PC is too slow, slow down rather than spiral
            last = now
            with v.lock():
                if live.pending:
                    live.start(live.pending)
                    live.pending = None
                    lag = 0.0
                    cm = live.ctl[live.mode].cam
                    v.cam.distance, v.cam.elevation, v.cam.azimuth = cm["dist"], cm["elev"], cm["az"]
                if not live.paused and lag > 0:
                    t_before = sim.d.time
                    live.advance(lag)
                    lag -= sim.d.time - t_before
                elif live.paused:
                    lag = 0.0
                if live.follow:
                    c = sim.com()
                    v.cam.lookat[:] = (c[0], c[1], live.ctl[live.mode].cam["z"])
                l, r = live.hud()
            # set_texts takes the viewer lock itself: calling it inside v.lock() deadlocks
            v.set_texts((mujoco.mjtFontScale.mjFONTSCALE_150, mujoco.mjtGridPos.mjGRID_TOPLEFT, l, r))
            v.sync()
            if close_after and now - t_open > close_after:
                print(f"auto-close: {live.mode} sim t={sim.d.time:.1f}s after {now - t_open:.1f}s wall, "
                      f"fell={live.fell}, status={live.status!r}", flush=True)
                break
            spare = 1 / 60 - (time.perf_counter() - now)
            if spare > 0:
                time.sleep(spare)
    print("viewer closed", flush=True)


def run_headless(live, seconds):
    """No window: run each mode for `seconds` of sim time at the same frame-chunked stepping; print HUD."""
    for mode in MODES:
        live.start(mode)
        t = time.perf_counter()
        while live.sim.d.time < seconds:
            live.advance(1 / 60)
        wall = time.perf_counter() - t
        l, r = live.hud()
        print(f"== {mode}: {seconds:.0f} s sim in {wall:.1f} s wall ({seconds / wall:.1f}x real time)")
        for a, b in zip(l.split("\n")[1:8], r.split("\n")[1:8]):
            print(f"   {a:18s} {b}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xml", nargs="?", default=str(DEFAULT_XML))
    ap.add_argument("--mode", choices=MODES, default="walk")
    ap.add_argument("--tour", action="store_true")
    ap.add_argument("--close-after", type=float)
    ap.add_argument("--headless", type=float)
    a = ap.parse_args()
    live = Live(a.xml)
    live.mode, live.tour = a.mode, a.tour
    if a.headless:
        run_headless(live, a.headless)
    else:
        run_viewer(live, a.close_after)


if __name__ == "__main__":
    main()
