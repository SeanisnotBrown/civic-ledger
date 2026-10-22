# Count before spend — the report the owner approves an AI run against

Owner decision 4 (§5 Phase 3): *"Collectors cache raw only. Before any AI call the run reports counts per source, per member, and after each filter step, plus estimated cost — then WAITS for the owner's approval."*

**No AI call has been made. Nothing in this repository has spent a cent.** The pre-filter is free and rule-based; the two gates below are priced, not run.

## Press coverage per pilot cell — read this first

The pilot was drawn equal by party and proportional by chamber (decision 10) so the fairness measurement has an equal-n base on both sides. **Press coverage can undo that after the draw, and no drop rate in this report can show it** — every rate below is computed over text that WAS collected.

| Cell | Rows | Collected | Single-page | Empty by markup | Refused | No list exists | Releases |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D house | 16 | 16 | 0 | 0 | 0 | 0 | 4301 |
| D senate | 4 | 3 | 0 | 0 | 1 | 0 | 3641 |
| R house | 16 | 15 | 0 | 0 | 0 | 1 | 2615 |
| R senate | 4 | 4 | 0 | 0 | 0 | 0 | 1818 |

Every cell has some press coverage.

### Every row that is not collecting

| Member | Party | Chamber | Reason |
| --- | --- | --- | --- |
| Andy Kim (`K000394`) | D | senate | refused — owner_checked: false |

### Rows with no press-release list at all

**Not a collection failure, and not counted as one in the table above.** The owner looked and these members' sites publish no press-release list, so there is nothing to collect: a zero here is the site's, not ours. Every URL tried is listed so the finding can be checked, and so a site that adds a list later reads as a change rather than as a discovery.

* **Max L. Miller** (`M001222`) — R house — site has no press-release list. Tried:
    * <https://maxmiller.house.gov/press-releases>
    * <https://maxmiller.house.gov/media/press-releases>
    * <https://maxmiller.house.gov/media>
    * <https://maxmiller.house.gov/news>

## The funnel

| Step | Statements | Member turns |
| --- | --- | --- |
| Collected | 17012 | 19811 |
| Of those, no readable body — a collection failure, never judged | 182 | 0 |
| Judged by the free pre-filter | 16830 | 19811 |
| After the free pre-filter (decision 2) | 14983 | 17625 |
| Of those, eligible for the AI | 14810 | — |
| Reaching the Haiku triage gate (decision 3) | 14810 | — |
| Reaching the Opus categorizer (decision 7 cap: 25/member) | 1000 | — |

173 surviving statements are marked **ineligible for the AI** and are never priced: they are the vote explanations the owner ruled on (R3, 2026-10-14) — kept as record, matched to their roll call mechanically, never categorized.

## Per source

| Source | Collected | No readable body (collection failure) | Kept | Dropped by the filter |
| --- | --- | --- | --- | --- |
| `congressional_record` | 4637 | 0 | 3104 | 1533 |
| `member_press` | 12375 | 182 | 11879 | 314 |

## Collection failures — no readable body, per row

A release the collector fetched and found no readable body on. **Not a filter drop:** the filter never saw any words to judge, so these are left out of the fairness rates below and out of "dropped by the filter". They are the collector's, listed by URL under `text_failures` in its own index.

| Member | Party | Source | Releases with no readable body |
| --- | --- | --- | --- |
| Gus M. Bilirakis (B001257) | R | `member_press` | 2 |
| Kathy Castor (C001066) | D | `member_press` | 15 |
| Neal P. Dunn (D000628) | R | `member_press` | 4 |
| Mike Ezell (E000235) | R | `member_press` | 12 |
| Bill Foster (F000454) | D | `member_press` | 15 |
| Julie Fedorchak (F000482) | R | `member_press` | 1 |
| Al Green (G000553) | D | `member_press` | 2 |
| Martin Heinrich (H001046) | D | `member_press` | 104 |
| Mike Johnson (J000299) | R | `member_press` | 15 |
| Mike Kennedy (K000403) | R | `member_press` | 1 |
| Betty McCollum (M001143) | D | `member_press` | 1 |
| Thomas Massie (M001184) | R | `member_press` | 1 |
| Scott Perry (P000605) | R | `member_press` | 3 |
| Jeanne Shaheen (S001181) | D | `member_press` | 2 |
| Lauren Underwood (U000040) | D | `member_press` | 1 |
| Ryan K. Zinke (Z000018) | R | `member_press` | 3 |

