# Native Onshape execution fixture

`assets/features/roller-fixture.fs` is original FeatureScript source, tested in Onshape with language and standard-library version 3095. It creates two drilled plates, a shaft and a hollow roller as four separate named solids. It is a backend integration test, not a purchased mechanism, complete robot, or fabrication package.

## Execute in an authorized document

1. Verify the document, mutable workspace and editing access. Preserve a baseline version. Do not alter sharing or a reference owner's source document.
2. Create a Feature Studio, paste the source and commit it. Resolve actual compiler errors; a local syntax/text check cannot compile FeatureScript. Do not change language/import versions blindly.
3. In a separate Part Studio, select the workspace custom feature `FRCstack test roller fixture`. If using Add custom features, an immutable version must contain the Feature Studio. Creating a version does not require publishing the custom feature; leave publication off unless authorized.
4. Check the nine millimetre parameters, regeneration status and four named parts. Export the whole Part Studio as STEP AP242, preserving axes/units and all four bodies. Independently inspect the resulting solids, dimensions and volume.
5. Repeat the variant and invalid-input cases below. Restore a valid state and create an immutable version with factual validation notes.

| Executed case | Expected result |
|---|---|
| Defaults: inner span 400, plate 80 × 120 × 6, hole 13, shaft 12, roller length 360, OD 50, bore 14 mm | Four solids; overall bounds 412 × 80 × 120 mm; summed volume 811643.967411 mm³ |
| Inner span 500, roller length 450 mm; other values unchanged | Four solids; bounds 512 × 80 × 120 mm; summed volume 985813.864126 mm³ |
| Bore 50 mm with OD 50 mm | Refused: shaft diameter < bore diameter < roller diameter is required; no successful geometry claim |

These are the executed cases, not proof that every combination within the UI bounds is safe. The Python helper's broad numerical bounds differ from the FeatureScript UI bounds; only shared valid inputs should be compared. No material or physical mass is assigned.

## Native assembly check

Insert the four generated parts once, retaining their Part Studio positions. Fix the left plate and group the two plates plus shaft. The roller must remain outside that stationary group.

For this origin-centered fixture, create one explicit connector at each of the shaft and roller instance origins. Rotate each connector about Y by 90 degrees so its primary Z axis follows the modeled shaft's world X axis. Define a revolute mate with the roller connector first and stationary shaft connector second. Verify both connector ownerships, the accepted mate and actual assembly position. Do not infer correctness from the tree names alone.

Executed native test: single animation, start 0°, end 360°, 36 steps, observed final current value 360°. The assembly STEP was also checked against independent BReps; all four solids matched and had no positive-volume static intersections. Because the roller is axisymmetric, its silhouette alone does not demonstrate rotation. Retain the angle readout and connector/mate evidence.

This does **not** establish continuous swept collision checking, bearing/retention design, drive torque, loads, strength, fuel handling, physical performance or complete robot functionality. STEP contains exported geometry, not native mate history. Keep the immutable Onshape assembly and evidence record alongside exports.

## Independent verification

The optional `scripts/cad_runtime.py` constructs the same nominal geometry independently in CadQuery. Compare all imported roots and all four solids, not only the first root. Bounds and total volume are insufficient by themselves: a misplaced hole can preserve both. For the executed fixture, each native solid was paired uniquely with its independent counterpart and both directional Boolean differences were checked; the sum was zero within a 0.0001 mm³ acceptance threshold. Pairwise static intersections and independently calculated volumes were also checked.

Separate the evidence: native UI/compiler/parameter/mate observations establish native execution, while STEP/kernel checks establish exported geometry. Neither establishes FEA or manufacturing readiness. Host-specific UI access is required; this file does not install an Onshape API connector.

## Role appearance check

Both backends apply an illustrative palette: plates RGB (0.72, 0.74, 0.77), shaft (0.42, 0.45, 0.49), roller (0.08, 0.09, 0.11). These are appearance roles, not verified team colors or engineering material assignments. No density or physical mass is implied. Existing manual Part Studio appearance overrides can take precedence over FeatureScript appearances.

Executed in Onshape: the updated FeatureScript compiled, all four parts regenerated, and colors propagated to the native assembly. Assembly STEP AP242 read-back preserved the four named part colors within 0.002 per channel (8-bit export quantization). Each colored native solid matched its independent counterpart with zero reported symmetric-difference volume; no positive-volume static intersections were found. A Part Studio STEP can contain valid colored solids without being a semantic assembly: use the actual assembly export when checking per-instance names and colors.

Primary documentation: [FeatureScript library](https://cad.onshape.com/FsDoc/library.html), [mate behavior](https://cad.onshape.com/help/Content/Assembly/mates.htm), [revolute mate](https://cad.onshape.com/help/Content/Assembly/revolute_mate.htm).
