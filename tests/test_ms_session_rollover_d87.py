"""D87 — Mississippi session rollover (2026-09-30 surgical review, finding 1).

`current_session()` follows the newest regular session with no config change, so when
LegiScan publishes the 2027 session the nightly ingests it automatically. The owner
ratified (2026-09-30) that a Mississippi grade is a CAREER grade spanning every ingested
session — matching the federal side, which already spans the 118th and 119th Congresses.

That only holds if nothing is silently replaced. Before D87 a rollover would have:
  * replaced a continuing legislator's member file with a 2027-only term list,
  * left a departed legislator frozen at `serving: true` forever,
  * dropped every 2026 bill from a member's legislation record (lowering their
    sponsored / cosponsored / enacted numbers),
  * dropped departed legislators from the crosswalk, and
  * written a manifest whose counts described 2027 while the pages showed both.

These tests drive two sessions through the real export into a tmp partition.
"""

from __future__ import annotations

import json

import pytest

from ingest import ms_legislature as ms
from ingest.models import LegItem, Member, MemberLegislation, Term


def _person(pid, party, role, district, name="A Legislator"):
    return {"person": {"people_id": pid, "party": party, "role": role, "district": district,
                       "name": name, "votesmart_id": 10 + pid, "ballotpedia": "",
                       "opensecrets_id": "", "bioguide_id": ""}}


def _bill(bill_id, number, title, sponsors, year=2026):
    return {"bill": {"bill_id": bill_id, "bill_number": number, "title": title,
                     "url": "https://legiscan.com/x",
                     "state_link": f"https://billstatus.ls.state.ms.us/{year}/x.xml",
                     "sponsors": [{"people_id": p, "sponsor_type_id": t} for p, t in sponsors],
                     "subjects": [],
                     "history": [{"date": f"{year}-01-08", "action": "Passed"}],
                     "status": 4, "status_date": f"{year}-03-17"}}


def _vote(rid, bill_id, desc, positions, chamber="H", year=2026):
    yea = sum(1 for _, t in positions if t == "Yea")
    nay = sum(1 for _, t in positions if t == "Nay")
    nv = sum(1 for _, t in positions if t == "NV")
    return {"roll_call": {"roll_call_id": rid, "bill_id": bill_id, "date": f"{year}-01-08",
                          "desc": desc, "yea": yea, "nay": nay, "nv": nv, "absent": 0,
                          "total": len(positions), "passed": 1, "chamber": chamber,
                          "votes": [{"people_id": p, "vote_id": 1, "vote_text": t}
                                    for p, t in positions]}}


@pytest.fixture
def partition(tmp_path, monkeypatch):
    """Point every MS export path at a tmp partition."""
    from ingest import export

    ms_dir = tmp_path / "data" / "state" / "ms"
    paths = {
        "MS_DIR": ms_dir,
        "MS_MEMBERS_DIR": ms_dir / "members",
        "MS_VOTES_DIR": ms_dir / "votes",
        "MS_BILLS_DIR": ms_dir / "bills",
        "MS_LEGISLATION_DIR": ms_dir / "legislation",
        "MS_MANIFEST_PATH": ms_dir / "manifest.json",
    }
    for name, value in paths.items():
        monkeypatch.setattr(export, name, value, raising=False)
    for name in ("MS_MEMBERS_DIR", "MS_VOTES_DIR", "MS_BILLS_DIR"):
        monkeypatch.setattr(ms, name, paths[name])
    return paths


def _session(sid, y):
    return {"session_id": sid, "session_name": f"{y} Regular Session",
            "dataset_hash": f"hash{sid}", "year_start": y, "year_end": y}


def _export_session(sid, year, people, bills, votes, partition):
    result = ms.build_records(sid, year, year, people, bills, votes)
    departed = ms._export_records(result)
    manifest = ms.build_ms_manifest(
        _session(sid, year), ms.disk_counts(),
        ms.merge_sessions(ms._read_json(partition["MS_MANIFEST_PATH"]), _session(sid, year)),
        "2026-09-30T00:00:00Z", "deadbeef",
    )
    ms._export_manifest(manifest)
    return result, departed, manifest


# Person 1 serves both sessions; person 2 leaves after 2026; person 3 arrives in 2027.
_P1, _P2, _P3 = 1, 2, 3


def _run_both(partition):
    s1 = _export_session(
        2249, 2026,
        [_person(_P1, "R", "Rep", "HD-001"), _person(_P2, "D", "Rep", "HD-002")],
        [_bill("100", "HB1", "Bill one.", [(_P1, 1), (_P2, 1)], 2026)],
        [_vote(11, "100", "House Passed", [(_P1, "Yea"), (_P2, "Nay")], year=2026)],
        partition,
    )
    s2 = _export_session(
        2400, 2027,
        [_person(_P1, "R", "Rep", "HD-001"), _person(_P3, "D", "Rep", "HD-003")],
        [_bill("200", "HB7", "Bill two.", [(_P1, 1), (_P3, 1)], 2027)],
        [_vote(22, "200", "House Passed", [(_P1, "Yea"), (_P3, "Yea")], year=2027)],
        partition,
    )
    return s1, s2


def test_earlier_session_votes_and_bills_survive_the_rollover(partition):
    """The career-grade contract: 2026 roll calls and bills stay on disk."""
    _run_both(partition)
    votes = {p.stem for p in partition["MS_VOTES_DIR"].glob("*.json")}
    bills = {p.stem for p in partition["MS_BILLS_DIR"].glob("*.json")}
    assert votes == {"ms-h-2249-11", "ms-h-2400-22"}
    assert bills == {"ms-hb1-2249", "ms-hb7-2400"}


