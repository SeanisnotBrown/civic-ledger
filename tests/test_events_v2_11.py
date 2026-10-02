"""V2-11 task 5 — the events projection (`ingest/events.py`) and invariant 8.

Three things these tests exist to pin, in order of how much damage getting them
wrong would do:

1. **Determinism.** The month files are a published artifact re-derived by
   `verify-recompute`, so a wall-clock, an unstable sort or a dict-order
   dependency would make the nightly commit a diff on a quiet day.
2. **No silent collapse.** D88's lesson: several real actions can share a date,
   a text and an action code and differ only in `committees`. A narrower event id
   publishes one event where the government recorded five.
3. **`has_page` matches what the site actually builds.** SD-33 3(c): only a bill
   that reached a recorded vote gets a `/b/` page, and a wrong answer here sends a
   subscriber to a URL that does not exist.

Everything here runs against fixtures in `tmp_path`, never `data/` — the V2-11
backfill may be mid-chunk while the suite runs, and a test that read the real
`data/bills/` would be reading a directory that is growing under it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest import events
from ingest.export import _dumps


# --- fixtures ----------------------------------------------------------------
def _action(**over) -> dict:
    base = dict(
        date="2026-03-04", time=None, text="Introduced in House.", type="IntroReferral",
        action_code="Intro-H", source_system="House", committees=None, rollcall_id=None,
    )
    base.update(over)
    return base


def _bill(bill_id="hr1-119", *, actions=None, **over) -> dict:
    base = dict(
        id=bill_id, jurisdiction="us", congress=119, type="hr", number=1,
        title_official="A Bill", policy_area="Health", subjects=["Health care costs"],
        sponsor_id="A000001", cosponsor_ids=[], actions=actions,
        latest_action="Referred.", latest_action_date="2026-03-04", cbo_estimates=[],
        source_url="https://www.congress.gov/bill/119/hr/1",
    )
    base.update(over)
    return base


def _dataset(tmp_path: Path, bills: list[dict], voted: list[str] | None = None) -> Path:
    data = tmp_path / "data"
    (data / "bills").mkdir(parents=True)
    for b in bills:
        (data / "bills" / f"{b['id']}.json").write_text(json.dumps(b), encoding="utf-8")
    (data / "votes").mkdir(parents=True)
    for n, bill_id in enumerate(voted or [], 1):
        (data / "votes" / f"h-119-1-{n:04d}.json").write_text(
            json.dumps({"rollcall": {"id": f"h-119-1-{n:04d}", "bill_id": bill_id},
                        "member_votes": []}),
            encoding="utf-8",
        )
    return data


# --- the D27 sentinel --------------------------------------------------------
def test_a_bill_with_no_timeline_yet_contributes_nothing(tmp_path: Path) -> None:
    """`actions is None` = NOT YET COLLECTED (D27). 1,040 bills are in that state
    until the backfill finishes, and none of them is an error."""
    assert events.compute(_dataset(tmp_path, [_bill(actions=None)])) == {}


def test_a_bill_the_government_lists_no_actions_for_contributes_nothing(tmp_path: Path) -> None:
    """`actions == []` = collected, and there are none. Also not an error, and
    must not be confused with the None case above."""
    assert events.compute(_dataset(tmp_path, [_bill(actions=[])])) == {}


def test_no_bills_directory_is_a_no_op(tmp_path: Path) -> None:
    assert events.compute(tmp_path / "data") == {}


# --- the projection ----------------------------------------------------------
def test_one_action_becomes_one_event_in_its_own_month(tmp_path: Path) -> None:
    data = _dataset(tmp_path, [_bill(actions=[_action(date="2026-03-04")])])
    out = events.compute(data)
    assert list(out) == ["2026-03"]
    assert out["2026-03"].count == 1
    e = out["2026-03"].events[0]
    assert (e.bill_id, e.date, e.text, e.type) == (
        "hr1-119", "2026-03-04", "Introduced in House.", "IntroReferral"
    )


def test_the_month_file_is_keyed_by_the_ACTION_date_not_the_bill(tmp_path: Path) -> None:
    """A bill introduced in 2023 and voted in 2026 appears in both months. The
    alternative — filing every action under the bill's own date — would mean an
    alert for today's floor vote never lands in this month's feed."""
    data = _dataset(tmp_path, [_bill(actions=[
        _action(date="2023-01-09", text="Introduced in House."),
        _action(date="2026-03-04", text="Passed House."),
    ])])
    out = events.compute(data)
    assert sorted(out) == ["2023-01", "2026-03"]
    assert [f.count for f in out.values()] == [1, 1]


def test_policy_area_and_subjects_are_denormalised_verbatim(tmp_path: Path) -> None:
    """A consumer filters a month by topic without loading 38,756 bill files."""
    data = _dataset(tmp_path, [_bill(
        policy_area="Armed Forces and National Security",
        subjects=["Military readiness", "Veterans' pensions"],
        actions=[_action()],
    )])
    e = events.compute(data)["2026-03"].events[0]
    assert e.policy_area == "Armed Forces and National Security"
    assert e.subjects == ["Military readiness", "Veterans' pensions"]


def test_a_bill_with_no_policy_area_yields_a_null_not_a_guess(tmp_path: Path) -> None:
    """D5: policy areas are government-assigned and never invented."""
    e = events.compute(
        _dataset(tmp_path, [_bill(policy_area=None, subjects=None, actions=[_action()])])
    )["2026-03"].events[0]
    assert e.policy_area is None and e.subjects is None


def test_committees_and_rollcall_id_travel_with_the_event(tmp_path: Path) -> None:
    data = _dataset(tmp_path, [_bill(actions=[_action(
        committees=["Armed Services Committee"], rollcall_id="h-119-1-0001"
    )])])
    e = events.compute(data)["2026-03"].events[0]
    assert e.committees == ["Armed Services Committee"]
    assert e.rollcall_id == "h-119-1-0001"


# --- no silent collapse (the D88 lesson) -------------------------------------
def test_actions_differing_only_by_committee_stay_FIVE_events(tmp_path: Path) -> None:
    """hr2670-118 really carries five of these. Hashing only the text would
    publish one event for five official actions — the exact shape of the bug D88
    found in `bill_actions()` (225 of 234 actions returned)."""
    same = dict(date="2026-03-04", text="Forwarded by Subcommittee to Full Committee "
                "by Voice Vote .", action_code="H-Fwd")
    data = _dataset(tmp_path, [_bill(actions=[
        _action(**same, committees=[c]) for c in
        ("Subcommittee A", "Subcommittee B", "Subcommittee C", "Subcommittee D",
         "Subcommittee E")
    ])])
    out = events.compute(data)["2026-03"]
    assert out.count == 5
    assert len({e.id for e in out.events}) == 5  # five DISTINCT ids, not one repeated


def test_two_genuinely_identical_rows_hash_the_same(tmp_path: Path) -> None:
    """The id is a function of the row and nothing else — same row, same id. This
    is what makes it usable as a de-duplication key by an alert consumer that sees
    the same month file twice."""
    row = _action()
    assert events.event_id("hr1-119", row) == events.event_id("hr1-119", dict(row))


def test_the_id_does_not_depend_on_field_ORDER(tmp_path: Path) -> None:
    """`sort_keys` in the hash payload. Without it, a reordered upstream payload
    would change every id in the feed and re-alert every subscriber."""
    row = _action()
    shuffled = {k: row[k] for k in reversed(list(row))}
    assert events.event_id("hr1-119", row) == events.event_id("hr1-119", shuffled)


def test_the_id_is_prefixed_for_a_human_reading_the_feed(tmp_path: Path) -> None:
    got = events.event_id("hr1-119", _action(date="2026-03-04"))
    assert got.startswith("hr1-119--2026-03-04--")
    assert len(got.rsplit("--", 1)[1]) == 12


# --- has_page (SD-33 3c) -----------------------------------------------------
def test_has_page_is_true_only_for_a_bill_that_reached_a_vote(tmp_path: Path) -> None:
    data = _dataset(
        tmp_path,
        [_bill("hr1-119", actions=[_action()]), _bill("hr2-119", number=2, actions=[_action()])],
        voted=["hr1-119"],
    )
    by_bill = {e.bill_id: e.has_page for e in events.compute(data)["2026-03"].events}
    assert by_bill == {"hr1-119": True, "hr2-119": False}


def test_a_pageless_bill_still_carries_a_working_link(tmp_path: Path) -> None:
    """Decision 3(c): it links to congress.gov, never to a `/b/` URL that does not
    exist, or `npm run test:links` fails on the first one."""
    e = events.compute(
        _dataset(tmp_path, [_bill(actions=[_action()])], voted=[])
    )["2026-03"].events[0]
    assert e.has_page is False
    assert e.source_url.startswith("https://www.congress.gov/")


def test_voted_bill_ids_reads_the_same_field_the_site_reads(tmp_path: Path) -> None:
    """`rollcall.bill_id` — the one field `votedBillIds()` in site/src/lib/data.ts
    uses. A roll call with no bill (a Speaker election) adds nothing."""
    data = _dataset(tmp_path, [_bill(actions=[_action()])], voted=["hr1-119"])
    (data / "votes" / "h-119-1-0099.json").write_text(
        json.dumps({"rollcall": {"id": "h-119-1-0099", "bill_id": None},
                    "member_votes": []}), encoding="utf-8")
    assert events.voted_bill_ids(data) == {"hr1-119"}


def test_voted_bill_ids_with_no_votes_directory(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    assert events.voted_bill_ids(tmp_path / "data") == set()


def test_has_page_matches_the_sites_paged_set(tmp_path: Path) -> None:
    """The rule in `events.voted_bill_ids` and the rule in `votedBillIds()` are
    the same sentence in two languages, so this test states it once more in a
    third place: a bill gets a page iff some roll call names it. If the site ever
    changes its rule, this test is the breadcrumb back to here."""
    data = _dataset(
        tmp_path,
        [_bill(f"hr{n}-119", number=n, actions=[_action()]) for n in (1, 2, 3)],
        voted=["hr1-119", "hr3-119"],
    )
    paged = {e.bill_id for e in events.compute(data)["2026-03"].events if e.has_page}
    assert paged == events.voted_bill_ids(data) == {"hr1-119", "hr3-119"}


# --- determinism (invariant 8's whole reason) --------------------------------
def test_the_projection_is_byte_stable_across_runs(tmp_path: Path) -> None:
    data = _dataset(tmp_path, [
        _bill(f"hr{n}-119", number=n, actions=[_action(date=d, text=f"Action {n}")])
        for n, d in enumerate(("2026-03-04", "2026-03-01", "2026-02-27"), 1)
    ])
    first = {m: _dumps(f.model_dump()) for m, f in events.compute(data).items()}
    second = {m: _dumps(f.model_dump()) for m, f in events.compute(data).items()}
    assert first == second


def test_events_are_newest_first_with_a_total_tiebreak(tmp_path: Path) -> None:
    """Newest action first (the feed order task 7 renders), and ties broken by
    bill then id so the order never depends on filesystem iteration."""
    data = _dataset(tmp_path, [
        _bill("hr2-119", number=2, actions=[_action(date="2026-03-01", text="older")]),
        _bill("hr1-119", number=1, actions=[_action(date="2026-03-09", text="newest")]),
        _bill("hr3-119", number=3, actions=[_action(date="2026-03-09", text="same day")]),
    ])
    rows = events.compute(data)["2026-03"].events
    assert [e.date for e in rows] == ["2026-03-09", "2026-03-09", "2026-03-01"]
    assert [e.bill_id for e in rows[:2]] == ["hr1-119", "hr3-119"]  # tie broken by bill


def test_the_sort_is_descending_by_real_date_not_by_string(tmp_path: Path) -> None:
    """Within a month the day is what moves, and a plain string reverse would also
    flip the tiebreakers. `_desc` negates the parts instead."""
    assert events._desc("2026-03-09") < events._desc("2026-03-01")
    assert events._desc("2026-12-31") < events._desc("2026-01-01")


def test_count_equals_the_rows_it_ships_with(tmp_path: Path) -> None:
    data = _dataset(tmp_path, [_bill(actions=[_action(), _action(text="Second.")])])
    f = events.compute(data)["2026-03"]
    assert f.count == len(f.events) == 2


def test_no_wall_clock_anywhere_in_the_module() -> None:
    """A cheap structural guard: the whole artifact is invalid if a clock gets in,
    and invariant 8 would only catch it on a day the value happened to change."""
    src = Path(events.__file__).read_text(encoding="utf-8")
    for banned in ("datetime", "time.time", "now(", "today("):
        assert banned not in src, f"{banned!r} in events.py — invariant 8 depends on no clock"


# --- the CLI + the exporter --------------------------------------------------
def test_run_writes_a_file_per_month_and_reports_the_total(tmp_path, monkeypatch, capsys):
    from ingest import cache, export

    data = _dataset(tmp_path, [_bill(actions=[
        _action(date="2026-03-04"), _action(date="2026-02-02", text="Earlier.")
    ])])
    monkeypatch.setattr(cache, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(export, "EVENTS_DIR", data / "events")
    assert events.run([]) == 0
    out = capsys.readouterr().out
    assert "2 event(s) across 2 month file(s)" in out
    assert sorted(p.name for p in (data / "events").iterdir()) == [
        "2026-02.json", "2026-03.json"
    ]


def test_run_refuses_an_unknown_argument(capsys) -> None:
    """Same discipline as `bill-activity`: a typo'd flag must not be ignored."""
    assert events.run(["--since", "30"]) == 2
    assert "unknown argument" in capsys.readouterr().out


