# Competition scouting workbook

Resolve the event/program/season and verify its roster before collection. Prefer current official event sources and documented APIs; links and installed code are not live API access. If the event name identifies multiple competitions, resolve the ambiguity. Include every roster team, including unobserved teams.

Use `assets/event.template.json` for event metadata and `assets/scouting-ledger.template.json` for each match. The latter is a blank schema, not a usable dataset until actual match/source fields and observations are provided. Read `scouting.md` for record fields and eligibility. Corrections stay in one ledger per match; merge independently captured windows before export and reject overlaps. Multiple ledgers with the same match ID are refused to prevent accidental double counting.

From the skill folder:

```sh
python -m pip install 'openpyxl>=3.1.5,<4'
python scripts/export_scouting.py event.json match-1.json match-2.json --output scouting.xlsx
```

Install the optional spreadsheet dependency only if missing and software installation is authorized; prefer an existing environment. No dependency is a video tracker. Without Python/openpyxl use an available spreadsheet skill/tool and reproduce these evidence semantics; deliver `.xlsx`, not merely Markdown or CSV renamed to Excel.

Sheets:

- Teams: roster, number of supplied observed match ledgers, observed scoring lower bounds, eligible piece counts/seconds/rates, unresolved records, replay exclusions, coverage caveats.
- Matches: per-team/per-match metrics. A missing row is not a zero score.
- Observations: all raw records, source intervals, visibility/review/replay/correction status, evidence and rule references. Capacity lower bounds, visible motors, retention tricks, simultaneous actions and struggles remain evidence, not inferred hidden totals.
- Mechanisms: team, description, evidence, source URL, uncertainty.
- Recommendations: team, action, evidence, source URL, bench test, uncertainty.
- Sources: explicit source URLs/descriptions.
- Readme: identity, data status, definitions, limitations and regeneration instructions.

Rates are weighted by total eligible active seconds, not an average of window averages. Unknown measurements remain `Unknown`, never zero. Observed points are not official totals. Keep official alliance scores in a separate explicitly labeled source/report if needed; do not attribute them to individual robots without evidence. No ranking based on missing data.

The exporter creates a static, formula-free reviewed snapshot. Edit source JSON and regenerate to recompute; do not present it as an editable scoring model. Raw external strings are stored literally, not as formulas or macros. It refuses overwriting files. Use a new filename per revision and inspect the resulting workbook's sheets, rows, values and evidence before delivering it.

If no live pipeline or usable footage exists, a roster-only workbook must say `Not scouted — no usable video observations`, with all measurements unknown. Do not describe it as a completed scouting run. If no verified roster is available either, report that missing input; do not invent team entries.
