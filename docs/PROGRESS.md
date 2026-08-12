# PROGRESS.md — Civic Alignment Platform build state

State-tracking file per `.claude` rules. Updated before ending any session.
Single source of truth for: current increment, acceptance status, blocked H-tasks.

**Last updated:** 2026-08-12, end of INC-6 session (absences & personal explanations).
**Git:** INC-1..INC-5 + MS GO-gate closed & pushed (all CI green). INC-6 being
committed now — confirm its CI is green next session.
**Remote:** https://github.com/SeanisnotBrown/civic-ledger.git (public).

> **PIPELINE ORDER (load-bearing, D24):** `ingest {house,senate}-votes` → `ingest
> classify` → `uv run checks`. An ingest re-export resets every roll to the
> provisional `unclassified`, so **classify must run after any ingest** or the
> `classification` check fails. INC-9's nightly job must sequence these.

---

## Current increment

**INC-6 — Absences & personal explanations — ✅ COMPLETE (build); content = H9.**
Queue → approve → publish pipeline for stated absence reasons. `uv run curate
absences search` searches CREC (govinfo) for the covered delegation's "Personal
Explanation" insertions, **hard-verifies each byline** (`HON. {NAME}` + `of {state}`
— rejects wrong-state surname collisions like Glenn Thompson of PA), extracts the
VERBATIM statement, auto-matches the roll by **absence-stub existence** (not date
arithmetic), and parks candidates in `data/quality/absence-queue/`. `uv run curate
absences approve [--granule <id>]` (interactive y/n/edit or owner-scriptable) writes
the verbatim `stated_reason` + CREC `stated_reason_source` + `declared_position`
onto the matching Absence. **Real MS candidate set = exactly 1** (Guest, `h-118-1-0031`,
YEA), queued and committed **pending owner approval (H9)** — per principle 5 the
builder ships the tool, the owner supplies content (D25); the machinery is proven
end-to-end by a test approving the real Guest granule onto a tmp stub. `data/absences/`
stays `stated_reason: null` until the owner acts. Banned-words excludes the queue
(D25). Design in **D25**. See "INC-6 output" below.

**Next: INC-7 — JSON export contracts — NOT STARTED.** `export.py` complete for
members/votes/bills/absences; `data/manifest.json` (counts, coverage, generated_at,
commit); `docs/data-contract.md`; `verify-recompute` fresh-clone script
(recompute vote totals from MemberVotes, match RollCall.totals 100%). Unblocked.

**(historical — INC-5)**
**INC-5 — vote_class classifier (§A1) — ✅ COMPLETE.**
Total classification of all **3,447** non-`non_position` rolls (both chambers) via
an ordered pure rules table (`ingest/classify.py`): procedural 1285, passage 886,
amendment 811, nomination 447, veto_override 14, **other 4 (0.12%)**. Ships the §A1
table + sanctioned extensions from the unmapped-questions loop over real 118–119
strings; the 4 `other` are honest one-offs (treaty ratification, a conference-insist
motion, 2 division-retention votes). R-RULE splits House "On Agreeing to the
Resolution" into `procedural` (Rules-Committee-`hsru00`-reported special rules, via
a committees fetch) vs `passage` (substantive) — the split INC-10 party-unity
depends on. `classify()` is pure/offline; golden test `tests/fixtures/questions.yaml`
(52 real strings) 100% pass. New CI gate `checks/classification.py` fails on any
`unclassified` roll or other-rate > 5%. Design in **D24**. See "INC-5 output" below.

**Next: INC-6 — Absences & personal explanations (content = H9) — NOT STARTED.**
CREC "personal explanation" search (govinfo, resolved INC-1) + covered-member names
→ review queue `data/quality/absence-queue/` → minimal CLI approver
(`uv run curate absences`) writes verbatim `Absence.stated_reason` + CREC page URL.

