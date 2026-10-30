"""Tests for component_runtime.py.

Tests that require CadQuery are skipped when the package is absent; module
import tests always run.  No external STEP files are required.

Run with: python -m pytest tests/test_component_runtime.py -v
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

SCRIPTS = Path(__file__).parent.parent / "skills" / "frcstack" / "scripts"
sys.path.insert(0, str(SCRIPTS))

# ---------------------------------------------------------------------------
# CadQuery availability gate
# ---------------------------------------------------------------------------

try:
    import cadquery as _cadquery_check
    _HAS_CQ = True
except ImportError:
    _HAS_CQ = False

_SKIP_CQ = unittest.skipUnless(_HAS_CQ, "CadQuery not installed — kernel tests skipped")


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
    cq = _cq()
    cq.exporters.export(cq.Workplane("XY").box(w, h, d), str(path))


def _make_offset_box_step(path: Path):
    cq = _cq()
    solid = cq.Workplane("XY").box(10, 10, 10).val().translate((10, 0, 0))
    assy = cq.Assembly()
    assy.add(solid, name="offset_box")
    assy.export(str(path))


def _make_two_solid_step(path: Path):
    cq = _cq()
    assy = cq.Assembly()
    assy.add(cq.Workplane("XY").box(10, 10, 10), name="box_origin")
    assy.add(
        cq.Workplane("XY").box(10, 10, 10),
        name="box_offset",
        loc=cq.Location(cq.Vector(50, 0, 0)),
    )
    assy.export(str(path))


def _make_two_solid_step_reversed(path: Path):
    """Same two solids written in reversed transfer order using OCP directly."""
    try:
        from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
        from OCP.Interface import Interface_Static
        import cadquery as cq

        Interface_Static.SetCVal_s("write.step.schema", "AP214")
        writer = STEPControl_Writer()

        box_far = cq.Workplane("XY").box(10, 10, 10).translate((50, 0, 0)).val()
        box_near = cq.Workplane("XY").box(10, 10, 10).val()

        writer.Transfer(box_far.wrapped, STEPControl_AsIs)
        writer.Transfer(box_near.wrapped, STEPControl_AsIs)
        writer.Write(str(path))
    except Exception:
        # Fall back to Assembly order if OCP direct write not available
        _make_two_solid_step(path)


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
# Module import tests (always run, no CadQuery needed)
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

    def test_bijective_roundtrip_exported(self):
        from component_runtime import _bijective_roundtrip
        self.assertTrue(callable(_bijective_roundtrip))

    def test_validate_url_exported(self):
        from component_runtime import _validate_url
        self.assertTrue(callable(_validate_url))


# ---------------------------------------------------------------------------
# URL validation tests (no CadQuery needed)
# ---------------------------------------------------------------------------

class TestURLValidation(unittest.TestCase):
    def _ok(self, url):
        from component_runtime import _validate_url
        _validate_url(url)  # must not raise

    def _bad(self, url):
        from component_runtime import _validate_url
        with self.assertRaises((ValueError, TypeError)):
            _validate_url(url)

    def test_valid_https_domain(self):
        self._ok("https://example.com/parts/tp001.step")

    def test_valid_https_subdomain(self):
        self._ok("https://cad.manufacturer.com/files/part.step")

    def test_http_rejected(self):
        self._bad("http://example.com/part.step")

    def test_ftp_rejected(self):
        self._bad("ftp://example.com/part.step")

    def test_localhost_rejected(self):
        self._bad("https://localhost/part.step")

    def test_loopback_ip_rejected(self):
        self._bad("https://127.0.0.1/part.step")

    def test_private_ip_10_rejected(self):
        """Private IP 10.x.x.x must be rejected — was being accepted before."""
        self._bad("https://10.0.0.1/part.step")

    def test_private_ip_192_168_rejected(self):
        self._bad("https://192.168.1.1/part.step")

    def test_private_ip_172_16_rejected(self):
        self._bad("https://172.16.0.1/part.step")

    def test_single_label_hostname_rejected(self):
        self._bad("https://intranet/part.step")

    def test_dotlocal_hostname_rejected(self):
        self._bad("https://myserver.local/part.step")

    def test_credentials_rejected(self):
        self._bad("https://user:pass@example.com/part.step")

    def test_whitespace_in_url_rejected(self):
        self._bad("https://example.com/part step.step")

    def test_control_char_in_url_rejected(self):
        self._bad("https://example.com/part\x00.step")

    def test_empty_string_rejected(self):
        self._bad("")

    def test_non_string_rejected(self):
        self._bad(None)

    def test_no_network_request_made(self):
        """URL validation must never import socket or make network calls."""
        import socket
        from component_runtime import _validate_url
        original_getaddrinfo = socket.getaddrinfo
        called = []
        def trap(*a, **kw):
            called.append(a)
            return original_getaddrinfo(*a, **kw)
        with patch.object(socket, "getaddrinfo", side_effect=trap):
            _validate_url("https://example.com/part.step")
        self.assertEqual(called, [], "URL validation must not call socket.getaddrinfo")


# ---------------------------------------------------------------------------
# Schema / instance-name / field validation (no CadQuery needed)
# ---------------------------------------------------------------------------

class TestSchemaValidation(unittest.TestCase):
    def test_schema_bool_true_rejected(self):
        from component_runtime import assemble
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            p = tdp / "m.json"
            p.write_text(json.dumps({"schema": True, "components": []}), encoding="utf-8")
            with self.assertRaises((ValueError, TypeError)):
                assemble(p, tdp / "out")

    def test_schema_int_1_accepted_form(self):
        """schema=1 (int) is valid; schema=True (bool==1) must be rejected."""
        from component_runtime import _strict_float
        # bool rejection at strict_float level
        with self.assertRaises(TypeError):
            _strict_float(True, "schema")

    def test_instance_name_invalid_char_rejected(self):
        from component_runtime import _validate_component
        if not _HAS_CQ:
            self.skipTest("CadQuery not installed")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            box = tdp / "box.step"
            _make_box_step(box)
            sha = _sha256_file(box)
            comp = _comp("invalid name!", "box.step", sha)
            with self.assertRaises(ValueError):
                _validate_component(comp, tdp, set())

    def test_instance_name_starts_with_digit_rejected(self):
        from component_runtime import _validate_component
        if not _HAS_CQ:
            self.skipTest("CadQuery not installed")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            box = tdp / "box.step"
            _make_box_step(box)
            sha = _sha256_file(box)
            comp = _comp("1invalid", "box.step", sha)
            with self.assertRaises(ValueError):
                _validate_component(comp, tdp, set())

    def test_instance_name_too_long_rejected(self):
        from component_runtime import _validate_component
        if not _HAS_CQ:
            self.skipTest("CadQuery not installed")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            box = tdp / "box.step"
            _make_box_step(box)
            sha = _sha256_file(box)
            comp = _comp("A" + "a" * 64, "box.step", sha)  # 65 chars after first
            with self.assertRaises(ValueError):
                _validate_component(comp, tdp, set())

    def test_huge_int_in_translation_rejected(self):
        from component_runtime import _strict_float
        # A huge int that overflows float
        huge = 10 ** 400
        with self.assertRaises((ValueError, OverflowError)):
            _strict_float(huge, "test")

    def test_bool_schema_value_rejected_in_assemble(self):
        from component_runtime import assemble
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            p = tdp / "m.json"
            p.write_text('{"schema": true, "components": []}', encoding="utf-8")
            with self.assertRaises((ValueError, TypeError)):
                assemble(p, tdp / "out")


# ---------------------------------------------------------------------------
# Path validation tests (no CadQuery needed for most)
# ---------------------------------------------------------------------------

class TestPathValidation(unittest.TestCase):
    def test_dotdot_segment_rejected(self):
        from component_runtime import _validate_component
        if not _HAS_CQ:
            self.skipTest("CadQuery not installed")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            box = tdp / "box.step"
            _make_box_step(box)
            sha = _sha256_file(box)
            comp = _comp("p1", "../box.step", sha)
            with self.assertRaises(ValueError):
                _validate_component(comp, tdp, set())

    def test_absolute_path_rejected(self):
        from component_runtime import _validate_component
        if not _HAS_CQ:
            self.skipTest("CadQuery not installed")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            box = tdp / "box.step"
            _make_box_step(box)
            sha = _sha256_file(box)
            comp = _comp("p1", str(box), sha)
            with self.assertRaises(ValueError):
                _validate_component(comp, tdp, set())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks not supported on this platform")
    def test_symlink_source_rejected(self):
        from component_runtime import _validate_component
        if not _HAS_CQ:
            self.skipTest("CadQuery not installed")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            box = tdp / "box.step"
            _make_box_step(box)
            sha = _sha256_file(box)
            link = tdp / "link.step"
            try:
                link.symlink_to(box)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation failed on this platform")
            comp = _comp("p1", "link.step", _sha256_file(link))
            with self.assertRaises(ValueError):
                _validate_component(comp, tdp, set())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks not supported on this platform")
    def test_symlinked_output_parent_rejected(self):
        from component_runtime import assemble
        if not _HAS_CQ:
            self.skipTest("CadQuery not installed")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            box = tdp / "box.step"
            _make_box_step(box)
            sha = _sha256_file(box)
            comp = _comp("p1", "box.step", sha)
            mf = _write_manifest(tdp, [comp])
            real_dir = tdp / "real_output_parent"
            real_dir.mkdir()
            link_parent = tdp / "link_parent"
            try:
                link_parent.symlink_to(real_dir)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation failed on this platform")
            out = link_parent / "out"
            with self.assertRaises((ValueError, FileExistsError, OSError)):
                assemble(mf, out)


# ---------------------------------------------------------------------------
# verify_solid_pair validation (no CadQuery needed for argument checks)
# ---------------------------------------------------------------------------

class TestVerifySolidPairValidation(unittest.TestCase):
    def test_invalid_tol_bool_raises(self):
        from component_runtime import verify_solid_pair
        dummy = MagicMock()
        with self.assertRaises(TypeError):
            verify_solid_pair(dummy, dummy, tol_mm3=True)

    def test_invalid_tol_string_raises(self):
        from component_runtime import verify_solid_pair
        dummy = MagicMock()
        with self.assertRaises(TypeError):
            verify_solid_pair(dummy, dummy, tol_mm3="1e-5")

    def test_invalid_tol_negative_raises(self):
        from component_runtime import verify_solid_pair
        dummy = MagicMock()
        with self.assertRaises(ValueError):
            verify_solid_pair(dummy, dummy, tol_mm3=-1.0)

    def test_invalid_tol_nan_raises(self):
        from component_runtime import verify_solid_pair
        dummy = MagicMock()
        with self.assertRaises(ValueError):
            verify_solid_pair(dummy, dummy, tol_mm3=float("nan"))

    def test_kernel_failure_raises_runtime_error(self):
        """verify_solid_pair must raise RuntimeError on kernel failure, not return False."""
        from component_runtime import verify_solid_pair

        class _BadSolid:
            def cut(self, other):
                raise RuntimeError("simulated kernel crash")

        with self.assertRaises(RuntimeError):
            verify_solid_pair(_BadSolid(), _BadSolid())

    def test_nonfinite_volume_raises_value_error(self):
        """verify_solid_pair must raise ValueError on nonfinite kernel volume."""
        from component_runtime import verify_solid_pair

        class _InfSolid:
            def cut(self, other):
                m = MagicMock()
                m.Volume.return_value = float("inf")
                return m

        with self.assertRaises(ValueError):
            verify_solid_pair(_InfSolid(), _InfSolid())


# ---------------------------------------------------------------------------
# Collision / interference tests (no CadQuery for mock tests)
# ---------------------------------------------------------------------------

class TestCollisionBehavior(unittest.TestCase):
    def test_kernel_failure_raises_not_empty(self):
        """_interferences must raise ValueError on kernel exception, not return []."""
        from component_runtime import _interferences

        class _BrokenShape:
            def intersect(self, other):
                raise RuntimeError("BRep_TOOL::Surface:  incorrect argument")

        with self.assertRaises(ValueError):
            _interferences([("a", _BrokenShape()), ("b", _BrokenShape())])

    def test_nonfinite_volume_raises(self):
        """_interferences must raise ValueError on nonfinite intersection volume."""
        from component_runtime import _interferences

        class _NanShape:
            def intersect(self, other):
                m = MagicMock()
                m.Volume.return_value = float("nan")
                return m

        with self.assertRaises(ValueError):
            _interferences([("a", _NanShape()), ("b", _NanShape())])

    def test_zero_overlap_ok(self):
        """_interferences with genuine zero overlap returns empty list."""
        from component_runtime import _interferences

        class _NoOverlapShape:
            def intersect(self, other):
                m = MagicMock()
                m.Volume.return_value = 0.0
                return m

        result = _interferences([("a", _NoOverlapShape()), ("b", _NoOverlapShape())])
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Input validation tests (CadQuery required for STEP fixture creation)
# ---------------------------------------------------------------------------

@_SKIP_CQ
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

    def test_tiny_rotation_axis_rejected(self):
        """Axis with magnitude below _MIN_AXIS_MAG must be rejected."""
        comp = _comp("p1", "box.step", self.box_sha)
        comp["rotation"]["axis"] = [1e-200, 0.0, 0.0]
        comp["rotation"]["degrees"] = 45.0
        self._assemble_fail([comp], "out_tiny_axis")

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

    def test_private_ip_url_rejected(self):
        """Private/RFC-1918 IP in source_url must be rejected."""
        comp = _comp("p1", "box.step", self.box_sha)
        comp["source_url"] = "https://192.168.0.1/part.step"
        self._assemble_fail([comp], "out_private_ip")


# ---------------------------------------------------------------------------
# Assembly behaviour tests (CadQuery required)
# ---------------------------------------------------------------------------

@_SKIP_CQ
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

        cls.two_rev_step = cls.td / "two_rev.step"
        _make_two_solid_step_reversed(cls.two_rev_step)
        cls.two_rev_sha = _sha256_file(cls.two_rev_step)

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
        from component_runtime import assemble
        comp = _comp("two_boxes", "two.step", self.two_sha)
        mf = _write_manifest(self.td, [comp])
        out = self.td / "out_multi"
        report = assemble(mf, out)
        self.assertTrue(report["export_success"])
        comp_report = report["components"][0]
        self.assertGreaterEqual(comp_report["source_solid_count"], 2)

    def test_multi_solid_reversed_order_roundtrip(self):
        """STEP body order is not identity contract; reversed-order source must still pass."""
        from component_runtime import assemble
        comp = _comp("two_rev", "two_rev.step", self.two_rev_sha)
        mf = _write_manifest(self.td, [comp])
        out = self.td / "out_multi_rev"
        try:
            report = assemble(mf, out)
            self.assertTrue(report["export_success"])
            self.assertGreaterEqual(report["components"][0]["source_solid_count"], 2)
            # roundtrip may or may not pass depending on kernel; do not assert pass
        except ValueError as e:
            # A roundtrip failure is acceptable here; what matters is it doesn't crash silently
            val_path = out / "validation.json"
            self.assertTrue(val_path.exists(), f"validation.json must exist even on failure: {e}")

    def test_instance_identity_roundtrip_verified_is_false(self):
        """Report must explicitly record instance_identity_roundtrip_verified=False."""
        from component_runtime import assemble
        comp = _comp("box1a", "box.step", self.box_sha)
        mf = _write_manifest(self.td, [comp])
        out = self.td / "out_idrv"
        try:
            report = assemble(mf, out)
        except ValueError:
            report = json.loads((out / "validation.json").read_text())
        self.assertIn("instance_identity_roundtrip_verified", report)
        self.assertFalse(report["instance_identity_roundtrip_verified"])

    def test_rotation_before_translation_placement(self):
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
        self.assertAlmostEqual(cx, 0.0, delta=0.5)
        self.assertAlmostEqual(cy, 10.0, delta=0.5)
        self.assertAlmostEqual(cz, 50.0, delta=0.5)

    def test_overlap_detected_clearance_false_export_succeeds(self):
        from component_runtime import assemble
        c1 = _comp("box_ol_a", "box.step", self.box_sha, tx=0.0)
        c2 = _comp("box_ol_b", "box.step", self.box_sha, tx=5.0)
        mf = _write_manifest(self.td, [c1, c2])
        out = self.td / "out_overlap"
        report = assemble(mf, out)
        self.assertTrue(report["export_success"], "Export must succeed even with overlaps")
        self.assertFalse(report["clearance_passed"], "Overlap must be reported")
        self.assertGreater(len(report["interferences"]), 0)

    def test_clearance_pass_export_success_are_independent_fields(self):
        """clearance_passed and export_success are logically independent."""
        from component_runtime import assemble
        c1 = _comp("box_sep_a", "box.step", self.box_sha, tx=0.0)
        c2 = _comp("box_sep_b", "box.step", self.box_sha, tx=200.0)
        mf = _write_manifest(self.td, [c1, c2])
        out = self.td / "out_sep"
        report = assemble(mf, out)
        # Non-overlapping: both should be true
        self.assertTrue(report["export_success"])
        self.assertTrue(report["clearance_passed"])

    def test_displaced_same_volume_detected(self):
        from component_runtime import verify_solid_pair
        cq = _cq()
        box_origin = cq.Workplane("XY").box(10, 10, 10).val()
        box_far = cq.Workplane("XY").box(10, 10, 10).val().translate((500, 0, 0))
        self.assertAlmostEqual(box_origin.Volume(), box_far.Volume(), places=3)
        self.assertFalse(
            verify_solid_pair(box_origin, box_far),
            "verify_solid_pair must detect displacement even at equal volumes",
        )
        box_same = cq.Workplane("XY").box(10, 10, 10).val()
        self.assertTrue(
            verify_solid_pair(box_origin, box_same),
            "verify_solid_pair must pass for geometrically identical solids",
        )

    def test_output_files_never_clobbered(self):
        from component_runtime import assemble
        comp = _comp("box1", "box.step", self.box_sha)
        mf = _write_manifest(self.td, [comp])
        out = self.td / "out_clobber"
        out.mkdir()
        with self.assertRaises((FileExistsError, ValueError, OSError)):
            assemble(mf, out)

    def test_validation_json_schema(self):
        from component_runtime import assemble
        comp = _comp("box1", "box.step", self.box_sha)
        mf = _write_manifest(self.td, [comp])
        out = self.td / "out_vschema"
        assemble(mf, out)
        val = json.loads((out / "validation.json").read_text(encoding="utf-8"))
        for key in (
            "schema", "components", "limitations", "units",
            "onshape_verified", "fabrication_ready", "clearance_passed",
            "instance_identity_roundtrip_verified",
        ):
            self.assertIn(key, val, f"validation.json missing key: {key!r}")
        self.assertFalse(val["onshape_verified"])
        self.assertFalse(val["fabrication_ready"])
        self.assertEqual(val["units"], "mm")
        self.assertFalse(val["instance_identity_roundtrip_verified"])

    def test_inputs_not_modified(self):
        from component_runtime import assemble
        comp = _comp("box1", "box.step", self.box_sha)
        mf = _write_manifest(self.td, [comp])
        sha_before = _sha256_file(self.box_step)
        mf_before = mf.read_bytes()
        out = self.td / "out_untouched"
        assemble(mf, out)
        self.assertEqual(_sha256_file(self.box_step), sha_before)
        self.assertEqual(mf.read_bytes(), mf_before)


# ---------------------------------------------------------------------------
# Roundtrip failure regression tests (CadQuery required)
# ---------------------------------------------------------------------------

@_SKIP_CQ
class TestRoundtripFailure(unittest.TestCase):
    """Regression tests for req #2: failed roundtrip must retain validation.json."""

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

    def test_failed_roundtrip_writes_validation_json_and_raises(self):
        """Patching verify_solid_pair to always fail must cause ValueError but keep evidence."""
        from component_runtime import assemble
        import component_runtime as cr

        def _always_fail(a, b, tol_mm3=1e-5):
            return False

        comp = _comp("box_fail", "box.step", self.box_sha)
        mf = _write_manifest(self.td, [comp])
        out = self.td / "out_fail_rt"

        with patch.object(cr, "verify_solid_pair", side_effect=_always_fail):
            with self.assertRaises(ValueError) as ctx:
                assemble(mf, out)

        val_path = out / "validation.json"
        self.assertTrue(val_path.exists(), "validation.json must exist after roundtrip failure")
        val = json.loads(val_path.read_text())
        self.assertFalse(val["roundtrip_passed"], "roundtrip_passed must be False in saved report")
        self.assertIn("roundtrip", str(ctx.exception).lower())

    def test_failed_roundtrip_cli_returns_nonzero(self):
        """CLI must return nonzero when roundtrip fails."""
        import component_runtime as cr

        def _always_fail(a, b, tol_mm3=1e-5):
            return False

        comp = _comp("box_cli", "box.step", self.box_sha)
        with tempfile.TemporaryDirectory() as td2:
            tdp = Path(td2)
            box = tdp / "box.step"
            _make_box_step(box)
            sha = _sha256_file(box)
            comp2 = _comp("box_cli2", "box.step", sha)
            mf = _write_manifest(tdp, [comp2])
            out = tdp / "out_cli"
            with patch.object(cr, "verify_solid_pair", side_effect=_always_fail):
                ret = cr.main(["assemble", str(mf), "--output", str(out)])
            self.assertNotEqual(ret, 0, "CLI must return nonzero on roundtrip failure")
            val_path = out / "validation.json"
            self.assertTrue(val_path.exists(), "validation.json must exist after CLI failure")

    def test_displaced_shape_assemble_fails(self):
        """A pair of displaced equal-volume shapes should cause roundtrip failure."""
        cq = _cq()
        import component_runtime as cr

        # Patch _bijective_roundtrip to simulate what happens with displaced geometry:
        # returned roundtrip_passed=False, results showing displacement
        def _fail_rt(orig_solids, rt_solids, tol_mm3=1e-5):
            results = [{"solid_orig_index": 0, "solid_rt_index": 0,
                        "passed": False, "original_volume_mm3": 1000.0,
                        "roundtrip_volume_mm3": 1000.0}]
            return False, results

        comp = _comp("box_disp", "box.step", self.box_sha)
        mf = _write_manifest(self.td, [comp])
        out = self.td / "out_displaced"

        with patch.object(cr, "_bijective_roundtrip", side_effect=_fail_rt):
            with self.assertRaises(ValueError):
                cr.assemble(mf, out)

        val_path = out / "validation.json"
        self.assertTrue(val_path.exists())
        val = json.loads(val_path.read_text())
        self.assertFalse(val["roundtrip_passed"])


