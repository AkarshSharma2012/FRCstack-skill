# Exact-source component placement

The optional `scripts/component_runtime.py` assembles local purchased STEP geometry with explicit source provenance and rigid transforms. It does not fetch models, infer a configuration, solve mates or generate a whole robot.

Use the same optional CAD environment as [local execution](free-resources.md). Keep third-party files in a private working directory, outside the public skill. The manifest and each STEP source belong under one directory tree. Pin source hashes and revisions before importing. A URL records a source, not permission or proof of correctness.

```json
{
  "schema": 1,
  "components": [{
    "instance_name": "left_module_plate",
    "file": "vendor/part.step",
    "sha256": "REPLACE_WITH_THE_ACTUAL_64_HEX_SHA256",
    "manufacturer": "ACTUAL_MANUFACTURER",
    "part_number": "EXACT_CONFIGURATION",
    "source_revision": "ACTUAL_SOURCE_REVISION_OR_EXPLICIT_UNKNOWN_LABEL",
    "source_url": "https://vendor.example/actual-source.step",
    "translation_mm": [0, 0, 0],
    "rotation": {"axis": [0, 0, 1], "degrees": 0}
  }]
}
```

This is an input template, not a usable manufacturer specification. Replace every placeholder. Transforms use the source-model origin: rotate first, then translate, with no scaling. Validate the source's datum against the drawing before choosing mating positions. Zero is an explicit choice, not proof of correct installation.

```sh
python scripts/component_runtime.py assemble path/to/manifest.json --output path/to/NEW-revision
```

From a repository checkout, use `skills/frcstack/scripts/component_runtime.py`. Never reuse an output directory. Preserve the manifest, source bytes, source hashes, `assembly.step` and `validation.json` together. Read `export_success`, `roundtrip_passed` and `clearance_passed` separately: actual overlap may export correctly while failing clearance; an import/kernel/round-trip failure is not a verified assembly.

Geometry read-back checks every solid and its location. Semantic instance identity, source appearance, native feature history, physical material properties and mate constraints require separate verification; a STEP solid collection cannot establish them. Positive-volume intersection checks do not establish minimum gaps, tolerance stacks, continuous moving clearance, fastener access or strength. A layout with two catalog plates is evidence of source placement, not a configured swerve module or robot.

Before integrating a real subsystem, verify the exact vendor variant, all critical drawing interfaces and its intended native assembly mates. Record measured modeling and verification times and any failed cases. Never promote a nearby part number, guessed transform or unexecuted analysis into a passed engineering check.
