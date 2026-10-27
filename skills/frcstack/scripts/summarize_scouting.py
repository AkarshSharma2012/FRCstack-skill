#!/usr/bin/env python3
"""Validate and summarize a recorded observation ledger; does not watch video."""
import argparse
import json
import math
from pathlib import Path

KINDS = {"intake_window", "fire_window", "score", "spill", "struggle", "visible_motors", "capacity_lower_bound", "simultaneous"}

def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def observation_status(record, superseded=()):
    if record['id'] in superseded:
        return 'Superseded'
    if record['is_replay']:
        return 'Replay'
    if record['visibility'] != 'direct' or not record['reviewed'] or (record['kind'] == 'score' and record['outcome'] == 'unknown'):
        return 'Unresolved'
    return 'Eligible'

def summarize(ledger):
    if ledger.get("schema") != 1 or ledger.get("program") not in {"FRC", "FTC"}:
        raise ValueError("Set schema=1 and the actual FRC/FTC program")
    for field in ("season", "event_id", "match_id", "source_url"):
        if not isinstance(ledger.get(field), str) or not ledger[field].strip():
            raise ValueError("Missing match/source field: " + field)
    observations = ledger.get("observations")
    if not isinstance(observations, list):
        raise ValueError("observations must be a list")
    records, superseded = {}, set()
    for record in observations:
        if not isinstance(record, dict):
            raise ValueError("Each observation must be an object")
        rid = record.get("id")
        if not isinstance(rid, str) or not rid or rid in records:
            raise ValueError("Missing or duplicate observation id")
        if not isinstance(record.get("team"), str) or not record["team"].isdigit() or int(record["team"]) <= 0:
            raise ValueError("Each record needs an observed numeric team id")
        if record.get("kind") not in KINDS:
            raise ValueError("Unknown observation kind")
        start, end = record.get("start_s"), record.get("end_s")
        if not number(start) or not number(end) or start < 0 or end < start:
            raise ValueError("Invalid source interval")
        if record.get("visibility") not in {"direct", "ambiguous", "occluded"} or type(record.get("reviewed")) is not bool or type(record.get("is_replay")) is not bool:
            raise ValueError("Explicit visibility/review/replay status required")
        if not isinstance(record.get("evidence"), str) or not record["evidence"].strip():
            raise ValueError("Missing frame evidence")
        if record["kind"].endswith("_window"):
            if type(record.get("count")) is not int or record["count"] < 0 or end <= start:
                raise ValueError("Rate window needs an integer count and positive interval")
        if record["kind"] == "score":
            if record.get("outcome") not in {"scored", "missed", "unknown"}:
                raise ValueError("Score outcome required")
            if record.get("points") is not None:
                if not number(record["points"]) or record["points"] < 0 or not isinstance(record.get("rule_ref"), str) or not record["rule_ref"].strip():
                    raise ValueError("Numeric points need a nonnegative value and rule reference")
        old = record.get("supersedes")
        if old is not None:
            if old not in records or old in superseded or (records[old]["team"], records[old]["kind"]) != (record["team"], record["kind"]):
                raise ValueError("Correction must replace an earlier active record for the same team/kind")
            superseded.add(old)
        records[rid] = record
    teams = {}
    windows = {}
    for rid, record in records.items():
        status = observation_status(record, superseded)
        if status == 'Superseded':
            continue
        team = record["team"]
        summary = teams.setdefault(team, {"reviewed_visible_scoring_events": None, "video_observed_points_lower_bound": None, "unresolved_records": 0, "excluded_replays": 0, "intake": None, "firing": None})
        if status == 'Replay':
            summary["excluded_replays"] += 1
            continue
        if status == 'Unresolved':
            summary["unresolved_records"] += 1
            continue
        kind = record["kind"]
        if kind == "score":
            if record["outcome"] == "scored":
                summary["reviewed_visible_scoring_events"] = (summary["reviewed_visible_scoring_events"] or 0) + 1
                if record.get("points") is not None:
                    summary["video_observed_points_lower_bound"] = (summary["video_observed_points_lower_bound"] or 0) + record["points"]
        elif kind in {"intake_window", "fire_window"}:
            key = (team, kind)
            intervals = windows.setdefault(key, [])
            if any(record["start_s"] < end and record["end_s"] > start for start, end in intervals):
                raise ValueError("Overlapping windows would double-count throughput")
            intervals.append((record["start_s"], record["end_s"]))
            name = "intake" if kind == "intake_window" else "firing"
            metric = summary[name] or {"visible_count": 0, "observed_active_s": 0, "pieces_per_s": None, "windows": 0}
            metric["visible_count"] += record["count"]
            metric["observed_active_s"] += record["end_s"] - record["start_s"]
            metric["windows"] += 1
            metric["pieces_per_s"] = metric["visible_count"] / metric["observed_active_s"]
            summary[name] = metric
    return {"schema": 1, "program": ledger["program"], "season": ledger["season"], "match_id": ledger["match_id"], "source_url": ledger["source_url"], "teams": teams, "superseded_records": len(superseded), "limitation": "Reviewed video observations only. Not an official score, hardware inventory, maximum rate, or proof of complete match coverage."}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = summarize(json.loads(args.ledger.read_text(encoding="utf-8-sig")))
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(text)
    else:
        print(text, end="")

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, TypeError) as error:
        raise SystemExit(str(error))
