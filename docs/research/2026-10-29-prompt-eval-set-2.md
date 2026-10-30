# Prompt evaluation — 60 rows, 60 with owner-unreviewed AI labels: agreement check, not a Q-K measurement

**Read this first.** The labels on held-out set 2 were written by a separate labeler session (an AI session, blind to the prompts), then re-checked against owner ruling R2a by another labeler session. **The owner has not reviewed them.** So every number below is how often the AI pipeline agrees with another AI's labels: an agreement check, NOT a Q-K measurement. No bar is assessed, and the publish gate stays closed.

Generated 2026-10-30 00:00 UTC by `uv run ingest prompt-eval`. Labels: `data/raw/labeling/2026-10-29-eval-set-2-flagged.csv`, a gitignored copy of `docs/labeling/2026-10-23-eval-set-2.csv` on branch `p3-labeling-set-2` at `10f0571e0` (40 yes / 20 no, 33 BORDERLINE; sha256 `325774e8a11d`). The copy is identical in every column except `notes`, where each row gets the `owner-unreviewed` flag the harness reads. The sheet itself carries no such flag, and without it the harness would have scored this as an owner-reviewed Q-K measurement.

- Triage: `claude-haiku-5-5`, prompt `v2` (sha256 `02263e150711`), effort `medium`
- Categorizer: `claude-opus-5-5`, prompt `v3` (sha256 `2b4352e05ff1`), effort `medium`
- Q-K bar: RATIFIED 2026-10-23 (proposed by copilot for owner 2026-10-22)

**60 of 60 labels are AI (copilot) labels, owner-unreviewed. This is AI-vs-AI agreement, NOT a valid Q-K measurement. The publish gate stays closed until the owner reviews or relabels them.**

## Precision by field

Precision = the share of the AI's calls on a field that the label agrees with. `proposition` is never scored (owner ruling 2026-10-22). `topic` counts the AI's one topic correct when it is the label's primary or secondary topic (owner ruling R1, 2026-10-23); `topic_primary_only` scores the same calls against the primary alone, for information: it has no bar and is never a D/R gap flag.

| Field | Bar | All | D | R | D/R gap | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `stance` | 90% | 89% (33/37) | 78% (14/18) | 100% (19/19) | 22 pts | not assessed (60 labels owner-unreviewed) |
| `topic` | 90% | 84% (31/37) | 94% (17/18) | 74% (14/19) | 21 pts | not assessed (60 labels owner-unreviewed) |
| `topic_primary_only` | none | 84% (31/37) | 94% (17/18) | 74% (14/19) | 21 pts | no bar |
| `priority_signal` | 90% | 78% (7/9) | 100% (4/4) | 60% (3/5) | 40 pts | not assessed (60 labels owner-unreviewed) |
| `specificity` | 80% | 95% (35/37) | 89% (16/18) | 100% (19/19) | 11 pts | not assessed (60 labels owner-unreviewed) |
| `takes_policy_position` | none | 95% (36/38) | 89% (17/19) | 100% (19/19) | 11 pts | no bar |

### Owner-labeled rows (0 rows)

| Field | Bar | All | D | R | D/R gap | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `stance` | 90% | — | — | — | — | not assessed (n=0 < 50) |
| `topic` | 90% | — | — | — | — | not assessed (n=0 < 50) |
| `topic_primary_only` | none | — | — | — | — | no bar |
| `priority_signal` | 90% | — | — | — | — | not assessed (n=0 < 50) |
| `specificity` | 80% | — | — | — | — | not assessed (n=0 < 50) |
| `takes_policy_position` | none | — | — | — | — | no bar |

### Copilot-labeled rows, owner-unreviewed (60 rows)

