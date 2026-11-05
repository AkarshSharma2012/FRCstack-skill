"""Walk parameter sweep: steps, step length, timing -> no fall, distance."""
import itertools
import json
import sys

import ollie_ctrl as C
import sim_ollie as S


def run(xml, steps, sl, ts, tw):
    orig = C.walk_plan

    def wp(sim, **kw):
        kw.update(step_len=sl, t_shift=ts, t_swing=tw)
        return orig(sim, **kw)
    C.walk_plan = wp
    try:
        r, _ = S.run_walk(xml, False, steps=steps, step_len=sl)
    finally:
        C.walk_plan = orig
    return r


def main(xml):
    res = []
    for sl, ts, tw in itertools.product((0.05, 0.06, 0.07), (1.0, 1.2), (0.9, 1.1)):
        r = run(xml, 6, sl, ts, tw)
        row = (r["fell"], r["distance_m"], r["ik_max_err_mm"], sl, ts, tw, r["duration_s"])
        res.append(row)
        print(*row, flush=True)
    ok = sorted([x for x in res if not x[0]], key=lambda x: -x[1])
    print("BEST", json.dumps(ok[:5]))


if __name__ == "__main__":
    main(sys.argv[1])
