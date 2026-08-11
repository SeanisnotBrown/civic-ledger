# decisions.md — ADR log

Spec-level decisions (D1–D18) live in `IMPLEMENTATION.md` §2 and are not
re-opened. This file records **builder** decisions made during construction:
one dated line each, per the handoff contract (§0.1c), plus the concrete
version pins §3 requires recording at INC-0.

## Version pins (recorded at INC-0, 2026-08-11)

Resolved and locked in `uv.lock` (Python) and `site/package-lock.json` (Node).

**Python** — managed 3.12.13 via uv (`.python-version` = 3.12):

| Package | Spec pin | Locked |
|---------|----------|--------|
| pydantic | ^2.7 | 2.13.4 |
| httpx | ^0.27 | 0.27.2 |
| tenacity | ^9 | 9.1.4 |
| PyYAML | ^6 | 6.0.3 |
| Flask | ^3 | 3.1.3 (curation only) |
| pytest | ^8 | 8.4.2 |
| ruff | latest | 0.16.2 |

**Node** — engine 22 LTS in CI (see 2026-08-11 deviation below):

| Package | Spec pin | Locked |
|---------|----------|--------|
| astro | ^5 | 5.18.2 |
| @astrojs/preact | — | 4.1.3 |
| preact | ^10 | 10.29.8 |
| tailwindcss | ^4 | 4.3.3 |
| @tailwindcss/vite | ^4 | 4.3.3 |
| fflate | ^0.8 | 0.8.3 |
| wrangler | ^4 | added with `worker/` at INC-16 (not needed until then) |

## Builder ADRs

- **2026-08-11 — uv installed via `pip install --user uv` (0.12.3).** The dev
  box had no uv; the standalone installer and winget were not used to keep the
  install auditable from the Python already present. uv added to user PATH.
- **2026-08-11 — Local Node is 24; CI pins Node 22 LTS (§3).** The build is
  Node-version-agnostic for Astro 5; CI uses the spec-pinned 22 for
  reproducibility. Local 24 is a tolerated dev deviation, not a project pin.
- **2026-08-11 — Tailwind v4 via `@tailwindcss/vite`, not `@astrojs/tailwind`.**
  The legacy Astro integration targets Tailwind v3; v4's Vite plugin is the
  supported path and matches the §3 pin.
- **2026-08-11 — `checks` entrypoint runs banned_words + no_llm at INC-0.** The
  data-dependent checks (symmetry, archive_links, integrity, Tier-3 guard) are
  no-ops on an empty dataset and are wired into `ingest/checks/run.py` as each
  increment implements real logic. This keeps `uv run checks` honest and green
  now without pretending checks exist that have no data to act on.
- **2026-08-11 — `no_llm.py` self-match defended two ways.** Endpoint fragments
  are assembled from concatenated string parts and the guard's own file is
  excluded from its scan; `tests/test_bootstrap.py` asserts the real scan over
  the real tree returns clean, so the guard cannot ship broken.
- **2026-08-11 — CI orders `astro build` before `uv run checks`.** §6.4 scans
  `site/dist/**`; that tree only exists after the build. Local acceptance runs
  checks before build (per the INC-0 acceptance string) where dist is simply
  absent and skipped-with-note; CI scans the real built output.

### INC-1 (2026-08-11)

- **D19 — Congress.gov members-by-state is a PATH segment `/member/{stateCode}`,
  not the spec's `?stateCode=` query param.** The query form returns HTTP 503; the
  path form returns clean JSON and `?currentMember=true` filters it to the 6 current
  MS members. Discovered in the INC-1 spike; documented in `SHAPES.md §1`. Later
  member ingest (INC-2) uses the path form.
- **2026-08-11 — Credentials are header-only (`X-Api-Key`), never in URL/params.**
  `ingest/cache.py` keys the disk cache on `sha256(url+params)` and writes a `.meta`
  sidecar with the URL; putting the key in the query would leak it into the cache key
  and into committed INC-1 samples. `ingest/spike.py::_assert_no_secret` additionally
  refuses to write any sample containing a key value. (LegiScan requires the key as a
  query param; `legiscan.py` computes its cache key/meta from op+params only, so the
  secret still never lands on disk.)
- **2026-08-11 — Hand-rolled `.env` reader (`ingest/env.py`), not python-dotenv.**
  Avoids adding a dependency (keeps `uv.lock` and the no-LLM lockfile scan simple);
  process env overrides the file so CI (secrets as env vars) and local dev both work.
- **2026-08-11 — `banned_words.py` excludes `data/quality/samples/`.** Raw upstream
  captures are verbatim government responses committed for audit/reproducibility
  (§6.2), not published fields the platform authors or frames; floor speech in a CREC
  capture can contain "contradicts" etc. §6.4 guards partisan-lean framing in rendered
  content, and nothing under `samples/` is ever rendered. Rationale in the check's
  `EXCLUDE_PREFIXES` comment.
- **2026-08-11 — Senate LIS menu and detail are in different directories.** Menu:
  `roll_call_lists/vote_menu_{c}_{s}.xml`; detail:
  `roll_call_votes/vote{c}{s}/vote_{c}_{s}_{NNNNN}.xml`. The spec's assumed
  `vote{cc}{s}/vote_menu_…` path 301-redirects to "not available". `SHAPES.md §6`.
- **2026-08-11 — CREC full-text search is via govinfo `POST /search`, not
  Congress.gov `/congressional-record` (a date index only).** Verified the govinfo
  search accepts the SAME api.data.gov key (H1) and returns 15,998 CREC hits for
  "personal explanation" with granule text/metadata links — so INC-6 has a real
  source and no risk is carried forward. `ingest/sources/govinfo.py::crec_search`;
  shapes in `SHAPES.md §5/§8`. (govinfo.py also carries the INC-19 USLM bill-text role.)
- **2026-08-11 — MS state verdict = DEFER, but feasibility is GO-positive.** H2
  (LegiScan key) was completed **mid-session**; the spike then confirmed LegiScan
  carries per-person MS positions with resolvable `people_id`s (`getRollCall` →
  `{people_id, vote_id, vote_text}`, 122 votes on a sampled roll call). The sole
  remaining GO gate — 5-bill match vs MS Journal PDFs — is deferred to INC-12
  branch A per D18/§0.4 (ship federal MVP first). Verdict stays DEFER by the binary
  rule until that cross-check runs. Evidence: `data/quality/ms-state-verdict.md`,
  `samples/legiscan_session_list_ms.json`. No other increment affected.
- **2026-08-11 — `spike.py` forces UTF-8 stdout.** §0.6 (PowerShell): status output
  uses non-cp1252 glyphs (`→`); `sys.stdout.reconfigure(encoding="utf-8")` prevents a
  `UnicodeEncodeError` crash regardless of the console codepage.
