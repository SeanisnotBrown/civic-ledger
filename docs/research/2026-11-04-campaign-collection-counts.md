# Campaign issue pages — collection counts (P3 task 2c)

Generated 2026-11-04 by `uv run ingest statements-campaign`. Window: most recent run only (owner decision 1). No AI call and no spend. Counts only: the page text stays in the gitignored `data/raw/campaign/`.

**URL provenance: copilot-authored, not reviewed by Sean.** A count here says what the pages held, not that a URL is right.

## By party

| Party | Rows with a URL | Rows collected | Statements | Characters | Skipped (null) | Refused | Blocked | Other unread |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D | 17 | 16 | 180 | 283,500 | 3 | 0 | 1 | 0 |
| R | 14 | 13 | 106 | 72,741 | 6 | 0 | 1 | 0 |

## By member

| Member | Party | Cycle | Layout | Pages read | Statements | Characters | Outcome |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Gus M. Bilirakis (`B001257`) | R | 2026 | single | 1 | 10 | 4,025 | complete |
| Jim Costa (`C001059`) | D | 2026 | single | 1 | 9 | 11,330 | complete |
| Angie Craig (`C001119`) | D | 2026 | index | 5 | 4 | 6,305 | complete |
| Mark DeSaulnier (`D000623`) | D | 2026 | single | 1 | 13 | 14,592 | complete |
| Sharice Davids (`D000629`) | D | 2026 | single | 1 | 13 | 15,783 | complete |
| Mike Ezell (`E000235`) | R | 2026 | index | 7 | 6 | 3,802 | complete |
| Bill Foster (`F000454`) | D | 2026 | index | 13 | 12 | 54,424 | complete |
| Julie Fedorchak (`F000482`) | R | 2026 | single | 1 | 1 | 639 | complete |
| Al Green (`G000553`) | D | 2026 | single | 1 | 8 | 4,004 | complete |
| Martin Heinrich (`H001046`) | D | 2024 | index | 15 | 14 | 36,204 | complete |
| Jahana Hayes (`H001081`) | D | 2026 | index | 15 | 14 | 6,520 | complete |
| Mark Harris (`H001102`) | R | 2026 | single | 1 | 6 | 2,569 | complete |
| Mark Kelly (`K000377`) | D | 2022 | — | 0 | 0 | 0 | blocked: HTTP 403 |
| Andy Kim (`K000394`) | D | 2024 | index | 10 | 9 | 14,030 | complete |
| Mike Kennedy (`K000403`) | R | 2026 | single | 1 | 9 | 5,855 | complete |
| Barry Loudermilk (`L000583`) | R | 2024 | — | 0 | 0 | 0 | blocked: HTTP 403 |
| Darin LaHood (`L000585`) | R | 2026 | single | 1 | 9 | 8,609 | complete |
| Thomas Massie (`M001184`) | R | 2026 | single | 1 | 5 | 1,196 | complete |
| John R. Moolenaar (`M001194`) | R | 2026 | index | 17 | 16 | 23,301 | complete |
| Max L. Miller (`M001222`) | R | 2026 | single | 1 | 7 | 2,290 | complete |
| Sarah McBride (`M001238`) | D | 2026 | index | 15 | 14 | 29,334 | complete |
| Scott Perry (`P000605`) | R | 2026 | single | 1 | 11 | 5,928 | complete |
| Mike Rounds (`R000605`) | R | 2026 | single | 1 | 12 | 3,755 | complete |
| Josh Riley (`R000622`) | D | 2026 | single | 1 | 23 | 22,336 | complete |
| Jeanne Shaheen (`S001181`) | D | 2020 | index | 13 | 12 | 30,309 | complete |
| Terri A. Sewell (`S001185`) | D | 2026 | index | 9 | 8 | 16,595 | complete |
| Lauren Underwood (`U000040`) | D | 2026 | index | 8 | 7 | 11,176 | complete |
| Juan Vargas (`V000130`) | D | 2026 | single | 1 | 7 | 1,867 | complete |
| Bruce Westerman (`W000821`) | R | 2026 | single | 1 | 4 | 2,968 | complete |
| George Whitesides (`W000830`) | D | 2026 | single | 1 | 13 | 8,691 | complete |
| Todd Young (`Y000064`) | R | 2022 | index | 11 | 10 | 7,804 | complete |

## Skipped: null in the source list

- Kathy Castor (`C001066`, D): campaign site has no issues page
- Neal P. Dunn (`D000628`, R): no campaign site found
- Bill Hagerty (`H000601`, R): campaign site has no issues page
- Mike Johnson (`J000299`, R): campaign site has no issues page
- Trent Kelly (`K000388`, R): campaign site has no issues page
- Betty McCollum (`M001143`, D): campaign site has no issues page
- Janice D. Schakowsky (`S001145`, D): campaign site has no issues page
- Tim Sheehy (`S001232`, R): campaign site has no issues page
- Ryan K. Zinke (`Z000018`, R): no campaign site found

## What this does not say

Every statement here is undated (`date_precision: undated`): a campaign page carries no date for its words, so none is stored, the export refuses it, and decision 7's newest-25 cap reaches it last. A skipped or blocked row is not a member with no positions.
