"""§5 Phase 3 owner decision 2 — the free rule-based pre-filter. No AI, no network.

The properties under test are the ones the decision and the owner's four rulings of
2026-10-14 exist for: every drop is logged with its reason, a vote urge is never dropped
as housekeeping, a tribute that argues policy survives, a vote explanation is kept but
never costs money, inserted material is cut at the member's own marker sentence, and the
fairness table is reproducible because rule order is fixed.

Every example here is real text from the pilot corpus, trimmed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest import prefilter

# --- fixtures -------------------------------------------------------------------------


def _record(
    *segments: str,
    member_id: str = "B001257",
    date: str = "2025-06-03",
    granule_id: str | None = None,
    source: str = "congressional_record",
    attribution: str = "turn",
    title: str = "A TITLE",
    granule_class: str = "HOUSE",
) -> dict:
    """One statement record in the shape every collector emits."""
    return {
        "member_id": member_id,
        "date": date,
        "granule_id": granule_id or f"CREC-{date}-pt1-PgH1-1",
        "package_id": f"CREC-{date}",
        "source": source,
        "attribution": attribution,
        "title": title,
        "granule_class": granule_class,
        "chamber": "HOUSE",
        "parsed_name": "Mr. BILIRAKIS",
        "url": "https://www.govinfo.gov/app/details/x",
        "speakers": 1,
        "segments": list(segments),
        "chars": sum(len(s) for s in segments),
    }


SUBSTANTIVE = (
    "Mr. BILIRAKIS. Mr. Speaker, this bill would lower the cost of electricity for "
    "families in manufactured housing, and the committee heard testimony from three "
    "separate consumer groups confirming that the current standards have not been "
    "updated in decades. That is why I support it."
)

TRIBUTE = (
    "Mr. BILIRAKIS. Mr. Speaker, it is a privilege to rise today to recognize Mr. Ricky "
    "Gude, Team Lead with Withlacoochee River Electric Cooperative, for his outstanding "
    "leadership and service as part of the Light Up Navajo Project."
)


# --- reading a turn -------------------------------------------------------------------


def test_content_strips_the_name_and_the_salutation():
    assert prefilter.content("  Mr. BILIRAKIS. Mr. Speaker, I rise today.") == "I rise today."
    assert prefilter.content("Ms. CASTOR of Florida. Mr. Speaker, we begin.") == "we begin."
    assert prefilter.content("Mr. HAGERTY. Mr. President, I ask.") == "I ask."
    assert prefilter.content("Madam Speaker, I object.") == "I object."
    assert prefilter.content("Mr. Chairman, the hour is late.") == "the hour is late."


def test_content_flattens_the_records_hard_line_wraps():
    """The Record wraps at ~72 columns, so a phrase written with spaces in a pattern
    would never match the stored text. This is why every rule reads `content()`."""
    wrapped = "Mr. BILIRAKIS. Mr. Speaker, I include in the\nRecord this letter."
    assert prefilter.content(wrapped) == "I include in the Record this letter."


def test_content_of_a_turn_with_no_opener_is_the_turn():
    assert prefilter.content("the hour is late.") == "the hour is late."
    assert prefilter.content("") == ""


def test_normalize_ignores_punctuation_and_case():
    assert prefilter.normalize("He said ``Yes!'' -- twice.") == "he said yes twice"


# --- the inserted-material cut (fact 5) ----------------------------------------------


def test_no_marker_leaves_the_turn_untouched():
    kept, cut = prefilter.cut_inserted_material(SUBSTANTIVE)
    assert cut == 0
    assert kept == SUBSTANTIVE


def test_cut_keeps_everything_up_to_and_including_the_marker_sentence():
    """The owner's rule, 2026-10-13: the marker is his words, what follows is not."""
    turn = (
        "Mr. BILIRAKIS. Mr. Speaker, I include in the Record a letter from the "
        "Industrial Energy Consumers of America dated November 17, 2025. Dear Chairman: "
        "We write to express our deep concern about the proposed rule."
    )
    kept, cut = prefilter.cut_inserted_material(turn)
    assert kept.endswith("dated November 17, 2025.")
    assert "Dear Chairman" not in kept
    assert cut == len(turn) - len(kept)


