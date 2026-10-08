# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated**
2026-10-08 (builder, after the first push, the deploy, and the owner's adjustment pass).
## FIRST ACTION NEXT SESSION
**Start Phase 3 at §5 task 1** — `data/config/ai.yaml` and `ingest/ai.py`, the one module every AI call goes
through, logging model, prompt version and input hash; add the Anthropic SDK to `pyproject.toml`. The owner's
out-of-plan adjustment pass is DONE (fact 8). `git pull` first if the tree is dirty: the nightly commits data
and pushes on its own. Only the archive.org keys block Phase 3, at task 3.
## Current phase
**Phase 3 — Statements pipeline. Current, NOT started; nothing now stands in front of it.** The
owner's unphased adjustment pass closed 2026-10-08 (fact 8). Phase 2 acceptance PASSED 2026-10-07. Q-A and Q-B are both ratified (§2),
so Phase 3 carries no open evaluative question. Nothing in Phase 3 exists yet: `ingest/ai.py`,
`data/config/ai.yaml` and `data/config/statement-sources.yaml` are all absent — verified, not assumed.
## Live facts
1. **The site is LIVE; 6 commits are now UNPUSHED and need the owner's word.** He authorised the first push
   2026-10-08 (`3ed943e9c..bd0ff7bcb`, 12 commits) and approved THAT push only. The 6 since — the adjustment
   pass and this file — are committed locally and waiting. Run the gates below, then ask.
2. **CI 37807667711 passed in full, Lighthouse included** — the one gate that had never run locally
   (Windows temp-dir permission error). No longer an unknown; it passed on the real build.
3. **Workers Builds deploys on push and is wired correctly** (the owner confirmed the dashboard). The deploy of
   `bd0ff7bcb` landed 2026-10-08 16:37Z, ~20 min after the push — the file volume makes it slow, not broken. Live
   and 200: `https://civic-ledger.sun-dragster453.workers.dev`
4. **Gates green before that push:** ruff; pytest 579 passed/1 skipped/100% cov (20m20s); build 13,115 pages in 63s, ~16,500 of the 20,000 free-plan file limit; `test:*` 7/7; 64 e2e.
5. **The 2026-10-07 nightly (37652899299) FAILED and is still undiagnosed** — unrelated to the push, and not
   picked up by the adjustment pass. **A dirty `data/` means something NEW is running, or the nightly pushed.**
6. Congress 119 backfill FINISHED, 0 fetch failures: 19,524/19,536 bills carry a timeline, 11 of the rest have no
   action on the record (D104). House amendment identities collected (637 Clerk XMLs); **Senate amendment sponsors are
   a documented gap** (§2) — the Senate names no sponsor anywhere in its vote XML.
7. **Phase 2 wording is all ratified in §2; nothing unratified is published.** Headline B, the
   22-entry motion table and its lines, the amendment rule, the Senate gap, the resolving-roll rule
   (a tally is a margin only when that roll call resolved the measure), the 14-day band with its
   exact dates, the title clamp. "This week" is not a heading. Nav "Members"; route `/federal`.
8. **The owner's 2026-10-08 adjustment pass is DONE, in four commits:** the interim neutral palette with purple
   removed (`c0f98ecc3`) and its two follow-ups (`a891685e5`); the Sol aesthetics audit plus the pointers that
   hand its items to Phases 3, 4, 5 and 10 (`eff14cbdc`); and P2.1, the AES-20/22/25 phone layout fixes the
   owner reviewed at 380px and approved (`348c7f365`). Every item is gated green. Phase 10 still owns the final
   palette, and no other audit item is applied until the owner approves it at its phase.
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
