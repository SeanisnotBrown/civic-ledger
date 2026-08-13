"""V2-1 (D60) — date-windowed coverage, the shared helper `house_votes.py`,
`senate_votes.py`, `checks/symmetry.py`, and `verify_recompute.py` all reuse so
mid-congress churn (a resignation, an expulsion, a death, a special election)
never reads as a false coverage gap.
"""

from __future__ import annotations

from ingest import coverage


def test_covered_on_within_single_term():
    terms = {"A": [("2023-01-03", "2025-01-03")]}
    assert coverage.covered_on(terms, "2024-06-01") == {"A"}


def test_covered_on_excludes_before_and_after_term():
    terms = {"A": [("2023-01-03", "2025-01-03")]}
    assert coverage.covered_on(terms, "2022-12-31") == set()
    assert coverage.covered_on(terms, "2025-01-04") == set()


def test_covered_on_boundaries_are_inclusive():
    terms = {"A": [("2023-01-03", "2025-01-03")]}
    assert coverage.covered_on(terms, "2023-01-03") == {"A"}
    assert coverage.covered_on(terms, "2025-01-03") == {"A"}


def test_covered_on_mid_congress_resignation_not_flagged_after_departure():
    # McCarthy-style: served part of the 118th, resigned mid-congress.
    terms = {"A": [("2023-01-03", "2023-12-20")]}
    assert coverage.covered_on(terms, "2023-06-01") == {"A"}
    assert coverage.covered_on(terms, "2024-01-15") == set()


def test_covered_on_seat_churn_two_people_same_window():
    # A seat changing hands mid-congress: both people are real, on different dates.
    terms = {
        "OLD": [("2023-01-03", "2023-09-29")],
        "NEW": [("2023-10-03", "2025-01-03")],
    }
    assert coverage.covered_on(terms, "2023-06-01") == {"OLD"}
    assert coverage.covered_on(terms, "2023-11-01") == {"NEW"}
    assert coverage.covered_on(terms, "2023-09-30") == set()  # true gap day


def test_covered_on_multiple_terms_non_contiguous():
    # A member who left and later returned (rare, but terms lists allow it).
    terms = {"A": [("2019-01-03", "2021-01-03"), ("2023-01-03", "2025-01-03")]}
    assert coverage.covered_on(terms, "2022-01-01") == set()
    assert coverage.covered_on(terms, "2020-01-01") == {"A"}
    assert coverage.covered_on(terms, "2024-01-01") == {"A"}


def test_member_terms_filters_by_chamber(tmp_path):
    import json

    (tmp_path / "A.json").write_text(json.dumps({
        "id": "A", "chamber": "house",
        "terms": [
            {"start": "2019-01-03", "end": "2021-01-03", "chamber": "senate", "party": "D"},
            {"start": "2023-01-03", "end": "2025-01-03", "chamber": "house", "party": "D"},
        ],
    }), encoding="utf-8")
    terms = coverage.member_terms(tmp_path, "house")
    assert terms == {"A": [("2023-01-03", "2025-01-03")]}


def test_member_terms_includes_chamber_switchers_by_term_not_current_chamber(tmp_path):
    # A House member in the 118th who won a Senate seat for the 119th: their
    # top-level (current/latest) chamber is now "senate", but their 118th House
    # terms are still real and must still show up in the HOUSE lookup (the bug
    # found empirically in V2-1 P2 — filtering on Member.chamber dropped them).
    import json

    (tmp_path / "B.json").write_text(json.dumps({
        "id": "B", "chamber": "senate",  # current chamber, post-switch
        "terms": [
            {"start": "2017-01-03", "end": "2023-01-03", "chamber": "house", "party": "R"},
            {"start": "2023-01-03", "end": "2025-01-03", "chamber": "house", "party": "R"},
            {"start": "2025-01-03", "end": "2031-01-03", "chamber": "senate", "party": "R"},
        ],
    }), encoding="utf-8")
    house_terms = coverage.member_terms(tmp_path, "house")
    senate_terms = coverage.member_terms(tmp_path, "senate")
    assert house_terms["B"] == [("2017-01-03", "2023-01-03"), ("2023-01-03", "2025-01-03")]
    assert senate_terms["B"] == [("2025-01-03", "2031-01-03")]
    assert coverage.covered_on(house_terms, "2023-06-01") == {"B"}
    assert coverage.covered_on(senate_terms, "2023-06-01") == set()
    assert coverage.covered_on(senate_terms, "2025-06-01") == {"B"}


def test_member_terms_empty_dir(tmp_path):
    assert coverage.member_terms(tmp_path, "house") == {}


def test_member_terms_missing_dir(tmp_path):
    assert coverage.member_terms(tmp_path / "nope", "house") == {}


# --- V2-1 (D61): the three gap-reporting exceptions -------------------------


def test_delegate_bioguides_detects_by_state(tmp_path):
    import json

    (tmp_path / "A.json").write_text(
        json.dumps({"id": "A", "state": "DC", "terms": []}), encoding="utf-8"
    )
    (tmp_path / "B.json").write_text(
        json.dumps({"id": "B", "state": "MS", "terms": []}), encoding="utf-8"
    )
    assert coverage.delegate_bioguides(tmp_path) == {"A"}


def test_speaker_on_within_and_outside_tenure():
    assert coverage.speaker_on("2023-06-01") == {"M001165"}  # McCarthy
    assert coverage.speaker_on("2024-01-01") == {"J000299"}  # Johnson
    assert coverage.speaker_on("2023-01-04") == set()  # before either was elected


def test_seating_lag_on_near_boundary_only():
    terms = {"A": [("2024-06-11", "2025-01-03")]}
    assert coverage.seating_lag_on(terms, "2024-06-12") == {"A"}  # 1 day after start
    assert coverage.seating_lag_on(terms, "2024-07-02") == {"A"}  # 21 days — boundary, inclusive
    assert coverage.seating_lag_on(terms, "2024-07-03") == set()  # 22 days — well clear
    assert coverage.seating_lag_on(terms, "2024-06-01") == {"A"}  # 10 days BEFORE start —
    # still within the window (harmless: not covered_on yet, so never actually
    # "expected" — expected_on() always intersects with covered_on() first).
    assert coverage.seating_lag_on(terms, "2024-05-01") == set()  # well before the window


def test_expected_on_subtracts_all_three_exceptions():
    terms = {
        "M001165": [("2017-01-03", "2027-01-03")],  # McCarthy — covered throughout
        "DELEGATE": [("2023-01-03", "2027-01-03")],
        "NEW": [("2024-06-11", "2027-01-03")],  # seated 2024-06-11 (seating-lag exception)
        "REGULAR": [("2023-01-03", "2027-01-03")],
    }
    delegates = {"DELEGATE"}
    # Within McCarthy's actual Speaker tenure (2023-01-07..2023-10-03): he's
    # covered_on but excluded from expected_on by the Speaker exception.
    assert coverage.expected_on(terms, "2023-06-01", delegates) == {"REGULAR"}
    # Within NEW's seating-lag window (first 14 days) and after McCarthy left the
    # Speakership (so he's expected again, like any regular covered member).
    assert coverage.expected_on(terms, "2024-06-15", delegates) == {"M001165", "REGULAR"}
    # Clear of both: everyone covered is expected except the delegate.
    assert coverage.expected_on(terms, "2024-08-01", delegates) == {
        "M001165", "NEW", "REGULAR"
    }
