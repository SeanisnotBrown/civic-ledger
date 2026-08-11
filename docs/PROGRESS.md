# PROGRESS.md — Civic Alignment Platform build state

State-tracking file per `.claude` rules. Updated before ending any session.
Single source of truth for: current increment, acceptance status, blocked H-tasks.

**Last updated:** 2026-08-11, end of INC-2 session.
**Git:** INC-1 fully closed (follow-up CI run `31528769266` = success, confirmed
this session). INC-2 commit being pushed now — confirm its CI is green next session.
**Remote:** https://github.com/SeanisnotBrown/civic-ledger.git (public).

---

## Current increment

**INC-2 — Canonical members & schema layer — ✅ COMPLETE.**
`ingest/models.py` holds the full §5 schema layer (Member, Bill, RollCall,
MemberVote, Absence, Statement, Candidate, QuizQuestion + Term/CboRef/PageCapture/
QuizOption/Provenance); Tier-1 records use `extra="forbid"`. `ingest members`
fetches congress-legislators, filters to the 6-member MS delegation, and exports
deterministic `data/members/{bioguide}.json`. **11 new tests** in
`tests/test_models.py` (schema edge cases incl. a synthetic party switch, the
6-member covered set, double-export byte-identity). Three builder judgment calls
recorded as **D20** in `decisions.md`. Acceptance gate green (2 checks, 35 tests,
1 page). See "INC-2 output" below.

**Next: INC-3 — House vote ingest — NOT STARTED.** Unblocked (no human task gates
INC-3→INC-8; H4/H5 next gate at INC-9). Working tree clean after the INC-2 commit.

> **Still-open owner decision (carried from INC-1, unanswered):** run the MS
> Journal-PDF GO cross-check now (flip DEFER→GO, unlock INC-12) or fold it into
> INC-12? Default applied = fold into INC-12 (D18-aligned). Not blocking federal work.

---

## How to resume (read this first in a new session)

1. **`uv` is not on PATH by default in a fresh shell.** It is installed at
   `C:\Users\SB\AppData\Roaming\Python\Python314\Scripts\uv.exe` and was added
   to the **user** PATH (takes effect in new shells). If `uv` is not found:
   - PowerShell: it should be on PATH now; if not, prepend that Scripts dir.
   - Bash tool: `export PATH="$PATH:/c/Users/SB/AppData/Roaming/Python/Python314/Scripts"`.
2. **Re-verify acceptance is still green before building INC-2:**
   `uv run checks && uv run pytest && (cd site && npm run build)` (Bash tool —
   PowerShell 5.1 rejects `&&`). Expect: 2 checks pass, **35 tests** pass, 1 page
   built. Also run `uv run ruff check .` (CI runs ruff separately from `checks`).
   (`uv run ingest members` re-exports the 6 member files; `ingest spike` re-runs
   the INC-1 pull — both cached, neither is a CI job.)
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
`tests/test_banned_words_scope.py` (2), all offline. MS verdict: **DEFER**
(feasibility GO-positive; Journal cross-check → INC-12). 11 samples committed.

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

## INC-3 — where to pick up

Spec: IMPLEMENTATION.md §7 "INC-3"; shapes in `SHAPES.md §2/§3`. Goal: every House
roll call, 118th–119th, with MS member positions.

Concrete steps (in order):
1. `ingest/sources/congress_gov.py`: enumerate roll calls per session
   (`/house-vote/{congress}/{session}`, paginate), fetch each detail + `/members`.
   **Case trap (SHAPES §3):** member positions use `bioguideID` (capital ID),
   the member endpoint uses `bioguideId`. Join `bioguideID` → `Member.id`.
2. Parse to `RollCall` + `MemberVote` per MS member. `voteCast`
   `"Yea"|"Nay"|"Present"|"Not Voting"` → `position` enum; `"Not Voting"` →
   `not_voting` AND seeds an `Absence` stub (reason `None`). `vote_class` is
   REQUIRED — until INC-5's classifier exists, fill a provisional value + rule id
   (or land INC-5 first; the spec orders 3→4→5, so a temporary `"other"`/rule
   `"unclassified"` is acceptable and replaced in INC-5).
3. `ingest/sources/clerk_house.py` (currently a stub): implement the clerk XML
   parse for the `checks/integrity.py` 10-sample cross-check (positions must match
   exactly). `sourceDataURL` on each vote is the clerk XML link, handed to us
   directly (SHAPES §2) — no separate discovery.
4. Export `data/votes/` + `data/absences/`; register the vote-coverage symmetry
   rule (§6.5) into `checks/run.py`.

**INC-3 acceptance:** ingested House roll-call count per session matches the
clerk's official session total; 10-sample clerk cross-check passes; no covered-
member vote gaps (symmetry). On count mismatch → `data/quality/house-gaps.md`.

Register data-dependent checks into `ingest/checks/run.py` as they gain real
logic (symmetry/archive/integrity still no-ops until they have data).

---

## Increment status

| INC | Title | Status | Acceptance |
|-----|-------|--------|------------|
| INC-0 | Repo bootstrap | ✅ done (CI green) | `uv run checks && uv run pytest && (cd site && npm run build)` — local + CI green 2026-08-11 |
| INC-1 | Source feasibility spike | ✅ done | samples + SHAPES.md committed; verdict = DEFER (H2 pending). All 6 federal sources reached |
| INC-2 | Canonical members & schema | ✅ done | models.py complete + 6 MS members exported + double-export determinism; 35 tests green |
| INC-3 | House vote ingest | **not started (next)** | — |
| INC-4 | Senate vote ingest ∥ | not started | — |
| INC-5 | vote_class classifier | not started | — |
| INC-6 | Absences & explanations | not started | content = H9 |
| INC-7 | JSON export contracts | not started | — |
| INC-8 | Site MVP | not started | — |
| INC-9 | Automation + deploy (PUBLIC MVP) | not started | blocked by H4, H5 |
| INC-10 | Metrics + methodology | not started | — |
| INC-10b | FEC funding (optional) | not started | blocked by H7 |
| INC-11 | Statement ledger + curation | not started | content = H8, H6 for SPN |
| INC-12 | Mississippi state layer | not started | branch by INC-1 verdict |
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
| H2 | INC-1 state branch | ✅ done (mid-session) — LegiScan key present; feasibility GO-positive; Journal cross-check → INC-12 |
| H3 | INC-0 push / all CI | ✅ done — repo live, pushed, CI green |
| H4 | INC-9, INC-16 | ⬜ pending — Cloudflare Pages + token |
| H5 | INC-9 | ⬜ pending — domain |
| H6 | INC-11 auth SPN | ⬜ pending — archive.org S3 keys (falls back to unauth SPN) |
| H7 | INC-10b | ⬜ pending — FEC key (optional increment) |
| H8–H12 | recurring content | ⬜ pending |
| H13 | pre-launch byline | ⬜ pending (non-blocking) |

## What exists in the repo now (INC-0 + INC-1 + INC-2 output)

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
