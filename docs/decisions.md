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

### INC-2 (2026-08-11)

- **D20 — three `Member` mapping choices where §5 left the shape to the builder.**
  All in `ingest/sources/legislators.py`, tested in `tests/test_models.py`:
  1. **`ids.fec` list → comma-joined string.** congress-legislators gives `fec` as a
     list (Wicker: `["H4MS01078","S8MS00196"]`), but §5 types `ids: dict[str, str]`.
     The list is joined with `,` to honor the contract; INC-10b splits on `,` when it
     needs the individual committee IDs. All other crosswalk values are already scalar.
  2. **Curated `CROSSWALK_KEYS`, not the whole `id` blob.** `ids` carries
     `{govtrack, lis, fec, opensecrets, thomas, icpsr}` (present-only). `bioguide` is
     omitted because it IS `Member.id`; research chrome (`wikidata`, `ballotpedia`,
     `google_entity_id`, …) is dropped. The two load-bearing joins are kept: `lis`
     (senate XML, INC-4) and `fec` (funding, INC-10b). `legiscan` is **absent from
     the source** — it would be added by INC-12 branch A if that is ever built.
  3. **`serving` = the latest term overlaps the latest covered Congress**
     (`max(CONGRESSES)` = 119), computed from committed term dates via
     `congress_window(N)` = `(1789+2·(N−1))-01-03 … +2yr` with strict inequalities.
     This is deterministic with NO wall-clock (§6.3): a `now()`-based "currently in
     office" would flip a member's `serving` mid-window and break the double-export
     byte-identity guarantee. Covered-set filtering runs on the **raw dicts before**
     `Member` construction, so a non-D/R/I party on any non-covered member cannot
     crash the MS ingest.
