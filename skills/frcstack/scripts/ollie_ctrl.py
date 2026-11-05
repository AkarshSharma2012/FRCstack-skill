"""
ollie_ctrl.py -- controllers for the OLLIE MuJoCo model (sim venv).

  Sim             thin wrapper: named joints, pose setting, dropping onto the floor
  ik_legs         MuJoCo-Jacobian IK: base pose + flat foot targets -> 12 leg joint angles
  walk_plan       quasi-static walking plan (COM over the stance foot before every lift)
  lqr_gain        finite-difference linearisation (mjd_transitionFD) + discrete LQR
Scripted / model-based controllers only -- no learned policy yet.
"""
from __future__ import annotations

import math

import mujoco
import numpy as np
from scipy.linalg import solve_discrete_are

LEG = ("hip_yaw", "hip_roll", "hip_pitch", "knee", "ankle_pitch", "ankle_roll")
FOOT_FWD = 0.031          # sole centre is 31 mm ahead of the foot-body origin (ankle-roll axis)
STS3250_NM = 50 * 0.0980665 * 11.1 / 12.0      # Feetech STS3250 drop-in upgrade (same case as ST3215)
STRONG = tuple(f"{j}_{s}" for j in ("hip_roll", "hip_pitch", "knee") for s in "LR")


class Sim:
    def __init__(self, xml, kp=60.0, kv=1.2, strong=False):
        self.m = mujoco.MjModel.from_xml_path(xml)
        self.d = mujoco.MjData(self.m)
        m = self.m
        self.act = {mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_ACTUATOR, i)[4:]: i for i in range(m.nu)}
        if strong:
            for n in STRONG:
                m.actuator_forcerange[self.act[n]] = (-STS3250_NM, STS3250_NM)
        # ST3215 position loop: stiff until the torque limit (stall reached at ~2.6 deg error with kp=60)
        for n, i in self.act.items():
            if not n.startswith(("wheel", "gripper", "neck")):
                m.actuator_gainprm[i, 0] = kp
                m.actuator_biasprm[i, 1] = -kp
                m.actuator_biasprm[i, 2] = -kv
            elif n.startswith("wheel"):
                # N20 as a real DC gearmotor: ctrl = duty in [-1, 1]; torque = stall*duty - (stall/w_free)*w
                stall = float(m.actuator_forcerange[i, 1])
                w_free = float(m.actuator_ctrlrange[i, 1])
                m.actuator_gainprm[i, :3] = (stall, 0, 0)
                m.actuator_biasprm[i, :3] = (0, 0, -stall / w_free)
                m.actuator_ctrlrange[i] = (-1.0, 1.0)
        self.wheel_free = float(m.actuator_ctrlrange[self.act["wheel_L"], 1]) if False else None
        jid = {n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n) for n in self.act}
        self.qadr = {n: int(m.jnt_qposadr[j]) for n, j in jid.items()}
        self.vadr = {n: int(m.jnt_dofadr[j]) for n, j in jid.items()}
        self.base = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "base")
        self.foot = {s: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, f"foot_{s}") for s in "LR"}

    def gid(self, name):
        return mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_GEOM, name)

    def set_pose(self, base_pos, base_quat, qdeg):
        d = self.d
        d.qpos[:3] = base_pos
        d.qpos[3:7] = base_quat
        for n, v in qdeg.items():
            if n in self.qadr and not n.startswith("wheel"):
                d.qpos[self.qadr[n]] = math.radians(v)
        d.qvel[:] = 0
        mujoco.mj_forward(self.m, d)

    def lowest(self, names):
        """Lowest world z over the given box / cylinder geoms."""
        m, d = self.m, self.d
        z = []
        for n in names:
            g = self.gid(n)
            R = d.geom_xmat[g].reshape(3, 3)
            s = m.geom_size[g]
            if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX:
                z.append(d.geom_xpos[g][2] - np.abs(R[2, :]) @ s)
            else:   # cylinder, axis = local z
                a = abs(R[2, 2])
                z.append(d.geom_xpos[g][2] - a * s[1] - math.sqrt(max(0.0, 1 - a * a)) * s[0])
        return min(z)

    def drop(self, names, gap=0.0004):
        self.d.qpos[2] -= self.lowest(names) - gap
        mujoco.mj_forward(self.m, self.d)

    def qdeg(self):
        return {n: math.degrees(self.d.qpos[a]) for n, a in self.qadr.items()}

    def rpy(self):
        w, x, y, z = self.d.qpos[3:7]
        roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
        pitch = math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))
        return roll, pitch

    def com(self):
        return self.d.subtree_com[self.base].copy()