## Fairness at each filter step (decision 4)

Rates are per party, over the turns that party brought to the filter — the pilot is equal by party in MEMBERS, not in turns. A step is flagged when the party rates differ by 1.5x or more over at least 50 dropped turns.

| Rule | Turns dropped | D | R | D rate | R rate | Flag |
| --- | --- | --- | --- | --- | --- | --- |
| `no-attributable-text` | 48 | 24 | 24 | 0.2% | 0.3% | even |
| `procedural` | 382 | 116 | 266 | 1.0% | 3.1% | **UNEVEN** |
| `ceremonial` | 1762 | 880 | 882 | 7.9% | 10.1% | even |
| `duplicate` | 42 | 32 | 10 | 0.3% | 0.1% | even |

### The same rates, per source

The rules do not bite equally on the two sources and the two sources are not equally distributed between the parties, so the combined table above can show a party skew that is really a source skew. The Congressional Record speaks in the first person ("I rise today to recognize"), which is what the ceremonial patterns match; a press office writes in the third ("Rep. X Honors a Local Lineman"), so the same rule fires far less there. Press volumes also differ sharply by member. Both tables are here so the two effects cannot be mistaken for each other.

| Source | Rule | Turns | D rate | R rate | Flag |
| --- | --- | --- | --- | --- | --- |
| `congressional_record` | `no-attributable-text` | 48 | 0.7% | 0.6% | even |
| `congressional_record` | `procedural` | 382 | 3.5% | 6.1% | **UNEVEN** |
| `congressional_record` | `ceremonial` | 1473 | 21.2% | 17.7% | even |
| `congressional_record` | `duplicate` | 17 | 0.3% | 0.1% | even |
| `member_press` | `no-attributable-text` | 0 | 0.0% | 0.0% | even |
| `member_press` | `procedural` | 0 | 0.0% | 0.0% | even |
| `member_press` | `ceremonial` | 289 | 2.2% | 2.6% | even |
| `member_press` | `duplicate` | 25 | 0.3% | 0.1% | even |

### Every flagged step

* `procedural` (all sources) — D 116 of 11140 turns (1.0%), R 266 of 8719 turns (3.1%); 382 turns dropped. **Owner-accepted 2026-10-14 (R4)**, on the condition below.
* `procedural` (`congressional_record`) — D 116 of 3338 turns (3.5%), R 266 of 4328 turns (6.1%); 382 turns dropped. **Owner-accepted 2026-10-14 (R4)**, on the condition below.

The owner accepted the procedural gap on 2026-10-14 **on condition that the drop log and this report break it down to each sub-rule**, so the structural explanation is checkable rather than asserted (R4). The cause is that the majority party's floor managers make the housekeeping requests.

| Sub-rule | Turns | D | R |
| --- | --- | --- | --- |
| `leave-to-revise-and-extend` | 67 | 7 | 60 |
| `adjournment-and-meeting-hour` | 9 | 1 | 8 |
| `quorum-call` | 49 | 32 | 17 |
| `committee-authority-to-meet` | 0 | 0 | 0 |
| `floor-privileges` | 3 | 3 | 0 |
| `yielding-time` | 199 | 45 | 154 |
| `calendar-and-morning-business` | 7 | 4 | 3 |
| `unanimous-consent-request` | 48 | 24 | 24 |

## Per member

