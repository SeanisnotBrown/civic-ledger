# Collector (a) — member press releases: the count report

Window **2023-01-03 to 2026-10-20** (owner decision 1). Source list: `data/config/statement-sources.yaml`, owner-maintained and read only. **No AI call, no archive capture, no spend.**

**38 rows collected, 1 refused, 1 with no press-release list at all.** 12375 releases in the window.

* Release bodies were pulled for every release counted below; **184 could not be read** and are listed in `data/raw/press/index.json` under `text_failures`. A release with no readable body is recorded as a failure, never as a statement with no words.

## Per member

| Member | Party | Releases | Text | Pages | Walk |
| --- | --- | --- | --- | --- | --- |
| Gus M. Bilirakis (B001257) | R | 274 | 272 | 29 | complete |
| Jim Costa (C001059) | D | 317 | 317 | 33 | complete |
| Kathy Castor (C001066) | D | 305 | 290 | 32 | complete |
| Angie Craig (C001119) | D | 378 | 378 | 39 | complete |
| Mark DeSaulnier (D000623) | D | 155 | 155 | 17 | complete |
| Neal P. Dunn (D000628) | R | 116 | 112 | 13 | complete |
| Sharice Davids (D000629) | D | 604 | 604 | 62 | complete |
| Mike Ezell (E000235) | R | 144 | 132 | 15 | complete |
| Bill Foster (F000454) | D | 192 | 177 | 21 | complete |
| Julie Fedorchak (F000482) | R | 276 | 275 | 28 | complete |
| Al Green (G000553) | D | 405 | 403 | 42 | complete |
| Bill Hagerty (H000601) | R | 578 | 578 | 117 | complete |
| Martin Heinrich (H001046) | D | 1413 | 1309 | 89 | complete |
| Jahana Hayes (H001081) | D | 252 | 252 | 27 | complete |
| Mark Harris (H001102) | R | 83 | 83 | 9 | complete |
| Mike Johnson (J000299) | R | 556 | 541 | 57 | complete |
| Mark Kelly (K000377) | D | 1071 | 1071 | 2 | complete |
| Trent Kelly (K000388) | R | 28 | 28 | 4 | complete |
| Mike Kennedy (K000403) | R | 69 | 68 | 7 | complete |
| Barry Loudermilk (L000583) | R | 101 | 101 | 12 | complete |
| Darin LaHood (L000585) | R | 229 | 229 | 24 | complete |
| Betty McCollum (M001143) | D | 305 | 304 | 32 | complete |
| Thomas Massie (M001184) | R | 53 | 52 | 7 | complete |
| John R. Moolenaar (M001194) | R | 324 | 324 | 34 | complete |
| Sarah McBride (M001238) | D | 170 | 170 | 17 | complete |
| Scott Perry (P000605) | R | 49 | 46 | 6 | complete |
| Mike Rounds (R000605) | R | 328 | 328 | 18 | complete |
| Josh Riley (R000622) | D | 101 | 101 | 6 | complete |
| Janice D. Schakowsky (S001145) | D | 304 | 304 | 32 | complete |
| Jeanne Shaheen (S001181) | D | 1157 | 1155 | 60 | complete |
| Terri A. Sewell (S001185) | D | 391 | 391 | 41 | complete |
| Tim Sheehy (S001232) | R | 96 | 96 | 9 | complete |
| Lauren Underwood (U000040) | D | 160 | 159 | 17 | complete |
| Juan Vargas (V000130) | D | 167 | 167 | 18 | complete |
| Bruce Westerman (W000821) | R | 116 | 116 | 13 | complete |
| George Whitesides (W000830) | D | 95 | 95 | 5 | complete |
| Todd Young (Y000064) | R | 816 | 816 | 3 | complete |
| Ryan K. Zinke (Z000018) | R | 197 | 194 | 20 | complete |

## Per party

| Party | Releases |
| --- | --- |
| D | 7942 |
| R | 4433 |

## Walks that did not reach the window's start

None: every walk reached the window's start.

## How page 2 was found, per row

`link` is the site's own Next or numbered link, which is what the walk follows. `page_url` is the URL GUESSED from the list URL, used only where the site publishes no such link — measured 2026-10-14, that guess is wrong on three of the four rows it was checked against, so a row sitting on it is a row whose deeper pages are not proven. `none` means page 2 was never asked for: the walk ended on page one.

