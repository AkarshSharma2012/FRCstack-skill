"""Independent checks of the pull-pull tendon actuation model and pinch pose.

Analytical model tests only.  They do not substitute for friction, creep,
sheath-compliance or prototype measurements."""
import itertools
import math
import pathlib
import sys
import unittest

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] /
                       "skills" / "frcstack" / "scripts"))
import hand_kinematics as hk
import hand_tendons as ht

ORDER = hk._JOINT_ORDER


class CouplingStructure(unittest.TestCase):
    def test_full_rank_both_routings(self):
        for r in ht.ROUTINGS:
            with self.subTest(routing=r):
                rep = ht.actuation_rank(r)
                self.assertEqual(rep["rank"], 20)
                self.assertGreater(rep["sigma_min_mm_per_rad"], 1.0)
                self.assertTrue(rep["lower_triangular_per_finger"])

    def test_determinant_is_product_of_drive_radii(self):
        # Independent of crossings: block lower-triangular => det = prod(diag).
        for r in ht.ROUTINGS:
            M = ht.coupling_matrix(r)
            prod = np.prod([ht._pulley_radius(n) for n in ORDER])
            self.assertAlmostEqual(np.linalg.det(M) / prod, 1.0, places=9)

    def test_no_cross_finger_coupling(self):
        M = ht.coupling_matrix("idler")
        for i, a in enumerate(ORDER):
            for j, b in enumerate(ORDER):
                if a.split("_")[0] != b.split("_")[0]:
                    self.assertEqual(M[i, j], 0.0, (a, b))

    def test_idler_crossings_present_and_distal_free(self):
        M = ht.coupling_matrix("idler")
        ix = {n: i for i, n in enumerate(ORDER)}
        # DIP loop crosses spread, MCP and PIP idlers.
        for crossed in ("index_spread", "index_mcp", "index_pip"):
            self.assertGreater(M[ix["index_dip"], ix[crossed]], 0)
        # MCP loop must not depend on PIP/DIP.
        self.assertEqual(M[ix["index_mcp"], ix["index_pip"]], 0)
        self.assertEqual(M[ix["index_mcp"], ix["index_dip"]], 0)

    def test_unknown_routing_rejected(self):
        with self.assertRaises(ValueError):
            ht.coupling_matrix("magic")


class IndependentAxisCommand(unittest.TestCase):
    """Each joint can be moved alone by a computed actuator vector."""

    def test_every_axis_isolated(self):
        for r in ht.ROUTINGS:
            for n in ORDER:
                q = np.zeros(20)
                q[ORDER.index(n)] = 10.0
                theta = ht.actuator_angles_deg(q, r)
                back = ht.joint_angles_deg(theta, r)
                with self.subTest(routing=r, joint=n):
                    np.testing.assert_allclose(back, q, atol=1e-9)

    def test_roundtrip_named_poses(self):
        for p in ("open", "partial", "closed", "pinch"):
            q = np.array([hk.pose(p)[n] for n in ORDER])
            for r in ht.ROUTINGS:
                np.testing.assert_allclose(
                    ht.joint_angles_deg(ht.actuator_angles_deg(q, r), r), q, atol=1e-9)

    def test_proximal_motion_needs_distal_compensation_with_idlers(self):
        # Moving MCP alone must also rotate the PIP/DIP actuators (coupling is real).
        q = np.zeros(20); q[ORDER.index("index_mcp")] = 30.0
        th = ht.actuator_angles_deg(q, "idler")
        self.assertNotAlmostEqual(th[ORDER.index("index_pip")], 0.0)
        self.assertNotAlmostEqual(th[ORDER.index("index_dip")], 0.0)


