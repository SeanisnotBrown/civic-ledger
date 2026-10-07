# STATUS.md — live state (keep under 50 lines)

Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Update before ending any
session; replace lines, never append. **Last updated:** 2026-10-07 (architect, docs only).

## Current phase
Phase 1 (docs and rule reset) — spec written, builder has not started. See `IMPLEMENTATIONv3.md` §Phases.

## Live facts
1. **A local backfill of Congress 119 bill timelines is RUNNING.** Dirty `data/` is its
   output, not abandoned work. Do not clean it, commit it, or run the gates while it runs.
   Relaunched 2026-10-07 08:14 CDT (PIDs 14644/20544 at launch; they change on restart).
   ~15,300 of ~19,400 timelines at launch, ~11/min. The 0-byte log is normal; judge off disk.
2. **Last CI run confirmed green:** 37536141049 at `ebe25c64a` (the last data push);
   `3ed943e9c` on the remote is docs-only after it. The nightly commits to `master`
   around 09:15 UTC and can reject a local push mid-gate: merge, then **regenerate**
   derived files (events, topics, manifest), never text-merge them.
3. **Build size:** 17,005 of the 20,000-file free hosting limit. Bill pages are final at
   1,040; the backfill adds data files, not pages.

## The backfill: check, stop, relaunch
Check it is alive (PowerShell; judge by the command line, not the process name):
```
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*bill-activity*' } | Select-Object ProcessId,CreationDate
ls -lt data/bills/*-119.json | head -1     # newest file should be seconds old
```
Relaunch if dead (owner-approved standing instruction, do not ask):
```
nohup uv run ingest bill-activity --congress 119 > backfill-119.log 2>&1 &
```
Before any gate run or data commit, in this order (stopping is safe at any moment;
resume is free): `Stop-Process -Id <pid> -Force` (PowerShell tool, the Bash sandbox
refuses it) → `uv run ingest events && uv run ingest topics && uv run export` →
`uv run verify-recompute` → `uv run ruff check .` → the pytest gate below →
`cd site && npm run build` + its `test:*` scripts → commit `data/` → relaunch.
Pytest needs ~4 GB free RAM and ~20 min; do not run it beside the build.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov-branch --cov-fail-under=100
```

## Owed by a human (owner)
- Cloudflare Workers Paid ($5/mo): deferred by owner until the layout is right. Unlocks email sending (Phases 6–7).
- Turnstile keys (free) and the Email Sending binding: needed when accounts ship (Phase 7).
- archive.org S3 keys (optional): raises the statement-capture rate limit (Phase 3).
- Answers to `IMPLEMENTATIONv3.md` §7 open questions, each when its phase arrives.

## Blocked
**pytest is red locally until Phase 1 task 2:** the privacy test reads `IMPLEMENTATIONv2.md`
at the repo root, now archived. Do not push until that test is fixed. Nothing else blocks Phase 1.
