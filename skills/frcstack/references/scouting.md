# Live YouTube match scouting

## Connect and observe

Confirm the public broadcast URL, event, season, target team(s), and intended capture duration. Respect stream access controls and service terms. Prefer an exposed supported video/frame tool. Use a continuous capture/tracking runner only if it is actually installed and operating; do not invent URLs, plugins, models, API methods, or connection status. Do not install background services, obtain credentials, or spend API credits merely because a scouting workflow requests data.

Record source presentation timestamps and wall-clock observation times separately. Handle stream buffering, delayed broadcasts, pauses, replay segments, cuts, duplicate frames, and reconnects. Maintain one match ID and clock alignment per round. Suspend automatic event counting during replay/unknown match identity. A replay must not count as a second scoring event.

Detect bumper/team identity across camera views. Track uncertainty when robots overlap, disappear, or cross paths; do not silently switch identities. Keep event IDs and original evidence immutable. Corrections supersede prior records and explain the change. Do not identify or score individual students from faces or behavior.

## Requested metrics

| Metric | Evidence and reporting rule |
| --- | --- |
| Fuel pickup rate | Count visible, attributable game-piece entries over a stated active-intake interval. Report pieces/s, interval length, observed count, and sampling coverage. Disappearing pieces near an intake do not automatically prove collection. |
| Firing rate | Count visible departures over a stated firing interval. Distinguish pieces launched, attempts, and pieces confirmed scored. Do not infer hit counts from motor sound or a blurred stream. |
| Simultaneous intake and firing | Report verified overlapping intervals of intake and firing, with evidence for both. A single screenshot or shots in adjacent intervals does not establish simultaneity. |
| Hopper capacity | Report a lower bound only when retained contents and initial fullness are supportable. Otherwise give a hypothesis range with assumptions, or unknown. Pieces fired are not capacity when the robot reloads concurrently. |
| Motor count | Count only distinct visible motors or documented manufacturer/team components. Identify duplicates across viewpoints. Hidden motors and shared transmissions remain unknown. Keep motor models and legality unverified until sourced. |
| Fuel retention concept | Describe visible flaps, gates, compliant fingers, geometry, rollers, belts, or routing. Separate observed mechanism from a hypothesis about its function. Track spill events with timestamps. |
| Cycle time | State the cycle boundaries (e.g. intake acquisition to confirmed scoring completion). Show median, spread, number of complete cycles, and incomplete/occluded cycles. Do not combine different definitions. |
| Struggles and missed opportunities | Record repeated alignment, reversals, jams, stalls, wheelspin, oscillation, spills, tipping, approach clearance problems, delayed firing, and downtime. Separate external defense from apparent robot/driver limitations. |

Express rates as interval-specific observations, not universal maximum capability. Do not infer exact RPM, motor torque, electrical current, material strength, internal capacity, or rated motor count from ordinary broadcast footage. Do not report zero during camera gaps. If sampling cannot resolve each game piece, decline an exact count and retain an interval/range or unknown.

Use official field CAD/drawings or measured references for metric positions. A camera homography applies to a calibrated plane, not every moving robot point at different heights. Broadcast zoom/cuts require recalibration. Raw pixels do not yield reliable field speed without calibration.

## Score attribution

Read the selected season's scoring rules and eligibility windows. Associate each candidate score with the robot, piece/action, period, timestamp, scoring condition, outcome, and evidence. Keep observed score lower bounds distinct from official match totals. Alliance scoreboard changes do not identify a specific robot's contribution unless the source explicitly provides it. OPR and other statistical estimates are not measured robot points.

FIRST's FRC score-details API supplies completed matches, not in-progress match scores. Use it for reconciliation after the match. The Blue Alliance can provide event/match context and alliance breakdowns when authorized credentials exist; do not assume every scoring field is individual-robot data. FTC needs its own current official data sources and rules.

## Diagnoses and advice

For each recommendation provide: observed symptom, timestamped examples, plausible explanations, counterevidence, proposed change, expected benefit, and a discriminating pit/bench test. Example: wheel motion with little translation supports possible wheelspin; it does not prove inadequate torque. Oscillation may involve control tuning, compliance, or impacts. Ask for logs or controlled tests before choosing a cause.

Rank improvements by demonstrated time/score loss, frequency, implementation effort, design risk, and uncertainty. Include strengths worth preserving. Highlight overlooked confounders: defense pressure, fouls, game phase, power-limited behavior, alliance coordination, field obstructions, and camera blind spots.

## Live output and quality gate

Maintain match/team event JSON, readable CSV, and a short round report. Include last-received frame time, processing lag, coverage/unknown intervals, correction history, and data-source attribution. A real-time 3D display must be backed by an operating tracker; a skill file does not create one.

Before claiming accuracy, manually annotate representative held-out clips with a second review. Measure identity switches, missed/double-counted events, event precision/recall, count error, timestamp error, visibility coverage, and latency at the actual frame resolution/rate. Include hard cases: rapid firing, concurrent intake, crowded field, glare, occlusion, camera cuts, replay, reconnect, partial match, and different robots. The user chooses acceptable thresholds; absent thresholds, report measured results without an “accurate” or “production-ready” label.

The bundled `scripts/summarize_scouting.py` validates an already-produced observation ledger and aggregates eligible records. It is not a vision model, live-video client, or independent proof of ground truth. Null output means insufficient observations, not a measured zero.

### Ledger records

Each observation has `id`, `team` (digits as a string), `kind`, `start_s`, `end_s`, `visibility` (`direct`, `ambiguous`, or `occluded`), `reviewed` (boolean), `is_replay` (boolean), and nonempty `evidence` describing source frames. Supported kinds are `intake_window`, `fire_window`, `score`, `spill`, `struggle`, `visible_motors`, `capacity_lower_bound`, and `simultaneous`. Optional `supersedes` refers to an earlier record with the same team/kind; corrections remain auditable in the original ledger.

Intake/fire windows require a nonnegative integer `count`, positive duration, and no overlapping count window for the same team/kind. Score records require `outcome` (`scored`, `missed`, `unknown`); numeric `points` additionally require a nonempty `rule_ref`. Unknown points remain null. Non-rate observations are preserved in the ledger rather than turned into invented quantitative metrics.

Run `python scripts/summarize_scouting.py <ledger.json> [--output <summary.json>]`. The helper includes only direct, reviewed, non-replay, non-superseded observations in measured count/rate aggregates. It keeps unresolved records separate and reports points strictly as a video-observed lower bound, never an official team score or estimated hopper capacity. Output refuses to overwrite an existing file.
