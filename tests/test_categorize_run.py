"""The run that fills the review queue, behind fakes: a fake model through the real
`ingest/ai.py`, a fake archive.org through the real SPN2 client, the real `ai.yaml` and
prompts. No network, no credential, no spend. The repo is a tmp_path."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import anthropic
import httpx
import httpx2
import pytest
import yaml

from curation import review
from ingest import ai, capture, categorize_run, triage_run
from ingest.sources import archive_org
from tests.test_capture import _fake, _handler
from tests.test_prefilter import SUBSTANTIVE, _record
from tests.test_triage_run import REQUEST, FakeClock, _limited

FIXED_NOW = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)
REAL_AI_YAML = Path(ai.repo_root()) / "data" / "config" / "ai.yaml"
SUGGESTION = {"topic": "Health", "stance": "for", "proposition": "capping insulin",
              "specificity": 2, "priority_signal": False, "confidence": "high"}


def _answer(data: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data)}], "stop_reason": "end_turn",
            "usage": {"input_tokens": 1000, "output_tokens": 1000}, "request_id": "req"}


class Model:
    """A fake model: the gate passes a text holding "pass"; the categorizer answers
    SUGGESTION unless `on_categorize(text, n)` says otherwise (a payload or an exception)."""

    def __init__(self, on_categorize=None) -> None:
        self.on_categorize = on_categorize or (lambda text, n: _answer(SUGGESTION))
        self.triaged = 0
        self.categorized = 0

    def __call__(self, request: dict) -> dict:
        text = request["messages"][0]["content"]
        if request["model"] == "claude-haiku-5-5":
            self.triaged += 1
            return _answer({"takes_policy_position": "pass" in text})
        self.categorized += 1
        answer = self.on_categorize(text, self.categorized - 1)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _member(data_dir: Path, member_id: str, party: str, texts: list[str]) -> None:
    statements = data_dir / "raw" / "crec" / "statements"
    statements.mkdir(parents=True, exist_ok=True)
    records = []
    for i, text in enumerate(texts):
        record = _record(f"Mr. X. Mr. Speaker, {text} {SUBSTANTIVE}", member_id=member_id,
                         date=f"2026-{1 + i % 9:02d}-{1 + i % 27:02d}",
                         granule_id=f"{member_id}-{i}")
        record["url"] = f"https://example.house.gov/{member_id}/{i}"
        records.append(record)
    (statements / f"{member_id}.json").write_text(json.dumps({
        "member": {"id": member_id, "name": f"Member {member_id}", "party": party},
        "statements": records,
    }), encoding="utf-8")


def _repo(tmp_path: Path, monkeypatch, *, d=("pass d0", "pass d1"), r=("pass r0", "pass r1"),
          outsider: bool = False) -> Path:
    data_dir = tmp_path / "data"
    _member(data_dir, "D000001", "D", list(d))
    _member(data_dir, "R000002", "R", list(r))
    if outsider:
        _member(data_dir, "X000003", "D", ["pass outsider"])
    (data_dir / "config").mkdir(parents=True)
    (data_dir / "quality").mkdir(parents=True)
    shutil.copy(REAL_AI_YAML, data_dir / "config" / "ai.yaml")
    (data_dir / "config" / "statement-pilot.yaml").write_text(yaml.safe_dump({"cells": [
        {"party": "D", "chamber": "house", "members": [{"id": "D000001"}]},
        {"party": "R", "chamber": "house", "members": [{"id": "R000002"}]},
    ]}), encoding="utf-8")
    monkeypatch.setattr(categorize_run, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(archive_org, "_last_unauth_capture_at", None)
    monkeypatch.delenv("IA_S3_ACCESS", raising=False)
    monkeypatch.delenv("IA_S3_SECRET", raising=False)
    return data_dir


def _go(argv=None, **kwargs) -> int:
    kwargs.setdefault("now", lambda: FIXED_NOW)
    kwargs.setdefault("sleep", lambda _s: None)
    return categorize_run.run(argv or [], **kwargs)


def _paid(model, *extra: str, cap: str = "5", **kwargs) -> int:
    kwargs.setdefault("client", _fake())
    return _go(["--approved-cap", cap, *extra], completer=model, **kwargs)


def _queue(data_dir: Path) -> list[dict]:
    path = review.queue_path(data_dir)
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


# --- count before spend (decision 4) -------------------------------------------------------


def test_without_the_flag_it_reports_saves_and_calls_nothing(tmp_path, monkeypatch,
                                                             capsys) -> None:
    data_dir = _repo(tmp_path, monkeypatch, outsider=True)

    def never(_request):
        raise AssertionError("an AI call before approval")

    assert _go(completer=never) == categorize_run.EXIT_OK
    out = capsys.readouterr().out
    assert "NO AI CALL MADE" in out
    assert "congressional_record" in out and "D000001 D" in out
    assert "no verdicts yet" in out
    assert "estimate, total: $" in out
    saved = json.loads((data_dir / "raw" / "categorize"
                        / "2026-11-04-count-before-spend.json").read_text(encoding="utf-8"))
    assert saved["counts"]["steps"]["collected"] == 4  # the outsider is not in the pilot
    assert saved["outside_pilot_records_ignored"] == 1
    assert saved["counts"]["steps"]["to_categorizer_worst_case"] == 4
    assert set(saved["counts"]["per_member"]) == {"D000001", "R000002"}
    assert saved["counts"]["per_source"]["congressional_record"]["kept"] == 4
    assert saved["fairness"]["triage"] == []
    assert not review.queue_path(data_dir).exists()


def test_over_the_cap_is_refused_before_any_call(tmp_path, monkeypatch, capsys) -> None:
    data_dir = _repo(tmp_path, monkeypatch)
    model = Model()
    assert _paid(model, cap="0.001") == categorize_run.EXIT_OVER_CAP
    assert "REFUSED: the estimate" in capsys.readouterr().out
    assert model.triaged == 0 and model.categorized == 0
    assert not categorize_run.spend_path(data_dir, "preview-1").exists()


def test_live_capture_must_be_opted_in_before_any_spend(tmp_path, monkeypatch, capsys) -> None:
    _repo(tmp_path, monkeypatch)
    model = Model()
    assert _paid(model, client=None) == categorize_run.EXIT_REFUSED
    assert "live capture is off" in capsys.readouterr().out
    assert model.triaged == 0


def test_the_estimate_takes_the_higher_of_length_and_the_logged_mean(tmp_path,
                                                                     monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch)
    config = ai.load_config(data_dir)
    task = config.task(categorize_run.CATEGORIZE)
    order = [{"member_id": "M", "segments": ["words " * 100], "date": "2026-01-01"}]

    def total() -> dict:
        return categorize_run.estimate(config, order, {}, set(), 25, data_dir)

    assert total()["categorize"]["logged_calls"] == 0
    assert total()["categorize"]["usd"] == total()["categorize"]["by_length_usd"]
    log = data_dir / "quality" / "ai-calls" / "2026-10.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text("\n".join(json.dumps(x) for x in (
        {"task": task.name, "prompt_version": task.prompt_version, "cached": False,
         "cost_usd": 2.0, "output_tokens": 300},
        {"task": task.name, "prompt_version": task.prompt_version, "cached": True,
         "cost_usd": 9.0, "output_tokens": 1},
        {"task": task.name, "prompt_version": "old", "cached": False, "cost_usd": 9.0,
         "output_tokens": 1},
    )) + "\n\n", encoding="utf-8")
    assert total()["categorize"]["logged_calls"] == 1
    assert total()["categorize"]["usd"] == 2.0


# --- the run -------------------------------------------------------------------------------


def test_a_run_writes_preview_items_review_can_read(tmp_path, monkeypatch, capsys) -> None:
    data_dir = _repo(tmp_path, monkeypatch, d=("pass d0", "reject d1"))
    model = Model()
    assert _paid(model) == categorize_run.EXIT_OK
    assert model.triaged == 4 and model.categorized == 3  # the gate's `no` is never asked
    lines = _queue(data_dir)
    assert {x["preview"] for x in lines} == {"copilot-run, owner-unreviewed"}
    assert {x["member_id"] for x in lines} == {"D000001", "R000002"}
    items = review.load_queue(data_dir)
    assert all(i.preview == "copilot-run, owner-unreviewed" for i in items)
    assert items[0].suggestion == SUGGESTION and items[0].prompt_version == "v3"
    assert items[0].party in ("D", "R") and items[0].id == lines[0]["id"]
    # Each statement's source page was captured first.
    captures = capture.load_captures(capture.ledger_path(data_dir))
    assert {x["url"] for x in lines} == set(captures)
    spent = json.loads(categorize_run.spend_path(data_dir, "preview-1")
                       .read_text(encoding="utf-8"))
    assert spent["spent_usd"] > 0 and spent["approved_cap_usd"] == 5.0
    assert not (data_dir / "statements").exists()
    assert "3 queued as preview" in capsys.readouterr().out


def test_a_rerun_resumes_and_pays_for_nothing_twice(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch)
    assert _paid(Model()) == categorize_run.EXIT_OK
    again = Model()
    assert _paid(again) == categorize_run.EXIT_OK
    assert again.triaged == 0 and again.categorized == 0
    assert len(_queue(data_dir)) == 4


def test_the_cap_covers_the_whole_named_run(tmp_path, monkeypatch, capsys) -> None:
    data_dir = _repo(tmp_path, monkeypatch)
    path = categorize_run.spend_path(data_dir, "preview-1")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"spent_usd": 4.99}), encoding="utf-8")
    assert _paid(Model()) == categorize_run.EXIT_OVER_CAP
    assert "left of the $5.00 cap" in capsys.readouterr().out
    assert _paid(Model(), "--run-name", "other") == categorize_run.EXIT_OK


def test_the_run_stops_at_the_cap_mid_batch(tmp_path, monkeypatch, capsys) -> None:
    texts = [f"pass number {i}" for i in range(14)]
    data_dir = _repo(tmp_path, monkeypatch, d=texts, r=texts[:0] or ("reject r",))
    model = Model()
    code = _paid(model, "--workers", "1", cap="0.4")
    assert code == categorize_run.EXIT_CAP
    assert 0 < len(_queue(data_dir)) < 14  # stopped, not finished
    assert model.categorized == len(_queue(data_dir))
    out = capsys.readouterr().out
    assert "categorize cap" in out and "stopped: run reached its $0.40 cap" in out
    spent = json.loads(categorize_run.spend_path(data_dir, "preview-1")
                       .read_text(encoding="utf-8"))["spent_usd"]
    assert spent <= 0.4


def test_the_triage_gate_stopping_ends_the_run_before_the_categorizer(tmp_path, monkeypatch,
                                                                      capsys) -> None:
    _repo(tmp_path, monkeypatch)
    model = Model()
    monkeypatch.setattr(triage_run, "triage",
                        lambda *a, **k: triage_run.Outcome(status="cap", stop_detail="spent"))
    assert _paid(model) == categorize_run.EXIT_CAP
    assert model.categorized == 0
    assert "stopped: spent" in capsys.readouterr().out


def test_a_stale_stop_file_is_cleared_and_a_live_one_stops(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch)
    stop = data_dir / triage_run.STOP_FILE
    stop.write_text("", encoding="utf-8")
    assert _paid(Model()) == categorize_run.EXIT_OK
    assert not stop.exists()
    run = ai.Run(config=ai.load_config(data_dir), completer=Model(), data_dir=data_dir)
    stop.write_text("", encoding="utf-8")
    outcome = categorize_run.categorize(run, [{"member_id": "M", "segments": ["x"]}],
                                        lambda *_a: None, stop_file=stop)
    assert outcome.status == "stopped"


# --- fairness (decision 4) -----------------------------------------------------------------


def _rejects(n: int, who: str = "d") -> list[str]:
    return [f"reject {who} item {i}" for i in range(n)]


def _passes(n: int, who: str = "d") -> list[str]:
    return [f"pass {who} item {i}" for i in range(n)]


def test_an_uneven_triage_gate_stops_before_the_categorizer(tmp_path, monkeypatch,
                                                            capsys) -> None:
    data_dir = _repo(tmp_path, monkeypatch, d=_rejects(40) + _passes(40),
                     r=_rejects(10, "r") + _passes(70, "r"))
    model = Model()
    assert _paid(model, cap="10") == categorize_run.EXIT_FAIRNESS
    out = capsys.readouterr().out
    assert "STOPPED: the triage step is uneven by party" in out
    assert "UNEVEN, NEEDS REVIEW" in out
    assert model.triaged == 160 and model.categorized == 0
    assert not review.queue_path(data_dir).exists()
    # Reviewed, it goes on, and the verdicts already paid for are not asked again.
    model = Model()
    assert _paid(model, "--fairness-reviewed", "triage", cap="10") == categorize_run.EXIT_OK
    assert model.triaged == 0 and model.categorized == 50  # 25 each, decision 7


def test_an_even_gate_does_not_stop(tmp_path, monkeypatch) -> None:
    _repo(tmp_path, monkeypatch, d=_rejects(30) + _passes(30),
          r=_rejects(30, "r") + _passes(30, "r"))
    assert _paid(Model(), cap="10") == categorize_run.EXIT_OK


def test_triage_rows_are_per_party_and_per_source() -> None:
    def statement(member, source, text):
        return {"member_id": member, "source": source, "segments": [text]}

    order = ([statement("D1", "press", f"d{i}") for i in range(100)]
             + [statement("R1", "record", f"r{i}") for i in range(100)]
             + [statement("R1", "record", "unanswered")])
    verdicts = {triage_run.fingerprint(s): {triage_run.VERDICT_FIELD: i % 2 == 0}
                for i, s in enumerate(order[:100])}
    verdicts |= {triage_run.fingerprint(s): {triage_run.VERDICT_FIELD: i % 10 != 0}
                 for i, s in enumerate(order[100:200])}
    rows = categorize_run.triage_rows(order, verdicts, {"D1": "D", "R1": "R"})
    assert [r["scope"] for r in rows] == ["all sources", "press", "record"]
    assert (rows[0]["D_rate"], rows[0]["R_rate"], rows[0]["uneven"]) == (50.0, 10.0, True)
    assert rows[1]["R_turns"] == 0 and rows[1]["R_rate"] == 0.0
    assert categorize_run.new_flags(rows) == [rows[0]]


def test_an_uneven_prefilter_rule_stops_before_any_spend_unless_accepted(tmp_path, monkeypatch,
                                                                         capsys) -> None:
    _repo(tmp_path, monkeypatch)
    row = {"rule": "ceremonial", "scope": "all sources", "uneven": True, "turns": 100,
           "D": 90, "D_turns": 900, "D_rate": 10.0, "R": 10, "R_turns": 900, "R_rate": 1.1}
    monkeypatch.setattr(categorize_run, "prefilter_rows", lambda *_a: [row])
    model = Model()
    assert _paid(model) == categorize_run.EXIT_FAIRNESS
    out = capsys.readouterr().out
    assert "STOPPED: the prefilter step is uneven" in out and model.triaged == 0
    # The procedural gap is the one the owner accepted (R4): shown, never a stop.
    monkeypatch.setattr(categorize_run, "prefilter_rows",
                        lambda *_a: [dict(row, rule="procedural")])
    assert _paid(model) == categorize_run.EXIT_OK
    assert "(uneven, owner-accepted R4)" in capsys.readouterr().out


# --- who is asked --------------------------------------------------------------------------


def test_select_is_newest_n_of_the_passed_once_per_text() -> None:
    def statement(member, text):
        return {"member_id": member, "segments": [text]}

    a, b, c, shared = (statement("M1", t) for t in ("a", "b", "c", "same"))
    twin = statement("M2", "same")
    unanswered = statement("M2", "open")
    verdicts = {triage_run.fingerprint(s): {triage_run.VERDICT_FIELD: s is not b}
                for s in (a, b, c, shared)}
    order = [a, b, shared, twin, c, unanswered]
    assert categorize_run.select(order, verdicts, 2) == [a, shared]
    assert categorize_run.select(order, verdicts, 5) == [a, shared, c]
    assert categorize_run.select(order, verdicts, 5, assume_pass=True) == [
        a, shared, c, unanswered]


def test_per_member_lowers_the_ceiling_and_cannot_raise_it(tmp_path, monkeypatch,
                                                           capsys) -> None:
    data_dir = _repo(tmp_path, monkeypatch, d=_passes(4), r=_passes(4, "r"))
    model = Model()
    assert _paid(model, "--per-member", "2") == categorize_run.EXIT_OK
    assert model.categorized == 4
    assert len(_queue(data_dir)) == 4
    with pytest.raises(SystemExit):
        _go(["--per-member", "26"])
    with pytest.raises(SystemExit):
        _go(["--workers", "0"])


def test_a_failed_capture_is_not_categorized(tmp_path, monkeypatch, capsys) -> None:
    data_dir = _repo(tmp_path, monkeypatch, d=("pass d0",), r=("pass r0",))
    records = data_dir / "raw" / "crec" / "statements" / "D000001.json"
    payload = json.loads(records.read_text(encoding="utf-8"))
    payload["statements"][0]["url"] = "https://example.house.gov/fail"
    records.write_text(json.dumps(payload), encoding="utf-8")
    model = Model()
    assert _paid(model) == categorize_run.EXIT_OK
    assert model.categorized == 1
    assert [x["member_id"] for x in _queue(data_dir)] == ["R000002"]
    assert "no live capture, not categorized: {'D': 1}" in capsys.readouterr().out


def test_a_statement_with_no_url_is_not_categorized(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch, d=("pass d0",), r=("pass r0",))
    records = data_dir / "raw" / "crec" / "statements" / "D000001.json"
    payload = json.loads(records.read_text(encoding="utf-8"))
    payload["statements"][0]["url"] = ""
    records.write_text(json.dumps(payload), encoding="utf-8")
    assert _paid(Model()) == categorize_run.EXIT_OK
    assert [x["member_id"] for x in _queue(data_dir)] == ["R000002"]


def test_a_429_from_archive_org_stops_before_the_categorizer(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch)
    model = Model()
    limited = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(429)))
    assert _paid(model, client=limited) == categorize_run.EXIT_API_ERROR
    assert model.categorized == 0 and not review.queue_path(data_dir).exists()


def test_the_live_opt_in_builds_the_real_client(tmp_path, monkeypatch) -> None:
    _repo(tmp_path, monkeypatch)
    built = {}

    class StandIn:
        def __init__(self, **kwargs) -> None:
            built.update(kwargs)

        def capture(self, url):
            return archive_org.Capture(url, f"https://web.archive.org/web/1/{url}",
                                       "20261104120000", "2026-11-04T12:00:00Z")

        def close(self) -> None:
            built["closed"] = True

    monkeypatch.setattr(capture, "SpnClient", StandIn)
    assert _paid(Model(), "--live-capture", client=None) == categorize_run.EXIT_OK
    assert built["client"] is None and built["closed"] is True


def test_a_resume_retries_only_its_own_failed_captures(tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch)
    site = "https://example.house.gov"
    mine, snapshot, outside = f"{site}/D000001/1", f"{site}/R000002/1", f"{site}/D000001/0"
    ledger = capture.ledger_path(data_dir)
    capture._append(ledger, {"url": mine, "status": "failed", "error": "SPN2 save returned 503"})
    capture._append(ledger, {"url": outside, "status": "failed",
                             "error": "SPN2 save returned 503"})
    capture._append(ledger, {"url": snapshot, "status": "failed", "error": (
        "archive_url did not resolve (HTTP 503): "
        f"https://web.archive.org/web/20261105163622/{snapshot}")})
    saved: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            saved.append(dict(httpx.QueryParams(req.content.decode()))["url"])
        return _handler(req)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert _paid(Model(), "--per-member", "1", client=client) == categorize_run.EXIT_OK
    assert saved == [mine]  # the snapshot needed no save; the outsider was never asked
    captures = capture.load_captures(ledger)
    assert captures[mine]["status"] == "captured"
    assert captures[snapshot]["timestamp"] == "20261105163622"
    assert captures[outside]["status"] == "failed"
    assert len(_queue(data_dir)) == 2


def test_archive_org_going_down_stops_the_run_and_a_resume_pays_for_nothing_twice(
        tmp_path, monkeypatch) -> None:
    data_dir = _repo(tmp_path, monkeypatch)

    def refused(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    model = Model()
    client = httpx.Client(transport=httpx.MockTransport(refused))
    assert _paid(model, client=client) == categorize_run.EXIT_UNREACHABLE
    assert model.triaged == 4 and model.categorized == 0
    assert not capture.ledger_path(data_dir).exists()  # no URL is marked failed
    spent = json.loads(categorize_run.spend_path(data_dir, "preview-1")
                       .read_text(encoding="utf-8"))
    assert spent["spent_usd"] > 0  # the paid triage is on the books
    again = Model()
    assert _paid(again) == categorize_run.EXIT_OK
    assert again.triaged == 0 and again.categorized == 4
    assert len(_queue(data_dir)) == 4


# --- the categorizer's failures ------------------------------------------------------------


def _ask(tmp_path, monkeypatch, script, n=3, **kwargs):
    data_dir = _repo(tmp_path, monkeypatch)
    config = ai.load_config(data_dir)
    run = ai.Run(config=config, completer=Model(script), data_dir=data_dir)
    statements = [{"member_id": "M", "segments": [f"text {i}"]} for i in range(n)]
    got: list[str] = []
    kwargs.setdefault("workers", 1)
    kwargs.setdefault("sleep", lambda _s: None)
    outcome = categorize_run.categorize(
        run, statements, lambda s, _r: got.append(s["segments"][0]), **kwargs)
    return outcome, got


def test_a_429_goes_back_to_the_front_and_keeps_the_order(tmp_path, monkeypatch) -> None:
    slept: list[float] = []

    def script(_text, n):
        return _limited(retry="7") if n == 1 else _limited(retry=None) if n == 2 else (
            _answer(SUGGESTION))

    outcome, got = _ask(tmp_path, monkeypatch, script, sleep=slept.append)
    assert outcome.status == "complete" and outcome.limited == 2
    assert got == ["text 0", "text 1", "text 2"]
    assert slept == [7.0, 2.0]  # the fallback backoff had already doubled


def test_the_monthly_spend_cap_stops_the_run(tmp_path, monkeypatch) -> None:
    body = {"error": {"details": {"error_code": "enforced_spend_limit_reached"}}}
    outcome, got = _ask(tmp_path, monkeypatch, lambda _t, _n: _limited(retry=None, body=body))
    assert outcome.status == "api-error" and "monthly spend cap" in outcome.stop_detail
    assert got == []


def test_a_rate_limit_stall_stops_the_run(tmp_path, monkeypatch) -> None:
    clock = FakeClock()

    def script(_text, _n):
        clock.t += triage_run.STALL_SECONDS + 1
        return _limited(retry="1")

    outcome, _got = _ask(tmp_path, monkeypatch, script, clock=clock, sleep=clock.sleep)
    assert outcome.status == "api-error" and "no answer" in outcome.stop_detail


def _connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(request=REQUEST)


def test_a_transient_error_is_retried_then_stops(tmp_path, monkeypatch) -> None:
    outcome, got = _ask(tmp_path, monkeypatch,
                        lambda _t, n: _connection_error() if n == 0 else _answer(SUGGESTION))
    assert outcome.status == "complete" and len(got) == 3
    outcome, got = _ask(tmp_path / "again", monkeypatch, lambda _t, _n: _connection_error())
    assert outcome.status == "api-error" and "APIConnectionError" in outcome.stop_detail
    assert outcome.errors[0]["error"] == "APIConnectionError" and got == []


def test_a_bad_answer_is_recorded_and_the_run_carries_on(tmp_path, monkeypatch) -> None:
    def script(_text, n):
        return {**_answer({}), "content": [{"type": "text", "text": "not json"}]} if n == 0 \
            else _answer(SUGGESTION)

    outcome, got = _ask(tmp_path, monkeypatch, script)
    assert outcome.status == "complete" and len(outcome.errors) == 1 and len(got) == 2


def test_a_hard_api_error_stops_the_run(tmp_path, monkeypatch) -> None:
    def script(_text, _n):
        return anthropic.BadRequestError(
            "bad", response=httpx2.Response(400, request=REQUEST), body=None)

    outcome, got = _ask(tmp_path, monkeypatch, script)
    assert outcome.status == "api-error" and "BadRequestError" in outcome.stop_detail


def test_the_first_stop_in_a_batch_is_the_one_reported() -> None:
    outcome = categorize_run.Outcome()
    outcome.stop("cap", "first")
    outcome.stop("api-error", "second")
    assert (outcome.status, outcome.stop_detail) == ("cap", "first")
