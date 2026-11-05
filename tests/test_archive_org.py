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
    SpnUnreachable,
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


def _drops(times: int, then=lambda _req: httpx.Response(200)):
    """A handler that loses the connection `times` times, then answers with `then`."""
    left = iter(range(times))

    def handler(req: httpx.Request) -> httpx.Response:
        if next(left, None) is not None:
            raise httpx.ConnectError("refused")
        return then(req)

    return handler


def test_a_dropped_connection_on_the_check_is_sent_again() -> None:
    spn, waits, _calls = _saved(_drops(1))
    assert spn.capture(URL).timestamp == STAMP
    assert waits == [archive_org.TRANSPORT_BACKOFF_S[0]]


def test_a_connection_that_stays_down_on_the_check_is_unreachable() -> None:
    spn, waits, calls = _saved(_drops(99))
    with pytest.raises(SpnUnreachable):
        spn.capture(URL)
    assert waits == list(archive_org.TRANSPORT_BACKOFF_S)
    assert _heads(calls) == len(archive_org.TRANSPORT_BACKOFF_S) + 1


def test_cdx_staying_down_is_unreachable_not_unlisted() -> None:
    spn, _waits, _calls = _saved(lambda _req: httpx.Response(503), _drops(99))
    with pytest.raises(SpnUnreachable):
        spn.capture(URL)


@pytest.mark.parametrize("method", ["POST", "GET"])
def test_a_transport_error_on_the_save_or_the_poll_is_sent_again(method) -> None:
    drop = _drops(2, then=lambda _req: None)
    waits: list[float] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == method:
            drop(req)
        if req.method == "POST":
            return httpx.Response(200, json={"job_id": "J"})
        if req.method == "GET":
            return httpx.Response(200, json={"status": "success", "timestamp": STAMP})
        return httpx.Response(200)

    archive_org._last_unauth_capture_at = None
    spn = SpnClient(client=_client(handler), poll_interval_s=0, sleep=waits.append)
    assert spn.capture(URL).timestamp == STAMP
    assert waits == list(archive_org.TRANSPORT_BACKOFF_S[:2])


@pytest.mark.parametrize("error", [httpx.ConnectTimeout("t"), httpx.ReadTimeout("t"),
                                   httpx.ReadError("reset"), httpx.ConnectError("refused")])
def test_every_transport_error_ends_as_unreachable_on_the_save(error) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        raise error

    with pytest.raises(SpnUnreachable):
        _spn(handler).capture(URL)


def test_an_error_that_is_not_transport_fails_the_url() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.TooManyRedirects("loop")

    with pytest.raises(SpnError, match="request failed") as caught:
        _spn(handler).capture(URL)
    assert not isinstance(caught.value, SpnUnreachable)


def test_a_status_answer_that_is_not_json_fails_the_url() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(200, json={"job_id": "J"})
        return httpx.Response(200, text="<html>offline</html>")

    with pytest.raises(SpnError, match="not JSON"):
        _spn(handler).capture(URL)


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


# --- sessions and pacing -------------------------------------------------------------------


def _authed(monkeypatch, handler, **kwargs) -> SpnClient:
    monkeypatch.setenv("IA_S3_ACCESS", "AK")
    monkeypatch.setenv("IA_S3_SECRET", "SK")
    return SpnClient(client=_client(handler), poll_interval_s=0, **kwargs)


def test_available_sessions_reads_the_account_status(monkeypatch) -> None:
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(path=req.url.path, auth=req.headers["authorization"], t=req.url.params["_t"])
        return httpx.Response(200, json={"available": 3, "processing": 0})

    assert _authed(monkeypatch, handler).available_sessions() == 3
    assert seen["path"] == "/save/status/user" and seen["auth"] == "LOW AK:SK" and seen["t"]


def test_available_sessions_is_one_without_keys_and_sends_nothing(monkeypatch) -> None:
    monkeypatch.delenv("IA_S3_ACCESS", raising=False)

    def handler(_req: httpx.Request) -> httpx.Response:
        raise AssertionError("a request without keys")

    assert _spn(handler).available_sessions() == 1


