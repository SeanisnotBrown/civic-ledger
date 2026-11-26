# Record party gap under the v2 triage verdicts (read-only, $0)

2026-11-26, copilot overnight turn (Sean away). **No AI was called, no network request was made, and nothing was changed** in any prompt, `ai.yaml`, `data/config/`, `ingest/` or tests. Row-level outputs and the script are in the gitignored `data/raw/analysis/triage_party_gap_v2.*`. No statement text, title or per-statement answer is quoted here. Counts by member are given; nothing here says why anyone wrote anything (rule 6).

## For Sean: one-screen brief (plain language)

**What the gap is today.** The first AI check asks of each statement: "does this take a position on a policy?" On Congressional Record items (floor speeches and Extensions of Remarks) it says yes to **80.9% of Democrats' (1,411 of 1,745)** and **68.7% of Republicans' (814 of 1,185)**: a **12.2-point difference**. On press releases it is the other way and small: D 73.4%, R 75.5% (-2.1). The "19.1% / 31.3%" in STATUS are the same Record numbers seen from the rejected side (D rejected 334 of 1,745 = 19.1%; R rejected 371 of 1,185 = 31.3%). They measure the Record only, per statement, under v2, and match the saved 2026-11-11 report exactly. The run's own stop rule fires because R is rejected 1.64 times as often as D (the stop is at 1.5 times). The old stub prompt had a 10.4-point gap, so v2 widened it by 1.8 points.

