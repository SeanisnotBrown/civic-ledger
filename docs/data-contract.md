# Data contract — the published dataset

Everything under `data/` (except `data/raw/`, which is gitignored) is the public
record. This document specifies every published file type and field so a third
party can clone the repo and **recompute figures and match** (brief §5.2). The
machine-readable form of each record shape lives in `data/schema/*.schema.json`,
generated from the pydantic models in `ingest/models.py`; this page is the human
companion. Field names in the JSON mirror the model names exactly.

**Global rules** (`ingest/export.py::_dumps`): every file is UTF-8, LF line
endings, keys sorted, 2-space indent, one trailing newline. No wall-clock value
appears inside any record — the single generation timestamp lives in
`data/manifest.json` (see below). `uv run export` run twice on the same dataset
produces byte-identical output; CI asserts this.

---

## `data/members/{bioguide}.json` — one per covered member

Schema: `data/schema/member.schema.json` (model `Member`).

| Field | Type | Notes |
|---|---|---|
| `id` | string | Bioguide id — the canonical member key everywhere. |
| `ids` | object(string→string) | ID crosswalk (`govtrack`, `lis`, `fec`, `opensecrets`, …). Join keys for other sources. |
| `name` | string | Display name. |
| `party` | `"D" \| "R" \| "I"` | Current affiliation = party of the most recent term. |
| `state` | string | Two-letter state (covered set = `MS`). |
| `district` | integer \| null | House district; `null` for senators. |
| `chamber` | `"house" \| "senate"` | |
| `serving` | boolean | Latest term overlaps the current covered Congress. |
| `terms` | array\<Term\> | Full history, sorted by `start`; party switches preserved. |

`Term`: `{ start, end (ISO dates), party ("D"\|"R"\|"I"), chamber ("house"\|"senate") }`.

## `data/votes/{chamber}-{congress}-{session}-{NNNN}.json` — one per roll call

Schema: `data/schema/vote.schema.json` (composite model `VoteFile`). Id form
`h-119-1-0234` / `s-119-1-0031` (chamber-congress-session-roll, 4-digit roll).
The file is a wrapper:

```json
{ "rollcall": { …RollCall… }, "member_votes": [ …MemberVote… ] }
```

`rollcall` (`RollCall`):

| Field | Type | Notes |
|---|---|---|
| `id` | string | Matches the filename stem. |
| `chamber` | `"house" \| "senate"` | |
| `congress` / `session` / `number` | integer | |
| `date` | string | ISO-8601 with source timezone offset. |
| `question` | string | Official question text, verbatim. |
| `vote_class` | `passage \| amendment \| procedural \| nomination \| veto_override \| other` | Classifier output (§A1). Never null. |
| `vote_class_rule` | string | Id of the rule that fired (auditability), e.g. `R-PASS-1`. The sentinel `non_position` marks Speaker-election rolls (see below). |
| `bill_id` | string \| null | Linked bill (`hr2-119`) or null (nominations, quorum, etc.). |
| `result` | string | Official result text (e.g. `Passed`). |
| `totals` | object(string→int) | **Chamber-wide** tally: `yea`/`nay`/`present`/`not_voting`. See the recompute note. |
| `party_totals` | object(string→object) \| null | **Aggregate** per-party split of `totals`, keyed by party letter (`D`/`R`/`I`), each `{yea,nay,present,not_voting}`. Derived from the raw response's per-member party (D36 retired at V2-1 — individual positions are now stored too, see `member_votes` below; `party_totals` is kept as the chamber's own official per-party tally, not a stand-in for missing data). `null` on `non_position` rolls. Sums to `totals` per category (verify-recompute invariant 4). Feeds party-unity. |
| `source_url` | string | Official record URL. |

`member_votes` (array of `MemberVote`), **every covered member of the roll's
chamber** (V2-1/D61 — every House and Senate seat, including the 6 non-voting
delegates when the source includes them; not just the historical 6-member
Mississippi delegation), sorted by `member_id`:

| Field | Type | Notes |
|---|---|---|
| `member_id` | string | Bioguide id. |
| `rollcall_id` | string | Matches `rollcall.id`. |
| `position` | `yea \| nay \| present \| not_voting` | |

