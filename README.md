# FRCstack

Onshape CAD and evidence-backed FRC/FTC scouting for agent hosts. Uses real FRCDesignLib/vendor components, team-specific standards and current-season rules. Produces actual Excel scouting snapshots from reviewed observation ledgers. Optional Autopilot integration; no paid provider required.

## Install by asking your agent

> Install FRCstack from https://github.com/AkarshSharma2012/FRCstack-skill. Inspect README.md and the installer first, use the appropriate skill directory for my host, preserve existing configuration, and explain the commands and actual available integrations.

Or with Git and Node 22+:

```sh
git clone https://github.com/AkarshSharma2012/FRCstack-skill.git
cd FRCstack-skill
node scripts/install.mjs --host claude
```

Choose `--host agents`, `--host codex`, or `--target <documented-host-skills-directory>`. The installer adds **frcstack** and the **frcscout** compatibility entrypoint. Do not install duplicate copies into multiple discovery directories for one host. Existing skills are not overwritten; explicit `--replace` moves previous versions into `.frcstack/backups` outside skill discovery. No global instructions, hooks, accounts or services are modified. Review any existing changes before replacing.

Without Node, copy both folders under `skills/` into the host's supported skills directory, preserving their references/scripts. For Chat/Cowork, upload a ZIP with `frcstack/SKILL.md` at its root folder through the supported skill interface; use a separate alias ZIP if needed. Session tools determine available operations. Restart/reload skill discovery if cached. Plain-language fallback: **Use frcstack to [goal]**.

## Commands

| Invocation | Result |
| --- | --- |
| `/frcstack create <requirements>` | Team-specific Onshape CAD using exact library/vendor parts |
| `/frcstack <requirements>` | Same as create |
| `/frcstack scout <competition link/name>` | Per-team `.xlsx`, timestamped evidence, coverage and unknowns |
| `/frcstack replicate <team> <competition/latest>` | Evidence-backed reconstruction with uncertain geometry labeled |
| `/frcscout replicate <team> <competition/latest>` | Compatibility alias for replication |
| `/frcstack review <model/mechanism>` | Rules, interfaces, motion and manufacturing review |
| `/frcstack compare <teams/event>` | Comparable observed performance and mechanism analysis |
| `/frcstack bom <model/version>` | Sourced purchased/custom parts list |
| `/frcstack setup` or `help` | Team/season profile, actual tool inventory, usage |
| `/autopilot frc <request>` | Same domain workflow through an independently installed updated Autopilot |

Slash support is host-dependent. These route agent workflows; they are not universal executable CAD endpoints. FRCstack works without Autopilot; when both exist only one owns orchestration, preventing recursive calls.

## What is implemented, and what is not

Included: installable instructions/references/templates, backed-up installer, observation-ledger validation, XLSX export, and automated local tests.

**Not bundled or connected:** a live YouTube capture service, trained robot/game-piece tracker, continuous 3D inference, an Onshape connector, account credentials, or an accuracy benchmark. An agent uses genuinely available tools or reports the missing capability. The skill cannot reveal hidden motors, exact hopper capacity, loads or unseen geometry from broadcast footage. It never promises a 100%-accurate replica. `latest` records the most recent publicly evidenced robot iteration and check date, not unseen private work.

FRCDesignLib is a community-maintained component library, normally used through FRCDesignApp. Exact configurations, critical interfaces, units and source versions require checking. FTC uses its own program/vendor libraries. Library presence does not certify current rule compliance or manufacturing readiness. See [CAD workflow](skills/frcstack/references/onshape.md) and [sources](skills/frcstack/references/sources.md).

## Scouting Excel export

Python 3.10+ and optional openpyxl 3.1.5+:

```sh
python -m pip install -r requirements.txt
python skills/frcstack/scripts/export_scouting.py event.json match1.json match2.json --output scouting.xlsx
```

Start from the [event template](skills/frcstack/assets/event.template.json) and [ledger template](skills/frcstack/assets/scouting-ledger.template.json). Fill verified event identity, roster and sources. Read [workbook semantics](skills/frcstack/references/workbook.md) and [record schema](skills/frcstack/references/scouting.md). All roster teams appear; absent footage remains unknown. Seven sheets retain team summaries, matches, raw observations, mechanisms, recommendations, sources and definitions. Rates use eligible active seconds; replays and corrected records are excluded from totals but retained as evidence. Output is a static snapshot, not official per-team telemetry. Exporting a workbook does not prove video-analysis accuracy.

## Tests and privacy

```sh
npm test
python -m unittest discover -s tests -v
```

Tests use synthetic data, not real competition results. Keep private team profiles, source CAD, stream captures, secrets and generated scouting reports in your project, not the skill repository. No telemetry or automatic uploads. MIT licensed; linked third-party CAD and media retain their own licenses.