> **RESOLVED (2026-08-11): MS state verdict flipped DEFER → GO.** Owner chose
> option A — ran the 5-bill Journal cross-check now. **5/5 votes matched** (470
> per-person positions, zero mismatches; both chambers, contested votes). Evidence:
> `data/quality/ms-state-verdict.md` + `data/quality/samples/ms_vote_xcheck/`;
> rationale D21 in `decisions.md`. **INC-12 branch A is unlocked but the build
> order does NOT change — the next increment is still INC-3.** INC-12 activates
> when reached, carrying two notes: bundle the billstatus intermediate CA (CI/Linux
> has no AIA chasing), and route LegiScan through a TTL'd cache path.

---

## How to resume (read this first in a new session)

1. **`uv` is not on PATH by default in a fresh shell.** It is installed at
   `C:\Users\SB\AppData\Roaming\Python\Python314\Scripts\uv.exe` and was added
   to the **user** PATH (takes effect in new shells). If `uv` is not found:
   - PowerShell: it should be on PATH now; if not, prepend that Scripts dir.
   - Bash tool: `export PATH="$PATH:/c/Users/SB/AppData/Roaming/Python/Python314/Scripts"`.
2. **Re-verify acceptance is still green before building INC-2:**
   `uv run checks && uv run pytest && (cd site && npm run build)` (Bash tool —
   PowerShell 5.1 rejects `&&`). Expect: **4 checks** pass (banned_words, no_llm,
   symmetry, integrity), **47 tests** pass, 1 page built. Also run
   `uv run ruff check .` (CI runs ruff separately from `checks`).
   (`uv run ingest house-votes` re-syncs `data/votes/` + `data/absences/` — cached,
   re-runnable, resumes on interruption; `ingest members` / `spike` likewise cached.)
   Note: the `integrity` check makes ~10 live clerk.house.gov fetches; a clerk
   outage warns (not a failure).
3. Python is uv-managed **3.12.13** (system Python is 3.14; project pins 3.12 via
   `.python-version`). `uv sync --frozen` is what CI runs; lockfile is consistent.
4. **Secrets:** `.env` holds `CONGRESS_API_KEY` (H1 done) and empty
   `LEGISCAN_API_KEY` (H2 pending). `.env` is gitignored — never commit it.
   Read keys from `.env`; do not hardcode.

---

## INC-1 output (done — read `SHAPES.md` before writing any parser)

`data/quality/samples/SHAPES.md` is the **authoritative field-shape contract**
for INC-2/3/4/5/6. Key discovered deviations from IMPLEMENTATION.md's assumptions
(all in SHAPES.md + `decisions.md`):
- **Members by state = PATH `/member/{stateCode}`, NOT `?stateCode=` (503).** (D19)
- **`bioguideId` (member list) vs `bioguideID` (house-vote positions)** — case differs.
- **Senate menu & detail are in different dirs**; the spec's `vote_menu` path
  301-redirects. Menu `roll_call_lists/`, detail `roll_call_votes/vote{c}{s}/`.
- **CREC full-text search RESOLVED** — Congress.gov `/congressional-record` is a
  date index only, but **govinfo `POST /search` does full-text with the SAME
  api.data.gov key** (15,998 "personal explanation" CREC hits). INC-6 has a real
  source; no risk carried forward.
- **Crosswalk joins:** house `bioguideID`→`id.bioguide`; senate `lis_member_id`→
  `id.lis` (both in `legislators_current_ms.yaml`).

Modules created: `ingest/env.py` (`.env` reader), `ingest/cache.py` (header-auth
disk cache; **credential never in URL/key/meta**), `ingest/spike.py` (`ingest
spike`, with secret-guard), sources `congress_gov.py` / `senate_xml.py` /
`legislators.py` / `clerk_house.py` (stub) / `legiscan.py` (state, DEFER path) /
`govinfo.py` (CREC search, INC-6). Tests: `tests/test_cache.py` (6) +
`tests/test_banned_words_scope.py` (2), all offline. MS verdict: initially DEFER
at INC-1; **flipped to GO on 2026-08-11** (5/5 Journal cross-check — see the
RESOLVED callout above). 11 samples committed.

## INC-2 output (done — the schema layer INC-3+ import from)

