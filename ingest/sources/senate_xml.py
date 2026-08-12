"""senate.gov LIS roll-call XML source (§3, D6). No auth key.

VERIFIED paths (INC-1 spike) — the menu and detail live in DIFFERENT dirs:
  * Menu:   /legislative/LIS/roll_call_lists/vote_menu_{c}_{s}.xml
  * Detail: /legislative/LIS/roll_call_votes/vote{c}{s}/vote_{c}_{s}_{NNNNN}.xml
    ({c}=congress, {s}=session, {NNNNN} = 5-digit zero-padded roll number).

The spec's assumed `roll_call_votes/vote{cc}{s}/vote_menu_…` path 301-redirects
to a "roll-call-vote-not-available" HTML page — do not use it (SHAPES.md).

Detail member blocks carry `lis_member_id` (e.g. "S428"), NOT bioguide; INC-4
maps it via the congress-legislators crosswalk.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ingest.cache import CachedResponse, fetch

BASE = "https://www.senate.gov/legislative/LIS"
SOURCE = "senate_xml"

# Detail <vote_cast> → canonical position (SHAPES §6). Senate ballots are always
# Yea/Nay/Present/Not Voting — there is no Aye/No form (that is a House
# Committee-of-the-Whole artifact) and no candidate-surname form, so anything
# outside this map is data corruption, not scope, and quarantines the roll.
VOTE_MAP: dict[str, str] = {
    "Yea": "yea",
    "Nay": "nay",
    "Present": "present",
    "Not Voting": "not_voting",
}


def vote_menu(congress: int, session: int) -> CachedResponse:
    url = f"{BASE}/roll_call_lists/vote_menu_{congress}_{session}.xml"
    return fetch(SOURCE, url, ext="xml")


def detail_url(congress: int, session: int, roll: int) -> str:
    padded = f"{roll:05d}"
    return f"{BASE}/roll_call_votes/vote{congress}{session}/vote_{congress}_{session}_{padded}.xml"


def vote_detail(congress: int, session: int, roll: int) -> CachedResponse:
    return fetch(SOURCE, detail_url(congress, session, roll), ext="xml")


def _int_or_none(text: str | None) -> int | None:
    text = (text or "").strip()
    return int(text) if text.isdigit() else None


def parse_menu(xml_text: str) -> dict[int, tuple[int | None, int | None]]:
    """Parse a `vote_menu_{c}_{s}.xml` into {roll number: (yeas, nays)}.

    The menu's per-vote `vote_tally` is the INDEPENDENT cross-source total (a
    different file from the detail): the ingest requires the detail's
    member-computed yea/nay to match this. `(None, None)` where a vote carries no
    tally (nothing to cross-check). Senate rolls are numbered 1..N contiguously,
    so the key set doubles as the completeness oracle."""
    root = ET.fromstring(xml_text)
    out: dict[int, tuple[int | None, int | None]] = {}
    for v in root.iter("vote"):
        num = _int_or_none(v.findtext("vote_number"))
        if num is None:
            continue
        tally = v.find("vote_tally")
        yeas = nays = None
        if tally is not None:
            yeas = _int_or_none(tally.findtext("yeas"))
            nays = _int_or_none(tally.findtext("nays"))
        out[num] = (yeas, nays)
    return out


def parse_positions(
    detail_xml: str, lis_to_bioguide: dict[str, str], state: str | None = None
) -> dict[str, str]:
    """bioguide → canonical position from a detail XML, joining `lis_member_id`
    through the crosswalk. `state` filters to one delegation (e.g. "MS"). The
    independent re-parse used by `checks/integrity.py`; an unmapped `vote_cast`
    is kept raw so a mismatch surfaces rather than silently maps."""
    root = ET.fromstring(detail_xml)
    out: dict[str, str] = {}
    for m in root.iter("member"):
        if state is not None and (m.findtext("state") or "").strip() != state:
            continue
        lis = (m.findtext("lis_member_id") or "").strip()
        bioguide = lis_to_bioguide.get(lis)
        if bioguide is None:
            continue
        raw = (m.findtext("vote_cast") or "").strip()
        out[bioguide] = VOTE_MAP.get(raw, raw)
    return out
