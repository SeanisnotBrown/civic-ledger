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
- `members`: `{ <bioguide>: MemberMetrics }` keyed by `attendance`,
  `cross_aisle_support`, `sponsored`, `cosponsored`, `enacted_rate`, `cosponsor_vote_gap`,
  `named_measure_mismatch`, `absence_context` (+ `position_mix`, `cosponsor_enacted_rate`).
  `cross_aisle_support` replaced `party_unity` federally (2026-08-15, owner: "a dumb stat");
  `party_unity` survives only in the MS subset (`MsMemberMetrics`, below). `pct` fields are `null` on a zero
  denominator (never a fabricated 0). No metric is a composite of others — the
  Tier-3 guard enforces it (§5). `named_measure_mismatch` compares a statement's
  owner-assigned stance to the member's own passage vote on the paired measure
  (D42, superseding D39's fail-closed design); it stays `[]` until a qualifying
  statement — specificity 2/3, a stance, a bill-id pairing — is curated (content
  = H8), never guessed. `cosponsor_vote_gap` is a factual list to be rendered
  only against its denominator, never as a headline (D38).

## `data/rankings/{metric}.json` — per-metric rank/percentile/mean (V2-2)

Schema: `data/schema/rankings.schema.json` (model `RankingsFile`), one file per
ranked metric: `attendance`, `cross_aisle_support`, `sponsored`, `cosponsored`,
`enacted_rate` (the five SCALAR Tier-2 metrics; the three list-type metrics are
not ranked). Deterministic, no wall-clock. **Recomputable from published data**:
`rankings.build_all()` reads ONLY `data/metrics.json` + `data/members` and
reproduces every file byte-for-byte — `verify-recompute` invariant 5 enforces it
(a ranking that cannot be re-derived may not ship). No thresholds, no labels: a
rank is a position, not a score (D67; evaluative grades are V2-4/`scoring.py`).

- `metric` / `value_field`: the ranked Tier-2 key and which scalar of it is ranked
  (`pct` for the three rate metrics, `count` for sponsored/cosponsored).
- `label`: `== METRIC_LABELS[metric]`. `methodology`: the shared ranking-method
  text, rendered on `/methods` (one `data-ranking` section per file, asserted equal
  to the file set by `check-metrics-sections.mjs`).
- `ranks_delegates`: `false` for `attendance`/`cross_aisle_support`, `true` for the three
  bill metrics (**D66**, owner-ratified). Non-voting delegates cannot vote on final
  passage, so their attendance/cross-aisle-support denominators are not comparable; they
  are held out of those two rankings (and listed in `excluded_delegates`) but ranked
  on the bill metrics.
- `chambers`: `{ house, senate }` — members are ranked WITHIN chamber. Each
  `ChamberRanking` carries `covered` (N ranked), `mean`/`median` (null when
  `covered == 0`), `party_means` (`{ party: mean }`, grouped by the member's current
  party; R-vs-D and R-vs-R both present, §0.4.2(c)), `excluded_delegates` (sorted
  bioguides held out by D66; `[]` when none), and `members` (`{ bioguide: { value,
  rank, percentile } }`). Rank is standard **competition** ranking (ties share a
  rank; the next rank skips). Percentile is the % of the chamber's ranked set with a
  strictly lower value. A member with a `null` metric value is not ranked on it.

## `data/config/thresholds.yaml` — ratified evaluative constants (V2-4)

Owner-ratified under propose→ratify→commit (§0.8/SD-27). Every evaluative number the
site publishes lives here with its `justification`, `citation` (URL or null), and
`ratified` date. **Nothing evaluative may publish from a value not committed here** —
`checks/integrity.py:grades_disclosure` (data side) and
`site/scripts/check-grade-labels.mjs` (render side) enforce it. V2-4 holds one entry,
`grades.attendance`: the letter-grade `bands` (grade/min/label), `min_eligible`, the
`exception_label`, and `formula_version`. The overall composite grade is deferred
until its formula is ratified.

## `data/grades/{category}.json` — evaluative grades (V2-4)

Schema: `data/schema/grades.schema.json` (model `GradesFile`), one file per graded
category (V2-4: `attendance`). Deterministic, **no wall-clock** (§6.3 beats §5's
"computed-at" wording — provenance is `formula_version` + the thresholds' `ratified`
date). **Recomputable**: `scoring.build_all()` reads only `data/metrics.json` +
`data/members` + `data/config/thresholds.yaml` and reproduces each file byte-for-byte
(`verify-recompute` invariant 6). Computed ONLY in `ingest/scoring.py` (the designated
Tier-3 module, §6.8).

- `category`/`metric`/`field`: what is graded (`attendance` → the `pct` of the
  attendance metric). `formula_version`/`ratified`/`min_eligible`/`exception_label`/
  `bands`: echoed from `thresholds.yaml` (the disclosure guard asserts an exact match).
- `members`: `{ bioguide: { value, grade, label } }` — the members actually graded,
  with the exact ratified `label` (e.g. `"F — Poor attendance"`).
- `exceptions`: `{ bioguide: reason }` where reason ∈ `delegate` (non-voting delegate,
  inherited D66 — eligible set not comparable), `min_service` (fewer than
  `min_eligible` eligible rolls), `no_record` (null attendance). §6.5 grading-coverage:
  every covered member is in `members` ∪ `exceptions` — silent drop = fail.

## `data/events/{YYYY-MM}.json` — the official-activity feed (V2-11)

Schema: `data/schema/events.schema.json` (model `EventsFile`), one file per calendar
month of ACTION dates. A pure projection of `data/bills/**` by `ingest/events.py`
(`uv run ingest events`): no network, no clock, nothing builder-authored — every text
field is the government's own, copied verbatim (0.5 forbids summarising anything that
publishes as fact). **Recomputable**: re-derives byte-for-byte from `data/bills` +
`data/votes` alone (`verify-recompute` **invariant 8**).

