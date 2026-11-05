"""P3 task 3 — the archive capture step, behind fakes. No network: every SPN2 answer comes
from an httpx.MockTransport, and the live client is never built. The repo is a tmp_path
with a small collected corpus, the REAL ai.yaml, and a triage ledger written here."""

from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

import httpx
import pytest
import yaml

from ingest import ai, capture, prefilter, triage_run
from ingest.checks import archive_links
from ingest.sources import archive_org
from tests.test_prefilter import SUBSTANTIVE, _record

REAL_AI_YAML = Path(ai.repo_root()) / "data" / "config" / "ai.yaml"
GOOD = "https://example.house.gov/media/good"
BAD = "https://example.house.gov/media/fail"
NO = "https://example.house.gov/media/no"


def _handler(req: httpx.Request) -> httpx.Response:
    """SPN2 as a fake: a URL with "fail" errors, "limited" draws a 429, the rest save."""
    if req.method == "POST":
        url = dict(httpx.QueryParams(req.content.decode()))["url"]
        if "limited" in url:
            return httpx.Response(429)
        return httpx.Response(200, json={"job_id": "fail" if "fail" in url else "ok"})
    if req.method == "GET":
        if req.url.path.endswith("/fail"):
            return httpx.Response(200, json={"status": "error", "status_ext": "error:blocked"})
        return httpx.Response(200, json={"status": "success", "timestamp": "20261104120000"})
    return httpx.Response(200)  # HEAD verify


def _fake() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(_handler))


@pytest.fixture(autouse=True)
def _unauth(monkeypatch) -> None:
    monkeypatch.delenv("IA_S3_ACCESS", raising=False)
    monkeypatch.delenv("IA_S3_SECRET", raising=False)
    monkeypatch.setattr(archive_org, "_last_unauth_capture_at", None)


def _repo(tmp_path: Path, monkeypatch, verdicts: dict[str, bool | None],
          live: bool | None = None) -> Path:
    """A corpus of one statement per URL; `verdicts` is the triage gate's answer for each
    (None: not triaged). `live` writes archive.yaml (None: no file)."""
    data_dir = tmp_path / "data"
    statements = data_dir / "raw" / "crec" / "statements"
    statements.mkdir(parents=True)
    records = []
    for i, url in enumerate(verdicts):
        record = _record(f"Mr. X. Mr. Speaker, item {i} {SUBSTANTIVE}", member_id="M000001",
                         date=f"2026-10-{1 + i:02d}", granule_id=f"G{i}")
        record["url"] = url
        records.append(record)
    (statements / "M000001.json").write_text(json.dumps({
        "member": {"id": "M000001", "name": "Member One", "party": "D"},
        "statements": records,
    }), encoding="utf-8")
    (data_dir / "config").mkdir(parents=True)
    shutil.copy(REAL_AI_YAML, data_dir / "config" / "ai.yaml")
    if live is not None:
        (data_dir / "config" / "archive.yaml").write_text(
            yaml.safe_dump({"live_capture": live}), encoding="utf-8")
    survivors = prefilter.run_prefilter(records, frozenset())["statements"]
    version = ai.load_config(data_dir).task(triage_run.TASK).prompt_version
    ledger = data_dir / "raw" / "triage" / f"{version}.jsonl"
    ledger.parent.mkdir(parents=True)
    with ledger.open("w", encoding="utf-8") as handle:
        for s in survivors:
            if verdicts[s["url"]] is not None:
                handle.write(json.dumps({"text_sha256": triage_run.fingerprint(s),
                                         triage_run.VERDICT_FIELD: verdicts[s["url"]]}) + "\n")
    monkeypatch.setattr(capture, "repo_root", lambda: tmp_path)
    return data_dir


def _go(argv=None, **kwargs) -> int:
    kwargs.setdefault("sleep", lambda _s: None)
    return capture.run(argv or [], **kwargs)


def _lines(data_dir: Path) -> list[dict]:
    path = capture.ledger_path(data_dir)
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


# --- the switch ----------------------------------------------------------------------------


def test_the_shipped_config_keeps_live_capture_off() -> None:
    """Owner ruling 2026-11-04: off until the owner turns it on."""
    assert capture.live_capture_enabled(Path(ai.repo_root()) / "data") is False


