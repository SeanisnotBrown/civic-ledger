# Why the triage gate passes fewer Republican Record statements (STATUS flag 4)

2026-10-23. Read-only analysis of cached data. **No AI was called and no network request was
made.** Nothing was changed in any prompt, the pre-filter, any verdict, `ingest/`,
`data/config/` or `tests/`.

**The verdicts studied come from the STUB prompt `v1-stub`, which was never evaluated.** They
say what that stub did, not what the v1 prompt (now in `ai.yaml`) will do.

**Section 3 quotes 20 statements the stub rejected**, as the overnight task asked (copilot
for the owner, 2026-10-23); texts in the held-out labeling set are excluded, so nothing here
reveals a verdict on a row the owner is still labeling. The project otherwise keeps
per-statement model answers out of the public repository (`data/raw/` only; see
`2a9c6c7fa`), so the owner may prefer section 3 moved to `data/raw/analysis/`.

## What was read

| File | Size / lines |
| --- | --- |
| `data/raw/triage/v1-stub.jsonl` (verdicts) | 6,474,683 bytes; 14,766 lines; 14,757 distinct texts (9 texts re-asked; the last line wins, as in `load_ledger`) |
| `data/raw/crec/statements/*.json` (Record, 40 files) | 23,581,012 bytes |
| `data/raw/press/statements/*.json` (press, 39 files) | 48,380,639 bytes |
| `data/config/statement-pilot.yaml` (party, chamber) | 3,083 bytes |
| `origin/p3-labeling-set:docs/labeling/2026-10-22-eval-set.csv` | 60 rows (column `text_sha256` only used) |

Method: the same join as `ingest/triage_run.py` (`run()` → `queue` → `tally`). All 17,012
collected records go through `prefilter.run_prefilter`; the 14,810 AI-eligible survivors are
joined to the ledger by `fingerprint` (sha256 of the kept segments joined by a blank line).
"Section" is the Record's `granule_class` (HOUSE / SENATE / EXTENSIONS; no other value occurs);
"sub-class" is `sub_granule_class`. Length = characters of the text the gate read. Party and
chamber come from the pilot file. Counts are per statement, as in the published report.
Script (not tracked): `data/raw/analysis/triage_party_gap.py`; outputs beside it
(`triage_party_gap.json`, `triage_party_gap.rows.jsonl`).

## 1. Headline numbers reproduced

| Source | D passed / judged | D rate | R passed / judged | R rate | Gap (pts) |
| --- | --- | --- | --- | --- | --- |
| Congressional Record | 1,456 / 1,745 | 83.4% | 865 / 1,184 | 73.1% | 10.3 |
| Press releases | 6,301 / 7,607 | 82.8% | 3,469 / 4,271 | 81.2% | 1.6 |
| Both | 7,757 / 9,352 | 82.9% | 4,334 / 5,455 | 79.5% | 3.4 |

These match STATUS flag 4 and `2026-10-22-triage-run.md` exactly (14,807 judged, 12,091
passed; 3 statements have no verdict: 1 D Record, 1 R Record, 1 R press). Counted once per
distinct text instead, Record is D 1,456/1,733 = 84.0% vs R 865/1,176 = 73.6% (12 D and 8 R
Record texts appear under two statements); the gap is the same.

By chamber: Record House D 77.3% (592/766) vs R 75.1% (637/848); **Record Senate D 88.3%
(864/979) vs R 67.9% (228/336)**. Press House D 77.6% vs R 79.3%; press Senate D 89.2% vs R
83.8%. The gap is a Record problem, and mostly a Senate-member problem.

## 2. Where the Record gap sits

### 2a. Section (what part of the Record the entry is in)

