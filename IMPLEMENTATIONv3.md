# IMPLEMENTATIONv3.md — Civic Ledger build spec

Adopted 2026-10-07. Read `MISSION.md` first. This file is the only spec.
Older specs and plans are archived under `docs/archive/` and are not read
before work. Where this file and the code disagree, the code is the fact and
this file gets corrected, with a line in `STATUS.md`.

**How to use it:** find the current phase in `STATUS.md` → read that phase in
§5 → do its tasks → prove its acceptance → update `STATUS.md` → commit.

---

## §1 Ground rules (owner-ratified 2026-10-07)

| # | Rule | Consequence |
|---|---|---|
| 0 | **Never publish something false or falsely framed.** A true number in a false frame is false. Site copy that describes the system counts: copy flips in the same commit as the feature that makes it true. | Outranks every other rule. It is what lets the site call bad, bad. |
| 1 | **Ask the owner when unsure, in plain non-technical language.** Short questions, each option's consequence in one line, grouped so he answers in one pass. Always required for anything evaluative: what counts as good or poor, where a cutoff sits, how a grade is worded. | Builders never author a political judgment. |
| 2 | **Credentials and account setup are the owner's.** The builder stubs the step, lists the click in `STATUS.md` under "Owed by a human", and moves on. | No phase stalls silently on a dashboard click. |
| 3 | **One phase at a time.** A phase's acceptance must pass before the next starts. | No wandering. |
| 4 | **Raw API responses are cached to disk before parsing. Never hammer a government API.** Re-parse from `data/raw/` when the cached payload already has what is needed. | Free keys stay free; re-runs are free. |
| 5 | **Evaluative constants are ratified before they publish.** Every threshold, weight, grade cutoff, and grade label follows propose → owner picks → commit to `data/config/thresholds.yaml` with the reason and the date. | Nothing judgmental ships from an unratified number. |
| 6 | **The site states facts, never motive.** A grade says what was measured ("voted against 6 of 9 stated priorities"), never why ("doesn't care"). Benefit-of-the-doubt context is worded as fact (§4.5). The banned-words check is the mechanical edge of this rule. | Verdicts stay defensible. |
| 7 | **AI-written text is labeled and human-approved before it publishes** (§4.6). | Nothing wrong ships; readers are never misled about authorship. |
| 8 | **The site may collect and read the user data its features need.** The privacy page states plainly what is collected and how it is used. It makes no promises; it describes. | Features are never blocked by a privacy rule; the page is never false. |
| 9 | **Before every push run both gates:** `uv run ruff check .` and the full pytest line with `CI=true GITHUB_ACTIONS=true` (recorded in `STATUS.md`), then the site build and its `test:*` scripts. | A green local run is not evidence CI is green. |
| 10 | **Secrets come from `.env`.** Never hardcoded, never committed. | — |
| 11 | **Commit at every passing acceptance** with message `P<N>: <what>`. | History is readable. |
| 12 | **Update `STATUS.md` before ending any session.** Keep it under 50 lines; replace, do not append. | The next session starts cold in one minute. |
| 13 | **Ship partial value early.** A live, correct, incomplete site beats a complete unbuilt one. | The tiebreaker for what to build first. |

Environment facts (not rules): dev is Windows 11, CI is Ubuntu; stdout stays
ASCII; commands live in `pyproject.toml` and `site/package.json`.

**Rules removed on 2026-10-07 (do not reinstate):** the no-AI-in-the-publishing-path
rule and its CI guard; every rule that limited collecting user data; the
"never sell your data" promise (the owner withdrew the promise itself, not
just the sentence); the requirement to read the old progress and decision logs.

---

## §2 Decisions ratified 2026-10-07

Each row is the owner's choice. A builder applies it; a builder does not reopen it.

