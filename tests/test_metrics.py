"""INC-10 tests — Tier-2 metrics. Unit tests drive each metric from a synthetic
Ctx; the recompute-and-match test re-derives the committed data/metrics.json from
the public dataset (§8 "recompute and match"), and the acceptance test pins the
metric-key set == the published-model fields.
"""

from __future__ import annotations

import json

import pytest

from ingest import metrics
from ingest.cache import repo_root
from ingest.metrics import METRICS, Ctx
from ingest.models import MemberMetrics, MetricsFile

_TERM = {"start": "2023-01-03", "end": "2029-01-03", "party": "R", "chamber": "senate"}
_MEMBER = {"id": "M1", "party": "R", "chamber": "senate", "terms": [_TERM]}


def _rc(rc_id, cls, bill_id, date, pt=None, congress=119):
    return {"id": rc_id, "vote_class": cls, "vote_class_rule": cls, "bill_id": bill_id,
            "date": date, "chamber": "senate", "congress": congress,
            "totals": {}, "party_totals": pt}


def _R(yea, nay):  # a party_totals block with only R present
    return {"R": {"yea": yea, "nay": nay, "present": 0, "not_voting": 0}}


def _ctx(positions, legislation=None, statements=None, voted=None, ended=frozenset({118})):
    return Ctx(
        members={"M1": _MEMBER},
        positions={"M1": positions},
        legislation=legislation or {"M1": {"member_id": "M1", "sponsored": [], "cosponsored": []}},
        statements=statements or [],
        voted_bill_ids=voted or set(),
        ended_congresses=ended,
    )


# --- attendance -----------------------------------------------------------


def test_attendance_counts_present_as_cast_missed_as_not_voting() -> None:
    pos = [
        (_rc("s-119-1-0001", "passage", "s1-119", "2025-01-01", _R(1, 0)), "yea"),
        (_rc("s-119-1-0002", "passage", "s2-119", "2025-01-02", _R(1, 0)), "present"),
        (_rc("s-119-1-0003", "passage", "s3-119", "2025-01-03", _R(1, 0)), "not_voting"),
    ]
    v = metrics.attendance("M1", _ctx(pos))
    assert v == {"eligible": 3, "cast": 2, "missed": 1, "pct": 66.67}


# --- party_unity ----------------------------------------------------------


def test_party_unity_majority_ties_and_procedural_exclusion() -> None:
    pos = [
        (_rc("r1", "passage", "b1", "2025-01-01", _R(40, 5)), "yea"),      # agrees w/ R majority
        (_rc("r2", "amendment", "b2", "2025-01-02", _R(40, 5)), "nay"),    # disagrees (maj. yea)
        (_rc("r3", "passage", "b3", "2025-01-03", _R(10, 10)), "yea"),     # party tie -> excluded
        (_rc("r4", "procedural", "b4", "2025-01-04", _R(40, 5)), "nay"),   # procedural -> excluded
        (_rc("r5", "passage", "b5", "2025-01-05", _R(40, 5)), "present"),  # present -> excluded
    ]
    v = metrics.party_unity("M1", _ctx(pos))
    assert v == {"substantive": 2, "agreed": 1, "pct": 50.0, "excluded_ties": 1}


def test_party_unity_null_when_no_substantive() -> None:
    v = metrics.party_unity("M1", _ctx([]))
    assert v["substantive"] == 0 and v["pct"] is None


# --- sponsored / cosponsored / enacted_rate -------------------------------


def test_counts_and_enacted_rate() -> None:
    leg = {"M1": {"member_id": "M1",
                  "sponsored": [{"bill_id": "s1-119", "congress": 119, "became_law": True},
                                {"bill_id": "s2-119", "congress": 119, "became_law": False},
                                {"bill_id": "s3-118", "congress": 118, "became_law": False}],
                  "cosponsored": [{"bill_id": "s9-119", "congress": 119, "became_law": False}]}}
    ctx = _ctx([], legislation=leg)
    assert metrics.sponsored("M1", ctx) == {"count": 3}
    assert metrics.cosponsored("M1", ctx) == {"count": 1}
    assert metrics.enacted_rate("M1", ctx) == {"sponsored": 3, "enacted": 1, "pct": 33.33}


