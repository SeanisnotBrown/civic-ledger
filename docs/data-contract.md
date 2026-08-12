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
| `source_url` | string | Official record URL. |

`member_votes` (array of `MemberVote`), **covered Mississippi delegation only**,
sorted by `member_id`:

| Field | Type | Notes |
|---|---|---|
| `member_id` | string | Bioguide id. |
| `rollcall_id` | string | Matches `rollcall.id`. |
| `position` | `yea \| nay \| present \| not_voting` | |

**`non_position` rolls:** Speaker/officer elections carry no yea/nay positions
(votes are cast for candidate names). They are published with counts in `totals`
but are excluded from coverage/subset checks; `vote_class_rule == "non_position"`
is the flag. There are 20 such rolls in the covered set.

## `data/absences/{member_id}--{rollcall_id}.json` — one per not-voting instance

Schema: `data/schema/absence.schema.json` (model `Absence`). A stub is written
for **every** `not_voting` `member_vote` (so the file exists reciprocally with
that position). Owner-approved CREC explanations (INC-6, H9) are added in place.

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
| `subjects` | array\<string\> \| null | Government-assigned legislative subject terms. **`null` = not yet collected** (a paginated sub-resource fetched by the INC-10 metrics layer); `[]` would mean collected-and-none. Never read `null` as "zero subjects" (D27). |
| `sponsor_id` | string \| null | Bioguide id of the primary sponsor. |
| `cosponsor_ids` | array\<string\> \| null | Bioguide ids. **`null` = not yet collected** (INC-10 backfills); distinct from `[]` (D27). |
| `latest_action` / `latest_action_date` | string | |
| `cbo_estimates` | array\<CboRef\> | `{ url, title, date }` — link-through only. Titles are entity-decoded like `title_official`. |
| `source_url` | string | The bill's public congress.gov page (`legislationUrl`). |

## `data/manifest.json` — dataset summary (the one wall-clock file)

| Field | Type | Notes |
|---|---|---|
| `generated_at` | string | ISO-8601 UTC of the export run. **The only wall-clock value in the dataset.** |
| `commit` | string | Short git sha = HEAD at generation time (the code that produced the export). It is **not** the commit that contains this manifest — that sha can't exist yet. |
| `congresses` | array\<int\> | Covered Congresses (`[118, 119]`). |
| `covered_state` | string | `MS`. |
| `counts` | object | `members`, `rollcalls`, `rollcalls_by_chamber`, `rollcalls_by_vote_class`, `non_position_rollcalls`, `member_votes`, `absences`, `bills`. |

## `data/schema/*.schema.json` — JSON Schema for the above

Generated from the pydantic models by `uv run export`. Committed so third parties
validate against the exact published contract. They change only when a model
changes — i.e. when the contract itself changes.

---

## Recompute and match — what a third party can verify (D22 / D26)

`uv run verify-recompute` (also run as a pytest test) checks these invariants over
**100% of roll calls** and exits nonzero on any mismatch:

1. **Coverage** — every covered member (per chamber/congress) has exactly one
   position in `member_votes` for every eligible (`non_position`-excluded) roll.
2. **Subset consistency** — for each position category, the count of embedded MS
   `member_votes` never exceeds `rollcall.totals[category]`.
3. **Absence reciprocity** — every `not_voting` `member_vote` has a matching
   absence file, and every absence file has a matching `not_voting` vote.

**What is deliberately NOT recomputable:** `rollcall.totals` is the *chamber-wide*
tally (for the House, counted at ingest from the full results list of all ~435
members; for the Senate, cross-checked against the official menu tally — D22/D23).
We publish `member_votes` for the covered Mississippi delegation only — we do not
persist the other ~429 members' positions — so the chamber totals cannot be
re-derived from this dataset. The totals are carried as the chamber figure, and
the subset check (invariant 2) is the honest recompute-and-match tying our
per-member data to it. This is a scope choice (the covered set), not a data gap.