**Where it sits.** Not on the House floor: both parties are kept at 81% (D 81.1%, R 81.5%). It sits in three separate places: Senate floor speech other than amendment filings, by the 8 senators in the pilot (D 70.0% vs R 42.1%); Extensions of Remarks (D 64.7% vs R 5.8%; one R member, Perry, has 39 of R's 86 and none kept); and Senate amendment filings (D 88.4% vs R 69.9%). Length matters too: statements of 4,000+ characters are kept equally (D 87.9%, R 86.2%); the gap is in shorter ones. Only 4 senators per party sit behind the Senate rows, so the 12.2 is not a tight number: resampling members puts it anywhere from +0.8 to +23.5 points.

**Is it what is being said, not who said it?** Partly, but the record's own fields do not close it. R's Record has more tribute-style entries (11.2% in the honorific sub-classes vs D 6.6%) and D's has far more Senate amendment filings (41% vs 14%). But R's Record is also mostly House floor speech (64% vs D 35%), where the parties are equal; so if R's Record had D's mix, R would be kept *less* (59.7% by section), not more. What the fields cannot show is whether the Senate speeches v2 rejected on the R side really take no position; only a person reading them can say.

**The 5 options, each with what it changes** (the 10-23 doc's five; none new):

1. **Leave as is and rely on the 60-row checks.** Fastest. Nothing moves. The first held-out set is spent for any changed prompt (rule R3), so only the second set can speak to v2, and it holds just 6 D and 6 R Record rows; that cannot settle a Record-only gap. A real run still stops at the fairness check unless you accept the flag (as you did for the preview).
2. **You hand-label a small Record-only sample.** Settles the unknown part. Effect on the numbers: cannot be computed without your labels, so no number. What exists to sample: 8 groups (House floor, Senate amendment filings, other Senate speech, Extensions, each for D and R), the smallest being R Extensions (86) and R amendment filings (166). A share measured on 20 rows is good to about plus or minus 22 points, on 50 rows 14, on 100 rows 10.
3. **Re-run the breakdown on the real prompt's verdicts.** Already done: this document is it, at no cost. v2 moved the Record keep rate from D 83.4% to 80.9% and R 73.1% to 68.7%. Most of the new R rejections are Senate amendment filings (42 R statements, 25.5% of its filings, flipped from kept to rejected; D 56 statements, 7.8%); no field explains that, only reading them would. Nothing further to compute; whether v2 is *right* is the held-out question.
4. **A free rule that drops the honorific Record sub-classes before any AI.** Removes 115 D and 133 R statements (v2 had already rejected 86 D and 119 R of them; it would also remove 29 D and 14 R that v2 had kept). The Record gap narrows from 12.2 to 8.7 points. **The stop still fires** (R rejected 1.58 times as often as D), so it does not remove the need for your decision. The rule itself is even (3.5% of D's turns, 3.4% of R's). It changes the categorizer set by only 4 statements (15 per member) or 7 (25 per member), at the same number of calls and the same dollars. It misses 13 D and 22 R entries with a tribute word in the title that sit in other sub-classes. It is a filter change, so it needs your ratification.
5. **Report Record and press separately, and Extensions apart from floor speech.** No statement, rate or dollar changes. The report already splits Record from press; the new section lines show House floor not flagged (rejected D 18.9% vs R 18.5%), Senate floor flagged (16.4% vs 44.2%), Extensions flagged (35.3% vs 94.2%). The stop still fires unless you accept it.

**Dollars (the same under every option).** The categorizer asks about each member's newest triage-yes statements. At the preview's 15 per member: 592 calls (579 already in the preview queue, 13 not). At decision 7's 25 per member: **982 calls, of which 232 are Record (D 91, R 141)**; 579 are already in the preview queue, 403 are not. Per-call price: STATUS's $0.0245 comes from 38 early calls; the 577 live calls of preview-1 averaged **$0.0260**. So 25 per member is about $24.06 at $0.0245 or $25.5 at $0.026; the 403 not-yet-queued are $9.87 or $10.5. Either way it is over the default $5 cap and needs your cap for that run.

**What stays unknown.** (a) Whether v2's rejections in the Senate and Extensions rows are right: no labels exist for them. (b) Why v2 rejects more Republican Senate amendment filings than the stub did: the fields do not say. (c) How tight the 12.2 is: 4 senators per party sit behind the Senate rows. (d) Whether a real run must repeat the 579 preview items: `categorize-run` skips queued ones; I did not decide that.

*Copilot recommendation, not reviewed by Sean: do option 5 now (free), do option 2 on only the Senate-floor and Extensions rows before a real run, and skip option 4 (it moves 4 to 7 statements and the stop still fires).*

## Method

**Data read (read-only):** `data/raw/triage/v2.jsonl` (14,759 lines, 14,759 distinct texts; the triage prompt `ai.yaml` names is `v2`; 14,775 live v2 calls in the committed call log, $4.49), `data/raw/triage/v1-stub.jsonl` (14,757 distinct texts) for comparison, `data/raw/crec/statements` and `data/raw/press/statements` (all 17,012 collected records), `data/raw/review/queue.jsonl` (the `id` field only, to count what is already queued), the two held-out sheets' `text_sha256` column only (no label or verdict read), and the committed `data/quality/ai-calls/*.jsonl` for the per-call price. Code is the committed branch (`0885c5a28`), imported, not copied.

**Join, as `ingest/triage_run.py` / `categorize_run.py` do it:** `prefilter.load_all` -> `pilot_only` (40 members; all 17,012 records are pilot) -> `prefilter.run_prefilter` -> `triage_run.queue` (14,810 AI-eligible statements) -> v2 verdict by `fingerprint` (sha256 of the kept segments). 14,809 have a v2 verdict; 1 (a D Record statement) still has none. The gap tables count statements, as the saved report does; distinct texts are shown once for contrast. The categorizer set is `categorize_run.select`, the project's own function. "Kept" = v2 `takes_policy_position` true. The 12.2 is a keep-rate difference; the saved report's rate is the drop rate, so 19.1 + 80.9 = 100.

**What "19.1% / 31.3%" measure:** `categorize_run.triage_rows`, row `congressional_record`: statements the v2 gate answered no to, divided by Record statements it answered, per party, over the pilot. `uneven` is `prefilter._uneven`: the higher drop rate at least 1.5 times the lower, and at least 50 dropped statements across both parties. Every row in Table 0 was asserted equal to `data/raw/categorize/2026-11-11-count-before-spend.json` by the script before any other number was computed.

**Groupings that are mine, descriptive only** (from the Record's own sub-class codes): "honorific sub-class" = HONORING, RECOGNIZING, TRIBUTETO, CELEBRATING, COMMEMORATING, CONGRATULATIONS, COMMENDING, INMEMORYOF, RETIREMENT (the 10-23 doc's list); "honorific word in the title" is the 10-23 doc's word list applied to the title (titles are used, never quoted); the session-label and floor-business groups are named in the script. Length bands are the 10-23 doc's. Resampling: members drawn with replacement within party, 4,000 draws, seed 20261126.

**Not computable without an AI call or a label, so no number is given:** option 2's effect on any rate; whether any v2 answer is correct; the cause of any flip. A v1-stub-to-v2 flip is not attributable to the R2 wording alone: the prompts differ in more than that.

## What did not reconcile, or needs a note

- 19.1% / 31.3% reconcile exactly (Table 0). STATUS's wording "v2 triage keeps D 19.1% / R 31.3%" is off: those are the *rejected* shares, they are Record only, and kept is 80.9% / 68.7%.
- STATUS's "$0.0245/call" is the 38-call figure (31 calls on 2026-10-29, 7 on 10-30). The committed log now holds 615 live categorizer v3 calls at a mean of $0.02594; the 577 calls logged on 2026-11-11 (preview-1) average $0.02603 (STATUS and the run log say 575 calls; the 2-call difference was not checked). preview-1's $19.4863 = categorizer calls $15.02 + the v2 triage run of 2026-11-05 $4.47. `categorize-run` takes the higher of its by-length estimate and the logged mean, so it would now use about $0.026.
- 982 calls at 25 per member (now) vs 993 in the 2026-11-04 dry run: that run had no verdicts and assumed every statement passes; the 982 uses the real v2 verdicts.
- 592 - 579 = 13 matches STATUS's "13 eligible left uncategorized".
- The stub gap is 10.4 here (unrounded 83.43 - 73.06) and 10.3 in the 10-23 doc (difference of the rounded rates); the stub had 1 R Record statement without a verdict, v2 has 1 D.
- The main worktree is mid-merge (another turn). This analysis imported the committed branch code and read only gitignored `data/raw/`, which that merge does not change.

---

# Full tables

Generated by `triage_party_gap_v2.py`. Every table is per statement unless it says turns. "kept" = v2 answered yes.

## Table 0. Reconciliation with STATUS 19.1% / 31.3%

| Scope | D dropped / answered | D drop rate | R dropped / answered | R drop rate | flagged uneven | check |
|---|---|---|---|---|---|---|
| all sources | 2359/9352 | 25.2% | 1419/5457 | 26.0% | False | identical to the 2026-11-11 saved report |
| congressional_record | 334/1745 | 19.1% | 371/1185 | 31.3% | True | identical to the 2026-11-11 saved report |
| member_press | 2025/7607 | 26.6% | 1048/4272 | 24.5% | False | identical to the 2026-11-11 saved report |

Corpus: collected 17012, pilot-only 17012, after pre-filter 14983, eligible 14810, with a v2 verdict 14809, no verdict [('D', 'congressional_record')].
v2 ledger distinct texts 14759; v1-stub ledger distinct texts 14757.

## Table 1. Headline, v2 verdicts (statement counts, as the report counts them)

| Slice | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) |
|---|---|---|---|---|---|
| Congressional Record | 1411/1745 | 80.9% | 814/1185 | 68.7% | +12.2 |
| Press releases | 5582/7607 | 73.4% | 3224/4272 | 75.5% | -2.1 |
| Both | 6993/9352 | 74.8% | 4038/5457 | 74.0% | +0.8 |

Distinct texts (first occurrence):

| Slice | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) |
|---|---|---|---|---|---|
| Record | 1411/1733 | 81.4% | 814/1177 | 69.2% | +12.3 |
| Press | 5582/7607 | 73.4% | 3224/4242 | 76.0% | -2.6 |

