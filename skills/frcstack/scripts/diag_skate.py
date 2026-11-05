"""Refine stable skate gains: speed tracking near the stable point (k_th 8, k_v 0.1, k_vi -0.3)."""
import itertools
import json
import sys

import sim_ollie as S


def main(xml, cruise=0.3):
    res = []
    for kth, kv, ki in itertools.product((6.0, 8.0, 12.0), (0.05, 0.1, 0.2), (-0.3, -0.6, -1.0)):
        r, _ = S.run_skate(xml, False, seconds=8.0, cruise=cruise, gains=dict(k_th=kth, k_dth=0.3, k_v=kv, k_vi=ki, k_x=0.0))
        row = (r["fell"], r["max_lean_deg"], r["toe_touch_s"], r["distance_m"], r["peak_speed_mps"], kth, kv, ki)
        res.append(row)
        print(*row, flush=True)
    ok = sorted([x for x in res if not x[0] and x[2] == 0], key=lambda x: -x[3])
    print("BEST", json.dumps(ok[:6]))


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.3)