def test_cut_treats_a_colon_as_the_end_of_the_marker_sentence():
    """"... the following list of 2026 Inductees:" is the whole of what he said."""
    turn = (
        "Mr. BILIRAKIS. I include in the Record the following list of 2026 Inductees: "
        "Jane Roe, University of Central Florida. John Doe, Georgia Tech."
    )
    kept, _ = prefilter.cut_inserted_material(turn)
    assert kept.endswith("2026 Inductees:")
    assert "Jane Roe" not in kept


def test_cut_accepts_a_terminator_inside_the_records_closing_quote():
    """A marker sentence naming a quoted headline ends `... can be a crisis.''` — a
    period followed by `''` rather than by a capital is still the end of his sentence.
    The one mis-cut found on the real corpus, 2026-10-14."""
    turn = (
        "Mr. BILIRAKIS. Mr. Speaker, I include in the Record the Tampa Bay Times "
        "article of December 30, ``For Tampa Bay's mobile home residents, high "
        "electric bills can be a crisis.'' For Tampa Bay's Mobile Home Residents "
        "(By Emily L. Mahoney, Dec. 30, 2025) Energy standards have not been updated."
    )
    kept, _ = prefilter.cut_inserted_material(turn)
    assert kept.endswith("can be a crisis.''")
    assert "Mahoney" not in kept


def test_cut_with_no_terminator_at_all_keeps_the_whole_turn():
    turn = "Mr. BILIRAKIS. I include in the Record the following names"
    kept, cut = prefilter.cut_inserted_material(turn)
    assert cut == 0
    assert kept.endswith("following names")


def test_the_floor_managers_extraneous_material_request_is_not_a_marker():
    """The negative lookahead that matters: this is a floor manager granting EVERY
    member leave to file, not this member inserting anything. Letting it through
    truncated 278 real rows at their opening sentence."""
    turn = (
        "Mr. BILIRAKIS. Mr. Speaker, I ask unanimous consent that all Members may have "
        "5 legislative days to revise and extend their remarks and insert extraneous "
        "material in the Record on this particular bill."
    )
    kept, cut = prefilter.cut_inserted_material(turn)
    assert cut == 0
    assert kept == turn


# --- the rules ------------------------------------------------------------------------


def test_a_turn_with_no_words_is_logged_not_passed():
    assert prefilter.classify_turn("") == ("no-attributable-text", None)


def test_substantive_argument_survives_every_rule():
    assert prefilter.classify_turn(prefilter.content(SUBSTANTIVE)) == (None, None)


@pytest.mark.parametrize(
    ("text", "sub_rule"),
    [
        (
            "I ask unanimous consent that all Members may have 5 legislative days in "
            "which to revise and extend their remarks.",
            "leave-to-revise-and-extend",
        ),
        ("I move that the House do now adjourn.", "adjournment-and-meeting-hour"),
        ("I suggest the absence of a quorum.", "quorum-call"),
        ("I have three requests for committees to meet today.", "committee-authority-to-meet"),
        (
            "I ask that the privileges of the floor be granted to Kelsie Hovenden.",
            "floor-privileges",
        ),
        ("I yield back the balance of my time.", "yielding-time"),
        (
            "I ask unanimous consent that the Senate be in a period of morning business.",
            "calendar-and-morning-business",
        ),
        ("I ask unanimous consent to speak for up to 2 minutes.", "unanimous-consent-request"),
    ],
)
def test_each_housekeeping_act_is_named_so_the_sub_rule_table_can_be_built(text, sub_rule):
    """R4's condition: the procedural gap must break down to each act."""
    assert prefilter.classify_turn(text) == ("procedural", sub_rule)
    assert prefilter.procedural_sub_rule(text) == sub_rule


def test_a_short_turn_that_performs_no_housekeeping_act_is_kept():
    assert prefilter.procedural_sub_rule("I thank the gentleman.") is None
    assert prefilter.classify_turn("I thank the gentleman.") == (None, None)


def test_a_vote_urge_is_a_position_and_is_never_dropped_as_housekeeping():
    """R2, the example the owner ruled on, 2026-10-14. 120 characters, procedural in
    shape, and a stated position on a bill."""
    text = (
        "in closing, I encourage a ``yes'' vote on this particular piece of legislation, "
        "and I yield back the balance of my time."
    )
    assert len(text) < prefilter.PROCEDURAL_MAX_CHARS
    assert prefilter.procedural_sub_rule(text) == "yielding-time"
    assert prefilter.classify_turn(text) == (None, None)


