import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcstack.data import EvidenceStore, UnsupportedProgramError  # noqa: E402
from frcstack.data import store as store_module  # noqa: E402
from frcstack.schema import Observation  # noqa: E402

URL = "https://example.test/watch?v=qm12"


def record(**overrides):
    base = dict(id="i1", team="1899", kind="intake_window", start_s=10.0, end_s=14.0,
                visibility="direct", reviewed=True, is_replay=False,
                evidence="frames 300-420", count=6)
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def ledger(*observations, **overrides):
    base = dict(schema=1, program="FRC", season="2026", event_id="2026wasno",
                match_id="qm12", source_url=URL, observations=list(observations))
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def statuses(store, team="1899", kinds=None):
    return {r.obs.id: r.classify()[0] for r in store.records(team, "FRC", "2026", kinds)}


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.store = EvidenceStore()
        self.addCleanup(self.store.close)

    def test_empty_store_has_nothing(self):
        self.assertEqual(self.store.scopes("1899"), [])
        self.assertEqual(self.store.matches_for("1899", "FRC", "2026"), [])
        self.assertEqual(self.store.records("1899", "FRC", "2026"), [])

    def test_import_stores_match_scope_and_source(self):
        self.assertEqual(self.store.import_ledger(ledger(record())), {"inserted": 1, "unchanged": 0})
        self.assertEqual(self.store.scopes("1899"), [("FRC", "2026")])
        self.assertEqual(self.store.matches_for("1899", "FRC", "2026"),
                         [{"match_key": "2026wasno_qm12", "source_url": URL}])
        (stored,) = self.store.records("1899", "FRC", "2026")
        self.assertEqual((stored.obs.count, stored.obs.start_s, stored.source_url), (6, 10.0, URL))
        self.assertEqual(stored.classify()[0], "verified")

    def test_import_is_idempotent(self):
        data = ledger(record(), record(id="i2", start_s=20.0, end_s=22.0, supersedes="i1"))
        self.store.import_ledger(copy.deepcopy(data))
        self.assertEqual(self.store.import_ledger(copy.deepcopy(data)), {"inserted": 0, "unchanged": 2})
        self.assertEqual(len(self.store.records("1899", "FRC", "2026")), 2)

    def test_changed_content_for_same_id_is_rejected(self):
        self.store.import_ledger(ledger(record()))
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.store.import_ledger(ledger(record(count=60)))
        self.assertEqual(self.store.records("1899", "FRC", "2026")[0].obs.count, 6)

    def test_legacy_record_does_not_gain_source_or_confidence(self):
        self.store.import_ledger(ledger(record(reviewed=False)))
        (stored,) = self.store.records("1899", "FRC", "2026")
        self.assertEqual(stored.unrecorded, ("source", "confidence"))
        entry = stored.to_dict()
        self.assertIsNone(entry["source"])
        self.assertIsNone(entry["confidence"])
        # schema defaults (model, 1.0) would have made this an "estimate"
        self.assertEqual(entry["status"], "unresolved")

    def test_missing_review_or_replay_fields_never_verify(self):
        self.store.import_ledger(ledger(record(id="a", reviewed=None),
                                        record(id="b", start_s=20.0, end_s=22.0, is_replay=None)))
        self.assertEqual(statuses(self.store), {"a": "unresolved", "b": "unresolved"})

    def test_missing_source_url_never_verifies(self):
        self.store.import_ledger(ledger(record(), source_url=None))
        (stored,) = self.store.records("1899", "FRC", "2026")
        self.assertIsNone(stored.source_url)
        self.assertEqual(stored.classify(), ("unresolved", "no source URL recorded for this match"))

    def test_recorded_model_provenance_is_kept(self):
        self.store.import_ledger(ledger(record(id="m1", reviewed=False, source="model", confidence=0.8),
                                        record(id="m2", start_s=30.0, end_s=31.0, reviewed=False,
                                               source="model", confidence=0.2)))
        self.assertEqual(statuses(self.store), {"m1": "estimate", "m2": "unresolved"})

    def test_replay_and_superseded_status(self):
        self.store.import_ledger(ledger(
            record(id="old"), record(id="new", supersedes="old", count=5),
            record(id="rp", start_s=40.0, end_s=44.0, is_replay=True)))
        self.assertEqual(statuses(self.store), {"old": "superseded", "new": "verified", "rp": "replay"})

    def test_bad_corrections_are_rejected(self):
        for bad in (record(id="x", supersedes="missing"),
                    record(id="x", supersedes="i1", team="254"),
                    record(id="x", supersedes="i1", kind="fire_window")):
            with self.assertRaises(ValueError):
                self.store.import_ledger(ledger(record(), bad))
        self.store.import_ledger(ledger(record(), record(id="c1", supersedes="i1")))
        with self.assertRaisesRegex(ValueError, "earlier active record"):
            self.store.import_ledger(ledger(record(id="c2", supersedes="i1")))

    def test_invalid_ledgers_roll_back_completely(self):
        bad_records = (
            record(id="bad", team="12A"), record(id="bad", end_s=5.0), record(id="bad", count=None),
            record(id="bad", count=1.5), record(id="bad", visibility="hidden"),
            record(id="bad", evidence=" "), record(id="bad", reviewed="yes"),
            record(id="bad", confidence=2.0), record(id="bad", source="rumor"),
            record(id="bad", kind="score"), record(id="bad", kind="score", outcome="scored", points=3),
            record(id=7), "not an object",
        )
        for bad in bad_records:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.store.import_ledger(ledger(record(id="good", start_s=50.0, end_s=51.0), bad))
        for broken in (ledger(record(), program=None), ledger(record(), season=None),
                       ledger(record(), match_id=None), ledger(record(), program="XRC"),
                       {"program": "FRC"}, [], None):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                self.store.import_ledger(broken)
        self.assertEqual(self.store.scopes("1899"), [])

    def test_vex_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(UnsupportedProgramError, "alphanumeric"):
            self.store.import_ledger(ledger(record(), program="VEX"))
        with self.assertRaises(UnsupportedProgramError):
            self.store.add_match("v5rc", "2026", "q1")

    def test_same_team_number_is_scoped_by_program_and_season(self):
        self.store.import_ledger(ledger(record()))
        self.store.import_ledger(ledger(record(count=1), program="FTC"))
        self.store.import_ledger(ledger(record(count=2), season="2025"))
        self.assertEqual(self.store.scopes("1899"), [("FRC", "2025"), ("FRC", "2026"), ("FTC", "2026")])
        self.assertEqual([r.obs.count for r in self.store.records("1899", "FTC", "2026")], [1])

    def test_second_source_for_same_match_is_rejected(self):
        self.store.import_ledger(ledger(record()))
        with self.assertRaisesRegex(ValueError, "double-count"):
            self.store.import_ledger(ledger(record(id="other"), source_url="https://example.test/mirror"))

    def test_coverage_without_observations(self):
        self.store.add_match("FRC", 2026, "2026wasno_qm3", URL, teams=["1899", "254"])
        self.assertEqual(self.store.scopes("254"), [("FRC", "2026")])
        self.assertEqual(self.store.records("254", "FRC", "2026"), [])
        with self.assertRaises(ValueError):
            self.store.add_match("FRC", 2026, "2026wasno_qm4", URL, teams=["99A"])

    def test_add_observations_uses_schema_records(self):
        obs = Observation(id="v1", team="1899", kind="fire_window", start_s=1.0, end_s=3.0,
                          visibility="direct", evidence="frames 30-90", confidence=0.9, count=4)
        result = self.store.add_observations("FRC", "2026", "2026wasno_qm9", [obs], source_url=URL)
        self.assertEqual(result, {"inserted": 1, "unchanged": 0})
        (stored,) = self.store.records("1899", "FRC", "2026")
        self.assertEqual(stored.obs, obs)
        self.assertEqual((stored.unrecorded, stored.classify()[0]), ((), "estimate"))
        with self.assertRaises(ValueError):
            self.store.add_observations("FRC", "2026", "2026wasno_qm9", [{"id": "dict"}])


class FileTests(unittest.TestCase):
    def test_file_round_trip_readonly_and_cli(self):
        import io
        import json
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "nested dir" / "evidence.db"
            ledger_path = Path(folder) / "ledger.json"
            ledger_path.write_text(json.dumps(ledger(record())), encoding="utf-8")
            for expected in ({"inserted": 1, "unchanged": 0}, {"inserted": 0, "unchanged": 1}):
                out = io.StringIO()
                with redirect_stdout(out):
                    code = store_module.main(["import-ledger", str(ledger_path), "--db", str(db)])
                self.assertEqual((code, json.loads(out.getvalue())), (0, expected))
            with EvidenceStore(db, readonly=True) as reader:
                self.assertEqual(len(reader.records("1899", "FRC", "2026")), 1)
                with self.assertRaises(Exception):
                    reader.add_match("FRC", "2026", "x", URL)
            ledger_path.write_text("{}", encoding="utf-8")
            with self.assertRaises(SystemExit):
                store_module.main(["import-ledger", str(ledger_path), "--db", str(db)])


if __name__ == "__main__":
    unittest.main()