| Section | D passed / n | D rate | R passed / n | R rate | Share of D's Record | Share of R's Record |
| --- | --- | --- | --- | --- | --- | --- |
| House floor | 491 / 603 | 81.4% | 631 / 762 | 82.8% | 35% | 64% |
| Senate floor | 855 / 969 | 88.2% | 228 / 336 | 67.9% | 56% | 28% |
| Extensions of Remarks | 110 / 173 | 63.6% | 6 / 86 | 7.0% | 10% | 7% |

On the House floor the two parties pass at the same rate. (Andy Kim's 8 House-section entries
pre-date his Senate term; they sit in D's House row.)

### 2b. The one big mix difference: Senate amendment texts

41% of D's Record (716 entries) is Senate "Text of Senate Amendment" filings (sub-class
`SAMENDMENTTEXTIND`); for R it is 14% (165). The gate passes these at the same rate for both
parties: **D 680/716 = 95.0%, R 155/165 = 93.9%**. Shaheen, Heinrich and Kelly file many.
Step-by-step:

| Slice of the Record | D | R | Gap (pts) |
| --- | --- | --- | --- |
| All | 1,456/1,745 = 83.4% | 865/1,184 = 73.1% | 10.3 |
| Less Senate amendment texts | 776/1,029 = 75.4% | 710/1,019 = 69.7% | 5.7 |
| Less amendment texts and Extensions (House floor + other Senate floor) | 666/856 = 77.8% | 704/933 = 75.5% | 2.3 |

What remains after that: Extensions of Remarks (2c) and other Senate floor speech (2d).

### 2c. Extensions of Remarks: two members decide it

| | D | R |
| --- | --- | --- |
| All Extensions | 110/173 = 63.6% | 6/86 = 7.0% |
| Dominant member | McCollum 91/98 = 92.9% (57% of D's Extensions) | Perry 0/39 = 0% (45% of R's) |
| Without that member | 19/75 = 25.3% | 6/47 = 12.8% |

McCollum's Extensions are mostly statements on bills ("I rise today in opposition to H.R.
4795…"). Perry's are honorifics ("HONORING COLONEL…", "CURRICULUM VITAE FOR…", "MRS. BETTY
ALFORD"). Extensions whose title carries no honorific word: D 102/113 vs R 4/31; reading R's
31 titles, nearly all are still tributes, welcomes, personal explanations or Mike Johnson's
annual Bundestag-exchange announcement.

### 2d. Other Senate floor speech (amendment texts removed)

| | D | R |
| --- | --- | --- |
| All | 175/253 = 69.2% | 73/171 = 42.7% |
| Sub-class TRIBUTE TO | 0/2 | 0/31 (Rounds has 24 of them) |
| Under 500 chars | 3/51 = 5.9% | 0/29 = 0% |
| 500–1,499 chars | 23/33 = 69.7% | 9/44 = 20.5% |
| 1,500+ chars | 149/169 = 88.2% | 64/98 = 65.3% |
| By member | Kim 40/43, Shaheen 65/80, Kelly 37/69, Heinrich 33/61 | Hagerty 28/56, Young 25/49, Sheehy 8/15, Rounds 12/51 |

