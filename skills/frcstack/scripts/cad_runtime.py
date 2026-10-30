"""Optional CPU CAD execution. Does not connect Onshape or certify a robot."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import time


ROLE_PALETTE: dict[str, tuple[float, float, float]] = {
    "plate":  (0.72, 0.74, 0.77),   # illustrative aluminium-like light grey; NOT a material/fabrication claim
    "shaft":  (0.42, 0.45, 0.49),   # illustrative steel-like mid-grey; NOT a material/fabrication claim
    "roller": (0.08, 0.09, 0.11),   # illustrative rubber-like dark; NOT a material/fabrication claim
}

# Maps assembly part name -> ROLE_PALETTE key.  Plates share the plate role.
_PART_ROLE: dict[str, str] = {
    "left_plate":  "plate",
    "right_plate": "plate",
    "shaft":       "shaft",
    "roller":      "roller",
}


def kernel():
    try:
        import cadquery
    except ImportError as error:
        raise RuntimeError("Install the optional CAD requirements in a dedicated environment; Onshape is not required for local solids") from error
    return cadquery


@dataclass(frozen=True)
class FixtureParameters:
    """Millimetres; original test geometry, not manufacturer dimensions."""
    inner_span_mm: float = 400
    plate_width_mm: float = 80
    plate_height_mm: float = 120
    plate_thickness_mm: float = 6
    hole_diameter_mm: float = 13
    shaft_diameter_mm: float = 12
    roller_length_mm: float = 360
    roller_diameter_mm: float = 50
    bore_diameter_mm: float = 14

    def validate(self):
        for name, value in asdict(self).items():
            if type(value) not in (int, float) or not 0.01 <= value <= 10000 or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number from 0.01 to 10000 mm")
        if self.roller_length_mm >= self.inner_span_mm:
            raise ValueError("roller must fit between the plate inner faces")
        if not self.shaft_diameter_mm < self.bore_diameter_mm < self.roller_diameter_mm:
            raise ValueError("require shaft diameter < bore diameter < roller diameter")
        if not self.shaft_diameter_mm < self.hole_diameter_mm < min(self.plate_width_mm, self.plate_height_mm):
            raise ValueError("shaft needs clearance inside a hole contained by the plate")
        if self.roller_diameter_mm >= self.plate_height_mm:
            raise ValueError("roller diameter must be smaller than the plate height")


@dataclass
class Fixture:
    parameters: FixtureParameters
    parts: dict


def build_fixture(parameters: FixtureParameters) -> Fixture:
    parameters.validate()
    cq = kernel()
    p = parameters
    try:
        plate = cq.Workplane("YZ").rect(p.plate_width_mm, p.plate_height_mm).extrude(p.plate_thickness_mm)
        hole = cq.Workplane("YZ").circle(p.hole_diameter_mm / 2).extrude(p.plate_thickness_mm)
        plate = plate.cut(hole).val()
        shaft = cq.Workplane("YZ").circle(p.shaft_diameter_mm / 2).extrude(p.inner_span_mm + 2 * p.plate_thickness_mm).val()
        roller = cq.Workplane("YZ").circle(p.roller_diameter_mm / 2).circle(p.bore_diameter_mm / 2).extrude(p.roller_length_mm).val()
    except Exception as error:
        raise ValueError(f"Kernel could not construct the requested fixture: {error}") from error
    parts = {
        "left_plate": plate.translate((-p.inner_span_mm / 2 - p.plate_thickness_mm, 0, 0)),
        "right_plate": plate.translate((p.inner_span_mm / 2, 0, 0)),
        "shaft": shaft.translate((-p.inner_span_mm / 2 - p.plate_thickness_mm, 0, 0)),
        "roller": roller.translate((-p.roller_length_mm / 2, 0, 0)),
    }
    for name, shape in parts.items():
        if not shape.isValid() or len(shape.Solids()) != 1 or shape.Volume() <= 0:
            raise ValueError(f"Kernel did not generate one valid positive-volume solid for {name}")
    return Fixture(parameters, parts)


def bounds(shape):
    box = shape.BoundingBox()
    return {"x": box.xlen, "y": box.ylen, "z": box.zlen}


def interferences(parts: dict, tolerance_mm3: float = 1e-6) -> list:
    if type(tolerance_mm3) not in (int, float) or not math.isfinite(tolerance_mm3) or tolerance_mm3 < 0:
        raise ValueError("interference volume tolerance must be nonnegative and finite")
    collisions = []
    for (a_name, a), (b_name, b) in itertools.combinations(parts.items(), 2):
        volume = a.intersect(b).Volume()
        if volume > tolerance_mm3:
            collisions.append({"parts": [a_name, b_name], "overlap_mm3": volume})
    return collisions


def sample_motion(fixture: Fixture, angles_degrees: list) -> dict:
    if not angles_degrees or len(angles_degrees) > 361 or any(type(a) not in (int, float) or not math.isfinite(a) for a in angles_degrees):
        raise ValueError("supply 1–361 finite numeric sample angles")
    collisions = []
    for angle in angles_degrees:
        parts = dict(fixture.parts)
        parts["roller"] = parts["roller"].rotate((0, 0, 0), (1, 0, 0), angle)
        collisions.extend({"angle_degrees": angle, **c} for c in interferences(parts))
    return {"angles_degrees": angles_degrees, "collisions": collisions,
            "continuous_motion_verified": False, "onshape_mates_verified": False,
            "limitation": "Sampled geometric poses of an axisymmetric test roller, not constrained dynamics or game-piece handling"}


def inspect_step(path: Path, max_bytes: int = 128 * 1024 * 1024, progress: bool = False) -> dict:
    path = Path(path)
    if path.suffix.lower() not in (".step", ".stp") or path.stat().st_size > max_bytes:
        raise ValueError("Expected a STEP file within the configured size limit")
    with path.open("rb") as stream:
        if not stream.read(256).lstrip().startswith(b"ISO-10303-21;"):
            raise ValueError("File does not contain an ISO STEP exchange header")
    started = time.perf_counter()
    cq = kernel()
    if progress:
        print("Importing STEP geometry...", file=sys.stderr, flush=True)
    try:
        roots = cq.importers.importStep(str(path)).vals()
        model = cq.Compound.makeCompound(roots)
        solids = model.Solids()
        if not solids:
            raise ValueError("No solids were imported")
        if progress:
            print(f"Checking {len(solids)} solids from {len(roots)} imported roots...", file=sys.stderr, flush=True)
        validity = [s.isValid() and math.isfinite(s.Volume()) and s.Volume() > 0 for s in solids]
        box = bounds(model)
    except Exception as error:
        raise ValueError(f"STEP import/inspection failed: {error}") from error
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"schema": 1, "file_name": path.name, "sha256": digest.hexdigest(),
            "bytes": path.stat().st_size, "imported_root_count": len(roots), "solid_count": len(solids),
            "all_solids_valid": all(validity), "invalid_solid_indices": [i for i, v in enumerate(validity) if not v],
            "bounds_mm": box, "sum_solid_volumes_mm3": math.fsum(s.Volume() for s in solids),
            "inspection_elapsed_seconds": time.perf_counter() - started,
            "kernel": "CadQuery " + cq.__version__, "units": "mm after STEP reader conversion",
            "scope": "BRep import validity, bounds and summed solid volumes; overlaps not subtracted",
            "fea_executed": False, "fabrication_ready": False, "onshape_verified": False}


def fixture_assembly(fixture: "Fixture") -> "cadquery.Assembly":
    """Return a CadQuery Assembly with deterministic role-palette colors applied.

    Appearance is illustrative only; it does not change engineering material,
    density, mass, or fabrication specification.  A manual Part Studio override
    in Onshape can shadow FeatureScript appearance defaults.
    """
    cq = kernel()
    assembly = cq.Assembly(name="original_roller_test_fixture")
    for name, shape in fixture.parts.items():
        role = _PART_ROLE[name]
        r, g, b = ROLE_PALETTE[role]
        assembly.add(shape, name=name, color=cq.Color(r, g, b))
    return assembly


def export_fixture(parameters: FixtureParameters, output: Path) -> dict:
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Use a new output directory; existing output is never overwritten")
    started = time.perf_counter()
    fixture = build_fixture(parameters)
    cq = kernel()
    collisions = interferences(fixture.parts)
    if collisions:
        raise ValueError("Generated fixture has interfering solids")
    assembly = fixture_assembly(fixture)
    output.mkdir(parents=True, exist_ok=False)
    step_path = output / "fixture.step"
    assembly.export(str(step_path))
    inspection = inspect_step(step_path)
    expected = bounds(cq.Compound.makeCompound(list(fixture.parts.values())))
    correct_bounds = all(math.isclose(expected[a], inspection["bounds_mm"][a], abs_tol=1e-5) for a in "xyz")
    expected_volume = math.fsum(p.Volume() for p in fixture.parts.values())
    correct_volume = math.isclose(expected_volume, inspection["sum_solid_volumes_mm3"], rel_tol=1e-8, abs_tol=1e-5)
    roundtrip = inspection["all_solids_valid"] and inspection["solid_count"] == 4 and correct_bounds and correct_volume
    report = {"schema": 1, "kind": "original_parametric_roller_test_fixture_not_a_robot",
              "parameters_mm": asdict(parameters), "parts": {name: {"bounds_mm": bounds(s), "volume_mm3": s.Volume()} for name, s in fixture.parts.items()},
              "static_collisions": collisions, "motion_samples": sample_motion(fixture, [0, 90, 180, 270, 360]),
              "step_import": inspection, "step_roundtrip_verified": roundtrip,
              "elapsed_seconds": time.perf_counter() - started,
              "fabrication_ready": False, "fea_executed": False, "onshape_verified": False,
              "purchased_parts_verified": False, "assembly_constraints_solved": False,
              "limits": ["Original test dimensions, not manufacturer drawings", "No bearings, couplings, fasteners or drive hardware specified", "No material or strength claim", "STEP preserves solids, not native Onshape parametric history", "No learned model weights or physical tests"]}
    for filename, data in (("parameters.json", asdict(parameters)), ("validation.json", report)):
        with (output / filename).open("x", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, allow_nan=False)
            stream.write("\n")
    if not roundtrip:
        raise ValueError("STEP read-back did not match generated geometry; inspect validation.json")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-fixture", help="Generate original test solids and STEP read-back evidence, not a complete robot")
    build.add_argument("--parameters", type=Path)
    build.add_argument("--output", type=Path, required=True)
    inspect = commands.add_parser("inspect-step", help="Inspect local STEP geometry without uploading it")
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "build-fixture":
            values = json.loads(args.parameters.read_text(encoding="utf-8")) if args.parameters else {}
            result = export_fixture(FixtureParameters(**values), args.output)
        else:
            if args.report and args.report.exists():
                raise FileExistsError("Inspection report exists; choose a new file")
            result = inspect_step(args.file, progress=True)
            if args.report:
                with args.report.open("x", encoding="utf-8") as stream:
                    json.dump(result, stream, indent=2, allow_nan=False)
                    stream.write("\n")
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, OSError, RuntimeError) as error:
        print(f"CAD error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
