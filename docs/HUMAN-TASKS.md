# HUMAN-TASKS.md — status table

Human-only tasks (§1). Each blocks the increment named. The builder does
everything possible around a block (code path + `.env.example` stub + this
table) and moves to the next unblocked increment (§0.2). Status is updated as
the owner completes each task.

| # | Task | Blocks | Status | Instructions |
|---|------|--------|--------|--------------|
| **H1** | Register Congress.gov / api.data.gov API key | INC-1 | ✅ done | https://api.congress.gov/sign-up/ → key by email → `.env` `CONGRESS_API_KEY` + GitHub repo secret of same name |
| **H2** | Register LegiScan API key | INC-1 (state verdict only) | ✅ done | Key in `.env` (added mid-INC-1). Spike confirmed LegiScan carries per-person MS positions with `people_id`s (GO-positive). Formal GO gate (Journal PDF cross-check) deferred to INC-12 branch A per D18. See `data/quality/ms-state-verdict.md`. |
| **H3** | Create GitHub repo + add secrets | INC-0 (push / CI) | ✅ done — **private, by owner decision (D59, 2026-08-13)** | Repo `civic-ledger` created and pushed, but as **private**, not the public repo the spec assumed. Found 2026-08-13; owner chose to keep it private rather than flip visibility, so site copy that claimed a public repository (`/privacy`, `/corrections`, `docs/correction-process.md`) was rewritten instead — see D59. Secrets: `CONGRESS_API_KEY`, `LEGISCAN_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `IA_S3_ACCESS`, `IA_S3_SECRET` |
| **H4** | Cloudflare account + **Workers** project (Static Assets) via Workers Builds | INC-9 (deploy), INC-16 | ✅ done | **Workers** (not Pages — Cloudflare deprecated the Pages git-integration flow). Repo connected via **Workers Builds**: project root `site/`, build `npm run build`, deploy `npx wrangler deploy` (default); the committed `site/wrangler.jsonc` serves `./dist` (`assets.directory`). A push auto-builds + deploys — **no `CLOUDFLARE_*` secret in GitHub CI** (Cloudflare's GitHub App triggers builds directly on the `push` webhook). Confirmed live. `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` are still needed later for the INC-16 aggregates Worker's manual `wrangler deploy`, but NOT for this auto-deploy. **If branch protection is enabled on `master`, allow the `github-actions[bot]` direct push** (a ruleset bypass) — the nightly job fast-forward-commits the data diff (never `--force`). Bot-authored pushes DO trigger Workers Builds: the Cloudflare GitHub App listens on the `push` webhook, which is not subject to Actions' `GITHUB_TOKEN` self-trigger suppression (verify on the first `data: nightly …` build — its author reads `github-actions[bot]` in the Cloudflare Deployments list). |
| **H5** | Purchase domain with WHOIS privacy | INC-9 | ✅ done | `civicledger.net` (the planned `.org` was already registered by a third party). Connected as a custom domain on the Worker; confirmed live and serving the real site. Not pointed at the homelab. |
| **H6** | archive.org account + S3-like API keys | INC-11 | ⬜ pending — **optional; tool works without it** | https://archive.org/account/s3.php → `IA_S3_ACCESS` / `IA_S3_SECRET` in `.env`. Raises the SPN capture rate limit (`Authorization: LOW …`). Without it the curation tool still captures, verifies, and saves — it just honors the ≤ 1 capture / 15 s unauthenticated ceiling. Header-only; never in a URL or log. |
| **H7** | FEC API key (optional INC-10b) | INC-10b | ⬜ pending | Same api.data.gov key usually works; else https://api.open.fec.gov → `FEC_API_KEY` |
| **H8** | Statement watchlist + curation (recurring) | INC-11 content | ⬜ pending — **tool shipped** | INC-11 build is green: run `uv run curate app` (loopback-only Flask app) → Statements tab → paste a verbatim quote + source URL → Capture (SPN2, verified) → Save (staged for commit). The owner selects, enters, assigns specificity + stance, and approves EVERY statement; nothing is builder-authored. Pairing is by bill id (edit `data/statements/_title_allowlist.yaml` for short titles, then `uv run curate statements repair`). Symmetry CI flags imbalance once the per-member median hits 5; banned-words scans all curated text; the weekly archive-links sweep withholds any statement whose capture dies. Phase-3 acceptance (20+ statements, ≥5 pairs, symmetry green, links live) is this recurring content task. |
| **H9** | Absence-explanation approvals (recurring) | INC-6 content | ⬜ pending — tool shipped, **1 candidate queued** | `uv run curate absences search` populates the queue (currently: Guest, `h-118-1-0031`, "would have voted YEA", verbatim in `data/quality/absence-queue/`). Owner runs `uv run curate absences approve` (interactive y/n/edit) or `... approve --granule <id>` to publish the verbatim reason + CREC source onto the Absence. Nothing publishes unapproved (INC-6 build is green; the ≥1-approved-example acceptance is this task). |
| **H10** | Candidate list + specificity scoring (recurring) | INC-13 content | ⬜ pending | Curate declared-candidate YAML from MS SoS filings; score every statement on the rubric; double-score the 10% sample. |
| **H11** | Quiz question bank review (one-time + on change) | INC-14 content | ⬜ pending | Bank ships from ANES/Pew/CCES via sourcing workflow; owner reviews every item; recruits a disagreeing external reviewer for original-wording items. |
| **H12** | Warrant canary signing (recurring, monthly) | INC-16 | ✅ void — RETIRED with the canary itself (SD-35, owner, 2026-10-05) | Nothing to sign and nothing to build: there is no canary page and no `site/src/content/canary.md`. H19 recorded the decision; this row was missed and is closed 2026-10-06. Do not reintroduce a canary — or a dated "no demand received" line — without a new dated decision. |
| **H13** | Byline decision (pre-launch, non-blocking) | — | ⬜ pending | Site builds unattributed (brief §10). Flip `SITE_ATTRIBUTION` in `site/config.ts` before launch if desired. |
| **H14** | Cloudflare Workers plan check | V2-1 | ⬜ pending | Static-asset limits (checked 2026-08-13): 20,000 files/version on Workers Free, 100,000 on Paid (raised 2025-09-02; requires wrangler ≥ 4.34.0), 25 MiB/file. V2-1's projected build is ~13k files — fits Free. When the build's file count reports ≥ 18,000 (CI prints it), decide: upgrade to Workers Paid ($5/mo) or hold state expansion. |
| **H15** | Threshold ratification (recurring) | V2-4, V2-5, V2-10 | ⬜ pending | Per IMPLEMENTATIONv2.md §0.8. The builder brings options in plain English with the reasoning; you pick; your choice is committed with its justification. Expect one sitting per increment that introduces evaluative output. |
| **H16** | Branch protection on `master` | V2-0 | ⬜ pending | GitHub → Settings → Branches → protect `master`: require CI, forbid force-push. Makes the correction-history promise (`docs/correction-process.md`) enforced rather than assumed. **The repo stays private (D59, owner decision 2026-08-13)**, and GitHub's branch-protection feature requires a paid plan on a private repo (confirmed via a live 403) — budget for that, or this task stays blocked. |
| **H17** | Turnstile site + secret keys | V2-8 | ⬜ pending | Cloudflare dashboard → Turnstile → new widget (invisible mode) → `.env` / repo secrets `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET`. |
| **H18** | Transactional email provider | V2-8 | ✅ **decided 2026-10-05 — Cloudflare Email Sending** (SD-36) | Owner chose Cloudflare over Resend/Postmark: one company instead of two sees reader email addresses, and the Workers Paid plan (H20) is required for V2-12 anyway. **Still owed by a human:** enable Email Sending on the account and create the binding/secret the Worker reads. **Accepted caveat:** 3,000 emails/month included — a daily digest exhausts that at ~100 subscribers. `/privacy` must name Cloudflare as both site deliverer and email sender. |
| **H19** | Warrant-canary decision | V2-7 | ✅ done — **RETIRED by the owner, SD-35, 2026-10-05. Nothing to click, nothing to build.** | Decide-item, plain terms in V2-7: the old canary promise ("we can't hand anything over because we hold nothing") dies once accounts exist. Options the builder will present: retire the canary idea, or reshape it ("we have received no demand as of {date}"). No canary was ever published, so retiring costs nothing visible. |
| **H20** | Cloudflare Workers Paid upgrade ($5/mo) | V2-12 (email sending needs Paid); V2-11 only if per-bill pages push the build past 18,000 files | ⬜ pending | Dashboard → Workers & Pages → Plans → Workers Paid. Unlocks Email Sending (3,000 emails/month included, verified 2026-09-23), the 100,000-file static limit, and removes the D1 free-tier daily row caps. Decide when the builder brings V2-11 task-1 numbers. |
| **H21** | Text-message alerts: spec amendment + provider | V2-13 (SMS) | ⬜ pending | Phone numbers are not yet a listed data class in §0.4.3 (SD-32 says "phone only after the owner ratifies it"). If wanted: ratify in plain terms, pick a provider (e.g. Twilio), complete its US sender registration (business identity + campaign vetting; timing/fees per provider), set `SMS_API_KEY` / sender id as secrets, and approve the consent + STOP wording. Email alerts (V2-12) do not wait on this. |
| **H22** | Topic bundles (optional) | V2-11 bundles section | ⬜ pending | Only if plan decision 4(b) is chosen: author `data/config/topic-bundles.yaml` — a plain name ("Guns") → a list of verbatim CRS subject terms — dated, like statement curation. Otherwise the site shows official terms only. |
| **H23** | Congress.gov key rate limit | V2-11 | ✅ done — **no action needed (D88, 2026-10-01)** | Measured live: the key returns `x-ratelimit-limit: 20000`. No header states the reset window, so the window is unconfirmed. `ingest/cache.py` throttles api.congress.gov to 1 request/second = 3,600/hour, so **the nightly never binds** (~1,740 requests a normal night, ~14,400 on a Sunday `--full`, both under 20,000 on any window of 4 h or more). A daily window would only matter for the one-time 155,000-request backfill, which `cache.py` would throttle through via `Retry-After`, not crash on. **The binding constraint on a normal night is wall-clock time, not the key.** No raise to request. The real budget question moved to H24 (Actions minutes): a full 38,756-bill backfill is ~43 h ≈ 2,590 CI minutes, more than a whole month's free allowance, so it must run locally and be committed. |
| **H24** | GitHub Actions minutes (private repo, free plan) | nightly (all increments) | 🟨 watch — **D86 shipped 2026-09-29** | The private repo gets 2,000 free Actions minutes/month (D59 keeps it private; owner stays on free plans, 2026-09-29). September overran (nightly ≈ 2,140 min) because the legislation ingest re-fetched everything nightly; D86 cut a normal night to ~15–45 min with one ~4 h `--full` night on Sundays (≈ 900–1,400 min/month). Nothing to click now: the allowance resets on the 1st. **If the bill email returns:** Billing & plans → Actions usage, and read which workflow grew. Escape hatches if it ever overruns again, none needed today: a self-hosted runner on the homelab (zero billed minutes), or making the repo public (unlimited; D59 says no). |

Legend: ⬜ pending · 🟨 in progress · ✅ done

## Impact on current build (INC-0..INC-12 + member-page stats done; v2 adopted 2026-08-13)

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

**Current priority (owner, 2026-09-23, SD-32): V2-11 → V2-7 → V2-8 → V2-12 →
V2-13** (`docs/plan-subscriptions-and-alerts.md`). **V2-11 is blocked by no
human task** (H23 is now closed — measured 2026-10-01, no raise needed, D88). What V2-11 now waits on is the owner's answers to plan decisions 3, 4 and 6, asked with D88's real numbers. V2-12 needs H17, H18,
H20; V2-13 SMS needs H21. H22 is optional.

**v2 human tasks (H14–H19), added at v2 adoption:** none block **V2-0**
(docs-only) except **H16**, whose click is this increment's own task-list
item — the builder verifies force-push refusal by reading the branch's
protection settings once done. **H14** (Workers file-count/plan check) blocks
**V2-1**; **H15** (threshold ratification) blocks **V2-4/V2-5/V2-10**; **H17**
(Turnstile) and **H18** (email provider) block **V2-8**; **H19** (canary
decision) blocks **V2-7**. All six are ⬜ pending. **H16 has a wrinkle found
this session: the repo is PRIVATE, and the owner has decided (D59) to keep
it that way** rather than make it public — GitHub's branch-protection
feature requires a paid plan on a private repo (confirmed via a live 403),
so H16 needs that budgeted before it can be done. Site copy that assumed a
public repository (`/privacy`, `/corrections`, `docs/correction-process.md`)
has been rewritten to match reality; `IMPLEMENTATIONv2.md` §3's "the client
is open source" line is now stale spec text — not edited here (spec changes
are the owner's call), but flagged in `docs/PROGRESS.md`.
