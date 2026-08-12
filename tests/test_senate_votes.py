"""INC-4 tests — Senate roll-call parsing, menu enumeration/tally cross-check,
crosswalk join, and detail re-parse. Offline: uses the four committed 119/1
detail samples (cloture-on-bill / amendment / passage-tie-break / nomination) +
the committed menu sample and inline fixtures. No network.
"""

from __future__ import annotations

import copy

import pytest

from ingest import senate_votes
from ingest.cache import repo_root
from ingest.export import export_rollcall
from ingest.models import RollCall
from ingest.sources import senate_xml

SAMPLES = repo_root() / "data" / "quality" / "samples"

# The two covered MS senators' lis→bioguide crosswalk (as INC-2 exports it).
MS_XWALK = {"S395": "H001079", "S318": "W000437"}


def _detail(roll: int) -> str:
    return (SAMPLES / f"senate_vote_detail_119_1_{roll:05d}.xml").read_text(encoding="utf-8")


def _menu() -> str:
    return (SAMPLES / "senate_vote_menu_119_1.xml").read_text(encoding="utf-8")


# --- menu enumeration & tally ---------------------------------------------


def test_menu_enumerates_contiguously():
    menu = senate_xml.parse_menu(_menu())
    rolls = sorted(menu)
    assert len(rolls) == 659
    assert rolls == list(range(1, 660))  # 1..N contiguous — the completeness oracle
    # A known tally is carried per vote (cloture on PN373 was 51-42).
    assert menu[659] == (51, 42)


# --- parsing: the four real shape variants --------------------------------


def test_parse_cloture_on_bill():
    rc, mvs, absences = senate_votes.parse_rollcall(_detail(1), 119, 1, MS_XWALK, (84, 9))
    assert isinstance(rc, RollCall)
    assert rc.id == "s-119-1-0001"
    assert rc.chamber == "senate"
    assert rc.number == 1
    assert rc.date == "2025-01-09T14:54:00"  # "January 9, 2025,  02:54 PM" → naive ISO
    assert rc.bill_id == "s5-119"  # <document> S. 5
    assert rc.totals["yea"] == 84 and rc.totals["nay"] == 9
    assert rc.source_url.endswith("/vote1191/vote_119_1_00001.xml")
    assert {mv.member_id for mv in mvs} == {"H001079", "W000437"}
    assert all(mv.position == "yea" for mv in mvs)
    assert absences == []


def test_parse_amendment_uses_underlying_bill():
    # Amendment vote: <document> type "S.Amdt." has no number; bill_id must fall
    # back to <amendment><amendment_to_document_number> = "H.R. 1".
    rc, mvs, _ = senate_votes.parse_rollcall(_detail(371), 119, 1, MS_XWALK, (50, 50))
    assert rc.bill_id == "hr1-119"
    assert rc.totals == {"yea": 50, "nay": 50, "present": 0, "not_voting": 0}


def test_parse_passage_tie_break_totals_agree_with_menu():
    # VP tie-break passage: VP is absent from members AND the menu tally, so the
    # member-computed 50-50 matches the menu 50-50 with no special handling.
    rc, mvs, _ = senate_votes.parse_rollcall(_detail(372), 119, 1, MS_XWALK, (50, 50))
    assert rc.bill_id == "hr1-119"
    assert rc.result == "Bill Passed"
    assert rc.totals["yea"] == 50 and rc.totals["nay"] == 50


def test_parse_nomination_has_no_bill_id():
    # PN373 is a nomination, not legislation → bill_id None; absentees seed nothing
    # for MS here (both MS senators voted Yea).
    rc, mvs, absences = senate_votes.parse_rollcall(_detail(659), 119, 1, MS_XWALK, (51, 42))
    assert rc.bill_id is None
    assert rc.totals["not_voting"] == 7  # <count> absent == 7
    assert all(mv.position == "yea" for mv in mvs)
    assert absences == []


# --- cross-source tally check ---------------------------------------------


def test_tally_mismatch_raises():
    with pytest.raises(senate_votes.TallyMismatch):
        senate_votes.parse_rollcall(_detail(1), 119, 1, MS_XWALK, (83, 9))  # wrong yea


def test_missing_menu_tally_skips_check():
    # Vote carries no menu tally → cross-check is skipped, not failed.
    rc, _, _ = senate_votes.parse_rollcall(_detail(1), 119, 1, MS_XWALK, (None, None))
    assert rc.totals["yea"] == 84


# --- position mapping, absences, crosswalk --------------------------------


def test_not_voting_seeds_absence_stub():
    xml = _detail(1).replace(
        "<vote_cast>Yea</vote_cast>\n      <lis_member_id>S318</lis_member_id>",
        "<vote_cast>Not Voting</vote_cast>\n      <lis_member_id>S318</lis_member_id>",
    )
    # menu tally no longer matches (one fewer yea) → skip the check for this fixture.
    rc, mvs, absences = senate_votes.parse_rollcall(xml, 119, 1, MS_XWALK, None)
    wicker = next(mv for mv in mvs if mv.member_id == "W000437")
    assert wicker.position == "not_voting"
    assert [a.member_id for a in absences] == ["W000437"]
    assert absences[0].rollcall_id == "s-119-1-0001"
    assert absences[0].stated_reason is None


def test_unknown_vote_cast_raises():
    xml = _detail(1).replace("<vote_cast>Yea</vote_cast>", "<vote_cast>Maybe</vote_cast>", 1)
    with pytest.raises(senate_votes.UnknownVoteCast):
        senate_votes.parse_rollcall(xml, 119, 1, MS_XWALK, None)


def test_ms_lis_not_in_crosswalk_raises():
    # A covered MS senator whose lis is absent from the crosswalk is a hard error,
    # never a silent drop.
    with pytest.raises(KeyError):
        senate_votes.parse_rollcall(_detail(1), 119, 1, {"S395": "H001079"}, (84, 9))


# --- bill-id normalization ------------------------------------------------


@pytest.mark.parametrize(
    ("mtype", "mnum", "expected"),
    [
        ("H.R.", "1", "hr1-119"),
        ("S.", "5", "s5-119"),
        ("S.J.Res.", "82", "sjres82-119"),
        ("PN", "373", None),
        ("Treaty Doc.", "5", None),
        ("S.Amdt.", "", None),
    ],
)
def test_measure_id_normalization(mtype, mnum, expected):
    assert senate_votes._measure_id(mtype, mnum, 119) == expected


# --- detail re-parse (integrity source) -----------------------------------


def test_parse_positions_joins_crosswalk_and_filters_state():
    ms = senate_xml.parse_positions(_detail(1), MS_XWALK, state="MS")
    assert ms == {"H001079": "yea", "W000437": "yea"}
    # No state filter → still only the members present in the (MS-only) crosswalk.
    everyone = senate_xml.parse_positions(_detail(1), MS_XWALK)
    assert everyone == {"H001079": "yea", "W000437": "yea"}


# --- deterministic export -------------------------------------------------


def test_senate_vote_export_deterministic(tmp_path):
    rc, mvs, _ = senate_votes.parse_rollcall(_detail(1), 119, 1, MS_XWALK, (84, 9))
    a = export_rollcall(rc, mvs, out_dir=tmp_path / "a")
    b = export_rollcall(rc, copy.deepcopy(mvs), out_dir=tmp_path / "b")
    assert a.read_bytes() == b.read_bytes()
    assert a.name == "s-119-1-0001.json"
    assert b"\r\n" not in a.read_bytes()
