"""The three owner-requested checks in the count-before-spend report (2026-10-14).

Each one is a check on a decision the owner had ALREADY made, not a restatement of it, so
what is under test is that it cannot quietly fail to show him the thing he asked to see:

  * press coverage per pilot cell — a cell with none of it has a say-vs-do comparison no
    drop rate in the report can reveal, because every rate is computed over text that was
    collected;
  * a seeded random sample of Republican procedural drops in FULL text — his own check on
    the R4 ruling, which is checkable only if he can read the turns;
  * the one-liner load on decision 7's first-run allowance.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from ingest import prefilter
from tests.test_prefilter import SUBSTANTIVE, _record

QUORUM = "Mr. HAGERTY. Mr. President, I ask unanimous consent that the quorum call be rescinded."
VOTE_URGE = (
    "Mr. X. Mr. Speaker, in closing, I encourage a ``yes'' vote on this particular bill, "
    "and I yield back the balance of my time."
)


# --- the denominator ------------------------------------------------------------------


def test_a_statement_with_no_turns_still_counts_once_in_the_denominator():
    """With `len(segments)` alone such a record adds 1 to a rule's numerator and 0 to the
    denominator. Measured 2026-10-14 on a part-collected corpus, the
    `no-attributable-text` row read 112.8% — a number that cannot mean anything, in the
    table the owner is asked to judge fairness by."""
    assert prefilter.judged_units(_record(SUBSTANTIVE)) == 1
    assert prefilter.judged_units(_record(SUBSTANTIVE, QUORUM)) == 2
    empty = _record()
    empty["segments"] = []
    assert prefilter.judged_units(empty) == 1


def test_no_drop_rate_can_exceed_one_hundred_percent():
    records = []
    for i in range(4):
        record = _record(member_id="D000001", granule_id=f"G{i}", attribution="none")
        record["segments"] = []
        records.append(record)
    result = prefilter.run_prefilter(records)
    rows = prefilter.fairness(records, result["drops"], {"D000001": "D"})
    row = next(r for r in rows if r["rule"] == "no-attributable-text")
    assert row["D_rate"] == 100.0


# --- the audit sample -----------------------------------------------------------------


def _procedural_corpus(n: int = 40, party_member: str = "R000002") -> list[dict]:
    return [
        _record(
            QUORUM,
            member_id=party_member,
            granule_id=f"G{i:03d}",
            date=f"2025-01-{i % 28 + 1:02d}",
        )
        for i in range(n)
    ]


def test_the_sample_is_twenty_republican_procedural_drops_in_full_text():
    records = _procedural_corpus()
    result = prefilter.run_prefilter(records)
    sample = prefilter.sample_procedural_drops(records, result["drops"], {"R000002": "R"})
    assert len(sample) == prefilter.PROCEDURAL_AUDIT_SIZE
    assert all(d["member_id"] == "R000002" for d in sample)
    assert all(d["sub_rule"] == "quorum-call" for d in sample)
    # The WHOLE turn, read back from the corpus — not the drop log's shortened excerpt,
    # and with the speaker name and salutation stripped the way the rule read it.
    assert all(d["text"].startswith("I ask unanimous consent") for d in sample)


def test_the_sample_is_seeded_so_the_owner_can_re_draw_the_identical_twenty():
    """A hand-picked sample would prove nothing, and an unseeded one could not be checked
    for having been picked."""
    records = _procedural_corpus()
    drops = prefilter.run_prefilter(records)["drops"]
    first = prefilter.sample_procedural_drops(records, drops, {"R000002": "R"})
    again = prefilter.sample_procedural_drops(records, drops, {"R000002": "R"})
    assert [d["statement_id"] for d in first] == [d["statement_id"] for d in again]


def test_a_different_seed_draws_a_different_twenty():
    """Proof the sample is actually random rather than the first twenty."""
    records = _procedural_corpus()
    drops = prefilter.run_prefilter(records)["drops"]
    a = prefilter.sample_procedural_drops(records, drops, {"R000002": "R"}, seed=1)
    b = prefilter.sample_procedural_drops(records, drops, {"R000002": "R"}, seed=2)
    assert [d["statement_id"] for d in a] != [d["statement_id"] for d in b]


def test_the_sample_takes_everything_when_there_are_fewer_than_twenty():
    records = _procedural_corpus(n=3)
    drops = prefilter.run_prefilter(records)["drops"]
    assert len(prefilter.sample_procedural_drops(records, drops, {"R000002": "R"})) == 3


def test_the_sample_is_empty_when_the_party_has_no_procedural_drops():
    records = [_record(SUBSTANTIVE, member_id="R000002", granule_id="G1")]
    drops = prefilter.run_prefilter(records)["drops"]
    assert prefilter.sample_procedural_drops(records, drops, {"R000002": "R"}) == []


def test_the_sample_only_draws_the_party_asked_for():
    records = _procedural_corpus(n=5, party_member="R000002") + _procedural_corpus(
        n=5, party_member="D000001"
    )
    drops = prefilter.run_prefilter(records)["drops"]
    parties = {"R000002": "R", "D000001": "D"}
    assert all(
        d["member_id"] == "D000001"
        for d in prefilter.sample_procedural_drops(records, drops, parties, party="D")
    )


def test_a_drop_whose_record_cannot_be_found_falls_back_to_its_logged_excerpt():
    """The log is the audit of record; a sample that silently dropped a row the corpus no
    longer holds would be a sample of a different thing."""
    records = _procedural_corpus(n=1)
    drops = prefilter.run_prefilter(records)["drops"]
    sample = prefilter.sample_procedural_drops([], drops, {"R000002": "R"})
    assert len(sample) == 1
    assert sample[0]["text"] == drops[0]["excerpt"]


def test_the_report_carries_the_sample_in_full_with_its_seed():
    records = _procedural_corpus()
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], _AI_CONFIG)
    text = prefilter.render_spend_report(
        records, result, {"R000002": "R"}, {"R000002": "A Republican"}, estimate
    )
    assert "## Audit sample — 20 Republican procedural drops" in text
    assert "if any of these argue policy, the rule is too wide" in text
    assert f"seed `{prefilter.PROCEDURAL_AUDIT_SEED}`" in text
    assert text.count("I ask unanimous consent that the quorum call be rescinded.") == 20


def test_the_report_says_so_when_there_is_nothing_to_audit():
    records = [_record(SUBSTANTIVE, member_id="D000001", granule_id="G1")]
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], _AI_CONFIG)
    text = prefilter.render_spend_report(records, result, {"D000001": "D"}, {}, estimate)
    assert "No Republican procedural drops in this corpus." in text


# --- the one-liner load ---------------------------------------------------------------

_AI_CONFIG = {
    "per_run_cost_cap_usd": 5.00,
    "max_statements_per_member_per_run": 25,
    "prices": {
        "claude-haiku-5-5": {"input": 0.10, "output": 0.50},
        "claude-opus-5-5": {"input": 4.00, "output": 20.00},
    },
    "tasks": {
        "triage_statement": {"model": "claude-haiku-5-5"},
        "categorize_statement": {"model": "claude-opus-5-5"},
    },
}


def test_a_statement_is_measured_the_way_the_rules_measure_a_turn():
    """Speaker name and salutation stripped, line wraps flattened — so "the procedural
    rule kept it" and "it is a one-liner" are the same measurement."""
    record = _record("Mr. BILIRAKIS. Mr. Speaker, I rise today.")
    survivor, _ = prefilter.apply_to_statement(record, {})
    assert survivor is not None
    assert prefilter.statement_content_chars(survivor) == len("I rise today.")


