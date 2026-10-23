# Prompt evaluation — 10-row smoke test, not a precision measurement

Generated 2026-10-23 03:34 UTC by `uv run ingest prompt-eval`. Labels: `data/raw/labeling/eval-set-a441d1c11.csv`, rows `EV01-EV10`.

- Triage: `claude-haiku-5-5`, prompt `v1` (sha256 `b49a776f73a1`), effort `medium`
- Categorizer: `claude-opus-5-5`, prompt `v1` (sha256 `69a2e6549b6b`), effort `medium`
- Q-K bar: PROVISIONAL, not ratified (proposed by copilot for owner 2026-10-22)

**This is a 10-row smoke test, not a precision measurement.** It shows the prompts, the scoring and the spend cap working end to end. No bar is assessed below 50 labeled rows, and a gap between the parties on this few rows is noise, not a finding.

## Precision by field

Precision = the share of the AI's calls on a field that the owner's label agrees with. `proposition` is never scored (owner ruling 2026-10-22).

| Field | Bar | All | D | R | D/R gap | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `stance` | 90% | 83% (5/6) | 100% (3/3) | 67% (2/3) | 33 pts | not assessed (n=10 < 50) |
| `topic` | 90% | 100% (6/6) | 100% (3/3) | 100% (3/3) | 0 pts | not assessed (n=10 < 50) |
| `priority_signal` | 90% | 100% (3/3) | 100% (2/2) | 100% (1/1) | 0 pts | not assessed (n=10 < 50) |
| `specificity` | 80% | 83% (5/6) | 67% (2/3) | 100% (3/3) | 33 pts | not assessed (n=10 < 50) |
| `takes_policy_position` | none | 100% (6/6) | 100% (3/3) | 100% (3/3) | 0 pts | no bar |

Gap over 10 points on `stance`, `specificity` — on a smoke test this is noise and does not stop anything.

## Counts

| | |
| --- | --- |
| Labeled rows scored | 10 |
| Rows skipped as not yet labeled | 0 |
| Rows with no answer (refusal or malformed) | 0 |
| Owner said yes, triage said no (missed; not a precision error) | 1 |
| Categorizer `mixed` stance calls (outside the for/against bar) | 0 |
| How the run ended | `complete` |
| API calls (cache hits are free) | 0 (16 cache hits) |
| Spent | $0.0000 of a $0.50 run cap |

Per-row agreement marks are NOT in this report: next to the owner's public labels they would give away the model's answer for each statement (counts, never answers). They are in the gitignored `data/raw/labeling/2026-10-23-prompt-eval-smoke-rows.md`.

## Notes (builder, 2026-10-23 overnight)

- Prompts were frozen and committed (`212b7bea2`) before this run. Nothing in either prompt
  changes because of these 10 rows: the 60-row set is held out from tuning.
- The labels are the owner's EV01–EV10 at `a441d1c11` on `p3-labeling-set`, copied
  read-only into the gitignored `data/raw/labeling/`. EV05 onward carry the bias flag
  (copilot-suggested, owner-confirmed); EV04 is owner-uncertain.
- Spend: $0.1369 (10 Haiku triage calls, 6 Opus categorizer calls), every call logged in
  `data/quality/ai-calls/2026-10.jsonl`. The ai.yaml cap stays $5.00; this run's own cap
  was $0.50.
- This file was regenerated from the cache after per-row marks moved out of committed
  reports (0 calls, $0; hence "0 (16 cache hits)" above). The live run's spend is the
  $0.1369 noted above. The first version, with the per-row table, stays in git history
  at `10fea6609`; it was not rewritten.