def test_live_capture_reads_true_only(tmp_path: Path) -> None:
    assert capture.live_capture_enabled(tmp_path) is False  # no file
    (tmp_path / "config").mkdir()
    path = tmp_path / "config" / "archive.yaml"
    for text, expected in (("", False), ("live_capture: yes-please", False),
                           ("live_capture: false", False), ("live_capture: true", True)):
        path.write_text(text, encoding="utf-8")
        assert capture.live_capture_enabled(tmp_path) is expected


def test_opt_in_off_refuses_a_live_run_and_sends_nothing(tmp_path, monkeypatch, capsys) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True}, live=False)

    def boom(**_kw):
        raise AssertionError("a live client was built with live capture off")

    monkeypatch.setattr(capture, "SpnClient", boom)
    assert _go() == capture.EXIT_REFUSED
    assert "REFUSED: live capture is off" in capsys.readouterr().out
    assert not capture.ledger_path(data_dir).exists()
    assert not (data_dir / capture.RESPONSES).exists()


def test_opt_in_on_builds_the_live_client(tmp_path, monkeypatch, capsys) -> None:
    """With the switch on and no fake injected, the run builds the real client (here a
    stand-in, so nothing leaves the machine)."""
    _repo(tmp_path, monkeypatch, {GOOD: True}, live=True)
    built = {}

    class StandIn:
        authenticated = True

        def __init__(self, **kwargs) -> None:
            built.update(kwargs)

        def available_sessions(self) -> int:
            return 1

        def capture(self, url):
            return archive_org.Capture(url, f"https://web.archive.org/web/1/{url}",
                                       "20261104120000", "2026-11-04T12:00:00Z")

        def close(self) -> None:
            built["closed"] = True

    monkeypatch.setattr(capture, "SpnClient", StandIn)
    assert _go() == capture.EXIT_OK
    assert built["client"] is None and built["closed"] is True
    assert "authenticated (IA S3 keys)" in capsys.readouterr().out


def test_the_command_line_opts_in_for_one_run(tmp_path, monkeypatch) -> None:
    """`archive.yaml` is committed and stays off: a local live run uses the flag."""
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True}, live=False)
    built = {}

    class StandIn:
        authenticated = False

        def __init__(self, **kwargs) -> None:
            built.update(kwargs)

        def available_sessions(self) -> int:
            return 1

        def capture(self, url):
            return archive_org.Capture(url, f"https://web.archive.org/web/1/{url}",
                                       "20261104120000", "2026-11-04T12:00:00Z")

        def close(self) -> None:
            pass

    monkeypatch.setattr(capture, "SpnClient", StandIn)
    assert _go(["--live-capture"]) == capture.EXIT_OK
    assert built["client"] is None
    assert _lines(data_dir)[0]["status"] == "captured"


# --- what is captured -----------------------------------------------------------------------


def test_only_statements_the_gate_passed_are_captured_once_each() -> None:
    a = {"url": GOOD, "segments": ["one"]}
    b = {"url": GOOD, "segments": ["two"]}  # same page, another text
    c = {"url": NO, "segments": ["three"]}
    d = {"url": "", "segments": ["four"]}
    e = {"url": BAD, "segments": ["five"]}  # never triaged
    verdicts = {triage_run.fingerprint(s): {triage_run.VERDICT_FIELD: v}
                for s, v in ((a, True), (b, True), (c, False), (d, True))}
    assert capture.select_urls([a, b, c, d, e], verdicts) == [GOOD]


def test_to_capture_skips_captured_and_failed_unless_asked() -> None:
    captures = {"a": {"status": "captured"}, "b": {"status": "failed"},
                "c": {"status": "dead"}}
    assert capture.to_capture(["a", "b", "c", "d"], captures) == ["c", "d"]
    assert capture.to_capture(["a", "b", "c", "d"], captures, retry_failed=True) == [
        "b", "c", "d"]


