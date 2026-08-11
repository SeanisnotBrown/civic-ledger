# SHAPES.md — observed source field shapes (INC-1 spike)

**Authoritative contract for every later parser.** Parsers in INC-2/3/4/5/6 are
written against the field names *observed here*, not against IMPLEMENTATION.md's
assumptions. Where the spec's assumed shape was wrong, the deviation is recorded
here and in `docs/decisions.md`. Samples captured 2026-08-11; each file in this
directory is the pretty-printed/verbatim body of one real response.

Legend: field names are quoted exactly as returned (case-sensitive — this bites).

---

## 1. Congress.gov — members by state
Sample: `congress_member_ms.json` · Endpoint: **`GET /v3/member/{stateCode}`**

> **DEVIATION (D19):** the spec's `GET /member?stateCode=MS&currentMember=true`
> **query-param** form returns **HTTP 503**. State filtering is a **path
> segment**: `/v3/member/MS`. `?currentMember=true` works as a query param on the
> path form and filters 29 all-time → 6 current. Confirmed 5R/1D (D1).

`{"members": [ { … } ], "pagination": {...}, "request": {...}}`

Member object fields:
- `bioguideId` — **lowercase `d`** (canonical key). *NB: house-vote member
  positions use `bioguideID` with capital ID — see §3.*
- `name` — `"Last, First"` (e.g. `"Wicker, Roger F."`). Not split into parts here.
- `partyName` — full word: `"Republican"` | `"Democratic"`. INC-2 maps → `"R"|"D"|"I"`.
- `state` — full name `"Mississippi"` (not `"MS"`).
- `district` — integer for House; **absent/None** for Senate.
- `terms` — `{"item": [ {"chamber": "House of Representatives"|"Senate",
  "startYear": 2023} ]}` — note the `.item` wrapper; sparse (no party-per-term here;
  use congress-legislators for full term history incl. party switches).
- `depiction`, `url`, `updateDate` — chrome/metadata.

## 2. Congress.gov — house vote list (beta)
Sample: `congress_house_vote_list_119_1.json` · Endpoint: `GET /v3/house-vote/{congress}/{session}`

`{"houseRollCallVotes": [ { … } ], "pagination": {...}}`
Each vote: `congress`, `sessionNumber`, `rollCallNumber` (int), `identifier`
(e.g. `11912025240`), `legislationType`+`legislationNumber` (`"HR"`,`"3424"`),
`legislationUrl`, `result` (`"Passed"`), `startDate`, `updateDate`, and
**`sourceDataURL`** = the clerk.house.gov XML for that roll (the D6 integrity
cross-check source, handed to us directly — no separate discovery needed).

## 3. Congress.gov — house vote detail + member positions (beta)
Samples: `congress_house_vote_detail_119_1_240.json`, `…_members_119_1_240.json`

Detail (`GET …/{roll}`) → `{"houseRollCallVote": { …, "voteQuestion",
"voteType", "votePartyTotal", "result", "sourceDataURL" }}`. `voteQuestion` +
`voteType` feed the §A1 `vote_class` classifier (INC-5).

