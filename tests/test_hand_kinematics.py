"""
test_hand_kinematics.py  --  unittest-based tests for hand_kinematics.py

Expected positions use independent arithmetic and explicit contract values.
"""

import math, copy, sys, pathlib, unittest
try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest('Optional NumPy/CAD runtime unavailable') from error

sys.path.insert(0,
    str(pathlib.Path(__file__).parent.parent / "skills" / "frcstack" / "scripts"))
from hand_kinematics import (
    joint_specs, forward_kinematics, pose, hand_dimensions,
)

_EXACT_EDGES = [
    # (joint_name, parent_link, child_link)
    ("index_spread",      "palm",             "index_carrier"),
    ("index_mcp",         "index_carrier",    "index_proximal"),
    ("index_pip",         "index_proximal",   "index_middle"),
    ("index_dip",         "index_middle",     "index_distal"),
    ("middle_spread",     "palm",             "middle_carrier"),
    ("middle_mcp",        "middle_carrier",   "middle_proximal"),
    ("middle_pip",        "middle_proximal",  "middle_middle"),
    ("middle_dip",        "middle_middle",    "middle_distal"),
    ("ring_spread",       "palm",             "ring_carrier"),
    ("ring_mcp",          "ring_carrier",     "ring_proximal"),
    ("ring_pip",          "ring_proximal",    "ring_middle"),
    ("ring_dip",          "ring_middle",      "ring_distal"),
    ("little_spread",     "palm",             "little_carrier"),
    ("little_mcp",        "little_carrier",   "little_proximal"),
    ("little_pip",        "little_proximal",  "little_middle"),
    ("little_dip",        "little_middle",    "little_distal"),
    ("thumb_yaw",         "palm",             "thumb_carrier"),
    ("thumb_opposition",  "thumb_carrier",    "thumb_proximal"),
    ("thumb_mcp",         "thumb_proximal",   "thumb_middle"),
    ("thumb_ip",          "thumb_middle",     "thumb_distal"),
]

def _zero():
    return {s["name"]: 0.0 for s in joint_specs()}

def _is_so3(m, atol=1e-9):
    R = m[:3, :3]
    return (np.allclose(R.T @ R, np.eye(3), atol=atol) and
            abs(np.linalg.det(R) - 1.0) < atol)


class TestJointSpecsExactEdges(unittest.TestCase):
    """Exact 20 parent-child edges; DIP parent must be <finger>_middle."""

    def test_exact_20_edges(self):
        by_name = {s["name"]: s for s in joint_specs()}
        self.assertEqual(len(by_name), 20)
        for jname, parent, child in _EXACT_EDGES:
            s = by_name[jname]
            self.assertEqual(s["parent_link"], parent,
                f"{jname}: expected parent '{parent}', got '{s['parent_link']}'")
            self.assertEqual(s["child_link"], child,
                f"{jname}: expected child '{child}', got '{s['child_link']}'")

    def test_dip_parent_is_middle(self):
        by_name = {s["name"]: s for s in joint_specs()}
        for f in ("index", "middle", "ring", "little"):
            self.assertEqual(by_name[f"{f}_dip"]["parent_link"], f"{f}_middle",
                f"{f}_dip parent must be {f}_middle")

    def test_data_isolation(self):
        s1 = joint_specs()
        s1[0]["name"] = "BAD"
        s1[0]["limits_deg"][0] = 9999.0
        s2 = joint_specs()
        self.assertNotEqual(s2[0]["name"], "BAD")
        self.assertNotEqual(s2[0]["limits_deg"][0], 9999.0)

    def test_axis_unit_vectors(self):
        for s in joint_specs():
            self.assertAlmostEqual(np.linalg.norm(s["axis_local"]), 1.0, places=9)

    def test_limits_ordered(self):
        for s in joint_specs():
            lo, hi = s["limits_deg"]
            self.assertLessEqual(lo, hi)


class TestMiddleFingerZeroTip(unittest.TestCase):
    """
    All-zero: middle root=(-10,43,10), carrier Y+8, prox Y+42, mid Y+27, dist Y+20
    tip = (-10, 43+8+42+27+20, 10) = (-10, 140, 10)
    """
    def test_tip(self):
        tip = forward_kinematics(_zero())["tips_mm"]["middle"]
        self.assertAlmostEqual(tip[0], -10.0, places=5)
        self.assertAlmostEqual(tip[1], 140.0, places=5)
        self.assertAlmostEqual(tip[2],  10.0, places=5)


