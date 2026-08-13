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
