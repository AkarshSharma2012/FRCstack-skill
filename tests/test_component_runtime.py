"""Tests for component_runtime.py.  Run RED before implementation; GREEN after.
All fixtures are kernel-generated temporary STEP files; no external files required.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "skills" / "frcstack" / "scripts"
sys.path.insert(0, str(SCRIPTS))


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _cq():
    import cadquery
    return cadquery


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_box_step(path: Path, w: float = 20.0, h: float = 15.0, d: float = 10.0):
    """Single-solid box centered at origin."""
    cq = _cq()
    cq.exporters.export(cq.Workplane("XY").box(w, h, d), str(path))


def _make_offset_box_step(path: Path):
    """Box with centroid at (10, 0, 0) so rotation is geometrically meaningful."""
    cq = _cq()
    solid = cq.Workplane("XY").box(10, 10, 10).val().translate((10, 0, 0))
    assy = cq.Assembly()
    assy.add(solid, name="offset_box")
    assy.export(str(path))


def _make_two_solid_step(path: Path):
    """Assembly STEP with two separate 10x10x10 boxes: one at origin, one at (50,0,0)."""
    cq = _cq()
    assy = cq.Assembly()
    assy.add(cq.Workplane("XY").box(10, 10, 10), name="box_origin")
    assy.add(
        cq.Workplane("XY").box(10, 10, 10),
        name="box_offset",
        loc=cq.Location(cq.Vector(50, 0, 0)),
    )
    assy.export(str(path))


def _comp(
    instance_name: str,
    file_str: str,
    sha256: str,
    tx: float = 0.0,
    ty: float = 0.0,
    tz: float = 0.0,
    ax: float = 0.0,
    ay: float = 0.0,
    az: float = 1.0,
    degrees: float = 0.0,
    manufacturer: str = "TestMfg",
    part_number: str = "TP-001",
    source_revision: str = "r1",
    source_url: str = "https://example.com/parts/tp001.step",
) -> dict:
    return {
        "instance_name": instance_name,
        "file": file_str,
        "sha256": sha256,
        "manufacturer": manufacturer,
        "part_number": part_number,
        "source_revision": source_revision,
        "source_url": source_url,
        "translation_mm": [tx, ty, tz],
        "rotation": {"axis": [ax, ay, az], "degrees": degrees},
    }


def _write_manifest(tmpdir: Path, components: list) -> Path:
    manifest = {"schema": 1, "components": components}
    p = tmpdir / "manifest.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Import smoke tests
# ---------------------------------------------------------------------------

class TestModuleImport(unittest.TestCase):
    def test_importable(self):
        import component_runtime  # noqa: F401

    def test_assemble_callable(self):
        from component_runtime import assemble
        self.assertTrue(callable(assemble))

    def test_verify_solid_pair_exported(self):
        from component_runtime import verify_solid_pair
        self.assertTrue(callable(verify_solid_pair))


# ---------------------------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------------------------

class TestInputValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        cls.td = Path(cls._td.name)
        cls.box_step = cls.td / "box.step"
        _make_box_step(cls.box_step)
        cls.box_sha = _sha256_file(cls.box_step)

    @classmethod
    def tearDownClass(cls):
        cls._td.cleanup()

    def _assemble_fail(self, components, out_name):
        from component_runtime import assemble
        mf = _write_manifest(self.td, components)
        with self.assertRaises((TypeError, ValueError, FileNotFoundError, OSError)):
            assemble(mf, self.td / out_name)

    def test_bool_in_translation_rejected(self):
        comp = _comp("p1", "box.step", self.box_sha)
        comp["translation_mm"] = [True, 0.0, 0.0]
        self._assemble_fail([comp], "out_bool_trans")

    def test_string_in_translation_rejected(self):
        comp = _comp("p1", "box.step", self.box_sha)
        comp["translation_mm"] = ["10", 0.0, 0.0]
        self._assemble_fail([comp], "out_str_trans")

    def test_nan_in_translation_rejected(self):
        comp = _comp("p1", "box.step", self.box_sha)
        comp["translation_mm"] = [float("nan"), 0.0, 0.0]
        self._assemble_fail([comp], "out_nan")

    def test_inf_in_translation_rejected(self):
        comp = _comp("p1", "box.step", self.box_sha)
        comp["translation_mm"] = [float("inf"), 0.0, 0.0]
        self._assemble_fail([comp], "out_inf")

    def test_translation_out_of_bounds_rejected(self):
        comp = _comp("p1", "box.step", self.box_sha, tx=20000.0)
        self._assemble_fail([comp], "out_oob")

    def test_path_traversal_rejected(self):
        comp = _comp("p1", "../box.step", self.box_sha)
        self._assemble_fail([comp], "out_traversal")

    def test_missing_file_rejected(self):
        comp = _comp("p1", "nonexistent.step", self.box_sha)
        self._assemble_fail([comp], "out_missing")

    def test_hash_mismatch_rejected(self):
        comp = _comp("p1", "box.step", "a" * 64)
        self._assemble_fail([comp], "out_hash")

    def test_duplicate_instance_name_rejected(self):
        c1 = _comp("dup", "box.step", self.box_sha)
        c2 = _comp("dup", "box.step", self.box_sha, tx=100.0)
        self._assemble_fail([c1, c2], "out_dup")

    def test_local_hostname_url_rejected(self):
        comp = _comp("p1", "box.step", self.box_sha)
        comp["source_url"] = "https://localhost/part.step"
        self._assemble_fail([comp], "out_local")

    def test_http_url_rejected(self):
        comp = _comp("p1", "box.step", self.box_sha)
        comp["source_url"] = "http://example.com/part.step"
        self._assemble_fail([comp], "out_http")

    def test_credentialed_url_rejected(self):
        comp = _comp("p1", "box.step", self.box_sha)
        comp["source_url"] = "https://user:pass@example.com/part.step"
        self._assemble_fail([comp], "out_cred")

    def test_zero_rotation_axis_rejected(self):
        comp = _comp("p1", "box.step", self.box_sha, ax=0.0, ay=0.0, az=0.0, degrees=45.0)
        self._assemble_fail([comp], "out_zero_axis")

    def test_empty_manufacturer_rejected(self):
        comp = _comp("p1", "box.step", self.box_sha)
        comp["manufacturer"] = ""
        self._assemble_fail([comp], "out_mfg")

    def test_existing_output_dir_rejected(self):
        from component_runtime import assemble
        comp = _comp("p1", "box.step", self.box_sha)
        mf = _write_manifest(self.td, [comp])
        existing = self.td / "out_existing"
        existing.mkdir()
        with self.assertRaises((FileExistsError, ValueError, OSError)):
            assemble(mf, existing)


# ---------------------------------------------------------------------------
# Assembly behaviour tests
# ---------------------------------------------------------------------------

class TestAssembly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        cls.td = Path(cls._td.name)

        cls.box_step = cls.td / "box.step"
        _make_box_step(cls.box_step, w=20, h=15, d=10)
        cls.box_sha = _sha256_file(cls.box_step)

        cls.offset_step = cls.td / "offset.step"
        _make_offset_box_step(cls.offset_step)
        cls.offset_sha = _sha256_file(cls.offset_step)

        cls.two_step = cls.td / "two.step"
        _make_two_solid_step(cls.two_step)
        cls.two_sha = _sha256_file(cls.two_step)

    @classmethod
    def tearDownClass(cls):
        cls._td.cleanup()

    def test_single_component_roundtrip(self):
        from component_runtime import assemble
        comp = _comp("box1", "box.step", self.box_sha)
        mf = _write_manifest(self.td, [comp])
        out = self.td / "out_single"
        report = assemble(mf, out)
        self.assertTrue((out / "assembly.step").exists())
        self.assertTrue((out / "validation.json").exists())
        self.assertTrue(report["export_success"])
        self.assertTrue(
            report["roundtrip_passed"],
            f"Roundtrip failed: {report.get('roundtrip_results')}",
        )

    def test_repeated_source_distinct_placements(self):
        from component_runtime import assemble
        c1 = _comp("box_a", "box.step", self.box_sha, tx=0.0)
        c2 = _comp("box_b", "box.step", self.box_sha, tx=200.0)
        mf = _write_manifest(self.td, [c1, c2])
        out = self.td / "out_repeated"
        report = assemble(mf, out)
        self.assertTrue(report["export_success"])
        self.assertEqual(report["component_count"], 2)
        self.assertTrue(
            report["roundtrip_passed"],
            f"Repeated parts roundtrip failed: {report.get('roundtrip_results')}",
        )

    def test_multi_solid_source_imports_all(self):
        """STEP with two separate solids: both must be imported per the instance."""
        from component_runtime import assemble
        comp = _comp("two_boxes", "two.step", self.two_sha)
        mf = _write_manifest(self.td, [comp])
        out = self.td / "out_multi"
        report = assemble(mf, out)
        self.assertTrue(report["export_success"])
        comp_report = report["components"][0]
        self.assertGreaterEqual(
            comp_report["source_solid_count"],
            2,
            "Expected at least 2 solids imported from two-solid STEP file",
        )

    def test_rotation_before_translation_placement(self):
        """Offset box centroid at (10,0,0): rotate 90 deg around Z -> (0,10,0),
        translate (0,0,50) -> final centroid (0,10,50).  Check independently."""
        from component_runtime import assemble
        comp = _comp(
            "offset1", "offset.step", self.offset_sha,
            tx=0.0, ty=0.0, tz=50.0,
            ax=0.0, ay=0.0, az=1.0, degrees=90.0,
        )
        mf = _write_manifest(self.td, [comp])
        out = self.td / "out_rot"
        report = assemble(mf, out)
        self.assertTrue(report["export_success"])
        self.assertTrue(
            report["roundtrip_passed"],
            f"Rotation roundtrip failed: {report.get('roundtrip_results')}",
        )
        bounds = report["components"][0]["bounds_mm"]
        cx = (bounds["xmin"] + bounds["xmax"]) / 2
        cy = (bounds["ymin"] + bounds["ymax"]) / 2
        cz = (bounds["zmin"] + bounds["zmax"]) / 2
        # Rodrigues: (10,0,0) rotated 90 deg CCW around Z -> (0,10,0); +tz=50 -> (0,10,50)
        self.assertAlmostEqual(cx, 0.0, delta=0.5, msg="cx after rotation+translation")
        self.assertAlmostEqual(cy, 10.0, delta=0.5, msg="cy after rotation+translation")
        self.assertAlmostEqual(cz, 50.0, delta=0.5, msg="cz after rotation+translation")

    def test_overlap_detected_clearance_false_export_succeeds(self):
        """Two partially-overlapping boxes: clearance_passed=False but export succeeds."""
        from component_runtime import assemble
        c1 = _comp("box_ol_a", "box.step", self.box_sha, tx=0.0)
        c2 = _comp("box_ol_b", "box.step", self.box_sha, tx=5.0)  # x-overlap: 10mm gap < 20mm box
        mf = _write_manifest(self.td, [c1, c2])
        out = self.td / "out_overlap"
        report = assemble(mf, out)
        self.assertTrue(report["export_success"], "Export must succeed even with overlaps")
        self.assertFalse(report["clearance_passed"], "Overlap must be reported")
        self.assertGreater(len(report["interferences"]), 0)

    def test_displaced_same_volume_detected(self):
        """verify_solid_pair must catch same-volume solids at different positions."""
        from component_runtime import verify_solid_pair
        cq = _cq()
        box_origin = cq.Workplane("XY").box(10, 10, 10).val()
        box_far = cq.Workplane("XY").box(10, 10, 10).val().translate((500, 0, 0))
        # Volumes identical
        self.assertAlmostEqual(box_origin.Volume(), box_far.Volume(), places=3)
        # But pair check must fail
        self.assertFalse(
            verify_solid_pair(box_origin, box_far),
            "verify_solid_pair must detect displacement even at equal volumes",
        )
        # Matching pair must pass
        box_same = cq.Workplane("XY").box(10, 10, 10).val()
        self.assertTrue(
            verify_solid_pair(box_origin, box_same),
            "verify_solid_pair must pass for geometrically identical solids",
        )

    def test_output_files_never_clobbered(self):
        """Existing output dir must be refused."""
        from component_runtime import assemble
        comp = _comp("box1", "box.step", self.box_sha)
        mf = _write_manifest(self.td, [comp])
        out = self.td / "out_clobber"
        out.mkdir()
        with self.assertRaises((FileExistsError, ValueError, OSError)):
            assemble(mf, out)

    def test_validation_json_schema(self):
        """validation.json must carry required provenance fields."""
        from component_runtime import assemble
        comp = _comp("box1", "box.step", self.box_sha)
        mf = _write_manifest(self.td, [comp])
        out = self.td / "out_vschema"
        assemble(mf, out)
        val = json.loads((out / "validation.json").read_text(encoding="utf-8"))
        for key in ("schema", "components", "limitations", "units",
                    "onshape_verified", "fabrication_ready", "clearance_passed"):
            self.assertIn(key, val, f"validation.json missing key: {key!r}")
        self.assertFalse(val["onshape_verified"])
        self.assertFalse(val["fabrication_ready"])
        self.assertEqual(val["units"], "mm")

    def test_inputs_not_modified(self):
        """Manifest and source STEP must be untouched after assembly."""
        from component_runtime import assemble
        comp = _comp("box1", "box.step", self.box_sha)
        mf = _write_manifest(self.td, [comp])
        sha_before = _sha256_file(self.box_step)
        mf_before = mf.read_bytes()
        out = self.td / "out_untouched"
        assemble(mf, out)
        self.assertEqual(_sha256_file(self.box_step), sha_before, "Source STEP must not change")
        self.assertEqual(mf.read_bytes(), mf_before, "Manifest must not change")


if __name__ == "__main__":
    unittest.main()