| Member | Page 2 found by | Page 2 URL |
| --- | --- | --- |
| Gus M. Bilirakis (B001257) | `link` | <https://bilirakis.house.gov/media/press-releases?page=1> |
| Jim Costa (C001059) | `link` | <https://costa.house.gov/media/press-releases?page=1> |
| Kathy Castor (C001066) | `link` | <https://castor.house.gov/news/documentquery.aspx?DocumentTypeID=821&Page=2> |
| Angie Craig (C001119) | `link` | <https://craig.house.gov/media/press-releases?page=1> |
| Mark DeSaulnier (D000623) | `link` | <https://desaulnier.house.gov/media-center/press-releases?page=1> |
| Neal P. Dunn (D000628) | `link` | <https://dunn.house.gov/news/documentquery.aspx?DocumentTypeID=27&Page=2> |
| Sharice Davids (D000629) | `link` | <https://davids.house.gov/media/press-releases?page=1> |
| Mike Ezell (E000235) | `link` | <https://ezell.house.gov/news/documentquery.aspx?DocumentTypeID=27&Page=2> |
| Bill Foster (F000454) | `link` | <https://foster.house.gov/media/press-releases?page=1> |
| Julie Fedorchak (F000482) | `link` | <https://fedorchak.house.gov/media/press-releases?page=1> |
| Al Green (G000553) | `link` | <https://algreen.house.gov/media/press-releases?page=1> |
| Bill Hagerty (H000601) | `link` | <https://www.hagerty.senate.gov/press-releases/page/2/> |
| Martin Heinrich (H001046) | `link` | <https://www.heinrich.senate.gov/newsroom/press-releases?pagenum_rs=2> |
| Jahana Hayes (H001081) | `link` | <https://hayes.house.gov/press-releases?page=2> |
| Mark Harris (H001102) | `link` | <https://markharris.house.gov/media/press-releases?page=1> |
| Mike Johnson (J000299) | `link` | <https://mikejohnson.house.gov/news/documentquery.aspx?DocumentTypeID=27&Page=2> |
| Mark Kelly (K000377) | `sitemap` | <https://www.kelly.senate.gov/press_releases-sitemap.xml> |
| Trent Kelly (K000388) | `link` | <https://trentkelly.house.gov/newsroom/documentquery.aspx?DocumentTypeID=27&Page=2> |
| Mike Kennedy (K000403) | `link` | <https://mikekennedy.house.gov/media/press-releases?page=1> |
| Barry Loudermilk (L000583) | `link` | <https://loudermilk.house.gov/category/press-releases/page/2/?et_blog> |
| Darin LaHood (L000585) | `link` | <https://lahood.house.gov/press-releases?page=2> |
| Betty McCollum (M001143) | `link` | <https://mccollum.house.gov/media/press-releases?page=1> |
| Thomas Massie (M001184) | `link` | <https://massie.house.gov/news/documentquery.aspx?DocumentTypeID=2362&Page=2> |
| John R. Moolenaar (M001194) | `link` | <https://moolenaar.house.gov/media-center/press-releases?page=1> |
| Sarah McBride (M001238) | `link` | <https://mcbride.house.gov/media/press-releases?page=1> |
| Scott Perry (P000605) | `link` | <https://perry.house.gov/news/documentquery.aspx?DocumentTypeID=2608&Page=2> |
| Mike Rounds (R000605) | `link` | <https://www.rounds.senate.gov/newsroom/press-releases?pagenum_rs=2> |
| Josh Riley (R000622) | `link` | <https://riley.house.gov/news/page/2/?et_blog> |
| Janice D. Schakowsky (S001145) | `link` | <https://schakowsky.house.gov/media/press-releases?page=1> |
| Jeanne Shaheen (S001181) | `link` | <https://www.shaheen.senate.gov/news/press?pagenum_rs=2> |
| Terri A. Sewell (S001185) | `link` | <https://sewell.house.gov/press-releases?page=2> |
| Tim Sheehy (S001232) | `page_url` | <https://www.sheehy.senate.gov/newsroom/press-releases/page/2/> |
| Lauren Underwood (U000040) | `link` | <https://underwood.house.gov/media/press-releases?page=1> |
| Juan Vargas (V000130) | `link` | <https://vargas.house.gov/media/press-releases?page=1> |
| Bruce Westerman (W000821) | `link` | <https://westerman.house.gov/media-center/press-releases?page=1> |
| George Whitesides (W000830) | `link` | <https://whitesides.house.gov/category/press-releases/page/2/?et_blog> |
| Todd Young (Y000064) | `sitemap` | <https://www.young.senate.gov/press_releases-sitemap.xml> |
| Ryan K. Zinke (Z000018) | `link` | <https://zinke.house.gov/media/press-releases?page=1> |

## Release pages read for their dates

These rows print no date on the list page at all, so each release's own page was read to date it — the one fetch the list page does not already pay for. A page that could not be fetched, and a page with no date marker on it, are both recorded below as failures and NEITHER is kept as a release: an undated statement cannot be placed inside or outside the window.

