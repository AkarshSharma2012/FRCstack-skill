"""Smoke: build every humanoid part, report validity, counts, mass and statics for each pose."""
import json
import sys
import time

import humanoid_geometry as G
import humanoid_layout as L


def main():
    t = time.time()
    for jn in L.JOINTS:
        if L.JOINTS[jn]["mount"] == "u":
            print(jn, [round(v, 1) for v in L.bracket_params(jn)])
    P = G.parts()
    print(f"built {len(P)} parts in {time.time() - t:.0f}s")
    mass, comp = G.link_inertia(P)
    print("total mass g", round(sum(mass.values())))
    for name, (q, sup) in L.poses().items():
        bad = L.in_range(q)
        if bad:
            print(name, "OUT OF RANGE", bad)
        if sup is None:
            continue
        r = L.statics(q, sup, mass, comp)
        worst = sorted(((abs(v), k) for k, v in r["torque_nm"].items() if L.JOINTS[k]["kind"] == "st"), reverse=True)[:4]
        print(name, "com", r["com_mm"], "margin", r["support_margin_mm"],
              "worst", [(k, round(v, 2)) for v, k in worst])
    json.dump({k: round(v) for k, v in mass.items()}, sys.stdout)


if __name__ == "__main__":
    main()
