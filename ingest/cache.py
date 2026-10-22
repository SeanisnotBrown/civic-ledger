"""Disk cache for every raw source fetch (§6.1, §6.2, §6.3).

Contract (all source modules fetch ONLY through `fetch()`):
  * Cache path: data/raw/{source}/{sha256(url+params)[:16]}.{ext} + a `.meta`
    sidecar recording {url, params, fetched_at, status, ext}.
  * Credentials NEVER enter the URL, the query params, or therefore the cache
    key or the `.meta` sidecar. Auth is header-only (`headers=`). This keeps the
    committed INC-1 samples and the on-disk meta free of secrets, and keeps the
    cache key stable across key rotation.
  * A cached URL is not re-fetched within `ttl_hours` (default 20h, §6.1). Pass
    `force=True` for the vote-detail <7-day exception, or `ttl_hours=0`.
  * Rate ceilings honored per host (§6.1): Congress.gov ≤ 1 req/sec sustained.
    A polite default interval applies to every other host.
  * Network failures retry with exponential backoff 2s→60s, 5 attempts
    (tenacity); `Retry-After` is honored on 429 before backoff.

`data/raw/` is gitignored — this is a dev convenience. The published dataset is
the exported JSON/YAML, not this cache.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


RAW_DIR = repo_root() / "data" / "raw"

# Per-host minimum seconds between live requests (§6.1). Congress.gov is the one
# with a hard published ceiling (≤ 1 req/sec sustained). Others get a polite 1s.
_HOST_MIN_INTERVAL: dict[str, float] = {
    "api.congress.gov": 1.0,
    "api.data.gov": 1.0,
}
_DEFAULT_MIN_INTERVAL = 1.0

# Wall-clock of the last live fetch per host, within this process run.
_last_fetch_at: dict[str, float] = {}

# Default cache freshness. `CIVIC_CACHE_TTL_HOURS` overrides it process-wide — used
# by one-time re-parses (e.g. the INC-10 party_totals backfill) to reuse the already
# cached raw responses instead of re-fetching, keeping the run offline and polite.
DEFAULT_TTL_HOURS = float(os.environ.get("CIVIC_CACHE_TTL_HOURS", "20"))
_HTTP_TIMEOUT = httpx.Timeout(30.0, connect=15.0)
_USER_AGENT = "civic-ledger/0.0 (+https://github.com/SeanisnotBrown/civic-ledger)"


def atomic_write_text(path: Path, text: str) -> Path:
    """Write `text` to `path` so that a kill or a power loss can never leave a
    PARTIAL file behind — the reader sees either the old bytes or the new ones.

    Why this exists (V2-11): the one-time 38,756-bill backfill runs for ~43 hours
    on a laptop that gets shut, so it is interrupted a dozen times by design. A
    plain `Path.write_text` is two syscalls on a truncated file, and a kill
    between them leaves a half-written record on disk. Two places that matters:

    * `export_bill` — a torn bill record is survivable (`bills_with_actions`
      cannot parse it, so the next run re-ingests it) but it costs a refetch and
      shows up as a corrupt file in `git status` until then.
    * `cache.fetch` — a torn CACHED body is worse, and is the one case that is
      not self-healing. The `.meta` sidecar is only written after a complete body
      write, so a Ctrl+C or an orderly shutdown always leaves meta absent and the
      torn body ignored. A true power loss is different: NTFS journals the
      metadata but not the data blocks, so the body can come back zero-length
      under a sidecar that still reads FRESH. That body then parses as a
      JSONDecodeError for the remaining TTL (up to 20 h) on every resume, and it
      is not in `run_activity`'s `fetch_errors`, so the whole run dies on it.

    `write + flush + fsync + os.replace` closes both. `os.replace` is atomic on
    NTFS as well as POSIX, and the fsync is what makes the *contents* durable
    before the rename publishes them — without it the rename can survive a power
    cut that the data did not. The temp file is a sibling (same volume, or
    `os.replace` would not be atomic) and is cleaned up if the write fails. Its name
    carries the thread as well as the process, so two threads writing the same path
    (the concurrent triage run) never share a temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path


class RetryableHTTPError(Exception):
    """Raised on 429/5xx so tenacity retries; 4xx (except 429) do not retry."""


@dataclass(frozen=True)
class CachedResponse:
    path: Path
    text: str
    status: int
    from_cache: bool
    ext: str

    def json(self):
        return json.loads(self.text)


def _cache_key(url: str, params: dict | None) -> str:
    """sha256 over url + canonicalised params. No credential is ever passed in
    params, so the key never depends on a secret."""
    canonical = url
    if params:
        items = sorted((str(k), str(v)) for k, v in params.items())
        canonical += "?" + "&".join(f"{k}={v}" for k, v in items)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _paths(source: str, key: str, ext: str) -> tuple[Path, Path]:
    base = RAW_DIR / source
    return base / f"{key}.{ext}", base / f"{key}.meta"