Read by hand, R's 34 rejects of 1,500+ characters here are mostly tributes and memorials
(Young's Hoosier-history speeches, often filed under "LEGISLATIVE SESSION" or "Executive
Session"), nomination speeches for a friend (Hagerty), and committee-meeting requests. D's 20
are the same kinds (tributes, committee requests, nomination speeches such as Kelly and Kim on
Hegseth), plus a few that read as policy (a Kelly defense provision, a Heinrich appropriations
objection, Shaheen on a national-emergency resolution). Nominations sub-class: D 9/14 pass
(Shaheen 4/7, Heinrich 2/2, Kelly 2/3, Kim 1/2), R 0/5 (all Hagerty); too few to read much into.

### 2e. Length

| Length (chars) | D passed / n | D rate | R passed / n | R rate |
| --- | --- | --- | --- | --- |
| < 500 | 34 / 117 | 29.1% | 1 / 61 | 1.6% |
| 500–1,499 | 482 / 563 | 85.6% | 138 / 243 | 56.8% |
| 1,500–3,999 | 531 / 628 | 84.6% | 280 / 396 | 70.7% |
| 4,000+ | 409 / 437 | 93.6% | 446 / 484 | 92.1% |

Short D entries pass more because they are amendment texts: 29 of D's 34 passes under 500
characters are amendment filings. Section × length (D / R): Extensions 1,500–3,999 62.4% / 3.5%; Senate
500–1,499 93.0% / 50.0%; Senate < 500 39.5% / 0%; House cells within 7 points everywhere
(e.g. 4,000+ 92.5% / 94.4%).

### 2f. Ceremonial sub-classes and title words

| Measure | D | R |
| --- | --- | --- |
| Entries in an honorific sub-class (HONORING, RECOGNIZING, TRIBUTE TO, CELEBRATING, COMMEMORATING, CONGRATULATIONS, COMMENDING, IN MEMORY OF, RETIREMENT) | 115 (6.6% of Record), 30 pass = 26.1% | 133 (11.2%), 16 pass = 12.0% |
| Title has an honorific word (TRIBUTE, HONORING, RECOGNIZING, ANNIVERSARY, LEGACY …) | 33/119 = 27.7% | 22/147 = 15.0% |
| Title has no such word | 1,423/1,626 = 87.5% | 843/1,037 = 81.3% |

R's Record is about twice as honorific by these crude markers, and the markers miss many (see
2c, 2d).

### 2g. Members (Record entries, passed / judged)

| D member | n | Pass | R member | n | Pass |
| --- | --- | --- | --- | --- | --- |
| Shaheen (S) | 367 | 92.6% | Westerman | 237 | 91.1% |
| Heinrich (S) | 263 | 86.7% | Perry | 118 | 57.6% |
| M. Kelly (S) | 199 | 77.4% | Hagerty (S) | 112 | 74.1% |
| McCollum | 161 | 93.8% | Rounds (S) | 110 | 60.9% |
| Kim (S) | 150 | 94.7% | Young (S) | 82 | 65.9% |
| Green | 143 | 68.5% | Bilirakis | 78 | 87.2% |
| Castor | 79 | 74.7% | Massie | 52 | 84.6% |
| DeSaulnier | 64 | 73.4% | Harris | 48 | 72.9% |
| Sewell | 51 | 86.3% | Kennedy | 46 | 63.0% |
| Costa | 47 | 70.2% | Miller | 46 | 67.4% |
| Foster | 41 | 80.5% | Johnson | 45 | 55.6% |
| McBride | 26 | 80.8% | LaHood | 34 | 67.6% |
| Craig | 25 | 80.0% | Sheehy (S) | 32 | 75.0% |
| Hayes | 25 | 84.0% | Fedorchak | 30 | 90.0% |
| Davids | 22 | 50.0% | Ezell | 26 | 80.8% |
| Schakowsky | 20 | 55.0% | Zinke | 24 | 50.0% |
| Underwood | 17 | 76.5% | Dunn | 18 | 66.7% |
| Vargas | 17 | 76.5% | Moolenaar | 17 | 82.4% |
| Whitesides | 16 | 68.8% | T. Kelly | 16 | 50.0% |
| Riley | 12 | 50.0% | Loudermilk | 13 | 30.8% |

Dominance: five D members (four senators plus McCollum) are 65% of D's Record (1,140/1,745);
D senators are 56% of D's Record entries, R senators 28%. Westerman alone is 20% of R's.
Leave-one-out: without Shaheen D is 81.0%; without Westerman R is 68.5%. Unweighted mean of
member pass rates: D 76.0% vs R 68.7% (20 members each).

### 2h. Composition check (reweighting)

"R at D's mix" = R's own pass rate in each cell, weighted by how D's entries spread over the
cells (and the reverse). Cells one party lacks are left out (count shown).

