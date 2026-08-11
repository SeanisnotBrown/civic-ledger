# HUMAN-TASKS.md — status table

Human-only tasks (§1). Each blocks the increment named. The builder does
everything possible around a block (code path + `.env.example` stub + this
table) and moves to the next unblocked increment (§0.2). Status is updated as
the owner completes each task.

| # | Task | Blocks | Status | Instructions |
|---|------|--------|--------|--------------|
| **H1** | Register Congress.gov / api.data.gov API key | INC-1 | ✅ done | https://api.congress.gov/sign-up/ → key by email → `.env` `CONGRESS_API_KEY` + GitHub repo secret of same name |
| **H2** | Register LegiScan API key | INC-1 (state verdict only) | ⬜ pending | https://legiscan.com/legiscan → free tier → `.env` / secret `LEGISCAN_API_KEY` |
| **H3** | Create public GitHub repo + add secrets | INC-0 (push / CI) | ✅ done | Suggest name `civic-ledger`. Secrets: `CONGRESS_API_KEY`, `LEGISCAN_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `IA_S3_ACCESS`, `IA_S3_SECRET` |
| **H4** | Cloudflare account + Pages project + API token | INC-9 (deploy), INC-16 | ⬜ pending | Pages project connected to repo, root `site/`, build `npm run build`, output `dist/`. Token with Pages+Workers+D1 edit → secret `CLOUDFLARE_API_TOKEN`; account ID → `CLOUDFLARE_ACCOUNT_ID` |
| **H5** | Purchase domain with WHOIS privacy | INC-9 | ⬜ pending | Any registrar with privacy default (Cloudflare Registrar). Point at Pages. **Never** point any record at the homelab. |
| **H6** | archive.org account + S3-like API keys | INC-11 | ⬜ pending | https://archive.org/account/s3.php → `IA_S3_ACCESS` / `IA_S3_SECRET`. Enables authenticated SPN. Falls back to unauthenticated until present. |
| **H7** | FEC API key (optional INC-10b) | INC-10b | ⬜ pending | Same api.data.gov key usually works; else https://api.open.fec.gov → `FEC_API_KEY` |
| **H8** | Statement watchlist + curation (recurring) | INC-11 content | ⬜ pending | `uv run curate`. Owner selects, enters, approves every statement. Symmetry CI flags imbalance. |
| **H9** | Absence-explanation approvals (recurring) | INC-6 content | ⬜ pending | Ingest queues candidate CREC excerpts; owner approves/rejects each. Nothing publishes unapproved. |
| **H10** | Candidate list + specificity scoring (recurring) | INC-13 content | ⬜ pending | Curate declared-candidate YAML from MS SoS filings; score every statement on the rubric; double-score the 10% sample. |
| **H11** | Quiz question bank review (one-time + on change) | INC-14 content | ⬜ pending | Bank ships from ANES/Pew/CCES via sourcing workflow; owner reviews every item; recruits a disagreeing external reviewer for original-wording items. |
| **H12** | Warrant canary signing (recurring, monthly) | INC-16 | ⬜ pending | Update `site/src/content/canary.md` date monthly. CI warns at 35 days, fails scheduled build at 45 (never blocks a correction deploy). |
| **H13** | Byline decision (pre-launch, non-blocking) | — | ⬜ pending | Site builds unattributed (brief §10). Flip `SITE_ATTRIBUTION` in `site/config.ts` before launch if desired. |

Legend: ⬜ pending · 🟨 in progress · ✅ done

## Impact on current build (INC-0)

INC-0 requires no human task to build. **H3** (repo + secrets) is the only one
that gates INC-0's "green in CI" clause: no GitHub remote exists yet, so CI has
not run. Local acceptance is green. Once H3 is done, push and confirm `ci.yml`
passes. Everything else (H1, H2, H4–H13) blocks later increments as tabled.
