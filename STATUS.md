# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-23 overnight (headless builder; copilot relaying the owner). **origin/master = `0d1276f0f`, CI green** (run 39846418012). **Branch `p3-overnight-2026-10-23` pushed, NOT merged** (owner rule: no merges overnight). **Branch `p3-labeling-set` pushed, NOT merged** (`a441d1c11`, worktree `..\Civic-Ledger-label`, untouched overnight).
## FIRST ACTION NEXT SESSION
1. **Owner reads `docs/owner-questions-2026-10-23.md`** (7 questions, builder's pick on each) and **ratifies or amends Q-K** (`thresholds.yaml` `categorizer_precision`, `ratified: false`, proposed by copilot 2026-10-22).
2. **FULL GATE OWED on `p3-overnight-2026-10-23`** before any merge: only ruff + the touched test files ran overnight (RAM shared with an emulator). Run `data/raw/gates.ps1` (now covers `ingest.prompt_eval`), then merge on the owner's OK.
3. **The owner finishes labeling EV11–EV60** on `p3-labeling-set` (owner labels only; a suggested label gets the bias flag in `notes`).
4. Then `uv run ingest prompt-eval --labels <csv>` on all 60 → first real precision; record it in `docs/data-contract.md`. **Do not tune the v1 prompts on the 60** (held out).
## Done overnight 2026-10-23 (branch `p3-overnight-2026-10-23`)
- `212b7bea2` task 4 part 1: prompts `triage_statement/v1.md` + `categorize_statement/v1.md` (topic = 33-area enum, specificity 1–3, priority_signal = Q-J verbatim); `ai.yaml` → v1, hashes pinned, `config_version` 3; stale Q-E/Q-F fixed; `ingest/prompt_eval.py` harness (precision per field + per party vs Q-K bar, D/R gap > 10 pts flagged, < 50 rows = "smoke test"); Q-K provisional bar in `thresholds.yaml`; spec §7 Q-K row + data-contract caveat; triage report no longer calls v1 a STUB.
- `10fea6609` **10-row smoke test, not a precision measurement** (EV01–EV10): `docs/research/2026-10-23-prompt-eval-smoke.md`. 16 calls (10 Haiku, 6 Opus), **$0.1369**, logged in `data/quality/ai-calls/2026-10.jsonl`. Run cap $0.50; ai.yaml cap stays **5.00**. `2a9c6c7fa`: per-row marks now go to a gitignored side file (next to the public labels they reveal the model's answers); `10fea6609` keeps the old table in history.
- `309442c17` task 5: Review tab in `curate app` (`curation/review.py`): one at a time, suggestion + confidence → approve / edit / reject; blind 1 in 10 (fixed seed × text fingerprint), label logged before reveal; running precision from blind labels (rolling 50, per party); **publish gate CLOSED** (Q-K unratified + no archive path for categorized statements); `export_approved` refuses and writes nothing. Tests: `tests/test_review.py`.
## Owner decisions pending
1. `docs/owner-questions-2026-10-23.md`: confidence wording; topic hints; does "I introduced" count as a priority signal; triage bar; where the review log lives; reject reasons; support/oppose ↔ for/against mapping.
2. **Q-K** ratify (gates publication). **Multi-topic labels** (primary + optional secondary?). **Narrowing the banned-words check** (1,283 s of the 31-min gate).
3. Still owed: **Q-C** Phase 4 bars, **Q-D** Phase 5 floor schedule; campaign issue-page URLs; archive.org keys (`IA_S3_ACCESS`/`IA_S3_SECRET`); `/corrections` repo claims and GitHub links. Proposal: `bill-activity` fetches from its last successful run.
## Flags to carry (observations, no verdict)
1. No categorizer run exists yet, so the review queue (`data/raw/review/queue.jsonl`) is empty; the categorize run that fills it is not built (needs owner OK + a one-run cap).
2. `Statement` model uses support/oppose + specificity 0–3; the categorizer uses for/against/mixed/none + 1–3 (owner question 7).
3. Press-release texts can open with website clutter; both v1 prompts are told to ignore it.
4. Step 9 rejects that read as substantive (Al Green 2026-06-12, McCollum/Thompson 2025-08-15, Ezell 2025-08-29); Record pass rate D 83.4% vs R 73.1%.
5. Step 9's verdicts belong to `v1-stub` (`data/raw/triage/v1-stub.jsonl`); a `triage-run` now uses v1 and starts fresh.
## Owner rulings in force (do not re-litigate)
2026-10-22: step 9 = triage only; office-logistics dropped; specificity 3 levels; topic = 33 policy areas; proposition not scored; a temporary cap change does not bump `config_version`. 2026-10-14: pre-filter R1-R4; Extensions of Remarks kept; dates US Eastern, month-only never matched to a day's vote; per-run cap 5.00, raised only by the owner for one run; Lighthouse 0.90.
## Launch lesson
Long jobs: WMI `Win32_Process.Create`, **CreateFlags 0x210**, hidden, in `../.civic-copilot/awake.ps1`; job scripts in `data/raw/` (`gates.ps1`, `step9.ps1`). **Stop processes only by a PID you started; never kill java/gradle/python/qemu by name.** With the Android emulator + Gradle sharing 15 GB RAM, pytest slows sharply.
## Current phase
**Phase 3 — Statements pipeline.** Tasks 1–2 as before ((c) waits on campaign URLs, (d) on platform access). Task 3 blocked (archive.org keys). Task 4: prompts v1 + harness done; 60-row measurement waits on labels. Task 5: dashboard built, gated. Tasks 6–7 not started.
## Live facts
1. **THE REPO IS PUBLIC.** `ubuntu-latest` = Ubuntu 26; Lighthouse 0.90 ratified §6.7.
2. `data/raw/` is gitignored: committed reports are the only record of a run. No statement publishes until `archive-links` refreshes `data/quality/archive-status.json`.
3. AI: `claude-opus-5-5` / `claude-sonnet-5-5` / `claude-haiku-5-5`; no `temperature`; SDK `max_retries=0`; **Build tier**. Spend tonight: $0.1369 of the $0.50 overnight allowance.
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` → `uv run ruff check .` → pytest (~31 min) → `cd site && npm run build` + its seven `test:*` scripts + `npx playwright test`. `data/raw/gates.ps1` runs it all.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov=ingest.ai --cov=ingest.pilot --cov=ingest.statements_crec --cov=ingest.prefilter --cov=ingest.statements_press --cov=ingest.press_render --cov=ingest.triage_run --cov=ingest.prompt_eval --cov-branch --cov-fail-under=100
```
