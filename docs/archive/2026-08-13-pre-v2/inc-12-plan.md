# INC-12 — Mississippi state legislature layer (branch A / GO) — scope & plan

> **STATUS: ✅ COMPLETE (2026-08-12).** All 6 phases shipped (ADRs D51–D56), plus the
> follow-on member-page Tier-2 stats for both jurisdictions (D57 federal, D58 MS). CI green,
> live on `civicledger.net/ms`. This doc is retained as the original scoping record; the
> authoritative current state is `docs/PROGRESS.md`. Actuals vs. the plan below: 174
> members / 1,725 rolls / 905 voted bills / 144,007 member votes / 0 quarantined; site
> 4,540→7,919 pages; the integrity spot-check shipped as the 5 GO-verdict samples (offline),
> and MS metrics (D58) were added on top of the plan's phase list.

Scoping doc for the next increment, written 2026-08-12 after the R-1..R-6 review
hardening closed. Branch A is unlocked (`data/quality/ms-state-verdict.md`: GO, 5/5
position match, 470 positions). This is the **largest increment yet** — it adds a whole
second jurisdiction. Nothing here is built; this is the plan to review before starting.

## Prerequisites — all in place

- `LEGISCAN_API_KEY` present **locally** (`.env`, 32 chars) **and as a GitHub Actions
  secret** (`gh secret list`: set 2026-08-11). Nightly can ingest state data.
- `ingest/sources/legiscan.py` exists (`session_list`, `dataset_list`, `get_dataset`);
  key handled as a query param kept out of the cache key + `.meta` (verified).
- GO evidence + reconciliation rules committed (`data/quality/samples/ms_vote_xcheck/`).
- No owner/human task blocks the build. (Owner content tasks like H8 are unrelated.)

## Data source & shape (verified from the spike + samples)

- **`getSessionList(MS)`** → current session = **2026 Regular Session, `session_id` 2249**,
  `sine_die: 1` (adjourned → the dataset is essentially STATIC; nightly is mostly a no-op).
- **`getDatasetList(MS)`** → per-session `access_key` + **`dataset_hash`** — one cheap call
  that decides whether anything needs downloading (the nightly gate; R-5 politeness spirit).
- **`getDataset(session_id, access_key)`** → a JSON envelope carrying a **base64-encoded
  ZIP** of the whole session (people, bills, rollcalls as JSON files). The spike only
  automated `getSessionList`; decoding + parsing the ZIP is **new work**. `getDataset` for
  2249 = **1,725 roll calls**, every one with full per-person `votes[]` of
  `{people_id, vote_text ∈ Yea|Nay|NV}`, and a **174-person masterlist** resolving
  `people_id → {name, party, district, ...}`.

## The #1 architecture constraint — the fail-closed guards are FEDERAL-shaped

The guards built through INC-11 (including the R-2 churn guards from last session) assume
every record in `data/{members,votes}/` is a federal record. Dropped in as-is, MS records
would light up CI red immediately:

- `metrics._load` raises (an MS member has no `data/legislation/` record — the R-2 guard).
- `checks/symmetry._covered` reads **all** members with no jurisdiction filter → MS terms
  overlap the congress windows → expects MS members on every federal roll → thousands of
  coverage gaps.
- `checks/classification.py` fails on any `unclassified` roll; the §A1 rules are
  congressional question strings — MS rolls won't match.
- `verify_recompute` iterates 100% of rolls; `export._count_dataset` counts everything;
  `data.ts::getAllVotes` feeds every federal member timeline.

**Decision: partitioned storage.** State data lives under **`data/state/ms/{members,
votes,bills}/`** (same canonical pydantic models). Every consumer then opts IN to state
data deliberately, instead of every federal guard needing a same-directory filter retrofit.
Deliverable includes a **consumer-sweep checklist**: grep every use of `MEMBERS_DIR`,
`VOTES_DIR`, `BILLS_DIR`, `repo_root() / "data"` and confirm each either stays
federal-only or explicitly handles the state partition.

