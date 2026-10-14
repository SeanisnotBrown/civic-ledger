"""§5 Phase 3 owner decision 4 — the count-before-spend report. No AI, no network.

The report is the thing the owner approves an AI run against, so what is under test is
that it cannot quietly omit any of the four things the decision names: counts per source,
counts per member, counts after each filter step, and the per-party drop rate at each step
with the uneven flag — plus the estimated bill against the cap.

The companion file `test_prefilter.py` covers the rules themselves.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ingest import prefilter
from tests.test_prefilter import SUBSTANTIVE, TRIBUTE, _corpus, _record

AI_CONFIG = {
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


def _survivor(member_id: str, date: str, text: str, *, eligible: bool = True) -> dict:
    record = _record(text, member_id=member_id, date=date, granule_id=f"G-{member_id}-{date}")
    survivor, _ = prefilter.apply_to_statement(record, {})
    assert survivor is not None
    survivor["ai_eligible"] = eligible
    return survivor


def _press(record: dict) -> dict:
    return {**record, "source": "member_press", "attribution": "press-office"}


def _ai_yaml(data_dir: Path, config: dict) -> None:
    (data_dir / "config").mkdir(parents=True, exist_ok=True)
    (data_dir / "config" / "ai.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")


# --- loading every collector at once --------------------------------------------------


def test_both_collectors_outputs_load_into_one_pass(tmp_path: Path):
    """The cross-source duplicate rule only works if both sources are in the same pass."""
    data_dir = tmp_path / "data"
    _corpus(data_dir)
    press_dir = data_dir / "raw" / "press" / "statements"
    press_dir.mkdir(parents=True)
    (press_dir / "D000001.json").write_text(
        json.dumps(
            {
                "member": {
                    "id": "D000001",
                    "name": "Member D000001",
                    "party": "D",
                    "chamber": "house",
                    "state": "FL",
                },
                "statements": [
                    _press(_record(SUBSTANTIVE, member_id="D000001", granule_id="/p/a-slug"))
                ],
            }
        ),
        encoding="utf-8",
    )
    records, parties, names = prefilter.load_all(data_dir)
    assert len(records) == 3
    assert {r["source"] for r in records} == {"congressional_record", "member_press"}
    assert parties == {"D000001": "D", "R000002": "R"}
    assert names["D000001"] == "Member D000001"


def test_a_collector_that_has_not_run_contributes_nothing_and_is_not_an_error(tmp_path: Path):
    """(c) waits on campaign URLs and (d) on platform access."""
    _corpus(tmp_path / "data")
    records, _, _ = prefilter.load_all(tmp_path / "data")
    assert len(records) == 2


def test_no_collector_output_at_all_says_what_to_run(tmp_path: Path):
    with pytest.raises(prefilter.PrefilterError, match="statements-press"):
        prefilter.load_all(tmp_path / "data")


# --- the estimate ---------------------------------------------------------------------


def test_the_estimate_prices_both_gates_from_the_committed_prices():
    survivors = [_survivor("D000001", "2026-01-01", SUBSTANTIVE)]
    estimate = prefilter.estimate_spend(survivors, AI_CONFIG)
    assert estimate["triage_statements"] == 1
    assert estimate["categorize_statements"] == 1
    assert estimate["triage_usd"] > 0
    assert estimate["categorize_usd"] > estimate["triage_usd"]
    assert estimate["cap_usd"] == 5.0
    assert estimate["over_cap"] is False


def test_a_vote_explanation_is_never_priced():
    """R3: kept as record, never categorized, so it must not appear in the bill."""
    survivors = [
        _survivor("D000001", "2026-01-01", SUBSTANTIVE),
        _survivor("D000001", "2026-01-02", SUBSTANTIVE + " two", eligible=False),
    ]
    estimate = prefilter.estimate_spend(survivors, AI_CONFIG)
    assert estimate["triage_statements"] == 1
    assert estimate["categorize_statements"] == 1
    assert estimate["ineligible"] == 1


def test_the_per_member_cap_bounds_the_categorizer_and_keeps_it_even():
    """Decision 7: each member's NEWEST 25 only, so no prolific press office consumes the
    run at the expense of a quiet one."""
    config = {**AI_CONFIG, "max_statements_per_member_per_run": 2}
    survivors = [
        _survivor("D000001", f"2026-01-0{i}", f"{SUBSTANTIVE} number {i}") for i in range(1, 6)
    ] + [_survivor("R000002", "2026-01-01", SUBSTANTIVE + " other member")]
    estimate = prefilter.estimate_spend(survivors, config)
    assert estimate["triage_statements"] == 6
    assert estimate["categorize_statements"] == 3  # 2 for the prolific one, 1 for the quiet


def test_the_cap_takes_each_members_newest():
    config = {**AI_CONFIG, "max_statements_per_member_per_run": 1}
    survivors = [
        _survivor("D000001", "2023-05-05", SUBSTANTIVE + " older"),
        _survivor("D000001", "2026-05-05", SUBSTANTIVE + " newest"),
    ]
    assert prefilter.estimate_spend(survivors, config)["categorize_statements"] == 1


def test_an_estimate_over_the_cap_is_flagged_rather_than_run():
    """Decision 9: the builder never raises the cap unasked."""
    config = {**AI_CONFIG, "per_run_cost_cap_usd": 0.001}
    estimate = prefilter.estimate_spend([_survivor("D1", "2026-01-01", SUBSTANTIVE)], config)
    assert estimate["over_cap"] is True


# --- the report -----------------------------------------------------------------------


def test_the_report_carries_everything_decision_4_asks_for():
    records = [
        _record(SUBSTANTIVE, member_id="D000001", granule_id="G1"),
        _record(TRIBUTE, member_id="R000002", granule_id="G2"),
        _press(_record(SUBSTANTIVE + " press", member_id="D000001", granule_id="/p/a")),
    ]
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], AI_CONFIG)
    text = prefilter.render_spend_report(
        records,
        result,
        {"D000001": "D", "R000002": "R"},
        {"D000001": "A Democrat", "R000002": "A Republican"},
        estimate,
    )
    assert "No AI call has been made" in text
    assert "## The funnel" in text
    assert "## Per source" in text and "`member_press`" in text
    assert "## Per member" in text and "A Democrat (D000001)" in text
    assert "## Fairness at each filter step" in text
    assert "## Estimated cost" in text
    assert "Cap (`per_run_cost_cap_usd`)" in text
    # A yes to spend is not a yes to publish.
    assert "Q-K" in text


def test_the_report_breaks_the_flagged_step_down_to_its_sub_rules():
    """R4's condition for accepting the uneven procedural rate."""
    records = [
        _record(
            "Mr. X. Mr. Speaker, I suggest the absence of a quorum.",
            member_id="R000002",
            granule_id=f"G{i}",
        )
        for i in range(prefilter.UNEVEN_MIN_TURNS + 1)
    ]
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], AI_CONFIG)
    text = prefilter.render_spend_report(
        records, result, {"R000002": "R"}, {"R000002": "A Republican"}, estimate
    )
    assert "**UNEVEN**" in text
    assert "on condition that the" in text
    assert "`quorum-call`" in text