**These are the only machine-readable URLs the site publishes**, served verbatim at
`/events/{YYYY-MM}.json` and `/events/latest.json` — the newest month that HAS events,
not the current calendar month (a build-time clock would break §6.3, and on the 1st of a
month the URL would read empty while yesterday's votes sat in the previous file). The
V2-12 alert Worker and the V2-13 push client read these and nothing else.

Events are **newest action first**, tie-broken by `bill_id` then `id` so the order never
depends on filesystem iteration. A month file is never deleted once written: invariant 8
reports a stale one rather than a published feed URL vanishing silently.

| Field | Type | Notes |
|---|---|---|
| `month` / `count` | string / int | `YYYY-MM`; `count == len(events)`. Both derived from the rows — no wall-clock. |
| `id` | string | `{bill_id}--{date}--{sha256(whole action row)[:12]}`. Hashes the WHOLE row, not just the text: five hr2670-118 actions share a date, a text and a code and differ only in `committees`, and a text-only hash would publish one event for five (D88/D95). Stable across runs and field order, so a consumer can use it as a de-duplication key. |
| `bill_id` / `date` | string | The bill, and the action's own date (which month file it lands in — not the bill's date). |
| `text` / `type` | string \| null / string | Verbatim official action text and the government's own action type. Never reworded or classified. **`text` can be `null`** (corrected 2026-10-05): congress.gov omits the field on rare rows — s4869-118's Library of Congress `Intro-S` row of 2024-07-30 has no `text` key at all, 1 bill in 19,125 on Congress 118. `null` means "the official record carries no sentence for this action", NOT "no action": the action is real and its `date`, `type`, `action_code` and `source_system` are all present. Never the empty string, so a nullish check is sufficient. |
| `action_code` / `source_system` | string \| null / string | Carried for the same reason as `committees`: both are inside the `id` hash, so without them a consumer sees two events it cannot tell apart. hr10547-118 really has two actions on 2024-12-20 both reading "Introduced in House" differing only in `action_code` ("Intro-H" vs "1000"). `source_system` is the NAME only (the Senate's block carries no code at all — D89). |
| `committees` | list \| null | The only thing distinguishing some otherwise identical rows (D89). |
| `rollcall_id` | string \| null | Set only when the action's recorded vote resolves to a roll call this dataset HOLDS — otherwise null, so no link to a `/v/` page that does not exist. |
| `policy_area` / `subjects` | string \| null / list \| null | Denormalised off the bill, government-assigned, verbatim (D5 — never invented). Lets a consumer filter a month by topic without loading 38,756 bill files. |
| `source_url` | string | The bill's congress.gov URL — the link for a bill with no page. |
| `has_page` | bool | Whether `/b/{bill_id}` exists (SD-33 3(c): only bills that reached a recorded vote get one). Carried here because the Worker and the push client cannot reach `data/votes/` to re-derive it, and a wrong guess publishes a link to a page that was never built. Mirrors `votedBillIds()` in `site/src/lib/data.ts`. |

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
| `topic` | string \| null | P3 task 6: the owner-approved policy area (one of the 33 official areas). `null` = not labeled: counts toward the Q-B total, toward no topic. |
| `priority_signal` | bool \| null | P3 task 6: the owner-approved Q-J priority signal. |
| `curator_note` | string \| null | Internal, **never rendered**. |

`data/priorities.json` (P3 task 6) is DERIVED, written by `uv run export` and re-derived
byte-for-byte by `verify-recompute` (`ingest/priorities.py`): per member with at least one
approved statement, `approved_statements`, `distinct_topics` and `listed` (the Q-B bar in
`thresholds.yaml` `priorities_list`: 5 approved statements across 3 topics, counted over the
member's CURRENT term only — owner, 2026-10-23). The top-level `list_wording_ratified`
(owner ruling 9, 2026-10-23) is false until the list wording (AES-14) is ratified; while it
is false the site shows no list for anyone. Only a `listed`
member carries `priorities` (topic + `support`/`oppose` + the Q-J routes that make it one:
`signal` and/or `repetition`, with the statement ids) and `conflicted_topics` (both sides in
the current term, so no priority). Below the bar nothing is inferred or published. The
campaign-issue-page route is not implemented: those pages are not collected yet. Empty today.

`data/statements/_title_allowlist.yaml` (owner-edited config, not a record) is the
D9 short-title → bill-id map: the one sanctioned exception to "pair by bill id
only". Keys match statement titles case-insensitively; values must be valid bill
ids. After editing it, run `curate statements repair` to re-resolve existing records.

`data/quality/statement-prefilter-drops.json` (P3 decision 2) is the pre-filter's
committed audit: every member TURN the free rule-based filter threw away before any
AI call, with the rule that dropped it, the `sub_rule` where it has one, and an
excerpt to check the decision against. The decision's own words are why it exists —
"a silent filter is a hidden editorial judgment." Header fields carry the funnel
(`statements_in`/`statements_kept`, `turns_in`/`turns_kept`), the fixed `rule_order`
(first match wins, so the per-rule counts are reproducible) and `procedural_max_chars`.
Sorted by (member, date, statement, turn, rule) with no wall-clock anywhere, so a
re-run over an unchanged corpus is byte-identical. The ratified rules it implements are
§2's four rulings of 2026-10-14; `ingest/prefilter.py` records each one and why.

**Rendered cache entries (P3 task 2a).** `data/raw/press/{key}.html` is normally a
plain GET, but eleven pilot rows publish their release list from JavaScript and a plain
GET returns a page with zero dated items (STATUS fact 7). For those,
`ingest/press_render.py` drives Playwright (via `site/scripts/render-press-pages.mjs`)
and stores the rendered body through `cache.store`, which writes the SAME key and
sidecar shape `cache.fetch` reads — so `statements_press.py` consumes a rendered page
without knowing it was rendered. The sidecar carries one extra field, `"renderer":
"playwright"`, which is how a rendered entry is told apart from a fetched one by looking
at the cache rather than by remembering. A render that FAILED is never stored: a cached
empty list would tell the collector the member published nothing and stay fresh for the
7-day press TTL. **CI cannot produce these** (the `python` job has no Node, and the
pages are live third-party sites), so they are refreshed by hand and expire on that
same 7-day TTL.

**Candidate statement dates (P3 task 2a).** `data/raw/press/statements/{member}.json`
carries the collector's candidate statements in the shape `ingest/prefilter.py` reads.
Two fields of that shape are the collector's own, and both exist because a press release
is dated by its publisher rather than by a roll call: `date` is the date as the publisher
printed it — `2026-10-07`, or `2026-09` where a month is ALL they printed — and
`date_precision` is `"day"` or `"month"` for exactly that reason. Owner decision 5
(2026-10-14): a month-only date is stored verbatim and **never padded to the 1st**, it
counts toward stated-priority detection, and it is **never matched against a single day's
vote** — a Phase 6 constraint recorded here, not yet implemented. `date_precision` is
carried explicitly rather than inferred from the length of `date`, because a rule that
depends on counting characters is a rule that gets missed. **CREC records
(`statements_crec.statement_record`) do not carry the field at all and are always
day-precision**, so a consumer reading both sources must treat its absence as `"day"`.
The date comes from the list page's own text where there is one, else the publisher's
permalink (`/2026/9/…`), and the release page's own date wins over the permalink where
the two agree — which is what upgrades a month to a day. Where they DISAGREE nothing is
resolved: the stored date stays as it was and the conflict is printed in the collection
report by row and URL, because a disagreement can mean the wrong page was attached to a
title. `index.json` carries those conflicts (`date_conflicts`), the releases that no page
could date (`date_failures`), and what the dating cost in fetches
(`release_page_fetches`).

**Categorizer precision (P3 task 4, Q-K — ratified 2026-10-23).** No statement
categorized by the AI publishes until the categorizer prompt in use clears the precision bar
in `data/config/thresholds.yaml` (`categorizer_precision`) on the held-out labeled set, and
archive capture exists. The bar, proposed 2026-10-22 by the copilot and ratified by the
owner 2026-10-23: stance 0.90 (over the AI's for/against calls),
topic 0.90, priority_signal 0.90 (over its positive calls), specificity 0.80; proposition
is not scored. Every field is reported by party; a D/R gap wider than 10 points stops for
owner review. Measured with `uv run ingest prompt-eval` on the held-out hand-labeled set
(at least 50 rows). **Caveat:** on a 60-row set one error is about 1.7 points and a 0.90
estimate is roughly +/- 8 points. The bar is a floor, not a guarantee; the blind 1-in-10
review log tightens it over time (rolling window of the last 50 blind items). Every
statement is still hand-approved by the owner before it publishes: the bar decides whether
the AI's suggestions are trustworthy enough to show him, not whether anything skips his
review. A complete `prompt-eval` run on at least 50 labeled rows records its counts in
`data/quality/categorizer-precision.json` (counts per field and party, the prompt versions
and hashes measured, each field's status, any D/R gap flag; no per-row mark, no model
answer); the publish gate trusts it only while those prompt versions are still in
`ai.yaml`. The first-pass triage has no bar (owner, 2026-10-23) and is reported only. No
measured precision is recorded here yet.

**Measurement on file, 2026-10-23 — NOT a Q-K measurement.** `prompt-eval` on all 60 rows
of the held-out set (`p3-labeling-set` at `4d83fe4f3`), triage `v1`, categorizer `v2`:
`docs/research/2026-10-23-prompt-eval-60.md`. **50 of 60 labels are AI (copilot) labels,
owner-unreviewed. This is AI-vs-AI agreement, NOT a valid Q-K measurement. The publish gate
stays closed until the owner reviews or relabels them.** Agreement, all 60 (D / R): stance
90% (86% / 95%), topic 88% (77% / 100%), priority_signal 100% of 6 calls, specificity 86%
(77% / 95%), first-pass triage 89% (79% / 100%). Owner-labeled EV01–EV10 alone: stance 83%
(5/6), topic 100% (6/6), priority_signal 1/1, specificity 83% (5/6), triage 100% (6/6).
Copilot-labeled EV11–EV60 alone: stance 92% (33/36), topic 86% (31/36), priority_signal
5/5, specificity 86% (31/36), triage 87% (33/38); every D/R split is in the report.
**Owner-label conflict:** the owner's own EV02, EV03 and EV10 have priority = yes on
credit-claiming or bill-introduction releases, which ruling 3 (2026-10-23) now says is no.
They are listed, not changed; the owner reconciles them.

**Review queue and log (P3 task 5) — NOT published.** `data/raw/review/queue.jsonl` (the
categorized statements awaiting review) and `data/raw/review/log.jsonl` (the owner's
blind labels and approve / edit / reject decisions, with per-field agreement marks) are
gitignored here and, per the owner's ruling of 2026-10-23, backed up off-machine to a
separate PRIVATE repository (the push step is a stub until that repository exists); it is
never committed to this public repository. The log holds the owner's labels and the AI cache's `input_hash`, never the
model's answer. Which items are blind (1 in 10) is a pure function of a fixed public seed
and the text fingerprint (`curation/review.py::is_blind`). Nothing in the review queue
reaches `data/statements/` while `curation/review.py::publish_gate` is closed: Q-K
unratified, a field's rolling blind precision below its bar, or no archive path for
categorized statements (task 3).

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

## Member photographs — `site/public/photos/` (P2 task 6)

| Item | Value |
|------|-------|
| Source project | [unitedstates/images](https://github.com/unitedstates/images) |
| Served from | `https://unitedstates.github.io/images/congress/225x275/{bioguide}.jpg` |
| Original source of the images | U.S. Government Publishing Office (GPO) |
| Licence of the images | Public domain (works of the U.S. federal government; the project records GPO's assurance that all photos are public domain) |
| Licence of the project's own files | CC0 1.0 Universal public domain dedication |
| Size published here | `225x275`, the smallest the project offers — the member header renders at 90x110 CSS px |
| Fetched by | `uv run ingest photos` (`ingest/photos.py`), 1 request/second |
| Raw cache | `data/raw/photos/{bioguide}.jpg` (gitignored); a `{bioguide}.absent` sidecar records an upstream 404 so a re-run does not ask again |
| Published copy | `site/public/photos/{bioguide}.jpg`, committed, served at `/photos/{bioguide}.jpg` |

The roster covers two Congresses and the project does not publish a photograph for
every member in it. A missing photograph is an ordinary state, not an error: the
member header falls back to the member's initials, and the build checks which files
actually exist (`memberPhotoUrl` in `site/src/lib/data.ts`) so no page ever links an
image that is not there.

## Committee assignments — `data/committees/membership.json` (P2 task 7)

| Item | Value |
|------|-------|
| Source project | [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) — the same project the roster comes from |
| Files read | `committee-membership-current.yaml` (seats) and `committees-current.yaml` (names, official URLs) |
| Built by | `uv run ingest committees` (`ingest/committees.py`) |
| Shape | `{source_url, seat_count, members: {bioguide: [{committee_id, name, parent_name, rank, title, source_url}]}}`, sorted keys, no wall-clock |
| `source_url` per seat | The committee's own official page where upstream publishes one; a subcommittee carries its parent committee's page |

The only derivation is the subcommittee id join: a subcommittee's key in the
membership file is its parent's `thomas_id` followed by its own (`HSAG` + `15` →
`HSAG15`). Names, ranks and titles are the project's values verbatim. Seats are
restricted to bioguide ids in `data/members/`, so the file never names a member the
site has no page for.

**Scope:** the upstream files are `-current`, so they describe committees as they
stand now. A member who has left office carries no seats, and the member page labels
the section as current assignments rather than implying they sit on none.

## Which amendment a House amendment vote was on

**Source.** The Clerk of the House's roll-call XML, the same document each of
those vote rows already cites as "Official record" (`rollcall.source_url`), e.g.
`https://clerk.house.gov/evs/2023/roll669.xml`. Fetched by
`uv run ingest vote-amendments`, one request per House amendment roll call,
through `ingest.cache.fetch` (cached, one request a second).

**Why a second fetch of a document we already have a URL for.** House votes are
ingested from congress.gov's `house-vote` member-votes endpoint, which gives the
question text as the bare string `On Agreeing to the Amendment` and nothing
else. 637 House roll calls in the dataset carry exactly that question, so
without the Clerk's own document a reader cannot tell which amendment their
member voted on. The Clerk's XML carries two fields congress.gov drops:

| XML element | Field on `RollCall` | Example |
| --- | --- | --- |
| `<amendment-num>` | `amendment_number` | `Amendment No. 57` |
| `<amendment-author>` | `amendment_sponsor` | `Lawler of New York Part B Amendment No. 114` |

Both are stored verbatim (the number gains the words "Amendment No." so a bare
`57` cannot be read as a bill number). `amendment-author` is the Clerk's own
phrasing and already names both the sponsor and the amendment's printed number,
so it is the one the vote row renders; `amendment-num` is a different number —
the sequence within that measure's debate — and is kept in the data only.

**Scope, and what is NOT claimed.** Both fields default to `null`, which is the
D27 "not collected" sentinel and not a claim that the roll call had no
amendment: a row renders no "Amendment:" line at all when they are null. The
Senate is out of scope by its own record — it writes the designation into the
question text itself (`On the Amendment S.Amdt. 316 to S.Con.Res. 7`) and names
no sponsor anywhere in its vote XML, so a Senate amendment's sponsor would have
to come from a different endpoint and is not published.

## What a vote decided (the motion table)

Not a data source: `site/src/lib/motions.ts` is a fixed, hand-written table that
maps a roll call's verbatim question to one plain-English line saying what a Yea
and a Nay on that motion did. It exists because the chamber's own question is
procedural — a Yea on a motion to table an impeachment resolution sets that
resolution aside, and a row showing only "Yea" and the resolution's title reads
backwards.

Rules the table is bound by, enforced by `npm run test:motions`:

* First match wins, and the order puts the OUTER motion first (a motion to table
  a motion to discharge is a tabling vote; cloture on a motion to proceed is a
  cloture vote).
* A question the table does not match gets **no line**, never a guess.
* Every line states what a Yea does AND what a Nay does.
* No threshold is printed that the record does not carry. The Senate's cloture
  requirement differs between legislation and nominations and our vote records
  do not hold `majority_requirement`, so no number appears there; suspension of
  the rules carries the same two-thirds requirement every time, so that one is
  stated.
* The line describes the procedure, never a member's reason for voting.

The same module's `resolvesMeasure()` decides whether a roll call's tally may be
published as the margin a bill passed or failed by. Without it, the "In Congress"
list attached a same-day amendment's 96-1 tally to a bill's passage line.

The whole table is rendered for readers at `/methods#motions`, from the module
itself, so the published explanation cannot drift from the published lines.
