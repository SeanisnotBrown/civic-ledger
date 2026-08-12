"""INC-3 tests — House roll-call parsing, clerk XML cross-check parsing, and
deterministic vote export. Offline: uses the committed 119/1/240 sample and
inline fixtures; no network.
"""

from __future__ import annotations

import copy
import json

import pytest

from ingest import house_votes
from ingest.cache import repo_root
from ingest.export import export_rollcall
from ingest.models import RollCall
from ingest.sources import clerk_house

SAMPLE = (
    repo_root() / "data" / "quality" / "samples"
    / "congress_house_vote_members_119_1_240.json"
)


def _sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


# --- parsing --------------------------------------------------------------


def test_parse_rollcall_totals_and_ms_votes():
    rc, mvs, absences = house_votes.parse_rollcall(_sample(), 119, 1)
    assert isinstance(rc, RollCall)
    assert rc.id == "h-119-1-0240"
    assert rc.chamber == "house"
    assert rc.totals == {"yea": 397, "nay": 1, "present": 0, "not_voting": 32}
    assert sum(rc.totals.values()) == 430  # every result bucketed
    # party_totals (INC-10): aggregate per-party split that sums back to totals.
    assert rc.party_totals is not None
    for cat in ("yea", "nay", "present", "not_voting"):
        assert sum(p[cat] for p in rc.party_totals.values()) == rc.totals[cat]
    assert rc.bill_id == "hr3424-119"
    assert rc.vote_class == "other" and rc.vote_class_rule == "unclassified"
    assert rc.source_url == "https://clerk.house.gov/evs/2025/roll240.xml"
    # Exactly the 4 MS House members, all Yea on this roll.
    assert {mv.member_id for mv in mvs} == {"E000235", "G000591", "K000388", "T000193"}
    assert all(mv.position == "yea" for mv in mvs)
    assert absences == []  # nobody from MS was not_voting here


def test_not_voting_seeds_absence_stub():
    data = _sample()
    # Flip one MS member to "Not Voting".
    for r in data["houseRollCallVoteMemberVotes"]["results"]:
        if r["bioguideID"] == "G000591":
            r["voteCast"] = "Not Voting"
    rc, mvs, absences = house_votes.parse_rollcall(data, 119, 1)
    guest = next(mv for mv in mvs if mv.member_id == "G000591")
    assert guest.position == "not_voting"
    assert [a.member_id for a in absences] == ["G000591"]
    assert absences[0].rollcall_id == "h-119-1-0240"
    assert absences[0].stated_reason is None


def test_aye_no_map_to_yea_nay():
    # "Recorded Vote" ballots (Committee of the Whole) use Aye/No, not Yea/Nay.
    data = _sample()
    results = data["houseRollCallVoteMemberVotes"]["results"]
    for r in results:
        if r["voteCast"] == "Yea":
            r["voteCast"] = "Aye"
    rc, mvs, _ = house_votes.parse_rollcall(data, 119, 1)
    assert rc.totals["yea"] == 397  # Aye counted as yea
    assert all(mv.position == "yea" for mv in mvs)


def test_lone_bad_cast_raises_not_non_position():
    # A single unmappable cast among 430 is a data glitch → quarantine, NOT a
    # silently-dropped roll (the majority rule protects real votes).
    data = _sample()
    data["houseRollCallVoteMemberVotes"]["results"][0]["voteCast"] = "Maybe"
    with pytest.raises(house_votes.UnknownVoteCast):
        house_votes.parse_rollcall(data, 119, 1)


def test_speaker_election_is_non_position():
    # Majority vote for a candidate by surname → RollCall (counts) but no positions.
    data = _sample()
    mvblock = data["houseRollCallVoteMemberVotes"]
    mvblock["voteQuestion"] = "Election of the Speaker"
    mvblock["legislationType"] = ""
    mvblock["legislationNumber"] = ""
    for i, r in enumerate(mvblock["results"]):
        r["voteCast"] = "McCarthy" if i % 2 else "Jeffries"
    rc, mvs, absences = house_votes.parse_rollcall(data, 119, 1)
    assert rc.vote_class_rule == "non_position"
    assert rc.bill_id is None
    assert rc.party_totals is None  # candidate-surname tally has no yea/nay to split
    assert mvs == [] and absences == []
    # totals is the accurate raw candidate tally
    assert set(rc.totals) == {"McCarthy", "Jeffries"}
    assert sum(rc.totals.values()) == 430


def test_bill_id_none_when_no_legislation():
    data = _sample()
    mv = data["houseRollCallVoteMemberVotes"]
    mv["legislationType"] = ""
    mv["legislationNumber"] = ""
    rc, _, _ = house_votes.parse_rollcall(data, 119, 1)
    assert rc.bill_id is None


def test_rollcall_id_format():
    assert house_votes.rollcall_id("house", 118, 2, 7) == "h-118-2-0007"
    assert house_votes.rollcall_id("senate", 119, 1, 234) == "s-119-1-0234"


# --- clerk XML cross-check parser -----------------------------------------

def _rv(name_id: str, state: str, vote: str) -> str:
    return (
        f'<recorded-vote><legislator name-id="{name_id}" state="{state}" '
        f'party="X">Name</legislator><vote>{vote}</vote></recorded-vote>'
    )


CLERK_XML = (
    '<?xml version="1.0"?>\n<rollcall-vote><vote-metadata>'
    "<rollcall-num>240</rollcall-num></vote-metadata><vote-data>"
    + _rv("A000370", "NC", "Yea")
    + _rv("E000235", "MS", "Yea")
    + _rv("T000193", "MS", "Not Voting")
    + "</vote-data></rollcall-vote>"
)


def test_clerk_parse_positions_filters_state_and_maps():
    ms = clerk_house.parse_positions(CLERK_XML, state="MS")
    assert ms == {"E000235": "yea", "T000193": "not_voting"}
    all_states = clerk_house.parse_positions(CLERK_XML)
    assert all_states["A000370"] == "yea"


def test_clerk_maps_aye_no_variant():
    xml = CLERK_XML.replace("<vote>Yea</vote>", "<vote>Aye</vote>")
    assert clerk_house.parse_positions(xml, state="MS")["E000235"] == "yea"


# --- deterministic export -------------------------------------------------


def test_vote_export_deterministic(tmp_path):
    rc, mvs, _ = house_votes.parse_rollcall(_sample(), 119, 1)
    a = export_rollcall(rc, mvs, out_dir=tmp_path / "a")
    b = export_rollcall(rc, copy.deepcopy(mvs), out_dir=tmp_path / "b")
    assert a.read_bytes() == b.read_bytes()
    rec = json.loads(a.read_text(encoding="utf-8"))
    assert rec["rollcall"]["id"] == "h-119-1-0240"
    assert [mv["member_id"] for mv in rec["member_votes"]] == sorted(
        mv["member_id"] for mv in rec["member_votes"]
    )
    assert b"\r\n" not in a.read_bytes()  # LF only