| Topic | Decision |
|---|---|
| Verdict wording | **Factual count.** "Voted against 6 of 9 stated priorities." No labels, no character words. |
| Left/right dot graph | **A vote is placed by which party's majority the member sided with:** with the Democratic majority only, with the Republican majority only, with both (bipartisan), or against both. Computed from the roll call's party totals. No outside score, no AI. |
| Grade categories | **Final five:** Consistency, Attendance, Effectiveness, Bipartisanship, Responsiveness. |
| Default weights | **Consistency 40 · Bipartisanship 20 · Attendance 15 · Effectiveness 15 · Responsiveness 10.** Readers can slide them. |
| Consistency timing | **Held until Phase 6** (benefit of the doubt) so no member is marked down for a compromise. Until then the overall grade is computed from the other four categories with the weights rescaled to 100, and the page says so. |
| Founding values kept | **Never publish something false or falsely framed** (rule 0). **Ship partial value early** (rule 13). |
| Grade cutoffs | **Fixed bars per category**, proposed by the builder from the real distribution, picked by the owner (rule 5). A member's grade never moves because of other members. |
| Contradiction vs compromise | A vote against a stated priority **counts as a contradiction unless the bill also contains something the member has a prior public statement against.** Then it is a compromise: shown with that evidence, not counted. |
| Odds of passage | **Historical rate by stage** ("of bills that reached this step, X% became law"), computed from the bill timelines, labeled as an estimate. Members' public stances adjust it once statements exist. |
| AI content | **Labeled ("AI summary, reviewed") and human-approved in the review dashboard before publishing.** |
| AI model | **A current Claude model, chosen per task by the builder, named in one config file (`data/config/ai.yaml`) with the prompt text versioned beside it.** |
| Outreach sender | **Automated, from a `civicledger.net` address, signed as the site.** Owner approves the template once. |
| Non-response window | **14 days.** |
| Statement sources (first release) | **All four:** official press releases (member .gov sites), floor speeches (Congressional Record), campaign issue pages from the most recent run, official social accounts. |
| Snapshots | **Every statement is archived** (Internet Archive capture) when collected. A statement whose capture dies is hidden until recaptured. |
| Anti-echo tools | **All four, in this order:** top-3 agree / top-3 disagree across the aisle → laddered quiz → "Challenge my stance" → periodic drift check-in. |
| Earlier-scope features | **Keep:** PAC donation timeline beside votes; bill diff viewer. **Cut for now:** sample ballot builder; net-worth / portfolio tracking. |
| Fact-check methodology | **Its own phase after accounts and alerts** (Phase 9). |
| Request a state | **Yes, in the accounts/alerts phase** as one more subscription type. |
| Phase order | **As listed in §5.** |
| Homepage entry point | **"Find your representatives" by state first**; address lookup later. |
| The "97% never got a floor vote" headline | **Keep, moved down into the stats area.** |
| Motive rule | **Kept.** Benefit-of-the-doubt is worded as fact: "This bill also contained X. [Name] publicly opposed X on [date]." |
| Ground rules kept | Ask in plain language; human tasks stay the owner's; acceptance before next phase; raw cache first. |
| CI checks kept | Banned words; symmetry; grade-label guard; lint + full tests + build before push. |
| Never-sell | **Promise withdrawn.** The privacy page describes what is collected and how it is used, nothing more. |
| HUMAN-TASKS file | **Archived.** Live items moved to `STATUS.md`. |
| Homepage order (2026-10-07) | **Intro -> In Congress -> the representative finder -> statistics.** The finder is one dropdown, states alphabetical by name. The intro's third line ("Find your representatives below.") is not shipped - it would point past the Congress band. |
| "In Congress" order (2026-10-07) | **One ranked list, consequence then contested** - not equal-weight buckets: (1) became law, (2) failed on the floor, (3) passed on a recorded roll call, closest tally first, (4) passed with no recorded vote, (5) placed on a calendar. Within a tier, newest first. Every key comes from the official record; **nothing is ordered by topic.** Shown to the reader on `/congress`. |
| Timeline page size (2026-10-07) | **50 rows per page as the reader sees it**, carried as 50-row chunks inside 300-row URLs with page numbers running across the whole record. 50 rows per URL would be 23,259 member pages and 35,580 files, past the 20,000 free-plan limit; the owner chose this over moving to Workers Paid now. |
| "In Congress" order, revised (2026-10-07, review 2) | **Recorded roll calls lead, then what became law.** (1) failed on a recorded roll call, (2) passed on a recorded roll call, closest tally first, (3) became law, (4) failed with no roll call in the record, (5) passed with no roll call in the record, (6) placed on a calendar. The owner gave the choice as "drop 'most consequential' from the copy OR put recorded roll-call votes above 'became law'" and left the pick to the builder; the builder picked the reorder, because a recorded vote is the only kind of action that puts members on the record by name. "Most consequential" is gone from the copy either way. Subject to the owner's reversal. |
| A tally may only be published as a measure's margin when the ROLL CALL RESOLVED THE MEASURE (2026-10-07) | A roll call joined to a passage or failure line must itself be a vote on the measure - passage, suspension, concurrence, a conference report, a veto override, or agreeing to a resolution - and never an amendment or a procedural motion on the same bill on the same day. Enforced by `resolvesMeasure()` in `site/src/lib/motions.ts`. Before the rule, s4668-119's passage line carried the 96-1 tally of an amendment voted the same day. |
| Procedural votes carry a plain-English meaning line (2026-10-07) | Every vote row states what a Yea and a Nay on that motion did, from a FIXED hand-written table (`site/src/lib/motions.ts`), first match wins, outer motion first, no line at all for a question the table does not cover, both sides always, and no threshold the record does not carry. Published in full at `/methods#motions` and gated by `npm run test:motions` (100% of 3,519 roll calls carry a line). |
| Homepage, revised (2026-10-07, review 2) | Hero fills the first screen with the state picker inside it; a row of three entry links (look up a politician, how grades work, where the data comes from); "In Congress" shows the top five compact, with "See everything"; the 97% fact is the only statistic left - the attendance distribution moved to `/federal`, above the grid each band filters. Nav label "Federal" -> "Members"; the ROUTE stays `/federal`. |
| Bill titles clamp to two lines (2026-10-07) | A title longer than two lines gets a "Show the full title" control, added by script only where the text actually overflows. Nothing is clamped server-side: with JavaScript off every title renders in full. |
| Homepage headline (2026-10-07, review 2) | **"Know what the people you vote for actually do."** The owner was offered four options and picked this one (option B). The full Q-A sentence - "Nobody should have to become an expert, or spend their life tracking politicians, to know what the people they vote for actually do." - sits immediately beneath it as the support line, set larger than the rest of the body copy, so his original wording is still published in full. One constant at the top of `site/src/pages/index.astro`. |
| The motion table, ratified in full (2026-10-07) | The owner read every line of `site/src/lib/motions.ts` and approved the table, amending one row: tabling now reads **"Tabling disposes of the matter without a vote on its merits - in practice, it kills it. A Yea kills it; a Nay keeps it alive."** The table's own rules are binding: fixed and hand-written (nothing generated, nothing from a model), first match wins, OUTER motion first, both sides always, no line at all for a question the table does not cover, no threshold the record does not carry (hence no number on cloture, which is three fifths for legislation and a simple majority for nominations), and what the motion does rather than why it was moved. 22 entries; 100% of 3,519 roll calls carry a line; gated by `npm run test:motions`; published for readers at `/methods#motions`, rendered from the module itself so the explanation cannot drift from the lines. |
| Per-position short lines on every vote row (2026-10-07) | Above the motion's explanation, each row states what THAT member did in one short clause - "Voted to kill it", "Voted to send it back to committee" - from a (yea, nay) pair written beside the motion's own entry, so the two cannot drift apart. Approved as shown. **Three deliberate silences:** a point of order (sustaining one runs in whichever direction the chair ruled, so no clause states what the member wanted done with the measure), the chamber's own proceedings (a Speaker election records a surname, not a yea/nay), and the positions "present" and absent (neither takes a direction; those rows already carry the member's stated reason or the exact string "No explanation on record."). |
| Which amendment a vote was on (2026-10-07) | House amendment rows render the **Clerk's own `amendment-author` line verbatim** ("Lawler of New York Part B Amendment No. 114"), because it already names both the sponsor and the amendment's printed number. `amendment-num` is stored but NOT displayed: it is a different number - the sequence within that measure's debate - and printing both would read as two different answers to one question. Filled by `uv run ingest vote-amendments` from the same Clerk XML each row already cites as "Official record"; 637 House rolls, one request a second. Both fields default to null, the D27 "not collected" sentinel, and a row with null renders no amendment line at all. |
| Senate amendment sponsors are NOT published (2026-10-07) | A documented gap, not an omission. The Senate writes the amendment's designation into the question text itself ("On the Amendment S.Amdt. 316 to S.Con.Res. 7"), so the number is already on the row - but it names **no sponsor anywhere in its vote XML**. Publishing one would require a different congress.gov endpoint, which is new data and a separate decision. Until then Senate amendment rows name the amendment and not its sponsor, and nothing on the page implies the sponsor is unknown to the record. |

