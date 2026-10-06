# IMPLEMENTATIONv2.md — Civic Ledger

### Build specification, second constitution. Consumed by Claude Code. A follow-up conversation with the owner EXISTS and is required at the points this document marks.

Adopted 2026-08-13. Supersedes `docs/archive/2026-08-13-pre-v2/IMPLEMENTATION.md`
("v1"). The owner amended three of the four founding values, scrapped the
never-ask rule, and pivoted the product federal-first; this document re-derives
every rule that descended from the old values. Appendix B proves nothing still
true was lost. Where this document and the code disagree, **the code is
authoritative** — say so in `docs/PROGRESS.md` and fix whichever is wrong.

---

## §CS — Current state (read before building anything)

v1 was written for an empty repository. This repository is not empty. **Do not
rebuild anything in the first list. Do not assume anything in the second list
exists.**

### Built, live, and working (INC-0..INC-12 + D57/D58, per `docs/PROGRESS.md`)

- **Live site:** `civicledger.net`, deployed by **Cloudflare Workers Builds**
  (Static Assets, `site/wrangler.jsonc`, no `CLOUDFLARE_*` secret in GitHub CI).
  Not Pages — v1's Pages references were stale (builder ADR D32).
- **Pipeline:** `ingest → classify → checks → export` (exact load-bearing order
  in the `PIPELINE ORDER` block of `docs/PROGRESS.md`). Nightly cron ingests,
  diff-gates, commits, and deploys unattended.
- **Federal data:** 3,467 roll calls (1,886 House / 1,581 Senate), 118th–119th
  Congresses; 1,011 bills; **positions persisted for the 6 MS members only**
  (10,626 member-vote rows) — that is builder ADR D36 and it is what V2-1
  changes. 8 Tier-2 metrics computed and rendered as stat tiles (D57).
- **Mississippi layer:** `data/state/ms/` — 174 legislators, 1,725 roll calls,
  905 vote-referenced bills, 144,007 member-vote rows, 5 scalar metrics (D58),
  `/ms/` routes. Preserved as-is during the pivot (SD-30).
- **CI:** `ci.yml`, `nightly.yml`, `archive-links.yml`. 6 checks (banned-words,
  no-LLM, symmetry, integrity + Tier-3 guard, archive-links, ms), 254 pytest
  tests, ruff, `verify-recompute`, Astro build (**7,919 pages**), 24 Playwright
  e2e, Lighthouse, `astro check`.
- **Member pages:** `/m/{bioguide}/{page}/` (56 pages) and `/ms/m/...` (748),
  paginated at `PAGE_SIZE = 200` (`site/src/pages/m/[member]/[page].astro`).
  Five stat tiles + collapsed adjacency list + vote record
  (`site/src/components/MemberStats.astro`).
- **Enforcement that works and survives v2 unchanged:** no-LLM guard
  (`ingest/checks/no_llm.py`), banned-words (`ingest/checks/banned_words.py` —
  allowlist = `site/src/content/glossary.md`; excludes `data/quality/samples/`,
  `data/quality/absence-queue/`, `data/raw/`), export determinism
  (`tests/test_export_contracts.py`, **not** `integrity.py` — v1 §6.3 was
  wrong), quarantine ceiling (`QUARANTINE_MAX_FRACTION` **is** enforced, in
  `ingest/bills.py` and `ingest/ms_legislature.py`), `source_url` on every
  record, correction process (`docs/correction-process.md`), pipeline order.

### Deliberately or accidentally NOT built (do not assume these exist)

- **No `worker/` directory. No server code of any kind.** v1 INC-16's
  aggregates Worker was never built; `K_ANON = 50` exists only as a constant in
  `ingest/config.py`, and `config.py`'s docstring claim of a worker↔ingest
  equality test is false (the only test is `tests/test_bootstrap.py`'s
  `K_ANON == 50`).
- **No warrant canary** (H12 never done; `site/src/content/canary.md` does not
  exist). **No threat-model page** (`/privacy` explicitly defers it). No
  accounts, no analytics, no quiz, no candidate tracker — v1 INC-13..INC-22
  were never built.
- **No coverage tooling** — v1 §8's "100% branch coverage floor" was never
  enforced. §8 below makes it real where it matters.
- The Tier-3 AST guard (`ingest/checks/integrity.py:tier3_violations`) is a
  tripwire, not a proof: it misses composites reached through shared helpers,
  subscript dispatch (`METRICS["x"](...)`), local aliasing, class-method or
  nested-function metrics, and goes inert if `METRICS` is not a dict literal of
  bare names; it can also false-positive on unrelated same-named methods.
  Never describe it as reliable.

---

## §0 — Ground rules for the builder

1. **Ask the owner when unsure.** The v1 never-ask rule is scrapped
   (owner amendment, 2026-08-13). Resolution ladder for any ambiguity:
   (a) if a Decision in §2 covers it, apply it; (b) if a runtime check can
   resolve it, run the check and follow the branch; (c) if it is a **judgment
   call about political evaluation** — what counts as good or poor performance
   on a dataset, where a threshold sits, how a grade is framed — **ask the
   owner and wait** (this is also required by rule 8); (d) only for mechanical,
   non-evaluative choices, pick the option that best serves §0.4 and record a
   dated ADR in `docs/decisions.md`.
   **Plain-language requirement:** every question to the owner is phrased in
   simple, non-technical terms with each option's consequence stated plainly.
   He is not a web-development or data-analytics specialist. Example of a
   question that MUST be asked, not resolved: "Should non-voting House
   delegates (DC, Puerto Rico, territories) appear in the rankings? They can't
   vote on final passage, so their attendance number isn't comparable."
2. **Human-only tasks still block by design.** Credentials, account setup, and
   recurring curation remain the owner's (§1). Build around the block, stub
   from `.env.example`, record the instruction in `docs/HUMAN-TASKS.md`, move
   to the next unblocked increment. (This rule survives the ask-rule change:
   it is about access, not silence.)
3. **Every increment ends with its acceptance criteria demonstrably passing** —
   a runnable command. Do not start V2-(N+1) with V2-N failing, except
   increments marked ∥.
4. **The four load-bearing values** — §0.4 below. Value #1 outranks the rest.
5. **No LLM output anywhere in the publishing path.** UNCHANGED from v1,
   verbatim: you may write code, tests, UI copy templates, and documentation;
   you may NOT generate, summarize, classify, or paraphrase any political
   content that publishes as fact. The owner did **not** amend this rule.
   Rule 8 exists precisely so the evaluative turn does not violate it.
6. **Windows 11 is the dev environment; CI runs Ubuntu.** Unchanged. Commands
   live in `pyproject.toml` / `package.json`. stdout stays ASCII (builder ADR,
   `decisions.md` 2026-08-12); `spike.py`'s UTF-8 reconfigure is grandfathered.
7. **Raw API responses cached to disk before parsing.** Unchanged. Never
   hammer a government API — V2-1 re-parses from cache wherever the cached
   payloads already contain all-member positions.
8. **Threshold authority (new, ratified by the owner 2026-08-13 — SD-27).**
   Every evaluative constant — a threshold ("below X% is poor"), a grade
   boundary, a category weight in the overall grade, a "lowest N%" dashboard
   cut — follows **propose → ratify → commit**: the builder proposes at least
   two options in plain English with the reasoning and any outside reference
   for each; the owner picks; the chosen value lands in a committed config
   file (§5) carrying the value, the justification, the citation if any, and
   the ratification date. **Nothing evaluative publishes from an unratified
   number.** This is how rule 5 and the evaluative turn coexist: the machine
   applies judgments; only the owner authors them.

---

## §0.4 — The four values, as amended 2026-08-13 and 2026-09-23 (SD-32)

In priority order when they conflict. **Value #1 is unchanged and is the
anchor: it outranks #2, #3, and #4, and it is what makes the evaluative turn
defensible rather than reckless.**

1. **Never publish something false or falsely framed.** Unchanged.
   A true number in a false frame violates this value.
