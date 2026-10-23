# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-23 overnight close (headless builder; copilot relaying the owner). **origin/master = `0d1276f0f`, CI green** (run 39846418012). **Branch `p3-overnight-2026-10-23` pushed, NOT merged**: full LOCAL gate green on `b106df097` (`gates.ps1` `EXIT=0 all 2026-10-23T00:06:53-05:00`: pytest 1,266 passed / 1 skipped / 100% coverage in 17.5 min; site build; eight `test:*`; Playwright 72 passed; Lighthouse not run locally). No GitHub CI run on it (`ci.yml` fires on master pushes and PRs only). **Branch `p3-labeling-set` pushed, NOT merged** (`a441d1c11`, worktree `..\Civic-Ledger-label`, untouched overnight).
## FIRST ACTION NEXT SESSION
1. **Owner reads `docs/owner-questions-2026-10-23.md`** (9 questions, builder's pick on each) **and the provisional Q-K** in `data/config/thresholds.yaml` (`categorizer_precision`, `ratified: false`, proposed by copilot 2026-10-22); ratifies or changes.
2. **The owner labels EV11–EV60** in `..\Civic-Ledger-label\docs\labeling\2026-10-22-eval-set.csv` on `p3-labeling-set`. The OWNER labels; a suggested label gets the bias flag in `notes`. Commit per batch; do not merge until the set is complete.
3. **Owner reviews `p3-overnight-2026-10-23` and decides the merge** (no merge without his OK).
4. **After labels:** `uv run ingest prompt-eval --labels <csv>` on all 60 → record precision in `docs/data-contract.md`. **Do not tune the v1 prompts on the 60** (held out).
5. **archive.org keys** (`IA_S3_ACCESS`/`IA_S3_SECRET`, owner's), then Phase 3 task 3.
## Done overnight 2026-10-23 (branch `p3-overnight-2026-10-23`)
- Task 4 (`212b7bea2`): prompts `triage_statement`/`categorize_statement` **v1** (topic = 33-area enum, specificity 1–3, priority_signal = Q-J verbatim); `ai.yaml` → v1, `config_version` 3; stale Q-E/Q-F fixed; `ingest/prompt_eval.py`; Q-K provisional bar; spec §7 Q-K row; data-contract caveat. Smoke (`10fea6609`, `2a9c6c7fa`): **10-row smoke test, not a precision measurement**, $0.1369, logged; per-row marks kept out of committed reports.
- Task 5 (`309442c17`): Review tab in `curate app` (`curation/review.py`): approve / edit / reject one at a time; blind 1 in 10; running precision from blind labels; **publish gate CLOSED** (Q-K unratified + no archive path).
- Task 6 (`af05b0786`): `ingest/priorities.py` → `data/priorities.json` (export writes, verify-recompute re-derives); Q-B bar now in `thresholds.yaml` `priorities_list`; Statement gains optional `topic`, `priority_signal`; **all 639 member pages show the Q-B empty state**; "beside how they voted" copy removed; `test:priorities` gate.
- Research: `c78beecf9` Record party gap (flag 4) = **mostly source mix** (`docs/research/2026-10-23-triage-party-gap.md`, 5 options, none chosen); `08a69c860` social access (task 2d): **Bluesky free API, archivable, but 0 official handles; YouTube free key, titles/descriptions only, 30-day refresh; X ~$0.005/post (pilot ≤ ~$576), must drop deleted posts; FB/IG/Threads need Meta verification + App Review; sampled X/FB archive copies held no text.** Prices read 2026-10-23; recheck before spend.
## Owner decisions pending
1. **Multi-topic labels:** allow a primary topic plus an optional secondary? He picked two topics on 4 of 10; the secondary sits in `notes` for now.
2. **Narrowing the banned-words check:** `test_banned_words_passes_on_clean_repo` took 1,283 s of the 31-min pytest gate (scans ~3.3 GB of `data/` + `site/dist/`, 95,778 files). It is a check rule: needs his OK.
3. Still owed: **Q-K** (gates publication), **Q-C** Phase 4 bars, **Q-D** Phase 5 floor schedule; campaign issue-page URLs; archive.org keys (`IA_S3_ACCESS`/`IA_S3_SECRET`); `/corrections` repo claims and GitHub links, restore or not. Proposal: `bill-activity` fetches from its last successful run, not a fixed 36 h.
4. New overnight: the 9 in `docs/owner-questions-2026-10-23.md`; **the Record party gap** (Phase 3 decision 4); **AES-14** / **AES-29** (not applied); social: which platforms, the X spend, deleted posts, the X "profiling" clause, archive rule vs X/FB; whether the party-gap doc's 20 quoted stub rejects stay in the repo.
5. **The Opus categorizer run** waits on the labeled-set precision and the owner's OK + a cap for that one run, restored to 5.00 the same session.
## Labeling set (`p3-labeling-set`)
60 statements, seed `20261022` (`affe3bc26`, `2af110463`; README rulings `842804137`). EV01–EV10 labeled (`a441d1c11`). EV05 onward: copilot-suggested, owner-confirmed (bias flag in notes). EV04 owner-uncertain.
## Flags to carry (observations, no verdict)
1. Review queue empty: no categorize run exists or is built. Step 9 verdicts belong to `v1-stub`; a `triage-run` now uses v1 and starts fresh (~$3.45).
2. Some press-release texts open with website clutter (address, "Email Me", phone); both v1 prompts are told to ignore it.
3. Some rejected samples read as substantive (Al Green floor remarks 2026-06-12, McCollum/Thompson resolution 2025-08-15, Ezell Katrina resolution 2025-08-29).
4. Statement record uses support/oppose + specificity 0–3; the categorizer uses for/against/mixed/none + 1–3 (owner question 7).
## How triage-run behaves
Starts at 4 in flight, ramps to `--workers` (default 96) on rate-limit headers; 429/529 halve it and wait `retry-after`; the monthly spend cap or 15 min without an answer stops it (exit 2). Cap exact (each call reserves an upper bound). Verdicts by TEXT fingerprint in `data/raw/triage/<prompt_version>.jsonl` (gitignored). Clean stop: `data/raw/triage.stop` (exit 4); exit 3 = cap.
## Owner rulings in force (do not re-litigate)
2026-10-22: step 9 = triage only; office-logistics dropped; manifest stamp diffs from `export` discarded; specificity 3 levels; topic = 33 policy areas; proposition not scored; a temporary cap change does not bump `config_version`. 2026-10-14: pre-filter R1-R4 (20-drop audit holds); Extensions of Remarks kept; one-liners unchanged; `/privacy` not restored; dates US Eastern, month-only never matched to a day's vote, conflicts flagged never guessed; per-run cap 5.00, raised only by the owner for one run; Lighthouse fixes 1-3 in, 300 rows per member page kept.
## Launch lesson
Long jobs: WMI `Win32_Process.Create`, **CreateFlags 0x210**, hidden, wrapped in `../.civic-copilot/awake.ps1`; job scripts in `data/raw/` (`gates.ps1` writes `START`/`EXIT=` to `gates.done`). **Stop processes only by a PID you started; never kill java/gradle/python/qemu by name.** With the Android emulator + Gradle sharing 15 GB RAM, pytest slows sharply.
## Current phase
**Phase 3 — Statements pipeline.** Task 1 DONE. Task 2: (a)(b) done, (c) waits on campaign URLs, (d) researched, owner decides. Task 3 blocked (archive.org keys). Task 4: prompts v1 + harness done; 60-row measurement waits on labels. Task 5 built, gated. Task 6 built, empty until approvals. Task 7 (AES-14/29) owner approval.
## Live facts
1. **THE REPO IS PUBLIC.** `ubuntu-latest` = Ubuntu 26; Lighthouse 0.90 ratified §6.7, never lower it.
2. `data/raw/` is gitignored: committed reports are the only record of a run. No statement publishes until `archive-links` refreshes `data/quality/archive-status.json`.
3. AI: `claude-opus-5-5` / `claude-sonnet-5-5` / `claude-haiku-5-5`; no `temperature`; SDK `max_retries=0`; **Build tier**. Overnight spend $0.1369; cap 5.00 untouched.
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` → `uv run ruff check .` → pytest → `cd site && npm run build` + its eight `test:*` scripts + `npx playwright test`. `data/raw/gates.ps1` runs it all.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov=ingest.ai --cov=ingest.pilot --cov=ingest.statements_crec --cov=ingest.prefilter --cov=ingest.statements_press --cov=ingest.press_render --cov=ingest.triage_run --cov=ingest.prompt_eval --cov=ingest.priorities --cov-branch --cov-fail-under=100
```
