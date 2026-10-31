"""
hand_runtime.py  --  Export and verify the proposed 20-DOF hand.
=================================================================
CLI:
    python hand_runtime.py build-hand --pose open|partial|closed --output FRESH_DIR

API:
    from hand_runtime import build_hand_export
    report = build_hand_export(pose_name, output)

DISCLAIMER:
- Proposed design targets only.  NOT fabrication-ready.
- No Onshape connection, FEA, material, native mates, or actuation claim.
- Native hand FeatureScript authored but has NOT compiled in Onshape.
- STEP preserves solid geometry; name/colour roundtrip is NOT independently
  verified.  Geometry verified via bijective Boolean-difference matching.
- Collision check covers all 210 part pairs including non-adjacent.
  Boolean intersection kernel failure RAISES; never silently becomes zero.
  Collision-free is claimed only when all 210 pairs return ≤ 1e-6 mm³.
  No claim of continuous collision-freedom across the full motion range.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Kernel guard
# ---------------------------------------------------------------------------

def _kernel():
    try:
        import cadquery
    except ImportError as exc:
        raise RuntimeError(
            "CadQuery is required; run from the .venv-cad environment"
        ) from exc
    return cadquery


# ---------------------------------------------------------------------------
# Path security helpers  (reuse same pattern as component_runtime)
# ---------------------------------------------------------------------------

def _no_links(path: Path) -> None:
    absolute = path.absolute()
    for item in (absolute, *absolute.parents):
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise ValueError(f"Symlink or junction in path: {item}")


# ---------------------------------------------------------------------------
# Colour constants
# ---------------------------------------------------------------------------

_PALM_COLOR     = (0.50, 0.50, 0.50)   # grey for palm / phalanges
_PHAL_COLOR     = (0.55, 0.55, 0.55)   # slightly lighter grey for phalanges
_CARRIER_COLOR  = (0.20, 0.45, 0.80)   # blue for carriers

# Authored appearance only; NOT independently verified in STEP roundtrip.
_PART_COLOR_MAP = {}
for _f in ("index", "middle", "ring", "little", "thumb"):
    _PART_COLOR_MAP[f"{_f}_carrier"] = _CARRIER_COLOR
    for _s in ("proximal", "middle", "distal"):
        _PART_COLOR_MAP[f"{_f}_{_s}"] = _PHAL_COLOR
_PART_COLOR_MAP["palm"] = _PALM_COLOR


# ---------------------------------------------------------------------------
# SHA-256 helper
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# AABB broad-phase + Boolean narrow-phase collision check
# (all 210 pairs; raises on kernel failure; never silently zero)
# ---------------------------------------------------------------------------

def _aabb_overlap(sa, sb) -> bool:
    """True if bounding boxes overlap (quick reject)."""
    a, b = sa.BoundingBox(), sb.BoundingBox()
    return (a.xmin < b.xmax and a.xmax > b.xmin and
            a.ymin < b.ymax and a.ymax > b.ymin and
            a.zmin < b.zmax and a.zmax > b.zmin)


def _check_all_collisions(named_parts: list[tuple[str, object]],
                           tol: float = 1e-6) -> list[dict]:
    """
    Check all n*(n-1)/2 pairs for n=21 (210 pairs).
    AABB broad phase skips pairs whose boxes don't overlap.
    Boolean narrow phase is run for every AABB-overlapping pair.
    Kernel exceptions RAISE as ValueError (never silently zero).
    Returns list of collision dicts with pair names and overlap_mm3.
    """
    collisions = []
    for (na, sa), (nb, sb) in itertools.combinations(named_parts, 2):
        if not _aabb_overlap(sa, sb):
            continue
        try:
            intersection = sa.intersect(sb)
            if not intersection.isValid():
                raise ValueError("invalid Boolean result")
            vol = intersection.Volume()
        except Exception as exc:
            raise ValueError(
                f"Collision kernel failure between {na!r} and {nb!r}: {exc}"
            ) from exc
        if not math.isfinite(vol) or vol < 0:
            raise ValueError(
                f"Collision check {na!r}x{nb!r} returned invalid volume: {vol}"
            )
        if vol > tol:
            collisions.append({"parts": [na, nb], "overlap_mm3": vol})
    return collisions


# ---------------------------------------------------------------------------
# STEP export
# ---------------------------------------------------------------------------

def _export_step(cq, named_parts: list[tuple[str, object]], step_path: Path) -> None:
    assy = cq.Assembly(name="proposed_20dof_hand_not_fabrication_ready")
    for name, solid in named_parts:
        r, g, b = _PART_COLOR_MAP.get(name, _PHAL_COLOR)
        assy.add(solid, name=name, color=cq.Color(r, g, b))
    assy.export(str(step_path))


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

_VALID_POSES = ("open", "partial", "closed", "pinch")

def build_hand_export(pose_name: str, output: "Path | str") -> dict:
    """
    Build the 20-DOF hand for *pose_name*, export STEP, verify geometry.

    Parameters
    ----------
    pose_name : str  -- one of 'open', 'partial', 'closed', 'pinch'
    output    : Path -- fresh (non-existent) output directory

    Returns the validation dict (same content as validation.json).
    Raises ValueError / FileExistsError / RuntimeError on any error.
    Writes validation.json before raising so evidence is preserved.
    """
    started = time.perf_counter()
    output = Path(output)

    # --- Input validation ---
    if not isinstance(pose_name, str) or pose_name not in _VALID_POSES:
        raise ValueError(
            f"Unknown pose {pose_name!r}. Valid values: {list(_VALID_POSES)}"
        )
    if ".." in output.parts:
        raise ValueError("Output path must not contain '..' segments")
    _no_links(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(
            f"Output directory already exists: {output}. Use a fresh directory."
        )

    # --- Resolve scripts path so hand_geometry/hand_kinematics importable ---
    _scripts = Path(__file__).resolve().parent
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))

    from hand_kinematics import pose as get_pose, hand_dimensions, joint_specs
    from hand_geometry import build_hand

    cq = _kernel()

    angles = get_pose(pose_name)
    hand = build_hand(angles)
    parts_dict: dict = hand["parts"]         # {name -> cq Shape}
    fk = hand["kinematics"]

    # Validate 21 parts
    expected_names = {"palm"} | {s["child_link"] for s in joint_specs()}
    if set(parts_dict) != expected_names:
        raise ValueError(
            f"build_hand returned unexpected part names. "
            f"Missing: {expected_names - set(parts_dict)}, "
            f"Extra: {set(parts_dict) - expected_names}"
        )
    for name, solid in parts_dict.items():
        if solid is None or not solid.isValid():
            raise ValueError(f"Part '{name}' is not a valid solid")
        if len(solid.Solids()) != 1:
            raise ValueError(f"Part '{name}' has {len(solid.Solids())} solids (expected 1)")
        v = solid.Volume()
        if not math.isfinite(v) or v <= 0:
            raise ValueError(f"Part '{name}' has invalid volume {v}")

    # Ordered list for consistent processing
    part_order = ["palm"] + [
        f"{f}_{s}"
        for f in ("index", "middle", "ring", "little", "thumb")
        for s in ("carrier", "proximal", "middle", "distal")
    ]
    named_parts = [(n, parts_dict[n]) for n in part_order]

    # Per-part reports
    part_reports = {}
    for name, solid in named_parts:
        bb = solid.BoundingBox()
        part_reports[name] = {
            "volume_mm3": solid.Volume(),
            "bounds_mm": {
                "xmin": bb.xmin, "xmax": bb.xmax,
                "ymin": bb.ymin, "ymax": bb.ymax,
                "zmin": bb.zmin, "zmax": bb.zmax,
            },
        }

    # --- Collision check (all 210 pairs) BEFORE export ---
    collision_error = None
    collisions = []
    try:
        collisions = _check_all_collisions(named_parts)
    except ValueError as exc:
        collision_error = str(exc)

    collision_free = (collision_error is None and len(collisions) == 0)

    # --- Export STEP ---
    output.mkdir(parents=True, exist_ok=False)
    step_path = output / "hand.step"
    export_success = False
    export_error = None
    try:
        _export_step(cq, named_parts, step_path)
        export_success = True
    except Exception as exc:
        export_error = str(exc)

    step_sha = _sha256_file(step_path) if export_success and step_path.exists() else None

    # --- Roundtrip: reimport + bijective Boolean geometry check ---
    rt_source_count = None
    rt_passed = False
    rt_results = []
    if export_success and step_path.exists():
        try:
            rt_roots = cq.importers.importStep(str(step_path)).vals()
            rt_compound = cq.Compound.makeCompound(rt_roots)
            rt_solids = rt_compound.Solids()
            rt_source_count = len(rt_solids)
            if rt_source_count != 21:
                raise ValueError(
                    f"Expected 21 solids on readback, got {rt_source_count}"
                )
            for i, s in enumerate(rt_solids):
                if not s.isValid() or not math.isfinite(s.Volume()) or s.Volume() <= 0:
                    raise ValueError(
                        f"Readback solid[{i}] invalid or non-positive-volume"
                    )
            from component_runtime import verify_solid_pair
            from solid_matching import match_solids
            orig_solids = [s for _, solid in named_parts for s in solid.Solids()]
            rt_passed, rt_results = match_solids(
                orig_solids, rt_solids, verify_solid_pair, 1e-5
            )
        except Exception as exc:
            rt_results = [{"error": f"Roundtrip failed: {exc}"}]

    # --- FK angle/transform summary ---
    angles_list = [fk["angles_deg"][j] for j in sorted(fk["angles_deg"])]
    hd = hand_dimensions()
    joints_summary = {}
    for jname, jdata in fk["joints"].items():
        joints_summary[jname] = {
            "origin_mm": jdata["origin_mm"],
            "axis_world": jdata["axis_world"],
        }

    elapsed = time.perf_counter() - started

    # Source SHA256 of key scripts
    source_shas = {}
    for fname in ("hand_geometry.py", "hand_kinematics.py", "hand_runtime.py"):
        p = _scripts / fname
        if p.exists():
            source_shas[fname] = hashlib.sha256(p.read_bytes()).hexdigest()

    report = {
        "schema": 1,
        "kind": "proposed_20dof_hand_not_fabrication_ready",
        "units": "mm",
        "pose": pose_name,
        "source_sha256": source_shas,
        "step_sha256": step_sha,
        "part_count_source": len(parts_dict),
        "part_count_roundtrip": rt_source_count,
        "fk_angles_deg": fk["angles_deg"],
        "fk_angles_list_sorted_by_name": angles_list,
        "fk_joints": joints_summary,
        "fk_tips_mm": fk["tips_mm"],
        "dimensions_mm": {
            "palm_width_mm": hd["palm_width_mm"],
            "palm_length_mm": hd["palm_length_mm"],
            "carrier_length_mm": hd["carrier_length_mm"],
        },
        "joint_count": 20,
        "parts": part_reports,
        "export_success": export_success,
        "export_error": export_error,
        "geometry_roundtrip_passed": rt_passed,
        "roundtrip_results": rt_results,
        "collision_pairs_checked": 210,
        "aabb_broad_phase_used": True,
        "collision_error": collision_error,
        "collisions": collisions,
        "collision_free_sampled_pose": collision_free,
        "native_mates_verified": False,
        "actuation_verified": False,
        "fea_executed": False,
        "fabrication_ready": False,
        "name_roundtrip_verified": False,
        "color_palm_phalanges_authored": list(_PALM_COLOR),
        "color_carriers_authored": list(_CARRIER_COLOR),
        "color_appearance_verified": False,
        "elapsed_seconds": elapsed,
        "limitations": [
            "All dimensions are proposed design targets only; not measured anatomy",
            "NOT fabrication-ready; not FEA-verified; not collision-free guaranteed",
            "Native hand FeatureScript authored but has NOT compiled in Onshape",
            "No Onshape connection, native assembly mates, motion simulation, or FEA",
            "No actuation (tendons/actuators absent from model)",
            "STEP preserves solid geometry; name/colour roundtrip NOT independently verified",
            "Geometry verified via bijective Boolean-difference matching (order-independent)",
            "Collision check covers all 210 part pairs with AABB broad phase + Boolean narrow",
            "Boolean kernel failure raises ValueError; never silently becomes zero overlap",
            "collision_free_sampled_pose refers to single named pose only; no continuous claim",
            "colour values are authored appearance; NOT independently STEP-roundtrip-verified",
        ],
    }

    val_path = output / "validation.json"
    with val_path.open("x", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, allow_nan=False)
        fh.write("\n")

    # Decide exit
    if not export_success:
        raise ValueError(f"Hand STEP export failed: {export_error}")
    if not rt_passed:
        raise ValueError(
            "Roundtrip geometry verification failed. "
            "See validation.json for per-solid details."
        )
    if collision_error is not None:
        raise ValueError(
            f"Collision check kernel error: {collision_error}. "
            "See validation.json."
        )
    if collisions:
        raise ValueError(
            f"Hand has {len(collisions)} collision(s) in pose '{pose_name}': "
            + ", ".join(f"{c['parts'][0]} x {c['parts'][1]} ({c['overlap_mm3']:.4f} mm3)"
                        for c in collisions)
            + ". See validation.json."
        )

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Export and verify the proposed 20-DOF hand geometry."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    build_cmd = sub.add_parser(
        "build-hand",
        help="Build hand at named pose, export STEP, verify geometry",
    )
    build_cmd.add_argument(
        "--pose", required=True,
        choices=list(_VALID_POSES),
        help="Named pose: open, partial, or closed",
    )
    build_cmd.add_argument(
        "--output", type=Path, required=True,
        help="Fresh (non-existent) output directory",
    )
    args = parser.parse_args(argv)

    try:
        if args.command == "build-hand":
            report = build_hand_export(args.pose, args.output)
            # Print a compact summary instead of the full JSON to stdout
            print(json.dumps({
                "pose": report["pose"],
                "part_count_source": report["part_count_source"],
                "part_count_roundtrip": report["part_count_roundtrip"],
                "geometry_roundtrip_passed": report["geometry_roundtrip_passed"],
                "collision_free_sampled_pose": report["collision_free_sampled_pose"],
                "collisions": report["collisions"],
                "export_success": report["export_success"],
                "step_sha256": report["step_sha256"],
                "elapsed_seconds": report["elapsed_seconds"],
            }, indent=2, allow_nan=False))
            return 0
    except (ValueError, TypeError, FileNotFoundError, FileExistsError,
            OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