def test_capture_success_is_recorded_with_its_raw_responses(tmp_path, monkeypatch,
                                                            capsys) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True, NO: False}, live=False)
    assert _go(client=_fake()) == capture.EXIT_OK
    out = capsys.readouterr().out
    assert "1 source URL(s) passed the triage gate" in out
    assert "unauthenticated: at most 1 capture every 15 s" in out
    (line,) = _lines(data_dir)
    assert line["url"] == GOOD and line["status"] == "captured"
    cap = capture.verified_capture(GOOD, capture.load_captures(capture.ledger_path(data_dir)))
    assert cap.archive_url == f"https://web.archive.org/web/20261104120000/{GOOD}"
    assert cap.captured_at == "2026-11-04T12:00:00Z"
    (raw,) = (data_dir / capture.RESPONSES).glob("*.jsonl")
    kinds = [json.loads(x)["kind"] for x in raw.read_text(encoding="utf-8").splitlines()]
    assert kinds == ["save", "status", "verify"]
    # A re-run sends nothing: the capture file already holds it.
    assert _go(client=_fake()) == capture.EXIT_OK
    assert len(_lines(data_dir)) == 1
    assert "0 to capture" in capsys.readouterr().out


def test_capture_failure_is_recorded_and_never_a_live_capture(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {BAD: True, GOOD: True})
    assert _go(client=_fake()) == capture.EXIT_OK
    captures = capture.load_captures(capture.ledger_path(data_dir))
    assert captures[BAD]["status"] == "failed" and "error:blocked" in captures[BAD]["error"]
    assert capture.verified_capture(BAD, captures) is None
    assert capture.verified_capture(GOOD, captures) is not None
    # Not asked again by default; asked again with --retry-failed.
    assert _go(client=_fake()) == capture.EXIT_OK
    assert len(_lines(data_dir)) == 2
    assert _go(["--retry-failed"], client=_fake()) == capture.EXIT_OK
    assert [x["url"] for x in _lines(data_dir)].count(BAD) == 2


def test_a_429_stops_the_run_without_recording_a_failure(tmp_path, monkeypatch) -> None:
    limited = "https://example.house.gov/media/limited"
    # Newest first: the limited page is asked first, and the run stops before the other.
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True, limited: True})
    assert _go(client=_fake()) == capture.EXIT_RATE_LIMITED
    assert not capture.ledger_path(data_dir).exists()


def test_limit_bounds_a_run(tmp_path, monkeypatch) -> None:
    urls = {f"https://example.house.gov/media/{i}": True for i in range(3)}
    data_dir = _repo(tmp_path, monkeypatch, urls)
    assert _go(["--limit", "2"], client=_fake()) == capture.EXIT_OK
    assert len(_lines(data_dir)) == 2


def test_dry_run_and_no_verdicts_send_nothing(tmp_path, monkeypatch, capsys) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    assert _go(["--dry-run"], client=_fake()) == capture.EXIT_OK
    assert not capture.ledger_path(data_dir).exists()
    data_dir = _repo(tmp_path / "other", monkeypatch, {GOOD: None})
    assert _go(client=_fake()) == capture.EXIT_OK
    assert "no triage verdicts under" in capsys.readouterr().out
    assert not capture.ledger_path(data_dir).exists()


# --- a capture that dies ---------------------------------------------------------------------


def test_a_dead_capture_is_hidden_until_recaptured(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    assert _go(client=_fake()) == capture.EXIT_OK
    path = capture.ledger_path(data_dir)
    monkeypatch.setattr(archive_links, "CAPTURES_PATH", path)
    monkeypatch.setattr(archive_links, "_load_statements", lambda: [])
    gone = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(404)))
    with monkeypatch.context() as m:
        m.setattr(archive_links.httpx, "Client", lambda: gone)
        assert archive_links.main() == 0  # unpublished: marked, not a site failure
    captures = capture.load_captures(path)
    assert captures[GOOD]["status"] == "dead"
    assert capture.verified_capture(GOOD, captures) is None
    # The next capture run asks again, and the new capture is live.
    assert _go(client=_fake()) == capture.EXIT_OK
    assert capture.verified_capture(GOOD, capture.load_captures(path)) is not None