| Member | Party | Collected | Kept | To the categorizer |
| --- | --- | --- | --- | --- |
| Gus M. Bilirakis (B001257) | R | 712 | 340 | 25 |
| Jim Costa (C001059) | D | 460 | 355 | 25 |
| Kathy Castor (C001066) | D | 428 | 368 | 25 |
| Angie Craig (C001119) | D | 476 | 402 | 25 |
| Mark DeSaulnier (D000623) | D | 327 | 228 | 25 |
| Neal P. Dunn (D000628) | R | 152 | 138 | 25 |
| Sharice Davids (D000629) | D | 656 | 620 | 25 |
| Mike Ezell (E000235) | R | 205 | 153 | 25 |
| Bill Foster (F000454) | D | 303 | 222 | 25 |
| Julie Fedorchak (F000482) | R | 323 | 298 | 25 |
| Al Green (G000553) | D | 575 | 559 | 25 |
| Bill Hagerty (H000601) | R | 713 | 684 | 25 |
| Martin Heinrich (H001046) | D | 1699 | 1556 | 25 |
| Jahana Hayes (H001081) | D | 288 | 283 | 25 |
| Mark Harris (H001102) | R | 135 | 123 | 25 |
| Mike Johnson (J000299) | R | 609 | 563 | 25 |
| Mark Kelly (K000377) | D | 1299 | 1247 | 25 |
| Trent Kelly (K000388) | R | 95 | 44 | 25 |
| Andy Kim (K000394) | D | 183 | 150 | 25 |
| Mike Kennedy (K000403) | R | 128 | 113 | 25 |
| Barry Loudermilk (L000583) | R | 133 | 111 | 25 |
| Darin LaHood (L000585) | R | 337 | 268 | 25 |
| Betty McCollum (M001143) | D | 523 | 466 | 25 |
| Thomas Massie (M001184) | R | 108 | 105 | 25 |
| John R. Moolenaar (M001194) | R | 346 | 334 | 25 |
| Max L. Miller (M001222) | R | 79 | 50 | 25 |
| Sarah McBride (M001238) | D | 210 | 187 | 25 |
| Scott Perry (P000605) | R | 218 | 179 | 25 |
| Mike Rounds (R000605) | R | 452 | 436 | 25 |
| Josh Riley (R000622) | D | 121 | 117 | 25 |
| Janice D. Schakowsky (S001145) | D | 358 | 323 | 25 |
| Jeanne Shaheen (S001181) | D | 1572 | 1498 | 25 |
| Terri A. Sewell (S001185) | D | 528 | 418 | 25 |
| Tim Sheehy (S001232) | R | 156 | 126 | 25 |
| Lauren Underwood (U000040) | D | 185 | 180 | 25 |
| Juan Vargas (V000130) | D | 228 | 180 | 25 |
| Bruce Westerman (W000821) | R | 396 | 353 | 25 |
| George Whitesides (W000830) | D | 116 | 111 | 25 |
| Todd Young (Y000064) | R | 941 | 881 | 25 |
| Ryan K. Zinke (Z000018) | R | 239 | 214 | 25 |

## One-liners in the first run's allowance (under 200 characters)

Decision 7 sends each member's newest **25** surviving statements to the categorizer. R2 deliberately KEEPS a bare vote urge — "I encourage a yes vote on this bill, and I yield back the balance of my time" — because a vote urge is a position. This is not a proposal to drop them. It is where the first run's money goes: a member whose allowance is mostly one-liners buys far less analysis than a member with argued speeches, and that is worth knowing before the run rather than after it.

| Member | Party | To the categorizer | Under the threshold | Flag |
| --- | --- | --- | --- | --- |
| Gus M. Bilirakis (`B001257`) | R | 25 | 0 |  |
| Jim Costa (`C001059`) | D | 25 | 0 |  |
| Kathy Castor (`C001066`) | D | 25 | 0 |  |
| Angie Craig (`C001119`) | D | 25 | 0 |  |
| Mark DeSaulnier (`D000623`) | D | 25 | 0 |  |
| Neal P. Dunn (`D000628`) | R | 25 | 0 |  |
| Sharice Davids (`D000629`) | D | 25 | 0 |  |
| Mike Ezell (`E000235`) | R | 25 | 0 |  |
| Bill Foster (`F000454`) | D | 25 | 0 |  |
| Julie Fedorchak (`F000482`) | R | 25 | 0 |  |
| Al Green (`G000553`) | D | 25 | 14 | **MOSTLY ONE-LINERS** |
| Bill Hagerty (`H000601`) | R | 25 | 2 |  |
| Martin Heinrich (`H001046`) | D | 25 | 0 |  |
| Jahana Hayes (`H001081`) | D | 25 | 0 |  |
| Mark Harris (`H001102`) | R | 25 | 0 |  |
| Mike Johnson (`J000299`) | R | 25 | 1 |  |
| Mark Kelly (`K000377`) | D | 25 | 0 |  |
| Trent Kelly (`K000388`) | R | 25 | 18 | **MOSTLY ONE-LINERS** |
| Andy Kim (`K000394`) | D | 25 | 1 |  |
| Mike Kennedy (`K000403`) | R | 25 | 0 |  |
| Barry Loudermilk (`L000583`) | R | 25 | 0 |  |
| Darin LaHood (`L000585`) | R | 25 | 1 |  |
| Betty McCollum (`M001143`) | D | 25 | 0 |  |
| Thomas Massie (`M001184`) | R | 25 | 0 |  |
| John R. Moolenaar (`M001194`) | R | 25 | 0 |  |
| Max L. Miller (`M001222`) | R | 25 | 0 |  |
| Sarah McBride (`M001238`) | D | 25 | 0 |  |
| Scott Perry (`P000605`) | R | 25 | 0 |  |
| Mike Rounds (`R000605`) | R | 25 | 0 |  |
| Josh Riley (`R000622`) | D | 25 | 0 |  |
| Janice D. Schakowsky (`S001145`) | D | 25 | 0 |  |
| Jeanne Shaheen (`S001181`) | D | 25 | 0 |  |
| Terri A. Sewell (`S001185`) | D | 25 | 0 |  |
| Tim Sheehy (`S001232`) | R | 25 | 0 |  |
| Lauren Underwood (`U000040`) | D | 25 | 0 |  |
| Juan Vargas (`V000130`) | D | 25 | 0 |  |
| Bruce Westerman (`W000821`) | R | 25 | 0 |  |
| George Whitesides (`W000830`) | D | 25 | 0 |  |
| Todd Young (`Y000064`) | R | 25 | 0 |  |
| Ryan K. Zinke (`Z000018`) | R | 25 | 0 |  |

