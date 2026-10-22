# Hand-labeling set — 60 statements, for the owner

Your labels are the answer key. The real AI prompts get tested against them before
anything is categorized for real (spec §5 Phase 3 task 4). Expect 2 to 3 minutes per
statement, 2 to 3 hours in all. It can be done in several sittings.

**File:** `2026-10-22-eval-set.csv`. Open it in Excel or Google Sheets and turn on text
wrap for the `text` column. Fill in only the empty columns.

## Before you start

- **Read only the `text` column.** It is exactly what the AI reads: no headline, and
  nothing you know about the member. Judge it the same way.
- **The machine's first-pass answers are not in this file.** They are in a separate file
  on this computer only, `data/raw/labeling/2026-10-22-eval-set-verdicts.csv`. Do not
  open it until you have finished labeling, or its answers will steer yours. (If it is
  missing, `draw_eval_set.py` rebuilds it exactly.)
- If a statement takes positions on several policies, label the main one and list the
  others under `notes`.

## What to fill in, one line per column

| Column | What to write |
| --- | --- |
| `takes_policy_position` | `yes` if the text takes a position on a specific policy (a bill, a program, a rule, a level of spending, a change in law). Otherwise `no`, and leave the rest of the row blank except `notes`. |
| `topic` | The one area from the list below that the position is about. |
| `stance` | `for` or `against` that policy. `mixed` only when the text argues both sides. If you can't tell, write `none` and say why in `notes`: `mixed` never means "unsure". |
| `proposition` | What they are for or against, in one short phrase taken from the text. Not just the subject: "capping insulin at $35 a month", not "health care". |
| `specificity` | **Leave blank for now.** Its levels haven't been defined yet (question 1 below). |
| `priority_signal` | `yes` only if the text says the issue ranks high for them ("my top priority", "I ran on this", "I'll fight for") or commits them to a concrete act: introducing, passing or blocking a specific thing. `no` for a passing mention, a reaction to the news, ceremonial wording, a group letter they co-signed, or praise for someone else's work. (Your rule of 2026-10-09.) |
| `notes` | Anything at all: doubts, a second position, "the text is cut off". |

**Topic list** (the official 33 policy areas; copy one exactly):
Agriculture and Food · Animals · Armed Forces and National Security · Arts, Culture,
Religion · Civil Rights and Liberties, Minority Issues · Commerce · Congress · Crime and Law
Enforcement · Economics and Public Finance · Education · Emergency Management · Energy ·
Environmental Protection · Families · Finance and Financial Sector · Foreign Trade and
International Finance · Government Operations and Politics · Health · Housing and Community
Development · Immigration · International Affairs · Labor and Employment · Law · Native
Americans · Private Legislation · Public Lands and Natural Resources · Science, Technology,
Communications · Social Sciences and History · Social Welfare · Sports and Recreation ·
Taxation · Transportation and Public Works · Water Resources Development

## Two worked examples (made up; not in the set)

1. *"Families in our district pay too much for insulin. Next week I will introduce a bill
   to cap it at $35 a month for everyone, and I won't stop until it passes."*
   → `yes` · `Health` · `for` · `capping insulin at $35 a month for everyone` · (blank) ·
   `yes` (commits to introducing a specific bill) · (blank)
2. *"Today we honor Sergeant Maria Lopez, who gave 30 years to our county sheriff's office.
   Our community is safer because of her."*
   → `no` · and the rest blank.

## Open questions for you (answer before the prompts are written)

1. **What should `specificity` measure?** My recommendation is three levels: *names a
   specific bill, rule, program or number* / *names a concrete change but nothing specific* /
   *names only the issue*.
   - Yes to these levels: you fill that column in on this same pass.
   - Different levels: tell me which and they replace mine.
   - Drop the field: the categorizer stops producing it.
2. **Topic: the 33 broad areas, or the 974 detailed subjects?** I recommend the 33.
   - The 33: it matches the member-page timeline filter, which already uses them.
   - The 974: each label is finer, but there are far more ways for the AI to miss.
3. **Which of your labels count toward the precision score?** `takes_policy_position`,
   `topic` and `stance` are straightforward to compare. `proposition` is free text.
   - Score it: you judge each AI phrase as "same meaning" or not, which is slower.
   - Don't score it: it gets shown, but nothing measures how good it is.
4. **The precision bar itself (Q-K) is still open:** how often must the AI agree with
   you before a categorized statement may publish? It isn't needed to label this set, only
   before anything publishes.

## How the 60 were picked (for checking, not for labeling)

Drawn by `draw_eval_set.py` with seed `20261022` from the 40-member pilot: 15 per party
and chamber, 3 floor speeches and 12 press releases in each (about the corpus's 1 in 5).
A third were rejected by the first pass, on purpose, so that the test can tell whether
the real prompt fixes the first pass's misses. That includes three named in the step 9
notes and five the pre-filter's own rule says name a bill or ask for a vote. So a precision
number from this set is not a corpus-wide number until it is reweighted. Texts over
8,000 characters were left out because they are too long to label by hand. That drops
459 of 2,931 floor speeches and 421 of 11,879 press releases, so long floor speeches are
under-represented here. These 60 are held out: whoever writes the prompts must not tune
them on this set.
