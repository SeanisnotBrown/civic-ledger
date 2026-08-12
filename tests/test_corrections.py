"""INC-9 / R-6 (L-2) — corrections ledger parsing. `git log --grep` matches the
whole message, so a commit whose BODY starts a line with `correction:` must NOT
produce a bogus ledger entry — only a `correction:`-SUBJECT commit counts. Pure,
offline: parse_log is driven with synthetic `git log` output."""

from __future__ import annotations

from ingest import corrections
from ingest.corrections import _FS, _RS


def _record(commit, date, subject) -> str:
    return f"{commit}{_FS}{date}{_FS}{subject}{_RS}"


def test_correction_subject_is_parsed_and_prefix_dropped() -> None:
    raw = _record("abc1234", "2026-01-02T00:00:00Z", "correction: fixed a bad roll date")
    entries = corrections.parse_log(raw)
    assert entries == [{"commit": "abc1234", "date": "2026-01-02T00:00:00Z",
                        "subject": "fixed a bad roll date"}]


def test_body_line_match_is_not_a_correction() -> None:
    # A normal commit whose subject is NOT a correction (grep matched its body).
    raw = _record("def5678", "2026-01-03T00:00:00Z", "docs: refresh PROGRESS")
    assert corrections.parse_log(raw) == []


def test_mixed_stream_keeps_only_correction_subjects() -> None:
    raw = (
        _record("aaa", "2026-01-01T00:00:00Z", "correction: real one")
        + _record("bbb", "2026-01-02T00:00:00Z", "feat: body mentions correction: nope")
    )
    entries = corrections.parse_log(raw)
    assert [e["commit"] for e in entries] == ["aaa"]
