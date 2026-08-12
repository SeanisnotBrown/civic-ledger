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