class TestThumbZeroTip(unittest.TestCase):
    """
    All-zero: root=(-43,-15,10), base=Rz(55deg).
    Local-Y travel = 8+24+30+22 = 84 mm along Rz(55) Y axis.
    World direction of local +Y after Rz(55) = (-sin55, cos55, 0).
    """
    def test_tip(self):
        r55 = math.radians(55.0)
        total = 8 + 24 + 30 + 22  # = 84
        exp_x = -43.0 + total * (-math.sin(r55))
        exp_y = -15.0 + total * ( math.cos(r55))
        tip = forward_kinematics(_zero())["tips_mm"]["thumb"]
        self.assertAlmostEqual(tip[0], exp_x, places=5)
        self.assertAlmostEqual(tip[1], exp_y, places=5)
        self.assertAlmostEqual(tip[2], 10.0,  places=5)


class TestIndexSpread15(unittest.TestCase):
    """
    spread=15: root=(-31,43,10), Rz(15). Total Y=8+38+25+18=89.
    local +Y -> world (-sin15, cos15, 0).
    """
    def test_tip(self):
        ang = _zero(); ang["index_spread"] = 15.0
        tip = forward_kinematics(ang)["tips_mm"]["index"]
        r = math.radians(15.0); total = 89
        self.assertAlmostEqual(tip[0], -31.0 + total*(-math.sin(r)), places=4)
        self.assertAlmostEqual(tip[1],  43.0 + total*( math.cos(r)), places=4)
        self.assertAlmostEqual(tip[2],  10.0,                         places=4)


class TestIndexMCP90(unittest.TestCase):
    """
    index MCP=90: after carrier (Y=43+8=51), Rx(90) rotates local +Y to world +Z.
    Remaining 38+25+18=81 mm adds to Z. tip=(-31, 51, 10+81=91).
    """
    def test_tip(self):
        ang = _zero(); ang["index_mcp"] = 90.0
        tip = forward_kinematics(ang)["tips_mm"]["index"]
        self.assertAlmostEqual(tip[0], -31.0, places=4)
        self.assertAlmostEqual(tip[1],  51.0, places=4)
        self.assertAlmostEqual(tip[2],  91.0, places=4)


class TestPerturbations(unittest.TestCase):
    """
    20 axis perturbations: each moves its own child but not its parent
    and not a sibling finger.
    """
    def test_all_20(self):
        fk0 = forward_kinematics(_zero())
        for s in joint_specs():
            jname, finger = s["name"], s["finger"]
            child, parent = s["child_link"], s["parent_link"]
            lo, hi = s["limits_deg"]
            mid = (lo + hi) / 2.0
            delta = max(1.0, (hi - lo) * 0.05)
            val = min(hi, mid + delta)
            ang = _zero(); ang[jname] = val
            fk1 = forward_kinematics(ang)
            # child changed
            self.assertGreater(
                np.max(np.abs(fk1["links"][child] - fk0["links"][child])), 1e-6,
                f"{jname}: child '{child}' unchanged")
            # parent unchanged
            self.assertLess(
                np.max(np.abs(fk1["links"][parent] - fk0["links"][parent])), 1e-9,
                f"{jname}: parent '{parent}' changed")
            # sibling finger tip unchanged
            sib = [f for f in ("index","middle","ring","little","thumb") if f != finger][0]
            self.assertLess(
                np.max(np.abs(np.array(fk1["tips_mm"][sib]) -
                              np.array(fk0["tips_mm"][sib]))), 1e-9,
                f"{jname}: sibling '{sib}' tip changed")


class TestOrthonormality(unittest.TestCase):
    def test_all_poses(self):
        for pname in ("open", "partial", "closed"):
            for lname, m in forward_kinematics(pose(pname))["links"].items():
                self.assertTrue(_is_so3(m),
                    f"Pose '{pname}' link '{lname}' not SO(3)")


