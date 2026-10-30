"""Standalone real purchased STEP assembly helper.

CLI: python component_runtime.py assemble manifest.json --output OUTPUT_DIR

Accepts a manifest (schema 1) with 1-32 purchased components, each with a local
STEP file and provenance metadata.  Applies rotation then translation, exports a
named assembly STEP, and writes validation.json with roundtrip verification.

Limitations: No Onshape, FEA, physical materials, or fabrication readiness.
URL is provenance metadata only; no network retrieval is performed here.
Hostname validation cannot guarantee public DNS destination.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import itertools
import json
import math
import re
import time
import urllib.parse
from pathlib import Path
import sys

MAX_COMPONENTS = 32
MAX_FILE_BYTES = 128 * 1024 * 1024  # 128 MiB
MAX_TRANSLATION_MM = 10_000.0
MAX_ROTATION_DEGREES = 360_000.0
_MIN_AXIS_MAG = 1e-10
_MAX_AXIS_MAG = 1e10
_INSTANCE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
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


def _no_links(path: Path) -> None:
    """Check every lexical ancestor before resolving links or creating output."""
    absolute = path.absolute()
    for item in (absolute, *absolute.parents):
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            raise ValueError(f"Symlink or junction in path: {item}")


def _strict_float(value, name: str) -> float:
    """Accept only int/float (not bool); must be finite and within float range."""
    if type(value) is bool:
        raise TypeError(f"{name}: boolean is not a valid numeric value")
    if type(value) not in (int, float):
        raise TypeError(f"{name}: expected numeric, got {type(value).__name__!r}")
    try:
        f = float(value)
    except OverflowError:
        raise ValueError(f"{name}: value too large to represent as float")
    if not math.isfinite(f):
        raise ValueError(f"{name}: value must be finite, got {value!r}")
    return f


def _validate_vector3(seq, name: str) -> tuple[float, float, float]:
    if not isinstance(seq, list) or len(seq) != 3:
        raise ValueError(f"{name}: expected list of 3 numbers")
    return tuple(_strict_float(v, f"{name}[{i}]") for i, v in enumerate(seq))


def _validate_url(url: str) -> None:
    """Validate provenance URL. No network request is performed.

    Hostname validation cannot guarantee the URL resolves to a public DNS
    destination; the URL is metadata only.
    """
    if not isinstance(url, str) or not url:
        raise ValueError("source_url must be a non-empty string")
    if any(c <= "\x20" or c == "\x7f" for c in url):
        raise ValueError("source_url must not contain whitespace or control characters")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"source_url must use https scheme, got {parsed.scheme!r}")
    if parsed.username or parsed.password:
        raise ValueError("source_url must not contain credentials")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("source_url must have a hostname")
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        raise ValueError(f"source_url port must be 1-65535, got {parsed.port}")

    # Determine if host is an IP literal or a domain name
    is_ip = False
    ip_obj = None
    try:
        ip_obj = ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        pass

    if is_ip:
        if not ip_obj.is_global:
            raise ValueError(
                f"source_url IP {host!r} is not a globally-routable address. "
                "URL is provenance metadata; no network request is performed."
            )
    else:
        # Domain name: reject single-label, .local, and known private names
        if "." not in host or host.endswith(".local") or host in _PRIVATE_HOSTS or host.startswith("127."):
            raise ValueError(
                f"source_url hostname {host!r} is local, single-label, or private. "
                "Hostname validation cannot guarantee public DNS destination."
            )


def _validate_component(comp: dict, manifest_dir: Path, seen_names: set) -> dict:
    """Validate one component entry and return cleaned metadata."""
    name = comp.get("instance_name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("instance_name must be a non-empty string")
    safe = name.strip()
    if not _INSTANCE_NAME_RE.match(safe):
        raise ValueError(
            f"instance_name {safe!r} must match ^[A-Za-z][A-Za-z0-9_-]{{0,63}}$"
        )
    if safe in seen_names:
        raise ValueError(f"Duplicate instance_name: {safe!r}")
    seen_names.add(safe)

    file_str = comp.get("file")
    if not isinstance(file_str, str) or not file_str.strip():
        raise ValueError(f"{safe}: file must be a non-empty string")
    rel = Path(file_str.strip())
    if rel.is_absolute() or rel.drive:
        raise ValueError(f"{safe}: file must be a relative path without drive")
    if ".." in rel.parts:
        raise ValueError(f"{safe}: file path must not contain '..' segments")

    _no_links(manifest_dir / rel)

    resolved = (manifest_dir / rel).resolve()
    try:
        resolved.relative_to(manifest_dir)
    except ValueError:
        raise ValueError(f"{safe}: file path escapes manifest directory (traversal)")

    if not resolved.exists():
        raise FileNotFoundError(f"{safe}: source file not found: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"{safe}: source must be a regular file, not a directory or device")
    if resolved.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"{safe}: source file exceeds 128 MiB limit")

    expected_sha = comp.get("sha256")
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise ValueError(f"{safe}: sha256 must be a 64-character hex string")
    try:
        int(expected_sha, 16)
    except ValueError:
        raise ValueError(f"{safe}: sha256 contains non-hex characters")
    actual_sha = _sha256_file(resolved)
    if actual_sha != expected_sha.lower():
        raise ValueError(f"{safe}: sha256 mismatch (expected {expected_sha!r})")

    for field in ("manufacturer", "part_number", "source_revision"):
        val = comp.get(field)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"{safe}: {field} must be a non-empty string")

    _validate_url(comp.get("source_url", ""))

    # Require explicit translation_mm
    if "translation_mm" not in comp:
        raise ValueError(f"{safe}: translation_mm is required (no silent default placement)")
    tx, ty, tz = _validate_vector3(comp["translation_mm"], f"{safe}.translation_mm")
    for v, label in ((tx, "tx"), (ty, "ty"), (tz, "tz")):
        if abs(v) > MAX_TRANSLATION_MM:
            raise ValueError(f"{safe}: {label}={v} exceeds ±{MAX_TRANSLATION_MM} mm")

    # Require explicit rotation with axis and degrees
    if "rotation" not in comp:
        raise ValueError(f"{safe}: rotation is required (no silent default placement)")
    rot = comp["rotation"]
    if not isinstance(rot, dict):
        raise ValueError(f"{safe}: rotation must be an object")
    if "axis" not in rot:
        raise ValueError(f"{safe}: rotation.axis is required")
    if "degrees" not in rot:
        raise ValueError(f"{safe}: rotation.degrees is required")
    ax, ay, az = _validate_vector3(rot["axis"], f"{safe}.rotation.axis")
    mag = math.sqrt(ax * ax + ay * ay + az * az)
    if mag < _MIN_AXIS_MAG:
        raise ValueError(f"{safe}: rotation axis too small to normalize (mag={mag:.2e})")
    if mag > _MAX_AXIS_MAG:
        raise ValueError(f"{safe}: rotation axis unusably large (mag={mag:.2e})")
    ax, ay, az = ax / mag, ay / mag, az / mag  # normalize to unit vector
    degrees = _strict_float(rot["degrees"], f"{safe}.rotation.degrees")
    if abs(degrees) > MAX_ROTATION_DEGREES:
        raise ValueError(f"{safe}: rotation.degrees {degrees} exceeds ±{MAX_ROTATION_DEGREES}")

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
    invalid = [i for i, s in enumerate(solids)
               if not s.isValid() or not math.isfinite(s.Volume()) or s.Volume() <= 0]
    if invalid:
        raise ValueError(f"{path.name}: solid(s) at indices {invalid} are invalid or zero-volume")
    return solids


def _apply_transform(solid, rotation: dict, translation_mm: tuple):
    """Apply rotation-at-origin then translation to an OCC solid."""
    ax, ay, az = rotation["axis"]
    deg = rotation["degrees"]
    tx, ty, tz = translation_mm
    if deg != 0.0:
        solid = solid.rotate((0, 0, 0), (ax, ay, az), deg)
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
    """Pairwise collision check.

    Raises ValueError on kernel failure or nonfinite volume — never silently
    converts a kernel exception into zero overlap.
    """
    collisions = []
    for (na, sa), (nb, sb) in itertools.combinations(placed, 2):
        try:
            vol = sa.intersect(sb).Volume()
        except Exception as exc:
            raise ValueError(
                f"Collision kernel failure between {na!r} and {nb!r}: {exc}"
            ) from exc
        if not math.isfinite(vol) or vol < 0:
            raise ValueError(
                f"Collision check {na!r}×{nb!r} returned invalid volume: {vol}"
            )
        if vol > tol:
            collisions.append({"instances": [na, nb], "overlap_mm3": vol})
    return collisions


def verify_solid_pair(solid_a, solid_b, tol_mm3: float = 1e-5) -> bool:
    """Return True iff both Boolean differences are near-zero (shapes coincide).

    A correct-volume but displaced roundtrip yields nonzero difference in at
    least one direction, so this detects displacement unlike volume-only checks.

    Raises TypeError/ValueError for invalid tolerance.
    Raises RuntimeError on kernel computation failure.
    Raises ValueError for nonfinite volume results.
    """
    if type(tol_mm3) is bool:
        raise TypeError("tol_mm3: boolean is not a valid tolerance value")
    if not isinstance(tol_mm3, (int, float)):
        raise TypeError(f"tol_mm3: expected numeric, got {type(tol_mm3).__name__!r}")
    if not math.isfinite(tol_mm3) or tol_mm3 < 0:
        raise ValueError(f"tol_mm3 must be a non-negative finite number, got {tol_mm3!r}")
    try:
        diff_ab = solid_a.cut(solid_b).Volume()
        diff_ba = solid_b.cut(solid_a).Volume()
    except Exception as exc:
        raise RuntimeError(f"Kernel error in solid pair verification: {exc}") from exc
    if not math.isfinite(diff_ab) or not math.isfinite(diff_ba):
        raise ValueError(
            f"Kernel returned nonfinite volume in pair check: "
            f"diff_ab={diff_ab}, diff_ba={diff_ba}"
        )
    return 0 <= diff_ab <= tol_mm3 and 0 <= diff_ba <= tol_mm3


def _bijective_roundtrip(orig_solids, rt_solids, tol_mm3: float = 1e-5) -> tuple[bool, list]:
    """Order-independent geometry matching; semantic instance identity unverified."""
    from solid_matching import match_solids
    return match_solids(orig_solids, rt_solids, verify_solid_pair, tol_mm3)


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def assemble(manifest_path: Path | str, output: Path | str) -> dict:
    """Validate manifest, assemble placed STEP solids, export and verify.

    Returns the validation dict (same as validation.json content).
    Raises ValueError/TypeError/FileNotFoundError/FileExistsError on any problem.
    Never modifies inputs; never clobbers existing output.
    Writes validation.json before raising on failed roundtrip so evidence is preserved.
    """
    manifest_path = Path(manifest_path)
    output = Path(output)

    if ".." in output.parts:
        raise ValueError("Output path must not contain '..' segments")
    _no_links(manifest_path)
    _no_links(output)

    if output.exists() or output.is_symlink():
        raise FileExistsError(
            f"Output directory already exists: {output}. Use a fresh directory."
        )

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read manifest: {exc}") from exc

    schema_val = raw.get("schema") if isinstance(raw, dict) else None
    if not isinstance(raw, dict) or type(schema_val) is not int or schema_val != 1:
        raise ValueError(
            "Manifest must be a JSON object with schema=1 (exact integer, not bool)"
        )

    components_raw = raw.get("components")
    if not isinstance(components_raw, list) or not components_raw:
        raise ValueError("Manifest must have a non-empty 'components' list")
    if len(components_raw) > MAX_COMPONENTS:
        raise ValueError(
            f"Manifest has {len(components_raw)} components; maximum is {MAX_COMPONENTS}"
        )

    manifest_dir = manifest_path.parent.resolve()
    seen_names: set[str] = set()
    validated = []
    for i, raw_comp in enumerate(components_raw):
        if not isinstance(raw_comp, dict):
            raise ValueError(f"Component at index {i} must be a JSON object")
        validated.append(_validate_component(raw_comp, manifest_dir, seen_names))

    cq = _kernel()
    started = time.perf_counter()

    source_cache: dict[Path, list] = {}
    placed_named: list[tuple[str, object]] = []
    comp_reports = []

    for comp in validated:
        path = comp["resolved_path"]
        if path not in source_cache:
            source_cache[path] = _import_solids(path)
        src_solids = source_cache[path]
        placed_solids = [
            _apply_transform(s, comp["rotation"], comp["translation_mm"])
            for s in src_solids
        ]
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

    # Collision check — raises on kernel failure; never silently converts to zero
    interfs = _interferences(placed_named)
    clearance_passed = len(interfs) == 0

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

    # Roundtrip: bijective geometry matching, order-independent
    roundtrip_results: list[dict] = []
    roundtrip_passed = False
    if export_success and assembly_path.exists():
        try:
            rt_roots = cq.importers.importStep(str(assembly_path)).vals()
            rt_compound = cq.Compound.makeCompound(rt_roots)
            rt_solids = rt_compound.Solids()
            if any(not s.isValid() or not math.isfinite(s.Volume()) or s.Volume() <= 0
                   for s in rt_solids):
                raise ValueError("Read-back contains invalid or non-positive-volume solids")
            orig_solids = [s for _, c in placed_named for s in c.Solids()]
            roundtrip_passed, roundtrip_results = _bijective_roundtrip(orig_solids, rt_solids)
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
        "clearance_scope": "Between manifest instances only; internal source-body overlaps untested",
        "export_success": export_success,
        "export_error": export_error,
        "roundtrip_passed": roundtrip_passed,
        "roundtrip_results": roundtrip_results,
        "instance_identity_roundtrip_verified": False,
        "elapsed_seconds": elapsed,
        "onshape_verified": False,
        "fabrication_ready": False,
        "fea_executed": False,
        "mates_solved": False,
        "limitations": [
            "URL is provenance documentation only; no network retrieval performed",
            "Hostname validation cannot guarantee public DNS destination; URL is metadata only",
            "Rotation applied at source origin then translation; no mate constraints",
            "No material, density, or strength claim",
            "STEP preserves solids; native parametric history is not retained",
            "Clearance check is pairwise intersection volume; not a certified tolerance analysis",
            "Collision kernel failure raises ValueError; never silently becomes zero overlap",
            "Roundtrip uses bijective Boolean-difference geometry matching; order-independent",
            "instance_identity_roundtrip_verified=false: geometry-only; no name roundtrip",
            "No Onshape connection, FEA, or fabrication readiness",
            "No exact team robot or game-piece specification",
        ],
    }

    # Always write validation.json before any raise so evidence is preserved
    val_path = output / "validation.json"
    with val_path.open("x", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, allow_nan=False)
        fh.write("\n")

    if not export_success:
        raise ValueError(f"Assembly export failed: {export_error}")

    if not roundtrip_passed:
        raise ValueError(
            "Roundtrip verification failed — geometry mismatch after STEP export/import. "
            "See validation.json for per-solid details."
        )

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