`ingest/models.py` = the complete §5 layer. Reuse these; do not redefine records.
- **`Member`** exported to `data/members/{bioguide}.json` (6 files, committed).
  `id`=bioguide; `ids`=curated string crosswalk (D20 — `fec` comma-joined,
  `lis`/`fec` are the join keys INC-4/INC-10b need); `terms` = full history,
  start-sorted, party switches preserved; `serving` = latest term overlaps
  congress 119 (deterministic, no wall-clock).
- `legislators.party_code(word)` — shared "Democrat"/"Democratic"→"D" mapper;
  **INC-3 reuses it for `voteParty`.** Raises on unmapped (→ quarantine, §6.1).
- `legislators.congress_window(N)` / `_term_overlaps` — congress↔date helpers;
  **INC-3 uses these to bucket roll calls into 118 vs 119.**
- `export._dumps(obj)` — the canonical serializer (sorted keys, 2-space, LF,
  trailing newline). Every INC-7 export contract should route through it.
- Tier-1 records (`Member`, `Bill`, `RollCall`, `MemberVote`, `Absence`, …) set
  `extra="forbid"` — an unexpected upstream field raises `ValidationError`
  (→ quarantine), it never silently rides into the published dataset.

## INC-3 output (done — the vote layer INC-4/5/6 build on)

- **`ingest/house_votes.py`** — `parse_rollcall(members_json, congress, session)`
  (pure) → `(RollCall, list[MemberVote], list[Absence])`, and `run()` (the
  `ingest house-votes` pipeline: enumerate → fetch `/members` per roll → quarantine
  → gaps → export). **Re-runnable/resumable** (cache); fault-tolerant per roll.
  - `VOTE_MAP` maps **both** Yea/Nay **and** Aye/No → yea/nay. **INC-4 senate
    parsing should reuse this insight** (LIS XML `vote_cast` is Yea/Nay; SHAPES §6).
  - Speaker elections = **`non_position`** rolls: a `RollCall` (counts) with a raw
    candidate tally in `totals`, **no** `member_votes`, excluded from symmetry +
    integrity. Detected by majority-unmappable `voteCast`.
  - `vote_class` provisional `other`/`unclassified` (INC-5 §A1 rewrites; leaves
    `non_position` alone).
- **`data/votes/{h-c-s-NNNN}.json`** = `{"rollcall": {...}, "member_votes": [...]}`
  (MS only, sorted). **`data/absences/{member}--{rollcall}.json`** = one stub per
  not_voting. `source_url` = clerk `sourceDataURL`.
- **`ingest/sources/clerk_house.py::parse_positions(xml, state)`** — bioguide→
  position from clerk XML (maps Aye/No too); the D6 independent cross-check source.
- **`checks/symmetry.py`** (vote coverage, §6.5) + **`checks/integrity.py`**
  (seeded 10-sample clerk cross-check; mismatch fails, unreachable warns) — both
  registered in `run.py`, both no-op on empty data.
- **`cache.py`** now retries timeouts/network errors (§6.1 bug fix) — reuse holds
  for every future source.

## INC-4 output (done — the Senate vote layer, mirrors INC-3)

- **`ingest/senate_votes.py`** — `parse_rollcall(detail_xml, congress, session,
  lis_to_bioguide, menu_tally)` (pure) → `(RollCall, list[MemberVote],
  list[Absence])`, and `run()` (the `ingest senate-votes` pipeline: parse menu →
  fetch each detail → cross-check tally → quarantine → gaps → export).
  Re-runnable/resumable (cache); idempotency re-verified (re-run byte-identical).
  - **Cross-SOURCE tally check** replaces INC-3's clerk: member-computed yea/nay
    must equal the menu's `vote_tally` (a different file) → else `TallyMismatch`.
  - **`_bill_id` handles 3 measure shapes** — `<document>` bill (`hr1-119`),
    amendment fallback to `<amendment><amendment_to_document_number>`, and
    nomination/treaty/quorum → `None`. Whitelist of real bill types.
  - **`_parse_date`** hand-rolls month parsing (locale-proof) → naive ISO ET.
  - **No `non_position` branch** (Senate has no candidate-surname rolls); VP
    tie-breaks handled by arithmetic that already agrees (D23).
