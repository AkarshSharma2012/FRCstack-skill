"""Standalone real purchased STEP assembly helper.

CLI: python component_runtime.py assemble manifest.json --output OUTPUT_DIR

Accepts a manifest (schema 1) that lists 1-32 purchased components, each
referencing a local STEP file with provenance metadata.  Applies rotation
(at source origin) then translation, exports a named assembly STEP, and
writes validation.json with roundtrip verification.

Limitations:
- No native Onshape connection, mates, FEA, or physical materials.
- Roundtrip verification uses Boolean difference per instance; no fabrication
  readiness claim.
- URL is provenance documentation; network retrieval is never performed here.
- No exact team robot or game-piece specification.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import time
import urllib.parse
from pathlib import Path
import sys

MAX_COMPONENTS = 32
MAX_FILE_BYTES = 128 * 1024 * 1024  # 128 MiB
MAX_TRANSLATION_MM = 10000.0
_PRIVATE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


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


def _strict_float(value, name: str) -> float:
    """Accept only int/float (not bool); must be finite."""
    if type(value) is bool:
        raise TypeError(f"{name}: boolean is not a valid numeric value")
    if type(value) not in (int, float):
        raise TypeError(f"{name}: expected numeric, got {type(value).__name__!r}")
    if not math.isfinite(float(value)):
        raise ValueError(f"{name}: value must be finite, got {value!r}")
    return float(value)


def _validate_vector3(seq, name: str) -> tuple[float, float, float]:
    if not isinstance(seq, list) or len(seq) != 3:
        raise ValueError(f"{name}: expected list of 3 numbers")
    return tuple(_strict_float(v, f"{name}[{i}]") for i, v in enumerate(seq))


def _validate_url(url: str) -> None:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("source_url must be a non-empty string")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"source_url must use https scheme, got {parsed.scheme!r}")
    if parsed.username or parsed.password:
        raise ValueError("source_url must not contain credentials")
    host = (parsed.hostname or "").lower()
    if not host or host in _PRIVATE_HOSTS or host.startswith("127.") or host.endswith(".local"):
        raise ValueError(f"source_url must not reference a local/private host: {host!r}")


def _validate_component(comp: dict, manifest_dir: Path, seen_names: set) -> dict:
    """Validate one component entry and return cleaned metadata."""
    # Instance name
    name = comp.get("instance_name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("instance_name must be a non-empty string")
    safe = name.strip()
    if safe in seen_names:
        raise ValueError(f"Duplicate instance_name: {safe!r}")
    seen_names.add(safe)

    # File path (no traversal, no symlinks)
    file_str = comp.get("file")
    if not isinstance(file_str, str) or not file_str.strip():
        raise ValueError(f"{safe}: file must be a non-empty string")
    rel = Path(file_str)
    if rel.is_absolute():
        raise ValueError(f"{safe}: file must be a relative path")
    resolved = (manifest_dir / rel).resolve()
    try:
        resolved.relative_to(manifest_dir.resolve())
    except ValueError:
        raise ValueError(f"{safe}: file path escapes manifest directory (traversal)")
    if resolved.is_symlink():
        raise ValueError(f"{safe}: symlink sources are not allowed")
    if not resolved.exists():
        raise FileNotFoundError(f"{safe}: source file not found: {resolved}")
    if resolved.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"{safe}: source file exceeds 128 MiB limit")

    # Hash
    expected_sha = comp.get("sha256")
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise ValueError(f"{safe}: sha256 must be a 64-character hex string")
    actual_sha = _sha256_file(resolved)
    if actual_sha != expected_sha.lower():
        raise ValueError(f"{safe}: sha256 mismatch (expected {expected_sha!r})")

    # Provenance strings
    for field in ("manufacturer", "part_number", "source_revision"):
        val = comp.get(field)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"{safe}: {field} must be a non-empty string")

    _validate_url(comp.get("source_url", ""))

    # Translation
    tx, ty, tz = _validate_vector3(comp.get("translation_mm", [0, 0, 0]), f"{safe}.translation_mm")
    for v, label in ((tx, "tx"), (ty, "ty"), (tz, "tz")):
        if abs(v) > MAX_TRANSLATION_MM:
            raise ValueError(f"{safe}: {label}={v} exceeds ±{MAX_TRANSLATION_MM} mm limit")

    # Rotation
    rot = comp.get("rotation", {})
    if not isinstance(rot, dict):
        raise ValueError(f"{safe}: rotation must be an object")
    ax, ay, az = _validate_vector3(rot.get("axis", [0, 0, 1]), f"{safe}.rotation.axis")
    if ax == 0.0 and ay == 0.0 and az == 0.0:
        raise ValueError(f"{safe}: rotation axis must be a nonzero vector")
    degrees = _strict_float(rot.get("degrees", 0), f"{safe}.rotation.degrees")

    return {
        "instance_name": safe,
        "resolved_path": resolved,
        "sha256": actual_sha,
        "manufacturer": comp["manufacturer"].strip(),
        "part_number": comp["part_number"].strip(),
        "source_revision": comp["source_revision"].strip(),
        "source_url": comp["source_url"].strip(),
        "translation_mm": (tx, ty, tz),
        "rotation": {"axis": (ax, ay, az), "degrees": degrees},
    }


def _import_solids(path: Path):
    """Import all solids from a STEP file as a list of OCC shapes."""
    cq = _kernel()
    roots = cq.importers.importStep(str(path)).vals()
    compound = cq.Compound.makeCompound(roots)
    solids = compound.Solids()
    if not solids:
        raise ValueError(f"No solids found in {path.name}")
    invalid = [i for i, s in enumerate(solids) if not s.isValid() or s.Volume() <= 0]
    if invalid:
        raise ValueError(f"{path.name}: solid(s) at indices {invalid} are invalid or zero-volume")
    return solids


def _apply_transform(solid, rotation: dict, translation_mm: tuple):
    """Apply rotation-at-origin then translation to an OCC solid."""
    ax, ay, az = rotation["axis"]
    deg = rotation["degrees"]
    tx, ty, tz = translation_mm
    # Rotate about origin
    if deg != 0.0:
        solid = solid.rotate((0, 0, 0), (ax, ay, az), deg)
    # Translate
    if tx != 0.0 or ty != 0.0 or tz != 0.0:
        solid = solid.translate((tx, ty, tz))
    return solid


def _bounds_dict(shape) -> dict:
    bb = shape.BoundingBox()
    return {
        "xmin": bb.xmin, "xmax": bb.xmax,
        "ymin": bb.ymin, "ymax": bb.ymax,
        "zmin": bb.zmin, "zmax": bb.zmax,
    }


def _interferences(placed: list[tuple[str, object]], tol: float = 1e-6) -> list[dict]:
    collisions = []
    for (na, sa), (nb, sb) in itertools.combinations(placed, 2):
        try:
            vol = sa.intersect(sb).Volume()
        except Exception:
            vol = 0.0
        if vol > tol:
            collisions.append({"instances": [na, nb], "overlap_mm3": vol})
    return collisions


def verify_solid_pair(solid_a, solid_b, tol_mm3: float = 1e-5) -> bool:
    """Return True iff both Boolean differences are near-zero (shapes coincide).

    A correct-volume but displaced roundtrip will yield a nonzero difference
    in at least one direction, so this detects displacement unlike volume-only checks.
    """
    try:
        diff_ab = solid_a.cut(solid_b).Volume()
        diff_ba = solid_b.cut(solid_a).Volume()
        return diff_ab <= tol_mm3 and diff_ba <= tol_mm3
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def assemble(manifest_path: Path | str, output: Path | str) -> dict:
    """Validate manifest, assemble placed STEP solids, export and verify.

    Returns the validation dict (same as validation.json content).
    Raises ValueError / TypeError / FileNotFoundError / FileExistsError on any problem.
    Never modifies inputs; never clobbers existing output.
    """
    manifest_path = Path(manifest_path)
    output = Path(output)

    # Guard: never clobber
    if output.exists() or output.is_symlink():
        raise FileExistsError(
            f"Output directory already exists: {output}. Use a fresh directory."
        )

    # Parse manifest
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read manifest: {exc}") from exc

    if not isinstance(raw, dict) or raw.get("schema") != 1:
        raise ValueError("Manifest must be a JSON object with schema=1")

    components_raw = raw.get("components")
    if not isinstance(components_raw, list) or not components_raw:
        raise ValueError("Manifest must have a non-empty 'components' list")
    if len(components_raw) > MAX_COMPONENTS:
        raise ValueError(f"Manifest has {len(components_raw)} components; maximum is {MAX_COMPONENTS}")

    manifest_dir = manifest_path.parent.resolve()
    seen_names: set[str] = set()
    validated = []
    for i, raw_comp in enumerate(components_raw):
        if not isinstance(raw_comp, dict):
            raise ValueError(f"Component at index {i} must be a JSON object")
        validated.append(_validate_component(raw_comp, manifest_dir, seen_names))

    # Import and transform all solids
    cq = _kernel()
    started = time.perf_counter()

    # Cache imports by resolved path (to honour repeated source occurrences)
    source_cache: dict[Path, list] = {}
    placed_named: list[tuple[str, object]] = []  # (instance_name, placed_solid_compound)
    comp_reports = []

    for comp in validated:
        path = comp["resolved_path"]
        if path not in source_cache:
            source_cache[path] = _import_solids(path)
        src_solids = source_cache[path]  # list of solids from this source file

        # Transform each solid by the component's rotation+translation
        placed_solids = [
            _apply_transform(s, comp["rotation"], comp["translation_mm"])
            for s in src_solids
        ]
        # Merge all placed solids into a compound for this instance
        placed_compound = cq.Compound.makeCompound(placed_solids)
        placed_named.append((comp["instance_name"], placed_compound))

        bb = _bounds_dict(placed_compound)
        comp_reports.append({
            "instance_name": comp["instance_name"],
            "file": str(path.relative_to(manifest_dir)),
            "sha256": comp["sha256"],
            "manufacturer": comp["manufacturer"],
            "part_number": comp["part_number"],
            "source_revision": comp["source_revision"],
            "source_url": comp["source_url"],
            "source_solid_count": len(src_solids),
            "translation_mm": list(comp["translation_mm"]),
            "rotation": {
                "axis": list(comp["rotation"]["axis"]),
                "degrees": comp["rotation"]["degrees"],
            },
            "bounds_mm": bb,
            "volume_mm3": placed_compound.Volume(),
        })

    # Check interferences
    interfs = _interferences(placed_named)
    clearance_passed = len(interfs) == 0

    # Build assembly and export
    output.mkdir(parents=True, exist_ok=False)
    assembly_path = output / "assembly.step"
    export_success = False
    export_error = None
    try:
        assy = cq.Assembly(name="purchased_component_assembly")
        for inst_name, compound in placed_named:
            assy.add(compound, name=inst_name)
        assy.export(str(assembly_path))
        export_success = True
    except Exception as exc:
        export_error = str(exc)

    # Roundtrip verification via Boolean differences per instance
    roundtrip_results = []
    roundtrip_passed = False
    if export_success and assembly_path.exists():
        try:
            rt_roots = cq.importers.importStep(str(assembly_path)).vals()
            rt_compound = cq.Compound.makeCompound(rt_roots)
            rt_solids = rt_compound.Solids()
            # Collect all original placed solids (flattened)
            orig_solids = [s for _, c in placed_named for s in c.Solids()]

            ok_count = 0
            fail_count = 0
            for i, (orig, rt) in enumerate(zip(orig_solids, rt_solids)):
                passed = verify_solid_pair(orig, rt)
                roundtrip_results.append({
                    "solid_index": i,
                    "passed": passed,
                    "original_volume_mm3": orig.Volume(),
                    "roundtrip_volume_mm3": rt.Volume(),
                })
                if passed:
                    ok_count += 1
                else:
                    fail_count += 1

            if len(rt_solids) != len(orig_solids):
                roundtrip_passed = False
                roundtrip_results.append({
                    "error": f"solid count mismatch: original={len(orig_solids)} roundtrip={len(rt_solids)}"
                })
            else:
                roundtrip_passed = (fail_count == 0)
        except Exception as exc:
            roundtrip_results.append({"error": f"Roundtrip import failed: {exc}"})

    elapsed = time.perf_counter() - started

    report = {
        "schema": 1,
        "kind": "purchased_component_assembly_not_a_robot",
        "units": "mm",
        "component_count": len(validated),
        "components": comp_reports,
        "interferences": interfs,
        "clearance_passed": clearance_passed,
        "export_success": export_success,
        "export_error": export_error,
        "roundtrip_passed": roundtrip_passed,
        "roundtrip_results": roundtrip_results,
        "elapsed_seconds": elapsed,
        "onshape_verified": False,
        "fabrication_ready": False,
        "fea_executed": False,
        "mates_solved": False,
        "limitations": [
            "URL is provenance documentation only; no network retrieval performed",
            "Rotation applied at source origin then translation; no mate constraints",
            "No material, density, or strength claim",
            "STEP preserves solids; native parametric history is not retained",
            "Clearance check is pairwise intersection volume; not a certified tolerance analysis",
            "Roundtrip uses Boolean differences; near-zero tolerance is 1e-5 mm^3",
            "No Onshape connection, FEA, or fabrication readiness",
            "No exact team robot or game-piece specification",
        ],
    }

    # Write validation.json
    val_path = output / "validation.json"
    with val_path.open("x", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, allow_nan=False)
        fh.write("\n")

    if not export_success:
        raise ValueError(f"Assembly export failed: {export_error}")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    assemble_cmd = sub.add_parser(
        "assemble",
        help="Assemble purchased STEP components from a manifest and export evidence",
    )
    assemble_cmd.add_argument("manifest", type=Path, help="Path to manifest.json (schema 1)")
    assemble_cmd.add_argument("--output", type=Path, required=True, help="Fresh output directory")
    args = parser.parse_args(argv)

    try:
        if args.command == "assemble":
            report = assemble(args.manifest, args.output)
            print(json.dumps(report, indent=2, allow_nan=False))
            return 0
    except (ValueError, TypeError, FileNotFoundError, FileExistsError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
