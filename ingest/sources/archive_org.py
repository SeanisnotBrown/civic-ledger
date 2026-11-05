"""INC-11 — archive.org Save Page Now 2 (SPN2) capture client.

The curation tool captures a permanent Wayback copy of every statement's source
before it can be saved (brief §5.10; "no verified capture, no save"). This module
is that capture path.

Why it does NOT go through cache.py: a capture is a mutating POST (it creates a new
Wayback snapshot), not an idempotent GET, so it must never be cached or replayed.

The flow (verified against archive.org's SPN2 public API):
  1. POST https://web.archive.org/save  (Accept: application/json; body `url=` and
     `skip_first_archive=1`, which SPN2 documents as faster) → {"url", "job_id"};
  2. poll GET https://web.archive.org/save/status/{job_id} until status is
     "success" (→ timestamp) or "error" (→ status_ext/message), or we time out, when
     a snapshot CDX lists from after the save still counts (jobs ran past 180 s on
     2026-11-05 and landed anyway);
  3. build archive_url = https://web.archive.org/web/{timestamp}/{original_url} and
     HEAD-verify it actually resolves before returning — VERIFIED means the snapshot
     exists, not merely that the job reported success (value #1). Playback can 503 for
     a snapshot that is there (seen 2026-11-05), so when the HEAD fails the CDX index
     is asked for that exact timestamp, and a 5xx is checked again over a bounded window.

SPN2 answers a save with a 429 `error:user-session-limit` while the account's sessions are
full, and says to wait a minute (seen 2026-11-05, with sessions free again seconds later).
That save waits and goes again over `SESSION_BACKOFF_S`; any other 429 stops the run.

A refused connection, a reset or a timeout says nothing about the page, so it never fails
a capture: every request rides one out over `TRANSPORT_BACKOFF_S`, then `SpnUnreachable`
ends the run and the URL is asked again on a later one.

Auth (H6): with IA S3 keys (IA_S3_ACCESS / IA_S3_SECRET) we send
`Authorization: LOW {access}:{secret}` — higher rate limits, per archive.org
guidance. Without them we fall back to unauthenticated capture and honor the §6.1
ceiling of ≤ 1 capture / 15 s. Keys are header-only, never logged or placed in a URL.

The HTTP client is injectable so tests drive the full poll loop through
`httpx.MockTransport` with no network. `on_response` (optional) receives every SPN2
response BEFORE it is parsed, so a caller can keep the raw payload on disk (rule 4)
without the POST ever being replayed from a cache.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from ingest import env

SAVE_URL = "https://web.archive.org/save"
STATUS_URL = "https://web.archive.org/save/status"
USER_STATUS_URL = "https://web.archive.org/save/status/user"
WAYBACK_PREFIX = "https://web.archive.org/web"
CDX_URL = "https://web.archive.org/cdx/search/cdx"

_USER_AGENT = "civic-ledger/0.0 (+https://github.com/SeanisnotBrown/civic-ledger)"
_HTTP_TIMEOUT = httpx.Timeout(60.0, connect=15.0)

# §6.1 unauthenticated ceiling: at most one capture every 15 seconds.
UNAUTH_MIN_INTERVAL_S = 15.0
# SPN2's documented ceiling is 7 captures a minute for an account: one save every 9 s.
SAVE_MIN_INTERVAL_S = 9.0
_last_unauth_capture_at: float | None = None

# Seconds to wait before each new check of a snapshot playback answered with a 5xx.
VERIFY_BACKOFF_S = (10.0, 30.0, 60.0, 120.0)
# Seconds to wait before sending a request again after a transport error.
TRANSPORT_BACKOFF_S = (30.0, 60.0, 120.0)
# Seconds to wait before sending a save again while the account's sessions are full.
SESSION_BACKOFF_S = (60.0, 120.0, 240.0)
SESSION_LIMIT = "error:user-session-limit"


class SpnError(Exception):
    """A capture failed, timed out, or produced an archive_url that does not resolve.
    The caller must treat this as "no verified capture" and refuse to save."""


class SpnRateLimited(SpnError):
    """archive.org answered 429. Not a failed capture: the URL is asked again on a later
    run."""


class SpnUnreachable(SpnError):
    """archive.org stayed out of reach past the backoff. Not a failed capture: the URL is
    asked again on a later run."""


@dataclass(frozen=True)
class Capture:
    original_url: str
    archive_url: str  # https://web.archive.org/web/{timestamp}/{original_url}
    timestamp: str  # Wayback 14-digit (YYYYMMDDhhmmss)
    captured_at: str  # ISO-8601 UTC derived from `timestamp`


def _auth_header() -> str | None:
    """`Authorization: LOW access:secret` if both IA S3 keys are set, else None
    (unauthenticated fallback). Header-only — a secret never enters a URL or a log."""
    access = env.get("IA_S3_ACCESS")
    secret = env.get("IA_S3_SECRET")
    if access and secret:
        return f"LOW {access}:{secret}"
    return None


def _timestamp_to_iso(ts: str) -> str:
    """Wayback 14-digit timestamp → ISO-8601 UTC. 20180326070330 → 2018-03-26T07:03:30Z."""
    if len(ts) != 14 or not ts.isdigit():
        raise SpnError(f"unexpected Wayback timestamp {ts!r}")
    return f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}T{ts[8:10]}:{ts[10:12]}:{ts[12:14]}Z"


class SpnClient:
    """SPN2 capture client. Inject `client` (an httpx.Client, real or MockTransport)
    and `sleep` for deterministic tests; leave them defaulted in production."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        poll_interval_s: float = 6.0,
        timeout_s: float = 360.0,
        sleep=time.sleep,
        monotonic=time.monotonic,
        on_response: Callable[[str, str, httpx.Response], None] | None = None,
    ) -> None:
        self._client = client or httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=True)
        self._owns_client = client is None
        self._poll_interval_s = poll_interval_s
        self._timeout_s = timeout_s
        self._sleep = sleep
        self._monotonic = monotonic
        self._auth = _auth_header()
        self._on_response = on_response
        self._save_lock = threading.Lock()
        self._last_save_at: float | None = None

    def _seen(self, kind: str, url: str, resp: httpx.Response) -> httpx.Response:
        """Hand the raw response to `on_response` (kind: save / status / verify) first."""
        if self._on_response is not None:
            self._on_response(kind, url, resp)
        return resp

    @property
    def authenticated(self) -> bool:
        return self._auth is not None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _headers(self) -> dict[str, str]:
        hdrs = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
        if self._auth:
            hdrs["Authorization"] = self._auth
        return hdrs

    def _send(self, request: Callable[[], httpx.Response]) -> httpx.Response:
        """`request()`, sent again after a transport error until the backoff runs out."""
        waits = iter(TRANSPORT_BACKOFF_S)
        while True:
            try:
                return request()
            except httpx.TransportError as exc:
                wait = next(waits, None)
                if wait is None:
                    raise SpnUnreachable(f"archive.org unreachable: {exc}") from exc
                self._sleep(wait)
            except httpx.HTTPError as exc:
                raise SpnError(f"archive.org request failed: {exc}") from exc

    def available_sessions(self) -> int:
        """The capture sessions SPN2 reports free for this account. 1 without keys, or when
        it does not say: the safe answer, and the first save finds out the rest."""
        if not self.authenticated:
            return 1
        try:
            resp = self._seen("sessions", USER_STATUS_URL, self._send(lambda: self._client.get(
                USER_STATUS_URL, params={"_t": str(time.time_ns())}, headers=self._headers())))
            return int(resp.json()["available"])
        except (SpnError, ValueError, KeyError, TypeError):
            return 1

    def _space_saves(self) -> None:
        """Hold this client's saves to `SAVE_MIN_INTERVAL_S` apart, across every worker."""
        with self._save_lock:
            if self._last_save_at is not None:
                wait = SAVE_MIN_INTERVAL_S - (self._monotonic() - self._last_save_at)
                if wait > 0:
                    self._sleep(wait)
            self._last_save_at = self._monotonic()

    def _rate_limit_unauth(self) -> None:
        """Enforce the §6.1 ≤ 1 capture / 15 s ceiling in unauthenticated mode."""
        global _last_unauth_capture_at
        if self.authenticated:
            self._space_saves()
            return
        if _last_unauth_capture_at is not None:
            wait = UNAUTH_MIN_INTERVAL_S - (self._monotonic() - _last_unauth_capture_at)
            if wait > 0:
                self._sleep(wait)
        _last_unauth_capture_at = self._monotonic()

    def _submit(self, url: str) -> str:
        waits = iter(SESSION_BACKOFF_S)
        while True:
            self._rate_limit_unauth()
            resp = self._seen("save", url, self._send(lambda: self._client.post(
                SAVE_URL, data={"url": url, "skip_first_archive": "1"},
                headers=self._headers())))
            if resp.status_code != 429:
                break
            wait = next(waits, None)
            if wait is None or SESSION_LIMIT not in resp.text:
                raise SpnRateLimited("SPN2 rate limited (429) — try again later")
            self._sleep(wait)
        if resp.status_code >= 400:
            raise SpnError(f"SPN2 save returned {resp.status_code}")
        try:
            job_id = resp.json().get("job_id")
        except ValueError as exc:
            raise SpnError(f"SPN2 save response was not JSON: {exc}") from exc
        if not job_id:
            raise SpnError("SPN2 save response carried no job_id")
        return job_id

    def _poll(self, job_id: str, url: str = "", since: str = "") -> str:
        """Poll the status endpoint until success (returns the timestamp), error, or
        timeout, when a snapshot CDX lists from `since` on is the answer. Deadline is
        wall-clock via the injected monotonic clock."""
        deadline = self._monotonic() + self._timeout_s
        while True:
            resp = self._seen("status", url, self._send(lambda: self._client.get(
                f"{STATUS_URL}/{job_id}", headers=self._headers())))
            if resp.status_code >= 400:
                raise SpnError(f"SPN2 status returned {resp.status_code}")
            try:
                body: dict[str, Any] = resp.json()
            except ValueError as exc:
                raise SpnError(f"SPN2 status response was not JSON: {exc}") from exc
            status = body.get("status")
            if status == "success":
                ts = body.get("timestamp")
                if not ts:
                    raise SpnError("SPN2 reported success but no timestamp")
                return ts
            if status == "error":
                ext = body.get("status_ext") or body.get("message") or "unknown"
                if ext == SESSION_LIMIT:
                    raise SpnRateLimited("SPN2 session limit reached — try again later")
                raise SpnError(f"SPN2 capture failed: {ext}")
            # status == "pending" (or an unknown transient state) → keep polling.
            if self._monotonic() >= deadline:
                found = self._snapshot_since(since, url)
                if found is not None:
                    return found
                raise SpnError(f"SPN2 capture timed out after {self._timeout_s:.0f}s")
            self._sleep(self._poll_interval_s)

    def _listed(self, url: str, **window: str) -> list[str]:
        """The timestamps of the 2xx/3xx snapshots of `url` CDX lists in `window`, oldest
        first."""
        resp = self._seen("cdx", url, self._send(lambda: self._client.get(
            CDX_URL, headers={"User-Agent": _USER_AGENT},
            params={"url": url, "output": "json", "fl": "timestamp,statuscode", **window})))
        if resp.status_code == 429:
            raise SpnRateLimited("CDX rate limited (429) — try again later")
        try:
            rows = resp.json()
        except ValueError:
            return []
        if resp.status_code >= 400 or not isinstance(rows, list):
            return []
        return [row[0] for row in rows[1:] if row[1][:1] in ("2", "3")]

    def _indexed(self, timestamp: str, url: str) -> bool:
        """True when CDX lists a good snapshot of `url` at exactly `timestamp`."""
        return timestamp in self._listed(url, **{"from": timestamp, "to": timestamp})

    def _snapshot_since(self, since: str, url: str) -> str | None:
        """The first good snapshot of `url` CDX lists at or after `since`, or None."""
        found = [t for t in self._listed(url, **{"from": since}) if t >= since]
        return found[0] if found else None

    def _verify(self, archive_url: str, timestamp: str, url: str = "") -> None:
        """HEAD the snapshot URL, then ask CDX. Neither one vouching for it means the
        capture did not land, so we refuse to treat it as verified (no verified capture,
        no save). Only a 5xx is worth asking about again."""
        for wait in (*VERIFY_BACKOFF_S, None):
            resp = self._seen("verify", url, self._send(lambda: self._client.head(archive_url)))
            if resp.status_code == 429:
                raise SpnRateLimited("snapshot check rate limited (429) — try again later")
            if resp.status_code < 400 or self._indexed(timestamp, url):
                return
            if wait is None or resp.status_code < 500:
                raise SpnError(
                    f"archive_url did not resolve (HTTP {resp.status_code}): {archive_url}")
            self._sleep(wait)

    def confirm(self, url: str, timestamp: str) -> Capture:
        """The verified `Capture` for a snapshot SPN2 already made, or `SpnError`. Sends
        no save."""
        archive_url = f"{WAYBACK_PREFIX}/{timestamp}/{url}"
        self._verify(archive_url, timestamp, url)
        return Capture(
            original_url=url,
            archive_url=archive_url,
            timestamp=timestamp,
            captured_at=_timestamp_to_iso(timestamp),
        )

    def recover(self, url: str, since: str) -> Capture:
        """The verified `Capture` for a save that timed out at our end, from the snapshot
        CDX lists at or after `since`, or `SpnError`. Sends no save."""
        found = self._snapshot_since(since, url)
        if found is None:
            raise SpnError(f"CDX lists no snapshot since {since}")
        return self.confirm(url, found)

    def capture(self, url: str) -> Capture:
        """Run the full capture → poll → verify flow, returning a verified `Capture`
        or raising `SpnError`. The returned archive_url was vouched for at capture time,
        by a HEAD or by the CDX index."""
        since = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        job_id = self._submit(url)
        return self.confirm(url, self._poll(job_id, url, since))
