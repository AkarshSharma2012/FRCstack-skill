"""Unit tests for the $700 humanoid layout, brackets and statics (no CAD kernel needed)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "frcstack", "scripts"))

import numpy as np  # noqa: E402

import humanoid_brackets as hb  # noqa: E402
import humanoid_layout as L  # noqa: E402


def _toy_mass():
    mass = {ln: 60.0 for ln in L.LINKS}
    mass["base"] = 1200.0
    Tl = L.link_transforms({})
    com = {}
    for ln in L.LINKS:
        jn = L._CHILD_JOINT.get(ln)
        com[ln] = np.array(L.JOINTS[jn]["p"], float) if jn else np.array([0.0, 0.0, 580.0])
    return mass, com


class HumanoidLayout(unittest.TestCase):
    def test_twenty_actuators(self):
        st = [j for j in L.JOINTS.values() if j["kind"] == "st"]
        sc = [j for j in L.JOINTS.values() if j["kind"] == "sc"]
        self.assertEqual((len(st), len(sc)), (16, 4))

    def test_servo_frames_are_rotations(self):
        for jn in L.JOINTS:
            R = L.servo_frame(jn)[:3, :3]
            self.assertAlmostEqual(np.linalg.det(R), 1.0, places=9)
            self.assertAlmostEqual(abs(np.dot(R[:, 2], L.JOINTS[jn]["axis"])), 1.0, places=9, msg=jn)

    def test_left_right_mirror(self):
        for jn in L.JOINTS:
            if jn.endswith("_L"):
                pl, pr = np.array(L.JOINTS[jn]["p"]), np.array(L.JOINTS[jn[:-2] + "_R"]["p"])
                self.assertTrue(np.allclose(pl * [1, -1, 1], pr), jn)

    def test_brackets_clear_over_full_range(self):
        for jn, j in L.JOINTS.items():
            if j["mount"] != "u":
                continue
            phi, R, xc = L.bracket_params(jn)
            self.assertLessEqual(xc, 27.0, jn)              # vendor M2 holes stay usable
            b = hb.bridge_poly(phi, R)
            case = hb._rect(hb.CASE_X[0], hb.CR_END, -hb.CASE_Y, hb.CASE_Y)
            for a in L.alpha_range(jn):
                self.assertFalse(hb._overlap(hb._rot2(b, a), case), (jn, a))

    def test_zero_pose_is_identity(self):
        for T in L.link_transforms({}).values():
            self.assertTrue(np.allclose(T, np.eye(4)))

    def test_joint_rotation_keeps_axis_point(self):
        for jn, j in L.JOINTS.items():
            T = L.joint_tf(jn, 37.0)
            p = np.array([*j["p"], 1.0])
            self.assertTrue(np.allclose(T @ p, p), jn)

    def test_poses_within_joint_limits(self):
        for name, (q, _) in L.poses(-9.0).items():
            self.assertEqual(L.in_range(q), [], name)

    def test_standing_statics_balanced(self):
        mass, com = _toy_mass()
        r = L.statics({}, "both", mass, com)
        self.assertGreater(r["support_margin_mm"], 30)
        for jn, t in r["torque_nm"].items():
            if jn.startswith(("knee", "hip_pitch", "ankle_pitch")):
                self.assertLess(abs(t), 0.3, jn)

    def test_balance_roll_puts_com_over_support_foot(self):
        mass, com = _toy_mass()
        roll = L.balance_roll(mass, com)
        q, sup = L.poses(roll)["single_support_left"]
        r = L.statics(q, sup, mass, com)
        self.assertGreater(r["support_margin_mm"], 20)

    def test_single_support_torque_under_stall(self):
        mass, com = _toy_mass()
        q, sup = L.poses(L.balance_roll(mass, com))["single_support_left"]
        r = L.statics(q, sup, mass, com)
        worst = max(abs(v) for k, v in r["torque_nm"].items() if L.JOINTS[k]["kind"] == "st")
        self.assertLess(worst, L.ST_STALL_NM)


if __name__ == "__main__":
    unittest.main()
