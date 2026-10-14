# Collector (a) — member press releases: the count report

Window **2023-01-03 to 2026-10-14** (owner decision 1). Source list: `data/config/statement-sources.yaml`, owner-maintained and read only. **No AI call, no archive capture, no spend.**

**32 rows collected, 8 refused.** 6180 releases in the window.

* Release bodies were pulled for every release counted below; **60 could not be read** and are listed in `data/raw/press/index.json` under `text_failures`. A release with no readable body is recorded as a failure, never as a statement with no words.

## Per member

| Member | Party | Releases | Text | Pages | Walk |
| --- | --- | --- | --- | --- | --- |
| Gus M. Bilirakis (B001257) | R | 274 | 272 | 29 | complete |
| Jim Costa (C001059) | D | 317 | 317 | 33 | complete |
| Kathy Castor (C001066) | D | 307 | 292 | 32 | complete |
| Angie Craig (C001119) | D | 378 | 378 | 39 | complete |
| Mark DeSaulnier (D000623) | D | 155 | 155 | 17 | complete |
| Neal P. Dunn (D000628) | R | 116 | 112 | 13 | complete |
| Sharice Davids (D000629) | D | 604 | 604 | 62 | complete |
| Mike Ezell (E000235) | R | 147 | 135 | 16 | complete |
| Bill Foster (F000454) | D | 192 | 177 | 21 | complete |
| Julie Fedorchak (F000482) | R | 276 | 275 | 29 | complete |
| Al Green (G000553) | D | 395 | 393 | 41 | complete |
| Bill Hagerty (H000601) | R | 578 | 578 | 117 | complete |
| Jahana Hayes (H001081) | D | 251 | 251 | 27 | complete |
| Mark Harris (H001102) | R | 83 | 83 | 10 | complete |
| Mark Kelly (K000377) | D | 0 | 0 | 1 | **INCOMPLETE — empty** |
| Trent Kelly (K000388) | R | 28 | 28 | 4 | complete |
| Mike Kennedy (K000403) | R | 69 | 68 | 8 | complete |
| Barry Loudermilk (L000583) | R | 101 | 101 | 12 | complete |
| Betty McCollum (M001143) | D | 305 | 304 | 32 | complete |
| John R. Moolenaar (M001194) | R | 324 | 324 | 34 | complete |
| Max L. Miller (M001222) | R | 0 | 0 | 1 | **INCOMPLETE — empty** |
| Sarah McBride (M001238) | D | 170 | 170 | 18 | complete |
| Scott Perry (P000605) | R | 50 | 47 | 6 | complete |
| Josh Riley (R000622) | D | 0 | 0 | 1 | **INCOMPLETE — empty** |
| Janice D. Schakowsky (S001145) | D | 304 | 304 | 32 | complete |
| Tim Sheehy (S001232) | R | 96 | 96 | 9 | complete |
| Lauren Underwood (U000040) | D | 160 | 159 | 17 | complete |
| Juan Vargas (V000130) | D | 167 | 167 | 18 | complete |
| Bruce Westerman (W000821) | R | 116 | 116 | 13 | complete |
| George Whitesides (W000830) | D | 0 | 0 | 1 | **INCOMPLETE — empty** |
| Todd Young (Y000064) | R | 20 | 20 | 1 | **INCOMPLETE — single-page** |
| Ryan K. Zinke (Z000018) | R | 197 | 194 | 21 | complete |

## Per party

| Party | Releases |
| --- | --- |
| D | 3705 |
| R | 2475 |

## Walks that did not reach the window's start

These members' counts are a floor, not a total. `window` (the walk reached 2023) and `exhausted` (the pager ran off the end of an archive that begins inside the window) both mean COMPLETE and are not listed here. Everything below stopped early, so the member is under-collected.

* `K000377` Mark Kelly — **empty**: no dated releases on the first page
* `M001222` Max L. Miller — **empty**: no dated releases on the first page
* `R000622` Josh Riley — **empty**: no dated releases on the first page
* `W000830` George Whitesides — **empty**: no dated releases on the first page
* `Y000064` Todd Young — **single-page**: one page only, and no page 2 — a short archive and a JavaScript 'load more' are indistinguishable to a plain GET

## Refused, by id

The source list's own rule: collector (a) must refuse a row that still says `owner_checked: false` (fact 7, STATUS.md). These are listed so a refusal is never mistaken for a member who published nothing.

* `H001046` Martin Heinrich — owner_checked: false
* `J000299` Mike Johnson — owner_checked: false
* `K000394` Andy Kim — owner_checked: false
* `L000585` Darin LaHood — owner_checked: false
* `M001184` Thomas Massie — owner_checked: false
* `R000605` Mike Rounds — owner_checked: false
* `S001181` Jeanne Shaheen — owner_checked: false
* `S001185` Terri A. Sewell — owner_checked: false
