# Hand-labeling set 2 — 60 statements, labeled blind

Your labels are the answer key. The changed AI prompts (triage v2, categorizer v3) get
tested against them before anything is categorized for real (spec §5 Phase 3 task 4).
Expect 2 to 3 minutes per statement, 2 to 3 hours in all. It can be done in several
sittings.

**File:** `2026-10-23-eval-set-2.csv` (rows `HO01`–`HO60`). Open it in Excel or Google
Sheets and turn on text wrap for the `text` column. Fill in only the empty columns.

**Set 1** (`2026-10-22-eval-set.csv`, rows `EV01`–`EV60`) is finished and stays as it is.
It is spent: owner ruling 3 below says it may not grade any changed prompt.

## Before you start

- **Whoever wrote the prompts must not label this set** (owner, 2026-10-23). The builder
  who wrote triage v2 / categorizer v3 drew it but did not read its texts. Label it in a
  fresh session.
- **Read only the `text` column.** It is exactly what the AI reads: no headline, and
  nothing you know about the member. Judge it the same way.
- **The machine's first-pass answers are not in this file.** They are in a separate file
  on this computer only, `data/raw/labeling/2026-10-23-eval-set-2-verdicts.csv`. Do not
  open it until you have finished labeling, or its answers will steer yours. (If it is
  missing, `draw_eval_set.py` rebuilds it exactly.)
- If a statement takes positions on two policies in different areas, put the main one's
  area in `topic` and the other's in `topic_secondary` (ruling 1 below). Anything beyond
  that goes in `notes`.

## What to fill in, one line per column

| Column | What to write |
| --- | --- |
| `takes_policy_position` | `yes` if the text takes a position on a specific policy (a bill, a program, a rule, a level of spending, a change in law). Otherwise `no`, and leave the rest of the row blank except `notes`. Announcements of grants or funding awards, commemorative or recognition resolutions, ceremonies, event appearances and check presentations are `no`, unless the text also argues for or against a specific policy change. Mentioning a past vote only to take credit for funding or an event is not a position by itself; stating how one voted on a named bill is a position (ruling 2 below). |
| `topic` | The one area from the list below that the main position is about (the primary topic). |
| `topic_secondary` | Optional. A second area from the same list, only when the text takes a position in a second area too. Otherwise blank. |
| `stance` | `for` or `against` that policy. `mixed` only when the text argues both sides. If you can't tell, write `none` and say why in `notes`: `mixed` never means "unsure". |
| `proposition` | What they are for or against, in one short phrase taken from the text. Not just the subject: "capping insulin at $35 a month", not "health care". |
| `specificity` | `1`, `2` or `3` (definitions below). |
| `priority_signal` | `yes` ONLY for explicit ranking language ("my top priority", "I ran on this") or a pledge about the future ("I'll fight for", "I am committed to"). `no` for announcing a bill that is already introduced, claiming credit for something already done, a passing mention, a reaction to the news, ceremonial wording, a group letter they co-signed, or praise for someone else's work. (Owner ruling 3, 2026-10-23.) |
| `notes` | Anything at all: doubts, a third position, "the text is cut off". |

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

**Specificity levels** (owner ruling, 2026-10-22):

- `1`: names a specific bill, rule, program or number. *"I voted for the CHIPS Act."*
- `2`: names a concrete change but nothing specific. *"We should make it easier to
  build new homes."*
- `3`: names only the issue. *"Housing costs are hurting families."*

## Two worked examples (made up; not in the set)

1. *"Families in our district pay too much for insulin. Next week I will introduce a bill
   to cap it at $35 a month for everyone, and I won't stop until it passes."*
   → `yes` · `Health` · (blank) · `for` · `capping insulin at $35 a month for everyone` ·
   `1` (names a number) · `yes` (commits to introducing a specific bill) · (blank)
2. *"Today we honor Sergeant Maria Lopez, who gave 30 years to our county sheriff's office.
   Our community is safer because of her."*
   → `no` · and the rest blank.

## Owner rulings that shape this sheet

2026-10-22: `specificity` has three levels (above); `topic` is one of the 33 official
areas; `proposition` is for reference only and not scored.

2026-10-23 (after the first measurement failed):

1. **Multi-topic labels.** A label has a primary topic and an optional secondary topic,
   from the same 33 areas. The AI still returns ONE topic; it counts as correct when it
   matches either the primary or the secondary.
2. **No-position rule**, the same for every party, in both AI prompts and in this sheet:
   announcements of grants or funding awards, commemorative or recognition resolutions,
   ceremonies, event appearances and check presentations take NO policy position, unless
   the text also argues for or against a specific policy change. Mentioning a past vote only
   to take credit for funding or an event is not a position by itself; stating how one voted
   on a named bill is a position.
3. **The first 60 are spent** for any changed prompt. A changed prompt is measured on a
   fresh held-out 60: this set.

The precision bar (Q-K) was ratified 2026-10-23: the AI must agree with these labels on
90% of its stance, topic and priority calls and 80% of its specificity calls, with no
D/R gap over 10 points, before anything it categorizes may publish.

## How the 60 were picked (for checking, not for labeling)

Drawn by `draw_eval_set.py` with seed `2026102302` from the 40-member pilot, the same way
as set 1: 15 per party and chamber, 3 floor speeches and 12 press releases in each (about
the corpus's 1 in 5); a third (20) rejected by the first pass, on purpose, so the test can
tell whether the prompts fix the first pass's misses; 8 of those 20 are rejects the
pre-filter's own rule says name a bill or ask for a vote. So a precision number from this
set is not a corpus-wide number until it is reweighted. Texts over 8,000 characters were
left out because they are too long to label by hand, so long floor speeches are
under-represented.

**Excluded before the draw: 282 of 13,878 candidates**, each listed with its reasons in
`2026-10-23-eval-set-2-excluded.csv` (a statement can have several):

- 60: set 1's rows (this includes the 10 smoke-test rows, EV01–EV10, so they add none).
- 4: the step 9 notes (Al Green's two releases of 2026-06-12, McCollum's National
  Nonprofit Day release of 2025-08-15, Ezell's release of 2025-08-29; three of the four
  are also set-1 rows).
- 129: same member and date as a statement sampled in `docs/research/` (the two
  count-before-spend reports' 20 samples each, the triage party-gap report's 20 quotes and
  its other citations). Broad on purpose: a member's other statements that day go too.
- 69: a URL listed in `docs/research/` (the 2026-10-19 and 2026-10-20 press collection
  reports).
- 38: a title quoted in `docs/research/` (the triage party-gap report, the 2026-10-15
  rendered-press report).

Unlike set 1, the step 9 rejects are not drawn, so both "names a bill or asks for a vote"
rejects per cell come from the pre-filter's rule. The draw reads `docs/research/` from the
checkout whose `data/` it reads (`docs/research/` as last changed at `78563d289`, the
same on master `4888e6b1f`); the pool after exclusion is
13,596, and its smallest party x chamber x source x verdict stratum holds 81.
