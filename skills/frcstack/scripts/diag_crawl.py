"""Crawl gait sweep: forward speed with no fall (sign of the stride both ways)."""
import itertools
import json
import sys

import sim_ollie as S


def main(xml):
    res = []
    for period, hip, sh, sign in itertools.product((1.0, 1.4), (9.0, 14.0), (10.0, 16.0), (1, -1)):
        g = dict(period=period, hip=sign * hip, knee=8.0, shoulder=sign * sh, elbow=12.0)
        r, _ = S.run_crawl(xml, False, seconds=8.0, gait=g)
        dx = r["end_x_m"] - r["start_x_m"]
        row = (r["fell"], round(dx, 3), r["max_body_height_m"], period, hip * sign, sh * sign)
        res.append(row)
        print(*row, flush=True)
    ok = sorted([x for x in res if not x[0]], key=lambda x: -x[1])
    print("BEST", json.dumps(ok[:5]))


if __name__ == "__main__":
    main(sys.argv[1])