| Member | Pages read for dates | Undatable |
| --- | --- | --- |
| Mark Kelly (K000377) | 1082 | 0 |
| Todd Young (Y000064) | 2133 | 0 |

## Date conflicts — two of the publisher's own dates disagree

Nothing below was resolved: the stored date is the one the list page or the permalink gave, and the release page's disagreeing date is reported rather than written. A page date outside the permalink's month, or a different day where the URL carried one, can mean the WRONG PAGE was attached to this title — which is a thing to check by eye, not to average.

* `C001119` — the release page says 2023-07-13, the list-page says 2023-07-27 — <https://craig.house.gov/media/press-releases/rep-angie-craig-asks-constituent-feedback-ahead-meetings-usps-eagan-and-prior>
* `D000629` — the release page says 2023-07-18, the list-page says 2023-11-10 — <https://davids.house.gov/media/press-releases/davids-bipartisan-bill-support-veteran-entrepreneurs-advances-out-committee>
* `D000629` — the release page says 2021-11-09, the list-page says 2024-11-15 — <https://davids.house.gov/media/press-releases/davids-celebrates-passage-bipartisan-infrastructure-bill-local-leaders>
* `D000629` — the release page says 2023-11-15, the list-page says 2026-01-13 — <https://davids.house.gov/media/press-releases/davids-celebrates-two-year-anniversary-bipartisan-infrastructure-law>
* `D000629` — the release page says 2024-05-31, the list-page says 2024-07-02 — <https://davids.house.gov/media/press-releases/davids-cleaver-announce-159-million-regional-law-enforcement-address-fentanyl>
* `D000629` — the release page says 2024-03-27, the list-page says 2024-04-15 — <https://davids.house.gov/media/press-releases/davids-hosts-usda-deputy-secretary-policymakers-discuss-supporting-kansas>
* `D000629` — the release page says 2022-08-12, the list-page says 2023-08-24 — <https://davids.house.gov/media/press-releases/davids-votes-lower-health-care-costs-create-clean-energy-jobs-reduce-deficit>
* `D000629` — the release page says 2022-09-22, the list-page says 2025-12-17 — <https://davids.house.gov/media/press-releases/passed-davids-bipartisan-bill-advance-new-aviation-technology-heads-president-s>
* `D000629` — the release page says 2023-06-20, the list-page says 2023-12-12 — <https://davids.house.gov/media/press-releases/reps-davids-barr-introduce-bipartisan-bill-address-impact-substance-abuse>
* `F000482` — the release page says 2025-05-22, the list-page says 2025-07-02 — <https://fedorchak.house.gov/media/press-releases/fedorchak-applauds-house-passage-historic-one-big-beautiful-bill>
* `F000482` — the release page says 2025-03-10, the list-page says 2025-05-20 — <https://fedorchak.house.gov/media/press-releases/fedorchak-issues-request-information-address-ais-growing-energy-demands>
* `F000482` — the release page says 2025-03-21, the list-page says 2026-03-05 — <https://fedorchak.house.gov/media/press-releases/north-dakota-delegation-reintroduces-legislation-empower-greater-development>
* `F000482` — the release page says 2025-04-10, the list-page says 2025-05-12 — <https://fedorchak.house.gov/media/press-releases/rep-fedorchak-introduces-bill-phase-out-intermittent-energy-subsidies>
* `G000553` — the release page says 2026-01-16, the list-page says 2026-02-07 — <https://algreen.house.gov/media/press-releases/congressman-al-greens-black-history-month-legislative-breakfast-meeting>
* `G000553` — the release page says 2026-08-17, the list-page says 2026-08-22 — <https://algreen.house.gov/media/press-releases/youre-invited-congressman-al-greens-5th-annual-slavery-remembrance-legislative>
* `H001046` — the release page says 2023-08-21, the list-page says 2025-08-15 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-staff-to-hold-mobile-office-hours-in-dona-ana-county>
* `H001046` — the release page says 2023-06-16, the list-page says 2026-06-19 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-juneteenth>
* `H001046` — the release page says 2015-05-22, the list-page says 2023-05-26 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-memorial-day>
* `H001046` — the release page says 2025-09-19, the list-page says 2025-10-01 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-trumps-government-shutdown>
* `H001046` — the release page says 2019-11-11, the list-page says 2024-11-11 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-veterans-day>
* `H001046` — the release page says 2024-01-18, the list-page says 2024-02-29 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-vote-to-keep-government-open>
* `R000605` — the release page says 2020-08-19, the list-page says 2023-06-14 — <https://www.rounds.senate.gov/newsroom/press-releases/nine-south-dakota-students-nominated-by-rounds-starting-at-us-service-academies>
* `R000622` — the list page says 2025-05-01, the permalink says 2025-04-29 — <https://riley.house.gov/2025/04/29/rep-riley-introduces-bipartisan-bill-crack-down-fentanyl-smuggling-border-and/>
* `R000622` — the list page says 2026-05-01, the permalink says 2026-04-27 — <https://riley.house.gov/2026/04/27/riley-votes-to-extend-broadband-network-for-first-responders/>
* `S001145` — the release page says 2024-05-15, the list-page says 2024-06-13 — <https://schakowsky.house.gov/media/press-releases/energy-and-commerce-leaders-hail-house-passage-bipartisan-ticket-act>
* `S001181` — the release page says 2020-01-22, the list-page says 2024-01-29 — <https://www.shaheen.senate.gov/news/press/shaheen-leads-bipartisan-legislation-to-hold-e-cigarette-companies-accountable-for-the-youth-vaping-crisis>
* `S001181` — the release page says 2021-01-07, the list-page says 2025-01-06 — <https://www.shaheen.senate.gov/news/press/shaheen-statement-on-congress-certification-of-presidential-election-results>
* `S001181` — the release page says 2022-03-01, the list-page says 2024-03-07 — <https://www.shaheen.senate.gov/news/press/shaheen-statement-on-president-bidens-state-of-the-union-address>
* `S001181` — the release page says 2017-01-20, the list-page says 2025-01-20 — <https://www.shaheen.senate.gov/news/press/shaheen-statement-on-the-inauguration-of-president-donald-trump>
* `U000040` — the release page says 2025-01-09, the list-page says 2026-01-07 — <https://underwood.house.gov/media/press-releases/underwood-and-shaheen-introduce-legislation-permanently-lower-health-care-0>
* `W000830` — the list page says 2026-05-07, the permalink says 2026-04-22 — <https://whitesides.house.gov/2026/04/22/reps-whitesides-houlahan-demand-pentagon-explain-cybersecurity-capability-gap-created-by-anthropic-supply-chain-designation/>