Same slices under the v1-stub verdicts (the 10-23 doc's basis), for comparison:

| Slice | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) |
|---|---|---|---|---|---|
| Record (v1-stub) | 1456/1745 | 83.4% | 865/1184 | 73.1% | +10.4 |
| Press (v1-stub) | 6301/7607 | 82.8% | 3469/4271 | 81.2% | +1.6 |
| Both (v1-stub) | 7757/9352 | 82.9% | 4334/5455 | 79.5% | +3.5 |

By chamber (v2):

| Slice | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) |
|---|---|---|---|---|---|
| Record, house | 592/766 | 77.3% | 626/848 | 73.8% | +3.5 |
| Record, senate | 819/979 | 83.7% | 188/337 | 55.8% | +27.9 |
| Press, house | 2873/4152 | 69.2% | 1834/2484 | 73.8% | -4.6 |
| Press, senate | 2709/3455 | 78.4% | 1390/1788 | 77.7% | +0.7 |

Record keep-rate gap, member-clustered bootstrap (resample members within party, 4,000 draws, seed 20261126): 95% interval +0.8 to +23.5 points. Record members with statements: D 20, R 20.

Unweighted mean of member Record keep rates, D: 74.6% (median 76.5%, 20 members).
Unweighted mean of member Record keep rates, R: 65.5% (median 67.6%, 20 members).

## Table 2. Where the Record gap sits (v2)

#### 2a. Section

| Slice | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) | Share of D's Record | Share of R's Record |
|---|---|---|---|---|---|---|---|
| House floor | 489/603 | 81.1% | 621/762 | 81.5% | -0.4 | 34.5% | 64.3% |
| Senate floor | 810/969 | 83.6% | 188/337 | 55.8% | +27.8 | 55.6% | 28.4% |
| Extensions of Remarks | 112/173 | 64.7% | 5/86 | 5.8% | +58.9 | 9.9% | 7.3% |

Sections other than the three: {}.

#### 2b. Section x chamber of the member

| Slice | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) |
|---|---|---|---|---|---|
| House floor, house member | 482/595 | 81.0% | 621/762 | 81.5% | -0.5 |
| House floor, senate member | 7/8 | 87.5% | 0/0 | n/a | n/a |
| Senate floor, senate member | 810/969 | 83.6% | 188/337 | 55.8% | +27.8 |
| Extensions of Remarks, house member | 110/171 | 64.3% | 5/86 | 5.8% | +58.5 |
| Extensions of Remarks, senate member | 2/2 | 100.0% | 0/0 | n/a | n/a |

#### 2c. Sub-class groups (my grouping of the Record's own sub-class codes)

| Slice | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) | D n | R n |
|---|---|---|---|---|---|---|---|
| Senate amendment text | 633/716 | 88.4% | 116/166 | 69.9% | +18.5 | 717 | 166 |
| honorific sub-class | 29/115 | 25.2% | 14/133 | 10.5% | +14.7 | 115 | 133 |
| session-label sub-class | 87/124 | 70.2% | 39/66 | 59.1% | +11.1 | 124 | 66 |
| floor-business sub-class | 19/51 | 37.3% | 17/51 | 33.3% | +3.9 | 51 | 51 |
| other sub-class | 1/1 | 100.0% | 3/3 | 100.0% | +0.0 | 1 | 3 |
| ALLOTHER | 642/738 | 87.0% | 625/766 | 81.6% | +5.4 | 738 | 766 |

Every sub-class code (Record):

