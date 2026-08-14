"""V2-4 (D68) — branch coverage for classify.run() + _is_rules_reported: the
live-fetch / file-rewrite plumbing the pure test_classify.py does not exercise.
Offline: a tmp votes dir + monkeypatched committee fetch."""

from __future__ import annotations

import json

from ingest import classify
from ingest.cache import RetryableHTTPError


def _seed(votes_dir, rid, question, bill_id, rule="unclassified"):
    votes_dir.mkdir(parents=True, exist_ok=True)
    (votes_dir / f"{rid}.json").write_text(
        json.dumps({
            "rollcall": {"id": rid, "question": question, "bill_id": bill_id,
                         "vote_class": "unclassified", "vote_class_rule": rule},
            "member_votes": [],
        }),
        encoding="utf-8",
    )


class _Resp:
    def __init__(self, payload): self._p = payload
    def json(self): return self._p


def _committees(reported: bool):
    acts = [{"name": "Reported by the Committee on Rules"}] if reported else [{"name": "Referred"}]
    return {"committees": [{"systemCode": "hsru00", "activities": acts}]}


def test_run_noop_when_no_votes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    (tmp_path / "data" / "votes").mkdir(parents=True)
    assert classify.run() == 0
    assert "no roll-call data" in capsys.readouterr().out


def test_run_classifies_and_resolves_rules(tmp_path, monkeypatch):
    votes = tmp_path / "data" / "votes"
    _seed(votes, "h-119-1-0001", "On Passage of the Bill", "hr1-119")
    _seed(votes, "h-119-1-0002", "On Agreeing to the Resolution", "hres5-119")  # → rules fetch
    _seed(votes, "h-119-1-0003", "Election of the Speaker", None, rule="non_position")  # skipped
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    from ingest.sources import congress_gov
    monkeypatch.setattr(congress_gov, "bill_committees", lambda c, t, n: _Resp(_committees(True)))

    assert classify.run() == 0

    def cls(rid, key="vote_class"):
        return json.loads((votes / f"{rid}.json").read_text())["rollcall"][key]

    assert cls("h-119-1-0001") == "passage"
    assert cls("h-119-1-0002") == "procedural"  # rules-reported hres → procedural
    assert cls("h-119-1-0003", "vote_class_rule") == "non_position"  # left untouched
    # the unmapped log is regenerated (empty, since nothing classified "other")
    unmapped = json.loads((tmp_path / "data" / "quality" / "unmapped_questions.json").read_text())
    assert unmapped["count"] == 0


def test_run_fails_when_other_rate_over_ceiling(tmp_path, monkeypatch):
    votes = tmp_path / "data" / "votes"
    _seed(votes, "h-119-1-0009", "Zzz nonsense question", "hr9-119")  # → other, 100% > ceiling
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    assert classify.run() == 1
    unmapped = json.loads((tmp_path / "data" / "quality" / "unmapped_questions.json").read_text())
    assert unmapped["count"] == 1 and "Zzz nonsense question" in unmapped["questions"]


def test_run_reports_committee_fetch_failure(tmp_path, monkeypatch):
    votes = tmp_path / "data" / "votes"
    _seed(votes, "h-119-1-0002", "On Agreeing to the Resolution", "hres5-119")
    _seed(votes, "h-119-1-0001", "On Passage", "hr1-119")  # keeps other-rate at 0
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    from ingest.sources import congress_gov

    def boom(c, t, n):
        raise RetryableHTTPError("503 server error")

    monkeypatch.setattr(congress_gov, "bill_committees", boom)
    assert classify.run() == 1  # a fetch failure fails the run (re-run retries)


def test_is_rules_reported_branches(monkeypatch):
    from ingest.sources import congress_gov

    assert classify._is_rules_reported("hr1-119") is False  # not an hres → no fetch at all
    monkeypatch.setattr(congress_gov, "bill_committees", lambda c, t, n: _Resp(_committees(True)))
    assert classify._is_rules_reported("hres5-119") is True
    monkeypatch.setattr(congress_gov, "bill_committees", lambda c, t, n: _Resp(_committees(False)))
    assert classify._is_rules_reported("hres5-119") is False  # hsru00 present but not reported
    monkeypatch.setattr(congress_gov, "bill_committees", lambda c, t, n: _Resp({"committees": []}))
    assert classify._is_rules_reported("hres5-119") is False  # no Rules committee at all