def test_the_cli_routes_the_events_subcommand(monkeypatch) -> None:
    from ingest import cli

    monkeypatch.setattr(events, "run", lambda argv: 7)
    assert cli.main(["events"]) == 7


def test_export_events_writes_atomically_and_byte_stably(tmp_path: Path) -> None:
    from ingest.export import export_events

    data = _dataset(tmp_path, [_bill(actions=[_action()])])
    months = events.compute(data)
    written = export_events(months, out_dir=tmp_path / "out")
    assert [p.name for p in written] == ["2026-03.json"]
    first = written[0].read_bytes()
    export_events(months, out_dir=tmp_path / "out")
    assert written[0].read_bytes() == first
    assert sorted(p.suffix for p in (tmp_path / "out").iterdir()) == [".json"]  # no .tmp


def test_the_published_file_validates_against_its_own_schema(tmp_path: Path) -> None:
    """data/schema/events.schema.json is generated from EventsFile, so a consumer
    validating the feed against it must accept what we actually write."""
    from ingest.models import EventsFile

    data = _dataset(tmp_path, [_bill(actions=[_action()])])
    raw = json.loads(_dumps(events.compute(data)["2026-03"].model_dump()))
    assert EventsFile(**raw).count == 1


# --- invariant 8 -------------------------------------------------------------
def test_invariant_8_passes_on_a_freshly_exported_dataset(tmp_path, monkeypatch) -> None:
    from ingest import export, verify_recompute

    data = _dataset(tmp_path, [_bill(actions=[_action()])], voted=["hr1-119"])
    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)
    export.export_events(events.compute(data), out_dir=data / "events")
    assert verify_recompute.check_events() == []