| Sub-class | Group | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) | D n | R n |
|---|---|---|---|---|---|---|---|---|
| ALLOTHER | ALLOTHER | 642/738 | 87.0% | 625/766 | 81.6% | +5.4 | 738 | 766 |
| SAMENDMENTTEXTIND | Senate amendment text | 633/716 | 88.4% | 116/166 | 69.9% | +18.5 | 717 | 166 |
| HONORING | honorific sub-class | 12/56 | 21.4% | 1/30 | 3.3% | +18.1 | 56 | 30 |
| RECOGNIZING | honorific sub-class | 7/25 | 28.0% | 8/52 | 15.4% | +12.6 | 25 | 52 |
| SLEGISLATIVE | session-label sub-class | 39/41 | 95.1% | 17/23 | 73.9% | +21.2 | 41 | 23 |
| SEXECCAL | session-label sub-class | 24/41 | 58.5% | 6/14 | 42.9% | +15.7 | 41 | 14 |
| SEXECSESSION | session-label sub-class | 15/28 | 53.6% | 12/21 | 57.1% | -3.6 | 28 | 21 |
| TRIBUTETO | honorific sub-class | 1/3 | 33.3% | 0/31 | 0.0% | +33.3 | 3 | 31 |
| SCONSENTREQUEST | floor-business sub-class | 15/16 | 93.8% | 14/15 | 93.3% | +0.4 | 16 | 15 |
| CELEBRATING | honorific sub-class | 6/17 | 35.3% | 2/7 | 28.6% | +6.7 | 17 | 7 |
| ADJOURNMENT | floor-business sub-class | 0/13 | 0.0% | 0/10 | 0.0% | +0.0 | 13 | 10 |
| SNOMINATIONS | session-label sub-class | 9/14 | 64.3% | 1/5 | 20.0% | +44.3 | 14 | 5 |
| CONGRATULATIONS | honorific sub-class | 0/4 | 0.0% | 2/8 | 25.0% | -25.0 | 4 | 8 |
| COMMEMORATING | honorific sub-class | 3/7 | 42.9% | 0/2 | 0.0% | +42.9 | 7 | 2 |
| SAUTHORITY | floor-business sub-class | 0/3 | 0.0% | 0/6 | 0.0% | +0.0 | 3 | 6 |
| PERSONALEXPLAIN | floor-business sub-class | 0/3 | 0.0% | 0/4 | 0.0% | +0.0 | 3 | 4 |
| SORDERFOR | floor-business sub-class | 0/4 | 0.0% | 0/3 | 0.0% | +0.0 | 4 | 3 |
| SPRIVILEGES | floor-business sub-class | 0/5 | 0.0% | 0/0 | n/a | n/a | 5 | 0 |
| HANNOUNCEMENT | floor-business sub-class | 1/1 | 100.0% | 3/4 | 75.0% | +25.0 | 1 | 4 |
| HAMENDMENTSIND | other sub-class | 1/1 | 100.0% | 3/3 | 100.0% | +0.0 | 1 | 3 |
| SCLOTURE | floor-business sub-class | 3/3 | 100.0% | 0/1 | 0.0% | +100.0 | 3 | 1 |
| INMEMORYOF | honorific sub-class | 0/3 | 0.0% | 0/0 | n/a | n/a | 3 | 0 |
| HCORRECTIONS | floor-business sub-class | 0/0 | n/a | 0/3 | 0.0% | n/a | 0 | 3 |
| SRECESS | floor-business sub-class | 0/1 | 0.0% | 0/1 | 0.0% | +0.0 | 1 | 1 |
| COMMENDING | honorific sub-class | 0/0 | n/a | 1/2 | 50.0% | n/a | 0 | 2 |
| SORDER | floor-business sub-class | 0/2 | 0.0% | 0/0 | n/a | n/a | 2 | 0 |
| SSTATEMENTS | session-label sub-class | 0/0 | n/a | 2/2 | 100.0% | n/a | 0 | 2 |
| CALLTOORDER | floor-business sub-class | 0/0 | n/a | 0/1 | 0.0% | n/a | 0 | 1 |
| SMEASUREDCAL | floor-business sub-class | 0/0 | n/a | 0/1 | 0.0% | n/a | 0 | 1 |
| SSTATEMENTSIND | session-label sub-class | 0/0 | n/a | 1/1 | 100.0% | n/a | 0 | 1 |
| SCALENDAR | floor-business sub-class | 0/0 | n/a | 0/1 | 0.0% | n/a | 0 | 1 |
| RETIREMENT | honorific sub-class | 0/0 | n/a | 0/1 | 0.0% | n/a | 0 | 1 |
| TECHNICALCORRECTIONS | floor-business sub-class | 0/0 | n/a | 0/1 | 0.0% | n/a | 0 | 1 |

#### 2d. Step-by-step removal of what is not a speech on a bill

| Slice | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) |
|---|---|---|---|---|---|
| All Record | 1411/1745 | 80.9% | 814/1185 | 68.7% | +12.2 |
| Less Senate amendment texts | 778/1029 | 75.6% | 698/1019 | 68.5% | +7.1 |
| Less amendment texts and Extensions | 666/856 | 77.8% | 693/933 | 74.3% | +3.5 |
| ...and less the 9 honorific sub-classes | 643/802 | 80.2% | 680/858 | 79.3% | +0.9 |
| House floor only | 489/603 | 81.1% | 621/762 | 81.5% | -0.4 |
| Senate floor, not amendment text | 177/253 | 70.0% | 72/171 | 42.1% | +27.9 |

#### 2e. Length band (characters the gate read)

| Slice | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) |
|---|---|---|---|---|---|
| Record <500 | 37/117 | 31.6% | 2/61 | 3.3% | +28.3 |
| Record 500-1,499 | 472/563 | 83.8% | 135/243 | 55.6% | +28.3 |
| Record 1,500-3,999 | 518/628 | 82.5% | 259/396 | 65.4% | +17.1 |
| Record 4,000+ | 384/437 | 87.9% | 418/485 | 86.2% | +1.7 |
| Press <500 | 55/226 | 24.3% | 8/84 | 9.5% | +14.8 |
| Press 500-1,499 | 877/1506 | 58.2% | 617/1045 | 59.0% | -0.8 |
| Press 1,500-3,999 | 3041/4049 | 75.1% | 1676/2121 | 79.0% | -3.9 |
| Press 4,000+ | 1609/1826 | 88.1% | 923/1022 | 90.3% | -2.2 |

Section x length (Record):

