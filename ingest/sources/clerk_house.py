"""clerk.house.gov roll-call XML source (§3, D6).

Two roles (per Decision D6): (a) fallback if the Congress.gov `house-vote` beta
path is unavailable, (b) the INDEPENDENT integrity cross-check source for INC-3
(`checks/integrity.py` re-fetches a sample and requires exact position matches).

The Congress.gov house-vote list conveniently returns each vote's clerk URL as
`sourceDataURL`, so callers usually pass that through directly. The canonical
form is https://clerk.house.gov/evs/{year}/roll{NNN}.xml (roll zero-padded to 3).
This module is a thin fetcher now; INC-3 adds the parser + cross-check logic.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ingest.cache import CachedResponse, fetch

SOURCE = "clerk_house"

# Clerk XML <vote> strings → canonical position enum (matches the API mapping).
_VOTE_MAP: dict[str, str] = {
    "Yea": "yea",
    "Aye": "yea",  # clerk uses Aye/No on "Yea-And-Nay" vs "Recorded Vote" ballots
    "Nay": "nay",
    "No": "nay",
    "Present": "present",
    "Not Voting": "not_voting",
}


def roll_xml(year: int, roll: int) -> CachedResponse:
    url = f"https://clerk.house.gov/evs/{year}/roll{roll:03d}.xml"
    return fetch(SOURCE, url, ext="xml")


def roll_xml_url(url: str) -> CachedResponse:
    """Fetch a clerk roll XML by its exact URL (e.g. Congress.gov `sourceDataURL`)."""
    return fetch(SOURCE, url, ext="xml")


def parse_positions(xml_text: str, state: str | None = None) -> dict[str, str]:
    """bioguide (`name-id`) → canonical position from a clerk roll XML.

    The INDEPENDENT integrity source (D6): `checks/integrity.py` re-fetches a
    sampled roll here and requires exact per-member agreement with the Congress.gov
    positions. `state` filters to one delegation (e.g. "MS") when given.
    """
    root = ET.fromstring(xml_text)
    out: dict[str, str] = {}
    for rv in root.iter("recorded-vote"):
        leg = rv.find("legislator")
        vote = rv.find("vote")
        if leg is None or vote is None:
            continue
        if state is not None and leg.get("state") != state:
            continue
        bioguide = leg.get("name-id")
        raw = (vote.text or "").strip()
        if bioguide is None:
            continue
        out[bioguide] = _VOTE_MAP.get(raw, raw)  # unmapped kept raw → mismatch surfaces
    return out
