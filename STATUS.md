# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated**
2026-10-09 (builder, Phase 3 task 1 in progress; spec amended, nothing committed).
## FIRST ACTION NEXT SESSION
**Phase 3 §5 task 2 — the collectors.** Task 1 is DONE and committed (`ai.yaml`, `ingest/ai.py`, 40 tests,
100% branch, in the CI gate). `git pull` FIRST: the nightly commits data and pushes on its own. Owed: the
live smoke call per task, blocked on `ANTHROPIC_API_KEY`; and the 40-member selection rule (options below).
## Current phase
**Phase 3 — Statements pipeline. TASK 1 DONE; TASK 2 (collectors) NEXT.** §5 Phase 3 gained TEN owner
decisions dated 2026-10-09: 118th-or-later window, rule-based pre-filter + per-party drop-rate fairness
check, Haiku triage gate, count-before-spend, $5.00 per-run cap, 40-member pilot, newest-25-per-member
categorizer cap, archive-after-filters (AMENDS the §2 Snapshots row), and the pilot draw (D10: 20D/20R,
16 House + 4 Senate each, random within cells from CURRENT 119th members, seed committed).
**KNOWN GAP: independents are not in the pilot draw** — cover them when collection widens past the 40.
Still absent: collectors, `statement-sources.yaml`.
## Live facts
1. **LIVE at `https://civic-ledger.sun-dragster453.workers.dev` (200).** Every push is owner-approved
   individually — **ask again before the next.** Workers Builds deploys on push (~20 min, not a hang).
2. **LIGHTHOUSE IS ON THE LINE — watch it.** CI 37831240611 FAILED mobile perf (`/` 0.88, `/m/A000055/1` 0.89,
   floor 0.90) then PASSED unchanged — noise, but margin ~0 on the two pages the nightly grows. Nothing fixed,
   gate NOT lowered (0.90 ratified §6.7); a repeat is a real regression.
3. **Data publishing is NOT at risk from it:** the nightly runs build, `checks` and `verify-recompute` — **no Lighthouse** — and its bot push triggers no CI.
4. **The nightly timeout bug is FIXED and pushed (`bd3a0f191`); nightly 37809447990 then PASSED** (139 members,
   zero timeouts, `2ddcf3895`). Transient fetch failures tolerated at max(2, 2% of roster) and retried next run;
   count regressions still fail at any count. Cron 09:15 -> **05:07 UTC**; `bill-activity --since` 30 -> **36 h**
   (gaps hit 27.7 h) — `_parse_activity_args`' code default stays 30.
5. Congress 119 backfill FINISHED, 0 failures: 19,524/19,536 bills have a timeline (11 have no action on the
   record, D104). **Senate amendment sponsors are a documented gap** (§2).
6. **Phase 2 wording is all ratified in §2; nothing unratified is published.** Headline B, the motion table,
   the amendment rule, the resolving-roll rule, the 14-day band, the title clamp, nav "Members", `/federal`.
7. **The 2026-10-08 adjustment pass is DONE:** neutral palette (`c0f98ecc3`, `a891685e5`), Sol audit + phase
   pointers (`eff14cbdc`), P2.1 phone fixes (`348c7f365`). No audit item applies until approved at its phase.
## Open questions (§7)
**Q-A, Q-B CLOSED** (§2). **Q-C** arrives with Phase 4 (bars per category). **Q-D** gates the Phase 5
upcoming-votes block (which floor-schedule source to trust; nothing claims a vote date now).
**Q-E and Q-F are NEW (2026-10-09), evaluative, and both gate task 4 — nothing categorized publishes until they
are ratified: (E)** what in a statement's own text establishes that the member calls something a **priority**;
**(F)** the **precision launch bar**. Options for both in `docs/research/2026-10-09-categorizer-model-review.md`.
## Owed by a human (owner)
1. **`ANTHROPIC_API_KEY` in `.env`** — MISSING today; blocks every Phase 3 AI call from task 1 onward.
2. **archive.org keys** — Phase 3 task 3: no live capture, no published statement.
3. **`data/config/statement-sources.yaml`** — owner-maintained press/campaign URLs per member; task 2
   cannot collect without it. Later: Workers Paid (P6-7), Turnstile (P7).
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` → `uv run ruff check .` →
the pytest gate below (~4 GB, ~27 min, never beside a site build) → `cd site && npm run build` + its seven `test:*` scripts + `npx playwright test`.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov=ingest.ai --cov-branch --cov-fail-under=100
```
