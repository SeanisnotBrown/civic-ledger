# Mississippi state-layer verdict (INC-1 step 4/5)

## Verdict: **GO** — LegiScan carries accurate per-person MS positions; INC-12 branch A is unlocked

Recorded 2026-08-11 (spike); **upgraded DEFER → GO on 2026-08-11** after the
owner elected to run the Journal cross-check now (PROGRESS.md option A) rather
than fold it into INC-12. The 5-bill position match against the official MS
roll-call record **passed 5/5**. Per Decision D18/§0.4 the build order is
unchanged — the federal MVP proceeds; **INC-12 branch A activates when reached**,
not before.

## Evidence (INC-1 step 4)

| Test (§7 INC-1 step 4) | Result |
|---|---|
| `LEGISCAN_API_KEY` present? | **Yes** (H2 completed 2026-08-11) |
| `getSessionList(MS)` reachable | **Yes** — 2026 Regular Session (`session_id` 2249). Sample: `samples/legiscan_session_list_ms.json` |
| `roll_call` carries per-person positions w/ resolvable `people_id`? | **Yes** — `getDataset(2249)` → 1,725 roll calls, **every one** with full per-person `votes[]` of `{people_id, vote_text}`; 174-person masterlist resolves ids (incl. `bioguide_id`, `district`, `party`) |
| **5-bill position match vs official chamber record** | ✅ **5/5** — 470 per-person positions (3×122 House + 2×52 Senate), **zero genuine mismatches**; counts tie out both directions. Evidence + methodology: `samples/ms_vote_xcheck/` |

The 5 sampled votes were all **contested** (HB2 61–59, SB2436 50–60, HB362
64–51, SB2232 26–26 tie, SB2587 24–25) and span both chambers, so the per-person
agreement is meaningful, not an artifact of unanimous votes. Full per-vote table,
PDF links, and the surname-reconciliation rules are in
`samples/ms_vote_xcheck/README.md`.

## Ground-truth choice (D21) — what GO does and does not prove

The comparison uses the official MS **per-vote roll-call PDF**
(`billstatus.ls.state.ms.us/2026/pdf/votes/{chamber}/{n}.pdf`), which is the
primary record the bound House/Senate Journal reprints — not the multi-hundred-
page bound Journal PDF the spec's wording named. This is the authoritative MS
record and is page-addressable per vote. Because **LegiScan scrapes billstatus**,
GO establishes **scrape fidelity against the official record** (exactly the risk
INC-12 carries), not agreement between two independent data origins. That is
sufficient for the gate's intent (§0.4: verify positions are correct before
building on them).

## What is already built

- `ingest/sources/legiscan.py` — callable path (`session_list`, `dataset_list`,
  `get_dataset`); key handled as a query param kept out of the cache key and
  `.meta` sidecar (verified: no key on disk).
- `ingest/spike.py::_run_state_verdict()` captures `getSessionList(MS)` whenever a
  key is present.

## Carried-forward notes for INC-12 branch A

1. **TLS:** `billstatus.ls.state.ms.us` serves an incomplete cert chain (omits
   the intermediate). The spike fetched via the OS trust store (AIA chasing);
   CI/Linux does not chase AIA, so INC-12's fetcher must **bundle the
   intermediate CA**. (D21)
2. **`legiscan._get` has no TTL/cache-freshness check** — every call is a live
   request (unlike `cache.fetch`). Fine for a one-shot spike; INC-12 should route
   LegiScan through a TTL'd cache path. (Logged in decisions.md.)
3. **Reconciliation rules** (NV = Absent∪Present, district-ordinal collisions,
   compound/hyphenated surnames, `Mr. Speaker` auto-detect, checksums both
   directions) are documented in `samples/ms_vote_xcheck/README.md` — reuse them
   for the branch-A ingest's own integrity check.
