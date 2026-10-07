# STATUS.md — live state (keep under 50 lines)

Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Last updated:** 2026-10-07 (builder, P1 acceptance passed).

## Current phase
**Phase 1 is done — acceptance passed 2026-10-07 and is committed.** Next is Phase 2
(homepage and member page restructure, existing data only); its open question is Q-A below.
**Nothing blocks Phase 2.**

## Live facts
1. **The Congress 119 bill-timeline backfill is RUNNING again** (relaunched 2026-10-07 after
   the P1 gates). Dirty `data/` is its output, not abandoned work — do not clean it, commit
   it, or run the gates while it runs. 17,738 of ~19,441 timelines, ~11/min: ~2.5 h left.
2. **`data/` on disk is AHEAD of what is committed, as expected.** The P1 commit is docs and
   code only; regenerated events (162,208 in 46 months), topics (973 subject terms over
   37,046 bills) and the manifest are uncommitted and go in the next data commit.
3. **Last CI run confirmed green:** 37536141049 at `ebe25c64a`. The nightly commits to `master`
   ~09:15 UTC and can reject a local push mid-gate: merge, then **regenerate** the derived
   files (events, topics, manifest), never text-merge them.
4. **Build size:** 17,011 of the 20,000-file free hosting limit, 14,267 pages. Bill pages are final at 1,040; the backfill adds data files, not pages.
5. **Two export-contract tests fail on stale derived data, not on code.** A gate run after the
   backfill has advanced needs the regenerate trio first (below), or
   `test_committed_manifest_matches_regeneration` + `test_verify_recompute_entrypoint_green`
   go red on a byte/bill-count mismatch. The trap, not a bug.

## The backfill: check, stop, relaunch
Check it is alive (PowerShell; judge by the command line, not the process name):
```
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*bill-activity*' } | Select-Object ProcessId,CreationDate
ls -lt data/bills/*-119.json | head -1     # newest file should be seconds old
```
Relaunch if dead (owner-approved, do not ask): `nohup uv run ingest bill-activity
--congress 119 > backfill-119.log 2>&1 &`

Before any gate run or data commit, in this order (stopping is safe at any moment; resume is
free): `Stop-Process -Id <pid> -Force` (PowerShell tool; the Bash sandbox refuses it) →
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute`
→ `uv run ruff check .` → the pytest gate below → `cd site && npm run build` + its `test:*`
scripts → commit `data/` → relaunch. Pytest needs ~4 GB RAM and ~22 min, not beside the build.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov-branch --cov-fail-under=100
```

## Owed by a human (owner)
1. **Q-A: the homepage intro wording** — Phase 2 task 1 cannot ship copy without it.
2. **P1 is committed, unpushed.** Pushing deploys the rewritten `/privacy`; owner's call.
3. Cloudflare Workers Paid ($5/mo): deferred by owner until the layout is right (Phases 6–7).
4. Turnstile keys and the Email Sending binding (Phase 7); archive.org S3 keys, optional (Phase 3).
5. Answers to `IMPLEMENTATIONv3.md` §7 open questions, each when its phase arrives.