Positions (`GET …/{roll}/members`) →
`{"houseRollCallVoteMemberVotes": {"results": [ { … } ]}}`. Each result:
- `bioguideID` — **capital ID** (≠ the member endpoint's `bioguideId`).
- `voteCast` — `"Yea"|"Nay"|"Present"|"Not Voting"` (Title Case). INC-3 maps →
  `position` enum (`yea|nay|present|not_voting`); `"Not Voting"` → `not_voting`
  which also seeds an `Absence` stub (reason None).
- `voteParty` (`"R"|"D"`), `voteState`, `firstName`, `lastName`.

## 4. Congress.gov — bill detail
Sample: `congress_bill_hr1_119.json` · Endpoint: `GET /v3/bill/{congress}/{type}/{number}`

`{"bill": { … }}`. Relevant fields:
- `policyArea` — **object** `{"name": "Economics and Public Finance"}` (government-
  assigned; §5 `policy_area` takes `.name`). May be absent.
- `subjects` — present as a sub-resource link/count; full list via `…/subjects`.
- `title`, `titles`, `sponsors`, `latestAction`, `type`, `number`, `congress`.
- **`cboCostEstimates`** — present on hr1-119 (D15 confirmed). List of
  `{"title", "description", "pubDate", "url"}` — link-through only, `url` → cbo.gov.
- `textVersions` sub-resource → USLM XML for the INC-19 diff viewer (via govinfo).

## 5. Congressional Record — full-text "personal explanation" search
Samples: `congress_congressional_record_index.json` (index, for the record),
`govinfo_crec_search_personal_explanation.json` (the real search hit).

> **DEVIATION, RESOLVED:** the Congress.gov `GET /v3/congressional-record`
> endpoint is only a **date-indexed issue list** (`{"Results", "Status"}`) — NOT
> full-text search. But **govinfo `POST /search` (§8) does full-text search with
> the SAME api.data.gov key** — so INC-6 has a working source. No risk carried
> forward. `personal explanation` → **15,998** CREC hits; a granule literally
> titled "PERSONAL EXPLANATION" is in the first page.

## 8. govinfo — CREC full-text search
Sample: `govinfo_crec_search_personal_explanation.json` · Endpoint:
**`POST https://api.govinfo.gov/search`** (X-Api-Key = the Congress.gov key).

Request body: `{"query": "\"personal explanation\" collection:CREC", "pageSize",
"offsetMark": "*", "sorts": [{"field": "publishdate", "sortOrder": "DESC"}]}`.
Response: `{"count", "offsetMark", "results": [ { … } ]}`. Each result:
- `title`, `dateIssued`, `collectionCode` (`"CREC"`), `packageId`
  (`"CREC-2026-07-20"`), `granuleId` (`"CREC-2026-07-20-pt1-PgH4671"` — the page),
- `download`: `{txtLink, modsLink, premisLink, zipLink}` — **`txtLink`** is the
  granule text (the personal-explanation excerpt source), **`modsLink`** is the
  metadata (member/page). `offsetMark` paginates (feed the returned value back).

INC-6 flow: search per covered member name + "personal explanation" → for each
hit fetch `txtLink` → extract the verbatim excerpt + `granuleId` page URL into the
approval queue (§7 INC-6). Member filtering + granule fetch belong to INC-6, not
INC-1.

## 6. senate.gov LIS — roll call XML
Samples: `senate_vote_menu_119_1.xml`, `senate_vote_detail_119_1_00001.xml`

> **DEVIATION:** menu and detail live in **different directories**.
> - Menu: `…/LIS/roll_call_lists/vote_menu_{c}_{s}.xml`
> - Detail: `…/LIS/roll_call_votes/vote{c}{s}/vote_{c}_{s}_{NNNNN}.xml` (5-digit roll)
> The spec's assumed `roll_call_votes/vote{cc}{s}/vote_menu_…` **301-redirects** to
> `roll-call-vote-not-available.htm`. The detail path shape the spec gave IS correct.

Menu tags (per `<vote>`): `vote_number` (5-digit, **newest-first**), `question`,
`result`, `vote_date`, `measure`, `issue`, `title`, `vote_tally`(`yeas`/`nays`).
119/1 had **659** votes.

Detail (`<roll_call_vote>` root): `vote_question_text`, `vote_result`, `question`,
`vote_date`, `congress`, `session`, `vote_number`, then `<members><member>…`.
Each `<member>`:
- `member_full` — `"Wicker (R-MS)"` style display string.
- `last_name`, `first_name`, `party` (`"R"|"D"`), `state` (`"MS"`).
- `vote_cast` — `"Yea"|"Nay"|"Present"|"Not Voting"`.
- **`lis_member_id`** — e.g. `"S318"` (Wicker). **NOT bioguide** → INC-4 maps it
  via congress-legislators `id.lis` (see §7). Both MS senators present (Yea/Yea in
  vote 1).

## 7. unitedstates/congress-legislators — ID crosswalk
Sample: `legislators_current_ms.yaml` (EXCERPT: 6 MS-delegation entries out of 537
in the full `legislators-current.yaml`; full file cached in `data/raw/`, not
committed — it is ~3MB of all members).

Per legislator: `id` dict is the crosswalk hub —
`bioguide` (→ Congress.gov), `lis` (→ senate XML `lis_member_id`), `fec` (list),
`govtrack`, `opensecrets`, `thomas`, `icpsr`, `ballotpedia`, `wikidata`, … .
`name`: `{first, last, official_full, …}`. `terms`: full history; each term has
`type` (`"sen"|"rep"`), `state`, `party` (full word, party switches preserved),
`class` (Senate), `start`, `end`, `district` (House). This is the source of truth
for §5 `Member.ids`, chamber, and term/party history (the Congress.gov member
`terms.item` is too sparse for that).

**Crosswalk summary (the two joins INC-3/4 depend on):**
- House positions `bioguideID` → legislators `id.bioguide` → canonical `Member.id`.
- Senate positions `lis_member_id` → legislators `id.lis` → canonical `Member.id`.

---

## Federal source reachability (INC-1 acceptance)
| Source | Status | Sample |
|---|---|---|
| Congress.gov members | ✅ (path form) | `congress_member_ms.json` |
| Congress.gov house-vote list/detail/members | ✅ | 3 house-vote samples |
| Congress.gov bill + CBO | ✅ | `congress_bill_hr1_119.json` |
| Congress.gov Congressional Record | ✅ index (date list) | `congress_congressional_record_index.json` |
| govinfo CREC full-text search | ✅ resolves INC-6 (same key) | `govinfo_crec_search_personal_explanation.json` |
| senate.gov LIS menu + detail | ✅ (corrected paths) | 2 senate XML samples |
| congress-legislators crosswalk | ✅ | `legislators_current_ms.yaml` |
| LegiScan (state) | ⛔ H2 pending → verdict DEFER | see `../ms-state-verdict.md` |

All six federal sources reachable. No federal source unreachable → no risk carried
forward per §7 INC-1 "On failure".
