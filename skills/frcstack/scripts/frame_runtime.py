"""Proposed rectangular chassis frame export and verification helper.

CLI: python frame_runtime.py build-frame --parameters <json> --output <newdir>

Accepts a JSON parameters file with exactly six frame_geometry fields.
Exports six named hollow tube rails to frame.step, re-imports them, verifies
geometry order-independently, and writes validation.json with full evidence.

Limitations:
- Proposed rectangular chassis layout only; NOT a complete robot or exact team replica.
- No Onshape connection, FEA, material claim, or fabrication readiness.
- Outer dimensions sourced from layout references; do not establish exact custom parts.
- Rail name roundtrip is unverified; geometry verified via bijective Boolean difference.
- Color (.72,.74,.77) is authored appearance only; NOT independently appearance-verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
import sys

from component_runtime import _no_links, _bijective_roundtrip, _interferences
from frame_geometry import build_frame

_FRAME_COLOR = (0.72, 0.74, 0.77)  # illustrative aluminium-like; NOT a material claim
_SIX_RAIL_NAMES = frozenset({
    "left_rail", "right_rail", "front_rail",
    "rear_rail", "crossbar_front", "crossbar_rear",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kernel():
    try:
        import cadquery
    except ImportError as exc:
        raise RuntimeError(
            "CadQuery is required; install in the .venv-cad environment"
        ) from exc
    return cadquery


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _bounds_dict(shape) -> dict:
    bb = shape.BoundingBox()
    return {
        "xmin": bb.xmin, "xmax": bb.xmax,
        "ymin": bb.ymin, "ymax": bb.ymax,
        "zmin": bb.zmin, "zmax": bb.zmax,
    }


def _validate_parameters_path(path: Path) -> dict:
    """Load, check symlinks, and parse the parameters JSON."""
    if ".." in path.absolute().parts:
        raise ValueError("Parameters path must not contain '..' segments")
    _no_links(path)
    try:
        source_bytes = path.read_bytes()
        raw = json.loads(source_bytes.decode("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read parameters file: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("Parameters file must be a JSON object")
    return raw, hashlib.sha256(source_bytes).hexdigest()


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def build_frame_export(parameters_path: Path | str, output: Path | str) -> dict:
    """Validate parameters, build frame, export STEP, verify, write validation.json.

    Parameters
    ----------
    parameters_path : path to JSON with exactly six frame_geometry fields
    output          : fresh (non-existent) output directory

    Returns the validation dict (same as validation.json).
    Raises ValueError/FileNotFoundError/FileExistsError on any problem.
    Writes validation.json before raising on failed roundtrip/validity/analytic/clearance.
    """
    started = time.perf_counter()
    parameters_path = Path(parameters_path)
    output = Path(output)

    # Security: reject '..' traversal and symlinks/junctions
    if ".." in output.parts:
        raise ValueError("Output path must not contain '..' segments")
    _no_links(output)

    # Validate parameters BEFORE creating output directory
    raw_params, params_sha = _validate_parameters_path(parameters_path)

    # No clobber
    if output.exists() or output.is_symlink():
        raise FileExistsError(
            f"Output directory already exists: {output}. Use a fresh directory."
        )

    # Build frame geometry (raises ValueError with detail on bad params)
    frame = build_frame(raw_params)
    parts = frame["parts"]
    cut_list = frame["cut_list"]
    expected_volume_mm3 = frame["expected_volume_mm3"]
    validated_params = frame["parameters"]
    if set(parts.keys()) != _SIX_RAIL_NAMES:
        raise ValueError("frame_geometry must produce exactly six named rails")

    cq = _kernel()

    # Validate six solids before export
    for name, shape in parts.items():
        solids = shape.Solids() if hasattr(shape, "Solids") else [shape]
        if len(solids) != 1:
            raise ValueError(f"{name}: expected exactly one solid")
        for i, s in enumerate(solids):
            if not s.isValid() or not math.isfinite(s.Volume()) or s.Volume() <= 0:
                raise ValueError(f"{name}[{i}]: invalid or non-positive-volume solid")

    # Per-rail bounds/volumes
    rail_reports = {}
    placed_named = []
    for name, shape in parts.items():
        vol = shape.Volume()
        rail_reports[name] = {
            "bounds_mm": _bounds_dict(shape),
            "volume_mm3": vol,
        }
        placed_named.append((name, shape))

    # Pairwise interference check (butt-joint touch is allowed; > 1e-6 mm3 is a fail)
    interfs = _interferences(placed_named)
    clearance_passed = len(interfs) == 0

    # Analytic volume agreement
    actual_total = math.fsum(v["volume_mm3"] for v in rail_reports.values())
    abs_diff = abs(actual_total - expected_volume_mm3)
    rel_diff = abs_diff / max(abs(expected_volume_mm3), 1e-30)
    analytic_passed = abs_diff <= 1e-4 or rel_diff <= 1e-9

    # Export six named rails to STEP via CadQuery Assembly
    output.mkdir(parents=True, exist_ok=False)
    step_path = output / "frame.step"
    export_success = False
    export_error = None
    try:
        assy = cq.Assembly(name="proposed_rectangular_chassis_not_complete_robot")
        r, g, b_col = _FRAME_COLOR
        for name, shape in parts.items():
            assy.add(shape, name=name, color=cq.Color(r, g, b_col))
        assy.export(str(step_path))
        export_success = True
    except Exception as exc:
        export_error = str(exc)

    step_sha = _sha256_file(step_path) if export_success and step_path.exists() else None

    # Re-import and bijective roundtrip verification
    roundtrip_results: list = []
    roundtrip_passed = False
    if export_success and step_path.exists():
        try:
            rt_roots = cq.importers.importStep(str(step_path)).vals()
            rt_compound = cq.Compound.makeCompound(rt_roots)
            rt_solids = rt_compound.Solids()
            if len(rt_solids) != 6:
                raise ValueError(
                    f"Expected 6 solids on readback, got {len(rt_solids)}"
                )
            for i, s in enumerate(rt_solids):
                if not s.isValid() or not math.isfinite(s.Volume()) or s.Volume() <= 0:
                    raise ValueError(f"Readback solid[{i}] is invalid or non-positive-volume")
            orig_solids = list(parts.values())
            roundtrip_passed, roundtrip_results = _bijective_roundtrip(orig_solids, rt_solids)
        except Exception as exc:
            roundtrip_results.append({"error": f"Roundtrip failed: {exc}"})

    elapsed = time.perf_counter() - started

    report = {
        "schema": 1,
        "kind": "proposed_rectangular_chassis_not_complete_robot",
        "units": "mm",
        "onshape_verified": False,
        "mates_solved": False,
        "fea_executed": False,
        "fabrication_ready": False,
        "exact_team_replica": False,
        "parameters": validated_params,
        "parameters_sha256": params_sha,
        "step_sha256": step_sha,
        "rails": rail_reports,
        "cut_list": cut_list,
        "expected_volume_mm3": expected_volume_mm3,
        "actual_volume_mm3": actual_total,
        "analytic_volume_abs_diff_mm3": abs_diff,
        "analytic_volume_rel_diff": rel_diff,
        "analytic_passed": analytic_passed,
        "interferences": interfs,
        "clearance_passed": clearance_passed,
        "export_success": export_success,
        "export_error": export_error,
        "roundtrip_passed": roundtrip_passed,
        "roundtrip_results": roundtrip_results,
        "name_roundtrip_verified": False,
        "color_authored": list(_FRAME_COLOR),
        "color_appearance_verified": False,
        "elapsed_seconds": elapsed,
        "limitations": [
            "Proposed rectangular chassis only; NOT a complete robot or exact team replica",
            "Outer dimensions are layout references; do not establish exact custom parts",
            "No Onshape connection, FEA, material, mass, or fabrication claim",
            "STEP preserves solids only; native parametric history not retained",
            "Rail name roundtrip unverified; geometry verified via bijective Boolean difference",
            "Color (.72,.74,.77) is authored appearance; NOT independently appearance-verified",
            "Butt-joint touch (zero volume intersection) is allowed; positive overlap is flagged",
            "Clearance check is pairwise intersection volume; not a certified tolerance analysis",
            "Collision kernel failure raises ValueError; never silently becomes zero overlap",
        ],
    }

    val_path = output / "validation.json"
    with val_path.open("x", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, allow_nan=False)
        fh.write("\n")

    if not export_success:
        raise ValueError(f"Frame STEP export failed: {export_error}")
    if not roundtrip_passed:
        raise ValueError(
            "Roundtrip verification failed -- geometry mismatch after STEP export/import. "
            "See validation.json for per-solid details."
        )
    if not analytic_passed:
        raise ValueError(
            f"Analytic volume mismatch: expected={expected_volume_mm3}, "
            f"actual={actual_total}, abs_diff={abs_diff}. See validation.json."
        )
    if not clearance_passed:
        raise ValueError(
            f"Frame rails have positive-volume interference: {interfs}. "
            "See validation.json."
        )

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build_cmd = sub.add_parser(
        "build-frame",
        help="Build proposed chassis frame, export STEP, verify geometry",
    )
    build_cmd.add_argument(
        "--parameters", type=Path, required=True,
        help="Path to JSON with exactly six frame_geometry fields",
    )
    build_cmd.add_argument(
        "--output", type=Path, required=True,
        help="Fresh (non-existent) output directory",
    )
    args = parser.parse_args(argv)

    try:
        if args.command == "build-frame":
            report = build_frame_export(args.parameters, args.output)
            print(json.dumps(report, indent=2, allow_nan=False))
            return 0
    except (ValueError, TypeError, FileNotFoundError, FileExistsError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
