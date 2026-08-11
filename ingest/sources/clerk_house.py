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

from ingest.cache import CachedResponse, fetch

SOURCE = "clerk_house"


def roll_xml(year: int, roll: int) -> CachedResponse:
    url = f"https://clerk.house.gov/evs/{year}/roll{roll:03d}.xml"
    return fetch(SOURCE, url, ext="xml")


def roll_xml_url(url: str) -> CachedResponse:
    """Fetch a clerk roll XML by its exact URL (e.g. Congress.gov `sourceDataURL`)."""
    return fetch(SOURCE, url, ext="xml")
