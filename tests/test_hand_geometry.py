"""Independent kernel checks for the proposed hand, not fabrication approval."""
import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] /
                       "skills" / "frcstack" / "scripts"))
try:
    import numpy as np
    import cadquery as cq
except ImportError:
    raise unittest.SkipTest("optional NumPy/CadQuery unavailable")
from hand_geometry import build_hand, _make_carrier
from hand_kinematics import hand_dimensions, joint_specs, pose


class HandGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {p: build_hand(pose(p)) for p in ("open", "partial", "closed")}

    def assert_empty(self, shape, label):
        self.assertTrue(shape.isValid(), f"invalid Boolean result: {label}")
        self.assertLess(abs(shape.Volume()), 1e-6, label)

    def test_all_21_bodies_valid_and_rigid(self):
        names = {"palm"} | {s["child_link"] for s in joint_specs()}
        nominal = self.cases["open"]["parts"]
        for label, result in self.cases.items():
            self.assertEqual(set(result["parts"]), names)
            for name, solid in result["parts"].items():
                with self.subTest(pose=label, part=name):
                    self.assertEqual(len(solid.Solids()), 1)
                    self.assertTrue(solid.isValid())
                    self.assertTrue(math.isfinite(solid.Volume()))
                    self.assertGreater(solid.Volume(), 0)
                    self.assertAlmostEqual(solid.Volume(), nominal[name].Volume(), delta=1e-5)

    def test_palm_bounds(self):
        bb = self.cases["open"]["parts"]["palm"].BoundingBox()
        for measured, expected in ((bb.xmin, -46), (bb.xmax, 45),
                                    (bb.zmin, -6), (bb.zmax, 7.7)):
            self.assertAlmostEqual(measured, expected, delta=1e-5)

    def test_all_palm_bores_through_plate_and_boss(self):
        palm = self.cases["open"]["parts"]["palm"]
        for name, data in hand_dimensions()["fingers"].items():
            x, y, _ = data["root_mm"]
            probe = cq.Solid.makeCylinder(1.19, 13.9, cq.Vector(x, y, -6.1))
            self.assert_empty(palm.intersect(probe), f"palm/{name} bore")

    def test_index_bores(self):
        parts = self.cases["open"]["parts"]
        yaw = cq.Solid.makeCylinder(1.19, 4.4, cq.Vector(-31, 43, 7.8))
        mcp = cq.Solid.makeCylinder(1.19, 16.2, cq.Vector(-39.1, 55, 10), cq.Vector(1, 0, 0))
        self.assert_empty(parts["index_carrier"].intersect(yaw), "carrier yaw bore")
        for part in ("index_carrier", "index_proximal"):
            self.assert_empty(parts[part].intersect(mcp), f"{part} MCP bore")

    def test_independent_mcp90_bounds(self):
        angles = pose("open")
        angles["index_mcp"] = 90
        bb = build_hand(angles)["parts"]["index_proximal"].BoundingBox()
        # Rx90 about (-31,55,10) maps local z[-6,6] to y[49,61],
        # local y[-5.5,44] to z[4.5,54], and preserves x[-8,8].
        for measured, expected in ((bb.xmin, -39), (bb.xmax, -23),
                                    (bb.ymin, 49), (bb.ymax, 61),
                                    (bb.zmin, 4.5), (bb.zmax, 54)):
            self.assertAlmostEqual(measured, expected, delta=1e-5)

    def test_adjacent_pairs_open_and_partial(self):
        for label in ("open", "partial"):
            parts = self.cases[label]["parts"]
            for spec in joint_specs():
                with self.subTest(pose=label, joint=spec["name"]):
                    self.assert_empty(parts[spec["parent_link"]].intersect(
                        parts[spec["child_link"]]), f"{label}/{spec['name']}")

    def test_short_carrier_refused(self):
        with self.assertRaises(ValueError):
            _make_carrier(cq, 10.9)


if __name__ == "__main__":
    unittest.main()