| Field | Bar | All | D | R | D/R gap | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `stance` | 90% | 89% (33/37) | 78% (14/18) | 100% (19/19) | 22 pts | not assessed (60 labels owner-unreviewed) |
| `topic` | 90% | 84% (31/37) | 94% (17/18) | 74% (14/19) | 21 pts | not assessed (60 labels owner-unreviewed) |
| `topic_primary_only` | none | 84% (31/37) | 94% (17/18) | 74% (14/19) | 21 pts | no bar |
| `priority_signal` | 90% | 78% (7/9) | 100% (4/4) | 60% (3/5) | 40 pts | not assessed (60 labels owner-unreviewed) |
| `specificity` | 80% | 95% (35/37) | 89% (16/18) | 100% (19/19) | 11 pts | not assessed (60 labels owner-unreviewed) |
| `takes_policy_position` | none | 95% (36/38) | 89% (17/19) | 100% (19/19) | 11 pts | no bar |

Gap over 10 points on `stance`, `topic`, `priority_signal`, `specificity`, `takes_policy_position` — measured partly against owner-unreviewed labels, so it is a lead to check, not a finding.

## Counts

| | |
| --- | --- |
| Labeled rows scored | 60 |
| Rows skipped as not yet labeled | 0 |
| Rows whose label is owner-unreviewed (copilot) | 60 |
| Rows with no answer (refusal or malformed) | 0 |
| Label said yes, triage said no (missed; not a precision error) | 4 |
| Categorizer `mixed` stance calls (outside the for/against bar) | 0 |
| How the run ended | `complete` |
| API calls (cache hits are free) | 98 (0 cache hits) |
| Spent | $0.9481 of a $2.50 run cap |

Per-row agreement marks are NOT in this report: next to the owner's public labels they would give away the model's answer for each statement (counts, never answers). They are in the gitignored `data/raw/labeling/2026-10-29-prompt-eval-set-2-rows.md`.

## Notes (builder, 2026-10-29)

**D/R gap.** The harness flags a gap over 10 points on 5 fields: `stance` 22, `topic` 21, `priority_signal` 40, `specificity` 11, `takes_policy_position` 11. The direction is not one-sided. `stance`, `specificity` and `takes_policy_position` agree less on D rows; `topic` and `priority_signal` agree less on R rows. Several cells are small (`priority_signal` is 4 D and 5 R calls). Because the labels are owner-unreviewed, each gap is something to check, not a finding.

**Against the bars, for information only (not assessed):** `stance` 89% vs 90%, `topic` 84% vs 90%, `priority_signal` 78% vs 90%, `specificity` 95% vs 80%. `topic_primary_only` equals `topic` (31/37): no call was decided by a secondary topic (R1).

**Disagreements, in counts.** 19 of 60 rows disagree with the label on at least one field. 15 of those 19 are BORDERLINE rows, and 8 are D and 11 are R. Broken down by field (a row can count on more than one field):

| Field | Rows | Of which BORDERLINE |
| --- | --- | --- |
| `takes_policy_position` (2 AI yes where the label says no; 4 misses where the label says yes and triage says no) | 6 | 5 |
| `topic` (on rows both call yes) | 5 | 5 |
| `priority_signal` (2 AI yes where the label says no; 3 AI no where the label says yes) | 5 | 3 |
| `stance` (on rows both call yes) | 3 | 2 |
| `specificity` (on rows both call yes) | 1 | 1 |

The precision table also counts each categorizer call on the 2 rows where the label says no as wrong. That is why, for example, `stance` shows 4 wrong while this table shows 3.

**The per-row table** (row, party, BORDERLINE, field, label, AI answer) is in the gitignored `data/raw/labeling/2026-10-29-prompt-eval-set-2-disagreements.md`, BORDERLINE rows first, for the owner's review. It is not in this report for the same reason as the per-row marks: the repository is public, and the AI's per-statement answers about named members are unreviewed AI output (counts, never answers). It was built from the `ai.py` cache with no new calls and no audit lines.

**The recorded measurement.** The harness writes `data/quality/categorizer-precision.json` after any complete run of 50 rows or more. It wrote one (`unreviewed_labels: 60`, every barred field "not assessed", gap flags on the 5 fields above). That file was **not committed**. The committed file stays as it was (categorizer v2, which the publish gate already calls stale), and the harness-written copy is kept in gitignored `data/raw/labeling/2026-10-29-categorizer-precision-set-2-harness-written.json`.
