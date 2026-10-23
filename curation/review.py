"""P3 task 5 — the review queue behind the curation app's Review tab.

The AI suggests; the owner decides. Each categorized statement is shown one at a time with
the categorizer's suggestion and its confidence word, and the owner approves it, edits it,
or rejects it. Nothing here authors a label: an approval adopts the AI's suggestion only
because the owner pressed Approve, and an edit is the owner's own label.

## Blind 1 in 10 (spec task 5)

A random 1 in 10 is shown BLIND: the suggestion stays hidden until the owner has entered
his own label, so the review log yields a precision number his judgment was not anchored
to. Which items are blind is a pure function of a fixed seed and the item's text
fingerprint (`is_blind`): reloading the page cannot un-blind an item, and anyone can check
the sample was random rather than chosen. His blind label is logged BEFORE the suggestion
is revealed, and running precision is computed from those blind labels only.

## The review log

`data/raw/review/log.jsonl`, one JSON line per event, append-only:

  * `blind_label` — the owner's label for a blind item, entered before the reveal, with
    the per-field agreement between it and the AI's calls (`ingest.prompt_eval.calls`,
    the same scoring the held-out evaluation uses).
  * `decision` — approve / edit / reject, with the final label for approve and edit.

The log stores the owner's labels and agreement marks, never the model's answer: that stays
in the AI cache under the `input_hash` the line names (counts, never answers — the rule
`ingest/triage_run.py` and `ingest/ai.py` already follow). The queue and the log sit under
the gitignored `data/raw/`, like every model output.

## The publish gate (Q-K)

Approved statements do NOT export anywhere publishable until `publish_gate` opens, and it
opens only when every condition holds:

  1. the Q-K precision bar in `thresholds.yaml` is ratified by the owner (a date, not
     `false`);
  2. no field's rolling precision over the last `rolling_blind_window` blind labels is
     below its bar (Q-K's running check);
  3. a categorized statement can be archived before it publishes (decision 8; task 3,
     blocked on the archive.org keys). Until that path exists the gate stays closed
     whatever Q-K says, because `data/statements/` takes only records with a verified
     capture (`curation/statements.py::build_statement`).

Nothing in this module writes to `data/statements/`.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ingest import ai, prompt_eval
from ingest.cache import repo_root
from ingest.prompt_eval import Label, Prediction, Row, Tally

# 1 in BLIND_EVERY items is blind (spec task 5). The seed is fixed and public so the blind
# sample is reproducible and checkable; it says nothing about which item is which until
# the fingerprint is hashed with it.
BLIND_EVERY = 10
BLIND_SEED = "civic-ledger-review-blind-2026-10-23"

ACTIONS = ("approve", "edit", "reject")
SCORED = ("stance", "topic", "priority_signal", "specificity")
STANCES = ("for", "against", "mixed", "none")

# Condition 3 of the gate. Flipped in the commit that builds archive capture for
# categorized statements (task 3) — never by hand.
ARCHIVE_PATH_BUILT = False


class ReviewError(ValueError):
    """A review action that cannot be recorded (unknown item, bad label, wrong order)."""


class PublishGateClosed(RuntimeError):
    """An export was asked for while the Q-K publish gate is closed."""


def _data(data_dir: Path | None) -> Path:
    return data_dir if data_dir is not None else repo_root() / "data"


def review_dir(data_dir: Path | None = None) -> Path:
    return _data(data_dir) / "raw" / "review"


def queue_path(data_dir: Path | None = None) -> Path:
    return review_dir(data_dir) / "queue.jsonl"


def log_path(data_dir: Path | None = None) -> Path:
    return review_dir(data_dir) / "log.jsonl"


def topics() -> list[str]:
    """The 33 policy areas, from the categorizer's own schema (one source of truth)."""
    schema = ai.load_config().task("categorize_statement").output_schema
    return list(schema["properties"]["topic"]["anyOf"][0]["enum"])


