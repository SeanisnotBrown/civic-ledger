# PROGRESS.md — Civic Alignment Platform build state

State-tracking file per `.claude` rules. Updated before ending any session.
Single source of truth for: current increment, acceptance status, blocked H-tasks.

**Last updated:** 2026-08-15, **V2-5 design pass (Nocturne)** session — in progress
(checkpoint 6, members explorer / D76).
**V2-1..V2-4 are COMPLETE and PUSHED** (through `4bb77d56`; CI green; live). V2-4 put
the first **attendance letter grades** (A–F, owner-ratified) live. **V2-5 is PARTIAL:**
the site's information architecture was rebuilt (landing dashboard + Federal/States
tabs + a filterable federal browser island) under the owner's standing authorization to
restructure and push without a per-change ask. But V2-5's own evaluative headline (the
"lowest N%" wide-eyed cut) is a NEW ratified threshold (**H15 round two**) and is
**DEFERRED to an owner sitting** — so **V2-5 stays OPEN; do not start V2-6.**
- **V2-5 DESIGN PASS (2026-08-14, IN PROGRESS) — Nocturne (owner's "Claude design"
  step).** The owner handed off `claudedesign/` (README + prototypes) — the parked
  visual-direction step — and asked to implement it: Nocturne dark theme, build-time
  charts, a multi-metric members explorer, `/compare`, and redesigned member/roll-call/
  methodology/MS views. Governance (D74, full detail in `decisions.md`): the pass is
  **design only within the still-OPEN V2-5** — it authors **no new evaluative constant**
  (colour is added *around* already-ratified V2-4 grade labels; the §6.8 grade-labels
  guard is untouched), so it needs no H15, and it does **not** close V2-5 (the "lowest
  N%" headline, H15 round two, stays owner-gated). Implementation order per the README's
  suggested sequence; committing green at each checkpoint.
  - **CHECKPOINT 1 — foundation (this commit).** `@theme` tokens + neutral-ramp remap in
    `global.css` (legacy pages carried to dark with no per-file churn; text shades kept
    ≥ WCAG-AA on ground + surface); **self-hosted Inter** (`site/public/fonts/`, latin +
    latin-ext variable woff2, OFL, preloaded, `swap`) replacing the prototype's Google
    Fonts link (§10.1); `Layout.astro` reshelled (1180px container, sticky dark nav,
    footer); `Badge.astro` recoloured (vote-class stays neutral — procedural, not
    evaluative); `MemberStats.astro` grade badge now tinted with its ratified band colour
    (colour-as-meaning reversal, D74); `MemberBrowser.tsx` controls recoloured (contract
    unchanged — drilldown intact). **Green:** `npm run build` 13,084 pages; grade-labels
    (5 pages/6 labels), metrics-sections (8+5), file-count (13,093/20,000); **e2e 31/31**
    (axe a11y + 380px on all 15 representative pages + the drill-down flow). Python suite
    unaffected (site-only). Lighthouse NOT re-run locally (CI≠local proxy, D73); the
    foundation is CSS+font only (no new JS/DOM weight), so perf delta is negligible — the
    real Lighthouse risk is the heavy redesigned views (later checkpoints), which will be
    calibrated against a known-passing baseline before commit.
  - **CHECKPOINT 2 — roll-call view + SplitBar (`44a7c59a`).** `charts/SplitBar.astro`
    (stacked position bar, contrast-adaptive inline counts). `/v/[roll]` rebuilt:
    chamber split + margin, per-party bars, tinted individual-positions grid; fixed the
    stale "Mississippi delegation" heading (member_votes has been chamber-wide since
    V2-1); absence disclosure preserved. `party_totals` typed on RollCall.
  - **CHECKPOINT 3 — overview dashboard + Histogram/BandLegend (`a17874e1`).**
    `charts/Histogram.astro` (21 index-based bins, band-coloured, index-math axis ticks;
    bins sum to 627, verified) + `charts/BandLegend.astro` (band chips → filtered federal
    list, drilldown href + verbatim labels kept). `index.astro` Nocturne hero + stat
    tiles (Members/Graded clickable; Roll calls/Individual votes non-clickable per §0.8)
    + histogram + by-class + chamber split + the single saturated States card. Every
    number derived; no new evaluative constant.
  - **CHECKPOINT 4 — two Tier-2 metrics (this commit).** `position_mix` (Yea/Nay share)
    and `cosponsor_enacted_rate` (cosponsored→law %) added to `ingest/metrics.py` +
    pydantic models — factual, no H15. Needed by the explorer + profile. metrics.json
    (10) + metrics.schema.json regenerated (manifest byte-stable). 100% branch coverage
    held on the 4 gated modules; checks (Tier-3 guard) + verify-recompute + metrics-
    sections (10) + ruff green. "Laws enacted"/"Became law" columns reuse enacted_rate.
  - **CHECKPOINT 5 — member profile + DotStrip (`0df1f1a4`).** `charts/DotStrip.astro`
    (linear distribution strip, deterministic scatter — no Math.random, byte-stable,
    focus marker). `/m/[member]` header rebuilt: identity + party dot, grade card (72px
    letter, band-colour tint, verbatim `data-grade-label`), per-CHAMBER rank line via
    `getMemberRanks().covered` (NOT 627), chamber attendance distribution strip, six fact
    tiles (incl. the new Yea/Nay share `position_mix`), state-delegation chart. Vote
    record + pagination unchanged; `MemberStats.astro` kept for MS pages. `data.ts` gains
    memoized `getGradedAttendanceByChamber()`. Percentile now renders on-page (**ADR
    D75**, reverses D69 safely — published value read verbatim, per-chamber denominator).
    Green: astro check 0, build 13,084, grade-labels, e2e 31/31 (a11y + 380px on graded
    + delegate pages). **✅ Lighthouse gate on `/m/A000055/1` (the ~440-dot DotStrip page)
    CONFIRMED GREEN — resolved 2026-08-15.** The DotStrip commit's own CI run
    (`0df1f1a4`) was cancelled when the D75 docs push superseded it, but HEAD `2192e879`
    (a superset — the DotStrip is present in its tree) ran the "Lighthouse (mobile perf +
    a11y >= 90)" step to a ✓ (CI run `31842462403`, job `site-and-checks`). CI's
    Lighthouse targets `/m/${firstMember}/1` = `/m/A000055/1`, so the real gate (the
    slower CI runner — the one that matters per D73/[[civic-ledger-ci-lighthouse-proxy]])
    passed WITH the DotStrip present. No DotStrip→SVG/bin change needed.
  - **CHECKPOINT 6 — members explorer (this commit; ADR D76).** `/federal` is now a
    multi-metric TABLE (attendance, party unity, yea share, sponsored, cosponsored,
    became-law), one row per member, static HTML + a controls-only island (chip filters,
    sortable headers, column-toggle). `lib/columns.ts` (`getExplorerColumns`) computes
    every cell + pulls each column's definition from the `ingest/metrics.py` docstring.
    **DOM budget was measured, not guessed** (the biggest risk): a throwaway 10-column
    spike hit **23,662 nodes / perf 93**; the shipped **6-column** lean table (bar as a
    `::before` pseudo = 0 nodes; value span dropped) is **10,964 nodes / perf 98, a11y
    100, CLS 0.000, TBT 0** — full CI Lighthouse config (9 URLs) green. The four extra
    metrics (nay share, laws enacted, cospon→law, percentile) stay on the member profile
    (D76 §1 — perf carve-out, no evaluative number). Kept the fraction denominator a real
    `<i>` (SR-readable/copyable) over a leaner `::after` (D76 §2). Default sort = `name`
    (static == island default → zero reorder → CLS 0 on the Lighthouse page; deviates from
    the README's attendance-desc, D76 §3). `.sub` median line 38%-opacity → neutral-500
    (WCAG-AA contrast fix the axe e2e caught, D76 §4). e2e migrated (`li`→`tr`, select→chip
    active-state; kept `#member-list`, `data-grade`, `a[href^="/m/"]`, computed visibility,
    the `?grade=A&sort=grade` deep-link) + a header-click sort test added. **DEFERRED to
    the `/compare` checkpoint:** the explorer's exclude ("set aside") + compare-select
    per-row controls (they pair with `/compare`, best injected on hydration).

  ### ▶ NEXT SESSION — start here (V2-5 Nocturne design pass, IN PROGRESS)
  - **State:** 6 checkpoints committed (`df225fa7..0df1f1a4` pushed; checkpoint 6 =
    explorer, this session). Whole site is Nocturne dark; dashboard, roll-call, member
    profile, AND the members explorer are redesigned; 2 new Tier-2 metrics landed.
    Everything green (build 13,084; grade-labels; e2e; full Lighthouse 9-URL green,
    `/federal` perf 98 / a11y 100). The DotStrip Lighthouse gate is confirmed (above).
  - **Design source:** `claudedesign/README.md` (the spec) + `Civic Ledger - Redesign.dc.html`
    (reference; read the relevant view's inline styles per screen). Tokens: `@theme` in
    `site/src/styles/global.css` (named Nocturne tokens + the neutral-ramp remap that
    carries un-redesigned pages to dark). Charts live in `site/src/components/charts/`
    (SplitBar, Histogram, BandLegend, DotStrip — pure props in, markup out).
  - **REMAINING views (README order):**
    1. ✅ **Members explorer** (`/federal`, README screen 2) — DONE, CHECKPOINT 6 / D76
       (see above). The one thing NOT yet built from screen 2: the per-row **exclude**
       ("set aside by you") + **compare-select** controls — deferred to the `/compare`
       checkpoint (they pair with it; inject them on hydration to keep the static DOM
       lean — the current static row is 17 elements, and 637 rows sit at 10,964 nodes /
       perf 98, so don't add per-row static nodes without re-measuring Lighthouse).
    2. **`/compare`** (new, README screen 4) — needs a **static-host carve-out ADR**:
       `?m=A&m=B` is invisible to a static build, so a small island reads
       `location.search` and renders from an embedded serialized `{id, metrics}` array
       (or hidden per-member fragments). Define + document the JS-off behaviour (a member
       picker) — the "everything present JS-off" acceptance can't literally hold here.
       Cap 2–4 members. The profile's "Compare with someone" button already links to
       `/compare?m={id}` (a temporary dead link until this ships). Needs a `CompareBars`
       chart (per-metric rows scaled within their own domain, domain printed). Reuse
       `lib/columns.ts` (`getExplorerColumns`) for the per-metric domains/definitions.
       Wire the explorer's compare-select here (multi-select → `/compare?m=…&m=…`).
    3. **Methodology + Mississippi** — convert `methods.astro`, `states/`, and the `ms/*`
       pages from the neutral-ramp fallback to the named Nocturne tokens (they render
       dark + a11y-green today via the ramp, but aren't "designed"). MS must NOT show the
       federal attendance grades (keep that paragraph).
  - **Not committed (owner's call):** `claudedesign/` bundle + the untracked review docs
    stay untracked — do not push without asking.
- **V2-5 (prior session, PARTIAL) — information architecture restructure (D72).** The
  old flat ~540-name landing page + two-item nav became: **four-tab nav** (Home ·
  Federal · States · Methodology, active-aware); **`/` overview dashboard** (plain-count
  coverage line — 637 members / 3,463 rolls / 966,261 votes, facts not evaluative;
  Federal/States entry cards; a NEUTRAL A→F attendance-grade distribution, each band
  deep-linking into the filtered federal list, no band promoted to a headline number —
  §0.8 held); **`/federal`** browsable all-members list via the repo's first **Preact
  island** (`MemberBrowser.tsx`, `client:visible` — the full 637-row list is SSR'd into
  static HTML so it works JS-off, is crawlable + deterministic; hydration adds
  filter/search/sort and reads `?grade/?chamber/?party/?sort/?q` for tile deep-links);
  **`/states`** thin MS card → existing `/ms` (MS URLs unchanged). **Nav-truth fixes
  (D71 family):** federal breadcrumbs Members→Federal (`/`→`/federal`); `/ms`
  breadcrumb "U.S. delegation"→"States"; 404 updated; footer **"Source" link to the
  private repo removed** (false-availability, like D71). `check-grade-labels.mjs`
  extended to scan the dashboard + federal island (regex broadened for Preact's
  `data-grade-label=""`). **DEFERRED (H15 round two, owner away):** the "lowest N%"
  wide-eyed headline is a new evaluative threshold, not made here; V2-5 stays OPEN.
  **Green:** astro check 0, build 13,084 pages, grade-labels (5 pages / 6 labels),
  metrics-sections (8+5), links (7,104), file-count (13,090/20,000), e2e **31** (incl.
  `/federal` + `/states` a11y + 380px, and the dashboard→filtered-list→member
  drill-down); `uv run checks` all-passed. Python suite unaffected (site-only).
  **Lighthouse correction (D73):** the first `/federal` build passed local Lighthouse
  but FAILED CI (run `31769853844`, `/federal` mobile perf 0.8 < 0.9 — the island
  hydrated all 637 rows). Fixed by making the roster static Astro HTML with a
  controls-only island; re-verified. Visual/design polish is the owner's separate
  later "Claude design" pass.
- **V2-4 (this session) — attendance grade (D70, owner-ratified H15 round one).**
  Propose→ratify→commit (§0.8): the owner picked, in two plain-language sittings with
  the data, to grade **attendance only** (overall composite DEFERRED — "a formula I
  will have to work on"; no unratified formula publishes); **letter grades A–F**;
  **fixed bars** A ≥99 · B ≥97 · C ≥95 · D ≥90 · F <90; **labels** Strong/Good/Fair/
  Weak/Poor; **min-service** < 50 eligible → "Too few votes to grade". Ratified values
  live in `data/config/thresholds.yaml`. `ingest/scoring.py` (Tier-3 module) →
  `data/grades/attendance.json` (627 graded, 10 excepted = delegate/min_service/
  no_record — every member graded ∪ excepted, §6.5). No wall-clock (§6.3). §6.8 guard
  rewritten prohibition→disclosure (`grades_disclosure` + `check-grade-labels.mjs`);
  `verify-recompute` inv 6; §8 gate gains scoring.py + **classify.py** (D68 paid).
  Member pages show a grade badge on the attendance tile (delegates: none — caption
  explains); `/methods` gains a Grades section. **§6.7 doctrine flipped partially**
  (only attendance graded): index/methods intros flip; MemberStats caption splits
  ("combines nothing into an overall score" stays, "draws no conclusion" flips for
  federal); metrics.py site-level "draws no conclusion" scoped (churned 2 digests →
  metrics.json regen, values unchanged, NO formula-version bump). **D71: two live
  Value-#1 falsehoods fixed** — the home page said "Mississippi delegation" while
  listing all 637 members (V2-1 miss); methods.astro claimed "source code is public"
  (false since D59). **Green:** checks 6/6 (grading-coverage + disclosure pass),
  coverage gate 100% on 4 modules, verify-recompute (grades + rankings + 3,463 rolls),
  export (10 schemas), ruff, build 13,082 pages, grade-labels/metrics-sections/
  file-count/links, e2e 26, astro check 0. (pytest full-suite: the git-history test
  goes green once the metrics.json regen is committed, as in V2-1.)
- **V2-3 (this session):** member pages' five stat tiles now show each metric's
  rank within the chamber — `"{ordinal} of {N} in the {House/Senate}"`, linking to
  the ranking methodology (`MemberStats.astro` + `getMemberRanks` in `data.ts`).
  Factual position only, NO grade/label (D69). Percentile deliberately not on the
  tile (would print "0th percentile" on worst-ranked pages + round a published
  number at render time); it stays in the JSON + `/methods`. Non-voting delegates
  show ranks only on the bill metrics + an on-page caption explaining the vote-metric
  exclusion (D66, made visible where the reader sees it). MS members unchanged (no
  MS rankings until V2-10). The `§6.7` "combines nothing into an overall score"
  caption is KEPT (flips at V2-4). e2e gains a delegate page. **Green:** `astro
  check` (0), `npm run build` (13,082 pages — V2-3 enriches pages, adds none),
  `npm run test:e2e` (26, incl. delegate a11y + 380px), `npm run test:lighthouse`
  (7 URLs, 21 runs, perf/a11y ≥ 90, exit 0 — ran cleanly locally this time),
  python suite unaffected (site-only change; still 301 green). Design in **D69**.
- **V2-2 feature (this session):** `ingest/rankings.py` → `data/rankings/
  {metric}.json` (the 5 scalar Tier-2 metrics: attendance/party_unity/
  enacted_rate as pct, sponsored/cosponsored as count), ranked WITHIN chamber,
  standard competition ranking, percentile = % of chamber strictly below, chamber
  + party means (R-vs-D and R-vs-R) rendered on `/methods`. Recomputable from
  `data/metrics.json` alone — `verify-recompute` gains invariant 5 (byte-match).
  `check-metrics-sections.mjs` extended to the ranking sections; `nightly.yml`
  regenerates rankings after metrics. **Owner decision D66:** non-voting delegates
  are ranked on the 3 bill metrics only, excluded from attendance/party-unity
  (barred from final passage — not comparable), exclusion published on `/methods`.
  Design in **D66/D67**; `data-contract.md` documents `data/rankings/`.
  **Green:** `uv run checks` (6/6), `uv run pytest` (292 passed), `uv run
  verify-recompute` (rankings recompute + 3,463 rolls), `uv run export` (9
  schemas), ruff, `npm run build` (13,082 pages), `test:metrics-sections` (8
  metrics + 5 rankings), `astro check` (0).
- **§8 coverage tooling — DONE (D68).** pytest-cov added; a CI step enforces
  **100% branch** on `ingest/metrics.py` + `ingest/rankings.py` (both driven to
  100% with real tests — no pragma-ing plumbing, no metric-body edits). Gate is a
  dedicated invocation, NOT in pytest addopts (plain/subset pytest stays fast); the
  exact command is in "How to resume" above. `classify.py` joins the gate at V2-4
  with `scoring.py` (its pure `classify()` is covered; only the live-fetch `run()`
  isn't — spec-faithful per §7 V2-2's task line naming only metrics+rankings). The
  one coverage exclusion is `if __name__ == "__main__":` (documented, §8).
- **Doctrine (§6.7):** `methods.astro:26` ("nothing is summarized, characterized,
  or scored") is KEPT — a rank is a position, not a score; it flips at V2-4 with
  grades, not now.
- **Still owner-gated / open:** P4 build.db (SD-29 vs measured "flat files fine" —
  D63, do NOT build unilaterally). V2-1's D64 (legislation truncation guard —
  10 verified genuine zeros) is in git history / decisions.md.
Previous: 2026-08-13, end of the **V2-0 —
docs-truth pass** session (plus a same-session follow-up, D59: the repo was
found private, the owner chose to keep it that way, so `/privacy` +
`/corrections` + `docs/correction-process.md` were rewritten to stop claiming
a public repository). Before that: 2026-08-13, end of the **spec v2 adoption**
session (constitutional amendment — see "Spec v2 adopted" below). Before that:
2026-08-12, end of the **member-page stats rendering** session (D57 federal +
D58 Mississippi) — the review's post-INC-12 item. (Same day, earlier: INC-12
all 6 phases; and post-review hardening round 2 — R-1/R-4/R-6/R-5.)
**Git:** INC-1..INC-12 + member-stats closed & pushed. Sequence today: R-1..R-6
(`17ea5be`/`4ef6e3b`/`65f36b7`/`92702ac`); **INC-12** six commits
(`803e3044` P1 schema/partition, `5826ac62` P2 LegiScan ingest, `14b15cab` P3 checks,
`feebe206` P4 site, `0ec9051b` P5 nightly, `8ac74cb1` P6 docs) + `9096c1b5` (PROGRESS) +
`5876f838` (e2e screenshot flake fix, non-fatal); then **member-page stats**:
`5002e641` (**D57** — render the 8 federal Tier-2 metrics as a KPI stat-tile row on member
pages, no composite/score) and `aa16914c` (**D58** — compute + render the 5 MS metrics; new
committed `data/state/ms/legislation/` from all 4,006 bills + `data/state/ms/metrics.json`).
**Local == origin/master; CI GREEN on HEAD `aa16914c`** — **live site deployed** (verified
`/m/W000437/1` and `/ms/m/ms-12068/1` both render their Record summary). Now **6 checks**
(incl. `ms`, with MS metrics recompute-and-match), **254 py tests**, ruff, verify-recompute,
Astro build (**7,919 pages**), **24/24 Playwright e2e**, Lighthouse, `astro check` 0 errors.
Classify verified byte-stable on the jurisdiction-migrated federal files (no phantom nightly
diff). The e2e 380px screenshot artifact is now fully non-fatal (a CI Chromium capture flake
had failed a passing layout check once).
**H4 + H5 DONE:** the site is **live at `civicledger.net`** via **Cloudflare Workers**
(Static Assets, deployed by **Workers Builds** on push — no `CLOUDFLARE_*` secret in GitHub
CI). Planned `.org` was taken → `.net`. Only remaining INC-9 acceptance box: observe one
untouched nightly commit + deploy on the next real data-change night (a real nightly was
**not** triggered this session — this local env has no secrets, so only GitHub Actions /
the owner's machine can run the live pipeline; confirm the first `data: nightly …` build's
author reads `github-actions[bot]`).
**Remote:** https://github.com/SeanisnotBrown/civic-ledger.git — **private, by
owner decision (D59, 2026-08-13).** Found private (not the public repo the spec
assumed) during the V2-0 session; owner chose to keep it private and have the
builder rewrite the site copy that had claimed a public repository (`/privacy`,
`/corrections`, `docs/correction-process.md`) instead of flipping visibility —
see the V2-0 section below and `docs/decisions.md` D59. Do not describe this
repo as public anywhere else in the docs or site.
**Untracked, local-only (NOT committed):** `TECHNICAL_REVIEW.md`,
`TECHNICAL_REVIEW_SUMMARY.md`, `civic-ledger-review-directive.md`, and
`PROMPT-A-fable5-spec-author.md` — the code review + directive that drove the
2026-08-12 session, and the spec-authoring prompt that drove the 2026-08-13 v2
adoption. The remediation backlog (R-1..R-6) is summarized below so it survives
even if these stay local. **Publishing them to the public repo is the owner's
call — do not commit without asking.**

> **PIPELINE ORDER (load-bearing, D24 + INC-7/8/10 + R-2/D46 + V2-2/D67):** `ingest members`
> (roster refresh FIRST — R-2, so vote coverage + unknown-member alarms read a fresh
> covered set) → `ingest {house,senate}-votes`
> → `ingest bills` → `ingest legislation` → `ingest classify` → `corrections` →
> `ingest metrics` → `ingest rankings` → `ingest grades` → `uv run export` → `uv run
> checks`. An ingest re-export resets every roll to the provisional `unclassified`, so
> **classify must run after any vote ingest**; **metrics must run after classify**
> (party-unity reads final `vote_class`) **+ after legislation**; **rankings (V2-2) and
> grades (V2-4) must run after metrics** (both derived from `data/metrics.json`; grades
> also read the ratified `data/config/thresholds.yaml`), and metrics/rankings/grades all
> run **before the nightly diff-gate** (derived — a change that only moves a rank or a
> grade must still reach the gate, D40/D67/D70); **export must run after any ingest** or
> manifest/schema drift fails. (`bills`/`legislation` are independent of classify;
> export/checks come last.)

---

## V2-1 — Federal data expansion (✅ COMPLETE — acceptance met 2026-08-13)

**Goal (unchanged from spec):** positions persisted for every serving member of
both chambers, 118th-119th; dataset fully recomputable; build scaled. Full
rationale/numbers/design in the `2cedc532` commit message and ADRs **D60-D63**
(`docs/decisions.md`). Two owner-ratified spec-adjacent decisions (fold into
`IMPLEMENTATIONv2.md` in a future session): **D61** (the 6 non-voting delegates
ARE included — excluding them broke full recomputability) and the roster-source
fix (merge `legislators-historical.yaml`, or 88 departed-118th members go
invisible to every check, reading green on a real gap).

**Scale now committed:** **637 members** (was 6), **966,261 member-vote rows**
(was 10,626), 3,463 rollcalls (4 quarantined rolls correctly publish nothing),
35,124 absence stubs sharded by congress.

**DONE + VERIFIED GREEN this session:**
- **P1-P3** (committed `2cedc532`): full roster + House (1,882/1,886, 4
  quarantined at 0.2%, 0 unexplained gaps) + Senate (1,581/1,581, 0/0) votes;
  new `ingest/coverage.py` (shared date-windowed eligibility + D61 exceptions:
  delegates, Speaker, 21-day seating-lag — all empirical/cited); `data/absences/`
  sharded by congress. Bug found+fixed: chamber-switchers invisible to their
  former chamber.
- **P5 (site) — DONE:** CI **file-count gate** (`site/scripts/check-file-count.mjs`
  → `test:file-count`, wired into `ci.yml` + `nightly.yml`, H14) — prints the
  built count, fails before the 20,000 Workers-Free limit; currently **13,082
  files, 6,918 of headroom**. `data.ts:getMemberVotes` moved from an
  O(members × rolls) per-page rescan to a one-pass memoized `Map` index (pure
  perf, identical output). Member-page pagination **NOT restructured** — file
  count is well under limit, so `PAGE_SIZE=200` stays (mechanical choice, D63).
  Site build green (13,082 pages), **24/24 e2e**, file-count gate green.
- **P6 (checks/docs) — MOSTLY DONE:** `checks/symmetry.py` + `verify_recompute.py`
  now use `coverage.py`/`expected_on()` (ingest + checks share one module, never
  drift) and the **subset (`<=`) invariant is upgraded to strict equality** —
  `member_votes` reconstructs `RollCall.totals` EXACTLY on every roll (the
  credibility payoff, D62). `checks/integrity.py` state="MS" hardcode removed —
  now cross-checks EVERY member against the clerk/detail XML (**10/10 House +
  10/10 Senate verified** against the independent official source). Quarantine
  now deletes any stale prior export (found via verify-recompute: the 4
  quarantined rolls were still publishing pre-V2-1 MS-only data). `party_unity`
  docstring flipped; manifest `covered_state` field removed (D62);
  `data/state/ms/metrics.json` + `data/manifest.json` regenerated. ADRs
  **D60-D63** written; `docs/data-contract.md` inverted (recomputability
  section + absence sharding path + member_votes scope). **`uv run checks`
  ALL PASSED; `uv run verify-recompute` green.**

**DONE this session (V2-1 finish) — the last gates closed:**
- **Federal legislation backfill COMPLETE — 637/637 members.** `ingest
  legislation` finished the 53-member tail from Congress.gov (cache-resumable).
  The exit gate flagged 10 members "no sponsored bill in congress {c}" — all
  **verified GENUINE zeros, not truncations**, and the unsound check was fixed
  (**D64**, see below). `data/metrics.json` regenerated over all 637 (the
  `sponsored`/`cosponsored` metrics count the whole 118–119 record, so e.g.
  Rubio reads 270, never a per-congress 0).
- **D64 — legislation truncation guard replaced** (commit `699f859b`). The 10
  flags were false positives of the `_sponsored_gaps` heuristic ("a served-
  congress zero can only be a broken fetch" — false). Causes: 4 served only days
  of the flagged congress (`S001197` Sasse 5d, `V000137` Vance 6d→VP, `R000595`
  Rubio 17d→State, `W000823` Waltz 17d→NSA), 4 late special-election seatings
  (`L000605`, `W000829`, `R000619`, `M001246`), 2 low-output former leaders
  (`P000197` Pelosi, `H000874` Hoyer — each 2 sponsored in 118–119, both 118th,
  **verified against the live API by a forced re-fetch**). Fix moves the Value-#1
  guard to where it is sound: `congress_gov.member_legislation` raises
  `TruncatedFetchError` on a premature-empty page (`offset < count`), and
  `legislation._count_regressions` fails on any congress that had records last
  run and now parses to zero. Catches a strict superset of the old heuristic,
  false-positives on none. Re-run after fix: exit 0, 637/637, no FAIL.
- **All acceptance gates GREEN** (working tree): `uv run checks` 6/6; `uv run
  verify-recompute` **exact** on 3,463 rolls; `uv run pytest` 282 passed (the
  git-history test flips green once the metrics commit lands — by construction);
  `uv run export`; `uv run ruff check ingest tests` (also fixed a pre-existing
  I001/E501 in house/senate_votes — commit `3851e0eb`); `npm run build` 13,082
  pages; `test:file-count` 13,086 files (6,914 under limit); `test:links` 7,104
  pages. Non-MS member page (`B001320`) renders the Tier-2 tiles with real values.
- **D65 — repo-size observation (spec V2-1 task 9):** `.git` grew 27→48 MB
  (134 MB legislation JSON packs to ~21 MB); `data/raw` (699 MB) stays gitignored.
  Well under the "few-hundred-MB" escalation line — no LFS/split, nothing for the
  owner on size.

**Still open / owner-gated (unchanged):**
- **P4 — build.db (SD-29) — NOT built; owner decision (D63).** Flat files hold
  at full scale (all gates green). SD-29 says build it at V2-1; the archived
  `inc-12-plan.md` framed adoption as trigger-based. Owner's call — do NOT build
  unilaterally, do NOT treat as done.
- **`git push`** of this session's three commits (`699f859b`, `3851e0eb`, + the
  V2-1 data commit) — private repo, owner's call whether/when to push to origin.

**Acceptance: MET.** `uv run checks` ✅ · `uv run verify-recompute` ✅ · `uv run
pytest` ✅ (post-commit) · `npm run build`/file-count/links ✅. V2-1 is the
blocking gate for V2-2/V2-5 — now clear.

---

## V2-0 — Docs-truth pass (2026-08-13) — ✅ COMPLETE

First v2 implementation increment (hand-off from `docs/kickoff-v2.md`), all 7
tasks from `IMPLEMENTATIONv2.md` §7 V2-0 done, zero behavior change:

- `docs/data-contract.md` — `named_measure_mismatch` fail-closed text (stale
  since D42 superseded D39) rewritten to describe the shipped stance-vs-
  passage-vote mechanism. The "deliberately NOT recomputable" section is
  untouched per the task (still true until V2-1).
- `CONTRIBUTING.md` — four-values paragraph replaced with the §0.4 amended
  values (evaluative-label disclosure standard, collect-minimum/encrypt-belief);
  `§6.11` → `§6.9`; both the LLM-policy and values sections now point at
  `IMPLEMENTATIONv2.md`.
- `docs/PROGRESS.md` (this file) — the stale "Current increment: INC-11"
  heading converted to `**(historical — INC-11)**` (matching the INC-10..
  INC-5 style below it); the four stale "Next: INC-N — NOT STARTED" lines
  (INC-10/INC-9/INC-8/INC-6) deleted; the stale "no CLAUDE.md file" note
  corrected; untracked-file list corrected to 4 files (added
  `PROMPT-A-fable5-spec-author.md`).
- `ingest/config.py` — module docstring's false claim of an existing
  worker↔ingest `K_ANON` equality test reworded to state the Worker (V2-8)
  doesn't exist yet.
- `docs/HUMAN-TASKS.md` — H14–H19 rows added (§1 of `IMPLEMENTATIONv2.md`);
  impact narrative refreshed with which v2 increment each blocks.
- `ingest/checks/banned_words.py` — module docstring's `IMPLEMENTATION.md`
  citation (now archived) reworded to `IMPLEMENTATIONv2.md` §6.4.
- **H16 (branch protection)** — NOT enabled; per the task, the owner does the
  click (GitHub → Settings → Branches). The builder's read-only pre-check
  (`gh api repos/.../branches/master/protection`) 403'd — see the flag below.

**Unplanned but load-bearing finding, resolved same session:** while
pre-checking H16, `gh repo view` showed the GitHub repo is **PRIVATE**,
contradicting `IMPLEMENTATIONv2.md` §3 ("the client is open source"),
`docs/correction-process.md`, and — most importantly — the LIVE site:
`site/src/pages/privacy.astro` and `corrections.astro` both asserted "the
public repository" as fact. Flagged to the owner as a possible Value #1
issue. **Owner decision (D59): keep the repo private; rewrite the site copy
instead of making it public.** Done same session: `privacy.astro` +
`corrections.astro` rewritten to drop every public-repository claim (the
corrections log itself stays genuinely public — it's rendered from
committed `data/corrections.json` regardless of repo visibility — but the
now-dead GitHub issue/commit links were removed, since a private repo 404s
them for a visitor); `docs/correction-process.md` §1 reworded (no public
issue tracker exists today — a real, currently-unbuilt gap, not decided
whether/how to fill); `docs/HUMAN-TASKS.md` H3/H16 corrected. Full detail in
`docs/decisions.md` D59. **Left alone, on purpose:** `IMPLEMENTATIONv2.md`
§3's "open source" line (spec text — the owner's call to amend, not the
builder's) and the internal (non-public-facing) "public repo" docstrings in
`ingest/verify_recompute.py`/`models.py`/`legislation.py`/`ms_metrics.py`
(lower priority — nothing rendered publicly reads them).

**Acceptance met:** `uv run checks` (6/6) + `uv run pytest` (254 passed) +
`uv run ruff check ingest tests` all green; `git status` shows only the six
files above touched, nothing under `data/`; `cd site && npm run build`
green, 7,919 pages (unchanged count — confirms zero behavior/data change).

---

## Spec v2 adopted (2026-08-13) — constitutional amendment, docs-only session

The owner amended the founding values (evaluative grading in scope; user-data
collection in scope; never-ask rule scrapped; federal-first pivot with a
dashboard landing page). This session (Fable 5, spec-author role — no code):

- **`IMPLEMENTATIONv2.md`** authored at the repo root — the sole spec going
  forward. Its §CS states what exists (don't rebuild) and what doesn't (don't
  assume); Appendix B is the disposition table proving nothing true was lost.
- **Archived unchanged via `git mv`** to `docs/archive/2026-08-13-pre-v2/`:
  `IMPLEMENTATION.md` (v1), `civic-ledger-scope.md`, `docs/inc-12-plan.md`
  (+ archive README explaining supersession).
- **ADRs SD-21..SD-31** appended to `docs/decisions.md`: the four amendments,
  the five owner-resolved decision gates (grading = category grades + fixed
  overall, SD-26; threshold propose→ratify→commit, SD-27; client-side-encrypted
  accounts, SD-28; JSON contract + build.db, SD-29; MS preserved then folded in,
  SD-30), and the SD/D renumbering that ends the D19 collision (SD-31).
- **`.claude` → `CLAUDE.md`** (git mv; the bare `.claude` filename was never
  auto-loaded by Claude Code) and rewritten for v2; `docs/kickoff-v2.md` added
  for the implementing session.
- **Verified after the moves:** `uv run pytest` 254 passed; `uv run checks`
  ALL PASSED — nothing reads the archived paths.

**V2-0 is now done — see the "V2-0 — Docs-truth pass" section above.** Next
actionable is **V2-1** (federal data expansion, the blocking gate for V2-2/
V2-5) — but it opens with a delegate/territory-coverage question that
`IMPLEMENTATIONv2.md` §0.1 flags as a MUST-ask, so it waits on the owner
(see this session's message). This ledger continues in this file (v2
increments log here, newest-first, same conventions).

---

## Post-review hardening (this session, 2026-08-12)

A code review (`TECHNICAL_REVIEW.md`, local/untracked) graded the INC-0..INC-11 build
(no Blockers; dataset verifies green) and proposed remediations **R-1..R-6** plus two
owner decisions. **Done this session:**

- **Grading reframe** (owner decision — commit `3847950`, ADRs **D19/D20** in
  IMPLEMENTATION.md): grading is transparent + **reader-adjustable** — weights live in
  the reader's browser; the site **never publishes a score it chose**. "objective"
  language removed where it implied the site grades. PAC "cost per vote" replaced with a
  donation↔vote **adjacency timeline** (adjacency, not conclusion). Guard clarifications:
  the §5 Tier-3 / INC-15 "no composite" ban is on the *build/publish* path only — the
  reader's browser may compute a grade client-side (D19). Also edited
  `civic-ledger-scope.md`. No code/data change.
- **R-3 — historical-retention scaffolding** (commit `fd9a108`, ADR **D45**):
  `data/metrics.json` now carries `schema_version` (manual formula-generation stamp) +
  per-metric `digest` (newline-normalized `sha256(source)[:16]` — formula identity, so a
  number states which formula produced it; CRLF/LF-normalized to hold D40 determinism
  cross-platform). Git is the supported metric time-series: `ingest metrics history
  <bioguide> [--metric <key>]` extracts the `(commit, generated_at, schema_version,
  metrics)` series; recompute-at-a-past-commit documented in `data-contract.md`.
  Materialized `data/metrics/history/` deferred until a trend UI needs it. Member metric
  values byte-unchanged.
- **R-2 — membership-churn resilience** (commit `f0c0f70`, ADR **D46**): nightly runs
  `ingest members` **first**; House `parse_rollcall(covered=…)` raises `UnknownMember` on
  an unrostered MS voter → quarantine → fail (parity with the Senate path); `metrics._load`
  raises on an orphan position (backstop); `symmetry.coverage_gaps` +
  `verify_recompute.check_dataset` now flag `got−expected` too; `legislation` sanity check
  relaxed to congresses the member actually **served** (pure `_sponsored_gaps`). Also
  fixed a latent `E501` in the R-3 `metrics history` help line. No data change.

### Round-2 remediations — DONE this session (R-1, R-4, R-6, R-5)

Whole review backlog (R-1..R-6) is now closed. Sequencing per the review was R-1 first
(gates H8), then R-4/R-6/R-5. None blocked INC-12.

- **R-1 (M-1/M-2/M-3/M-6) — curation hardening, GATES H8 — DONE (`17ea5be`, ADR D47):**
  (a) statement id now `{member}-{date}-{sha8(source)}-{sha6(text)}` so two different
  quotes from one source+date no longer overwrite (done now — corpus empty — so never a
  published-id migration); (b) `Statement.date` gets an ISO validator, the Flask app
  validates date+specificity at CAPTURE time (never burns an SPN save) and pops the draft
  only on a successful save; (c) single statement loader `ingest/statements_io.py` — metrics
  EXCLUDE dead-archive statements (no `named_measure_mismatch` leak through the metric side
  door), symmetry/archive_links include them, export counts records; `data.ts` is the
  documented TS mirror. `FORMULA_SCHEMA_VERSION` **1 → 2**. (d) CSRF/loopback-Origin guard
  on every curation POST. Removed zero-caller `capture_and_save`.
- **R-4 (M-4/M-5) — truth guards — DONE (`4ef6e3b`, ADR D48):** `attendance.pct → None`
  when `eligible == 0` (`AttendanceValue.pct: float | None`; metrics.schema.json → number/
  null); absence edit path is trim-only (edited reason must be a non-empty, whitespace-
  normalized substring of the verbatim CREC text). metrics.json regenerated; no current
  member value changes.
- **R-6 (L-1/L-2/L-3, §4 delete) — DONE (`65f36b7`, ADR D49):** manifest counts
  `non_position` under its own key (`other` now reads 4, not 24); `corrections.parse_log`
  keeps only `correction:`-SUBJECT commits; `bills.run` prints the fetch-failure list once;
  deleted unused `clerk_house.roll_xml`. Manifest + data-contract updated.
- **R-5 (M-7) — nightly efficiency — DONE (ADR D50):** `nightly.yml` persists `data/raw/`
  with `actions/cache` (unique-key save + `restore-keys` prefix restore; the 20h cache TTL
  handles staleness). **OPEN — runtime verification:** the first run only SAVES; the
  cache-hit skip count shows on the SECOND scheduled run.

**Round-1 remediations (prior session):** grading reframe (D19/D20), **R-3** retention
scaffolding (`fd9a108`, D45), **R-2** membership-churn resilience (`f0c0f70`, D46).

**Owner escalations parked (do NOT build without explicit reprioritization):** the
**grading engine itself** (§7 — the reader-weight UI that computes a grade over the D19
line) and **PAC funding metrics** (INC-10b, needs H7). R-3/R-2 built the *scaffolding*
for the former; the engine is a separate owner decision.

---

## Increment history (INC-5..INC-11 detail — INC-12 + v2 status is in "Spec v2
adopted" and "Post-review hardening" above)

**(historical — INC-11)**
**INC-11 — Statement ledger + curation tool + pairing — ✅ BUILD COMPLETE;
content = H8 (owner), H6 optional.**
Machinery shipped and proven end-to-end; the published corpus is **empty by design**
(a statement is an owner-selected verbatim quote with a verified archive — principle 5;
the builder never authors one, exactly as INC-6 shipped the absence pipeline with zero
published reasons). **Acceptance is split:** the BUILD acceptance (below) is met by the
builder; the CONTENT acceptance (Phase-3: 20+ statements, ≥5 pairs rendering,
per-member/party symmetry green, every archive link live, banned-words green on curated
text) is owner-gated on **H8** and is a recurring content task, not a build gap.

What shipped:
- **`Statement` model** gains owner-assigned `stated_position` (support/oppose, D42) +
  published `paired_bill_ids` (D41); `data/statements/{id}.json` + `statement.schema.json`
  + `export_statement`; manifest `counts.statements`.
- **`ingest/pairing.py`** — the SINGLE D9 resolver (bill-id form / exact
  `_title_allowlist.yaml` title / else unpaired). Curation resolves once and stores it;
  the metric layer and site READ `paired_bill_ids` and never re-resolve (D41).
- **`named_measure_mismatch` un-fails-closed** (D42): stance vs the member's own
  **passage** vote on a resolved measure; no-stance / unresolved / non-passage excluded,
  never guessed. Docstring (= methodology) rewritten → `data/metrics.json` regenerated;
  recompute-and-match still green.
- **SPN2 capture** (`ingest/sources/archive_org.py`): POST /save → poll → **HEAD-verify**
  the archive_url before it counts (value #1); mutating POST so it bypasses `cache.py`;
  IA S3 keys (H6) with unauth ≤ 1/15 s fallback. **`curation/statements.py`** save path:
  "no verified capture, no save" enforced server-side (requires a real `Capture`); pairing
  resolved at save; `git add` staging; `curate statements repair` re-resolves after an
  allowlist edit (D43).
- **`curation/app.py`** — loopback-only Flask app (`assert_loopback` refuses non-loopback;
  the Save control appears only after a verified capture) with a Statements tab and an
  Absence-approval tab that supersedes the INC-6 CLI. `curate app` / `curate statements`.
- **Site:** `getMemberTimeline` interleaves statements + votes newest-first (zero
  statements ⇒ the vote page unchanged); `StatementCard` renders a paired vote adjacent
  with ZERO relational language; new **`/pairing`** page (bright line + draws-no-conclusion)
  linked from every timeline. Dead-archive statements excluded at build via the committed
  report (D44).
- **`checks/archive_links.py`** + **`archive-links.yml`** (weekly): HEAD every archive_url;
  4xx → committed `data/quality/archive-status.json` + nonzero exit (unpublishable); 5xx /
  network → warn only. Kept OUT of the offline `uv run checks` suite.
- Design in **D41–D44**; data-contract + HUMAN-TASKS (H6 optional, H8 tool-shipped)
  updated. **187 py tests** green; ruff clean; full checks + cross-check 10/10;
  verify-recompute green; 4,540 pages build; a fixture pair renders end-to-end (statement
  + paired roll + `/pairing` link) then removed. See "INC-11 output".

**BUILD acceptance met:** curation captures→verifies→saves with no-capture-no-save enforced
server-side; loopback-only bind; pairing resolves once (D9) and both metric + site consume
it; mismatch computes stance vs passage vote; archive-links sweep flags dead links → build
excludes; symmetry statement rules live (inactive at 0); banned-words scans curated text.

**(historical — INC-10)**
**INC-10 — Metrics layer + methodology page — ✅ COMPLETE.**
Eight Tier-2 metrics (`ingest/metrics.py`, pure/offline) → **`data/metrics.json`**:
attendance, party_unity (substantive classes; majority from new aggregate
`RollCall.party_totals`; ties/procedural/absent excluded), sponsored/cosponsored,
enacted_rate (own-number "Became Public Law"), cosponsor_vote_gap (factual list, never
a score), named_measure_mismatch (fail-closed until INC-11), absence_context (same-day
participation, vote-record-only). Each metric **docstring IS the methodology** —
extracted to `metrics.json` and rendered as one section per metric on `/methods`
(`check-metrics-sections.mjs` asserts section-set == metric-key set). Backfilled bill
`subjects`/`cosponsor_ids` for all 1,011 bills; new **`data/legislation/{member}.json`**
(sponsored/cosponsored, quiet-night-safe shape); new aggregate **`party_totals`** on all
3,467 rolls (re-parsed from cache, offline). **Tier-3 AST guard** active (no metric
consumes another); **symmetry statement-balance rules activated** (vacuously green at
zero statements). verify-recompute gains a 4th invariant (party splits sum to totals) +
a full metrics recompute-and-match test. Design in **D36–D40**. **149 py tests** green;
full checks + cross-check 10/10; 4,539 pages build; metrics-sections + source-links green.
See "INC-10 output". **Acceptance met** (recompute covers every metric + matches; methods
section-set == metric-key-set; Tier-3 guard active).

**(historical — INC-9)**
**INC-9 — Automation + deploy — ✅ COMPLETE (site live; one nightly-observation box open).**
The unattended pipeline is built and CI-green. **`nightly.yml`** (cron `15 09 * * *`
UTC + `workflow_dispatch`): incremental ingest → conditional classify → corrections →
**diff-gate** → (on real change) export → site build → checks → verify-recompute →
commit `data: nightly {date}` → push. A push triggers **Cloudflare Workers Builds**
(D32, the deploy); the workflow holds no Cloudflare secret and never commits on a
failed check (last good deploy stays live). **Incremental ingest** (`incremental.py`,
D31): finalized rolls (>7d, already exported) are skipped — measured 3,454 skip / 13
refetch today — so nightly is API-polite (§0.7); recent + new rolls refresh, and a
re-fetched recent roll is restored to byte-identical by classify so it triggers no
commit (D33). **Corrections** are data (`data/corrections.json` from `git log --grep
correction:`, rendered by `/corrections`; D34) + `docs/correction-process.md`.
`/privacy` + `404.astro` stubs added; footer already carries data-last-updated. **New
gate: Lighthouse mobile perf + a11y ≥ 90** (`lighthouserc.cjs`, CI). Deploy target
moved to **Workers** (`site/wrangler.jsonc`, `assets.directory: ./dist`). Design in
**D31–D34**. See "INC-9 output".

**Owner (INC-9) — DONE:** H4 (Cloudflare **Workers** project, connected via **Workers
Builds**: root `site/`, build `npm run build`, deploy `npx wrangler deploy` default) and
H5 (domain `civicledger.net`, custom domain on the Worker) are complete — the site is
live and auto-deploys on push, no `CLOUDFLARE_*` secret in GitHub CI. Only remaining
acceptance is to **observe one untouched nightly run commit + live deploy** on the next
real data-change night. If branch protection is enabled on `master`, the
`github-actions[bot]` push needs a ruleset bypass (H4 note). Lighthouse ≥ 90 passes CI.

**(historical — INC-8)**
**INC-8 — Site MVP — ✅ COMPLETE.**
The static site renders the record: **member index** (`/`), **member detail** with a
paginated vote list (`/m/[member]/[page]`, 200 rows/page), **single-vote page**
(`/v/[roll]`), **single-bill page** (`/b/[bill]`), plus `/methods` + `/corrections`
stubs. **4,537 pages build from committed `data/**` with no network.** §6.7 copy rules
are enforced via shared components (`VoteRow`, `Badge`, `Layout`): every vote row shows
position, date, roll #, always-visible vote_class badge (neutral tooltip), verbatim
question, bill link, official-record link; absences render the verbatim reason + CREC
link or the EXACT "No explanation on record."; bill titles carry the ⓘ drafter-title
affordance; the footer carries data-last-updated (manifest) + methodology/corrections
links + build commit (`PUBLIC_BUILD_COMMIT`=CI sha). Data layer = `site/src/lib/data.ts`
(`node:fs` over `data/**`, memoized). **Bill ingest** (`ingest bills`, D27) landed first
as its own concern: 1,011 vote-referenced bills, detail-only, `subjects`/`cosponsor_ids`
deferred to INC-10 as `None` (schema widened to `list[str] | None`); 0 quarantined.
Acceptance enforced by 3 CI gates (D30): `astro build` offline; `check-source-links.mjs`
(4,478 vote/bill pages each cite their `source_url`); Playwright `@axe-core` WCAG2 A/AA +
380px no-overflow on 6 representative pages. Design in **D27–D30**. See "INC-8 output".

**(historical — INC-7)**
**INC-7 — JSON export contracts — ✅ COMPLETE.**
The published dataset is now a stable, documented, deterministic contract.
`ingest/export.py` gains `export_bill()`, JSON-Schema generation from the pydantic
models (`data/schema/{member,vote,bill,absence}.schema.json` — the vote file maps
to a composite `VoteFile` wrapper, not a bare `RollCall`), and a manifest builder.
`uv run export` is **offline** and regenerates only the DERIVED artifacts (schemas +
`data/manifest.json`) from the committed dataset — it never re-ingests (that would
reset `vote_class`, D24). The manifest is the single wall-clock/commit carrier (§6.3);
both are injected (`build_manifest(generated_at, commit)`), `main()` resolves real
UTC + `git rev-parse --short HEAD` (env overrides `CIVIC_GENERATED_AT`/`CIVIC_COMMIT`).
New `uv run verify-recompute` (`ingest/verify_recompute.py`, also a pytest test)
checks **coverage + subset + absence-reciprocity** over 100% of 3,467 rolls — the
honest recompute-and-match given MS-only `member_votes` vs chamber-wide `totals`
(**D26** resolves the D22 tension; full rationale in `docs/data-contract.md`).
`docs/data-contract.md` documents every file + field, the `non_position` special
case, the absence filename convention, and what is/isn't recomputable. Design in
**D26**. See "INC-7 output" below.

**(historical — INC-6)**
**INC-6 — Absences & personal explanations — ✅ COMPLETE (build); content = H9.**
Queue → approve → publish pipeline for stated absence reasons. `uv run curate
absences search` searches CREC (govinfo) for the covered delegation's "Personal
Explanation" insertions, **hard-verifies each byline** (`HON. {NAME}` + `of {state}`
— rejects wrong-state surname collisions like Glenn Thompson of PA), extracts the
VERBATIM statement, auto-matches the roll by **absence-stub existence** (not date
arithmetic), and parks candidates in `data/quality/absence-queue/`. `uv run curate
absences approve [--granule <id>]` (interactive y/n/edit or owner-scriptable) writes
the verbatim `stated_reason` + CREC `stated_reason_source` + `declared_position`
onto the matching Absence. **Real MS candidate set = exactly 1** (Guest, `h-118-1-0031`,
YEA), queued and committed **pending owner approval (H9)** — per principle 5 the
builder ships the tool, the owner supplies content (D25); the machinery is proven
end-to-end by a test approving the real Guest granule onto a tmp stub. `data/absences/`
stays `stated_reason: null` until the owner acts. Banned-words excludes the queue
(D25). Design in **D25**. See "INC-6 output" below.

**(historical — INC-5)**
**INC-5 — vote_class classifier (§A1) — ✅ COMPLETE.**
Total classification of all **3,447** non-`non_position` rolls (both chambers) via
an ordered pure rules table (`ingest/classify.py`): procedural 1285, passage 886,
amendment 811, nomination 447, veto_override 14, **other 4 (0.12%)**. Ships the §A1
table + sanctioned extensions from the unmapped-questions loop over real 118–119
strings; the 4 `other` are honest one-offs (treaty ratification, a conference-insist
motion, 2 division-retention votes). R-RULE splits House "On Agreeing to the
Resolution" into `procedural` (Rules-Committee-`hsru00`-reported special rules, via
a committees fetch) vs `passage` (substantive) — the split INC-10 party-unity
depends on. `classify()` is pure/offline; golden test `tests/fixtures/questions.yaml`
(52 real strings) 100% pass. New CI gate `checks/classification.py` fails on any
`unclassified` roll or other-rate > 5%. Design in **D24**. See "INC-5 output" below.

> **RESOLVED (2026-08-11): MS state verdict flipped DEFER → GO.** Owner chose
> option A — ran the 5-bill Journal cross-check now. **5/5 votes matched** (470
> per-person positions, zero mismatches; both chambers, contested votes). Evidence:
> `data/quality/ms-state-verdict.md` + `data/quality/samples/ms_vote_xcheck/`;
> rationale D21 in `decisions.md`. **INC-12 branch A is unlocked but the build
> order does NOT change — the next increment is still INC-3.** INC-12 activates
> when reached, carrying two notes: bundle the billstatus intermediate CA (CI/Linux
> has no AIA chasing), and route LegiScan through a TTL'd cache path.

---

## How to resume (read this first in a new session)

1. **`uv` is not on PATH by default in a fresh shell.** It is installed at
   `C:\Users\SB\AppData\Roaming\Python\Python314\Scripts\uv.exe` and was added
   to the **user** PATH (takes effect in new shells). If `uv` is not found:
   - PowerShell: it should be on PATH now; if not, prepend that Scripts dir.
   - Bash tool: `export PATH="$PATH:/c/Users/SB/AppData/Roaming/Python/Python314/Scripts"`.
2. **Re-verify the tree is still green before starting new work:**
   `uv run checks && uv run pytest && (cd site && npm run build)` (Bash tool —
   PowerShell 5.1 rejects `&&`). Expect (as of `f0c0f70`): **5 checks** pass
   (banned_words, no_llm, symmetry, classification, integrity), **200 tests** pass,
   ~4,540 pages built, `verify-recompute` green. Also run `uv run ruff check ingest tests`
   (CI runs ruff separately from `checks`; keep lines ≤ 100 — an `E501` reddened CI once).
   (`uv run ingest house-votes` re-syncs `data/votes/` + `data/absences/` — cached,
   re-runnable, resumes on interruption; `ingest members` / `spike` likewise cached.)
   Note: the `integrity` check makes ~10 live clerk.house.gov fetches; a clerk
   outage warns (not a failure).
   **§8 coverage gate (V2-2/V2-4, D68) — CI runs this; plain `uv run pytest` does NOT
   measure coverage (kept fast/subset-usable), so run the gate explicitly before a
   change to any of the four gated modules:**
   `uv run pytest --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov-branch --cov-fail-under=100 --cov-report=term-missing`
   (must stay 100% branch on all four). `ingest rankings` → `data/rankings/*.json` and
   `ingest grades` → `data/grades/*.json` are both pure/offline, derived from
   `data/metrics.json` (grades also read `data/config/thresholds.yaml`), run after
   `ingest metrics`.
3. Python is uv-managed **3.12.13** (system Python is 3.14; project pins 3.12 via
   `.python-version`). `uv sync --frozen` is what CI runs; lockfile is consistent.
4. **Secrets:** `.env` holds `CONGRESS_API_KEY` (H1 done) and empty
   `LEGISCAN_API_KEY` (H2 pending). `.env` is gitignored — never commit it.
   Read keys from `.env`; do not hardcode.

---

## INC-1 output (done — read `SHAPES.md` before writing any parser)

`data/quality/samples/SHAPES.md` is the **authoritative field-shape contract**
for INC-2/3/4/5/6. Key discovered deviations from IMPLEMENTATION.md's assumptions
(all in SHAPES.md + `decisions.md`):
- **Members by state = PATH `/member/{stateCode}`, NOT `?stateCode=` (503).** (D19)
- **`bioguideId` (member list) vs `bioguideID` (house-vote positions)** — case differs.
- **Senate menu & detail are in different dirs**; the spec's `vote_menu` path
  301-redirects. Menu `roll_call_lists/`, detail `roll_call_votes/vote{c}{s}/`.
- **CREC full-text search RESOLVED** — Congress.gov `/congressional-record` is a
  date index only, but **govinfo `POST /search` does full-text with the SAME
  api.data.gov key** (15,998 "personal explanation" CREC hits). INC-6 has a real
  source; no risk carried forward.
- **Crosswalk joins:** house `bioguideID`→`id.bioguide`; senate `lis_member_id`→
  `id.lis` (both in `legislators_current_ms.yaml`).

Modules created: `ingest/env.py` (`.env` reader), `ingest/cache.py` (header-auth
disk cache; **credential never in URL/key/meta**), `ingest/spike.py` (`ingest
spike`, with secret-guard), sources `congress_gov.py` / `senate_xml.py` /
`legislators.py` / `clerk_house.py` (stub) / `legiscan.py` (state, DEFER path) /
`govinfo.py` (CREC search, INC-6). Tests: `tests/test_cache.py` (6) +
`tests/test_banned_words_scope.py` (2), all offline. MS verdict: initially DEFER
at INC-1; **flipped to GO on 2026-08-11** (5/5 Journal cross-check — see the
RESOLVED callout above). 11 samples committed.

## INC-2 output (done — the schema layer INC-3+ import from)

`ingest/models.py` = the complete §5 layer. Reuse these; do not redefine records.
- **`Member`** exported to `data/members/{bioguide}.json` (6 files, committed).
  `id`=bioguide; `ids`=curated string crosswalk (D20 — `fec` comma-joined,
  `lis`/`fec` are the join keys INC-4/INC-10b need); `terms` = full history,
  start-sorted, party switches preserved; `serving` = latest term overlaps
  congress 119 (deterministic, no wall-clock).
- `legislators.party_code(word)` — shared "Democrat"/"Democratic"→"D" mapper;
  **INC-3 reuses it for `voteParty`.** Raises on unmapped (→ quarantine, §6.1).
- `legislators.congress_window(N)` / `_term_overlaps` — congress↔date helpers;
  **INC-3 uses these to bucket roll calls into 118 vs 119.**
- `export._dumps(obj)` — the canonical serializer (sorted keys, 2-space, LF,
  trailing newline). Every INC-7 export contract should route through it.
- Tier-1 records (`Member`, `Bill`, `RollCall`, `MemberVote`, `Absence`, …) set
  `extra="forbid"` — an unexpected upstream field raises `ValidationError`
  (→ quarantine), it never silently rides into the published dataset.

## INC-3 output (done — the vote layer INC-4/5/6 build on)

- **`ingest/house_votes.py`** — `parse_rollcall(members_json, congress, session)`
  (pure) → `(RollCall, list[MemberVote], list[Absence])`, and `run()` (the
  `ingest house-votes` pipeline: enumerate → fetch `/members` per roll → quarantine
  → gaps → export). **Re-runnable/resumable** (cache); fault-tolerant per roll.
  - `VOTE_MAP` maps **both** Yea/Nay **and** Aye/No → yea/nay. **INC-4 senate
    parsing should reuse this insight** (LIS XML `vote_cast` is Yea/Nay; SHAPES §6).
  - Speaker elections = **`non_position`** rolls: a `RollCall` (counts) with a raw
    candidate tally in `totals`, **no** `member_votes`, excluded from symmetry +
    integrity. Detected by majority-unmappable `voteCast`.
  - `vote_class` provisional `other`/`unclassified` (INC-5 §A1 rewrites; leaves
    `non_position` alone).
- **`data/votes/{h-c-s-NNNN}.json`** = `{"rollcall": {...}, "member_votes": [...]}`
  (MS only, sorted). **`data/absences/{member}--{rollcall}.json`** = one stub per
  not_voting. `source_url` = clerk `sourceDataURL`.
- **`ingest/sources/clerk_house.py::parse_positions(xml, state)`** — bioguide→
  position from clerk XML (maps Aye/No too); the D6 independent cross-check source.
- **`checks/symmetry.py`** (vote coverage, §6.5) + **`checks/integrity.py`**
  (seeded 10-sample clerk cross-check; mismatch fails, unreachable warns) — both
  registered in `run.py`, both no-op on empty data.
- **`cache.py`** now retries timeouts/network errors (§6.1 bug fix) — reuse holds
  for every future source.

## INC-4 output (done — the Senate vote layer, mirrors INC-3)

- **`ingest/senate_votes.py`** — `parse_rollcall(detail_xml, congress, session,
  lis_to_bioguide, menu_tally)` (pure) → `(RollCall, list[MemberVote],
  list[Absence])`, and `run()` (the `ingest senate-votes` pipeline: parse menu →
  fetch each detail → cross-check tally → quarantine → gaps → export).
  Re-runnable/resumable (cache); idempotency re-verified (re-run byte-identical).
  - **Cross-SOURCE tally check** replaces INC-3's clerk: member-computed yea/nay
    must equal the menu's `vote_tally` (a different file) → else `TallyMismatch`.
  - **`_bill_id` handles 3 measure shapes** — `<document>` bill (`hr1-119`),
    amendment fallback to `<amendment><amendment_to_document_number>`, and
    nomination/treaty/quorum → `None`. Whitelist of real bill types.
  - **`_parse_date`** hand-rolls month parsing (locale-proof) → naive ISO ET.
  - **No `non_position` branch** (Senate has no candidate-surname rolls); VP
    tie-breaks handled by arithmetic that already agrees (D23).
- **`ingest/sources/senate_xml.py`** — added `parse_menu` (→ `{roll: (yeas,nays)}`,
  the enumeration + tally source), `detail_url`, and `parse_positions(detail_xml,
  lis_to_bioguide, state)` (the D6-style independent re-parse for integrity).
- **`data/votes/s-{c}-{s}-NNNN.json`** (1,581 files) + **`data/absences/`** (87
  Senate stubs; 243 total with House). Same export contract as INC-3.
- **`checks/symmetry.py`** generalized: `coverage_gaps(chamber, prefix)` runs House
  + Senate; report gains a `"senate"` key. **`checks/integrity.py`** runs a House
  clerk pass + a Senate detail-reparse pass (each no-op until its data exists).
- **`cli.py`** `senate-votes` subcommand.
- Tests: **`tests/test_senate_votes.py` (18)** — menu contiguity, all 4 real shape
  variants, tally-mismatch, crosswalk join, bill-id normalization, determinism.
  Committed 3 new detail samples (371/372/659). Test count 47 → 65.

## INC-5 output (done — the classified vote layer INC-8/10 render + score on)

- **`ingest/classify.py`** — `classify(question, *, is_rules_resolution=False) ->
  (VoteClass, rule_id)` is a PURE, offline, ordered rules table (`RULES` =
  module-level tuples, renderable on the INC-10 methodology page). FIRST match wins;
  order encodes precedence. `run()` = the `ingest classify` pipeline: rewrites
  `vote_class`/`vote_class_rule` in place on every non-`non_position`
  `data/votes/*.json`, regenerates `data/quality/unmapped_questions.json`
  (deterministic sorted regen, D24), fails if other-rate > `MAX_OTHER_RATE`.
  Idempotent (re-run byte-identical).
- **R-RULE** kept pure via the `is_rules_resolution` arg; `run()` computes it by
  fetching `bill/{c}/hres/{n}/committees` (`congress_gov.bill_committees`, new) and
  checking for House Rules `hsru00` + a "Reported" activity.
- **`checks/classification.py`** (new, registered in `run.py`) — CI gate: fails on
  any `unclassified` roll or other-rate > ceiling. **`cli.py`** `classify` subcommand.
- Tests: **`tests/test_classify.py` (9)** + golden **`tests/fixtures/questions.yaml`**
  (52 verbatim real strings, every rule id, both R-RULE branches, treaty). 65 → 74.
- **⚠ ORDER: ingest → classify → checks** (D24). Re-running an ingest resets rolls to
  `unclassified`; the classification gate then fails until `classify` re-runs.

## INC-6 output (done — the absence-explanation curation pipeline)

- **`curation/absences.py`** — pure `parse_granule` (byline, verbatim statement,
  roll refs, declared position), `verify_member` (the wrong-state gate), stub-
  existence `match_rollcall`, `search()` (CREC → verified queue) and `approve()` /
  `approve_one()` (owner approval → verbatim Absence). `_publish` refuses an
  unmatched roll (an Absence is keyed member+roll).
- **`ingest/sources/govinfo.py`** — `crec_personal_explanations(state, start, end)`
  (title+byline-scoped search), `granule_text(pkg, gid)` (header-auth), `granule_url`
  (the public `govinfo.gov/app/details/...` citation, verified 200).
- **`curation/cli.py`** — `curate absences {search|approve}` (`approve --granule <id>`
  is the owner's non-interactive path). **`banned_words.py`** excludes
  `data/quality/absence-queue/` (D25).
- Tests: **`tests/test_absences.py` (12)** + the queue-exclusion case in
  `test_banned_words_scope.py`; committed real fixture
  `data/quality/samples/crec_personal_explanation_guest.htm`. 74 → 86.
- **Queued, pending H9:** `data/quality/absence-queue/CREC-2023-01-13-pt1-PgE29-4.json`
  (Guest). Owner approval is H9; `data/absences/` reasons stay null until then.

## INC-7 output (done — the public export contract)

- **`ingest/export.py`** — `export_bill()` (+ the `Bill` schema; no bill data yet,
  ships so the contract is complete for every Tier-1 type — bill ingest = INC-8);
  `export_schemas()` writes `data/schema/{member,vote,bill,absence}.schema.json` from
  the pydantic models (the vote file maps to a composite **`VoteFile`** wrapper, not a
  bare `RollCall`); `build_manifest(generated_at, commit)` / `export_manifest()` with
  both wall-clock values **injected**; offline `main()` regenerates schemas + manifest
  from committed data (resolves real UTC + `git rev-parse --short HEAD`; env overrides
  `CIVIC_GENERATED_AT` / `CIVIC_COMMIT`). `main()` never re-ingests (D24 reset trap).
- **`ingest/verify_recompute.py`** (new `verify-recompute` console entry) —
  `check_dataset()` runs 3 invariants over 100% of rolls: (1) coverage (member_votes
  accounts every covered member per eligible roll), (2) subset (MS position count <=
  chamber `totals[cat]`), (3) absence reciprocity (not_voting vote <-> absence stub,
  both ways). **D26** = the resolution of the D22 recompute tension (chamber totals
  are not re-derivable from MS-only member_votes; the subset check is the honest tie).
  Reuses `checks/symmetry._covered` so covered-set logic never drifts.
- **`data/manifest.json`** — generated_at, commit, congresses, covered_state, and a
  `counts` block (members 6, rollcalls 3,467 [house 1,886 / senate 1,581], member_votes
  10,626, absences 243, bills 0, non_position 20, by-vote-class). The ONE wall-clock file.
- **`data/schema/*.schema.json`** — 4 committed JSON Schemas; a test fails if they
  drift from a fresh `export` (re-run `uv run export` to refresh).
- **`docs/data-contract.md`** — every file + field, the `non_position` sentinel, the
  `{member}--{roll}` absence filename, and the recompute-and-match definition + limit.
- Tests: **`tests/test_export_contracts.py` (9)** — manifest determinism + injected
  fields + committed-manifest-matches-recount, schema determinism + composite vote
  schema + committed-schemas-current, bill export round-trip, verify-recompute green
  on the committed dataset (× entrypoint). 86 → 95. Design in **D26**.

## INC-8 output (done — the public site MVP + bill ingest)

- **`ingest/bills.py`** (new `ingest bills` subcommand) — pure `parse_bill` +
  `parse_bill_id` + `run()`. Covered set = `referenced_bill_ids()` (distinct non-null
  `RollCall.bill_id`, 1,011). Detail-only fetch; `subjects`/`cosponsor_ids` = None
  (D27); titles `html.unescape`d; `source_url` = `legislationUrl`. Quarantine + §6.1
  ceiling. **0 quarantined.** `models.Bill.subjects`/`cosponsor_ids` widened to
  `list[str] | None`; `data/bills/*.json` (1,011) committed; manifest bills 0 → 1,011.
- **`site/src/lib/data.ts`** — build-time `node:fs` readers over `data/**` (memoized),
  typed to mirror §5; derived views `getMemberVotes` (newest-first), `getVotesForBill`,
  `paginate`. **`site/src/lib/display.ts`** — vote_class labels + neutral tooltips
  (UI chrome), `formatDate`, `billLabel`, `ordinal`.
- **Components** (`site/src/components/`): `Layout.astro` (shell + §6.7 footer),
  `Badge.astro` (vote_class + tooltip), `VoteRow.astro` (the full §6.7 vote row incl.
  absence rendering). **Pages**: `index.astro` (member index), `m/[member]/[page].astro`
  (paginated, 200/page — ⚠ `getStaticPaths` is scope-isolated, keep locals inside it),
  `v/[roll].astro`, `b/[bill].astro` (ⓘ affordance + CBO link-throughs + rolls-on-bill),
  `methods.astro` + `corrections.astro` stubs. **4,537 pages, built offline in ~25s.**
- **Acceptance harness**: `site/scripts/check-source-links.mjs` (`npm run test:links` —
  4,478 pages cite their source_url), Playwright `site/e2e/` (`@axe-core` WCAG2 A/AA +
  380px overflow, 6 data-derived representative pages; fullPage screenshot is
  best-effort — chromium can't capture a rule-resolution page listing hundreds of votes).
  `playwright.config.ts` webServer = `astro preview`. **12/12 e2e pass.**
- **CI** (`.github/workflows/ci.yml`): python job adds `verify-recompute`; site job adds
  `PUBLIC_BUILD_COMMIT=github.sha` on build, `test:links`, `playwright install chromium`,
  `test:e2e`. **`@types/node` + astro.config tailwind-plugin cast** make `astro check`
  clean (0 errors). Tests: **`tests/test_bills.py` (13)** — id parsing, core-field parse,
  D27 None assertion, entity-decode, missing-field raise. 95 → 108 (python). Design in
  **D27–D30**.

## INC-9 output (done — the unattended pipeline; site LIVE at civicledger.net)

- **`ingest/incremental.py`** (D31) — `final_cutoff(now)`, `is_final(date, cutoff)`,
  `roll_is_final`, `recent_bill_ids`, `bill_is_skippable`. Wired into `house_votes.run`,
  `senate_votes.run` (skip finalized rolls before fetch), `bills.run` (skip exported
  bills except those on recent rolls). All take an injected cutoff → 7 deterministic
  tests (`tests/test_incremental.py`). Ingest prints "N new/refreshed, M skipped".
- **`.github/workflows/nightly.yml`** (D32/D33) — cron + `workflow_dispatch`;
  `permissions: contents: write`; `fetch-depth: 0`; `CONGRESS_API_KEY` from secret.
  Ordering: ingest votes+bills → (if votes moved) classify → corrections → diff-gate on
  `data/` → real change: export → `npm run build` → checks → verify-recompute →
  commit+push; quiet night: build+checks for drift, exit 0 (no commit). Holds NO
  Cloudflare secret — push triggers Workers Builds.
- **`site/wrangler.jsonc`** — assets-only Worker, `assets.directory: ./dist`,
  `not_found_handling: 404-page`; **`site/src/pages/404.astro`**. `wrangler ^4` pinned
  in site devDeps. Layout footer build-commit now reads `WORKERS_CI_COMMIT_SHA`.
- **`ingest/corrections.py`** (`corrections` console entry, D34) — `git log --grep
  '^correction:'` → `data/corrections.json` (committed `[]`); `corrections.astro`
  renders it (`getCorrections` in `data.ts`); **`docs/correction-process.md`** (§A4).
- **`site/src/pages/privacy.astro`** — privacy summary stub (full threat model = INC-16).
- **Lighthouse** (`site/lighthouserc.cjs`, `npm run test:lighthouse`, CI step) — mobile
  perf + a11y ≥ 90, URLs derived from data, median of 3 vs `astro preview`. **Passes**
  (MVP pages carry no client JS). `/privacy` added to the e2e page set (**14/14 e2e**).
- **Docs**: H4/H5 → Workers, marked 🟨; `.env.example` H4 note; PIPELINE ORDER callout
  extended (ingest → bills → classify → export → checks). Tests 108 → **115** (python).

**INC-9 acceptance status:** procedural classification displayed ✅; missed votes show
reason/absence ✅; methodology stub live ✅; mobile Lighthouse ≥ 90 ✅ (local + CI);
six members complete ✅. **Nightly pipeline REHEARSED green** (`gh workflow run
nightly.yml`, run 31606758399, 2026-08-12): house 0 refreshed / 1,886 skipped, senate
11 refreshed / 1,570 skipped, bills 4 fetched / 1,007 skipped — classify restored the 11
re-fetched senate rolls byte-identical, so the diff-gate saw no change → **quiet night,
no commit** (validates D33); checks + verify-recompute green. **H4/H5 now DONE:** site
live at `civicledger.net` via Workers Builds. Only open box: observe a nightly that
actually commits new data + its deploy (next real data-change night). **D33 assumption
resolved by mechanism:** a `GITHUB_TOKEN`/bot push DOES trigger Workers Builds — the
Cloudflare GitHub App listens on the `push` webhook, which (unlike GitHub Actions
workflow triggers) is not suppressed for the default token; confirm empirically when the
first `data: nightly …` build shows author `github-actions[bot]` in Cloudflare Deployments.

**D35 (bugfix this session):** the ingest now re-exports absence stubs with
`overwrite=False`, so a nightly re-fetch of a recent roll never clobbers an owner-
approved `stated_reason` into a false "No explanation on record." (value #1). Landed +
CI-green before the rehearsal.

## INC-10 output (done)

- **`ingest/metrics.py`** — 8 pure/offline Tier-2 metrics (docstring == methodology):
  attendance, party_unity, sponsored, cosponsored, enacted_rate, cosponsor_vote_gap,
  named_measure_mismatch, absence_context → **`data/metrics.json`** (`ingest metrics`).
  `METRICS` registry drives the Tier-3 AST guard.
- **`data/legislation/{member}.json`** (`ingest legislation`) — sponsored/cosponsored
  bills, 118–119; quiet-night-safe (`LegItem` has no live latest-action; only frozen
  `enacted_action`); amendments excluded; covered-window paginator.
- **Bill backfill** — all 1,011 bills now carry `subjects` + `cosponsor_ids`
  (`ingest bills --all`); fetched for every exported bill so a re-export never reverts.
- **`RollCall.party_totals`** — aggregate per-party split on all 3,467 rolls
  (re-parsed from cache, offline, `--all`); `None` on non_position; verify-recompute
  invariant 4. **classify** round-trips it.
- **`/methods`** auto-built: one `data-metric` section per methodology key;
  `check-metrics-sections.mjs` (CI) asserts section-set == metric-key-set.
- **Symmetry** statement-balance rules activated (inactive/green at 0 statements);
  **Tier-3 guard** in `checks/integrity.py`; ci.yml + nightly.yml wired
  (`legislation` after bills, `metrics` after corrections before the diff-gate).
- Design in **D36–D40**; data-contract.md updated. **149 py tests**; full checks +
  cross-check 10/10; 4,539 pages; metrics-sections + source-links green.

**Next — INC-11 (Statement ledger + curation + pairing; content = H8, H6 for SPN).**
Load-bearing carry-overs from INC-10: (1) `named_measure_mismatch` FAILS CLOSED — it
raises the moment a specificity-2/3 statement naming a voted measure is curated, so
INC-11 MUST build the statement-STANCE comparison (a Statement has no stance field
today) before curating qualifying statements (D39). (2) Member-page rendering of the
metrics (esp. `cosponsor_vote_gap`) must follow D38: never a bare count, always against
its denominator, never a headline. (3) Statement symmetry rules are live and will gate
the curated corpus once the median reaches 5 (config.SYMMETRY_MEDIAN_ACTIVATION).

**INC-8 acceptance (met):** `astro build` from data alone ✅; axe-core a11y ✅ (14/14
Playwright); 380px layout + screenshot ✅; every rendered claim traces to a `source_url`
✅ (source-link trace, 4,478 pages).

---

## Increment status

| INC | Title | Status | Acceptance |
|-----|-------|--------|------------|
| INC-0 | Repo bootstrap | ✅ done (CI green) | `uv run checks && uv run pytest && (cd site && npm run build)` — local + CI green 2026-08-11 |
| INC-1 | Source feasibility spike | ✅ done | samples + SHAPES.md committed; all 6 federal sources reached; MS verdict **GO** (cross-check run 2026-08-11) |
| INC-2 | Canonical members & schema | ✅ done | models.py complete + 6 MS members exported + double-export determinism; 35 tests green |
| INC-3 | House vote ingest | ✅ done | 1,886 rolls (counts match, contiguous), 10/10 clerk cross-check, symmetry OK; 47 tests |
| INC-4 | Senate vote ingest ∥ | ✅ done | 1,581 rolls (contiguous 1..N per session, 119/1=659), 10/10 detail cross-check + menu-tally check, symmetry OK both chambers; 65 tests |
| INC-5 | vote_class classifier | ✅ done | 3,447 rolls classified, other 0.12% (≤5%); golden 52-string fixture 100%; R-RULE via Rules-Cmte fetch; classification CI gate; 74 tests |
| INC-6 | Absences & explanations | ✅ done (build); content = H9 | pipeline green (search→verify→queue→approve), byline gate, stub-existence match, queue banned-words-excluded; 1 candidate queued pending owner approval; 86 tests |
| INC-7 | JSON export contracts | ✅ done | double-export byte-identical (manifest + 4 schemas); `verify-recompute` matches 100% of 3,467 rolls (coverage+subset+reciprocity, D26); manifest + data-contract.md committed; 95 tests |
| INC-8 | Site MVP | ✅ done | 4,539 pages build offline; 1,011 bills ingested (0 quarantine); source-link trace 4,478 pages; axe WCAG2 A/AA + 380px 14/14 Playwright; §6.7 via shared components; 117 py tests + e2e |
| INC-9 | Automation + deploy (PUBLIC MVP) | ✅ done — **site LIVE at `civicledger.net`** (Workers Builds) | nightly.yml (incremental skip-if-final, diff-gated commit, Workers Builds deploy); corrections-as-data; Lighthouse mobile ≥ 90 (local+CI); nightly rehearsed green; 117 py tests. H4/H5 done. Open box: observe one real-data nightly commit + deploy |
| INC-10 | Metrics + methodology | ✅ done | 8 Tier-2 metrics → data/metrics.json; methods page auto-built from docstrings (section-set == metric-key-set); bill subjects/cosponsors backfilled; data/legislation/ + aggregate party_totals; Tier-3 AST guard + symmetry statement rules active; verify-recompute 4th invariant + metrics recompute-match; 149 py tests, D36–D40 |
| INC-10b | FEC funding (optional) | not started | blocked by H7 |
| INC-11 | Statement ledger + curation | ✅ build done; content = H8 | curation Flask app (loopback-only, no-capture-no-save server-side) + SPN2 verified capture; Statement stance + D9 single-source pairing (paired_bill_ids); named_measure_mismatch un-failed-closed (stance vs passage vote); member timeline interleave + /pairing page; weekly archive-links sweep (dead → build-excluded); 187 py tests at close (217 after R-1/R-4/R-6 hardening), D41–D44 + D47–D50. Phase-3 content acceptance (20+ statements, ≥5 pairs) is H8 |
| INC-12 | Mississippi state layer | ✅ done (branch A) | LegiScan bulk ingest → data/state/ms/ (174 members, 1,725 rolls, 905 voted bills, 144,007 member votes, 0 quarantined); jurisdiction schema + partitioned storage (D51); MS classifier + TTL cache (D52); checks/ms consistency + 5/5 official-PDF spot-check (D53); /ms site pages, site 4,540→7,919 (D54); hash-gated nightly (D55); /methods#mississippi limitations page (D56). **Member-page Tier-2 stats: federal (D57) + MS (D58 — legislation layer from all 4,006 bills + metrics.json).** 254 py tests; checks + 24/24 e2e + astro-check green |
| — | Member-page stat rendering | ✅ done (D57/D58) | 8 federal + 5 MS Tier-2 metrics rendered as a KPI stat-tile row atop each member page (`MemberStats.astro`, jurisdiction-aware) — each with its denominator, NO composite/score. The review's post-INC-12 item |
| INC-13 | Candidate Tracker | not started | content = H10 |
| INC-14 | Alignment Quiz engine | not started | content = H11 |
| INC-15 | Alignment outputs | not started | — |
| INC-16 | Aggregates Worker + privacy | not started | H4 done (Workers live); canary = H12 |
| INC-17 | Challenge & Calibration | not started | — |
| INC-18 | Longitudinal drift | not started | — |
| INC-19 | Bill diff viewer | not started | — |
| INC-20 | "Nobody Told You" feed + glossary ∥ | not started | — |
| INC-21 | Ballot builder + share cards | not started | — |
| INC-22 | Zero-knowledge sync (post-v1 stub) | deferred | Decision D12 — do not build this pass |

## Blocked human tasks (see docs/HUMAN-TASKS.md for full table)

| H | Blocks | Status |
|---|--------|--------|
| H1 | INC-1 | ✅ done — CONGRESS_API_KEY in .env + GitHub secret |
| H2 | INC-1 state branch | ✅ done — LegiScan key present; **Journal cross-check run 2026-08-11 → verdict GO (5/5)**; INC-12 branch A unlocked |
| H3 | INC-0 push / all CI | ✅ done — repo live, pushed, CI green |
| H4 | INC-9, INC-16 | ✅ done — Cloudflare **Workers** via Workers Builds (root `site/`, build `npm run build`, deploy `npx wrangler deploy`); no `CLOUDFLARE_*` GitHub secret; site live. Enable `github-actions[bot]` push bypass if branch protection is added |
| H5 | INC-9 | ✅ done — **`civicledger.net`** (`.org` was taken) custom domain on the Worker; live |
| H6 | INC-11 auth SPN | ⬜ pending — archive.org S3 keys (falls back to unauth SPN) |
| H7 | INC-10b | ⬜ pending — FEC key (optional increment) |
| H8–H12 | recurring content | ⬜ pending |
| H13 | pre-launch byline | ⬜ pending (non-blocking) |

## What exists in the repo now (INC-0..INC-9 output)

**INC-9 additions:** `ingest/incremental.py` (skip-if-final) wired into house/senate/
bills run(); `ingest/corrections.py` (+ `corrections` console entry) → `data/corrections.json`;
`.github/workflows/nightly.yml`; `site/wrangler.jsonc` + `site/src/pages/404.astro` +
`privacy.astro`; corrections rewired to data (`getCorrections` in `data.ts`,
`corrections.astro`); `site/lighthouserc.cjs` + `test:lighthouse` script + CI step;
`wrangler` devDep; `docs/correction-process.md`; H4/H5→Workers in HUMAN-TASKS + `.env.example`;
Layout `WORKERS_CI_COMMIT_SHA`; `tests/test_incremental.py` (7). D31–D34 in `decisions.md`.
Test count 108 → 117 (python) + 14 Playwright e2e.

**INC-8 additions:** `ingest/bills.py` (+ `bills` subcommand); `Bill.subjects`/
`cosponsor_ids` widened to `list[str] | None` in `models.py`; `data/bills/*.json`
(1,011); the full Astro site — `site/src/lib/{data,display}.ts`,
`site/src/components/{Layout,Badge,VoteRow}.astro`, pages `index`/`m/[member]/[page]`/
`v/[roll]`/`b/[bill]`/`methods`/`corrections`; `site/scripts/check-source-links.mjs`;
`site/e2e/{fixtures,a11y,mobile}` + `playwright.config.ts`; `@types/node` +
`@playwright/test` + `@axe-core/playwright` devDeps; the astro.config tailwind cast;
CI additions (verify-recompute, source-link, playwright, `PUBLIC_BUILD_COMMIT`);
`tests/test_bills.py` (13). D27–D30 in `decisions.md`. Test count 95 → 108 (python)
+ 12 Playwright e2e.

**INC-7 additions:** `ingest/verify_recompute.py` (the `verify-recompute` console
entry + `check_dataset`), the `VoteFile` wrapper + `export_bill`/`export_schemas`/
`build_manifest`/`export_manifest`/offline `main()` in `ingest/export.py`, the
`verify-recompute` script in `pyproject.toml`, `docs/data-contract.md`,
`tests/test_export_contracts.py` (9), and the committed derived artifacts
`data/manifest.json` + `data/schema/{member,vote,bill,absence}.schema.json`. D26 in
`decisions.md`. Test count 86 → 95.

**INC-6 additions:** `curation/absences.py` (search→verify→queue→approve pipeline),
`crec_personal_explanations`/`granule_text`/`granule_url` in `ingest/sources/govinfo.py`,
the `absences` subcommands in `curation/cli.py`, the `absence-queue/` exclusion in
`ingest/checks/banned_words.py`, `tests/test_absences.py` (12) + a queue-exclusion
test, the committed `data/quality/samples/crec_personal_explanation_guest.htm` fixture,
and one pending queue file `data/quality/absence-queue/*.json`. Also swept printed
U+2192 arrows → ASCII (Windows cp1252 crash). D25 in `decisions.md`. Test count 74 → 86.

**INC-5 additions:** `ingest/classify.py` (pure §A1 rules table + `classify`
pipeline, `classify` subcommand), `congress_gov.bill_committees`,
`ingest/checks/classification.py` (registered in `run.py`), `tests/test_classify.py`
(9) + `tests/fixtures/questions.yaml` (52 real strings), the `classify` wiring in
`cli.py`, `data/quality/unmapped_questions.json`, and the in-place re-classification
of all **3,447** `data/votes/*.json` (vote_class/vote_class_rule rewritten). D24 in
`decisions.md`. Test count 65 → 74.

**INC-4 additions:** `ingest/senate_votes.py` (parser + `run()` pipeline,
`senate-votes` subcommand), `parse_menu`/`detail_url`/`parse_positions`/`VOTE_MAP`
in `ingest/sources/senate_xml.py`, both-chamber generalization of
`checks/symmetry.py`, the Senate re-parse pass in `checks/integrity.py`, the
`senate-votes` wiring in `cli.py`, `tests/test_senate_votes.py` (18) + 3 committed
detail samples (371/372/659), and the committed dataset: **1,581 `data/votes/s-*.json`
+ 87 Senate `data/absences/*.json`** + the updated `data/quality/symmetry-report.json`.
D23 in `decisions.md`. Test count 47 → 65.

**INC-3 additions:** `ingest/house_votes.py` (parser + `run()` pipeline,
`house-votes` subcommand), `parse_positions` in `ingest/sources/clerk_house.py`,
`house_vote_roll_numbers` enumeration in `congress_gov.py`, `export_rollcall`/
`export_absence` in `export.py`, `checks/symmetry.py` + `checks/integrity.py`
(registered in `run.py`), the `cache.py` timeout-retry fix,
`tests/test_house_votes.py` (10) + a cache retry test, and the committed dataset:
**1,886 `data/votes/*.json` + 156 `data/absences/*.json`** +
`data/quality/symmetry-report.json`. D22 in `decisions.md`. Test count 36 → 47.

**INC-2 additions:** `ingest/models.py` (full §5 schema layer), the raw→`Member`
parser in `ingest/sources/legislators.py` (`party_code`, `congress_window`,
`is_covered`, `covered_members`), the deterministic serializer + `export_members`
in `ingest/export.py`, the `members` subcommand in `cli.py`, `tests/test_models.py`
(11 offline tests), and 6 committed `data/members/*.json`. D20 in `decisions.md`.
Test count 23 → 35.

**INC-1 additions:** `ingest/env.py`, `ingest/cache.py`, `ingest/spike.py`,
`ingest/sources/{congress_gov,senate_xml,legislators,clerk_house,legiscan}.py`,
`tests/test_cache.py` (6) + `tests/test_banned_words_scope.py` (2) offline tests,
`ingest/sources/govinfo.py`, and the committed `data/quality/samples/`
(11 samples + `SHAPES.md`) + `data/quality/ms-state-verdict.md`.
`banned_words.py` now excludes `data/quality/samples/` (ADR). `ingest spike`
subcommand wired in `cli.py`. Test count 15 → 23.

## Prior state (INC-0 output)

- **Python (uv):** `pyproject.toml` (console scripts `ingest`/`export`/`curate`/
  `checks`; hatchling ships two packages `ingest` + `curation`), `uv.lock`,
  `.python-version`=3.12.
- `ingest/config.py` — `K_ANON=50`, `CONGRESSES=[118,119]`, `COVERED_STATE="MS"`,
  symmetry + quarantine + max-other-rate thresholds.
- `ingest/checks/` — `banned_words.py` (§6.4), `no_llm.py` (§6.6, self-match
  defended two ways + tested), `run.py` (the `checks` entrypoint).
- Stub entrypoints: `ingest/cli.py`, `ingest/export.py`, `curation/cli.py`
  (all print a status + exit 0; real logic lands in later increments).
- `tests/test_bootstrap.py` — 15 tests (entrypoints importable, K_ANON, congress
  coverage, banned-words detect/clean, no_llm self-non-match + detection).
- **Site (Node/npm):** `site/` Astro 5 static scaffold, Tailwind v4 via
  `@tailwindcss/vite`, Preact islands, placeholder `index.astro`,
  `site/package-lock.json`. `dist/` is gitignored (CI builds it).
- **CI:** `.github/workflows/ci.yml` — Node 22, `astral-sh/setup-uv`, `uv sync
  --frozen`, **build-before-checks** so §6.4 scans real `site/dist/**`.
- **Docs:** `docs/HUMAN-TASKS.md`, `docs/decisions.md` (version pins + builder
  ADRs), `CONTRIBUTING.md` (no-LLM policy), `.env.example`, this file.
- **Repo hygiene:** `.gitattributes` forces LF everywhere (protects §6.3
  export determinism); `.gitignore` covers `.env`, `data/raw/`, `build.db`,
  caches, `node_modules/`, `dist/`.

## Notes / open items / ADR pointers

- **Post-review ADRs:** grading reframe = **D19/D20** (IMPLEMENTATION.md §2); R-3 = **D45**,
  R-2 = **D46**, R-1 = **D47**, R-4 = **D48**, R-6 = **D49**, R-5 = **D50** (all
  `docs/decisions.md`). **The whole review backlog R-1..R-6 is now CLOSED** (source: local
  `TECHNICAL_REVIEW.md`). H8 statement curation is unblocked (R-1 landed).
- **INC-12 (MS state layer) ADRs: D51–D56** (`docs/decisions.md`); full plan in
  `docs/inc-12-plan.md`; contract in `docs/data-contract.md` (state section). **INC-12 is
  DONE** (all 6 phases). **Member-page stats: D57 (federal) + D58 (Mississippi) — DONE:**
  both jurisdictions render the Tier-2 stat tiles on member pages (attendance, party unity,
  sponsored/authored, cosponsored/co-authored, enacted/became-law), each with its
  denominator, NO composite score (Tier-3 rule holds). **Next actionable = the
  reader-adjustable scorecard** (the overall-grade experience, client-side weights per D19 —
  the remaining big item the owner flagged) OR **INC-13** (Candidate Tracker, content = H10)
  — owner's pick. Open runtime-verification boxes (not blockers): R-5 cache-hit on the 2nd
  nightly; INC-9 first-real-data nightly commit + deploy; the first MS nightly hash-gate no-op.
- **Deferred (later increments):** backfill prior MS sessions; the flat-file→SQLite
  build-accelerator decision (review §6 — revisit before a 2nd state; MS kept flat-file,
  ~7,900 pages, still fine).
- Version pins recorded in `docs/decisions.md` (Python + Node) at INC-0.
- Dev environment: Windows 11 + PowerShell. `uv` at
  `%APPDATA%\Python\Python314\Scripts` on user PATH. Local Python 3.14 → project
  pins 3.12 (uv-managed). Local Node 24 → CI pins Node 22 LTS (logged in decisions.md).
- **Non-blocking CI warning:** logs show "Node.js 20 is deprecated" for
  `actions/checkout@v4` / `setup-node@v4` / `setup-uv@v5`. This is GitHub
  *runner-infra* deprecation of the actions' own Node runtime, **not** our Node
  22 pin. Does not fail CI; resolves when those actions ship Node-24 releases.
  No action needed; revisit only if it ever turns into a hard failure.
- **CLAUDE.md note (historical):** through the v1 build, there was no `CLAUDE.md`
  file — its content lived in the bare `.claude` file (never auto-loaded by
  Claude Code), pointing at `IMPLEMENTATION.md`. Fixed at v2 adoption: `.claude`
  → `CLAUDE.md` (git mv), rewritten to point at `IMPLEMENTATIONv2.md`.
- **Watch in INC-1:** (a) the `/house-vote` beta endpoint may 404 → clerk XML
  fallback + log deviation; (b) Senate vote filename must be discovered from the
  `vote_menu` XML, not assumed; (c) H2 absence forces the state verdict to DEFER.