def test_the_report_says_so_when_no_step_is_flagged():
    records = [_record(SUBSTANTIVE, member_id="D000001", granule_id="G1")]
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], AI_CONFIG)
    text = prefilter.render_spend_report(records, result, {"D000001": "D"}, {}, estimate)
    assert "No step is flagged." in text


def test_the_report_names_the_cap_verdict_both_ways():
    records = [_record(SUBSTANTIVE, member_id="D000001", granule_id="G1")]
    result = prefilter.run_prefilter(records)
    under = prefilter.render_spend_report(
        records,
        result,
        {"D000001": "D"},
        {},
        prefilter.estimate_spend(result["statements"], AI_CONFIG),
    )
    assert "**Under the cap.**" in under
    over = prefilter.render_spend_report(
        records,
        result,
        {"D000001": "D"},
        {},
        prefilter.estimate_spend(
            result["statements"], {**AI_CONFIG, "per_run_cost_cap_usd": 0.0001}
        ),
    )
    assert "**OVER THE CAP.**" in over
    assert "never raises it unasked" in over


# --- the runner -----------------------------------------------------------------------


def test_the_report_run_writes_the_report_and_makes_no_ai_call(
    tmp_path: Path, capsys, monkeypatch
):
    data_dir = tmp_path / "data"
    _corpus(data_dir)
    _ai_yaml(data_dir, AI_CONFIG)
    monkeypatch.setattr(prefilter, "repo_root", lambda: tmp_path)

    assert prefilter.run(["--report"]) == 0
    out = capsys.readouterr().out
    assert "estimate: $" in out
    assert "NO AI CALL MADE" in out
    reports = list((tmp_path / "docs" / "research").glob("*-count-before-spend.md"))
    assert len(reports) == 1
    assert "count before spend" in reports[0].read_text(encoding="utf-8").lower()


def test_the_report_run_flags_an_over_cap_estimate_in_its_own_output(
    tmp_path: Path, capsys, monkeypatch
):
    data_dir = tmp_path / "data"
    _corpus(data_dir)
    _ai_yaml(data_dir, {**AI_CONFIG, "per_run_cost_cap_usd": 0.0001})
    monkeypatch.setattr(prefilter, "repo_root", lambda: tmp_path)
    assert prefilter.run(["--report"]) == 0
    assert "OVER THE CAP" in capsys.readouterr().out


def test_the_report_splits_the_fairness_table_by_source():
    """The rules do not bite equally on the two sources, and press volumes differ sharply
    by member, so a combined rate can show a party skew that is really a source skew."""
    records = [
        _record(TRIBUTE, member_id="D000001", granule_id=f"G{i}") for i in range(30)
    ] + [
        _press(_record(f"{SUBSTANTIVE} press {i}", member_id="R000002", granule_id=f"/p/{i}"))
        for i in range(30)
    ]
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], AI_CONFIG)
    text = prefilter.render_spend_report(
        records, result, {"D000001": "D", "R000002": "R"}, {}, estimate
    )
    assert "### The same rates, per source" in text
    assert "| `congressional_record` | `ceremonial` |" in text
    assert "| `member_press` | `ceremonial` |" in text


def test_a_single_source_corpus_gets_no_per_source_table():
    """One source needs no split, and an extra table of the same numbers is noise."""
    records = [_record(SUBSTANTIVE, member_id="D000001", granule_id="G1")]
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], AI_CONFIG)
    text = prefilter.render_spend_report(records, result, {"D000001": "D"}, {}, estimate)
    assert "### The same rates, per source" not in text


def test_the_per_source_rates_count_only_that_sources_turns():
    records = [_record(TRIBUTE, member_id="D000001", granule_id="G1")] + [
        _press(_record(SUBSTANTIVE, member_id="D000001", granule_id="/p/a"))
    ]
    result = prefilter.run_prefilter(records)
    crec = prefilter.fairness(
        records, result["drops"], {"D000001": "D"}, source="congressional_record"
    )
    press = prefilter.fairness(
        records, result["drops"], {"D000001": "D"}, source="member_press"
    )
    assert next(r for r in crec if r["rule"] == "ceremonial")["D_rate"] == 100.0
    assert next(r for r in press if r["rule"] == "ceremonial")["D_rate"] == 0.0