@pytest.mark.parametrize("answer", [
    lambda _req: httpx.Response(401, json={"message": "log in"}),
    lambda _req: httpx.Response(429, json={"message": "slow down"}),
    lambda _req: httpx.Response(200, text="<html>"),
    lambda _req: httpx.Response(200, json={"available": None}),
    _drops(99),
])
def test_available_sessions_is_one_when_it_cannot_tell(monkeypatch, answer) -> None:
    assert _authed(monkeypatch, answer, sleep=lambda _s: None).available_sessions() == 1


def test_authenticated_saves_stay_spaced_for_the_per_minute_ceiling(monkeypatch) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(200, json={"job_id": "J"})
        if req.method == "GET":
            return httpx.Response(200, json={"status": "success", "timestamp": STAMP})
        return httpx.Response(200)

    waits: list[float] = []
    clock = iter([100.0, 103.0, 112.0, 200.0, 200.0])
    spn = _authed(monkeypatch, handler, sleep=waits.append, monotonic=lambda: next(clock, 300.0))
    spn._submit(URL)
    spn._submit(URL)
    assert waits == [archive_org.SAVE_MIN_INTERVAL_S - 3.0]
    spn._submit(URL)
    assert len(waits) == 1  # long enough has passed


def test_the_session_limit_stops_rather_than_fails_the_url() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(200, json={"job_id": "J"})
        return httpx.Response(200, json={"status": "error",
                                         "status_ext": "error:user-session-limit"})

    with pytest.raises(SpnRateLimited):
        _spn(handler).capture(URL)


# --- a save that outlives the poll deadline ------------------------------------------------


def _pending(cdx) -> tuple[SpnClient, list[httpx.Request]]:
    """SPN2 accepts the save and never finishes the job inside the deadline."""
    calls: list[httpx.Request] = []
    ticks = iter(range(0, 100000, 400))

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if req.method == "POST":
            return httpx.Response(200, json={"job_id": "J"})
        if req.method == "HEAD":
            return httpx.Response(200)
        if req.url.path == "/cdx/search/cdx":
            return cdx(req)
        return httpx.Response(200, json={"status": "pending"})

    archive_org._last_unauth_capture_at = None
    spn = SpnClient(client=_client(handler), poll_interval_s=0, sleep=lambda _s: None,
                    monotonic=lambda: float(next(ticks)))
    return spn, calls


def test_a_timeout_with_a_cdx_snapshot_from_that_save_is_a_capture() -> None:
    later = "20991231000000"
    seen = {}

    def cdx(req: httpx.Request) -> httpx.Response:
        seen.update(req.url.params)
        return httpx.Response(200, json=[["timestamp", "statuscode"], [later, "200"]])

    spn, calls = _pending(cdx)
    cap = spn.capture(URL)
    assert cap.timestamp == later
    assert sum(req.method == "POST" for req in calls) == 1  # no second save
    assert seen["url"] == URL and "to" not in seen and len(seen["from"]) == 14


@pytest.mark.parametrize("rows", [
    [],
    [["timestamp", "statuscode"]],
    [["timestamp", "statuscode"], ["20200101000000", "200"]],  # older than the save
    [["timestamp", "statuscode"], ["20991231000000", "503"]],  # not a good snapshot
])
def test_a_timeout_with_no_snapshot_from_that_save_fails(rows) -> None:
    spn, _calls = _pending(lambda _req: httpx.Response(200, json=rows))
    with pytest.raises(SpnError, match="timed out after"):
        spn.capture(URL)