**2 member(s) flagged**: more than half of what they send to the categorizer is under 200 characters. The threshold is "more than half of what they actually bring", not of the 25 allowance — a member with six statements is not flagged for having four short ones out of an allowance they never filled.


## Audit sample — 20 Republican procedural drops, at random, in full

On 2026-10-14 the owner accepted a procedural drop rate roughly 2.3x higher for Republicans, on the explanation that the majority party's floor managers make the housekeeping requests. **This is the check on that.** Read them: *if any of these argue policy, the rule is too wide and the ruling should be revisited.*

Drawn at random with seed `20261014`, committed here so the same 20 can be re-drawn — a hand-picked sample would prove nothing, and an unseeded one could not be checked for having been picked. The text is the WHOLE turn, read back from the corpus, not the drop log's shortened excerpt.

1. **Gus M. Bilirakis** (`B001257`), 2025-04-28 — `leave-to-revise-and-extend` — SETTING CONSUMER STANDARDS FOR LITHIUM-ION BATTERIES ACT

   > I ask unanimous consent that all Members have 5 legislative days in which to revise and extend their remarks and include extraneous material in the Record on the bill.

2. **Bill Hagerty** (`H000601`), 2024-05-02 — `quorum-call` — LEGISLATIVE SESSION

   > I ask unanimous consent that the order for the quorum call be rescinded. The PRESIDING OFFICER (Mr. King). Without objection, it is so ordered. The Senator from Tennessee. Unanimous Consent Request

3. **Bill Hagerty** (`H000601`), 2024-05-16 — `unanimous-consent-request` — EXECUTIVE CALENDAR

   > I ask unanimous consent for Senator Schatz and I to conclude our remarks prior to the vote.

4. **Bill Hagerty** (`H000601`), 2026-07-22 — `quorum-call` — The New York Times (Executive Session)

   > I ask unanimous consent that the order for the quorum call be rescinded.

5. **Thomas Massie** (`M001184`), 2024-03-12 — `leave-to-revise-and-extend` — PROVIDING FOR CONSIDERATION OF H.R. 6276, UTILIZING SPACE EFFICIENTLY AND IMPROVING TECHNOLOGIES ACT OF 2023, AND PROVIDING FOR CONSIDERATION OF H. RES. 1065, DENOUNCING THE BIDEN ADMINISTRATION'S...

   > I ask unanimous consent that all Members have 5 legislative days in which to revise and extend their remarks.

6. **Max L. Miller** (`M001222`), 2023-05-09 — `yielding-time` — TESTING, RAPID ANALYSIS, AND NARCOTIC QUALITY RESEARCH ACT

   > I am ready to close, and I reserve the balance of my time.

7. **Scott Perry** (`P000605`), 2026-09-16 — `yielding-time` — STOPPING POLITICAL DISCRIMINATION IN DISASTER ASSISTANCE ACT

   > I reserve the balance of my time.

8. **Mike Rounds** (`R000605`), 2023-03-08 — `calendar-and-morning-business` — MORNING BUSINESS

   > I ask unanimous consent that the Senate be in a period of morning business, with Senators permitted to speak therein for up to 10 minutes each.

9. **Mike Rounds** (`R000605`), 2024-03-21 — `unanimous-consent-request` — Israel (Executive Session)

   > I ask unanimous consent to speak for up to 5 minutes, followed by Senator Tester for up to 10 minutes prior to the scheduled rollcall votes.