- **2026-08-11 — INC-2 exports members in-memory → JSON, no SQLite yet.** §4 names
  `build.db` and `export.py` is specced "SQLite → JSON", but INC-2's acceptance
  (models.py + 6 files + determinism) needs only a pure `list[Member]` → JSON step.
  The full SQLite export contracts land in INC-7 (per `export.py`'s own docstring);
  building the DB layer now would be scope ahead of a passing acceptance gate.
- **2026-08-11 — shared `party_code()` mapper handles both spellings.**
  congress-legislators says `"Democrat"`, Congress.gov says `"Democratic"`; both map
  to `"D"`. The mapper raises on any unmapped word (the §6.1 quarantine path) and is
  exported so INC-3's `voteParty` reuses one source of truth.

### INC-1 GO-gate resolution — MS state verdict DEFER → GO (2026-08-11)

Owner elected PROGRESS option A (run the Journal cross-check now). Result: **GO**,
5/5 votes, 470 per-person positions, zero mismatches. Full write-up:
`data/quality/ms-state-verdict.md` + `data/quality/samples/ms_vote_xcheck/`.

- **D21 — ground truth = the official MS per-vote roll-call PDF, not the bound
  Journal.** The gate's wording said "chamber Journal PDF pages." We compared
  against `billstatus.ls.state.ms.us/2026/pdf/votes/{chamber}/{n}.pdf` — the
  primary per-vote record the bound Journal reprints, and the exact URL LegiScan's
  own `roll_call.state_link` points to. It is born-digital, text-extractable
  (pypdf), page-addressable per vote, and unambiguously the official record.
  **Honest scope:** LegiScan *scrapes* billstatus, so GO proves **scrape fidelity
  against the official record** (the risk INC-12 carries), not agreement between
  two independent origins — sufficient for the §0.4 correctness gate. The SoS also
  publishes the bound House/Senate Journal (e.g. `MS HOUSE JOURNAL V1 2025`) which
  reprints these same roll calls; we did not fetch the several-hundred-page volume.
- **2026-08-11 — `billstatus.ls.state.ms.us` serves an incomplete TLS chain.**
  It omits the intermediate CA; default verification fails
  (`CERTIFICATE_VERIFY_FAILED`). The spike verified via the OS trust store
  (`truststore`, which does AIA chasing on Windows) — real verification, **not**
  `verify=False`. **Load-bearing for INC-12:** CI/Linux does not chase AIA, so the
  branch-A fetcher must bundle the intermediate CA (or ship it in the cert bundle);
  do not disable verification.
- **2026-08-11 — `legiscan._get` has no TTL/cache-freshness check** (unlike
  `cache.fetch`): every call is a live request that also re-counts LegiScan quota.
  Acceptable for one-shot spikes; **INC-12 must route LegiScan through a TTL'd
  cache path.** Not fixed now (no INC in flight owns LegiScan ingest yet).
- **2026-08-11 — spike/analysis scripts not committed.** The comparison depends on
  the gitignored `getDataset` payload (needs the key); a committed script that
  can't run out-of-the-box (and would be linted by CI) is worse than prose. The
  reconciliation rules are captured in `ms_vote_xcheck/README.md` for INC-12 reuse;
  the committed PDFs + `.txt` are the reviewable evidence. (Mirrors INC-1: markdown
  verdict + committed samples, no one-off script beyond the reusable `spike.py`.)

### INC-3 (2026-08-11) — House vote ingest

- **D22 — one `/members` fetch per roll; chamber totals computed from results.**
  The `/house-vote/{c}/{s}/{roll}/members` response carries `voteQuestion`,
  `voteType`, `result`, `sourceDataURL`, `startDate` **and** every member's
  position (verified live), so the whole `RollCall` + positions come from a single
  fetch — no separate `/detail` call. `totals` (yea/nay/present/not_voting) are
  counted from the full results list, not read from `votePartyTotal`, keeping them
  independent and self-checking (`sum(totals) == len(results)`; e.g. 435 at session
  start, 430 after vacancies). ~1,886 rolls across 118/1-2 + 119/1-2; the beta
  endpoint covers the 118th (no clerk fallback needed for enumeration).
- **`vote_class` is provisional `other` / rule `unclassified` until INC-5.** §5
  requires `vote_class` non-null but the §A1 classifier is INC-5 (build order
  3→4→5). INC-5 rewrites every roll's class; the resulting whole-dataset diff is
  real-change noise, accepted.
- **`voteCast` has two yea/nay spellings + a candidate-vote form (found mid-run).**
  The first ingest quarantined 72 of 118/1's first 90 rolls; investigation split
  them cleanly:
  1. **`Aye`/`No` ≡ `Yea`/`Nay`.** "Recorded Vote" ballots (Committee of the
     Whole, amendments) return `Aye`/`No`; "Yea-and-Nay" ballots (final passage)
     return `Yea`/`Nay`. Both are the same position — `VOTE_MAP` maps all four
     (matching the clerk XML, which uses `Aye`/`No` there too).
  2. **Speaker-election rolls are `non_position`.** Members vote for a candidate by
     surname (`McCarthy`, `Jeffries`, …), which cannot be a yea/nay `MemberVote`.
     Such a roll still gets a `RollCall` (it counts toward the session total) with
     `vote_class_rule="non_position"`, an accurate **raw candidate tally** in
     `totals` (dict[str,int], keyed by candidate, not the yea/nay buckets), and
     **no** `member_votes`; it is excluded from vote-coverage symmetry and from the
     integrity sample. Detection is by **majority** unmappable `voteCast` (a lone
     stray cast on a normal roll instead quarantines — a real glitch, not scope).
     15 such rolls in 118/1 (the Jan-2023 15-ballot Speaker election).
- **Export layout:** `data/votes/{h-c-s-NNNN}.json` = the chamber `RollCall` with
  the MS delegation's `member_votes` embedded (sorted by member_id). **Absence
  stubs live in their own `data/absences/{member}--{rollcall}.json` files**, not
  embedded — INC-6 curation adds a `stated_reason` to an Absence and must not have
  to rewrite the (larger, more-linked) vote record. `not_voting` seeds both a
  `MemberVote` (position `not_voting`) and an Absence stub.
- **`source_url` = the clerk `sourceDataURL`** (the public, authoritative XML the
  record was cross-checked against), not the API URL — a reader can verify it.
- **Integrity cross-check (`checks/integrity.py`)** samples 10 rolls seeded from a
  hash of the sorted roll-id set: reproducible per dataset, re-rolls as data grows.
  A position **mismatch fails CI**; a clerk **network** failure only **warns** (an
  outage must not read as corruption). The clerk HTML vote index bot-blocks
  automated fetches (**403**), so completeness rests on API `pagination.count` +
  contiguous roll numbering + this per-roll clerk-XML cross-check, not the HTML
  index page.
- **Quarantine (§6.1) goes live.** A roll that fails validation is written to
  `data/quality/quarantine/` and skipped; because every roll carries MS members, a
  parse failure is treated as an MS-delegation failure → the run hard-fails at the
  end (correctness outranks completeness). Covered-member gaps (a roll missing an MS
  member) are written to `data/quality/house-gaps.md` and also fail.
- **`checks/symmetry.py` activates the vote-coverage rule** (§6.5) over the exported
  data (not the ingest run), publishing `data/quality/symmetry-report.json`; the
  covered House set is derived from `data/members/*.json` (`chamber=="house"`), never
  hardcoded.
- **`cache.py` now retries timeouts/network errors, not just 429/5xx (bug fix).**
  §6.1 says "retry on 429/5xx/**timeouts**", but `_live_get` only retried
  `RetryableHTTPError`. The first full run died at 539/1,886 on a lone
  `httpx.ReadTimeout`. Fix: retry on `(RetryableHTTPError, httpx.TransportError)`
  (covers Read/Connect timeouts + network errors). Regression test in
  `test_cache.py`.
- **`house_votes.run()` is per-roll fault-tolerant + resumable.** A fetch that
  survives all retries (persistent 5xx → `RetryableHTTPError`, timeout →
  `httpx.HTTPError`, disk → `OSError`) is recorded to a `fetch_failures` list and
  skipped, not raised — one bad request can't discard a 30-minute run. The run
  fails at the end if any remain; a re-run retries only those (cached rolls are
  instant). The full 1,886-roll backfill took **4 runs** to complete (two crashes
  from the above gaps, one external kill at ~11 min likely a background-task
  duration cap) — each resumed from cache; the final pass reported all four
  sessions at their exact official counts (724/517/362/283).
- **Completeness proof = contiguous roll numbering + count.** House roll calls are
  numbered 1..N sequentially per session; all four sessions verified contiguous
  `1..N` with `N == pagination.count`, which (with the 10/10 clerk cross-check) is
  the "official session total" evidence, since the clerk HTML index is 403-blocked.

### INC-4 (2026-08-12) — Senate vote ingest (∥, mirrors INC-3)

- **D23 — two files per roll; totals member-computed and cross-checked against the
  menu tally (the Senate's independent cross-source, in lieu of a clerk).** The
  session `vote_menu_{c}_{s}.xml` enumerates rolls and carries a per-vote
  `vote_tally` (yeas/nays); the per-roll `vote_detail` XML carries every member's
  `vote_cast`. `RollCall.totals` is computed from the detail member list (House
  precedent, D22), then required to equal the menu tally — a genuine cross-SOURCE
  check between two different files. A mismatch raises `TallyMismatch` → quarantine.
  This replaces INC-3's separate clerk.house.gov source (the Senate has none);
  `checks/integrity.py` additionally re-fetches sampled details and re-parses MS
  positions to catch export/serialization corruption.
- **VP tie-breaks need no special handling.** On a 50-50 roll the Vice President is
  absent from `<members>`, the detail `<count>` block, AND the menu tally, so the
  member-computed 50-50 agrees with the menu with no VP arithmetic. The tie-break is
  carried by `result` (e.g. "Bill Passed") and `<tie_breaker>`; `totals` stays
  member-computed (RollCall is `extra="forbid"`; no schema field added). Verified
  against the real 119/1 H.R.1 reconciliation passage (roll 372).
- **Crosswalk = `lis_member_id` → `Member.ids["lis"]` → bioguide (SHAPES §6/§7).**
  Senate detail keys members by LIS id (e.g. `S318` Wicker), not bioguide. The join
  runs through the INC-2 export (`chamber=="senate"`); only the covered delegation
  is exported, which is all the ingest stores. An MS senator whose LIS is missing
  from the crosswalk is a hard `KeyError` → quarantine, never a silent drop.
- **`bill_id` handles three measure shapes.** Bill/passage rolls carry the measure
  in `<document>` (`H.R.`→`hr1-119`); amendment rolls leave `<document>` half-empty
  (type `S.Amdt.`, no number) and put the underlying bill in
  `<amendment><amendment_to_document_number>` (`"H.R. 1"`) — so `_bill_id` falls
  back there (else every vote-a-rama roll loses its bill link). Nominations (`PN`),
  treaty docs, and quorum calls are not legislation → `bill_id` stays `None` (never
  faked). A whitelist of real bill types gates it.
- **`vote_date` "July 1, 2025,  11:56 AM" → naive ISO `2025-07-01T11:56:00`.** Parsed
  with a hand-rolled month map (not `strptime %B`, which is locale-dependent) so CI
  is locale-proof and deterministic (§6.3). No UTC offset is fabricated — the wall
  time is Eastern as senate.gov publishes it (House `startDate` already carries its
  own `-04:00`/`-05:00` offset; the two sources differ in granularity by design).
- **Completeness proof = contiguous roll numbering.** Senate rolls are numbered
  `1..N` per session with no separate count field; the ingest requires the menu key
  set to equal `range(1, max+1)`, a hole or short list failing to
  `data/quality/senate-gaps.md`. Stronger than House's pagination count.
- **`VOTE_MAP` is conservative** (`Yea/Nay/Present/Not Voting`; unmapped →
  quarantine). The Senate has no Aye/No (House Committee-of-the-Whole artifact) and
  no candidate-surname rolls, so **no `non_position` branch** — a majority-unmappable
  roll would be corruption, not scope. No `Guilty/Not Guilty` rolls exist in 118–119.
- **`checks/symmetry.py` generalized to both chambers**; the report gains a
  `"senate"` key. `checks/integrity.py` runs a House pass (clerk) and a Senate pass
  (detail re-parse), each a no-op until its data exists.
- **Probe-before-parse (INC-1 discipline).** Before writing the parser, fetched one
  detail of each shape variant — cloture-on-bill (roll 1), amendment (371), VP
  tie-break passage (372), nomination (659) — and committed them as offline test
  samples. The probe settled the `<document>`/`<amendment>`/`<tie_breaker>` shapes a
  single sample would have hidden.

### INC-5 (2026-08-12) — vote_class classifier (§A1)

- **D24 — `classify()` is a pure, offline, ordered rules table (D7); the one
  data-dependent rule (R-RULE) is kept pure by parameter.** Every roll gets a
  `vote_class` + the `vote_class_rule` id that fired (auditable; renders on the INC-10
  methodology page). The table is module-level data (`RULES` = tuples of
  `(rule_id, class, patterns, mode)`), not an if-chain, so it is exportable. FIRST
  match wins; order encodes precedence (cloture before the generic motion-to-proceed
  rule so "On Cloture on the Motion to Proceed" audits as cloture; treaty ratification
  before the "On the Resolution" passage rule so it isn't swallowed).
- **§A1 extended via the unmapped-questions loop over real 118–119 strings.** The
  spec's initial table left ~1/3 of rolls as `other` (suspend-and-agree/concur,
  joint/concurrent resolutions, discharge/refer/reconsider/instruct/point-of-order/
  decision-of-chair/adjourn, Senate motion forms embedded in "On the Motion (…)").
  Added deterministic rows for each observed family; **final `other` rate is well
  under the 5% ceiling** and the only intentional `other` is treaty ratification
  (R-TREATY, 1 roll — no treaty class exists in §5). Singletons are left honest
  `other` rather than given speculative rules.
- **R-RULE signal = the House Rules Committee (`hsru00`) with a "Reported" activity**
  on the resolution's Congress.gov committees sub-resource — a government-assigned
  fact, not a title heuristic. The pipeline fetches `bill/{c}/hres/{n}/committees`
  once per unique `hres` "On Agreeing to the Resolution" roll (~150; the 24 non-`hres`
  cases are `hconres`/`sconres`/privileged resolutions — never rule adoptions, so
  they default to R-RES/passage). Rules-reported ⇒ procedural (R-RULE); else ⇒
  passage (R-RES). This split matters: INC-10 party-unity excludes `procedural`.
- **Classification is a SEPARATE pipeline step that rewrites votes in place**
  (`ingest classify`), not part of ingest. **Required order: ingest → classify →
  checks.** An ingest re-export resets every roll to the provisional `unclassified`
  (house_votes/senate_votes always write the provisional class), so re-running an
  ingest after classify clobbers classifications; the new `checks/classification.py`
  gate (CI, blocking) catches this by failing on any `unclassified` roll or an
  `other` rate over the ceiling. Documented here + in the INC-9 automation pickup so
  the nightly job sequences the steps. `non_position` (Speaker-election) rolls are
  left untouched — not §A1-classifiable.
- **`unmapped_questions.json` is regenerated deterministically (sorted + counts),
  not appended.** The spec says "append", but an append is order/history-dependent
  and would break §6.3 export determinism (nightly diffs). A sorted full regen is
  the determinism-preserving equivalent; the file is a quality artifact, not an
  audit log (git history is the audit log).
- **Golden test:** `tests/fixtures/questions.yaml` — 50 verbatim real strings (Senate
  ones keep trailing measure text, so the fixture tests what production sees),
  covering every rule id incl. both R-RULE branches and the treaty. 100% pass.

### INC-6 (2026-08-12) — Absences & personal explanations

- **D25 — the builder ships the curation tool; the owner supplies the content
  (principle 5, H9).** A personal-explanation `stated_reason` renders on the site as
  fact, so approving one into `data/absences/` is "filling the tool with political
  content" even though the text is verbatim — the `Absence` docstring requires it be
  *owner-approved* AND verbatim (conjunctive), and the increment header marks the
  content H9. So INC-6 lands the pipeline GREEN (search → verify → queue → approver +
  the exclusion test) but the "≥1 real approved example" acceptance is recorded
  **pending H9**, mirroring INC-1's DEFER precedent. The machinery is proven
  end-to-end by a test that approves the real committed Guest granule onto a *tmp*
  stub; real `data/absences/*.json` keep `stated_reason: null` until the owner acts.
- **Member identity is hard-verified against the granule byline, not the search.**
  A CREC surname search returns wrong-state members (the real case: "HON. GLENN
  THOMPSON of pennsylvania" surfaces under a "Thompson" search though the covered
  member is Bennie Thompson of Mississippi). `verify_member` requires the byline
  state to equal the member's state AND the surname to appear in "HON. {NAME}".
  Search is additionally scoped `title:"Personal Explanation" "of Mississippi"`,
  which alone cut the covered set to exactly ONE real candidate (Guest, 2023-01-13,
  Roll 31, YEA) out of 1,152 personal explanations in 118–119.
- **Roll auto-match = stub existence, not date arithmetic.** Explanations are filed
  after the vote and roll numbers reset per session, so a granule date can't be
  mapped to a roll id directly. For member M + "Roll Call No. N", generate candidate
  ids across covered sessions that STARTED on/before the granule year and keep the
  one where `data/absences/M--{id}.json` already exists (the member was recorded
  not_voting). Exactly one hit → auto-match; zero or many → left unmatched for the
  owner (never guess). Multi-roll insertions → no match and `declared_position=None`
  (positions can't be mechanically paired to rolls; the model only allows yea/nay).
- **`data/quality/absence-queue/` is excluded from the §6.4 banned-words scan.** It
  holds UNAPPROVED verbatim member text; a candidate containing a banned phrase must
  not fail CI before the owner has seen it. Once approved, the text lands in
  `data/absences/` and IS scanned. (Mirrors the INC-1 samples-exclusion ADR; test in
  `test_banned_words_scope.py`.)
- **Senate has zero personal explanations by construction** — "Personal Explanation"
  lives in the House's Extensions of Remarks section. The pipeline derives chamber
  from the member record (never hardcoded); Senate members simply return no hits.
- **Windows/cp1252 portability:** replaced the U+2192 arrow in CLI help + FAIL prints
  with ASCII "->". Windows' console codec can't encode it and crashed `ingest`/
  `curate` help (a latent bug from INC-4/5; CI on UTF-8 never hit it). Em-dash/§ are
  cp1252-safe and kept. Rule of thumb going forward: stdout stays ASCII.

### INC-7 (2026-08-12) — JSON export contracts

- **D26 — `verify-recompute` checks a coverage/subset/reciprocity match, NOT a
  chamber-total recompute (resolves the D22 tension).** The brief's "third party can
  recompute and match" (§5.2) meets a hard scope limit: `RollCall.totals` is the
  chamber-wide tally (House: counted from the full results list at ingest; Senate:
  cross-checked vs the menu tally — D22/D23), but we persist `member_votes` for the
  covered MS delegation only. So totals are structurally not re-derivable from the
  published dataset — the only "option (b)" (persist all ~435 positions) contradicts
  the covered-set design and republishes data that isn't ours to curate. `uv run
  verify-recompute` (also a pytest test, satisfying §8's "recompute-and-match script
  as a test") instead verifies three invariants over 100% of rolls: (1) coverage —
  every covered member has exactly one `member_votes` position per eligible
  (`non_position`-excluded) roll; (2) subset — per category, MS position count <=
  `totals[category]`; (3) absence reciprocity — every `not_voting` vote <-> its
  absence stub, both directions. Invariant (2) is the honest tie between our
  per-member data and the chamber figure. Documented in `docs/data-contract.md`.
- **A not_voting member appears in BOTH `member_votes` (position `not_voting`) AND an
  absence stub — that is the reciprocal design, not a conflict.** INC-3/4 record every
  covered member in `member_votes` for every eligible roll (so symmetry's
  `got == expected` holds), and additionally emit an `Absence` stub per not_voting so
  INC-6 curation can attach a stated_reason without touching the vote file. The first
  cut of the coverage invariant flagged all 224 not_voting instances as "both voted
  and absent"; corrected so coverage is accounted by `member_votes` alone and the
  vote<->stub correspondence is invariant (3).
- **The manifest is the single wall-clock/commit carrier (§6.3); both are injected,
  never read inside the builder.** `build_manifest(generated_at, commit)` takes both
  as args so the double-export determinism test passes fixed values; `export.main()`
  resolves the real UTC time + `git rev-parse --short HEAD` (env overrides
  `CIVIC_GENERATED_AT`/`CIVIC_COMMIT` for reproducible/CI runs). `commit` = HEAD at
  generation time (the code that produced the export), explicitly NOT the commit that
  will contain the manifest (that sha can't exist yet). The nightly job's per-run
  manifest timestamp change is expected diff noise; every other record stays
  wall-clock-free.
- **`uv run export` is offline and regenerates only DERIVED artifacts (schemas +
  manifest).** It must never re-run an ingest: that needs the gitignored raw cache +
  network, and (D24) resets every `vote_class` to `unclassified` until a reclassify.
  Per-record files are written by their ingests; `export` covers what depends on the
  whole committed dataset. Keeps the export step network-free in CI.
- **JSON Schemas describe FILE shapes, not just models.** The vote file is a composite
  `{rollcall, member_votes}`, so it maps to a `VoteFile` wrapper model, not a bare
  `RollCall`. Schemas for member/vote/bill/absence are generated from pydantic and
  committed under `data/schema/`; a test fails if the committed copies drift from a
  fresh generation (re-run `uv run export`). `export_bill()` + the Bill schema ship now
  though no bill data exists yet, so the contract is complete for every Tier-1 type
  (bill ingest lands with INC-8).

### INC-9 (2026-08-12) — Automation + deploy

- **D31 — incremental ingest = skip-if-FINAL, not a blanket long TTL (§6.1).** The
  cache TTL is 20h but nightly runs every 24h, so without a skip every cached vote
  detail would re-fetch nightly (~3,467 calls, an API hammer, §0.7). `incremental.py`
  peeks the ALREADY-EXPORTED file: if `data/votes/{id}.json` exists and its
  `rollcall.date` is older than 7 days, the roll is skipped entirely (no fetch/parse/
  export). This resolves the chicken-and-egg (the date is in the response, not knowable
  before fetching) by reading the export, and — critically — a blanket long TTL was
  REJECTED because it would never refresh a vote corrected by the clerk 2 days later
  (value #1). Recent (<7d) and new rolls fall through to a normal fetch; the 20h TTL
  gives them correct refresh without `force`. Bills mirror this: skip if exported,
  EXCEPT bills referenced by a roll <7d old (their `latest_action` moves). Measured:
  today 3,454 rolls skip, 13 refetch. Unparseable/naive dates are treated as NOT final
  (never skip on ambiguity). All helpers take an injected `cutoff` → deterministic tests.
- **D32 — deploy is Cloudflare Workers (Static Assets) via Workers Builds; the
  workflows hold NO Cloudflare secret.** (Updated mid-INC-9 from Pages → Workers per
  the owner's H4 setup.) `site/wrangler.jsonc` declares an assets-only Worker serving
  `./dist` with `not_found_handling: "404-page"` (a `404.astro` now builds). Workers
  Builds watches the repo: a push runs `npm run build` and deploys — so `nightly.yml`
  just commits+pushes when green, and a failed check exits nonzero WITHOUT committing,
  leaving the last good deploy live (§6.1). `CLOUDFLARE_API_TOKEN`/`ACCOUNT_ID` are for
  the INC-16 aggregates Worker + D1 and manual `wrangler deploy`, not the site auto-
  deploy. The footer build-commit reads `WORKERS_CI_COMMIT_SHA` (Workers Builds' var,
  via `process.env` — not PUBLIC_-prefixed) after our own `PUBLIC_BUILD_COMMIT`.
- **D33 — nightly ordering + "commit only on real change".** ingest votes+bills →
  (if vote data moved) classify → corrections → **diff-gate on `data/`** → if changed:
  export → site build → checks → verify-recompute → commit+push; else: export/build/
  checks for drift detection, exit 0 without committing. Classify runs conditionally
  because re-fetching a recent roll re-exports it as provisional `unclassified` (D24) —
  classify RESTORES it to byte-identical, so an unchanged recent roll leaves no diff and
  triggers no commit. This makes `generated_at` mean "last real data change" (the
  manifest isn't regenerated until after the diff-gate, so its per-run timestamp can't
  false-trigger the gate). Note: a push made with `GITHUB_TOKEN` does NOT retrigger
  `ci.yml` (checks already ran inline in nightly); Workers Builds still deploys (its
  webhook is a GitHub App, not Actions). Branch protection, when enabled, must bypass
  the `github-actions[bot]` push (documented in H4); the push is always fast-forward,
  never `--force`.
- **D34 — corrections are data, not a git-shell in the page; Lighthouse is the new
  gate.** `ingest/corrections.py` (`uv run corrections`) reads `git log --grep
  '^correction:'` → `data/corrections.json`, which `/corrections` renders — so the
  Cloudflare build (which can't shell to git and doesn't control clone depth) still
  "builds from data alone". Nightly regenerates it with `fetch-depth: 0`. Lighthouse
  mobile perf + a11y ≥ 90 (`lighthouserc.cjs`, URLs derived from data, median of 3 runs
  against `astro preview`) is wired into CI — the INC-9 acceptance gate; the MVP pages
  carry no client JS so they score ~100.
- **D35 — the ingest re-exports absence stubs with `overwrite=False` so it never
  clobbers an owner-approved reason.** `export_absence()` wrote unconditionally; the
  ingest emits a bare stub (`stated_reason=None`) for every `not_voting` on every
  FETCHED roll. Nightly re-fetches recent (<7d) rolls (D31), and a personal explanation
  can be filed within days of the vote (INC-6's real Guest case: filed 1 day after) —
  so an unconditional re-write would silently reset an H9 approval to "No explanation on
  record.", a false statement (value #1). Fix: the ingest passes `overwrite=False`
  (preserve any existing file — the stub carries nothing a re-fetch updates; the reason
  fields are owner-owned); the curation tool writes the approved Absence directly, not
  through this helper, so it still overwrites correctly. A position correction that
  orphans a stub is caught by verify-recompute's reciprocity invariant, not silently.

### INC-8 (2026-08-12) — Site MVP

- **D27 — detail-only bill ingest; `subjects` and `cosponsor_ids` deferred to INC-10
  as `None` (not `[]`).** The covered bill set = the 1,011 distinct non-null
  `RollCall.bill_id`s, so every vote's bill link resolves to a real page. One
  `/bill/{c}/{type}/{number}` fetch yields every field the INC-8 bill page renders
  INLINE (title, policyArea, first sponsor, cboCostEstimates, latestAction —
  SHAPES §4). `subjects` and `cosponsors` are paginated sub-resources consumed by
  INC-10 metrics, not INC-8, so fetching them now would be ~3× the requests for data
  nothing renders yet. They are left `None` — and the `Bill` schema was widened to
  `list[str] | None` — because an empty `[]` is a POSITIVE false claim ("zero
  cosponsors"), which value #1 forbids; `None` = not-yet-collected, mirroring
  `Statement.specificity_level`. INC-10 backfills. `source_url` = the bill's public
  `legislationUrl` (congress.gov), not the API URL. Titles are `html.unescape`d (the
  API entity-encodes `&#039;`/`&amp;`; the decoded char is the faithful verbatim
  string and avoids a double-escape on render — a lossless normalization, not a
  paraphrase). Quarantine + §6.1 ceiling apply; this is NOT full bill coverage
  (INC-10's per-member sponsored-legislation enumeration is a different set).
- **D28 — the site reads committed `data/**` at build time via `node:fs`, never a
  bundler glob.** `site/src/lib/data.ts` memoizes per-directory reads; pages call it
  from Astro frontmatter (Node during `astro build`). Zero runtime data fetching
  (§10.1) — the output is static HTML. **Member vote lists are paginated at 200
  rows/page** (`m/[member]/[page]`): a member has ~1,700+ eligible rolls, and one
  page of that fails 380px usability and the INC-9 Lighthouse budget. ~3,467 vote
  pages + ~1,011 bill pages + member pages build from data alone.
- **D29 — §6.7 copy rules are implemented as shared components so they can't drift
  per-page.** `VoteRow.astro` encodes the full vote-row contract (position, date,
  roll #, always-visible `Badge`, verbatim question, bill link, official record);
  `Badge.astro` renders the vote_class with a neutral, non-lean tooltip; absences
  render the verbatim reason + CREC link or the EXACT string "No explanation on
  record."; bill titles carry the ⓘ "titles are written by the drafters" affordance;
  `Layout.astro`'s footer carries data-last-updated (manifest), methodology +
  corrections links, and the build commit (`PUBLIC_BUILD_COMMIT`, set to the CI sha).
  vote_class tooltip copy lives in `display.ts` as UI chrome (§0.5) — kept strictly
  procedural since only the INC-20 glossary page is banned-words-allowlisted.
- **D30 — INC-8 acceptance is enforced by three CI gates.** (a) `astro build` from
  committed data with no network; (b) `scripts/check-source-links.mjs` — a plain
  node pass over `dist/` asserting every vote and bill page's HTML cites its record's
  `source_url` (the "every rendered claim traces to a source_url" criterion, ~4,500
  pages, cheap string check); (c) Playwright (`@axe-core/playwright`) — WCAG2 A/AA
  axe scan + a 380px no-horizontal-overflow assertion + screenshot artifacts on six
  representative pages, run against `astro preview`. Browsers install in CI after the
  build. Representative page ids are computed from data (never hardcoded), so the
  suite can't target a page that doesn't exist.

### INC-10 (2026-08-12) — Metrics layer + methodology page

- **D36 — aggregate `party_totals` on `RollCall` makes party-unity honest and
  recomputable, without storing any non-Mississippi individual.** A true party-unity
  metric needs each party's majority position per roll; we store only the MS
  delegation's positions. The raw House (`voteParty`) and Senate (`<party>`)
  responses carry every member's party, so the parser now derives a per-party
  breakdown of the same chamber tally and stores that AGGREGATE (`{D:{yea,nay,…},
  R:{…},I:{…}}`) — no individual non-MS position is added (value #3; these are
  public officials' public votes in aggregate). `None` on `non_position` rolls (D27
  not-applicable sentinel). `verify-recompute` gains a 4th invariant: the party
  splits sum to the chamber totals per category, and are present exactly on position
  rolls — the third-party proof that the aggregates are internally honest even
  though the per-member source isn't committed. Backfilled all 3,467 rolls by
  re-parsing the cached raw responses (`CIVIC_CACHE_TTL_HOURS` override + `ingest
  {house,senate}-votes --all`) — fully offline, no re-fetch, polite (§0.7);
  `classify` round-trips the new field (full-record passthrough).
- **D37 — `data/legislation/{member}.json` is the committed metrics input, shaped to
  survive the quiet-night diff-gate.** Metrics must recompute from the repo (the
  verify-recompute contract), so member sponsored/cosponsored bills are a committed
  artifact, not a live count. Three shape decisions: (a) `LegItem` carries NO live
  latest-action field — a bill's latest action moves through committee, so storing
  it would diff `data/legislation/` almost every night and defeat D33; only a FROZEN
  `enacted_action` is kept, and only when `became_law` (an enacted bill's action
  never changes). (b) Floor AMENDMENTS are excluded — the endpoints interleave them
  (`type:null`, an `amendmentNumber`) but an amendment is not a bill and can't become
  law under its own number; "sponsored/cosponsored" means bills and resolutions.
  (c) The covered-window paginator stops only on a fully-out-of-window page, never on
  the first old item, so boundary jitter can't drop covered tail items (an undercount,
  value #1). `enacted_rate` counts only bills enacted UNDER THEIR OWN NUMBER
  ("Became Public Law") — a documented understatement, since much text is enacted by
  folding into another vehicle, which we will not fabricate attribution for.
- **D38 — `cosponsor_vote_gap` is a factual list with a base-rate caveat baked into
  the published methodology, and tightened from the literal spec.** The spec said
  "cosponsored + no floor action ≥ 1 session"; we implemented "cosponsored in a
  Congress that HAS ENDED" (a bill cosponsored in session 1 routinely gets its vote
  in session 2, so listing it mid-Congress is a false "went nowhere" — value #1). The
  data proved the `no_floor_action` variant is base rate, not member signal (191–436
  per member, symmetric across parties: most introduced bills never get a floor vote,
  and scheduling is leadership's, not the cosponsor's). Rather than delete a
  spec-listed metric (D26 precedent — adapt via ADR), that caveat is written into the
  metric's docstring, which IS the published methodology sitting next to the list;
  the ADR further BINDS future rendering: never a bare count, always against its
  denominator, never a headline. The `cosponsored_and_voted_nay` variant computed
  zero for every member — an honest published null; its items carry the roll id for
  traceability (§6.7).
- **D39 — `named_measure_mismatch` fails closed until INC-11 supplies statement
  stance.** The mismatch is "specific statement naming a measure vs the OPPOSITE
  recorded vote", but a `Statement` is verbatim text with no stance/paraphrase field
  (by design), so the opposite-position test cannot be computed today. The function
  returns `[]` (empty by construction — zero statements exist) and RAISES if a
  qualifying statement (member-matched, specificity 2–3, non-empty `named_measures`)
  is ever curated before the stance comparison is built — the nightly then fails
  loudly and the last good deploy stays live, forcing INC-11 to implement it rather
  than letting a false "mismatch" publish (value #1).
- **D40 — metrics are Tier-2, pure/offline, docstring-as-methodology, guarded against
  Tier-3.** Every metric reads only the committed dataset (a `Ctx` loaded once), so a
  third party recomputes from the public repo; the `test_recompute_matches_committed`
  test is exactly `build().model_dump() == data/metrics.json` — the recompute-and-match
  for all 8 metrics at once. Each metric function's docstring is extracted verbatim
  (`inspect.cleandoc`) into `data/metrics.json` and rendered as that metric's
  methods-page section (one section per key, asserted by `check-metrics-sections.mjs`).
  The `METRICS` registry drives an AST Tier-3 guard (`checks/integrity.py`) that fails
  if any metric function calls another — structurally preventing a per-member composite
  "spectrum" (§5). `_load` raises on a missing legislation record (no silent false
  zeros). `metrics.json` is DERIVED data recomputed in the nightly after classify +
  corrections but before the diff-gate, so a legislation-only change (a new
  cosponsorship — a real event, legitimate periodic commit, not churn) still reaches
  the gate; a truly-quiet night regenerates it byte-identically (D33).
- **D41 — statement↔vote pairing resolves in ONE place (Python), and the result is
  published on the record.** D9's bright line (pair by bill id; a short title only via
  the owner's explicit `_title_allowlist.yaml`) must mean the same thing in the metric
  layer (Python) and the timeline (TypeScript at build). Implementing it twice would let
  the two drift. So `ingest/pairing.py::resolve` is the sole resolver; curation runs it
  at save time and stores the outcome in `Statement.paired_bill_ids`; `metrics.py` and
  `data.ts` both READ that field and never re-resolve. Editing the allowlist afterwards
  requires `curate statements repair` to re-resolve existing records (resolution is
  otherwise frozen at save). Statements are published as deterministic **JSON**, not the
  spec's "YAML written" — `symmetry._load_statements` and `metrics._load` already glob
  `data/statements/*.json`, and the data-contract's global rule is JSON via `_dumps`;
  only `_title_allowlist.yaml` (owner-edited config, not a record) stays YAML.
- **D42 — `named_measure_mismatch` un-fails-closed via an owner-assigned stance field.**
  D39 deferred the opposite-position test for want of a stance. INC-11 adds
  `Statement.stated_position` (`support`/`oppose`/`null`) — an owner classification, the
  sibling of `specificity_level`, NOT a paraphrase (`text` stays verbatim). The metric now
  emits an entry when a specificity-2/3 statement with a stance names a measure that
  resolves to a bill (D41) AND the member's own **passage** vote on that bill is the
  opposite side (support⇒Yea expected, oppose⇒Nay). Deliberately EXCLUDED, never guessed:
  no stance, an unresolved measure, and every non-passage class (a Nay on a procedural
  motion is not a vote against the bill). Entries carry both records + both dates and claim
  no sequence — adjacency only (§6.7). Empty until qualifying statements are curated (H8).
  Because the docstring IS the published methodology, this rewrite re-generates
  `data/metrics.json`; the recompute-and-match test (D40) enforces that.
- **D43 — "no verified capture, no save" is enforced server-side, and capture never goes
  through the cache.** A statement's permanent Wayback copy is captured via the SPN2 API
  (`ingest/sources/archive_org.py`): POST /save → poll status → and then HEAD-verify the
  `archive_url` actually resolves before the capture counts as verified (value #1). This is
  a mutating POST, so it must NEVER be cached/replayed — it bypasses `cache.py` entirely.
  `curation.statements.build_statement` requires a real `Capture` object (the sole producer
  of a verified `archive_url`), so a raw URL string cannot be saved; the Flask app's Save
  control likewise appears only after a verified capture. Auth uses IA S3 keys (H6,
  `Authorization: LOW …`, header-only) with an unauthenticated fallback that honors the §6.1
  ≤ 1 capture / 15 s ceiling. The curation Flask app binds loopback only (`assert_loopback`
  refuses any non-loopback host) and supersedes the INC-6 absence CLI.
- **D44 — dead archive links are excluded at BUILD time via a committed report.** "Flagged
  unpublishable" has to survive into the static build, which reads only the repo — so the
  weekly `checks/archive_links.py` sweep HEADs every `archive_url` and writes the confirmed
  dead ids to the committed `data/quality/archive-status.json`; `data.ts::getStatements`
  drops any statement listed there until it is recaptured. A 4xx is dead (fail + exclude); a
  network error or 5xx is a transient outage (warn only, never excludes) — the integrity
  clerk-outage pattern. The sweep is weekly + network, so it is deliberately kept OUT of the
  offline-deterministic `uv run checks` suite; the `archive-links.yml` workflow commits the
  regenerated report first (so the next build excludes a newly-dead link) and then propagates
  the nonzero exit as the GitHub failure notification (the alert channel, like nightly).

### R-3 (2026-08-12) — Historical-retention scaffolding (review H-2)

- **D45 — metrics carry formula identity, and git is the supported metric time-series;
  a materialized history directory is deferred.** The scope doc's "adjust grading
  historically so long-term metrics are not skewed" needs two things decided *before* any
  grading engine exists, or they cost a reconstruction later. (a) **Formula identity on
  `data/metrics.json`:** a top-level `schema_version` integer (manually bumped on any
  semantic formula change — the coarse guard that also covers shared `_`-helpers) and a
  per-metric `digest` = `sha256(newline-normalized function source)[:16]` in each
  `methodology` entry (auto-bumps on any change to that metric function's body). Together
  they let a future re-weighting know whether two historical numbers are formula-comparable.
  The digest is newline-normalized *before* hashing so a Windows-dev CRLF checkout and CI's
  LF produce the same digest — otherwise `metrics.json`, and the D40 `build() == committed`
  determinism, would differ per platform. Both fields are pure/offline, so D40 still holds
  (committed `metrics.json` + schema regenerated; existing values byte-unchanged). Known,
  documented limitation: the digest covers the metric function's own source only, which is
  why the manual `schema_version` bump is contractually required for helper changes.
  (b) **Time-series contract:** git is the store — every nightly commit of `metrics.json`
  is a dated snapshot anchored by that commit's `manifest.generated_at`. Made a *supported*
  contract, not an accident: `git checkout <sha> -- data/ && uv run ingest metrics`
  reproduces that commit's file byte-for-byte (D40 extended along the time axis, documented
  in `docs/data-contract.md`), and a new reporting command `ingest metrics history
  <bioguide> [--metric <key>]` extracts the `(commit, generated_at, schema_version, metrics)`
  series from git history. That command reads git only and is NOT on the build/export path,
  so it is exempt from the no-network/no-wall-clock rules that bind `build()`; it emits the
  recorded values verbatim and computes no composite, ranking, or score — preserving Tier-2
  discipline and the D19 line (grades are the reader's to compute, never the site's).
  (c) **Deferred:** a materialized `data/metrics/history/` directory buys nothing until a
  trend UI needs random-access to old snapshots; git already holds the series, so it waits.
  The **grading engine itself remains an owner escalation (§7)** and is deliberately NOT
  built here — this is scaffolding only.

### R-2 (2026-08-12) — Membership-churn resilience (review H-1)

- **D46 — the covered-member set refreshes nightly, and an official in the vote record
  but not the roster halts the run instead of drifting in silently.** The MS delegation
  changes mid-Congress (special election, death, resignation); the set was frozen
  (`nightly.yml` never ran `ingest members`) and the two chambers failed in opposite bad
  ways — House silently exported an orphan (votes on file, no page, no metrics, no alarm,
  the exact asymmetric-coverage shape value #2 forbids), Senate raised `KeyError` on every
  new roll and failed permanently. Five decisions: (a) **Roster refresh FIRST** — `ingest
  members` runs before the vote ingests in `nightly.yml` (idempotent, keyless
  congress-legislators fetch; a quiet night rewrites `data/members/*.json` byte-identically,
  D33), so a delegation change lands before `_covered_house`/`_lis_to_bioguide` read it and
  the common case self-heals. (b) **House loud-fail parity** — `house_votes.run` now computes
  `extra = voted_ms − expected_ms` post-parse and, on a hit, quarantines the roll, records an
  `unknown` failure, and **skips export** (no orphan written to disk at all — stronger than
  "export then fail") before returning nonzero with a `run \`ingest members\`` message. The
  Senate raise is left as-is: it was already the correct alarm; only its permanence (no
  refresh) was the defect, now cured. Chosen post-parse in `run()` over passing the covered
  set into `parse_rollcall` so the parser stays pure (no test churn). (c) **Metrics backstop**
  — `metrics._load` raises on a position whose `member_id` has no Member record (mirrors the
  missing-legislation guard), defending direct `ingest metrics` runs. (d) **Legislation
  relaxation** — the "≥1 sponsored bill in EACH covered congress" sanity check now applies
  only to congresses the member actually SERVED (from `terms` via `_term_overlaps`), so a
  member who joined after the 118th no longer false-fails on zero 118th bills. Residual: a
  member who served only the current congress and genuinely sponsored zero bills in it still
  trips the check (a served-congress zero reads as a truncated fetch); acceptable per the
  review's own acceptance framing. (e) **Check-layer detection** — `checks/symmetry.py` and
  `verify_recompute.py` flagged `expected − got` only, so an extra committed member never
  alarmed; both now also flag `got − expected`, closing the gap on the already-committed
  dataset as defense-in-depth. No published schema or data changes — every fix is pass/fail
  logic or ordering; on the current six-member delegation (all rostered, all served both
  congresses) behavior and committed data are byte-identical.

### R-1 (2026-08-12) — Statement-ledger hardening (review M-1/M-2/M-3/M-6), gates H8

- **D47 — the statement tool is hardened BEFORE the owner curates the first real quote,
  because every soft spot becomes a published-data migration once content exists.** Four
  changes: **(a) id includes the text (M-2).** The id was `{member}-{date}-{sha8(source)}`,
  so two different quotes from one source on one date silently overwrote each other; it is
  now `{member}-{date}-{sha8(source)}-{sha6(text)}` — identical re-curation stays idempotent,
  distinct quotes get distinct files. Done now (corpus empty) so it is never a rename of
  published ids. **(b) input validation (M-6).** `Statement.date` gains a pydantic
  `field_validator` requiring ISO `YYYY-MM-DD` (a mistyped date otherwise rode into the id
  and broke newest-first timeline ordering); specificity is already a `Literal[0,1,2,3]`.
  The Flask app validates date + specificity at CAPTURE time — before the rate-limited SPN
  save — so a typo never burns an archive capture (stronger than the review's save-time
  minimum), and the save handler now peeks the draft and pops it only on success, so a
  rejected save never discards a verified capture. The validator is invisible to
  `model_json_schema()`, so `statement.schema.json` does not churn. **(c) one statement
  loader (M-3).** Loading was implemented four times with drifting semantics — the metric
  layer published `named_measure_mismatch` entries (the single most sensitive artifact,
  carrying a `source_url`) from statements the site withheld for a dead archive. New
  `ingest/statements_io.py` is the single reader; `_`-prefixed config files are always
  skipped, and one flag decides dead-archive exclusion: **metrics excludes dead**
  (unpublishable must not leak through the metric side door — its docstring, = the published
  methodology, now says so), **archive_links and symmetry include dead** (the sweep must
  re-check everything; balance is about curation effort, not publication), **export counts
  records on disk**. `symmetry._load_statements`/`archive_links._load_statements` stay as
  thin wrappers (preserving the monkeypatch surface); `site/src/lib/data.ts` is the
  TypeScript mirror, cross-referenced to the Python source of truth. This changes the metric
  input universe (a shared-`_`-helper change the per-metric digest cannot see), so
  `FORMULA_SCHEMA_VERSION` bumps **1 → 2** (also covering R-4a); member values are unchanged
  (corpus empty), only `metrics.json`'s `schema_version` + the mismatch methodology
  digest/text move. **(d) CSRF guard (M-1).** The loopback Flask app accepted plain form
  POSTs, so a malicious page the owner had open could forge a cross-origin approval/capture.
  A per-process token (unguessable, regenerated each start) is embedded in every form and
  required on every POST via `secrets.compare_digest`, plus a belt check rejecting any POST
  whose `Origin`/`Referer`, when present, is not loopback (`Origin: null` included). Applies
  to `/statements/capture`, `/statements/save`, `/absences/approve`. **Also removed** the
  zero-caller `capture_and_save` (§4 delete) — an untested parallel write path into the
  published dataset.

### R-4 (2026-08-12) — Truth-guard patches (review M-4/M-5)

- **D48 — two paths that could publish a false factual claim are closed at the source.**
  **(a) Attendance null on a zero denominator (M-4).** `attendance.pct` returned a
  fabricated `0.0` when `eligible == 0`, contradicting `data-contract.md` ("pct is null on
  a zero denominator, never a fabricated 0") and the D27 false-zero rule; unreachable for
  the current six, but a mid-term arrival with zero eligible rolls (compounding H-1/R-2)
  would have published "attendance 0.0%". Now `pct` is `None` when `eligible == 0`;
  `AttendanceValue.pct` widens to `float | None` (regenerating `metrics.schema.json`'s
  `pct` to `anyOf number/null` and the attendance methodology digest/text). No current
  member value changes. The `FORMULA_SCHEMA_VERSION` bump for this shipped with R-1 (-> 2).
  **(b) Absence edit path is trim-only (M-5).** The `e`/edit branch attached the CREC page
  citation to whatever the owner typed, so a paraphrase or typo could publish as a
  "verbatim" quote the source never carried. `approve_one(reason=...)` now requires the
  edited text, whitespace-normalized, to be a NON-EMPTY substring of the candidate's
  `verbatim_text` — trimming a salutation is allowed, rewriting is refused with a message
  pointing at the queue file; the interactive loop catches the refusal instead of crashing.
  Empty/whitespace-only edits are rejected (else `""` — a substring of everything — would
  publish an empty citation).

### R-6 (2026-08-12) — Small fixes batch (review L-1/L-2/L-3, §4 delete)

- **D49 — a batch of low-severity correctness + cruft fixes; no behavior change to any
  published figure.** (L-1) The manifest counted the 20 Speaker-election `non_position`
  rolls inside `rollcalls_by_vote_class.other` (= 24), hiding the genuine one-off rate (4).
  `_count_dataset` now counts them under a distinct `non_position` key (= the existing
  `non_position_rollcalls`), so `other` reads honestly; `data-contract.md` updated.
  (L-2) `corrections.parse_log` now keeps only entries whose SUBJECT starts with
  `correction:` — `git log --grep` matches the whole message, so a commit with the tag in
  its BODY was producing a bogus, un-prefixed ledger entry. (L-3) `bills.run` printed fetch
  failures twice; collapsed to the single FAIL line that decides the exit code. (§4 delete)
  Removed the unused `clerk_house.roll_xml(year, roll)` — `roll_xml_url()` is the path
  integrity uses. Manifest regenerated (counts split only; the `other`/`non_position`
  numbers move, nothing else).

### R-5 (2026-08-12) — Nightly raw-cache persistence (review M-7)

- **D50 — `data/raw/` is persisted across nightly runs with `actions/cache`, so a quiet
  night makes a dozen live requests instead of hundreds.** The ephemeral runner re-fetched
  every enumeration/menu page, every recent roll, and each member's full sponsored/
  cosponsored pagination at the enforced 1 req/s — within the politeness rules but against
  their spirit (§0.7), and each request was a transient-failure chance to abort the night.
  Cache key is unique per run (`nightly-raw-${{ github.run_id }}`) so every night SAVES a
  fresh snapshot, while `restore-keys: nightly-raw-` restores the most recent prior cache.
  Staleness needs no special handling: the cache layer's own 20h TTL (`ingest/cache.py`,
  `CIVIC_CACHE_TTL_HOURS`) re-fetches anything older, and the incremental ingest already
  skips finalized rolls. **Open — needs runtime verification:** the first run after this
  lands only SAVES (no prior cache exists); the cache-hit skip count shows on the SECOND
  scheduled run. Nothing else in the pipeline changes.

## INC-12 — Mississippi state legislature layer (branch A / GO)

### D51 (2026-08-12) — jurisdiction schema extension + partitioned storage

- **State data extends the canonical schema and lives in its own directory partition, so
  the federal fail-closed guards never see it.** The guards built through INC-11 (incl. the
  R-2 churn guards) assume every record under `data/{members,votes,bills}/` is federal;
  dropped in as-is, MS records would fail CI instantly (metrics' missing-legislation raise,
  symmetry expecting MS members on every federal roll, the classification gate on
  non-congressional question strings). **Two coupled decisions:** (a) **partition** — MS
  records live under `data/state/ms/{members,votes,bills}/`; every federal consumer globs
  `data/{...}/*.json` NON-recursively (verified by a consumer sweep of `MEMBERS_DIR`/
  `VOTES_DIR`/`BILLS_DIR`/`repo_root()/"data"`), so the partition is invisible to them and a
  state consumer opts in explicitly — no federal guard needs a retrofit. (b) **extend, don't
  fork** (spec INC-12, review section 6) — `Member`/`RollCall`/`Bill` gain `jurisdiction:
  str = "us"`, and `RollCall.congress`/`Bill.congress` widen to `int | None` (a state roll
  has no US Congress; MS `RollCall.session` carries the LegiScan session_id instead). The
  default keeps pre-INC-12 reads unchanged. **Field-leak trap settled by one-time
  migration:** with a defaulted field, `classify.run`/`export` would re-emit federal files
  WITH the key piecemeal on the next vote-change night; instead a single offline migration
  round-tripped all 4,484 federal records (6 members, 1,011 bills, 3,467 votes) through the
  models so they already carry `"jurisdiction": "us"` — re-emit is now byte-stable and the
  leak cannot happen. Schemas regenerated; 217 tests + checks + verify-recompute green; site
  builds. No federal value changed (metrics.json/manifest byte-unchanged). MS party code `N`
  (nonpartisan, 1 member) maps to `I` in the D/R/I model — documented on the limitations
  page (phase 6).

### D52 (2026-08-12) — LegiScan bulk ingest, MS classifier, TTL cache, banned-words fix

- **`ingest ms` turns the LegiScan bulk dataset for the current MS session into the
  canonical schema under data/state/ms/.** Flow: `getDatasetList(MS)` → the current REGULAR
  session (max `year_start`, non-special = 2026 Regular, session 2249) with its `access_key`
  + `dataset_hash` → `getDataset` returns a base64 ZIP (people/bills/votes JSON) → decode →
  pure `build_records` → export. Result committed: **174 members, 1,725 roll calls, 905
  vote-referenced bills, 144,007 member votes, 0 quarantined.** Discipline mirrors the
  federal ingests: pure parsers + a pure `build_records` the tests drive offline; a per-roll
  **tally cross-check** (per-person counts must equal the LegiScan header yea/nay/nv, else
  `TallyMismatch` → quarantine); an **unknown-people_id guard** (`UnknownPerson`, parity with
  R-2); `party_totals` **fully computed** (LegiScan gives every position, so this is the
  whole 174-member chamber, not a covered delegation — feeds a future MS party-unity).
  Bills published = vote-referenced only (parity with federal D27). Records carry no
  wall-clock; only the MS manifest carries an injected `generated_at`/`commit`/`dataset_hash`.
- **MS vote classifier** (`classify_ms`): the §A1 congressional classifier does not apply to
  MS `desc` strings, so a small MS-scoped keyword table maps the 16 observed descriptions →
  {passage, veto_override, procedural}. All 1,725 rolls classified (1,721 passage / 3
  veto_override / 1 procedural), zero `other`.
- **TTL cache for LegiScan** (the carried-forward gap): `legiscan._get` gained a
  `fetched_at`-freshness check (default `DEFAULT_TTL_HOURS`=20, `CIVIC_CACHE_TTL_HOURS`
  overridable) so a re-run reads the cached response instead of re-fetching (and re-counting
  quota); the key still never touches the cache key or `.meta`.
- **banned-words word-boundary fix** (surfaced by real MS data): the §6.4 check matched
  substrings, so the real bill title "Junior **Auxiliar**y of …" tripped `liar`
  (aux-i-LIAR-y); "familiar"/"peculiar" would too. Now each term matches as a whole word
  (`\bterm\b`) — the intent all along (§6.4 targets partisan framing words we authored). A
  standalone banned word is still caught; regression test added. No prior hit changes.
  MS party `N` (nonpartisan, 1 member) → `I` in the D/R/I model (limitations page, phase 6).

### D53 (2026-08-12) — MS checks + integrity spot-check (offline)

- **`checks/ms.py` (registered in the offline suite) guards the MS partition with two
  passes.** CONSISTENCY (the verify-recompute + classification + party-split analog):
  every MS roll's member_votes recompute the stored `totals`, `party_totals` sum to
  `totals` per category, every voter is in the roster, and no roll is `other`/`MS-OTHER`.
  INTEGRITY (scrape fidelity): the GO verdict (D21) matched LegiScan to the official
  billstatus per-vote PDFs 5/5 (470 per-person positions) — this re-runs that at the
  **tally level in CI, offline**, against the committed sample PDFs (`data/quality/
  samples/ms_vote_xcheck/*.txt`): each sample's official Yeas/Nays/Absent `Total--N`
  (House uses "Absent or…", Senate "Absent and…", House may add "Present--") must equal
  our ingested roll's totals. All 1,725 rolls recompute; 5/5 official tallies match.
- **Deliberately offline, not a live billstatus fetch:** the official per-vote PDF URL
  (e.g. `.../votes/house/0100010.pdf`) is NOT derivable from the LegiScan record, so an
  arbitrary-roll live fetch isn't possible without manual URL discovery — and a live
  billstatus fetch would need the bundled intermediate CA (CI/Linux does no AIA chasing,
  D21). The committed-sample tally check gives real, deterministic scrape-fidelity
  regression coverage without that fragility. **Deviation from spec's "10-vote":** the
  automated CI guard covers the 5 GO-verdict samples; the per-person 470-position match
  is recorded in the verdict. Expanding to more samples is additive (drop a PDF text +
  its roll_call_id into `_SAMPLES`).

### D54 (2026-08-12) — MS state site pages under /ms/

- **The state layer renders under a `/ms/` route prefix with its own loaders and a lean
  vote-row, so the federal site is byte-identical when no state data exists.** New pages:
  `/ms` (index, House + Senate by district), `/ms/m/[member]/[page]` (paginated vote list),
  `/ms/v/[roll]` (question, totals, all positions grouped Yea/Nay/Not-voting), `/ms/b/[bill]`
  (title, sponsor/cosponsors, subjects, rolls-on-bill). `data.ts` gets parallel `getMs*`
  loaders reading `data/state/ms/` (separate from the federal loaders — no cross-
  contamination). `MsVoteRow` mirrors the §6.7 contract but routes to `/ms/…` and omits the
  federal CREC "No explanation on record." line (MS has no personal-explanation pipeline;
  the position label states Not-voting plainly). Site grew 4,540 → **7,919 pages**. The
  federal home links to `/ms`. Gates extended to cover the partition: `check-source-links`
  now verifies MS vote+bill pages cite their source_url (7,108 pages); the Playwright axe +
  380px suite adds 4 MS pages (24/24 green); Lighthouse adds the heaviest MS page. `astro
  check` clean (the `congress: int|None` widening surfaced one federal-roll-page guard).
  Source-URL honesty: MS roll calls cite the LegiScan vote page (our data source; bots get
  403 but humans see it — the string-presence check is unaffected), bills cite the official
  billstatus link where present; the scrape-fidelity framing is on the limitations page.

### D55 (2026-08-12) — nightly MS refresh, hash-gated

- **`nightly.yml` runs `uv run ingest ms` (with `LEGISCAN_API_KEY`, already a GH secret)
  after the federal ingests; a `dataset_hash` gate makes a quiet night a one-request
  no-op.** `run()` first calls `getDatasetList` (one cheap call) for the current session's
  `dataset_hash`; if it equals the committed MS manifest's hash and the data is present,
  it fetches nothing and rewrites nothing — crucially NOT the manifest's wall-clock
  `generated_at`, so it can never false-trip the nightly `git status --porcelain data/`
  diff-gate (the 2026 session is `sine_die`, so this is the normal case). A new/changed
  session (hash differs) re-ingests data/state/ms/ and the existing diff-gate commits it.
  `--force` bypasses the gate for a manual full re-ingest. CI needs no LegiScan key — it
  builds + checks from the committed MS data offline (checks/ms + the MS pages + the
  source-link/e2e gates all run on committed data).

### D56 (2026-08-12) — MS data-limitations page (spec acceptance)

- **`/methods#mississippi` publicly documents what the MS layer does and does not cover**
  (the INC-12 acceptance "gaps documented publicly"), linked from the `/ms` index and the
  federal home. It states, in plain language: the source is LegiScan mirroring the official
  `billstatus.ls.state.ms.us` record, with scrape fidelity verified against the official
  per-vote PDFs (470 positions; the CI spot-check re-confirms sampled tallies); coverage is
  the current regular session only; positions are Yea/Nay/not-voting only (not-voting folds
  absent + present, and there is no personal-explanation process); LegiScan's one
  "Nonpartisan" member is shown as Independent; only vote-referenced bills are published;
  and the Tier-2 metrics are not yet computed for MS members. A plain `<h2 id="mississippi">`
  section — it carries no `data-metric`, so the metrics-sections set-equality check is
  unaffected. `data-contract.md` gains the matching `data/state/ms/` file-format section.
  **INC-12 complete** (all 6 phases; ADRs D51–D56).

### D57 (2026-08-12) — member-page metric rendering (the review's post-INC-12 item)

- **The 8 Tier-2 metrics were computed + published in `data/metrics.json` since INC-10 but
  rendered NOWHERE except the `/methods` definitions — so a visitor saw the raw vote list
  but no organized statistics.** `MemberStats.astro` now surfaces them as a KPI row of stat
  tiles at the top of each federal member page (`/m/[member]/[page]`), under the D38
  discipline: every figure carries its denominator/context (attendance = cast of eligible;
  party unity = agreed of substantive; enacted = enacted of sponsored), each tile links to
  its exact `/methods#metric-*` section, the `cosponsor_vote_gap` adjacencies sit in a
  collapsed `<details>` with their base-rate caveat, and — load-bearing — **nothing is
  combined into a per-member score** (the Tier-3 no-composite rule / "no thumb on the
  scale"; a reader may weigh these client-side later, D19). Plain ink on the neutral surface
  (no color-as-meaning; the form is stat tiles, not a chart); null pct (R-4) renders "—".
  MS members are unaffected (no `data/metrics.json` entry → the guard skips the section);
  computing MS metrics is a follow-on. axe + 380px green; banned-words green; astro check 0.

### D58 (2026-08-12) — Mississippi Tier-2 metrics (follow-on to D57)

- **The 5 scalar stats now compute + render for the 174 MS legislators, reusing the
  federal FORMULAS verbatim.** `ms_metrics.build()` loads the committed MS partition into
  the federal `metrics.Ctx` and calls `metrics.{attendance,party_unity,sponsored,
  cosponsored,enacted_rate}` unchanged — identical semantics + audited digest, only the
  source data and methodology TEXT are MS-specific (the federal docstrings say "covered
  Congresses"). Recomputable: a new committed **`data/state/ms/legislation/{member}.json`**
  (built from ALL 4,006 session bills, not just the 905 vote-referenced ones, so
  sponsorship counts are complete) + **`data/state/ms/metrics.json`** — `checks/ms.py` adds
  a recompute-and-match. **Two MS-specific data decisions:** (a) LegiScan marks every MS
  bill author `sponsor_type_id 1` (no primary/co distinction), so the FIRST-listed author
  is the principal ("authored") and the rest are "co-authored" — documented on the
  limitations page. (b) "became law" = the official history action **"Approved by
  Governor"** (368 bills carry it); reliably detectable, so MS gets a real enacted rate
  (e.g. an appropriations chair at 56/74, rank-and-file near 0 — honest variance).
  `MemberStats.astro` made jurisdiction-aware (a `periodLabel` + `jurisdiction` prop; MS
  labels "authored/co-authored", methodology links to `/methods#mississippi`); MS member
  pages render the tiles; the limitations page updated (stats now computed). `LegItem.congress`
  widened to `int|None`; `MsMemberMetrics`/`MsMetricsFile` models + `ms-metrics.schema.json`
  added. Still NO composite/score (Tier-3 rule holds). 254 tests; checks + 24/24 e2e green.

## Constitutional amendment + spec v2 adoption (2026-08-13)

The owner amended the founding values; `IMPLEMENTATION.md` and
`civic-ledger-scope.md` are archived unchanged at `docs/archive/2026-08-13-pre-v2/`
and superseded by **`IMPLEMENTATIONv2.md`**. The entries below are **SD-series
(spec decisions)**; their canonical home is IMPLEMENTATIONv2.md §2 — this log
carries the dated record. Builder ADRs continue as **D59+** in this file only.

- **SD-31 (2026-08-13) — ADR renumbering ends the D19 collision.** v1 spec §2's
  D1–D20 are renamed **SD-1..SD-20** one-to-one (canonical in IMPLEMENTATIONv2 §2);
  this file's builder D19–D58 keep their numbers untouched (append-only, never
  rewritten). Correcting note: **this file's line-3 header claim "D1–D18 live in
  IMPLEMENTATION.md" was stale** — the v1 spec carried D19–D20 too, colliding with
  this file's own D19 (Congress.gov path segment). Old citations of "the D19 line"
  in D45/D57 meant spec-D19 = **SD-19**.
- **SD-21 (2026-08-13) — Amendment 1: evaluative labels under a disclosure
  standard** replace "never render partisan lean." Publishable iff: published
  formula on /methods, official-source data, identical standard for every member
  and party (R-vs-D and R-vs-R), rendered with inputs + denominator, thresholds
  owner-ratified. Motive/intent/honesty/character never asserted. Value #1
  (never false or falsely framed) is unchanged and outranks it.
- **SD-22 (2026-08-13) — Amendment 2: data collection in scope.** Accounts
  (email+password), quiz answers/issue weights tied to an account, aggregate
  state-of-origin analytics; never sold; anonymous browsing stays. **Blocking
  gate:** every privacy document must be rewritten, true, and deployed before
  the first byte of user data is collected (V2-7 before V2-8/V2-9) — else the
  site publishes false statements about itself, a Value-#1 violation.
- **SD-23 (2026-08-13) — Amendment 3: the never-ask rule is scrapped.** The
  builder asks the owner when unsure, in plain non-technical language —
  especially judgment calls about what counts as good/poor performance.
- **SD-24 (2026-08-13) — Amendment 4: federal-first pivot.** All serving House +
  Senate members become the primary covered set; landing page becomes a
  drill-down stats dashboard; Federal + States tabs; states mirror the federal
  presentation and grow over time.
- **SD-25 (2026-08-13) — Value #4 ("ship partial value early") reconfirmed
  unchanged** by the owner after clarification.
- **SD-26 (2026-08-13) — Gate 1 resolved: grading level = per-category grades
  PLUS one fixed site-published overall grade** with an over-time trend
  (owner chose this over ranks-only, category-only, and reader-adjustable).
  **Retires SD-19** (grades-only-in-the-reader's-browser). The Tier-3 guard is
  repurposed from prohibition to disclosure (composites only in the designated
  scoring module, from ratified config) — IMPLEMENTATIONv2 §6.8.
- **SD-27 (2026-08-13) — Gate 2 resolved: threshold authority = propose →
  ratify → commit.** The builder proposes evaluative constants in plain English
  with rationale/citations; the owner ratifies; the value lands in committed
  config with its justification. Nothing evaluative publishes unratified — this
  is how the unamended no-LLM rule (§0.5) and the evaluative turn coexist.
- **SD-28 (2026-08-13) — Gate 3 resolved: account architecture = client-side
  encryption.** Argon2id auth; belief payload encrypted on-device (password-
  derived key + recovery code), server stores ciphertext only; public profile
  strictly opt-in and outside the encryption guarantee; hard delete; trends only
  via K-anon (=50) counters. Owner accepted the forgot-password-loses-answers
  trade-off. Supersedes SD-12; amends SD-2 and SD-17.
- **SD-29 (2026-08-13) — Gate 4 resolved: storage = public JSON contract +
  SQLite build accelerator.** Published data stays deterministic in-repo JSON;
  gitignored `build.db` becomes the required build intermediate at V2-1
  (triggering the deferred flat-file→SQLite decision); vote pages restructured
  to hold the built file count under the Workers Static Assets limit (verified
  2026-08-13: 20,000 files/version Free, 100,000 Paid, 25 MiB/file).
- **SD-30 (2026-08-13) — Gate 5 resolved: Mississippi preserved as-is through
  the pivot**, reskinned to mirror the federal presentation and folded under the
  States tab in V2-10. Touched once, at the end, against a finished template.

**Fates of the frequently-cited old decisions:** spec **D2 → SD-2 amended**
(counter-Worker design survives as the trends path; joined by the sync service —
note the Worker was never built); **D12 → SD-12 superseded** by SD-28 (its
ciphertext-only core survives inside the account architecture); **D17 → SD-17
amended** (analytics now in scope: aggregate, cookieless, state-of-origin);
**D19(spec) → SD-19 RETIRED** by SD-26; **D20 → SD-20 survives** (adjacency,
never "cost per vote" — the motive line outlives the evaluative turn);
**D1 → SD-1 amended** (covered set widens to all serving federal members);
builder **D36 dies at V2-1** (all-member positions will be persisted; the
"deliberately not recomputable" caveat inverts into full third-party
recomputability — retire with a dated D59+ ADR when V2-1 ships). This file's
**D19 (path segment) is untouched** and remains correct.

## V2-0 implementation session (2026-08-13)

- **D59 (2026-08-13) — GitHub repo stays private; site copy corrected to
  match, instead of making the repo public.** While pre-checking H16 (branch
  protection) the builder found `gh repo view` reports the repo as
  **private**, contradicting `IMPLEMENTATIONv2.md` §3 ("the client is open
  source"), `docs/correction-process.md`, and — live on the site —
  `/privacy` ("the entire dataset is the public repository") and
  `/corrections` ("the full history of the dataset is in the public
  repository"). Flagged to the owner as a possible Value #1 issue (a live
  page asserting something that may not be true). **Owner decision: leave
  the repo private; rewrite the site copy instead of flipping visibility.**
  Builder then rewrote `site/src/pages/privacy.astro` and `corrections.astro`
  to drop the public-repository claims (kept: no per-visitor data, every
  fact links to its official source, the corrections log itself — rendered
  from committed `data/corrections.json` — is public regardless of repo
  visibility) and removed the now-dead GitHub issue/commit/commits links,
  since a private repo 404s them for the public. `docs/correction-process.md`
  §1 reworded: no public issue tracker exists today; this is a known,
  unbuilt gap (a future email-based reporting channel is one option, not
  decided). `docs/HUMAN-TASKS.md` H3 and H16 updated to state the repo is
  private by decision. **Not touched:** `IMPLEMENTATIONv2.md` §3 (spec text —
  changing it is the owner's call, not the builder's); internal (non-public-
  facing) docstrings in `ingest/verify_recompute.py`, `models.py`,
  `legislation.py`, `ms_metrics.py` that also say "the public repo" — lower
  priority since nothing rendered publicly reads them, left for a future
  pass. `data/` untouched; zero data/behavior change; `uv run checks` +
  `uv run pytest` + `npm run build` all green after the edit.

## V2-1 implementation session (2026-08-13) — federal data expansion

- **D60 (2026-08-13) — federal coverage = every voting-state member of both
  chambers, from current + historical rosters, date-windowed.** V2-1 replaces
  the 6-member Mississippi delegation with all serving House + Senate members,
  118th-119th. Two things this required, both mechanical (not owner-evaluative):
  (a) `legislators.py` now fetches AND merges `legislators-current.yaml` +
  `legislators-historical.yaml` — current-only omits anyone who left office
  between the 118th and 119th, and since `data/members/` is the source every
  coverage check reads, such a member would be invisible to the checks too
  (expected and got would both silently exclude them, so a real gap reads
  green). 88 departed-118th members recovered. (b) New `ingest/coverage.py` is
  the single shared "who held this seat on this date" computation, imported by
  `house_votes`/`senate_votes` (ingest-time filter + R-2 churn guard) and
  `checks/symmetry`/`verify_recompute` (check-time verification), so the two
  never drift. Coverage is DATE-windowed, not per-congress: the 118th alone saw
  a Speaker resign, a member expelled, two deaths, and a Senate seat change
  hands twice mid-term, and per-congress granularity flags all of them missing
  outside their real service window. Bug found + fixed empirically:
  `member_terms` first filtered on a member's CURRENT chamber, so chamber-
  switchers (a House member who won a Senate seat) were invisible to their
  former chamber entirely — 1,225 of 1,886 House rolls misfired before the fix.
- **D61 (2026-08-13) — the 6 non-voting House delegates ARE included (reverses
  D60's initial exclusion); OWNER-RATIFIED.** D60 first excluded DC/PR/GU/AS/
  VI/MP. Reversed once exclusion was found to break full recomputability: the
  delegates cast REAL recorded votes on 623 of 1,886 House rolls (Committee of
  the Whole — measured), so omitting them made `RollCall.totals` non-
  reproducible from `member_votes` on every such roll. Options put to the owner
  in plain language: (a) include them, marked non-voting where a floor-vote
  metric would otherwise apply; (b) leave them out and accept a permanent
  "official total includes delegates not in this dataset" asterisk on ~1/3 of
  House rolls. **Owner chose (a).** Delegates now join the roster and appear in
  `member_votes` whenever the source lists them; they are structurally excluded
  only from the "expected on every roll" set (`coverage.expected_on`), since the
  Constitution bars them from final-passage rolls — a fact about EXPECTATION,
  not about what is recorded. `expected_on` subtracts three empirically-found,
  cited, non-guessed exceptions from the roster: delegates, the sitting Speaker
  (customarily doesn't vote on routine business — McCarthy + Johnson accounted
  for 700 of 833 raw gap entries), and a 21-day seating-lag tolerance around a
  member's term boundary (from two real special-election members, Rulli +
  Suozzi, whose gaps traced to their first two weeks). The R-2 `UnknownMember`
  churn guard stays on the FULL roster (`covered_on`), so a genuine roster gap
  still fails loudly. `legislators.VOTING_STATES` is repurposed from a roster
  filter into a delegate-DETECTION set. Result: House 1,882/1,886 rolls succeed
  (4 quarantined at 0.2% — a member who died the day before the 118th convened,
  and two rolls dated one day after a member's departure — under the 2%
  ceiling); Senate 1,581/1,581; 0 unexplained gaps either chamber.
- **D62 (2026-08-13) — builder D36 retired; the "not recomputable" caveat
  inverts into full recomputability.** D36 introduced aggregate `party_totals`
  precisely BECAUSE individual non-MS positions weren't collected (so party-
  unity could be computed without storing them). V2-1 persists every member's
  position, so `RollCall.totals` is now EXACTLY reconstructable from
  `member_votes` on every roll — the credibility upgrade of the pivot ("check
  my math" now holds precisely, not as a subset bound). `verify_recompute`
  invariant 2 changed from subset (`<=`) to strict equality; `party_totals` is
  KEPT (it is the chamber's own official per-party tally, still what party-unity
  reads for "the majority side," not a stand-in for missing data). The manifest
  `covered_state` field is REMOVED (federal coverage is no longer state-scoped;
  the MS *state-legislature* layer keeps its own separate `covered_state`,
  unaffected). `party_unity`'s D36-derived docstring line flips here. A roll
  that fails to re-parse under the new model is quarantined AND has any stale
  prior export deleted (found via verify-recompute: the 4 quarantined rolls
  were still publishing pre-V2-1 MS-only data, invisibly wrong under the new
  "every position" contract).
- **D63 (2026-08-13) — `data/absences/` sharded one level by congress; the
  member-vote pagination is NOT restructured (file count is under limit).**
  Full-roster ingest produces ~35,000 absence stubs — too many for one flat
  directory — so `export_absence` writes to `data/absences/{congress}/`
  (`congress_of()`), and every reader (`verify_recompute`, `curation/absences`,
  the site's `data.ts:readNestedDir`) is updated. Separately, V2-1 task 4
  offered "restructure member pages (summary + paginated) OR raise PAGE_SIZE —
  builder's mechanical choice": the built file count is **13,090**, well under
  the 18,000 warn / 20,000 Workers-Free limit, so the mechanical choice is to
  KEEP the current `PAGE_SIZE=200` structure unchanged and add a CI file-count
  gate (`site/scripts/check-file-count.mjs`, wired into `ci.yml` + `nightly.yml`
  per H14) rather than restructure prematurely. `data.ts:getMemberVotes` was
  changed from an O(members × rolls) per-page rescan to a one-pass memoized
  `Map<memberId, rows>` index — a pure performance fix (identical output), since
  the old scan dominated the now-much-larger build. **Open (P4/SD-29):** the
  `build.db` SQLite intermediate is NOT built. The flat-file architecture holds
  at full federal scale (measured: ~30s ingest re-parse, ~80s site build,
  verify-recompute green), and the underlying deferred decision (archived
  `inc-12-plan.md`) framed adoption as trigger-based, not date-based. This
  tension between SD-29 ("build at V2-1") and the measured "flat files are
  fine" is flagged for the owner rather than resolved unilaterally — do not
  treat build.db as done.
- **D64 (2026-08-13) — legislation truncation guard moved from a result-level
  heuristic to a fetch-level check + a zero-regression check (value #1).** The
  full-roster legislation backfill (637/637) failed its exit gate on **10
  members** flagged "no sponsored bill in congress {c} (truncated fetch?)" by
  the pre-D64 `_sponsored_gaps` heuristic. All 10 were verified GENUINE zeros,
  not truncations — the heuristic's premise ("a served-congress zero can only
  be a broken fetch") is false. The roster and cause of each:
  - **Served only days of the flagged congress** (a term technically overlaps,
    but no one authors a bill in a week): `S001197` Sasse (5 days of the 118th,
    resigned 2023-01-08), `V000137` Vance (6 days of the 119th → Vice
    President), `R000595` Rubio (17 days of the 119th → Secretary of State),
    `W000823` Waltz (17 days of the 119th → National Security Advisor).
  - **Late special-election seatings** (seated near/after the congress's active
    legislating): `L000605` Lee Carter & `W000829` Wied (~8 weeks at the end of
    the 118th), `R000619` Rulli (~7 months of the 118th), `M001246` Mejia
    (seated 2026-04-20, ~4 months into the 119th).
  - **Full-term but genuinely low output** — verified against the LIVE API by a
    forced (cache-busting) re-fetch: `P000197` Pelosi and `H000874` Hoyer each
    sponsored exactly **2** bills in the whole 118–119 window, both in the
    118th, zero in the 119th (former leadership sponsor almost nothing). This is
    the case no mechanical served-days rule can catch, and it is precisely why
    the guard must not infer truncation from a zero.
  **Fix.** The real Value-#1 risk (a broken fetch publishing a false zero) is
  now caught at its source. (1) `congress_gov.member_legislation` raises
  `TruncatedFetchError` on an *empty* page returned while `offset < count`
  (the paginator breaks on `offset >= count` before it can page past the end,
  so an empty page mid-stream is never legitimate; `count` is read once from
  page 0). (2) `legislation._count_regressions` fails the run if any congress
  that had records in the previously-committed export now parses to zero — bills
  do not un-sponsor, so a drop-to-zero on a refetch is a corrupt-but-non-empty
  page the fetch guard can't see. Together they catch a strict superset of what
  the old heuristic caught (total-zero truncation) plus the corrupt-page case,
  while eliminating the 10 false positives; a genuine served-congress zero (zero
  before AND after) is a true fact and never fails. Residual blind spot (tripwire
  not proof, §CS): a corrupt `count: 0`/no-pagination response at offset 0 on a
  *first-ever* ingest has no baseline and no count to check — documented in both
  functions' docstrings. Ingest re-run after the fix: exit 0, 637/637, no FAIL.
  Metrics are unaffected (the `sponsored`/`cosponsored` metrics count the whole
  118–119 record, so e.g. Rubio's tile reads 270, never a per-congress 0).
- **D65 (2026-08-13) — V2-1 repo-size observation (spec V2-1 task 9): `.git`
  growth is healthy; no LFS/split, no owner escalation.** Measured at V2-1
  completion, this machine: the committed dataset in the working tree is
  ~324 MB (`data/legislation` 134 MB — the V2-1 addition, `data/votes` 108 MB,
  `data/absences` 49 MB, `data/state` 26 MB, `bills` 4.8 MB, `members` 2.3 MB).
  JSON compresses well in git: staging the 631 new legislation files +
  regenerated `metrics.json`/`manifest.json` grew `.git` **27 MB → 48 MB**, i.e.
  the ~134 MB legislation add is ~21 MB packed (≈6.4:1). The raw API cache
  (`data/raw`, 699 MB) stays gitignored and never enters history. The spec's
  escalation trigger is `.git` growth "> a few hundred MB"; at 48 MB total we are
  an order of magnitude under it, so the flat-file-in-repo contract (SD-29's
  "inspectable JSON is the product's credibility") holds unchanged — no Git LFS,
  no repo split, nothing to bring to the owner on size. Nightly diffs stay small
  (incremental ingest + the quiet-night diff-gate touch few files). Re-measure at
  each state added under V2-10; revisit only if a single commit or the pack
  crosses the few-hundred-MB line.

---

## V2-1 acceptance (2026-08-13) — MET

`uv run checks` (6/6) · `uv run verify-recompute` (exact reproduction +
reciprocity on 3,463 rolls — the D62 "check my math" invariant at full scale) ·
`uv run pytest` (all green once the regenerated `metrics.json` is committed — the
git-history test `test_metrics_history_reproduces_head` reproduces HEAD only after
the commit, by construction) · `uv run export` · `uv run ruff check ingest tests`
· `npm run build` (13,082 pages) · `npm run test:file-count` (13,086 files, 6,914
under the 20,000 Workers-Free limit, H14) · `npm run test:links` (7,104 pages cite
`source_url`). Scale: 637 members, 966,261 member-vote rows, 3,463 roll calls.

---

## V2-2 — ranking & percentile layer (2026-08-13)

- **D66 (2026-08-13) — non-voting delegates are ranked ONLY on the bill metrics;
  OWNER-RATIFIED.** V2-2 introduces comparative rankings. The non-voting House
  delegates (DC, PR, GU, VI, AS, MP — 8 delegate records across the 118th-119th,
  a couple of seats changing hands mid-period) are barred from voting on final
  passage, so their attendance and party-unity figures are measured over
  a much smaller, different set of rolls (85–623 vs a full member's ~1,862) and are
  not comparable — but they sponsor and cosponsor bills fully (Delegate Norton of
  DC ranks #2 in the House for bills sponsored). Put to the owner in plain language
  (§0.1 — this is the exact delegate question §0.1/§7 V2-1 flags as must-ask, not
  builder-resolvable), with three options (bill-metrics-only / out-of-all /
  in-everything). **Owner chose bill-metrics-only.** Implemented in
  `rankings.VOTE_METRICS = {attendance, party_unity}`: delegates are excluded from
  those two rankings and listed per-chamber in `excluded_delegates`; they are
  ranked on sponsored/cosponsored/enacted_rate. The exclusion is never silent —
  `/methods` states it and the reason (§6.5). Parallels D61 (delegate coverage
  handling, owner-ratified); delegates keep full record pages and stat tiles
  regardless — this affects only the comparison lists.
- **D67 (2026-08-13) — rankings design (mechanical, non-evaluative).** `ingest/
  rankings.py` → `data/rankings/{metric}.json` (one per ranked metric), a new
  `ingest rankings` step (pipeline: after `ingest metrics`, before the diff-gate —
  same D40 "derived artifact reaches the gate" rule; wired into `nightly.yml`).
  Choices, each a builder call under §0.1(d), no threshold or label (that is V2-4
  under §0.8):
  - **Rankable set:** the 5 SCALAR Tier-2 metrics — attendance/party_unity/
    enacted_rate (`pct`) and sponsored/cosponsored (`count`). The other three
    (cosponsor_vote_gap, named_measure_mismatch, absence_context) are lists of
    records, not a single comparable number, and are not ranked.
  - **Grouping:** within chamber (House/Senate separate — different calendars and
    vote counts). Chamber + party come from the member's CURRENT record; a
    chamber-switcher ranks in the chamber they now sit in. Metrics use per-roll
    party; rankings group by current party — stated on `/methods`.
  - **Ties:** standard competition ranking (§5 pre-decided) — tied members share a
    rank, the next rank skips.
  - **Percentile:** the % of the chamber's ranked set with a STRICTLY LOWER value
    (so the count behind each percentile is visible, §0.4.2(d)); defined in the
    rendered methods text.
  - **Null values** (attendance pct before a first vote; enacted_rate when nothing
    was sponsored): the member is not ranked on that metric — never at a fabricated 0.
  - **`value` type:** int for counts, float for percentages (`int | float`, smart
    union preserves the source type so a count never renders "45.0").
  - **Recompute contract:** rankings read ONLY committed `data/metrics.json` +
    `data/members`, so a third party re-derives them; `verify-recompute` invariant
    5 re-runs `build_all()` and byte-compares every committed file (a ranking that
    cannot be recomputed may not ship — §7 V2-2 "on failure").
  - **Doctrine (§6.7):** rank/percentile/mean of published facts is a factual
    position, not a score/label; `methods.astro:26` ("nothing is summarized,
    characterized, or scored") is KEPT per §6.7 (it flips at V2-4 with grades), and
    the ranking copy uses no best/worst/grade wording. Party means (R-vs-D and
    R-vs-R — every party under the same standard, §0.4.2(c)) are rendered on
    `/methods`. `check-metrics-sections.mjs` extended: `data-ranking` sections set
    == ranked-metric set (a ranking can't ship without its disclosed methodology).
- **D68 (2026-08-13) — §8 coverage gate: 100% branch on `ingest/metrics.py` +
  `ingest/rankings.py`, enforced in CI; `classify.py` deferred to V2-4.** §8
  requires 100% branch coverage on the small, pure, credibility-bearing modules,
  and forbids silently lowering it. Implemented as a dedicated CI invocation
  (`uv run pytest --cov=ingest.metrics --cov=ingest.rankings --cov-branch
  --cov-fail-under=100 --cov-report=term-missing`) — NOT in pytest `addopts`, so a
  plain/subset `uv run pytest` stays usable; the exact gate command is recorded in
  `docs/PROGRESS.md`. Both modules were driven to 100% with real tests (rankings'
  `run()` + loader; metrics' `_load` missing-legislation guard, `_party_on`
  off-term fallback, `named_measure_mismatch` other-member skip, the full `history()`
  git-series edge branches via a tmp git repo — with `git config user.name/email`
  set in the fixture since CI runners have no global identity — and the `run()`
  history-CLI + export paths). **Two scope decisions, both spec-faithful, not
  silent-lowering:**
  - `classify.py` is in §8's eventual list but NOT §7 V2-2's task line ("coverage
    tooling lands for `metrics.py`/`rankings.py`"). Its gap is the bulk — the entire
    live-fetch, file-rewriting `run()` orchestration (~75 lines); its pure,
    credibility-bearing `classify()` is already covered. It joins the gate at V2-4,
    when `scoring.py` lands and §6.8 rewrites `checks/integrity.py` — the natural
    moment to add the I/O-path tests. Listed here, not silently skipped.
  - The one coverage exclusion is `if __name__ == "__main__":` (the module runner,
    never executed under pytest) via `[tool.coverage.report] exclude_lines` — the
    "listed, not silent" form §8 allows. No metric/ranking function body was edited
    to reach a branch (that would churn `_formula_digest` → metrics.json); every
    branch is reached by a test as the code stands.

---

## V2-3 — member-page rank context (2026-08-13)

- **D69 (2026-08-13) — member-page rank rendering (mechanical, non-evaluative).**
  V2-3 puts each member's V2-2 rank onto their own page's five stat tiles
  (`MemberStats.astro`, fed a `ranks` prop the federal member template builds via
  `getMemberRanks`). Choices, all builder-level (no threshold, no label — grades
  are V2-4):
  - **Tile rank line renders `"{ordinal(rank)} of {covered} in the {House/Senate}"`**
    (e.g. "12th of 100 in the Senate") — the spec's own `§6.7` example shape
    ("42nd of 100 senators"), linking to `/methods#ranking-{metric}`. The
    **percentile is deliberately NOT shown on the tile**: ordinalizing a rounded
    percentile would (a) print "0th percentile" on the worst-ranked members' pages —
    the most-scrutinized pages — and (b) round a published number at render time,
    against §0.4.2(d)'s inputs-visible rule. The exact percentile stays in
    `data/rankings/*.json` and is defined on `/methods`.
  - **A member is shown a rank only where they are actually ranked.** A null metric
    value (e.g. no enacted rate when nothing was sponsored) → no rank line on that
    tile. A **non-voting delegate** (D66) → no rank line on attendance/party-unity,
    PLUS an explanatory caption clause on their page ("As a non-voting delegate, they
    are not ranked on attendance or party unity … they are ranked on the bill
    measures") so the missing ranks are explained WHERE the reader sees them, not only
    on `/methods` (§6.5 symmetry, made visible). Delegate detection uses the ranking's
    own `excluded_delegates` list — the authoritative D66 signal — never a guess from
    which tiles lack a rank (which a newly-seated null-value member would trip).
  - **MS members get no rank context** — there are no MS rankings until V2-10; the MS
    template passes no `ranks`, so the tiles render exactly as before.
  - **Doctrine (§6.7):** the "combines nothing into an overall score and draws no
    conclusion" caption is KEPT — a rank is a factual position on one metric, not a
    composite/score; it flips at V2-4 with grades. The intro line gains "and its rank
    within the chamber" (federal only) — true today.
  - **Tests:** the e2e page list (`e2e/fixtures.ts`) gains a delegate page, derived
    from `excluded_delegates` so it never rots — covering the mixed ranked/unranked
    tile path + the delegate caption at a11y and 380px.

---

## V2-4 — grades (first evaluative increment, 2026-08-13)

- **D70 (2026-08-13) — attendance letter grade; OWNER-RATIFIED via propose→ratify
  →commit (§0.8/SD-27, H15 round one).** The first evaluative output (SD-26). The
  owner was brought two rounds of options in plain English WITH the data
  distributions; every ratified value below is the owner's pick, committed in
  `data/config/thresholds.yaml` with its reasoning + date. The paper trail:
  - **Scope:** grade ONE category, attendance, for now. The owner explicitly
    deferred the OVERALL composite grade ("that will be a formula I will have to
    work on") — so V2-4 publishes an attendance grade and NO overall grade; the
    composite lands when its formula + category weights are ratified (§0.8 — no
    unratified formula publishes).
  - **Which measures:** owner chose attendance only. The other four were declined
    with the data reasons shown to them (party-unity has no neutral direction —
    grading it is a political stance; sponsored/cosponsored are volume not quality;
    enacted-rate is median-zero and understates — grading "0% = poor" is a false
    frame). Attendance is the clean one (higher plainly better, a real low tail).
  - **Style:** letter grades A–F. **Cutoffs (fixed bars, "spread across the real
    range"):** A ≥99% · B ≥97% · C ≥95% · D ≥90% · F <90%. **Labels:** A "Strong",
    B "Good", C "Fair", D "Weak", F "Poor" attendance. Fixed bars (not a curve) so
    a member's grade never moves because of others (fits "check my math"); one bar
    set applies to both chambers (an attendance % means the same in each).
  - **Minimum service:** owner chose < 50 eligible roll calls → set aside, shown
    "Too few votes to grade" (sets aside 1 member today). Non-voting delegates are
    also not graded (inherited D66 — eligible set not comparable). §6.5
    grading-coverage: every covered member is graded OR in the published
    `exceptions` map (delegate / min_service / no_record) — 627 graded + 10
    excepted = all 637, silent drop = fail.
  - **Design:** `ingest/scoring.py` (the sole Tier-3 composer; composes nothing yet
    — one metric per grade) → `data/grades/attendance.json`, from ratified
    thresholds only. **No wall-clock** in grade records (§6.3 beats §5's "computed-at
    date" wording — code is authoritative when the spec disagrees; provenance is
    `formula_version` + `ratified`). `verify-recompute` invariant 6 (grades re-derive
    byte-for-byte). **§6.8 guard rewritten prohibition→disclosure** (`checks/
    integrity.py`): Tier-2 metrics still may not compose (metrics.py AST check kept);
    published grades must carry EXACTLY the config's bands/labels/exception_label/
    min_eligible/formula_version/ratified (`grades_disclosure`); the render-side half
    is `site/scripts/check-grade-labels.mjs` (every `data-grade-label` on the built
    site ⊆ config labels). Both are tripwires-plus-review (§CS blind spots carry).
    §8 coverage gate gains `scoring.py` (100%) **and `classify.py`** (100%, the D68
    commitment — its live-fetch `run()` now has tmp-repo/mock tests).
  - **§6.7 doctrine flips (partial, because only attendance is graded):**
    `index.astro` and `methods.astro` intros flip (site now grades/characterizes);
    `MemberStats` caption SPLITS — "combines nothing into an overall score" STAYS
    (no composite), "draws no conclusion" flips (federal); MS keeps "draws no
    conclusion" (state figures aren't graded); `ms/index.astro` reworded to scope
    the no-grades claim to the states; `metrics.py` — the module + two list-metric
    docstrings' SITE-level "draws no conclusion" scoped (metrics.py still doesn't
    score; "here" stays true), the per-metric "not a score" claims kept; rankings/
    adjacency "not a score" kept (SD-20). The docstring edits churn `_formula_digest`
    for two metrics → `metrics.json` regenerated (values byte-unchanged → rankings +
    grades byte-identical); **no `FORMULA_SCHEMA_VERSION` bump** — a docstring edit is
    not a change to how a number is computed.
- **D71 (2026-08-13) — two live Value-#1 falsehoods fixed in the V2-4 doctrine
  pass.** Both pre-existed V2-4 and were caught while editing the same files:
  (1) the **home page** was titled "Mississippi delegation" and its intro said "for
  Mississippi's members of Congress," but since V2-1 it lists all **637** federal
  members (Butler of CA included) — a false frame shipped live through V2-1/2/3.
  Retitled "Members of Congress"; intro rewritten to the U.S. House and Senate.
  (2) `methods.astro` still claimed "The full data pipeline and this site's source
  code are public" — false since D59 (the repo is private); the V2-0 truth sweep
  fixed `/privacy` + `/corrections` but missed this line. Removed the public-source
  claim (kept "every figure traces to an official source"). Both are Value #1 (never
  publish something false/falsely framed), which outranks everything — fixed on
  sight, not deferred to V2-5's dashboard rebuild.

- **D72 (2026-08-13) — V2-5 information architecture: landing dashboard + Federal/
  States tabs (PARTIAL; the evaluative headline is deferred).** The site's front door
  was a flat wall of ~540 member names under a two-item nav (Members | Methodology).
  Built under the owner's standing authorization to restructure the layout and push
  without a per-change ask ("Push it all… re-structure the site's layout… do not ask
  me to push or not"). Changes:
  - **Nav → four tabs** (Home · Federal · States · Methodology), active-aware; the
    brand still links home. Detail pages light their section (member/vote/bill →
    Federal; `/ms/*` → States).
  - **`/` is now an overview dashboard**, not a member list: a plain-count coverage
    line (637 members, 3,463 roll calls, 966,261 recorded votes — facts, not
    evaluative), two entry cards (Federal, States), and a NEUTRAL attendance-grade
    distribution — the already-ratified grades tallied A→F in band order, each band
    linking into the federal list filtered to it. No single band is promoted to a
    headline number.
  - **`/federal`** is the browsable all-members list: a **Preact island**
    (`MemberBrowser.tsx`, the repo's first) mounted `client:visible`, so the full
    637-row list is server-rendered into static HTML (usable with JS off, crawlable,
    deterministic) and hydration only adds filter/search/sort. It reads
    `?grade`/`?chamber`/`?party`/`?sort`/`?q` on mount so a dashboard tile deep-links
    straight to the filtered view (V2-5's click-through rule). Delegates are shown but
    "Not graded" on attendance (D66), never scored.
  - **`/states`** is a thin tab: one Mississippi card → existing `/ms` (MS URLs
    unchanged), plus a "more states over time" note.
  - **Stale nav wording fixed (D71 family):** federal breadcrumbs "Members → /" became
    "Federal → /federal"; the `/ms` breadcrumb "U.S. delegation" became "States"; 404
    updated. The footer **"Source" link to the private repo was removed** — same
    false-availability class as D71 (a public visitor hits a login wall); it returns
    if/when the repo goes public.
  - **§0.8 held while the owner is away:** the V2-5 "lowest N% wide-eyed" headline is a
    NEW ratified threshold (H15 round two) and was NOT made here. The grade
    distribution is only a tally of already-ratified outputs (no new evaluative
    constant). `check-grade-labels.mjs` was extended to scan the dashboard + federal
    island, and its extractor regex broadened to also match Preact's
    `data-grade-label=""` serialization; the text checked against the ratified set is
    unchanged. **V2-5 therefore stays OPEN** pending the owner sitting.
  Preact was already pinned (astro.config + package.json since setup); no new
  dependency. Visual/design polish is a separate later pass (owner's "Claude design").

- **D73 (2026-08-13) — /federal mobile-performance fix + correction to D72's
  "green" claim.** D72, that increment's PROGRESS "Green" line, and the V2-5 commit
  messages (`aa3b6fdf`, `d910562e`) all stated Lighthouse passed. That was true
  locally but NOT on CI: run `31769853844` failed the Lighthouse gate — `/federal`
  scored **0.8 mobile performance** (gate ≥ 0.9; a11y passed). The local machine is
  faster than the CI runner, so a local pass was not a safe proxy — a calibration
  error on my part. **Diagnosis:** the first `/federal` build rendered the full
  637-row roster *inside* the Preact island, which (a) hydrated 637 rows on load and
  (b) serialized the roster a second time as JSON island props — high Total Blocking
  Time + LCP under throttled-mobile emulation. **Fix:** the roster is now static Astro
  HTML on the page (the same shape as the old ~540-row homepage, which has always
  cleared CI Lighthouse); the island is **controls-only** and enhances that list in
  place — filtering by each row's inline `display` (an inline style, chosen over the
  `hidden` attribute because the rows' Tailwind `flex` class would beat a UA
  `[hidden]{display:none}` in the cascade and silently leave "hidden" rows visible),
  sorting by reordering rows, both from `data-*` attributes. The island props blob
  drops from the whole roster to `{listId,total}`. The drill-down e2e now asserts
  computed visibility (`toBeHidden`), not the attribute, so a cascade regression fails
  loud. Note the honesty point: the CI failure did not roll anything back — the
  Cloudflare deploy is push-triggered and independent of CI, so the slower `/federal`
  was briefly live between `aa3b6fdf` and this fix.

- **D74 (2026-08-14) — Nocturne design pass: colour-as-meaning reversal + design
  tokens + self-hosted Inter.** The owner's separate "Claude design" step (parked in
  `IMPLEMENTATIONv2.md` Appendix B as a want, and in `docs/PROGRESS.md` as the pass
  after V2-5) arrived as a handoff bundle, `claudedesign/` (README + two `.dc.html`
  prototypes + a flattened data sample). It specifies the **Nocturne** dark theme,
  build-time charts, a multi-metric members explorer, and a `/compare` view. This ADR
  records the load-bearing decisions of implementing it; the mechanical work is design,
  not evaluative.
  1. **Colour-as-meaning reversed.** `Badge.astro` and `MemberStats.astro` carried
     comments asserting a blanket *no colour-as-meaning* rule. The owner's redesign
     deliberately colour-codes **attendance grade bands, party, and vote positions**.
     The reversal is presentational — colour is added *around* the owner-ratified grade
     label (the exact string still renders inside `<span data-grade-label>`, so the
     §6.8 grade-labels guard is untouched), around a party letter, around a vote
     position — it authors **no new evaluative number**. The graded values and their
     labels were already ratified at V2-4 (`thresholds.yaml`). The **vote-class** badge
     (`Badge.astro`) stays visually neutral on purpose: a procedural category is neither
     evaluative nor partisan, so it takes no colour. Value #2's disclosure standard is
     unaffected — every graded figure still links to its formula and shows its
     denominator.
  2. **Token authority.** The bundle references `_ds/nocturne-*/styles.css`, which it
     does **not** ship (five files only). The design README's token table and the
     prototype inline styles are therefore the authoritative token source. Tokens live
     in `site/src/styles/global.css` as a Tailwind v4 `@theme` block (ground/surface,
     accent, grade bands, party, vote positions, hairlines). Legacy pages not yet
     redesigned are carried to dark by remapping Tailwind's `neutral` ramp inside the
     same `@theme` (light-theme utilities → dark values, kept ≥ WCAG-AA on ground and
     surface; verified by the axe e2e suite) — a mechanical choice that avoids editing
     241 utility occurrences across 22 files in one commit; each page converts to the
     named tokens as it is redesigned.
  3. **Inter self-hosted (§10.1).** The prototypes load Inter from Google Fonts; that
     must not ship. Vendored `site/public/fonts/inter-latin.woff2` (48 KB) +
     `inter-latin-ext.woff2` (85 KB, fetched only when a glyph in its `unicode-range`
     appears) — Google's css2 now serves one variable woff2 per subset covering the
     400–500 range Nocturne uses — with `OFL.txt` (SIL Open Font License 1.1) alongside.
     `@font-face` is declared locally with `font-display: swap`; the latin file is
     preloaded. The few symbol glyphs outside the subset (arrows, check/cross) fall back
     to the system UI sans.
  This pass is **design only within the still-OPEN V2-5**: it introduces no new
  evaluative constant, so it needs no H15 ratification, and it does **not** close V2-5 —
  the "lowest N%" wide-eyed headline (H15 round two) remains owner-gated. Commits carry
  the `V2-5:` convention.

- **D75 (2026-08-14) — attendance percentile now renders on the member profile
  (reverses D69's tile choice).** The Nocturne member profile (D74) shows the attendance
  percentile in two places: the grade card's rank line ("… higher than {p}% of them")
  and a "Attendance percentile" fact tile. **D69 deliberately kept percentile OFF the
  member-page tile** for two reasons: a worst-ranked member's page would read "0th
  percentile," and rendering risked rounding a published number at display time. This
  ADR reverses that, because the owner's design handoff (`claudedesign/`) calls for the
  percentile on the profile, and the reversal is safe on both of D69's counts:
  (a) the value rendered is the **published** V2-2 percentile read verbatim from
  `data/rankings/attendance.json` via `getMemberRanks()` — it is NOT recomputed or
  re-rounded at render; (b) the rank line uses the **per-chamber** covered N
  (`getMemberRanks().covered`, delegates excluded per D66), never the cross-chamber 627,
  so a per-chamber rank is never printed against a whole-population denominator (that
  would be a Value-#1 false frame). A 0th-percentile member honestly reads "higher than
  0% of them" — factual, and the design's intent. Non-ranked members (delegates) show
  "not ranked", never a fabricated percentile. Presentational only (no new evaluative
  constant; §0.8 untouched). Recorded so a later session does not "fix" it back to D69.

- **D76 (2026-08-15) — Nocturne members explorer (README screen 2): a multi-metric
  table under a measured DOM budget.** `/federal` becomes a sortable/filterable metric
  table (attendance, party unity, yea share, sponsored, cosponsored, became-law), one
  row per member. Rows are STATIC Astro HTML (D73 holds — the roster is never rendered
  or serialised inside the island); `MemberBrowser.tsx` is a controls-only island that
  filters by row `display`, sorts by reordering rows, and hides columns by `data-col`,
  all from each row's `data-*`. Column definitions are read from `ingest/metrics.py`
  docstrings via `getExplorerColumns()` (`lib/columns.ts`) — the sentence beside a number
  is the one the function that computes it carries; never retyped (a README acceptance
  criterion). Load-bearing decisions:
  1. **Six columns, not ten — a MEASURED DOM-budget carve-out.** The cost driver on
     mobile is *node count* (Style & Layout), not bytes: a throwaway spike of the full
     ten-column table measured **23,662 DOM nodes / perf 93** locally (gzip made transfer
     a non-issue at 159 KB). Node count — not markup verbosity — sets first paint, and
     the CI runner is slower than local (the D73 lesson). So the table renders the
     README's **six default columns**; the four the prototype could toggle in (nay share,
     laws enacted, cosponsored→law, attendance percentile) are dropped from the table and
     already live on each member's **profile** page. This relaxes the prototype's
     "one chip per available metric / all columns in the DOM" — that was the previous
     session's reading, not an owner ratification, and it is the right lever to give.
     The carve-out is **presentational/performance, authors no evaluative number**, so it
     needs no H15. Lean cells hold the budget: the value bar is a `::before`
     pseudo-element (**0 DOM nodes**), and the per-cell value `<span>` was dropped
     (−3,822 nodes). Final `/federal`: **10,964 nodes, perf 98, a11y 100, CLS 0.000,
     TBT 0**; the full CI Lighthouse config (9 URLs) passes, every other page 100.
  2. **The fraction denominator stays a real `<i>` element, not a `::after`.** Moving it
     to `content: attr()` would have saved ~2,548 nodes and reached perf ~100, but the
     site's premise is *the denominator is always visible* — pseudo-content is not
     selectable, not copyable, and outside the a11y tree. Keeping it a real element (SR-
     readable, copyable) at perf 98 was chosen over a leaner-but-hollow denominator. This
     is safe for CI: unlike D73 (which failed on Total-Blocking-Time from hydrating 637
     rows), this page has **TBT 0 and CLS 0** — only FCP/LCP degrade under CI throttling,
     roughly linearly, and the layout-heavier DotStrip member page already clears CI.
  3. **Default sort is `name`, not the README's attendance-descending.** The static
     table and the island's default sort must match, or hydration reorders 637 rows and
     spikes CLS on the one Lighthouse-tested page. Name order also keeps the neutral,
     crawlable default (no evaluative ordering promoted by default, §0.8) and needs zero
     reorder. Attendance-descending is one header-click away; a deep-link (`?sort=…`)
     reorders on its own page, which is not Lighthouse-gated.
  4. **`.sub` median line: 38% opacity → `neutral-500` (a11y over fidelity).** The
     prototype's "median {value}" at 38% opacity renders `#6e6f79` on the surface —
     **3.0:1 at 10px, a WCAG-AA color-contrast failure** the axe e2e caught. Raised to
     the ramp's AA-on-every-surface shade. Grade colour stays honest too: the grade
     letter is neutral full-contrast `--color-text` with the band colour carried by the
     attendance bar + a low-alpha cell tint (a colourblind-safe reading that also passes
     contrast), never a low-contrast coloured letter.
  5. **`content-visibility: auto` on the `<tr>` rows was a no-op — and the reason given
     here was wrong (corrected by D78).** This ADR originally blamed `table-layout: auto`
     and proposed a `table-layout: fixed` fix. That is incorrect: layout containment can
     **never** apply to `<tr>`/row-group boxes (they can't establish containment),
     regardless of `table-layout`, so no table variant would have helped. And the "98
     passes" claim below was **local-only** — this build scored perf **0.77 on CI**
     (run `31895378122`), the D73 pattern repeating. Both are fixed in **D78**: `/federal`
     was rebuilt as a `role="table"` grid of `<div>`s (block rows CAN be contained), where
     `content-visibility` genuinely skips the off-screen rows.
  6. **e2e migrated, invariants kept.** `drilldown.spec.ts` moves `li`→`tr` and
     select-value assertions → chip active-state (`[data-chip="grade"][data-value="A"]`
     `aria-pressed`) + active header (`[data-sort="grade"][data-active]`); it keeps the
     dashboard href `/federal?grade=A&sort=grade` and its query semantics, `#member-list`
     as the row container, per-row `data-grade`, `a[href^="/m/"]`, and **computed
     visibility** (`toBeHidden`) so a cascade regression still fails loud. A header-click
     sort test was added (deep-link was the only sort coverage). Grade labels still render
     verbatim inside `<span data-grade-label>` (the §6.8 guard scans all 637 rows).
  **Deferred to the `/compare` checkpoint:** the explorer's "set aside" (exclude) and
  "compare selected" per-row controls — they pair with the `/compare` page and are best
  injected on hydration (keeping the static DOM lean). Design-only within the still-OPEN
  V2-5: no new evaluative constant, §0.8 untouched, H15-round-two headline still gated.

- **D77 (2026-08-15) — `/compare` (README screen 4): the site's one client-rendered view,
  a deliberate carve-out from "works with JS off".** The member set lives in the query
  string (`?m=A&m=B`, 2–4 members). A static build cannot know it, and pre-building every
  member combination is impossible, so the comparison is rendered **client-side** by the
  `Compare` island from a data blob embedded in the page. `compare.astro` server-renders
  the shell (heading, lede, the 637-option picker `<select>`, a `<noscript>` that points
  to `/federal`) + a compact blob (every member's identity, verbatim grade, per-chamber
  attendance rank, and the six columns' precomputed `{display, fraction, fill}` — reusing
  `getExplorerColumns`). This is the FIRST page where the general acceptance "everything
  present with JS disabled" cannot literally hold; JS-off users get the picker + the
  noscript pointer, not the comparison. Load-bearing decisions:
  1. **Cross-chamber attendance is disclosed, never silently juxtaposed (Value #1).** The
     site's own doctrine (D66) says House vs Senate attendance is not comparable — that is
     why ranks are per-chamber. `/compare`'s shared 50–100 attendance axis could place
     members of different chambers on one scale, so when the selected set spans chambers
     the axis caption states each figure is measured against that member's own chamber and
     that the site does not rank attendance across chambers. Rank lines already use the
     per-chamber `covered` N. **Delegates** (non-voting) render a grade-null card with the
     same non-comparability language the profile uses and plot no marker on the axis — an
     empty grade is never shown as if it were a low one.
  2. **Every evaluative constant comes from data, and §6.8 holds here BY CONSTRUCTION.**
     The shared-axis tick marks the C grade at the C band's `min` **read from
     `data/grades/attendance.json`**, never a literal `95` that would go stale on a
     re-ratification. Grade band labels pass through the blob **verbatim** from
     `getMemberGrade()`. Critical note for future sessions: `check-grade-labels.mjs` scans
     built *HTML* and therefore **cannot see client-rendered labels** — on `/compare` the
     §6.8 guarantee is upheld not by the scanner but by construction: the island prints
     only strings the blob carried and contains **no grade-label literal**. Any future
     evaluative string on this page must likewise come from committed data, not the island.
  3. **No colour literals in the blob or the island's data.** Bar/grade colours are derived
     client-side from `(columnKey, gradeLetter)` via a ~10-entry map, so the blob carries
     no `var(--color-…)` strings (≈3,800 avoided) and the island invents no colour meaning
     beyond the ratified grade letter it was given.
  4. **Bars scale within each metric's own stated domain** (the `fill` is precomputed to
     that domain in `getExplorerColumns`), with the domain printed under each row label, so
     a count column can never masquerade as a percentage — the same honesty rule as the
     explorer. The `</script>`-in-JSON hazard is closed by replacing every `<` in the
     embedded blob with its JSON unicode escape.
  **Verification:** bare `/compare` joins the e2e `PAGES` sweep (axe a11y + 380px on the
  picker/prompt); a dedicated `compare.spec.ts` drives `?m=<house>&m=<senate>`, waits for
  the client render, asserts both cards + both chart sections + the cross-chamber
  disclosure, runs **axe on the fully rendered comparison** (the only a11y coverage the
  island markup gets), and checks that removing a member updates the cards + the `?m=` URL.
  `/compare` is deliberately NOT added to `lighthouserc.cjs`: a fully client-rendered page
  measures the island's render, not a static document, so gating its mobile perf would be
  noise; it is kept lean (blob is data, not DOM; only the 2–4 selected members render).
  The profile's "Compare with someone" link (`/compare?m={id}`) is now live (was a dead
  link since D74). Design-only within the still-OPEN V2-5: no new evaluative constant,
  §0.8 untouched, H15-round-two headline still gated. **Still deferred:** wiring the
  explorer's multi-select "compare selected (n)" → `/compare?m=…&m=…` (the picker + the
  profile link reach `/compare` today; the explorer bulk-select is a later polish).

- **D78 (2026-08-15) — the explorer failed CI Lighthouse at 0.77; fixed by making the
  rows block-level so `content-visibility` actually works (the D73 pattern, again).**
  D76's `/federal` scored perf **0.98 locally but 0.77 on CI** (run `31895378122`; gate
  ≥ 0.9), with build/checks/e2e all green — the slower CI runner, exactly the calibration
  trap D73 warned about ([[civic-ledger-ci-lighthouse-proxy]]), and my D76 §5 "full CI
  Lighthouse green" line was a **local-only overclaim** (corrected in D76 + PROGRESS). The
  Cloudflare deploy is push-triggered and independent of CI, so the slow page was briefly
  live. **Root cause:** the `content-visibility: auto` I'd added to the `<tr>` rows was a
  **no-op** — CSS layout containment cannot apply to internal table boxes (`<tr>`, row
  groups), so all ~11,000 nodes laid out on every paint; on the throttled CI CPU that
  dominated FCP/LCP. (My local proof: adding/removing it moved Style & Layout by 0ms.)
  **Fix:** `/federal` is rebuilt as an ARIA `role="table"` grid of `<div>`s — block-level
  rows CAN establish containment, so `content-visibility: auto` (with
  `contain-intrinsic-size`) skips layout + paint for the ~620 off-screen rows. Same six
  columns, same lean cells, same `data-*` contract; the island's row selector moves from
  `tr[data-member]` to `[data-member]` and it now sets `aria-sort` on the active
  `columnheader`. **New push gate (the lesson): the local score is saturated and useless
  as a proxy** — instead compare the page's **Style & Layout milliseconds** against a
  known-CI-green anchor page on the same machine. Measured: `/m/A000055/1` (CI-green
  anchor, 2,658 nodes) = **258 ms**; the rebuilt `/federal` (10,973 nodes) = **83 ms**,
  i.e. *below* the anchor — where the real-table build was 663 ms. perf 99 local, CLS
  0.000, a11y 100 (the new ARIA grid re-verified with axe). e2e: the `drilldown` selectors
  moved `tr`→`[data-member]`, and a hydration-race in the header-sort test (it clicked a
  header before `client:idle` wired it) is fixed with a `data-mb-ready` marker the island
  sets once wired. Kept every contract piece verbatim: `#member-list`, `data-grade`,
  `a[href^="/m/"]`, computed-visibility, the `?grade=A&sort=grade` deep-link. Committed +
  pushed **alone** (not stacked under `/compare`), CI watched to green before `/compare`.
  Design-only within OPEN V2-5; no evaluative constant; §0.8 untouched.

- **D79 (2026-08-15) — methodology + Mississippi redesign (README screens 6–7): the last
  Nocturne view.** Design-only. Converts `methods.astro`, `states/index.astro`, and the
  `ms/*` pages from the neutral-ramp fallback to the named Nocturne tokens, and to Nocturne
  weights — `font-semibold` → `font-medium` (the ramp remaps colour but NOT font weight, so
  every heading was still bolder than Nocturne's 400/500 rule). The two "designed" surfaces:
  1. **Methodology.** The Grades section becomes a bands **table** (a dot in the band
     colour + the verbatim ratified label inside `<span data-grade-label>` + the numeric
     range derived from consecutive cutoffs + a population bar + the count) and a **Set
     aside** card naming all 10 exceptions with a human-readable reason (`delegate` →
     "Non-voting delegate", `min_service` → "Too little service", `no_record` → "No eligible
     record"). The band population counts (A 139 … F 40) are the SAME neutral distribution
     the dashboard already publishes via BandLegend — no band promoted, **no new evaluative
     constant, §0.8 held**. The `check-metrics-sections` `data-metric`/`data-ranking`
     sections, the `#grade-attendance` anchor (the member badge's target), the
     `#mississippi` anchor, and the `check-grade-labels` markers are all preserved. The
     bands table sits in an `overflow-x-auto` region that is `tabindex="0"` + labelled — it
     has no focusable children (unlike `/federal`), so axe's `scrollable-region-focusable`
     rule needs the region itself keyboard-reachable (caught by the mobile a11y e2e).
  2. **Mississippi.** `/ms` gains four count tiles (legislators, roll calls, bills voted,
     individual votes) + roll-calls-by-chamber (SplitBar) + roll-calls-by-category bars,
     read straight from the committed manifest counts (`rollcalls_by_chamber` /
     `rollcalls_by_vote_class`), above the navigable roster. **HARD constraint kept
     (README screen 6): Mississippi does NOT show the federal attendance grades** — MS's
     record can't support the same eligible-roll-call denominator; the "grades do not
     extend to the states" paragraph stays verbatim.
  Gates: astro check 0, build 13,085 (page count unchanged — existing pages restyled),
  grade-labels, metrics-sections (10 + 5), e2e 36 (incl. `/methods` + `/ms` axe a11y and
  380px). No new evaluative constant; §0.8 untouched; V2-5 stays OPEN (H15 round two, the
  "lowest N%" headline, still owner-gated). This completes the Nocturne pass's VIEW coverage;
  the only remaining Nocturne items are polish: the explorer's exclude + compare-select
  per-row controls (inject on hydration).
- **D80 (2026-08-15) — the explorer's per-row selection controls (README screen 2, the last
  Nocturne polish item): compare-select + exclude, injected on hydration into statically
  reserved gutters.** Design-only; no evaluative constant, §0.8 untouched. README screen 2
  specs a compare-toggle column (leading, 30px) and an exclude column (trailing, 24px) per
  row, a heading "Compare selected (n)" primary button, and a filter-card "Set aside by you"
  restore row. The tension: `/federal` already carries 637 rich rows at the block-row-grid
  content-visibility budget (D78), so 637 × extra STATIC cells would grow the perf-critical
  initial DOM — the very trap D73/D78 warn against. Resolution, three constraints, each
  chosen to clear a specific CI gate:
  1. **Zero layout shift (CLS is 25% of the mobile-perf score; D78's runner fails at the
     margin).** The two gutters are reserved **statically** in CSS (`.row/.hrow {
     position: relative; padding-left: 30px; padding-right: 24px }`, `min-width` 880 → 960),
     so first paint already has the space. The island injects the controls as
     **absolutely-positioned** `role="cell"` children into those gutters — they never enter
     flex layout, so nothing reflows. Measured **CLS 0.0000** locally (the one Lighthouse
     number that does NOT saturate on this machine, so it's trustworthy — see
     [[civic-ledger-ci-lighthouse-proxy]]).
  2. **Valid ARIA grid.** A bare `<button>` child of `role="row"` fails axe's
     `aria-required-children` (wcag2a → the a11y gate). So each control is injected as
     `<div role="cell"><button></button></div>`, with two matching sr-only `role=
     "columnheader"` divs in the header. A dedicated e2e (`drilldown.spec.ts`) waits for the
     controls to be present (`data-mb-ready`, set AFTER injection) and asserts axe returns
     zero violations — the generic a11y sweep can race the `client:idle` injection.
  3. **Cheap injection.** ONE delegated `click` listener on `#member-list` (not 1,274),
     matching via `closest('button[data-act]')`; the handler reads the member off the clicked
     row's `data-id`/`data-name` and mutates state with **functional** setState updaters, so
     it never closes over a stale selection and survives sort re-appends. The injection loop
     is write-only (no interleaved `offsetWidth`-style reads that would force 637 synchronous
     layouts). State (`excluded: Map<id,name>`, `compare: string[]` capped at 4) is
     session-ephemeral and stays OUT of the URL — only filter/column state is linkable per
     the spec. Excluding folds into the existing filter effect (`display:none` + not counted);
     the heading link appears at ≥2 selections and points at `/compare?m=…&m=…`; excluding a
     selected member drops them from the compare set.
  **Perf verdict (the D78 proxy, not the saturated score):** `/federal` Style & Layout
  **81 ms** vs the CI-green anchor `/m/A000055/1` at **153 ms** — comfortably below, on the
  exact axis that sank the `<table>` build (663 ms → 0.77). Script Eval 80 ms (hydration +
  the ~1,274-node injection), TBT 5 ms, perf 0.98 local. DOM grew 10,964 → 13,517 (a
  diagnostic, not a scored gate; the injected nodes sit inside content-visibility rows).
  **Deliberately NOT built (out of documented polish scope):** README screen 2 also lists a
  "Not graded" grade filter chip the island lacks — noted as a spec gap in PROGRESS, not
  added here. Gates: astro check 0, build 13,085, e2e **40** (incl. exclude→hide→restore,
  select-2→compare-link→navigate, and the injected-controls axe scan), grade-labels (5/6),
  metrics-sections (10+5), links, file-count. This closes the Nocturne pass's polish items;
  **V2-5 stays OPEN — the "lowest N%" headline (H15 round two) is still owner-gated.**
- **D81 (2026-08-15) — retired `party_unity` federally; added `cross_aisle_support`.**
  Direct owner instruction while preparing the H15 round-two headline options: **"delete the
  party unity. This is a dumb stat."** and, choosing among the cross-aisle definitions I
  brought, **"Go with option two."** (option two = of the OTHER major party's final-passage
  bills a member voted on, the share they voted Yea). Factual metric work (Tier-2) — no H15
  and no evaluative constant; a rate with its denominator always shown, not a grade.
  - **New metric `cross_aisle_support`** (`ingest/metrics.py`): over the passage + veto-
    override rolls sponsored by the member's opposite major party that they cast Yea/Nay on,
    `pct = yea / considered`; null when `considered == 0` (independents have no single
    opposing party, so they fall out with a 0 denominator — no special-case, the `_OPPOSITE`
    map does it; **no min-N threshold** — a min-N would be an unratified cutoff, and the
    denominator is always published). Voter and sponsor party are both taken on the roll's
    date (`_party_on`); `data/bills` carries no introduced date, so the roll date is the one
    consistent reference. A voted-on bill absent from `data/bills` **raises** (mirrors the
    `_load` orphan-vote guard) rather than silently shrinking the denominator. `_load` now
    also reads each bill's sponsor into `Ctx.bill_sponsor` — a shared-input change the
    per-metric digest can't see, so **`FORMULA_SCHEMA_VERSION` 2 → 3**.
  - **Honesty caveat, published in the docstring → methods page** (the `position_mix`
    "NOT an approval measure" precedent): the majority controls which bills reach a final-
    passage vote, so the pool of "opposing-party bills" differs by party and, for the
    minority, skews to the less-contested measures leadership allows up. It reads as support-
    when-it-comes-up, NOT a complete bipartisanship score. Validated for face-value: the top
    scorers are the known cross-aisle names (Fitzpatrick 95%, Bacon 94%, Lawler 92%).
  - **Federal-only (owner decision, this session).** Asked whether the deletion reaches
    Mississippi (which shows the same stat via the shared `MemberStats.astro`), the owner
    chose **"Federal only; keep party unity on MS."** So `party_unity` stays in the `METRICS`
    registry, `METRIC_LABELS`, and `PartyUnityValue` — the MS layer (`ms_metrics.py`) still
    computes and publishes it unchanged (MS `metrics.json` is byte-identical after this
    change). Federal build iterates a new **`FEDERAL_METRICS`** subset (registry minus
    `party_unity`); `MemberMetrics` swaps `party_unity`→`cross_aisle_support`; the
    `set(FEDERAL_METRICS) == MemberMetrics.model_fields` test replaces the old `set(METRICS)`
    one. Rankings swap `party_unity`→`cross_aisle_support` in `RANKED_METRICS` + the delegate-
    excluded `VOTE_METRICS`. Site: the explorer column, the federal member-page tile, and the
    `/compare` island/prose move to cross-aisle; the MS-only `MemberStats.astro` and the MS
    methodology paragraph keep "party unity" verbatim.
  - **Spec note (NOT edited — owner's document):** IMPLEMENTATIONv2.md still lists
    "Party unity %" in its metric table. Flagged to the owner to amend; the builder does not
    edit the spec.
  - Gates: `checks` all-passed (Tier-3 guard OK on the new metric; MS metrics recompute),
    `verify-recompute` OK (metrics + 5 rankings incl. `cross_aisle_support` + grade recompute
    exactly), pytest 319 passed (+ the known git-history test, green once this regen commits),
    build 13,085, astro check 0, metrics-sections (10+5), grade-labels, e2e 40. The
    regenerated `data/metrics.json` + `data/rankings/` + `data/schema/metrics.schema.json`
    ship in the SAME commit as the code (the D40 `build() == committed` determinism test is
    red between halves of a split commit).

- **D82 (2026-08-16) — V2-5 wide-eyed headline: "97% of bills introduced never got a floor
  vote."** The landing headline deferred since V2-5 opened (framed in the spec as "the
  'lowest N%' cut is a ratified threshold — H15 round two"). Two findings collapsed it into a
  factual, no-ratification-of-a-threshold build. **(1) No data pull needed.** The owner had
  authorized pulling the "full introduced-bill universe"; orientation found it already in
  committed data — `data/legislation/{member}.json` holds every bill all 637 covered members
  SPONSORED (bill_id + introduced_date + became_law). Union = **37,669** distinct bills; the
  voted set = distinct non-null `RollCall.bill_id` (**1,011**). So **36,658 (97.3%)** of members'
  bills never appear in a recorded roll call. Robustness checks (all from existing data): law-
  track only (hr/s/hjres/sjres) = 97.7%; 118th (closed) = 97.2%, 119th = 97.4% — the number does
  not depend on lumping in resolutions or on the ongoing Congress. Option B (cosponsorship cross-
  aisle) is ALSO computable now (30,076/30,078 cosponsored bills resolve to a sponsor) — the pull
  is entirely moot. **(2) Factual, not evaluative (§0.8, D81 precedent).** A plain count with no
  cutoff, no grade, no member singled out needs no ratified threshold; the owner still ratified
  the *wording* + denominator, choosing "all measures / 97%" from three framings I offered.
  **Truth caveat (Value #1), disclosed on `/methods#floor-votes`:** "floor vote" = *recorded
  roll-call* vote — a bill can still pass by voice/UC with no roll. This is not hypothetical:
  **232 of the 375** of these bills that became law did so with no roll call in our data. So the
  headline says "recorded floor votes" and the sub-copy says "most died in committee," never
  "got no consideration." **Mechanics:** `ingest/legislation_stats.py` (`compute(data_dir)`,
  pure, single-source) → new `manifest.counts.legislation` block; `verify_recompute` invariant 7
  re-derives it byte-exact (a landing number that can't be recomputed from public data may not
  ship). The "97%" is a display rounding of the exact committed counts, which are shown in full
  beside it — no stored evaluative number. Added to the §8 100%-branch coverage gate (5th
  module). **Open nuance flagged to owner:** spec V2-5 says a headline "that cannot be clicked
  through to its full list may not render"; this is a systemic bill count with no per-member
  "who," so it renders as a non-clickable flagship stat (exact counts inline + methods link) —
  the D72 precedent for "Roll calls"/"Individual votes." Whether to build a bill drill-down list
  is the owner's call; not built. Spec §7 V2-5 headline line is now stale (owner to amend).
- **D83 (2026-09-21) — accept-list for known-quarantined rolls; the nightly stops failing on
  them.** The `nightly` workflow had failed **every night since V2-1** (`2cedc532`) — `uv run
  ingest house-votes` returns nonzero whenever any roll is quarantined, and four House rolls are
  permanently quarantined as `UnknownMember` because a recorded voter falls outside the covered
  roster on the roll's date: `h-118-1-0001` (M001200, not rostered), `h-119-1-0001` (G000578,
  term ends 2024-11-13 in the roster), `h-119-2-0130` + `h-119-2-0131` (S001157, term ends
  2026-04-21). Quarantine deletes the votes file, so `incremental.roll_is_final` sees no export
  → the rolls re-fetch and re-quarantine every night → exit 1 → a nightly-failure email, forever.
  Nothing bad was ever published (the committed data is byte-stable; `ci.yml`'s verify-recompute +
  checks are green *without* these four rolls), so the only effect was the recurring email.
  **Decision (owner-ratified 2026-09-21 via an in-session choice among four options — accept-list,
  fix roster, investigate source, silence emails — owner picked accept-list).** Added
  `data/quality/accepted-quarantine.yaml`: owner-reviewed roll ids → factual reason. A quarantine
  on a listed id is recorded and its stale export removed exactly as before, but it lands in an
  `accepted` list (printed as `note:`, not `FAIL:`) instead of `ms_failures`, so the run stays
  green. A **new/unexpected** quarantine still fails loudly — the "nightly failed" signal is
  preserved for genuine drift, just not spent on these four known cases. Loader
  `incremental.accepted_quarantines()` (pure, missing file → empty) is wired into **both**
  `house_votes.run()` and `senate_votes.run()` (senate matches today empty — guards against the
  identical future email loop). Reasons stay factual/neutral because §6.4 banned-words scans
  `data/quality/` (this file is not excluded). Tests: loader (missing file, load), the partition
  decision (known→non-fatal, new→fatal), and a drift guard (accept-list ids == committed
  quarantine ids). Gates green: ruff, pytest 330, §8 100%-branch, checks, verify-recompute. **Not
  a data fix:** the four votes remain unpublished; whether to correct the roster (widen a term,
  add M001200) so they ingest is a separate owner call, left open.

## SD-32 — Amendment 5: the site may read and collect what its features need (2026-09-23)

- **SD-32 (2026-09-23, owner-ratified) — data-reading amendment + priority reorder.** The
  owner asked for profiles, topic subscriptions, bill tracking, and email/text alerts, then
  directed: *"change anything in the plans or other docs that stop the site from reading or
  collecting data."* Applied the same day: `IMPLEMENTATIONv2.md` §0.4.3 (Value #3 reworded:
  collect only what the product needs, never sell, deletion deletes — the site may **read**
  what it stores), SD-2/SD-12/SD-22/SD-28 dispositions, §3 (worker scope + boundary), §5
  (account model: readable `users` / `preferences` / `subscriptions` / `deliveries` /
  `channels` / `profiles`; schema test = tables equal the `/privacy` storage list), §7 V2-7
  (privacy page + threat model now say the data is readable and demand-producible), §7 V2-8
  (client-side crypto + recovery code retired; email verification + reset by email), §8 test
  families, §10 consequence paragraph (rewritten: a legal demand yields readable follows,
  preferences, answers, addresses — the owner's informed trade), Appendix B INC-22, and the
  end-of-spec build order. `CLAUDE.md`/`AGENTS.md`/`CONTRIBUTING.md`/`docs/kickoff-v2.md`
  updated to match. **Untouched on purpose:** the LIVE `/privacy` page — it says nothing is
  collected, which is TRUE today; Value #1 (unamended) forbids rewriting it until V2-7 ships the
  truthful version alongside the first collecting feature. **Priority reorder (same decision):**
  V2-11 (bill activity + topics + feeds, zero collection) → V2-7 → V2-8 → V2-12 (subscriptions
  + email) → V2-13 (text / push); V2-6 deferred (only two grade-history commits exist). Plan
  and open decisions 2–7: `docs/plan-subscriptions-and-alerts.md`. New human tasks H20–H23.

- **D84 (2026-09-24) — the nightly rebases before it pushes; a mid-run commit no longer
  destroys a green night.** The `nightly` job's last step was a bare `git push`
  (`nightly.yml:142`). Steps 1–5 run for **hours** between the job's `actions/checkout` and
  that push — 4h17m, 4h32m, 4h43m, 5h51m across the last four runs — so any commit landing on
  `master` inside that window makes the push non-fast-forward and the job exits 1. Two runs
  died exactly this way, both **after every gate had already passed**: `35622111686`
  (2026-09-21, `non-fast-forward`) and `35872806073` (2026-09-23, `fetch first`). The 09-23 run
  had produced commit `b7e65fbfb`, "data: nightly 2026-09-23", 258 files / 4,024 insertions
  including two new Senate rolls (`s-119-2-0239`, `s-119-2-0240`) — `ALL CHECKS PASSED`,
  `verify-recompute: OK` on 3,503 roll calls — and the whole thing was discarded at the last
  instruction. **This is the failure `docs/plan-subscriptions-and-alerts.md` §2 V2-11 task 8
  predicted in advance** ("the nightly runs 4–5 hours between its checkout and its push; a
  second workflow committing to `master` in that window makes the nightly's push
  non-fast-forward and fails a green night") and prescribed the mitigation for; the second
  workflow it anticipated has not been built yet, but a human pushing docs does the same damage.
  **Fix:** `git fetch origin master` + `git rebase origin/master` + `git push origin HEAD:master`
  in a bounded 3-attempt loop. **`--force` is never used** — a rejection means somebody else's
  work is on the remote. The rebase is a clean replay because the data commit touches only
  `data/`, which nothing but this job writes; a genuine conflict fails the job loudly, leaving
  the last good deploy live (§6.1), the same outcome as today. **Residual risk, accepted:** a
  *code* change (metric formula, thresholds) landing mid-run leaves the rebased data computed
  against the old code. `ci.yml` runs `verify-recompute` on every push, so that skew fails
  visibly on the resulting commit rather than shipping silently. **Not a data fix and not a
  V2-N acceptance:** no ingest logic, no threshold, nothing evaluative changes — §0.8 does not
  apply. The 09-23 data is not permanently lost; the ingest is incremental against the live
  record, so the next green run re-collects it. **Distinct from D83:** D83 fixed the 2-minute
  quarantine failures (2026-09-18/19/20); D84 fixes the multi-hour push failures
  (2026-09-21/23). **Acceptance:** one green `nightly` run that commits and pushes a data diff.
  **Unrelated and NOT addressed here:** the `Node.js 20 is deprecated` line in the failure
  emails is a GitHub runner warning about `actions/checkout@v4`, `actions/setup-node@v4`,
  `actions/cache@v4` and `astral-sh/setup-uv@v5`. It is noise — it appears on green runs too
  (`35737604333`, 2026-09-22) and never caused a failure. Bumping those action majors is a
  separate change, deliberately not bundled, so this fix's acceptance run has one unambiguous
  failure mode.

- **D85 (2026-09-24) — GitHub Actions bumped off the deprecated Node 20 runtime; `setup-uv` is
  pinned to a commit SHA because it no longer publishes major tags.** Every run was printing
  `Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run
  on Node.js 24` (GitHub's 2025-09-19 changelog). It was never a failure — it printed on the
  GREEN run `35737604333` too — but the forced-Node-24 grace period ends, so all **11** action
  refs across all three workflows were bumped in one commit: `actions/checkout@v4 → @v7`,
  `actions/setup-node@v4 → @v7`, `actions/cache@v4 → @v6`, `astral-sh/setup-uv@v5 →
  @c18668ad3cf93ea998bef934396af7bb5c839dc7` (v10.2.0). Targets were read from each repo's
  releases API, **not guessed**. **The non-obvious constraint — do not "fix" this back to a
  major tag:** `setup-uv` v8.0.0 stopped publishing major and minor tags on purpose ("pinning to
  major releases opens up users to supply chain attacks like what happened to tj-actions"), and
  `repos/astral-sh/setup-uv/git/ref/tags/v10` returns **404**. `@v10` would not resolve, so the
  full commit SHA with a trailing `# v10.2.0` comment is the only correct form. **Breaking
  changes reviewed, none of which bite here:** checkout v5 moved to Node 24 and v7 blocks
  checking out fork PRs for `pull_request_target`/`workflow_run` (neither event is used);
  cache v5 needs Actions Runner ≥ 2.327.1 (hosted `ubuntu-latest` is current); setup-node v5
  made package-manager caching automatic — the explicit `cache: npm` +
  `cache-dependency-path: site/package-lock.json` still matter because the lockfile is in
  `site/`, not the repo root, and both inputs are still declared in `setup-node@v7`'s
  `action.yml` (verified); setup-uv v9 changed `prune-cache` to default `false` (larger caches,
  no behavior change) and v10 disables auto-caching for `pull_request_target`/`workflow_run`/
  `release` (none used). **Deliberately NOT bundled with D84** so that fix's acceptance run has
  one unambiguous failure mode. **Acceptance:** a green `ci.yml` run on this push — immediate,
  unlike D84's ~5h nightly. If ci goes red, this bump is the only variable: revert the commit
  rather than debugging forward. The first `nightly` on the bumped actions is 2026-09-25; the
  D84 acceptance run `36015043828` checked out `368dbf088` and predates this, so the two
  acceptances stay independent.

- **D86 (2026-09-29) — nightly legislation ingest probes lifetime counts and re-pages only
  members whose counts moved; a full re-page runs on Sundays.** Owner-chosen ("proceed with
  option 1") after the free GitHub Actions allowance ran out on 2026-09-28 (both nightlies
  since died in 5 s: *"The job was not started because recent account payments have failed or
  your spending limit needs to be increased"*). **Where the minutes went:** `uv run ingest
  legislation` — 3h35m of the 09-27 run's 3h50m (`14:45:36Z → 18:20:31Z`; everything else,
  votes/bills/classify/build/checks, ~15 min). It re-fetched every one of 639 members' sponsored
  + cosponsored lists every night: ~3,500 pages of 250 items, and a 250-item cosponsored page
  takes ~7 s (measured live, W000437), so the 1 req/s throttle was not even the bottleneck. The
  restored raw cache (R-5) never helped because its TTL is 20 h and the cadence is 24 h. **Why
  it only showed up on 09-21:** before D83 the nightly crashed at step 2 (house-votes) after ~2
  min every night from 09-01 to 09-20, so the legislation step never ran; fixing the crash
  exposed the real cost. September: nightly ≈ 2,140 min + ci ≈ 127 min > the 2,000-minute
  private-repo allowance (owner keeps the repo private, D59; stays on free plans — owner,
  2026-09-29). **Fix:** `congress_gov.member_lifetime_counts()` — ONE `/member/{id}` request
  whose `sponsoredLegislation.count` / `cosponsoredLegislation.count` equal the list endpoints'
  `pagination.count` (verified live: 761 / 4,534 on both for W000437; ~0.6–0.9 s). Each
  `data/legislation/{id}.json` now stores that pair as `lifetime_counts` (schema regenerated;
  not a published metric — the metrics still read the covered-window `sponsored`/`cosponsored`
  lists). `legislation.should_refetch()` (pure) re-pages a member iff the record predates D86
  or either count differs — up OR down (a withdrawn cosponsorship lowers it). A malformed probe
  reads as 0/0, which cannot equal a real committed pair, so probe failure degrades to the full
  fetch, never to a stale reuse. An unchanged member's file is left byte-identical (D33
  quiet-night gate). **Staleness bound, stated:** the probe cannot see an already-listed bill
  whose latest action moves to "Became Public Law" with no new sponsorship by that member, so
  `nightly.yml` passes `--full` on Sundays (`date -u +%u = 7`); enactment flags lag ≤ 7 days.
  The **first** post-D86 night re-pages everyone once (no record carries counts yet) — one more
  ~4 h run, then ~11 min for the probe (639 × ~1 s) plus the changed members. **Budget after:**
  quiet night ~15–25 min, busy day 30–90 min, Sunday ~4 h → ≈ 900–1,400 min/month, inside the
  2,000. **Not evaluative, not a V2-N acceptance:** no metric, threshold, or wording changes;
  the same data lands, on a different schedule. **Rejected:** raising the cache TTL above 24 h
  (the restored cache would then always be "fresh" and legislation would never refresh at
  all); a self-hosted homelab runner (zero billed minutes, but an owner setup task — offered as
  option 3, not chosen); public repo (unlimited minutes; D59 stands). **Acceptance:** the first
  non-Sunday nightly after the first full post-D86 run completes in < 1 h and prints
  `N re-fetched + M unchanged (kept) of 639 members`.

- **D87 (2026-09-30) — surgical code-review remediation: MS sessions accumulate (career
  numbers), five ingest hardening fixes, two owner rulings on published copy.**
  A full external-stance audit (`code-reviews/review-2026-09-30.md`: 0 Critical, 1 High,
  5 Medium, 5 Low) found one time bomb and a set of latent crash paths. All eleven
  findings plus the dead-code inventory are fixed here. **Not a V2-N increment and not
  evaluative:** no metric, threshold, formula, or grade wording changes, and no committed
  record is rewritten (the only `data/` diff is a comment in `accepted-quarantine.yaml`).
  **(1) Mississippi session rollover — the High.** `current_session()` follows the newest
  regular session with no config change, but the export overwrote by member key and never
  reconciled. When LegiScan publishes the 2027 session (typically January) the nightly
  would have written it beside the 2026 data while `/methods` said "only the current
  regular session is included". **Owner ruling (2026-09-30), asked in plain language and
  answered: a Mississippi grade is a CAREER grade — numbers and trends must span a
  legislator's whole career, not the newest session.** So the fix is NOT the delete the
  review proposed (that would have reset every MS member to 2027-only): the partition
  ACCUMULATES, matching the federal side, which already spans the 118th and 119th.
  Accumulating is only safe if nothing is silently replaced, so: `merge_member` keeps a
  continuing legislator's earlier terms (dedup on the whole term, start-sorted);
  `_mark_departed` flips `serving` to false in place for members absent from the new
  roster (they were frozen at `serving: true`, since `export_members` only writes the
  members it is given); `merge_legislation` unions sponsored/cosponsored on `bill_id`
  (legislation files are keyed by MEMBER, not session — the one place a rollover would
  have silently LOWERED a published sponsorship number); the crosswalk keeps departed
  members; `disk_counts()` recomputes the manifest `counts` from the committed partition
  instead of from the one session just built; and the manifest gains `sessions[]`, every
  session included, newest first. `/methods` coverage and the `/ms` roll-call tile now
  name what the counts actually span (`msCoverageLabel`). Roll ids (`ms-h-<session>-<id>`)
  and bill ids (`ms-hb1-<session>`) already carried the session, so nothing collides.
  **Verified byte-identical on today's single-session data:** `disk_counts()` reproduces
  the committed manifest's `counts` exactly, and a same-session re-export is byte-for-byte
  stable (`test_single_session_export_is_unchanged_by_the_merge`); the only manifest
  change on the next `ingest ms` is the added `sessions` key. `checks/ms.py`'s five
  hardcoded 2249 sample rolls stay valid precisely because files accumulate.
  **Owner tasks before January:** threshold review for career-span MS numbers
  (§0.8 — the numbers' meaning widens even though no formula changes), and per-session
  browsing / trend display, which is deferred to its own increment (the MS index still
  lists every member file, departed ones included).
  **(2) Ingest hardening.** `senate_votes` pre-parse caught only `ET.ParseError` while
  `_parse_date` raises `ValueError`/`KeyError` — one odd date from senate.gov aborted the
  whole run and skipped every later roll; now quarantined. `house_votes` read `startDate`
  OUTSIDE its try (a missing key aborted; a null date raised `TypeError` inside
  `coverage.covered_on`'s slice); moved in, `TypeError` caught. `legiscan._get` replaced
  `raise_for_status()` with `LegiScanHTTPError`: LegiScan requires the key as a QUERY
  param and httpx embeds the request URL in that message, so a 4xx/5xx printed
  `key=<secret>` (GitHub masks its own secrets; a local run and a pasted log do not).
  `accepted-quarantine.yaml` now accepts BILL ids too — one flat file, ids cannot collide
  — so a bill Congress.gov never publishes is a printed note instead of a nightly failure
  forever. Quarantine files are unlinked once the record exports cleanly, so the directory
  describes what is actually quarantined. **Rejected:** caching 404s in `cache.fetch` —
  the house-vote clerk fallback relies on a 404 raising.
  **(3) Actions minutes.** `bill_committees` takes `ttl_hours`; `classify` passes 30 days.
  The 20 h default expired before the 24 h nightly cadence, so up to 215 Rules-Committee
  lookups were re-fetched every night the vote files changed. Unlike the legislation lists
  (where D86 REJECTED a >24 h TTL, because those must keep refreshing), this answer is
  final: Rules reports a special rule BEFORE the floor vote it governs. Saves ≥ ~4 min per
  active night. `archive-links.yml` got nightly's fetch-rebase-retry loop (D84 shape).
  **(4) Published copy — owner rulings.** *Privacy:* "visiting this site leaves no record
  anywhere", "nothing you do here is sent to any server the operator runs", and the
  "results stay in your own browser" promise are all false or about to be (Cloudflare
  hosts the site and reports request counts; SD-32 lets features collect what they need).
  **Owner (2026-09-30): strip it — the no-logging claim is impossible for what the project
  needs to do, and the rest of the page is being rewritten in a later session.** Deleted,
  not reworded: the three false claims are cut and the two paragraphs left grammatical by
  deletion alone — no new privacy claim was written, and no Cloudflare copy added, because
  that option was not chosen. V2-7 still
  owns the full rewrite. *Absence explanations:* the Congressional Record search is scoped
  to Mississippi, so 631 of 639 members can never have a stated reason. **Owner
  (2026-09-30): say so plainly rather than widen the search** (widening multiplies the H9
  review queue ~50×); one sentence added to `/methods` Sources.
  **(5) Dead code.** Deleted `getVote`, `getMsVote`, and the `Manifest.covered_state` type
  field (removed from the manifest at V2-1). KEPT: `models.py` `PageCapture`/`Candidate`/
  `Provenance`/`QuizOption`/`QuizQuestion` and `config.K_ANON` (parked by §5 and Appendix
  B). **Spec/code disagreement, recorded not fixed:** `banned_words.ALLOWLIST` allowlists
  `site/src/content/glossary.md`, which does not exist — the spec (§CS, Appendix B)
  describes the glossary as existing. Harmless today; the owner decides whether the
  glossary page gets built or the allowlist entry goes.
  **(6) Documented, not changed.** The D86 probe cannot see a same-day cosponsorship
  add-plus-withdraw (the lifetime count is unchanged); bounded to 7 days by the Sunday
  `--full` run, same as the enactment case. Whether `cosponsoredLegislation.count` moves
  on a withdrawal is NOT confirmed live (header auth, no offline check) — stated as
  unconfirmed in the module docstring rather than asserted.
  **Acceptance:** `uv run pytest` 363 passed (was 341; +22 new across
  `tests/test_ingest_hardening_d87.py` and `tests/test_ms_session_rollover_d87.py`),
  `uv run ruff check .` clean, `uv run checks` ALL CHECKS PASSED (banned-words scanned the
  two edited pages), `astro check` 0 errors, `astro build` 13,161 pages, `git status data/`
  shows only the accept-list comment.

- **D88 (2026-10-01) — V2-11 task 1: the bill API surface, measured live, not assumed.**
  The plan (`docs/plan-subscriptions-and-alerts.md` §2 V2-11 task 1) requires one
  authenticated call per unknown before the ingest is sized: the `/bill` list endpoint's
  update-date filtering/sorting and page size, the `/actions` sub-resource shape and
  pagination, and the per-key rate limit. All probed 2026-10-01 against the live API with
  `CONGRESS_API_KEY`. Two samples committed under `data/quality/samples/`
  (`congress_bill_actions_hr2670_118.json`, `congress_bill_list_sorted_updatedate.json`);
  field shapes recorded as **SHAPES.md §9**, which is the contract the parser gets written
  against. Non-evaluative: no metric, threshold, grade or published number is involved.
  **(1) Corpus size — the plan's "roughly 15,000-20,000 per Congress" is confirmed at the
  top of its range.** `pagination.count` on `/bill/{congress}`: **118th = 19,315**,
  **119th = 19,441**, **38,756 covered bills** against the 1,038 that reach a roll call
  today (2.7%). The unscoped `/bill` count is 430,715 (all congresses on file).
  **(2) The update window works.** `fromDateTime` / `toDateTime` (ISO `...Z`) are honored
  and compose with the `/bill/{congress}` path form. Discriminating check, per the method
  the plan demands: the filtered count must differ from the unfiltered one or the parameter
  was ignored. **24 h = 435 bills** vs 430,715 unfiltered; **7 d = 1,954**. Scoped to the
  covered Congresses the same 24 h window gives **118th = 16, 119th = 411 (427 total)**.
  **(3) DEVIATION — `sort=updateDate+desc` is silently ignored.** The documented `+` form
  is transmitted as a literal `%2B` and the API discards the whole sort: `updateDate+desc`,
  `updateDate+asc` and a deliberate `sort=BOGUSVALUE` control all return the **identical**
  page (first row `2025-04-07` on a day when bills were updated `2026-10-01`). The working
  form is **`sort=updateDate desc`** — a literal space, encoded `%20` — which returns
  genuinely newest-first. Caught only because the probe compared against a bogus-value
  control rather than reading the first page and declaring success. Recorded in SHAPES.md
  §9 as a deviation so no later parser reintroduces the `+`.
  **(4) Page ceiling is 250 and `limit=251` clamps rather than errors** — a silent
  truncation of exactly the kind `TruncatedFetchError` (D64) exists to catch, so the
  paginator must trust `pagination.count`, never the returned length.
  **(5) `/actions` shape.** Top-level `{"actions": [...], "pagination": {...}}`. Fields over
  324 real actions across four bills: `actionDate` (always), `text` (verbatim, stored as-is
  per §0.5), `type`, and the **optional** `actionTime` (142/234 on NDAA FY24, 9/64, 10/26 —
  nullable, never sort on it alone), `actionCode`, `committees`, `calendarNumber`, plus
  `recordedVotes` — `{chamber, congress, date, rollNumber, sessionNumber, url}`, which is
  the join to an existing `RollCall.id`. **Pagination is UNEXERCISED and stated as such:**
  the largest action list found is **234** (`hr2670-118`, NDAA FY24; also probed hr3684-117
  = 101, hr748-116 = 49, s2226-118 = 46), all under the 250 ceiling, so `pagination.next`
  never appeared on `/actions`. The paginated branch still gets written and gets a unit test
  against a synthetic payload; it cannot be confirmed live until a bill exceeds 250 actions.
  **(6) Rate limit — H23 answered.** Response headers carry `x-ratelimit-limit: 20000` /
  `x-ratelimit-remaining`; **no header states the reset window**, so the window is NOT
  confirmed and is not asserted here. Note the direction of the risk: a LONGER window makes
  the cap tighter, not looser — `ingest/cache.py` throttles `api.congress.gov` to 1 req/s
  = 3,600/hour, so a daily window would be exhausted after ~5.6 hours of continuous fetching.
  - **The nightly never binds on either reading.** A normal night is ~1,740 requests and a
    Sunday `--full` ~14,400, both under 20,000 on any window of 4 hours or more.
  - **The one-time backfill does depend on the window:** ~155,000 requests is ~43 h if the
    window is hourly, but closer to 8 days if it is daily. `cache.py` already honors
    `Retry-After` on a 429 (line ~139), so it throttles rather than crashes either way.
  - Cheap confirmation whenever convenient: make one call ~1 h after a burst and read
    `x-ratelimit-remaining`; back near 20,000 means hourly. Not done here — only 14 minutes
    had elapsed when this was written.
  **No rate-limit raise is needed; H23 closes.** The binding constraint on a normal night is
  wall-clock, not the key.
  **(7) Sizing, from the measured numbers.** `ingest/bills.py` spends 3 requests per bill
  today (`bill_detail`, `bill_subjects`, `bill_cosponsor_ids`); `/actions` makes it 4.
  - Full backfill of all 38,756 covered bills: 155,024 requests + 156 list pages at 1 req/s
    = **at least ~43 hours** — a FLOOR, not an estimate: the throttle sets it, and D86
    measured a single 250-item page taking ~7 s, so the real figure is higher. That is
    **≥ ~2,590 GitHub Actions minutes — more than one entire month's 2,000-minute free
    allowance** (H24). **It cannot run in CI.** It can run locally over a sitting or two and
    be committed, which costs zero billed minutes.
  - Steady state, full refetch of every updated bill. The daily figure is a RANGE, not the
    single Thursday sample: 435 in the probed 24 h, but 1,954 over 7 d ≈ 280/day, so
    **280-435 bills/day x 4 = ~19-29 min/night = ~560-870 min/month**. The D86 nightly
    already uses ~900-1,400 (H24), so **this does not fit the free allowance at either end.**
  - Steady state, actions-only for bills already known, with the full 4 calls only for
    genuinely new ones: **~5-7 min/night = ~150-210 min/month**, which does fit inside the
    existing headroom.
  These three numbers are what owner decisions 3 and 6 are asked against; they are reported,
  not acted on. No ingest code is written in this entry — task 1 is measurement only, and
  the plan gates tasks 4 onward on decisions 3, 4 and 6.

## SD-33 — V2-11 shape ratified: coverage, topics, cadence, channel (2026-10-01)

- **SD-33 (2026-10-01, owner-ratified) — the four open V2-11 decisions, answered.** Asked in
  plain language at the end of V2-11 task 1 as `docs/plan-subscriptions-and-alerts.md` §1
  requires, carrying D88's measured numbers rather than estimates. Canonical home is
  `IMPLEMENTATIONv2.md` §2; this is the dated append-only record (SD-31).
  **Decision 3 — coverage = (c).** All **38,756** bills in the covered Congresses are tracked
  for alerts, topics and feeds; only the bills that reach a recorded vote (**1,038** today)
  get a `/b/` page. Per the plan's own warning, a topic row or feed entry for a pageless bill
  links to that bill's `source_url` on congress.gov and **never** to a `/b/` URL that does not
  exist, or `npm run test:links` fails.
  **Decision 4 — topics = (a).** Official government vocabulary only: the 31 policy areas and
  872 CRS subject terms, verbatim, with mechanical slugs. No owner-authored bundles in this
  release. **H22 stays optional and is not a blocker**; bundles can be added later as a
  disclosed, dated editorial artifact without changing anything else.
  **Decision 6 — cadence = daily digest**, carried by the existing `nightly.yml`. No second
  intra-day workflow, so no new GitHub Actions minutes beyond the ingest itself. Per-
  subscription "faster" remains addable later.
  **Decision 2 — channel = email first.** This makes **H17** (Turnstile), **H18** (email
  provider) and **H20** (Workers Paid) the V2-12 blockers. Text and browser push are phase 2;
  **H21 is untouched and phone numbers remain a data class the spec does not permit.**
  **Decision 7 — Workers Paid is NOT forced by V2-11.** Only the 1,038 voted bills get pages,
  so the build stays under the Workers Free 20,000-file limit (it is at 13,161 today). The
  $5/mo upgrade is deferred to **V2-12**, where Email Sending requires it regardless.
  **What decided decision 3 was the backfill cost, not the API.** At the 1 req/s ceiling a
  full 38,756-bill fetch is **at least ~43 h ≈ 2,590 GitHub Actions minutes** — more than one
  entire month's 2,000-minute free allowance (H24). **It therefore runs locally once and is
  committed; it must never run in CI.** The steady state must likewise be actions-only for
  bills already known (~5-7 min/night, ~150-210 min/month) rather than a full refetch of every
  updated bill (~19-29 min/night, ~560-870 min/month), which does not fit beside the D86
  nightly's existing ~900-1,400. **This is a build constraint on tasks 4 and 5, not a
  preference.** Option (a) (voted bills only) was rejected because a bill invisible until its
  first recorded vote defeats the owner's stated request; pages for all 38,756 were rejected
  as unwanted pages plus a forced plan upgrade.
  Not evaluative: no metric, threshold, grade boundary or published number is involved, so
  §0.8 does not apply. These are scope and cost choices, ratified because the plan reserved
  them for the owner.

- **D88 addendum (2026-10-01, written during V2-11 task 2) — three more measured facts,
  two of which change how a parser must be written.** Recorded here because they were
  found after D88 was committed and the log is append-only. All three are also in
  SHAPES.md section 9, which is the contract the parser is written against.
  **(a) Actions have no id, and (date, time, code, text) is NOT unique.** `hr2670-118`
  carries five rows reading "Forwarded by Subcommittee to Full Committee by Voice Vote ."
  on 2023-06-13 under code `H23000`, and six reading "Subcommittee Consideration and
  Mark-up Session Held." under `H22000` — each a different subcommittee, discriminated
  **only** by the `committees` field. The first cut of `bill_actions()` keyed its dedupe
  on that four-field tuple and silently returned **225 of 234** real actions. Caught by a
  live smoke test, not by the unit suite, which was synthetic and shared the wrong
  assumption. Fixed two ways: dedupe hashes the whole row, **and** the function now raises
  `TruncatedFetchError` if the unique-row count comes in under `pagination.count`, so a
  future collapse fails loudly instead of publishing a short timeline. Both are regression-
  tested (`tests/test_bill_activity_v2_11.py`).
  **(b) There is no deep-offset ceiling.** `offset=19300` on `/bill/118` (count 19,315)
  still serves rows; `offset >= count` returns an empty page rather than an error; sort
  composes with a deep offset. A count-bounded loop can therefore enumerate a whole
  Congress — the backfill path needs no cursor or date-slicing workaround.
  **(c) `sort=updateDate asc` works too, but DESCENDING is the direction a crawl must
  use.** A bill updated mid-crawl jumps to position 0 and shifts the pages behind it down,
  so a descending crawl re-reads a row it already has (idempotent, deduped for free).
  Ascending moves the touched bill to the end and shifts everything after it up, which
  **skips** a row at the cursor. Duplicates are recoverable; skips are silent undercounts
  (value #1). `UPDATE_SORT` is a module constant with a test asserting its exact value, so
  neither the direction nor the `+`/space trap can regress unnoticed.

- **D89 (2026-10-01) — V2-11 task 3: the `BillAction` schema, with one field the plan
  did not list and one it did not constrain.** `ingest/models.py` gains `BillAction`;
  `Bill.actions: list[BillAction] | None = None` joins `subjects` and `cosponsor_ids`
  under the same D27 sentinel (None = not collected, [] = collected and none exist).
  `ingest/bills.py` gains the pure `parse_actions()` and `rollcall_id_for()`. 24 tests
  (`tests/test_bill_actions_model_v2_11.py`); `data/schema/bill.schema.json` regenerated.
  Mechanical and non-evaluative (§0.1(d)): no metric, threshold or published number.
  **Nullability was measured before it was written, not inferred from the plan.** 520 real
  actions across six bills and four Congresses: `actionDate`/`sourceSystem`/`text`/`type`
  present on all 520; `actionCode` 337; `actionTime` 227 (44%); `committees` 97;
  `recordedVotes` 58. Table in SHAPES.md §9. The task-2 bug is why this survey happened at
  all — an assumed shape cost nine real actions there, so no field here is typed from the
  plan's prose.
  **(1) `committees` ADDED to the plan's field list.** The plan specifies
  `BillAction(date, time|None, text, type, action_code|None, source_system, rollcall_id|None)`.
  That set cannot represent hr2670-118 honestly: five of its actions share a date, text and
  action code and differ **only** in which subcommittee acted. Without `committees` the
  rendered timeline repeats one line five times with no explanation, and the whole-row
  dedupe that (correctly) kept them looks like a bug. Stored verbatim, names only.
  **(2) `type` is `str`, not a `Literal`.** Eight values appear in the survey and the set
  belongs to the government. A Literal would quarantine an entire bill the first time
  Congress coins a ninth action type — a brittleness with no upside.
  **(3) `source_system` stores the name, not the code.** The Senate's block is
  `{"name": "Senate"}` with no `code` field at all (183 of 520 rows), so a stored code would
  be null for a whole chamber while carrying nothing the name does not.
  **(4) `rollcall_id` is resolved against what this dataset HOLDS, not against what exists.**
  `parse_actions(raw, known_rollcall_ids=...)` sets the id only on a hit; the default is to
  resolve nothing, because "I was not told what exists" must never degrade to "assume it all
  exists". Measured: 40 of 58 resolved, and all 18 misses were 117th/116th Congress — real
  votes outside the covered window, where an emitted id would be a link to a `/v/` page that
  was never built. `rollcall_id_for()` mirrors `house_votes.rollcall_id` exactly, zero padding
  included, and is tested against it.
  **Verified live, per the task-2 rule that synthetic tests cannot catch a wrong premise:**
  `parse_actions` over the real NDAA timeline returns 234 of 234 rows, links 18 roll calls,
  and keeps all seven subcommittee-forwarding rows distinct.
  **(5) `date` is tightened past the house `fromisoformat` convention, deliberately.** The
  timeline is ordered by STRING comparison on this field, and bare `_date.fromisoformat`
  accepts the ISO basic form `20230613` and week dates `2023-W24-2` on Python 3.11+ (both
  verified live on 3.12.13). Both parse to a real date and then sort wrong, so a mixed-format
  timeline would render silently out of order rather than fail. `BillAction.date` therefore
  requires the extended `YYYY-MM-DD` form explicitly. **Found, not fixed, elsewhere:**
  `Statement.date` (models.py ~line 498) has the same gap and its own comment says ordering is
  exactly what it is protecting. Not changed here — different increment, and there are zero
  committed statements today. The owner or a later increment decides.
  **(6) `committees` stores names only.** The raw rows also carry `systemCode` (e.g. `hsas35`),
  the stable join key if per-committee pages ever exist; not stored today because nothing reads
  it, and it is one line to add when something does.
  **Acceptance:** ruff clean, pytest **416 passed** (386 + 30 new: 24 written before the date
  tightening, which added 6 more), `uv run checks` ALL CHECKS PASSED, schema regenerated and
  byte-stable. No `data/bills/*.json` file changes yet — the timeline lands when task 4
  re-exports.
