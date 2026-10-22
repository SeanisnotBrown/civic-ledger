# Congressional Record collection counts — the pilot 40

Generated 2026-10-22 by `uv run ingest statements-crec`.

Window **2023-01-03 → 2026-10-20** (owner decision 1), **793** Record issues read. Counts are granules the Record's own MODS metadata records the member as **SPEAKING** in — not name matches. Nothing has been filtered, categorized or captured: no AI call was made and no archive snapshot was taken.

`EXTENSIONS` is Extensions of Remarks — written insertions rather than floor speech. They are collected and counted separately because whether they count as a statement for grading is an owner call, not the collector's.

| Member | Party | Chamber | House | Senate | Extensions | Total | Text pulled |
|---|---|---|---|---|---|---|---|
| Gus M. Bilirakis (B001257) | R | house | 77 | 0 | 361 | 438 | 438 |
| Jim Costa (C001059) | D | house | 47 | 0 | 96 | 143 | 143 |
| Kathy Castor (C001066) | D | house | 62 | 0 | 61 | 123 | 123 |
| Angie Craig (C001119) | D | house | 31 | 0 | 67 | 98 | 98 |
| Mark DeSaulnier (D000623) | D | house | 93 | 0 | 79 | 172 | 172 |
| Neal P. Dunn (D000628) | R | house | 17 | 0 | 19 | 36 | 36 |
| Sharice Davids (D000629) | D | house | 14 | 0 | 38 | 52 | 52 |
| Mike Ezell (E000235) | R | house | 50 | 0 | 11 | 61 | 61 |
| Bill Foster (F000454) | D | house | 45 | 0 | 66 | 111 | 111 |
| Julie Fedorchak (F000482) | R | house | 47 | 0 | 0 | 47 | 47 |
| Al Green (G000553) | D | house | 161 | 0 | 9 | 170 | 170 |
| Bill Hagerty (H000601) | R | senate | 0 | 135 | 0 | 135 | 135 |
| Martin Heinrich (H001046) | D | senate | 0 | 286 | 0 | 286 | 286 |
| Jahana Hayes (H001081) | D | house | 32 | 0 | 4 | 36 | 36 |
| Mark Harris (H001102) | R | house | 52 | 0 | 0 | 52 | 52 |
| Mike Johnson (J000299) | R | house | 43 | 0 | 10 | 53 | 53 |
| Mark Kelly (K000377) | D | senate | 0 | 228 | 0 | 228 | 228 |
| Trent Kelly (K000388) | R | house | 14 | 0 | 53 | 67 | 67 |
| Andy Kim (K000394) | D | senate | 9 | 146 | 28 | 183 | 183 |
| Mike Kennedy (K000403) | R | house | 59 | 0 | 0 | 59 | 59 |
| Barry Loudermilk (L000583) | R | house | 18 | 0 | 14 | 32 | 32 |
| Darin LaHood (L000585) | R | house | 48 | 0 | 60 | 108 | 108 |
| Betty McCollum (M001143) | D | house | 76 | 0 | 142 | 218 | 218 |
| Thomas Massie (M001184) | R | house | 52 | 0 | 3 | 55 | 55 |
| John R. Moolenaar (M001194) | R | house | 19 | 0 | 3 | 22 | 22 |
| Max L. Miller (M001222) | R | house | 75 | 0 | 4 | 79 | 79 |
| Sarah McBride (M001238) | D | house | 38 | 0 | 2 | 40 | 40 |
| Scott Perry (P000605) | R | house | 98 | 0 | 71 | 169 | 169 |
| Mike Rounds (R000605) | R | senate | 0 | 124 | 0 | 124 | 124 |
| Josh Riley (R000622) | D | house | 20 | 0 | 0 | 20 | 20 |
| Janice D. Schakowsky (S001145) | D | house | 24 | 0 | 30 | 54 | 54 |
| Jeanne Shaheen (S001181) | D | senate | 0 | 415 | 0 | 415 | 415 |
| Terri A. Sewell (S001185) | D | house | 84 | 0 | 53 | 137 | 137 |
| Tim Sheehy (S001232) | R | senate | 0 | 60 | 0 | 60 | 60 |
| Lauren Underwood (U000040) | D | house | 24 | 0 | 1 | 25 | 25 |
| Juan Vargas (V000130) | D | house | 27 | 0 | 34 | 61 | 61 |
| Bruce Westerman (W000821) | R | house | 249 | 0 | 31 | 280 | 280 |
| George Whitesides (W000830) | D | house | 18 | 0 | 3 | 21 | 21 |
| Todd Young (Y000064) | R | senate | 0 | 125 | 0 | 125 | 125 |
| Ryan K. Zinke (Z000018) | R | house | 19 | 0 | 23 | 42 | 42 |

## Per party

| Party | Members | House | Senate | Extensions | Total | Mean per member |
|---|---|---|---|---|---|---|
| D | 20 | 805 | 1075 | 713 | 2593 | 129.7 |
| R | 20 | 937 | 444 | 663 | 2044 | 102.2 |

## What a reader should check before approving any spend

* Granule text was pulled for **every** granule counted above.
* Members with **no** speaking granule in the window: none.
* **No cost is estimated here, by design.** Nothing has been through the pre-filter (decision 2) or the triage gate (decision 3), so a per-statement estimate taken off these counts would be meaningless. For scale only, the known CEILING is decision 7's cap — 40 members x 25 newest = 1,000 categorized at the $0.0095-$0.014 measured on 2026-10-09, so $10-14, which exceeds the $5 per-run cap and will stop for owner approval. That is the flow working, not a surprise.
* Issues that could not be read: 0
