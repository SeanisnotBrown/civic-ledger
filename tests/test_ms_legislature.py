"""INC-12 phase 2 — Mississippi LegiScan ingest. Pure parsers + build driven by
inlined LegiScan-shaped records (no network): party mapping, district ordinals, the
MS vote classifier, per-roll tally cross-check, unknown-person guard, computed
party_totals, referenced-bills-only, and build determinism."""

from __future__ import annotations

import pytest

from ingest import ms_legislature as ms
from ingest.export import _dumps


def _person(pid, party, role, district, name="A Legislator"):
    return {"person": {"people_id": pid, "party": party, "role": role, "district": district,
                       "name": name, "votesmart_id": 10 + pid, "ballotpedia": "",
                       "opensecrets_id": "", "bioguide_id": ""}}


def _bill(bill_id, number, title, sponsors, subjects=(), url="https://legiscan.com/x",
          state_link="https://billstatus.ls.state.ms.us/2026/pdf/history/HB/HB0001.xml"):
    return {"bill": {"bill_id": bill_id, "bill_number": number, "title": title, "url": url,
                     "state_link": state_link,
                     "sponsors": [{"people_id": p, "sponsor_type_id": t} for p, t in sponsors],
                     "subjects": [{"subject_name": s} for s in subjects],
                     "history": [{"date": "2026-01-05", "action": "Referred To Committee"},
                                 {"date": "2026-01-08", "action": "Passed"}],
                     "status": 4, "status_date": "2026-03-17"}}


def _vote(rid, bill_id, desc, positions, chamber="H", passed=1):
    yea = sum(1 for _, t in positions if t == "Yea")
    nay = sum(1 for _, t in positions if t == "Nay")
    nv = sum(1 for _, t in positions if t == "NV")
    return {"roll_call": {"roll_call_id": rid, "bill_id": bill_id, "date": "2026-01-08",
                          "desc": desc, "yea": yea, "nay": nay, "nv": nv, "absent": 0,
                          "total": len(positions), "passed": passed, "chamber": chamber,
                          "votes": [{"people_id": p, "vote_id": 1, "vote_text": t}
                                    for p, t in positions]}}


# --- classifier -----------------------------------------------------------


@pytest.mark.parametrize("desc,expected", [
    ("House Passed", "passage"),
    ("Senate Passed As Amended", "passage"),
    ("Senate Adopted", "passage"),
    ("House Conference Report Adopted", "passage"),
    ("Senate Concurred in Amend From House", "passage"),
    ("House Failed", "passage"),
    ("House Veto Overridden", "veto_override"),
    ("Senate Veto Sustained", "veto_override"),
    ("Senate Tabled Failed", "procedural"),  # 'tabled' beats 'failed' (order)
])
def test_classify_ms(desc, expected):
    cls, rule = ms.classify_ms(desc)
    assert cls == expected and rule.startswith("MS-")


def test_classify_ms_unknown_is_other():
    assert ms.classify_ms("Some New Motion")[0] == "other"


# --- person ---------------------------------------------------------------


def test_parse_person_maps_role_district_and_ids():
    m = ms.parse_person(_person(6493, "D", "Rep", "HD-103", "Percy Watson"), 2026, 2026)
    assert m.id == "ms-6493" and m.chamber == "house" and m.district == 103
    assert m.party == "D" and m.jurisdiction == "ms" and m.state == "MS" and m.serving
    assert m.ids["legiscan"] == "6493" and m.ids["votesmart"] == "6503"
    assert m.terms[0].start == "2026-01-01" and m.terms[0].end == "2026-12-31"


def test_parse_person_senator_and_nonpartisan_mapping():
    sen = ms.parse_person(_person(700, "R", "Sen", "SD-047"), 2026, 2026)
    assert sen.chamber == "senate" and sen.district == 47
    nonpartisan = ms.parse_person(_person(26472, "N", "Rep", "HD-082"), 2026, 2026)
    assert nonpartisan.party == "I"  # N (nonpartisan) -> I, documented


# --- bill -----------------------------------------------------------------


