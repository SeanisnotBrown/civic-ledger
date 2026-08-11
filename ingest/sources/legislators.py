"""unitedstates/congress-legislators source (§3) + the raw→`Member` parser.

This is the canonical ID crosswalk (bioguide ↔ govtrack, fec, opensecrets, lis,
thomas…) that every later module joins against, and the source of truth for
chamber and full term/party history — the Congress.gov member endpoint's
`terms.item` is too sparse (SHAPES §1, §7).

Fetched from the project's raw GitHub content (YAML, no auth), cached like any
other source. `legislators-current.yaml` holds only currently-serving members;
INC-1 committed a 6-entry MS excerpt into data/quality/samples/ for offline tests.

Parsing rules (D20):
  * party full word → "D"|"R"|"I" via `party_code` (shared with INC-3's voteParty).
  * `type` "sen"|"rep" → chamber "senate"|"house"; `district` from House terms.
  * `ids` = a curated string crosswalk; the multi-valued `fec` list is comma-joined
    to honor §5's `dict[str, str]`. `legiscan` is absent upstream (added only if
    INC-12 branch A is ever built).
  * `serving` = the member's latest term overlaps the latest covered Congress —
    a deterministic definition with no wall-clock (§6.3).
Covered-set filtering runs on the RAW dicts before Member construction, so an
exotic party string on some non-covered historical member can never crash the
MS ingest.
"""

from __future__ import annotations

from ingest.cache import CachedResponse, fetch
from ingest.models import Member, Term

CURRENT_URL = (
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
    "legislators-current.yaml"
)
SOURCE = "legislators"

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


def is_covered(entry: dict, congresses: list[int], state: str) -> bool:
    """Covered = most recent term is in `state` AND some term overlaps a covered
    Congress. Runs on the raw dict, before Member validation."""
    terms = entry.get("terms") or []
    if not terms or terms[-1].get("state") != state:
        return False
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


def covered_members(raw: list[dict], congresses: list[int], state: str) -> list[Member]:
    """Filter raw congress-legislators entries to the covered delegation, then
    construct validated `Member`s. Returns them sorted by bioguide id (stable
    export order). Filter-before-construct is load-bearing (see module docstring)."""
    members = [
        _to_member(entry, congresses)
        for entry in raw
        if is_covered(entry, congresses, state)
    ]
    return sorted(members, key=lambda m: m.id)