- **`ingest/sources/senate_xml.py`** — added `parse_menu` (→ `{roll: (yeas,nays)}`,
  the enumeration + tally source), `detail_url`, and `parse_positions(detail_xml,
  lis_to_bioguide, state)` (the D6-style independent re-parse for integrity).
- **`data/votes/s-{c}-{s}-NNNN.json`** (1,581 files) + **`data/absences/`** (87
  Senate stubs; 243 total with House). Same export contract as INC-3.
- **`checks/symmetry.py`** generalized: `coverage_gaps(chamber, prefix)` runs House
  + Senate; report gains a `"senate"` key. **`checks/integrity.py`** runs a House
  clerk pass + a Senate detail-reparse pass (each no-op until its data exists).
- **`cli.py`** `senate-votes` subcommand.
- Tests: **`tests/test_senate_votes.py` (18)** — menu contiguity, all 4 real shape
  variants, tally-mismatch, crosswalk join, bill-id normalization, determinism.
  Committed 3 new detail samples (371/372/659). Test count 47 → 65.

## INC-5 output (done — the classified vote layer INC-8/10 render + score on)

- **`ingest/classify.py`** — `classify(question, *, is_rules_resolution=False) ->
  (VoteClass, rule_id)` is a PURE, offline, ordered rules table (`RULES` =
  module-level tuples, renderable on the INC-10 methodology page). FIRST match wins;
  order encodes precedence. `run()` = the `ingest classify` pipeline: rewrites
  `vote_class`/`vote_class_rule` in place on every non-`non_position`
  `data/votes/*.json`, regenerates `data/quality/unmapped_questions.json`
  (deterministic sorted regen, D24), fails if other-rate > `MAX_OTHER_RATE`.
  Idempotent (re-run byte-identical).
- **R-RULE** kept pure via the `is_rules_resolution` arg; `run()` computes it by
  fetching `bill/{c}/hres/{n}/committees` (`congress_gov.bill_committees`, new) and
  checking for House Rules `hsru00` + a "Reported" activity.
- **`checks/classification.py`** (new, registered in `run.py`) — CI gate: fails on
  any `unclassified` roll or other-rate > ceiling. **`cli.py`** `classify` subcommand.
- Tests: **`tests/test_classify.py` (9)** + golden **`tests/fixtures/questions.yaml`**
  (52 verbatim real strings, every rule id, both R-RULE branches, treaty). 65 → 74.
- **⚠ ORDER: ingest → classify → checks** (D24). Re-running an ingest resets rolls to
  `unclassified`; the classification gate then fails until `classify` re-runs.

## INC-6 output (done — the absence-explanation curation pipeline)

- **`curation/absences.py`** — pure `parse_granule` (byline, verbatim statement,
  roll refs, declared position), `verify_member` (the wrong-state gate), stub-
  existence `match_rollcall`, `search()` (CREC → verified queue) and `approve()` /
  `approve_one()` (owner approval → verbatim Absence). `_publish` refuses an
  unmatched roll (an Absence is keyed member+roll).
- **`ingest/sources/govinfo.py`** — `crec_personal_explanations(state, start, end)`
  (title+byline-scoped search), `granule_text(pkg, gid)` (header-auth), `granule_url`
  (the public `govinfo.gov/app/details/...` citation, verified 200).
