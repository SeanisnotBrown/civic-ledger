# STATUS.md — live state (keep under 50 lines)

Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-07 (builder, P2 gates green).
## Current phase
**Phase 2 is built; every mechanical gate passes. Acceptance is NOT complete:** its last item
is "owner looks at `/` and one member page and says yes" — owed below; Phase 3 waits on it.

## Live facts
1. **The Congress 119 backfill is STILL RUNNING** (relaunched 2026-10-07). Dirty `data/bills/`
   is its output — do not clean, commit, or gate while it runs. P2 touched no bill data;
   regenerated events/topics/manifest go in the next data commit, and until then two
   export-contract tests fail on stale derived data, not on code.
2. **Build after P2: 16,456 of the 20,000 free-plan file limit**, 13,094 pages. Member pages
   now hold 300 timeline rows a page (was 200), paying for the new bill-action rows and the
   photos — deep `/m/{id}/{n}` URLs moved as a result.
3. **Photographs: 618 of 639 members**, from `unitedstates/images` (public domain, GPO; licence
   + URL in `docs/data-contract.md`); the other 21 are unpublished upstream and show initials.
4. **Committees: 3,895 seats, 531 members**, from congress-legislators (`uv run ingest
   committees` → `data/committees/membership.json`). Added to `nightly.yml` behind `ingest
   members`: the page calls them *current*, which holds only if it re-pulls.
5. **Lighthouse is unverified** — it dies locally on a Windows temp-dir permission error, not
   an assertion. It gates CI on push, and both `/` and member page 1 grew, so the first push
   may surface a perf regression. Every other push gate was run and is green.
6. **Three P2 deviations, deliberate:** the activity filter uses **policy area** (33 official
   terms) where task 8 said bill subjects (973 will not fit a usable select — same vocabulary,
   one level up); `/privacy` keeps its prose link to `/threat-model` because
   `test_privacy_page_links_to_the_threat_model` requires it (the footer link is gone, which is
   what "hide" meant); 30 bill actions have a null `text` and are skipped, not left blank.

## The backfill: check, stop, relaunch
Alive? (PowerShell; judge by the command line, not the process name)
```
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*bill-activity*' } | Select-Object ProcessId,CreationDate
```
Relaunch if dead (owner-approved, do not ask): `nohup uv run ingest bill-activity --congress 119 > backfill-119.log 2>&1 &`

Before any gate run or data commit, in order (stopping is safe; resume is free):
`Stop-Process -Id <pid> -Force` (PowerShell tool; the Bash sandbox refuses it) →
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` →
`uv run ruff check .` → the pytest gate below → `cd site && npm run build` + its `test:*`
scripts → commit `data/` → relaunch. Pytest needs ~4 GB and ~22 min, not beside the build.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov-branch --cov-fail-under=100
```

## Owed by a human (owner)
1. **Look at `/` and one member page; say yes or no.** Last P2 acceptance item. `cd site && npm run preview`.
2. **P1 and P2 are committed, unpushed.** Pushing deploys the new `/privacy` and homepage; run both gates first.
3. Workers Paid ($5/mo), deferred until the layout is right (Phases 6-7); Turnstile + Email Sending (Phase 7); archive.org keys (Phase 3).
4. Answers to the `IMPLEMENTATIONv3.md` §7 open questions, each as its phase arrives.
