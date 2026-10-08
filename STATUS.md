# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated**
2026-10-08 (builder, after the adjustment pass, the nightly fix, and two pushes).
## FIRST ACTION NEXT SESSION
**Start Phase 3 at §5 task 1** — `data/config/ai.yaml` and `ingest/ai.py`, the one module every AI call goes
through, logging model, prompt version and input hash; add the Anthropic SDK to `pyproject.toml`. `git pull`
first: the nightly commits data and pushes on its own. Only the archive.org keys block Phase 3, at task 3.
## Current phase
**Phase 3 — Statements pipeline. Current, NOT started; nothing stands in front of it.** The owner's unphased
adjustment pass closed 2026-10-08. Phase 2 acceptance PASSED 2026-10-07; Q-A and Q-B are ratified (§2). Nothing
in Phase 3 exists yet: `ingest/ai.py`, `data/config/ai.yaml`, `data/config/statement-sources.yaml` — all absent.
## Live facts
1. **Everything is PUSHED and LIVE; nothing is waiting.** The owner authorised two pushes on 2026-10-08 and
   approved each one specifically — **ask again before the next**. Workers Builds deploys on push (~20 min for
   the file volume, not a hang). Live and 200: `https://civic-ledger.sun-dragster453.workers.dev`
2. **LIGHTHOUSE IS SITTING ON THE LINE — watch it.** CI 37831240611 FAILED the mobile perf gate first attempt
   (`/` 0.88 from runs 0.69/0.88/0.88; `/m/A000055/1` 0.89 from 0.77/0.89/0.87; floor 0.90, a11y fine) and
   PASSED unchanged on re-run, so that night was runner noise. But the margin is ~0, the pages that missed are
   the two the nightly's data grows, and page weight only rises until Phase 10 (AES-01/02). Nothing was fixed
   and the gate was NOT lowered — 0.90 is the ratified §6.7 standard. A repeat is a real regression, not noise.
3. **Data publishing is NOT at risk from that:** the nightly runs build, `test:file-count`, `checks` and
   `verify-recompute` — **no Lighthouse** — and its bot push triggers no CI (GitHub loop prevention).
4. **The nightly timeout bug is FIXED and pushed (`bd3a0f191`); nightly 37809447990 then PASSED** (139 members,
   zero timeouts, pushed `2ddcf3895`). 2026-10-07 (37652899299) died on three
   ReadTimeouts out of 639 members; `legislation` had no failure ceiling while `bills` had one. Transient fetch
   failures are now tolerated at max(2, 2% of roster) and retried next run; count regressions still fail at any
   count. Cron moved 09:15 -> **05:07 UTC** (every run fired 5-9 h late) and `bill-activity --since` 30 -> **36 h**
   (measured gaps reached 27.7 h, leaving 2.3 h). The code default in `_parse_activity_args` stays 30.
5. Congress 119 backfill FINISHED, 0 fetch failures: 19,524/19,536 bills carry a timeline (11 have no action on
   the record, D104). House amendment ids collected; **Senate amendment sponsors are a documented gap** (§2).
6. **Phase 2 wording is all ratified in §2; nothing unratified is published.** Headline B, the motion table and
   its short lines, the amendment rule, the Senate gap, the resolving-roll rule (a tally is a margin only when
   that roll call resolved the measure), the 14-day band, the title clamp. Nav "Members"; route `/federal`.
7. **The 2026-10-08 adjustment pass is DONE:** interim neutral palette, purple gone (`c0f98ecc3`, `a891685e5`);
   the Sol audit and its pointers into Phases 3, 4, 5 and 10 (`eff14cbdc`); P2.1 phone layout fixes AES-20/22/25,
   owner-reviewed at 380px (`348c7f365`). No other audit item applies until the owner approves it at its phase.
## Open questions (§7)
**Q-A and Q-B are CLOSED** (§2). **Q-C arrives with Phase 4** (fixed bars per category). **Q-D gates the Phase 5
upcoming-votes block** — which floor-schedule source to trust; nothing on the site claims a vote date now.
## Owed by a human (owner)
1. **archive.org keys** — Phase 3 task 3: no live capture, no published statement.
2. **`data/config/statement-sources.yaml`** — owner-maintained press/campaign URLs per member; Phase 3 task 2
   cannot collect without it. Later: Workers Paid (P6-7), Turnstile (P7).
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` → `uv run ruff check .` →
the pytest gate below (~4 GB, ~27 min, never beside a site build) → `cd site && npm run build` + its seven `test:*` scripts + `npx playwright test`.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov-branch --cov-fail-under=100
```