def test_saves_ask_spn2_to_skip_the_first_archive_check() -> None:
    bodies: list[dict[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            bodies.append(dict(httpx.QueryParams(req.content.decode())))
            return httpx.Response(200, json={"job_id": "J"})
        if req.method == "GET":
            return httpx.Response(200, json={"status": "success", "timestamp": STAMP})
        return httpx.Response(200)

    _spn(handler).capture(URL)
    assert bodies == [{"url": URL, "skip_first_archive": "1"}]


def test_the_poll_deadline_is_six_minutes() -> None:
    assert SpnClient(client=_client(lambda _req: httpx.Response(200)))._timeout_s == 360.0


def test_recover_finds_the_snapshot_and_sends_no_save() -> None:
    spn, calls = _pending(lambda _req: httpx.Response(200, json=LISTED))
    assert spn.recover(URL, "20261105000000").timestamp == STAMP
    assert not [req for req in calls if req.method == "POST"]


def test_recover_with_nothing_listed_is_an_error() -> None:
    spn, _calls = _pending(lambda _req: httpx.Response(200, json=[]))
    with pytest.raises(SpnError, match="no snapshot since"):
        spn.recover(URL, "20261105000000")


# --- a save refused because the account's sessions are full --------------------------------

FULL = {"status": "error", "status_ext": "error:user-session-limit",
        "message": "You have already reached the limit of active Save Page Now sessions."}


def _refused(times: int, answer=lambda: httpx.Response(429, json=FULL)):
    """SPN2 refuses `times` saves with `answer`, then takes them. Returns the client, its
    waits and the saves it saw."""
    waits: list[float] = []
    saves: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            saves.append(req)
            if len(saves) <= times:
                return answer()
            return httpx.Response(200, json={"job_id": "J"})
        if req.method == "GET":
            return httpx.Response(200, json={"status": "success", "timestamp": STAMP})
        return httpx.Response(200)

    archive_org._last_unauth_capture_at = None
    return SpnClient(client=_client(handler), poll_interval_s=0, sleep=waits.append,
                     monotonic=lambda: 1e6 + len(saves) * 100), waits, saves


def test_a_full_session_429_waits_and_saves_again() -> None:
    spn, waits, saves = _refused(2)
    assert spn.capture(URL).timestamp == STAMP
    assert waits == list(archive_org.SESSION_BACKOFF_S[:2])
    assert len(saves) == 3


def test_sessions_that_stay_full_stop_the_run() -> None:
    spn, waits, saves = _refused(99)
    with pytest.raises(SpnRateLimited):
        spn.capture(URL)
    assert waits == list(archive_org.SESSION_BACKOFF_S)
    assert len(saves) == len(archive_org.SESSION_BACKOFF_S) + 1


def test_any_other_429_stops_at_once() -> None:
    spn, waits, saves = _refused(99, lambda: httpx.Response(429, text="slow down"))
    with pytest.raises(SpnRateLimited):
        spn.capture(URL)
    assert waits == [] and len(saves) == 1


# --- a 429 on the status poll --------------------------------------------------------------


def _poll_refused(times: int):
    """The status poll draws an HTML 429 `times` times, then the job succeeds."""
    waits: list[float] = []
    left = iter(range(times))

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(200, json={"job_id": "J"})
        if req.method == "HEAD":
            return httpx.Response(200)
        if next(left, None) is not None:
            return httpx.Response(429, text="<h1>429 Too Many Requests</h1>")
        return httpx.Response(200, json={"status": "success", "timestamp": STAMP})

    archive_org._last_unauth_capture_at = None
    return SpnClient(client=_client(handler), poll_interval_s=0, sleep=waits.append), waits


def test_a_429_on_the_poll_waits_and_keeps_polling() -> None:
    spn, waits = _poll_refused(2)
    assert spn.capture(URL).timestamp == STAMP
    assert waits == list(archive_org.SESSION_BACKOFF_S[:2])


def test_a_poll_that_stays_refused_stops_and_never_fails_the_url() -> None:
    spn, waits = _poll_refused(99)
    with pytest.raises(SpnRateLimited):
        spn.capture(URL)
    assert waits == list(archive_org.SESSION_BACKOFF_S)


def test_a_missing_snapshot_carries_its_timestamp() -> None:
    spn, _waits, _calls = _saved(lambda _req: httpx.Response(404))
    with pytest.raises(archive_org.SpnSnapshotMissing) as caught:
        spn.capture(URL)
    assert caught.value.timestamp == STAMP