def test_a_long_speech_that_opens_with_a_consent_request_is_not_dropped():
    """The length guard R2 keeps: a 40,434-character floor speech in the pilot corpus
    opens with a unanimous-consent request."""
    text = "I ask unanimous consent to speak for 10 minutes. " + ("policy argument. " * 40)
    assert len(text) >= prefilter.PROCEDURAL_MAX_CHARS
    assert prefilter.procedural_sub_rule(text) == "unanimous-consent-request"
    assert prefilter.classify_turn(text) == (None, None)


def test_a_tribute_is_dropped_as_ceremonial():
    assert prefilter.classify_turn(prefilter.content(TRIBUTE)) == ("ceremonial", None)


def test_a_tribute_that_argues_policy_survives_whole():
    """R1, the example the owner ruled on: a Holocaust-remembrance Extension that closes
    with a call to action."""
    text = (
        "I rise today to remember the victims of anti-Semitism in America in the 1920s. "
        "Mr. Speaker, I urge my colleagues to go see this comparative analogy."
    )
    assert prefilter.CEREMONIAL.search(text)
    assert prefilter.classify_turn(text) == (None, None)


def test_a_tribute_that_names_a_bill_survives_whole():
    text = "I rise today to congratulate the sponsors of H.R. 2269, which I cosponsor."
    assert prefilter.argues_policy(text) is True
    assert prefilter.classify_turn(text) == (None, None)


def test_a_possessive_before_a_year_is_not_a_bill_citation():
    """Measured 2026-10-14: a case-insensitive `S\\.?\\s?\\d{1,4}` read the possessive in
    "Florida's 2024 Person of the Year" as bill "S. 2024" and rescued 56 pure tributes
    from the ceremonial rule on that basis. A citation must carry its period and may not
    be preceded by a word character."""
    text = (
        "I rise today to recognize the PanCyprian Association of Florida's 2024 Person "
        "of the Year, Savas Tsivicos, a native of Cyprus."
    )
    assert prefilter.argues_policy(text) is False
    assert prefilter.classify_turn(text) == ("ceremonial", None)


@pytest.mark.parametrize(
    "citation",
    ["H.R. 139", "H.R.139", "HR 139", "H. Res. 550", "S. 2882", "S.J. Res. 90"],
)
def test_the_records_own_bill_citation_forms_are_read_as_policy(citation):
    assert prefilter.argues_policy(f"I rise today to honor the sponsors of {citation}.") is True


@pytest.mark.parametrize(
    "text",
    [
        "the department's 145-year history was unprecedented",
        "Robert Kennedy's 1968 Presidential campaign",
        "his service spanned 1942 to 1945 in the Pacific",
    ],
)
def test_ordinary_prose_is_not_read_as_a_bill_citation(text):
    assert prefilter.argues_policy(text) is False


def test_office_logistics_is_dropped():
    text = "I will host a town hall in Pasco County on Thursday evening."
    assert prefilter.classify_turn(text) == ("office-logistics", None)


def test_office_logistics_does_not_fire_on_a_tribute_that_mentions_an_internship():
    """Deliberately narrow: the first draft of this rule mis-fired on 48 tributes."""
    text = (
        "I rise today to honor the exceptional dedication of one of my outstanding "
        "constituents, Brian Dillon, who has recently completed an internship."
    )
    assert prefilter.classify_turn(text) == ("ceremonial", None)


# --- one statement through the filter -------------------------------------------------


def test_a_statement_the_record_attributes_no_words_to_is_dropped_and_logged():
    """48 rows in the pilot corpus. Logged at turn -1: there is no turn to point at."""
    survivor, drops = prefilter.apply_to_statement(
        _record(attribution="none"), {}
    )
    assert survivor is None
    assert [d["rule"] for d in drops] == ["no-attributable-text"]
    assert drops[0]["turn"] == -1


def test_a_statement_with_no_segments_is_dropped_and_logged():
    record = _record()
    record["segments"] = []
    survivor, drops = prefilter.apply_to_statement(record, {})
    assert survivor is None
    assert [d["rule"] for d in drops] == ["no-attributable-text"]