---

## §3 What the repository already has (audited 2026-10-07, read-only)

"Committed" is the last pushed state (`a5817e33c`). "On disk" includes the
running Congress 119 backfill. **Reuse all of this. Do not re-pull it.**

### 3.1 Data on hand

| Data | Committed | On disk | Serves |
|---|---|---|---|
| Members, House + Senate, 118th–119th | 639 | 639 | Member page header; roster; "find your reps" by state |
| Roll calls (party totals, question, result, class) | 3,519 (1,913 H / 1,606 S) | same | Vote record; attendance; left/right dot graph; bipartisan votes |
| Individual recorded votes | 982,167 | same | Vote record; attendance; consistency |
| Bill files (title, policy area, subjects, sponsor, cosponsors, CBO links) | 26,079 | 36,198 | Bills section; topics; effectiveness |
| Bill action timelines | 118th complete (19,308); 119th partial | 16,879 of ~19,441 for the 119th | Bill-process tracker; "this week"; events; odds by stage |
| Events (bill actions by month) | 119,645 in 46 months | regenerate after backfill | "This week in Congress"; alerts |
| Topics (official vocabulary) | 33 policy areas, 971 subjects | same | Topic subscriptions; timeline filters |
| Member legislation (sponsored / cosponsored, became-law flag) | 639 files; 38,893 sponsored | same | Bills introduced; effectiveness |
| Absences | 35,678; stated reason almost always empty; 1 candidate queued | same | Attendance; absence rows; responsiveness |
| Metrics already computed | attendance, sponsored, cosponsored, enacted rate, cosponsor enacted rate, cross-aisle support, cosponsor-to-vote gap, named-measure mismatch, yea/nay share, absence context | | Grade inputs |
| Rankings | 5 (attendance, sponsored, cosponsored, cross-aisle support, enacted rate) | | Grade context |
| Grades | Attendance only (A–F fixed bars, ratified 2026-08-13) | | Grading |
| Statements | **0.** Schema, curation app, and archive-capture tool exist. | | Consistency — **blocked until Phase 3** |
| Mississippi | 174 legislators, 1,725 roll calls, 905 bills, 144,007 votes | | States (back burner, untouched) |
| Raw API cache | ~282,000 files, gitignored | | Re-parse without refetch |