def test_the_committed_report_never_names_an_unpublished_capture(tmp_path, monkeypatch,
                                                                capsys) -> None:
    """The capture file says which pages passed the triage gate: counts only, never URLs,
    reach `data/quality/archive-status.json`."""
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    assert _go(client=_fake()) == capture.EXIT_OK
    report_path = tmp_path / "archive-status.json"
    monkeypatch.setattr(archive_links, "CAPTURES_PATH", capture.ledger_path(data_dir))
    monkeypatch.setattr(archive_links, "STATUS_PATH", report_path)
    monkeypatch.setattr(archive_links, "_load_statements", lambda: [
        {"id": "s1", "archive_url": "https://web.archive.org/web/1/https://ok"}])
    alive = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(200)))
    with monkeypatch.context() as m:
        m.setattr(archive_links.httpx, "Client", lambda: alive)
        assert archive_links.main() == 0
    assert "swept 1 unpublished capture(s): 1 alive, 0 dead" in capsys.readouterr().out
    report = report_path.read_text(encoding="utf-8")
    assert json.loads(report)["checked"] == 1 and GOOD not in report
    assert capture.load_captures(capture.ledger_path(data_dir))[GOOD]["status"] == "captured"


def test_mark_dead_appends_one_line_each(tmp_path: Path) -> None:
    path = tmp_path / "captures.jsonl"
    path.write_text("\n", encoding="utf-8")  # a blank line is skipped
    capture.mark_dead(path, [{"url": "a", "archive_url": "w/a"}], now="2026-11-04T00:00:00Z")
    assert capture.load_captures(path) == {"a": {"url": "a", "status": "dead",
                                                 "archive_url": "w/a",
                                                 "ts": "2026-11-04T00:00:00Z"}}


# --- a failed line that names a snapshot ---------------------------------------------------

OLD = "20261105163622"


def _failed_check(data_dir: Path, url: str) -> None:
    """The line a 503 on the snapshot check left: SPN2 saved the page at OLD."""
    capture._append(capture.ledger_path(data_dir), {
        "url": url, "status": "failed", "ts": "2026-11-05T16:36:45+00:00",
        "error": f"archive_url did not resolve (HTTP 503): "
                 f"https://web.archive.org/web/{OLD}/{url}"})


