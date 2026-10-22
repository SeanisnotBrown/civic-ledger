# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-22 close (builder, copilot relaying the owner). **Pushed with this STATUS commit** (gates `EXIT=0 all` 14:59 on `eedf918b0`: 1,193 passed, pytest 31 min). Check CI for it first.
## FIRST ACTION NEXT SESSION
1. **CI for the push** (`gh run list --branch master`). If red, fix it before anything else.
2. **Task 4 starts: the hand-labeling set + the real prompts.** Draw a held-out set of at least 50 statements (seeded, both parties, both sources, both chambers), have the OWNER label it (labels are evaluative; the builder never authors them), then write the real triage and categorizer prompts and measure precision against the set (record it in `docs/data-contract.md`). Q-K (the precision bar) must be answered before anything categorized publishes. **The Opus categorizer waits for this; do not run it on the stubs.**
3. Owner to see before task 4: the step 9 fairness numbers below, and the 3 refused statements.
## Notes for the next session (observations, no verdict)
1. **The banned-words check is the slowest gate.** `test_banned_words_passes_on_clean_repo` scans ~3.3 GB of `data/` and `site/dist/` (95,778 files; `data/metrics.json` alone is 32 MB, and `site/dist/` repeats the event files). Narrowing what it scans would speed every gate, but it is a check rule: it needs the owner's OK.
2. **Triage observations from the step 9 samples, for writing the real prompt:**
   - Some press-release texts open with website clutter (office address, "Email Me", phone numbers).
   - Some rejected samples read as substantive: Al Green's floor remarks (2026-06-12), the McCollum/Thompson bipartisan resolution (2025-08-15), Ezell's Katrina-anniversary resolution (2025-08-29).
   - The Congressional Record pass rate differs by party: D 83.4% (1,456/1,745) vs R 73.1% (865/1,184).
## Step 9 DONE 2026-10-22 — first pass only (owner ruling: option b, no Opus)
`uv run ingest triage-run` (Haiku `v1-stub`, `ingest/triage_run.py`): 14,807 of 14,810 eligible statements judged (14,757 distinct texts); **12,091 passed (81.7%), 2,716 rejected**. Pass rate D 82.9% (7,757/9,352) vs R 79.5% (4,334/5,455); by source CREC 79.2%, press 82.3%; R Congressional Record 73.1% vs D 83.4%. 3 statements refused by Haiku twice (Y000064 CREC 2026-07-13 S3900, M001194 press "CCP threat to our food supply", H001046 CREC 2026-04-22 S2014-5): listed as failures. **Spent $3.454** = $0.1445 (sequential run, stopped) + $3.3079 (concurrent, Build tier: 5,000 RPM, ~77 verdicts/s, 0 rate-limited retries) + $0.0016 (retry). Cap restored to 5.00. Reports: `docs/research/2026-10-22-triage-run-main.md` (main run) and `-triage-run.md` (final totals). Verdicts: `data/raw/triage/v1-stub.jsonl` (gitignored, model output); call log `data/quality/ai-calls/2026-10.jsonl` (tracked).
## Owner rulings, 2026-10-22 (do not re-litigate)
1. **Step 9 = triage only**; the Opus categorizer waits for prompts tested on ≥50 hand-labeled statements. 2. **`office-logistics` pre-filter rule DROPPED**; triage prompt `v1-stub` judges substance, never category (spec amended `13e9a47f7`). 3. **Manifest stamp diffs from `export` are discarded.** 4. A temporary cap change does not bump `config_version`; the call log and STATUS are committed after a run.
## How triage-run behaves
Concurrent: starts at 4 in flight, ramps to `--workers` (default 96) on the rate-limit headers; a 429/529 halves it and waits `retry-after`; a 429 is never an error. Cap exact: each call reserves an upper-bound cost before sending. Resumable: verdicts are keyed by TEXT fingerprint (8 ASPX press sites share one `granule_id`; 4 CREC granules hold two texts). Clean stop: create `data/raw/triage.stop` (exit 4). Exit 3 = cap, 2 = API error/spend cap/stall.
## Launch lesson
Long jobs: WMI `Win32_Process.Create`, **CreateFlags 0x210**, hidden, wrapped in `../.civic-copilot/awake.ps1`. Job scripts in `data/raw/` (gitignored): `gates.ps1` (events/topics/export/verify-recompute first; writes `START` to `gates.done`), `step8.ps1`, `step9.ps1`. **Stop processes only by a PID you started; never kill java/gradle/python by name** (another project builds Android on this PC).
## Current phase
**Phase 3 — Statements pipeline.** Task 1 DONE. Task 2: (a) DONE (press, 38 rows), (b) DONE (CREC 4,637); pre-filter, count-before-spend (step 8) and first-pass triage (step 9) DONE. (c) waits on campaign URLs; (d) needs platform access. Task 3 blocked (no archive.org keys). **Task 4 next** (above). **Read §5 Phase 3's TEN owner decisions first.**
## Owner decisions, 2026-10-14 — all ratified, do not re-litigate
1. **Pre-filter R1-R4** (`ingest/prefilter.py` docstring); 20-drop audit (seed `20261014`) HOLDS. 2. **Extensions of Remarks KEPT**. 3. **One-liners**: no change for the pilot. 4. **`/privacy`: NO** restore. 5. **Dates**: month-only stored verbatim, NEVER matched to a single day's vote; conflicts flagged, never resolved by guesswork; stored dates are US Eastern. 6. **Spend**: per-run cap 5.00; raised only by the owner, for one run. Nothing publishes: Q-K open. 7. **Lighthouse fixes 1-3** in; **300 rows per member page KEPT**.
## Live facts
1. **THE REPO IS PUBLIC.** `ubuntu-latest` = Ubuntu 26; CI green on it. Lighthouse 0.90 is ratified §6.7; never lower it.
2. **`data/raw/` is gitignored**: committed reports are the only record of a walk or a run. Press cache TTL 7 days.
3. **No statement is publishable** until `archive-links` refreshes `data/quality/archive-status.json`. Rendered fetch: six rows (`press_render.RENDER_ROWS`); CI cannot refresh them.
4. Owner source rulings (`statement-sources.yaml`): Kelly and Young collect from `press_sitemap`; Miller `no_press_source`; **only K000394 Kim is `owner_checked: false`** (bot wall).
5. AI: `claude-opus-5-5` / `claude-sonnet-5-5` / `claude-haiku-5-5`; no `temperature`, `effort` is the knob; the SDK client has `max_retries=0` (triage-run paces itself). Account is **Build tier** (Haiku 5,000 RPM / 5M ITPM). **PROPOSAL, owner to decide:** `bill-activity` fetches from its last successful run, not a fixed 36 h.
## Open questions (§7) / owed by a human
**Q-K OPEN, gates publication.** **Q-C** Phase 4 bars, **Q-D** Phase 5 floor schedule. Owner owes: the task-4 labels; campaign issue-page URLs; archive.org keys (`IA_S3_ACCESS`/`IA_S3_SECRET`); `/corrections` repo claims and GitHub links, restore or not.
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` → `uv run ruff check .` → the pytest gate (~4 GB, ~26 min on a quiet machine, never beside a site build) → `cd site && npm run build` + its seven `test:*` scripts + `npx playwright test`. `data/raw/gates.ps1` runs all of it.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov=ingest.ai --cov=ingest.pilot --cov=ingest.statements_crec --cov=ingest.prefilter --cov=ingest.statements_press --cov=ingest.press_render --cov=ingest.triage_run --cov-branch --cov-fail-under=100
```