def _fresh(meta_path: Path, ttl_hours: float) -> bool:
    if ttl_hours <= 0 or not meta_path.exists():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(meta["fetched_at"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return False
    age_hours = (datetime.now(UTC) - fetched_at).total_seconds() / 3600.0
    return age_hours < ttl_hours


def _throttle(host: str) -> None:
    interval = _HOST_MIN_INTERVAL.get(host, _DEFAULT_MIN_INTERVAL)
    last = _last_fetch_at.get(host)
    if last is not None:
        wait = interval - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_fetch_at[host] = time.monotonic()


@retry(
    # §6.1: retry on 429/5xx AND timeouts/network errors. httpx.TransportError is
    # the base for ReadTimeout/ConnectTimeout/ConnectError/ReadError/etc., so a
    # transient blip on any one of ~1,886 sequential fetches self-heals instead of
    # crashing the whole run.
    retry=retry_if_exception_type((RetryableHTTPError, httpx.TransportError)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    reraise=True,
)
def _live_get(url: str, params: dict | None, headers: dict | None) -> httpx.Response:
    host = urlsplit(url).netloc
    _throttle(host)
    hdrs = {"User-Agent": _USER_AGENT}
    if headers:
        hdrs.update(headers)
    resp = httpx.get(url, params=params, headers=hdrs, timeout=_HTTP_TIMEOUT, follow_redirects=True)
    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            time.sleep(min(int(retry_after), 60))
        raise RetryableHTTPError(f"429 rate limited for {url}")
    if resp.status_code >= 500:
        raise RetryableHTTPError(f"{resp.status_code} server error for {url}")
    return resp


def fetch(
    source: str,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    ext: str = "json",
    ttl_hours: float = DEFAULT_TTL_HOURS,
    force: bool = False,
    accept_status: tuple[int, ...] = (200, 302),
) -> CachedResponse:
    """Fetch `url` through the disk cache, returning the cached-or-live body.

    `source` names the subdir under data/raw/. `ext` is the on-disk extension
    (`json` or `xml`). `headers` carries auth (never the URL). Non-accepted
    status codes raise httpx.HTTPStatusError so callers can branch (e.g. the
    house-vote 404 → clerk fallback in INC-1).
    """
    key = _cache_key(url, params)
    data_path, meta_path = _paths(source, key, ext)

    if not force and _fresh(meta_path, ttl_hours) and data_path.exists():
        return CachedResponse(
            path=data_path,
            text=data_path.read_text(encoding="utf-8"),
            status=json.loads(meta_path.read_text(encoding="utf-8")).get("status", 200),
            from_cache=True,
            ext=ext,
        )

    resp = _live_get(url, params, headers)
    if resp.status_code not in accept_status:
        resp.raise_for_status()  # non-accepted (e.g. 404) → HTTPStatusError to caller

    # Atomic (see `atomic_write_text`): an interrupted backfill must never leave a
    # truncated body that a still-fresh `.meta` would then serve from cache.
    atomic_write_text(data_path, resp.text)
    meta = {
        "url": url,  # NOTE: never contains a credential (header-auth only)
        "params": params or {},
        "fetched_at": datetime.now(UTC).isoformat(),
        "status": resp.status_code,
        "ext": ext,
    }
    # Written AFTER the body, and atomically: the sidecar is the commit record for
    # this cache entry, so it must not exist until the body it describes is whole.
    atomic_write_text(meta_path, json.dumps(meta, indent=2, sort_keys=True))

    return CachedResponse(
        path=data_path, text=resp.text, status=resp.status_code, from_cache=False, ext=ext
    )


def store(
    source: str,
    url: str,
    text: str,
    *,
    params: dict | None = None,
    ext: str = "json",
    status: int = 200,
    renderer: str | None = None,
) -> Path:
    """Write a body into the cache as if `fetch()` had retrieved it.

    The one caller is the rendered-fetch path (`ingest/press_render.py`): eleven pilot
    rows publish their release list from JavaScript, so a plain GET returns a page with
    zero dated items (STATUS fact 7). A browser renders those pages and the body lands
    here, which is what lets `statements_press.py` consume them UNCHANGED — it still
    only ever reads through `fetch()`, and finds a fresh entry waiting.

    `renderer` is recorded in the sidecar so a rendered entry is distinguishable from a
    plain GET by looking at the cache, not by remembering. `_fresh()` reads only
    `fetched_at`, so the extra key costs nothing.

    Same write order and atomicity as `fetch()`: body first, sidecar second, both
    atomic, so an interrupted run never leaves a torn body under a fresh sidecar.
    """
    key = _cache_key(url, params)
    data_path, meta_path = _paths(source, key, ext)
    atomic_write_text(data_path, text)
    meta = {
        "url": url,
        "params": params or {},
        "fetched_at": datetime.now(UTC).isoformat(),
        "status": status,
        "ext": ext,
    }
    if renderer:
        meta["renderer"] = renderer
    atomic_write_text(meta_path, json.dumps(meta, indent=2, sort_keys=True))
    return data_path