Pipeline, as built: `ingest → classify → checks → export`, nightly at 09:15 UTC,
auto-commit, Cloudflare Workers Builds deploys on push. Site is Astro static
with Preact islands. No server code exists yet.

### 3.2 Data each feature still needs

| Feature | Missing | Candidate source | Verified? |
|---|---|---|---|
| Consistency; say-vs-do | Statements | Member .gov press pages; Congressional Record via govinfo (client exists in `ingest/sources/govinfo.py`); campaign sites; official social accounts | Not verified |
| Member header | Photos | Bioguide (bioguide.congress.gov) or the unitedstates/images project | Not verified |
| Priorities & work | Committee assignments per member | unitedstates/congress-legislators `committee-membership-current.yaml`; congress.gov member endpoint | Not verified (only committee names on bill actions exist today) |
| Bio line | Years in office | Derivable from `terms` in member files | Exists |
| Bio line (low priority) | Election margin | FEC results; MIT Election Lab | Not verified |
| Bio line (low priority) | Education / background | Bioguide biography text | Not verified |
| "This week / next week" | Upcoming floor schedule | House: docs.house.gov / Majority Leader schedule; Senate: senate.gov floor schedule | Not verified |
| Bill page "what's left" | Stage model of the process | Derivable from action codes already stored | Exists, needs mapping |
| Benefit of the doubt | Bill text by section | congress.gov text endpoint; govinfo USLM | Not verified; CBO links exist |
| Responsiveness | Outreach log (sent, answered, status) | New table + sender (decided: site address) | Does not exist |
| Odds of passage | Pass rate by stage | Derivable from 26,000+ timelines | Exists, needs computing |
| Find your reps (address) | Address → district | Census Geocoder | Not verified; state-only needs nothing |
| Accounts / alerts | Users, email verifications, preferences, subscriptions, deliveries, channels, profiles | New D1 tables (designed, not built); Cloudflare Email Sending (needs Workers Paid) | Designed, unbuilt |
| PAC timeline (late) | Contributions | FEC API | Not verified |
| Bill diff (late) | Bill text versions | govinfo USLM XML | Not verified |

---

## §4 The product

### 4.1 Homepage
1. **Top:** welcoming. What the site is, why it exists, in a few plain lines. "Find your representatives": pick a state → its senators and House members. No stats, no jargon.
2. **Middle:** "In Congress this week and next." Upcoming votes · what passed · what died · urgent items. Each with a short AI summary (labeled, reviewed). Official legislative activity only, not outside news.
3. **Bottom:** statistics, including the "97% never got a floor vote" fact.

### 4.2 Member page
**Above the fold:** photo · name, party, state/district · **overall grade, large** · consistency verdict ("Voted against 6 of 9 stated priorities") · one fact line (years in office; margin and education later, low priority).

**Scroll 1 — Grades:** one card per category (§4.3) · weight sliders · **left/right dot graph** of every vote, placed by party-majority rule (§2).

**Scroll 2 — Priorities and work:** stated priorities, each with how they voted on it · committees · bills introduced, sponsored, cosponsored.

**Scroll 3 — Activity timeline:** newest first; votes, statements, bills, absences, outreach entries; filter by topic and by type.

### 4.3 Grading
| Category | Measures | Inputs |
|---|---|---|
| Consistency | Votes against stated priorities, net of compromises (§2) | Statements × votes |
| Attendance | Votes cast ÷ eligible | Roll calls, absences (built) |
| Effectiveness | Own bills that moved or became law | Legislation files, timelines |
| Bipartisanship | Cross-aisle cosponsors on own bills; votes with the other party's majority | Bills, roll calls (metrics exist) |
| Responsiveness | Share of requests for comment answered within 14 days | Outreach log |

- Five categories roll into **one overall grade** at the default weights (§2); readers slide the weights; defaults are visible to everyone.
- Every grade opens to its math: formula, inputs, denominator, covered-set size.
- Every published grade carries `formula_version`; inputs are retained so any past grade recomputes under any formula. Trends never skew on a formula change.
- Cutoffs are fixed bars per category, ratified (rule 5). Members with too little data show an exception label with the reason.

