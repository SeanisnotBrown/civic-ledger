# Mississippi state-layer verdict (INC-1 step 4/5)

## Verdict: **DEFER** — but feasibility is GO-positive; sole remaining gate is the Journal cross-check (→ INC-12)

Recorded 2026-08-11. **H2 (LegiScan key) was completed mid-session**, so this
supersedes the earlier "DEFER because no key" reading. Per Decision D18 and §0.4
(ship the federal MVP first), the formal GO gate — a 5-bill position match against
MS Journal PDF excerpts — is **deferred to INC-12 branch A** (which the spec
already scopes to do a Journal spot-check). The federal build proceeds to INC-2
untouched.

## Evidence (INC-1 step 4)

| Test (§7 INC-1 step 4) | Result |
|---|---|
| `LEGISCAN_API_KEY` present? | **Yes** (H2 completed 2026-08-11) |
| `getSessionList(MS)` reachable | **Yes** — 2026 Regular Session (`session_id` 2249). Sample: `samples/legiscan_session_list_ms.json` |
| `roll_call` carries per-person positions w/ resolvable `people_id`? | **Yes** — `getRollCall` → `votes[]` of `{people_id, vote_id, vote_text}` (122 per-person votes on a sampled MS roll call); `people_id` resolves via `getPerson`/masterlist |
| 5-bill position match vs chamber Journal PDFs | **Not yet run** — deferred to INC-12 branch A (Journal PDF tractability unassessed; may be scanned) |

The core feasibility question the spike exists to answer — *does LegiScan carry
per-person MS positions with resolvable ids?* — is **YES**. The only reason the
verdict is DEFER rather than GO is the binary rule: GO requires the 5/5 Journal
cross-check, which is intentionally deferred to INC-12 (not blocking federal).

## What is already built

- `ingest/sources/legiscan.py` — callable path (`session_list`, `dataset_list`,
  `get_dataset`); key handled as a query param kept out of the cache key and
  `.meta` sidecar (verified: no key on disk).
- `ingest/spike.py::_run_state_verdict()` captures `getSessionList(MS)` whenever a
  key is present (it did, this session).

## To convert DEFER → GO (INC-12 branch A opener)

1. Sample 5 MS bills with recorded roll calls; pull `getRollCall` per-person
   positions.
2. Download 2 MS House/Senate Journal PDF excerpts covering those votes; compare
   per-person positions. **5-of-5 match = GO** → activate INC-12 branch A full
   ingest.
3. If Journal PDFs are scanned/untractable or any mismatch → verdict stays DEFER;
   run the Branch B parseability assessment + public `/methodology#mississippi`
   note (D18).