## URLs the release filter refused, and why

Each of these has the SHAPE of a release on its member's list and was taken out anyway, for the reason given. Nothing here is a silent drop: the owner decides what counts as a member's own statement, so a URL this collector removes from a statement list is printed where it can be disagreed with. A URL linked on every page of an archive appears once.

* `C001066` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://castor.house.gov/news/documentquery.aspx?DocumentTypeID=817>
* `C001066` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://castor.house.gov/news/documentquery.aspx?IssueID=111866>
* `C001066` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://castor.house.gov/news/documentquery.aspx?IssueID=118662>
* `E000235` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://ezell.house.gov/news/documentquery.aspx?IssueID=10109>
* `E000235` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://ezell.house.gov/news/documentquery.aspx?IssueID=10360>
* `E000235` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://ezell.house.gov/news/documentquery.aspx?IssueID=81>
* `J000299` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://mikejohnson.house.gov/news/documentquery.aspx?IssueID=14898>
* `J000299` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://mikejohnson.house.gov/news/documentquery.aspx?IssueID=14899>
* `M001184` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://massie.house.gov/news/documentquery.aspx?DocumentTypeID=2365>
* `M001184` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://massie.house.gov/news/documentquery.aspx?IssueID=112042>
* `M001184` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://massie.house.gov/news/documentquery.aspx?IssueID=112049>
* `M001184` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://massie.house.gov/news/documentquery.aspx?IssueID=112050>
* `M001184` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://massie.house.gov/news/documentquery.aspx?IssueID=112052>
* `M001184` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://massie.house.gov/news/documentquery.aspx?IssueID=59656>
* `P000605` — a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a release (a single release there is `documentsingle.aspx`) — <https://perry.house.gov/news/documentquery.aspx?IssueID=119133>
* `R000622` — a `newsletter-subscribe` path segment — a subscribe form, not a release — <https://riley.house.gov/news/newsletter-subscribe/>

## Refused, by id

The source list's own rule: collector (a) must refuse a row that still says `owner_checked: false` (fact 7, STATUS.md). These are listed so a refusal is never mistaken for a member who published nothing.

* `K000394` Andy Kim — owner_checked: false

## No press-release list exists, by id

**These are not a collection failure and are not counted as one anywhere in this report.** The owner looked, and the member's site publishes no press-release list at all — so there is nothing to collect, nothing to fix, and no reading of this report in which these rows are members who said nothing. Every URL that was tried is listed, so the finding can be checked rather than taken on trust, and so a site that adds a list later is recognised as a change rather than as a discovery.

* `M001222` Max L. Miller — site has no press-release list. Tried:
    * <https://maxmiller.house.gov/press-releases>
    * <https://maxmiller.house.gov/media/press-releases>
    * <https://maxmiller.house.gov/media>
    * <https://maxmiller.house.gov/news>

