"""
test_hand_runtime.py  --  Unit and integration tests for hand_runtime.py.
=========================================================================
- NumPy/CadQuery tests skip if deps absent.
- Roundtrip and collision fixtures use the real kernel.
- No test merely matches implementation constants.
- Avoids repeated expensive full builds: setUpClass builds open once.
"""
import math
import pathlib
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "skills" / "frcstack" / "scripts"
sys.path.insert(0, str(_SCRIPTS))

# ---------------------------------------------------------------------------
# Pure-Python tests (no kernel required)
# ---------------------------------------------------------------------------

class HandRuntimeInputValidation(unittest.TestCase):
    """Validate rejection of bad inputs without requiring CadQuery."""

    def _import(self):
        import hand_runtime as hr
        return hr

    def test_unknown_pose_raises(self):
        hr = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "should_not_exist"
            with self.assertRaises((ValueError, RuntimeError)) as cm:
                hr.build_hand_export("fist", out)
            # Must identify the bad pose
            self.assertIn("fist", str(cm.exception))

    def test_existing_output_raises(self):
        hr = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "existing"
            out.mkdir()
            with self.assertRaises(FileExistsError):
                hr.build_hand_export("open", out)

    def test_symlink_output_refused(self):
        """Symlink in output path must raise ValueError, not silently proceed."""
        hr = self._import()
        import os
        with tempfile.TemporaryDirectory() as tmp:
            real_dir = Path(tmp) / "real"
            real_dir.mkdir()
            link = Path(tmp) / "link"
            try:
                os.symlink(str(real_dir), str(link))
            except OSError:
                self.skipTest("Symlink creation not supported on this system")
            with self.assertRaises((ValueError, FileExistsError)):
                hr.build_hand_export("open", link / "output")

    def test_cli_unknown_pose_exit_nonzero(self):
        """CLI with unknown pose must exit non-zero."""
        hr = self._import()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "x"
            code = hr.main(["build-hand", "--pose", "open", "--output", str(out)])
            # open is valid -- but kernel may not be present; either 0 or 2
            # Test bad pose separately:
        with tempfile.TemporaryDirectory() as tmp2:
            # argparse will reject unknown pose via choices -- SystemExit
            out2 = Path(tmp2) / "y"
            with self.assertRaises(SystemExit) as cm:
                hr.main(["build-hand", "--pose", "grip", "--output", str(out2)])
            self.assertNotEqual(cm.exception.code, 0)

    def test_valid_pose_names(self):
        hr = self._import()
        self.assertIn("open",    hr._VALID_POSES)
        self.assertIn("partial", hr._VALID_POSES)
        self.assertIn("closed",  hr._VALID_POSES)
        self.assertIn("pinch",   hr._VALID_POSES)
        self.assertEqual(len(hr._VALID_POSES), 4)

    def test_part_color_map_covers_21_parts(self):
        hr = self._import()
        expected = {"palm"} | {
            f"{f}_{s}"
            for f in ("index", "middle", "ring", "little", "thumb")
            for s in ("carrier", "proximal", "middle", "distal")
        }
        self.assertEqual(set(hr._PART_COLOR_MAP.keys()), expected)

    def test_carrier_color_is_blue_ish(self):
        hr = self._import()
        r, g, b = hr._CARRIER_COLOR
        # Blue carriers: b dominant
        self.assertGreater(b, r)
        self.assertGreater(b, g)

    def test_palm_phal_color_is_grey_ish(self):
        hr = self._import()
        r, g, b = hr._PALM_COLOR
        # Grey: all channels within 0.1 of each other
        self.assertLess(abs(r - g), 0.1)
        self.assertLess(abs(g - b), 0.1)


# ---------------------------------------------------------------------------
# Kernel tests (require CadQuery + NumPy)
# ---------------------------------------------------------------------------

try:
    import numpy as np
    import cadquery as cq
    _HAS_KERNEL = True
except ImportError:
    _HAS_KERNEL = False

_SKIP_MSG = "CadQuery/NumPy not available"


