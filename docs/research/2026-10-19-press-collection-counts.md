# Collector (a) — member press releases: the count report

Window **2023-01-03 to 2026-10-19** (owner decision 1). Source list: `data/config/statement-sources.yaml`, owner-maintained and read only. **No AI call, no archive capture, no spend.**

**38 rows collected, 1 refused, 1 with no press-release list at all.** 11572 releases in the window.

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
| Mike Rounds (R000605) | R | 327 | 327 | 18 | complete |
| Josh Riley (R000622) | D | 101 | 101 | 6 | complete |
| Janice D. Schakowsky (S001145) | D | 304 | 304 | 32 | complete |
| Jeanne Shaheen (S001181) | D | 1151 | 1149 | 60 | complete |
| Terri A. Sewell (S001185) | D | 391 | 391 | 41 | complete |
| Tim Sheehy (S001232) | R | 96 | 96 | 9 | complete |
| Lauren Underwood (U000040) | D | 160 | 159 | 17 | complete |
| Juan Vargas (V000130) | D | 167 | 167 | 18 | complete |
| Bruce Westerman (W000821) | R | 116 | 116 | 13 | complete |
| George Whitesides (W000830) | D | 95 | 95 | 5 | complete |
| Todd Young (Y000064) | R | 20 | 20 | 1 | **INCOMPLETE — single-page** |
| Ryan K. Zinke (Z000018) | R | 197 | 194 | 20 | complete |

## Per party

| Party | Releases |
| --- | --- |
| D | 7936 |
| R | 3636 |

## Walks that did not reach the window's start

These members' counts are a floor, not a total. `window` (the walk reached 2023) and `exhausted` (the pager ran off the end of an archive that begins inside the window) both mean COMPLETE and are not listed here. Everything below stopped early, so the member is under-collected.

* `Y000064` Todd Young — **single-page**: one page only, and no page 2 — a short archive and a JavaScript 'load more' are indistinguishable to a plain GET

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
| Todd Young (Y000064) | `page_url` | <https://www.young.senate.gov/newsroom/press-releases/page/2/> |
| Ryan K. Zinke (Z000018) | `link` | <https://zinke.house.gov/media/press-releases?page=1> |

## Release pages read for their dates

These rows print no date on the list page at all, so each release's own page was read to date it — the one fetch the list page does not already pay for. A page that could not be fetched, and a page with no date marker on it, are both recorded below as failures and NEITHER is kept as a release: an undated statement cannot be placed inside or outside the window.

| Member | Pages read for dates | Undatable |
| --- | --- | --- |
| Mark Kelly (K000377) | 1082 | 0 |
| Mike Rounds (R000605) | 355 | 0 |
| Jeanne Shaheen (S001181) | 1187 | 0 |
| Todd Young (Y000064) | 1 | 1 |

Every undatable release, with the reason:

* `Y000064` — HTTPStatusError — <https://www.young.senate.gov/newsroom/press-releases/{{{data.link}}}>

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
* `H000601` — the release page says 2023-01-28, the list-page says 2023-01-27 — <https://www.hagerty.senate.gov/press-releases/2023/01/27/hagerty-statement-on-release-of-tyre-nichols-footage/>
* `H000601` — the release page says 2023-02-08, the list-page says 2023-02-07 — <https://www.hagerty.senate.gov/press-releases/2023/02/07/hagerty-releases-video-statement-in-response-to-bidens-state-of-the-union-address-2/>
* `H000601` — the release page says 2023-03-09, the list-page says 2023-03-08 — <https://www.hagerty.senate.gov/press-releases/2023/03/08/hagerty-resolution-to-block-d-c-s-irresponsible-crime-bill-passes-senate/>
* `H000601` — the release page says 2023-03-09, the list-page says 2023-03-08 — <https://www.hagerty.senate.gov/press-releases/2023/03/08/hagerty-the-senate-will-not-stand-by-while-our-nations-capital-becomes-a-safe-haven-for-violent-criminals/>
* `H000601` — the release page says 2023-03-21, the list-page says 2023-03-20 — <https://www.hagerty.senate.gov/press-releases/2023/03/20/hagerty-resolution-to-block-d-c-s-irresponsible-crime-bill-signed-into-law/>
* `H000601` — the release page says 2023-03-23, the list-page says 2023-03-22 — <https://www.hagerty.senate.gov/press-releases/2023/03/22/for-a-fourth-time-hagerty-presses-yellen-for-update-on-the-promised-investigation-of-taxpayer-information-leak/>
* `H000601` — the release page says 2023-04-25, the list-page says 2023-04-24 — <https://www.hagerty.senate.gov/press-releases/2023/04/24/icymi-hagerty-joins-fox-and-friends-to-discuss-hunter-biden-sudan-fentanyl-legislation/>
* `H000601` — the release page says 2023-05-11, the list-page says 2023-05-10 — <https://www.hagerty.senate.gov/press-releases/2023/05/10/with-title-42-expiration-hours-away-senate-democrats-block-hagertys-legislation-to-stop-fentanyl-border-crossings-for-the-fourth-time/>
* `H000601` — the release page says 2023-05-30, the list-page says 2023-05-29 — <https://www.hagerty.senate.gov/press-releases/2023/05/29/icymi-hagerty-joins-maria-bartiromos-wall-street-on-fox-business-to-discuss-the-biden-administrations-weakness-toward-communist-china/>
* `H000601` — the release page says 2023-06-20, the list-page says 2023-06-19 — <https://www.hagerty.senate.gov/press-releases/2023/06/19/icymi-hagerty-joins-kudlow-on-fox-business-to-discuss-the-biden-administrations-weakness-toward-communist-china-and-irans-terror-regime/>
* `H000601` — the release page says 2023-06-30, the list-page says 2023-06-29 — <https://www.hagerty.senate.gov/press-releases/2023/06/29/hagerty-mccaul-u-s-tech-found-in-ccp-spy-balloon-heightens-our-concerns/>
* `H000601` — the release page says 2023-07-12, the list-page says 2023-07-11 — <https://www.hagerty.senate.gov/press-releases/2023/07/11/hagerty-kelly-colleagues-introduce-bipartisan-bicameral-bill-to-remove-bureaucratic-barriers-to-american-production-of-semiconductors/>
* `H000601` — the release page says 2023-07-13, the list-page says 2023-07-12 — <https://www.hagerty.senate.gov/press-releases/2023/07/12/hagerty-on-biden-admin-collusion-with-big-tech-theyre-fighting-to-continue-censoring-americans/>
* `H000601` — the release page says 2023-10-17, the list-page says 2023-10-16 — <https://www.hagerty.senate.gov/press-releases/2023/10/16/icymi-hagerty-joins-americas-newsroom-on-fox-news-to-discuss-iran-backed-hamas-attack-on-israel/>
* `H000601` — the release page says 2023-10-18, the list-page says 2023-10-17 — <https://www.hagerty.senate.gov/press-releases/2023/10/17/despite-irans-clear-role-in-hamas-terrorist-attack-on-israel-senate-democrats-block-hagertys-legislation-to-prevent-sanction-relief-on-iran/>
* `H000601` — the release page says 2023-11-08, the list-page says 2023-11-07 — <https://www.hagerty.senate.gov/press-releases/2023/11/07/hagerty-risch-barrasso-ricketts-cruz-introduce-legislation-to-impose-sanctions-related-to-chinese-spy-base-in-cuba/>
* `H000601` — the release page says 2023-11-16, the list-page says 2023-11-15 — <https://www.hagerty.senate.gov/press-releases/2023/11/15/hagerty-prevails-in-effort-to-ban-chinese-harvesting-of-americans-dna/>
* `H000601` — the release page says 2024-02-13, the list-page says 2024-02-12 — <https://www.hagerty.senate.gov/press-releases/2024/02/12/hagerty-peters-gallagher-krishnamoorthi-call-on-biden-admin-to-investigate-chinese-biotech-company-wuxi-apptec/>
* `H000601` — the release page says 2024-02-22, the list-page says 2024-02-21 — <https://www.hagerty.senate.gov/press-releases/2024/02/21/hagerty-discusses-border-crisis-and-its-effects-after-traveling-to-south-texas-with-tennessee-sheriffs-and-mayors/>
* `H000601` — the release page says 2024-03-08, the list-page says 2024-03-07 — <https://www.hagerty.senate.gov/press-releases/2024/03/07/hagerty-releases-video-statement-in-response-to-bidens-state-of-the-union-address-3/>
* `H000601` — the release page says 2024-03-09, the list-page says 2024-03-08 — <https://www.hagerty.senate.gov/press-releases/2024/03/08/hagerty-statement-on-senate-democrats-siding-with-illegal-immigrants-over-american-citizens-on-voting-power/>
* `H000601` — the release page says 2024-03-13, the list-page says 2024-03-12 — <https://www.hagerty.senate.gov/press-releases/2024/03/12/icymi-hagerty-joins-the-evening-edit-on-fox-business-to-discuss-democrats-blocking-his-amendment-to-bar-the-census-from-counting-illegal-aliens/>
* `H000601` — the release page says 2024-03-28, the list-page says 2024-03-27 — <https://www.hagerty.senate.gov/press-releases/2024/03/27/icymi-hagerty-joins-americas-newsroom-on-fox-news-to-discuss-democrats-blocking-his-amendment-to-prohibit-the-biden-admin-from-flying-illegal-aliens-into-the-country/>
* `H000601` — the release page says 2024-04-04, the list-page says 2024-04-03 — <https://www.hagerty.senate.gov/press-releases/2024/04/03/icymi-hagerty-joins-kudlow-on-fox-business-to-discuss-bidens-failed-trade-policies/>
* `H000601` — the release page says 2024-04-04, the list-page says 2024-04-03 — <https://www.hagerty.senate.gov/press-releases/2024/04/03/icymi-hagerty-joins-mornings-with-maria-on-fox-business-to-discuss-bidens-weakness-toward-china-democrats-siding-with-illegal-aliens-over-american-citizens-nyse-visit/>
* `H000601` — the release page says 2024-04-11, the list-page says 2024-04-10 — <https://www.hagerty.senate.gov/press-releases/2024/04/10/hagerty-kaine-introduce-legislation-to-strengthen-modernize-u-s-philippines-military-alliance/>
* `H000601` — the release page says 2024-05-14, the list-page says 2024-05-13 — <https://www.hagerty.senate.gov/press-releases/2024/05/13/icymi-hagerty-joins-kudlow-on-fox-business-to-discuss-trump-trial-bidens-appeasement-of-americas-adversaries/>
* `H000601` — the release page says 2024-06-05, the list-page says 2024-06-04 — <https://www.hagerty.senate.gov/press-releases/2024/06/04/fbi-director-wray-wont-say-to-hagerty-whether-five-different-democrat-prosecutions-of-trump-during-election-are-coincidence-or-coordinated-election-interference/>
* `H000601` — the release page says 2024-07-30, the list-page says 2024-07-29 — <https://www.hagerty.senate.gov/press-releases/2024/07/29/icymi-hagerty-joins-the-evening-edit-on-fox-business-to-discuss-bitcoin-nashville-2024-conference/>
* `H000601` — the release page says 2024-09-19, the list-page says 2024-09-18 — <https://www.hagerty.senate.gov/press-releases/2024/09/18/hagerty-statement-on-biden-harris-administrations-cover-up-of-special-envoy-rob-malleys-iran-collusion-scandal/>
* `H000601` — the release page says 2024-11-19, the list-page says 2024-11-18 — <https://www.hagerty.senate.gov/press-releases/2024/11/18/hagerty-calls-out-doj-for-politically-motivated-potentially-unlawful-unionization-effort/>
* `H000601` — the release page says 2024-12-17, the list-page says 2024-12-16 — <https://www.hagerty.senate.gov/press-releases/2024/12/16/icymi-hagerty-joins-your-world-with-neil-cavuto-on-fox-news-to-discuss-his-support-for-trumps-cabinet-nominees/>
* `H000601` — the release page says 2024-12-18, the list-page says 2024-12-17 — <https://www.hagerty.senate.gov/press-releases/2024/12/17/hagerty-introduces-legislation-to-stop-biden-admins-effort-to-sell-border-wall-parts/>
* `H000601` — the release page says 2024-12-21, the list-page says 2024-12-20 — <https://www.hagerty.senate.gov/press-releases/2024/12/20/icymi-hagerty-joins-mornings-with-maria-on-fox-business-to-discuss-government-funding-process/>
* `H000601` — the release page says 2024-12-21, the list-page says 2024-12-20 — <https://www.hagerty.senate.gov/press-releases/2024/12/20/on-senate-floor-hagerty-calls-out-u-s-trade-rep-for-siding-with-mexico-in-its-seizure-of-vulcan-materials-property/>
* `H000601` — the release page says 2025-01-22, the list-page says 2025-01-21 — <https://www.hagerty.senate.gov/press-releases/2025/01/21/hagerty-stefanik-is-right-person-for-u-s-ambassador-to-un/>
* `H000601` — the release page says 2025-02-10, the list-page says 2025-02-09 — <https://www.hagerty.senate.gov/press-releases/2025/02/09/icymi-hagerty-joins-face-the-nation-on-cbs-to-discuss-trumps-government-reform/>
* `H000601` — the release page says 2025-02-20, the list-page says 2025-02-19 — <https://www.hagerty.senate.gov/press-releases/2025/02/19/hagerty-blunt-rochester-introduce-bipartisan-legislation-to-modernize-credit-union-boards/>
* `H000601` — the release page says 2025-03-05, the list-page says 2025-03-04 — <https://www.hagerty.senate.gov/press-releases/2025/03/04/hagerty-releases-video-statement-in-response-to-trumps-remarks-to-a-joint-session-of-congress/>
* `H000601` — the release page says 2025-03-11, the list-page says 2025-03-10 — <https://www.hagerty.senate.gov/press-releases/2025/03/10/hagerty-leads-colleagues-in-reintroducing-updated-legislation-on-stablecoins/>
* `H000601` — the release page says 2025-04-24, the list-page says 2025-04-23 — <https://www.hagerty.senate.gov/press-releases/2025/04/23/hagerty-kaine-urge-mexican-government-to-cease-unfair-treatment-of-u-s-based-vulcan-materials-company/>
* `H000601` — the release page says 2025-05-12, the list-page says 2025-05-11 — <https://www.hagerty.senate.gov/press-releases/2025/05/11/icymi-hagerty-joins-sunday-morning-futures-on-fox-news-to-discuss-trade-negotiations-debt-ceiling-spending-cuts/>
* `H001046` — the release page says 2023-08-21, the list-page says 2025-08-15 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-staff-to-hold-mobile-office-hours-in-dona-ana-county>
* `H001046` — the release page says 2023-06-16, the list-page says 2026-06-19 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-juneteenth>
* `H001046` — the release page says 2015-05-22, the list-page says 2023-05-26 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-memorial-day>
* `H001046` — the release page says 2025-09-19, the list-page says 2025-10-01 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-trumps-government-shutdown>
* `H001046` — the release page says 2019-11-11, the list-page says 2024-11-11 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-veterans-day>
* `H001046` — the release page says 2024-01-18, the list-page says 2024-02-29 — <https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-statement-on-vote-to-keep-government-open>
* `R000622` — the list page says 2025-05-01, the permalink says 2025-04-29 — <https://riley.house.gov/2025/04/29/rep-riley-introduces-bipartisan-bill-crack-down-fentanyl-smuggling-border-and/>
* `R000622` — the list page says 2026-05-01, the permalink says 2026-04-27 — <https://riley.house.gov/2026/04/27/riley-votes-to-extend-broadband-network-for-first-responders/>
* `S001145` — the release page says 2024-05-15, the list-page says 2024-06-13 — <https://schakowsky.house.gov/media/press-releases/energy-and-commerce-leaders-hail-house-passage-bipartisan-ticket-act>
* `S001181` — the release page says 2023-10-05, the list-page says 2023-10-04 — <https://www.shaheen.senate.gov/news/press/shaheen-collins-laud-passage-of-bipartisan-resolution-to-designate-energy-efficiency-day>
* `S001181` — the release page says 2023-09-14, the list-page says 2023-09-17 — <https://www.shaheen.senate.gov/news/press/shaheen-reintroduces-constitutional-amendment-to-overturn-citizens-united-ruling-get-dark-money-out-of-our-elections>
* `S001181` — the release page says 2023-09-14, the list-page says 2023-09-17 — <https://www.shaheen.senate.gov/news/press/shaheen-statement-on-2022-portsmouth-naval-shipyard-economic-impact-report>
* `S001232` — the release page says 2025-11-14, the list-page says 2025-11-13 — <https://www.sheehy.senate.gov/news/press-releases/icymi-how-one-montana-senator-managed-to-move-the-trump-white-house-twice/>
* `S001232` — the release page says 2025-11-11, the list-page says 2025-11-10 — <https://www.sheehy.senate.gov/news/press-releases/sheehy-statement-on-vote-to-end-schumer-shutdown/>
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