### 4.4 Statements (the "say" half)
Process: collect → AI categorizes (topic, stance, specificity) with a one-word confidence → human review dashboard → **owner approves one at a time** → publish with source link and archive snapshot.
Sources: press releases, Congressional Record floor speeches, campaign issue pages (most recent run), official social accounts. Every statement is archived on capture.

### 4.5 Benefit of the doubt
When a vote contradicts a stated priority, the site shows, as fact: *"This bill also contained X. [Name] publicly opposed X on [date]."* The X comes from the bill's actual contents; the prior position comes from the member's own published statements. Nothing is invented. If the record does not support an explanation, none is shown.
The site sends a request for comment to the office (automated, site address). The date sent and the status are logged and shown. After 14 days with no reply, "No response" is recorded. Absences work the same way: show a trustworthy reason if one exists, otherwise ask the office and log the result. Both feed Responsiveness.

### 4.6 Bills and chamber activity
- AI-written bill summaries, labeled and reviewed. **The prompts are designed carefully and versioned**; their quality is the site's quality.
- Each bill page: what it does · what else is bundled in · where it stands · what is left before it becomes law · odds of passage (historical by stage, labeled estimate).
- "This week in Congress" on the homepage from the same data.

### 4.7 Accounts, topics, alerts
- Accounts (email + password) let a reader track their own views over time.
- Readers pick topics that matter to them (official vocabulary, e.g. "Firearms and explosives").
- Email alerts: every action on a bill in a subscribed topic, including members' public comments on it; on one specific bill, when scheduled for a vote or on the result.
- Each email: what happened · short bill explanation · a simple steps-done vs steps-left visual · the % odds · who to call based on the step left (passed the House → call your senators).
- "Request a state": one more subscription; emails when the state is added.
- Anti-echo tools (Phase 8): top-3 agree/disagree across the aisle → laddered quiz → challenge my stance → drift check-in.

### 4.8 Privacy
The site collects what its features need. The privacy page states plainly what is collected and how it is used. It makes no promises.

### 4.9 Cuts (applied in Phase 2)
Off the homepage: roll-calls-by-class panel, chamber bar chart, dataset count tiles. Hidden: threat-model page, build commit hash in the footer, States tab. No values lists, no "every fact links to its source" banners anywhere.

### 4.10 States
Back burner. Mississippi data stays untouched. Planned in Phase 11, after federal works the way the owner wants.

---

## §5 Phases

Format per phase: **Goal · Mission tie · Tasks · Acceptance · Out of scope · Open questions.**
Commit as `P<N>: <what>` at each passing acceptance.
Counts inside acceptance criteria (how many statements, bills, emails) are builder
proposals, not ratified numbers; the owner may change any of them when the phase starts.

### Phase 1 — Docs and rule reset
**Goal:** the repo's rules match §1, old process docs are out of the way, and CI stays green.
**Mission tie:** removes the rules that blocked the core (AI categorization, statements) and the reading load that ate sessions.
**Tasks:**
1. Delete the no-AI guard: `ingest/checks/no_llm.py`, its entry in `ingest/checks/run.py`, its assertions in `tests/test_bootstrap.py`, and the policy section in `CONTRIBUTING.md` (rewrite that file to point at `MISSION.md` and §1; keep the corrections and data-is-public-record sections).
2. **First, because pytest is red until it is done:** `tests/test_privacy_accuracy_v2_7.py` reads `IMPLEMENTATIONv2.md` from the repo root (lines ~221 and ~265), which is now archived. Repoint or rewrite those two tests. Then remove the never-sell sentences from `site/src/pages/privacy.astro` and `site/src/pages/threat-model.astro`, and the "collect as little as possible" line. Rewrite `/privacy` as a plain description: what is collected today (nothing beyond server logs at the host), what accounts will collect when they ship, how each item is used. Update the test to the new wording and rename it to drop the old increment name.
3. Repoint comments and docstrings that cite the archived spec or progress file at this file: `ingest/__init__.py`, `ingest/checks/banned_words.py`, `ingest/config.py`, `site/src/lib/storageDisclosure.ts`, `site/src/lib/topicFeed.ts`, and the privacy test from task 2. Also remove the "AI-classified statements: flag and stop" standing rule wherever it is quoted in code comments.
4. Confirm `docs/archive/2026-10-07-pre-v3/README.md` lists every moved file (the architect moved them; verify nothing live imports or links to them).
5. Update `STATUS.md`.
**Acceptance:** `uv run ruff check .` clean; full pytest line green; `uv run checks` passes with no `no_llm` line; `cd site && npm run build && npm run test:links` green; `grep -ri "never sold\|never sell" site/src` returns nothing.
**Out of scope:** any page layout change, any new data, any AI call.
**Open questions:** none.