2. **Evaluative labels only under the disclosure standard.** *(Replaces
   "never render partisan lean.")* The site now defines good and poor
   performance, highlights best and worst performers, and calls bad, bad.
   An evaluative label — a rank, a percentile, a grade, or a threshold
   classification such as "poor attendance" — is publishable **if and only
   if** it is:
   - (a) computed by a formula published on `/methods`;
   - (b) from data traceable to an official source;
   - (c) applied identically to every member and every party in the covered
     set — R-vs-D and R-vs-R comparison both exist, same standard for all;
   - (d) rendered with its inputs and denominator visible or one click away;
   - (e) built only on thresholds and weights ratified under §0.8.
   **The site never asserts motive, intent, honesty, or character. It reports
   what the numbers show, never why.** The banned-words list (§6.4) is the
   mechanical edge of that line and survives unchanged. Do not write "the
   site permits some bias" anywhere: the operative concept is *evaluative
   judgment under a disclosed uniform standard*, which is a different axis
   from partisan bias, and conflating them in writing is a liability with no
   upside.
3. **Collect only what the product needs; never sell it; deletion
   deletes.** *(Amended 2026-09-23, SD-32. Replaces the 2026-08-13 wording
   "collect the minimum; what identifies belief is unreadable or
   aggregated.")* The site may collect, store, and **read** the user data its
   features need: accounts (email + password), what a user follows (bills,
   topics, members), notification channels the user opts into (email; phone
   only after the owner ratifies it), preferences, quiz answers and issue
   weights tied to an account, and aggregate site analytics including
   state-of-origin. Nothing in this document may forbid the site from
   reading data it needs to deliver a feature the owner has scheduled.
   Conditions that survive — **narrowed by SD-34 (2026-10-05)**: anonymous use
   of the full public record stays available forever; population trends
   published from user data come only from K-anonymous aggregates (K = 50);
   **data is never sold** — the one standing promise, and the only privacy
   claim the owner stated himself; shared no further than the named service
   providers; deletion hard-deletes.
   **SD-34 withdrew two of the conditions that used to sit in this list:**
   "nothing is collected that no scheduled feature needs" and "analytics are
   aggregate and cookieless". The project may now collect ahead of a
   scheduled need, and may set cookies. Do not reinstate either as a value
   without a dated decision — and do not write either onto the site.
   **Every privacy statement on the site must be true before the collection
   it describes ships** — that ordering is a blocking gate (V2-7), because a
   false `/privacy` page is a Value #1 violation. The gate orders work; it
   does not forbid collection.
4. **Ship partial value early.** Unchanged (owner reconfirmed 2026-08-13): a
   live, correct, incomplete site beats a complete unbuilt one.

---

## §1 — Human-only tasks

`docs/HUMAN-TASKS.md` is the authoritative status table (H1–H13; H1–H5 done,
site live). v2 adds:

| # | Task | Blocks | Instructions |
|---|---|---|---|
| **H14** | Cloudflare Workers plan check | V2-1 | Static-asset limits (checked 2026-08-13): **20,000 files/version on Workers Free, 100,000 on Paid** (raised 2025-09-02; requires wrangler ≥ 4.34.0), 25 MiB/file. V2-1's projected build is ~13k files — fits Free. When the build's file count reports ≥ 18,000 (CI prints it), decide: upgrade to Workers Paid ($5/mo) or hold state expansion. |
| **H15** | Threshold ratification (recurring) | V2-4, V2-5, V2-10 | Per §0.8. The builder brings options in plain English; you pick; your choice is committed with its reasoning. Expect one sitting per increment that introduces evaluative output. |
| **H16** | Branch protection on `master` | V2-0 | GitHub → Settings → Branches → protect `master`: require CI, forbid force-push. This makes the correction-history promise (`docs/correction-process.md`) enforced rather than assumed. |
| **H17** | Turnstile site + secret keys | V2-8 | Cloudflare dashboard → Turnstile → new widget (invisible mode) → `.env` / repo secrets `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET`. |
| **H18** | Transactional email provider | V2-8 | **DECIDED 2026-10-05 by SD-36: Cloudflare Email Sending.** The earlier text here said "pick a provider (e.g. Resend/MailChannels), create API key → secret `EMAIL_API_KEY`" and is superseded — no third-party key, a `send_email` binding instead. **Still owed by a human:** enable Email Sending on the Cloudflare account and create the binding/secret the Worker reads. The sender sees recipient addresses and message text, and `/privacy` names it (done 2026-10-06, D102). |
| **H19** | Warrant-canary decision | V2-7 | Decide-item, plain terms in V2-7: the old canary promise ("we can't hand anything over because we hold nothing") dies once accounts exist. Options the builder will present: retire the canary idea, or reshape it ("we have received no demand as of {date}"). No canary was ever published, so retiring costs nothing visible. |

---

## §2 — Decisions

### Numbering scheme (SD-31 records this in the ADR log)

v1's §2 decisions and `docs/decisions.md`'s builder decisions collided at D19
(spec D19 = reader-side grading; builder D19 = a Congress.gov path-segment
finding). Resolution:

- **SD-n** ("spec decision") — constitutional/spec-level decisions. Canonical
  home: **this section.** SD-1..SD-20 are v1's D1..D20 renamed one-to-one.
  SD-21+ are new. `docs/decisions.md` carries a dated record of SD-21+ for
  the append-only log.
- **D-n** ("builder decision") — remains `docs/decisions.md`, unchanged,
  append-only; D19–D58 keep their numbers; future builder ADRs continue at
  **D59**. History is never rewritten; a correcting note in the log fixes its
  stale "D1–D18" header claim.
- Old citations: "the D19 line" in builder ADRs D45/D57 meant spec-D19 — read
  as **SD-19** (now retired, see below).

### SD-1..SD-20 (v1 D1..D20) — dispositions

| # | Was | Disposition |
|---|---|---|
| SD-1 | Symmetry per-member, party-mean secondary | **Amended.** Covered set becomes all serving federal members (V2-1); per-member equal depth still the rule; party-mean comparisons become first-class rendered output (R-vs-D averages), not just a check. |
| SD-2 | One server component: counter-only aggregates Worker | **Amended.** The counter Worker (never built) survives as the *trends* path and is joined by the account service (SD-28, as amended by SD-32). "One server component" becomes "the only server code is `worker/`, and everything it stores is listed on `/privacy`." |
| SD-3 | Stack: Python/uv/pydantic → SQLite → JSON → Astro → **Cloudflare Pages** | **Amended.** Deploy is Workers Static Assets via Workers Builds (builder D32). Rest of the stack carried; SQLite gains the committed-pipeline role in SD-29. |
| SD-4 | Monorepo, single public repo | **Carried.** |
| SD-5 | Federal depth: 118th + 119th | **Carried.** The pivot widens *who* is covered, not *when*. Older congresses remain unscheduled. |
| SD-6 | House: Congress.gov primary, clerk XML fallback/check; Senate: LIS XML | **Carried.** V2-1 reuses these sources; they already contain every member's position. |
| SD-7 | vote_class rules table, unmapped → other | **Carried.** (Rules table = v1 §A1, now authoritative in `ingest/classify.py`.) |
| SD-8 | Absence reasons curated, never auto-published | **Carried.** |
| SD-9 | Pairing by bill id; short titles only via allowlist | **Carried.** |
| SD-10 | Ballot builder via Census Geocoder + curated race file | **Carried (parked** with INC-21 in the backlog, Appendix B). |
| SD-11 | Drift reminders via bare .ics | **Carried (parked).** |
| SD-12 | Zero-knowledge sync deferred post-v1 | **Retired.** Superseded by SD-28 (2026-08-13), then its client-side-encryption core was retired by SD-32 (2026-09-23): the server stores readable user data. |
| SD-13 | `CAP1.` portable quiz codes | **Carried (parked** with the quiz). |
| SD-14 | Bill diff on USLM XML | **Carried (parked).** |
| SD-15 | CBO link-through | **Carried.** |
| SD-16 | FEC out of MVP | **Carried (parked).** |
| SD-17 | No analytics; if ever, cookieless CF only, default-off | **Amended.** Analytics are now in scope (owner amendment): aggregate, cookieless, state-of-origin for prioritizing states. V2-9. The "no fingerprinting, no per-user rows" spirit survives. |
| SD-18 | MS branch verdict mechanics | **Retired (completed).** INC-12 shipped branch A. |
| SD-19 | Grades computed only in the reader's browser; publish path never computes a composite | **RETIRED** by SD-26 (owner, Gate 1). The site now publishes category grades and one fixed overall grade. The Tier-3 guard is repurposed, not deleted — §6.8. |
| SD-20 | Donations/votes as adjacency timeline, never "cost per vote" | **Carried.** The motive line survives the evaluative turn: performance may be graded; purchase of a vote may never be asserted. |

### New spec decisions (owner-ratified 2026-08-13)

| # | Decision | Rationale |
|---|---|---|
| SD-21 | **Amendment 1 adopted:** Value #2 replaced by the evaluative-label disclosure standard (§0.4.2) | Owner: "define what poor performance is then call poor performers, poor performers ONLY where I can back it with stats," same standard both parties, full formula transparency, no motive claims. |
| SD-22 | **Amendment 2 adopted:** Value #3 replaced by collect-minimum/encrypt-belief (§0.4.3); privacy-docs-first is a blocking gate | Owner: will collect, won't sell; anonymous mode stays. A false privacy page would violate unamended Value #1, hence the gate. **The encrypt-belief part is amended by SD-32 (2026-09-23).** |
| SD-23 | **Amendment 3 adopted:** never-ask rule scrapped; ask in plain language (§0.1), especially on evaluative judgment | Owner's explicit instruction. |
| SD-24 | **Amendment 4 adopted:** federal-first pivot; landing page becomes a drill-down stats dashboard; Federal + States tabs; state sections mirror the federal presentation | Owner: federal is "an all in one source that everyone in the country can view"; fastest reach. |
| SD-25 | **Value #4 unchanged** (owner reconfirmed) | Prioritization tiebreaker; no conflict with the amendments. |
| SD-26 | **Gate 1 = option (c):** per-category grades **plus one fixed site-published overall grade**, with an over-time trend; no reader re-weighting requirement | Owner's choice over (a) ranks-only, (b) category-only, (d) reader-adjustable overall. Retires SD-19. |
| SD-27 | **Gate 2:** threshold authority = propose → ratify → commit (§0.8) | Keeps the unamended no-LLM rule intact: the owner authors every evaluative constant; the build applies it. |
| SD-28 | **Gate 3 (as amended by SD-32, 2026-09-23):** accounts = email + password (Argon2id); user data (follows, preferences, quiz answers, weights) stored **readable** on the server; public profile strictly opt-in — published means public; deletion hard-deletes; trends only via K-anon (=50) counters; ~~no IP retention, logging off~~ — **those last two clauses are WITHDRAWN by SD-34 (2026-10-05): the project may log requests and may keep IP columns, and neither may be claimed on the site.** The rest of this row stands. | The 2026-08-13 choice was client-side encryption ("locked even from you"). Retired by SD-32: server-sent alerts require the server to read what a user follows, and the owner chose to let the site read and collect what its features need. Password reset no longer loses data. |
| SD-29 | **Gate 4:** published data stays deterministic JSON in-repo (the inspectable contract); a gitignored SQLite `build.db` becomes the build accelerator; vote-record pages restructured to control page count | Numbers in V2-1. The JSON contract is the product's credibility; the caveat "chamber totals are not recomputable" dies with V2-1 — a stated credibility upgrade. |
| SD-30 | **Gate 5:** Mississippi layer preserved as-is through the pivot; reskinned to mirror federal presentation and folded under the States tab in V2-10 | Fastest pivot; nothing live breaks; MS is touched once, at the end, against a finished federal template. |
| SD-31 | **ADR renumbering** as described above | Ends the D19 collision without rewriting append-only history. |
| SD-32 | **Amendment 5 (owner, 2026-09-23): the site may read and collect the user data its features need.** Value #3 reworded (§0.4.3); SD-28's client-side encryption requirement retired; every "no plaintext / cannot read / ciphertext-only" rule in this document is void. Surviving guardrails: collect nothing no scheduled feature needs; disclosed on `/privacy` before it ships (V2-7, Value #1); never sold; K-anon for published trends; hard delete. **Priority order amended:** V2-11 → V2-7 → V2-8 → V2-12 → V2-13 (`docs/plan-subscriptions-and-alerts.md`); V2-6 deferred. | Owner's request: profiles, topic subscriptions, bill tracking, email/text alerts. Alerts cannot be sent by a server that cannot read the subscription list. Owner directed: "change anything in the plans or other docs that stop the site from reading or collecting data." Consequence stated in §10. |
| SD-33 | **V2-11 shape ratified (owner, 2026-10-01), asked with D88's measured numbers.** **(3) Coverage = option (c):** all 38,756 bills in the covered Congresses are tracked for alerts, topics and feeds; only bills that reach a recorded vote get a `/b/` page. A pageless bill links to its `source_url` on congress.gov, never to a `/b/` URL that does not exist. **(4) Topics = option (a):** official government vocabulary only — the 31 policy areas and 872 CRS subject terms, verbatim. No owner-authored bundles for now; H22 stays optional and unblocked. **(6) Cadence = daily digest**, carried by the existing nightly. No second intra-day workflow. **(2) Channel = email first**, which makes H17/H18/H20 the V2-12 blockers; text/push stay phase 2 (H21 untouched). **(7) Workers Paid is NOT forced by V2-11** — only the 1,038 voted bills get pages, so the build stays under the 20,000-file free limit; the $5/mo upgrade is deferred to V2-12, where email sending requires it. | The one-time backfill is the cost that decided it: at 1 req/s a full 38,756-bill fetch is ≥ ~43 h ≈ 2,590 GitHub Actions minutes, more than a whole month's free allowance (H24), so **it runs locally once and is committed, never in CI.** Steady state must then be actions-only for known bills (~5–7 min/night) rather than a full refetch (~19–29 min/night), which would not fit beside the D86 nightly. Option (a) was rejected because a bill invisible until its first recorded vote defeats the owner's actual request ("get an alert when a bill that affects gun rights comes up"); pages for all 38,756 were rejected as 38,756 pages nobody asked for plus a forced plan upgrade. Daily and official-terms-only both preserve the option to add faster alerts and owner bundles later without rework. |

---

## §3 — Architecture & stack

As built today (see §CS) plus the v2 additions:

```
SOURCES (unchanged): api.congress.gov v3 · senate.gov LIS XML · clerk.house.gov XML
  unitedstates/congress-legislators · LegiScan (MS) · govinfo

ingest/ (Python 3.12, uv, pydantic v2, httpx)
  raw cache (data/raw/, gitignored)
   → SQLite build.db (gitignored, V2-1: becomes the required intermediate)
   → deterministic JSON export → data/ (committed, THE public contract)
   → rankings + grades (V2-2/V2-4: computed in the designated scoring module
     from ratified config, published like any other export)

site/ (Astro 5 static, Tailwind, Preact islands for filterable lists)
   → Cloudflare Workers Static Assets, deployed by Workers Builds on push

server code (V2-8+, the only server code):
  worker/ — (a) auth + user data (D1: users, subscriptions, preferences —
  readable, SD-32), (b) alert delivery (V2-12: reads the published events
  feed, sends email), (c) K-anon aggregate counters (v1 §10.2 design, built
  new), (d) aggregate analytics counters (V2-9). No IP writes, logging off.
```

Version pins: as locked in `uv.lock` / `site/package-lock.json` (recorded in
`docs/decisions.md`). New pins (wrangler ≥ 4.34.0, argon2/webcrypto libs) are
recorded there at the increment that adds them.

Hard boundaries carried from v1: no homelab; all published data diffable in
the public repo; no LLM in the publishing path (CI-enforced); symmetry checks
can fail the build; K-anon threshold enforced in code; mobile-first; the
client is open source. Amended boundary (SD-22, then SD-32): "quiz scoring
100% client-side" becomes "**the server stores only what a scheduled feature
needs, and every stored table is listed on `/privacy` before it exists**."

---

## §4 — Repository layout (delta from today)

Today's tree is authoritative (see `git ls-files`). v2 adds/changes:

```
ingest/
  rankings.py        # V2-2: per-metric rank/percentile/mean per chamber
  scoring.py         # V2-4: THE designated composite module (§6.8) — grades
data/
  config/thresholds.yaml   # §0.8 ratified constants, with justifications
  rankings/                # V2-2 exports
  grades/                  # V2-4 exports (incl. formula_version, history)
site/src/pages/
  index.astro              # V2-5: becomes the dashboard
  federal/                 # V2-5: Federal tab + filterable list pages
  states/                  # V2-5: States tab (MS entry; grows over time)
worker/                    # V2-8: wrangler project (auth/sync + counters)
docs/
  archive/2026-08-13-pre-v2/   # v1 spec, scope doc, inc-12 plan (unchanged)
  kickoff-v2.md
```

`data/raw/` and `build.db` stay gitignored. `data/` remains the published
dataset; everything in it is public record.

---

## §5 — Data schemas (delta; pydantic, JSON mirrors field names)

Existing schemas in `ingest/models.py` are authoritative and unchanged unless
listed. Export rules (sorted, LF, deterministic, `source_url` everywhere)
unchanged.

- **MemberVote** — schema unchanged; **coverage changes**: V2-1 persists a row
  for every serving member of both chambers, not only MS. `Member` records
  ingest for the full roster (congress-legislators is already the source; the
  covered set is never hardcoded — SD-7 family).
- **Thresholds config** (`data/config/thresholds.yaml`, new): per entry —
  `key` (what it gates), `value`, `labels` (the exact rendered words),
  `justification` (owner's plain-language reasoning), `citation`
  (source URL or null), `ratified` (date). CI check: every evaluative string
  rendered on the site traces to an entry (§6.8).
- **Rankings export** (new, V2-2): per metric × member — value, rank, covered
  N, percentile, chamber, mean/median for the chamber and per party. Ties:
  standard competition ranking (mechanical choice — ADR, not owner).
- **Grades export** (new, V2-4): per member — per-category grade, overall
  grade, `formula_version`, inputs by reference (metric keys), computed-at
  date. History retained per the D45/R-3 time-series mechanism so the trend
  chart (V2-6) and *historical re-grading under a tweaked formula* (owner
  requirement) are possible: grades are always recomputable for any past date
  from retained metric history + any formula version.
- **Account model** (V2-8/V2-12, D1 tables — never exported to `data/`;
  readable, SD-32):
  `users(id, email, email_verified_at, pw_hash argon2id, created_at)`;
  `email_verifications(user_id, email, code_hash, created_at)` — the address a
  reader has given but not yet confirmed, plus the one-time code sent to confirm
  it (double opt-in; `docs/plan-subscriptions-and-alerts.md` task 1). **Added
  2026-10-06 by SD-38: SEVEN tables, not six.** The owner ratified disclosing
  this one on its own line rather than folding it into "your email address", so
  the storage list the reader is shown has seven items and the V2-7 accuracy
  test counts seven. Columns settle in V2-8; the disclosure guard compares
  table names. No lifetime is stated here or on the site — the code's expiry
  window is unratified (owner question Q4, with `deliveries` retention);
  `preferences(user_id, json, updated_at)` — quiz answers, issue weights,
  settings;
  `subscriptions(user_id, kind ∈ {bill, topic, member}, key, cadence, created_at)`;
  `deliveries(user_id, event_key, sent_at)` — alert idempotency;
  `channels(user_id, kind ∈ {email, phone, push}, address, verified_at)` —
  phone only after H21;
  `profiles(user_id, published_json, updated_at)` — the opt-in public profile;
  published means public.
  **Retention, ratified 2026-10-06 by SD-39 (Q4):** `deliveries` rows are purged at
  **90 days**; a signup confirmation code is valid **24 hours**; a password-reset token
  is valid **1 hour**. All three are single-use where applicable and deleted on use, not
  left to expire. V2-8 must define each number **once** in the Worker with a test pinning
  it to this paragraph — same shape as `K_ANON` and the privacy surface, because a
  retention period the code and the record disagree about is a privacy claim that has
  silently become false. **No duration appears on the site** (§6.7): the page states what
  is held and that the code is deleted once confirmed, never how long anything is kept. A schema test asserts that the set of tables and
  columns equals the storage list stated on `/privacy` (§8, the V2-7 accuracy
  test) — the guard is disclosure, not encryption.

**Tier discipline, restated for v2:** Tier 1 = records. Tier 2 = per-metric
outputs of `ingest/metrics.py` (docstring = methodology page, unchanged
mechanism). **Tier 3 exists now** (SD-26): cross-metric composites and grades
— computed **only** in `ingest/scoring.py` from ratified `thresholds.yaml`,
published with formula and inputs. §6.8 replaces the old prohibition guard
with a disclosure guard.

---

## §6 — Global engineering rules

### 6.1 Error handling & failure modes — carried from v1 unchanged
Retry/backoff, stale-not-fatal sources, quarantine (ceiling enforced — v1's
claim is real in code), honor rate limits, nightly failure = last deploy stays
live (**Workers Builds** keeps the last successful build; v1 said "Pages").

### 6.2 Raw cache — carried unchanged.

### 6.3 Determinism — carried, with the record corrected
Double-export byte-identical. Enforced by `tests/test_export_contracts.py`
(v1 wrongly credited `checks/integrity.py`). V2-1's build.db step must not
break this: export reads from build.db in deterministic order.

### 6.4 Banned-strings check — carried UNCHANGED, deliberately
The 12 banned terms are motive-and-character words (`hypocrisy`, `liar`,
`flip-flop`, ...). "Lowest 10% attendance," "worst performers," and "poor
attendance" are none of them and need no list change. **Keeping this check
intact is part of what makes the evaluative posture defensible**: the site
can now say *poor*, and still structurally cannot say *liar*. Extensions only
by PR. Allowlist/exclusions as in code (`banned_words.py`), which is broader
than v1 §6.4 described (three excluded data subtrees + glossary).

### 6.5 Symmetry — re-derived, now MORE load-bearing
Symmetry is the mechanical proof of §0.4.2(c): the same standard applied to
everyone. Covered set = **all serving members of both chambers** after V2-1.
- Vote coverage: every covered member has a MemberVote/Absence for every
  eligible roll call. Gap = fail.
- **Grading coverage (new):** every covered member is graded by the same
  `formula_version`, or appears in a published exceptions list with a stated
  mechanical reason (e.g. served < N eligible days — threshold ratified per
  §0.8). Silent exemption = fail.
- **Best/worst symmetry (new):** any surface listing worst performers renders
  best performers with equal prominence from the same formula.
- Statement/specificity/candidate rules: carried, activate with their parked
  features.

### 6.6 No-LLM structural guard — carried unchanged
Same packages/endpoints/policy checks; scan gains `worker/` when it exists
(already in `SCAN_DIRS`). Interplay with §0.8: an unratified evaluative
constant is treated as seriously as an LLM call — both are the machine
authoring politics.

### 6.7 UI copy rules — rewritten
Carried: vote-row anatomy, official-title affordance, absence strings,
adjacency-marker rules, footer (updated/method/corrections/commit), 380px
mobile-first, Lighthouse ≥ 90.
New:
- Every evaluative label renders with: the formula link (`/methods#...`), the
  denominator or inputs, and the covered-set size ("42nd of 100 senators").
- Grade copy states what is measured, never why ("missed 21% of votes",
  never "doesn't care about the job").
- **Copy flips atomically with the feature that makes it true.** The live
  doctrine strings — "without a thumb on the scale" (`site/src/pages/
  index.astro:16`, `ms/index.astro:17`), "nothing is summarized,
  characterized, or scored" (`methods.astro:26`), "combines nothing into an
  overall score" (`MemberStats.astro:65`), "not a score" (`MemberStats.astro:
  90`), and the `ingest/metrics.py` docstring phrases ("never a score", "The
  site draws no conclusion", the module docstring) — are TRUE today and stay
  until V2-4 ships grades, whereupon V2-4's inventory replaces every one of
  them. Flipping them early publishes a false description (Value #1);
  flipping them late does the same.
- The D36-derived docstring line in `party_unity` ("We do not collect
  individual non-Mississippi members' positions") flips earlier, at V2-1,
  which is when it stops being true.

### 6.8 Tier-3 guard — repurposed from prohibition to disclosure (new)
Old rule: no composite anywhere in the publish path. New rule (SD-26):
composites exist **only** in `ingest/scoring.py`; every published evaluative
output traces to a ratified `thresholds.yaml` entry and a published formula.
The AST guard in `checks/integrity.py` is rewritten to enforce the new shape:
(a) no metric-composition outside `scoring.py`; (b) `scoring.py` reads
thresholds only from the committed config; (c) every `thresholds.yaml` key is
referenced and every rendered evaluative label string appears in the config's
`labels`. Its blind spots (§CS) carry over — document them in the check's
docstring; it is a tripwire backed by review, not a proof.

### 6.9 Archive links (was the phantom "§6.11")
`checks/archive_links.py` + `archive-links.yml` weekly HEAD checks; dead
archive link = statement unpublishable until recaptured. v1 never defined the
§6.11 that `CONTRIBUTING.md` cites; V2-0 fixes the citation to §6.9.

---

## §7 — Build increments

Numbered **V2-0..V2-10** (cannot collide with completed INC-0..INC-12 or the
retired INC-13..22 labels). Each: **Goal → Tasks → Acceptance (runnable) →
On failure.** Sequential unless marked ∥. Commit convention: `V2-N: <what>`.

**Standing rule — deliberate omission:** the owner removed the
AI-classifies-statements idea from this round (it conflicts with the
unamended §0.5). It remains recorded in the archived scope doc. If any
increment's work touches it, **flag it to the owner and stop.** Do not
implement, decide, or delete it.

### V2-0 — Docs-truth pass (zero behavior change)
**Goal:** every governance doc, docstring-adjacent claim, and cross-reference
tells the truth about the system as it exists today — before any behavior
changes, so a later failed increment cannot corrupt the doctrine.
Defense of doing this first: the diff is clean and reviewable, each fix is
independently verifiable, and V2-1+ then edit true documents instead of
compounding stale ones.
**Tasks (complete file inventory):**
1. `docs/data-contract.md` — lines ~150–151: `named_measure_mismatch`
   fail-closed text is stale (D42 superseded D39); align with the shipped
   `stated_position` mechanism. Do NOT touch the "deliberately NOT
   recomputable" section yet — it is still true until V2-1.
2. `CONTRIBUTING.md` — "§6.11" → §6.9 of this spec; four-values paragraph →
   the §0.4 amended values; point at IMPLEMENTATIONv2.md.
3. `docs/PROGRESS.md` — "Current increment" heading still says INC-11; fix to
   reflect INC-12 + D57/D58 done + v2 adopted; delete the four stale
   "Next: INC-N — NOT STARTED" lines (218/243/268/304 region). The ledger
   **continues** in this one file (decision: single append-only ledger, one
   state file, no v2 fork — a new "v2 era" divider section is enough).
4. `ingest/config.py` — module docstring's claim of a worker↔ingest K_ANON
   equality test is false; reword to "single source of truth; the Worker
   (V2-8) must import/mirror this and a test asserts equality when it
   exists." (Docstring-only edit = zero behavior.)
5. `docs/HUMAN-TASKS.md` — add H14–H19 rows (§1); refresh the impact
   narrative.
6. Enable H16 (owner does the click; builder verifies via API that
   force-push is refused).
7. `ingest/checks/banned_words.py` module docstring — its root-out-of-scope
   rationale cites `IMPLEMENTATION.md` (now archived); reword to
   IMPLEMENTATIONv2.md §6.4, which quotes the list for the same reason.
   (Docstring-only edit = zero behavior.)
**Which tests break:** none may. **Acceptance:**
`uv run checks && uv run pytest` green and byte-identical `data/` (no export
ran); `npm run build` green. **On failure:** a docs edit that trips a check
means the edit was wrong — revert it, not the check.

### V2-1 — Federal data expansion (BLOCKING gate for V2-2/V2-5)
**Goal:** positions persisted for **every serving member of both chambers**,
118th–119th; dataset fully recomputable; build scaled.
**Tasks:**
1. Roster: ingest all serving members from congress-legislators (House +
   Senate + the delegate question → **ask the owner**, §0.1 example).
   Retire `COVERED_STATE` semantics in `ingest/config.py` (the constant may
   remain for the MS state layer's use; federal coverage is the roster).
2. Votes: persist all-member positions. Source payloads (Senate LIS XML,
   clerk XML, Congress.gov) already carry them; re-parse from `data/raw/`
   cache where present rather than re-fetching (§0.7).
   Scale numbers (measured 2026-08-13): 3,467 rolls; expect ≈ **1.0M
   member-vote rows** (1,886 House rolls × ~435 + 1,581 Senate × ~100), votes
   files ~1.2 KB → ~15–25 KB each, `data/votes/` ~4 MB → ~50 MB. Shard
   `data/votes/` by congress subdirectory to keep directories listable.
3. Build accelerator (SD-29): `build.db` (SQLite, gitignored) becomes the
   required intermediate between ingest and export/site build; the flat-file
   defer recorded in the archived `inc-12-plan.md` §build.db is hereby
   triggered. Export stays deterministic (§6.3).
4. Pages: member pages for ~541 members. At `PAGE_SIZE=200` naïvely ≈
   5,000–9,000 new pages → projected total ~13,000–16,000 built files vs the
   **20,000-file Workers Free limit (100,000 Paid; 25 MiB/file — verified
   2026-08-13, re-verify at deploy, H14)**. Restructure the vote record:
   default member page = summary + latest votes; full record paginated
   per-congress (halves page counts) or raise PAGE_SIZE — builder's
   mechanical choice, ADR it. **CI must print and assert the built file
   count** against the plan limit (H14).
5. `docs/data-contract.md` v2: the "What is deliberately NOT recomputable"
   section is **deleted and replaced** by its inverse — chamber totals are
   now fully recomputable from published member positions; third parties can
   re-derive everything. Say so plainly: for a project whose pitch is "check
   my math," this is the credibility upgrade of the pivot. Retire builder
   D36 with a dated ADR (D59+).
6. `verify-recompute` invariant upgraded: recomputed chamber totals must
   equal `RollCall.totals` for 100% of rolls **from full member positions**
   (the old subset check becomes the strict equality it always wanted to be).
7. `ingest/metrics.py` `party_unity` docstring: the "we do not collect
   non-Mississippi positions" line flips here (§6.7); metric semantics may
   now use true per-member data (keep the aggregate formula unless the owner
   is asked — the published methodology must match what runs).
8. Symmetry vote-coverage over the full covered set; quarantine ceiling
   applies per chamber.
9. Git/repo strategy: the published dataset is the repo; expect a one-time
   ~50 MB commit and larger nightly diffs. Record repo-size observations in
   the ADR; if `.git` growth becomes pathological (> a few hundred MB),
   propose options to the owner — do not adopt LFS/splitting unilaterally.
**Which tests break legitimately:** manifest-count fixtures, any test
asserting 6 members/10,626 rows, bootstrap COVERED_STATE assertions,
data-contract prose tests. **Must stay green untouched:** classifier goldens,
export determinism, banned-words scope tests, no-LLM, MS partition checks.
**Acceptance:** `uv run checks && uv run pytest && uv run verify-recompute`
green; `npm run build` green with file-count printed < plan limit;
`npm run test:links` green. **On failure:** missing positions for any member
on any roll → `data/quality/` gap report; CI red until zero or quarantined
with cause.

### V2-2 — Ranking & percentile layer
**Goal:** every Tier-2 metric gains rank/percentile/mean context per chamber
and per party — pure math, no thresholds, no labels yet.
**Tasks:** `ingest/rankings.py` + export per §5; `/methods` gains one section
per ranking family (extend `check-metrics-sections.mjs` set-equality
legitimately); party means published (R-vs-D and R-vs-R per §0.4.2(c));
coverage tooling lands (§8) for `metrics.py`/`rankings.py`.
**Tests:** metrics-sections script updated; recompute extended.
**Acceptance:** `uv run checks && uv run pytest && uv run verify-recompute &&
npm run build && npm run test:metrics-sections`. **On failure:** a ranking
that cannot be recomputed from published data may not export.

### V2-3 — Member-page rank context
**Goal:** the five stat tiles show "value — rank of N (percentile)" with
formula links; the surface Gate 1's grades will later land on.
**Tasks:** `site/src/components/MemberStats.astro` + member page templates;
copy per §6.7 (rank context is factual — the "combines nothing into an
overall score" caption stays true and stays put until V2-4).
**Tests:** e2e member-page specs update; axe + 380px must stay green.
**Acceptance:** `npm run build && npm run test:e2e && npm run
test:lighthouse` + python suite green.

### V2-4 — Grades (SD-26) — first evaluative increment
**Goal:** per-category grades + one overall grade per member, from ratified
thresholds, with every doctrine string flipped in the same commit series.
**Tasks:**
1. **H15 ratification round one** (§0.8): builder proposes per-category
   threshold options and overall-grade weights in plain English (with
   references, e.g. how attendance distributions actually look in the data);
   owner ratifies; `data/config/thresholds.yaml` lands with justifications.
2. `ingest/scoring.py` (the designated module) + grades export + rendering
   on member pages (tiles gain grade badges; overall grade with formula
   link and inputs).
3. §6.8 guard rewrite in `checks/integrity.py` + its tests (old prohibition
   tests retire **in the same change** as the new disclosure tests land).
4. **Copy inventory — every string flips here** (§6.7): `index.astro:16`,
   `ms/index.astro:17` (or route-appropriate wording), `methods.astro:26`,
   `MemberStats.astro:65` caption, `:90` adjacency label (adjacency stays
   "not a score" — SD-20 — but the caption around it changes),
   `ingest/metrics.py` module + `cosponsor_vote_gap` + `named_measure_
   mismatch` docstrings ("never a score"/"draws no conclusion" → "scored
   only under the published formula; motive never asserted"). New wording
   must satisfy §0.4.2 and pass banned-words.
5. Symmetry: grading-coverage + best/worst rules (§6.5) activate.
**Which tests break legitimately:** Tier-3 prohibition tests, docstring-text
assertions, e2e snapshots, methods-page content tests. **Must stay green:**
banned-words (grade copy uses no motive words), determinism, recompute,
no-LLM. **Acceptance:** `uv run checks && uv run pytest && uv run
verify-recompute && npm run build && npm run test:metrics-sections && npm run
test:e2e`. **On failure:** an unratified threshold in the config or an
evaluative string not traceable to it fails `checks` — that is the §6.8 guard
working; get ratification, don't relax the guard.

### V2-5 — Landing dashboard + Federal/States tabs
**Goal:** `civicledger.net/` becomes the overview dashboard — headline stats
("averages… or the lowest 10% of a category… something that makes users go
wide-eyed"), every metric clickable into a filterable all-members list.
**Tasks:** dashboard `index.astro` (headline tiles from rankings/grades
exports; the "lowest N%" cut is a ratified threshold — H15 round two);
`/federal` tab with chamber list pages + Preact filterable/sortable list
island (static data, client filtering); `/states` tab listing MS (and a
plain "more states over time" note); nav update; every dashboard tile
deep-links to the filtered list that reproduces it.
**Tests:** e2e drill-down flow (dashboard tile → filtered list → member
page); Lighthouse on the new heaviest pages.
**Acceptance:** `npm run build && npm run test:e2e && npm run test:lighthouse
&& npm run test:links` + python suite. **On failure:** a headline number that
cannot be clicked through to its full list may not render.

### V2-6 — Grade-over-time trend
**Goal:** the "stock chart" — overall and per-category grade trends, per
member and aggregate (party means, chamber mean), from retained metric
history (D45/R-3), including recompute-under-current-formula so a formula
tweak re-grades history honestly (`formula_version` on every point).
**Acceptance:** `uv run verify-recompute` covers a historical point;
`npm run build && npm run test:e2e`. **On failure:** if history depth is
insufficient for a chart, render the honest short series — never synthesize
backfill.

### V2-7 — Privacy truth gate (BLOCKING: nothing that stores user data — V2-8/V2-9/V2-12/V2-13 — ships first)
**Goal:** every privacy statement the site will make is written, true, and
deployed **before the first byte of user data is collected**.
**Tasks:**
1. Rewrite `/privacy` (`site/src/pages/privacy.astro`): what is and isn't
   collected today; what V2-8/V2-9/V2-12/V2-13 will collect, exactly (the §5
   table list, in plain words); that the operator can read it (SD-32); the
   public-profile carve-out (**"anything you choose to publish on your
   profile is public"**); deletion semantics; each service provider's role
   (email provider H18; texting provider H21 if chosen) and what it sees; the
   K-anon rule; data never sold; that anonymous use and the feeds (V2-11)
   need no account.
2. Author the threat-model page (new content, v1 §A2 outline as the skeleton,
   rewritten for the account era): what a legal demand can yield — **the
   account table, what each account follows, its preferences and answers,
   and its notification addresses, all readable** — stated plainly, with the
   mitigations that remain. **▶ AMENDED BY SD-34 (2026-10-05): two of the four
   mitigations this task originally named are withdrawn.** "Nothing stored
   beyond the listed tables" and "no IP logs" are gone — the project may log
   and may store beyond §5. The page must NOT claim either. What remains to
   state: **hard delete**, **K-anon for anything published**, and **the one
   standing promise, that the data is never sold** (§10). Also state the
   host's position plainly, as `/privacy` now does: Cloudflare receives the
   reader's requests and that is outside the operator's control. A page that
   lists a withdrawn guarantee is exactly the Value #1 failure this whole
   increment exists to prevent.
3. **H19 canary decision — DONE (SD-35, owner, 2026-10-05): RETIRED.** Asked
   in plain terms whether to retire the warrant-canary idea or reshape it to
   "we have received no demand as of {date}", the owner said retire it. So
   there is no canary page, no canary line, and **nothing to build**. No
   canary was ever published, so retiring costs nothing visible. Do not
   reintroduce one without a dated decision — and note why the reshaped
   version was not free: "no demand as of {date}" is a claim that must be
   re-verified and re-dated on every deploy or it silently becomes a lie, and
   a stale canary is worse than none.
4. `docs/data-contract.md` + `CONTRIBUTING.md` privacy language aligned.
**Acceptance:** `npm run build && npm run test:links` + a new accuracy test
(grep-style, per v1 §10.4's idea): the deployed privacy page's stated
storage list and K constant match code/config. **On failure:** the accuracy
test failing means site text and system diverged — fix the text or the
system, never the test.

### V2-8 — Accounts + preference sync (SD-28 as amended by SD-32; needs H17, H18)
**Goal:** email+password accounts (profiles) whose preferences the site stores
and can read (SD-32), with the email verified before anything is sent to it.
**Tasks:** `worker/` wrangler project + D1 schema per §5 (schema test: tables
== the `/privacy` storage list); signup/login (Argon2id server-side); email
verification (double opt-in) and password reset by email — no data loss on
reset; `preferences` sync (readable JSON); opt-in public profile (explicit
publish action); hard delete cascading every table; Turnstile on write
endpoints; logging/logpush off with config committed; K-anon counter
endpoints (v1 §10.2 design, built new) for any trend the site publishes.
**Tests (new families):** Playwright network assertion that requests carry
only the documented fields; D1 schema assertion against the `/privacy` list;
K-anon gate (49 → nothing renders, 50 → renders); deletion e2e (every row
gone).
**Acceptance:** full python + `npm run build && npm run test:e2e` including
the new specs against `wrangler dev`. **On failure:** any stored field or
table not listed on `/privacy` is a Value-#1 breach — stop, fix the page or
the schema, add the regression test, then continue.

### V2-9 — Analytics (amended SD-17)
**Goal:** aggregate, cookieless traffic + state-of-origin, to prioritize
which states to add.
**Tasks:** Cloudflare Web Analytics (cookieless) for traffic/pages; if
state-level granularity requires it, an aggregate region counter on the
Worker (increment `(iso_week, region)`; IP read transiently for geo by the
edge, never written) — same K-anon publication gate if any of it renders
publicly; `/privacy` updated in the same increment (§6.7 atomicity).
**Acceptance:** `npm run build && npm run test:e2e` (cookie-absence
assertion) + accuracy test from V2-7 still green.

### V2-10 — Mississippi mirror & fold-in (SD-30)
**Goal:** MS presentation mirrors federal (ranks, grades, dashboard entry)
and lives under the States tab; the owner's "all of the data presented on
the House and Senate members at the federal level will be mirrored in the
state reps portion."
**Tasks:** apply rankings/scoring to the MS partition (D58 precedent: reuse
formulas verbatim, MS-specific thresholds ratified via H15 round three —
MS distributions differ); `/ms` routes preserved or redirected under
`/states/ms`; limitations page updated.
**Acceptance:** full suite: `uv run checks && uv run pytest && uv run
verify-recompute && npm run build && npm run test:links && npm run
test:metrics-sections && npm run test:e2e && npm run test:lighthouse`.

### V2-11 · V2-12 · V2-13 — Bill activity + topics + feeds · Subscriptions + email alerts · Text / push (ratified priority, SD-32, 2026-09-23)
Full Goal/Tasks/Acceptance/On-failure text lives in
`docs/plan-subscriptions-and-alerts.md` and is folded here once V2-11's API
verification (its task 1) lands the measured numbers. **Order:** V2-11 (zero
collection; needs no privacy gate) → V2-7 → V2-8 → V2-12 → V2-13. V2-6 is
deferred until enough nightly grade history exists to chart. Decision 1 in
that plan's §1 is ratified as SD-32 (the site reads what it stores); its
decisions 2–7 are asked with real numbers at the end of V2-11 task 1.

---

## §8 — Testing requirements

Carried: pytest model/classifier/metric/export suites; e2e; the checks suite;
`verify-recompute` as the third-party-recompute proof.
Corrected from v1 (which claimed unenforced things):
- **Coverage is enforced from V2-2 on**, where it matters: `pytest-cov` with
  100% branch on `ingest/metrics.py`, `ingest/rankings.py`,
  `ingest/scoring.py`, `ingest/classify.py` (small, pure,
  credibility-bearing modules); no repo-wide floor. If 100% proves
  unreachable on a specific module, ask the owner with the uncovered branches
  listed — do not silently lower it.
- The `correction:` convention and no-force-push are enforced by H16 branch
  protection plus CI, not by prose.
- New v2 test families: §6.8 disclosure-guard tests; threshold-traceability;
  grading-coverage symmetry; documented-fields-only network assertions and
  the D1-schema-equals-`/privacy`-list assertion (SD-32); K-anon render gate;
  built-file-count guard (V2-1); events recompute + feed validity (V2-11);
  alert idempotency + unsubscribe (V2-12).

## §9 — CI/CD

- `ci.yml` (PR + main): lint, tests, checks, site build. Red blocks merge.
- `nightly.yml` (cron): ingest (hash/diff-gated) → classify → checks → export
  → commit `data: nightly {date}` → push → **Workers Builds auto-deploys**.
  Failure = GitHub notification; last deploy stays live.
- `archive-links.yml` (weekly). The v1-named `archive-recapture.yml` /
  `agg-export.yml` never existed; an aggregates-export job is added at V2-8
  when there are counters to export.
- Branch protection per H16.

## §10 — Privacy engineering v2 (SD-28; replaces v1 §10)

**The consequence, stated once, plainly (owner: read this — updated for
SD-32, 2026-09-23).** Once V2-8 ships, the site operates a database that
links email addresses (and, if V2-13 SMS is ratified, phone numbers) to what
each person follows, their preferences, and their quiz answers — **all of it
readable by the operator and producible under a legal demand.** The
2026-08-13 design encrypted answers on the device so a demand yielded only
ciphertext; the owner retired that on 2026-09-23 because server-sent alerts
require the server to read the subscription list, and chose to let the site
read and collect what its features need.

**▶ SD-34 (2026-10-05) WITHDRAWS THE REST OF THE GUARANTEES.** SD-32 had kept
a remainder — "nothing is stored beyond the tables listed in §5 and on
`/privacy`; hard deletion; no IP columns and logging off" — and the owner has
now withdrawn it, in his words: *"what this is going to evolve to, I am going
to have to track this info. My only promise is to never sell this data."* So
the project MAY log requests, keep IP columns, set cookies for the anonymous
reader, hold per-submission rows behind aggregates, let the anonymous
reader's browsing reach the Worker, and store beyond the §5 tables. **Nothing
in this section forbids tracking any more.** The email/texting providers see
addresses and message text.

**THE ONE STANDING PROMISE: the data is never sold.** This is the only
privacy claim in this project stated by the owner himself rather than
inserted by a builder, and per §0.8 it is the only one publishable without
further ratification. It must appear on `/privacy`. Note what makes it
different in kind from the claims it replaces: selling data is an act of the
operator, so the promise cannot be falsified by the host, the stack, or a
feature shipped later — which is exactly why every withdrawn claim was
indefensible and this one is not.

**Three things SD-34 did NOT withdraw, and a future session must not read it
as withdrawing** (the owner spoke about promises to readers, not about
engineering safety): **Argon2id** password hashing; the **K-anon (=50) render
gate** on published aggregates, which keeps a *published* figure from
re-identifying an individual and is therefore a Value #1 accuracy control as
much as a privacy one; and **hard deletion on request**, a user-facing right
he was not asked about and did not revoke. Removing any of those needs its
own dated decision.

- **10.1 Client rules:** no third-party CDNs; localStorage for local state
  with a visible erase button; `data/` is read at BUILD time only and is
  never fetched at runtime — that one is an architecture fact (the repo is
  private, so the loader cannot read it from a browser) and it survives
  SD-34 as architecture while no longer being offered as a privacy
  guarantee. `site/src/lib/data.ts` and `site/src/pages/events/[month].json.ts`
  both cite this clause, so do not delete it without updating them.
  (SD-34 withdrew "no cookies for the anonymous experience" and "the
  anonymous reader's browsing never touches the Worker".)
- **10.2 Server code:** the `worker/` project only. Auth + the readable user
  tables of §5 + integer counters + alert delivery. Argon2id for password
  hashes. (SD-34 withdrew "no per-submission rows for aggregates", "no IP
  columns anywhere", "logging off", and the requirement that every stored
  table be listed on `/privacy`. `/privacy` must still be accurate about what
  is stored — V2-7 and the §10.4 accuracy test are unchanged — but the page
  is now a description, not a guarantee.)
- **10.3 Publication path:** any server-derived figure the site renders
  (trends, analytics) passes the K-anon (=50) gate before export to
  `data/aggregates/`; below-threshold cells never leave D1. The
  worker↔ingest K constant equality test becomes real at V2-8 (making
  `config.py`'s docstring true at last).
- **10.4 Pages:** `/privacy` + threat-model page per V2-7, with the
  drift-proof accuracy test. **No canary** — retired by the owner, SD-35
  (2026-10-05); H19 is closed and nothing is built for it.

---

## §A1 — vote_class rules table
Carried unchanged. The authoritative table is the code
(`ingest/classify.py`) + its golden tests; the archived v1 §A1 is its
historical statement. It renders on `/methods` as before.

## §A2 — Threat-model outline · §A3 — Banned strings · §A4 — Corrections
A2: superseded by V2-7's rewrite (v1's outline is the skeleton, the content
changes). A3: carried — the list is code (§6.4). A4: carried —
`docs/correction-process.md` verified still true and untouched by the
amendments.

---

## Appendix B — Disposition table (the anti-loss proof)

Every numbered v1 section, every v1 decision, and every scope-document want.
**Carried** = still true/required, restated in v2. **Amended** = changed as
described. **Retired** = no longer holds, reason given. **Parked** = still
wanted, deliberately not scheduled in V2-0..V2-10; lives in this table as
the backlog of record.

### v1 sections

| v1 § | One line | Disposition |
|---|---|---|
| §0.1 | Never ask the owner | **Retired** (owner amendment) → v2 §0.1 ask-when-unsure, plain language |
| §0.2 | Human tasks block by design | **Carried**, re-motivated (access, not silence) |
| §0.3 | Acceptance passes before next increment | **Carried** |
| §0.4 | Four values | **Amended** — see §0.4; #1 and #4 unchanged, #2 and #3 rewritten |
| §0.5 | No LLM in publishing path | **Carried unchanged** (explicitly not amended) |
| §0.6 | Windows dev env | **Carried** + stdout-ASCII builder rule noted |
| §0.7 | Raw cache first | **Carried** |
| §1 H1–H13 | Human task table | **Carried** — `docs/HUMAN-TASKS.md` is authoritative status; v2 adds H14–H19 |
| §2 D1–D20 | Spec decisions | **Renamed SD-1..SD-20**; per-decision dispositions in §2 (SD-18, SD-19 retired; SD-2, SD-3, SD-12→28, SD-17 amended; rest carried/parked) |
| §3 | Architecture & stack | **Amended** (Pages→Workers; build.db promoted; worker/ scope) |
| §4 | Repo layout | **Amended** (delta in §4; v1's `archive-recapture.yml`/`agg-export.yml` never existed) |
| §5 | Schemas + tier discipline | **Amended** (additions §5; Tier 3 now exists under §6.8 discipline) |
| §6.1 | Failure modes | **Carried** (quarantine ceiling confirmed enforced) |
| §6.2 | Raw cache detail | **Carried** |
| §6.3 | Determinism | **Carried**, enforcement credit corrected to `tests/test_export_contracts.py` |
| §6.4 | Banned strings | **Carried unchanged, deliberately** (§6.4 rationale) |
| §6.5 | Symmetry | **Amended** — covered set widens; grading-coverage + best/worst rules added |
| §6.6 | No-LLM guard | **Carried** |
| §6.7 | UI copy rules | **Amended** — evaluative-label rendering rules; atomic copy flips |
| "§6.11" | (cited by CONTRIBUTING, never defined) | **Fixed** as §6.9 archive links |
| §7 INC-0..12 | Built increments | **Retired (completed)** — live; history in PROGRESS.md; do not rebuild |
| §7 INC-13 | Candidate tracker | **Parked** (wanted per scope doc; post-V2 backlog; H10 rubric intact) |
| §7 INC-14/15 | Quiz + alignment outputs | **Parked** — note INC-15's no-cross-issue-aggregate rule is superseded by SD-26 for *site* grades; alignment-to-YOUR-values remains a reader-side feature when built |
| §7 INC-16 | Aggregates Worker + privacy pages | **Superseded** by V2-7/V2-8/V2-9 (was never built) |
| §7 INC-17 | Challenge & calibration | **Parked** |
| §7 INC-18 | Longitudinal drift | **Parked** (K-anon transition counters concept reused by V2-8) |
| §7 INC-19 | Bill diff viewer | **Parked** (SD-14 carried) |
| §7 INC-20 | "Nobody Told You" + glossary | **Parked** (glossary exists and stays the banned-words allowlist) |
| §7 INC-21 | Ballot builder + share cards | **Parked** (SD-10 carried) |
| §7 INC-22 | ZK sync stub | **Retired** — superseded by SD-28/V2-8, whose encryption core was then retired by SD-32 (2026-09-23) |
| §8 | Testing | **Amended** — coverage claim made real and scoped (V2-2 on) |
| §9 | CI/CD | **Amended** — real workflow names; Workers Builds; H16 |
| §10.1–10.4 | Privacy engineering | **Superseded** by v2 §10 (old text described a never-built system whose premises the owner amended away) |
| §A1 | vote_class table | **Carried** (code authoritative) |
| §A2 | Threat-model outline | **Superseded** (V2-7 rewrite; outline reused as skeleton) |
| §A3 | Banned list pointer | **Carried** |
| §A4 | Correction skeleton | **Carried** (process doc verified unchanged) |

### Scope document (`docs/archive/2026-08-13-pre-v2/civic-ledger-scope.md`)

| Want | Disposition |
|---|---|
| Formula-based grading, weights per category, overall performance grade | **Carried** → SD-26, V2-4 (site-published, fixed; the 2026-08-12 reader-adjustable reframe is superseded by the owner's Gate-1 choice) |
| "No thumb on the scale" | **Amended** → §0.4.2 disclosure standard (uniform standard + full transparency replaces publish-no-judgment) |
| Every fact links to official source; curated source list | **Carried** (unchanged enforcement) |
| Statements hand-curated one at a time | **Carried** (parked with statement features) |
| **AI-categorize statements → human review dashboard** | **PARKED BY OWNER — do not touch.** Conflicts with unamended §0.5; flag and stop if reached (§7 standing rule) |
| Anonymous mode + optional email/password accounts + elective public profile | **Carried** → SD-28, V2-8 (matches the owner's original sketch almost exactly) |
| Audience: younger, BLUF, engagement | **Carried** as design intent → V2-5 dashboard is its first concrete expression |
| Data entities (member/bill/rollcall/statement/issue/jurisdiction) | **Carried** — built ones live; statement/issue entities parked with their features |
| Jurisdiction priority ladder (State→Federal→President→VP→appointees→50 states) | **Amended** — owner's 2026-08-13 pivot puts Federal first; President/VP/appointees remain parked wants |
| Rankings: state internal, federal, top/bottom 10, "overall American politician grade" trend | **Carried** → V2-2/V2-5/V2-6 |
| Compare states vs states, states vs federal | **Parked** (needs ≥ 2 states; note in V2-10) |
| Adjust grading historically as formula tweaks (no skewed long-term metrics) | **Carried** → `formula_version` + history recompute, V2-6 |
| Track politician financials/net worth/stock-portfolio over time | **Parked** (new data sources; propose post-V2) |
| PAC donations adjacent to votes, never bought-vote claims | **Carried** (SD-20; parked with FEC work, SD-16) |
| Say-vs-do gap as heavy grading input | **Parked with statements** — grading v1 (V2-4) uses vote-record metrics; say-vs-do joins the formula when the statement ledger has content (H8), via H15 ratification |
| Missed votes + absence reasons + outreach-for-comment with logged non-response | **Carried** (absences live); the outreach/auto-email idea **parked** — flag to owner before building (it contacts officials' offices in his name) |
| Cosponsor metrics incl. cross-aisle | **Carried** (metrics live; cross-aisle split is a V2-2 ranking candidate — ask owner at H15 whether it becomes graded) |
| Bill grading vs YOUR values | **Parked** (quiz-dependent, INC-14/15 family) |
| Candidate ran-on vs did-in-office | **Parked** (INC-13 family) |
| Tools & views: member/bill/roll-call pages | **Carried (built)** |
| Quiz, issue-priority selector, challenge tab, bill diff, feed, ballot, share cards, disagree-with-me, drift check-in | **Parked** (each retains its v1 increment design as the reference) |
| Neutrality × gradings fork | **Re-resolved** by SD-26 (owner, 2026-08-13) — supersedes the 2026-08-12 reader-side resolution |
| 50-state rollout phasing; "Request a state" + email-on-add | **Carried in spirit** → States tab grows over time (V2-5); request-a-state feature parked (email collection touches V2-7 scope — flag when built) |
| State data plumbing (no single API for 50 states) | **Carried** — unsolved beyond LegiScan/MS; revisit per state |
| Federal all-officials: record or gradings? | **Resolved** — gradings for everyone (SD-26) |
| Visual design direction | **Parked** (owner's separate reference-reaction step, unchanged) |

---

*End of specification. Build order: V2-0 → V2-5 done; then (SD-32) V2-11 →
V2-7 → V2-8 → V2-12 → V2-13, with V2-6, V2-9, V2-10 after. Blocking gates:
V2-1 before V2-2/V2-5; V2-7 before anything that stores user data (V2-8,
V2-9, V2-12, V2-13) — an ordering, not a prohibition. Every stop point is a
coherent public product. When unsure — especially about what
counts as good or poor performance — ask the owner, in plain language.*
