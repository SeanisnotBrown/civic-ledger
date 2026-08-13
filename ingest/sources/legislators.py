"""unitedstates/congress-legislators source (§3) + the raw→`Member` parser.

This is the canonical ID crosswalk (bioguide ↔ govtrack, fec, opensecrets, lis,
thomas…) that every later module joins against, and the source of truth for
chamber and full term/party history — the Congress.gov member endpoint's
`terms.item` is too sparse (SHAPES §1, §7).

Fetched from the project's raw GitHub content (YAML, no auth), cached like any
other source. `legislators-current.yaml` holds only CURRENTLY-serving members —
by itself it is insufficient for full 118th+119th coverage (V2-1): a member who
served the 118th but left office before the 119th (retired, lost, died, resigned,
expelled) never appears in it at all, and — because `data/members/*.json` is the
same source every coverage/gap check reads — that member would be invisible to
every check too, not merely absent: `expected` and `got` would both silently
exclude them, so a real gap would read as green (D60). `legislators-historical.yaml`
(the companion file, ~9 MB, verified live 2026-08-13) carries everyone else back to
1789; V2-1 fetches BOTH and merges by bioguide id before filtering, so anyone whose
term overlapped 118 or 119 is covered regardless of whether they still hold office
today. INC-1 committed a 6-entry MS excerpt into data/quality/samples/ for offline
tests (current-only; unaffected by this change since it's a fixture, not fetched).

Parsing rules (D20):
  * party full word → "D"|"R"|"I" via `party_code` (shared with INC-3's voteParty).
  * `type` "sen"|"rep" → chamber "senate"|"house"; `district` from House terms.
  * `ids` = a curated string crosswalk; the multi-valued `fec` list is comma-joined
    to honor §5's `dict[str, str]`. `legiscan` is absent upstream (added only if
    INC-12 branch A is ever built).
  * `serving` = the member's latest term overlaps the latest covered Congress —
    a deterministic definition with no wall-clock (§6.3). A departed 118th-only
    member has `serving=False`; callers must render/count that deliberately.
Covered-set filtering runs on the RAW dicts before Member construction, so an
exotic party string on some non-covered historical member can never crash the
federal ingest.

Delegate scope (V2-1, D61 — supersedes D60): the covered set is every House and
Senate seat, INCLUDING the 6 non-voting House delegates (DC, PR, GU, AS, VI, MP).
D60 first excluded them; the owner reversed that once excluding them was found to
break full recomputability (delegates cast real recorded votes on ~1/3 of House
rolls — Committee of the Whole — so omitting them made `RollCall.totals`
permanently non-reproducible from `member_votes` on every such roll). `VOTING_STATES`
stays defined below, repurposed from a roster FILTER into a delegate-DETECTION set:
`ingest/coverage.py` uses it to keep delegates out of the "expected on every roll"
set (they are constitutionally barred from final-passage rolls — a structural fact,
not a customary one, same mechanism as the Speaker's customary non-voting).
"""

from __future__ import annotations

from ingest.cache import CachedResponse, fetch
from ingest.models import Member, Term

CURRENT_URL = (
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
    "legislators-current.yaml"
)
HISTORICAL_URL = (
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
    "legislators-historical.yaml"
)
SOURCE = "legislators"

# The 50 states' USPS postal codes — deliberately excludes DC + the 5 territories
# (AS, GU, MP, PR, VI), whose House seats are non-voting delegates. Used by
# ingest/coverage.py to detect delegates (D61) — no longer a roster filter here.
VOTING_STATES: frozenset[str] = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
})

# Curated crosswalk keys pulled into Member.ids, present-only. bioguide is
# omitted (it IS Member.id); google_entity_id/wikidata/etc. are research chrome.
CROSSWALK_KEYS: tuple[str, ...] = (
    "govtrack",
    "lis",
    "fec",
    "opensecrets",
    "thomas",
    "icpsr",
)

_PARTY_CODES: dict[str, str] = {
    "Republican": "R",
    "Democrat": "D",  # congress-legislators spelling
    "Democratic": "D",  # Congress.gov spelling (INC-3 voteParty reuse)
    "Independent": "I",
}

