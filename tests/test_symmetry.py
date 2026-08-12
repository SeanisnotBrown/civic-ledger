"""INC-10 tests — statement-balance symmetry (§6.5, D1). The rule is INACTIVE
(never a failure) below the activation median, which is its real state at INC-10
(zero statements). Above it, the three balance findings fire. All pure/offline.
"""

from __future__ import annotations

from ingest import config
from ingest.checks.symmetry import statement_balance

_MEMBERS = [
    {"id": "R1", "party": "R"},
    {"id": "R2", "party": "R"},
    {"id": "D1", "party": "D"},
]


def _stmts(by_member: dict[str, int], *, scored: dict[str, int] | None = None) -> list[dict]:
    scored = scored or {}
    out: list[dict] = []
    for mid, n in by_member.items():
        for i in range(n):
            lvl = 2 if i < scored.get(mid, 0) else None
            out.append({"member_id": mid, "specificity_level": lvl})
    return out


def test_zero_statements_is_inactive_not_a_failure() -> None:
    # The INC-10 reality: no statements exist yet → inactive, green.
    rep = statement_balance(_MEMBERS, [])
    assert rep["status"] == "inactive"
    assert rep["total_statements"] == 0


def test_below_activation_median_is_inactive() -> None:
    # Everyone has a few but the median is under the activation floor.
    rep = statement_balance(_MEMBERS, _stmts({"R1": 4, "R2": 4, "D1": 4}))
    assert rep["status"] == "inactive"
    assert config.SYMMETRY_MEDIAN_ACTIVATION == 5  # pin the contract the test rides on


def test_active_and_balanced_passes() -> None:
    rep = statement_balance(
        _MEMBERS,
        _stmts({"R1": 6, "R2": 6, "D1": 6}, scored={"R1": 3, "R2": 3, "D1": 3}),
    )
    assert rep["status"] == "pass", rep
    assert rep["findings"] == []


def test_member_below_floor_fails() -> None:
    # D1 has far fewer than 0.60 * median(=6) = 3.6 → floor violation.
    rep = statement_balance(_MEMBERS, _stmts({"R1": 6, "R2": 6, "D1": 1}))
    assert rep["status"] == "fail"
    assert any("D1" in f for f in rep["findings"])


def test_party_mean_gap_fails() -> None:
    # R mean = 10, D mean = 6 → 40% gap > 25% threshold. Floors still satisfied.
    rep = statement_balance(_MEMBERS, _stmts({"R1": 10, "R2": 10, "D1": 6}))
    assert rep["status"] == "fail"
    assert any("party mean" in f for f in rep["findings"])


def test_specificity_gap_fails() -> None:
    # Counts balanced, but R scores 100% of its statements and D scores 0%.
    rep = statement_balance(
        _MEMBERS,
        _stmts({"R1": 6, "R2": 6, "D1": 6}, scored={"R1": 6, "R2": 6, "D1": 0}),
    )
    assert rep["status"] == "fail"
    assert any("specificity" in f for f in rep["findings"])
