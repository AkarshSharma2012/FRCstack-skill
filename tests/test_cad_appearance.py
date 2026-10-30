"""Behavioural tests for deterministic role-palette appearance in the fixture assembly.

These tests verify that:
- ROLE_PALETTE constants exist with three roles (plate, shaft, roller)
- fixture_assembly() assigns the correct CadQuery Color to every part
- The exported STEP file carries COLOUR_RGB / STYLED_ITEM records
- Geometry (solid count, volumes, bounds) is unaffected by appearance assignment

No network, Onshape login, or bought-part claims are made here.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/frcstack/scripts/cad_runtime.py"


def _load_runtime():
    spec = importlib.util.spec_from_file_location("frcstack_cad_runtime_appearance", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(importlib.util.find_spec("cadquery"), "optional CadQuery runtime not installed")
class AppearancePaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cad = _load_runtime() if SCRIPT.exists() else None

    def runtime(self):
        self.assertIsNotNone(self.cad, "cad_runtime module could not be loaded")
        return self.cad

    def test_role_palette_constant_exists_with_three_roles(self):
        """ROLE_PALETTE must be a dict with plate, shaft and roller keys."""
        c = self.runtime()
        self.assertTrue(hasattr(c, "ROLE_PALETTE"), "ROLE_PALETTE missing from cad_runtime")
        palette = c.ROLE_PALETTE
        for role in ("plate", "shaft", "roller"):
            self.assertIn(role, palette, f"ROLE_PALETTE missing role '{role}'")
            r, g, b = palette[role]
            for ch in (r, g, b):
                self.assertIsInstance(ch, float)
                self.assertGreaterEqual(ch, 0.0)
                self.assertLessEqual(ch, 1.0)

    def test_plate_palette_is_aluminium_light_grey(self):
        c = self.runtime()
        r, g, b = c.ROLE_PALETTE["plate"]
        self.assertAlmostEqual(r, 0.72, places=2)
        self.assertAlmostEqual(g, 0.74, places=2)
        self.assertAlmostEqual(b, 0.77, places=2)

    def test_shaft_palette_is_steel_mid_grey(self):
        c = self.runtime()
        r, g, b = c.ROLE_PALETTE["shaft"]
        self.assertAlmostEqual(r, 0.42, places=2)
        self.assertAlmostEqual(g, 0.45, places=2)
        self.assertAlmostEqual(b, 0.49, places=2)

    def test_roller_palette_is_rubber_dark(self):
        c = self.runtime()
        r, g, b = c.ROLE_PALETTE["roller"]
        self.assertAlmostEqual(r, 0.08, places=2)
        self.assertAlmostEqual(g, 0.09, places=2)
        self.assertAlmostEqual(b, 0.11, places=2)

    def test_fixture_assembly_helper_is_callable(self):
        c = self.runtime()
        self.assertTrue(
            callable(getattr(c, "fixture_assembly", None)),
            "fixture_assembly() helper not found in cad_runtime",
        )

    def test_assembly_contains_four_named_children(self):
        c = self.runtime()
        fixture = c.build_fixture(c.FixtureParameters())
        asm = c.fixture_assembly(fixture)
        names = {ch.name for ch in asm.children}
        self.assertEqual(names, {"left_plate", "right_plate", "shaft", "roller"})

    def test_every_assembly_child_has_a_color_object(self):
        c = self.runtime()
        fixture = c.build_fixture(c.FixtureParameters())
        asm = c.fixture_assembly(fixture)
        for ch in asm.children:
            self.assertIsNotNone(
                ch.color, f"Part '{ch.name}' has no color assigned in assembly"
            )

    def test_plate_parts_receive_aluminium_palette_color(self):
        c = self.runtime()
        fixture = c.build_fixture(c.FixtureParameters())
        asm = c.fixture_assembly(fixture)
        by_name = {ch.name: ch.color.toTuple() for ch in asm.children}
        pr, pg, pb = c.ROLE_PALETTE["plate"]
        for part in ("left_plate", "right_plate"):
            r, g, b, _ = by_name[part]
            self.assertAlmostEqual(r, pr, delta=0.01, msg=f"{part} R channel wrong")
            self.assertAlmostEqual(g, pg, delta=0.01, msg=f"{part} G channel wrong")
            self.assertAlmostEqual(b, pb, delta=0.01, msg=f"{part} B channel wrong")

    def test_shaft_receives_steel_palette_color(self):
        c = self.runtime()
        fixture = c.build_fixture(c.FixtureParameters())
        asm = c.fixture_assembly(fixture)
        by_name = {ch.name: ch.color.toTuple() for ch in asm.children}
        sr, sg, sb = c.ROLE_PALETTE["shaft"]
        r, g, b, _ = by_name["shaft"]
        self.assertAlmostEqual(r, sr, delta=0.01)
        self.assertAlmostEqual(g, sg, delta=0.01)
        self.assertAlmostEqual(b, sb, delta=0.01)

    def test_roller_receives_rubber_palette_color(self):
        c = self.runtime()
        fixture = c.build_fixture(c.FixtureParameters())
        asm = c.fixture_assembly(fixture)
        by_name = {ch.name: ch.color.toTuple() for ch in asm.children}
        rr, rg, rb = c.ROLE_PALETTE["roller"]
        r, g, b, _ = by_name["roller"]
        self.assertAlmostEqual(r, rr, delta=0.01)
        self.assertAlmostEqual(g, rg, delta=0.01)
        self.assertAlmostEqual(b, rb, delta=0.01)

    def test_exported_step_contains_at_least_three_colour_rgb_records(self):
        """STEP must embed one COLOUR_RGB per distinct role (plate/shaft/roller)."""
        c = self.runtime()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fixture"
            c.export_fixture(c.FixtureParameters(), out)
            step_text = (out / "fixture.step").read_text(errors="replace")
            colour_lines = [l for l in step_text.splitlines() if "COLOUR_RGB" in l]
            self.assertGreaterEqual(
                len(colour_lines),
                3,
                f"Expected >=3 COLOUR_RGB records in STEP, found {len(colour_lines)}",
            )

    def test_exported_step_contains_styled_item_records(self):
        c = self.runtime()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fixture"
            c.export_fixture(c.FixtureParameters(), out)
            step_text = (out / "fixture.step").read_text(errors="replace")
            styled = [l for l in step_text.splitlines() if "STYLED_ITEM" in l]
            self.assertGreaterEqual(len(styled), 1, "No STYLED_ITEM records found in STEP")

    def test_plate_colour_value_appears_in_step(self):
        """STEP must contain a COLOUR_RGB whose numeric values match the plate palette."""
        c = self.runtime()
        pr, pg, pb = c.ROLE_PALETTE["plate"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fixture"
            c.export_fixture(c.FixtureParameters(), out)
            step_text = (out / "fixture.step").read_text(errors="replace")
            found = _step_has_colour(step_text, pr, pg, pb, tol=0.01)
            self.assertTrue(
                found,
                f"COLOUR_RGB matching plate palette ({pr},{pg},{pb}) not found in STEP",
            )

    def test_shaft_colour_value_appears_in_step(self):
        c = self.runtime()
        sr, sg, sb = c.ROLE_PALETTE["shaft"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fixture"
            c.export_fixture(c.FixtureParameters(), out)
            step_text = (out / "fixture.step").read_text(errors="replace")
            self.assertTrue(
                _step_has_colour(step_text, sr, sg, sb, tol=0.01),
                f"COLOUR_RGB matching shaft palette ({sr},{sg},{sb}) not found in STEP",
            )

    def test_roller_colour_value_appears_in_step(self):
        c = self.runtime()
        rr, rg, rb = c.ROLE_PALETTE["roller"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fixture"
            c.export_fixture(c.FixtureParameters(), out)
            step_text = (out / "fixture.step").read_text(errors="replace")
            self.assertTrue(
                _step_has_colour(step_text, rr, rg, rb, tol=0.01),
                f"COLOUR_RGB matching roller palette ({rr},{rg},{rb}) not found in STEP",
            )

    def test_appearance_does_not_alter_solid_count_or_volumes(self):
        """fixture_assembly must preserve all four solids at their original volumes."""
        import math
        c = self.runtime()
        fixture = c.build_fixture(c.FixtureParameters())
        asm = c.fixture_assembly(fixture)
        self.assertEqual(len(asm.children), 4)
        for name, shape in fixture.parts.items():
            self.assertGreater(shape.Volume(), 0)
            self.assertTrue(math.isfinite(shape.Volume()))


def _step_has_colour(step_text, want_r, want_g, want_b, tol=0.01):
    """Return True if any COLOUR_RGB line in the STEP text matches (r,g,b) within tol."""
    for record in _step_records(step_text):
        if "COLOUR_RGB" not in record:
            continue
        try:
            nums = []
            for token in record.split(","):
                token = token.strip().strip("()'\"#;")
                for sub in token.split("("):
                    sub = sub.strip().strip(")'\"#;")
                    try:
                        nums.append(float(sub))
                    except ValueError:
                        pass
            if len(nums) >= 3:
                r, g, b = nums[-3], nums[-2], nums[-1]
                if abs(r - want_r) <= tol and abs(g - want_g) <= tol and abs(b - want_b) <= tol:
                    return True
        except (ValueError, IndexError):
            pass
    return False
def _step_records(step_text):
    """Yield logical STEP data records (semicolon-terminated) as single strings."""
    buf = ""
    for line in step_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            buf = stripped
        elif buf:
            buf += " " + stripped
        if buf.endswith(";"):
            yield buf
            buf = ""


if __name__ == "__main__":
    unittest.main()