## Step 7 supplement — computed from `data/raw/press/index.json` (walk 7b, 2026-10-20)

Added by hand on 2026-10-22 from the index walk 7b wrote (`generated_at` 2026-10-20T18:37:49Z); nothing was re-walked, nothing was fetched and no AI was called. The generator does not write these sections, so a re-run of `statements-press` will drop them. The 2026-10-19 report and its own supplement are left as they were, as the record of the walk before the date fix and Young's sitemap.

### Coverage per pilot cell

| Cell | Rows collected / rows in cell | Releases | Not collected |
| --- | --- | --- | --- |
| D house | 16 / 16 | 4301 | — |
| D senate | 3 / 4 | 3641 | 1 refused |
| R house | 15 / 16 | 2615 | 1 no-list |
| R senate | 4 / 4 | 1818 | — |

`collected` means a COMPLETE stop (`window`, `exhausted`, `sitemap`). All 38 walked rows stopped that way. Against 10-19: R senate goes from 3/4 to 4/4 (Young, 20 → 816 releases), and the total goes from 11572 to 12375 (+803 = Young +796, Shaheen +6, Rounds +1; see the date-conflict split below for five of Shaheen's and Rounds's seven).

### Per row: pages, earliest date, stop reason, page 2, text failures

"Late start" flags every row whose earliest in-window release is after 2023-01-03. Most are not a collection gap: a `window` stop means the walk saw a release OLDER than the window and stopped, so the row is complete and simply published nothing on the first day(s); an `exhausted` stop at 2025-01-03 is a member who took office with the 119th Congress. The rows that look genuinely short are called out under the table. Text failures above 5% of a row's releases are flagged.

| Member | Releases | Pages | Earliest | Stop | Page 2 | Text failures | Flags |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Gus M. Bilirakis (B001257) | 274 | 29 | 2023-01-04 | `window` | `link` | 2 (0.7%) | late start |
| Jim Costa (C001059) | 317 | 33 | 2023-01-06 | `window` | `link` | 0 (0.0%) | late start |
| Kathy Castor (C001066) | 305 | 32 | 2023-01-05 | `window` | `link` | 15 (4.9%) | late start |
| Angie Craig (C001119) | 378 | 39 | 2023-01-05 | `window` | `link` | 0 (0.0%) | late start |
| Mark DeSaulnier (D000623) | 155 | 17 | 2023-01-11 | `window` | `link` | 0 (0.0%) | late start |
| Neal P. Dunn (D000628) | 116 | 13 | 2023-01-07 | `window` | `link` | 4 (3.4%) | late start |
| Sharice Davids (D000629) | 604 | 62 | 2023-01-04 | `window` | `link` | 0 (0.0%) | late start |
| Mike Ezell (E000235) | 144 | 15 | 2023-01-07 | `exhausted` | `link` | 12 (8.3%) | late start, **text >5%** |
| Bill Foster (F000454) | 192 | 21 | 2023-01-03 | `window` | `link` | 15 (7.8%) | **text >5%** |
| Julie Fedorchak (F000482) | 276 | 28 | 2025-01-03 | `exhausted` | `link` | 1 (0.4%) | late start |
| Al Green (G000553) | 405 | 42 | 2023-01-09 | `window` | `link` | 2 (0.5%) | late start |
| Bill Hagerty (H000601) | 578 | 117 | 2023-01-09 | `window` | `link` | 0 (0.0%) | late start |
| Martin Heinrich (H001046) | 1413 | 89 | 2023-01-05 | `window` | `link` | 106 (7.5%) | late start, **text >5%** |
| Jahana Hayes (H001081) | 252 | 27 | 2023-01-07 | `window` | `link` | 0 (0.0%) | late start |
| Mark Harris (H001102) | 83 | 9 | 2025-01-03 | `exhausted` | `link` | 0 (0.0%) | late start |
| Mike Johnson (J000299) | 556 | 57 | 2023-01-05 | `window` | `link` | 15 (2.7%) | late start |
| Mark Kelly (K000377) | 1071 | 2 | 2023-01-03 | `sitemap` | `sitemap` | 0 (0.0%) | — |
| Trent Kelly (K000388) | 28 | 4 | 2023-02-14 | `window` | `link` | 0 (0.0%) | late start |
| Mike Kennedy (K000403) | 69 | 7 | 2025-01-03 | `exhausted` | `link` | 1 (1.4%) | late start |
| Barry Loudermilk (L000583) | 101 | 12 | 2023-01-26 | `window` | `link` | 0 (0.0%) | late start |
| Darin LaHood (L000585) | 229 | 24 | 2023-01-07 | `window` | `link` | 0 (0.0%) | late start |
| Betty McCollum (M001143) | 305 | 32 | 2023-01-09 | `window` | `link` | 1 (0.3%) | late start |
| Thomas Massie (M001184) | 53 | 7 | 2023-01-12 | `window` | `link` | 1 (1.9%) | late start |
| John R. Moolenaar (M001194) | 324 | 34 | 2023-01-07 | `window` | `link` | 0 (0.0%) | late start |
| Sarah McBride (M001238) | 170 | 17 | 2025-01-03 | `exhausted` | `link` | 0 (0.0%) | late start |
| Scott Perry (P000605) | 49 | 6 | 2024-01-18 | `window` | `link` | 3 (6.1%) | late start, **text >5%** |
| Mike Rounds (R000605) | 328 | 18 | 2023-01-11 | `window` | `link` | 0 (0.0%) | late start |
| Josh Riley (R000622) | 101 | 6 | 2025-01-03 | `exhausted` | `link` | 0 (0.0%) | late start |
| Janice D. Schakowsky (S001145) | 304 | 32 | 2023-01-06 | `window` | `link` | 0 (0.0%) | late start |
| Jeanne Shaheen (S001181) | 1157 | 60 | 2023-01-04 | `window` | `link` | 2 (0.2%) | late start |
| Terri A. Sewell (S001185) | 391 | 41 | 2023-01-06 | `window` | `link` | 0 (0.0%) | late start |
| Tim Sheehy (S001232) | 96 | 9 | 2025-01-07 | `exhausted` | `page_url` | 0 (0.0%) | late start |
| Lauren Underwood (U000040) | 160 | 17 | 2023-01-06 | `window` | `link` | 1 (0.6%) | late start |
| Juan Vargas (V000130) | 167 | 18 | 2023-01-26 | `window` | `link` | 0 (0.0%) | late start |
| Bruce Westerman (W000821) | 116 | 13 | 2023-01-03 | `window` | `link` | 0 (0.0%) | — |
| George Whitesides (W000830) | 95 | 5 | 2025-01-03 | `exhausted` | `link` | 0 (0.0%) | late start |
| Todd Young (Y000064) | 816 | 3 | 2023-01-03 | `sitemap` | `sitemap` | 0 (0.0%) | — |
| Ryan K. Zinke (Z000018) | 197 | 20 | 2023-01-03 | `exhausted` | `link` | 3 (1.5%) | — |