**`non_position` rolls:** Speaker/officer elections carry no yea/nay positions
(votes are cast for candidate names). They are published with counts in `totals`
but are excluded from coverage/subset checks; `vote_class_rule == "non_position"`
is the flag. There are 20 such rolls in the covered set.

## `data/absences/{congress}/{member_id}--{rollcall_id}.json` — one per not-voting instance

Schema: `data/schema/absence.schema.json` (model `Absence`). Sharded one level by
congress (V2-1) — full-roster coverage produces ~35,000 stubs, too many for one
flat directory. A stub is written for **every** `not_voting` `member_vote` (so
the file exists reciprocally with that position). Owner-approved CREC
explanations (INC-6, H9) are added in place.

| Field | Type | Notes |
|---|---|---|
| `member_id` / `rollcall_id` | string | Compose the filename. |
| `stated_reason` | string \| null | Owner-approved verbatim CREC quote, or null → UI renders "No explanation on record." |
| `stated_reason_source` | string \| null | CREC page URL; **required** whenever `stated_reason` is present. |
| `declared_position` | `yea \| nay` \| null | "Had I been present…", verbatim-sourced only. |

## `data/bills/{id}.json` — one per bill

Schema: `data/schema/bill.schema.json` (model `Bill`). Id form `hr2-119`. The
published set is the **vote-referenced bills only** — every distinct non-null
`RollCall.bill_id` (1,011 at INC-8), so every vote's bill link resolves to a page.
This is deliberately NOT full-congress bill coverage (D27).

| Field | Type | Notes |
|---|---|---|
| `id` | string | `type+number+congress`, lowercase. |
| `congress` / `number` | integer | |
| `type` | string | e.g. `hr`, `s`, `hres`. |
| `title_official` | string | Official short title; drafter-written, never a description of effect. HTML entities from the API (`&#039;`, `&amp;`) are decoded to their characters at ingest — a third party diffing against raw API responses should expect the decoded form. |
| `policy_area` | string \| null | Government-assigned only. |
| `subjects` | array\<string\> \| null | Government-assigned legislative subject terms (sorted). Populated at INC-10 for every bill; `[]` legitimately means collected-and-none. `null` (not-yet-collected, D27) no longer occurs in the published set. |
| `sponsor_id` | string \| null | Bioguide id of the primary sponsor. |
| `cosponsor_ids` | array\<string\> \| null | Bioguide ids of CURRENT cosponsors (withdrawn excluded), sorted. Populated at INC-10; `[]` = collected-and-none. |
| `latest_action` / `latest_action_date` | string | |
| `cbo_estimates` | array\<CboRef\> | `{ url, title, date }` — link-through only. Titles are entity-decoded like `title_official`. |
| `source_url` | string | The bill's public congress.gov page (`legislationUrl`). |

## `data/legislation/{member_id}.json` — one per covered member (INC-10)

Schema: `data/schema/legislation.schema.json` (model `MemberLegislation`). The
committed input to the sponsored/cosponsored/enacted/gap metrics — metrics read
this, never the live API (D37), so every legislation figure recomputes from the
repo. Scope: bills and resolutions in the covered Congresses (118–119); floor
amendments are excluded (not bills).

| Field | Type | Notes |
|---|---|---|
| `member_id` | string | Bioguide id. |
| `sponsored` / `cosponsored` | array\<LegItem\> | Sorted by `bill_id`. |
| `source_url` | string | The member's sponsored-legislation endpoint (human-checkable). |

`LegItem`: `{ bill_id, congress, title (entity-decoded), introduced_date|null,
became_law (bool — "Became Public Law" under its own number), enacted_action
(the frozen enacting text; null unless enacted), source_url }`. It deliberately
carries **no live latest-action field** so the file diffs only on real events
(new sponsorship/cosponsorship/enactment), preserving the quiet-night diff-gate (D37).

## `data/metrics.json` — computed Tier-2 metrics (INC-10)

Schema: `data/schema/metrics.schema.json` (model `MetricsFile`). Deterministic, no
wall-clock. Recomputable in full: `build().model_dump()` equals this file (D40).

