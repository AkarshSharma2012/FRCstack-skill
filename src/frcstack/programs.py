"""Competition programs and seasons.

Field geometry here drives the pixel-to-field mapping, so every value carries
its source and whether it has been checked against the official field drawing.
Unverified values are usable for development but are reported as such.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

INCH = 0.0254


@dataclass(frozen=True)
class Season:
    program: str          # "FRC", "FTC", or "VEX"
    year: int
    game: str
    field_length_m: float
    field_width_m: float
    alliance_size: int
    match_length_s: int
    auto_length_s: int
    source: str
    verified: bool        # True only after checking the official manual/drawing


SEASONS: dict[str, Season] = {
    "frc2026": Season(
        program="FRC", year=2026, game="REBUILT",
        field_length_m=651.2 * INCH, field_width_m=317.7 * INCH,
        alliance_size=3, match_length_s=160, auto_length_s=20,
        source="FRC game manual field dimensions; verify against the 2026 field drawing",
        verified=False,
    ),
    "ftc2026": Season(
        program="FTC", year=2026, game="current FTC season",
        field_length_m=144 * INCH, field_width_m=144 * INCH,
        alliance_size=2, match_length_s=150, auto_length_s=30,
        source="FTC 12 ft x 12 ft field (nominal); verify against the season manual",
        verified=False,
    ),
    "vex2026": Season(
        program="VEX", year=2026, game="current V5RC season",
        field_length_m=144 * INCH, field_width_m=144 * INCH,
        alliance_size=2, match_length_s=120, auto_length_s=15,
        source="VEX V5RC 12 ft x 12 ft field (nominal); verify against the game manual",
        verified=False,
    ),
}

# Where each program's schedules/results come from.
DATA_SOURCES = {
    "FRC": ("The Blue Alliance API v3", "FRC Events API", "Statbotics"),
    "FTC": ("FTC Events API", "FTCScout"),
    "VEX": ("RobotEvents API",),
}


def get_season(key: str) -> Season:
    try:
        return SEASONS[key.lower()]
    except KeyError:
        raise KeyError(f"unknown season {key!r}; known: {', '.join(sorted(SEASONS))}") from None


def _show(args: argparse.Namespace) -> int:
    seasons = [get_season(args.season)] if args.season else list(SEASONS.values())
    print(json.dumps([asdict(s) for s in seasons], indent=2))
    return 0


def register(sub) -> None:
    parser = sub.add_parser("seasons", help="list supported programs, seasons, and field geometry")
    parser.add_argument("season", nargs="?", help="season key such as frc2026")
    parser.set_defaults(handler=_show)