def test_the_housekeeping_turn_goes_and_the_speech_in_the_same_granule_stays():
    """Why the unit is the turn: one granule in the pilot corpus holds both."""
    record = _record("Mr. HAGERTY. Mr. President, I suggest the absence of a quorum.", SUBSTANTIVE)
    survivor, drops = prefilter.apply_to_statement(record, {})
    assert survivor is not None
    assert survivor["segments"] == [SUBSTANTIVE]
    assert survivor["prefilter"] == {
        "turns_in": 2,
        "turns_kept": 1,
        "inserted_material_chars_cut": 0,
    }
    assert [(d["rule"], d["sub_rule"], d["turn"]) for d in drops] == [
        ("procedural", "quorum-call", 0)
    ]


def test_a_statement_whose_every_turn_drops_is_dropped():
    survivor, drops = prefilter.apply_to_statement(_record(TRIBUTE), {})
    assert survivor is None
    assert [d["rule"] for d in drops] == ["ceremonial"]


def test_a_vote_explanation_is_kept_and_marked_never_to_reach_the_ai():
    """R3: 80 rows in the pilot corpus, D 55 / R 25. A recorded stance on real votes,
    and nothing the AI can add to "YEA on Roll Call No. 559"."""
    record = _record(
        "Mr. COSTA. Mr. Speaker, on Wednesday, November 1, 2023, I was unable to "
        "physically attend proceedings. Had I been present, I would have voted YEA on "
        "Roll Call No. 559.",
        title="PERSONAL EXPLANATION",
    )
    survivor, drops = prefilter.apply_to_statement(record, {})
    assert drops == []
    assert survivor is not None
    assert survivor["ai_eligible"] is False
    assert survivor["ai_ineligible_reason"] == "vote-explanation"


def test_a_statement_that_is_not_a_vote_explanation_is_ai_eligible():
    survivor, _ = prefilter.apply_to_statement(_record(SUBSTANTIVE), {})
    assert survivor is not None
    assert survivor["ai_eligible"] is True
    assert "ai_ineligible_reason" not in survivor


def test_a_vote_explanation_is_matched_on_the_body_not_the_title():
    """So a press release that explains a vote is caught too — the filter is
    source-agnostic and press offices do not write Record titles."""
    record = _record(
        "Mr. HEINRICH. Mr. President, on October 6, 2025, I was unavoidably absent for "
        "the following rollcall votes.",
        title="SENATOR ISSUES STATEMENT",
        source="member_press",
    )
    survivor, _ = prefilter.apply_to_statement(record, {})
    assert survivor is not None
    assert survivor["ai_eligible"] is False


def test_the_inserted_material_cut_is_recorded_on_the_survivor():
    record = _record(
        "Mr. BILIRAKIS. Mr. Speaker, electricity costs are rising for families in "
        "manufactured housing, which is why this matters. I include in the Record a "
        "letter from the Industrial Energy Consumers of America. Dear Chairman: we "
        "write to express our concern about the rule as proposed."
    )
    survivor, drops = prefilter.apply_to_statement(record, {})
    assert drops == []
    assert survivor is not None
    assert "Dear Chairman" not in survivor["segments"][0]
    assert survivor["prefilter"]["inserted_material_chars_cut"] > 0
    assert survivor["chars"] == len(survivor["segments"][0])


# --- duplicates -----------------------------------------------------------------------


def test_the_same_announcement_twice_keeps_the_first_and_logs_the_second():
    """23 groups inside the Congressional Record alone — the same Extension filed on two
    days. The log names which occurrence it duplicates."""
    seen: dict = {}
    first = _record(SUBSTANTIVE, date="2025-05-21", granule_id="CREC-A")
    second = _record(SUBSTANTIVE, date="2025-06-03", granule_id="CREC-B")
    kept_first, drops_first = prefilter.apply_to_statement(first, seen)
    kept_second, drops_second = prefilter.apply_to_statement(second, seen)
    assert kept_first is not None
    assert drops_first == []
    assert kept_second is None
    assert drops_second[0]["rule"] == "duplicate"
    assert drops_second[0]["duplicate_of"] == "CREC-A"
    assert drops_second[0]["duplicate_of_date"] == "2025-05-21"