def test_invariant_8_catches_an_edited_action_text(tmp_path, monkeypatch) -> None:
    """0.5 forbids rewording government text. This is the check that notices."""
    from ingest import export, verify_recompute

    data = _dataset(tmp_path, [_bill(actions=[_action()])])
    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)
    written = export.export_events(events.compute(data), out_dir=data / "events")[0]
    written.write_text(
        written.read_text(encoding="utf-8").replace("Introduced in House.", "Introduced!"),
        encoding="utf-8",
    )
    assert any("committed bytes != recompute" in f for f in verify_recompute.check_events())


def test_invariant_8_catches_a_stale_month_file(tmp_path, monkeypatch) -> None:
    """`export_events` never deletes a month file, by design. This is the other
    half of that decision: the leftover is reported rather than ignored."""
    from ingest import export, verify_recompute

    data = _dataset(tmp_path, [_bill(actions=[_action()])])
    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)
    export.export_events(events.compute(data), out_dir=data / "events")
    (data / "events" / "2019-07.json").write_text(
        _dumps({"month": "2019-07", "count": 0, "events": []}), encoding="utf-8"
    )
    assert any("no longer re-derives" in f for f in verify_recompute.check_events())


def test_invariant_8_catches_a_month_file_that_was_never_written(tmp_path, monkeypatch) -> None:
    from ingest import export, verify_recompute

    data = _dataset(tmp_path, [_bill(actions=[
        _action(date="2026-03-04"), _action(date="2026-02-02", text="Earlier.")
    ])])
    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)
    export.export_events(events.compute(data), out_dir=data / "events")
    (data / "events" / "2026-02.json").unlink()
    assert any("recomputed but no committed file" in f
               for f in verify_recompute.check_events())


def test_invariant_8_is_a_no_op_before_the_events_directory_exists(tmp_path, monkeypatch):
    from ingest import verify_recompute

    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)
    (tmp_path / "data").mkdir()
    assert verify_recompute.check_events() == []


@pytest.mark.parametrize("bad", ["20260304", "2026-W10-3", "2026-3-04"])
def test_a_non_extended_iso_date_cannot_reach_the_month_slice(bad: str) -> None:
    """`_MONTH` is a slice, which is only safe because `BillAction._iso_date`
    rejects every other ISO form. If that validator ever loosens, `2026-W10-3`
    would file an action under month `2026-W1`."""
    from pydantic import ValidationError

    from ingest.models import BillAction

    with pytest.raises(ValidationError):
        BillAction(date=bad, text="t", type="Floor", source_system="House")
