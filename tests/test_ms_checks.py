"""INC-12 phase 3 — MS state-layer checks. Unit tests drive the consistency
invariants from synthetic rolls; the integrity + full-suite tests run over the
committed data/state/ms/ dataset + the committed official-PDF samples (offline)."""

from __future__ import annotations

from ingest.checks import ms


def _roll(rid="ms-h-2249-1", *, totals, party_totals, member_votes,
          vote_class="passage", rule="MS-PASS", question="House Passed"):
    return {"rollcall": {"id": rid, "totals": totals, "party_totals": party_totals,
                         "vote_class": vote_class, "vote_class_rule": rule, "question": question},
            "member_votes": member_votes}


def _clean_roll():
    return _roll(
        totals={"yea": 2, "nay": 1, "present": 0, "not_voting": 0},
        party_totals={"R": {"yea": 2, "nay": 0, "present": 0, "not_voting": 0},
                      "D": {"yea": 0, "nay": 1, "present": 0, "not_voting": 0}},
        member_votes=[{"member_id": "ms-1", "position": "yea"},
                      {"member_id": "ms-2", "position": "yea"},
                      {"member_id": "ms-3", "position": "nay"}],
    )


_ROSTER = {"ms-1", "ms-2", "ms-3"}


# --- PDF total parsing ----------------------------------------------------


def test_parse_house_or_bucket():
    txt = "Yeas--A, B. Total--2. \nNays--C. Total--1. \nAbsent or those not voting--D. Total--1."
    assert ms.parse_official_totals(txt) == {"yea": 2, "nay": 1, "not_voting": 1}


def test_parse_senate_and_bucket_and_house_present():
    # Senate says "Absent and those not voting"; House can add a Present bucket — both
    # fold into not_voting.
    sen = ("Yeas--A. Total--1. \nNays--B. Total--1. \n"
           "Absent and those not voting--C, D, E. Total--3.")
    assert ms.parse_official_totals(sen)["not_voting"] == 3
    house = ("Yeas--A. Total--1. \nNays--B. Total--1. \n"
             "Present--C. Total--1. \nAbsent or those not voting--D. Total--1.")
    assert ms.parse_official_totals(house)["not_voting"] == 2


# --- consistency invariants -----------------------------------------------


def test_consistency_clean_roll_passes():
    assert ms.consistency_failures([_clean_roll()], _ROSTER) == []


def test_consistency_flags_total_mismatch():
    r = _clean_roll()
    r["rollcall"]["totals"]["yea"] = 5  # lie about the tally
    fails = ms.consistency_failures([r], _ROSTER)
    assert any("recompute" in f for f in fails)


def test_consistency_flags_unknown_voter():
    r = _clean_roll()
    r["member_votes"][0]["member_id"] = "ms-999"
    fails = ms.consistency_failures([r], _ROSTER)
    assert any("not in the MS roster" in f for f in fails)


def test_consistency_flags_party_totals_sum():
    r = _clean_roll()
    r["rollcall"]["party_totals"]["R"]["yea"] = 1  # no longer sums to totals.yea=2
    fails = ms.consistency_failures([r], _ROSTER)
    assert any("party_totals" in f for f in fails)


def test_consistency_flags_unclassified():
    r = _clean_roll()
    r["rollcall"]["vote_class"] = "other"
    r["rollcall"]["vote_class_rule"] = "MS-OTHER"
    fails = ms.consistency_failures([r], _ROSTER)
    assert any("unclassified" in f for f in fails)


# --- integrity + full suite over committed data (offline) -----------------


def test_integrity_spot_check_matches_official_pdfs():
    # Scrape-fidelity regression: every committed sample's official tally equals our
    # ingested roll's totals (the automated form of the GO-verdict 5/5, D21).
    votes_by_id = {rec["rollcall"]["id"]: rec for rec in ms._load_votes()}
    if not votes_by_id:
        import pytest
        pytest.skip("no committed MS data in this checkout")
    assert ms.integrity_failures(votes_by_id) == []


def test_ms_check_main_green_on_committed_dataset():
    assert ms.main() == 0