@unittest.skipUnless(_HAS_KERNEL, _SKIP_MSG)
class HandRuntimeOpenBuild(unittest.TestCase):
    """Build the open pose once and reuse across tests."""

    @classmethod
    def setUpClass(cls):
        import hand_runtime as hr
        cls.hr = hr
        cls.tmp = tempfile.mkdtemp()
        cls.out = Path(cls.tmp) / "open"
        try:
            cls.report = hr.build_hand_export("open", cls.out)
        except ValueError as exc:
            # If there are collisions the report is still written;
            # capture the error for collision tests
            cls.report_error = str(exc)
            val = cls.out / "validation.json"
            if val.exists():
                import json
                cls.report = json.loads(val.read_text(encoding="utf-8"))
            else:
                cls.report = None
        else:
            cls.report_error = None

    def test_validation_json_written(self):
        self.assertTrue((self.out / "validation.json").exists())

    def test_hand_step_written(self):
        self.assertTrue((self.out / "hand.step").exists())

    def test_21_source_parts(self):
        self.assertIsNotNone(self.report)
        self.assertEqual(self.report["part_count_source"], 21)

    def test_21_roundtrip_solids(self):
        self.assertIsNotNone(self.report)
        self.assertEqual(self.report["part_count_roundtrip"], 21)

    def test_geometry_roundtrip_passed(self):
        self.assertIsNotNone(self.report)
        self.assertTrue(
            self.report["geometry_roundtrip_passed"],
            "Roundtrip failed: " + str(self.report.get("roundtrip_results"))
        )

    def test_all_21_part_volumes_positive_finite(self):
        self.assertIsNotNone(self.report)
        for name, pr in self.report["parts"].items():
            with self.subTest(part=name):
                v = pr["volume_mm3"]
                self.assertTrue(math.isfinite(v), f"{name}: non-finite volume")
                self.assertGreater(v, 0, f"{name}: non-positive volume")

    def test_collision_pairs_checked_count(self):
        self.assertIsNotNone(self.report)
        self.assertEqual(self.report["collision_pairs_checked"], 210)

    def test_schema_fields_present(self):
        self.assertIsNotNone(self.report)
        for key in (
            "native_mates_verified", "actuation_verified",
            "fea_executed", "fabrication_ready",
            "name_roundtrip_verified", "color_appearance_verified",
        ):
            self.assertIn(key, self.report)
            self.assertFalse(self.report[key], f"{key} must be False")

    def test_20_joints_in_fk(self):
        self.assertIsNotNone(self.report)
        self.assertEqual(len(self.report["fk_angles_deg"]), 20)
        self.assertEqual(self.report["joint_count"], 20)

    def test_open_pose_all_angles_zero(self):
        self.assertIsNotNone(self.report)
        for jname, val in self.report["fk_angles_deg"].items():
            with self.subTest(joint=jname):
                self.assertEqual(val, 0.0)

    def test_step_sha256_is_64hex(self):
        self.assertIsNotNone(self.report)
        sha = self.report.get("step_sha256")
        self.assertIsNotNone(sha)
        self.assertEqual(len(sha), 64)
        int(sha, 16)  # raises if not hex

    def test_collision_free_open_pose_reported(self):
        """Open pose collision_free flag must be accurately reported (not assumed True)."""
        self.assertIsNotNone(self.report)
        # The flag must be present and be a boolean
        self.assertIsInstance(self.report["collision_free_sampled_pose"], bool)
        # Collision list must match the flag
        collisions = self.report.get("collisions", [])
        if self.report["collision_free_sampled_pose"]:
            self.assertEqual(collisions, [])
        else:
            # Report must list actual pairs with names and volumes
            self.assertGreater(len(collisions), 0)
            for c in collisions:
                self.assertIn("parts", c)
                self.assertEqual(len(c["parts"]), 2)
                self.assertIn("overlap_mm3", c)
                self.assertGreater(c["overlap_mm3"], 0)

    def test_existing_output_refused_after_first_build(self):
        """Second call to same output dir must raise FileExistsError."""
        with self.assertRaises(FileExistsError):
            self.hr.build_hand_export("open", self.out)

    def tearDown(self):
        pass  # keep output for inspection

    @classmethod
    def tearDownClass(cls):
        import shutil
        try:
            shutil.rmtree(cls.tmp)
        except Exception:
            pass