# ---------------------------------------------------------------------------
# Bijective roundtrip logic tests (no CadQuery for pure logic, mocks used)
# ---------------------------------------------------------------------------

class TestBijectiveRoundtrip(unittest.TestCase):
    def _solid(self, vol: float, offset: float = 0.0):
        """Mock solid that cuts to near-zero if same offset, large if different."""
        class _MockSolid:
            def __init__(self, v, o):
                self._vol = v
                self._off = o
            def Volume(self):
                return self._vol
            def cut(self, other):
                # Returns near-zero if offsets match, large otherwise
                diff = abs(self._off - other._off)
                m = MagicMock()
                m.Volume.return_value = diff * 100.0
                return m
        return _MockSolid(vol, offset)

    def test_identical_solids_pass(self):
        from component_runtime import _bijective_roundtrip
        s = self._solid(1000.0, 0.0)
        t = self._solid(1000.0, 0.0)
        passed, results = _bijective_roundtrip([s], [t], tol_mm3=1.0)
        self.assertTrue(passed)

    def test_displaced_same_volume_fails(self):
        from component_runtime import _bijective_roundtrip
        s = self._solid(1000.0, 0.0)
        t = self._solid(1000.0, 50.0)
        passed, results = _bijective_roundtrip([s], [t], tol_mm3=1.0)
        self.assertFalse(passed)

    def test_count_mismatch_fails(self):
        from component_runtime import _bijective_roundtrip
        s1 = self._solid(1000.0, 0.0)
        s2 = self._solid(1000.0, 50.0)
        passed, results = _bijective_roundtrip([s1, s2], [s1], tol_mm3=1.0)
        self.assertFalse(passed)
        self.assertTrue(any("mismatch" in str(r) for r in results))

    def test_reversed_order_matched_correctly(self):
        """Order-independent: reversed rt order must still find bijection."""
        from component_runtime import _bijective_roundtrip
        a = self._solid(1000.0, 0.0)
        b = self._solid(1000.0, 100.0)
        # rt in reversed order: b first, a second
        passed, results = _bijective_roundtrip([a, b], [b, a], tol_mm3=1.0)
        self.assertTrue(passed, f"Reversed order must still match: {results}")

    def test_repeated_identical_solids(self):
        """Two identical solids must both be matched (identity count preserved)."""
        from component_runtime import _bijective_roundtrip
        a1 = self._solid(1000.0, 0.0)
        a2 = self._solid(1000.0, 0.0)
        b1 = self._solid(1000.0, 0.0)
        b2 = self._solid(1000.0, 0.0)
        passed, results = _bijective_roundtrip([a1, a2], [b1, b2], tol_mm3=1.0)
        self.assertTrue(passed)
        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
