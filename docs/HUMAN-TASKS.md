# HUMAN-TASKS.md — status table

Human-only tasks (§1). Each blocks the increment named. The builder does
everything possible around a block (code path + `.env.example` stub + this
table) and moves to the next unblocked increment (§0.2). Status is updated as
the owner completes each task.

| # | Task | Blocks | Status | Instructions |
|---|------|--------|--------|--------------|
| **H1** | Register Congress.gov / api.data.gov API key | INC-1 | ✅ done | https://api.congress.gov/sign-up/ → key by email → `.env` `CONGRESS_API_KEY` + GitHub repo secret of same name |
| **H2** | Register LegiScan API key | INC-1 (state verdict only) | ✅ done | Key in `.env` (added mid-INC-1). Spike confirmed LegiScan carries per-person MS positions with `people_id`s (GO-positive). Formal GO gate (Journal PDF cross-check) deferred to INC-12 branch A per D18. See `data/quality/ms-state-verdict.md`. |
| **H3** | Create public GitHub repo + add secrets | INC-0 (push / CI) | ✅ done | Suggest name `civic-ledger`. Secrets: `CONGRESS_API_KEY`, `LEGISCAN_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `IA_S3_ACCESS`, `IA_S3_SECRET` |
| **H4** | Cloudflare account + **Workers** project (Static Assets) via Workers Builds | INC-9 (deploy), INC-16 | ✅ done | **Workers** (not Pages — Cloudflare deprecated the Pages git-integration flow). Repo connected via **Workers Builds**: project root `site/`, build `npm run build`, deploy `npx wrangler deploy` (default); the committed `site/wrangler.jsonc` serves `./dist` (`assets.directory`). A push auto-builds + deploys — **no `CLOUDFLARE_*` secret in GitHub CI** (Cloudflare's GitHub App triggers builds directly on the `push` webhook). Confirmed live. `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` are still needed later for the INC-16 aggregates Worker's manual `wrangler deploy`, but NOT for this auto-deploy. **If branch protection is enabled on `master`, allow the `github-actions[bot]` direct push** (a ruleset bypass) — the nightly job fast-forward-commits the data diff (never `--force`). Bot-authored pushes DO trigger Workers Builds: the Cloudflare GitHub App listens on the `push` webhook, which is not subject to Actions' `GITHUB_TOKEN` self-trigger suppression (verify on the first `data: nightly …` build — its author reads `github-actions[bot]` in the Cloudflare Deployments list). |
| **H5** | Purchase domain with WHOIS privacy | INC-9 | ✅ done | `civicledger.net` (the planned `.org` was already registered by a third party). Connected as a custom domain on the Worker; confirmed live and serving the real site. Not pointed at the homelab. |
| **H6** | archive.org account + S3-like API keys | INC-11 | ⬜ pending — **optional; tool works without it** | https://archive.org/account/s3.php → `IA_S3_ACCESS` / `IA_S3_SECRET` in `.env`. Raises the SPN capture rate limit (`Authorization: LOW …`). Without it the curation tool still captures, verifies, and saves — it just honors the ≤ 1 capture / 15 s unauthenticated ceiling. Header-only; never in a URL or log. |
| **H7** | FEC API key (optional INC-10b) | INC-10b | ⬜ pending | Same api.data.gov key usually works; else https://api.open.fec.gov → `FEC_API_KEY` |
| **H8** | Statement watchlist + curation (recurring) | INC-11 content | ⬜ pending — **tool shipped** | INC-11 build is green: run `uv run curate app` (loopback-only Flask app) → Statements tab → paste a verbatim quote + source URL → Capture (SPN2, verified) → Save (staged for commit). The owner selects, enters, assigns specificity + stance, and approves EVERY statement; nothing is builder-authored. Pairing is by bill id (edit `data/statements/_title_allowlist.yaml` for short titles, then `uv run curate statements repair`). Symmetry CI flags imbalance once the per-member median hits 5; banned-words scans all curated text; the weekly archive-links sweep withholds any statement whose capture dies. Phase-3 acceptance (20+ statements, ≥5 pairs, symmetry green, links live) is this recurring content task. |
| **H9** | Absence-explanation approvals (recurring) | INC-6 content | ⬜ pending — tool shipped, **1 candidate queued** | `uv run curate absences search` populates the queue (currently: Guest, `h-118-1-0031`, "would have voted YEA", verbatim in `data/quality/absence-queue/`). Owner runs `uv run curate absences approve` (interactive y/n/edit) or `... approve --granule <id>` to publish the verbatim reason + CREC source onto the Absence. Nothing publishes unapproved (INC-6 build is green; the ≥1-approved-example acceptance is this task). |
| **H10** | Candidate list + specificity scoring (recurring) | INC-13 content | ⬜ pending | Curate declared-candidate YAML from MS SoS filings; score every statement on the rubric; double-score the 10% sample. |
| **H11** | Quiz question bank review (one-time + on change) | INC-14 content | ⬜ pending | Bank ships from ANES/Pew/CCES via sourcing workflow; owner reviews every item; recruits a disagreeing external reviewer for original-wording items. |
| **H12** | Warrant canary signing (recurring, monthly) | INC-16 | ⬜ pending | Update `site/src/content/canary.md` date monthly. CI warns at 35 days, fails scheduled build at 45 (never blocks a correction deploy). |
| **H13** | Byline decision (pre-launch, non-blocking) | — | ⬜ pending | Site builds unattributed (brief §10). Flip `SITE_ATTRIBUTION` in `site/config.ts` before launch if desired. |

Legend: ⬜ pending · 🟨 in progress · ✅ done

## Impact on current build (INC-0..INC-12 + member-page stats done)

**No human task blocks the current build.** H1 (Congress.gov) + H3 (repo/secrets) +
H4/H5 (Cloudflare Workers + `civicledger.net`) are done — the site is live and
auto-deploys on push. **H2 (LegiScan) is done and now fully consumed:** INC-12 branch A
built the MS state layer on it (174 legislators, 1,725 rolls; ADRs D51–D58), and the GO
gate resolved 5/5 (D21). Member pages in both jurisdictions render the Tier-2 stat tiles
(D57/D58).

The remaining human tasks are all **content/recurring or optional**, none blocking code:
- **H6** (archive.org S3 keys) — optional; the statement tool works without it.
- **H7** (FEC key) — only for the optional INC-10b funding increment.
- **H8/H9** (statement + absence content) — tools shipped; owner-curated content.
- **H10** (candidate list/scoring) — for INC-13 (Candidate Tracker), not yet built.
- **H11/H12/H13** — quiz bank review, warrant-canary signing, byline decision (later increments).

Open runtime-verification boxes (not blockers, observed on the next scheduled run): the
INC-9 first-real-data nightly commit + deploy, the R-5 raw-cache hit, and the first MS
nightly hash-gate no-op.
