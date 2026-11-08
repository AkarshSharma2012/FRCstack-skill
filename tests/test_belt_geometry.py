"""Kernel checks for the continuous two-pulley belt backing."""

import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/frcstack/scripts"))
try:
    import cadquery as cq
except ImportError as exc:
    raise unittest.SkipTest("optional CadQuery unavailable") from exc

from belt_geometry import build_open_belt
from component_runtime import verify_solid_pair


class OpenBeltGeometryTests(unittest.TestCase):
    def check_backing(self, driver, driven, count, center):
        width, thickness, pitch = 15, 2, 5
        result = build_open_belt(driver, driven, count, pitch, width, thickness)
        belt = result["solid"]
        self.assertEqual(len(belt.Solids()), 1)
        self.assertTrue(belt.isValid())
        self.assertAlmostEqual(belt.Volume(), count * pitch * width * thickness, places=6)
        self.assertAlmostEqual(result["layout"]["center_distance_mm"], center, places=6)
        bounds = belt.BoundingBox()
        self.assertAlmostEqual(bounds.xmin, -driver * pitch / math.tau - thickness / 2)
        self.assertAlmostEqual(bounds.xmax, center + driven * pitch / math.tau + thickness / 2)
        self.assertAlmostEqual(bounds.zmin, -width / 2)
        self.assertAlmostEqual(bounds.zmax, width / 2)
        for axis in (0, center):
            self.assertFalse(belt.isInside(cq.Vector(axis, 0, 0)))
        return belt

    def test_equal_pulleys_from_kit_belt_count(self):
        self.check_backing(42, 42, 131, 222.5)

    def test_unequal_and_reversed_pulley_order(self):
        for driver, driven in ((18, 36), (36, 18)):
            with self.subTest(driver=driver):
                self.check_backing(driver, driven, 80, 131.720400527)

    def test_step_roundtrip_checks_location_and_shape(self):
        belt = self.check_backing(18, 36, 80, 131.720400527)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "belt.step"
            cq.exporters.export(belt, str(path))
            imported = cq.importers.importStep(str(path)).solids().vals()
            self.assertEqual(len(imported), 1)
            self.assertTrue(verify_solid_pair(belt, imported[0]))

    def test_backing_cannot_consume_small_pulley_opening(self):
        with self.assertRaises(ValueError):
            build_open_belt(18, 36, 80, 5, 15, 30)


if __name__ == "__main__":
    unittest.main()
