# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated**
2026-10-09 (builder; task 1 done, the pilot draw done, collectors not started).
## FIRST ACTION NEXT SESSION
**Phase 3 §5 task 2 — collector (b), Congressional Record floor speeches** via the existing
`ingest/sources/govinfo.py`, scoped to the 40 ids in `data/config/statement-pilot.yaml`. The ONLY unblocked
collector: (a)/(c) need `statement-sources.yaml` (owed), (d) needs platform access. **`git pull` FIRST** —
the nightly pushes on its own. **3 commits are UNPUSHED.**
## Current phase
**Phase 3 — Statements pipeline.** Task 1 DONE (`ai.yaml`, `ingest/ai.py`, verified live). Task 2: the D10
draw is DONE (`data/config/statement-pilot.yaml` — 40 members, seed 20261009, snapshot 2026-10-09T19:53Z);
the four collectors are NOT started. **Read §5 Phase 3's TEN owner decisions (2026-10-09) before writing a
collector** — they set the window, filters, spend and scope.
## Live facts
1. **3 commits UNPUSHED** — `2700e0056` (Q-J), `69dfa3916` (STATUS), `a20c19dbf` (pilot draw). Live through
   `38c1235d5`: `https://civic-ledger.sun-dragster453.workers.dev`. Every push is owner-approved — **ask.**
2. **LIGHTHOUSE IS INTERMITTENT AT ~0 MARGIN — a regression, not noise (owner).** 37831240611 FAILED (`/`
   0.88, `/m/A000055/1` 0.89, floor 0.90) then passed on re-run; **37843065185 on `67e5291bc` FAILED and
   was never re-run** (red CI predates Phase 3); 37979980189 PASSED. A pass is not a fix. **Do not re-run
   — DIAGNOSE `/` and `/m/A000055/1`,** propose minimal fixes. 0.90 is ratified §6.7; never lower it.
3. **The AI gateway is verified against the LIVE API** (4 calls, $0.023376): both tasks answer,
   `proposition: null` is accepted, stance `none` returns on ceremonial text. **~$0.0095–$0.014 per
   categorized statement**, so decision 7's ceiling (40 × 25) estimates $10–14 and WILL stop at the $5 cap.
4. Models verified live: `claude-opus-5-5` ($4/$20), `claude-sonnet-5-5` ($2/$10), `claude-haiku-5-5`
   ($0.10/$0.50); Opus 5 is LEGACY. **No `temperature`** — models 400 on it; `effort` is the knob (tested).
5. **Rule-0 bug fixed** (`38c1235d5`): the "No longer serving." note used `member.serving`, which stays TRUE
   for a mid-term departure, so 16 departed members read as sitting. Now `holdsSeatAsOf` — ONE definition of
   "in office" site-wide, no `serving` reader left in `site/`. 100 pages carry it, up from 84; 66 e2e.
6. Nightly timeout bug FIXED (`bd3a0f191`): transient failures tolerated at max(2, 2% of roster), count
   regressions still fail. Cron **05:07 UTC**, `--since` **36 h**. 119 backfill DONE; **Senate amendment
   sponsors are a documented gap** (§2).
7. **Q-J is RATIFIED** (§2): what a stated priority is, per-statement and per-member, with the gate that no
   hidden priority moves a grade. Constants in `thresholds.yaml`; **`formula_version` NOT bumped — it bumps
   in the Phase 6 commit where Consistency goes live.**
## Open questions (§7)
**Q-K is OPEN and gates task 4:** the precision launch bar (options in
`docs/research/2026-10-09-categorizer-model-review.md`, not ratified). **Q-C** Phase 4 bars, **Q-D** Phase 5
floor schedule, **Q-J ANSWERED**. Real **Q-E**/**Q-F** are Phase 7/8 — untouched (briefly mislabelled).
## Owed by a human (owner)
1. **`data/config/statement-sources.yaml`** — press/campaign URLs, now only the **40 drawn members**, not
   540. Builder offered to draft it (roster + press-page discovery, every guess flagged); owner has not
   answered. Task 2 (a) and (c) cannot collect without it.
2. **archive.org keys** — task 3: no live capture, no published statement. Later: Workers Paid (P6-7).
3. **Pending:** does the Speaker (`J000299`, drawn into R/House) stay in the 40? He customarily does not
   vote, so his say-vs-do record is the thinnest in the sample. `ANTHROPIC_API_KEY` is DONE and working.
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` → `uv run ruff check .` →
the pytest gate below (~4 GB, ~29 min, never beside a site build) → `cd site && npm run build` + its seven `test:*` scripts + `npx playwright test`.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov=ingest.ai --cov=ingest.pilot --cov-branch --cov-fail-under=100
```
