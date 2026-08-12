"""INC-11 — SPN2 capture client. The full submit → poll → verify flow is driven
through httpx.MockTransport (no network). A capture is only "verified" when the
archive_url actually HEAD-resolves; any failure raises SpnError (→ no save)."""

from __future__ import annotations

import httpx
import pytest

from ingest.sources import archive_org
from ingest.sources.archive_org import Capture, SpnClient, SpnError, _timestamp_to_iso


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