def _recording(head_status: int) -> tuple[httpx.Client, list[httpx.Request]]:
    """`_handler`, except a check of the OLD snapshot answers `head_status`."""
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if req.method == "HEAD" and OLD in str(req.url):
            return httpx.Response(head_status)
        return _handler(req)

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_a_retry_marks_a_snapshot_that_now_resolves_without_a_new_save(tmp_path,
                                                                       monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    _failed_check(data_dir, GOOD)
    client, calls = _recording(200)
    assert _go(["--retry-failed"], client=client) == capture.EXIT_OK
    assert not [req for req in calls if req.method == "POST"]
    entry = capture.load_captures(capture.ledger_path(data_dir))[GOOD]
    assert entry["status"] == "captured" and entry["timestamp"] == OLD


def test_a_retry_saves_again_when_the_named_snapshot_is_gone(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    _failed_check(data_dir, GOOD)
    client, calls = _recording(404)
    assert _go(["--retry-failed"], client=client) == capture.EXIT_OK
    assert len([req for req in calls if req.method == "POST"]) == 1
    entry = capture.load_captures(capture.ledger_path(data_dir))[GOOD]
    assert entry["status"] == "captured" and entry["timestamp"] == "20261104120000"


def test_a_429_on_the_recheck_stops_the_run(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    _failed_check(data_dir, GOOD)
    client, calls = _recording(429)
    assert _go(["--retry-failed"], client=client) == capture.EXIT_RATE_LIMITED
    assert not [req for req in calls if req.method == "POST"]
    assert len(_lines(data_dir)) == 1


# --- archive.org out of reach --------------------------------------------------------------


def _down(times: int) -> httpx.Client:
    """`_handler` behind a connection that is refused `times` times first."""
    left = iter(range(times))

    def handler(req: httpx.Request) -> httpx.Response:
        if next(left, None) is not None:
            raise httpx.ConnectError("refused")
        return _handler(req)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_transport_error_then_success_is_a_capture(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    assert _go(client=_down(2)) == capture.EXIT_OK
    assert capture.load_captures(capture.ledger_path(data_dir))[GOOD]["status"] == "captured"


def test_archive_org_staying_down_stops_cleanly_and_a_resume_picks_the_url_up(
        tmp_path, monkeypatch, capsys) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True, BAD: True})
    assert _go(client=_down(99)) == capture.EXIT_UNREACHABLE
    assert not capture.ledger_path(data_dir).exists()  # no URL is marked failed
    assert "archive.org unreachable" in capsys.readouterr().out
    assert _go(client=_fake()) == capture.EXIT_OK
    captures = capture.load_captures(capture.ledger_path(data_dir))
    assert capture.verified_capture(GOOD, captures) is not None


def test_archive_org_going_down_on_a_recheck_stops_and_keeps_the_line(tmp_path,
                                                                      monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    _failed_check(data_dir, GOOD)
    assert _go(["--retry-failed"], client=_down(99)) == capture.EXIT_UNREACHABLE
    assert len(_lines(data_dir)) == 1


# --- several captures at once --------------------------------------------------------------


class Stub:
    """An SPN client that records its calls; `act(url)` runs inside each capture."""

    def __init__(self, act=lambda _url: None) -> None:
        self.act = act
        self.lock = threading.Lock()
        self.calls: list[str] = []
        self.flying = 0
        self.peak = 0

    def capture(self, url: str) -> archive_org.Capture:
        with self.lock:
            self.calls.append(url)
            self.flying += 1
            self.peak = max(self.peak, self.flying)
        try:
            self.act(url)
        finally:
            with self.lock:
                self.flying -= 1
        return archive_org.Capture(url, f"https://web.archive.org/web/20261104120000/{url}",
                                   "20261104120000", "2026-11-04T12:00:00Z")


def _urls(n: int) -> list[str]:
    return [f"https://example.house.gov/{i}" for i in range(n)]


def test_captures_in_flight_reach_the_bound_and_never_pass_it(tmp_path: Path) -> None:
    together = threading.Barrier(3, timeout=10)
    first_wave = iter(range(3))

    def act(_url: str) -> None:
        if next(first_wave, None) is not None:
            together.wait()

    stub = Stub(act)
    outcome = capture.capture_all(stub, _urls(20), tmp_path / "c.jsonl", workers=3,
                                  now=lambda: "t")
    assert stub.peak == 3
    assert outcome.captured == 20 and outcome.failed == 0 and outcome.status == "complete"
    assert len(capture.load_captures(tmp_path / "c.jsonl")) == 20


@pytest.mark.parametrize(("error", "status"), [
    (archive_org.SpnRateLimited("429"), "rate-limited"),
    (archive_org.SpnUnreachable("down"), "unreachable"),
])
def test_a_stop_from_any_worker_stops_them_all(tmp_path: Path, error, status) -> None:
    urls = _urls(30)
    released = threading.Event()

    def act(url: str) -> None:
        if url == urls[0]:
            raise error
        assert released.wait(10)

    stub = Stub(act)
    outcome = capture.capture_all(stub, urls, tmp_path / "c.jsonl", workers=3, now=lambda: "t",
                                  progress=lambda _line: released.set())
    assert outcome.status == status
    assert len(stub.calls) <= 3  # the ones in flight, and nothing after
    captures = capture.load_captures(tmp_path / "c.jsonl")
    assert urls[0] not in captures  # a stop never fails the URL
    assert outcome.captured == len(captures) == len(stub.calls) - 1


def test_an_unexpected_error_stops_the_workers_and_surfaces(tmp_path: Path) -> None:
    def act(_url: str) -> None:
        raise RuntimeError("a bug")

    stub = Stub(act)
    with pytest.raises(RuntimeError, match="a bug"):
        capture.capture_all(stub, _urls(30), tmp_path / "c.jsonl", workers=3, now=lambda: "t")
    assert len(stub.calls) <= 3


def test_workers_give_the_same_results_as_the_serial_path(tmp_path: Path) -> None:
    urls = [*_urls(7), BAD, *[f"{u}/x" for u in _urls(5)]]
    results = {}
    for workers in (1, 4):
        path = tmp_path / f"{workers}.jsonl"
        spn = archive_org.SpnClient(client=_fake(), poll_interval_s=0, sleep=lambda _s: None)
        outcome = capture.capture_all(spn, urls, path, workers=workers, now=lambda: "t")
        results[workers] = (outcome, capture.load_captures(path))
    assert results[1] == results[4]
    assert results[1][0].failed == 1 and results[1][0].captured == len(urls) - 1


def test_a_limit_holds_with_workers(tmp_path: Path) -> None:
    stub = Stub()
    outcome = capture.capture_all(stub, _urls(10), tmp_path / "c.jsonl", limit=4, workers=3,
                                  now=lambda: "t")
    assert outcome.status == "limit" and sorted(stub.calls) == sorted(_urls(4))


@pytest.mark.parametrize(("config", "free", "expected"), [
    (None, 9, capture.DEFAULT_MAX_CONCURRENT),  # no file: the default
    ({"max_concurrent_captures": 4}, 3, 3),     # SPN2 has fewer free
    ({"max_concurrent_captures": 2}, 3, 2),     # the config is lower
    ({"max_concurrent_captures": 4}, 0, 1),     # never fewer than one
])
def test_the_bound_is_the_lower_of_the_config_and_the_free_sessions(tmp_path, config, free,
                                                                    expected) -> None:
    class Sessions:
        def available_sessions(self) -> int:
            return free

    if config is not None:
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "archive.yaml").write_text(yaml.safe_dump(config),
                                                          encoding="utf-8")
    assert capture.capture_workers(Sessions(), tmp_path) == expected


def test_the_shipped_bound_is_four() -> None:
    assert capture._config(Path(ai.repo_root()) / "data")["max_concurrent_captures"] == 4


# --- a failed line for a save that timed out -----------------------------------------------


def _timed_out(data_dir: Path, url: str) -> None:
    capture._append(capture.ledger_path(data_dir), {
        "url": url, "status": "failed", "ts": "2026-11-05T18:11:02+00:00",
        "error": "SPN2 capture timed out after 180s"})


def _cdx(rows: list[list[str]] | int) -> tuple[httpx.Client, list[httpx.Request]]:
    """`_handler` with CDX answering `rows`, or that status when it is a number."""
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if req.url.path == "/cdx/search/cdx":
            if isinstance(rows, int):
                return httpx.Response(rows)
            return httpx.Response(200, json=rows)
        return _handler(req)

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_a_retry_recovers_a_timed_out_save_from_cdx_without_a_new_save(tmp_path,
                                                                       monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    _timed_out(data_dir, GOOD)
    landed = "20261105181104"
    client, calls = _cdx([["timestamp", "statuscode"], [landed, "200"]])
    assert _go(["--retry-failed"], client=client) == capture.EXIT_OK
    assert not [req for req in calls if req.method == "POST"]
    # The search starts before the save: 18:11:02 less the 180 s deadline and the slack.
    assert [req.url.params["from"] for req in calls if "cdx" in req.url.path] == [
        "20261105180702"]
    entry = capture.load_captures(capture.ledger_path(data_dir))[GOOD]
    assert entry["status"] == "captured" and entry["timestamp"] == landed


def test_a_retry_saves_again_when_cdx_has_nothing_from_the_timed_out_save(tmp_path,
                                                                          monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    _timed_out(data_dir, GOOD)
    client, calls = _cdx([])
    assert _go(["--retry-failed"], client=client) == capture.EXIT_OK
    assert len([req for req in calls if req.method == "POST"]) == 1
    entry = capture.load_captures(capture.ledger_path(data_dir))[GOOD]
    assert entry["status"] == "captured" and entry["timestamp"] == "20261104120000"


def test_a_429_from_cdx_on_a_recovery_stops_the_run(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    _timed_out(data_dir, GOOD)
    client, calls = _cdx(429)
    assert _go(["--retry-failed"], client=client) == capture.EXIT_RATE_LIMITED
    assert not [req for req in calls if req.method == "POST"]
    assert len(_lines(data_dir)) == 1


# --- the account's sessions full -----------------------------------------------------------


def _full(times: int) -> httpx.Client:
    """`_handler`, with the first `times` saves refused for full sessions."""
    left = iter(range(times))

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST" and next(left, None) is not None:
            return httpx.Response(429, json={"status_ext": "error:user-session-limit"})
        return _handler(req)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_full_sessions_cost_a_wait_not_the_run(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    assert _go(client=_full(1)) == capture.EXIT_OK
    assert capture.load_captures(capture.ledger_path(data_dir))[GOOD]["status"] == "captured"


def test_sessions_that_stay_full_stop_without_failing_the_url(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, {GOOD: True})
    assert _go(client=_full(99)) == capture.EXIT_RATE_LIMITED
    assert not capture.ledger_path(data_dir).exists()
