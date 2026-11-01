"""grasp_search_v3.py -- search ball placement, finger spread and thumb pose for the 150 mm ball.

Usage: python grasp_search_v3.py OUT_JSON
Writes the best collision-free 5-finger grasp (lowest worst-case actuator utilisation over
six gravity directions) and the top candidates.  Analytical statics only."""
import itertools
import json
import sys

import hand_v3_grasp as gr


def main(out_path):
    best, rows = None, []
    spreads = {"neutral": (0.0, 0.0, 0.0, 0.0), "fan_a": (8.0, 2.0, -4.0, -10.0),
               "fan_b": (-8.0, -2.0, 4.0, 10.0)}
    grid = itertools.product((12.0, 18.0, 24.0), (14.0, 20.0, 26.0), (0.0, 20.0, 35.0),
                             (75.0, 90.0), spreads.items())
    for cx, cy, yaw, opp, (sname, sp) in grid:
        q, contacts, c = gr.grasp(cx, cy, spreads=sp, thumb=(yaw, opp))
        fingers = sorted({f for f, *_ in contacts if f != "palm"})
        if len(fingers) < 4:
            continue
        ev = gr.evaluate(q, contacts, c)
        worst = max(ev.values())
        gap = gr.self_collision(q, c)
        row = dict(worst_2g=worst, cx=cx, cy=cy, yaw=yaw, opp=opp, spread=sname,
                   fingers=fingers, finger_gap_mm=round(gap, 2))
        rows.append(row)
        if gap > 0 and (best is None or worst < best["worst_2g"]):
            best = dict(row, per_direction_2g=ev, q=[round(v, 2) for v in q],
                        n_contacts=len(contacts))
    rows.sort(key=lambda r: r["worst_2g"])
    out = {"best": best, "top": rows[:10], "evaluated": len(rows),
           "safety_g": gr.SAFETY_G, "u_allow_nm": gr.U_ALLOW,
           "note": "utilisation = worst actuator torque / U_ALLOW; scales linearly with g-load"}
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({"best": {k: v for k, v in (best or {}).items() if k != "q"}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