**Todd Young (`Y000064`) is collected:** 816 releases, earliest **2023-01-03**, the window's first day. His 3 sitemaps list 2,138 URLs; 1,317 fall outside the window and 2,133 release pages were read for their dates (`<lastmod>` ignored, owner ruling 2026-10-19), with 0 undatable and 0 text failures. The 10-19 "severely under-collected" line for him is closed.

**Rows that look short, by eye — unchanged from 10-19:**

* `P000605` Scott Perry — stopped `window` after 6 pages, earliest in-window release 2024-01-18, none from 2023. Checked 2026-10-19: the gap is real, on his own list.
* `K000388` Trent Kelly — 28 releases in nearly four years, nothing between 2023-03-28 and 2024-10-25. Checked 2026-10-19: the gap is real, on his own list.
* `S001232` Tim Sheehy — complete (`exhausted`), but page 2 is still the GUESSED `page_url`, now the only row on it. His 96 releases from 2025-01-07 look plausible.

### The `MAX_PAGES = 200` guard

**No row was stopped by it.** The deepest walk is still Bill Hagerty (`H000601`) at 117 pages; the two sitemap rows read 2 and 3 sitemaps. The limit was not changed.

### Text failures per row

**184 entries, 182 releases.** `text_failures` holds 184 entries: 182 "no body text" (D 140, R 42) and 2 HTTPStatusError. The 2 HTTPStatusError entries are for two Heinrich releases that ALSO appear among the 182 as "no body text" (the fetch failed, and the release was then recorded again with an empty body), so **182 distinct releases** have no readable body: D 140, R 42. That matches the 182 empty press records in `data/raw/press/statements/` exactly, every one of them a recorded failure. The "184 could not be read" at the top of this report, and Heinrich's 106 in the table above, count those two releases twice; by release, Heinrich has 104 (7.4%). **The same entries, split and per-row counts as 10-19**: no row gained or lost a failure, and Young adds none. Per row, by entry:

