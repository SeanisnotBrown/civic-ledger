"""§5 Phase 3 task 4 — the prompt evaluation harness. No network, no credential, no spend:
the API is a fake completer, and the cache and audit log go to tmp_path."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from ingest import ai, prompt_eval
from ingest.prompt_eval import Label, Prediction, Row

COLUMNS = [
    "id", "member", "party", "chamber", "source", "date", "date_precision", "url", "text",
    "takes_policy_position", "topic", "stance", "proposition", "specificity",
    "priority_signal", "notes", "text_sha256",
]


def _csv(path: Path, rows: list[dict]) -> Path:
    # Written with a byte-order mark, the way Excel saves the owner's sheet.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in COLUMNS})
    return path


def _yes(i: int, party: str = "D", **over) -> dict:
    row = {"id": f"EV{i:02d}", "party": party, "text": f"policy text {i}",
           "takes_policy_position": "yes", "topic": "Health", "stance": "for",
           "proposition": "capping insulin", "specificity": "1", "priority_signal": "no"}
    row.update(over)
    return row


def _no(i: int, party: str = "R") -> dict:
    return {"id": f"EV{i:02d}", "party": party, "text": f"ceremony text {i}",
            "takes_policy_position": "no"}


# --- the bar ---------------------------------------------------------------------------


def test_the_shipped_bar_is_the_provisional_q_k_answer_and_is_not_ratified() -> None:
    bar = prompt_eval.load_bar()
    assert bar.ratified is False
    assert bar.proposed_by == "copilot for owner 2026-10-22"
    assert bar.fields == {"stance": 0.90, "topic": 0.90, "priority_signal": 0.90,
                          "specificity": 0.80}
    assert "proposition" not in bar.fields
    assert bar.min_labeled_rows == 50
    assert bar.party_gap_max_points == 10
    assert bar.rolling_blind_window == 50


def _thresholds(tmp_path: Path, ratified) -> Path:
    import yaml

    body = {"categorizer_precision": {
        "ratified": ratified, "min_labeled_rows": 50,
        "fields": {"stance": 0.9}, "party_gap_max_points": 10, "rolling_blind_window": 50,
    }}
    path = tmp_path / "config" / "thresholds.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(body), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("mark", [False, None, "", True])
def test_only_a_date_ratifies_the_bar(tmp_path: Path, mark) -> None:
    assert prompt_eval.load_bar(_thresholds(tmp_path, mark)).ratified is False


def test_a_quoted_or_unquoted_date_ratifies_the_bar(tmp_path: Path) -> None:
    assert prompt_eval.load_bar(_thresholds(tmp_path, "2026-10-23")).ratified_on == "2026-10-23"
    path = tmp_path / "config" / "thresholds.yaml"
    path.write_text(path.read_text().replace("'2026-10-23'", "2026-10-23"), encoding="utf-8")
    assert prompt_eval.load_bar(tmp_path).ratified_on == "2026-10-23"


def test_a_missing_or_incomplete_bar_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "config" / "thresholds.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("grades: {}\n", encoding="utf-8")
    with pytest.raises(prompt_eval.EvalError, match="no `categorizer_precision`"):
        prompt_eval.load_bar(tmp_path)
    path.write_text("categorizer_precision: {ratified: false}\n", encoding="utf-8")
    with pytest.raises(prompt_eval.EvalError, match="incomplete"):
        prompt_eval.load_bar(tmp_path)


# --- the labels ------------------------------------------------------------------------


def test_parse_ids_expands_ranges_and_keeps_singles() -> None:
    assert prompt_eval.parse_ids("EV01-EV03,EV10") == {"EV01", "EV02", "EV03", "EV10"}
    assert prompt_eval.parse_ids("EV08-10") == {"EV08", "EV09", "EV10"}
    assert prompt_eval.parse_ids(None) is None


def test_unlabeled_rows_are_skipped_not_scored_as_wrong(tmp_path: Path) -> None:
    path = _csv(tmp_path / "l.csv", [_yes(1), _no(2), {"id": "EV03", "party": "D",
                                                        "text": "x"}])
    rows, unlabeled = prompt_eval.read_labels(path)
    assert [r.id for r in rows] == ["EV01", "EV02"]
    assert unlabeled == ["EV03"]
    assert rows[0].label == Label(True, "Health", "for", 1, False)
    assert rows[1].label == Label(False)


def test_id_filter_and_normalization(tmp_path: Path) -> None:
    path = _csv(tmp_path / "l.csv", [_yes(1, stance="Against", takes_policy_position="Yes"),
                                     _yes(2)])
    rows, _ = prompt_eval.read_labels(path, {"EV01"})
    assert [r.id for r in rows] == ["EV01"]
    assert rows[0].label.stance == "against"


@pytest.mark.parametrize("over, match", [
    ({"takes_policy_position": "maybe"}, "yes or no"),
    ({"stance": "unclear"}, "stance must be"),
    ({"specificity": "high"}, "specificity must be"),
])
def test_a_malformed_label_is_named(tmp_path: Path, over, match) -> None:
    with pytest.raises(prompt_eval.EvalError, match=match):
        prompt_eval.read_labels(_csv(tmp_path / "l.csv", [_yes(1, **over)]))


# --- scoring ---------------------------------------------------------------------------


def _row(i: int, party: str, label: Label) -> Row:
    return Row(id=f"EV{i:02d}", party=party, text="t", label=label)


YES = Label(True, "Health", "for", 1, True)
CAT = {"topic": "Health", "stance": "for", "proposition": "p", "specificity": 1,
       "priority_signal": True, "confidence": "high"}


def test_each_field_is_precision_over_the_ais_calls() -> None:
    rows = [_row(1, "D", YES), _row(2, "D", Label(False)), _row(3, "R", YES)]
    preds = {
        "EV01": Prediction(True, dict(CAT)),
        # Triage passed a statement the owner said takes no position: every call the
        # categorizer makes on it is a false positive.
        "EV02": Prediction(True, dict(CAT)),
        # Wrong topic and stance; no priority call; mixed is outside the stance bar.
        "EV03": Prediction(True, dict(CAT, topic="Taxation", stance="mixed",
                                      priority_signal=False, specificity=2)),
    }
    result = prompt_eval.score(rows, preds, [])
    f = result.by_field
    assert (f["takes_policy_position"]["all"].correct, f["takes_policy_position"]["all"].called) \
        == (2, 3)
    assert (f["stance"]["all"].correct, f["stance"]["all"].called) == (1, 2)
    assert (f["topic"]["all"].correct, f["topic"]["all"].called) == (1, 3)
    assert (f["priority_signal"]["all"].correct, f["priority_signal"]["all"].called) == (1, 2)
    assert (f["specificity"]["all"].correct, f["specificity"]["all"].called) == (1, 3)
    assert result.mixed_calls == 1
    assert result.per_row["EV02"]["stance"] is False


def test_a_topic_match_ignores_case_and_spacing_only() -> None:
    rows = [_row(1, "D", Label(True, "Arts, Culture, Religion", "for", 2, False))]
    ok = prompt_eval.score(rows, {"EV01": Prediction(True, dict(
        CAT, topic="arts,  culture, religion"))}, [])
    assert ok.by_field["topic"]["all"].correct == 1
    bad = prompt_eval.score(rows, {"EV01": Prediction(True, dict(CAT, topic="Arts"))}, [])
    assert bad.by_field["topic"]["all"].correct == 0


def test_a_triage_miss_is_counted_but_is_not_a_precision_error() -> None:
    result = prompt_eval.score([_row(1, "D", YES)], {"EV01": Prediction(False)}, [])
    assert result.triage_rejected_owner_yes == 1
    assert result.by_field["takes_policy_position"]["all"].called == 0


def test_precision_is_split_by_party_and_a_wide_gap_is_flagged() -> None:
    rows = [_row(i, "D", YES) for i in range(1, 6)] + [_row(i, "R", YES) for i in range(6, 11)]
    preds = {r.id: Prediction(True, dict(CAT)) for r in rows}
    preds["EV06"] = Prediction(True, dict(CAT, stance="against"))  # R: 4/5 on stance
    result = prompt_eval.score(rows, preds, [])
    stance = result.by_field["stance"]
    assert stance["D"].precision == 1.0
    assert stance["R"].precision == pytest.approx(0.8)
    assert prompt_eval.party_gap_points(stance) == pytest.approx(20)
    bar = prompt_eval.load_bar()
    assert prompt_eval.gap_flags(result, bar) == ["stance"]


def test_no_gap_without_calls_on_both_sides() -> None:
    tallies = {"D": prompt_eval.Tally(2, 2), "R": prompt_eval.Tally()}
    assert prompt_eval.party_gap_points(tallies) is None


def test_bars_are_not_assessed_below_the_minimum_set_size() -> None:
    bar = prompt_eval.load_bar()
    tally = prompt_eval.Tally(10, 10)
    assert bar_text(bar, tally, 10).startswith("not assessed (n=10")
    assert bar_text(bar, tally, 60) == "meets"
    assert bar_text(bar, prompt_eval.Tally(10, 8), 60) == "BELOW"
    assert bar_text(bar, prompt_eval.Tally(), 60) == "not assessed (no calls)"
    assert prompt_eval.bar_status("takes_policy_position", tally, bar, 60) == "no bar"
    assert prompt_eval.title(10, bar) == "10-row smoke test, not a precision measurement"
    assert prompt_eval.title(60, bar) == "Precision on 60 hand-labeled statements"


def bar_text(bar, tally, rows) -> str:
    return prompt_eval.bar_status("stance", tally, bar, rows)


# --- the command, end to end with a fake API -------------------------------------------


def _answer(data: dict, stop: str = "end_turn") -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data)}], "stop_reason": stop,
            "usage": {"input_tokens": 1000, "output_tokens": 200}, "request_id": "req"}


class FakeApi:
    """Haiku answers the triage question from the text; Opus returns CAT."""

    def __init__(self, refuse: str | None = None, explode: bool = False) -> None:
        self.models: list[str] = []
        self.refuse = refuse
        self.explode = explode

    def __call__(self, request: dict) -> dict:
        self.models.append(request["model"])
        text = request["messages"][0]["content"]
        if self.explode:
            raise RuntimeError("400 bad schema")
        if self.refuse and self.refuse in text:
            return _answer({}, stop="refusal")
        if request["model"] == "claude-haiku-5-5":
            return _answer({"takes_policy_position": text.startswith("policy")})
        return _answer(CAT)


def _ten(tmp_path: Path) -> Path:
    rows = [_yes(i, "D" if i <= 5 else "R") for i in range(1, 9)] + [_no(9), _no(10)]
    rows.append({"id": "EV11", "party": "D", "text": "policy unlabeled"})
    return _csv(tmp_path / "labels.csv", rows)


def test_a_ten_row_run_is_titled_a_smoke_test_and_categorizes_only_what_triage_passed(
    tmp_path: Path,
) -> None:
    api = FakeApi()
    out = tmp_path / "report.md"
    code = prompt_eval.run(["--labels", str(_ten(tmp_path)), "--ids", "EV01-EV11",
                            "--out", str(out)], completer=api, data_dir=tmp_path)
    assert code == prompt_eval.EXIT_OK
    assert api.models.count("claude-haiku-5-5") == 10
    assert api.models.count("claude-opus-5-5") == 8  # the two ceremony rows never reach it
    report = out.read_text(encoding="utf-8")
    assert report.startswith(
        "# Prompt evaluation — 10-row smoke test, not a precision measurement")
    assert "PROVISIONAL, not ratified" in report
    assert "not assessed (n=10 < 50)" in report
    assert "| Rows skipped as not yet labeled | 1 |" in report
    # Counts, never answers: no model label appears in the report.
    assert "capping insulin" not in report and '"stance"' not in report
    # Every call was logged by ai.py into the tmp audit log, not the repository's.
    log = list((tmp_path / "quality" / "ai-calls").glob("*.jsonl"))
    assert len(log) == 1 and len(log[0].read_text().splitlines()) == 18


def test_a_refusal_is_no_answer_for_that_row_and_the_run_goes_on(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    code = prompt_eval.run(["--labels", str(_ten(tmp_path)), "--out", str(out)],
                           completer=FakeApi(refuse="policy text 3"), data_dir=tmp_path)
    assert code == prompt_eval.EXIT_OK
    assert "| Rows with no answer (refusal or malformed) | 1: EV03 |" in out.read_text(
        encoding="utf-8")


def test_an_api_error_stops_the_run_and_the_report_says_so(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    code = prompt_eval.run(["--labels", str(_ten(tmp_path)), "--out", str(out)],
                           completer=FakeApi(explode=True), data_dir=tmp_path)
    assert code == prompt_eval.EXIT_STOPPED
    assert "`api-error`: RuntimeError: 400 bad schema" in out.read_text(encoding="utf-8")


def test_the_run_cap_stops_the_run_exactly(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    # A cap below one Opus reservation: triage runs, the first categorizer call is refused.
    code = prompt_eval.run(["--labels", str(_ten(tmp_path)), "--out", str(out),
                            "--cap", "0.01"], completer=FakeApi(), data_dir=tmp_path)
    assert code == prompt_eval.EXIT_STOPPED
    assert "`cap`" in out.read_text(encoding="utf-8")


@pytest.mark.parametrize("cap", ["0", "-1", "5.01"])
def test_the_cap_can_only_lower_the_ai_yaml_cap(tmp_path: Path, cap: str) -> None:
    api = FakeApi()
    code = prompt_eval.run(["--labels", str(_ten(tmp_path)), "--cap", cap,
                            "--out", str(tmp_path / "r.md")], completer=api, data_dir=tmp_path)
    assert code == prompt_eval.EXIT_STOPPED
    assert api.models == []
    assert ai.load_config().per_run_cost_cap_usd == 5.00


def test_parse_ids_ignores_empty_parts() -> None:
    assert prompt_eval.parse_ids("EV01,,EV02, ") == {"EV01", "EV02"}


def test_an_abstaining_categorizer_makes_no_calls() -> None:
    abstain = {"topic": None, "stance": "none", "proposition": None, "specificity": None,
               "priority_signal": False, "confidence": "low"}
    result = prompt_eval.score([_row(1, "D", YES)], {"EV01": Prediction(True, abstain)}, [])
    assert result.per_row["EV01"] == {"takes_policy_position": True}


def test_a_categorizer_refusal_is_no_answer(tmp_path: Path) -> None:
    class RefuseOpus(FakeApi):
        def __call__(self, request: dict) -> dict:
            if request["model"] == "claude-opus-5-5":
                self.models.append(request["model"])
                return _answer({}, stop="refusal")
            return super().__call__(request)

    out = tmp_path / "r.md"
    prompt_eval.run(["--labels", str(_ten(tmp_path)), "--ids", "EV01", "--out", str(out)],
                    completer=RefuseOpus(), data_dir=tmp_path)
    assert "| Rows with no answer (refusal or malformed) | 1: EV01 |" in out.read_text(
        encoding="utf-8")


def _gap_result(n_each: int) -> prompt_eval.Score:
    rows = [_row(i, "D", YES) for i in range(n_each)]
    rows += [_row(100 + i, "R", YES) for i in range(n_each)]
    preds = {r.id: Prediction(True, dict(CAT)) for r in rows}
    preds["EV100"] = Prediction(True, dict(CAT, stance="against"))
    preds["EV101"] = Prediction(True, dict(CAT, stance="against"))
    preds["EV102"] = Prediction(True, dict(CAT, stance="against"))
    return prompt_eval.score(rows, preds, [])


def _render(result: prompt_eval.Score, tmp_path: Path) -> str:
    run = ai.Run(config=ai.load_config(), completer=FakeApi(), data_dir=tmp_path)
    return prompt_eval.render(result=result, bar=prompt_eval.load_bar(),
                              outcome=prompt_eval.Outcome(), run=run, labels_path="l.csv",
                              ids=None, generated="now")


def test_a_wide_party_gap_on_a_full_set_stops_for_owner_review(tmp_path: Path) -> None:
    report = _render(_gap_result(25), tmp_path)
    assert report.startswith("# Prompt evaluation — Precision on 50 hand-labeled statements")
    assert "**STOP for owner review:** the D/R gap passes 10 points on `stance`." in report
    assert "smoke test" not in report


def test_a_wide_gap_on_a_smoke_test_is_reported_as_noise(tmp_path: Path) -> None:
    report = _render(_gap_result(5), tmp_path)
    assert "STOP" not in report
    assert "on a smoke test this is noise and does not stop anything" in report


def test_without_a_test_seam_the_run_uses_the_live_api_and_the_repo_data(
    tmp_path: Path, monkeypatch
) -> None:
    built: list[dict] = []
    real_run = ai.Run

    def fake_run(**kwargs):
        built.append(dict(kwargs))
        kwargs.update(completer=FakeApi(), data_dir=tmp_path)
        return real_run(**kwargs)

    monkeypatch.setattr(prompt_eval.ai, "Run", fake_run)
    prompt_eval.run(["--labels", str(_ten(tmp_path)), "--ids", "EV09",
                     "--out", str(tmp_path / "r.md")])
    assert "completer" not in built[0] and built[0]["data_dir"] is None
