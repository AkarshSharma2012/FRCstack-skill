"""Shared records passed between the vision, data, scouting, and query layers.

Every number FRCstack reports traces back to one of these records, so they
carry provenance (``source``), certainty (``confidence``/``visibility``), and
the evidence needed to re-check them by eye.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Literal

Source = Literal["human", "model"]
Visibility = Literal["direct", "ambiguous", "occluded"]

# Observation kinds understood by the scouting summarizer. Vision lanes may add
# kinds; unknown kinds are kept as evidence but never aggregated into rates.
OBSERVATION_KINDS = frozenset({
    "intake_window", "fire_window", "score", "spill", "struggle",
    "visible_motors", "capacity_lower_bound", "simultaneous",
    "disabled", "defense_played", "defense_received", "climb",
})

# A model observation at or above this confidence counts toward "estimate"
# aggregates. Only human-reviewed records count toward "verified" aggregates.
ESTIMATE_CONFIDENCE = 0.6


def _finite(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")


def _team(value: str | None, *, required: bool) -> None:
    if value is None and not required:
        return
    if not isinstance(value, str) or not value.isdigit() or int(value) <= 0:
        raise ValueError("team must be a positive team number as a string")


@dataclass(frozen=True)
class TrackPoint:
    """One robot position sample. ``team`` is None until identity is resolved."""

    match_key: str
    track_id: int
    t_s: float
    x_m: float
    y_m: float
    confidence: float
    team: str | None = None
    alliance: Literal["red", "blue"] | None = None

    def __post_init__(self) -> None:
        for name in ("t_s", "x_m", "y_m", "confidence"):
            _finite(getattr(self, name), name)
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")
        if self.t_s < 0:
            raise ValueError("t_s must be nonnegative")
        _team(self.team, required=False)


@dataclass(frozen=True)
class Observation:
    """A timestamped claim about one robot, compatible with the scouting ledger."""

    id: str
    team: str
    kind: str
    start_s: float
    end_s: float
    visibility: Visibility
    evidence: str
    source: Source = "model"
    confidence: float = 1.0
    reviewed: bool = False
    is_replay: bool = False
    count: int | None = None
    outcome: Literal["scored", "missed", "unknown"] | None = None
    points: float | None = None
    rule_ref: str | None = None
    supersedes: str | None = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id is required")
        _team(self.team, required=True)
        _finite(self.start_s, "start_s")
        _finite(self.end_s, "end_s")
        if self.start_s < 0 or self.end_s < self.start_s:
            raise ValueError("invalid interval")
        if self.visibility not in ("direct", "ambiguous", "occluded"):
            raise ValueError("invalid visibility")
        if self.source not in ("human", "model"):
            raise ValueError("invalid source")
        _finite(self.confidence, "confidence")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")
        if not self.evidence.strip():
            raise ValueError("evidence is required")

    @property
    def tier(self) -> Literal["verified", "estimate", "unresolved"]:
        """How an aggregate may use this record.

        verified: human-reviewed, direct, not a replay.
        estimate: unreviewed model output that is direct and confident.
        unresolved: everything else (kept as evidence, never totaled).
        """
        if self.is_replay or self.visibility != "direct":
            return "unresolved"
        if self.reviewed:
            return "verified"
        if self.source == "model" and self.confidence >= ESTIMATE_CONFIDENCE:
            return "estimate"
        return "unresolved"

    def to_ledger(self) -> dict:
        """Ledger-compatible dict (see skills/frcstack/references/scouting.md)."""
        record = {k: v for k, v in asdict(self).items() if v is not None and k != "extra"}
        record.update(self.extra)
        return record
