---
name: frcstack
description: Create FRC/FTC Onshape robot CAD using real component libraries, scout competitions into evidence-backed Excel workbooks, reconstruct observed robots, and review mechanisms. Supports create, scout, replicate, review, compare, and bom workflows.
---

# FRCstack

Turn a team's requirements and observed match behavior into editable Onshape designs and evidence-backed scouting records. Onshape is the primary CAD target; YouTube live broadcasts are the primary scouting input. Use available host capabilities rather than pretending a skill is itself a live video inference service.

## First run

Interpret `/frcstack <requirements>` as `create` by default. Explicit commands:

| Command | Outcome |
| --- | --- |
| `create <requirements>` | Editable Onshape parts/assemblies, or clearly labeled unexecuted source if access is unavailable. `design` is a compatibility synonym. |
| `scout <competition URL/name>` | Per-team `.xlsx` scouting workbook with timestamped evidence, unknowns, and coverage. |
| `replicate <team> <competition/latest>` | Evidence-backed robot reconstruction, not a promise of 100% accuracy. `reconstruct` is a synonym. |
| `review <model/mechanism>` | Interface, rule, motion, and manufacturing review. |
| `compare <teams/event>` | Comparable observed performance/mechanisms with coverage and confounders. |
| `bom <model/version>` | Sourced parts list: exact vendor/configuration, quantities, custom parts, unknowns. |
| `setup` or `help` | Capability inventory and usage guide. |

These are arguments after the skill name, not universally registered independent slash commands. Do not interpret an empty invocation as permission to invent a whole robot: ask for the design goal. The optional `frcscout` skill routes `/frcscout replicate ...` here.

Read the applicable references: [live scouting](references/scouting.md), [reconstruction](references/reconstruction.md), [Onshape CAD](references/onshape.md), and [engineering checks](references/engineering.md). Load only those needed.

Create a separate team profile from [the template](assets/team-profile.template.json) for each program, team number, and season. Ask for missing design-critical inputs; do not assign another team's standards or use unconfirmed dimensions for fabrication. Store profiles in the user's project, not in this public skill. Do not include student names, passwords, tokens, or unrelated personal data.

Inventory the tools actually exposed for video frames/stream capture, temporal tracking, CAD editing, code execution, and official results. State each as tested, available-but-untested, or unavailable. An open YouTube page is not evidence of continuous frame access. A transcript is not a substitute for watching a mechanism. An Onshape login is not an API integration.

Explain the selected setup and invocation examples. `/frcstack help` should repeat this guide. Native slash syntax is host-dependent; “Use frcstack to ...” is the fallback.

## Orchestration

Choose one orchestration owner. If invoked through `/autopilot frc`, Autopilot already owns orchestration: supply the FRCstack domain workflow directly, never route back to Autopilot. If invoked directly and Autopilot is installed, read its applicable routing guidance once and apply it without reinvoking `/autopilot frc`. Autopilot is optional. Without it: scope the deliverable, discover actual tools, plan around dependencies, execute authorized steps, verify, and checkpoint evidence. Use specialists only when relevant and available; no stack, paid provider, or swarm is mandatory.

## Shared evidence and season rules

Pin program, season, event/match identity, team identity, and video source before observations. Confirm rules from current official FIRST materials and applicable updates/Q&A; record rule IDs, revision, source URL, and check date. Upcoming unreleased games have unknown rules. Never reuse FRC limits for FTC or one season's scoring weights for another.

Use the [primary source entry points](references/sources.md) to locate current manuals, APIs, and modeling documentation.

Keep observations, hypotheses, dimensions, and recommendations separate. Label a dimension as measured, manufacturer-specified, estimated, or unknown. Label an event direct, ambiguous, or occluded, plus its review status. Never turn a visual guess into a verified count or calibrated probability.

## Scout a live broadcast

Use [live scouting](references/scouting.md). Track each match and robot separately, keep an append-only evidence ledger, and aggregate only eligible observations. Required targets include intake throughput, firing throughput, simultaneous intake/firing, retained/lost fuel, apparent hopper lower bounds, visible motors, mechanism concepts, and visible struggles. Every claim needs source timestamps and visibility limitations.

Resolve a competition name to a verified season/event URL and roster; ask only if identity is ambiguous. Include every roster team, not just visible/high-performing robots. Read [workbook export](references/workbook.md) and deliver an actual `.xlsx`, not a prose substitute. If a source or pipeline is missing, a clearly labeled partial workbook may contain roster/context plus unknown measurements; it is not a completed scouting run. `compare` uses comparable evidence/conditions and does not rank unknowns as poor performance.

If a live frame/tracking pipeline is unavailable, report the missing capability and produce a setup/specification or analyze an accessible supplied clip. Never claim to be continuously watching, collecting in the background, or measuring live latency without a running verified pipeline.

## Reconstruct a robot from video

Use [reconstruction](references/reconstruction.md). Produce an updateable visible-geometry proxy with uncertain regions explicitly tagged. Do not equate a proxy, mesh, Gaussian splat, or render with editable manufacturing CAD. Occluded internal motors, wiring, material thickness, hopper fullness, and rated performance remain unknown without additional evidence.

For `latest`, check current public team/event evidence and record the as-of date and chosen robot iteration. Latest published CAD, latest match footage, and the team's current private robot may differ. Cite which is being replicated. Prefer permission-compatible public source CAD and manufacturer parts when available. Never claim exact hidden internals or 100% accuracy from video. Keep estimated/verified components visibly distinct.

## Create and improve Onshape CAD

Use [Onshape CAD](references/onshape.md) and [engineering checks](references/engineering.md). Build editable parametric Part Studios and assemblies in a verified user-authorized document/workspace. Generate FeatureScript when appropriate; assemblies and document operations require separate host/API/UI capabilities. Version changes, measure geometry, verify motion/clearances, and produce drawings/BOM/exports when requested.

For FRC purchased components, start with FRCDesignLib through FRCDesignApp and the team's approved manufacturer libraries. It is a community-maintained library, not a FIRST-authored guarantee of correctness or legality. Insert/derive exact part numbers and configurations; verify critical interfaces against manufacturer drawings and record source versions. Create custom parametric parts around those interfaces, not approximate substitutes for catalog components. For FTC, resolve the separate FTC library linked by Onshape and the team's actual vendors rather than assuming FRC hardware fits.

Video-derived observations may motivate a design proposal. They do not establish exact dimensions, hidden geometry, strength, manufacturing fit, or legality. Obtain or derive the missing engineering inputs before claiming a design is fabrication-ready.

For `bom`, read the verified model/version and component provenance. Separate purchased and custom parts; include exact variant, quantity, material/process, source URL, and cost/check date only when sourced. Unknown quantities/prices remain unknown. No purchase or paid upload follows from creating a BOM.

## Completion

Deliver the actual accessible Onshape document/version or clearly label unexecuted source/instructions. Include a validation record, assumptions, unresolved risks, and next practical test. Scouting reports include coverage, corrected event counts, rate denominators, unknown periods, and evidence for recommendations. No claim of accuracy or real-time operation without measured evidence from an operating pipeline and reviewed ground truth.