@unittest.skipUnless(_HAS_KERNEL, _SKIP_MSG)
class HandRuntimeCollisionReporting(unittest.TestCase):
    """Collision reporting: collisions must include real pair names and volumes."""

    def test_real_overlap_has_measured_volume(self):
        import cadquery as cq
        import hand_runtime as hr
        a = cq.Workplane("XY").box(1, 1, 1).val()
        b = a.translate(cq.Vector(0.5, 0, 0))
        rows = hr._check_all_collisions([("left", a), ("right", b)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["parts"], ["left", "right"])
        self.assertAlmostEqual(rows[0]["overlap_mm3"], 0.5, places=8)

    def test_invalid_boolean_result_is_not_clearance(self):
        from unittest.mock import Mock, patch
        import hand_runtime as hr
        a = Mock()
        a.intersect.return_value.isValid.return_value = False
        a.intersect.return_value.Volume.return_value = 0
        with patch.object(hr, "_aabb_overlap", return_value=True):
            with self.assertRaisesRegex(ValueError, "invalid Boolean result"):
                hr._check_all_collisions([("a", a), ("b", a)])

    def test_collision_check_helper_raises_on_kernel_error(self):
        """_check_all_collisions must raise ValueError on kernel failure."""
        import hand_runtime as hr

        class BadShape:
            def BoundingBox(self):
                class BB:
                    xmin = -1; xmax = 1; ymin = -1; ymax = 1; zmin = -1; zmax = 1
                return BB()
            def intersect(self, other):
                raise RuntimeError("kernel exploded")

        bad = BadShape()
        named = [("a", bad), ("b", bad)]
        with self.assertRaises(ValueError) as cm:
            hr._check_all_collisions(named)
        self.assertIn("kernel failure", str(cm.exception))

    def test_aabb_no_overlap_skips_boolean(self):
        """Parts whose bounding boxes don't overlap skip the Boolean call."""
        import hand_runtime as hr

        class FarShape:
            def __init__(self, offset):
                self._offset = offset
            def BoundingBox(self):
                o = self._offset
                class BB:
                    xmin = o; xmax = o + 1
                    ymin = 0; ymax = 1
                    zmin = 0; zmax = 1
                return BB()
            def intersect(self, other):
                raise AssertionError("Boolean should not be called for non-overlapping AABB")

        named = [("far_a", FarShape(0)), ("far_b", FarShape(1000))]
        result = hr._check_all_collisions(named)
        self.assertEqual(result, [])


@unittest.skipUnless(_HAS_KERNEL, _SKIP_MSG)
class HandRuntimePartialClosed(unittest.TestCase):
    """Test partial and closed poses produce valid reports."""

    @classmethod
    def setUpClass(cls):
        cls.tmp_dirs = {}
        cls.reports = {}
        cls.errors = {}
        import hand_runtime as hr
        import json
        for p in ("partial", "closed"):
            tmp = tempfile.mkdtemp()
            out = Path(tmp) / p
            cls.tmp_dirs[p] = (tmp, out)
            try:
                cls.reports[p] = hr.build_hand_export(p, out)
                cls.errors[p] = None
            except ValueError as exc:
                cls.errors[p] = str(exc)
                val = out / "validation.json"
                if val.exists():
                    cls.reports[p] = json.loads(val.read_text(encoding="utf-8"))
                else:
                    cls.reports[p] = None

    def test_partial_validation_json_exists(self):
        _, out = self.tmp_dirs["partial"]
        self.assertTrue((out / "validation.json").exists())

    def test_closed_validation_json_exists(self):
        _, out = self.tmp_dirs["closed"]
        self.assertTrue((out / "validation.json").exists())

    def test_partial_21_parts(self):
        r = self.reports.get("partial")
        self.assertIsNotNone(r)
        self.assertEqual(r["part_count_source"], 21)

    def test_closed_21_parts(self):
        r = self.reports.get("closed")
        self.assertIsNotNone(r)
        self.assertEqual(r["part_count_source"], 21)

    def test_partial_angles_nonzero(self):
        r = self.reports.get("partial")
        self.assertIsNotNone(r)
        nonzero = [v for v in r["fk_angles_deg"].values() if v != 0.0]
        self.assertGreater(len(nonzero), 0, "partial pose must have some nonzero angles")

    def test_closed_mcp_angles_greater_than_partial(self):
        rp = self.reports.get("partial")
        rc = self.reports.get("closed")
        if rp is None or rc is None:
            self.skipTest("Reports unavailable")
        self.assertGreater(
            rc["fk_angles_deg"]["index_mcp"],
            rp["fk_angles_deg"]["index_mcp"],
        )

    def test_closed_collision_flag_is_bool(self):
        r = self.reports.get("closed")
        self.assertIsNotNone(r)
        self.assertIsInstance(r["collision_free_sampled_pose"], bool)

    def test_closed_collisions_reported_with_pair_names(self):
        """If closed pose has collisions they must have pair names and volumes."""
        r = self.reports.get("closed")
        self.assertIsNotNone(r)
        for c in r.get("collisions", []):
            self.assertIn("parts", c)
            self.assertEqual(len(c["parts"]), 2)
            self.assertIn("overlap_mm3", c)
            self.assertTrue(math.isfinite(c["overlap_mm3"]))
            self.assertGreater(c["overlap_mm3"], 0)

    @classmethod
    def tearDownClass(cls):
        import shutil
        for tmp, _ in cls.tmp_dirs.values():
            try:
                shutil.rmtree(tmp)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
