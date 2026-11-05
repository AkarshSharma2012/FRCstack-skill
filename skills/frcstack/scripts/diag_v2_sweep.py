"""v2 sweep: walk (stock vs STS3250, timing) and crawl gait.  Prints one line per run."""
import itertools
import sys

import ollie_ctrl as C
import sim_ollie as S

xml, what = sys.argv[1], sys.argv[2]
S.load_poses(xml)
_Sim = C.Sim


def use(strong):
    C.Sim = lambda x, **kw: _Sim(x, strong=strong, **kw)


if what == "walk":
    orig = C.walk_plan
    for strong, sl, ts, tw, lift in itertools.product((False, True), (0.05, 0.07), (1.2, 1.6), (0.9, 1.3), (0.03,)):
        use(strong)
        C.walk_plan = lambda sim, _o=orig, **kw: _o(sim, **dict(kw, step_len=sl, t_shift=ts, t_swing=tw, lift=lift))
        r, _ = S.run_walk(xml, None, steps=6, step_len=sl)
        print("strong" if strong else "stock ", sl, ts, tw, "| fell", r["fell"], "dist", r["distance_m"], "t", r["duration_s"],
              "worst", r["worst_joint"], r["worst_frac_of_force_limit"], flush=True)
    C.walk_plan = orig
else:
    for strong, per, hip, sh in itertools.product((False, True), (1.0, 1.4), (10.0, 14.0, 18.0), (12.0, 16.0, 22.0)):
        use(strong)
        r, _ = S.run_crawl(xml, None, seconds=12.0, gait=dict(period=per, hip=hip, shoulder=sh, knee=8.0, elbow=12.0))
        print("strong" if strong else "stock ", per, hip, sh, "| fell", r["fell"], "dist", r["distance_m"],
              "top", r["max_body_height_m"], "worst", r["worst_joint"], r["worst_frac_of_force_limit"], flush=True)
C.Sim = _Sim
