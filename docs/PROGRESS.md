# PROGRESS.md — Civic Alignment Platform build state

State-tracking file per `.claude` rules. Updated before ending any session.
Single source of truth for: current increment, acceptance status, blocked H-tasks.

**Last updated:** 2026-08-11, end of session.
**Git:** HEAD `fd39489` on `master`, pushed, in sync with `origin/master`, working tree clean.
**Remote:** https://github.com/SeanisnotBrown/civic-ledger.git (public).

---

## Current increment

**INC-0 — Repo bootstrap — ✅ COMPLETE (local + CI green).**
CI run `31525155390` passed both jobs (`python`, `site-and-checks`); doc-update
run `31525263905` also green.

**Next: INC-1 — Source feasibility spike — NOT STARTED.**
Federal branch is now **unblocked** (H1 done → `CONGRESS_API_KEY` present).
The state-branch verdict portion still needs **H2** (LegiScan); if H2 is still
pending when INC-1 runs, the verdict defaults to **DEFER** and the federal build
continues untouched (§0.2, Decision D18). Nothing else is in progress. Working
tree is clean — a fresh session starts cleanly.

---

## How to resume (read this first in a new session)

1. **`uv` is not on PATH by default in a fresh shell.** It is installed at
   `C:\Users\SB\AppData\Roaming\Python\Python314\Scripts\uv.exe` and was added
   to the **user** PATH (takes effect in new shells). If `uv` is not found:
   - PowerShell: it should be on PATH now; if not, prepend that Scripts dir.
   - Bash tool: `export PATH="$PATH:/c/Users/SB/AppData/Roaming/Python/Python314/Scripts"`.
2. **Re-verify INC-0 acceptance is still green before building INC-1:**
   `uv run checks && uv run pytest && (cd site && npm run build)` (Bash tool —
   PowerShell 5.1 rejects `&&`). Expect: 2 checks pass, 15 tests pass, 1 page built.
3. Python is uv-managed **3.12.13** (system Python is 3.14; project pins 3.12 via
   `.python-version`). `uv sync --frozen` is what CI runs; lockfile is consistent.
4. **Secrets:** `.env` holds `CONGRESS_API_KEY` (H1 done) and empty
   `LEGISCAN_API_KEY` (H2 pending). `.env` is gitignored — never commit it.
   Read keys from `.env`; do not hardcode.

---

## INC-1 — detailed plan / where to pick up

Spec: IMPLEMENTATION.md §7 "INC-1", §6.2 (raw cache), §A1 context. Goal: raw
samples on disk from every federal source + a written MS-state GO/DEFER verdict.
**No parser is written in later increments against spec assumptions — they are
written against the field shapes observed here (`SHAPES.md`).**

Concrete first steps (in order):
1. Build `ingest/cache.py` first — disk cache at
   `data/raw/{source}/{sha256(url+params)[:16]}.json|xml` + `.meta` sidecar
   (url, fetched_at, status). Gitignored (`data/raw/` already in `.gitignore`).
   Honor rate ceilings (§6.1/§6.3): Congress.gov ≤ 1 req/sec; never re-fetch a
   cached URL within 20h. All fetches go through this module.
2. `ingest/sources/congress_gov.py` — pull, into the cache and then copy the
   sample into `data/quality/samples/` (committed — the INC-1 exception to the
   gitignore, §6.2):
   - member list: `/member?currentMember=true&stateCode=MS`
   - one House roll call: `/house-vote/119/1/{n}` — **if the beta path 404s,
     fall back** to `https://clerk.house.gov/evs/2025/roll{NNN}.xml` and record
     the deviation in `docs/decisions.md`.
   - one bill detail carrying `cboCostEstimates`.
   - one CREC search hit for `"personal explanation"`.
3. Senate: one vote XML. **Discover the exact filename pattern from the session's
   `vote_menu` XML first — do not assume** the
   `vote_119_1_{NNNNN}.xml` shape (§7 INC-1 step 1).
4. `ingest/sources/legislators.py` — pull `legislators-current.yaml` from
   `unitedstates/congress-legislators`.
5. Write `data/quality/samples/SHAPES.md` documenting observed field names per
   source (this is the contract later parsers target).
6. **State branch (needs H2):** LegiScan `getSessionList(MS)` → `getDataset` →
   verdict test (do `roll_call` records carry per-person positions with
   resolvable `people_id`s? sample 5 bills vs Journal PDF pages; 5/5 = GO).
   If H2 pending / LegiScan unreachable / ambiguous → **DEFER** (correctness
   outranks scope). Write `data/quality/ms-state-verdict.md` with an unambiguous
   GO/DEFER + evidence table.

**INC-1 acceptance:** samples committed; `SHAPES.md` complete; verdict file
exists with unambiguous GO/DEFER + evidence.
**On failure:** any single federal source unreachable → note in `SHAPES.md`,
continue (its ingest increment carries the risk). LegiScan unreachable → DEFER.

Modules to create in INC-1: `ingest/cache.py`, `ingest/sources/congress_gov.py`,
`ingest/sources/senate_xml.py`, `ingest/sources/legislators.py`,
`ingest/sources/legiscan.py` (state branch), and (stub, for cross-check later)
`ingest/sources/clerk_house.py`. Register any new blocking check into
`ingest/checks/run.py` as it gains real logic (currently only banned_words +
no_llm are wired; symmetry/archive/integrity are no-ops on empty data).

---

## Increment status

| INC | Title | Status | Acceptance |
|-----|-------|--------|------------|
| INC-0 | Repo bootstrap | ✅ done (CI green) | `uv run checks && uv run pytest && (cd site && npm run build)` — local + CI green 2026-08-11 |
| INC-1 | Source feasibility spike | **not started (next)** | samples committed + SHAPES.md + GO/DEFER verdict. Federal unblocked (H1); state needs H2 else DEFER |
| INC-2 | Canonical members & schema | not started | — |
| INC-3 | House vote ingest | not started | — |
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
| H2 | INC-1 state branch | ⬜ pending — LegiScan API key. Absence → INC-1 verdict = DEFER (no other impact) |
| H3 | INC-0 push / all CI | ✅ done — repo live, pushed, CI green |
| H4 | INC-9, INC-16 | ⬜ pending — Cloudflare Pages + token |
| H5 | INC-9 | ⬜ pending — domain |
| H6 | INC-11 auth SPN | ⬜ pending — archive.org S3 keys (falls back to unauth SPN) |
| H7 | INC-10b | ⬜ pending — FEC key (optional increment) |
| H8–H12 | recurring content | ⬜ pending |
| H13 | pre-launch byline | ⬜ pending (non-blocking) |

## What exists in the repo now (INC-0 output)

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
