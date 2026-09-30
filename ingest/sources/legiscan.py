"""LegiScan API source — Mississippi state layer (§7 INC-1 step 4, INC-12 branch A).

Built as a callable code path per §0.2 ("build the code path, stub the credential")
even while H2 (LEGISCAN_API_KEY) is pending. When the key is absent, the INC-1
state-branch verdict is DEFER (Decision D18) and nothing here runs in the federal
build.

Auth: LegiScan takes the key as a query param (`key=`), which is unavoidable per
its API. To keep the key out of the cache key and the `.meta` sidecar, this module
uses its own fetch (`_get`) that computes the cache key and writes the meta from
op+params ONLY — the secret is added to the live request and to nothing on disk.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import httpx

from ingest import env
from ingest.cache import _USER_AGENT, DEFAULT_TTL_HOURS, RAW_DIR

BASE = "https://api.legiscan.com/"
SOURCE = "legiscan"


class LegiScanHTTPError(Exception):
    """A non-2xx from LegiScan, carrying the op + status but NOT the request URL.

    `httpx.HTTPStatusError`'s message is `"... for url '{response.url}'"`, and because
    LegiScan requires the key as a query param that URL contains `key=<secret>`. Raising
    our own type keeps the key out of tracebacks and out of any log the owner pastes when
    asking for help — the same guarantee the module docstring makes for the cache.
    """


def available() -> bool:
    """True if a LegiScan key is configured (H2 done)."""
    return bool(env.get("LEGISCAN_API_KEY"))


def _is_fresh(meta_path, ttl_hours: float) -> bool:
    """True if a cached `.meta` sidecar's `fetched_at` is within `ttl_hours`."""
    if not meta_path.exists():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(meta["fetched_at"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return False
    age_h = (datetime.now(UTC) - fetched).total_seconds() / 3600.0
    return age_h < ttl_hours


def _get(op: str, ttl_hours: float | None = None, **params) -> dict:
    """Call a LegiScan operation through a TTL'd disk cache (D52; the spike's uncached
    `_get` re-fetched — and re-counted quota — on every call). A cached response within
    `ttl_hours` (default `DEFAULT_TTL_HOURS`, `CIVIC_CACHE_TTL_HOURS`-overridable) is
    read from disk. The key is added ONLY to the live request, never to the cache key
    or the `.meta` (LegiScan requires the key as a query param)."""
    ttl = DEFAULT_TTL_HOURS if ttl_hours is None else ttl_hours
    query = {"op": op, **{k: str(v) for k, v in params.items()}}
    # Cache key derives from op+params WITHOUT the secret.
    canonical = op + "?" + "&".join(f"{k}={v}" for k, v in sorted(query.items()))
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    data_path = RAW_DIR / SOURCE / f"{digest}.json"
    meta_path = RAW_DIR / SOURCE / f"{digest}.meta"

    if _is_fresh(meta_path, ttl) and data_path.exists():
        return json.loads(data_path.read_text(encoding="utf-8"))

    key = env.require("LEGISCAN_API_KEY")
    resp = httpx.get(
        BASE,
        params={**query, "key": key},
        headers={"User-Agent": _USER_AGENT},
        timeout=60,
        follow_redirects=True,
    )
    if resp.status_code >= 400:
        # NOT raise_for_status(): its message embeds the URL, hence `key=<secret>`.
        raise LegiScanHTTPError(f"LegiScan {op} returned HTTP {resp.status_code}")
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(resp.text, encoding="utf-8", newline="\n")
    meta_path.write_text(
        json.dumps(
            {"op": op, "params": query, "fetched_at": datetime.now(UTC).isoformat(),
             "status": resp.status_code},
            indent=2, sort_keys=True,
        ),
        encoding="utf-8", newline="\n",
    )
    return json.loads(resp.text)


def session_list(state: str = "MS") -> dict:
    return _get("getSessionList", state=state)


def dataset_list(state: str = "MS") -> dict:
    return _get("getDatasetList", state=state)


def get_dataset(session_id: int, access_key: str) -> dict:
    return _get("getDataset", id=session_id, access_key=access_key)
