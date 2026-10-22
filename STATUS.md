# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-22 session close (builder, copilot relaying the owner). **origin/master = this STATUS commit** (on `84dd528fe`; gates `EXIT=0 all` 14:59, 1,193 passed). **Branch `p3-labeling-set` pushed, NOT merged** (`a441d1c11`, worktree `..\Civic-Ledger-label`).
## FIRST ACTION NEXT SESSION
1. **CI for master** (`gh run list --branch master`); if red, fix that first.
2. **The owner finishes labeling EV11–EV60** in `..\Civic-Ledger-label\docs\labeling\2026-10-22-eval-set.csv` (EV01–EV10 done, `a441d1c11`). Labels are evaluative: the OWNER labels; a builder or copilot may suggest only if the row's notes say so (bias flag). Commit per batch on `p3-labeling-set`; do not merge until the set is complete.
3. **Write the real triage and categorizer prompts** (new versions; fix the stale Q-ids then), test both against the labeled set, record precision in `docs/data-contract.md`.
4. **Only then the Opus categorizer run**: needs the owner's OK and a cap set for that one run, restored to 5.00 the same session. Q-K (precision bar) must be answered before anything categorized publishes.
## Owner decisions pending
1. **Multi-topic labels:** allow a primary topic plus an optional secondary? He picked two topics on 4 of 10; the secondary sits in `notes` for now.
2. **Narrowing the banned-words check:** `test_banned_words_passes_on_clean_repo` took 1,283 s of the 31-min pytest gate (scans ~3.3 GB of `data/` + `site/dist/`, 95,778 files). It is a check rule: needs his OK.
3. Still owed: **Q-K** (gates publication), **Q-C** Phase 4 bars, **Q-D** Phase 5 floor schedule; campaign issue-page URLs; archive.org keys (`IA_S3_ACCESS`/`IA_S3_SECRET`); `/corrections` repo claims and GitHub links, restore or not. Proposal: `bill-activity` fetches from its last successful run, not a fixed 36 h.
## Done 2026-10-22
Step 7b report (`45cb7847c`); `p3-unreadable-bodies` merged. Step 8 count-before-spend (`c9d511760`). `office-logistics` pre-filter rule dropped (owner ruling; spec amended `13e9a47f7`; triage prompt `v1-stub` judges substance, not category). `triage-run` built: concurrent, rate-limit-paced, cap-exact, resumable (`639c25cf8`). **Step 9 first-pass triage (`eedf918b0`):** 14,807 of 14,810 judged, **12,091 passed (81.7%)**, 2,716 rejected; D 82.9% / R 79.5%; **$3.45** spent; Build tier, 96 in flight, 0 rate-limited retries; 3 statements refused twice by Haiku, listed in `docs/research/2026-10-22-triage-run.md`. Cap back to 5.00.
## Labeling set (`p3-labeling-set`)
60 statements, seed `20261022` (`affe3bc26`, `2af110463`; README rulings `842804137`). **Owner rulings 2026-10-22:** specificity = 3 levels; topic = the 33 broad policy areas; proposition = reference only, NOT scored. EV05 onward: copilot-suggested, owner-confirmed (bias flag in notes). EV04 owner-uncertain.
## Flags to carry (observations, no verdict)
1. **Stale Q-ids:** `data/config/ai.yaml` (lines 8-9, 132, 140), `ingest/ai.py` docstring and `ingest/prompts/categorize_statement/v0-stub.md` say Q-E/Q-F; they mean Q-J (stated priority) / Q-K (precision bar). Editing the stub changes its hash: fix it in the new prompt version.
2. Some press-release texts open with website clutter (address, "Email Me", phone).
3. Some rejected samples read as substantive (Al Green floor remarks 2026-06-12, McCollum/Thompson resolution 2025-08-15, Ezell Katrina resolution 2025-08-29).
4. Congressional Record pass rate by party: D 83.4% (1,456/1,745) vs R 73.1% (865/1,184).
## How triage-run behaves
Starts at 4 in flight, ramps to `--workers` (default 96) on rate-limit headers; 429/529 halve it and wait `retry-after`; a 429 is never an error; the monthly spend cap or 15 min without an answer stops it (exit 2). Each call reserves an upper-bound cost first (cap exact). Verdicts keyed by TEXT fingerprint in `data/raw/triage/<prompt_version>.jsonl` (gitignored). Clean stop: `data/raw/triage.stop` (exit 4); exit 3 = cap.
## Owner rulings in force (do not re-litigate)
2026-10-22: step 9 = triage only; office-logistics dropped; manifest stamp diffs from `export` discarded; a temporary cap change does not bump `config_version`. 2026-10-14: pre-filter R1-R4 (20-drop audit holds); Extensions of Remarks kept; one-liners unchanged; `/privacy` not restored; dates stored US Eastern, month-only never matched to a day's vote, conflicts flagged never guessed; per-run cap 5.00, raised only by the owner for one run; Lighthouse fixes 1-3 in, 300 rows per member page kept.
## Launch lesson
Long jobs: WMI `Win32_Process.Create`, **CreateFlags 0x210**, hidden, wrapped in `../.civic-copilot/awake.ps1`; job scripts in `data/raw/` (`gates.ps1` runs events/topics/export/verify-recompute first, writes `START` to `gates.done`, and has `faulthandler_timeout=900` + `--durations=15`; `step9.ps1`). **Stop processes only by a PID you started; never kill java/gradle/python by name.** When the other project's Android emulator + Gradle share the 15 GB of RAM, pytest slows sharply (banned-words alone >15 min).
## Live facts
1. **THE REPO IS PUBLIC.** `ubuntu-latest` = Ubuntu 26; Lighthouse 0.90 ratified §6.7, never lower it.
2. `data/raw/` is gitignored: committed reports are the only record of a walk or run. No statement is publishable until `archive-links` refreshes `data/quality/archive-status.json`.
3. Sources (`statement-sources.yaml`): Kelly and Young via `press_sitemap`; Miller `no_press_source`; only K000394 Kim `owner_checked: false`.
4. AI: `claude-opus-5-5` / `claude-sonnet-5-5` / `claude-haiku-5-5`; no `temperature`; SDK `max_retries=0`. Account is **Build tier** (Haiku 5,000 RPM / 5M ITPM).
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` → `uv run ruff check .` → pytest (~4 GB, ~31 min) → `cd site && npm run build` + its seven `test:*` scripts + `npx playwright test`. `data/raw/gates.ps1` runs it all.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov=ingest.ai --cov=ingest.pilot --cov=ingest.statements_crec --cov=ingest.prefilter --cov=ingest.statements_press --cov=ingest.press_render --cov=ingest.triage_run --cov-branch --cov-fail-under=100
```