Side benefit: with partitioned dirs, add `jurisdiction: str = "us"` (default) to the
models and federal files DON'T need rewriting — pydantic fills the default on read.
**One trap to settle:** `classify.run` rewrites vote files in place, so on the next
vote-change night the new field would start leaking into federal records piecemeal. Settle
deliberately — a one-time migration commit that stamps the field on all federal rolls, OR
verify classify's round-trip preserves byte-identity and pin it with a test.

## Schema extension (extend canonical, never fork a state schema — spec §INC-12, review §6)

Add `jurisdiction` to `Member`, `RollCall`, `Bill`, `MemberVote`. Per-record design items
to resolve during the build (named here, not all decided now):

- **id scheme:** `h-119-1-0234` doesn't fit a state roll → an `ms-` namespaced form (e.g.
  `ms-h-2249-<n>`); member ids in a new **`ms_leg` namespace** (`ms-HD-048` / `ms-<people_id>`),
  with a crosswalk file (`people_id ↔ ms_leg id ↔ district`).
- **`RollCall.congress`** — not applicable to a state roll → likely `int | None` + a
  session/year field, or a jurisdiction-scoped session id.
- **MS bill-id form** vs `ingest/bills.py::parse_bill_id` (HB/SB vs hr/s).
- **`vote_class`** — the §A1 classifier is congressional; MS question strings need either
  new rules or a jurisdiction-scoped classification pass (state rolls must not fail the
  federal `classification` gate).
- **party** — `Member.party` is `Literal["D","R","I"]`; confirm MS legislators fit (add a
  code only if a real independent/other appears).

## Build phases (proposed order)

1. **Schema + storage decision** — add `jurisdiction`; create `data/state/ms/`; settle the
   classify field-leak trap; consumer-sweep checklist. (No data yet.)
2. **Ingest + crosswalk** — TTL-cache `getDataset` (wrap `legiscan._get` with a freshness
   check on the `.meta` `fetched_at`, since it has none today — carried note), decode the
   base64 ZIP, parse people → `ms_leg` members + crosswalk, bills, roll calls with per-person
   positions. `party_totals` is **fully computable** here (unlike federal — LegiScan gives
   every position, so this is the whole chamber, not a delegation).
3. **Checks / integrity analog** — a billstatus per-vote-PDF spot check (10 votes) reusing
   the documented `ms_vote_xcheck` reconciliation rules **verbatim** (they're a gift);
   symmetry/coverage rules scoped to the MS covered set (= all 174 legislators).
   **Bundle the billstatus intermediate CA** — CI/Linux does no AIA chasing (D21).
4. **Site** — state member pages, roll pages, district lookup; wired so zero state data =
   the federal site unchanged.
5. **Nightly wiring** — a LegiScan step gated on `getDatasetList` `dataset_hash` (skip the
   download when the session hash is unchanged; the 2026 session is `sine_die`, so this is
   near-always a no-op).
6. **Public data-limitations page** — an acceptance item, NOT optional: document anything
   LegiScan lacks vs the official record (`/methodology#mississippi` or similar).

## Decisions to record in decisions.md

- **Storage / build.db (review §6 flag):** the review recommends introducing an internal
  SQLite build accelerator "when the second jurisdiction lands" but its BINDING ask is only
  to "record the decision either way." **Recommendation: DEFER + measure + trigger.** MS
  roughly doubles the file/page count (~4,700 → ~6,600 records; ~+174 member + ~+1,725 roll
  pages) — still comfortably flat-file. Measure site-build time before/after; keep flat-file
  for INC-12; record a concrete trigger for adopting build.db (e.g. the 3rd jurisdiction, or
  build time crossing a threshold). Not a blocking question.

## Acceptance (roadmap Phase-4 / IMPLEMENTATION.md §INC-12)

Both chambers' current session ingested; 10-vote billstatus spot check passes; state member
pages render; gaps documented on a public data-limitations page; all existing federal checks
+ tests stay green (the partition must not perturb the federal dataset byte-wise).

## Out of scope for INC-12 (later)

Backfilling prior MS sessions (2025 special, earlier regulars) — one later increment once
the current-session pipeline is proven. District/geocoder-based "find my legislator" beyond
a basic lookup. Any grading/composite (still the §7 owner escalation).