| Slice | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) |
|---|---|---|---|---|---|
| House floor <500 | 3/30 | 10.0% | 1/25 | 4.0% | +6.0 |
| House floor 500-1,499 | 141/197 | 71.6% | 100/151 | 66.2% | +5.3 |
| House floor 1,500-3,999 | 198/215 | 92.1% | 205/244 | 84.0% | +8.1 |
| House floor 4,000+ | 147/161 | 91.3% | 315/342 | 92.1% | -0.8 |
| Senate floor <500 | 33/81 | 40.7% | 0/29 | 0.0% | +40.7 |
| Senate floor 500-1,499 | 310/341 | 90.9% | 33/72 | 45.8% | +45.1 |
| Senate floor 1,500-3,999 | 240/288 | 83.3% | 53/95 | 55.8% | +27.5 |
| Senate floor 4,000+ | 227/259 | 87.6% | 102/141 | 72.3% | +15.3 |
| Extensions of Remarks <500 | 1/6 | 16.7% | 1/7 | 14.3% | +2.4 |
| Extensions of Remarks 500-1,499 | 21/25 | 84.0% | 2/20 | 10.0% | +74.0 |
| Extensions of Remarks 1,500-3,999 | 80/125 | 64.0% | 1/57 | 1.8% | +62.2 |
| Extensions of Remarks 4,000+ | 10/17 | 58.8% | 1/2 | 50.0% | +8.8 |

#### 2f. Record members (statements judged, kept, keep rate)

**D** (20 members, 1745 judged statements; top-5 share 65.3%):

| Member | Chamber | n | kept | keep rate |
|---|---|---|---|---|
| Jeanne Shaheen (S001181) | senate | 367 | 321 | 87.5% |
| Martin Heinrich (H001046) | senate | 263 | 214 | 81.4% |
| Mark Kelly (K000377) | senate | 199 | 142 | 71.4% |
| Betty McCollum (M001143) | house | 161 | 153 | 95.0% |
| Andy Kim (K000394) | senate | 150 | 142 | 94.7% |
| Al Green (G000553) | house | 143 | 100 | 69.9% |
| Kathy Castor (C001066) | house | 79 | 59 | 74.7% |
| Mark DeSaulnier (D000623) | house | 64 | 46 | 71.9% |
| Terri A. Sewell (S001185) | house | 51 | 45 | 88.2% |
| Jim Costa (C001059) | house | 47 | 31 | 66.0% |
| Bill Foster (F000454) | house | 41 | 33 | 80.5% |
| Sarah McBride (M001238) | house | 26 | 21 | 80.8% |
| Jahana Hayes (H001081) | house | 25 | 21 | 84.0% |
| Angie Craig (C001119) | house | 25 | 19 | 76.0% |
| Sharice Davids (D000629) | house | 22 | 11 | 50.0% |
| Janice D. Schakowsky (S001145) | house | 20 | 11 | 55.0% |
| Juan Vargas (V000130) | house | 17 | 13 | 76.5% |
| Lauren Underwood (U000040) | house | 17 | 13 | 76.5% |
| George Whitesides (W000830) | house | 16 | 10 | 62.5% |
| Josh Riley (R000622) | house | 12 | 6 | 50.0% |

**R** (20 members, 1185 judged statements; top-5 share 55.7%):

| Member | Chamber | n | kept | keep rate |
|---|---|---|---|---|
| Bruce Westerman (W000821) | house | 237 | 212 | 89.5% |
| Scott Perry (P000605) | house | 118 | 65 | 55.1% |
| Bill Hagerty (H000601) | senate | 112 | 74 | 66.1% |
| Mike Rounds (R000605) | senate | 110 | 50 | 45.5% |
| Todd Young (Y000064) | senate | 83 | 47 | 56.6% |
| Gus M. Bilirakis (B001257) | house | 78 | 66 | 84.6% |
| Thomas Massie (M001184) | house | 52 | 44 | 84.6% |
| Mark Harris (H001102) | house | 48 | 34 | 70.8% |
| Max L. Miller (M001222) | house | 46 | 32 | 69.6% |
| Mike Kennedy (K000403) | house | 46 | 27 | 58.7% |
| Mike Johnson (J000299) | house | 45 | 24 | 53.3% |
| Darin LaHood (L000585) | house | 34 | 23 | 67.6% |
| Tim Sheehy (S001232) | senate | 32 | 17 | 53.1% |
| Julie Fedorchak (F000482) | house | 30 | 27 | 90.0% |
| Mike Ezell (E000235) | house | 26 | 21 | 80.8% |
| Ryan K. Zinke (Z000018) | house | 24 | 13 | 54.2% |
| Neal P. Dunn (D000628) | house | 18 | 13 | 72.2% |
| John R. Moolenaar (M001194) | house | 17 | 14 | 82.4% |
| Trent Kelly (K000388) | house | 16 | 7 | 43.8% |
| Barry Loudermilk (L000583) | house | 13 | 4 | 30.8% |

Leave-one-out (Record keep rate without the biggest member of each party):

| Party | Left out | Rest keep rate |
|---|---|---|
| D | Jeanne Shaheen (S001181) | 1090/1378 = 79.1% |
| R | Bruce Westerman (W000821) | 602/948 = 63.5% |

Record entries by calendar year (statements, per party; description of the mix only):

| Year | D n / keep | R n / keep |
|---|---|---|
| 2023 | 276 / 70.3% | 272 / 69.9% |
| 2024 | 285 / 68.8% | 305 / 65.9% |
| 2025 | 718 / 87.2% | 320 / 71.2% |
| 2026 | 467 / 84.8% | 288 / 67.7% |

#### 2g. The three cells where the gap sits, by member (statements judged / kept)

**Senate amendment text**

