"""Smoke: build all OLLIE parts, mass, and solve skate / crawl poses."""
import time

import numpy as np

import humanoid_layout as L
import ollie_geometry as OG
import ollie_physics as OP


def main():
    t = time.time()
    P = OG.parts()
    print(f"built {len(P)} parts in {time.time() - t:.0f}s")
    mass, comz = OG.link_inertia(P)
    print("mass g", round(sum(mass.values())))
    r = OP.statics({}, np.eye(4), ["sole_L", "sole_R"], mass, comz)
    print("stand", r["com_mm"], r["support_margin_mm"], r["balance_residual_n"])
    q, Tb, err = OP.skate_pose(mass, comz)
    r = OP.statics(q, Tb, ["wheel_L", "wheel_R"], mass, comz)
    print("skate err", round(err, 2), {k: v for k, v in q.items() if k.endswith("_L")}, r["support_margin_mm"],
          r["balance_residual_n"])
    print(" pendulum", OP.pendulum(q, Tb, mass, comz))
    q, Tb, beta = OP.crawl_pose(mass, comz)
    r = OP.statics(q, Tb, ["knee_L", "knee_R", "paw_L", "paw_R"], mass, comz)
    print("crawl beta", beta, {k: v for k, v in q.items() if k.endswith("_L")}, "margin", r["support_margin_mm"],
          "contacts", r["contacts"], "resid", r["balance_residual_n"])
    worst = sorted(((abs(v), k) for k, v in r["torque_nm"].items()), reverse=True)[:5]
    print(" crawl worst", [(k, round(v, 2)) for v, k in worst])
    Tl = OP.transforms(q, Tb)
    print(" crawl top z", round(max((Tl[p.link] @ np.array([*p.shape.Center().toTuple(), 1]))[2] for p in P.values())))


if __name__ == "__main__":
    main()