# --------------------------------------------------------------------------- IK
def _ranges(sim: Sim):
    out = {}
    for n, a in sim.qadr.items():
        j = mujoco.mj_name2id(sim.m, mujoco.mjtObj.mjOBJ_JOINT, n)
        if sim.m.jnt_limited[j]:
            out[n] = tuple(math.degrees(v) for v in sim.m.jnt_range[j])
    return out


SEED = {f"{j}_{s}": v for s in "LR" for j, v in (("hip_pitch", -15.0), ("knee", 30.0), ("ankle_pitch", -15.0))}


def ik_legs(sim: Sim, base_pos, feet: dict, qseed: dict, iters=30, tol=1e-5):
    """Upright base at base_pos; feet[s] = world xyz of the foot-body origin, foot kept flat.
    Damped least squares with step clamp and joint-limit clamp.  Returns (q degrees, max position error m)."""
    m, d = sim.m, sim.d
    rng = getattr(sim, "_rng", None) or _ranges(sim)
    sim._rng = rng
    q = dict(SEED)
    q.update(qseed)
    jacp = np.zeros((3, m.nv))
    jacr = np.zeros((3, m.nv))
    worst = 1.0
    for _ in range(iters):
        sim.set_pose(base_pos, (1, 0, 0, 0), q)
        worst = 0.0
        for s, target in feet.items():
            b = sim.foot[s]
            ep = np.asarray(target) - d.xpos[b]
            R = d.xmat[b].reshape(3, 3)
            er = 0.5 * np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
            worst = max(worst, float(np.linalg.norm(ep)))
            mujoco.mj_jacBody(m, d, jacp, jacr, b)
            cols = [sim.vadr[f"{j}_{s}"] for j in LEG]
            w = 0.1                                   # rad error weighted like 0.1 m
            J = np.vstack([jacp[:, cols], jacr[:, cols] * w])
            e = np.r_[ep, -er * w]
            dq = J.T @ np.linalg.solve(J @ J.T + 1e-4 * np.eye(6), e)
            dq = np.clip(dq, -0.15, 0.15)
            for k, j in enumerate(LEG):
                n = f"{j}_{s}"
                v = q.get(n, 0.0) + math.degrees(dq[k])
                lo, hi = rng.get(n, (-180, 180))
                q[n] = min(max(v, lo), hi)
        if worst < tol:
            break
    return q, worst


def com_over(sim: Sim, base_z, feet, com_xy, qseed, rounds=3):
    """Base xy chosen so the whole-body COM projects onto com_xy (quasi-static)."""
    bxy = np.array(sim._bxy if hasattr(sim, "_bxy") else com_xy, float)
    q = qseed
    err = 0.0
    for _ in range(rounds):
        q, err = ik_legs(sim, (bxy[0], bxy[1], base_z), feet, q)
        bxy += np.asarray(com_xy) - sim.com()[:2]
    q, err = ik_legs(sim, (bxy[0], bxy[1], base_z), feet, q)
    sim._bxy = bxy.copy()
    return q, bxy, err


