# Triage run — the first pass (Haiku), counts only

Generated 2026-10-22T18:01:33+00:00 by `uv run ingest triage-run`. Task `triage_statement`, model `claude-haiku-5-5`, prompt `v1-stub` (a STUB: nothing here may be published or counted toward precision).

**The Opus categorizer was NOT called** (owner ruling 2026-10-22, step 9 option b): it waits for a prompt tested against at least 50 hand-labeled statements.

## This invocation

| | |
| --- | --- |
| How it ended | `complete` |
| Verdicts recorded this time | 14118 |
| API calls made (cache hits are free) | 14121 (0 cache hits) |
| Spent this time | $3.3079 of a $4.00 cap |
| Most calls in flight at once | 96 (ceiling 96) |
| Rate-limited calls retried (never errors) | 0 |
| Connection or server errors retried | 0 |
| Rate limits the API reported | requests 5000/min, input-tokens 5000000/min, output-tokens 1000000/min |
| Statements with no verdict because of an error | 3 |

## All runs under this prompt version

14810 statements are eligible (pre-filter survivors, less the vote explanations R3 keeps out of the AI). 14807 have a verdict: **12091 take a position on an identifiable policy**, 2716 do not. 3 are still to do.

## Per pilot cell

| Cell | Eligible | Triaged | Passed | Not passed | Remaining |
| --- | --- | --- | --- | --- | --- |
| D house | 4918 | 4918 | 3812 | 1106 | 0 |
| D senate | 4435 | 4434 | 3945 | 489 | 1 |
| R house | 3332 | 3331 | 2607 | 724 | 1 |
| R senate | 2125 | 2124 | 1727 | 397 | 1 |

## Per member

"Short of 25" flags a member with fewer than decision 7's 25 passed statements once triage is finished: the categorizer would get less from them than its allowance.

| Member | Cell | Eligible | Triaged | Passed | Not passed | Remaining | Flag |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Gus M. Bilirakis (B001257) | R house | 340 | 340 | 286 | 54 | 0 |  |
| Jim Costa (C001059) | D house | 353 | 353 | 279 | 74 | 0 |  |
| Kathy Castor (C001066) | D house | 364 | 364 | 303 | 61 | 0 |  |
| Angie Craig (C001119) | D house | 397 | 397 | 312 | 85 | 0 |  |
| Mark DeSaulnier (D000623) | D house | 216 | 216 | 127 | 89 | 0 |  |
| Neal P. Dunn (D000628) | R house | 128 | 128 | 99 | 29 | 0 |  |
| Sharice Davids (D000629) | D house | 618 | 618 | 529 | 89 | 0 |  |
| Mike Ezell (E000235) | R house | 152 | 152 | 118 | 34 | 0 |  |
| Bill Foster (F000454) | D house | 215 | 215 | 168 | 47 | 0 |  |
| Julie Fedorchak (F000482) | R house | 298 | 298 | 237 | 61 | 0 |  |
| Al Green (G000553) | D house | 541 | 541 | 255 | 286 | 0 |  |
| Bill Hagerty (H000601) | R senate | 683 | 683 | 581 | 102 | 0 |  |
| Martin Heinrich (H001046) | D senate | 1552 | 1551 | 1357 | 194 | 1 |  |
| Jahana Hayes (H001081) | D house | 275 | 275 | 234 | 41 | 0 |  |
| Mark Harris (H001102) | R house | 123 | 123 | 92 | 31 | 0 |  |
| Mike Johnson (J000299) | R house | 562 | 562 | 435 | 127 | 0 |  |
| Mark Kelly (K000377) | D senate | 1246 | 1246 | 1084 | 162 | 0 |  |
| Trent Kelly (K000388) | R house | 44 | 44 | 8 | 36 | 0 | short of 25 |
| Andy Kim (K000394) | D senate | 150 | 150 | 142 | 8 | 0 |  |
| Mike Kennedy (K000403) | R house | 113 | 113 | 91 | 22 | 0 |  |
| Barry Loudermilk (L000583) | R house | 109 | 109 | 79 | 30 | 0 |  |
| Darin LaHood (L000585) | R house | 254 | 254 | 210 | 44 | 0 |  |
| Betty McCollum (M001143) | D house | 458 | 458 | 381 | 77 | 0 |  |
| Thomas Massie (M001184) | R house | 104 | 104 | 90 | 14 | 0 |  |
| John R. Moolenaar (M001194) | R house | 334 | 333 | 266 | 67 | 1 |  |
| Max L. Miller (M001222) | R house | 46 | 46 | 31 | 15 | 0 |  |
| Sarah McBride (M001238) | D house | 186 | 186 | 162 | 24 | 0 |  |
| Scott Perry (P000605) | R house | 163 | 163 | 106 | 57 | 0 |  |
| Mike Rounds (R000605) | R senate | 435 | 435 | 332 | 103 | 0 |  |
| Josh Riley (R000622) | D house | 113 | 113 | 105 | 8 | 0 |  |
| Janice D. Schakowsky (S001145) | D house | 317 | 317 | 268 | 49 | 0 |  |
| Jeanne Shaheen (S001181) | D senate | 1487 | 1487 | 1362 | 125 | 0 |  |
| Terri A. Sewell (S001185) | D house | 401 | 401 | 305 | 96 | 0 |  |
| Tim Sheehy (S001232) | R senate | 126 | 126 | 103 | 23 | 0 |  |
| Lauren Underwood (U000040) | D house | 173 | 173 | 128 | 45 | 0 |  |
| Juan Vargas (V000130) | D house | 180 | 180 | 165 | 15 | 0 |  |
| Bruce Westerman (W000821) | R house | 348 | 348 | 293 | 55 | 0 |  |
| George Whitesides (W000830) | D house | 111 | 111 | 91 | 20 | 0 |  |
| Todd Young (Y000064) | R senate | 881 | 880 | 711 | 169 | 1 |  |
| Ryan K. Zinke (Z000018) | R house | 214 | 214 | 166 | 48 | 0 |  |

## Errors this time (no verdict; a re-run asks again)

* `Y000064|congressional_record|https://www.govinfo.gov/app/details/CREC-2026-07-13/CREC-2026-07-13-pt1-PgS3900` — triage_statement: the model declined this input (refusal)
* `M001194|member_press|https://moolenaar.house.gov/media-center/press-releases/moolenaar-michigan-arrest-highlights-ccp-threat-our-food-supply-and-our` — triage_statement: the model declined this input (refusal)
* `H001046|congressional_record|https://www.govinfo.gov/app/details/CREC-2026-04-22/CREC-2026-04-22-pt1-PgS2014-5` — triage_statement: the model declined this input (refusal)