def test_a_duplicate_is_caught_across_sources_not_just_within_one():
    """The decision says "duplicates of the same announcement across sources". The press
    release and the floor version of one announcement differ in punctuation, not words."""
    seen: dict = {}
    floor = _record(SUBSTANTIVE, granule_id="CREC-A")
    press = _record(
        SUBSTANTIVE.replace(",", "") + "  ",
        granule_id="PRESS-A",
        source="member_press",
    )
    prefilter.apply_to_statement(floor, seen)
    kept, drops = prefilter.apply_to_statement(press, seen)
    assert kept is None
    assert drops[0]["rule"] == "duplicate"
    assert drops[0]["source"] == "member_press"


def test_two_members_saying_the_same_short_thing_are_not_duplicates():
    seen: dict = {}
    text = "I thank the gentleman for his leadership, and I appreciate the work done."
    one = _record(text, member_id="A000001")
    two = _record(text, member_id="B000002")
    assert prefilter.apply_to_statement(one, seen)[0] is not None
    assert prefilter.apply_to_statement(two, seen)[0] is not None


def test_short_turns_are_never_called_duplicates():
    """Two turns of "I thank the gentleman." are not one announcement published twice."""
    seen: dict = {}
    short = "I thank the gentleman and appreciate it."
    assert len(prefilter.normalize(short)) < prefilter.DUPLICATE_MIN_CHARS
    first = _record(short, granule_id="CREC-A")
    second = _record(short, granule_id="CREC-B")
    assert prefilter.apply_to_statement(first, seen)[0] is not None
    assert prefilter.apply_to_statement(second, seen)[0] is not None


# --- the pass -------------------------------------------------------------------------


def test_the_pass_counts_statements_and_turns_in_and_out():
    other = SUBSTANTIVE.replace("electricity", "natural gas")
    records = [
        _record(SUBSTANTIVE, granule_id="CREC-A"),
        _record(TRIBUTE, granule_id="CREC-B"),
        _record("Mr. X. I yield back the balance of my time.", other, granule_id="CREC-C"),
    ]
    result = prefilter.run_prefilter(records)
    assert result["statements_in"] == 3
    assert result["turns_in"] == 4
    assert result["statements_kept"] == 2
    assert result["turns_kept"] == 2
    assert len(result["drops"]) == 2


def test_the_duplicate_rule_always_keeps_the_earliest_occurrence():
    """Records are sorted before the pass, so which of a duplicate pair is logged does
    not depend on a directory listing — the drop log is byte-identical on a re-run."""
    later = _record(SUBSTANTIVE, date="2025-06-03", granule_id="CREC-LATER")
    earlier = _record(SUBSTANTIVE, date="2025-05-21", granule_id="CREC-EARLY")
    for order in ([later, earlier], [earlier, later]):
        result = prefilter.run_prefilter(order)
        assert [s["granule_id"] for s in result["statements"]] == ["CREC-EARLY"]
        assert result["drops"][0]["statement_id"] == "CREC-LATER"


# --- the audit ------------------------------------------------------------------------


def test_rule_counts_shows_every_rule_even_at_zero():
    """A rule that fired nothing is a fact about the corpus and must not vanish."""
    counts = prefilter.rule_counts([{"rule": "ceremonial"}])
    assert counts == {
        "no-attributable-text": 0,
        "procedural": 0,
        "ceremonial": 1,
        "office-logistics": 0,
        "duplicate": 0,
    }


def test_the_sub_rule_table_is_r4s_condition_and_splits_by_party():
    drops = [
        {"rule": "procedural", "sub_rule": "leave-to-revise-and-extend", "member_id": "R1"},
        {"rule": "procedural", "sub_rule": "leave-to-revise-and-extend", "member_id": "R2"},
        {"rule": "procedural", "sub_rule": "quorum-call", "member_id": "D1"},
    ]
    rows = prefilter.sub_rule_counts(drops, {"R1": "R", "R2": "R", "D1": "D"})
    by_name = {r["sub_rule"]: r for r in rows}
    assert by_name["leave-to-revise-and-extend"] == {
        "sub_rule": "leave-to-revise-and-extend",
        "turns": 2,
        "D": 0,
        "R": 2,
    }
    assert by_name["quorum-call"]["D"] == 1
    assert len(rows) == len(prefilter.PROCEDURAL_SUB_RULES)
    assert by_name["floor-privileges"]["turns"] == 0


