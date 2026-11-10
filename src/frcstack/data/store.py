"""Local SQLite evidence store for analyzed matches.

Every stored observation is scoped by program, season, and match, and keeps
the provenance it arrived with. Fields a legacy ledger never recorded
(``source``, ``confidence``, ``reviewed``, ``is_replay``) are stored as NULL
and can only lower a record's tier, never raise it. Stored evidence is
immutable: a correction is a new record that ``supersedes`` the old one.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from frcstack.schema import Observation

SUPPORTED_PROGRAMS = ("FRC", "FTC")
# VEX teams are alphanumeric (e.g. 1234A); schema.Observation is numeric-only.
UNSUPPORTED_PROGRAMS = ("VEX", "V5RC", "VIQRC", "VURC")
ENV_DB = "FRCSTACK_DB"
PROVENANCE_FIELDS = ("source", "confidence", "reviewed", "is_replay")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    match_pk INTEGER PRIMARY KEY,
    program TEXT NOT NULL,
    season TEXT NOT NULL,
    match_key TEXT NOT NULL,
    source_url TEXT,
    UNIQUE (program, season, match_key)
);
CREATE TABLE IF NOT EXISTS coverage (
    match_pk INTEGER NOT NULL REFERENCES matches(match_pk),
    team TEXT NOT NULL,
    PRIMARY KEY (match_pk, team)
);
CREATE TABLE IF NOT EXISTS observations (
    match_pk INTEGER NOT NULL REFERENCES matches(match_pk),
    obs_id TEXT NOT NULL,
    team TEXT NOT NULL,
    kind TEXT NOT NULL,
    start_s REAL NOT NULL,
    end_s REAL NOT NULL,
    visibility TEXT NOT NULL,
    evidence TEXT NOT NULL,
    source TEXT,
    confidence REAL,
    reviewed INTEGER,
    is_replay INTEGER,
    count INTEGER,
    outcome TEXT,
    points REAL,
    rule_ref TEXT,
    supersedes TEXT,
    extra TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (match_pk, obs_id)
);
CREATE INDEX IF NOT EXISTS observations_team ON observations(team);
"""

_COLUMNS = ("obs_id", "team", "kind", "start_s", "end_s", "visibility", "evidence",
            "source", "confidence", "reviewed", "is_replay", "count", "outcome",
            "points", "rule_ref", "supersedes", "extra")
_OBSERVATION_FIELDS = {f.name for f in dataclasses.fields(Observation)}


class UnsupportedProgramError(ValueError):
    """The program's team identities do not fit the numeric-only schema yet."""


def default_db_path() -> Path:
    """Evidence database path: ``$FRCSTACK_DB`` or ``.frcstack/evidence.db``."""
    return Path(os.environ.get(ENV_DB) or Path(".frcstack") / "evidence.db")


