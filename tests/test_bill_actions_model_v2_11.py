"""V2-11 task 3 — the `BillAction` schema and the pure `parse_actions` mapper.

Nullability here is measured, not assumed: 520 real actions across six bills and
four Congresses were surveyed before the model was written (D88 addendum).
`actionDate`, `text`, `type` and `sourceSystem` were present on all 520;
`actionCode` on 337, `actionTime` on 227, `committees` on 97, `recordedVotes` on
58. The tests below pin each of those decisions so a later "tidy-up" cannot
quietly make a required field optional or vice versa.

**`text` is the one the survey got wrong, and real data — not a tidy-up — is why
it is now optional (2026-10-05).** Congress 118's full backfill hit s4869-118,
whose Library of Congress `Intro-S` row (2024-07-30) carries no `text` key at
all. The required field raised `KeyError: 'text'` and quarantined the whole
bill, so a missing sentence cost a missing bill — 1 in 19,125. The tests below
now pin the opposite direction for this one field: a row without `text` must
parse, must store `None`, and must NEVER store `""` (the site's `actionText()`
guard is nullish `??`, which an empty string slips past, rendering a blank
timeline line — an action with no content, a Value #1 false framing).
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ingest.bills import parse_actions, rollcall_id_for
from ingest.models import Bill, BillAction


def _raw(
    date="2023-06-13",
    text="Introduced in House",
    type_="IntroReferral",
    *,
    time=None,
    code=None,
    committees=None,
    recorded=None,
    source="Library of Congress",
):
    a = {
        "actionDate": date,
        "type": type_,
        "sourceSystem": {"name": source},
    }
    # `text=None` means "the key is ABSENT", which is what congress.gov actually
    # served on s4869-118 — not a present-but-null value.
    if text is not None:
        a["text"] = text
    if time is not None:
        a["actionTime"] = time
    if code is not None:
        a["actionCode"] = code
    if committees is not None:
        a["committees"] = [{"name": c, "systemCode": "hsas00"} for c in committees]
    if recorded is not None:
        a["recordedVotes"] = recorded
    return a


def _rv(chamber="House", congress=118, session=1, roll=723):
    return {
        "chamber": chamber,
        "congress": congress,
        "sessionNumber": session,
        "rollNumber": roll,
        "date": "2023-12-14T15:45:30Z",
        "url": "https://clerk.house.gov/evs/2023/roll723.xml",
    }


# --- the schema --------------------------------------------------------------
def test_required_fields_are_the_ones_always_present():
    a = BillAction(
        date="2023-06-13", text="Introduced in House", type="IntroReferral",
        source_system="Library of Congress",
    )
    assert a.time is None
    assert a.action_code is None
    assert a.committees is None
    assert a.rollcall_id is None


@pytest.mark.parametrize("missing", ["date", "type", "source_system"])
def test_measured_required_fields_cannot_be_omitted(missing):
    """`text` is deliberately NOT in this list any more — see the module
    docstring. These three were present on all 520 surveyed actions and on every
    action the Congress-118 backfill parsed (its only `text`-shaped failure was
    s4869-118); nothing orders a timeline, names its chamber or labels its stage
    without them."""
    kwargs = {
        "date": "2023-06-13",
        "text": "Introduced in House",
        "type": "IntroReferral",
        "source_system": "Library of Congress",
    }
    del kwargs[missing]
    with pytest.raises(ValidationError):
        BillAction(**kwargs)


def test_text_is_optional_and_defaults_to_none():
    """The s4869-118 correction at the schema layer. `None` is the published
    representation of "the official record carries no sentence for this action";
    the action itself is still real and fully identified by its other fields."""
    a = BillAction(
        date="2024-07-30", type="IntroReferral", action_code="Intro-S",
        source_system="Library of Congress",
    )
    assert a.text is None
    assert (a.date, a.type, a.action_code) == ("2024-07-30", "IntroReferral", "Intro-S")


def test_text_null_round_trips_through_the_export_serialization():
    """`ingest.export._dumps` must write `"text": null`, not drop the key. Two
    things depend on it: `ingest.events.event_id` and `entryId()` in
    `site/src/lib/atom.ts` hash the stored row, and JSON.stringify OMITS an
    `undefined` while Python keeps a `None` — so a dropped key would split the
    two ids and re-notify every subscriber on that bill."""
    from ingest.export import _dumps

    a = BillAction(
        date="2024-07-30", type="IntroReferral", source_system="Library of Congress"
    )
    dumped = _dumps(a.model_dump())
    assert '"text": null' in dumped
    assert json.loads(dumped)["text"] is None


def test_unknown_field_is_rejected():
    # Tier-1 strictness: upstream schema drift must fail loudly, not ride along.
    with pytest.raises(ValidationError):
        BillAction(
            date="2023-06-13", text="x", type="Floor",
            source_system="Senate", surpriseField="?",
        )


@pytest.mark.parametrize(
    "bad",
    [
        "13-06-2023",  # day-first
        "2023-6-13",   # not zero-padded
        "20230613",    # ISO BASIC form -- date.fromisoformat ACCEPTS this
        "2023-W24-2",  # ISO week date -- date.fromisoformat ACCEPTS this too
        "",
        "not a date",
    ],
)
def test_only_the_extended_iso_date_form_is_accepted(bad):
    """The timeline is ordered by string comparison on `date`, so a date that
    parses but sorts differently is worse than one that fails: it renders out of
    order silently. Bare `date.fromisoformat` is too permissive on 3.11+ --
    "20230613" and "2023-W24-2" both parse to 2023-06-13 and both sort wrong."""
    with pytest.raises(ValidationError):
        BillAction(date=bad, text="x", type="Floor", source_system="Senate")


def test_the_extended_form_is_accepted():
    assert BillAction(
        date="2023-06-13", text="x", type="Floor", source_system="Senate"
    ).date == "2023-06-13"


def test_type_is_not_a_closed_set():
    # Eight values appear in the survey and the set is the government's to extend.
    # A new action type must not quarantine the whole bill.
    a = BillAction(
        date="2023-06-13", text="x", type="SomeNewTypeIn2027",
        source_system="Senate",
    )
    assert a.type == "SomeNewTypeIn2027"


def test_bill_actions_defaults_to_the_not_collected_sentinel():
    # D27: None = not collected, [] = collected and the government lists none.
    # The two must stay distinguishable or an empty timeline becomes a false claim.
    bill = Bill(
        id="hr1-119", congress=119, type="hr", number=1, title_official="A Bill",
        policy_area=None, sponsor_id=None, latest_action="Referred.",
        latest_action_date="2025-01-03", cbo_estimates=[],
        source_url="https://example.gov/hr1",
    )
    assert bill.actions is None
    bill_collected = bill.model_copy(update={"actions": []})
    assert bill_collected.actions == []
    assert bill_collected.actions is not None


# --- rollcall_id_for ---------------------------------------------------------
def test_rollcall_id_for_matches_the_house_votes_helper_exactly():
    # A near-miss here is a link to a page that does not exist. The zero padding
    # is the easy thing to get wrong.
    assert rollcall_id_for(_rv("House", 118, 1, 723)) == "h-118-1-0723"
    assert rollcall_id_for(_rv("Senate", 119, 2, 7)) == "s-119-2-0007"


def test_rollcall_id_for_returns_none_on_malformed_entry():
    assert rollcall_id_for({}) is None
    assert rollcall_id_for({"chamber": "House", "congress": "x"}) is None
    assert rollcall_id_for({"chamber": "House", "congress": 118}) is None


# --- parse_actions -----------------------------------------------------------
def test_parse_actions_preserves_order_and_count():
    raw = [_raw(text="third"), _raw(text="second"), _raw(text="first")]
    got = parse_actions(raw)
    assert [a.text for a in got] == ["third", "second", "first"]


def test_parse_actions_maps_every_optional_field():
    raw = [_raw(time="15:45:30", code="H37100", committees=["Rules Committee"])]
    a = parse_actions(raw)[0]
    assert a.time == "15:45:30"
    assert a.action_code == "H37100"
    assert a.committees == ["Rules Committee"]


def test_parse_actions_normalises_absent_optionals_to_none_not_empty():
    a = parse_actions([_raw()])[0]
    assert a.time is None and a.action_code is None and a.committees is None


def test_parse_actions_reads_source_system_name_only():
    # The Senate block is {"name": "Senate"} with NO code at all, so a stored
    # code would be null for an entire chamber.
    assert parse_actions([_raw(source="Senate")])[0].source_system == "Senate"


def test_parse_actions_unescapes_entities_in_text_and_committees():
    # The same lossless decode parse_bill applies to titles: storing the raw
    # entity would double-escape when the site renders it as text.
    raw = [_raw(text="Rules &amp; Administration said &#039;no&#039;",
                committees=["Ways &amp; Means"])]
    a = parse_actions(raw)[0]
    assert a.text == "Rules & Administration said 'no'"
    assert a.committees == ["Ways & Means"]


def test_parse_actions_keeps_rows_distinguished_only_by_committee():
    """The task-2 bug, now at the model layer. Five real actions share a date,
    text and action code on hr2670-118 and differ only in `committees`. All five
    must survive parsing as distinct rows, each naming its own subcommittee."""
    subs = [
        "Cyber, Information Technologies, and Innovation Subcommittee",
        "Seapower and Projection Forces Subcommittee",
        "Military Personnel Subcommittee",
        "Tactical Air and Land Forces Subcommittee",
        "Intelligence and Special Operations Subcommittee",
    ]
    raw = [
        _raw(text="Forwarded by Subcommittee to Full Committee by Voice Vote .",
             type_="Committee", code="H23000", committees=[s])
        for s in subs
    ]
    got = parse_actions(raw)
    assert len(got) == 5
    assert [a.committees[0] for a in got] == subs


# --- rollcall resolution: the "else left null" rule --------------------------
def test_parse_actions_links_a_rollcall_we_hold():
    raw = [_raw(text="On passage", type_="Floor", recorded=[_rv(roll=723)])]
    got = parse_actions(raw, known_rollcall_ids={"h-118-1-0723"})
    assert got[0].rollcall_id == "h-118-1-0723"


def test_parse_actions_leaves_an_uncovered_rollcall_null():
    """40 of 58 recordedVotes resolved in the survey; all 18 misses were 117th or
    116th Congress — real votes outside the covered window. Emitting an id for
    those would render a link to a /v/ page that was never built."""
    raw = [_raw(text="On passage", recorded=[_rv(congress=117, roll=370)])]
    got = parse_actions(raw, known_rollcall_ids={"h-118-1-0723"})
    assert got[0].rollcall_id is None


def test_parse_actions_resolves_nothing_when_no_known_set_is_given():
    # The conservative default. "I was not told what exists" must never mean
    # "assume it all exists".
    raw = [_raw(recorded=[_rv()])]
    assert parse_actions(raw)[0].rollcall_id is None


def test_parse_actions_takes_the_first_resolvable_of_several_recorded_votes():
    raw = [_raw(recorded=[_rv(congress=117, roll=370), _rv(congress=118, roll=723)])]
    got = parse_actions(raw, known_rollcall_ids={"h-118-1-0723"})
    assert got[0].rollcall_id == "h-118-1-0723"


def test_parse_actions_survives_a_malformed_recorded_vote():
    raw = [_raw(recorded=[{"chamber": "House"}])]
    assert parse_actions(raw, known_rollcall_ids={"h-118-1-0723"})[0].rollcall_id is None


def test_parse_actions_raises_on_a_missing_required_field():
    # A malformed action must still quarantine the bill (§6.1). `sourceSystem` is
    # the omission under test and it is omitted EXPLICITLY — `text` used to be
    # missing from this row too, which made the test ambiguous once `text` became
    # optional. An action with no chamber of origin is not publishable.
    with pytest.raises((ValidationError, KeyError)):
        parse_actions([{"actionDate": "2023-06-13", "text": "x", "type": "Floor"}])


# --- the s4869-118 correction: a row congress.gov served with no `text` -------
def test_parse_actions_tolerates_a_row_with_no_text_key():
    """The exact shape that quarantined s4869-118, replayed from the cached
    payload (`data/raw/congress_gov/97050f2fb96e4fb9.json`): a Library of
    Congress `Intro-S` row with `actionDate`, `actionCode`, `sourceSystem` and
    `type` and NO `text` key. It must parse, not raise — the old required field
    turned one missing sentence into one missing bill."""
    raw = [{
        "actionCode": "Intro-S",
        "actionDate": "2024-07-30",
        "sourceSystem": {"code": 9, "name": "Library of Congress"},
        "type": "IntroReferral",
    }]
    got = parse_actions(raw)
    assert len(got) == 1
    a = got[0]
    assert a.text is None
    # Everything the government DID publish about the action survives, so the
    # timeline still shows a dated, coded, attributed step.
    assert (a.date, a.type, a.action_code, a.source_system) == (
        "2024-07-30", "IntroReferral", "Intro-S", "Library of Congress"
    )


def test_parse_actions_stores_none_not_empty_string_for_absent_text():
    """`""` is forbidden, and this is the test that keeps it forbidden. The site's
    `actionText()` substitutes its "(no action text on the official record)" copy
    with a nullish `??`; an empty string is not nullish, so it would slip through
    and render a blank line — publishing an action with no content (Value #1).
    Both an absent key and an empty string must normalise to `None`."""
    assert parse_actions([_raw(text=None)])[0].text is None
    assert parse_actions([_raw(text="")])[0].text is None


def test_parse_actions_keeps_the_rest_of_a_timeline_when_one_row_has_no_text():
    """s4869-118's real payload is three rows, only the middle one missing text.
    All three must publish: dropping the row would undercount the official
    timeline, which is the same false-zero D88 fought over `committees`."""
    raw = [
        _raw(date="2024-08-01", text="Read twice and referred to the Committee."),
        _raw(date="2024-07-30", text=None, code="Intro-S"),
        _raw(date="2024-07-30", text="Introduced in Senate."),
    ]
    got = parse_actions(raw)
    assert [a.text for a in got] == [
        "Read twice and referred to the Committee.", None, "Introduced in Senate."
    ]


def test_parse_actions_still_unescapes_when_text_is_present():
    # The nullable guard must not have cost the lossless entity decode.
    assert parse_actions([_raw(text="A &amp; B")])[0].text == "A & B"


def test_parse_actions_empty_input_is_empty_output():
    assert parse_actions([]) == []