def test_parse_bill_ids_sponsors_subjects():
    b = ms.parse_bill(_bill("2066078", "HB1", "An Act.", [(6493, 1), (700, 2), (701, 2)],
                            subjects=["Courts", "Judges"]), 2249)
    assert b.id == "ms-hb1-2249" and b.type == "hb" and b.number == 1 and b.congress is None
    assert b.sponsor_id == "ms-6493" and b.cosponsor_ids == ["ms-700", "ms-701"]
    assert b.subjects == ["Courts", "Judges"] and b.jurisdiction == "ms"
    assert b.source_url.startswith("https://billstatus.ls.state.ms.us")
    assert b.latest_action == "Passed" and b.latest_action_date == "2026-01-08"


# --- roll call ------------------------------------------------------------


def _people_index():
    people = [_person(1, "R", "Rep", "HD-001"), _person(2, "D", "Rep", "HD-002"),
              _person(3, "I", "Rep", "HD-003")]
    members = [ms.parse_person(p, 2026, 2026) for p in people]
    return {int(p["person"]["people_id"]): m for p, m in zip(people, members, strict=True)}


def test_parse_rollcall_positions_party_totals_and_bill():
    idx = _people_index()
    vote = _vote(1612732, "2066078", "House Passed As Amended",
                 [(1, "Yea"), (2, "Nay"), (3, "NV")])
    rc, mvs = ms.parse_rollcall(vote, 2249, idx, {"2066078": "HB1"})
    assert rc.id == "ms-h-2249-1612732" and rc.bill_id == "ms-hb1-2249"
    assert rc.vote_class == "passage" and rc.congress is None and rc.session == 2249
    assert rc.totals == {"yea": 1, "nay": 1, "present": 0, "not_voting": 1}
    assert rc.party_totals["R"]["yea"] == 1 and rc.party_totals["D"]["nay"] == 1
    assert rc.party_totals["I"]["not_voting"] == 1
    assert rc.source_url == "https://legiscan.com/MS/rollcall/HB1/id/1612732"
    assert [mv.member_id for mv in mvs] == ["ms-1", "ms-2", "ms-3"]


def test_parse_rollcall_tally_mismatch_raises():
    idx = _people_index()
    vote = _vote(9, "2066078", "House Passed", [(1, "Yea"), (2, "Nay")])
    vote["roll_call"]["yea"] = 5  # header lies about the count
    with pytest.raises(ms.TallyMismatch):
        ms.parse_rollcall(vote, 2249, idx, {"2066078": "HB1"})


def test_parse_rollcall_unknown_person_raises():
    idx = _people_index()
    vote = _vote(9, "2066078", "House Passed", [(1, "Yea"), (999, "Yea")])
    with pytest.raises(ms.UnknownPerson):
        ms.parse_rollcall(vote, 2249, idx, {"2066078": "HB1"})


# --- build ----------------------------------------------------------------


def test_build_records_end_to_end_and_referenced_bills_only():
    people = [_person(1, "R", "Rep", "HD-001"), _person(2, "D", "Rep", "HD-002")]
    bills = [_bill("100", "HB1", "Bill one.", [(1, 1)]),
             _bill("200", "HB2", "Bill two.", [(2, 1)]),
             _bill("300", "HB3", "Never voted.", [(1, 1)])]  # not referenced by any roll
    votes = [_vote(11, "100", "House Passed", [(1, "Yea"), (2, "Nay")]),
             _vote(12, "200", "House Passed", [(1, "Yea"), (2, "Yea")])]
    r = ms.build_records(2249, 2026, 2026, people, bills, votes)
    assert len(r.members) == 2 and len(r.rollcalls) == 2
    assert {b.id for b in r.bills} == {"ms-hb1-2249", "ms-hb2-2249"}  # HB3 excluded
    assert r.quarantined == []
    assert r.crosswalk["ms-1"]["legiscan_people_id"] == 1


