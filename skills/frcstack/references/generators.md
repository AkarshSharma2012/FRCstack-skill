# Generator selection and execution gates

Checked October 29, 2026. Select a generator for a defined interface, not because it has an impressive name. The [FRCDesign maintained index](https://www.frcdesign.org/resources/featurescripts/) documents the following candidates; discovery is not execution or installation evidence.

| Need | Candidate from the index | Required independent check before acceptance |
| --- | --- | --- |
| Belts and chain | Origin Cube FRC Functions plus Belt & Chain Gen | Exact pitch, teeth, center spacing, wrap, tension adjustment and moving clearance; a visual belt is not a verified purchase length. |
| Shafts and spacers | Robot Shaft / Robot Spacer in Alex's bundle | Actual cross-section, length, retention, fits and tool access against sourced mating hardware. |
| Punched tube | Tube Converter in Julia's bundle | Stock profile, wall, hole pitch and orientation; postpone expensive repeated features until interfaces are stable. |
| Custom spur or sector gear | Spur Gear | Pitch system, pressure angle, teeth, bore, backlash and mating center distance; geometry does not prove printed tooth strength. |

Choose exact catalog parts from [FRCDesignLib through FRCDesignApp](https://www.frcdesign.org/resources/frcdesignlib/) for purchased hardware, not a visually similar generated substitute. The library is community-maintained. Verify the source revision/configuration and manufacturer's drawing. Account installation or subscription steps are separate from source discovery and may require the user's authorization.

[Gear Generator 3](https://geargenerator.com/) is a separate product, not an installed Onshape feature. Its web exports require an export pass; its [desktop products](https://geargenerator.com/desktop.html) require a license. Do not purchase, activate, bypass export gating or claim an integration by mentioning the product. Prefer an available permitted native generator for the current task; record an unmet capability if that route cannot produce the required geometry.

For every chosen generator, record its owner, exact document/version/feature identity, parameters and expected analytic/drawing dimensions. Run nominal, useful variant and invalid-input cases in the actual CAD backend. Inspect regenerated solids and exported geometry, not only a successful button click. Record timing including regeneration and verification. A local source file is unexecuted until its native feature compiles and regenerates; an assembly mate or structural study needs its own executed evidence.