| Cells | R at D's mix (actual R 73.1%) | D at R's mix (actual D 83.4%) |
| --- | --- | --- |
| Section | 67.0% | 82.1% |
| Length bucket | 67.0% | 85.6% |
| Section × length | 62.5% | 84.8% |
| Section × length × honorific title word | 69.8% | 82.2% (1 left out) |
| Section × sub-class | 75.6% (21 left out) | 77.5% (15 left out) |
| Section × sub-class × length | 74.4% (73 left out) | 81.8% (55 left out) |

Read plainly: by section and length alone, R's mix is *favourable* (more long House floor
speech), so reweighting makes R look worse, not better. Only sub-class (which isolates
amendment texts and some honorifics) moves R up, closing about 2.5 of the 10.3 points. **The
fields on the records do not capture "this is a tribute" well**: Perry's "CURRICULUM VITAE
FOR…" and Young's memorials under "LEGISLATIVE SESSION" look like ordinary entries to every
field. So the measurable mix explains little, while reading the rejects (2c, 2d, section 3)
suggests content mix explains much more. That second part is a reading, not a measurement.

## 3. Ten R and ten D Record rejects, drawn at random

Method (reproducible): for each party, take the Record statements the stub rejected, keep one
per distinct text, sort by (member id, date, granule id, text sha256), and **remove every text
whose `text_sha256` is in the owner's held-out labeling set** (removed 2 R and 2 D; pools 311 →
309 R, 277 → 275 D), so nothing here reveals a machine verdict on a row the owner is still
labeling. Then one `random.Random(20261023)`: `rng.sample(R pool, 10)`, then
`rng.sample(D pool, 10)`. Text = first 400 characters, whitespace collapsed. Flag 3's three
named examples (Al Green, McCollum/Thompson, Ezell) are press releases, outside this Record
analysis, and are not quoted.

### Republican Record rejects (drawn first)

R1. **Thomas Massie** (M001184), 2024-05-08, House, 6,752 chars, "RAISING A QUESTION OF THE PRIVILEGES OF THE HOUSE"
   > Mr. MASSIE. I object. Mr. MASSIE. Mr. Speaker, on that I demand the yeas and nays. The yeas and nays were ordered. This will be a 5-minute vote. The vote was taken by electronic device, and there were--yeas 359, nays 43, answered ``present'' 7, not voting 21, as follows: [Roll No. 188] YEAS--359 Adams Aderholt Aguilar Alford Allen Allred Amo Amodei Armstrong Arrington Auchincloss Babin Bacon Baird

R2. **John R. Moolenaar** (M001194), 2024-11-20, House, 1,105 chars, "AFFIRMING THE NATURE AND IMPORTANCE OF THE SUPPORT OF THE UNITED STATES FOR THE "
   > Mr. MOOLENAAR. Mr. Speaker, I thank the gentleman for yielding. Mr. Speaker, I join my Michigan colleague, Representative Slotkin, in support of H. Res. 554. This resolution is an important bipartisan affirmation of our support of religious and ethnic minorities in Iraq who experience violent persecution for their religious beliefs. Chaldean Christians are a religious minority in Iraq, and they ha

R3. **Mike Kennedy** (K000403), 2026-05-21, House, 778 chars, "SPIRIT OF DECENCY"
   > Mr. KENNEDY of Utah. Mr. Speaker, with all politics aside, I think we can agree that despite war and other terrible situations, there are still good things in this world--things like courage, things like sacrifice, and fighting spirit. The decency people manage to hold onto when everything gives every reason not to is commendable. A family member of mine told me about a friend of theirs named Teod

R4. **Todd Young** (Y000064), 2023-11-01, Senate, 11,369 chars, "UNANIMOUS CONSENT REQUESTS--EXECUTIVE CALENDAR"
   > Mr. YOUNG. Mr. President, I thank the President for the recognition. Let me begin with the obvious because I think Senator Graham did a great job of laying out what is at stake. He offered multiple arguments for why these amazing patriots who dedicated their professional lives to defending our safety, our security, our way of life should be promoted and should be promoted this evening. But a diffe

