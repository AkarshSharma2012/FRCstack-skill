# Team-grounded design decisions

Checked October 29, 2026. These are reference-based workflows, not trained model weights or universal team standards. Distinguish the published practice from FRCstack's proposed application below. Preserve the user's complete robot specification; a simpler reference is not permission to shrink it.

## Requirements before mechanism: Robonauts 118

The [2026 Everybot team thread](https://www.chiefdelphi.com/t/the-2026-robonauts-frc-everybot-low-resource-build/510331) describes a requirements list independent of the mechanism chosen to meet it. The team documents a design change toward modifying KitBot components and cautions that unpublished swerve-module support and chassis dimensions were not yet certain at those posts. Their [project site](https://www.118everybot.org/) emphasizes basic tools and tolerance accommodation.

FRCstack application: write measurable functions, required states and shop capability before choosing architecture. Record each interface's source revision. A similar-looking module is not an interchangeable mount. A changed reference decision invalidates affected interfaces and requires a new check; do not carry an early estimate into fabrication drawings as a confirmed dimension.

## Interfaces before detailed plates: HighTide 4414

The team's [2026 RIPCURRENT binder](https://2026.team4414.com/) describes a block model that includes power transmission and critical geometry while initially simplifying plate outlines. Detailed parts follow the established layout. Its published drivetrain includes custom geometry, so a stock vendor plate alone is not evidence of the complete team's configuration.

FRCstack application: establish axes, bearing seats, transmission spacing, component configurations, moving envelopes and fastener access before cosmetic profiles. Label unknown interface dimensions explicitly. Keep simplified space claims separate from verified purchased geometry. Accept a detailed revision only after its interface and motion checks still pass; visually plausible plate outlines do not prove fit.

## Resource-dependent architecture: Spectrum 3847

Spectrum's [MCC guide](https://spectrum3847.org/resources/frc-mcc-guide/) prioritizes reliable chosen functions, early driving/tuning, maintainable wiring and designs within the team's resources. It includes CAD sketches for linkage mounting and full-scale templates for shops without CNC equipment. Its historical drivetrain recommendations are contextual, not a universal prohibition on swerve or a current-season rule.

FRCstack application: compare options against the actual deadline, manufacturing capability and required functions. Record the rejected alternative and reason. Plan service access and an inexpensive physical test of the highest-risk behavior. Do not replace the requested benchmark architecture merely because a simpler concept would pass a smaller test.

## Apply the cases in create, debug and review

1. **Create:** record requirements, architecture rationale, a subsystem dependency graph and interface table. Each dimension is sourced, measured, estimated or unknown. Lock exact vendor/configuration/revision before generating custom mounting geometry.
2. **Debug:** reproduce the failure at a named version; classify source identity, units, datum, placement, regeneration, constraint, collision, load or manufacturing error. Measure before changing geometry. Recheck dependent interfaces after a fix.
3. **Review:** compare delivered geometry with requirements and independent references. Inspect all bodies/occurrences, actual exported positions, intended motion and service access. A green geometry export is not a passed fit, structural or game-performance test.
4. **Release:** retain source versions, parameters, exact component provenance, drawings/BOM and executed checks. List every unexecuted load, motion, physical or rules check. Time actual modeling plus verification, excluding reference download time only if explicitly reported separately.

This workflow supplies engineering decisions to the executing agent; it does not install a solver, connect Onshape or fill unknown geometry automatically.
