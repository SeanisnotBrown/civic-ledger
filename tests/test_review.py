"""P3 task 5 — the review queue: blind 1-in-10 sampling, the review log, running precision,
and the Q-K publish gate. No network, no AI call; the queue and log live in tmp_path."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from curation import review
from curation.app import create_app
from ingest import ai, prompt_eval

SUGGESTION = {"topic": "Health", "stance": "for", "proposition": "capping insulin at $35",
              "specificity": 1, "priority_signal": True, "confidence": "medium"}


def _ids(blind: bool, n: int) -> list[str]:
    out: list[str] = []
    i = 0
    while len(out) < n:
        candidate = hashlib.sha256(f"text {i}".encode()).hexdigest()
        if review.is_blind(candidate) is blind:
            out.append(candidate)
        i += 1
    return out


def _queue(tmp_path: Path, ids: list[str], party: str = "D", **over) -> Path:
    path = review.queue_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for item_id in ids:
            handle.write(json.dumps({
                "id": item_id, "member_id": "M000001", "party": party,
                "text": f"statement {item_id[:6]}", "url": "https://example.house.gov/x",
                "date": "2026-10-01", "source": "member_press", "input_hash": "h" + item_id[:8],
                "prompt_version": "v1", "suggestion": dict(SUGGESTION, **over),
            }) + "\n")
    return tmp_path


OWNER_SAME = {"takes_policy_position": "yes", "topic": "Health", "stance": "for",
              "proposition": "insulin", "specificity": "1", "priority_signal": "yes"}
OWNER_DIFF = {"takes_policy_position": "yes", "topic": "Taxation", "stance": "against",
              "specificity": "2", "priority_signal": "no"}


# --- blind sampling ------------------------------------------------------------------


def test_blind_is_one_in_ten_and_fixed_per_item() -> None:
    ids = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(20_000)]
    rate = sum(review.is_blind(i) for i in ids) / len(ids)
    assert 0.09 < rate < 0.11
    assert [review.is_blind(i) for i in ids[:500]] == [review.is_blind(i) for i in ids[:500]]


def test_next_item_is_one_at_a_time_in_queue_order(tmp_path: Path) -> None:
    ids = _ids(False, 3)
    _queue(tmp_path, ids)
    nxt = review.next_item(tmp_path)
    assert nxt.item.id == ids[0] and nxt.stage == "review" and nxt.remaining == 3
    review.record_decision(ids[0], "approve", data_dir=tmp_path)
    assert review.next_item(tmp_path).item.id == ids[1]
    review.record_decision(ids[1], "reject", data_dir=tmp_path)
    review.record_decision(ids[2], "approve", data_dir=tmp_path)
    assert review.next_item(tmp_path) is None


def test_a_blind_item_is_labeled_before_it_is_revealed(tmp_path: Path) -> None:
    (item_id,) = _ids(True, 1)
    _queue(tmp_path, [item_id])
    assert review.next_item(tmp_path).stage == "label"
    with pytest.raises(review.ReviewError, match="enter your own label"):
        review.record_decision(item_id, "approve", data_dir=tmp_path)
    review.record_blind_label(item_id, OWNER_DIFF, tmp_path)
    nxt = review.next_item(tmp_path)
    assert nxt.stage == "reveal" and nxt.blind_label["topic"] == "Taxation"
    with pytest.raises(review.ReviewError, match="already on file"):
        review.record_blind_label(item_id, OWNER_SAME, tmp_path)
    review.record_decision(item_id, "approve", data_dir=tmp_path)
    events = [e["event"] for e in review.load_log(tmp_path)]
    assert events == ["blind_label", "decision"]


def test_a_non_blind_item_takes_no_blind_label(tmp_path: Path) -> None:
    (item_id,) = _ids(False, 1)
    _queue(tmp_path, [item_id])
    with pytest.raises(review.ReviewError, match="not blind"):
        review.record_blind_label(item_id, OWNER_SAME, tmp_path)


# --- the log -------------------------------------------------------------------------


def test_the_log_holds_the_owners_labels_and_agreement_never_the_models_answer(
    tmp_path: Path,
) -> None:
    (blind_id,) = _ids(True, 1)
    (open_id,) = _ids(False, 1)
    _queue(tmp_path, [blind_id, open_id])
    line = review.record_blind_label(blind_id, OWNER_DIFF, tmp_path, now="T1")
    assert line["agree"] == {"stance": False, "topic": False, "priority_signal": False,
                             "specificity": False}
    edit = review.record_decision(open_id, "edit", dict(OWNER_SAME, specificity="2"),
                                  tmp_path, now="T2")
    assert edit["agree"] == {"stance": True, "topic": True, "priority_signal": True,
                             "specificity": False}
    raw = review.log_path(tmp_path).read_text(encoding="utf-8")
    assert "capping insulin at $35" not in raw  # the model's proposition is not logged
    assert '"confidence"' not in raw
    assert all(json.loads(x)["input_hash"].startswith("h") for x in raw.splitlines())


def test_approve_adopts_the_suggestion_and_reject_carries_no_label(tmp_path: Path) -> None:
    ids = _ids(False, 2)
    _queue(tmp_path, ids)
    approve = review.record_decision(ids[0], "approve", data_dir=tmp_path)
    assert approve["label"]["topic"] == "Health" and all(approve["agree"].values())
    reject = review.record_decision(ids[1], "reject", data_dir=tmp_path)
    assert "label" not in reject and "agree" not in reject
    assert [e["item_id"] for e in review.approved(tmp_path)] == [ids[0]]


@pytest.mark.parametrize("form, match", [
    ({"takes_policy_position": "maybe"}, "yes or no"),
    ({"stance": "unclear"}, "stance must be"),
    ({"stance": "for", "topic": "Healthcare"}, "not one of the 33"),
    ({"stance": "for", "specificity": "4"}, "specificity must be"),
])
def test_a_bad_label_is_refused(form, match) -> None:
    with pytest.raises(review.ReviewError, match=match):
        review.clean_label(form)


def test_a_no_label_clears_the_rest() -> None:
    assert review.clean_label({"takes_policy_position": "no", "topic": "Health"}) == {
        "takes_policy_position": False, "topic": None, "stance": "none", "proposition": None,
        "specificity": None, "priority_signal": False}


def test_bad_actions_and_unknown_items_are_refused(tmp_path: Path) -> None:
    ids = _ids(False, 1)
    _queue(tmp_path, ids)
    with pytest.raises(review.ReviewError, match="action must be"):
        review.record_decision(ids[0], "publish", data_dir=tmp_path)
    with pytest.raises(review.ReviewError, match="no queued item"):
        review.record_decision("nope", "approve", data_dir=tmp_path)
    review.record_decision(ids[0], "approve", data_dir=tmp_path)
    with pytest.raises(review.ReviewError, match="already decided"):
        review.record_decision(ids[0], "reject", data_dir=tmp_path)


# --- running precision -----------------------------------------------------------------


def test_running_precision_comes_from_blind_labels_only_over_the_window(
    tmp_path: Path,
) -> None:
    blind = _ids(True, 4)
    opened = _ids(False, 1)
    _queue(tmp_path, blind[:2], party="D")
    _queue(tmp_path, blind[2:], party="R")
    _queue(tmp_path, opened)
    review.record_blind_label(blind[0], OWNER_DIFF, tmp_path)  # oldest: outside window 3
    review.record_blind_label(blind[1], OWNER_SAME, tmp_path)
    review.record_blind_label(blind[2], OWNER_SAME, tmp_path)
    review.record_blind_label(blind[3], OWNER_DIFF, tmp_path)
    review.record_decision(opened[0], "approve", data_dir=tmp_path)  # anchored only
    run = review.running_precision(tmp_path, window=3)
    assert run.blind_items == 3
    assert (run.blind["stance"]["all"].correct, run.blind["stance"]["all"].called) == (2, 3)
    assert run.blind["stance"]["D"].precision == 1.0
    assert run.blind["stance"]["R"].precision == 0.5
    assert (run.anchored["stance"].correct, run.anchored["stance"].called) == (1, 1)
    assert review.running_precision(tmp_path).window == 50  # from thresholds.yaml


# --- the publish gate (Q-K) -------------------------------------------------------------


def test_with_q_k_ratified_the_gate_is_still_closed_until_measured_and_archived(
    tmp_path: Path,
) -> None:
    """Q-K was ratified 2026-10-23. Ratifying the bar opens nothing by itself."""
    gate = review.publish_gate(tmp_path)
    assert gate.open is False
    assert not any("not ratified" in r for r in gate.reasons)
    assert any("not been measured on the held-out labeled set" in r for r in gate.reasons)
    assert any("cannot be archived yet" in r for r in gate.reasons)


def _thresholds(tmp_path: Path, ratified) -> Path:
    real = yaml.safe_load((Path(review.repo_root()) / "data" / "config" / "thresholds.yaml")
                          .read_text(encoding="utf-8"))
    entry = dict(real["categorizer_precision"], ratified=ratified)
    path = tmp_path / "t" / "config" / "thresholds.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump({"categorizer_precision": entry}), encoding="utf-8")
    return tmp_path / "t"


_OMIT = object()


def _measured(tmp_path: Path, *, version: str | None = None, status: str = "meets",
              gaps: list[str] = (), unreviewed=0) -> None:
    task = ai.load_config().task("categorize_statement")
    path = prompt_eval.measurement_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "generated": "2026-10-24", "labeled_rows": 60, "party_gap_flags": list(gaps),
        "tasks": {"categorize_statement": {
            "prompt_version": version or task.prompt_version,
            "prompt_sha256": task.prompt_sha256 if version is None else "x",
            "model": task.model}},
        "fields": {"stance": {"status": status}, "topic": {"status": "meets"},
                   "takes_policy_position": {"status": "no bar"}},
        **({} if unreviewed is _OMIT else {"unreviewed_labels": unreviewed}),
    }), encoding="utf-8")


def test_an_unratified_bar_keeps_the_gate_closed(tmp_path: Path) -> None:
    gate = review.publish_gate(tmp_path, thresholds_dir=_thresholds(tmp_path, False))
    assert any("Q-K precision bar is not ratified" in r and "copilot for owner" in r
               for r in gate.reasons)


@pytest.mark.parametrize("kwargs, reason", [
    ({"version": "v1"}, "the held-out measurement is for categorizer v1, not v2"),
    ({"status": "BELOW"}, "held-out precision on stance is BELOW"),
    ({"gaps": ["topic"]}, "held-out D/R gap flagged on topic: owner review"),
    # Copilot-labeled rows can never satisfy Q-K, even when every bar is met.
    ({"unreviewed": 50}, "rests on 50 labels the owner has not reviewed"),
    ({"unreviewed": _OMIT}, "rests on an unknown number of labels the owner has not"),
])
def test_a_stale_or_failing_measurement_keeps_the_gate_closed(tmp_path: Path, kwargs,
                                                              reason) -> None:
    _measured(tmp_path, **kwargs)
    gate = review.publish_gate(tmp_path)
    assert any(reason in r for r in gate.reasons), gate.reasons


def test_the_gate_opens_only_when_every_condition_holds(tmp_path: Path, monkeypatch) -> None:
    thresholds = _thresholds(tmp_path, "2026-10-23")
    _measured(tmp_path)
    gate = review.publish_gate(tmp_path, thresholds_dir=thresholds)
    assert gate.reasons == ("categorized statements cannot be archived yet (task 3: "
                            "archive.org keys); nothing unarchived publishes",)
    monkeypatch.setattr(review, "ARCHIVE_PATH_BUILT", True)
    assert review.publish_gate(tmp_path, thresholds_dir=thresholds).open is True
    # A blind label below the bar closes it again (Q-K's running check).
    (item_id,) = _ids(True, 1)
    _queue(tmp_path, [item_id])
    review.record_blind_label(item_id, OWNER_DIFF, tmp_path)
    gate = review.publish_gate(tmp_path, thresholds_dir=thresholds)
    assert gate.open is False
    assert any("rolling blind precision on stance is 0%" in r for r in gate.reasons)


def test_export_refuses_while_the_gate_is_closed_and_writes_nothing(tmp_path: Path) -> None:
    ids = _ids(False, 1)
    _queue(tmp_path, ids)
    review.record_decision(ids[0], "approve", data_dir=tmp_path)
    with pytest.raises(review.PublishGateClosed, match="nothing exported: the categorizer"):
        review.export_approved(tmp_path)
    assert not (tmp_path / "statements").exists()


# --- owner rulings 2026-10-23 -----------------------------------------------------------


@pytest.mark.parametrize("stance, position", [
    ("for", "support"), ("against", "oppose"), ("mixed", None), ("none", None), (None, None),
])
def test_stance_maps_to_the_published_record_per_ruling_7(stance, position) -> None:
    fields = review.statement_fields({"stance": stance, "specificity": 2, "topic": "Health",
                                      "priority_signal": True})
    assert fields == {"stated_position": position, "specificity_level": 2, "topic": "Health",
                      "priority_signal": True}


def test_the_review_log_is_git_ignored_in_the_public_repo() -> None:
    import subprocess

    rel = review.log_path().relative_to(review.repo_root()).as_posix()
    probe = subprocess.run(["git", "check-ignore", "-q", rel], cwd=review.repo_root())
    assert probe.returncode == 0


def test_the_private_backup_is_a_stub_that_pushes_nothing(tmp_path: Path, monkeypatch) -> None:
    assert review.backup_review_log(tmp_path) == "nothing to back up: no review log yet"
    ids = _ids(False, 1)
    _queue(tmp_path, ids)
    review.record_decision(ids[0], "approve", data_dir=tmp_path)
    monkeypatch.delenv(review.BACKUP_REMOTE_ENV, raising=False)
    monkeypatch.setattr("ingest.env.get", lambda name, default=None: None)
    assert review.backup_review_log(tmp_path).startswith("not configured: the owner creates")
    monkeypatch.setattr("ingest.env.get", lambda name, default=None: "git@example:private")
    assert "still a stub; nothing was pushed" in review.backup_review_log(tmp_path)


# --- the Review tab ------------------------------------------------------------------


def _csrf(client) -> str:
    html = client.get("/statements").get_data(as_text=True)
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def test_the_review_tab_hides_the_suggestion_on_a_blind_item_until_he_labels_it(
    tmp_path: Path,
) -> None:
    (item_id,) = _ids(True, 1)
    _queue(tmp_path, [item_id])
    client = create_app(tmp_path).test_client()
    html = client.get("/review").get_data(as_text=True)
    assert "Blind item" in html
    assert "AI suggestion" not in html and "capping insulin" not in html
    assert "medium" not in html  # not even the confidence word
    assert "Publishing: <strong>CLOSED</strong>" in html
    r = client.post("/review/blind", data=dict(OWNER_DIFF, csrf=_csrf(client),
                                               item_id=item_id), follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "AI suggestion" in html and "capping insulin at $35" in html
    assert "Your blind label" in html
    assert "Running precision from your blind labels" in html and "(0/1)" in html


def test_the_review_tab_shows_a_non_blind_suggestion_and_records_a_decision(
    tmp_path: Path,
) -> None:
    ids = _ids(False, 2)
    _queue(tmp_path, ids)
    client = create_app(tmp_path).test_client()
    html = client.get("/review").get_data(as_text=True)
    assert "AI suggestion" in html and "confidence: <strong>medium</strong>" in html
    csrf = _csrf(client)
    r = client.post("/review/decide", data={"csrf": csrf, "item_id": ids[0],
                                            "action": "approve"}, follow_redirects=True)
    assert "Recorded: approve." in r.get_data(as_text=True)
    r = client.post("/review/decide", data=dict(OWNER_SAME, csrf=csrf, item_id=ids[1],
                                                action="edit"), follow_redirects=True)
    assert "Nothing waiting for review." in r.get_data(as_text=True)
    assert not (tmp_path / "statements").exists()


def test_review_errors_are_shown_not_raised(tmp_path: Path) -> None:
    ids = _ids(False, 1)
    _queue(tmp_path, ids)
    client = create_app(tmp_path).test_client()
    csrf = _csrf(client)
    r = client.post("/review/blind", data=dict(OWNER_SAME, csrf=csrf, item_id=ids[0]),
                    follow_redirects=True)
    assert "Not saved: this item is not blind" in r.get_data(as_text=True)
    r = client.post("/review/decide", data={"csrf": csrf, "item_id": ids[0],
                                            "action": "publish"}, follow_redirects=True)
    assert "Not saved: action must be" in r.get_data(as_text=True)


def test_review_posts_need_the_csrf_token(tmp_path: Path) -> None:
    ids = _ids(False, 1)
    _queue(tmp_path, ids)
    client = create_app(tmp_path).test_client()
    assert client.post("/review/decide", data={"item_id": ids[0],
                                               "action": "approve"}).status_code == 403
    assert review.load_log(tmp_path) == []


def test_an_empty_queue_says_so(tmp_path: Path) -> None:
    html = create_app(tmp_path).test_client().get("/review").get_data(as_text=True)
    assert "Nothing waiting for review." in html