R5. **Scott Perry** (P000605), 2024-10-04, Extensions, 3,682 chars, "HONORING COLONEL TIMOTHY EARL BOOK"
   > Mr. PERRY. Mr. Speaker, I'm honored and humbled to recognize the distinguished career and tireless service of Colonel (Col.) Timothy Earl Book, United States Air Force, upon the auspicious occasion of his retirement after 30 years of selfless and loyal service to our Nation. Col. Book's legacy--most recently as Assistant Professor and Director of Strategic Management Systems at the United States A

R6. **Darin LaHood** (L000585), 2026-06-08, Extensions, 2,004 chars, "RECOGNIZING AND HONORING MAJOR GENERAL DANIEL R. McDONOUGH"
   > Mr. LaHOOD. Mr. Speaker, today, I recognize and honor the extraordinary service of Major General Daniel R. McDonough, whose distinguished career has had a lasting impact on Peoria, Illinois, and the United States of America. General McDonough devoted nearly four decades to the United States Air Force and the Illinois Air National Guard, building a legacy of leadership, professionalism, and commitm

R7. **Todd Young** (Y000064), 2025-11-20, Senate, 9,455 chars, "Trump appointees win again. Eight of the ten least partisan judges were nominate"
   > Mr. YOUNG. Mr. President, on the campus of Indiana University, a tablet placed on the floor of the student union pays tribute to the men and women who served in the Civil War. Over 80 years ago, in March 1942, three young Hoosiers stood over that marker. They raised their right hands, and they joined those ranks. When the oath began, they were college students in the last days of childhood. When i

R8. **Scott Perry** (P000605), 2025-01-31, Extensions, 2,122 chars, "RECOGNIZING SERGEANT HAROLD PRESSEL"
   > Mr. PERRY. Mr. Speaker, I'm honored to recognize Sergeant (SGT) Harold Pressel, U.S. Army Air Corps, on the auspicious occasion of his 101st Birthday on February 3, 2025. SGT Pressel honorably served alongside the ``Greatest Generation'' in WWII as a machine gunner on the B-24 Liberator, during which he earned--among myriad awards and decorations--the Purple Heart for his actions and wounds in com

