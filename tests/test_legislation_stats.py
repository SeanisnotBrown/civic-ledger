"""V2-5 tests — the introduced-bill universe stat behind the dashboard headline.

`compute` is driven from a synthetic data dir (legislation/ + votes/); the recompute
guard (verify_recompute invariant 7) is exercised end-to-end by `uv run verify-recompute`
in CI, and its mismatch branch is unit-tested here against a doctored manifest.
"""

from __future__ import annotations

import json
from pathlib import Path

from ingest import legislation_stats, verify_recompute


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8", newline="\n")


def _roll(bill_id: str | None) -> dict:
    return {"rollcall": {"bill_id": bill_id}}


def _legis(member_id: str, sponsored: list[tuple[str, bool]]) -> dict:
    return {
        "member_id": member_id,
        "sponsored": [{"bill_id": b, "became_law": law} for b, law in sponsored],
        "cosponsored": [],
    }


def test_compute_zero_on_empty_dataset(tmp_path: Path) -> None:
    # No legislation/ or votes/ dir yet (pre-V2-1): every count is 0, never a crash.
    v = legislation_stats.compute(tmp_path)
    assert v == {
        "sponsored_bills": 0, "sponsored_with_rollcall": 0,
        "sponsored_without_rollcall": 0, "sponsored_became_law": 0,
        "became_law_without_rollcall": 0,
    }


def test_compute_counts_universe_votes_and_law_without_rollcall(tmp_path: Path) -> None:
    # Two members sponsor 5 distinct bills. Voted set covers 2 of them. Of the 2 that
    # became law, one got a roll call and one did NOT (voice/UC) -> the disclosure count.
    _write(tmp_path / "legislation" / "M1.json",
           _legis("M1", [("hr1-119", True), ("hr2-119", False), ("hr3-119", True)]))
    _write(tmp_path / "legislation" / "M2.json",
           _legis("M2", [("s10-119", False), ("s11-119", False)]))
    # hr1 got a recorded roll call (and became law); hr3 became law but has no roll;
    # s10 got a roll call but never became law; a null-bill roll is ignored.
    _write(tmp_path / "votes" / "r1.json", _roll("hr1-119"))
    _write(tmp_path / "votes" / "r2.json", _roll("s10-119"))
    _write(tmp_path / "votes" / "r3.json", _roll(None))

    v = legislation_stats.compute(tmp_path)
    assert v == {
        "sponsored_bills": 5,
        "sponsored_with_rollcall": 2,        # hr1, s10
        "sponsored_without_rollcall": 3,     # hr2, hr3, s11
        "sponsored_became_law": 2,           # hr1, hr3
        "became_law_without_rollcall": 1,    # hr3 (hr1 had a roll call)
    }


def test_check_legislation_stats_flags_a_stale_manifest(tmp_path, monkeypatch) -> None:
    # verify_recompute invariant 7: a manifest whose published block disagrees with a
    # fresh recompute is a failure (a landing number that no longer derives from data).
    _write(tmp_path / "data" / "legislation" / "M1.json", _legis("M1", [("hr1-119", False)]))
    _write(tmp_path / "data" / "votes" / "r1.json", _roll("hr1-119"))
    fresh = legislation_stats.compute(tmp_path / "data")
    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)

    _write(tmp_path / "data" / "manifest.json", {"counts": {"legislation": fresh}})
    assert verify_recompute.check_legislation_stats() == []  # matches -> no failure

    stale = {**fresh, "sponsored_bills": fresh["sponsored_bills"] + 99}
    _write(tmp_path / "data" / "manifest.json", {"counts": {"legislation": stale}})
    failures = verify_recompute.check_legislation_stats()
    assert len(failures) == 1 and "legislation stats" in failures[0]


def test_check_legislation_stats_noop_without_block(tmp_path, monkeypatch) -> None:
    # A pre-V2-5 manifest (no legislation block) or no legislation dir is a clean no-op.
    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)
    assert verify_recompute.check_legislation_stats() == []  # no legislation dir
    _write(tmp_path / "data" / "legislation" / "M1.json", _legis("M1", []))
    _write(tmp_path / "data" / "manifest.json", {"counts": {}})
    assert verify_recompute.check_legislation_stats() == []  # block absent
