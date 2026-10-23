# Prompt evaluation — Precision on 60 hand-labeled statements

Generated 2026-10-23 15:28 UTC by `uv run ingest prompt-eval`. Labels: `../Civic-Ledger-label/docs/labeling/2026-10-22-eval-set.csv`.

- Triage: `claude-haiku-5-5`, prompt `v1` (sha256 `b49a776f73a1`), effort `medium`
- Categorizer: `claude-opus-5-5`, prompt `v2` (sha256 `7fb86e15aba7`), effort `medium`
- Q-K bar: RATIFIED 2026-10-23 (proposed by copilot for owner 2026-10-22)

## Precision by field

Precision = the share of the AI's calls on a field that the label agrees with. `proposition` is never scored (owner ruling 2026-10-22).

| Field | Bar | All | D | R | D/R gap | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `stance` | 90% | 90% (38/42) | 86% (19/22) | 95% (19/20) | 9 pts | meets |
| `topic` | 90% | 88% (37/42) | 77% (17/22) | 100% (20/20) | 23 pts | BELOW |
| `priority_signal` | 90% | 100% (6/6) | 100% (2/2) | 100% (4/4) | 0 pts | meets |
| `specificity` | 80% | 86% (36/42) | 77% (17/22) | 95% (19/20) | 18 pts | meets |
| `takes_policy_position` | none | 89% (39/44) | 79% (19/24) | 100% (20/20) | 21 pts | no bar |

**STOP for owner review:** the D/R gap passes 10 points on `topic`, `specificity`, `takes_policy_position`.

## Counts

| | |
| --- | --- |
| Labeled rows scored | 60 |
| Rows skipped as not yet labeled | 0 |
| Rows whose label is owner-unreviewed (copilot) | 0 |
| Rows with no answer (refusal or malformed) | 0 |
| Label said yes, triage said no (missed; not a precision error) | 4 |
| Categorizer `mixed` stance calls (outside the for/against bar) | 0 |
| How the run ended | `complete` |
| API calls (cache hits are free) | 0 (104 cache hits) |
| Spent | $0.0000 of a $0.25 run cap |

Per-row agreement marks are NOT in this report: next to the owner's public labels they would give away the model's answer for each statement (counts, never answers). They are in the gitignored `data/raw/labeling/2026-10-23-prompt-eval-60-owner-reviewed-rows.md`.
