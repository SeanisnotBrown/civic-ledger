"""Score the triage and categorizer prompts against the owner's hand-labeled set (§5 Phase 3
task 4), field by field and party by party, against the Q-K precision bar.

The answer key is the owner's: `docs/labeling/2026-10-22-eval-set.csv` (branch
`p3-labeling-set`), one row per statement, the `text` column exactly what the AI reads.
A row whose `takes_policy_position` is still blank is UNLABELED and skipped: it is not a
wrong answer, it is a row nobody has answered yet.

## The pipeline being scored

The same order production uses. The triage prompt reads every labeled row; the
categorizer reads only the rows the triage passed, as it will in a real run. So a
categorizer call on a row the owner labeled `no` is a real false positive — exactly the
statement that would reach his review queue with a wrong suggestion.

## Precision, per field

Precision is the share of the AI's CALLS on a field that the owner's own label agrees
with — the thing Q-K bars, because a call is what reaches the owner as a suggestion:

  * `takes_policy_position` — over the triage's `true` calls; correct when the owner said
    `yes`. Reported, no bar (Q-K sets none for it).
  * `stance` — over the categorizer's `for` / `against` calls (Q-K's own wording); correct
    when the owner said `yes` with the same stance. A `mixed` call is counted separately.
  * `topic` — over the categorizer's non-null topics; correct when the owner said `yes`
    and the AI's one topic is the label's primary OR its optional secondary topic
    (`topic_secondary`; owner ruling R1, 2026-10-23). The AI still returns one topic.
    `topic_primary_only` scores the same calls against the primary alone, so the effect
    of R1 stays visible; it has no bar and is never a D/R gap flag.
  * `priority_signal` — over the categorizer's `true` calls; correct when the owner said
    `yes`. False positives are the harmful direction (Q-K).
  * `specificity` — over the categorizer's non-null levels; correct on the same level.
  * `proposition` — never scored (owner ruling 2026-10-22: reference only).

Every field is also split by party, and a D/R gap wider than the bar's
`party_gap_max_points` is flagged for owner review. A bar is only ASSESSED when the set
has at least `min_labeled_rows` labeled rows; below that the report is titled "N-row smoke
test, not a precision measurement" and says no bar was assessed.

## Spend

Every call goes through `ingest/ai.py` (hashed, cached, logged, capped). The run's cap is
`--cap`, which may LOWER the `ai.yaml` cap for this run and can never raise it. Calls are
sequential with `reserve=True`, so the cap is exact. A refusal or malformed answer is "no
answer" for that row, counted and reported; any other API error stops the run, and the
report says how far it got. Re-runs are free: answers are cached by input hash.

The committed report holds counts only, never the model's labels: the repository holds
counts, never answers (the same rule as `ingest/triage_run.py`). Per-row agree/disagree
marks go to a gitignored side file under `data/raw/labeling/`, because next to the owner's
public labels they would reveal the model's answer per statement. The answers themselves
are in the gitignored cache the audit log's `input_hash` names.

    uv run ingest prompt-eval --labels data/raw/labeling/eval-set.csv --ids EV01-EV10
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from ingest import ai
from ingest.cache import atomic_write_text, repo_root

TRIAGE = "triage_statement"
CATEGORIZE = "categorize_statement"
PARTIES = ("D", "R")
# Report order. The four Q-K fields first, then the triage field, which has no bar.
FIELDS = ("stance", "topic", "priority_signal", "specificity", "takes_policy_position")
# Every reported field. `topic_primary_only` is information only (`topic` scored against
# the label's primary alone, as before owner ruling R1): it is not in FIELDS, so it has no
# bar, is never a D/R gap flag and never closes the publish gate.
REPORTED = ("stance", "topic", "topic_primary_only", "priority_signal", "specificity",
            "takes_policy_position")
DEFAULT_CAP_USD = 0.50

EXIT_OK = 0
EXIT_STOPPED = 2


class EvalError(RuntimeError):
    """The labels file or the precision bar is unusable."""


# --- the bar (Q-K) ---------------------------------------------------------------------


@dataclass(frozen=True)
class PrecisionBar:
    """`thresholds.yaml` `categorizer_precision`. `ratified` is False or the date string."""

    ratified: bool
    ratified_on: str | None
    proposed_by: str | None
    min_labeled_rows: int
    fields: dict[str, float]
    party_gap_max_points: float
    rolling_blind_window: int


def load_bar(data_dir: Path | None = None) -> PrecisionBar:
    base = data_dir if data_dir is not None else repo_root() / "data"
    raw = yaml.safe_load((base / "config" / "thresholds.yaml").read_text(encoding="utf-8"))
    entry = (raw or {}).get("categorizer_precision")
    if not isinstance(entry, dict):
        raise EvalError("thresholds.yaml has no `categorizer_precision` entry (Q-K)")
    try:
        mark = entry["ratified"]
        # Ratified means the owner wrote the date he approved it, quoted or not (YAML reads
        # an unquoted date as a date). False, null, an empty string or a bare `true` with
        # no date all leave the bar unratified.
        if isinstance(mark, date):
            mark = mark.isoformat()
        on = mark.strip() if isinstance(mark, str) and mark.strip() else None
        return PrecisionBar(
            ratified=on is not None,
            ratified_on=on,
            proposed_by=entry.get("proposed_by"),
            min_labeled_rows=int(entry["min_labeled_rows"]),
            fields={k: float(v) for k, v in entry["fields"].items()},
            party_gap_max_points=float(entry["party_gap_max_points"]),
            rolling_blind_window=int(entry["rolling_blind_window"]),
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise EvalError(f"thresholds.yaml categorizer_precision is incomplete: {exc}") from exc


# --- the labels ------------------------------------------------------------------------


@dataclass(frozen=True)
class Label:
    """The owner's answer for one statement, normalized. Fields beyond
    `takes_policy_position` are None when he left them blank (always, on a `no` row)."""

    takes_policy_position: bool
    topic: str | None = None
    stance: str | None = None
    specificity: int | None = None
    priority_signal: bool | None = None
    # Owner ruling R1, 2026-10-23: an optional second policy area. A sheet without the
    # column (the original 60) reads as None.
    topic_secondary: str | None = None


@dataclass(frozen=True)
class Row:
    id: str
    party: str
    text: str
    label: Label
    # True when the row's `notes` say the label is not the owner's own reviewed judgment
    # (`COPILOT-LABELED` / `owner-unreviewed`). Such a label can be scored for information,
    # but it can never count toward Q-K: only owner-reviewed labels measure precision.
    unreviewed: bool = False


# The bias flag the labeling sheet puts in `notes` on a label the owner has not reviewed.
UNREVIEWED_FLAG = re.compile(r"copilot-labeled|owner-unreviewed", re.IGNORECASE)


def _yes_no(value: str, *, column: str, row_id: str) -> bool | None:
    v = value.strip().lower()
    if not v:
        return None
    if v in ("yes", "y", "true"):
        return True
    if v in ("no", "n", "false"):
        return False
    raise EvalError(f"{row_id}: `{column}` must be yes or no, got {value!r}")


def _label(raw: dict[str, str]) -> Label | None:
    row_id = raw.get("id", "?")
    takes = _yes_no(raw.get("takes_policy_position", ""), column="takes_policy_position",
                    row_id=row_id)
    if takes is None:
        return None
    if not takes:
        return Label(takes_policy_position=False)
    stance = raw.get("stance", "").strip().lower() or None
    if stance is not None and stance not in ("for", "against", "mixed", "none"):
        raise EvalError(f"{row_id}: stance must be for/against/mixed/none, got {stance!r}")
    spec_raw = raw.get("specificity", "").strip()
    try:
        specificity = int(spec_raw) if spec_raw else None
    except ValueError as exc:
        raise EvalError(f"{row_id}: specificity must be 1, 2 or 3, got {spec_raw!r}") from exc
    return Label(
        takes_policy_position=True,
        topic=raw.get("topic", "").strip() or None,
        stance=stance,
        specificity=specificity,
        priority_signal=_yes_no(raw.get("priority_signal", ""), column="priority_signal",
                                row_id=row_id),
        topic_secondary=(raw.get("topic_secondary") or "").strip() or None,
    )


def parse_ids(spec: str | None) -> set[str] | None:
    """`EV01-EV10,EV14` -> the ids. None means every row."""
    if not spec:
        return None
    ids: set[str] = set()
    for part in spec.split(","):
        part = part.strip()
        m = re.fullmatch(r"([A-Za-z]+)(\d+)-(?:[A-Za-z]+)?(\d+)", part)
        if m:
            prefix, lo, hi = m.group(1), int(m.group(2)), int(m.group(3))
            width = len(m.group(2))
            ids.update(f"{prefix}{n:0{width}d}" for n in range(lo, hi + 1))
        elif part:
            ids.add(part)
    return ids


def read_labels(path: Path, ids: set[str] | None = None) -> tuple[list[Row], list[str]]:
    """(labeled rows, ids skipped as unlabeled), in file order. `utf-8-sig`: the sheet is
    saved by Excel with a byte-order mark."""
    rows: list[Row] = []
    unlabeled: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            if ids is not None and raw["id"] not in ids:
                continue
            label = _label(raw)
            if label is None:
                unlabeled.append(raw["id"])
                continue
            rows.append(Row(id=raw["id"], party=raw["party"].strip(), text=raw["text"],
                            label=label,
                            unreviewed=bool(UNREVIEWED_FLAG.search(raw.get("notes") or ""))))
    return rows, unlabeled


# --- scoring ---------------------------------------------------------------------------


@dataclass
class Prediction:
    """What the pipeline answered for one row. None = not asked or no answer."""

    takes_policy_position: bool | None = None
    categorized: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


def _same_topic(a: str, b: str) -> bool:
    norm = lambda s: " ".join(s.split()).casefold()  # noqa: E731
    return norm(a) == norm(b)


def calls(row: Row, pred: Prediction) -> dict[str, bool]:
    """For each field the AI made a call on for this row: did the owner agree?"""
    owner = row.label
    out: dict[str, bool] = {}
    if pred.takes_policy_position:
        out["takes_policy_position"] = owner.takes_policy_position
    cat = pred.categorized
    if not cat:
        return out
    yes = owner.takes_policy_position
    if cat.get("stance") in ("for", "against"):
        out["stance"] = yes and owner.stance == cat["stance"]
    if cat.get("topic"):
        primary = yes and owner.topic is not None and _same_topic(owner.topic, cat["topic"])
        secondary = (yes and owner.topic_secondary is not None
                     and _same_topic(owner.topic_secondary, cat["topic"]))
        out["topic"] = primary or secondary  # owner ruling R1, 2026-10-23
        out["topic_primary_only"] = primary
    if cat.get("priority_signal") is True:
        out["priority_signal"] = yes and owner.priority_signal is True
    if cat.get("specificity") is not None:
        out["specificity"] = yes and owner.specificity == cat["specificity"]
    return out


@dataclass
class Tally:
    called: int = 0
    correct: int = 0

    @property
    def precision(self) -> float | None:
        return self.correct / self.called if self.called else None


@dataclass
class Score:
    rows: int
    unlabeled: list[str]
    by_field: dict[str, dict[str, Tally]]  # field -> "all" | party -> Tally
    per_row: dict[str, dict[str, bool]]
    no_answer: list[str]
    mixed_calls: int
    triage_rejected_owner_yes: int
    unreviewed: list[str] = field(default_factory=list)  # ids whose label is not the owner's


def score(rows: Iterable[Row], preds: dict[str, Prediction], unlabeled: list[str]) -> Score:
    rows = list(rows)
    by_field = {f: {"all": Tally(), **{p: Tally() for p in PARTIES}} for f in REPORTED}
    per_row: dict[str, dict[str, bool]] = {}
    no_answer: list[str] = []
    mixed = 0
    missed = 0
    for row in rows:
        pred = preds.get(row.id, Prediction())
        if pred.errors:
            no_answer.append(row.id)
        if pred.takes_policy_position is False and row.label.takes_policy_position:
            missed += 1
        if pred.categorized and pred.categorized.get("stance") == "mixed":
            mixed += 1
        verdicts = calls(row, pred)
        per_row[row.id] = verdicts
        for name, ok in verdicts.items():
            for bucket in ("all", row.party):
                tally = by_field[name].setdefault(bucket, Tally())
                tally.called += 1
                tally.correct += int(ok)
    return Score(rows=len(rows), unlabeled=unlabeled, by_field=by_field, per_row=per_row,
                 no_answer=no_answer, mixed_calls=mixed, triage_rejected_owner_yes=missed,
                 unreviewed=[r.id for r in rows if r.unreviewed])


def party_gap_points(tallies: dict[str, Tally]) -> float | None:
    """|D - R| in percentage points, or None when either party has no calls."""
    d, r = tallies["D"].precision, tallies["R"].precision
    if d is None or r is None:
        return None
    return abs(d - r) * 100


def bar_status(name: str, tally: Tally, bar: PrecisionBar, rows: int,
               unreviewed: int = 0) -> str:
    if name not in bar.fields:
        return "no bar"
    if unreviewed:
        return f"not assessed ({unreviewed} labels owner-unreviewed)"
    if rows < bar.min_labeled_rows:
        return f"not assessed (n={rows} < {bar.min_labeled_rows})"
    if tally.precision is None:
        return "not assessed (no calls)"
    return "meets" if tally.precision >= bar.fields[name] else "BELOW"


def gap_flags(result: Score, bar: PrecisionBar) -> list[str]:
    """Every field whose D/R gap passes the bar: flagged for owner review."""
    flags = []
    for name in FIELDS:
        gap = party_gap_points(result.by_field[name])
        if gap is not None and gap > bar.party_gap_max_points:
            flags.append(name)
    return flags


# --- running the prompts ---------------------------------------------------------------


@dataclass
class Outcome:
    status: str = "complete"  # complete | cap | api-error
    detail: str = ""


def predict(run: ai.Run, rows: list[Row]) -> tuple[dict[str, Prediction], Outcome]:
    """Triage every row, categorize what it passes. Sequential: one call in flight, so a
    small cap is never tripped by reservations for calls that were never going to be made."""
    preds: dict[str, Prediction] = {}
    outcome = Outcome()
    for row in rows:
        pred = preds.setdefault(row.id, Prediction())
        try:
            try:
                verdict = run.call(TRIAGE, row.text, reserve=True)
                pred.takes_policy_position = bool(verdict.data["takes_policy_position"])
            except ai.AiResponseError as exc:
                pred.errors.append(str(exc))
                continue
            if not pred.takes_policy_position:
                continue
            try:
                pred.categorized = run.call(CATEGORIZE, row.text, reserve=True).data
            except ai.AiResponseError as exc:
                pred.errors.append(str(exc))
        except ai.AiCapReached as exc:
            outcome = Outcome("cap", str(exc))
            break
        except Exception as exc:  # noqa: BLE001 — any API failure stops the run, reported
            outcome = Outcome("api-error", f"{type(exc).__name__}: {exc}")
            break
    return preds, outcome


# --- the report ------------------------------------------------------------------------


def _pct(t: Tally) -> str:
    return "—" if t.precision is None else f"{t.precision:.0%} ({t.correct}/{t.called})"


def _field_table(result: Score, bar: PrecisionBar) -> list[str]:
    """One precision table: each field, all and by party, against its bar."""
    lines = [
        "| Field | Bar | All | D | R | D/R gap | Status |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name in REPORTED:
        t = result.by_field[name]
        gap = party_gap_points(t)
        bar_text = f"{bar.fields[name]:.0%}" if name in bar.fields else "none"
        gap_text = "—" if gap is None else f"{gap:.0f} pts"
        status = bar_status(name, t["all"], bar, result.rows, len(result.unreviewed))
        lines.append(
            f"| `{name}` | {bar_text} | {_pct(t['all'])} | {_pct(t['D'])} | {_pct(t['R'])} | "
            f"{gap_text} | {status} |"
        )
    return lines


def title(rows: int, bar: PrecisionBar, unreviewed: int = 0) -> str:
    if unreviewed:
        return (f"{rows} rows, {unreviewed} with owner-unreviewed AI labels: agreement check, "
                "not a Q-K measurement")
    if rows < bar.min_labeled_rows:
        return f"{rows}-row smoke test, not a precision measurement"
    return f"Precision on {rows} hand-labeled statements"


def render(
    *,
    result: Score,
    bar: PrecisionBar,
    outcome: Outcome,
    run: ai.Run,
    labels_path: str,
    ids: str | None,
    generated: str,
    rows_path: str,
    splits: tuple[tuple[str, Score], ...] = (),
) -> str:
    tri = run.config.task(TRIAGE)
    cat = run.config.task(CATEGORIZE)
    unreviewed = len(result.unreviewed)
    smoke = result.rows < bar.min_labeled_rows and not unreviewed
    bar_state = f"RATIFIED {bar.ratified_on}" if bar.ratified else "NOT ratified"
    lines = [
        f"# Prompt evaluation — {title(result.rows, bar, unreviewed)}",
        "",
        f"Generated {generated} by `uv run ingest prompt-eval`. Labels: `{labels_path}`"
        + (f", rows `{ids}`" if ids else "") + ".",
        "",
        f"- Triage: `{tri.model}`, prompt `{tri.prompt_version}` "
        f"(sha256 `{tri.prompt_sha256[:12]}`), effort `{tri.effort}`",
        f"- Categorizer: `{cat.model}`, prompt `{cat.prompt_version}` "
        f"(sha256 `{cat.prompt_sha256[:12]}`), effort `{cat.effort}`",
        f"- Q-K bar: {bar_state}"
        + (f" (proposed by {bar.proposed_by})" if bar.proposed_by else ""),
        "",
    ]
    if smoke:
        lines += [
            f"**This is a {result.rows}-row smoke test, not a precision measurement.** It "
            f"shows the prompts, the scoring and the spend cap working end to end. No bar "
            f"is assessed below {bar.min_labeled_rows} labeled rows, and a gap between the "
            "parties on this few rows is noise, not a finding.",
            "",
        ]
    if unreviewed:
        lines += [
            f"**{unreviewed} of {result.rows} labels are AI (copilot) labels, "
            "owner-unreviewed. This is AI-vs-AI agreement, NOT a valid Q-K measurement. The "
            "publish gate stays closed until the owner reviews or relabels them.**",
            "",
        ]
    lines += [
        "## Precision by field",
        "",
        "Precision = the share of the AI's calls on a field that the label agrees with. "
        "`proposition` is never scored (owner ruling 2026-10-22). `topic` counts the AI's "
        "one topic correct when it is the label's primary or secondary topic (owner ruling "
        "R1, 2026-10-23); `topic_primary_only` scores the same calls against the primary "
        "alone, for information: it has no bar and is never a D/R gap flag.",
        "",
        *_field_table(result, bar),
    ]
    for heading, part in splits:
        lines += ["", f"### {heading} ({part.rows} rows)", "", *_field_table(part, bar)]
    flags = gap_flags(result, bar)
    lines += [""]
    if flags and not smoke and not unreviewed:
        lines.append(
            f"**STOP for owner review:** the D/R gap passes {bar.party_gap_max_points:.0f} "
            f"points on {', '.join(f'`{f}`' for f in flags)}."
        )
    elif flags and unreviewed:
        lines.append(
            f"Gap over {bar.party_gap_max_points:.0f} points on "
            f"{', '.join(f'`{f}`' for f in flags)} — measured partly against owner-unreviewed "
            "labels, so it is a lead to check, not a finding."
        )
    elif flags:
        lines.append(
            f"Gap over {bar.party_gap_max_points:.0f} points on "
            f"{', '.join(f'`{f}`' for f in flags)} — on a smoke test this is noise and does "
            "not stop anything."
        )
    else:
        lines.append(f"No field's D/R gap passes {bar.party_gap_max_points:.0f} points.")
    lines += [
        "",
        "## Counts",
        "",
        "| | |",
        "| --- | --- |",
        f"| Labeled rows scored | {result.rows} |",
        f"| Rows skipped as not yet labeled | {len(result.unlabeled)} |",
        f"| Rows whose label is owner-unreviewed (copilot) | {len(result.unreviewed)} |",
        f"| Rows with no answer (refusal or malformed) | {len(result.no_answer)}"
        + (f": {', '.join(result.no_answer)}" if result.no_answer else "") + " |",
        f"| Label said yes, triage said no (missed; not a precision error) | "
        f"{result.triage_rejected_owner_yes} |",
        f"| Categorizer `mixed` stance calls (outside the for/against bar) | "
        f"{result.mixed_calls} |",
        f"| How the run ended | `{outcome.status}`"
        + (f": {outcome.detail}" if outcome.detail else "") + " |",
        f"| API calls (cache hits are free) | {run.calls} ({run.cache_hits} cache hits) |",
        f"| Spent | ${run.spent_usd:.4f} of a ${run.cap:.2f} run cap |",
        "",
        "Per-row agreement marks are NOT in this report: next to the owner's public labels "
        "they would give away the model's answer for each statement (counts, never "
        f"answers). They are in the gitignored `{rows_path}`.",
    ]
    return "\n".join(lines) + "\n"


def render_rows(result: Score) -> str:
    """Per-row agree/disagree marks, for the gitignored side file only."""
    lines = [
        "# Per row: did the owner agree with each call the AI made?",
        "",
        "`yes` / `no` per call; blank = the AI made no call on that field. Gitignored: with "
        "the owner's labels these marks reveal the model's answer per statement.",
        "",
        "| Row | " + " | ".join(f"`{f}`" for f in REPORTED) + " |",
        "| --- | " + " | ".join("---" for _ in REPORTED) + " |",
    ]
    for row_id, verdicts in result.per_row.items():
        cells = [
            "" if f not in verdicts else ("yes" if verdicts[f] else "no") for f in REPORTED
        ]
        lines.append(f"| {row_id} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


# --- the recorded measurement (what the publish gate reads) ------------------------------


def measurement_path(data_dir: Path | None = None) -> Path:
    base = data_dir if data_dir is not None else repo_root() / "data"
    return base / "quality" / "categorizer-precision.json"


def measurement(result: Score, bar: PrecisionBar, config: ai.AiConfig, *,
                generated: str) -> dict[str, Any]:
    """The held-out measurement in counts only — never a per-row mark or a model answer.
    Written only for a complete run on at least `min_labeled_rows` labeled rows; the gate
    trusts it only while the prompt versions and hashes it names are still in `ai.yaml`."""
    tasks = {name: {"prompt_version": config.task(name).prompt_version,
                    "prompt_sha256": config.task(name).prompt_sha256,
                    "model": config.task(name).model} for name in (TRIAGE, CATEGORIZE)}
    fields = {}
    # `topic_primary_only` carries status "no bar", which the publish gate ignores.
    for name in REPORTED:
        tallies = result.by_field[name]
        fields[name] = {
            "called": {k: t.called for k, t in sorted(tallies.items())},
            "correct": {k: t.correct for k, t in sorted(tallies.items())},
            "status": bar_status(name, tallies["all"], bar, result.rows,
                                 len(result.unreviewed)),
        }
    # How many labels are NOT the owner's reviewed judgment (copilot-labeled). The publish
    # gate stays closed while this is above zero: only owner-reviewed labels satisfy Q-K.
    return {"generated": generated, "labeled_rows": result.rows, "tasks": tasks,
            "fields": fields, "party_gap_flags": gap_flags(result, bar),
            "unreviewed_labels": len(result.unreviewed)}


# --- command ---------------------------------------------------------------------------


def run(
    argv: list[str] | None = None,
    *,
    completer: ai.Completer | None = None,
    data_dir: Path | None = None,
) -> int:
    """`completer` and `data_dir` are the test seam: a fake API, and a cache and audit log
    written somewhere other than the repository's `data/`."""
    parser = argparse.ArgumentParser(prog="ingest prompt-eval", description=__doc__.split(
        "\n")[0])
    parser.add_argument("--labels", required=True, help="the owner's labeled CSV")
    parser.add_argument("--ids", help="rows to score, e.g. EV01-EV10 (default: every row)")
    parser.add_argument("--cap", type=float, default=DEFAULT_CAP_USD,
                        help="this run's dollar cap; may only LOWER the ai.yaml cap")
    parser.add_argument("--out", help="report path (default docs/research/<date>-prompt-eval.md)")
    args = parser.parse_args(argv)

    config = ai.load_config()
    if args.cap <= 0 or args.cap > config.per_run_cost_cap_usd:
        print(f"prompt-eval: --cap must be above 0 and at most the ai.yaml cap "
              f"(${config.per_run_cost_cap_usd:.2f}); it can only lower it")
        return EXIT_STOPPED
    bar = load_bar()
    rows, unlabeled = read_labels(Path(args.labels), parse_ids(args.ids))
    kwargs: dict[str, Any] = {"config": config, "cap_usd": args.cap, "data_dir": data_dir}
    if completer is not None:
        kwargs["completer"] = completer
    airun = ai.Run(**kwargs)
    print(f"prompt-eval: {len(rows)} labeled rows, {len(unlabeled)} unlabeled skipped; "
          f"cap ${args.cap:.2f}")
    preds, outcome = predict(airun, rows)
    result = score(rows, preds, unlabeled)
    splits: tuple[tuple[str, Score], ...] = ()
    if result.unreviewed:
        owner = [r for r in rows if not r.unreviewed]
        copilot = [r for r in rows if r.unreviewed]
        splits = (("Owner-labeled rows", score(owner, preds, [])),
                  ("Copilot-labeled rows, owner-unreviewed", score(copilot, preds, [])))
    now = datetime.now(UTC)
    out = Path(args.out) if args.out else (
        repo_root() / "docs" / "research" / f"{now:%Y-%m-%d}-prompt-eval.md"
    )
    rows_name = f"raw/labeling/{out.stem}-rows.md"
    rows_file = (data_dir if data_dir is not None else repo_root() / "data") / rows_name
    report = render(result=result, bar=bar, outcome=outcome, run=airun,
                    labels_path=args.labels, ids=args.ids,
                    generated=now.strftime("%Y-%m-%d %H:%M UTC"),
                    rows_path=f"data/{rows_name}", splits=splits)
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(out, report)
    rows_file.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(rows_file, render_rows(result))
    if outcome.status == "complete" and result.rows >= bar.min_labeled_rows:
        recorded = measurement_path(data_dir)
        recorded.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(recorded, json.dumps(
            measurement(result, bar, airun.config, generated=now.strftime("%Y-%m-%d")),
            indent=2, sort_keys=True) + "\n")
        print(f"prompt-eval: measurement recorded in {recorded}")
    print(f"prompt-eval: {outcome.status}; {airun.calls} calls, ${airun.spent_usd:.4f} "
          f"spent; report {out}")
    return EXIT_OK if outcome.status == "complete" else EXIT_STOPPED