10. **Mike Rounds** (`R000605`), 2026-03-18 — `unanimous-consent-request` — RESOLUTIONS SUBMITTED TODAY

   > I ask unanimous consent that the resolutions be agreed to, the preambles be agreed to, and that the motions to reconsider be considered made and laid upon the table, all en bloc.

11. **Bruce Westerman** (`W000821`), 2023-11-06 — `yielding-time` — WOMEN'S SUFFRAGE NATIONAL MONUMENT LOCATION ACT

   > I am prepared to close, and I reserve the balance of my time.

12. **Bruce Westerman** (`W000821`), 2023-11-29 — `yielding-time` — PROTECTING OUR COMMUNITIES FROM FAILURE TO SECURE THE BORDER ACT OF 2023

   > I believe I have about as much time left as the Biden administration put into the permitting process on Floyd Bennett Field. I am prepared to close, and I reserve the balance of my time.

13. **Bruce Westerman** (`W000821`), 2024-12-03 — `yielding-time` — LAHAINA NATIONAL HERITAGE AREA STUDY ACT

   > I have no further requests for time. I am prepared to close, and I reserve the balance of my time.

14. **Bruce Westerman** (`W000821`), 2025-05-13 — `yielding-time` — REDESIGNATION OF PATERSON GREAT FALLS NHP FACILITIES

   > I have no further requests for time. I am prepared to close, and I reserve the balance of my time.

15. **Bruce Westerman** (`W000821`), 2025-05-13 — `yielding-time` — SALEM MARITIME NATIONAL HISTORICAL PARK REDESIGNATION AND BOUNDARY STUDY ACT

   > I have no further requests for time. I am prepared to close, and I reserve the balance of my time.

16. **Bruce Westerman** (`W000821`), 2025-07-14 — `yielding-time` — BOLTS DITCH ACT

   > I have no further requests for time. I am prepared to close, and I reserve the balance of my time.

17. **Bruce Westerman** (`W000821`), 2025-09-03 — `yielding-time` — PROVIDING FOR CONGRESSIONAL DISAPPROVAL OF THE RULE SUBMITTED BY THE BUREAU OF LAND MANAGEMENT RELATING TO "MILES CITY FIELD OFFICE RECORD OF DECISION AND APPROVED RESOURCE MANAGEMENT PLAN...

   > I have no further requests for time. I am prepared to close, and I reserve the balance of my time.

18. **Bruce Westerman** (`W000821`), 2026-06-02 — `yielding-time` — CROSS-BOUNDARY WILDFIRE SOLUTIONS ACT

   > I am prepared to close, and I reserve the balance of my time.

19. **Todd Young** (`Y000064`), 2023-06-14 — `unanimous-consent-request` — Unanimous Consent Request--Executive Calendar (Executive Session)

   > I ask unanimous consent to speak for up to 10 minutes prior to the scheduled rollcall votes.

20. **Todd Young** (`Y000064`), 2024-05-16 — `unanimous-consent-request` — PRIVILEGES OF THE FLOOR

   > I ask unanimous consent that DeMark Schulze, a State Department Pearson fellow from my office and a 2005 graduate of the University of Notre Dame, be granted floor privileges until August 3, 2024.


## Estimated cost

| Stage | Statements | Estimated |
| --- | --- | --- |
| Haiku triage gate | 14810 | $2.8713 |
| Opus categorizer | 1000 | $20.94 |
| **Total** | | **$23.81** |
| Cap (`per_run_cost_cap_usd`) | | $5.00 |

**OVER THE CAP.** The run would stop part-way. The owner raises the cap for a run, or the builder does not run it — the builder never raises it unasked (decision 9).

Priced from `data/config/ai.yaml` — the same prices `ingest/ai.py` enforces the cap on — at roughly four characters per token, plus prompt and schema overhead and the model's own thinking tokens on the way out. The categorizer line prices the WORST case: every statement passing the triage gate. Measured against four live calls on 2026-10-09, a categorized statement ran $0.0095-$0.014.

## What a yes authorises, and what it does not

A yes here authorises **one run** of the triage gate and the categorizer under the cap above. It does not authorise publishing anything: Q-K, the precision launch bar, is still open, and nothing categorized publishes before it is answered. Archive capture (decision 8) happens after both gates and before the review queue, and the archive sweep's own keys are still owed.