## Step 7 supplement — computed from `data/raw/press/index.json` (2026-10-19)

Added by hand from the index this run wrote; nothing was re-walked and no AI was called. The generator does not write these sections, so a re-run of `statements-press` will drop them.

### Coverage per pilot cell

| Cell | Rows collected / rows in cell | Releases | Not collected |
| --- | --- | --- | --- |
| D house | 16 / 16 | 4301 | — |
| D senate | 3 / 4 | 3635 | 1 refused |
| R house | 15 / 16 | 2615 | 1 no-list |
| R senate | 3 / 4 | 1021 | 1 single-page |

`collected` means a COMPLETE stop (`window`, `exhausted`, `sitemap`). `single-page` (Young) is counted as releases but NOT as collected.

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
| Mike Rounds (R000605) | 327 | 18 | 2023-01-11 | `window` | `link` | 0 (0.0%) | late start |
| Josh Riley (R000622) | 101 | 6 | 2025-01-03 | `exhausted` | `link` | 0 (0.0%) | late start |
| Janice D. Schakowsky (S001145) | 304 | 32 | 2023-01-06 | `window` | `link` | 0 (0.0%) | late start |
| Jeanne Shaheen (S001181) | 1151 | 60 | 2023-01-04 | `window` | `link` | 2 (0.2%) | late start |
| Terri A. Sewell (S001185) | 391 | 41 | 2023-01-06 | `window` | `link` | 0 (0.0%) | late start |
| Tim Sheehy (S001232) | 96 | 9 | 2025-01-07 | `exhausted` | `page_url` | 0 (0.0%) | late start |
| Lauren Underwood (U000040) | 160 | 17 | 2023-01-06 | `window` | `link` | 1 (0.6%) | late start |
| Juan Vargas (V000130) | 167 | 18 | 2023-01-26 | `window` | `link` | 0 (0.0%) | late start |
| Bruce Westerman (W000821) | 116 | 13 | 2023-01-03 | `window` | `link` | 0 (0.0%) | — |
| George Whitesides (W000830) | 95 | 5 | 2025-01-03 | `exhausted` | `link` | 0 (0.0%) | late start |
| Todd Young (Y000064) | 20 | 1 | 2026-09-16 | `single-page` | `page_url` | 0 (0.0%) | late start |
| Ryan K. Zinke (Z000018) | 197 | 20 | 2023-01-03 | `exhausted` | `link` | 3 (1.5%) | — |

