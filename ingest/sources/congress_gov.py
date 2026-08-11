"""api.congress.gov v3 source (§3, D6). Auth: X-Api-Key header (never in URL).

Endpoints are the ones VERIFIED in the INC-1 spike, not the spec's assumptions:
  * Members by state is a PATH segment `/member/{stateCode}`, NOT a query param.
    The `?stateCode=` query form returns 503 (recorded in SHAPES.md + decisions).
  * House votes use the beta `/house-vote/{congress}/{session}` family; the list
    response carries each vote's clerk XML `sourceDataURL` for cross-checking.
  * Member positions live at `/house-vote/{c}/{s}/{roll}/members`, where the id
    field is `bioguideID` (capital ID) — the member-list endpoint uses `bioguideId`.

Every fetch is cached (ingest/cache.py). Rate ceiling ≤ 1 req/sec is enforced
there per host.
"""

from __future__ import annotations

from ingest import env
from ingest.cache import CachedResponse, fetch

BASE = "https://api.congress.gov/v3"
SOURCE = "congress_gov"


def _headers() -> dict[str, str]:
    # Header-only auth; the key never enters a URL, param, or cache key.
    return {"X-Api-Key": env.require("CONGRESS_API_KEY")}


def _get(path: str, params: dict | None = None, **kw) -> CachedResponse:
    p = {"format": "json"}
    if params:
        p.update(params)
    return fetch(SOURCE, f"{BASE}/{path.lstrip('/')}", params=p, headers=_headers(), **kw)


# --- Members --------------------------------------------------------------
def members_by_state(state: str, current_only: bool = True, limit: int = 250) -> CachedResponse:
    params = {"limit": str(limit)}
    if current_only:
        params["currentMember"] = "true"
    return _get(f"member/{state}", params)


# --- House votes (beta) ---------------------------------------------------
def house_vote_list(
    congress: int, session: int, limit: int = 250, offset: int = 0
) -> CachedResponse:
    return _get(f"house-vote/{congress}/{session}", {"limit": str(limit), "offset": str(offset)})


def house_vote_detail(congress: int, session: int, roll: int) -> CachedResponse:
    return _get(f"house-vote/{congress}/{session}/{roll}")


def house_vote_members(congress: int, session: int, roll: int) -> CachedResponse:
    return _get(f"house-vote/{congress}/{session}/{roll}/members")


# --- Bills ----------------------------------------------------------------
def bill_detail(congress: int, bill_type: str, number: int) -> CachedResponse:
    return _get(f"bill/{congress}/{bill_type.lower()}/{number}")


# --- Congressional Record (index; full-text search is an INC-6 concern) ---
def congressional_record(limit: int = 20, **params) -> CachedResponse:
    extra = {k: str(v) for k, v in params.items()}
    return _get("congressional-record", {"limit": str(limit), **extra})
