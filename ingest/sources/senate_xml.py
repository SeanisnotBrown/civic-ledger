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

from ingest.cache import CachedResponse, fetch

BASE = "https://www.senate.gov/legislative/LIS"
SOURCE = "senate_xml"


def vote_menu(congress: int, session: int) -> CachedResponse:
    url = f"{BASE}/roll_call_lists/vote_menu_{congress}_{session}.xml"
    return fetch(SOURCE, url, ext="xml")


def vote_detail(congress: int, session: int, roll: int) -> CachedResponse:
    padded = f"{roll:05d}"
    url = f"{BASE}/roll_call_votes/vote{congress}{session}/vote_{congress}_{session}_{padded}.xml"
    return fetch(SOURCE, url, ext="xml")
