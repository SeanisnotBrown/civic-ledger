# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated**
2026-10-08 (builder, after the first authorised push and the deploy that followed it).
## FIRST ACTION NEXT SESSION
**`git pull` first** — nightly 37809447990 was in flight when this was written and it commits data and pushes on its own.
Then **the owner has out-of-plan adjustments to action before Phase 3 resumes**: ask him for the list and do that first
(the Sol audit, fact 8, is likely part of it). Phase 3 stays next, at §5 task 1 — `data/config/ai.yaml` and `ingest/ai.py`,
the one module every AI call goes through, logging model, prompt version and input hash.
## Current phase
**Phase 3 — Statements pipeline. Current, NOT started. An unphased adjustment pass comes first at
the owner's direction.** Phase 2 acceptance PASSED 2026-10-07. Q-A and Q-B are both ratified (§2),
so Phase 3 carries no open evaluative question. Nothing in Phase 3 exists yet: `ingest/ai.py`,
`data/config/ai.yaml` and `data/config/statement-sources.yaml` are all absent — verified, not assumed.
## Live facts
1. **The site is PUSHED and LIVE.** The owner authorised the first push 2026-10-08;
   `3ed943e9c..bd0ff7bcb`, all 12 commits, are on `origin/master`. He approved THAT push, not
   pushes in general — ask again before the next one.
2. **CI 37807667711 passed in full, Lighthouse included** — the one gate that had never run locally
   (Windows temp-dir permission error). No longer an unknown; it passed on the real build.
3. **Workers Builds deploys on push and is wired correctly** (the owner confirmed the dashboard). The deploy of
   `bd0ff7bcb` landed 2026-10-08 16:37Z, ~20 min after the push — the file volume makes it slow, not broken. Live
   and 200: `https://civic-ledger.sun-dragster453.workers.dev`
4. **Gates green before that push:** ruff; pytest 579 passed/1 skipped/100% cov (20m20s); build 13,115 pages in 63s, ~16,500 of the 20,000 free-plan file limit; `test:*` 7/7; 64 e2e.
5. **The 2026-10-07 nightly (37652899299) FAILED, undiagnosed.** Unrelated to the push; a candidate
   for the adjustment pass. **A dirty `data/` means something NEW is running, or the nightly pushed.**
6. Congress 119 backfill FINISHED, 0 fetch failures: 19,524/19,536 bills carry a timeline, 11 of the rest have no
   action on the record (D104). House amendment identities collected (637 Clerk XMLs); **Senate amendment sponsors are
   a documented gap** (§2) — the Senate names no sponsor anywhere in its vote XML.
7. **Phase 2 wording is all ratified in §2; nothing unratified is published.** Headline B, the
   22-entry motion table and its lines, the amendment rule, the Senate gap, the resolving-roll rule
   (a tally is a margin only when that roll call resolved the measure), the 14-day band with its
   exact dates, the title clamp. "This week" is not a heading. Nav "Members"; route `/federal`.
8. **UNCOMMITTED work in the tree, none of it written by the 2026-10-08 builder session:** the
   outside aesthetics audit `docs/design/2026-10-08-sol-aesthetics-audit.md` (reference only), its
   Phase 10 block in §5 of `IMPLEMENTATIONv3.md`, and live edits to ~9 `site/src` files including
   `global.css`. Nothing in it is ratified and no gate has been run over it. Ask the owner what it
   is and whether it is finished before committing, reverting or building on any of it.
## Open questions (§7)
**Q-A and Q-B are CLOSED** (§2). **Q-C arrives with Phase 4** (fixed bars per category). **Q-D gates the Phase 5 upcoming-votes block** — which floor-schedule source to trust; nothing on the site claims a vote date now.
## Owed by a human (owner)
1. **archive.org keys** — Phase 3 task 3: no live capture, no published statement.
2. **`data/config/statement-sources.yaml`** — owner-maintained press/campaign URLs per member;
   Phase 3 task 2 cannot collect without it. Later: Workers Paid (P6-7), Turnstile (P7).
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` → `uv run ruff check .` →
the pytest gate below (~4 GB, ~22 min, never beside a site build) → `cd site && npm run build` + its seven `test:*` scripts + `npx playwright test`.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov-branch --cov-fail-under=100
```