### Phase 2 — Homepage and member page restructure (existing data only)
**Goal:** the homepage and member page have the §4.1 / §4.2 shape, built from data already on disk.
**Mission tie:** verdict first, welcoming to newcomers, stats out of the reader's face.
**Tasks:**
1. Homepage top: intro copy (owner approves the wording) + "find your representatives" by state (members grouped by state from `data/members/`).
2. Homepage middle: "In Congress this week and next" from `data/events/` — what passed, what died, upcoming where the record shows a scheduled action. No AI summary yet; verbatim action text with the bill title. Leave a clearly marked slot for the summary (Phase 5).
3. Homepage bottom: stats area with the 97% fact. Remove the by-class panel, chamber chart, and count tiles.
4. Member page above the fold: name/party/state/district, years in office from `terms`, attendance grade as the only grade for now with "more categories coming" stated plainly, photo slot (source task 6).
5. Member page scroll 1: left/right dot graph by the party-majority rule from `party_totals` + the member's vote. Grade cards for Attendance; placeholder cards for the other four stating "not yet graded" with what will be measured.
6. Photos: pull from Bioguide or the unitedstates/images project into `data/raw/` then `site/public/`; record the source and license in `docs/data-contract.md`. If neither source is usable, ask the owner.
7. Member page scroll 2: bills introduced / sponsored / cosponsored from `data/legislation/`. Committees: ingest `committee-membership-current.yaml` if it verifies; otherwise leave the section with "coming" and note the gap in `STATUS.md`.
8. Member page scroll 3: timeline of votes, bill actions on their bills, absences; filter by topic and type. **Built with policy area, not subject terms** (2026-10-07): 973 subject terms do not fit a usable control, and policy area is the same official vocabulary one level up. 50 rows a page (see §2).
9. Hide the threat-model page, the footer commit hash, and the States tab (keep routes alive; remove nav links). Remove values lists and source-link banners from copy.
**Acceptance:** build green; e2e (axe + 380px) green on `/`, a House member page, a Senate member page; `test:links`, `test:file-count`, `test:grade-labels` green; owner looks at `/` and one member page and says yes.
**Acceptance status (2026-10-07): NOT PASSED — PENDING.** Every mechanical criterion is green
(build 13,115 pages; all seven `test:*`; 64 e2e; ruff; `verify-recompute`). The owner has
reviewed twice and said no twice; both rounds of fixes are applied and ratified in §2. The
single outstanding criterion is **the owner looking at `/` and one member page and saying
yes**. Phase 3 does not start until he does. Lighthouse is unverified locally (Windows temp-dir
permission error) and gates CI on push; nothing is pushed.
**Out of scope:** new grades, AI text, statements, accounts, visual redesign beyond layout.
**Open questions:** Q-A (homepage intro wording, owner writes or approves).

### Phase 3 — Statements pipeline
**Goal:** statements are collected, AI-categorized, reviewed, approved, archived, and shown on member pages.
**Mission tie:** this is the missing half of say-vs-do. Nothing else in the mission works without it.
**Tasks:**
1. `data/config/ai.yaml`: model id per task, prompt version, temperature. Add the Anthropic SDK to `pyproject.toml`. All AI calls go through one module, `ingest/ai.py`, that logs model, prompt version, and input hash per call.
2. Collectors, one per source, caching raw to `data/raw/`: (a) member press pages (member .gov sites; URL list in `data/config/statement-sources.yaml`, owner-maintained); (b) Congressional Record floor speeches via the existing govinfo client; (c) campaign issue pages (URL per member, owner-maintained); (d) official social accounts (platform access must be verified first; if unavailable, record that in `STATUS.md` and ship without it).
3. Archive capture on collect (existing `ingest/sources/archive_org.py`); a statement without a live capture does not publish.
4. Categorizer prompt: topic (official vocabulary), stance (for / against / mixed), specificity, priority signal (does the member call this a priority?), confidence word. **Prompt written with care, tested against a held-out hand-labeled set of at least 50 statements before use; record precision in `docs/data-contract.md`.**
5. Review dashboard in the existing curation app: queue → AI suggestion + confidence → approve / edit / reject, one at a time. Approved statements export to `data/statements/`.
6. Member page: "Stated priorities" list from approved statements; statements in the activity timeline.
**Acceptance:** ≥ 100 approved statements across ≥ 20 members of both parties; categorizer precision reported; archive links live (`uv run archive-links`); symmetry check green; build + e2e green.
**Out of scope:** grading from statements (Phase 4); benefit of the doubt (Phase 6).
**Open questions:** Q-B (minimum statements per member before anything is shown; evaluative, ratify).