class TestInvalidInputs(unittest.TestCase):
    def test_rejects_nan(self):
        ang = _zero(); ang["index_mcp"] = float("nan")
        self.assertRaises((ValueError, TypeError), forward_kinematics, ang)

    def test_rejects_inf(self):
        ang = _zero(); ang["ring_pip"] = float("inf")
        self.assertRaises((ValueError, TypeError), forward_kinematics, ang)

    def test_rejects_bool(self):
        ang = _zero(); ang["little_dip"] = True
        self.assertRaises(TypeError, forward_kinematics, ang)

    def test_rejects_np_bool(self):
        ang = _zero(); ang["index_mcp"] = np.bool_(True)
        self.assertRaises(TypeError, forward_kinematics, ang)

    def test_rejects_string(self):
        ang = _zero(); ang["middle_mcp"] = "45"
        self.assertRaises(TypeError, forward_kinematics, ang)

    def test_rejects_nested_array(self):
        ang = _zero(); ang["index_mcp"] = np.array([0.0])  # 1-element array
        self.assertRaises(TypeError, forward_kinematics, ang)

    def test_rejects_coercible_object(self):
        class CoercibleObj:
            def __float__(self): return 0.0
        ang = _zero(); ang["index_mcp"] = CoercibleObj()
        self.assertRaises(TypeError, forward_kinematics, ang)

    def test_rejects_huge_int(self):
        ang = _zero(); ang["middle_mcp"] = 10**400
        self.assertRaises((ValueError, TypeError, OverflowError),
                          forward_kinematics, ang)

    def test_rejects_missing_key(self):
        ang = _zero(); del ang["thumb_ip"]
        self.assertRaises(ValueError, forward_kinematics, ang)

    def test_rejects_extra_key(self):
        ang = _zero(); ang["extra_joint"] = 0.0
        self.assertRaises(ValueError, forward_kinematics, ang)

    def test_rejects_2d_array(self):
        self.assertRaises((ValueError, TypeError),
                          forward_kinematics, np.zeros((4, 5)))

    def test_rejects_wrong_length(self):
        self.assertRaises(ValueError, forward_kinematics, [0.0] * 19)

    def test_rejects_out_of_limits_high(self):
        ang = _zero(); ang["index_pip"] = 120.0
        self.assertRaises(ValueError, forward_kinematics, ang)

    def test_rejects_out_of_limits_low(self):
        ang = _zero(); ang["index_spread"] = -20.0
        self.assertRaises(ValueError, forward_kinematics, ang)

    def test_accepts_flat_list(self):
        result = forward_kinematics([0.0] * 20)
        self.assertIn("tips_mm", result)

    def test_accepts_numpy_1d(self):
        result = forward_kinematics(np.zeros(20))
        self.assertIn("tips_mm", result)

    def test_accepts_np_int_scalar(self):
        ang = _zero(); ang["index_mcp"] = np.int32(0)
        result = forward_kinematics(ang)
        self.assertIn("tips_mm", result)

    def test_accepts_np_float_scalar(self):
        ang = _zero(); ang["index_mcp"] = np.float64(0.0)
        result = forward_kinematics(ang)
        self.assertIn("tips_mm", result)

    def test_rejects_nested_sequence(self):
        bad = [[0.0] * 20]   # 2-D nested list
        self.assertRaises((ValueError, TypeError), forward_kinematics, bad)


class TestHandDimensions(unittest.TestCase):
    def test_top_level_keys(self):
        d = hand_dimensions()
        for k in ("palm_width_mm", "palm_length_mm", "carrier_length_mm", "fingers"):
            self.assertIn(k, d)

    def test_palm_values(self):
        d = hand_dimensions()
        self.assertEqual(d["palm_width_mm"], 90)
        self.assertEqual(d["palm_length_mm"], 86)
        self.assertEqual(d["carrier_length_mm"], 8)

    def test_all_five_fingers(self):
        d = hand_dimensions()
        self.assertEqual(set(d["fingers"].keys()),
                         {"index","middle","ring","little","thumb"})

    def test_finger_keys(self):
        for fdata in hand_dimensions()["fingers"].values():
            for k in ("root_mm", "base_yaw_deg", "lengths_mm"):
                self.assertIn(k, fdata)

    def test_thumb_base_yaw(self):
        d = hand_dimensions()
        self.assertAlmostEqual(d["fingers"]["thumb"]["base_yaw_deg"], 55.0)

    def test_long_finger_base_yaw_zero(self):
        d = hand_dimensions()
        for f in ("index","middle","ring","little"):
            self.assertEqual(d["fingers"][f]["base_yaw_deg"], 0.0)

    def test_isolation(self):
        d1 = hand_dimensions()
        d1["fingers"]["index"]["root_mm"][0] = 9999
        d2 = hand_dimensions()
        self.assertNotEqual(d2["fingers"]["index"]["root_mm"][0], 9999)


class TestPoseAPI(unittest.TestCase):
    def test_open_all_zero(self):
        self.assertTrue(all(v == 0.0 for v in pose("open").values()))

    def test_returns_20(self):
        for n in ("open","partial","closed"):
            self.assertEqual(len(pose(n)), 20)

    def test_unknown_raises(self):
        self.assertRaises(ValueError, pose, "pinch")

    def test_fresh_copy(self):
        p1 = pose("partial"); p1["index_mcp"] = 9999.0
        p2 = pose("partial")
        self.assertNotEqual(p2["index_mcp"], 9999.0)

    def test_within_limits(self):
        sm = {s["name"]: s for s in joint_specs()}
        for pname in ("open","partial","closed"):
            for jname, val in pose(pname).items():
                lo, hi = sm[jname]["limits_deg"]
                self.assertGreaterEqual(val, lo)
                self.assertLessEqual(val, hi)

    def test_passthrough_fk(self):
        for pname in ("open","partial","closed"):
            self.assertIn("tips_mm", forward_kinematics(pose(pname)))


if __name__ == "__main__":
    unittest.main()