def test_fairness_rates_are_against_the_turns_that_party_brought():
    """The pilot is equal by party in MEMBERS, not in turns, so an absolute count would
    compare unlike with unlike."""
    records = [
        _record(*(["x"] * 10), member_id="D1"),
        _record(*(["x"] * 5), member_id="R1"),
    ]
    drops = [{"rule": "ceremonial", "member_id": "D1"}] * 2 + [
        {"rule": "ceremonial", "member_id": "R1"}
    ]
    rows = prefilter.fairness(records, drops, {"D1": "D", "R1": "R"})
    ceremonial = next(r for r in rows if r["rule"] == "ceremonial")
    assert ceremonial["D_rate"] == 20.0
    assert ceremonial["R_rate"] == 20.0
    assert ceremonial["uneven"] is False


def test_fairness_counts_a_member_of_unknown_party_without_crashing():
    records = [_record("x", member_id="Z9")]
    rows = prefilter.fairness(records, [{"rule": "ceremonial", "member_id": "Z9"}], {})
    ceremonial = next(r for r in rows if r["rule"] == "ceremonial")
    assert ceremonial["turns"] == 1
    assert ceremonial["D"] == 0 and ceremonial["R"] == 0
    assert ceremonial["D_rate"] == 0.0


def test_a_rule_that_fired_nothing_is_not_flagged_uneven():
    assert prefilter._uneven(0.0, 0.0, 0) is False


def test_a_real_gap_over_enough_turns_is_flagged():
    """The procedural gap: 3.5% versus 6.2% over 382 turns."""
    assert prefilter._uneven(3.5, 6.2, 382) is True


def test_a_one_sided_rule_over_enough_turns_is_flagged():
    assert prefilter._uneven(0.0, 4.0, 300) is True


def test_a_ratio_on_too_few_turns_is_noise_not_unevenness():
    """17 duplicate turns split 14/3 is a 3x ratio and a 0.2-point difference."""
    assert prefilter._uneven(0.3, 0.1, 17) is False


def test_an_even_rule_is_not_flagged():
    assert prefilter._uneven(20.3, 17.5, 1427) is False


def test_both_rates_zero_over_many_turns_is_not_flagged():
    assert prefilter._uneven(0.0, 0.0, 100) is False


# --- the drop log ---------------------------------------------------------------------


def test_the_drop_log_is_sorted_wall_clock_free_and_reproducible(tmp_path: Path):
    data_dir = tmp_path / "data"
    (data_dir / "quality").mkdir(parents=True)
    records = [
        _record(TRIBUTE, member_id="R0001", granule_id="CREC-Z"),
        _record(TRIBUTE, member_id="A0001", granule_id="CREC-A"),
    ]
    result = prefilter.run_prefilter(records)
    path = prefilter.write_drop_log(result, data_dir)
    first = path.read_text(encoding="utf-8")
    payload = json.loads(first)

    assert payload["rule_order"] == list(prefilter.DROP_RULES)
    assert payload["procedural_max_chars"] == prefilter.PROCEDURAL_MAX_CHARS
    assert payload["statements_in"] == 2
    assert payload["statements_kept"] == 0
    assert [d["member_id"] for d in payload["drops"]] == ["A0001", "R0001"]
    assert all(d["rule"] == "ceremonial" for d in payload["drops"])
    assert "generated_at" not in first and "202" not in first.split('"date"')[0]

    # A re-run over unchanged input is byte-identical, so a real change shows as a diff.
    prefilter.write_drop_log(prefilter.run_prefilter(records), data_dir)
    assert path.read_text(encoding="utf-8") == first


def test_every_drop_carries_the_reason_and_an_excerpt_to_check_it_against(tmp_path: Path):
    """The decision's own words: a silent filter is a hidden editorial judgment."""
    data_dir = tmp_path / "data"
    (data_dir / "quality").mkdir(parents=True)
    result = prefilter.run_prefilter([_record(TRIBUTE)])
    payload = json.loads(prefilter.write_drop_log(result, data_dir).read_text(encoding="utf-8"))
    drop = payload["drops"][0]
    assert drop["rule"] == "ceremonial"
    assert drop["excerpt"].startswith("it is a privilege to rise today to recognize")
    assert drop["title"] == "A TITLE"
    assert drop["source"] == "congressional_record"
    assert drop["chars"] > 0