def test_a_member_whose_allowance_is_mostly_one_liners_is_flagged():
    survivors = []
    for i in range(10):
        text = VOTE_URGE if i < 6 else f"{SUBSTANTIVE} number {i}"
        record = _record(text, member_id="R000002", granule_id=f"G{i}", date=f"2025-01-{i + 1:02d}")
        survivor, _ = prefilter.apply_to_statement(record, {})
        assert survivor is not None
        survivors.append(survivor)
    rows = prefilter.short_statement_load(survivors, 25)
    assert rows[0]["to_categorizer"] == 10
    assert rows[0]["short"] == 6
    assert rows[0]["majority_short"] is True


def test_a_member_with_argued_speeches_is_not_flagged():
    survivors = []
    for i in range(10):
        text = VOTE_URGE if i < 4 else f"{SUBSTANTIVE} number {i}"
        record = _record(text, member_id="R000002", granule_id=f"G{i}", date=f"2025-01-{i + 1:02d}")
        survivor, _ = prefilter.apply_to_statement(record, {})
        assert survivor is not None
        survivors.append(survivor)
    rows = prefilter.short_statement_load(survivors, 25)
    assert rows[0]["short"] == 4
    assert rows[0]["majority_short"] is False


def test_the_threshold_is_half_of_what_the_member_brings_not_half_of_the_cap():
    """A member with six statements is not flagged for having four short ones out of a
    25 allowance they never filled — nor spared because four is under half of 25."""
    survivors = []
    for i in range(6):
        text = VOTE_URGE if i < 4 else f"{SUBSTANTIVE} number {i}"
        record = _record(text, member_id="R000002", granule_id=f"G{i}", date=f"2025-01-{i + 1:02d}")
        survivor, _ = prefilter.apply_to_statement(record, {})
        assert survivor is not None
        survivors.append(survivor)
    rows = prefilter.short_statement_load(survivors, 25)
    assert rows[0]["to_categorizer"] == 6
    assert rows[0]["majority_short"] is True


