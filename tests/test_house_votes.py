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


def test_parse_rollcall_totals_and_all_voting_state_votes():
    # V2-1 (D60): every voting-state member's position is persisted, not just MS's.
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
    # All 430 results become positions — this fixture's real roll has no delegates.
    assert len(mvs) == 430
    assert sum(1 for mv in mvs if mv.position == "not_voting") == 32
    # The 4 MS House members are among them, all Yea on this roll.
    ms = {"E000235", "G000591", "K000388", "T000193"}
    assert ms <= {mv.member_id for mv in mvs}
    assert all(mv.position == "yea" for mv in mvs if mv.member_id in ms)
    assert len(absences) == 32  # one stub per not_voting result, matching totals


def test_non_voting_delegate_included_in_positions():
    # D61: a non-voting House delegate's result IS persisted when the source
    # includes it (delegates vote in Committee of the Whole); coverage
    # EXPECTATIONS, not what gets recorded, is where D61 excludes them
    # (ingest/coverage.py:expected_on, exercised in test_coverage.py).
    data = _sample()
    data["houseRollCallVoteMemberVotes"]["results"].append(
        {"bioguideID": "N000147", "voteState": "DC", "voteCast": "Yea", "voteParty": "D",
         "congress": 119}
    )
    rc, mvs, _ = house_votes.parse_rollcall(data, 119, 1)
    assert "N000147" in {mv.member_id for mv in mvs}
    assert len(mvs) == 431  # the delegate result is now recorded like any other


def test_not_voting_seeds_absence_stub():
    data = _sample()
    # Flip one MS member to "Not Voting".
    for r in data["houseRollCallVoteMemberVotes"]["results"]:
        if r["bioguideID"] == "G000591":
            r["voteCast"] = "Not Voting"
    rc, mvs, absences = house_votes.parse_rollcall(data, 119, 1)
    guest = next(mv for mv in mvs if mv.member_id == "G000591")
    assert guest.position == "not_voting"
    assert len(absences) == 33  # 32 already not_voting on this roll + G000591
    guest_absence = next(a for a in absences if a.member_id == "G000591")
    assert guest_absence.rollcall_id == "h-119-1-0240"
    assert guest_absence.stated_reason is None


def test_aye_no_map_to_yea_nay():
    # "Recorded Vote" ballots (Committee of the Whole) use Aye/No, not Yea/Nay.
    data = _sample()
    results = data["houseRollCallVoteMemberVotes"]["results"]
    for r in results:
        if r["voteCast"] == "Yea":
            r["voteCast"] = "Aye"
    rc, mvs, _ = house_votes.parse_rollcall(data, 119, 1)
    assert rc.totals["yea"] == 397  # Aye counted as yea
    assert sum(1 for mv in mvs if mv.position == "yea") == 397
    # The 4 MS House members, previously asserted all-Yea, still map to yea via Aye.
    ms = {"E000235", "G000591", "K000388", "T000193"}
    assert all(mv.position == "yea" for mv in mvs if mv.member_id in ms)


def test_lone_bad_cast_raises_not_non_position():
    # A single unmappable cast among 430 is a data glitch → quarantine, NOT a
    # silently-dropped roll (the majority rule protects real votes).
    data = _sample()
    data["houseRollCallVoteMemberVotes"]["results"][0]["voteCast"] = "Maybe"
    with pytest.raises(house_votes.UnknownVoteCast):
        house_votes.parse_rollcall(data, 119, 1)


MS_ON_SAMPLE = {"E000235", "G000591", "K000388", "T000193"}
ALL_ON_SAMPLE = {
    r["bioguideID"] for r in _sample()["houseRollCallVoteMemberVotes"]["results"]
}


def test_unknown_member_raises_when_roster_stale():
    # R-2/D60: a new member appears in the roll but not the (date-windowed) covered
    # set the roster hasn't caught up to) → raise, so the ingest quarantines + fails
    # loudly instead of exporting an orphan (votes on file, no page/metrics — value #2).
    data = _sample()
    data["houseRollCallVoteMemberVotes"]["results"].append(
        {"bioguideID": "X000999", "voteState": "MS", "voteCast": "Yea", "voteParty": "R",
         "congress": 119}
    )
    with pytest.raises(house_votes.UnknownMember) as exc:
        house_votes.parse_rollcall(data, 119, 1, covered=ALL_ON_SAMPLE)
    assert "X000999" in str(exc.value)


def test_covered_set_matching_roster_does_not_raise():
    # The steady state: every voter on the roll is rostered → no churn alarm.
    rc, mvs, _ = house_votes.parse_rollcall(_sample(), 119, 1, covered=ALL_ON_SAMPLE)
    assert {mv.member_id for mv in mvs} == ALL_ON_SAMPLE


def test_covered_none_skips_churn_check():
    # Backfill / unit-test path passes no covered set → the check is inert.
    data = _sample()
    data["houseRollCallVoteMemberVotes"]["results"].append(
        {"bioguideID": "X000999", "voteState": "MS", "voteCast": "Yea", "voteParty": "R",
         "congress": 119}
    )
    rc, mvs, _ = house_votes.parse_rollcall(data, 119, 1)  # covered defaults to None
    assert "X000999" in {mv.member_id for mv in mvs}


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


# --- accepted-quarantine accept-list (§6.1) -------------------------------


def test_accepted_quarantines_missing_file_is_empty(tmp_path):
    # No accept-list file → nothing is accepted (every quarantine stays fatal).
    from ingest import incremental
    assert incremental.accepted_quarantines(root=tmp_path) == {}


def test_accepted_quarantines_loads_ids_and_reasons(tmp_path):
    from ingest import incremental
    qdir = tmp_path / "data" / "quality"
    qdir.mkdir(parents=True)
    (qdir / "accepted-quarantine.yaml").write_text(
        'h-119-2-0130: "voter S001157 outside their roster term window"\n',
        encoding="utf-8",
    )
    accepted = incremental.accepted_quarantines(root=tmp_path)
    assert accepted == {"h-119-2-0130": "voter S001157 outside their roster term window"}


def test_accept_list_partitions_known_from_new():
    # The run() decision, unit-tested without network: a quarantined id on the
    # accept-list is non-fatal; an unlisted id fails the run (preserves the alarm).
    accepted_ids = {"h-119-2-0130"}
    ms_failures: list[str] = []
    accepted: list[str] = []
    for rc_id in ("h-119-2-0130", "h-999-9-9999"):  # one known, one new
        (accepted if rc_id in accepted_ids else ms_failures).append(rc_id)
    assert accepted == ["h-119-2-0130"]      # known → not a failure
    assert ms_failures == ["h-999-9-9999"]   # new → still fatal
    assert bool(ms_failures) is True         # run() would return 1


def test_committed_accept_list_matches_committed_quarantines():
    # Guard: every id on the accept-list has a real quarantine record, and every
    # committed quarantine is accounted for — so the list can't silently drift.
    from ingest import incremental
    accepted = incremental.accepted_quarantines()
    qdir = repo_root() / "data" / "quality" / "quarantine"
    on_disk = {p.stem for p in qdir.glob("*.json")}
    assert set(accepted) == on_disk


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