* `H001046` Martin Heinrich — 106 (104 no body text, 2 HTTPStatusError)
* `C001066` Kathy Castor — 15 (15 no body text)
* `F000454` Bill Foster — 15 (15 no body text)
* `J000299` Mike Johnson — 15 (15 no body text)
* `E000235` Mike Ezell — 12 (12 no body text)
* `D000628` Neal P. Dunn — 4 (4 no body text)
* `P000605` Scott Perry — 3 (3 no body text)
* `Z000018` Ryan K. Zinke — 3 (3 no body text)
* `B001257` Gus M. Bilirakis — 2 (2 no body text)
* `G000553` Al Green — 2 (2 no body text)
* `S001181` Jeanne Shaheen — 2 (2 no body text)
* `F000482` Julie Fedorchak — 1 (1 no body text)
* `K000403` Mike Kennedy — 1 (1 no body text)
* `M001143` Betty McCollum — 1 (1 no body text)
* `M001184` Thomas Massie — 1 (1 no body text)
* `U000040` Lauren Underwood — 1 (1 no body text)

The two releases logged twice, once as HTTPStatusError and once as "no body text", both Heinrich's:

* `H001046` — HTTPStatusError — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-lujan-convene-air-force-leadership-to-discuss-future-investments-in-cannon-air-force-base-secure-commitment-to-long-term-success-of-cannon>
* `H001046` — HTTPStatusError — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-lujan-congratulate-xochitl-torres-small-on-confirmation-as-deputy-secretary-of-agriculture>

### Eastern-time date check (new for 7b)

Re-read offline from the cached release pages: each stored date against the same page read once on the US Eastern clock and once as plain UTC (the pre-fix reading).

* `K000377` Mark Kelly — 1071 releases, all dated from their own release pages. **76** read one day later in UTC than in Eastern time, and **all 1071 stored dates equal the Eastern reading**: the 76 have moved back a day, as measured on 10-19.
* `Y000064` Todd Young — 816 releases, all dated from their own release pages. 15 would have been a day late in UTC; all 816 stored dates equal the Eastern reading.
* `H000601` Bill Hagerty — 42 of his release pages read a day later in UTC. His stored dates come from his list page, and the 42 off-by-one conflicts they caused on 10-19 are gone.

### Date conflicts, split (31 total, none resolved)

On 10-19 there were 73: 10 different-year, 45 off-by-one, 18 other.

**A. Same URL, different year — 15.** The two dates are in different years and more than six months apart. Ten are the ten from 10-19. **Five are new, and all five are releases 10-19 did not count:** each release page carries a date BEFORE the window (2017 to 2022). On 10-19 the walk read 1,187 of Shaheen's and 355 of Rounds's release pages to date their anchors; in 7b it read none for dates, and every release on both rows carries its list-page date. That is consistent with these five having been dated by their release pages on 10-19 (and so falling outside the window), and by their list pages now (inside it). Four are the reused-URL pattern (an inauguration, an election certification, a State of the Union, a reintroduced bill). Kept and flagged, not resolved (decision 5), but the stored date may be the wrong year, and if it is, the release is not in the window at all.

* `D000629` — the release page says 2023-11-15, the list-page says 2026-01-13 — <https://davids.house.gov/media/press-releases/davids-celebrates-two-year-anniversary-bipartisan-infrastructure-law>
* `D000629` — the release page says 2022-09-22, the list-page says 2025-12-17 — <https://davids.house.gov/media/press-releases/passed-davids-bipartisan-bill-advance-new-aviation-technology-heads-president-s>
* `D000629` — the release page says 2021-11-09, the list-page says 2024-11-15 — <https://davids.house.gov/media/press-releases/davids-celebrates-passage-bipartisan-infrastructure-bill-local-leaders>
* `D000629` — the release page says 2022-08-12, the list-page says 2023-08-24 — <https://davids.house.gov/media/press-releases/davids-votes-lower-health-care-costs-create-clean-energy-jobs-reduce-deficit>
* `F000482` — the release page says 2025-03-21, the list-page says 2026-03-05 — <https://fedorchak.house.gov/media/press-releases/north-dakota-delegation-reintroduces-legislation-empower-greater-development>
* `H001046` — the release page says 2023-06-16, the list-page says 2026-06-19 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-juneteenth>
* `H001046` — the release page says 2023-08-21, the list-page says 2025-08-15 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-staff-to-hold-mobile-office-hours-in-dona-ana-county>
* `H001046` — the release page says 2019-11-11, the list-page says 2024-11-11 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-veterans-day>
* `H001046` — the release page says 2015-05-22, the list-page says 2023-05-26 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-memorial-day>
* `U000040` — the release page says 2025-01-09, the list-page says 2026-01-07 — <https://underwood.house.gov/media/press-releases/underwood-and-shaheen-introduce-legislation-permanently-lower-health-care-0>
* **new** `R000605` — the release page says 2020-08-19, the list-page says 2023-06-14 — <https://www.rounds.senate.gov/newsroom/press-releases/nine-south-dakota-students-nominated-by-rounds-starting-at-us-service-academies>
* **new** `S001181` — the release page says 2017-01-20, the list-page says 2025-01-20 — <https://www.shaheen.senate.gov/news/press/shaheen-statement-on-the-inauguration-of-president-donald-trump>
* **new** `S001181` — the release page says 2021-01-07, the list-page says 2025-01-06 — <https://www.shaheen.senate.gov/news/press/shaheen-statement-on-congress-certification-of-presidential-election-results>
* **new** `S001181` — the release page says 2022-03-01, the list-page says 2024-03-07 — <https://www.shaheen.senate.gov/news/press/shaheen-statement-on-president-bidens-state-of-the-union-address>
* **new** `S001181` — the release page says 2020-01-22, the list-page says 2024-01-29 — <https://www.shaheen.senate.gov/news/press/shaheen-leads-bipartisan-legislation-to-hold-e-cigarette-companies-accountable-for-the-youth-vaping-crisis>