- **`curation/cli.py`** — `curate absences {search|approve}` (`approve --granule <id>`
  is the owner's non-interactive path). **`banned_words.py`** excludes
  `data/quality/absence-queue/` (D25).
- Tests: **`tests/test_absences.py` (12)** + the queue-exclusion case in
  `test_banned_words_scope.py`; committed real fixture
  `data/quality/samples/crec_personal_explanation_guest.htm`. 74 → 86.
- **Queued, pending H9:** `data/quality/absence-queue/CREC-2023-01-13-pt1-PgE29-4.json`
  (Guest). Owner approval is H9; `data/absences/` reasons stay null until then.

## INC-7 — where to pick up

Spec: IMPLEMENTATION.md §7 "INC-7". Goal: a stable, documented, deterministic public
dataset. Steps:
1. `export.py` complete for members/votes/bills/absences (members/votes/absences
   already export via their ingests; add any missing record types + a single
   `export` entry that regenerates all). Keep `_dumps` determinism.
2. **`data/manifest.json`** — counts, congress coverage, `generated_at`, and the
   commit sha. **This is the ONE place a wall-clock/commit value lives** (§6.3): every
   record stays wall-clock-free so nightly diffs show only real changes; the manifest
   carries the timestamp. So `generated_at`/commit must be injected (env/arg), not
   read at import, or the double-export test breaks.
3. **`docs/data-contract.md`** — every file + field, for third-party recompute.
4. **`verify-recompute`** — a fresh-clone script (new console entry) that recomputes
   each RollCall's totals from its `member_votes`… **BUT NOTE:** votes export only the
   **covered MS** `member_votes`, while `RollCall.totals` is the **chamber-wide** tally
   (D22). So "recompute totals from MemberVotes" can't mean the embedded MS rows.
   Resolve in INC-7: either (a) recompute a *coverage* invariant (every covered member
   has exactly one position per eligible roll — overlaps symmetry), or (b) persist the
   raw chamber tally to recompute against. Pick and document; the brief's intent is
   "third party can recompute and match", so (b) or a documented (a) both satisfy it.

**INC-7 acceptance:** double-export byte-identical; JSON Schema files generated from
pydantic and committed; `verify-recompute` matches 100% of roll calls (per the
resolved definition above).

---

## Increment status

| INC | Title | Status | Acceptance |
|-----|-------|--------|------------|
| INC-0 | Repo bootstrap | ✅ done (CI green) | `uv run checks && uv run pytest && (cd site && npm run build)` — local + CI green 2026-08-11 |
| INC-1 | Source feasibility spike | ✅ done | samples + SHAPES.md committed; all 6 federal sources reached; MS verdict **GO** (cross-check run 2026-08-11) |
| INC-2 | Canonical members & schema | ✅ done | models.py complete + 6 MS members exported + double-export determinism; 35 tests green |
| INC-3 | House vote ingest | ✅ done | 1,886 rolls (counts match, contiguous), 10/10 clerk cross-check, symmetry OK; 47 tests |
| INC-4 | Senate vote ingest ∥ | ✅ done | 1,581 rolls (contiguous 1..N per session, 119/1=659), 10/10 detail cross-check + menu-tally check, symmetry OK both chambers; 65 tests |
| INC-5 | vote_class classifier | ✅ done | 3,447 rolls classified, other 0.12% (≤5%); golden 52-string fixture 100%; R-RULE via Rules-Cmte fetch; classification CI gate; 74 tests |
| INC-6 | Absences & explanations | ✅ done (build); content = H9 | pipeline green (search→verify→queue→approve), byline gate, stub-existence match, queue banned-words-excluded; 1 candidate queued pending owner approval; 86 tests |
| INC-7 | JSON export contracts | **not started (next)** | — |
| INC-8 | Site MVP | not started | — |
| INC-9 | Automation + deploy (PUBLIC MVP) | not started | blocked by H4, H5 |
| INC-10 | Metrics + methodology | not started | — |
| INC-10b | FEC funding (optional) | not started | blocked by H7 |
| INC-11 | Statement ledger + curation | not started | content = H8, H6 for SPN |
| INC-12 | Mississippi state layer | not started | **branch A** (INC-1 verdict = GO, 5/5); unlocked, builds when reached |
| INC-13 | Candidate Tracker | not started | content = H10 |
| INC-14 | Alignment Quiz engine | not started | content = H11 |
| INC-15 | Alignment outputs | not started | — |
| INC-16 | Aggregates Worker + privacy | not started | blocked by H4, canary = H12 |
| INC-17 | Challenge & Calibration | not started | — |
| INC-18 | Longitudinal drift | not started | — |
| INC-19 | Bill diff viewer | not started | — |
| INC-20 | "Nobody Told You" feed + glossary ∥ | not started | — |
| INC-21 | Ballot builder + share cards | not started | — |
| INC-22 | Zero-knowledge sync (post-v1 stub) | deferred | Decision D12 — do not build this pass |

## Blocked human tasks (see docs/HUMAN-TASKS.md for full table)

| H | Blocks | Status |
|---|--------|--------|
| H1 | INC-1 | ✅ done — CONGRESS_API_KEY in .env + GitHub secret |
| H2 | INC-1 state branch | ✅ done — LegiScan key present; **Journal cross-check run 2026-08-11 → verdict GO (5/5)**; INC-12 branch A unlocked |
| H3 | INC-0 push / all CI | ✅ done — repo live, pushed, CI green |
| H4 | INC-9, INC-16 | ⬜ pending — Cloudflare Pages + token |
| H5 | INC-9 | ⬜ pending — domain |
| H6 | INC-11 auth SPN | ⬜ pending — archive.org S3 keys (falls back to unauth SPN) |
| H7 | INC-10b | ⬜ pending — FEC key (optional increment) |
| H8–H12 | recurring content | ⬜ pending |
| H13 | pre-launch byline | ⬜ pending (non-blocking) |

## What exists in the repo now (INC-0..INC-6 output)

**INC-6 additions:** `curation/absences.py` (search→verify→queue→approve pipeline),
`crec_personal_explanations`/`granule_text`/`granule_url` in `ingest/sources/govinfo.py`,
the `absences` subcommands in `curation/cli.py`, the `absence-queue/` exclusion in
`ingest/checks/banned_words.py`, `tests/test_absences.py` (12) + a queue-exclusion
test, the committed `data/quality/samples/crec_personal_explanation_guest.htm` fixture,
and one pending queue file `data/quality/absence-queue/*.json`. Also swept printed
U+2192 arrows → ASCII (Windows cp1252 crash). D25 in `decisions.md`. Test count 74 → 86.

**INC-5 additions:** `ingest/classify.py` (pure §A1 rules table + `classify`
pipeline, `classify` subcommand), `congress_gov.bill_committees`,
`ingest/checks/classification.py` (registered in `run.py`), `tests/test_classify.py`
(9) + `tests/fixtures/questions.yaml` (52 real strings), the `classify` wiring in
`cli.py`, `data/quality/unmapped_questions.json`, and the in-place re-classification
of all **3,447** `data/votes/*.json` (vote_class/vote_class_rule rewritten). D24 in
`decisions.md`. Test count 65 → 74.

**INC-4 additions:** `ingest/senate_votes.py` (parser + `run()` pipeline,
`senate-votes` subcommand), `parse_menu`/`detail_url`/`parse_positions`/`VOTE_MAP`
in `ingest/sources/senate_xml.py`, both-chamber generalization of
`checks/symmetry.py`, the Senate re-parse pass in `checks/integrity.py`, the
`senate-votes` wiring in `cli.py`, `tests/test_senate_votes.py` (18) + 3 committed
detail samples (371/372/659), and the committed dataset: **1,581 `data/votes/s-*.json`
+ 87 Senate `data/absences/*.json`** + the updated `data/quality/symmetry-report.json`.
D23 in `decisions.md`. Test count 47 → 65.

**INC-3 additions:** `ingest/house_votes.py` (parser + `run()` pipeline,
`house-votes` subcommand), `parse_positions` in `ingest/sources/clerk_house.py`,
`house_vote_roll_numbers` enumeration in `congress_gov.py`, `export_rollcall`/
`export_absence` in `export.py`, `checks/symmetry.py` + `checks/integrity.py`
(registered in `run.py`), the `cache.py` timeout-retry fix,
`tests/test_house_votes.py` (10) + a cache retry test, and the committed dataset:
**1,886 `data/votes/*.json` + 156 `data/absences/*.json`** +
`data/quality/symmetry-report.json`. D22 in `decisions.md`. Test count 36 → 47.

**INC-2 additions:** `ingest/models.py` (full §5 schema layer), the raw→`Member`
parser in `ingest/sources/legislators.py` (`party_code`, `congress_window`,
`is_covered`, `covered_members`), the deterministic serializer + `export_members`
in `ingest/export.py`, the `members` subcommand in `cli.py`, `tests/test_models.py`
(11 offline tests), and 6 committed `data/members/*.json`. D20 in `decisions.md`.
Test count 23 → 35.

**INC-1 additions:** `ingest/env.py`, `ingest/cache.py`, `ingest/spike.py`,
`ingest/sources/{congress_gov,senate_xml,legislators,clerk_house,legiscan}.py`,
`tests/test_cache.py` (6) + `tests/test_banned_words_scope.py` (2) offline tests,
`ingest/sources/govinfo.py`, and the committed `data/quality/samples/`
(11 samples + `SHAPES.md`) + `data/quality/ms-state-verdict.md`.
`banned_words.py` now excludes `data/quality/samples/` (ADR). `ingest spike`
subcommand wired in `cli.py`. Test count 15 → 23.

## Prior state (INC-0 output)

- **Python (uv):** `pyproject.toml` (console scripts `ingest`/`export`/`curate`/
  `checks`; hatchling ships two packages `ingest` + `curation`), `uv.lock`,
  `.python-version`=3.12.
- `ingest/config.py` — `K_ANON=50`, `CONGRESSES=[118,119]`, `COVERED_STATE="MS"`,
  symmetry + quarantine + max-other-rate thresholds.
- `ingest/checks/` — `banned_words.py` (§6.4), `no_llm.py` (§6.6, self-match
  defended two ways + tested), `run.py` (the `checks` entrypoint).
- Stub entrypoints: `ingest/cli.py`, `ingest/export.py`, `curation/cli.py`
  (all print a status + exit 0; real logic lands in later increments).
- `tests/test_bootstrap.py` — 15 tests (entrypoints importable, K_ANON, congress
  coverage, banned-words detect/clean, no_llm self-non-match + detection).
- **Site (Node/npm):** `site/` Astro 5 static scaffold, Tailwind v4 via
  `@tailwindcss/vite`, Preact islands, placeholder `index.astro`,
  `site/package-lock.json`. `dist/` is gitignored (CI builds it).
- **CI:** `.github/workflows/ci.yml` — Node 22, `astral-sh/setup-uv`, `uv sync
  --frozen`, **build-before-checks** so §6.4 scans real `site/dist/**`.
- **Docs:** `docs/HUMAN-TASKS.md`, `docs/decisions.md` (version pins + builder
  ADRs), `CONTRIBUTING.md` (no-LLM policy), `.env.example`, this file.
- **Repo hygiene:** `.gitattributes` forces LF everywhere (protects §6.3
  export determinism); `.gitignore` covers `.env`, `data/raw/`, `build.db`,
  caches, `node_modules/`, `dist/`.

## Notes / open items / ADR pointers

- Version pins recorded in `docs/decisions.md` (Python + Node) at INC-0.
- Dev environment: Windows 11 + PowerShell. `uv` at
  `%APPDATA%\Python\Python314\Scripts` on user PATH. Local Python 3.14 → project
  pins 3.12 (uv-managed). Local Node 24 → CI pins Node 22 LTS (logged in decisions.md).
- **Non-blocking CI warning:** logs show "Node.js 20 is deprecated" for
  `actions/checkout@v4` / `setup-node@v4` / `setup-uv@v5`. This is GitHub
  *runner-infra* deprecation of the actions' own Node runtime, **not** our Node
  22 pin. Does not fail CI; resolves when those actions ship Node-24 releases.
  No action needed; revisit only if it ever turns into a hard failure.
- **CLAUDE.md note:** there is no `CLAUDE.md` file; its content lives in the
  `.claude` file (points to IMPLEMENTATION.md + working rules). Followed as-is.
- **Watch in INC-1:** (a) the `/house-vote` beta endpoint may 404 → clerk XML
  fallback + log deviation; (b) Senate vote filename must be discovered from the
  `vote_menu` XML, not assumed; (c) H2 absence forces the state verdict to DEFER.
