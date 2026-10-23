# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-23 overnight, third pass (headless builder; copilot relaying the owner). **origin/master = `0d1276f0f`, CI green** (run 39846418012). **Branch `p3-overnight-2026-10-23` pushed, NOT merged** (owner rule: no merges overnight; `ci.yml` runs only on master pushes and PRs, so the branch has had no GitHub CI run — the LOCAL full gate is green, below). **Branch `p3-labeling-set` pushed, NOT merged** (`a441d1c11`, worktree `..\Civic-Ledger-label`, untouched overnight).
## FIRST ACTION NEXT SESSION
1. **Owner reads `docs/owner-questions-2026-10-23.md`** (9 questions, builder's pick on each) and **ratifies or amends Q-K** (`thresholds.yaml` `categorizer_precision`, `ratified: false`, proposed by copilot 2026-10-22).
2. **Full local gate GREEN on `b106df097`** (`data/raw/gates.ps1`, `EXIT=0 all 2026-10-23T00:06:53-05:00`): events/topics/export, verify-recompute (incl. the priorities file), ruff, **pytest 1,266 passed, 1 skipped, coverage 100%** (17.5 min), site build, all eight `test:*` (`test:priorities` 639/639 empty state), **Playwright 72 passed**. Lighthouse was not run (not in gates.ps1; CI runs it). Manifest stamp diff discarded. Merge only on the owner's OK.
3. **Owner decides the Record party gap** (Phase 3 decision 4): `docs/research/2026-10-23-triage-party-gap.md`, five options, none chosen.
4. **The owner finishes labeling EV11–EV60** on `p3-labeling-set`; then `uv run ingest prompt-eval --labels <csv>` on all 60 → first real precision into `docs/data-contract.md`. **Do not tune the v1 prompts on the 60** (held out).
## Done overnight 2026-10-23 (branch `p3-overnight-2026-10-23`)
- `212b7bea2` task 4: prompts v1 (topic = 33-area enum, specificity 1–3, priority_signal = Q-J verbatim); `ai.yaml` → v1, `config_version` 3; stale Q-E/Q-F fixed; `ingest/prompt_eval.py` (precision per field + party vs the Q-K bar); Q-K provisional bar; spec §7 Q-K row; data-contract caveat. `10fea6609`/`2a9c6c7fa`: **10-row smoke test, not a precision measurement**, $0.1369 (16 calls, logged); per-row marks kept out of committed reports.
- `309442c17` task 5: Review tab in `curate app` (`curation/review.py`): one at a time, approve / edit / reject; blind 1 in 10; running precision from blind labels; **publish gate CLOSED** (Q-K unratified + no archive path); `export_approved` refuses.
- `af05b0786` task 6: `ingest/priorities.py` → `data/priorities.json` (export writes it, verify-recompute re-derives it): Q-B bar (5 approved across 3 topics, now in `thresholds.yaml` `priorities_list`) + Q-J rules (signal / 3-across-2-months / current term / both sides → none; campaign route not collected). Statement model gains optional `topic`, `priority_signal`. **All 639 member pages show the Q-B empty state** (0 approved statements); the copy promising statements "beside how they voted" is gone. `test:priorities` dist gate.
- `c78beecf9` flag 4 research (no AI): Record gap D 83.4% / R 73.1% looks **mostly source mix** — D's Record is 41% Senate amendment texts (pass ~95% both parties); Extensions = McCollum bill statements vs Perry tributes; R Senate tributes; like-for-like House floor 81.4% vs 82.8%; small unresolved residual in non-ceremonial Senate speech (D 68/86 vs R 19/31). Quotes 20 stub rejects (held-out set excluded).
- `08a69c860` task 2(d) research: **Social: Bluesky free API, archivable, but 0 official handles in congress-legislators; YouTube free (key), titles/descriptions only, 30-day refresh rule; X pay-per-use ~$0.005/post (pilot backfill ≤ ~$576), must drop deleted posts; FB/IG/Threads need Meta Business Verification + App Review; sampled archive copies of X/FB posts held no text (archive rule fails there).** Prices read 2026-10-23; recheck before any spend.
## Owner decisions pending
1. `docs/owner-questions-2026-10-23.md` (9): confidence wording; topic hints; "I introduced" as priority; triage bar; review log location; reject reasons; support/oppose ↔ for/against; what counts toward Q-B; priorities-list wording.
2. **AES-14** (priorities panel + "not collected yet" wording) and **AES-29** (one action-row pattern) — NOT applied; need owner approval. The listed-priorities wording renders for no one until statements are approved.
3. **Q-K** ratify. **Multi-topic labels.** **Narrowing the banned-words check.** Social: which platforms, the X spend, deleted posts, the X "profiling" clause, archive rule vs X/FB.
4. Still owed: **Q-C**, **Q-D**; campaign issue-page URLs; archive.org keys (`IA_S3_ACCESS`/`IA_S3_SECRET`); `/corrections` repo claims. Proposal: `bill-activity` fetches from its last successful run.
## Flags to carry (observations, no verdict)
1. Review queue empty: no categorize run exists or is built (needs owner OK + a one-run cap).
2. Step 9 verdicts belong to `v1-stub`; a `triage-run` now uses v1 and starts fresh (~$3.45).
3. Press texts can open with website clutter; both v1 prompts are told to ignore it.
## Owner rulings in force (do not re-litigate)
2026-10-22: step 9 = triage only; office-logistics dropped; specificity 3 levels; topic = 33 policy areas; proposition not scored; a temporary cap change does not bump `config_version`. 2026-10-14: pre-filter R1-R4; Extensions of Remarks kept; dates US Eastern, month-only never matched to a day's vote; per-run cap 5.00, raised only by the owner for one run; Lighthouse 0.90.
## Launch lesson
Long jobs: WMI `Win32_Process.Create`, **CreateFlags 0x210**, hidden, in `../.civic-copilot/awake.ps1`; job scripts in `data/raw/`. **Stop processes only by a PID you started; never kill java/gradle/python/qemu by name.** With the emulator + Gradle sharing 15 GB RAM, pytest slows sharply.
## Current phase
**Phase 3 — Statements pipeline.** Task 2: (a)(b) done, (c) waits on campaign URLs, (d) researched, needs owner decisions. Task 3 blocked (archive.org keys). Task 4: prompts v1 + harness done; 60-row measurement waits on labels. Task 5: built, gated. Task 6: built, empty until approvals. Task 7 (AES-14/29): owner approval.
## Live facts
1. **THE REPO IS PUBLIC.** `ubuntu-latest` = Ubuntu 26; Lighthouse 0.90 ratified §6.7.
2. `data/raw/` is gitignored: committed reports are the only record of a run. No statement publishes until `archive-links` refreshes `data/quality/archive-status.json`.
3. AI: `claude-opus-5-5` / `claude-sonnet-5-5` / `claude-haiku-5-5`; no `temperature`; SDK `max_retries=0`; **Build tier**. Overnight spend: $0.1369 of a $0.50 allowance.
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` → `uv run ruff check .` → pytest (~31 min) → `cd site && npm run build` + its eight `test:*` scripts + `npx playwright test`. `data/raw/gates.ps1` runs it all.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov=ingest.ai --cov=ingest.pilot --cov=ingest.statements_crec --cov=ingest.prefilter --cov=ingest.statements_press --cov=ingest.press_render --cov=ingest.triage_run --cov=ingest.prompt_eval --cov=ingest.priorities --cov-branch --cov-fail-under=100
```