def test_only_the_newest_within_the_cap_are_measured():
    """Decision 7 sends the NEWEST n, so older statements are not part of this run's
    allowance and must not move the count."""
    survivors = []
    for i, (date, text) in enumerate(
        [("2026-01-01", SUBSTANTIVE), ("2023-01-01", VOTE_URGE)]
    ):
        record = _record(text, member_id="R000002", granule_id=f"G{i}", date=date)
        survivor, _ = prefilter.apply_to_statement(record, {})
        assert survivor is not None
        survivors.append(survivor)
    rows = prefilter.short_statement_load(survivors, 1)
    assert rows[0]["to_categorizer"] == 1
    assert rows[0]["short"] == 0


def test_a_statement_the_ai_never_sees_is_not_part_of_the_allowance():
    record = _record(
        "Mr. COSTA. Mr. Speaker, I was unable to attend. Had I been present, I would "
        "have voted YEA on Roll Call No. 559.",
        member_id="R000002",
    )
    survivor, _ = prefilter.apply_to_statement(record, {})
    assert survivor is not None and survivor["ai_eligible"] is False
    assert prefilter.short_statement_load([survivor], 25) == []


def test_the_report_names_the_flagged_members_and_the_threshold():
    survivors = []
    for i in range(4):
        record = _record(
            VOTE_URGE, member_id="R000002", granule_id=f"G{i}", date=f"2025-01-0{i + 1}"
        )
        survivor, _ = prefilter.apply_to_statement(record, {})
        assert survivor is not None
        survivors.append(survivor)
    result = {
        "statements_in": 4,
        "statements_kept": 4,
        "turns_in": 4,
        "turns_kept": 4,
        "statements": survivors,
        "drops": [],
    }
    estimate = prefilter.estimate_spend(survivors, _AI_CONFIG)
    text = prefilter.render_spend_report(
        survivors, result, {"R000002": "R"}, {"R000002": "A Republican"}, estimate
    )
    assert "## One-liners in the first run's allowance" in text
    assert "**MOSTLY ONE-LINERS**" in text
    assert "1 member(s) flagged" in text
    assert "not a proposal to drop them" in text.replace("It is not", "not")


def test_the_report_says_so_when_no_member_is_flagged():
    record = _record(SUBSTANTIVE, member_id="D000001", granule_id="G1")
    result = prefilter.run_prefilter([record])
    estimate = prefilter.estimate_spend(result["statements"], _AI_CONFIG)
    text = prefilter.render_spend_report(
        [record], result, {"D000001": "D"}, {}, estimate
    )
    assert "No member is flagged" in text


# --- press coverage per pilot cell ----------------------------------------------------


