"""Kernel-free checks for the v3 in-palm hand layout (packing, routing, bay, grasp model)."""
import itertools
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "frcstack" / "scripts"))
import hand_kinematics as hk  # noqa: E402
import hand_v3_layout as lay  # noqa: E402


def _overlap(a, b, tol=1e-9):
    return all(a[0][i] < b[1][i] - tol and b[0][i] < a[1][i] - tol for i in range(3))


class V3Layout(unittest.TestCase):
    def test_twenty_actuators_one_per_joint(self):
        slots = lay.motor_slots()
        self.assertEqual(len(slots), 20)
        self.assertEqual({s["joint"] for s in slots}, set(hk._JOINT_ORDER))

    def test_motor_volumes_disjoint(self):
        boxes = [(s["joint"], k, b) for s in lay.motor_slots() for k, b in lay.motor_boxes(s).items()]
        for (j1, k1, b1), (j2, k2, b2) in itertools.combinations(boxes, 2):
            if j1 != j2:
                self.assertFalse(_overlap(b1, b2), (j1, k1, j2, k2))

    def test_everything_inside_palm_interior(self):
        (x0, x1), (y0, y1), (z0, z1) = lay.INTERIOR
        vols = [b for s in lay.motor_slots() for b in lay.motor_boxes(s).values()]
        vols += list(lay.pcb_envelope().values())
        for lo, hi in vols:
            self.assertTrue(x0 <= lo[0] and hi[0] <= x1 and y0 <= lo[1] and hi[1] <= y1
                            and z0 <= lo[2] and hi[2] <= z1, (lo, hi))

    def test_electronics_bay_fits_its_budget_and_clears_motors(self):
        b = lay.electronics_budget()
        self.assertTrue(b["fits"])
        self.assertLess(b["bay_volume_cm3"], 8.0)
        motors = [v for s in lay.motor_slots() for v in lay.motor_boxes(s).values()]
        for e in lay.pcb_envelope().values():
            for m in motors:
                self.assertFalse(_overlap(e, m))

    def test_forty_strands_end_at_unique_exits(self):
        S = lay.strand_paths()
        self.assertEqual(len(S), 40)
        ends = {tuple(np.round(p[-1], 6)) for _, _, p in S}
        self.assertEqual(len(ends), 40)
        for _, _, pts in S:
            self.assertAlmostEqual(pts[-1][2], lay.EXIT_Z)

    def test_strands_clear_each_other_motors_and_bay(self):
        segs = [(n, a, b) for n, _f, pts in lay.strand_paths() for a, b in lay.polyline_segments(pts)
                if np.linalg.norm(np.subtract(b, a)) > 1e-6]
        for (n1, a1, b1), (n2, a2, b2) in itertools.combinations(segs, 2):
            if n1 != n2:
                self.assertGreaterEqual(lay.seg_seg_dist(a1, b1, a2, b2), 2 * lay.STRAND_R + 0.2, (n1, n2))
        boxes = [(s["joint"], k, b) for s in lay.motor_slots() for k, b in lay.motor_boxes(s).items()]
        boxes += [(None, "pcb_" + k, b) for k, b in lay.pcb_envelope().items()]
        for n, a, b in segs:
            own = n.rsplit("_", 1)[0]
            for j, k, (lo, hi) in boxes:
                if j == own and k == "drum":
                    continue
                self.assertGreaterEqual(lay.seg_box_dist(a, b, lo, hi, n=30), lay.STRAND_R + 0.15, (n, j, k))

    def test_right_hand_scaled_kinematics(self):
        L = lay.links(hk.pose("open"))
        for T in L.values():
            self.assertAlmostEqual(np.linalg.det(T[:3, :3]), 1.0, places=9)
        r = lay.finger_roots()
        self.assertGreater(r["thumb"][0], 40)                      # thumb on +X (right hand)
        self.assertGreater(r["index"][0], r["little"][0])
        self.assertAlmostEqual(lay.segment_lengths()["middle"][0], 1.1 * 42.0)

    def test_power_budget_within_xarm_tool_supply(self):
        p = lay.power_budget()
        self.assertAlmostEqual(p["tool_supply_w"], 24.0 * 1.8)
        self.assertLessEqual(p["firmware_total_current_cap_a"], p["motor_bus_12v_a_available"] + 1e-9)


class V3Grasp(unittest.TestCase):
    def test_ball_and_lp_consistency(self):
        import hand_v3_grasp as gr
        self.assertAlmostEqual(gr.BALL_D, 150.114, places=3)
        q, contacts, c = gr.grasp(24.0, 26.0, spreads=(8.0, 2.0, -4.0, -10.0), thumb=(20.0, 90.0))
        fingers = {f for f, *_ in contacts if f != "palm"}
        self.assertGreaterEqual(len(fingers), 4)
        hk.forward_kinematics(dict(zip(hk._JOINT_ORDER, q)))      # within joint limits
        ev = gr.evaluate(q, contacts, c)
        self.assertAlmostEqual(ev["palm_up"], 0.0, places=6)       # palm alone carries it
        self.assertTrue(all(math.isfinite(v) for v in ev.values()))


if __name__ == "__main__":
    unittest.main()
