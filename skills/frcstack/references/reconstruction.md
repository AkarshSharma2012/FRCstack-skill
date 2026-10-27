# Visible robot reconstruction

Separate three deliverables: a live tracked visual proxy, an inferred mechanism explanation, and a dimensioned editable design. None automatically establishes the others.

## Inputs and uncertainty

Use multiple useful views, known field landmarks, and manufacturer component dimensions where identifiable. Record view timestamps, calibration, assumed scale, and dimensional uncertainty. Do not use a guessed full robot dimension as the sole scale reference and then claim an independently measured envelope.

Broadcast robots move, mechanisms articulate, camera views jump, and surfaces are repetitive or reflective. Ordinary static-scene photogrammetry cannot be assumed to work on these frames. If using a reconstruction library, follow its documented assumptions, test it on the footage, and label failures. One RGB view does not uniquely determine hidden or absolute-scale geometry.

## Updateable proxy

Identify chassis, bumpers, wheels, intake path, hopper, shooter, turret, elevator/arm, and obvious linkages. Use simple bounded parametric approximations until evidence supports more detail. Maintain a component graph with measured/estimated/unknown dimensions, source views, and observed degrees of freedom. Preserve separate configurations for observed poses. Do not fill unseen sides with invented engineering detail.

A live proxy may update position, pose, and mechanism configuration while dimensions remain estimated. Show its uncertainty in the display and exports. Do not claim a live reconstruction exists merely because a static rendering was generated.

## Transfer to Onshape

Create named variables and features, separate moving components, and explicit mates for supported motion. Include source evidence and an assumptions table. Imported meshes/STEP files can be references, but they do not create editable native feature history automatically. Reconstruction exports must be labeled concept/reference and cannot be released for manufacturing without measured interfaces, loads, materials, tolerances, and rebuild/fit checks.

Proposals inspired by a visible retention trick should describe the underlying principle and adapt it to the team's known geometry. Record the source of reused public components and their reuse/license conditions; do not mix a team's private documents into another team's deliverable.