**B. Off by exactly one day — 0.** All 45 from 10-19 (Hagerty 42, Sheehy 2, Shaheen 1) are gone: release-page timestamps are now read on the US Eastern clock.

**C. Everything else — 16.** Same year, 2 to 175 days apart: the 18 from 10-19 less Shaheen's two (release page 2023-09-14 against list page 2023-09-17), which are no longer reported.

* `C001119` — the release page says 2023-07-13, the list-page says 2023-07-27 — <https://craig.house.gov/media/press-releases/rep-angie-craig-asks-constituent-feedback-ahead-meetings-usps-eagan-and-prior>
* `D000629` — the release page says 2024-05-31, the list-page says 2024-07-02 — <https://davids.house.gov/media/press-releases/davids-cleaver-announce-159-million-regional-law-enforcement-address-fentanyl>
* `D000629` — the release page says 2024-03-27, the list-page says 2024-04-15 — <https://davids.house.gov/media/press-releases/davids-hosts-usda-deputy-secretary-policymakers-discuss-supporting-kansas>
* `D000629` — the release page says 2023-06-20, the list-page says 2023-12-12 — <https://davids.house.gov/media/press-releases/reps-davids-barr-introduce-bipartisan-bill-address-impact-substance-abuse>
* `D000629` — the release page says 2023-07-18, the list-page says 2023-11-10 — <https://davids.house.gov/media/press-releases/davids-bipartisan-bill-support-veteran-entrepreneurs-advances-out-committee>
* `F000482` — the release page says 2025-05-22, the list-page says 2025-07-02 — <https://fedorchak.house.gov/media/press-releases/fedorchak-applauds-house-passage-historic-one-big-beautiful-bill>
* `F000482` — the release page says 2025-03-10, the list-page says 2025-05-20 — <https://fedorchak.house.gov/media/press-releases/fedorchak-issues-request-information-address-ais-growing-energy-demands>
* `F000482` — the release page says 2025-04-10, the list-page says 2025-05-12 — <https://fedorchak.house.gov/media/press-releases/rep-fedorchak-introduces-bill-phase-out-intermittent-energy-subsidies>
* `G000553` — the release page says 2026-08-17, the list-page says 2026-08-22 — <https://algreen.house.gov/media/press-releases/youre-invited-congressman-al-greens-5th-annual-slavery-remembrance-legislative>
* `G000553` — the release page says 2026-01-16, the list-page says 2026-02-07 — <https://algreen.house.gov/media/press-releases/congressman-al-greens-black-history-month-legislative-breakfast-meeting>
* `H001046` — the release page says 2025-09-19, the list-page says 2025-10-01 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-trumps-government-shutdown>
* `H001046` — the release page says 2024-01-18, the list-page says 2024-02-29 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-vote-to-keep-government-open>
* `R000622` — the list page says 2026-05-01, the permalink says 2026-04-27 — <https://riley.house.gov/2026/04/27/riley-votes-to-extend-broadband-network-for-first-responders/>
* `R000622` — the list page says 2025-05-01, the permalink says 2025-04-29 — <https://riley.house.gov/2025/04/29/rep-riley-introduces-bipartisan-bill-crack-down-fentanyl-smuggling-border-and/>
* `S001145` — the release page says 2024-05-15, the list-page says 2024-06-13 — <https://schakowsky.house.gov/media/press-releases/energy-and-commerce-leaders-hail-house-passage-bipartisan-ticket-act>
* `W000830` — the list page says 2026-05-07, the permalink says 2026-04-22 — <https://whitesides.house.gov/2026/04/22/reps-whitesides-houlahan-demand-pentagon-explain-cybersecurity-capability-gap-created-by-anthropic-supply-chain-designation/>
