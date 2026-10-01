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

## 9. Congress.gov — bill `/actions` sub-resource + `/bill` list surface (V2-11 task 1, probed 2026-10-01)
Samples: `congress_bill_actions_hr2670_118.json`, `congress_bill_list_sorted_updatedate.json`
Endpoints: **`GET /v3/bill/{congress}/{type}/{number}/actions`**, **`GET /v3/bill[/{congress}]`**

`{"actions": [ { ... } ], "pagination": {"count": N, "next": url|absent}}`

Action object fields (union over 324 real actions across 4 bills):
- `actionDate` — `"YYYY-MM-DD"`. **Always present.**
- `actionTime` — `"HH:MM:SS"`. **Optional** — present on 142/234 (NDAA FY24),
  9/64, 10/26. Absent on most Library-of-Congress-sourced rows. Model it
  nullable; never sort on it alone.
- `text` — the verbatim action sentence. Stored as-is (section 0.5, no summarising).
- `type` — e.g. `"President"`, `"Floor"`, `"Committee"`, `"IntroReferral"`.
- `actionCode` — e.g. `"E40000"`. **Optional** (absent on some chamber rows).
- `sourceSystem` — `{"code": int, "name": str}`, e.g. `9` / `"Library of Congress"`.
- `committees` — **optional** list, present only on committee actions.
- `calendarNumber` — **optional**, seen only on NDAA FY24.
- `recordedVotes` — **optional** list. Shape:
  `{"chamber": "House"|"Senate", "congress": int, "date": ISO8601Z,
    "rollNumber": int, "sessionNumber": int, "url": clerk/senate XML url}`.
  This is the join to an existing `RollCall.id` (plan task 3).

> **PAGINATION UNEXERCISED.** The largest action list found is **234**
> (`hr2670-118`, NDAA FY24) — under the 250 page ceiling, so `pagination.next`
> was never returned on `/actions`. The paginated path must still be written and
> must be covered by a unit test against a synthetic payload; it cannot be
> confirmed live until a bill exceeds 250 actions.

**Field presence, measured over 520 real actions** (hr2670-118, hr2882-118,
hjres104-119, hr3684-117, hr748-116, s2226-118 — four Congresses; task 3 survey).
This is what the `BillAction` schema's required/optional split is derived from:

| field | present | schema |
|---|---|---|
| `actionDate` | 520/520 | `date` — required |
| `sourceSystem` | 520/520 | `source_system` — required |
| `text` | 520/520 | `text` — required, verbatim |
| `type` | 520/520 | `type` — required, **plain string, not a Literal** |
| `actionCode` | 337/520 (65%) | `action_code` — optional |
| `actionTime` | 227/520 (44%) | `time` — optional, **never a sort key** |
| `committees` | 97/520 (19%) | `committees` — optional, **identity-bearing** |
| `recordedVotes` | 58/520 (11%) | `rollcall_id` — optional |

> **`sourceSystem` has no `code` on Senate rows.** The four variants seen are
> `{"code": 2, "name": "House floor actions"}` (240), **`{"name": "Senate"}` with
> no code at all** (183), `{"code": 9, "name": "Library of Congress"}` (62), and
> `{"code": 1, "name": "House committee actions"}` (35). The schema stores the
> NAME only — a stored code would be null for an entire chamber.

> **`type` is an open set.** Eight values in the survey: `Floor` (321),
> `ResolvingDifferences` (70), `Committee` (68), `IntroReferral` (20),
> `President` (15), `BecameLaw` (10), `Calendars` (9), `NotUsed` (7). It is the
> government's set to extend, so it is typed `str`; a Literal would quarantine a
> whole bill for the crime of a new action type.

> **`recordedVotes` resolves to a roll call only ~69% of the time, by design.**
> 40 of 58 entries matched a `RollCall.id` this dataset holds; **all 18 misses
> were 117th or 116th Congress** — real votes outside the covered window. The
> parser emits `rollcall_id: null` for those rather than a link to a `/v/` page
> that was never built.

> **IDENTITY REQUIRES THE WHOLE ROW. There is no action id, and
> (`actionDate`, `actionTime`, `actionCode`, `text`) is NOT unique.** On
> `hr2670-118`, five rows read "Forwarded by Subcommittee to Full Committee by
> Voice Vote ." on 2023-06-13 with code `H23000`, and six read "Subcommittee
> Consideration and Mark-up Session Held." with code `H22000` -- each a different
> subcommittee, **discriminated only by `committees`**. A parser that keys on that
> four-field tuple collapses 234 real actions to 225 (measured, task 2). Any
> dedupe must hash the entire row, and the result must be checked against
> `pagination.count` -- fewer unique rows than the government claims is an
> incomplete timeline, not a clean one.

**`/bill` list surface:**
- Page ceiling is **250**. `limit=251` silently **clamps to 250** — it does not error.
- **No deep-offset ceiling** (measured task 2): `offset=19300` on `/bill/118`
  (count 19,315) still serves rows, and `offset >= count` returns an empty page
  rather than an error — so a count-bounded loop enumerates a whole Congress and
  terminates cleanly. Sort composes with a deep offset.
- **`sort=updateDate asc` also works** (literal space), but **descending is the
  direction a crawl must use.** A bill touched mid-crawl gets a new `updateDate`
  and jumps to position 0, shifting the pages behind it down, so a descending crawl
  RE-READS a row it already has. Ascending moves the touched bill to the end and
  shifts everything after it up, which SKIPS a row at the cursor. Duplicates are
  free to dedupe; skips are silent undercounts.
- `fromDateTime` / `toDateTime` (ISO `YYYY-MM-DDTHH:MM:SSZ`) **work** and compose
  with the `/bill/{congress}` path form.
- > **DEVIATION (D88): `sort=updateDate+desc` is SILENTLY IGNORED.** The `+`
  > is transmitted as a literal `%2B`, which the API discards along with the whole
  > sort, returning the identical page as `sort=BOGUSVALUE`. **The working form is
  > `sort=updateDate desc`** (a literal space, encoded `%20`). Verified by three-way
  > comparison: `updateDate+desc`, `updateDate+asc` and `BOGUSVALUE` all return the
  > same bytes; `updateDate desc` returns genuinely newest-first. Any code that
  > passes the documented `+` form is sorting by nothing.
- Rate limit headers: `x-ratelimit-limit: 20000`, `x-ratelimit-remaining`.
  The reset window is **not** stated in any header (see D88 — it does not bind,
  because the local 1 req/s ceiling caps us at 3,600/h regardless).

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