def test_a_long_excerpt_is_trimmed_so_the_log_stays_readable(tmp_path: Path):
    data_dir = tmp_path / "data"
    (data_dir / "quality").mkdir(parents=True)
    long_tribute = "Mr. X. I rise today to recognize " + ("a constituent and " * 60)
    result = prefilter.run_prefilter([_record(long_tribute)])
    payload = json.loads(prefilter.write_drop_log(result, data_dir).read_text(encoding="utf-8"))
    assert len(payload["drops"][0]["excerpt"]) == 240


# --- loading and the runner -----------------------------------------------------------


def _corpus(data_dir: Path) -> None:
    statements = data_dir / "raw" / "crec" / "statements"
    statements.mkdir(parents=True)
    (data_dir / "quality").mkdir(parents=True, exist_ok=True)
    for member_id, party, segments in (
        ("D000001", "D", [SUBSTANTIVE, TRIBUTE]),
        ("R000002", "R", ["Mr. X. I yield back the balance of my time.", SUBSTANTIVE]),
    ):
        (statements / f"{member_id}.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-10-13T00:00:00+00:00",
                    "member": {
                        "id": member_id,
                        "name": f"Member {member_id}",
                        "party": party,
                        "chamber": "house",
                        "state": "FL",
                    },
                    "window": {"start": "2023-01-03", "end": "2026-10-13"},
                    "statements": [
                        _record(*segments, member_id=member_id, granule_id=f"CREC-{member_id}")
                    ],
                }
            ),
            encoding="utf-8",
        )


def test_load_crec_reads_the_corpus_and_each_members_party_from_the_sample(tmp_path: Path):
    _corpus(tmp_path / "data")
    records, parties = prefilter.load_crec(tmp_path / "data")
    assert len(records) == 2
    assert parties == {"D000001": "D", "R000002": "R"}


def test_load_crec_says_what_to_run_when_nothing_has_been_collected(tmp_path: Path):
    with pytest.raises(prefilter.PrefilterError, match="ingest statements-crec"):
        prefilter.load_crec(tmp_path / "data")


def test_the_runner_writes_the_drop_log_and_reports(tmp_path: Path, capsys, monkeypatch):
    _corpus(tmp_path / "data")
    monkeypatch.setattr(prefilter, "repo_root", lambda: tmp_path)
    assert prefilter.run([]) == 0
    out = capsys.readouterr().out
    assert "pre-filter: 2 statements (4 turns) -> 2 kept (2 turns)" in out
    assert "ceremonial" in out and "fairness" in out
    assert "inserted material cut:" in out
    assert (tmp_path / "data" / "quality" / "statement-prefilter-drops.json").exists()


def test_the_runner_flags_an_uneven_step_in_its_own_output(tmp_path: Path, capsys, monkeypatch):
    data_dir = tmp_path / "data"
    statements = data_dir / "raw" / "crec" / "statements"
    statements.mkdir(parents=True)
    (data_dir / "quality").mkdir(parents=True)
    # Enough turns to clear the noise floor, dropped on one side only.
    (statements / "R000002.json").write_text(
        json.dumps(
            {
                "member": {
                    "id": "R000002", "name": "R", "party": "R", "chamber": "house", "state": "FL"
                },
                "statements": [
                    _record(TRIBUTE, member_id="R000002", granule_id=f"CREC-{i}")
                    for i in range(prefilter.UNEVEN_MIN_TURNS + 1)
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(prefilter, "repo_root", lambda: tmp_path)
    assert prefilter.run([]) == 0
    assert "<-- UNEVEN" in capsys.readouterr().out


def test_dry_run_writes_nothing(tmp_path: Path, capsys, monkeypatch):
    _corpus(tmp_path / "data")
    monkeypatch.setattr(prefilter, "repo_root", lambda: tmp_path)
    assert prefilter.run(["--dry-run"]) == 0
    assert "no drop log written" in capsys.readouterr().out
    assert not (tmp_path / "data" / "quality" / "statement-prefilter-drops.json").exists()


def test_the_cli_routes_to_the_prefilter(monkeypatch):
    from ingest import cli

    called: dict = {}

    def _record_argv(argv: list[str]) -> int:
        called["argv"] = argv
        return 0

    monkeypatch.setattr(prefilter, "run", _record_argv)
    assert cli.main(["prefilter", "--dry-run"]) == 0
    assert called["argv"] == ["--dry-run"]