def is_blind(item_id: str) -> bool:
    """True for a random 1 in BLIND_EVERY items, fixed per item."""
    digest = hashlib.sha256(f"{BLIND_SEED}:{item_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % BLIND_EVERY == 0


# --- the queue -------------------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    """One categorized statement awaiting review. `id` is the text's sha256 — the same
    fingerprint the triage ledger keys on — so the same text is reviewed once."""

    id: str
    member_id: str
    party: str
    text: str
    url: str | None
    date: str | None
    source: str | None
    input_hash: str
    prompt_version: str
    suggestion: dict[str, Any]

    @property
    def blind(self) -> bool:
        return is_blind(self.id)


def _item(raw: dict[str, Any]) -> Item:
    return Item(
        id=raw["id"], member_id=raw["member_id"], party=raw["party"], text=raw["text"],
        url=raw.get("url"), date=raw.get("date"), source=raw.get("source"),
        input_hash=raw["input_hash"], prompt_version=raw["prompt_version"],
        suggestion=dict(raw["suggestion"]),
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def load_queue(data_dir: Path | None = None) -> list[Item]:
    return [_item(raw) for raw in _jsonl(queue_path(data_dir))]


def load_log(data_dir: Path | None = None) -> list[dict[str, Any]]:
    return _jsonl(log_path(data_dir))


def _append(data_dir: Path | None, line: dict[str, Any]) -> None:
    path = log_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n")


@dataclass(frozen=True)
class Next:
    """What the Review tab shows. `stage` is `label` (blind, suggestion hidden), `reveal`
    (blind, his label in, suggestion shown) or `review` (not blind). None when done."""

    item: Item
    stage: str
    blind_label: dict[str, Any] | None
    remaining: int


def next_item(data_dir: Path | None = None) -> Next | None:
    """The first queued item with no decision yet. One at a time, in queue order."""
    log = load_log(data_dir)
    decided = {e["item_id"] for e in log if e["event"] == "decision"}
    labels = {e["item_id"]: e["label"] for e in log if e["event"] == "blind_label"}
    pending = [i for i in load_queue(data_dir) if i.id not in decided]
    if not pending:
        return None
    item = pending[0]
    if not item.blind:
        stage = "review"
    elif item.id in labels:
        stage = "reveal"
    else:
        stage = "label"
    return Next(item=item, stage=stage, blind_label=labels.get(item.id),
                remaining=len(pending))


def _find(item_id: str, data_dir: Path | None) -> Item:
    for item in load_queue(data_dir):
        if item.id == item_id:
            return item
    raise ReviewError(f"no queued item {item_id!r}")


# --- labels and agreement ---------------------------------------------------------------


def clean_label(form: dict[str, Any]) -> dict[str, Any]:
    """The owner's label from a form, validated. A `no` on takes_policy_position clears
    the rest, the way the labeling sheet does."""
    takes = str(form.get("takes_policy_position", "yes")).strip().lower()
    if takes not in ("yes", "no"):
        raise ReviewError("takes_policy_position must be yes or no")
    if takes == "no":
        return {"takes_policy_position": False, "topic": None, "stance": "none",
                "proposition": None, "specificity": None, "priority_signal": False}
    stance = str(form.get("stance", "")).strip().lower()
    if stance not in STANCES:
        raise ReviewError(f"stance must be one of {', '.join(STANCES)}")
    topic = str(form.get("topic", "")).strip() or None
    if topic is not None and topic not in topics():
        raise ReviewError(f"topic {topic!r} is not one of the 33 policy areas")
    spec_raw = str(form.get("specificity", "")).strip()
    if spec_raw not in ("", "1", "2", "3"):
        raise ReviewError("specificity must be 1, 2, 3 or blank")
    return {
        "takes_policy_position": True,
        "topic": topic,
        "stance": stance,
        "proposition": str(form.get("proposition", "")).strip() or None,
        "specificity": int(spec_raw) if spec_raw else None,
        "priority_signal": str(form.get("priority_signal", "no")).strip().lower() == "yes",
    }


def agreement(item: Item, label: dict[str, Any]) -> dict[str, bool]:
    """For each field the AI made a call on: does the owner's label agree? The held-out
    evaluation's own scoring, so the running number and the launch number mean the same."""
    row = Row(id=item.id, party=item.party, text="", label=Label(
        takes_policy_position=label["takes_policy_position"], topic=label.get("topic"),
        stance=label.get("stance"), specificity=label.get("specificity"),
        priority_signal=label.get("priority_signal"),
    ))
    verdicts = prompt_eval.calls(row, Prediction(takes_policy_position=None,
                                                 categorized=item.suggestion))
    return {k: v for k, v in verdicts.items() if k in SCORED}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def record_blind_label(item_id: str, form: dict[str, Any], data_dir: Path | None = None,
                       *, now: str | None = None) -> dict[str, Any]:
    """Log the owner's own label for a blind item. Only before the reveal, only once."""
    item = _find(item_id, data_dir)
    if not item.blind:
        raise ReviewError("this item is not blind; review it with the suggestion shown")
    log = load_log(data_dir)
    if any(e["item_id"] == item_id and e["event"] in ("blind_label", "decision") for e in log):
        raise ReviewError("a blind label is already on file for this item")
    label = clean_label(form)
    line = {"event": "blind_label", "ts": now or _now(), "item_id": item.id,
            "party": item.party, "input_hash": item.input_hash,
            "prompt_version": item.prompt_version, "label": label,
            "agree": agreement(item, label)}
    _append(data_dir, line)
    return line


def record_decision(item_id: str, action: str, form: dict[str, Any] | None = None,
                    data_dir: Path | None = None, *, now: str | None = None) -> dict[str, Any]:
    """Approve (adopt the suggestion), edit (the owner's label) or reject. A blind item
    cannot be decided until its blind label is on file."""
    if action not in ACTIONS:
        raise ReviewError(f"action must be one of {', '.join(ACTIONS)}")
    item = _find(item_id, data_dir)
    log = load_log(data_dir)
    if any(e["item_id"] == item_id and e["event"] == "decision" for e in log):
        raise ReviewError("this item is already decided")
    if item.blind and not any(
        e["item_id"] == item_id and e["event"] == "blind_label" for e in log
    ):
        raise ReviewError("blind item: enter your own label before the suggestion is shown")
    line: dict[str, Any] = {"event": "decision", "ts": now or _now(), "item_id": item.id,
                            "party": item.party, "input_hash": item.input_hash,
                            "prompt_version": item.prompt_version, "action": action,
                            "blind": item.blind}
    if action == "approve":
        line["label"] = {"takes_policy_position": item.suggestion.get("stance") != "none", **{
            k: item.suggestion.get(k) for k in
            ("topic", "stance", "proposition", "specificity", "priority_signal")}}
        line["agree"] = agreement(item, line["label"])
    elif action == "edit":
        line["label"] = clean_label(form or {})
        line["agree"] = agreement(item, line["label"])
    _append(data_dir, line)
    return line


# --- running precision ------------------------------------------------------------------


@dataclass
class Running:
    """Precision per field from the blind labels (unanchored), plus the anchored number
    from every approve/edit for comparison. `window` blind labels at most."""

    window: int
    blind_items: int
    blind: dict[str, dict[str, Tally]] = field(default_factory=dict)
    anchored: dict[str, Tally] = field(default_factory=dict)


def running_precision(data_dir: Path | None = None, *, window: int | None = None) -> Running:
    if window is None:
        window = prompt_eval.load_bar().rolling_blind_window
    log = load_log(data_dir)
    recent = deque((e for e in log if e["event"] == "blind_label"), maxlen=window)
    result = Running(
        window=window, blind_items=len(recent),
        blind={f: {"all": Tally(), "D": Tally(), "R": Tally()} for f in SCORED},
        anchored={f: Tally() for f in SCORED},
    )
    for entry in recent:
        for name, ok in entry["agree"].items():
            for bucket in ("all", entry["party"]):
                tally = result.blind[name].setdefault(bucket, Tally())
                tally.called += 1
                tally.correct += int(ok)
    for entry in log:
        if entry["event"] == "decision" and "agree" in entry:
            for name, ok in entry["agree"].items():
                result.anchored[name].called += 1
                result.anchored[name].correct += int(ok)
    return result


# --- the publish gate -------------------------------------------------------------------


@dataclass(frozen=True)
class Gate:
    open: bool
    reasons: tuple[str, ...]


def publish_gate(data_dir: Path | None = None, *, thresholds_dir: Path | None = None) -> Gate:
    """Closed unless every condition in the module docstring holds. `reasons` says why."""
    bar = prompt_eval.load_bar(thresholds_dir)
    reasons: list[str] = []
    if not bar.ratified:
        who = f", proposed by {bar.proposed_by}" if bar.proposed_by else ""
        reasons.append(f"the Q-K precision bar is not ratified by the owner{who}")
    running = running_precision(data_dir, window=bar.rolling_blind_window)
    for name, minimum in bar.fields.items():
        precision = running.blind[name]["all"].precision
        if precision is not None and precision < minimum:
            reasons.append(f"rolling blind precision on {name} is {precision:.0%}, below "
                           f"its {minimum:.0%} bar")
    if not ARCHIVE_PATH_BUILT:
        reasons.append("categorized statements cannot be archived yet (task 3: archive.org "
                       "keys); nothing unarchived publishes")
    return Gate(open=not reasons, reasons=tuple(reasons))


def approved(data_dir: Path | None = None) -> list[dict[str, Any]]:
    """Every approve/edit decision, newest last. Gitignored; publishes nowhere."""
    return [e for e in load_log(data_dir)
            if e["event"] == "decision" and e["action"] in ("approve", "edit")]


def export_approved(data_dir: Path | None = None, *,
                    thresholds_dir: Path | None = None) -> list[Path]:
    """The only door from the review log toward `data/statements/`. Refuses while the gate
    is closed. With it open, the export goes through `curation/statements.build_statement`
    (verified capture required) — and that path is condition 3, not built yet."""
    gate = publish_gate(data_dir, thresholds_dir=thresholds_dir)
    if not gate.open:
        raise PublishGateClosed("nothing exported: " + "; ".join(gate.reasons))
    raise PublishGateClosed(  # pragma: no cover — unreachable while ARCHIVE_PATH_BUILT is False
        "export through build_statement is built together with the archive path (task 3)"
    )