### Phase 4 — Grading: all categories, overall grade, sliders
**Goal:** five category grades and one overall grade on every member page, with sliders and the math one click away.
**Mission tie:** accountability with the formula shown.
**Tasks:**
1. Ratification sitting (rule 5): builder proposes fixed bars per category from the real distributions; owner picks; `thresholds.yaml` gains all five categories, the default weights (§2), and bumps `formula_version`.
2. `ingest/scoring.py`: Attendance (exists), Effectiveness, Bipartisanship, Responsiveness (shows "not yet measured" until Phase 6 produces an outreach log), overall grade. **Consistency is held until Phase 6** (§2): its card shows "graded once compromises can be told from contradictions," and the overall grade uses the other categories with weights rescaled to 100 and says so.
3. Grades export retains inputs per member per run so history recomputes under any formula.
4. Member page: five cards, overall grade large, consistency verdict line, weight sliders (client-side; defaults from config; "reset to defaults").
5. Methods page: one section per category with the formula and the ratified bars.
6. Symmetry: every member graded by the same `formula_version` or listed in the exceptions with a mechanical reason.
**Acceptance:** `uv run verify-recompute` reproduces every grade; `test:grade-labels`, symmetry, build, e2e green; owner reviews three member pages (one from each party and one independent) and says yes.
**Out of scope:** trend charts over time (later), states.
**Open questions:** Q-C (bars per category, asked in task 1).

### Phase 5 — Bills: AI summaries, this-week, process tracker, odds
**Goal:** every bill page explains itself; the homepage reports the week; odds of passage are shown.
**Mission tie:** staying current on what is actually being worked on, passed, or killed.
**Tasks:**
1. Stage model: map action codes to stages (introduced → committee → floor → other chamber → to president → law / died). Record the mapping in `docs/data-contract.md`.
2. Odds by stage: historical share of bills reaching each stage that became law, by Congress; export to `data/config/odds.json`; label "estimate" on every surface.
3. Summary prompt: what it does · what else is bundled · plain language. Designed with care, versioned in `ai.yaml`, tested on 30 hand-checked bills. Output goes to the review dashboard; approved summaries export to `data/bills/`.
4. Bill page: summary (labeled "AI summary, reviewed"), bundle list, stage tracker visual, what is left, odds.
5. Homepage middle: AI summaries fill the Phase 2 slot; upcoming items from the floor schedule source if it verifies, otherwise from scheduled actions in the record.
**Acceptance:** 100% of bills with a page have a reviewed summary or show "summary pending" (never an unreviewed one); build, links, e2e green; owner reads five summaries and says yes.
**Out of scope:** statements, accounts.
**Open questions:** Q-D (floor schedule source, verify before use).

### Phase 6 — Benefit of the doubt and office outreach
**Goal:** contradictions show their context; the site asks offices for comment and logs the answer.
**Mission tie:** context beats outrage; responsiveness becomes measurable.
**Tasks:**
1. Bill contents by section (text endpoint, verify) → bundle items with topics.
2. Compromise detector: contradiction + bundle item the member has an approved prior statement against → compromise record with both citations. Rendered as fact (§2 motive rule). Reviewed in the dashboard before publishing.
3. Outreach: template approved by the owner; sender `comment@civicledger.net` (needs Email Sending → Workers Paid, owed by a human); outreach table (member, subject, sent, replied, status); 14-day non-response job.
4. Member page: outreach entries in the timeline with dates and status; absences show the logged result.
5. Consistency goes live (contradictions net of compromises) and joins the overall grade at its full weight; Responsiveness goes live.
**Acceptance:** first 20 outreach emails sent and logged; at least one 14-day rollover recorded; grades recompute; build and e2e green.
**Out of scope:** accounts.
**Open questions:** none beyond the human-owed plan upgrade.