| Party | Member | n | kept | keep rate |
|---|---|---|---|---|
| D | Jeanne Shaheen (S001181) | 287 | 258 | 89.9% |
| D | Martin Heinrich (H001046) | 202 | 179 | 88.6% |
| D | Mark Kelly (K000377) | 130 | 103 | 79.2% |
| D | Andy Kim (K000394) | 97 | 93 | 95.9% |
| R | Mike Rounds (R000605) | 59 | 38 | 64.4% |
| R | Bill Hagerty (H000601) | 56 | 46 | 82.1% |
| R | Todd Young (Y000064) | 34 | 21 | 61.8% |
| R | Tim Sheehy (S001232) | 17 | 11 | 64.7% |

**Senate floor, other**

| Party | Member | n | kept | keep rate |
|---|---|---|---|---|
| D | Jeanne Shaheen (S001181) | 80 | 63 | 78.8% |
| D | Mark Kelly (K000377) | 69 | 39 | 56.5% |
| D | Martin Heinrich (H001046) | 61 | 35 | 57.4% |
| D | Andy Kim (K000394) | 43 | 40 | 93.0% |
| R | Bill Hagerty (H000601) | 56 | 28 | 50.0% |
| R | Mike Rounds (R000605) | 51 | 12 | 23.5% |
| R | Todd Young (Y000064) | 49 | 26 | 53.1% |
| R | Tim Sheehy (S001232) | 15 | 6 | 40.0% |

**Extensions of Remarks**

| Party | Member | n | kept | keep rate |
|---|---|---|---|---|
| D | Betty McCollum (M001143) | 98 | 93 | 94.9% |
| D | Kathy Castor (C001066) | 19 | 2 | 10.5% |
| D | Jim Costa (C001059) | 12 | 0 | 0.0% |
| D | Sharice Davids (D000629) | 9 | 3 | 33.3% |
| D | Mark DeSaulnier (D000623) | 8 | 0 | 0.0% |
| D | Bill Foster (F000454) | 7 | 1 | 14.3% |
| D | Terri A. Sewell (S001185) | 6 | 5 | 83.3% |
| D | Al Green (G000553) | 6 | 5 | 83.3% |
| D | Andy Kim (K000394) | 2 | 2 | 100.0% |
| D | Janice D. Schakowsky (S001145) | 2 | 0 | 0.0% |
| D | Angie Craig (C001119) | 1 | 1 | 100.0% |
| D | George Whitesides (W000830) | 1 | 0 | 0.0% |
| D | Sarah McBride (M001238) | 1 | 0 | 0.0% |
| D | Juan Vargas (V000130) | 1 | 0 | 0.0% |
| R | Scott Perry (P000605) | 39 | 0 | 0.0% |
| R | Mike Johnson (J000299) | 7 | 1 | 14.3% |
| R | Gus M. Bilirakis (B001257) | 7 | 1 | 14.3% |
| R | Darin LaHood (L000585) | 6 | 0 | 0.0% |
| R | Ryan K. Zinke (Z000018) | 6 | 1 | 16.7% |
| R | Trent Kelly (K000388) | 5 | 0 | 0.0% |
| R | Bruce Westerman (W000821) | 5 | 1 | 20.0% |
| R | Neal P. Dunn (D000628) | 4 | 0 | 0.0% |
| R | Barry Loudermilk (L000583) | 3 | 0 | 0.0% |
| R | Thomas Massie (M001184) | 2 | 0 | 0.0% |
| R | Max L. Miller (M001222) | 1 | 0 | 0.0% |
| R | Mike Ezell (E000235) | 1 | 1 | 100.0% |

## Table 3. Is it what is being said? (fields on the record only)

#### 3a. Composition of each party's Record (share of that party's statements)

| Marker | D count (share) | R count (share) |
|---|---|---|
| Senate amendment text | 717 (41.1%) | 166 (14.0%) |
| Extensions of Remarks | 173 (9.9%) | 86 (7.3%) |
| honorific sub-class (9) | 115 (6.6%) | 133 (11.2%) |
| honorific word in the title | 119 (6.8%) | 147 (12.4%) |
| honorific sub-class OR title word | 128 (7.3%) | 155 (13.1%) |
| session-label sub-class | 124 (7.1%) | 66 (5.6%) |
| floor-business sub-class | 51 (2.9%) | 51 (4.3%) |
| under 500 characters | 117 (6.7%) | 61 (5.1%) |
| 4,000+ characters | 437 (25.0%) | 485 (40.9%) |
| Senate-member statements | 980 (56.1%) | 337 (28.4%) |

v2 keep rate inside each marker:

| Slice | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) |
|---|---|---|---|---|---|
| honorific sub-class (9) | 29/115 | 25.2% | 14/133 | 10.5% | +14.7 |
| honorific title word | 32/119 | 26.9% | 20/147 | 13.6% | +13.3 |
| honorific by neither | 1376/1617 | 85.1% | 793/1030 | 77.0% | +8.1 |

#### 3b. Reweighting (own keep rate per cell, other party's mix)

Actual: R 68.7%, D 80.9% (gap +12.2).

| Cells | R at D's mix | D at R's mix | gap if R at D's mix | gap if D at R's mix |
|---|---|---|---|---|
| Section | 59.7% (0 left out) | 80.6% (0 left out) | +21.1 | +11.9 |
| Length band | 63.3% (0 left out) | 82.3% (0 left out) | +17.6 | +13.7 |
| Section x length | 56.1% (0 left out) | 83.0% (0 left out) | +24.8 | +14.3 |
| Section x group | 65.1% (0 left out) | 76.2% (0 left out) | +15.7 | +7.5 |
| Section x group x length | 64.6% (30 left out) | 79.3% (31 left out) | +16.2 | +10.6 |
| Section x sub-class | 65.1% (21 left out) | 77.8% (15 left out) | +15.8 | +9.1 |
| Section x sub-class x length | 65.3% (73 left out) | 80.0% (55 left out) | +15.6 | +11.4 |

