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


# --- unreadable press bodies are the collector's failures, not the filter's drops -----

LOGISTICS = "I will host a town hall in Pasco County on Thursday evening."


def _unreadable(member_id: str, slug: str) -> dict:
    """A press record whose page had no readable body: collector (a) writes it with no
    turns and lists its URL under `text_failures` in its index."""
    record = _press(_record(member_id=member_id, granule_id=f"/p/{slug}"))
    record["url"] = f"https://x.house.gov/press/{slug}"
    return record


def test_an_unreadable_press_body_is_a_collection_failure_not_a_drop():
    """Measured 2026-10-20: 182 of these were logged as `no-attributable-text` and tripped
    its uneven flag. They are set aside before the filter, never judged."""
    unreadable = _unreadable("D000001", "no-body")
    records = [_record(SUBSTANTIVE, member_id="D000001", granule_id="G1"), unreadable]
    result = prefilter.run_prefilter(records, frozenset({("D000001", unreadable["url"])}))
    assert result["drops"] == []
    assert result["statements_unreadable"] == 1
    assert result["collection_failures"] == [
        {
            "member_id": "D000001",
            "date": "2025-06-03",
            "source": "member_press",
            "url": unreadable["url"],
            "reason": "no-readable-body",
        }
    ]
    assert unreadable not in result["judged_records"]
    assert result["statements_in"] == 2 and result["statements_kept"] == 1


def test_an_empty_press_record_that_is_not_a_recorded_failure_stops_the_run():
    """The collector's index and its statements disagree; which is wrong is not a guess."""
    unreadable = _unreadable("D000001", "no-body")
    with pytest.raises(prefilter.PrefilterError, match="NOT among the collector's recorded"):
        prefilter.run_prefilter([unreadable])
    with pytest.raises(prefilter.PrefilterError, match="no-body"):
        prefilter.run_prefilter([unreadable], frozenset({("R000002", unreadable["url"])}))


def test_an_empty_record_turn_still_means_no_attributable_text():
    """`no-attributable-text` keeps its original Record meaning, failures set or not."""
    record = _record(member_id="D000001", granule_id="G1")
    result = prefilter.run_prefilter([record], frozenset({("D000001", "https://other")}))
    assert [d["rule"] for d in result["drops"]] == ["no-attributable-text"]
    assert result["collection_failures"] == []


