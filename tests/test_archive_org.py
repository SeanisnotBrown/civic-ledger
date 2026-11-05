"""INC-11 — SPN2 capture client. The full submit → poll → verify flow is driven
through httpx.MockTransport (no network). A capture is only "verified" when the
archive_url actually HEAD-resolves; any failure raises SpnError (→ no save)."""

from __future__ import annotations

import httpx
import pytest

from ingest.sources import archive_org
from ingest.sources.archive_org import (
    Capture,
    SpnClient,
    SpnError,
    SpnRateLimited,
    _timestamp_to_iso,
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _spn(handler) -> SpnClient:
    return SpnClient(client=_client(handler), poll_interval_s=0, sleep=lambda _s: None)


def test_timestamp_to_iso() -> None:
    assert _timestamp_to_iso("20180326070330") == "2018-03-26T07:03:30Z"


def test_timestamp_to_iso_rejects_garbage() -> None:
    with pytest.raises(SpnError):
        _timestamp_to_iso("nope")


def test_capture_polls_until_success_then_verifies() -> None:
    seen = {"status": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST" and req.url.path == "/save":
            assert req.headers["accept"] == "application/json"
            return httpx.Response(200, json={"url": "https://ex.com/a", "job_id": "J"})
        if req.method == "GET" and req.url.path.startswith("/save/status/"):
            seen["status"] += 1
            if seen["status"] < 3:
                return httpx.Response(200, json={"status": "pending", "job_id": "J"})
            return httpx.Response(200, json={"status": "success", "job_id": "J",
                                             "timestamp": "20240115120000",
                                             "original_url": "https://ex.com/a"})
        if req.method == "HEAD":
            return httpx.Response(200)
        return httpx.Response(404)

    cap = _spn(handler).capture("https://ex.com/a")
    assert isinstance(cap, Capture)
    assert cap.archive_url == "https://web.archive.org/web/20240115120000/https://ex.com/a"
    assert cap.captured_at == "2024-01-15T12:00:00Z"
    assert seen["status"] == 3  # polled through the pending states


def test_capture_raises_on_spn_error_status() -> None:
    def handler(req):
        if req.method == "POST":
            return httpx.Response(200, json={"job_id": "J"})
        return httpx.Response(200, json={"status": "error",
                                         "status_ext": "error:invalid-host-resolution"})
    with pytest.raises(SpnError, match="invalid-host-resolution"):
        _spn(handler).capture("https://bad.example")


def test_capture_refuses_when_archive_url_does_not_resolve() -> None:
    # Job reports success, but the snapshot HEAD is a 404 → NOT verified → SpnError.
    def handler(req):
        if req.method == "POST":
            return httpx.Response(200, json={"job_id": "J"})
        if req.method == "GET":
            return httpx.Response(200, json={"status": "success", "timestamp": "20240101000000"})
        return httpx.Response(404)  # HEAD verify fails
    with pytest.raises(SpnError, match="did not resolve"):
        _spn(handler).capture("https://ex.com/a")


def test_capture_times_out_while_pending() -> None:
    def handler(req):
        if req.method == "POST":
            return httpx.Response(200, json={"job_id": "J"})
        return httpx.Response(200, json={"status": "pending"})
    # Deadline in the past on the first poll via a monotonic clock that always advances.
    clock = iter([0.0, 100.0, 200.0, 300.0])
    spn = SpnClient(client=_client(handler), poll_interval_s=0, timeout_s=1.0,
                    sleep=lambda _s: None, monotonic=lambda: next(clock))
    with pytest.raises(SpnError, match="timed out"):
        spn.capture("https://ex.com/a")


def test_missing_job_id_raises() -> None:
    def handler(req):
        return httpx.Response(200, json={"url": "x"})  # no job_id
    with pytest.raises(SpnError, match="job_id"):
        _spn(handler).capture("https://ex.com/a")


def test_auth_header_present_only_with_both_keys(monkeypatch) -> None:
    monkeypatch.setattr(archive_org.env, "get", lambda name, default=None: {
        "IA_S3_ACCESS": "AK", "IA_S3_SECRET": "SK"}.get(name, default))
    assert archive_org._auth_header() == "LOW AK:SK"
    monkeypatch.setattr(archive_org.env, "get", lambda name, default=None: None)
    assert archive_org._auth_header() is None


# --- the snapshot check: playback can be down while the snapshot is there ------------------

URL = "https://ex.com/a"
STAMP = "20261105163622"
LISTED = [["timestamp", "statuscode"], [STAMP, "200"]]


def _saved(head, cdx=lambda _req: httpx.Response(200, json=[])):
    """SPN2 saves at STAMP; `head` and `cdx` answer the two checks. Returns the client, the
    waits it took and the requests it made."""
    archive_org._last_unauth_capture_at = None  # the 15 s pacing is not under test
    waits: list[float] = []
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if req.method == "POST":
            return httpx.Response(200, json={"job_id": "J"})
        if req.method == "HEAD":
            return head(req)
        if req.url.path == "/cdx/search/cdx":
            return cdx(req)
        return httpx.Response(200, json={"status": "success", "timestamp": STAMP})

    spn = SpnClient(client=_client(handler), poll_interval_s=0, sleep=waits.append)
    return spn, waits, calls


def _heads(calls: list[httpx.Request]) -> int:
    return sum(req.method == "HEAD" for req in calls)


def test_a_503_then_a_200_on_the_check_is_a_capture() -> None:
    answers = iter([503, 503, 200])
    spn, waits, calls = _saved(lambda _req: httpx.Response(next(answers)))
    assert spn.capture(URL).timestamp == STAMP
    assert waits == list(archive_org.VERIFY_BACKOFF_S[:2])
    assert _heads(calls) == 3


def test_cdx_listing_the_exact_snapshot_is_proof_when_playback_is_down() -> None:
    seen = {}

    def cdx(req: httpx.Request) -> httpx.Response:
        seen.update(req.url.params)
        return httpx.Response(200, json=LISTED)

    spn, waits, _calls = _saved(lambda _req: httpx.Response(503), cdx)
    cap = spn.capture(URL)
    assert cap.archive_url == f"https://web.archive.org/web/{STAMP}/{URL}"
    assert waits == []  # the index answered, so nothing waited
    assert seen["url"] == URL and seen["from"] == STAMP and seen["to"] == STAMP


def test_a_snapshot_neither_check_finds_is_a_failure_after_the_window() -> None:
    spn, waits, calls = _saved(lambda _req: httpx.Response(503))
    with pytest.raises(SpnError, match=r"did not resolve \(HTTP 503\)"):
        spn.capture(URL)
    assert waits == list(archive_org.VERIFY_BACKOFF_S)
    assert _heads(calls) == len(archive_org.VERIFY_BACKOFF_S) + 1


def test_a_404_on_the_check_is_not_asked_again() -> None:
    spn, waits, calls = _saved(lambda _req: httpx.Response(404))
    with pytest.raises(SpnError, match="did not resolve"):
        spn.capture(URL)
    assert waits == [] and _heads(calls) == 1


@pytest.mark.parametrize("cdx", [
    lambda _req: httpx.Response(200, json=[["timestamp", "statuscode"], [STAMP, "404"]]),
    lambda _req: httpx.Response(200, json=[["timestamp", "statuscode"], ["20261105000000", "200"]]),
    lambda _req: httpx.Response(200, json={"status": "not a cdx answer"}),
    lambda _req: httpx.Response(200, text=""),
    lambda _req: httpx.Response(503, json=LISTED),
])
def test_cdx_vouches_only_for_a_good_row_at_that_timestamp(cdx) -> None:
    spn, _waits, _calls = _saved(lambda _req: httpx.Response(404), cdx)
    with pytest.raises(SpnError, match="did not resolve"):
        spn.capture(URL)


def test_a_dropped_connection_on_either_check_is_asked_again() -> None:
    answers = iter([httpx.ConnectError("reset"), httpx.Response(200)])

    def head(_req: httpx.Request) -> httpx.Response:
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def cdx(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("reset")

    spn, waits, _calls = _saved(head, cdx)
    assert spn.capture(URL).timestamp == STAMP
    assert waits == [archive_org.VERIFY_BACKOFF_S[0]]


def test_a_connection_that_stays_down_is_a_failure() -> None:
    def head(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("reset")

    spn, _waits, _calls = _saved(head)
    with pytest.raises(SpnError, match="could not verify"):
        spn.capture(URL)


@pytest.mark.parametrize(("head", "cdx"), [(429, 200), (503, 429)])
def test_a_429_on_either_check_stops_rather_than_fails(head, cdx) -> None:
    spn, waits, _calls = _saved(lambda _req: httpx.Response(head),
                                lambda _req: httpx.Response(cdx, json=[]))
    with pytest.raises(SpnRateLimited):
        spn.capture(URL)
    assert waits == []


def test_confirm_checks_a_snapshot_without_a_save() -> None:
    spn, _waits, calls = _saved(lambda _req: httpx.Response(200))
    assert spn.confirm(URL, STAMP).captured_at == "2026-11-05T16:36:22Z"
    assert [req.method for req in calls] == ["HEAD"]
