"""INC-2 tests — §5 schema layer + congress-legislators → Member parsing +
deterministic member export. Offline: parses the committed MS sample, never the
network.
"""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from ingest import config
from ingest.cache import repo_root
from ingest.export import export_members
from ingest.models import Absence, Member, Term
from ingest.sources import legislators

SAMPLE = repo_root() / "data" / "quality" / "samples" / "legislators_current_ms.yaml"

MS_BIOGUIDES = {"W000437", "T000193", "K000388", "H001079", "G000591", "E000235"}


def _raw() -> list[dict]:
    return yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))


def _members() -> list[Member]:
    return legislators.covered_members(_raw(), config.CONGRESSES)


# --- schema validation ----------------------------------------------------


def test_member_valid_minimal():
    m = Member(
        id="X000001",
        ids={"govtrack": "1"},
        name="Test Member",
        party="R",
        state="MS",
        district=1,
        chamber="house",
        serving=True,
        terms=[Term(start="2023-01-03", end="2025-01-03", party="R", chamber="house")],
    )
    assert m.party == "R"


def test_member_rejects_unmapped_party():
    with pytest.raises(ValidationError):
        Member(
            id="X",
            ids={},
            name="N",
            party="Whig",  # not D/R/I
            state="MS",
            district=None,
            chamber="senate",
            serving=True,
            terms=[],
        )


def test_member_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Member(
            id="X",
            ids={},
            name="N",
            party="R",
            state="MS",
            district=1,
            chamber="house",
            serving=True,
            terms=[],
            bogus="drift",  # extra="forbid" must reject
        )


def test_party_switch_preserved_in_terms():
    # No MS member switched party; synthesize one to prove the history is kept
    # verbatim and the top-level party tracks the most recent term.
    entry = {
        "id": {"bioguide": "Z999999", "govtrack": 5},
        "name": {"first": "Party", "last": "Switcher", "official_full": "Party Switcher"},
        "terms": [
            {"start": "2021-01-03", "end": "2023-01-03", "party": "Democrat",
             "state": "MS", "type": "rep", "district": 2},
            {"start": "2023-01-03", "end": "2025-01-03", "party": "Republican",
             "state": "MS", "type": "rep", "district": 2},
        ],
    }
    (member,) = legislators.covered_members([entry], config.CONGRESSES)
    assert [t.party for t in member.terms] == ["D", "R"]  # both preserved, in order
    assert member.party == "R"  # current = latest term


def test_absence_reason_requires_source():
    Absence(member_id="m", rollcall_id="r")  # no reason → fine
    with pytest.raises(ValidationError):
        Absence(member_id="m", rollcall_id="r", stated_reason="was in district")


# --- parsing the covered MS delegation ------------------------------------


def test_covered_set_is_the_six_ms_members():
    members = _members()
    assert len(members) == 6
    assert {m.id for m in members} == MS_BIOGUIDES


def test_member_field_mapping():
    by_id = {m.id: m for m in _members()}

    wicker = by_id["W000437"]  # senior senator
    assert wicker.chamber == "senate"
    assert wicker.district is None
    assert wicker.party == "R"
    assert wicker.serving is True
    assert wicker.ids["lis"] == "S318"
    assert wicker.ids["fec"] == "H4MS01078,S8MS00196"  # list → comma-joined (D20)

    thompson = by_id["T000193"]  # the lone Democrat
    assert thompson.party == "D"
    assert thompson.chamber == "house"

    kelly = by_id["K000388"]  # district 1
    assert kelly.district == 1
    assert kelly.chamber == "house"


def test_wicker_early_house_term_not_marked_119():
    # Wicker's 1995 House term must not overlap the 119th Congress window.
    assert legislators._term_overlaps(
        {"start": "1995-01-04", "end": "1997-01-03"}, 119
    ) is False
    assert legislators._term_overlaps(
        {"start": "2025-01-03", "end": "2031-01-03"}, 119
    ) is True


def test_terms_sorted_by_start():
    wicker = {m.id: m for m in _members()}["W000437"]
    starts = [t.start for t in wicker.terms]
    assert starts == sorted(starts)


# --- V2-1: voting-state filter + current/historical merge ------------------


def _delegate_entry(state: str) -> dict:
    return {
        "id": {"bioguide": "D999999", "govtrack": 9},
        "name": {"first": "Non", "last": "Voting", "official_full": "Non Voting"},
        "terms": [
            {"start": "2023-01-03", "end": "2025-01-03", "party": "Democrat",
             "state": state, "type": "rep", "district": 0},
        ],
    }


@pytest.mark.parametrize("state", ["DC", "PR", "GU", "AS", "VI", "MP"])
def test_non_voting_delegate_included_in_roster(state):
    # D61 (supersedes D60): delegates ARE covered members — excluding them broke
    # full recomputability (they cast real votes on ~1/3 of House rolls). The
    # roster is state-agnostic now; delegate detection moves to ingest/coverage.py.
    (member,) = legislators.covered_members([_delegate_entry(state)], config.CONGRESSES)
    assert member.state == state


def test_voting_state_included():
    assert len(legislators.covered_members([_delegate_entry("MS")], config.CONGRESSES)) == 1


def test_merge_raw_unions_and_prefers_current_on_collision():
    current_entry = {"id": {"bioguide": "X1"}, "name": {}, "flag": "current"}
    historical_entry = {"id": {"bioguide": "X1"}, "name": {}, "flag": "historical"}
    only_historical = {"id": {"bioguide": "X2"}, "name": {}, "flag": "historical"}
    merged = legislators.merge_raw([current_entry], [historical_entry, only_historical])
    by_id = {e["id"]["bioguide"]: e for e in merged}
    assert by_id["X1"]["flag"] == "current"  # collision: current wins
    assert by_id["X2"]["flag"] == "historical"  # historical-only entry preserved
    assert len(merged) == 2


# --- deterministic export -------------------------------------------------


def test_export_writes_six_files(tmp_path):
    paths = export_members(_members(), out_dir=tmp_path)
    assert len(paths) == 6
    assert {p.stem for p in paths} == MS_BIOGUIDES


def test_double_export_byte_identical(tmp_path):
    members = _members()
    dir_a, dir_b = tmp_path / "a", tmp_path / "b"
    export_members(members, out_dir=dir_a)
    export_members(members, out_dir=dir_b)
    for bioguide in MS_BIOGUIDES:
        a = (dir_a / f"{bioguide}.json").read_bytes()
        b = (dir_b / f"{bioguide}.json").read_bytes()
        assert a == b, f"{bioguide} export is non-deterministic"


def test_export_is_lf_and_sorted_keys(tmp_path):
    (path,) = [p for p in export_members(_members(), out_dir=tmp_path) if p.stem == "W000437"]
    raw = path.read_bytes()
    assert b"\r\n" not in raw  # LF only (§6.3 / .gitattributes)
    assert raw.endswith(b"\n")
    obj = yaml.safe_load(path.read_text(encoding="utf-8"))  # JSON is valid YAML
    # top-level keys are alphabetically sorted
    text = path.read_text(encoding="utf-8")
    keys = [line.strip().split('"')[1] for line in text.splitlines() if line.startswith("  \"")]
    assert keys == sorted(keys)
    assert obj["id"] == "W000437"