R9. **Neal P. Dunn** (D000628), 2024-09-11, House, 300 chars, "ADJOURNMENT"
   > Mr. DUNN of Florida. Mr. Speaker, I move that the House do now adjourn. The motion was agreed to; accordingly (at 7 o'clock and 56 minutes p.m.), under its previous order, the House adjourned until tomorrow, Thursday, September 12, 2024, at 9 a.m. ____________________

R10. **Mike Rounds** (R000605), 2023-11-14, Senate, 743 chars, "TRIBUTE TO NOAH McNAUGHTON"
   > Mr. ROUNDS. Mr. President, today I recognize Noah McNaughton, an intern in my Washington, DC, office, for all the hard work he has done on behalf of my office and the State of South Dakota. Mr. McNaughton is a graduate of Lyman High School in Presho, SD. Currently, he is attending Dakota State University, where he studies cyber leadership and intelligence. Mr. McNaughton is a dedicated and diligen

### Democratic Record rejects (drawn second)

D1. **Mark DeSaulnier** (D000623), 2023-02-14, Extensions, 2,206 chars, "HONORING THE LIFE AND SERVICE OF JANET ABELSON"
   > Mr. DeSAULNIER. Mr. Speaker, I rise today, alongside Congressman John Garamendi, to recognize the life and service of former Mayor of El Cerrito, Janet Abelson. Throughout her life, Janet was a fierce advocate for marginalized communities. Janet was a resident of El Cerrito beginning in 1970 and was first elected to the El Cerrito City Council in 1999. She served as mayor in 2002, 2006, 2010, 2014

D2. **Betty McCollum** (M001143), 2025-06-24, House, 1,610 chars, "CONDEMNING THE ATTACKS ON MINNESOTA LAWMAKERS IN BROOKLYN PARK AND CHAMPLIN, MIN"
   > Ms. McCOLLUM. Mr. Speaker, I rise in full support of this resolution, and I thank Congresswoman Morrison on behalf of the entire Minnesota delegation for bringing us together. We must stand united to condemn the assassination of Minnesota Speaker Emerita Melissa Hortman and her husband, Mark, and the attempted murder of Senator John Hoffman and his wife, Yvette. Political violence targeted these t

D3. **Al Green** (G000553), 2025-06-27, House, 8,375 chars, "CELEBRATING LGBTQIA+ COMMUNITY"
   > Mr. GREEN of Texas. Mr. Speaker, and still I rise. I say ``and still I rise'' because I have been censured, but I would like to assure people that I have not been silenced; censured but not silenced. I rise today, Mr. Speaker, proud to say that I am an ally of the LGBTQIA+ community, an ally. I rise as an ally, Mr. Speaker, to acknowledge that H. Res. 550, the original LGBTQIA+ Pride Month resolut

D4. **Mark Kelly** (K000377), 2023-07-13, Senate, 1,112 chars, "Text of Senate Amendment 783"
   > SA 783. Mr. KELLY submitted an amendment intended to be proposed by him to the bill S. 2226, to authorize appropriations for fiscal year 2024 for military activities of the Department of Defense, for military construction, and for defense activities of the Department of Energy, to prescribe military personnel strengths for such fiscal year, and for other purposes; which was ordered to lie on the t

D5. **Mark Kelly** (K000377), 2025-07-23, Senate, 1,551 chars, "Text of Senate Amendment 2978"
   > SA 2978. Mr. KELLY (for himself and Mr. Sullivan) submitted an amendment intended to be proposed by him to the bill S. 2296, to authorize appropriations for fiscal year 2026 for military activities of the Department of Defense, for military construction, and for defense activities of the Department of Energy, to prescribe military personnel strengths for such fiscal year, and for other purposes; w

D6. **Mark Kelly** (K000377), 2023-02-28, Senate, 1,972 chars, "AUTHORITY FOR COMMITTEES TO MEET"
   > Mr. KELLY. Madam President, I have seven requests for committees to meet during today's session of the Senate. They have the approval of the Majority and Minority Leaders. Pursuant to rule XXVI, paragraph 5(a), of the Standing Rules of the Senate, the following committees are authorized to meet during today's session of the Senate: COMMITTEE ON ARMED SERVICES The Committee on Armed Services is aut

D7. **Martin Heinrich** (H001046), 2024-03-07, Senate, 240 chars, "PRIVILEGES OF THE FLOOR"
   > Mr. HEINRICH. Madam President, I ask unanimous consent that Devon Gorbey, Wasem Gawish, Max Katz, Cynthia Bailey, Cliff Ho, Will Murray, Jon Yap, who are all fellows in my office, be granted privileges to the floor until January 2, 2025.

D8. **Mark Kelly** (K000377), 2025-08-01, Senate, 2,169 chars, "Text of Senate Amendment 3521"
   > SA 3521. Mr. KELLY (for himself and Mr. Gallego) submitted an amendment intended to be proposed by him to the bill S. 2296, to authorize appropriations for fiscal year 2026 for military activities of the Department of Defense, for military construction, and for defense activities of the Department of Energy, to prescribe military personnel strengths for such fiscal year, and for other purposes; wh

D9. **Kathy Castor** (C001066), 2024-03-05, Extensions, 3,640 chars, "RECOGNIZING TAMPA BAY'S TRAILBLAZER DR. CYNTHIA JOHNSON, IN HONOR OF BLACK HISTO"
   > Ms. CASTOR of Florida. Mr. Speaker, I rise today during Black History Month to celebrate a true public servant, Dr. Cynthia Johnson. Her commitment to service in the community began at an early age while she accompanied her mother on weekly deliveries for Meals on Wheels and participated in other community service endeavors. Dr. Johnson developed a compassionate determination to make a positive im

D10. **Betty McCollum** (M001143), 2025-09-02, Extensions, 176 chars, "MOURNING THE TRAGIC SHOOTING AT ANNUNCIATION CATHOLIC CHURCH IN MINNEAPOLIS, MIN"
   > Ms. McCOLLUM. Mr. Speaker, I would like to include in the Record the following statement mourning the tragic shooting at Annunciation Catholic Church in Minneapolis, Minnesota.

Tally of the sample: R = 4 honorifics (Perry ×2, LaHood, Rounds intern), 2 procedural (Massie
roll call, Dunn adjournment), 1 Young speech on held-up military promotions (R4), 1 Young
speech that opens with a long historical story (R7), 1 human-interest floor speech (Kennedy), 1 support for a House resolution on Iraqi minorities
(Moolenaar). D = 3 Kelly amendment texts (the rare 5% of amendment texts rejected), 2
procedural (Heinrich floor privileges, Kelly committee meetings), 2 honorifics (DeSaulnier,
Castor), 1 one-line "include in the Record" (McCollum), 2 resolution floor speeches (McCollum
condemning political violence; Green on a Pride resolution). Both samples hold a few rejects
a reader might call substantive (Moolenaar, Young R4, McCollum D2, Green D3, the Kelly
amendments); that is flag 3's question (is the stub too strict?), and it appears on both sides.

## 4. Conclusion, in plain language

**Mostly the source material, with a small part that cannot be settled from this data.**

- Where the two parties' Record entries are the same kind of thing, the gate treats them the
  same: House floor speech 81.4% vs 82.8%; Senate amendment texts 95.0% vs 93.9%; press
  releases 82.8% vs 81.2%.
- About half the gap (10.3 → 5.7 points) is that D's Record is 41% Senate amendment filings,
  which nearly always pass, against 14% for R. That is about what the members file, not the
  gate.
- Most of the rest sits in two places dominated by a few members: Extensions of Remarks
  (McCollum's bill statements vs Perry's 39 honorifics), and Senate floor speech that is not
  amendment text, where R's entries are largely tributes (Rounds, Young, Sheehy) and nomination
  speeches. Remove amendment texts and Extensions and the gap is 2.3 points.
- **Limits.** (1) The "tribute" reading comes from titles and reading rejects, not from a
  labeled measurement; the formal reweighting on record fields does not close the gap, because
  those fields miss most tributes. (2) A residual remains in non-ceremonial Senate speech
  (D 68/86 vs R 19/31; small numbers, heavy in Todd Young's story-first speeches). Whether the
  stub judges those unfairly or they simply are not policy statements needs a person to label
  them. (3) This is the stub prompt; v1 may behave differently. (4) The 60-row held-out set has
  only 12 Record rows (3 per cell), too few to settle a Record-only question.

## 5. Options for the owner (none chosen; decision 4: an uneven filter stops for owner review)

- **Leave as is; rely on the 60-row v1 measurement** → fastest; it cannot settle a Record-only
  gap (12 Record rows).
- **Hand-label a small Record-only sample, stratified by the cells above** (e.g. Senate
  non-amendment speech and Extensions, both parties) → settles the residual; costs owner time.
- **Re-run this breakdown on v1's verdicts once a v1 triage run exists** → shows whether the
  pattern survives the real prompt; needs an AI run the owner approves.
- **Add a pre-filter rule for honorific Record sub-classes (TRIBUTE TO, HONORING, RECOGNIZING)**
  → a filter change needing ratification; it would also drop the D and R honorifics the stub
  passed (30 D, 16 R), and misses honorifics filed under other sub-classes.
- **Report Record and press pass rates separately, and Extensions apart from floor speech** →
  no model change; the published numbers show where a gap comes from.