## Table 4. v1-stub -> v2: what changed per statement (option 3)

Statements with both verdicts: 14807 of 14810 (no v1 verdict: 3). The v1-stub and v2 prompts differ in more than the R2 wording (stub -> v1 -> v2), so a flip is not attributable to R2 alone.

| Slice | D pass->fail / fail->pass | D as % of slice | R pass->fail / fail->pass | R as % of slice |
|---|---|---|---|---|
| Record | 72 / 27 | 4.1% / 1.5% | 62 / 10 | 5.2% / 0.8% |
| Press | 762 / 43 | 10.0% / 0.6% | 260 / 15 | 6.1% / 0.4% |
| Both | 834 / 70 | 8.9% / 0.7% | 322 / 25 | 5.9% / 0.5% |
| Record, House floor | 12 / 10 | 2.0% / 1.7% | 16 / 6 | 2.1% / 0.8% |
| Record, Senate floor | 59 / 14 | 6.1% / 1.4% | 45 / 4 | 13.4% / 1.2% |
| Record, Extensions of Remarks | 1 / 3 | 0.6% / 1.7% | 1 / 0 | 1.2% / 0.0% |
| Record, Senate amendment text | 56 / 9 | 7.8% / 1.3% | 42 / 2 | 25.5% / 1.2% |
| Record, honorific sub-class | 2 / 1 | 1.7% / 0.9% | 2 / 0 | 1.5% / 0.0% |
| Record, session-label sub-class | 3 / 2 | 2.4% / 1.6% | 0 / 1 | 0.0% / 1.5% |
| Record, floor-business sub-class | 0 / 0 | 0.0% / 0.0% | 2 / 1 | 3.9% / 2.0% |
| Record, ALLOTHER | 11 / 15 | 1.5% / 2.0% | 16 / 6 | 2.1% / 0.8% |

Net movement of the Record keep rate, v1-stub -> v2, by party: 

| Party | v1-stub keep | v2 keep | change (pts) |
|---|---|---|---|
| D | 1456/1745 = 83.4% | 1411/1745 = 80.9% | -2.6 |
| R | 865/1184 = 73.1% | 814/1185 = 68.7% | -4.4 |

## Table 5. The five options

Categorizer v3 live calls in the committed call log: 615, mean $0.02594 per call. The task and STATUS use $0.0245 (the 38-call figure from before preview-1); both are shown.

#### 5.0 Baseline: today, nothing changed

Triage-gate drop rates, exactly as `categorize-run` prints them (rate = share DROPPED):

| Scope | D dropped/answered | D drop | R dropped/answered | R drop | R/D drop ratio | flagged uneven (stops the run, exit 7) |
|---|---|---|---|---|---|---|
| all sources | 2359/9352 | 25.2% | 1419/5457 | 26.0% | 1.03x | False |
| congressional_record | 334/1745 | 19.1% | 371/1185 | 31.3% | 1.64x | True |
| member_press | 2025/7607 | 26.6% | 1048/4272 | 24.5% | 0.92x | False |

Rule in force (`prefilter._uneven`): flagged when the higher drop rate is at least 1.5x the lower AND the two parties' dropped statements total at least 50; `categorize-run` refuses to spend (exit 7) on a flag unless `--fairness-reviewed triage` is passed.

Categorizer set under decision 7 (newest N triage-yes per member), by party and source:

| N | calls | D Record | R Record | D press | R press | already in preview queue | not yet queued | $ at 0.0245 | $ at log mean 0.0259 | $ at 0.0245, not-yet-queued only |
|---|---|---|---|---|---|---|---|---|---|---|
| 15 per member | 592 | 47 | 91 | 253 | 201 | 579 | 13 | $14.50 | $15.35 | $0.32 |
| 25 per member | 982 | 91 | 141 | 409 | 341 | 579 | 403 | $24.06 | $25.47 | $9.87 |

Check: preview-1 asked for 15 per member and reports 592 eligible; this run gets 592.

v2-triage-yes pool (no per-member cap), by party and source: D congressional_record 1411, D member_press 5582, R congressional_record 814, R member_press 3224

Members whose 25 slots are not full (fewer than 25 triage-yes statements): 1 of 40; by party D 0, R 1.

#### 5.1 Leave as is; rely on the 60-row held-out measurement

No statement, rate or dollar changes. What the held-out rows can say about a Record-only gap (counts only, by party and source; rows matched to the corpus by text hash, no label or verdict read):

| Set | rows | matched to a current statement | D Record | R Record | D press | R press |
|---|---|---|---|---|---|---|
| set 1 (2026-10-22) | 60 | 60 | 6 | 6 | 24 | 24 |
| set 2 (2026-10-23) | 60 | 60 | 6 | 6 | 24 | 24 |
| both sets | 120 | 120 | 12 | 12 | 48 | 48 |

Record rows in both sets by party and section: D Extensions of Remarks 2, D House floor 4, D Senate floor 6, R Extensions of Remarks 1, R House floor 5, R Senate floor 6

#### 5.2 Hand-label a small Record-only sample, stratified

Effect on keep rates or the gap: NOT computable without the owner's labels; no number is given. What is computable is how many statements each stratum holds (v2 verdicts):