class TravelAndRange(unittest.TestCase):
    def test_spans_fit_single_turn_absolute_mode(self):
        for r in ht.ROUTINGS:
            rep = ht.travel_report(r)
            self.assertTrue(rep["fits_single_turn_position_mode"])
            self.assertLessEqual(rep["max_span_deg"], ht.TARGET_SPAN_DEG + 1e-9)

    def test_corner_enumeration_matches_report(self):
        # Brute-force the joint-limit box corners for the thumb (4 joints),
        # independent of the closed-form min/max used in travel_report.
        lims = {s["name"]: s["limits_deg"] for s in hk.joint_specs()}
        thumb = [n for n in ORDER if n.startswith("thumb")]
        base = np.zeros(20)
        for loop in thumb:
            vals = []
            for corner in itertools.product(*[lims[n] for n in thumb]):
                q = base.copy()
                for n, v in zip(thumb, corner):
                    q[ORDER.index(n)] = v
                vals.append(ht.actuator_angles_deg(q, "idler")[ORDER.index(loop)])
            span = max(vals) - min(vals)
            rep = ht.travel_report("idler")["per_actuator"][loop]["span_deg"]
            self.assertAlmostEqual(span, rep, places=6, msg=loop)

    def test_spool_radii_printable(self):
        for r in ht.ROUTINGS:
            radii = ht.spool_radii_mm(r)
            self.assertTrue(np.all(radii >= ht.SPOOL_R_MIN_MM - 1e-12))
            self.assertTrue(np.all(radii <= ht.SPOOL_R_MAX_MM + 1e-12))


class Statics(unittest.TestCase):
    def test_virtual_work(self):
        # Lossless power balance: tau.dq == dT.(M dq), checked with random data.
        rng = np.random.default_rng(3)
        M = ht.coupling_matrix("idler") / 1000.0
        for _ in range(5):
            tau = rng.normal(size=20) * 0.05
            dq = rng.normal(size=20) * 0.01
            dT = np.linalg.solve(M.T, tau)
            self.assertAlmostEqual(tau @ dq, dT @ (M @ dq), places=12)

    def test_tip_torque_by_finite_difference(self):
        # tau_i = J_i^T F with J from finite-differenced FK tip positions.
        q = hk.pose("partial")
        F = np.array([0.0, 0.0, 1.0])
        tau = ht.joint_torques_for_tip_force(q, "index", F)
        h = 1e-4
        for n in ("index_spread", "index_mcp", "index_pip", "index_dip"):
            qp, qm = dict(q), dict(q)
            qp[n] += h; qm[n] -= h
            dp = (np.array(hk.forward_kinematics(qp)["tips_mm"]["index"]) -
                  np.array(hk.forward_kinematics(qm)["tips_mm"]["index"])) / (2 * math.radians(h))
            self.assertAlmostEqual(tau[ORDER.index(n)], dp @ F / 1000.0, places=6, msg=n)

    def test_friction_only_raises_motor_torque(self):
        for r in ht.ROUTINGS:
            eta = ht.loop_efficiency(r)
            self.assertTrue(np.all((eta > 0) & (eta < 1)))

    def test_force_capacity_reported_and_positive(self):
        q = hk.pose("pinch")
        for f in ("index", "thumb"):
            rep = ht.max_tip_force(q, f, (0, 0, 1))
            self.assertGreater(rep["max_force_n"], 0.5)
            self.assertIn(rep["limiting_actuator"], ORDER)
            self.assertGreater(rep["line_break_load_required_n"], rep["peak_tension_diff_n"])


class PinchPose(unittest.TestCase):
    def test_pinch_within_limits_and_pads_facing(self):
        q = hk.pose("pinch")
        fk = hk.forward_kinematics(q)          # raises if outside limits
        t = np.array(fk["tips_mm"]["thumb"]); i = np.array(fk["tips_mm"]["index"])
        d = np.linalg.norm(i - t)
        self.assertTrue(5.0 < d < 15.0, d)
        u = (i - t) / d
        thumb_pad = fk["links"]["thumb_distal"][:3, 2]
        index_pad = fk["links"]["index_distal"][:3, 2]
        self.assertGreater(u @ thumb_pad, math.cos(math.radians(20)))
        self.assertGreater(-u @ index_pad, math.cos(math.radians(20)))

    def test_pinch_other_fingers_untouched(self):
        q = hk.pose("pinch")
        for n in ORDER:
            if n.split("_")[0] in ("middle", "ring", "little"):
                self.assertEqual(q[n], 0.0)


if __name__ == "__main__":
    unittest.main()
