"""Independent analytic/geometry checks for reusable structural parts."""
import importlib.util
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/frcstack/scripts'))
import parts_geometry as pg


class InputContractTests(unittest.TestCase):
    def test_invalid_and_missing_dimensions_are_refused(self):
        base = dict(width_mm=50.8, height_mm=25.4, wall_mm=1.5875, length_mm=250)
        for value in [True, '250', float('nan'), float('inf'), 0, -1, 10001, 10**1000]:
            with self.subTest(value_type=type(value).__name__), self.assertRaises((ValueError, TypeError)):
                pg.generate_part('rect_tube', {**base, 'length_mm': value})
        with self.assertRaises(ValueError):
            pg.generate_part('rect_tube', dict(width_mm=50, height_mm=25, wall_mm=2))

    def test_plate_requires_explicit_hole_list(self):
        with self.assertRaises(ValueError):
            pg.generate_part('plate', dict(width_mm=100, height_mm=80, thickness_mm=6))

    def test_wrong_analytic_volume_is_refused(self):
        class BadShape:
            def isValid(self): return True
            def Solids(self): return [self]
            def Volume(self): return 1000.0
        with patch.dict(pg._BUILDERS, {'fault': lambda p: (BadShape(), 2000.0)}):
            with self.assertRaises(ValueError):
                pg.generate_part('fault', {})

    def test_invalid_solid_is_refused(self):
        class BadShape:
            def isValid(self): return False
            def Solids(self): return [self]
            def Volume(self): return 1000.0
        with patch.dict(pg._BUILDERS, {'fault': lambda p: (BadShape(), 1000.0)}):
            with self.assertRaises(ValueError):
                pg.generate_part('fault', {})


@unittest.skipUnless(importlib.util.find_spec('cadquery'), 'optional CadQuery not installed')
class KernelGeometryTests(unittest.TestCase):
    def test_rectangular_stock_area_and_datum(self):
        shape, volume = pg.generate_part('rect_tube', dict(
            width_mm=50.8, height_mm=25.4, wall_mm=1.5875, length_mm=250))
        area = 50.8 * 25.4 - 47.625 * 22.225
        self.assertAlmostEqual(volume, area * 250, places=6)
        self.assertAlmostEqual(shape.Volume(), area * 250, places=5)
        self.assertEqual(len(shape.Solids()), 1)
        box = shape.BoundingBox()
        self.assertAlmostEqual(box.zmin, 0, places=6)
        self.assertAlmostEqual(box.zmax, 250, places=6)
        self.assertAlmostEqual(box.xmin, -25.4, places=6)
        self.assertTrue(shape.isValid())

    def test_dimension_variant_rebuilds_geometry(self):
        shape, volume = pg.generate_part('rect_tube', dict(
            width_mm=50.8, height_mm=25.4, wall_mm=1.5875, length_mm=500))
        self.assertAlmostEqual(shape.BoundingBox().zlen, 500, places=6)
        self.assertAlmostEqual(volume, 2 * (50.8 * 25.4 - 47.625 * 22.225) * 250, places=6)

    def test_round_tube_matches_analytic_volume(self):
        shape, volume = pg.generate_part('round_tube', dict(
            outer_diameter_mm=38.1, inner_diameter_mm=31.75, length_mm=200))
        wanted = math.pi * (19.05**2 - 15.875**2) * 200
        self.assertAlmostEqual(volume, wanted, places=6)
        self.assertAlmostEqual(shape.Volume(), wanted, places=5)

    def test_drilled_plate_actual_void_is_at_requested_location(self):
        import cadquery as cq
        shape, volume = pg.generate_part('plate', dict(width_mm=100, height_mm=80, thickness_mm=6,
            holes=[dict(x_mm=-20, y_mm=10, diameter_mm=10)]))
        wanted = 100 * 80 * 6 - math.pi * 25 * 6
        self.assertAlmostEqual(volume, wanted, places=6)
        self.assertAlmostEqual(shape.Volume(), wanted, places=5)
        probe = cq.Workplane('XY').center(-20, 10).circle(4).extrude(6).val()
        self.assertAlmostEqual(shape.intersect(probe).Volume(), 0, places=6)
        other = cq.Workplane('XY').center(20, 10).circle(4).extrude(6).val()
        self.assertAlmostEqual(shape.intersect(other).Volume(), math.pi * 16 * 6, places=5)

    def test_edge_tangent_and_overlapping_holes_are_refused(self):
        for holes in [[dict(x_mm=45, y_mm=0, diameter_mm=10)],
                      [dict(x_mm=0, y_mm=0, diameter_mm=10), dict(x_mm=5, y_mm=0, diameter_mm=10)]]:
            with self.subTest(holes=holes), self.assertRaises(ValueError):
                pg.generate_part('plate', dict(width_mm=100, height_mm=80, thickness_mm=6, holes=holes))

    def test_multiple_solids_cannot_be_a_single_part(self):
        import cadquery as cq
        a = cq.Workplane().box(10, 10, 10).val()
        b = a.translate((50, 0, 0))
        compound = cq.Compound.makeCompound([a, b])
        with patch.dict(pg._BUILDERS, {'fault': lambda p: (compound, 2000)}):
            with self.assertRaises(ValueError):
                pg.generate_part('fault', {})


if __name__ == '__main__':
    unittest.main()
