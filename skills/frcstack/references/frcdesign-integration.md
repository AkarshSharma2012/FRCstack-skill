# FRCDesign subsystem integration

The [course index](frcdesign-course-index.md) links every lesson in Stages 1C, 1D and 1E. Apply these patterns with the selected hardware and team process.

## Stage 1C — Practice mechanisms

| Exercise | Transferable design method | Evidence to collect |
|---|---|---|
| Flat intake | Design live roller shafts, belt reduction and frame attachments together. Support clamped thin tube where needed. | Change width and verify shaft and spacer regeneration. Check infeed and service access. |
| Dead axle rollers | Fix the axle and support the rotating roller. Balance commonality with space and cost. | Verify bearing contact, axial retention and removal. |
| Shooter | Support wheels on rigid plates and choose a ratio for the required surface speed. Use a torque-transfer interface sized for the load. | Inspect full drive path, wheel support, compression and coupling. |
| Telescoping hook | Plan member overlap, sliding clearance and transfer of hook and stop loads. | Check overlap, side loading, retention and service at full extension. |
| Flipped gearbox | Adjust motor placement to tension the drive. Preserve support for the adjustment loads. | Check travel, clearance and tool access at both adjustment extremes. |
| Direction swap | Trace the sign through each mesh to get the required roller rotation. | Verify shaft spacing and actual output direction. |
| Vertical rollers | Lay out each belt stage and give the series room for installation and adjustment. | Confirm stock lengths, alignment, motion direction and tension range. |
| Indexer centering | Aim roller surface directions and contact toward the center path. Support fasteners through thin walls. | Test off-center entry, jam access and relative roller speed. |

Ground the stable datum in each subassembly. Keep intended revolute and slider motion. Use a mate sequence that lets a reviewer diagnose misalignment and overconstraints. [Practice mechanism overview](https://frcdesign.org/learning-course/stage1/1c/exercise-overview/)

## Stage 1D — Top-down design

Build a master layout around the origin, wheel and pivot axes, frame and bumper outlines, service zones and mounting planes. Define which inputs the team will vary and which interfaces must stay fixed. Derive the relevant subset into each part studio. Organize dependencies from layout to parts to assembly. Use stable references and test a meaningful parameter change before detailing. [Top-down design](https://frcdesign.org/learning-course/stage1/1d/top-down-design/) · [Layout sketch](https://frcdesign.org/learning-course/stage1/1d/layout-sketch/) · [Master sketch practices](https://frcdesign.org/best-practices/master-sketch-setup/)

Place a swerve module in the intended configuration before repeating it. Check mount coordinates, handedness, drive axis and steering envelope against its actual part model. Keep versioned subassemblies and place them against consistent datums in the top-level robot. Inspect the path and interfaces between subsystems there. [Part modeling](https://frcdesign.org/learning-course/stage1/1d/part-modeling/) · [Top-level assembly](https://frcdesign.org/learning-course/stage1/1d/top-level-assembly/)

## Stage 1E — Subsystem packaging

| Exercise | Method | Acceptance evidence |
|---|---|---|
| Battery holder | Choose location from mass, wiring, retention and removal requirements. Model the battery, restraints, connector and hand access. | Inspect the retention load path and test insertion and removal. |
| Electronics | Begin with exact envelopes, mount points and connectors. Plan power and signal routes, strain relief, bends and access. | Check actual screws, connector withdrawal and service space. |
| Bellypan pocketing | Preserve load paths from mounts to supports. Select rib and tool dimensions for the process. Pocket after main interfaces stabilize. | Compare mass and review stiffness, fastener edge distances and cutting access. |
| Bumpers | Derive the perimeter and height envelope from current season rules. Organize the bumper set for clearance review. | Record rule IDs and inspect game-piece paths, installed size and clearances. |
| Bumper mounting | Model the selected retainers, load path and installation sequence. | Verify positive engagement, tool access and actual retention separately. |

Record CAD, calculated and physical evidence separately. Treat course sample dimensions and part counts as specific to those exercises. [Subsystem workflow](https://frcdesign.org/learning-course/stage1/1e/introduction/)
