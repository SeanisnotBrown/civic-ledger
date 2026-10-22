"""P3 step 9 — the triage-only run. No network, no credential, no spend.

The run goes through the real `ingest/ai.py` with a fake completer, over the REAL
`ai.yaml` and the REAL triage prompt, so the shipped configuration is under test too.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import anthropic
import httpx2
import pytest
import yaml

from ingest import ai, triage_run
from tests.test_prefilter import SUBSTANTIVE, _corpus, _record

FIXED_NOW = datetime(2026, 10, 22, 15, 0, tzinfo=UTC)
REAL_AI_YAML = Path(ai.repo_root()) / "data" / "config" / "ai.yaml"


def _haiku(verdict: bool, *, stop: str = "end_turn") -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps({"takes_policy_position": verdict})}],
        "stop_reason": stop,
        "usage": {"input_tokens": 1000, "output_tokens": 20},
        "request_id": "req_t",
    }


class Fake:
    """A completer that records every request and answers from a script."""

    def __init__(self, *answers: dict | Exception) -> None:
        self.answers = list(answers)
        self.sent: list[dict] = []

    def __call__(self, request: dict) -> dict:
        self.sent.append(request)
        answer = self.answers.pop(0) if self.answers else _haiku(True)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _repo(tmp_path: Path, monkeypatch, *, cap: float | None = None) -> Path:
    """A repo root in tmp_path: the prefilter test corpus (one statement each for D000001
    and R000002), the real ai.yaml, and a pilot naming their cells."""
    data_dir = tmp_path / "data"
    _corpus(data_dir)
    # The two members' surviving turns are the same sentence in that corpus, and the
    # gateway serves identical text from its cache. Make R000002's distinct.
    r_file = data_dir / "raw" / "crec" / "statements" / "R000002.json"
    payload = json.loads(r_file.read_text(encoding="utf-8"))
    payload["statements"][0]["segments"][1] += " The Senate should pass it this month."
    r_file.write_text(json.dumps(payload), encoding="utf-8")
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


def _report(root: Path) -> str:
    return (root / "docs" / "research" / "2026-10-22-triage-run.md").read_text(encoding="utf-8")


def _ledger(root: Path) -> list[dict]:
    task = ai.load_config(root / "data").task(triage_run.TASK)
    path = root / "data" / "raw" / "triage" / f"{task.prompt_version}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# --- the order ------------------------------------------------------------------------


def _survivor(member_id: str, date: str, *, eligible: bool = True) -> dict:
    record = _record(SUBSTANTIVE, member_id=member_id, date=date, granule_id=f"{member_id}-{date}")
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


# --- the ledger -----------------------------------------------------------------------


def test_a_missing_ledger_is_empty_and_a_later_line_replaces_an_earlier_one(tmp_path: Path):
    path = tmp_path / "v.jsonl"
    assert triage_run.load_ledger(path) == {}
    path.write_text(
        '{"key": "k", "text_sha256": "a"}\n\n{"key": "k", "text_sha256": "b"}\n',
        encoding="utf-8",
    )
    assert triage_run.load_ledger(path) == {"k": {"key": "k", "text_sha256": "b"}}


def test_a_verdict_counts_only_for_the_same_text():
    statement = _survivor("A", "2026-01-01")
    key = triage_run.statement_key(statement)
    same = triage_run.text_sha256(triage_run.statement_text(statement))
    assert triage_run.has_verdict(statement, {key: {"text_sha256": same}})
    assert not triage_run.has_verdict(statement, {key: {"text_sha256": "changed"}})
    assert not triage_run.has_verdict(statement, {})


# --- the run --------------------------------------------------------------------------


def test_a_full_run_records_every_verdict_and_reports_per_cell(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch)
    fake = Fake(_haiku(True), _haiku(False))
    assert triage_run.run([], completer=fake, now=lambda: FIXED_NOW) == triage_run.EXIT_OK

    verdicts = {e["member_id"]: e["takes_policy_position"] for e in _ledger(root)}
    assert verdicts == {"D000001": True, "R000002": False}
    text = _report(root)
    assert "| How it ended | `complete` |" in text
    assert "**The Opus categorizer was NOT called**" in text
    assert "| D house | 1 | 1 | 1 | 0 | 0 |" in text
    assert "| R senate | 1 | 1 | 0 | 1 | 0 |" in text
    assert "| Member D000001 (D000001) | D house | 1 | 1 | 1 | 0 | 0 | short of 25 |" in text
    assert "Stopped:" not in text and "## Errors" not in text
    assert "complete: 2 verdict(s), 2 call(s)" in capsys.readouterr().out


def test_the_run_never_asks_the_categorizer(tmp_path, monkeypatch):
    """Owner ruling 2026-10-22: the first pass only. Fails if any request for another task
    or model leaves this module, and if the categorizer is even reachable."""
    _repo(tmp_path, monkeypatch)
    config = ai.load_config(tmp_path / "data")
    triage_model = config.task("triage_statement").model
    categorizer = config.task("categorize_statement")
    asked: list[str] = []
    real_call = ai.Run.call

    def spy(self, task_name, user_text):
        asked.append(task_name)
        assert "categorize_statement" not in self.config.tasks
        return real_call(self, task_name, user_text)

    monkeypatch.setattr(ai.Run, "call", spy)
    fake = Fake()
    triage_run.run([], completer=fake, now=lambda: FIXED_NOW)

    assert asked and set(asked) == {"triage_statement"}
    assert fake.sent and all(r["model"] == triage_model for r in fake.sent)
    assert all(r["model"] != categorizer.model for r in fake.sent)
    assert all(
        r["system"] != ai.prompt_text(categorizer) for r in fake.sent
    )


def test_a_rerun_skips_what_is_already_triaged(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch)
    triage_run.run([], completer=Fake(), now=lambda: FIXED_NOW)
    capsys.readouterr()
    again = Fake()
    assert triage_run.run([], completer=again, now=lambda: FIXED_NOW) == triage_run.EXIT_OK
    assert again.sent == []
    assert "2 already triaged under" in capsys.readouterr().out
    assert len(_ledger(root)) == 2


def test_the_run_stops_cleanly_at_the_cap(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch, cap=0.00001)
    fake = Fake()
    assert triage_run.run([], completer=fake, now=lambda: FIXED_NOW) == triage_run.EXIT_CAP
    assert len(fake.sent) == 1  # the second call is refused before it is made
    assert len(_ledger(root)) == 1
    text = _report(root)
    assert "| How it ended | `cap` |" in text
    assert "Stopped: run reached its $0.00 cap" in text
    assert "stopped: run reached" in capsys.readouterr().out
    assert "| Member R000002 (R000002) | R senate | 1 | 0 | 0 | 0 | 1 |  |" in text


def test_a_bad_answer_is_recorded_and_the_run_carries_on(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    fake = Fake(_haiku(True, stop="refusal"), _haiku(True))
    assert triage_run.run([], completer=fake, now=lambda: FIXED_NOW) == triage_run.EXIT_OK
    assert len(fake.sent) == 2 and len(_ledger(root)) == 1
    text = _report(root)
    assert "## Errors this time (no verdict; a re-run asks again)" in text
    assert "(refusal)" in text


def test_an_api_failure_stops_the_run_and_a_rerun_resumes(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    down = anthropic.APIConnectionError(
        message="connection reset", request=httpx2.Request("POST", "https://api.anthropic.com")
    )
    fake = Fake(_haiku(True), down)
    assert triage_run.run([], completer=fake, now=lambda: FIXED_NOW) == triage_run.EXIT_API_ERROR
    assert "| How it ended | `api-error` |" in _report(root)
    assert "Stopped: APIConnectionError" in _report(root)
    resume = Fake()
    assert triage_run.run([], completer=resume, now=lambda: FIXED_NOW) == triage_run.EXIT_OK
    assert len(resume.sent) == 1 and len(_ledger(root)) == 2


def test_limit_caps_the_calls_of_one_invocation(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    fake = Fake()
    assert triage_run.run(["--limit", "1"], completer=fake, now=lambda: FIXED_NOW) == 0
    assert len(fake.sent) == 1
    assert "| How it ended | `limit` |" in _report(root)


def test_dry_run_makes_no_call_and_writes_nothing(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch)
    fake = Fake()
    assert triage_run.run(["--dry-run"], completer=fake) == triage_run.EXIT_OK
    assert fake.sent == []
    assert not (root / "docs").exists()
    out = capsys.readouterr().out
    assert "0 already triaged" in out and "2 to do" in out and "--dry-run" in out


def test_progress_is_reported_as_the_run_goes(tmp_path, monkeypatch, capsys):
    _repo(tmp_path, monkeypatch)
    monkeypatch.setattr(triage_run, "PROGRESS_EVERY", 1)
    triage_run.run([], completer=Fake(), now=lambda: FIXED_NOW)
    assert "triaged 2, $" in capsys.readouterr().out


def test_the_live_completer_and_the_wall_clock_are_the_defaults(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    fake = Fake()
    monkeypatch.setattr(ai, "_live_completer", fake)
    assert triage_run.run([]) == triage_run.EXIT_OK
    assert len(fake.sent) == 2
    assert list((root / "docs" / "research").glob("*-triage-run.md"))


@pytest.mark.parametrize("member_id", ["D000001", "R000002"])
def test_every_queued_statement_is_one_the_prefilter_kept(tmp_path, monkeypatch, member_id):
    root = _repo(tmp_path, monkeypatch)
    triage_run.run([], completer=Fake(), now=lambda: FIXED_NOW)
    assert member_id in {e["member_id"] for e in _ledger(root)}
