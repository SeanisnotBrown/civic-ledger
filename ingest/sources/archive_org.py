"""INC-11 — archive.org Save Page Now 2 (SPN2) capture client.

The curation tool captures a permanent Wayback copy of every statement's source
before it can be saved (brief §5.10; "no verified capture, no save"). This module
is that capture path.

Why it does NOT go through cache.py: a capture is a mutating POST (it creates a new
Wayback snapshot), not an idempotent GET, so it must never be cached or replayed.

The flow (verified against archive.org's SPN2 public API):
  1. POST https://web.archive.org/save  (Accept: application/json; body `url=`) →
     {"url", "job_id"};
  2. poll GET https://web.archive.org/save/status/{job_id} until status is
     "success" (→ timestamp) or "error" (→ status_ext/message), or we time out;
  3. build archive_url = https://web.archive.org/web/{timestamp}/{original_url} and
     HEAD-verify it actually resolves before returning — VERIFIED means the snapshot
     exists, not merely that the job reported success (value #1).

Auth (H6): with IA S3 keys (IA_S3_ACCESS / IA_S3_SECRET) we send
`Authorization: LOW {access}:{secret}` — higher rate limits, per archive.org
guidance. Without them we fall back to unauthenticated capture and honor the §6.1
ceiling of ≤ 1 capture / 15 s. Keys are header-only, never logged or placed in a URL.

The HTTP client is injectable so tests drive the full poll loop through
`httpx.MockTransport` with no network.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from ingest import env

SAVE_URL = "https://web.archive.org/save"
STATUS_URL = "https://web.archive.org/save/status"
WAYBACK_PREFIX = "https://web.archive.org/web"

_USER_AGENT = "civic-ledger/0.0 (+https://github.com/SeanisnotBrown/civic-ledger)"
_HTTP_TIMEOUT = httpx.Timeout(60.0, connect=15.0)

# §6.1 unauthenticated ceiling: at most one capture every 15 seconds.
UNAUTH_MIN_INTERVAL_S = 15.0
_last_unauth_capture_at: float | None = None


class SpnError(Exception):
    """A capture failed, timed out, or produced an archive_url that does not resolve.
    The caller must treat this as "no verified capture" and refuse to save."""


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
        timeout_s: float = 180.0,
        sleep=time.sleep,
        monotonic=time.monotonic,
    ) -> None:
        self._client = client or httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=True)
        self._owns_client = client is None
        self._poll_interval_s = poll_interval_s
        self._timeout_s = timeout_s
        self._sleep = sleep
        self._monotonic = monotonic
        self._auth = _auth_header()

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

    def _rate_limit_unauth(self) -> None:
        """Enforce the §6.1 ≤ 1 capture / 15 s ceiling in unauthenticated mode."""
        global _last_unauth_capture_at
        if self.authenticated:
            return
        if _last_unauth_capture_at is not None:
            wait = UNAUTH_MIN_INTERVAL_S - (self._monotonic() - _last_unauth_capture_at)
            if wait > 0:
                self._sleep(wait)
        _last_unauth_capture_at = self._monotonic()

    def _submit(self, url: str) -> str:
        self._rate_limit_unauth()
        resp = self._client.post(SAVE_URL, data={"url": url}, headers=self._headers())
        if resp.status_code == 429:
            raise SpnError("SPN2 rate limited (429) — try again later")
        if resp.status_code >= 400:
            raise SpnError(f"SPN2 save returned {resp.status_code}")
        try:
            job_id = resp.json().get("job_id")
        except ValueError as exc:
            raise SpnError(f"SPN2 save response was not JSON: {exc}") from exc
        if not job_id:
            raise SpnError("SPN2 save response carried no job_id")
        return job_id

    def _poll(self, job_id: str) -> str:
        """Poll the status endpoint until success (returns the timestamp), error, or
        timeout. Deadline is wall-clock via the injected monotonic clock."""
        deadline = self._monotonic() + self._timeout_s
        while True:
            resp = self._client.get(f"{STATUS_URL}/{job_id}", headers=self._headers())
            if resp.status_code >= 400:
                raise SpnError(f"SPN2 status returned {resp.status_code}")
            body = resp.json()
            status = body.get("status")
            if status == "success":
                ts = body.get("timestamp")
                if not ts:
                    raise SpnError("SPN2 reported success but no timestamp")
                return ts
            if status == "error":
                ext = body.get("status_ext") or body.get("message") or "unknown"
                raise SpnError(f"SPN2 capture failed: {ext}")
            # status == "pending" (or an unknown transient state) → keep polling.
            if self._monotonic() >= deadline:
                raise SpnError(f"SPN2 capture timed out after {self._timeout_s:.0f}s")
            self._sleep(self._poll_interval_s)

    def _verify(self, archive_url: str) -> None:
        """HEAD the snapshot URL; a non-2xx/3xx means the capture did not actually
        land, so we refuse to treat it as verified (no verified capture, no save)."""
        try:
            resp = self._client.head(archive_url)
        except httpx.HTTPError as exc:
            raise SpnError(f"could not verify {archive_url}: {exc}") from exc
        if resp.status_code >= 400:
            raise SpnError(f"archive_url did not resolve (HTTP {resp.status_code}): {archive_url}")

    def capture(self, url: str) -> Capture:
        """Run the full capture → poll → verify flow, returning a verified `Capture`
        or raising `SpnError`. The returned archive_url is guaranteed to have
        resolved (HEAD-checked) at capture time."""
        job_id = self._submit(url)
        timestamp = self._poll(job_id)
        archive_url = f"{WAYBACK_PREFIX}/{timestamp}/{url}"
        self._verify(archive_url)
        return Capture(
            original_url=url,
            archive_url=archive_url,
            timestamp=timestamp,
            captured_at=_timestamp_to_iso(timestamp),
        )
