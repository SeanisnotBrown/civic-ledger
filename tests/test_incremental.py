"""INC-9 tests — the incremental-ingest skip policy (§6.1). Pure/deterministic:
the 7-day cutoff is injected, and file-reading helpers use tmp dirs. No network.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ingest import incremental

# A fixed "now" so the cutoff (now - 7d = 2026-08-05T00:00:00Z) is deterministic.
NOW = datetime(2026, 8, 12, tzinfo=UTC)
CUTOFF = incremental.final_cutoff(NOW)


def test_cutoff_is_seven_days_before_now() -> None:
    assert CUTOFF == datetime(2026, 8, 5, tzinfo=UTC)


def test_is_final_true_for_old_dates() -> None:
    assert incremental.is_final("2025-01-03T12:33:00-05:00", CUTOFF) is True
    assert incremental.is_final("2026-08-04T23:59:00+00:00", CUTOFF) is True


def test_is_final_false_for_recent_dates() -> None:
    # Within the 7-day window → still refreshable.
    assert incremental.is_final("2026-08-10T09:00:00-04:00", CUTOFF) is False
    assert incremental.is_final("2026-08-05T00:00:01+00:00", CUTOFF) is False


def test_is_final_false_on_unparseable() -> None:
    # Ambiguity must never skip (correctness outranks politeness, §0.4).
    assert incremental.is_final("not-a-date", CUTOFF) is False


def _write_roll(votes_dir: Path, rc_id: str, date_iso: str) -> None:
    votes_dir.mkdir(parents=True, exist_ok=True)
    (votes_dir / f"{rc_id}.json").write_text(
        json.dumps({"rollcall": {"id": rc_id, "date": date_iso, "bill_id": None}}),
        encoding="utf-8",
    )


def test_roll_is_final_requires_export_and_old_date(tmp_path: Path) -> None:
    vd = tmp_path / "votes"
    _write_roll(vd, "h-118-1-0001", "2023-01-09T12:00:00-05:00")
    _write_roll(vd, "h-119-2-0500", "2026-08-11T12:00:00-04:00")
    # Exported + old → skip.
    assert incremental.roll_is_final("h-118-1-0001", CUTOFF, votes_dir=vd) is True
    # Exported + recent → do not skip.
    assert incremental.roll_is_final("h-119-2-0500", CUTOFF, votes_dir=vd) is False
    # Never exported → do not skip (must fetch a brand-new roll).
    assert incremental.roll_is_final("h-119-2-0999", CUTOFF, votes_dir=vd) is False


def test_recent_bill_ids_only_from_recent_rolls(tmp_path: Path) -> None:
    vd = tmp_path / "votes"
    vd.mkdir(parents=True)
    (vd / "a.json").write_text(json.dumps(
        {"rollcall": {"id": "a", "date": "2023-01-09T12:00:00-05:00", "bill_id": "hr1-118"}}))
    (vd / "b.json").write_text(json.dumps(
        {"rollcall": {"id": "b", "date": "2026-08-11T12:00:00-04:00", "bill_id": "hr9-119"}}))
    (vd / "c.json").write_text(json.dumps(
        {"rollcall": {"id": "c", "date": "2026-08-11T12:00:00-04:00", "bill_id": None}}))
    recent = incremental.recent_bill_ids(CUTOFF, votes_dir=vd)
    assert recent == {"hr9-119"}  # old bill excluded; null bill_id ignored


def test_bill_is_skippable(tmp_path: Path) -> None:
    bd = tmp_path / "bills"
    bd.mkdir(parents=True)
    (bd / "hr1-118.json").write_text("{}")
    # Exported and not recent → skip.
    assert incremental.bill_is_skippable("hr1-118", set(), bills_dir=bd) is True
    # Exported but referenced by a recent roll → refresh.
    assert incremental.bill_is_skippable("hr1-118", {"hr1-118"}, bills_dir=bd) is False
    # Not exported → fetch.
    assert incremental.bill_is_skippable("hr2-119", set(), bills_dir=bd) is False
