# Proposed parametric chassis

This generator creates six separate hollow tube rails, a cut list and verified STEP geometry. It is an original rectangular layout, not a complete robot or an exact reconstruction of Team 4414. Its default overall envelope and tube stock are motivated by the team's [2026 technical binder](https://2026.team4414.com/). The symmetric crossbar placement is a proposed design choice. The team's custom chamfers, split rail, mounting holes, fasteners, bumper structure and module interfaces are not reproduced.

## Execute locally

Use the optional isolated CadQuery environment described in [free resources](free-resources.md). Save an explicit parameter file; no dimensions are silently filled by the Python API:

```json
{
  "width_mm": 635,
  "length_mm": 812.8,
  "stock_width_mm": 25.4,
  "stock_height_mm": 50.8,
  "wall_mm": 1.5875,
  "crossbar_spacing_mm": 300
}
```

```sh
python skills/frcstack/scripts/frame_runtime.py build-frame --parameters chassis.json --output .frcstack/chassis-001
```

Use a fresh output directory. The helper refuses linked paths and existing outputs. It creates `frame.step` and `validation.json`. Read the actual validation result: valid positive-volume solids, analytic material volume, pairwise overlap and order-independent exported geometry are checked. Failure returns a nonzero CLI result; export/readback failures retain a validation record. Input or pre-export kernel failures may stop before creating an output directory.

Coordinates: X is frame width, Y is length, Z starts at the bottom of the tubes. Side rails run the full length. Four transverse rails butt against the side rails' inner faces. Interior crossbars are centered at plus/minus half the crossbar spacing. Butt-joint face contact is allowed; positive-volume overlap fails. This geometry does not include a fastening or welding design.

The STEP assembly authors rail names and a grey appearance. This helper verifies geometry, not name/color roundtrip semantics or physical materials. Its elapsed time includes input checking, generation, export and verification; it excludes Python/kernel startup. A six-rail timing is not a whole-robot modeling benchmark.

## Native Onshape feature

`assets/features/frame-layout.fs` exports `frcstackFrame`, labeled **Proposed rectangular chassis**. Verify the authorized document/workspace before creating a separate Feature Studio and Part Studio. Use the host's actual browser/API workflow; this source does not establish an Onshape connection. Match the FeatureScript/import version to the target environment. Do not publish a feature or change sharing implicitly.

Executed October 30, 2026 with FeatureScript 3095:

| Case | Overall bounds, mm | Solids | Material volume, mm³ |
|---|---|---|---|
| Nominal parameters above | 635 × 812.8 × 50.8 | 6 | 918699.7755 |
| Width700, length900, stock30×60, wall2, spacing400 | 700 × 900 × 60 | 6 | 1499840 |

All six native rails in both exports matched independent local solids with zero reported Boolean-difference volume in both directions. No positive-volume rail intersections were found. All 60 faces per case retained the illustrative grey RGB within 0.002/channel after STEP export. An impossible 20 mm wall on 30 mm stock was refused natively with zero parts; nominal geometry was restored. The native editor's source was copied back and matched the local file after newline normalization.

This is component/layout evidence. It establishes no whole-robot completion, fitted vendor interfaces, physical material assignment, native assembly mates, motion/FEA result, rules compliance or fabrication readiness. Add exact sourced interfaces and validate the actual completed assembly before making those claims.