_CHAMBER: dict[str, str] = {"sen": "senate", "rep": "house"}


def current() -> CachedResponse:
    return fetch(SOURCE, CURRENT_URL, ext="yaml")


def historical() -> CachedResponse:
    return fetch(SOURCE, HISTORICAL_URL, ext="yaml")


def merge_raw(current_raw: list[dict], historical_raw: list[dict]) -> list[dict]:
    """Union of both rosters by bioguide id. The two upstream files are already
    disjoint by convention (a person moves from -current to -historical once they
    leave office), but a currently-serving entry wins any id collision — it is
    the fresher record and 'serving' is computed from it."""
    by_id = {e["id"]["bioguide"]: e for e in historical_raw}
    by_id.update({e["id"]["bioguide"]: e for e in current_raw})
    return list(by_id.values())


def party_code(word: str) -> str:
    """Full party word → canonical "D"|"R"|"I". Raises on anything unmapped so
    the record lands in quarantine (§6.1) rather than exporting a wrong party."""
    try:
        return _PARTY_CODES[word]
    except KeyError as exc:
        raise ValueError(f"unmapped party {word!r}") from exc


def congress_window(congress: int) -> tuple[str, str]:
    """(start, end) ISO dates for a Congress. 119th began 2025-01-03; each runs
    two years. Deterministic, no wall-clock (§6.3)."""
    start_year = 1789 + 2 * (congress - 1)
    return f"{start_year}-01-03", f"{start_year + 2}-01-03"


def _term_overlaps(term: dict, congress: int) -> bool:
    win_start, win_end = congress_window(congress)
    # Strict inequalities: a term ending exactly when a Congress begins belongs
    # to the previous Congress, not this one.
    return term["start"] < win_end and term["end"] > win_start


def _crosswalk(raw_id: dict) -> dict[str, str]:
    ids: dict[str, str] = {}
    for key in CROSSWALK_KEYS:
        val = raw_id.get(key)
        if val is None:
            continue
        ids[key] = ",".join(str(v) for v in val) if isinstance(val, list) else str(val)
    return ids


def is_covered(entry: dict, congresses: list[int]) -> bool:
    """Covered = some term overlaps a covered Congress (D61: every House and
    Senate seat, including the 6 non-voting delegates). Runs on the raw dict,
    before Member validation."""
    terms = entry.get("terms") or []
    return any(_term_overlaps(t, c) for t in terms for c in congresses)


def _to_member(entry: dict, congresses: list[int]) -> Member:
    latest = entry["terms"][-1]
    name = entry["name"]
    display = name.get("official_full") or f"{name['first']} {name['last']}"
    chamber = _CHAMBER[latest["type"]]

    terms = [
        Term(
            start=t["start"],
            end=t["end"],
            party=party_code(t["party"]),
            chamber=_CHAMBER[t["type"]],
        )
        for t in sorted(entry["terms"], key=lambda t: (t["start"], t["end"]))
    ]
    latest_congress = max(congresses)
    return Member(
        id=entry["id"]["bioguide"],
        ids=_crosswalk(entry["id"]),
        name=display,
        party=party_code(latest["party"]),
        state=latest["state"],
        district=latest.get("district") if chamber == "house" else None,
        chamber=chamber,
        serving=_term_overlaps(latest, latest_congress),
        terms=terms,
    )


def covered_members(raw: list[dict], congresses: list[int]) -> list[Member]:
    """Filter raw congress-legislators entries (current+historical merged, see
    `merge_raw`) to the covered set — every member of both chambers, including
    the 6 non-voting delegates (D61), who served a covered Congress — then
    construct validated `Member`s. Returns them sorted by bioguide id (stable
    export order). Filter-before-construct is load-bearing (see module docstring)."""
    members = [
        _to_member(entry, congresses)
        for entry in raw
        if is_covered(entry, congresses)
    ]
    return sorted(members, key=lambda m: m.id)
