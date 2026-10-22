# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-22 (builder, copilot relaying the owner). **origin/master = `8e2cb12d2`** (CI green). **Local master is 2 commits ahead, NOT pushed:** `20f8bf8d2` (office-logistics rule dropped) and `c9d511760` (step 8 report). The gates passed on that exact code and data (`data/raw/gates.done` = `EXIT=0 all`, 10:42).
## FIRST ACTION NEXT SESSION
1. **Step 9 is BLOCKED on an owner question. No AI call has been made, and `ai.yaml` still says `per_run_cost_cap_usd: 5.00`.** Found on 2026-10-22:
   - **There is no run command.** `ingest/ai.py` makes one call at a time (cap, cache, audit log); nothing walks the survivors, picks each member's newest 25, triages them, then categorizes. Building it = a new module plus tests at 100% branch coverage (~1-2 h). The run itself is ~15,800 sequential calls (several hours, detached).
   - **Both prompts are `v0-stub`.** The categorizer stub's header says its output "may not be published, shown in the review queue as a suggestion, or counted toward precision", and §5 Phase 3 task 4 says the real prompt is tested on ≥50 hand-labeled statements BEFORE use. So the $20.94 Opus part would buy output the project's own rules cannot use yet.
   - **The triage stub lists "office logistics" as `false` by name**, so the 124 statements the owner sent to Haiku will be screened out by a category list in the prompt, not by judging their substance.
   - **Owner options:** (a) run as planned with the stubs, ~$23.81, proves the plumbing, categorizations thrown away at task 4; (b) build the driver and run TRIAGE ONLY, ~$2.87, Opus waits for task 4's prompt; (c) no spend now, Step 9 becomes task 4's first run.
2. **Push** the 2 local commits (gates already green; `git pull --rebase` first, never forced), then check CI.
3. Then whatever the owner chose in 1. **The $24.00 cap is for ONE run only**: restore 5.00 and commit it in the same session.
## Owner rulings, 2026-10-22 (do not re-litigate)
1. **Cost cap $24.00 for the ONE step 9 run**, restored to 5.00 in the same session. Replaces decision 6's $23.00.
2. **`office-logistics` rule DROPPED** (`20f8bf8d2`; ruling recorded in the `ingest/prefilter.py` docstring). `procedural` stays as accepted on 10-14. `IMPLEMENTATIONv3.md` §5 Phase 3 decision 2 still lists office logistics; that line needs amending.
3. **Manifest stamp diffs from `export` are discarded**, not committed (also 10-20).
## Step 8 result (`c9d511760`, `docs/research/2026-10-22-count-before-spend.md`)
17,012 statements (CREC 4,637 + press 12,375); 182 unreadable press bodies set aside (182 releases; the 184 entries count two Heinrich releases twice); 14,983 kept; 14,810 to triage (Haiku, $2.87); 1,000 to the categorizer (40 × 25, Opus, $20.94 worst case). **Estimate $23.81.** Only uneven step: `procedural` D 1.0% / R 3.1%, accepted 10-14. Coverage: D house 16/16, D senate 3/4 (Kim refused), R house 15/16 (Miller no list), R senate 4/4.
## Done 2026-10-22
Step 7b report `45cb7847c` (Kelly's 76 dates verified moved back a day; 0 off-by-one conflicts; Young 816 from 2023-01-03; 5 Shaheen/Rounds releases newly in the window whose own pages date them 2017-2022, flagged). `p3-unreadable-bodies` merged (`8e2cb12d2`) and pushed; worktree removed. The CREC re-run took 85 min, not ~5: the granule text pass re-fetched instead of reading the cache.
## Launch lesson
Long jobs: WMI `Win32_Process.Create`, **CreateFlags 0x210**, hidden, wrapped in `../.civic-copilot/awake.ps1`. Job scripts in `data/raw/` (gitignored): `gates.ps1` (now runs events/topics/export/verify-recompute first, and writes `START` to `gates.done` on launch), `step8.ps1`. **Stop processes only by a PID you started**: on 10-22 another session killed every `python.exe` by name and took a gates run with it.
## Current phase
**Phase 3 — Statements pipeline.** Task 1 DONE. Task 2: (a) DONE (press, 38 rows), (b) DONE (CREC 4,637 granules); pre-filter DONE; count-before-spend DONE (step 8). (c) waits on campaign URLs; (d) needs platform access. Task 3 blocked (no archive.org keys). Task 4 (real prompts, ≥50 labeled set, Q-K) not started. **Read §5 Phase 3's TEN owner decisions first.**
## Owner decisions, 2026-10-14 — all ratified, do not re-litigate
1. **Pre-filter R1-R4** (`ingest/prefilter.py` docstring); 20-drop audit (seed `20261014`) HOLDS. 2. **Extensions of Remarks KEPT**. 3. **One-liners**: no change for the pilot. 4. **`/privacy`: NO** restore. 5. **Dates**: month-only stored verbatim, NEVER matched to a single day's vote; conflicts flagged, never resolved by guesswork; stored dates are US Eastern. 6. **Spend**: superseded by the 2026-10-22 ruling above. Nothing publishes: Q-K open. 7. **Lighthouse fixes 1-3** in; **300 rows per member page KEPT**.
## Live facts
1. **THE REPO IS PUBLIC.** `ubuntu-latest` = Ubuntu 26; CI green on it. Lighthouse 0.90 is ratified §6.7; never lower it.
2. **`data/raw/` is gitignored**: the committed count reports are the only record of a walk. Press cache TTL 7 days.
3. **No statement is publishable** until `archive-links` refreshes `data/quality/archive-status.json`. Rendered fetch: six rows (`press_render.RENDER_ROWS`); CI cannot refresh them.
4. Owner source rulings (`statement-sources.yaml`): Kelly and Young collect from `press_sitemap`; Miller `no_press_source`; **only K000394 Kim is `owner_checked: false`** (bot wall).
5. AI gateway verified live (~$0.0095-$0.014 per statement); `claude-opus-5-5` / `claude-sonnet-5-5` / `claude-haiku-5-5`; no `temperature`, `effort` is the knob. **PROPOSAL, owner to decide:** `bill-activity` fetches from its last successful run, not a fixed 36 h.
## Open questions (§7) / owed by a human
**Step 9 choice (above).** **Q-K OPEN, gates publication.** **Q-C** Phase 4 bars, **Q-D** Phase 5 floor schedule. Owner owes: campaign issue-page URLs; archive.org keys (`IA_S3_ACCESS`/`IA_S3_SECRET`); `/corrections` repo claims and GitHub links, restore or not.
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` → `uv run ruff check .` → the pytest gate (~4 GB, ~26 min, never beside a site build) → `cd site && npm run build` + its seven `test:*` scripts + `npx playwright test`. `data/raw/gates.ps1` runs all of it.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov=ingest.ai --cov=ingest.pilot --cov=ingest.statements_crec --cov=ingest.prefilter --cov=ingest.statements_press --cov=ingest.press_render --cov=ingest.triage_run --cov-branch --cov-fail-under=100
```
