"""api.govinfo.gov source (§3). Auth: X-Api-Key header, same api.data.gov key
as Congress.gov (verified in the INC-1 spike — one key covers both).

Two roles:
  * CREC full-text search (INC-6): the `/search` endpoint DOES support full-text
    queries the Congress.gov `/congressional-record` index cannot — so the
    "personal explanation" candidate extraction has a real source. Each hit
    carries `packageId`, `granuleId`, and `download.txtLink` (the granule text)
    + `modsLink` (metadata) for excerpt + page-URL capture.
  * Bill text versions (USLM XML) for the INC-19 diff viewer — added there.

`/search` is a POST with a JSON body; this module caches it with a key derived
from the request body only (no credential on disk), mirroring cache.py's contract.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import httpx

from ingest import env
from ingest.cache import _USER_AGENT, RAW_DIR, fetch

SOURCE = "govinfo"
SEARCH_URL = "https://api.govinfo.gov/search"
GRANULE_HTM = "https://api.govinfo.gov/packages/{pkg}/granules/{granule}/htm"


def _headers() -> dict[str, str]:
    return {"X-Api-Key": env.require("CONGRESS_API_KEY"), "User-Agent": _USER_AGENT}


def _cached_post(url: str, body: dict) -> dict:
    """POST `body` to `url`, caching on sha256(url+body). The key never enters
    the cache key or `.meta` (header-auth); body is credential-free."""
    canonical = url + json.dumps(body, sort_keys=True)
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    data_path = RAW_DIR / SOURCE / f"{digest}.json"
    meta_path = RAW_DIR / SOURCE / f"{digest}.meta"
    if data_path.exists():
        return json.loads(data_path.read_text(encoding="utf-8"))

    resp = httpx.post(url, headers=_headers(), json=body, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(resp.text, encoding="utf-8", newline="\n")
    meta_path.write_text(
        json.dumps(
            {"url": url, "body": body, "fetched_at": datetime.now(UTC).isoformat(),
             "status": resp.status_code},
            indent=2, sort_keys=True,
        ),
        encoding="utf-8", newline="\n",
    )
    return json.loads(resp.text)


def crec_search(phrase: str, page_size: int = 20) -> dict:
    """Full-text search the Congressional Record (CREC) for an exact phrase.
    Returns govinfo's `{count, offsetMark, results:[{title, packageId, granuleId,
    dateIssued, download:{txtLink, modsLink, ...}}]}`."""
    body = {
        "query": f'"{phrase}" collection:CREC',
        "pageSize": page_size,
        "offsetMark": "*",
        "sorts": [{"field": "publishdate", "sortOrder": "DESC"}],
    }
    return _cached_post(SEARCH_URL, body)


def crec_personal_explanations(state_name: str, start: str, end: str, page_size: int = 50) -> dict:
    """CREC "Personal Explanation" insertions for one state's delegation over a
    date window. Scoping to the granule TITLE ("Personal Explanation") + the byline
    phrase ("of {state}") is what separates a real personal-explanation insertion
    (a member stating how they would have voted on a missed roll) from the phrase
    merely appearing in floor debate — and it cuts wrong-state surname collisions
    (e.g. Thompson of Mississippi vs. Thompson of Pennsylvania) at the search layer.
    The caller still hard-verifies the byline per granule (INC-6)."""
    body = {
        "query": (
            f'title:"Personal Explanation" "of {state_name}" '
            f"collection:CREC publishdate:range({start},{end})"
        ),
        "pageSize": page_size,
        "offsetMark": "*",
        "sorts": [{"field": "publishdate", "sortOrder": "DESC"}],
    }
    return _cached_post(SEARCH_URL, body)


def granule_text(package_id: str, granule_id: str) -> str:
    """The granule's text (htm) — header-auth, so the key never enters the URL or
    the disk cache key (cache.py contract)."""
    url = GRANULE_HTM.format(pkg=package_id, granule=granule_id)
    return fetch(SOURCE, url, ext="htm", headers=_headers()).text


def granule_url(package_id: str, granule_id: str) -> str:
    """The stable PUBLIC citation for a granule (verified 200): the govinfo details
    page. This is what a published `stated_reason_source` points a reader to."""
    return f"https://www.govinfo.gov/app/details/{package_id}/{granule_id}"
