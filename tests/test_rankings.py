"""V2-2 tests — rankings & percentile layer. Offline; build_metric/build_all are
pure over injected metrics+members fixtures (no committed-data read)."""

from __future__ import annotations

from ingest import rankings
from ingest.rankings import (
    RANKED_METRICS,
    VOTE_METRICS,
    _rank_and_percentile,
    build_all,
    build_metric,
)

# A tiny roster: House {H1,H2,H3,NEW,DEL} + Senate {S1,S2}. DEL sits for Puerto
# Rico (a non-voting delegate — "PR" is not in VOTING_STATES). NEW has no
# attendance value (newly seated). Parties mix so party-means are checkable.
MEMBERS = {
    "H1": {"id": "H1", "chamber": "house", "state": "CA", "party": "D"},
    "H2": {"id": "H2", "chamber": "house", "state": "TX", "party": "R"},
    "H3": {"id": "H3", "chamber": "house", "state": "NY", "party": "D"},
    "NEW": {"id": "NEW", "chamber": "house", "state": "OH", "party": "R"},
    "DEL": {"id": "DEL", "chamber": "house", "state": "PR", "party": "D"},
    "S1": {"id": "S1", "chamber": "senate", "state": "CA", "party": "D"},
    "S2": {"id": "S2", "chamber": "senate", "state": "TX", "party": "R"},
}
METRICS = {
    "H1": {"attendance": {"pct": 90.0}, "sponsored": {"count": 10}},
    "H2": {"attendance": {"pct": 90.0}, "sponsored": {"count": 5}},
    "H3": {"attendance": {"pct": 80.0}, "sponsored": {"count": 5}},
    "NEW": {"attendance": {"pct": None}, "sponsored": {"count": 3}},
    "DEL": {"attendance": {"pct": 100.0}, "sponsored": {"count": 20}},
    "S1": {"attendance": {"pct": 95.0}, "sponsored": {"count": 8}},
    "S2": {"attendance": {"pct": 85.0}, "sponsored": {"count": 8}},
}


def test_competition_rank_and_percentile_with_ties():
    # Values 90,90,80: the two 90s share rank 1; 80 is rank 3 (competition). Percentile
    # = % strictly below: each 90 has 1 of 3 below (33.3); 80 has none (0.0).
    rp = _rank_and_percentile([("a", 90.0), ("b", 90.0), ("c", 80.0)])
    assert rp["a"] == (1, 33.3) and rp["b"] == (1, 33.3)
    assert rp["c"] == (3, 0.0)


def test_vote_metric_excludes_delegates_and_null_values():
    rf = build_metric("attendance", "pct", METRICS, MEMBERS, "Attendance")
    assert rf.ranks_delegates is False
    house = rf.chambers["house"]
    assert "DEL" not in house.members and house.excluded_delegates == ["DEL"]
    assert "NEW" not in house.members  # null pct → not ranked, not "excluded"
    assert house.covered == 3  # H1, H2, H3
    assert house.mean == round((90 + 90 + 80) / 3, 2) and house.median == 90.0
    # party means group by CURRENT party: D = mean(H1,H3), R = H2 only.
    assert house.party_means == {"D": 85.0, "R": 90.0}


def test_bill_metric_includes_delegates_and_preserves_int():
    rf = build_metric("sponsored", "count", METRICS, MEMBERS, "Bills sponsored")
    assert rf.ranks_delegates is True
    house = rf.chambers["house"]
    assert house.excluded_delegates == []
    assert "DEL" in house.members
    entry = house.members["DEL"]
    assert entry.value == 20 and isinstance(entry.value, int)  # not 20.0
    assert entry.rank == 1  # DEL sponsored the most (20)
    # H2 and H3 tie at 5 → share a rank; NEW (3) is last.
    assert house.members["H2"].rank == house.members["H3"].rank
    assert house.covered == 5  # counts are never null


def test_chambers_ranked_separately():
    rf = build_metric("attendance", "pct", METRICS, MEMBERS, "Attendance")
    senate = rf.chambers["senate"]
    assert set(senate.members) == {"S1", "S2"}
    assert senate.members["S1"].rank == 1 and senate.members["S2"].rank == 2
    assert senate.excluded_delegates == []


def test_empty_chamber_has_null_mean_median():
    # A metric present for no one in a chamber → covered 0, null aggregates.
    rf = build_metric("attendance", "pct", {"S1": {"attendance": {"pct": None}}},
                      {"S1": MEMBERS["S1"]}, "Attendance")
    senate = rf.chambers["senate"]
    assert senate.covered == 0 and senate.mean is None and senate.median is None
    assert senate.members == {}


def test_build_all_covers_exactly_the_ranked_metrics():
    all_rf = build_all(METRICS, MEMBERS)
    assert set(all_rf) == set(RANKED_METRICS)
    # Vote metrics hold delegates out; the rest include them.
    for key, rf in all_rf.items():
        assert rf.ranks_delegates == (key not in VOTE_METRICS)
        assert rf.metric == key and rf.label


def test_methodology_text_is_present_and_non_evaluative():
    rf = build_metric("attendance", "pct", METRICS, MEMBERS, "Attendance")
    text = rf.methodology.lower()
    assert "percentile" in text and "delegate" in text
    # No evaluative framing at V2-2 (banned/label words belong to V2-4).
    for word in ("best", "worst", "grade", "good", "poor"):
        assert word not in text


def test_rank_direction_is_by_value_descending():
    # Rank 1 is the highest value, not the lowest.
    rp = _rank_and_percentile([("hi", 99.0), ("lo", 1.0)])
    assert rp["hi"][0] == 1 and rp["lo"][0] == 2


def test_export_writes_one_file_per_ranked_metric(tmp_path):
    from ingest.export import export_rankings

    out = tmp_path / "rankings"
    paths = export_rankings(build_all(METRICS, MEMBERS), out_dir=out)
    written = sorted(p.name for p in out.glob("*.json"))
    assert written == ["attendance.json", "cosponsored.json", "enacted_rate.json",
                       "party_unity.json", "sponsored.json"]
    assert len(paths) == 5


def test_run_loads_committed_data_and_returns_zero(monkeypatch):
    # run() loads the committed dataset (exercising _load_inputs) then exports; stub
    # only the writer so the test does not touch data/rankings/.
    from ingest import export

    captured: dict[str, list[str]] = {}
    monkeypatch.setattr(
        export, "export_rankings",
        lambda built, **kw: captured.setdefault("keys", sorted(built)) and [],
    )
    assert rankings.run() == 0
    assert captured["keys"] == sorted(RANKED_METRICS)
