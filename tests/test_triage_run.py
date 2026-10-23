"""P3 step 9 — the triage-only run, concurrent and paced. No network, no credential, no spend.

The run goes through the real `ingest/ai.py` with a fake completer, over the REAL
`ai.yaml` and the REAL triage prompt, so the shipped configuration is under test too.
Answers are decided by the statement's TEXT, never by arrival order: with calls in flight
in parallel, the order they return in is not fixed.
"""

from __future__ import annotations

import json
import random
import shutil
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import anthropic
import httpx2
import pytest
import yaml

from ingest import ai, triage_run
from tests.test_prefilter import SUBSTANTIVE, _record

FIXED_NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)
REAL_AI_YAML = Path(ai.repo_root()) / "data" / "config" / "ai.yaml"
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _answer(verdict: bool, *, stop: str = "end_turn", limits: dict | None = None) -> dict:
    payload = {
        "content": [{"type": "text", "text": json.dumps({"takes_policy_position": verdict})}],
        "stop_reason": stop,
        "usage": {"input_tokens": 600, "output_tokens": 20},
        "request_id": "req_t",
    }
    if limits is not None:
        payload[ai.RATE_LIMITS_KEY] = limits
    return payload


def _limited(retry: str | None = "2", body: dict | None = None) -> anthropic.RateLimitError:
    headers = {"retry-after": retry} if retry is not None else {}
    return anthropic.RateLimitError(
        "rate limited", response=httpx2.Response(429, headers=headers, request=REQUEST), body=body
    )


class Fake:
    """A thread-safe completer that records every request. `script(text, n)` decides the
    answer for the n-th time a text is asked (n from 0): a payload, or an exception."""

    def __init__(self, script=None) -> None:
        self.script = script or (lambda text, n: _answer("pass" in text))
        self.sent: list[dict] = []
        self.asked: dict[str, int] = {}
        self.lock = threading.Lock()

    def __call__(self, request: dict) -> dict:
        text = request["messages"][0]["content"]
        with self.lock:
            self.sent.append(request)
            n = self.asked.get(text, 0)
            self.asked[text] = n + 1
        answer = self.script(text, n)
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeClock:
    """A monotonic clock that only moves when the run sleeps."""

    def __init__(self) -> None:
        self.t = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


def _statements_file(data_dir: Path, member_id: str, party: str, texts: list[str]) -> None:
    statements = data_dir / "raw" / "crec" / "statements"
    statements.mkdir(parents=True, exist_ok=True)
    records = [
        _record(
            f"Mr. X. Mr. Speaker, {text} {SUBSTANTIVE}",
            member_id=member_id,
            date=f"2026-{1 + i % 9:02d}-{1 + i % 27:02d}",
            granule_id=f"CREC-{member_id}-{i}",
        )
        for i, text in enumerate(texts)
    ]
    (statements / f"{member_id}.json").write_text(
        json.dumps(
            {
                "member": {"id": member_id, "name": f"Member {member_id}", "party": party},
                "statements": records,
            }
        ),
        encoding="utf-8",
    )