def _pilot_and_index(
    data_dir: Path,
    *,
    walks: list[dict],
    refused: list[dict],
    no_list: list[dict] | None = None,
) -> None:
    (data_dir / "config").mkdir(parents=True, exist_ok=True)
    (data_dir / "raw" / "press").mkdir(parents=True, exist_ok=True)
    (data_dir / "config" / "statement-pilot.yaml").write_text(
        yaml.safe_dump(
            {
                "cells": [
                    {
                        "party": "D",
                        "chamber": "senate",
                        "members": [
                            {"id": "H001046", "name": "Martin Heinrich", "state": "NM"},
                            {"id": "K000377", "name": "Mark Kelly", "state": "AZ"},
                        ],
                    },
                    {
                        "party": "R",
                        "chamber": "senate",
                        "members": [
                            {"id": "H000601", "name": "Bill Hagerty", "state": "TN"},
                            {"id": "Y000064", "name": "Todd Young", "state": "IN"},
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "raw" / "press" / "index.json").write_text(
        json.dumps({"walks": walks, "refused": refused, "no_list": no_list or []}),
        encoding="utf-8",
    )


def test_a_cell_whose_every_row_fails_is_named_as_zero_coverage(tmp_path: Path):
    """All four Senate Democrats in the real pilot are non-collecting — three refused and
    one empty by markup — so that cell's "say" side rests on the Congressional Record
    alone, and no drop rate in the report can show it."""
    data_dir = tmp_path / "data"
    _pilot_and_index(
        data_dir,
        walks=[
            {"member_id": "K000377", "releases": 0, "pages_read": 1, "stopped": "empty"},
            {"member_id": "H000601", "releases": 578, "pages_read": 117, "stopped": "window"},
            {"member_id": "Y000064", "releases": 20, "pages_read": 1, "stopped": "single-page"},
        ],
        refused=[{"id": "H001046", "name": "Martin Heinrich", "reason": "owner_checked: false"}],
    )
    coverage = prefilter.press_coverage(data_dir)
    cells = {(c["party"], c["chamber"]): c for c in coverage["cells"]}

    senate_d = cells[("D", "senate")]
    assert senate_d["releases"] == 0
    assert senate_d["zero_coverage"] is True
    assert (senate_d["refused"], senate_d["empty"], senate_d["collected"]) == (1, 1, 0)

    senate_r = cells[("R", "senate")]
    assert senate_r["releases"] == 598
    assert senate_r["zero_coverage"] is False
    assert (senate_r["collected"], senate_r["single_page"]) == (1, 1)

    assert [r["id"] for r in coverage["non_collecting"]] == ["H001046", "K000377"]
    assert coverage["non_collecting"][0]["chamber"] == "senate"
    assert "owner_checked: false" in coverage["non_collecting"][0]["reason"]
    assert "not in the HTML" in coverage["non_collecting"][1]["reason"]


def test_a_single_page_walk_counts_its_releases_but_not_as_collected(tmp_path: Path):
    """It collected something, so the cell is not zero-coverage; it may be truncated, so
    it is not COMPLETE either."""
    data_dir = tmp_path / "data"
    _pilot_and_index(
        data_dir,
        walks=[
            {"member_id": "K000377", "releases": 7, "pages_read": 1, "stopped": "single-page"}
        ],
        refused=[{"id": "H001046", "name": "Martin Heinrich", "reason": "owner_checked: false"}],
    )
    cell = next(
        c for c in prefilter.press_coverage(data_dir)["cells"] if c["chamber"] == "senate"
    )
    assert cell["single_page"] == 1
    assert cell["collected"] == 0
    assert cell["zero_coverage"] is False


def test_an_errored_or_repeated_walk_is_reported_with_its_own_reason(tmp_path: Path):
    data_dir = tmp_path / "data"
    _pilot_and_index(
        data_dir,
        walks=[
            {
                "member_id": "K000377",
                "releases": 4,
                "pages_read": 2,
                "stopped": "repeat",
                "detail": "page 1 repeats a page already read",
            }
        ],
        refused=[],
    )
    coverage = prefilter.press_coverage(data_dir)
    row = next(r for r in coverage["non_collecting"] if r["id"] == "K000377")
    assert "repeat" in row["reason"]
    assert "repeats a page already read" in row["reason"]


def test_a_pilot_row_absent_from_the_index_is_reported_not_ignored(tmp_path: Path):
    """A member who was never walked must not read as a member who published nothing."""
    data_dir = tmp_path / "data"
    _pilot_and_index(data_dir, walks=[], refused=[])
    coverage = prefilter.press_coverage(data_dir)
    assert {r["id"] for r in coverage["non_collecting"]} == {
        "H001046",
        "K000377",
        "H000601",
        "Y000064",
    }
    assert all("not walked" in r["reason"] for r in coverage["non_collecting"])


def test_no_press_index_at_all_is_said_plainly_rather_than_shown_as_zeros(tmp_path: Path):
    coverage = prefilter.press_coverage(tmp_path / "data")
    assert coverage == {
        "cells": [],
        "non_collecting": [],
        "no_list": [],
        "available": False,
    }


# --- a row whose site publishes no press-release list (STATUS step 6) -----------------

MILLER = {
    "id": "K000377",
    "reason": "site has no press-release list",
    "urls_tried": [
        "https://maxmiller.house.gov/press-releases",
        "https://maxmiller.house.gov/news",
    ],
}


def test_a_sitemap_walk_counts_as_collected_not_as_a_failure(tmp_path: Path):
    """`K000377` walks the press-release sitemap his own site publishes, which enumerates
    the whole archive. Listing a member collected in full under "not collecting" would be
    the worst misreport this table can make — in the one report the owner approves spend
    against. The complete-stop set is imported from the collector, not copied."""
    data_dir = tmp_path / "data"
    _pilot_and_index(
        data_dir,
        walks=[
            {
                "member_id": "K000377",
                "releases": 1082,
                "pages_read": 2,
                "stopped": "sitemap",
                "detail": "1495 URL(s) in 2 sitemap(s); 413 outside the window",
            }
        ],
        refused=[],
    )
    coverage = prefilter.press_coverage(data_dir)
    cell = next(c for c in coverage["cells"] if c["party"] == "D")
    assert (cell["collected"], cell["releases"]) == (1, 1082)
    # Every other row in the fixture is absent from its walks, so each is reported as
    # not walked — K000377 is the only one this test says anything about.
    assert "K000377" not in [r["id"] for r in coverage["non_collecting"]]
    assert all("not walked" in r["reason"] for r in coverage["non_collecting"])
    assert "sitemap" in prefilter.COMPLETE_STOPS


def test_a_row_with_no_press_list_is_never_counted_as_a_collection_failure(tmp_path: Path):
    """STATUS step 6. `M001222` Miller's site publishes no press-release list, so his
    zero is the site's and not ours: counted in its own column, kept out of the failure
    counts, and kept out of the "not collecting" list entirely. (The pilot fixture here
    carries him in `K000377`'s seat — what is under test is the flag, not the member.)"""
    data_dir = tmp_path / "data"
    _pilot_and_index(
        data_dir,
        walks=[
            {"member_id": "H001046", "releases": 9, "pages_read": 2, "stopped": "window"},
            {"member_id": "H000601", "releases": 578, "pages_read": 117, "stopped": "window"},
            {"member_id": "Y000064", "releases": 20, "pages_read": 1, "stopped": "single-page"},
        ],
        refused=[],
        no_list=[MILLER],
    )
    coverage = prefilter.press_coverage(data_dir)
    cell = next(c for c in coverage["cells"] if c["party"] == "D")
    assert cell["no_list"] == 1
    assert (cell["empty"], cell["refused"], cell["other"]) == (0, 0, 0)
    assert cell["collected"] == 1
    assert [r["id"] for r in coverage["non_collecting"]] == []
    assert coverage["no_list"] == [
        {
            "id": "K000377",
            "name": "Mark Kelly",
            "party": "D",
            "chamber": "senate",
            "reason": MILLER["reason"],
            "urls_tried": MILLER["urls_tried"],
        }
    ]


def test_the_no_list_flag_beats_a_walk_that_also_mentions_the_row(tmp_path: Path):
    """An index can carry both — a stale walk and the owner's finding. "No list exists"
    wins: it is the owner's own screening of the site, and the walk cannot have read a
    list that is not there."""
    data_dir = tmp_path / "data"
    _pilot_and_index(
        data_dir,
        walks=[{"member_id": "K000377", "releases": 0, "pages_read": 1, "stopped": "empty"}],
        refused=[{"id": "K000377", "name": "Mark Kelly", "reason": "owner_checked: false"}],
        no_list=[MILLER],
    )
    cell = next(c for c in prefilter.press_coverage(data_dir)["cells"] if c["party"] == "D")
    assert (cell["no_list"], cell["empty"], cell["refused"]) == (1, 0, 0)


def test_a_zero_coverage_cell_does_not_blame_a_row_that_has_no_list(tmp_path: Path):
    """The failure count holds the no-list row out: counting it among the failures would
    make the cell look worse than it is while hiding the one true thing about it."""
    data_dir = tmp_path / "data"
    _pilot_and_index(
        data_dir,
        walks=[{"member_id": "H000601", "releases": 5, "pages_read": 2, "stopped": "window"}],
        refused=[{"id": "H001046", "name": "Martin Heinrich", "reason": "owner_checked: false"}],
        no_list=[MILLER],
    )
    coverage = prefilter.press_coverage(data_dir)
    records = [_record(SUBSTANTIVE, member_id="H000601", granule_id="G1")]
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], _AI_CONFIG)
    text = prefilter.render_spend_report(
        records, result, {"H000601": "R"}, {}, estimate, coverage
    )
    assert "**The D senate cell has ZERO press coverage.** 1 of its 2 rows fail" in text
    assert "1 of that cell's rows publish no press-release list at all" in text
    assert "not one of the failures above and is not counted as one" in text
    assert "### Rows with no press-release list at all" in text
    assert "**Mark Kelly** (`K000377`) — D senate — site has no press-release list" in text
    assert "    * <https://maxmiller.house.gov/news>" in text
    assert "| No list exists |" in text
    # Never in the failure table.
    assert "| Mark Kelly (`K000377`) | D | senate |" not in text


def test_the_report_says_so_when_every_row_has_a_list(tmp_path: Path):
    data_dir = tmp_path / "data"
    _pilot_and_index(
        data_dir,
        walks=[
            {"member_id": m, "releases": 5, "pages_read": 2, "stopped": "window"}
            for m in ("H001046", "K000377", "H000601", "Y000064")
        ],
        refused=[],
    )
    records = [_record(SUBSTANTIVE, member_id="H000601", granule_id="G1")]
    result = prefilter.run_prefilter(records)
    text = prefilter.render_spend_report(
        records,
        result,
        {"H000601": "R"},
        {},
        prefilter.estimate_spend(result["statements"], _AI_CONFIG),
        prefilter.press_coverage(data_dir),
    )
    assert "None: every row in the pilot has a press-release list to read." in text


def test_the_report_puts_coverage_first_and_names_the_empty_cell(tmp_path: Path):
    data_dir = tmp_path / "data"
    _pilot_and_index(
        data_dir,
        walks=[
            {"member_id": "K000377", "releases": 0, "pages_read": 1, "stopped": "empty"},
            {"member_id": "H000601", "releases": 578, "pages_read": 117, "stopped": "window"},
            {"member_id": "Y000064", "releases": 20, "pages_read": 1, "stopped": "single-page"},
        ],
        refused=[{"id": "H001046", "name": "Martin Heinrich", "reason": "owner_checked: false"}],
    )
    records = [_record(SUBSTANTIVE, member_id="H000601", granule_id="G1")]
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], _AI_CONFIG)
    text = prefilter.render_spend_report(
        records,
        result,
        {"H000601": "R"},
        {},
        estimate,
        prefilter.press_coverage(data_dir),
    )
    # First, before the funnel: a cell with no coverage changes how everything after it
    # should be read.
    assert text.index("Press coverage per pilot cell") < text.index("## The funnel")
    assert "**The D senate cell has ZERO press coverage.**" in text
    assert "Martin Heinrich (`H001046`)" in text
    assert "a press office and a floor speech are not the same voice" in text


def test_the_report_says_so_when_every_cell_has_coverage(tmp_path: Path):
    data_dir = tmp_path / "data"
    _pilot_and_index(
        data_dir,
        walks=[
            {"member_id": "H001046", "releases": 5, "pages_read": 2, "stopped": "window"},
            {"member_id": "K000377", "releases": 5, "pages_read": 2, "stopped": "window"},
            {"member_id": "H000601", "releases": 5, "pages_read": 2, "stopped": "window"},
            {"member_id": "Y000064", "releases": 5, "pages_read": 2, "stopped": "window"},
        ],
        refused=[],
    )
    coverage = prefilter.press_coverage(data_dir)
    records = [_record(SUBSTANTIVE, member_id="H000601", granule_id="G1")]
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], _AI_CONFIG)
    text = prefilter.render_spend_report(
        records, result, {"H000601": "R"}, {}, estimate, coverage
    )
    assert "Every cell has some press coverage." in text
    assert "None: every row in the pilot collects." in text


def test_the_report_says_plainly_when_the_collector_has_not_run():
    records = [_record(SUBSTANTIVE, member_id="D000001", granule_id="G1")]
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], _AI_CONFIG)
    text = prefilter.render_spend_report(records, result, {"D000001": "D"}, {}, estimate)
    assert "collector (a) has not run" in text
