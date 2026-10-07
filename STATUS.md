# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-07 (builder, P2 review round 1 applied).
## Current phase
**Phase 2, second pass.** The owner reviewed `/` and a member page on 2026-10-07, said no, and
gave ten fixes; all ten are applied and every gate is green again. His look is still the open
acceptance item (below); Phase 3 waits on it.

## Live facts
1. **The Congress 119 backfill is STILL RUNNING** (relaunched 2026-10-07). Dirty `data/bills/`
   is its output — do not clean, commit, or gate while it runs. P2 touched no bill data; the
   regenerate trio is owed before any gate run (two export tests go red on stale derived data).
2. **Build: 16,464 of the 20,000 free-plan file limit**, 13,102 pages. Every push gate is green
   except **Lighthouse, which is unverified** — it dies locally on a Windows temp-dir permission
   error, not an assertion. All three changed pages grew, so the push may surface a perf hit.
3. **Review round 1, all ten applied:** "currently in office" now means a term actually covers
   the dataset's own date, not the roster's `serving` flag — 539 members, every state with two
   senators (was 555, four showing three); vote rows carry the bill's title; one state dropdown
   alphabetical by name; attendance once; one "not collected yet" line; 50 rows a page; the band
   links to `/congress`; the intro's third line is gone; order is intro → In Congress → finder
   → stats.
4. **Two decisions ratified today, in §2:** the "In Congress" ranking (consequence then
   contested, nothing by topic) and the page size (50 rows as read, in 300-row URLs — 50 per
   URL is 35,580 files, past the free limit).
5. **New data, both documented in `docs/data-contract.md`:** 618 of 639 photographs from
   `unitedstates/images` (public domain, GPO; the other 21 are unpublished upstream and show
   initials), and 3,895 committee seats across 531 members from congress-legislators, now
   re-pulled nightly behind `ingest members` because the page calls them *current*.
6. **Phase 5 owns upcoming floor votes** (§5 task 5, confirmed): this week's and next week's
   scheduled votes go at the TOP of In Congress, above what became law. Gated on Q-D (which
   schedule source to trust). Nothing on the page claims a vote date today.
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
1. **Look at `/` and one member page again; say yes or no.** Last P2 acceptance item. `cd site && npm run preview`.
2. **P1 and P2 are committed, unpushed.** Pushing deploys the new `/privacy` and homepage; run both gates first.
3. Workers Paid ($5/mo), deferred until the layout is right (Phases 6-7); Turnstile + Email Sending (Phase 7); archive.org keys (Phase 3).
4. Answers to the §7 open questions as each phase arrives — Q-D now gates the Phase 5 upcoming-votes block.