def test_the_text_failures_come_from_each_collectors_own_index(tmp_path: Path):
    raw = tmp_path / "data" / "raw"
    (raw / "press").mkdir(parents=True)
    (raw / "press" / "index.json").write_text(
        json.dumps(
            {
                "text_failures": [
                    {"id": "D000001", "url": "https://x/a", "error": "HTTPStatusError"},
                    {"id": "D000001", "url": "https://x/a", "error": "no body text"},
                    {"id": "R000002", "url": "https://x/b", "error": "no body text"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (raw / "crec").mkdir()
    (raw / "crec" / "index.json").write_text(json.dumps({"issues": 3}), encoding="utf-8")
    assert prefilter.load_text_failures(tmp_path / "data") == frozenset(
        {("D000001", "https://x/a"), ("R000002", "https://x/b")}
    )
    assert prefilter.load_text_failures(tmp_path / "nothing") == frozenset()


def _unreadable_corpus() -> tuple[list[dict], frozenset]:
    """60 unreadable Democratic press bodies against none on the Republican side: enough
    to trip the uneven flag if they were counted as drops."""
    bad = [_unreadable("D000001", f"no-body-{i}") for i in range(60)]
    good = [
        _press(_record(f"{SUBSTANTIVE} {who} {i}", member_id=who, granule_id=f"/p/{who}{i}"))
        for i in range(30)
        for who in ("D000001", "R000002")
    ]
    return bad + good, frozenset(("D000001", r["url"]) for r in bad)


def test_the_report_lists_collection_failures_per_row_and_rates_exclude_them():
    records, failures = _unreadable_corpus()
    result = prefilter.run_prefilter(records, failures)
    estimate = prefilter.estimate_spend(result["statements"], AI_CONFIG)
    text = prefilter.render_spend_report(
        records, result, {"D000001": "D", "R000002": "R"}, {"D000001": "A Democrat"}, estimate
    )
    assert "## Collection failures — no readable body, per row" in text
    assert "| A Democrat (D000001) | D | `member_press` | 60 |" in text
    assert "| Of those, no readable body — a collection failure, never judged | 60 | 0 |" in text
    assert "| Judged by the free pre-filter | 60 |" in text
    # Collected 120, unreadable 60, kept 60, dropped by the filter 0.
    assert "| `member_press` | 120 | 60 | 60 | 0 |" in text
    assert "| `no-attributable-text` | 0 | 0 | 0 | 0.0% | 0.0% | even |" in text
    assert "No step is flagged." in text
    rows = prefilter.fairness(result["judged_records"], result["drops"], {"D000001": "D"})
    assert next(r for r in rows if r["rule"] == "no-attributable-text")["D_turns"] == 30


def test_a_report_with_no_collection_failures_says_none():
    records = [_record(SUBSTANTIVE, member_id="D000001", granule_id="G1")]
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], AI_CONFIG)
    text = prefilter.render_spend_report(records, result, {"D000001": "D"}, {}, estimate)
    section = text.split("## Collection failures — no readable body, per row")[1]
    assert section.split("##")[0].strip().endswith("None.")


# --- every uneven step is named; the owner's acceptance covers procedural alone -------


def _logistics_corpus() -> list[dict]:
    """Office logistics in Democratic press releases, none in Republican ones."""
    return [
        _press(_record(f"{LOGISTICS} Visit {i}.", member_id="D000001", granule_id=f"/p/d{i}"))
        for i in range(60)
    ] + [
        _press(_record(f"{SUBSTANTIVE} r {i}", member_id="R000002", granule_id=f"/p/r{i}"))
        for i in range(60)
    ]


def test_a_new_uneven_step_is_named_and_left_for_the_owner():
    records = _logistics_corpus()
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], AI_CONFIG)
    text = prefilter.render_spend_report(
        records, result, {"D000001": "D", "R000002": "R"}, {}, estimate
    )
    section = text.split("### Every flagged step")[1].split("## Per member")[0]
    assert (
        "* `office-logistics` (all sources) — D 60 of 60 turns (100.0%), R 0 of 60 turns "
        "(0.0%); 60 turns dropped. **NEW, needs the owner's ruling.**"
    ) in section
    # The acceptance of 2026-10-14 is of the procedural gap; it is not lent to this one.
    assert "Owner-accepted" not in section
    assert "on condition that the" not in section


def test_the_procedural_flag_carries_the_owners_acceptance_and_a_new_flag_does_not():
    quorum = [
        _record(
            "Mr. X. Mr. Speaker, I suggest the absence of a quorum.",
            member_id="R000002",
            granule_id=f"G{i}",
        )
        for i in range(prefilter.UNEVEN_MIN_TURNS + 1)
    ] + [
        _record(f"{SUBSTANTIVE} d {i}", member_id="D000001", granule_id=f"H{i}")
        for i in range(prefilter.UNEVEN_MIN_TURNS + 1)
    ]
    records = quorum + _logistics_corpus()
    result = prefilter.run_prefilter(records)
    estimate = prefilter.estimate_spend(result["statements"], AI_CONFIG)
    text = prefilter.render_spend_report(
        records, result, {"D000001": "D", "R000002": "R"}, {}, estimate
    )
    section = text.split("### Every flagged step")[1].split("## Per member")[0]
    procedural = next(line for line in section.splitlines() if "`procedural` (all" in line)
    assert procedural.endswith("**Owner-accepted 2026-10-14 (R4)**, on the condition below.")
    # Per-source flags are listed too, each under its own source.
    assert "* `office-logistics` (`member_press`)" in section
    assert "* `procedural` (`congressional_record`)" in section
    for line in section.splitlines():
        if line.startswith("* `office-logistics`"):
            assert line.endswith("**NEW, needs the owner's ruling.**")
    assert "on condition that the" in section and "`quorum-call`" in section


def test_the_run_sets_unreadable_bodies_aside_and_logs_them_apart(
    tmp_path: Path, capsys, monkeypatch
):
    data_dir = tmp_path / "data"
    _corpus(data_dir)
    _ai_yaml(data_dir, AI_CONFIG)
    unreadable = _unreadable("D000001", "no-body")
    press = data_dir / "raw" / "press"
    (press / "statements").mkdir(parents=True)
    (press / "statements" / "D000001.json").write_text(
        json.dumps(
            {"member": {"id": "D000001", "name": "M", "party": "D"}, "statements": [unreadable]}
        ),
        encoding="utf-8",
    )
    (press / "index.json").write_text(
        json.dumps({"text_failures": [{"id": "D000001", "url": unreadable["url"]}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(prefilter, "repo_root", lambda: tmp_path)
    assert prefilter.run([]) == 0
    assert "no-readable-body           1  (collection failures" in capsys.readouterr().out
    log = json.loads(
        (data_dir / "quality" / "statement-prefilter-drops.json").read_text(encoding="utf-8")
    )
    assert log["statements_unreadable"] == 1
    assert [f["url"] for f in log["collection_failures"]] == [unreadable["url"]]
    assert all(d["rule"] != "no-attributable-text" for d in log["drops"])