- `schema_version`: integer formula-generation stamp (R-3/D45), bumped by hand on any
  *semantic* change to how metrics are computed — including changes to the shared
  helpers the per-metric `digest` does not cover. Numbers carrying different
  `schema_version`s are not guaranteed formula-comparable.
- `methodology`: `{ <metric_key>: { label, text, digest } }` — `text` is the metric
  function's docstring verbatim (formula, inclusions/exclusions, source); `digest` is
  the formula identity, `sha256(newline-normalized function source)[:16]`, so any
  published value states exactly which formula produced it (it bumps on any change to
  that function's body). The methods page renders one section per key (asserted equal
  by `check-metrics-sections.mjs`).
- `members`: `{ <bioguide>: MemberMetrics }` with the 8 keys `attendance`,
  `party_unity`, `sponsored`, `cosponsored`, `enacted_rate`, `cosponsor_vote_gap`,
  `named_measure_mismatch`, `absence_context`. `pct` fields are `null` on a zero
  denominator (never a fabricated 0). No metric is a composite of others — the
  Tier-3 guard enforces it (§5). `named_measure_mismatch` compares a statement's
  owner-assigned stance to the member's own passage vote on the paired measure
  (D42, superseding D39's fail-closed design); it stays `[]` until a qualifying
  statement — specificity 2/3, a stance, a bill-id pairing — is curated (content
  = H8), never guessed. `cosponsor_vote_gap` is a factual list to be rendered
  only against its denominator, never as a headline (D38).

## `data/statements/{id}.json` — one per curated statement (INC-11)

Schema: `data/schema/statement.schema.json` (model `Statement`). OWNER-curated
(content = H8) via the local Flask curation tool: the owner pastes a verbatim quote
and its source, the tool captures a permanent Wayback copy and refuses to save
without a verified one (D43), resolves the pairing (D41), and writes this record.
Nothing here is builder-authored. Empty at launch (the machinery ships; the corpus
is owner-supplied, like INC-6 absences).

| Field | Type | Notes |
|---|---|---|
| `id` | string | `{member}-{date}-{sha8(source_url)}` — stable, so re-curating the same source is idempotent. |
| `member_id` | string | Bioguide id (covered member). |
| `text` | string | The statement, VERBATIM. There is deliberately no paraphrase field. |
| `date` / `venue` | string | When and where it was said. |
| `source_url` | string | The primary source. |
| `archive_url` | string | Permanent Wayback snapshot; **required** — no verified capture, no save (D43). HEAD-verified at capture time and swept weekly (see archive-status). |
| `archive_captured_at` | string | ISO-8601 UTC of the snapshot. |
| `named_measures` | array\<string\> | Measures the statement names, verbatim (bill ids or short titles). |
| `paired_bill_ids` | array\<string\> | The D9 pairing RESULT: `named_measures` resolved to canonical bill ids (bill-id form passes through; an allowlisted title maps; anything else is unpaired and omitted). Resolved once in Python (`ingest/pairing.py`); the metric layer and site both read this and never re-resolve (D41). Sorted, de-duplicated. |
| `specificity_level` | `0\|1\|2\|3` \| null | Owner-assigned; `null` = unscored. |
| `stated_position` | `"support" \| "oppose"` \| null | Owner-assigned stance (D42) — the sibling of specificity, NOT a paraphrase. `support` ⇒ expected Yea on passage, `oppose` ⇒ Nay. The only basis for `named_measure_mismatch`; `null` → excluded from it. |
| `curator_note` | string \| null | Internal, **never rendered**. |

`data/statements/_title_allowlist.yaml` (owner-edited config, not a record) is the
D9 short-title → bill-id map: the one sanctioned exception to "pair by bill id
only". Keys match statement titles case-insensitively; values must be valid bill
ids. After editing it, run `curate statements repair` to re-resolve existing records.

`data/quality/archive-status.json` (INC-11) is the weekly archive-link sweep's
committed report: `dead_statement_ids` (sorted) plus `dead`/`unreachable` detail and
counts. The site build reads `dead_statement_ids` and excludes those statements until
they are recaptured (D44). Deterministic, no wall-clock, so a quiet week is
byte-identical.

## `data/manifest.json` — dataset summary (the one wall-clock file)

| Field | Type | Notes |
|---|---|---|
| `generated_at` | string | ISO-8601 UTC of the export run. **The only wall-clock value in the dataset.** |
| `commit` | string | Short git sha = HEAD at generation time (the code that produced the export). It is **not** the commit that contains this manifest — that sha can't exist yet. |
| `congresses` | array\<int\> | Covered Congresses (`[118, 119]`). |
| `counts` | object | `members`, `rollcalls`, `rollcalls_by_chamber`, `rollcalls_by_vote_class`, `non_position_rollcalls`, `member_votes`, `absences`, `bills`, `statements`. In `rollcalls_by_vote_class`, `non_position` rolls are counted under their own `non_position` key (equal to `non_position_rollcalls`), **not** folded into `other` — so `other` reflects only the genuine one-off classifications (L-1). |

## `data/schema/*.schema.json` — JSON Schema for the above

Generated from the pydantic models by `uv run export`. Committed so third parties
validate against the exact published contract. They change only when a model
changes — i.e. when the contract itself changes.

---

## Recompute and match — what a third party can verify (D22/D26, superseded by D61)

`uv run verify-recompute` (also run as a pytest test) checks these invariants over
**100% of roll calls** and exits nonzero on any mismatch:

1. **Coverage** — every expected member (date-windowed per roll — see
   `ingest/coverage.py` — with the D61 exceptions subtracted: the 6 non-voting
   delegates, the sitting Speaker's customary non-votes, and a short seating-lag
   tolerance around a member's term boundary) has exactly one position in
   `member_votes` for every eligible (`non_position`-excluded) roll.
2. **Exact reproduction** — for each position category, the count of embedded
   `member_votes` equals `rollcall.totals[category]` EXACTLY.
3. **Absence reciprocity** — every `not_voting` `member_vote` has a matching
   absence file, and every absence file has a matching `not_voting` vote.
4. **Party-total consistency** — `party_totals` sums (over parties) to `totals` in
   every category, and is present exactly on position rolls (`null` on `non_position`).

The metrics are also fully recomputable: `ingest/metrics.py` reads only this dataset,
and a test asserts `build() == data/metrics.json` (all metrics at once, D40).

**Full recomputability, not a subset check (D61 — this is the credibility
upgrade of the V2-1 pivot).** Before V2-1, `member_votes` carried only the
6-member Mississippi delegation while `rollcall.totals` was the *chamber-wide*
tally, so the chamber totals could not be re-derived from the published dataset
(D22/D26 recorded that limit explicitly, and invariant 2 was a "never exceeds"
subset bound tying MS's numbers to the chamber figure). V2-1 persists a position
for every member of both chambers — delegates included, since they cast real
recorded votes on House Committee-of-the-Whole rolls and omitting them would
have reintroduced the same non-reproducibility on those rolls — so `member_votes`
now reconstructs `rollcall.totals` exactly, on every roll, with no exception:
**a third party can clone this repository and re-derive every chamber vote total
from the published per-member positions alone.** A roll that fails to re-parse
under the current data model is quarantined AND has any stale prior export
removed (never a stale file from an earlier architecture sitting invisibly next
to the current ones) — see `data/quality/quarantine/`.

---

## Historical retention — the metric time-series (R-3/D45)

Metrics need to be trend-able and re-weightable retroactively without skewing
long-term series. Two guarantees make that possible now, before any grading exists;
building them later would require reconstruction.

**Git is the series store.** Every nightly commit of `data/metrics.json` is a dated
snapshot, anchored by that commit's `data/manifest.json.generated_at`. No separate
`data/metrics/history/` directory is materialized — that is deferred until a trend UI
needs it (D45).

**Recompute-at-a-past-commit is a supported contract.** Because `metrics.py` is pure
and reads only the committed dataset, a past state is reproducible:

```
git checkout <sha> -- data/           # restore that snapshot's inputs
uv run ingest metrics                 # recompute
# → data/metrics.json byte-identical to the file committed at <sha>
```

This is the D40 `build() == committed` equivalence extended along the time axis. The
per-metric `digest` and `schema_version` in each snapshot tell a later re-weighting
whether two historical numbers were produced by the same formula (comparable) or not.

**Extracting the series:** `uv run ingest metrics history <bioguide> [--metric <key>]`
walks the git history of `metrics.json` and prints, oldest→newest, one JSON row per
snapshot:

```json
{ "commit": "<sha>", "generated_at": "<iso8601|null>",
  "schema_version": 1, "metrics": { …the member's MemberMetrics… } }
```

It is a **reporting** tool (reads git only; not part of the build/export path, so it
is exempt from the no-network/no-wall-clock rules that bind `build()`), and it emits
the recorded values verbatim — no aggregation, ranking, or score. Snapshots where the
member is absent are skipped; snapshots predating R-3 carry `schema_version: null` and
no digests, and parse leniently.

## Mississippi state layer — `data/state/ms/` (INC-12)

State data is **partitioned** under `data/state/ms/` so the federal checks (which glob
`data/{members,votes,bills}/*.json` non-recursively) never see it. It uses the **same
canonical models** as the federal data (extend, don't fork), with a `jurisdiction` field
distinguishing the two.

| Path | Contents |
|------|----------|
| `data/state/ms/members/ms-{people_id}.json` | `Member`, `jurisdiction: "ms"`, `id` = `ms-<LegiScan people_id>`, `district` = the HD/SD ordinal, `ids.legiscan` set. One synthesized `Term` for the session. |
| `data/state/ms/votes/ms-{h\|s}-{session_id}-{roll_call_id}.json` | `VoteFile` (`RollCall` + every member's `MemberVote`). `RollCall.jurisdiction: "ms"`, `congress: null`, `session` = LegiScan session_id, `number` = roll_call_id, `party_totals` fully computed (every position is present). `member_votes` include `not_voting` rows (no separate absence stubs). |
| `data/state/ms/bills/ms-{type}{number}-{session_id}.json` | `Bill`, `jurisdiction: "ms"`, `congress: null`. Only vote-referenced measures. `source_url` = the official billstatus link where present. |
| `data/state/ms/crosswalk.json` | `ms-id → {legiscan_people_id, name, party, chamber, district}`. |
| `data/state/ms/legislation/ms-{people_id}.json` | `MemberLegislation` (INC-13). Per-member `sponsored` + `cosponsored` `LegItem`s built from **ALL** session bills (not just the vote-referenced ones), so authorship counts are complete + recomputable. MS reading: the FIRST-listed author is the principal ("sponsored"), the rest are "cosponsored" (LegiScan gives no primary/co split); `LegItem.became_law` = the official history action "Approved by Governor", `congress: null`. |
| `data/state/ms/metrics.json` | `MsMetricsFile` (INC-13). The MS Tier-2 subset per member — `attendance`, `party_unity`, `sponsored`, `cosponsored`, `enacted_rate` — computed by REUSING the federal metric formulas (`ingest/metrics.py`) over the MS partition; recomputable (`ms_metrics.build() == committed`, `checks/ms.py`). The federal list-type metrics (gap/mismatch/absence_context) are not computed for MS. No wall-clock. |
| `data/state/ms/manifest.json` | MS partition manifest: `session_id`, `session_name`, `dataset_hash` (the nightly change gate), counts. Carries the one injected `generated_at`. |

**Differences from the federal record (documented on `/methods#mississippi`):** positions
are Yea/Nay/not-voting only (LegiScan gives no Present/Absent split — `not_voting` folds
both); there is no personal-explanation pipeline (a missed vote shows no reason); LegiScan
party `N` (nonpartisan) is shown as `I`; only vote-referenced bills are published as bill
pages (though authorship is counted over ALL bills via `legislation/`); MS "sponsored" =
principal (first-listed) author, "cosponsored" = additional author (INC-13). **Source
integrity:** LegiScan mirrors
the official `billstatus.ls.state.ms.us` record; scrape fidelity is verified against the
official per-vote PDFs (470 positions in the GO verdict; `checks/ms.py` re-confirms the
sampled tallies every build). Not recomputable from a third-party origin — it is the
official record as mirrored by LegiScan, verified, not two independent sources.