def _repo(tmp_path: Path, monkeypatch, *, d_texts=None, r_texts=None, cap=None) -> Path:
    """A repo root in tmp_path: statements for D000001 and R000002, the real ai.yaml, and a
    pilot naming their cells. A text containing "pass" gets a `true` from the default Fake."""
    data_dir = tmp_path / "data"
    _statements_file(data_dir, "D000001", "D", d_texts or ["pass one"])
    _statements_file(data_dir, "R000002", "R", r_texts or ["fail one"])
    (data_dir / "quality").mkdir(parents=True, exist_ok=True)
    (data_dir / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy(REAL_AI_YAML, data_dir / "config" / "ai.yaml")
    if cap is not None:
        raw = yaml.safe_load((data_dir / "config" / "ai.yaml").read_text(encoding="utf-8"))
        raw["per_run_cost_cap_usd"] = cap
        (data_dir / "config" / "ai.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    pilot = {
        "cells": [
            {"party": "D", "chamber": "house", "members": [{"id": "D000001"}]},
            {"party": "R", "chamber": "senate", "members": [{"id": "R000002"}]},
        ]
    }
    (data_dir / "config" / "statement-pilot.yaml").write_text(
        yaml.safe_dump(pilot), encoding="utf-8"
    )
    monkeypatch.setattr(triage_run, "repo_root", lambda: tmp_path)
    return tmp_path


def _go(argv=None, **kwargs) -> int:
    kwargs.setdefault("now", lambda: FIXED_NOW)
    return triage_run.run(argv or [], **kwargs)


def _report(root: Path) -> str:
    return (root / "docs" / "research" / "2026-10-22-triage-run.md").read_text(encoding="utf-8")


def _ledger_lines(root: Path) -> list[dict]:
    task = ai.load_config(root / "data").task(triage_run.TASK)
    path = root / "data" / "raw" / "triage" / f"{task.prompt_version}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _audit_lines(root: Path) -> list[dict]:
    path = root / "data" / "quality" / "ai-calls" / "2026-10.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _many(n: int, word: str) -> list[str]:
    return [f"{word} statement number {i}" for i in range(n)]


# --- the order ------------------------------------------------------------------------


def _survivor(member_id: str, date: str, *, eligible: bool = True, text: str = SUBSTANTIVE):
    record = _record(text, member_id=member_id, date=date, granule_id=f"{member_id}-{date}")
    return {**record, "ai_eligible": eligible}


def test_the_queue_is_newest_first_and_takes_one_member_at_a_time():
    survivors = [
        _survivor("A", "2024-01-01"),
        _survivor("A", "2026-01-01"),
        _survivor("A", "2025-01-01"),
        _survivor("B", "2023-06-01"),
        _survivor("B", "2026-05-01", eligible=False),  # R3: never sent to the AI
    ]
    order = [(s["member_id"], s["date"]) for s in triage_run.queue(survivors)]
    assert order == [
        ("A", "2026-01-01"),
        ("B", "2023-06-01"),
        ("A", "2025-01-01"),
        ("A", "2024-01-01"),
    ]


def test_an_empty_corpus_queues_nothing():
    assert triage_run.queue([]) == []


# --- the ledger: a verdict belongs to a TEXT ------------------------------------------


def test_a_missing_ledger_is_empty_and_a_later_line_replaces_an_earlier_one(tmp_path: Path):
    path = tmp_path / "v.jsonl"
    assert triage_run.load_ledger(path) == {}
    path.write_text(
        '{"text_sha256": "a", "v": 1}\n\n{"text_sha256": "a", "v": 2}\n', encoding="utf-8"
    )
    assert triage_run.load_ledger(path) == {"a": {"text_sha256": "a", "v": 2}}


def test_statements_sharing_an_id_but_not_a_text_are_each_asked():
    """Measured 2026-10-22: eight members' press releases share one `granule_id` (an ASPX
    path with its `?DocumentID=` dropped), and four Record granules hold two texts. Keyed
    on the id, they overwrote each other's verdicts and were asked again on every resume."""
    one = {**_survivor("A", "2026-01-01", text="first text"), "granule_id": "/news/doc.aspx"}
    two = {**_survivor("A", "2026-01-02", text="second text"), "granule_id": "/news/doc.aspx"}
    one["url"] = "https://a.house.gov/news/doc.aspx?DocumentID=1"
    two["url"] = "https://a.house.gov/news/doc.aspx?DocumentID=2"
    assert len(triage_run.to_ask([one, two], {})) == 2
    assert triage_run.statement_key(one) != triage_run.statement_key(two)
    ledger = {triage_run.fingerprint(one): {"text_sha256": triage_run.fingerprint(one)}}
    assert triage_run.has_verdict(one, ledger) and not triage_run.has_verdict(two, ledger)
    assert triage_run.to_ask([one, two], ledger) == [two]


def test_the_same_text_is_asked_once_however_many_statements_carry_it():
    a = _survivor("A", "2026-01-01", text="a joint release")
    b = _survivor("B", "2026-01-01", text="a joint release")
    assert triage_run.to_ask([a, b], {}) == [a]


def test_the_key_falls_back_to_the_granule_id_when_there_is_no_url():
    statement = {"member_id": "A", "source": "congressional_record", "granule_id": "G1"}
    assert triage_run.statement_key(statement) == "A|congressional_record|G1"


# --- reading the API's rate-limit headers ---------------------------------------------


def _headers(req_left: int, tok_left: int, req_limit: int = 1000, tok_limit: int = 2_000_000):
    return {
        "anthropic-ratelimit-requests-limit": str(req_limit),
        "anthropic-ratelimit-requests-remaining": str(req_left),
        "anthropic-ratelimit-input-tokens-limit": str(tok_limit),
        "anthropic-ratelimit-input-tokens-remaining": str(tok_left),
    }


def test_headroom_is_the_tighter_of_requests_and_tokens():
    assert triage_run.headroom(_headers(900, 200_000)) == pytest.approx(0.1)
    assert triage_run.headroom({}) is None
    assert triage_run.headroom({"anthropic-ratelimit-requests-limit": "x",
                                "anthropic-ratelimit-requests-remaining": "5"}) is None
    assert triage_run.headroom({"anthropic-ratelimit-requests-limit": "0",
                                "anthropic-ratelimit-requests-remaining": "0"}) is None


def test_the_pacer_ramps_up_with_room_and_down_without_it():
    pacer = triage_run.Pacer(ceiling=6)
    assert pacer.limit == triage_run.START_WORKERS
    for _ in range(5):
        pacer.on_answer(_headers(950, 1_900_000))
    assert pacer.limit == 6  # never past the ceiling
    pacer.on_answer(_headers(500, 300_000))  # between the marks: no change
    assert pacer.limit == 6
    pacer.on_answer(_headers(50, 1_900_000))  # requests nearly gone
    assert pacer.limit == 4
    pacer.on_answer({})  # a cache hit says nothing
    assert pacer.limit == 4
    for _ in range(10):
        pacer.on_answer(_headers(10, 10_000))
    assert pacer.limit == 1  # never below one


def test_the_pacer_halves_and_holds_back_on_a_429():
    pacer = triage_run.Pacer(ceiling=2)
    assert pacer.limit == 2  # opens at the ceiling when that is below START_WORKERS
    pacer.limit = 8
    pacer.on_limited(5.0, now=100.0)
    assert pacer.limit == 4 and pacer.not_before == 105.0
    pacer.on_limited(None, now=100.0)  # no retry-after: back off, doubling
    pacer.on_limited(None, now=100.0)
    assert pacer.backoff == 4.0 and pacer.not_before == 105.0
    for _ in range(10):
        pacer.on_limited(None, now=200.0)
    assert pacer.backoff == triage_run.BACKOFF_MAX_SECONDS and pacer.limit == 1
    pacer.on_answer({})
    assert pacer.backoff == triage_run.BACKOFF_FIRST_SECONDS


def test_retry_after_is_read_from_the_error_when_it_is_usable():
    assert triage_run.retry_after(_limited("7")) == 7.0
    assert triage_run.retry_after(_limited("soon")) is None
    assert triage_run.retry_after(_limited(None)) is None
    assert triage_run.retry_after(ValueError("no response")) is None


def test_the_monthly_spend_cap_is_told_apart_from_a_rate_limit():
    spend = {"type": "error", "error": {"type": "rate_limit_error",
                                        "details": {"error_code": "enforced_spend_limit_reached"}}}
    assert triage_run.spend_cap_reached(_limited(None, body=spend))
    assert not triage_run.spend_cap_reached(_limited("3", body=spend))
    assert not triage_run.spend_cap_reached(_limited(None, body={"error": "flat"}))
    assert not triage_run.spend_cap_reached(_limited(None, body="not a dict"))
    assert not triage_run.spend_cap_reached(ValueError("other"))


# --- the run --------------------------------------------------------------------------


def test_a_full_run_records_every_verdict_and_reports_per_cell(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch)
    assert _go(completer=Fake()) == triage_run.EXIT_OK

    verdicts = {e["member_id"]: e["takes_policy_position"] for e in _ledger_lines(root)}
    assert verdicts == {"D000001": True, "R000002": False}
    text = _report(root)
    assert "| How it ended | `complete` |" in text
    assert "**The Opus categorizer was NOT called**" in text
    assert "| D house | 1 | 1 | 1 | 0 | 0 |" in text
    assert "| R senate | 1 | 1 | 0 | 1 | 0 |" in text
    assert "| Member D000001 (D000001) | D house | 1 | 1 | 1 | 0 | 0 | short of 25 |" in text
    assert "| Rate limits the API reported | none in the headers |" in text
    assert "Stopped:" not in text and "## Errors" not in text
    assert "complete: 2 verdict(s), 2 call(s)" in capsys.readouterr().out


def test_the_run_never_asks_the_categorizer(tmp_path, monkeypatch):
    """Owner ruling 2026-10-22: the first pass only. Fails if any request for another task
    or model leaves this module, and if the categorizer is even reachable."""
    _repo(tmp_path, monkeypatch, d_texts=_many(5, "pass"), r_texts=_many(5, "fail"))
    config = ai.load_config(tmp_path / "data")
    triage_model = config.task("triage_statement").model
    categorizer = config.task("categorize_statement")
    asked: list[str] = []
    real_call = ai.Run.call

    def spy(self, task_name, user_text, **kwargs):
        asked.append(task_name)
        assert "categorize_statement" not in self.config.tasks
        return real_call(self, task_name, user_text, **kwargs)

    monkeypatch.setattr(ai.Run, "call", spy)
    fake = Fake()
    _go(completer=fake)

    assert asked and set(asked) == {"triage_statement"}
    assert fake.sent and all(r["model"] == triage_model for r in fake.sent)
    assert all(r["model"] != categorizer.model for r in fake.sent)
    assert all(r["system"] != ai.prompt_text(categorizer) for r in fake.sent)


def test_concurrent_answers_leave_complete_lines_in_both_files(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch, d_texts=_many(120, "pass"), r_texts=_many(120, "fail"))

    def jittery(text, n):
        time.sleep(random.uniform(0, 0.003))
        return _answer("pass" in text, limits=_headers(990, 1_990_000))

    fake = Fake(jittery)
    assert _go(["--workers", "16"], completer=fake) == triage_run.EXIT_OK
    ledger = _ledger_lines(root)  # every line parses, or this raises
    audit = _audit_lines(root)
    assert len(ledger) == 240 and len(audit) == 240 and len(fake.sent) == 240
    assert len({e["text_sha256"] for e in ledger}) == 240
    assert sum(e["takes_policy_position"] for e in ledger) == 120
    assert "Most calls in flight at once | " in _report(root)
    peak = int(_report(root).split("Most calls in flight at once | ")[1].split(" ")[0])
    assert 1 < peak <= 16


def test_the_cap_is_never_passed_with_many_calls_in_flight(tmp_path, monkeypatch):
    task_config = ai.load_config()
    task = task_config.task(triage_run.TASK)
    bound = ai.max_cost_usd(
        task, task_config.price(task.model), ai.prompt_text(task), "x" * 200
    )
    root = _repo(tmp_path, monkeypatch, d_texts=_many(40, "pass"), r_texts=_many(40, "fail"),
                 cap=bound * 6)
    gate = threading.Barrier(4, timeout=1)

    def slow(text, n):
        try:
            gate.wait()  # hold four calls in flight together
        except threading.BrokenBarrierError:
            pass
        return _answer(True, limits=_headers(990, 1_990_000))

    assert _go(["--workers", "32"], completer=Fake(slow)) == triage_run.EXIT_CAP
    lines = _audit_lines(root)
    assert sum(line["cost_usd"] for line in lines) <= bound * 6
    assert lines[-1]["run_spent_usd"] <= bound * 6
    assert "| How it ended | `cap` |" in _report(root)
    assert "held for calls in flight" in _report(root)


def test_a_429_is_retried_after_retry_after_and_never_counted_as_an_error(
    tmp_path, monkeypatch
):
    root = _repo(tmp_path, monkeypatch)
    clock = FakeClock()

    def once_limited(text, n):
        return _limited("2") if n == 0 and "pass" in text else _answer("pass" in text)

    fake = Fake(once_limited)
    assert _go(["--workers", "1"], completer=fake, sleep=clock.sleep, clock=clock) == 0
    assert clock.slept == [2.0]
    assert len(_ledger_lines(root)) == 2
    text = _report(root)
    assert "| Rate-limited calls retried (never errors) | 1 |" in text
    assert "| Statements with no verdict because of an error | 0 |" in text


def test_a_429_while_other_calls_are_in_flight_waits_without_blocking_them(
    tmp_path, monkeypatch
):
    root = _repo(tmp_path, monkeypatch, d_texts=["pass slow"], r_texts=["fail limited"])
    release = threading.Event()

    def script(text, n):
        if "slow" in text:
            release.wait(5)
            return _answer(True)
        if n == 0:
            threading.Timer(0.3, release.set).start()
            return _limited("0.05")
        return _answer(False)

    assert _go(["--workers", "4"], completer=Fake(script)) == triage_run.EXIT_OK
    assert len(_ledger_lines(root)) == 2


def test_a_429_without_retry_after_backs_off(tmp_path, monkeypatch):
    _repo(tmp_path, monkeypatch, d_texts=["pass"], r_texts=["fail"])
    clock = FakeClock()

    def script(text, n):
        return _limited(None) if n < 2 and "pass" in text else _answer("pass" in text)

    _go(["--workers", "1"], completer=Fake(script), sleep=clock.sleep, clock=clock)
    assert clock.slept == [1.0, 2.0]


def test_the_monthly_spend_cap_stops_the_run_rather_than_retrying(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    body = {"error": {"details": {"error_code": "enforced_spend_limit_reached"}}}
    fake = Fake(lambda text, n: _limited(None, body=body))
    assert _go(["--workers", "1"], completer=fake) == triage_run.EXIT_API_ERROR
    assert len(fake.sent) == 1
    assert "monthly spend cap" in _report(root)


def test_endless_rate_limits_stop_the_run_as_resumable(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    clock = FakeClock()
    fake = Fake(lambda text, n: _limited("600"))
    code = _go(["--workers", "1"], completer=fake, sleep=clock.sleep, clock=clock)
    assert code == triage_run.EXIT_API_ERROR
    assert "rate limited with no answer for 900s" in _report(root)


def test_a_dropped_connection_is_retried(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    clock = FakeClock()

    def script(text, n):
        if n == 0 and "pass" in text:
            return anthropic.APIConnectionError(message="reset", request=REQUEST)
        return _answer("pass" in text)

    assert _go(["--workers", "1"], completer=Fake(script), sleep=clock.sleep, clock=clock) == 0
    assert len(_ledger_lines(root)) == 2
    assert "| Connection or server errors retried | 1 |" in _report(root)


def test_a_connection_that_never_comes_back_stops_the_run(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    clock = FakeClock()
    fake = Fake(lambda text, n: anthropic.APIConnectionError(message="down", request=REQUEST))
    code = _go(["--workers", "1"], completer=fake, sleep=clock.sleep, clock=clock)
    assert code == triage_run.EXIT_API_ERROR
    assert len(fake.sent) == triage_run.MAX_CONNECT_ATTEMPTS
    assert f"after {triage_run.MAX_CONNECT_ATTEMPTS} attempts" in _report(root)


def test_a_non_retryable_api_error_stops_the_run(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    denied = anthropic.AuthenticationError(
        "bad key", response=httpx2.Response(401, request=REQUEST), body=None
    )
    assert _go(["--workers", "1"], completer=Fake(lambda t, n: denied)) == 2
    assert "Stopped: AuthenticationError" in _report(root)


def test_a_bad_answer_is_recorded_and_the_run_carries_on(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    fake = Fake(lambda text, n: _answer(True, stop="refusal" if "pass" in text else "end_turn"))
    assert _go(completer=fake) == triage_run.EXIT_OK
    assert len(fake.sent) == 2 and len(_ledger_lines(root)) == 1
    text = _report(root)
    assert "## Errors this time (no verdict; a re-run asks again)" in text
    assert "(refusal)" in text


def test_a_rerun_skips_what_is_already_triaged(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch)
    _go(completer=Fake())
    capsys.readouterr()
    again = Fake()
    assert _go(completer=again) == triage_run.EXIT_OK
    assert again.sent == []
    assert "2 already triaged under" in capsys.readouterr().out
    assert len(_ledger_lines(root)) == 2


def test_a_clean_stop_mid_run_then_a_resume_finishes_without_asking_twice(
    tmp_path, monkeypatch
):
    root = _repo(tmp_path, monkeypatch, d_texts=_many(30, "pass"), r_texts=_many(30, "fail"))
    stop_file = root / "data" / triage_run.STOP_FILE
    calls = {"n": 0}
    lock = threading.Lock()

    def stops_after_ten(text, n):
        with lock:
            calls["n"] += 1
            if calls["n"] == 10:
                stop_file.parent.mkdir(parents=True, exist_ok=True)
                stop_file.write_text("stop", encoding="utf-8")
        return _answer("pass" in text)

    first = Fake(stops_after_ten)
    assert _go(["--workers", "4"], completer=first) == triage_run.EXIT_STOPPED
    done_first = len(_ledger_lines(root))
    assert 10 <= done_first < 60
    assert "| How it ended | `stopped` |" in _report(root)

    second = Fake()
    assert _go(completer=second) == triage_run.EXIT_OK  # also removes the stale stop file
    assert not stop_file.exists()
    asked_twice = set(first.asked) & set(second.asked)
    assert asked_twice == set()
    assert len({e["text_sha256"] for e in _ledger_lines(root)}) == 60


def test_limit_caps_the_statements_one_invocation_sends(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch, d_texts=_many(3, "pass"))
    fake = Fake()
    assert _go(["--limit", "2", "--workers", "1"], completer=fake) == 0
    assert len(fake.sent) == 2
    assert "| How it ended | `limit` |" in _report(root)


def test_dry_run_makes_no_call_and_writes_nothing(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch)
    fake = Fake()
    assert triage_run.run(["--dry-run"], completer=fake) == triage_run.EXIT_OK
    assert fake.sent == []
    assert not (root / "docs").exists()
    out = capsys.readouterr().out
    assert "0 already triaged" in out and "2 distinct texts to ask" in out


def test_workers_must_be_at_least_one(tmp_path, monkeypatch):
    _repo(tmp_path, monkeypatch)
    with pytest.raises(SystemExit):
        triage_run.run(["--workers", "0"])


def test_progress_and_the_reported_limits_reach_the_log(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch)
    monkeypatch.setattr(triage_run, "PROGRESS_EVERY", 1)
    limits = {**_headers(990, 1_990_000), "anthropic-ratelimit-output-tokens-limit": "400000"}
    _go(completer=Fake(lambda text, n: _answer(True, limits=limits)))
    out = capsys.readouterr().out
    assert out.count("rate limits reported by the API") == 1
    assert "requests 1000/min, input-tokens 2000000/min, output-tokens 400000/min" in out
    assert "triaged 2, $" in out
    assert "requests 1000/min" in _report(root)


def test_the_live_completer_and_the_wall_clock_are_the_defaults(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    fake = Fake()
    monkeypatch.setattr(ai, "_live_completer", fake)
    assert triage_run.run([]) == triage_run.EXIT_OK
    assert len(fake.sent) == 2
    assert list((root / "docs" / "research").glob("*-triage-run.md"))


def test_the_report_calls_a_stub_a_stub_and_nothing_else_one() -> None:
    """A report must not label a real prompt version a STUB, nor a stub anything else."""
    task = ai.load_config().task(triage_run.TASK)
    stub = replace(task, prompt_version="v1-stub")
    real = replace(task, prompt_version="v1")
    assert triage_run.prompt_status(stub).startswith("a STUB")
    assert "STUB" not in triage_run.prompt_status(real)
    assert "untested" in triage_run.prompt_status(real)
