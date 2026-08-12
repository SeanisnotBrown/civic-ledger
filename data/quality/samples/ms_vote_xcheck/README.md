# MS LegiScan → official-record cross-check (INC-1 GO gate)

Evidence for flipping the Mississippi state-layer verdict **DEFER → GO**
(`../../ms-state-verdict.md`, D21). Captured 2026-08-11 against the **2026 MS
Regular Session** (LegiScan `session_id` 2249).

## What this proves

For 5 sampled roll calls, **every** per-person position LegiScan reports matches
the official Mississippi Legislature roll-call record — **470 individual member
positions checked (3×122 House + 2×52 Senate), zero genuine mismatches**, with
vote totals tying out in both directions.

**Scope honesty:** LegiScan *scrapes* `billstatus.ls.state.ms.us`, so this
verifies **scrape fidelity against the official record** — exactly the risk
INC-12 carries — not agreement between two independent origins. The billstatus
per-vote PDF is the primary roll-call record the bound House/Senate Journal
reprints (the SoS publishes the bound Journal, e.g. `MS HOUSE JOURNAL V1 2025`);
we use the per-vote PDF as the cleaner, page-addressable form of the same record.

## The 5 sampled votes (all contested → per-person matching is meaningful)

| Bill | Chamber | roll_call_id | LegiScan | Official PDF (`billstatus.ls.state.ms.us/2026/pdf/votes/...`) | Result |
|------|---------|--------------|----------|-----------------|--------|
| HB2    | House  | 1614160 | Y61 N59 NV2  | `house/0100010.pdf`  | ✅ 122/122 |
| SB2436 | House  | 1659549 | Y50 N60 NV12 | `house/0640013.pdf`  | ✅ 122/122 |
| HB362  | House  | 1630454 | Y64 N51 NV7  | `house/0370008.pdf`  | ✅ 122/122 |
| SB2232 | Senate | 1625251 | Y26 N26 NV0  | `senate/0310054.pdf` | ✅ 52/52 (26–26 tie, failed) |
| SB2587 | Senate | 1632993 | Y24 N25 NV3  | `senate/0380042.pdf` | ✅ 52/52 |

Each `{tag}.pdf` is the verbatim official record; `{tag}.txt` is the pypdf text
extraction used for the comparison.

## Reconciliation rules (needed again when INC-12 branch A is built)

The PDFs are **born-digital and text-extractable** (pypdf, ~1.5–2 KB text each);
they list members by surname in `Yeas--` / `Nays--` / `Absent or those not
voting--` (and, House only, `Present--`) buckets ending `Total--N`. Mapping those
surname tokens back to LegiScan `people_id`s required:

1. **NV equivalence:** LegiScan `vote_text` ∈ {Yea, Nay, **NV**} only. The
   PDF's `Absent or those not voting` **∪** `Present` buckets = LegiScan NV.
   (House uses a separate `Present--` bucket; Senate did not in these samples.)
2. **Duplicate surnames → district ordinal.** The PDF disambiguates collisions
   as `Anderson (110th)` / `Anderson (122nd)`; match on the ordinal vs LegiScan
   `district` (`HD-110` → 110). The ordinal is the reliable key even when the PDF
   also adds initials (`Simmons D. T. (12th)` → SD-012).
3. **Compound / hyphenated surnames.** The PDF prints either the full compound
   (`Gillespie Isom`, `Butler-Washington`) **or only the final component**
   (`McGee` for LegiScan `Warren McGee`; `McCray` for `Jackson-McCray`). Match on
   full last name OR its final word, splitting on space **and** hyphen; a
   uniqueness guard rejects ambiguous matches (a real collision would carry an
   ordinal).
4. **`Mr. Speaker`.** The House Speaker (Jason White, HD-048) is listed as
   `Mr. Speaker`, never by surname. Auto-detected as the single roster member
   left unassigned after all other tokens resolve — verified unique on all 3
   House votes. (Senate: the Lt. Governor presides but is not a member, so no
   analogous token.)
5. **Suffixes / initials** (`Creekmore IV`, `Simmons D. T.`) are stripped before
   surname matching.

**Checksums (both directions):** parsed bucket sizes must equal the PDF
`Total--N` line **and** LegiScan yea/nay/(nv+absent) counts before any per-person
comparison; any unmatched token is printed and resolved by hand, never
fuzzy-matched silently.

## Provenance / deviations

- LegiScan source: `getDataset(session_id=2249)` (one call; the whole session).
- `billstatus.ls.state.ms.us` serves an **incomplete TLS chain** (omits the
  intermediate); fetched via the OS trust store (AIA chasing). INC-12's fetcher
  must bundle the intermediate CA — CI runs Linux, which does **not** do AIA
  chasing. See D21 in `../../../docs/decisions.md`.
