import copy
import importlib.util
import unittest
from pathlib import Path

script = Path(__file__).resolve().parents[1] / "skills/frcstack/scripts/summarize_scouting.py"
spec = importlib.util.spec_from_file_location("scout", script)
scout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scout)

def ledger():
    return {"schema": 1, "program": "FRC", "season": "test-season", "event_id": "fixture", "match_id": "fixture-q1", "source_url": "synthetic-fixture-not-a-real-video", "observations": []}

def record(**kwargs):
    return {"id": "a", "team": "1234", "kind": "intake_window", "start_s": 10, "end_s": 14, "count": 12, "visibility": "direct", "reviewed": True, "is_replay": False, "evidence": "Synthetic test fixture", **kwargs}

class ScoutTests(unittest.TestCase):
    def test_rate_denominator_is_observed_active_interval(self):
        data = ledger(); data["observations"] = [record()]
        result = scout.summarize(data)["teams"]["1234"]
        self.assertEqual(result["intake"]["pieces_per_s"], 3)
        self.assertIsNone(result["video_observed_points_lower_bound"])

    def test_occlusion_is_unknown_not_zero(self):
        data = ledger(); data["observations"] = [record(visibility="occluded")]
        result = scout.summarize(data)["teams"]["1234"]
        self.assertIsNone(result["intake"])
        self.assertEqual(result["unresolved_records"], 1)

    def test_replay_is_excluded(self):
        data = ledger(); data["observations"] = [record(is_replay=True)]
        result = scout.summarize(data)["teams"]["1234"]
        self.assertIsNone(result["intake"])
        self.assertEqual(result["excluded_replays"], 1)

    def test_overlap_and_duplicate_ids_are_rejected(self):
        for second in [record(), record(id="b", start_s=12)]:
            data = ledger(); data["observations"] = [record(), second]
            with self.assertRaises(ValueError): scout.summarize(data)

    def test_corrected_record_does_not_double_count(self):
        data = ledger(); data["observations"] = [record(), record(id="b", count=8, supersedes="a")]
        result = scout.summarize(data)
        self.assertEqual(result["teams"]["1234"]["intake"]["visible_count"], 8)
        self.assertEqual(result["superseded_records"], 1)

    def test_points_need_rule_evidence(self):
        data = ledger(); data["observations"] = [record(kind="score", outcome="scored", points=5)]
        with self.assertRaises(ValueError): scout.summarize(data)
        data["observations"][0]["rule_ref"] = "synthetic-fixture-rule"
        self.assertEqual(scout.summarize(data)["teams"]["1234"]["video_observed_points_lower_bound"], 5)

    def test_motor_and_capacity_observations_do_not_invent_totals(self):
        data = ledger(); data["observations"] = [record(kind="visible_motors"), record(id="b",kind="capacity_lower_bound")]
        result = scout.summarize(data)["teams"]["1234"]
        self.assertIsNone(result["video_observed_points_lower_bound"])
        self.assertNotIn("total_motor_count", result)
        self.assertNotIn("hopper_capacity", result)

    def test_invalid_time_and_nonfinite_counts_rejected(self):
        for change in [{"start_s": -1}, {"end_s": 10}, {"count": float("nan")}, {"count": True}]:
            data = ledger(); data["observations"] = [record(**change)]
            with self.assertRaises(ValueError): scout.summarize(data)

    def test_unknown_match_or_wrong_team_correction_rejected(self):
        data = ledger(); data["match_id"] = None
        with self.assertRaises(ValueError): scout.summarize(data)
        data = ledger(); data["observations"] = [record(), record(id="b",team="9999",supersedes="a")]
        with self.assertRaises(ValueError): scout.summarize(data)

if __name__ == "__main__": unittest.main()