| Stratum | Party | statements | v2 kept | v2 dropped | members |
|---|---|---|---|---|---|
| House floor | D | 603 | 489 | 114 | 17 |
| House floor | R | 762 | 621 | 141 | 16 |
| Senate amendment text | D | 717 | 633 | 83 | 4 |
| Senate amendment text | R | 166 | 116 | 50 | 4 |
| Senate floor, other | D | 253 | 177 | 76 | 4 |
| Senate floor, other | R | 171 | 72 | 99 | 4 |
| Extensions of Remarks | D | 173 | 112 | 61 | 14 |
| Extensions of Remarks | R | 86 | 5 | 81 | 12 |

Plain arithmetic (no data): a share measured on n rows has a 95% half-width of about 0.98/sqrt(n) at worst: n=20: +/-22 pts, n=50: +/-14 pts, n=100: +/-10 pts, n=200: +/-7 pts.

#### 5.3 Re-run this breakdown on the real prompt's verdicts

The v2 triage run already exists ($4.49 logged, 14,775 live calls), so this document IS that re-run; sections 1-4 are its result and no further AI call changes any number here. No statement, rate or dollar moves. What a v2 re-run cannot show is whether v2's answers are RIGHT: that needs the labeled held-out set (`p3-prompts-v3` set-2 check, which found a D/R gap flag on 5 categorizer fields and is owner-unreviewed).

#### 5.4 Pre-filter rule for the honorific Record sub-classes

Statements the rule would remove BEFORE triage (the nine codes: CELEBRATING, COMMEMORATING, COMMENDING, CONGRATULATIONS, HONORING, INMEMORYOF, RECOGNIZING, RETIREMENT, TRIBUTETO):

| Party | statements removed | of which v2 kept | of which v2 dropped | of which in the preview queue now | turns removed |
|---|---|---|---|---|---|
| D | 115 | 29 | 86 | 3 | 116 |
| R | 133 | 14 | 119 | 1 | 146 |

Resulting triage-gate rates (after the removal):

| Scope | D dropped/answered | D drop | R dropped/answered | R drop | R/D drop ratio | flagged uneven |
|---|---|---|---|---|---|---|
| all sources | 2273/9237 | 24.6% | 1300/5324 | 24.4% | 0.99x | False |
| Record | 248/1630 | 15.2% | 252/1052 | 24.0% | 1.58x | True |
| press | 2025/7607 | 26.6% | 1048/4272 | 24.5% | 0.92x | False |

Record keep rate after the removal, and (for contrast) the share of EACH PARTY's whole Record that still reaches the categorizer pool:

| Slice | D kept / judged | D keep | R kept / judged | R keep | Gap D-R (pts) |
|---|---|---|---|---|---|
| Record, today | 1411/1745 | 80.9% | 814/1185 | 68.7% | +12.2 |
| Record, honorific sub-classes removed | 1382/1630 | 84.8% | 800/1052 | 76.0% | +8.7 |

| Party | Record statements | in the yes-pool today | in the yes-pool after the rule |
|---|---|---|---|
| D | 1746 | 1411 | 1382 |
| R | 1185 | 814 | 800 |

Pre-filter fairness row the new rule would add (Record scope, turns; denominator = turns judged by the pre-filter, as `prefilter.fairness` counts):

| Party | turns judged | new-rule turns | new-rule rate | existing ceremonial turns | existing ceremonial rate | ceremonial + new rate |
|---|---|---|---|---|---|---|
| D | 3338 | 116 | 3.5% | 706 | 21.2% | 24.6% |
| R | 4328 | 146 | 3.4% | 767 | 17.7% | 21.1% |

New rule alone: D 3.5% vs R 3.4% (ratio R/D 0.97x, 262 turns): `prefilter._uneven` says False. Combined with the existing ceremonial rule: D 24.6% vs R 21.1%, `_uneven` False. `OWNER_ACCEPTED_RULES` is ['procedural'] only, so a flag on a new rule would stop the run again.

| Party | Record statements with an honorific title word but NOT in the nine sub-classes | v2 kept | v2 dropped |
|---|---|---|---|
| D | 13 | 6 | 7 |
| R | 22 | 7 | 15 |

The 9 honorific codes cover how many of v2's Record drops (share of each party's v2-dropped Record statements):

| Party | v2-dropped Record | of those in the nine honorific codes | share |
|---|---|---|---|
| D | 334 | 86 | 25.7% |
| R | 371 | 119 | 32.1% |

Categorizer set and dollars under the rule:

| N | calls | change vs today | statements leaving the set | statements entering (back-fill) | D Record | R Record | D press | R press | $ at 0.0245 | $ change | not yet queued | $ not yet queued |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 per member | 592 | 0 | 4 | 4 | 45 | 90 | 255 | 202 | $14.50 | $+0.00 | 17 | $0.42 |
| 25 per member | 982 | 0 | 7 | 7 | 87 | 141 | 413 | 341 | $24.06 | $+0.00 | 407 | $9.97 |

#### 5.5 Report Record and press rates separately, and Extensions apart from floor speech

No statement changes; no model change; no dollar change. The per-source split already exists (it is where 19.1% / 31.3% comes from). What is new is a per-section line. The gate's own flag rule applied to each section (drop rates, `categorize_run._rows`):

| Section | D dropped/answered | D drop | R dropped/answered | R drop | flagged uneven |
|---|---|---|---|---|---|
| House floor | 114/603 | 18.9% | 141/762 | 18.5% | False |
| Senate floor | 159/969 | 16.4% | 149/337 | 44.2% | True |
| Extensions of Remarks | 61/173 | 35.3% | 81/86 | 94.2% | True |
| Senate floor, not amendment text | 76/253 | 30.0% | 99/171 | 57.9% | True |

The run-stopping rule is unchanged by reporting: the Record row stays flagged unless the owner passes `--fairness-reviewed triage` (as the preview did).