**Rows that look short, by eye — to check, not resolved:**

* `Y000064` Todd Young — `single-page`: 20 releases, all 2026-09-16 to 2026-10-09. The one undatable link is `{{{data.link}}}`, an unrendered template placeholder, so the list is built by JavaScript and a plain GET sees one page. **Severely under-collected.**
* `P000605` Scott Perry — stopped `window` after 6 pages, yet his earliest in-window release is 2024-01-18 and there are none from 2023. Either the list (`DocumentTypeID=2608`) has a real 2023 gap, or it is not his full press-release list.
* `K000388` Trent Kelly — 28 releases in nearly four years, with nothing between 2023-03-28 and 2024-10-25. Low volume is plausible for him (decision 3), but the gap is worth one look at his site.
* `S001232` Tim Sheehy — complete (`exhausted`), but page 2 was the GUESSED `page_url`, which the 2026-10-14 check found wrong on three of four rows. His 96 releases from 2025-01-07 look plausible.

### The `MAX_PAGES = 200` guard

**No row was stopped by it.** The deepest walk was Bill Hagerty (`H000601`) at 117 pages. The limit was not changed.

### Text failures per row

184 in total: 182 no body text, 2 HTTPStatusError. Per row (all listed in the table above):

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

### Date conflicts, split (73 total, none resolved)

