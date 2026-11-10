"""Answer plain-English questions about a team from the local evidence store.

``frcstack ask "pull up intake data on team 1899"`` reads stored evidence only:
no network and no language model. The answer separates human-reviewed
observations from model estimates, lists the evidence timestamps behind every
number, and says so when there is no analyzed data or not enough evidence.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from frcstack.data.store import (EvidenceRecord, EvidenceStore, UnsupportedProgramError,
                                 default_db_path, normalize_program, normalize_season)

# topic -> (question words, observation kinds)
TOPICS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "intake": (("intake", "intaking", "pickup", "pick up", "collect"), ("intake_window",)),
    "firing": (("fire", "firing", "shoot", "shooting", "shooter", "launch"), ("fire_window",)),
    "scoring": (("score", "scores", "scoring", "points"), ("score",)),
    "climb": (("climb", "climbing", "endgame"), ("climb",)),
    "defense": (("defense", "defence", "defending"), ("defense_played", "defense_received")),
    "struggles": (("struggle", "struggles", "jam", "spill", "problems"), ("struggle", "spill", "disabled")),
}
RATE_KINDS = ("intake_window", "fire_window")
STATUS_TEXT = {
    "human_reviewed": "human-reviewed observations",
    "model_estimate": "model estimates only (not human-reviewed)",
    "insufficient_evidence": "insufficient evidence (analyzed, but nothing countable)",
    "no_analyzed_data": "no analyzed data",
    "ambiguous": "clarification needed",
    "unsupported": "unsupported",
    "invalid": "invalid question",
}
LIMITATIONS = (
    "Rates cover only the listed observed windows; time the robot was not seen is unknown, not zero.",
    "Only observations attributed to this robot are used; alliance scoreboard totals are not "
    "robot contributions and are never used.",
    "Interval-specific observations, not a maximum capability or an official score.",
)

_YEAR = r"(?:19|20)\d{2}"
_PROGRAM_RE = re.compile(rf"\b(frc|ftc|vex|v5rc|viqrc|vurc)[\s-]*({_YEAR})?\b", re.I)
_TEAM_RE = re.compile(r"\bteams?\s*#?\s*([A-Za-z]*\d\w*)", re.I)
_NUMBER_RE = re.compile(r"(?<![\w.])\d+[A-Za-z]?(?!\w|\.\d)")


class _Clarify(Exception):
    """The question cannot be answered as asked; carries status and message."""

    def __init__(self, status: str, message: str, **details) -> None:
        super().__init__(message)
        self.status, self.message, self.details = status, message, details


def parse_question(question: str) -> dict:
    """Extract team, program, season, and topic from a question.

    Returns lists of candidates for team/program/season so the caller can ask
    for clarification instead of guessing.
    """
    text = question if isinstance(question, str) else ""
    programs, seasons, teams = [], [], []
    for match in _PROGRAM_RE.finditer(text):
        name = match.group(1).upper()
        programs.append("VEX" if name in ("V5RC", "VIQRC", "VURC") else name)
        if match.group(2):
            seasons.append(match.group(2))
    rest = _PROGRAM_RE.sub(" ", text)
    teams += [match.group(1) for match in _TEAM_RE.finditer(rest)]
    rest = _TEAM_RE.sub(" ", rest)
    numbers = _NUMBER_RE.findall(rest)
    years = [n for n in numbers if re.fullmatch(_YEAR, n)]
    others = [n for n in numbers if n not in years]
    if teams:
        teams += others
        seasons += years
    elif others:
        teams, seasons = others, seasons + years
    else:
        teams = years            # "data on 2026": a lone number is the team; several get a question
    lowered = text.lower()
    topics = [topic for topic, (words, _) in TOPICS.items()
              if any(re.search(rf"\b{re.escape(word)}", lowered) for word in words)]

    def unique(items: list[str]) -> list[str]:
        return list(dict.fromkeys(items))

    return {"teams": unique(teams), "programs": unique(programs),
            "seasons": unique(seasons), "topics": topics}


def _resolve(question, store, team, program, season) -> tuple[str, str, str, str]:
    """Pin down (team, program, season, topic) or raise _Clarify."""
    if not isinstance(question, str) or not question.strip():
        raise _Clarify("invalid", "Ask a question such as: pull up intake data on team 1899")
    parsed = parse_question(question)
    teams = [team] if team else parsed["teams"]
    programs = [program] if program else parsed["programs"]
    seasons = [str(season)] if season else parsed["seasons"]
    if not teams:
        raise _Clarify("invalid", "Which team? Include a team number, e.g. 'team 1899'.")
    if len(teams) > 1:
        raise _Clarify("ambiguous", "One team at a time: say 'team <number>' (and the season "
                       "as a year) so the team number is not confused with other numbers.",
                       candidates=teams)
    team = str(teams[0]).strip()
    if len(programs) > 1 or len(seasons) > 1:
        raise _Clarify("ambiguous", "Name exactly one program and one season.",
                       programs=programs, seasons=seasons)
    try:
        program = normalize_program(programs[0]) if programs else None
        season = normalize_season(seasons[0]) if seasons else None
    except UnsupportedProgramError as error:
        raise _Clarify("unsupported", str(error)) from None
    except ValueError as error:
        raise _Clarify("invalid", str(error)) from None
    if not team.isdigit():
        if re.fullmatch(r"\d+[A-Za-z]+", team):
            raise _Clarify("unsupported", f"Team {team.upper()} looks like a VEX-style alphanumeric "
                           "identity. The evidence schema is numeric-only (FRC/FTC); VEX is "
                           "unsupported until a team identity extension is implemented.")
        raise _Clarify("invalid", f"{team!r} is not a team number.")
    if int(team) <= 0 or len(team) > 6:
        raise _Clarify("invalid", f"{team!r} is not a valid team number.")
    team = str(int(team))
    if len(parsed["topics"]) > 1:
        raise _Clarify("ambiguous", "One topic at a time, please.", topics=parsed["topics"])
    topic = parsed["topics"][0] if parsed["topics"] else "overview"
    if program is None or season is None:
        found = store.scopes(team) if store is not None else []
        found = [(p, s) for p, s in found if program in (None, p) and season in (None, s)]
        if len(found) > 1:
            listing = ", ".join(f"{p} {s}" for p, s in found)
            raise _Clarify(
                "ambiguous", f"Team {team} has analyzed matches in more than one competition "
                f"({listing}). Those are different robots; say which program and season you mean.",
                team=team, candidates=[{"program": p, "season": s} for p, s in found])
        if len(found) == 1:
            program, season = found[0]
    return team, program, season, topic


def _dedupe(records: list[EvidenceRecord], taken: dict[str, list[tuple[float, float]]]
            ) -> tuple[list[EvidenceRecord], list[EvidenceRecord]]:
    """Keep rate windows that do not overlap an already-counted window of the same match."""
    kept, dropped = [], []
    for record in records:
        if record.obs.kind not in RATE_KINDS:
            kept.append(record)
            continue
        spans = taken.setdefault(f"{record.match_key}|{record.obs.kind}", [])
        start, end = record.obs.start_s, record.obs.end_s
        if any(start < other_end and end > other_start for other_start, other_end in spans):
            dropped.append(record)
        else:
            spans.append((start, end))
            kept.append(record)
    return kept, dropped


def _aggregate(topic_kinds: tuple[str, ...], records: list[EvidenceRecord]) -> dict | None:
    """Attributable totals for one tier; None (never zero) when nothing was counted."""
    if not records:
        return None
    result: dict = {"records": len(records), "matches": len({r.match_key for r in records})}
    windows = [r.obs for r in records if r.obs.kind in RATE_KINDS]
    if windows and topic_kinds and all(kind in RATE_KINDS for kind in topic_kinds):
        pieces = sum(obs.count for obs in windows)
        active = sum(obs.end_s - obs.start_s for obs in windows)
        result.update(pieces=pieces, observed_active_s=round(active, 3),
                      pieces_per_s=round(pieces / active, 4), windows=len(windows))
    scores = [r.obs for r in records if r.obs.kind == "score"]
    if scores and topic_kinds == ("score",):
        scored = [obs for obs in scores if obs.outcome == "scored"]
        pointed = [obs.points for obs in scored if obs.points is not None]
        result.update(scored_events=len(scored),
                      missed_events=sum(obs.outcome == "missed" for obs in scores),
                      video_observed_points_lower_bound=sum(pointed) if pointed else None)
    return result


def answer(question: str, store: EvidenceStore | None, *, team: str | None = None,
           program: str | None = None, season: str | None = None) -> dict:
    """Answer one question from stored evidence. ``store`` is None when no database exists."""
    base = {"question": question, "team": None, "program": None, "season": None, "topic": None}
    try:
        team, program, season, topic = _resolve(question, store, team, program, season)
    except _Clarify as stop:
        return {**base, "status": stop.status, "clarification": stop.message, **stop.details}
    base.update(team=team, program=program, season=season, topic=topic)
    kinds = TOPICS[topic][1] if topic in TOPICS else None
    matches = store.matches_for(team, program, season) if store is not None and program and season else []
    records = store.records(team, program, season, kinds) if matches else []
    result = {**base, "status": "no_analyzed_data",
              "coverage": {"matches_analyzed": len(matches),
                           "match_keys": [match["match_key"] for match in matches]},
              "human_reviewed": None, "model_estimate": None, "evidence": [],
              "not_counted": {}, "limitations": list(LIMITATIONS)}
    if not matches:
        scope = " ".join(filter(None, (program, season))) or "any program or season"
        result["summary"] = (f"No analyzed data is stored for team {team} in {scope}. "
                             "That means not analyzed yet, not zero.")
        return result
    by_status: dict[str, list[EvidenceRecord]] = {}
    for record in records:
        by_status.setdefault(record.classify()[0], []).append(record)
    taken: dict[str, list[tuple[float, float]]] = {}
    verified, overlap_v = _dedupe(by_status.get("verified", []), taken)
    estimate, overlap_e = _dedupe(by_status.get("estimate", []), taken)
    overlapping = {(record.match_key, record.obs.id) for record in overlap_v + overlap_e}
    result["status"] = ("human_reviewed" if verified else "model_estimate" if estimate
                        else "insufficient_evidence")
    agg_kinds = kinds or ()
    result["human_reviewed"] = _aggregate(agg_kinds, verified)
    result["model_estimate"] = _aggregate(agg_kinds, estimate)
    for record in records:
        entry = record.to_dict()
        if (record.match_key, record.obs.id) in overlapping:
            entry["status"], entry["reason"] = "overlap", "overlaps a window already counted"
        entry["counted"] = entry["status"] in ("verified", "estimate")
        result["evidence"].append(entry)
    for entry in result["evidence"]:
        if not entry["counted"]:
            result["not_counted"][entry["status"]] = result["not_counted"].get(entry["status"], 0) + 1
    if estimate:
        result["limitations"].append("Model estimates are unreviewed and are kept out of the "
                                     "human-reviewed totals; do not add the two together.")
    if result["status"] == "insufficient_evidence":
        result["summary"] = (
            f"Team {team} appears in {len(matches)} analyzed {program} {season} match(es), but no "
            f"{topic} observation is countable ({len(records)} uncounted record(s)). Unknown, not zero.")
    else:
        result["summary"] = f"Team {team}, {program} {season}, {topic}: {STATUS_TEXT[result['status']]}."
    return result


def _describe(label: str, agg: dict | None) -> str:
    if agg is None:
        return f"{label}: none"
    parts = [f"{agg['records']} record(s) in {agg['matches']} match(es)"]
    if "pieces_per_s" in agg:
        parts.append(f"{agg['pieces']} pieces in {agg['observed_active_s']} s observed "
                     f"= {agg['pieces_per_s']} pieces/s over {agg['windows']} window(s)")
    if "scored_events" in agg:
        points = agg["video_observed_points_lower_bound"]
        parts.append(f"{agg['scored_events']} scored, {agg['missed_events']} missed, points lower "
                     f"bound {'unknown' if points is None else points}")
    return f"{label}: " + "; ".join(parts)


def format_text(result: dict) -> str:
    """Readable report for the terminal (ASCII only)."""
    lines = [f"Status: {STATUS_TEXT[result['status']]}"]
    if "clarification" in result:
        return "\n".join(lines + [result["clarification"]])
    lines.append(result["summary"])
    if result["coverage"]["matches_analyzed"]:
        lines.append("Analyzed matches: " + ", ".join(result["coverage"]["match_keys"]))
        lines.append(_describe("Human-reviewed", result["human_reviewed"]))
        lines.append(_describe("Model estimate (unreviewed)", result["model_estimate"]))
    if result["evidence"]:
        lines.append("Evidence:")
    for entry in result["evidence"]:
        count = "" if entry["count"] is None else f" count={entry['count']}"
        lines.append(f"  [{entry['status']}] {entry['match_key']} {entry['start_s']:g}-{entry['end_s']:g}s "
                     f"{entry['kind']}{count} ({entry['reason']}): {entry['evidence']} "
                     f"<{entry['source_url'] or 'no source recorded'}>")
    if result["not_counted"]:
        lines.append("Not counted: " + ", ".join(f"{n} {name}" for name, n in result["not_counted"].items()))
    lines.append("Limitations:")
    lines += [f"  - {text}" for text in result["limitations"]]
    return "\n".join(lines)


def _handle(args: argparse.Namespace) -> int:
    path = Path(args.db) if args.db else default_db_path()
    store = None
    try:
        if path.exists():
            store = EvidenceStore(path, readonly=True)
        result = answer(" ".join(args.question), store, team=args.team,
                        program=args.program, season=args.season)
    except sqlite3.Error as error:
        print(f"cannot read evidence database {path}: {error}")
        return 1
    finally:
        if store is not None:
            store.close()
    print(json.dumps(result, indent=2, allow_nan=False) if args.json else format_text(result))
    return 2 if result["status"] in ("ambiguous", "unsupported", "invalid") else 0


def register(sub) -> None:
    parser = sub.add_parser("ask", help="answer a question about a team from stored evidence (offline)")
    parser.add_argument("question", nargs="+", help='e.g. "pull up intake data on team 1899"')
    parser.add_argument("--json", action="store_true", help="print the full answer as JSON")
    parser.add_argument("--db", help="evidence database (default $FRCSTACK_DB or .frcstack/evidence.db)")
    parser.add_argument("--team", help="team number (overrides the question)")
    parser.add_argument("--program", help="FRC or FTC (overrides the question)")
    parser.add_argument("--season", help="season year (overrides the question)")
    parser.set_defaults(handler=_handle)
