"""unitedstates/congress-legislators source (§3). The canonical ID crosswalk
(bioguide ↔ govtrack, fec, opensecrets, lis, thomas…) used across every module.

Fetched from the project's raw GitHub content. YAML, no auth. Cached like any
other source; the full file is large, so INC-1 excerpts only the covered-state
delegation into the committed samples (SHAPES.md documents the excerpting).
"""

from __future__ import annotations

from ingest.cache import CachedResponse, fetch

CURRENT_URL = (
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
    "legislators-current.yaml"
)
SOURCE = "legislators"


def current() -> CachedResponse:
    return fetch(SOURCE, CURRENT_URL, ext="yaml")
