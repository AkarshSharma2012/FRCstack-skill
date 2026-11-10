import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcstack import ask, cli  # noqa: E402
from frcstack.data.store import EvidenceStore  # noqa: E402

URL = "https://example.test/watch?v=qm12"
QUESTION = "pull up intake data on team 1899"


def record(**overrides):
    base = dict(id="i1", team="1899", kind="intake_window", start_s=10.0, end_s=14.0,
                visibility="direct", reviewed=True, is_replay=False,
                evidence="frames 300-420", count=6)
    base.update(overrides)
    return base


def model(**overrides):
    return record(**{"reviewed": False, "source": "model", "confidence": 0.8, **overrides})


def ledger(*observations, **overrides):
    base = dict(schema=1, program="FRC", season="2026", event_id="2026wasno",
                match_id="qm12", source_url=URL, observations=list(observations))
    base.update(overrides)
    return base


class AskTests(unittest.TestCase):
    def setUp(self):
        self.store = EvidenceStore()
        self.addCleanup(self.store.close)

    def ask(self, question=QUESTION, **kwargs):
        result = ask.answer(question, self.store, **kwargs)
        json.dumps(result, allow_nan=False)      # every answer must be JSON-ready
        self.assertIsInstance(ask.format_text(result), str)
        return result

    def test_empty_database_and_missing_database(self):
        for store in (self.store, None):
            result = ask.answer(QUESTION, store)
            self.assertEqual(result["status"], "no_analyzed_data")
            self.assertIsNone(result["human_reviewed"])
            self.assertIn("not zero", result["summary"])

    def test_unseen_team(self):
        self.store.import_ledger(ledger(record()))
        result = self.ask("intake data on team 254")
        self.assertEqual((result["status"], result["team"], result["evidence"]),
                         ("no_analyzed_data", "254", []))

    def test_valid_reviewed_intake(self):
        self.store.import_ledger(ledger(record(), record(id="i2", start_s=30.0, end_s=32.0, count=3)))
        result = self.ask()
        self.assertEqual((result["status"], result["program"], result["season"], result["topic"]),
                         ("human_reviewed", "FRC", "2026", "intake"))
        self.assertEqual(result["human_reviewed"],
                         {"records": 2, "matches": 1, "pieces": 9, "observed_active_s": 6.0,
                          "pieces_per_s": 1.5, "windows": 2})
        self.assertIsNone(result["model_estimate"])
        first = result["evidence"][0]
        self.assertEqual((first["match_key"], first["start_s"], first["end_s"], first["source_url"]),
                         ("2026wasno_qm12", 10.0, 14.0, URL))
        self.assertTrue(result["limitations"])
        self.assertIn("1.5 pieces/s", ask.format_text(result))

    def test_hidden_intake_is_insufficient_not_zero(self):
        self.store.import_ledger(ledger(record(visibility="occluded")))
        result = self.ask()
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["human_reviewed"])
        self.assertIsNone(result["model_estimate"])
        self.assertEqual(result["not_counted"], {"unresolved": 1})
        self.assertEqual((result["evidence"][0]["start_s"], result["evidence"][0]["counted"]), (10.0, False))
        self.assertIn("not zero", result["summary"])

    def test_covered_team_without_observations_is_insufficient(self):
        self.store.add_match("FRC", "2026", "2026wasno_qm3", URL, teams=["1899"])
        result = self.ask()
        self.assertEqual((result["status"], result["coverage"]["matches_analyzed"]),
                         ("insufficient_evidence", 1))

    def test_model_estimate_is_separate_from_reviewed(self):
        self.store.import_ledger(ledger(model(id="m1")))
        result = self.ask()
        self.assertEqual(result["status"], "model_estimate")
        self.assertIsNone(result["human_reviewed"])
        self.assertEqual(result["model_estimate"]["pieces_per_s"], 1.5)
        self.assertIn("do not add", result["limitations"][-1])
        self.store.import_ledger(ledger(record(id="h1", start_s=50.0, end_s=52.0, count=1), match_id="qm13"))
        result = self.ask()
        self.assertEqual(result["status"], "human_reviewed")
        self.assertEqual((result["human_reviewed"]["pieces"], result["model_estimate"]["pieces"]), (1, 6))

    def test_legacy_unreviewed_record_is_not_an_estimate(self):
        self.store.import_ledger(ledger(record(reviewed=False)))
        result = self.ask()
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["evidence"][0]["confidence"])

    def test_replays_are_not_counted(self):
        self.store.import_ledger(ledger(record(), record(id="rp", start_s=40.0, end_s=44.0, is_replay=True)))
        result = self.ask()
        self.assertEqual(result["human_reviewed"]["pieces"], 6)
        self.assertEqual(result["not_counted"], {"replay": 1})

    def test_superseded_records_are_not_counted(self):
        self.store.import_ledger(ledger(record(id="old", count=9), record(id="new", supersedes="old", count=5)))
        result = self.ask()
        self.assertEqual((result["human_reviewed"]["pieces"], result["human_reviewed"]["windows"]), (5, 1))
        self.assertEqual(result["not_counted"], {"superseded": 1})

    def test_overlapping_windows_are_not_double_counted(self):
        self.store.import_ledger(ledger(
            record(), record(id="dup", start_s=12.0, end_s=16.0, count=4),
            model(id="m-same", start_s=11.0, end_s=13.0, count=2),
            model(id="m-later", start_s=60.0, end_s=62.0, count=2)))
        result = self.ask()
        self.assertEqual((result["human_reviewed"]["pieces"], result["human_reviewed"]["observed_active_s"]), (6, 4.0))
        self.assertEqual((result["model_estimate"]["pieces"], result["model_estimate"]["windows"]), (2, 1))
        self.assertEqual(result["not_counted"], {"overlap": 2})

    def test_same_times_in_different_matches_both_count(self):
        self.store.import_ledger(ledger(record()))
        self.store.import_ledger(ledger(record(), match_id="qm20", source_url=URL + "b"))
        result = self.ask()
        self.assertEqual((result["human_reviewed"]["pieces"], result["human_reviewed"]["matches"]), (12, 2))

    def test_overlap_ids_are_scoped_to_match(self):
        self.store.import_ledger(ledger(record(id="first"), record(id="reused", start_s=11.0)))
        self.store.import_ledger(ledger(record(id="reused"), match_id="qm13"))
        result = self.ask()
        self.assertEqual(result["human_reviewed"]["pieces"], 12)
        self.assertEqual(result["not_counted"], {"overlap": 1})
        counted = [entry for entry in result["evidence"] if entry["counted"]]
        self.assertEqual(len(counted), 2)

    def test_bare_second_team_is_not_silently_ignored(self):
        result = self.ask("compare intake for team 1899 and 254")
        self.assertEqual(result["status"], "ambiguous")

    def test_ambiguous_program_or_season_asks_for_clarification(self):
        self.store.import_ledger(ledger(record()))
        self.store.import_ledger(ledger(record(count=1), program="FTC"))
        self.store.import_ledger(ledger(record(count=2), season="2025"))
        result = self.ask()
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(len(result["candidates"]), 3)
        self.assertNotIn("human_reviewed", result)
        self.assertEqual(self.ask("FRC " + QUESTION)["status"], "ambiguous")      # two FRC seasons
        self.assertEqual(self.ask(QUESTION + " in 2026")["status"], "ambiguous")  # FRC and FTC 2026
        self.assertEqual(self.ask("ftc " + QUESTION)["human_reviewed"]["pieces"], 1)
        self.assertEqual(self.ask(QUESTION + " frc 2025")["human_reviewed"]["pieces"], 2)
        self.assertEqual(self.ask("frc2026 " + QUESTION)["human_reviewed"]["pieces"], 6)
        self.assertEqual(self.ask(program="frc", season="2026")["human_reviewed"]["pieces"], 6)
        self.assertEqual(self.ask("frc 2024 " + QUESTION)["status"], "no_analyzed_data")

    def test_ambiguous_team(self):
        self.assertEqual(self.ask("intake for team 1899 and team 254")["status"], "ambiguous")
        self.assertEqual(self.ask("intake 2056 2026")["status"], "ambiguous")
        self.assertEqual(self.ask("frc and ftc intake team 1899")["status"], "ambiguous")
        self.assertEqual(self.ask("intake and scoring for team 1899")["status"], "ambiguous")

    def test_invalid_input(self):
        for question in ("", "   ", "pull up intake data", None, "intake data on team 0"):
            with self.subTest(question=question):
                self.assertEqual(ask.answer(question, self.store)["status"], "invalid")
        self.assertEqual(self.ask(program="XRC")["status"], "invalid")

    def test_vex_is_unsupported(self):
        for question in ("intake data on team 1234A", "vex intake data on team 1234",
                         "v5rc 2026 team 99999B scoring"):
            with self.subTest(question=question):
                self.assertEqual(self.ask(question)["status"], "unsupported")

    def test_question_parsing(self):
        parsed = ask.parse_question("How fast does 1899 shoot in 2026?")
        self.assertEqual((parsed["teams"], parsed["seasons"], parsed["topics"]), (["1899"], ["2026"], ["firing"]))
        self.assertEqual(ask.parse_question("intake data on 2026")["teams"], ["2026"])
        self.assertEqual(ask.parse_question("team 2026 intake in 2026")["seasons"], ["2026"])

    def test_scores_stay_robot_attributed(self):
        score = dict(kind="score", count=None, start_s=20.0, end_s=20.5)
        self.store.import_ledger(ledger(
            record(id="s1", outcome="scored", points=3, rule_ref="G1", **score),
            record(id="s2", outcome="scored", **{**score, "start_s": 25.0, "end_s": 25.5}),
            record(id="s3", outcome="missed", **{**score, "start_s": 28.0, "end_s": 28.5}),
            record(id="s4", outcome="unknown", **{**score, "start_s": 29.0, "end_s": 29.5}),
            record(id="s5", team="254", outcome="scored", points=50, rule_ref="G1", **score),
            record(id="al", kind="alliance_score", count=None, points=120, rule_ref="scoreboard"),
            alliance_score={"red": 120}))
        result = self.ask("scoring for team 1899")
        self.assertEqual(result["human_reviewed"],
                         {"records": 3, "matches": 1, "scored_events": 2, "missed_events": 1,
                          "video_observed_points_lower_bound": 3})
        self.assertEqual(result["not_counted"], {"unresolved": 1})
        self.assertTrue(any("alliance" in text for text in result["limitations"]))

    def test_overview_lists_evidence_without_mixing_rates(self):
        self.store.import_ledger(ledger(record(), record(id="f1", kind="fire_window", count=8)))
        result = self.ask("what do we have on team 1899")
        self.assertEqual((result["topic"], result["status"]), ("overview", "human_reviewed"))
        self.assertEqual(result["human_reviewed"], {"records": 2, "matches": 1})


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_cli_text_json_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "evidence.db"
            code, text = self.run_cli("ask", QUESTION, "--db", str(db))
            self.assertEqual(code, 0)
            self.assertIn("no analyzed data", text)
            self.assertFalse(db.exists())            # asking never creates a database
            with EvidenceStore(db) as store:
                store.import_ledger(ledger(record()))
            code, text = self.run_cli("ask", QUESTION, "--db", str(db), "--json")
            payload = json.loads(text)
            self.assertEqual((code, payload["status"], payload["human_reviewed"]["pieces_per_s"]),
                             (0, "human_reviewed", 1.5))
            code, text = self.run_cli("ask", QUESTION, "--db", str(db))
            self.assertEqual(code, 0)
            self.assertIn("frames 300-420", text)
            self.assertTrue(text.isascii())
            code, text = self.run_cli("ask", "intake", "data", "on", "team", "1234A", "--db", str(db))
            self.assertEqual(code, 2)
            self.assertIn("unsupported", text)


if __name__ == "__main__":
    unittest.main()
