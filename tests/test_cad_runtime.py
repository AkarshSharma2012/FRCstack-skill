"""Real-kernel tests; no network, training, Onshape login, or copied team CAD."""
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/frcstack/scripts/cad_runtime.py"


@unittest.skipUnless(importlib.util.find_spec("cadquery"), "optional CadQuery runtime not installed")
class CadRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cad = None
        if SCRIPT.exists():
            spec = importlib.util.spec_from_file_location("frcstack_cad_runtime", SCRIPT)
            cls.cad = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = cls.cad
            spec.loader.exec_module(cls.cad)

    def runtime(self):
        self.assertIsNotNone(self.cad, "CAD execution helper has not been implemented")
        return self.cad

    def test_fixture_contains_four_valid_separate_solids(self):
        c = self.runtime()
        result = c.build_fixture(c.FixtureParameters())
        self.assertEqual(set(result.parts), {"left_plate", "right_plate", "shaft", "roller"})
        for shape in result.parts.values():
            self.assertTrue(shape.isValid())
            self.assertEqual(len(shape.Solids()), 1)
            self.assertGreater(shape.Volume(), 0)

    def test_geometry_matches_hand_calculated_plate_and_roller_volumes(self):
        c = self.runtime()
        result = c.build_fixture(c.FixtureParameters())
        # Plate 80 x 120 x 6 with diameter-13 central hole.
        self.assertAlmostEqual(result.parts["left_plate"].Volume(), 56803.606262315, places=5)
        # Roller tube L=360, OD=50, ID=14.
        self.assertAlmostEqual(result.parts["roller"].Volume(), math.pi * 207360, places=5)

    def test_span_and_roller_length_changes_rebuild_real_geometry(self):
        c = self.runtime()
        a = c.build_fixture(c.FixtureParameters())
        b = c.build_fixture(c.FixtureParameters(inner_span_mm=500, roller_length_mm=450))
        self.assertAlmostEqual(a.parts["shaft"].BoundingBox().xlen, 412)
        self.assertAlmostEqual(b.parts["shaft"].BoundingBox().xlen, 512)
        self.assertAlmostEqual(b.parts["roller"].BoundingBox().xlen, 450)
        self.assertGreater(b.parts["roller"].Volume(), a.parts["roller"].Volume())

    def test_invalid_and_nonfinite_parameters_are_refused(self):
        c = self.runtime()
        for values in ({"inner_span_mm": 0}, {"roller_length_mm": 405},
                       {"shaft_diameter_mm": 14}, {"bore_diameter_mm": 50},
                       {"hole_diameter_mm": 80}, {"plate_thickness_mm": -1},
                       {"inner_span_mm": float("nan")}, {"roller_length_mm": float("inf")},
                       {"inner_span_mm": True}, {"roller_length_mm": "360"},
                       {"plate_thickness_mm": 1e-8}, {"inner_span_mm": 10**1000}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                c.build_fixture(c.FixtureParameters(**values))

    def test_default_fixture_has_no_pairwise_positive_volume_overlap(self):
        c = self.runtime()
        self.assertEqual(c.interferences(c.build_fixture(c.FixtureParameters()).parts), [])

    def test_deliberate_overlap_is_detected_by_kernel_not_names(self):
        c = self.runtime()
        import cadquery as cq
        a = cq.Workplane().box(10, 10, 10).val()
        b = cq.Workplane().box(10, 10, 10).translate((5, 0, 0)).val()
        collisions = c.interferences({"a": a, "b": b})
        self.assertEqual(len(collisions), 1)
        self.assertAlmostEqual(collisions[0]["overlap_mm3"], 500)

    def test_geometry_sampling_reports_coverage_without_claiming_continuous_motion(self):
        c = self.runtime()
        result = c.sample_motion(c.build_fixture(c.FixtureParameters()), [0, 90, 180, 270, 360])
        self.assertEqual(result["angles_degrees"], [0, 90, 180, 270, 360])
        self.assertEqual(result["collisions"], [])
        self.assertFalse(result["continuous_motion_verified"])
        self.assertFalse(result["onshape_mates_verified"])
        for invalid in ([], [float("nan")], [True], ["90"]):
            with self.assertRaises(ValueError):
                c.sample_motion(c.build_fixture(c.FixtureParameters()), invalid)

    def test_step_roundtrip_preserves_four_solids_and_bounds(self):
        c = self.runtime()
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "fixture"
            report = c.export_fixture(c.FixtureParameters(), out)
            imported = c.inspect_step(out / "fixture.step")
            self.assertEqual(imported["solid_count"], 4)
            self.assertTrue(imported["all_solids_valid"])
            self.assertAlmostEqual(imported["bounds_mm"]["x"], 412, places=5)
            self.assertAlmostEqual(imported["bounds_mm"]["y"], 80, places=5)
            self.assertAlmostEqual(imported["bounds_mm"]["z"], 120, places=5)
            self.assertTrue(report["step_roundtrip_verified"])
            self.assertFalse(report["fabrication_ready"])
            self.assertFalse(report["fea_executed"])
            self.assertTrue((out / "parameters.json").is_file())

    def test_existing_output_is_preserved_without_overwrite(self):
        c = self.runtime()
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            keep = out / "keep.txt"
            keep.write_text("user data")
            with self.assertRaises(FileExistsError):
                c.export_fixture(c.FixtureParameters(), out)
            self.assertEqual(keep.read_text(), "user data")

    def test_invalid_input_does_not_create_output_directory(self):
        c = self.runtime()
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "invalid"
            with self.assertRaises(ValueError):
                c.export_fixture(c.FixtureParameters(inner_span_mm=-1), out)
            self.assertFalse(out.exists())

    def test_non_step_or_empty_file_cannot_be_reported_as_valid_cad(self):
        c = self.runtime()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "not_cad.step"
            path.write_text("This is not a STEP model")
            with self.assertRaises(ValueError):
                c.inspect_step(path)

    def test_multi_root_step_inspection_includes_every_root(self):
        c = self.runtime()
        import cadquery as cq
        from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
        from OCP.IFSelect import IFSelect_RetDone
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "two-roots.step"
            writer = STEPControl_Writer()
            writer.Transfer(cq.Workplane().box(10, 10, 10).val().wrapped, STEPControl_AsIs)
            writer.Transfer(cq.Workplane().box(20, 20, 20).translate((100, 0, 0)).val().wrapped, STEPControl_AsIs)
            self.assertEqual(writer.Write(str(path)), IFSelect_RetDone)
            result = c.inspect_step(path)
            self.assertEqual(result["solid_count"], 2)
            self.assertAlmostEqual(result["bounds_mm"]["x"], 115)
            self.assertAlmostEqual(result["sum_solid_volumes_mm3"], 9000)


if __name__ == "__main__":
    unittest.main()