### Phase 7 — Accounts, topic subscriptions, email alerts
**Goal:** readers sign up, pick topics and bills, and get the §4.7 email.
**Mission tie:** nobody has to track the people they vote for by hand.
**Tasks:**
1. `worker/` with D1: users, email_verifications, preferences, subscriptions (bill / topic / member / state-request), deliveries, channels, profiles. Argon2id passwords, double opt-in, password reset, hard delete, Turnstile on writes.
2. Privacy page updated in the same commit the tables ship (description, not promise).
3. Alert job: reads the published events, matches subscriptions, renders the email (what happened · summary · steps visual · odds · who to call for the reader's state), sends via Cloudflare Email Sending, records deliveries, one-click unsubscribe.
4. "Request a state" subscription.
5. Caps: subscriptions per account, emails per user per day, global daily ceiling under the plan quota with an owner alert at 80%.
**Acceptance:** signup → verify → subscribe → receive one real alert, end to end; delete removes every row; e2e against `wrangler dev` green.
**Out of scope:** SMS and push; anti-echo tools.
**Open questions:** Q-E (alert email wording, owner approves the template).

### Phase 8 — Anti-echo-chamber tools
**Goal:** the four tools, in order: top-3 agree/disagree across the aisle → laddered quiz → challenge my stance → drift check-in.
**Mission tie:** pulls readers out of echo chambers with facts.
**Tasks:** one sub-phase per tool, each with its own acceptance; quiz question bank reviewed by the owner before use.
**Acceptance (per tool):** works for a signed-in reader; owner tries it and says yes.
**Out of scope:** fact-check.
**Open questions:** Q-F (quiz bank review).

### Phase 9 — Fact-check methodology
**Goal:** a written, published method for checking claims reported by the left and the right, reusing the statements pipeline and review dashboard.
**Mission tie:** no side is "right"; the method applies equally.
**Tasks:** proposal to the owner first; build only what he approves.
**Acceptance:** owner approves the method; first ten checks published.
**Out of scope:** everything else.
**Open questions:** Q-G (scope of the method).

### Phase 10 — Design pass
**Goal:** the site looks like a well-made editorial or data-journalism site, on a phone first.
**Mission tie:** simple, digestible, built for short attention spans.
**Direction (builder's research, 2026-10-07; owner decides when this phase starts):**
- Avoid: purple/indigo accents and purple-to-blue gradients (the current accent family); Inter as the only typeface (the current one); gradient headlines, glowing blobs; everything in rounded cards with soft shadows, cards in cards; three-column feature grids; emoji as icons; generic dashboard look.
- Lean toward: editorial feel, strong typographic hierarchy; grade colors that do not overlap party red and blue; mobile-first; scroll-driven explanation for complex things.
- Study: Our World in Data; The Pudding; GovTrack.us. The owner brings his own reference sites at this phase.
- **Owner's visual reference (2026-10-07): opensecrets.org — AESTHETICS ONLY** (look and feel: color, type, spacing, visual weight). Do NOT take features, content, data, page structure, or subject focus from it. At this phase the builder studies it, lists the specific visual traits it would borrow, and gets the owner's approval before applying any. Not to be acted on before Phase 10.
**Acceptance:** owner approves; Lighthouse ≥ 90; axe green.
**Open questions:** Q-H (owner's reference sites).

### Phase 11 — States
**Goal:** a plan for adding states, starting from the Mississippi data already in the repo.
**Mission tie:** federal first, states over time.
**Tasks:** proposal to the owner; nothing built before he approves it.
**Open questions:** Q-I (which states first; "request a state" data informs this).

---

## §6 Engineering constants (carried, unchanged)

- Pipeline order `ingest → classify → checks → export`; nightly cron; auto-deploy on push.
- `data/` is the published record: deterministic JSON, sorted keys, `source_url` on every record, corrections are new commits (see `docs/correction-process.md`).
- Checks that can fail the build: banned words, symmetry, classification, integrity, grade-label guard, source-link trace, file-count, feed ids, action rows, e2e (axe + 380px), Lighthouse.
- Hosting: Cloudflare Workers static assets, 20,000-file limit on the free plan (17,005 used). Email sending needs the paid plan.
- `data/config/thresholds.yaml` is the only place an evaluative constant lives.

---

## §7 Open questions for the owner

| Id | Question | Blocks |
|---|---|---|
| Q-A | Homepage intro wording | **Answered 2026-10-07** (below) |
| Q-B | Minimum approved statements before a member's priorities list shows | Phase 3 |
| Q-C | Fixed bars for each of the four new categories | Phase 4 task 1 |
| Q-D | Which floor-schedule source to trust for "upcoming" | Phase 5 task 5 |
| Q-E | Alert email template wording | Phase 7 task 3 |
| Q-F | Quiz question bank review | Phase 8 |
| Q-G | Fact-check method scope | Phase 9 |
| Q-H | Owner's reference sites for design | Phase 10 |
| Q-I | Which states first | Phase 11 |

A phase may say "blocked on Q-N" in `STATUS.md` if the owner wants to answer later.

### Q-A answered - homepage intro (owner, 2026-10-07)

Phase 2 task 1 ships this text verbatim as the homepage intro:

> Nobody should have to become an expert, or spend their life tracking
> politicians, to know what the people they vote for actually do.
>
> So this site does the tracking. It is built from the official record - the
> votes, the bills, the attendance - and it is the same record for every member
> of every party.
>
> Find your representatives below.

**Amended 2026-10-07 (owner, at P2 review):** the third line, "Find your
representatives below.", is NOT shipped. The homepage order he set is intro -> In
Congress -> the representative finder -> statistics, so that sentence would point
past the Congress band rather than at the finder. The first two paragraphs ship
verbatim as above.

It deliberately claims neither say-vs-do nor an overall grade: statements land
in Phase 3 and the other four category grades in Phase 4, and rule 0 flips copy
in the same commit as the feature that makes it true. Revisit this wording at
each of those phases.
