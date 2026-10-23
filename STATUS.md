# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-23 ~01:10 (headless builder; copilot relaying the owner). **origin/master = `0d1276f0f`, CI green** (run 39846418012). **Branch `p3-overnight-2026-10-23` pushed, NOT merged**: the last full local gate was green on `b106df097` (pytest 1,266 passed, Playwright 72); **FULL GATE OWED again** for the owner-rulings commit (tonight: ruff, touched tests, site build + eight `test:*` only, emulator running). No GitHub CI run on the branch. **Branch `p3-labeling-set`**: the copilot is labeling there tonight; builders do not touch it or `..\Civic-Ledger-label`.
## FIRST ACTION NEXT SESSION
1. **Finish labeling EV11–EV60** on `p3-labeling-set`. NOTE: the sheet's `priority_signal` guidance ("commits them to a concrete act: introducing...") predates owner ruling 3 (2026-10-23): an act already done ("Today I introduced a bill") is NOT a priority signal. Label per ruling 3.
2. **Run the full gate** (`data/raw/gates.ps1`, emulator off) on the branch; **owner reviews `p3-overnight-2026-10-23` and decides the merge.**
3. **After labels:** `uv run ingest prompt-eval --labels <csv>` on all 60 (categorizer **v2**) → writes `data/quality/categorizer-precision.json` (the publish gate reads it) → record precision in `docs/data-contract.md`. Do not tune prompts on the 60.
4. **archive.org keys** (`IA_S3_ACCESS`/`IA_S3_SECRET`), then Phase 3 task 3.
## Owner rulings 2026-10-23 (applied on the branch; recorded in spec §2)
**Q-K RATIFIED** as written (`thresholds.yaml` `categorizer_precision`, `ratified: "2026-10-23"`). Publish gate (`curation/review.py`) now also requires the held-out measurement, for the categorizer prompt in `ai.yaml`, to clear every bar with no D/R gap flag; plus archive capture. Questions 1–9: confidence word kept; topic hints kept; **"I introduced" is not a priority signal → `categorize_statement` v2** (`config_version` 4; unmeasured); triage has no bar; review log git-ignored + private off-machine backup (push step stubbed: `review.backup_review_log`); reject reasons queued; stance for→support, against→oppose, mixed/none→blank (`review.statement_fields`); **Q-B counts current-term statements only**; **no priorities list renders until AES-14 is ratified** (`priorities_list.list_wording_ratified: false`; a qualifying member would see a "held for review" line).
## Owed by a human
1. **Create the PRIVATE GitHub repo for the review-log backup** and set `REVIEW_LOG_BACKUP_REMOTE` in `.env` (then the builder builds the push step).
2. archive.org keys (`IA_S3_ACCESS`/`IA_S3_SECRET`). 3. Campaign issue-page URLs.
## Queued (build later)
1. **Reject asks why** (takes no position / wrong member / broken text / other) — after task 3 unblocks (owner ruling 6).
## Owner decisions pending
1. **Multi-topic labels:** allow a primary topic plus an optional secondary? He picked two topics on 4 of 10; the secondary sits in `notes` for now.
2. **Narrowing the banned-words check:** `test_banned_words_passes_on_clean_repo` took 1,283 s of the 31-min pytest gate (scans ~3.3 GB of `data/` + `site/dist/`, 95,778 files). It is a check rule: needs his OK.
3. Still owed: **Q-C** Phase 4 bars, **Q-D** Phase 5 floor schedule; campaign issue-page URLs; archive.org keys (`IA_S3_ACCESS`/`IA_S3_SECRET`); `/corrections` repo claims and GitHub links, restore or not. Proposal: `bill-activity` fetches from its last successful run, not a fixed 36 h.
4. From overnight: **the Record party gap** (Phase 3 decision 4; `docs/research/2026-10-23-triage-party-gap.md`, 5 options); **AES-14** / **AES-29** (not applied); social (`docs/research/2026-10-23-social-access.md`): which platforms, the X spend, deleted posts, the X "profiling" clause, archive rule vs X/FB; whether the party-gap doc's 20 quoted stub rejects stay in the repo.
5. **The Opus categorizer run** waits on the labeled-set precision and the owner's OK + a cap for that one run, restored to 5.00 the same session.
## Labeling set (`p3-labeling-set`)
60 statements, seed `20261022` (`affe3bc26`, `2af110463`; README rulings `842804137`). EV01–EV10 labeled (`a441d1c11`). EV05 onward: copilot-suggested, owner-confirmed (bias flag in notes). EV04 owner-uncertain.
## Flags to carry (observations, no verdict)
1. Review queue empty: no categorize run exists or is built. Step 9 verdicts belong to `v1-stub`; a `triage-run` now uses v1 and starts fresh (~$3.45).
2. v1's 10-row smoke test does not carry over to categorizer v2 (unmeasured).
3. Some press-release texts open with website clutter; both prompts are told to ignore it. Some rejected samples read as substantive (Al Green 2026-06-12, McCollum/Thompson 2025-08-15, Ezell 2025-08-29).
## Owner rulings in force (do not re-litigate)
2026-10-23: Q-K ratified; questions 1–9 above. 2026-10-22: step 9 = triage only; office-logistics dropped; manifest stamp diffs from `export` discarded; specificity 3 levels; topic = 33 policy areas; proposition not scored; a temporary cap change does not bump `config_version`. 2026-10-14: pre-filter R1-R4; Extensions of Remarks kept; one-liners unchanged; `/privacy` not restored; dates US Eastern, month-only never matched to a day's vote, conflicts flagged never guessed; per-run cap 5.00, raised only by the owner for one run; Lighthouse fixes 1-3 in, 300 rows per member page kept.
## Launch lesson
Long jobs: WMI `Win32_Process.Create`, **CreateFlags 0x210**, hidden, wrapped in `../.civic-copilot/awake.ps1`; job scripts in `data/raw/` (`gates.ps1` writes `START`/`EXIT=` to `gates.done`). **Stop processes only by a PID you started; never kill java/gradle/python/qemu by name.** With the emulator + Gradle sharing 15 GB RAM, pytest slows sharply.
## Current phase
**Phase 3 — Statements pipeline.** Task 2: (a)(b) done, (c) waits on campaign URLs, (d) researched, owner decides. Task 3 blocked (archive.org keys). Task 4: prompts (triage v1, categorizer v2) + harness done; 60-row measurement waits on labels. Task 5 built, gated. Task 6 built; lists held for AES-14. Task 7 (AES-14/29) owner approval.
## Live facts
1. **THE REPO IS PUBLIC.** `ubuntu-latest` = Ubuntu 26; Lighthouse 0.90 ratified §6.7, never lower it.
2. `data/raw/` is gitignored: committed reports are the only record of a run. No statement publishes until `archive-links` refreshes `data/quality/archive-status.json`.
3. AI: `claude-opus-5-5` / `claude-sonnet-5-5` / `claude-haiku-5-5`; no `temperature`; SDK `max_retries=0`; **Build tier**. No AI calls since the $0.1369 smoke test; cap 5.00 untouched.
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` → `uv run ruff check .` → pytest → `cd site && npm run build` + its eight `test:*` scripts + `npx playwright test`. `data/raw/gates.ps1` runs it all (pytest line includes `--cov=ingest.prompt_eval --cov=ingest.priorities`, see `.github/workflows/ci.yml`).