**A. Same URL, different year — 10.** The two dates are in different years and more than six months apart. Some are the reused-URL pattern (an annual statement whose page is rewritten in place: Juneteenth, Veterans Day, Memorial Day); others look like a list page showing a later re-post or update date over an older release (Davids, Fedorchak, Underwood). Either way the stored date may be the wrong year.

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

**B. Off by exactly one day — 45** (H000601 42, S001181 1, S001232 2). The release page is always one day LATER than the list page or the permalink, which carries the date in its own path for Hagerty. That is the signature of a page timestamp read in UTC for an evening Eastern-time post, not a wrong page. Each is listed in the section above.

**C. Everything else — 18.** Same year, 2 to 175 days apart.

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
* `S001181` — the release page says 2023-09-14, the list-page says 2023-09-17 — <https://www.shaheen.senate.gov/news/press/shaheen-statement-on-2022-portsmouth-naval-shipyard-economic-impact-report>
* `S001181` — the release page says 2023-09-14, the list-page says 2023-09-17 — <https://www.shaheen.senate.gov/news/press/shaheen-reintroduces-constitutional-amendment-to-overturn-citizens-united-ruling-get-dark-money-out-of-our-elections>
* `W000830` — the list page says 2026-05-07, the permalink says 2026-04-22 — <https://whitesides.house.gov/2026/04/22/reps-whitesides-houlahan-demand-pentagon-explain-cybersecurity-capability-gap-created-by-anthropic-supply-chain-designation/>
