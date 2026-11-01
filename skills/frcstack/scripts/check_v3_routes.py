"""check_v3_routes.py -- fast (no CAD) clearance check of v3 strands vs strands, motors, plugs,
drums and the PCB envelope.  Prints violations; exit 1 if any."""
import itertools
import sys

import numpy as np

import hand_v3_layout as lay

GAP = 2 * lay.STRAND_R + 0.2          # strand-strand min centre distance


def main():
    S = lay.strand_paths()
    segs = [(n, a, b) for n, _f, pts in S for a, b in lay.polyline_segments(pts)
            if np.linalg.norm(np.subtract(b, a)) > 1e-6]
    bad = []
    for (n1, a1, b1), (n2, a2, b2) in itertools.combinations(segs, 2):
        if n1 == n2:
            continue
        d = lay.seg_seg_dist(a1, b1, a2, b2)
        if d < GAP:
            bad.append(("strand", n1, n2, round(d, 3)))
    boxes = []
    for s in lay.motor_slots():
        for k, (lo, hi) in lay.motor_boxes(s).items():
            boxes.append((f"{k}_{s['joint']}", s["joint"], lo, hi))
    for k, (lo, hi) in lay.pcb_envelope().items():
        boxes.append((f"pcb_{k}", None, lo, hi))
    for n, a, b in segs:
        own = n.rsplit("_", 1)[0]
        for bn, joint, lo, hi in boxes:
            if joint == own and bn.startswith("drum"):
                continue
            d = lay.seg_box_dist(a, b, lo, hi, n=40)
            if d < lay.STRAND_R + 0.15:
                bad.append(("box", n, bn, round(d, 3)))
    for x in bad[:60]:
        print(x)
    print("violations", len(bad), "segments", len(segs))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
