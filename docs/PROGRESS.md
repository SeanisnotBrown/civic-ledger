# PROGRESS.md — Civic Alignment Platform build state

State-tracking file per `.claude` rules. Updated before ending any session.
Single source of truth for: current increment, acceptance status, blocked H-tasks.

## Current increment

**INC-0 — Repo bootstrap** — status: **✅ COMPLETE — CI green on master (run 31525155390, 2026-08-11)**

Next: **INC-1 — Source feasibility spike** (blocked by H1; H2 for state branch).
Cannot start until H1 provides `CONGRESS_API_KEY`. Per §0.2, build the code path
and stub the credential; INC-1 acceptance needs real API responses to cache.

## Increment status

| INC | Title | Status | Acceptance |
|-----|-------|--------|------------|
| INC-0 | Repo bootstrap | ✅ done (CI green) | `uv run checks && uv run pytest && (cd site && npm run build)` — local + CI green 2026-08-11 |
| INC-1 | Source feasibility spike | not started | blocked by H1 (H2 for state branch) |
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
| H2 | INC-1 state branch | pending — LegiScan API key |
| H3 | INC-0 push / all CI | ✅ done — repo live, pushed, CI green |
| H4 | INC-9, INC-16 | pending — Cloudflare Pages + token |
| H5 | INC-9 | pending — domain |
| H6 | INC-11 auth SPN | pending — archive.org S3 keys |
| H7 | INC-10b | pending — FEC key |
| H8–H12 | recurring content | pending |
| H13 | pre-launch byline | pending (non-blocking) |

## Notes / running ADR pointers

- Version pins recorded in `docs/decisions.md` at INC-0.
- Dev environment: Windows 11 + PowerShell. `uv` installed to
  `%APPDATA%\Python\Python314\Scripts` and added to user PATH.
- Local Python is 3.14; project pins 3.12 via `.python-version` (uv-managed).
- Local Node is 24; CI pins Node 22 LTS (deviation logged in decisions.md).
</content>
</invoke>