def test_continuing_legislator_keeps_both_terms(partition):
    """Member files are keyed by people_id, so a plain overwrite would leave a
    legislator with a 2027-only term while their 2026 votes still counted."""
    _run_both(partition)
    rec = json.loads((partition["MS_MEMBERS_DIR"] / "ms-1.json").read_text(encoding="utf-8"))
    assert [(t["start"], t["end"]) for t in rec["terms"]] == [
        ("2026-01-01", "2026-12-31"), ("2027-01-01", "2027-12-31")]
    assert rec["serving"] is True


def test_departed_legislator_is_marked_not_serving_but_kept(partition):
    """Their 2026 votes stay, so their record must stay — with `serving` telling the
    truth instead of being frozen at the value the 2026 roster set."""
    _, (_, departed, _) = _run_both(partition)
    rec = json.loads((partition["MS_MEMBERS_DIR"] / "ms-2.json").read_text(encoding="utf-8"))
    assert rec["serving"] is False
    assert departed == ["ms-2"]
    # The newcomer and the continuing member are untouched.
    for mid in ("ms-1", "ms-3"):
        kept = json.loads((partition["MS_MEMBERS_DIR"] / f"{mid}.json").read_text(encoding="utf-8"))
        assert kept["serving"] is True


def test_legislation_record_keeps_the_earlier_session(partition):
    """Legislation files are keyed by member, NOT by session — the one place where a
    rollover would silently lower a published sponsorship number."""
    _run_both(partition)
    rec = json.loads(
        (partition["MS_LEGISLATION_DIR"] / "ms-1.json").read_text(encoding="utf-8"))
    assert [i["bill_id"] for i in rec["sponsored"]] == ["ms-hb1-2249", "ms-hb7-2400"]


def test_crosswalk_keeps_departed_members(partition):
    _run_both(partition)
    xwalk = json.loads(
        (partition["MS_DIR"] / "crosswalk.json").read_text(encoding="utf-8"))
    assert sorted(xwalk) == ["ms-1", "ms-2", "ms-3"]


def test_manifest_counts_the_whole_partition_and_lists_both_sessions(partition):
    """The manifest used to count only the session just built."""
    _, (_, _, manifest) = _run_both(partition)
    assert manifest["session_id"] == 2400  # the CURRENT session drives the change gate
    assert manifest["dataset_hash"] == "hash2400"
    assert [r["session_id"] for r in manifest["sessions"]] == [2400, 2249]
    assert manifest["counts"]["rollcalls"] == 2
    assert manifest["counts"]["bills"] == 2
    assert manifest["counts"]["members"] == 3  # incl. the departed one
    assert manifest["counts"]["member_votes"] == 4


def test_single_session_export_is_unchanged_by_the_merge(partition):
    """Acceptance guard: with one session on disk every merge must dedup to exactly
    what a plain overwrite wrote — otherwise this change would rewrite committed data."""
    people = [_person(_P1, "R", "Rep", "HD-001"), _person(_P2, "D", "Rep", "HD-002")]
    bills = [_bill("100", "HB1", "Bill one.", [(_P1, 1), (_P2, 1)], 2026)]
    votes = [_vote(11, "100", "House Passed", [(_P1, "Yea"), (_P2, "Nay")], year=2026)]

    _export_session(2249, 2026, people, bills, votes, partition)
    first = {p.relative_to(partition["MS_DIR"]).as_posix(): p.read_bytes()
             for p in sorted(partition["MS_DIR"].rglob("*.json"))}
    _export_session(2249, 2026, people, bills, votes, partition)  # same session again
    second = {p.relative_to(partition["MS_DIR"]).as_posix(): p.read_bytes()
              for p in sorted(partition["MS_DIR"].rglob("*.json"))}
    assert first == second


# --- the pure merge helpers -----------------------------------------------


def _member(terms, serving=True):
    return Member(id="ms-1", ids={"legiscan": "1"}, name="A", party="R", state="MS",
                  district=1, chamber="house", jurisdiction="ms", serving=serving,
                  terms=terms)


def test_merge_member_dedups_and_sorts_terms():
    t26 = Term(start="2026-01-01", end="2026-12-31", party="R", chamber="house")
    t27 = Term(start="2027-01-01", end="2027-12-31", party="R", chamber="house")
    prior = _member([t26]).model_dump()
    assert ms.merge_member(prior, _member([t27])).terms == [t26, t27]
    assert ms.merge_member(prior, _member([t26])).terms == [t26]  # idempotent
    assert ms.merge_member(None, _member([t27])).terms == [t27]


def test_merge_legislation_unions_on_bill_id():
    def item(bid):
        return LegItem(bill_id=bid, congress=None, title="t", became_law=False,
                       introduced_date="2026-01-05",
                       source_url="https://legiscan.com/MS")

    prior = MemberLegislation(member_id="ms-1", sponsored=[item("ms-hb1-2249")],
                              cosponsored=[], source_url="https://legiscan.com/MS").model_dump()
    fresh = MemberLegislation(member_id="ms-1", sponsored=[item("ms-hb7-2400")],
                              cosponsored=[], source_url="https://legiscan.com/MS")
    merged = ms.merge_legislation(prior, fresh)
    assert [i.bill_id for i in merged.sponsored] == ["ms-hb1-2249", "ms-hb7-2400"]
    assert ms.merge_legislation(None, fresh).sponsored == fresh.sponsored


def test_merge_sessions_is_newest_first_and_idempotent():
    s1, s2 = _session(2249, 2026), _session(2400, 2027)
    first = ms.merge_sessions(None, s1)
    assert [r["session_id"] for r in first] == [2249]
    second = ms.merge_sessions({"sessions": first}, s2)
    assert [r["session_id"] for r in second] == [2400, 2249]
    assert ms.merge_sessions({"sessions": second}, s2) == second
