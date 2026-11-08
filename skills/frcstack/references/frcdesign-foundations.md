# FRCDesign foundations

The [complete lesson index](frcdesign-course-index.md) covers the course from setup through independent projects. Exercise values describe the selected example. Transfer dimensions and fits to a new robot using the actual parts, loads and manufacturing process.

## Orientation and setup

Learn the editor and library route appropriate to the host. Confirm units, orientation, account access and operation of the needed tools. Benchmark a repeat build from a clean start, identify the slowest steps and compare the result with measured requirements. Keep geometry, regeneration and verification timings separate. [Improvement lesson](https://frcdesign.org/learning-course/stage1/1a/focusing-on-improvement/)

Use the source, version and configuration of each library part. A light display configuration can make reviews faster. Check whether its omitted features affect the interfaces under review. Tube Converter, Robot Shaft, Robot Spacer, Belt & Chain Gen and Origin Cube are dependencies of particular workflows. Confirm access and behavior before relying on them. [Part library](https://frcdesign.org/learning-course/course-setup/required-course-tools/part-library/) · [Custom features](https://frcdesign.org/learning-course/course-setup/required-course-tools/featurescripts/)

## Stage 1A — Parts and assemblies

| Exercise | Application | Evidence |
|---|---|---|
| Navigation and first tubes | Establish a useful view and origin. Build separate members from explicit stock, wall and hole-pattern inputs. | Inspect units, part count, wall thickness and clear bore. |
| More tubes and sketch basics | Derive lengths from reference faces or dimensions. Constrain shape and position and use symmetry where intended. | Change a driver dimension and inspect the affected members. |
| Drivetrain frame | Lay out rail and wheel datums before manufacturing features. Reserve access for the real mounts. | Measure wheelbase, track and frame extent after regeneration. |
| Box and triangle frames | Derive member angles and section orientation from the superstructure layout. | Verify diagonals, angled joints and alignment. |
| Plate workflow and gussets | Locate functional holes first. Shape the perimeter for edge distance and access. | Check holes against mating geometry and the chosen manufacturing process. |
| Superstructure panels | Pattern interfaces that truly repeat. Allow for hardware, wiring and removal. | Verify panel fit and removal path. |
| Motor mounting | Locate the exact face, boss, shaft and bolt pattern. Include fastener engagement and wrench clearance. | Compare modeled axes and faces with the selected motor and gearbox. |
| Rivets, swerve and gusset setup | Select grip length and access for real hardware. Use a consistent datum for each corner and pattern instances only where appropriate. | Inspect module orientation, fastener reach and load path. |
| Full frame and finishing | Build subassemblies with purposeful degrees of freedom and clear names. | Inspect inventory, mates, measured clearances and export readback. |

Use a stable datum and drive dependent dimensions from the master geometry. A useful regeneration test is changing the spacing of symmetric crossmembers and checking that both move while their offsets and joint interfaces remain consistent. [Part Studio setup](https://frcdesign.org/learning-course/stage1/1a/section1-setup/) · [Swerve assembly](https://frcdesign.org/learning-course/stage1/1a/section3-exercise2/)

## Stage 1B — Power transmissions

Start with required output speed, working torque, duration and expected load. Relate speed and torque with the selected ratio, then account for efficiency, current, heat, starts and shocks. Vendor curves and physical tests supply different evidence. [Motors](https://frcdesign.org/learning-course/stage1/1b/motors/) · [Torque and speed](https://frcdesign.org/learning-course/stage1/1b/torque-speed/)

- Gears. Match the tooth system and pressure angle. Make pitch circles tangent for nominal spacing of standard external gears. Multiply driven-to-driver ratios across stages and track rotation direction at each mesh. Evaluate backlash and tooth strength separately. [Gears](https://frcdesign.org/learning-course/stage1/1b/gears/)
- Belts. Choose a stocked pitch and tooth count. Solve the pitch path before freezing shaft locations. Model the full loop, engagement, flange clearance, adjustment range and installation access. [Belts](https://frcdesign.org/learning-course/stage1/1b/belts/)
- Chain. Use compatible sprockets and a feasible stock link count. Account for adjustment, loaded spans, service and wear. Use the vendor's chain sizing method. [Chain](https://frcdesign.org/learning-course/stage1/1b/chain/)
- Supports. Size shafts, bearings or bushings, spacers and retention from the actual load path. Check support alignment, axial capture and rotating surfaces against stationary parts. [Shafts and bearings](https://frcdesign.org/learning-course/stage1/1b/shafts-bearings/)

| Exercise | Check on a new design |
|---|---|
| Simple gearbox | Constrain axes and derive plates. Inspect center spacing, bolt pattern, shaft protrusion, bearing and spacer fit. |
| Two-stage gearbox | Identify compound gears sharing a shaft. Check both center distances, ratio, direction and retention. |
| Gear and belt gearbox | Close the belt loop at an available length and derive plates from resulting axes. Verify engagement, tension travel and surrounding clearance. |

Use the [local layout calculations and complete-drive criteria](frcdesign-validation.md). An empty gearbox housing and two pulley circles cannot show a verified power path. An exact purchased assembly can supply that path when the configuration and interfaces are documented.
