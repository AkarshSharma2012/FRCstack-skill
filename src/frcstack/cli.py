"""`frcstack` command line entry point.

Each feature area owns a module exposing ``register(subparsers)``. The CLI
discovers them here so feature lanes never need to edit this file.
"""
from __future__ import annotations

import argparse
import importlib
import sys

import frcstack
from frcstack import __version__

# (module, purpose). A module that is missing or fails to import because an
# optional dependency is absent is reported, not fatal.
COMMAND_MODULES = (
    ("frcstack.programs", "program/season info"),
    ("frcstack.data.cli", "fetch schedules, results, and team data"),
    ("frcstack.vision.cli", "analyze match video"),
    ("frcstack.scout.cli", "scouting ledgers, metrics, and Excel export"),
    ("frcstack.ask", "plain-English questions about analyzed teams"),
    ("frcstack.cad.cli", "verified CAD generators"),
)


def build_parser() -> tuple[argparse.ArgumentParser, list[str]]:
    parser = argparse.ArgumentParser(prog="frcstack", description=frcstack.__doc__)
    parser.add_argument("--version", action="version", version=f"frcstack {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    unavailable = []
    for name, purpose in COMMAND_MODULES:
        try:
            module = importlib.import_module(name)
        except ImportError as error:
            unavailable.append(f"{name} ({purpose}): {error}")
            continue
        register = getattr(module, "register", None)
        if register is not None:
            register(sub)
    return parser, unavailable


def main(argv: list[str] | None = None) -> int:
    parser, unavailable = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        if unavailable:
            print("\nUnavailable command groups:", file=sys.stderr)
            for line in unavailable:
                print("  " + line, file=sys.stderr)
        return 0
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.error(f"command {args.command!r} has no handler")
    result = handler(args)
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
