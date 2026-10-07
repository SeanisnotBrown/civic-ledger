# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-07 (builder, P2 review round 2 applied).
## Current phase
**Phase 2, third pass.** The owner reviewed `/` and a member page again, said no, and gave
eight fixes: seven applied and green, item 3 built but needing one approval (below). His
look is still the open acceptance item; Phase 3 waits on it.

## Live facts
1. **The Congress 119 backfill is STILL RUNNING** (pids 45316/47388). Dirty `data/bills/` is
   its output — do not clean, commit, or gate while it runs. The regenerate trio is owed;
   until then two export tests go red on stale derived data, the only pytest red.
2. **Build: ~16,500 of the 20,000 free-plan file limit**, 13,111 pages. All seven `test:*`
   gates green, 64 e2e green, ruff clean, banned-words 0. **Lighthouse unverified** — it
   dies locally on a Windows temp-dir permission error, and gates CI on push.
3. **A false number was being published and is fixed.** A passage line took the tally of ANY
   roll call on that bill that day, so `s4668-119` carried an amendment's 96-1 as its passage
   margin. A tally may now only be a measure's margin when that roll resolved it (§2).
4. **New in §2, five decisions:** recorded roll calls lead "In Congress" above what became law
   (the owner gave a choice and left the pick to me — reversible); the resolving-roll rule;
   a fixed meaning line on every vote row from `site/src/lib/motions.ts` (100% of 3,519 roll
   calls, gated by `npm run test:motions`, published at `/methods#motions`); the restructured
   homepage; a two-line title clamp. Nav label "Members"; the route stays `/federal`.
5. **"This week" was NOT shipped as a heading, deliberately.** A 7-day window from the
   record's last date (2026-10-05) holds 1 enacted measure and ZERO recorded roll calls; the
   14-day window holds 8 and 2. The band keeps 14 days and prints its exact dates.
6. **Phase 5 owns upcoming floor votes** (§5 task 5): this week's and next week's scheduled
   votes go at the TOP of In Congress. Gated on Q-D. Nothing claims a vote date today.
## The backfill: check, stop, relaunch
Alive? (PowerShell; judge by the command line, not the process name):
```
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*bill-activity*' } | Select-Object ProcessId,CreationDate
```
Relaunch if dead (owner-approved, do not ask): `nohup uv run ingest bill-activity --congress 119 > backfill-119.log 2>&1 &`

Before any gate run or data commit, in order (stopping is safe; resume is free):
`Stop-Process -Id <pid> -Force` (PowerShell tool; the Bash sandbox refuses it) → `uv run ingest
events && uv run ingest topics && uv run export` → `uv run verify-recompute` → `uv run ruff
check .` → the pytest gate below → `cd site && npm run build` + its `test:*` scripts → commit
`data/` → relaunch. Pytest needs ~4 GB and ~22 min, not beside the build.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov-branch --cov-fail-under=100
```
## Owed by a human (owner)
1. **Approve the motion table** (at `/methods#motions`) and **one fetch**: `uv run ingest
   vote-amendments` reads 637 House amendment rolls from the Clerk's XML, 1 req/sec, ~11 min.
   Until it runs, House amendment rows name no amendment (review item 3).
2. **Look at `/` and a member page again; say yes or no.** Last P2 acceptance item.
3. **P1 and P2 are committed, unpushed.** Run both gates before pushing.
4. Workers Paid ($5/mo), deferred to Phases 6–7; Turnstile + Email Sending (Phase 7);
   archive.org keys (Phase 3); §7 answers as each phase arrives.