def _smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def walk_plan(sim: Sim, steps=4, step_len=0.045, lift=0.022, base_z=-0.018, t_shift=1.4, t_swing=1.4,
              dt=0.02, arm_q=None):
    """Precompute a quasi-static walk.  Returns list of (time, qdeg targets, stance) at dt."""
    foot0 = {"L": np.array([-0.012, 0.045, 0.033]), "R": np.array([-0.012, -0.045, 0.033])}
    feet = {s: v.copy() for s, v in foot0.items()}

    def centre(s):
        return feet[s][:2] + np.array([FOOT_FWD, 0.0])
    plan, t = [], 0.0
    q = dict(SEED)
    worst = 0.0
    com_xy = (centre("L") + centre("R")) / 2
    seq = []
    stance = "L"
    for k in range(steps):
        swing = "R" if stance == "L" else "L"
        seq.append(("shift", stance, swing))
        seq.append(("swing", stance, swing, step_len * (1.0 if k else 0.5)))
        stance = swing
    seq.append(("shift_mid", None, None))
    for item in seq:
        if item[0] in ("shift", "shift_mid"):
            start = com_xy.copy()
            goal = centre(item[1]) if item[0] == "shift" else (centre("L") + centre("R")) / 2
            if item[0] == "shift":
                goal = goal + np.array([0.0, -0.004 if item[1] == "L" else 0.004])   # stay just inside
            n = int(t_shift / dt)
            for i in range(n + 1):
                com_xy = start + (goal - start) * _smooth(i / n)
                q, bxy, err = com_over(sim, base_z, feet, com_xy, q, rounds=2 if i else 4)
                worst = max(worst, err)
                plan.append((t, dict(q, **(arm_q or {})), item[1] or "both", bxy.copy()))
                t += dt
        else:
            _, st, sw, dx = item
            a = feet[sw].copy()
            b = a + np.array([dx + (feet[st][0] - a[0]), 0.0, 0.0])
            n = int(t_swing / dt)
            for i in range(n + 1):
                u = _smooth(i / n)
                p = a + (b - a) * u
                p[2] = a[2] + lift * math.sin(math.pi * u)
                feet[sw] = p
                q, bxy, err = com_over(sim, base_z, feet, com_xy, q, rounds=1)
                worst = max(worst, err)
                plan.append((t, dict(q, **(arm_q or {})), st, bxy.copy()))
                t += dt
            feet[sw] = b
    if hasattr(sim, "_bxy"):
        del sim._bxy
    return plan, worst


# --------------------------------------------------------------------------- LQR
def equilibrium_ctrl(sim: Sim, qref_deg):
    """Actuator controls that hold the current state still (position actuators: ctrl = q + f/kp)."""
    m, d = sim.m, sim.d
    d.qacc[:] = 0
    mujoco.mj_inverse(m, d)
    tau = d.qfrc_inverse.copy()
    ctrl = np.zeros(m.nu)
    for n, i in sim.act.items():
        v = sim.vadr[n]
        kp = m.actuator_gainprm[i, 0]
        if n.startswith("wheel"):
            ctrl[i] = tau[v] / kp
        else:
            ctrl[i] = d.qpos[sim.qadr[n]] + tau[v] / kp
    return ctrl, tau


def lqr_gain(sim: Sim, ctrl0, q_base=(60, 60, 60, 300, 300, 120), q_joint=4.0, q_wheel=20.0, q_vel=0.5,
             r_act=1.0, r_wheel=0.2, inputs=None):
    """Discrete LQR on the full model linearised at the current state.  inputs: actuator names to use
    (default all); other actuators stay at ctrl0.  Returns (K, input indices)."""
    m, d = sim.m, sim.d
    nv = m.nv
    A = np.zeros((2 * nv + m.na, 2 * nv + m.na))
    B = np.zeros((2 * nv + m.na, m.nu))
    d.ctrl[:] = ctrl0
    mujoco.mjd_transitionFD(m, d, 1e-6, True, A, B, None, None)
    idx = [sim.act[n] for n in inputs] if inputs else list(range(m.nu))
    B = B[:, idx]
    Q = np.full(2 * nv, 1e-4)
    Q[:6] = q_base
    for n, i in sim.act.items():
        Q[sim.vadr[n]] = q_wheel if n.startswith("wheel") else q_joint
    Q[nv:] = q_vel
    Q[nv:nv + 6] = np.array(q_base) * 0.1 + 1e-4
    R = np.eye(len(idx)) * r_act
    for k, i in enumerate(idx):
        n = [a for a, j in sim.act.items() if j == i][0]
        if n.startswith("wheel"):
            R[k, k] = r_wheel
    P = solve_discrete_are(A, B, np.diag(Q), R)
    K = np.linalg.solve(R + B.T @ P @ B, B.T @ P @ A)
    return K, idx


def state_error(sim: Sim, qpos_ref):
    """[dq (nv), dv (nv)] with dq = qpos - qpos_ref in the tangent space (mj_differentiatePos(qpos_ref -> qpos))."""
    m, d = sim.m, sim.d
    dq = np.zeros(m.nv)
    mujoco.mj_differentiatePos(m, dq, 1.0, qpos_ref, d.qpos)
    return np.r_[dq, d.qvel]


def _state_error_old(sim: Sim, qpos_ref):
    m, d = sim.m, sim.d
    dq = np.zeros(m.nv)
    mujoco.mj_differentiatePos(m, dq, 1, qpos_ref, d.qpos)
    return np.r_[dq, d.qvel]
