# FRCDesign mechanism design

Use the [course index](frcdesign-course-index.md) for every Stage 2 lesson, including the project, layout, parts and assembly pages. Each project proceeds from requirements and load paths to layout, custom geometry, assembly and evidence.

## Stage 2A — Shooter

Start from target geometry, permissible shot positions, game-piece variation and shot cadence. Use a trajectory calculation to establish an initial angle and speed, then measure launch behavior with actual pieces. Wheel surface speed comes from radius and angular speed. The conversion to piece speed depends on contact and slip. Compare inertia, spin-up and recovery with the actual motor and thermal limits. [Trajectory](https://frcdesign.org/learning-course/stage2/2a/ball-trajectory/) · [Exit velocity](https://frcdesign.org/learning-course/stage2/2a/exit-velocity/) · [Spin control](https://frcdesign.org/learning-course/stage2/2a/spin-control/)

Drive the layout from the piece path and exit tangent. Keep guide offset, wheel size and spacing editable so compression and wrap can be tuned. Too much compression increases load. Too little contact can cause slip and scatter. Evaluate support stiffness, friction, tension, shaft alignment and accessible adjustment. Measure exit angle, clearance, shot variation and recovery. [Compression and wrap](https://frcdesign.org/learning-course/stage2/2a/compression-wrap/) · [Rigidity](https://frcdesign.org/learning-course/stage2/2a/structure-rigidity/) · [Friction](https://frcdesign.org/learning-course/stage2/2a/friction-efficiency/)

## Stage 2B — Dead axle pivot

Lay out the pivot axis, output stage, supports and stops. A fixed axle carries support loads while the mechanism turns on the selected bearings or bushings. Trace radial and axial loads and check deflection, binding and retention. Estimate output torque using the actual lever arms, orientation and worst expected load. [Strength](https://frcdesign.org/learning-course/stage2/2b/strength/) · [Friction](https://frcdesign.org/learning-course/stage2/2b/friction/)

Choose ratio and drive type from load, speed, packaging, adjustment and permitted lost motion. Check both directions of travel. Measure backlash separately from loaded deflection and verify adjustment access at a service position. Verify limit positions, stops, clearance over motion and angular lost motion when reversing. [Power transmission](https://frcdesign.org/learning-course/stage2/2b/power-transmission/) · [Tensioning](https://frcdesign.org/learning-course/stage2/2b/tensioning/) · [Backlash](https://frcdesign.org/learning-course/stage2/2b/backlash/)

## Stage 2C — Slapdown intake

Place floor, bumper, deployed and stored states, pivot and piece envelopes in one layout. Trace pickup to handoff. Test rollers across likely approach offsets and piece conditions. Treat roller speed guidance as a starting hypothesis and measure actual throughput and rejection. Give side impacts a load path to the frame and plan removal of trapped pieces. [Intake rules](https://frcdesign.org/learning-course/stage2/2c/intake-golden-rules/) · [Robustness](https://frcdesign.org/learning-course/stage2/2c/robustness/) · [Rollers](https://frcdesign.org/learning-course/stage2/2c/rollers/)

Where the roller drive passes through the pivot, model both motion paths and supports. Check that deployment maintains the intended belt geometry and clearances. Verify stop positions, wiring travel and the floor-to-handoff envelope. Sample collision through the travel and refine checks near close clearances. [Pivot](https://frcdesign.org/learning-course/stage2/2c/pivot/) · [Zombie axles](https://frcdesign.org/learning-course/stage2/2c/zombie-axles/)

## Stage 2D — Cascade elevator

Define loads, collapsed and extended envelopes, travel and service access. Derive stage lengths and overlap from the layout. Verify bearing-block alignment and anti-racking load paths. Draw each cable or chain as a continuous labeled route through the correct stages. Calculate individual stage travel and line speed for the chosen rigging before sizing the drive. [Elevator blocks](https://frcdesign.org/learning-course/stage2/2d/elevator-blocks/) · [Layout sketch](https://frcdesign.org/learning-course/stage2/2d/layout-sketch/) · [Rigging](https://frcdesign.org/learning-course/stage2/2d/rigging/)

Check chain attachment, cable clamps and terminations, bend radius, spool travel, tension adjustment and access using the selected hardware. Inspect overlap, end stops, routing and clearance through motion. Document load and stopping assumptions and a supervised test where appropriate. [Chain attachment](https://frcdesign.org/learning-course/stage2/2d/chain-attachment/) · [Cable clamp](https://frcdesign.org/learning-course/stage2/2d/cable-clamp/) · [Cable ends](https://frcdesign.org/learning-course/stage2/2d/cable-ends/) · [Drive system](https://frcdesign.org/learning-course/stage2/2d/drive-system/)

Use the [Design Handbook](https://frcdesign.org/design-handbook/) for materials, motion components and manufacturing choices. Compare design tradeoffs in the [mechanism examples](https://frcdesign.org/mechanism-examples/) and organize the model using [CAD best practices](https://frcdesign.org/best-practices/). Keep CAD, calculated and physical evidence distinct in the [engineering review](engineering.md).
