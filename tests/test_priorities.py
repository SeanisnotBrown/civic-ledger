"""P3 task 6 — stated priorities from approved statements: the Q-B list bar and the Q-J
per-member rules. Fixtures only; nothing is written to the repository's data/."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from ingest import priorities, verify_recompute
from ingest.cache import repo_root

RULES = priorities.Rules(min_approved_statements=5, min_distinct_topics=3,
                         repetition_statements=3, repetition_distinct_months=2)
TERM = "2025-01-03"


def _s(i: int, topic: str | None = "Health", stance: str | None = "support",
       date: str = "2025-03-01", signal: bool | None = False, member: str = "M1") -> dict:
    return {"id": f"{member}-{i:03d}", "member_id": member, "date": date, "topic": topic,
            "stated_position": stance, "priority_signal": signal}


def _filler(start: int = 100) -> list[dict]:
    """Three statements on two other topics, no stance: they clear Q-B's spread without
    forming any priority of their own."""
    return [_s(start, "Taxation", None), _s(start + 1, "Energy", None),
            _s(start + 2, "Energy", None)]


# --- the constants -------------------------------------------------------------------


def test_q_b_is_five_approved_statements_across_three_topics() -> None:
    """§2 "Q-B answered" — one constant, checked by its own test."""
    raw = yaml.safe_load((repo_root() / "data" / "config" / "thresholds.yaml")
                         .read_text(encoding="utf-8"))
    assert raw["priorities_list"]["ratified"] == "2026-10-07"
    assert priorities.load_rules() == RULES


# --- Q-B: whether a list shows at all ---------------------------------------------------


def test_below_the_q_b_bar_nothing_is_inferred_or_published() -> None:
    four = [_s(1, signal=True), _s(2, "Taxation"), _s(3, "Energy"), _s(4, "Energy")]
    entry = priorities.member_priorities(four, TERM, RULES)
    assert entry == {"approved_statements": 4, "distinct_topics": 3, "listed": False}


def test_five_statements_on_two_topics_still_show_no_list() -> None:
    five = [_s(i, "Health" if i < 3 else "Energy") for i in range(5)]
    assert priorities.member_priorities(five, TERM, RULES)["listed"] is False


def test_unlabeled_statements_count_toward_the_total_but_toward_no_topic() -> None:
    five = [_s(i, topic=None, stance=None) for i in range(5)]
    entry = priorities.member_priorities(five, TERM, RULES)
    assert (entry["approved_statements"], entry["distinct_topics"], entry["listed"]) == (5, 0,
                                                                                          False)


# --- Q-J: which topics are priorities ---------------------------------------------------


def test_one_signalled_statement_makes_a_priority() -> None:
    entry = priorities.member_priorities(
        [_s(1, signal=True), _s(2, "Energy", "oppose")] + _filler(), TERM, RULES)
    assert entry["listed"] is True
    assert entry["priorities"] == [{"topic": "Health", "stance": "support",
                                    "routes": ["signal"], "statement_ids": ["M1-001"]}]


def test_repetition_needs_three_statements_across_two_calendar_months() -> None:
    same_month = [_s(i, date=f"2025-03-0{i}") for i in range(1, 4)]
    entry = priorities.member_priorities(same_month + _filler(), TERM, RULES)
    assert entry["priorities"] == []
    two_months = [_s(1, date="2025-03-01"), _s(2, date="2025-03-20"), _s(3, date="2025-04-02")]
    entry = priorities.member_priorities(two_months + _filler(), TERM, RULES)
    assert entry["priorities"][0]["routes"] == ["repetition"]
    assert entry["priorities"][0]["statement_ids"] == ["M1-001", "M1-002", "M1-003"]


def test_both_routes_are_named_when_both_hold() -> None:
    items = [_s(1, date="2025-03-01", signal=True), _s(2, date="2025-04-01"),
             _s(3, date="2025-05-01")]
    entry = priorities.member_priorities(items + _filler(), TERM, RULES)
    assert entry["priorities"][0]["routes"] == ["signal", "repetition"]


def test_statements_on_both_sides_of_a_topic_set_no_priority_on_it() -> None:
    items = [_s(1, signal=True), _s(2, stance="oppose", signal=True), _s(3, "Energy",
                                                                         signal=True)]
    entry = priorities.member_priorities(items + _filler(), TERM, RULES)
    assert entry["conflicted_topics"] == ["Health"]
    assert [p["topic"] for p in entry["priorities"]] == ["Energy"]


def test_only_the_current_term_counts_toward_a_priority() -> None:
    old = [_s(1, date="2024-06-01", signal=True)]
    entry = priorities.member_priorities(old + [_s(2, "Energy")] + _filler(), TERM, RULES)
    assert entry["listed"] is True  # Q-B counts every approved statement
    assert entry["priorities"] == []
    # No term on file: nothing is excluded.
    entry = priorities.member_priorities(old + [_s(2, "Energy")] + _filler(), None, RULES)
    assert entry["priorities"][0]["statement_ids"] == ["M1-001"]


def test_a_statement_without_a_stance_forms_no_priority_even_when_signalled() -> None:
    entry = priorities.member_priorities([_s(1, stance=None, signal=True), _s(2, "Energy")]
                                         + _filler(), TERM, RULES)
    assert entry["priorities"] == []


# --- the file ---------------------------------------------------------------------------


def _dataset(tmp_path: Path, statements: list[dict], dead: list[str] = ()) -> Path:
    data = tmp_path / "data"
    (data / "config").mkdir(parents=True)
    (data / "config" / "thresholds.yaml").write_text(
        (repo_root() / "data" / "config" / "thresholds.yaml").read_text(encoding="utf-8"),
        encoding="utf-8")
    (data / "members").mkdir()
    (data / "members" / "M1.json").write_text(json.dumps({"id": "M1", "terms": [
        {"start": "2023-01-03"}, {"start": TERM}]}), encoding="utf-8")
    (data / "members" / "M2.json").write_text(json.dumps({"id": "M2", "terms": []}),
                                              encoding="utf-8")
    (data / "statements").mkdir()
    (data / "statements" / "_title_allowlist.yaml").write_text("{}\n", encoding="utf-8")
    for s in statements:
        (data / "statements" / f"{s['id']}.json").write_text(json.dumps(s), encoding="utf-8")
    (data / "quality").mkdir()
    (data / "quality" / "archive-status.json").write_text(
        json.dumps({"dead_statement_ids": list(dead)}), encoding="utf-8")
    return data


def test_compute_reads_approved_statements_terms_and_excludes_dead_archives(
    tmp_path: Path,
) -> None:
    items = [_s(1, signal=True), _s(2, "Energy", "oppose")] + _filler()
    data = _dataset(tmp_path, items + [_s(9, member="M2")], dead=["M1-002"])
    result = priorities.compute(data)
    assert result["bar"] == {"min_approved_statements": 5, "min_distinct_topics": 3}
    assert result["members"]["M1"]["approved_statements"] == 4  # the dead one is out
    assert result["members"]["M1"]["listed"] is False
    assert result["members"]["M2"] == {"approved_statements": 1, "distinct_topics": 1,
                                       "listed": False}
    written = priorities.write(data)
    assert json.loads(written.read_text(encoding="utf-8")) == result


def test_with_no_approved_statements_no_member_is_listed(tmp_path: Path) -> None:
    assert priorities.compute(_dataset(tmp_path, []))["members"] == {}


def test_the_committed_file_is_today_empty_and_re_derives() -> None:
    """Zero approved statements today: every member page shows the Q-B empty state."""
    committed = json.loads(priorities.path().read_text(encoding="utf-8"))
    assert committed["members"] == {}
    assert verify_recompute.check_priorities() == []


def test_verify_recompute_catches_a_drifted_file(tmp_path: Path, monkeypatch) -> None:
    data = _dataset(tmp_path, [_s(1)])
    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)
    assert verify_recompute.check_priorities() == []  # no file: nothing to check
    priorities.write(data)
    assert verify_recompute.check_priorities() == []
    priorities.path(data).write_text('{"members": {}}\n', encoding="utf-8")
    assert "priorities — committed bytes != recompute" in verify_recompute.check_priorities()[0]


def test_without_member_records_no_term_filter_applies(tmp_path: Path) -> None:
    import shutil

    items = [_s(1, date="2020-01-01", signal=True), _s(2, "Energy")] + _filler()
    data = _dataset(tmp_path, items)
    shutil.rmtree(data / "members")
    entry = priorities.compute(data)["members"]["M1"]
    assert entry["priorities"][0]["statement_ids"] == ["M1-001"]