def test_enacted_rate_null_when_no_sponsored() -> None:
    assert metrics.enacted_rate("M1", _ctx([]))["pct"] is None


# --- cosponsor_vote_gap ---------------------------------------------------


def test_gap_voted_nay_and_no_floor_action() -> None:
    leg = {"M1": {"member_id": "M1", "sponsored": [], "cosponsored": [
        {"bill_id": "s10-118", "congress": 118, "became_law": False},   # no floor, ended
        {"bill_id": "s11-119", "congress": 119, "became_law": False},   # ongoing -> never listed
        {"bill_id": "s12-118", "congress": 118, "became_law": False},   # got a floor vote (nay)
    ]}}
    pos = [(_rc("s-118-1-0005", "passage", "s12-118", "2024-01-01", _R(1, 0), congress=118), "nay")]
    gaps = metrics.cosponsor_vote_gap("M1", _ctx(pos, legislation=leg, voted={"s12-118"}))
    kinds = {(g["bill_id"], g["kind"]) for g in gaps}
    assert ("s12-118", "cosponsored_and_voted_nay") in kinds
    assert ("s10-118", "cosponsored_no_floor_action") in kinds
    assert not any(g["bill_id"] == "s11-119" for g in gaps)  # ongoing congress excluded
    nay = next(g for g in gaps if g["kind"] == "cosponsored_and_voted_nay")
    assert nay["rollcall_id"] == "s-118-1-0005"  # traceable to the roll


# --- named_measure_mismatch (fail-closed) ---------------------------------


def test_mismatch_empty_without_statements() -> None:
    assert metrics.named_measure_mismatch("M1", _ctx([])) == []


def test_mismatch_fails_closed_on_qualifying_statement() -> None:
    stmts = [{"member_id": "M1", "specificity_level": 2, "named_measures": ["s1-119"],
              "id": "st1", "source_url": "u"}]
    with pytest.raises(NotImplementedError):
        metrics.named_measure_mismatch("M1", _ctx([], statements=stmts))


# --- absence_context ------------------------------------------------------


def test_absence_context_same_day_participation() -> None:
    pos = [
        (_rc("s-119-1-0001", "passage", "b1", "2025-03-05T10:00:00", _R(1, 0)), "yea"),
        (_rc("s-119-1-0002", "passage", "b2", "2025-03-05T11:00:00", _R(1, 0)), "not_voting"),
        (_rc("s-119-1-0003", "passage", "b3", "2025-03-06T10:00:00", _R(1, 0)), "not_voting"),
    ]
    rows = metrics.absence_context("M1", _ctx(pos))
    by_roll = {c["rollcall_id"]: c for c in rows}
    # Missed s-...0002 but cast s-...0001 the same day: 2 rolls that day, 1 cast.
    assert by_roll["s-119-1-0002"] == {"rollcall_id": "s-119-1-0002", "date": "2025-03-05",
                                       "same_day_total": 2, "same_day_cast": 1}
    # Missed the only roll on 03-06: 1 that day, 0 cast — never framed as "absent".
    assert by_roll["s-119-1-0003"]["same_day_cast"] == 0


# --- acceptance: keys, recompute-and-match --------------------------------


def test_metric_keys_equal_published_model_fields() -> None:
    # The methods-page set-equality contract rides on these three being identical.
    assert set(METRICS) == set(MemberMetrics.model_fields)


def test_recompute_matches_committed_metrics_json() -> None:
    committed = json.loads((repo_root() / "data" / "metrics.json").read_text(encoding="utf-8"))
    fresh = metrics.build().model_dump()
    assert fresh == committed, "data/metrics.json is stale — re-run `ingest metrics`"


def test_committed_metrics_schema_valid() -> None:
    MetricsFile.model_validate(
        json.loads((repo_root() / "data" / "metrics.json").read_text(encoding="utf-8"))
    )
