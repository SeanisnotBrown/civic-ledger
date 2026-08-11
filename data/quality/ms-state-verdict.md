# Mississippi state-layer verdict (INC-1 step 4/5)

## Verdict: **DEFER**

Recorded 2026-08-11. Governs INC-12 (Decision D18): the DEFER branch activates
**as documentation only**; **no other increment changes**; the federal build
proceeds to INC-2 untouched.

## Why DEFER (evidence)

| Test (§7 INC-1 step 4) | Result |
|---|---|
| `LEGISCAN_API_KEY` present? | **No — H2 pending** at execution date |
| `getSessionList(MS)` reachable | Not run (no key) |
| `roll_call` records carry per-person positions w/ resolvable `people_id`? | Untested (no key) |
| 5-bill position match vs chamber Journal PDFs | Untested (no key) |

The verdict rule is explicit: the only outcomes are **GO** (LegiScan carries
positions, verified 5/5 against Journal PDFs) or **DEFER**; "if ambiguous, verdict
is DEFER (correctness outranks scope, §0.4)." With no key, GO cannot be
established, so the verdict is **DEFER** by rule — not a judgment that LegiScan
lacks the data, only that it is **unverified**.

## What is already built (so GO is a fast follow, per §0.2)

- `ingest/sources/legiscan.py` — callable code path (`session_list`,
  `dataset_list`, `get_dataset`), with the key handled as a query param that is
  kept out of the cache key and `.meta` sidecar.
- `.env.example` names `LEGISCAN_API_KEY`; `docs/HUMAN-TASKS.md` H2 has the
  registration instruction.
- `ingest/spike.py::_run_state_verdict()` runs the reachability step and writes
  `legiscan_session_list_ms.json` automatically **the moment a key is present** —
  re-run `uv run ingest spike` after H2 to gather the GO evidence.

## To convert DEFER → GO (owner)

1. Complete **H2** (register LegiScan free-tier key → `.env` + repo secret).
2. Re-run `uv run ingest spike`; it captures `getSessionList(MS)` and the current
   session dataset.
3. Sample 5 bills; compare `roll_call` per-person positions to the corresponding
   MS House/Senate Journal PDF pages (download 2 Journal excerpts). **5-of-5 match
   = GO**; update this file's verdict to GO and activate INC-12 branch A.
4. Any absence/unverifiability/ambiguity → the verdict stays **DEFER**.
