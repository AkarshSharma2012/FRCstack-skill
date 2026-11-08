# Apply the course to a CAD build

Use the [course index](frcdesign-course-index.md) to find the relevant lesson, then apply the module guidance to the actual part and assembly. Read the upstream drawing or versioned CAD for every critical purchased interface. Preserve the source geometry and identify custom geometry separately.

## Transmission layout checks

The local calculator covers two external spur gears of a common diametral pitch and an open timing belt on two pulleys. Both return nominal pitch geometry in millimetres. The belt solver uses two straight external tangents and the corresponding wrap arcs on the pitch circles. Its engagement estimate describes the theoretical wrap, not the number of teeth carrying load. Source lessons are [gear basics](https://frcdesign.org/learning-course/stage1/1b/gears/) and [belt and pulley basics](https://frcdesign.org/learning-course/stage1/1b/belts/).

Run from the skill folder with Python 3:

```sh
python scripts/transmission_layout.py spur 20 60 --dp 20
python scripts/transmission_layout.py belt 18 36 --belt-teeth 80 --pitch-mm 5
```

The spur case gives a 50.8 mm center distance and 3:1 reduction with reversed output. The belt case gives a 400 mm pitch length and approximately 131.7204 mm center distance. An equal 42T pair with a 131T, 5 mm belt gives 222.5 mm center distance. Transfer center spacing into the master layout and compare against the modeled shaft axes. Confirm tooth profile, pressure angle for gears, pulley flanges, installed tension range, engagement and vendor tolerances separately. Chain pitch geometry, idlers, crossed belts, profile shifts and loaded deflection require their own models.

## Evidence for a complete drivetrain

1. Set design inputs and constraints before laying out the frame. Document the selected season, target wheelbase and track, ground clearance, bumper envelope, stock, manufacturing process and the selected drive architecture.
2. Make a master layout with wheel axes or swerve pivots, drivetrain envelope, powertrain pitch geometry, and access zones for the battery, electronics and tools. Derive plates and rails from that layout. Regenerate at least one safe parameter change and inspect the moved interfaces.
3. For each drive side or module, trace motor through every stage to its wheels. A belt or chain stage needs the complete path, its pulleys or sprockets, identified stock size and available tension travel. A gearbox needs actual internals or a verified exact purchased assembly with a documented ratio and interfaces. Include shafts, bearings, spacers, retention, mount fasteners and tool access.
4. Distinguish authored, sourced and provisional parts in the assembly and BOM. Verify mounts against actual geometry. Check interfaces, clearance, wheel contact or drop, and representative travel. Valid STEP solids alone do not verify those relationships.
5. Export a named assembly and reopen it independently. Record geometry and assembly counts, exercised motions, exact variants, and remaining checks. Keep structural and physical claims separate. See [engineering checks](engineering.md).

## Benchmark gates

Start the timer before a fresh build session launches. Record independently observed times for the assembled artifact, its verification and the end of the run. State whether parts were cached. A complete from-scratch result requires newly authored frame and layout with integrated, verified drive hardware. Extracting a prior assembly is useful as a reference and does not establish that capability.

Use the November 8, 2026 benchmark as a negative regression case. The generated concept exported at 498.31 s but left out belt loops, gearbox internals and fasteners and used motor stubs. It fails the completeness gate even though an export exists before 600 s. The separately extracted FIRST KitBot drivetrain had 317 valid STEP solids and is a positive readback case. It fails the originality gate and the 600 s target. Keep those two outcomes separate when assessing a future run.