def test_build_records_quarantines_bad_roll_not_the_session():
    people = [_person(1, "R", "Rep", "HD-001")]
    bills = [_bill("100", "HB1", "Bill.", [(1, 1)])]
    good = _vote(11, "100", "House Passed", [(1, "Yea")])
    bad = _vote(12, "100", "House Passed", [(1, "Yea"), (999, "Yea")])  # unknown person
    r = ms.build_records(2249, 2026, 2026, people, bills, [good, bad])
    assert len(r.rollcalls) == 1  # good one survives
    assert any("roll:12" in q for q in r.quarantined)


def test_run_is_a_noop_when_dataset_hash_unchanged(monkeypatch, tmp_path):
    # The nightly gate (D55): matching committed hash -> no fetch, no rewrite, exit 0.
    monkeypatch.setattr(ms.legiscan, "available", lambda: True)
    monkeypatch.setattr(ms, "current_session",
                        lambda *a, **k: {"session_id": 2249, "dataset_hash": "SAME"})
    monkeypatch.setattr(ms, "_committed_dataset_hash", lambda: "SAME")
    monkeypatch.setattr(ms, "MS_VOTES_DIR", tmp_path)  # exists() is True
    monkeypatch.setattr(ms, "fetch_dataset",
                        lambda *a, **k: pytest.fail("must not fetch when hash unchanged"))
    assert ms.run([]) == 0


def _bill_hist(bill_id, number, sponsors, actions):
    b = _bill(bill_id, number, "A bill.", sponsors)
    b["bill"]["history"] = [{"date": "2026-01-05", "action": a} for a in actions]
    return b


def test_leg_item_detects_gubernatorial_approval():
    signed = _bill_hist("100", "HB1", [(1, 1)], ["Referred", "Approved by Governor"])
    li = ms._leg_item(signed, 2249)
    assert li.became_law is True and li.enacted_action == "Approved by Governor"
    assert li.bill_id == "ms-hb1-2249" and li.congress is None
    died = _bill_hist("101", "HB2", [(1, 1)], ["Referred", "Died In Committee"])
    assert ms._leg_item(died, 2249).became_law is False


def test_build_legislation_principal_vs_coauthors():
    members = [ms.parse_person(_person(1, "R", "Rep", "HD-001"), 2026, 2026),
               ms.parse_person(_person(2, "D", "Rep", "HD-002"), 2026, 2026)]
    # Bill A: member 1 principal (first), member 2 co-author. Bill B: member 2 principal.
    bills = [_bill_hist("100", "HB1", [(1, 1), (2, 1)], ["Approved by Governor"]),
             _bill_hist("200", "HB2", [(2, 1)], ["Died"])]
    leg = {m.member_id: m for m in ms.build_legislation(members, bills, 2249)}
    assert [li.bill_id for li in leg["ms-1"].sponsored] == ["ms-hb1-2249"]
    assert [li.bill_id for li in leg["ms-1"].cosponsored] == []
    assert [li.bill_id for li in leg["ms-2"].sponsored] == ["ms-hb2-2249"]
    assert [li.bill_id for li in leg["ms-2"].cosponsored] == ["ms-hb1-2249"]
    # The principal's authored bill is enacted; enacted_rate can see it.
    assert leg["ms-1"].sponsored[0].became_law is True


def test_build_records_is_deterministic():
    people = [_person(2, "D", "Rep", "HD-002"), _person(1, "R", "Rep", "HD-001")]
    bills = [_bill("100", "HB1", "Bill.", [(1, 1), (2, 2)])]
    votes = [_vote(11, "100", "House Passed", [(2, "Yea"), (1, "Nay")])]
    a = ms.build_records(2249, 2026, 2026, people, bills, votes)
    b = ms.build_records(2249, 2026, 2026, people, bills, votes)
    assert _dumps(a.crosswalk) == _dumps(b.crosswalk)
    dump = lambda recs: [_dumps(m.model_dump()) for m in recs]  # noqa: E731
    assert dump(a.members) == dump(b.members)
    assert _dumps(a.rollcalls[0][0].model_dump()) == _dumps(b.rollcalls[0][0].model_dump())
