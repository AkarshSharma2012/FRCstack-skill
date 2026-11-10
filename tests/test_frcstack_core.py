import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcstack import cli, programs  # noqa: E402
from frcstack.schema import Observation, TrackPoint  # noqa: E402


def obs(**overrides):
    base = dict(id="o1", team="1899", kind="intake_window", start_s=1.0, end_s=3.0,
                visibility="direct", evidence="frames 30-90", count=2)
    base.update(overrides)
    return Observation(**base)


class SchemaTests(unittest.TestCase):
    def test_tiers(self):
        self.assertEqual(obs(reviewed=True).tier, "verified")
        self.assertEqual(obs(confidence=0.9).tier, "estimate")
        self.assertEqual(obs(confidence=0.3).tier, "unresolved")
        self.assertEqual(obs(visibility="occluded", reviewed=True).tier, "unresolved")
        self.assertEqual(obs(is_replay=True, reviewed=True).tier, "unresolved")
        self.assertEqual(obs(source="human", confidence=0.9).tier, "unresolved")

    def test_rejects_bad_records(self):
        for bad in (dict(team="abc"), dict(end_s=0.5), dict(confidence=1.5),
                    dict(evidence="  "), dict(start_s=float("nan"))):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                obs(**bad)

    def test_ledger_round_trip_drops_nones(self):
        record = obs(extra={"zone": "hub"}).to_ledger()
        self.assertNotIn("outcome", record)
        self.assertEqual(record["zone"], "hub")
        self.assertEqual(record["count"], 2)

    def test_trackpoint_validation(self):
        TrackPoint("2026wasam_qm1", 1, 0.0, 1.0, 2.0, 0.8)
        with self.assertRaises(ValueError):
            TrackPoint("k", 1, -1.0, 1.0, 2.0, 0.8)
        with self.assertRaises(ValueError):
            TrackPoint("k", 1, 0.0, 1.0, 2.0, 0.8, team="12a")


class CliTests(unittest.TestCase):
    def test_help_lists_seasons_and_never_crashes_on_missing_groups(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cli.main([]), 0)
        self.assertIn("seasons", out.getvalue())

    def test_seasons_json(self):
        out = io.StringIO()
        with redirect_stdout(out):
            cli.main(["seasons", "frc2026"])
        self.assertIn('"game": "REBUILT"', out.getvalue())

    def test_all_programs_present(self):
        self.assertEqual({s.program for s in programs.SEASONS.values()}, {"FRC", "FTC", "VEX"})
        with self.assertRaises(KeyError):
            programs.get_season("frc1999")


if __name__ == "__main__":
    unittest.main()