def normalize_program(value: object) -> str:
    """Return ``FRC`` or ``FTC``; raise for VEX (unsupported) and unknown programs."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("program is required (FRC or FTC)")
    program = value.strip().upper()
    if program in UNSUPPORTED_PROGRAMS:
        raise UnsupportedProgramError(
            "VEX team identities are alphanumeric (e.g. 1234A) and the evidence schema is "
            "numeric-only; VEX is unsupported until a team identity extension is implemented")
    if program not in SUPPORTED_PROGRAMS:
        raise ValueError(f"unknown program {value!r}; supported: {', '.join(SUPPORTED_PROGRAMS)}")
    return program


def normalize_season(value: object) -> str:
    """Return the season year when exactly one is present, else the trimmed text."""
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
        raise ValueError("season is required")
    text = str(value).strip()
    years = set(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", text))
    return years.pop() if len(years) == 1 else text.lower()


def _check_team(team: object) -> str:
    if not isinstance(team, str) or not team.isdigit() or int(team) <= 0:
        raise ValueError("team must be a positive team number as a string")
    return team


def _check_rules(obs: Observation) -> None:
    """Ledger rules from skills/frcstack/references/scouting.md."""
    if not isinstance(obs.kind, str) or not obs.kind:
        raise ValueError(f"{obs.id}: kind is required")
    if obs.count is not None and (type(obs.count) is not int or obs.count < 0):
        raise ValueError(f"{obs.id}: count must be a nonnegative integer")
    if obs.kind.endswith("_window") and (obs.count is None or obs.end_s <= obs.start_s):
        raise ValueError(f"{obs.id}: rate window needs an integer count and positive interval")
    if obs.outcome not in (None, "scored", "missed", "unknown"):
        raise ValueError(f"{obs.id}: invalid outcome")
    if obs.kind == "score" and obs.outcome is None:
        raise ValueError(f"{obs.id}: score outcome required")
    if obs.points is not None:
        numeric = not isinstance(obs.points, bool) and isinstance(obs.points, (int, float))
        if not numeric or not math.isfinite(obs.points) or obs.points < 0 or not (obs.rule_ref or "").strip():
            raise ValueError(f"{obs.id}: numeric points need a nonnegative value and rule reference")
    if obs.supersedes is not None and (not isinstance(obs.supersedes, str) or obs.supersedes == obs.id):
        raise ValueError(f"{obs.id}: supersedes must name a different earlier record")
    if type(obs.reviewed) is not bool or type(obs.is_replay) is not bool:
        raise ValueError(f"{obs.id}: reviewed and is_replay must be booleans")


def _ledger_observation(record: object) -> tuple[Observation, tuple[str, ...]]:
    """Build an Observation from a ledger dict and list its unrecorded provenance.

    Placeholders for unrecorded fields are the most conservative values, so the
    in-memory Observation can never claim more than the ledger did.
    """
    if not isinstance(record, dict):
        raise ValueError("each observation must be an object")
    if not isinstance(record.get("id"), str):
        raise ValueError("each observation needs a string id")
    unrecorded = tuple(name for name in PROVENANCE_FIELDS if record.get(name) is None)
    known = {k: v for k, v in record.items() if k in _OBSERVATION_FIELDS and k != "extra" and v is not None}
    extra = {k: v for k, v in record.items() if k not in _OBSERVATION_FIELDS}
    if isinstance(record.get("extra"), dict):
        extra.update(record["extra"])
    known.setdefault("source", "model")
    known.setdefault("reviewed", False)
    known.setdefault("is_replay", False)
    if "confidence" in unrecorded:
        known["confidence"] = 0.0
    try:
        return Observation(extra=extra, **known), unrecorded
    except TypeError as error:
        raise ValueError(f"{record['id'] or '<no id>'}: {error}") from None
    except AttributeError:
        raise ValueError(f"{record['id'] or '<no id>'}: evidence must be text") from None


@dataclass(frozen=True)
class EvidenceRecord:
    """One stored observation with its match scope and provenance gaps."""

    program: str
    season: str
    match_key: str
    source_url: str | None
    obs: Observation
    unrecorded: tuple[str, ...] = ()
    superseded_by: str | None = None

    def classify(self) -> tuple[str, str]:
        """Return ``(status, reason)``.

        status is ``verified``, ``estimate``, ``unresolved``, ``replay``, or
        ``superseded``. Only the first two may enter an aggregate.
        """
        obs = self.obs
        if self.superseded_by is not None:
            return "superseded", f"corrected by {self.superseded_by}"
        if "is_replay" in self.unrecorded:
            return "unresolved", "replay status not recorded"
        if obs.is_replay:
            return "replay", "replay footage is never counted"
        if obs.visibility != "direct":
            return "unresolved", f"visibility was {obs.visibility}"
        if self.source_url is None:
            return "unresolved", "no source URL recorded for this match"
        if obs.kind == "score" and obs.outcome == "unknown":
            return "unresolved", "score outcome unknown"
        if obs.reviewed:
            return "verified", "human-reviewed, direct view"
        if "source" in self.unrecorded or "confidence" in self.unrecorded:
            return "unresolved", "not reviewed; source/confidence not recorded"
        if obs.tier == "estimate":
            return "estimate", "unreviewed model output"
        if obs.source == "model":
            return "unresolved", "model confidence below the estimate threshold"
        return "unresolved", "human note not yet reviewed"

    def to_dict(self) -> dict:
        """JSON-ready evidence entry; unrecorded provenance is reported as null."""
        status, reason = self.classify()
        obs = self.obs
        provenance = {name: None if name in self.unrecorded else getattr(obs, name)
                      for name in PROVENANCE_FIELDS}
        return {
            "match_key": self.match_key, "source_url": self.source_url, "id": obs.id,
            "kind": obs.kind, "start_s": obs.start_s, "end_s": obs.end_s,
            "status": status, "reason": reason, "visibility": obs.visibility,
            **provenance, "count": obs.count, "outcome": obs.outcome, "points": obs.points,
            "rule_ref": obs.rule_ref, "supersedes": obs.supersedes, "evidence": obs.evidence,
        }


class EvidenceStore:
    """SQLite-backed evidence store. Use ``":memory:"`` for tests."""

    def __init__(self, path: str | Path = ":memory:", *, readonly: bool = False) -> None:
        if readonly:
            self._conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
        else:
            if str(path) != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(path))
            self._conn.executescript(_SCHEMA)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "EvidenceStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- writing -----------------------------------------------------------
    def add_match(self, program: str, season: object, match_key: str,
                  source_url: str | None = None, teams: Iterable[str] = ()) -> int:
        """Record an analyzed match and the teams known to be in it; idempotent."""
        with self._conn:
            return self._add_match(program, season, match_key, source_url, teams)

    def _add_match(self, program, season, match_key, source_url, teams) -> int:
        program, season = normalize_program(program), normalize_season(season)
        if not isinstance(match_key, str) or not match_key.strip():
            raise ValueError("match_key is required")
        if source_url is not None and (not isinstance(source_url, str) or not source_url.strip()):
            raise ValueError("source_url must be a nonempty string or omitted")
        if isinstance(teams, str):
            raise ValueError("teams must be a list of team numbers")
        teams = [_check_team(team) for team in teams]
        key = (program, season, match_key.strip())
        row = self._conn.execute(
            "SELECT match_pk, source_url FROM matches WHERE program=? AND season=? AND match_key=?",
            key).fetchone()
        if row is None:
            match_pk = self._conn.execute(
                "INSERT INTO matches (program, season, match_key, source_url) VALUES (?,?,?,?)",
                key + (source_url,)).lastrowid
        else:
            match_pk = row["match_pk"]
            if row["source_url"] != source_url:
                raise ValueError(
                    f"match {key[2]} is already stored with source {row['source_url']!r}; a second "
                    "source for the same match would double-count it")
        self._conn.executemany("INSERT OR IGNORE INTO coverage (match_pk, team) VALUES (?,?)",
                               [(match_pk, team) for team in teams])
        return match_pk

    def add_observations(self, program: str, season: object, match_key: str,
                         observations: Iterable[Observation], *, source_url: str | None = None,
                         teams: Iterable[str] = ()) -> dict:
        """Store fully-specified observations for one match (all-or-nothing)."""
        observations = list(observations)
        if not all(isinstance(obs, Observation) for obs in observations):
            raise ValueError("observations must be schema.Observation records")
        return self._store(program, season, match_key, source_url, teams,
                           [(obs, ()) for obs in observations])

    def import_ledger(self, ledger: object) -> dict:
        """Import a scouting ledger dict (legacy schema 1 or newer); idempotent.

        Missing provenance is stored as unrecorded, never defaulted to a value
        that would make a record look verified or estimated.
        """
        if not isinstance(ledger, dict):
            raise ValueError("ledger must be a JSON object")
        if not isinstance(ledger.get("observations"), list):
            raise ValueError("observations must be a list")
        match_key = ledger.get("match_key") or ledger.get("match_id")
        if not isinstance(match_key, str) or not match_key.strip():
            raise ValueError("ledger needs a match_id")
        event = ledger.get("event_id")
        if isinstance(event, str) and event.strip() and not match_key.startswith(event.strip()):
            match_key = f"{event.strip()}_{match_key.strip()}"
        source_url = ledger.get("source_url")
        if isinstance(source_url, str) and not source_url.strip():
            source_url = None
        rows = [_ledger_observation(record) for record in ledger["observations"]]
        return self._store(ledger.get("program"), ledger.get("season"), match_key, source_url,
                           ledger.get("teams") or (), rows)

    def _store(self, program, season, match_key, source_url, teams, rows) -> dict:
        result = {"inserted": 0, "unchanged": 0}
        with self._conn:  # one transaction: a bad record rolls the whole batch back
            match_pk = self._add_match(program, season, match_key, source_url, teams)
            for obs, unrecorded in rows:
                result[self._insert(match_pk, obs, unrecorded)] += 1
        return result

    def _insert(self, match_pk: int, obs: Observation, unrecorded: tuple[str, ...]) -> str:
        _check_rules(obs)
        try:
            extra = json.dumps(obs.extra, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError):
            raise ValueError(f"{obs.id}: extra fields must be JSON data") from None
        provenance = [None if name in unrecorded else value for name, value in (
            ("source", obs.source), ("confidence", float(obs.confidence)),
            ("reviewed", int(obs.reviewed)), ("is_replay", int(obs.is_replay)))]
        values = (obs.id, obs.team, obs.kind, float(obs.start_s), float(obs.end_s), obs.visibility,
                  obs.evidence, *provenance, obs.count, obs.outcome, obs.points, obs.rule_ref,
                  obs.supersedes, extra)
        existing = self._conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM observations WHERE match_pk=? AND obs_id=?",
            (match_pk, obs.id)).fetchone()
        if existing is not None:
            if tuple(existing) == values:
                return "unchanged"
            raise ValueError(f"{obs.id}: already stored with different content; evidence is "
                             "immutable, add a correction that supersedes it")
        if obs.supersedes is not None:
            old = self._conn.execute(
                "SELECT team, kind, (SELECT obs_id FROM observations s WHERE s.match_pk=o.match_pk "
                "AND s.supersedes=o.obs_id) AS replaced FROM observations o "
                "WHERE match_pk=? AND obs_id=?", (match_pk, obs.supersedes)).fetchone()
            if old is None or old["replaced"] or (old["team"], old["kind"]) != (obs.team, obs.kind):
                raise ValueError(f"{obs.id}: correction must replace an earlier active record "
                                 "for the same team/kind in the same match")
        self._conn.execute(
            f"INSERT INTO observations (match_pk, {', '.join(_COLUMNS)}) "
            f"VALUES (?{', ?' * len(_COLUMNS)})", (match_pk, *values))
        self._conn.execute("INSERT OR IGNORE INTO coverage (match_pk, team) VALUES (?,?)",
                           (match_pk, obs.team))
        return "inserted"

    # -- reading -----------------------------------------------------------
    def scopes(self, team: str) -> list[tuple[str, str]]:
        """Every (program, season) in which this team number has analyzed matches."""
        rows = self._conn.execute(
            "SELECT DISTINCT m.program, m.season FROM coverage c JOIN matches m USING (match_pk) "
            "WHERE c.team=? ORDER BY m.program, m.season", (team,)).fetchall()
        return [(row["program"], row["season"]) for row in rows]

    def matches_for(self, team: str, program: str, season: str) -> list[dict]:
        """Analyzed matches known to include the team within one program/season."""
        rows = self._conn.execute(
            "SELECT m.match_key, m.source_url FROM coverage c JOIN matches m USING (match_pk) "
            "WHERE c.team=? AND m.program=? AND m.season=? ORDER BY m.match_key",
            (team, program, season)).fetchall()
        return [dict(row) for row in rows]

    def records(self, team: str, program: str, season: str,
                kinds: Iterable[str] | None = None) -> list[EvidenceRecord]:
        """Stored evidence for one team in one program/season, in time order."""
        sql = ("SELECT m.program, m.season, m.match_key, m.source_url, o.*, "
               "(SELECT s.obs_id FROM observations s WHERE s.match_pk=o.match_pk "
               "AND s.supersedes=o.obs_id) AS superseded_by "
               "FROM observations o JOIN matches m USING (match_pk) "
               "WHERE o.team=? AND m.program=? AND m.season=?")
        params: list = [team, program, season]
        if kinds is not None:
            kinds = list(kinds)
            sql += f" AND o.kind IN ({', '.join('?' * len(kinds))})"
            params += kinds
        sql += " ORDER BY m.match_key, o.start_s, o.obs_id"
        return [self._record(row) for row in self._conn.execute(sql, params)]

    @staticmethod
    def _record(row: sqlite3.Row) -> EvidenceRecord:
        unrecorded = tuple(name for name in PROVENANCE_FIELDS if row[name] is None)
        obs = Observation(
            id=row["obs_id"], team=row["team"], kind=row["kind"], start_s=row["start_s"],
            end_s=row["end_s"], visibility=row["visibility"], evidence=row["evidence"],
            source=row["source"] or "model",
            confidence=0.0 if row["confidence"] is None else row["confidence"],
            reviewed=bool(row["reviewed"]), is_replay=bool(row["is_replay"]),
            count=row["count"], outcome=row["outcome"], points=row["points"],
            rule_ref=row["rule_ref"], supersedes=row["supersedes"], extra=json.loads(row["extra"]))
        return EvidenceRecord(row["program"], row["season"], row["match_key"], row["source_url"],
                              obs, unrecorded, row["superseded_by"])


def main(argv: list[str] | None = None) -> int:
    """``python -m frcstack.data.store import-ledger <ledger.json> [--db PATH]``."""
    parser = argparse.ArgumentParser(prog="frcstack.data.store", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    load = sub.add_parser("import-ledger", help="import a scouting ledger JSON file")
    load.add_argument("ledger", type=Path)
    load.add_argument("--db", type=Path, help=f"database path (default ${ENV_DB} or .frcstack/evidence.db)")
    args = parser.parse_args(argv)
    try:
        ledger = json.loads(args.ledger.read_text(encoding="utf-8-sig"))
        with EvidenceStore(args.db or default_db_path()) as store:
            result = store.import_ledger(ledger)
    except (ValueError, OSError, sqlite3.Error) as error:
        raise SystemExit(f"import failed: {error}") from None
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
