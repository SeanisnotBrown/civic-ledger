"""The first pass: every pre-filtered statement through the Haiku triage gate (§5 Phase 3
decision 3), and NOTHING after it.

**Owner ruling 2026-10-22 (step 9, option b): triage only.** The Opus categorizer waits
until its prompt has been tested against a held-out hand-labeled set of at least 50
statements (spec task 4); both prompts are still stubs. So this command can reach exactly
one AI task. It builds its `ai.Run` over a configuration holding `triage_statement` ALONE,
so a categorizer call is not merely avoided but impossible: `ai.py` would refuse it as an
unknown task before any request was built. `tests/test_triage_run.py` fails if a request
for any other task or model ever leaves this module.

Every call goes through `ingest/ai.py`, so each one is hashed, cached, written to the
tracked audit log and counted against the per-run cap — this module adds the batch, not a
second way to call the API.

## Order: newest first, one member at a time

Each member's statements are sorted newest first (decision 7's own order), then the queue
takes one from every member in turn, by member id. A run the cap stops part-way has
therefore triaged every member to the same depth, instead of spending the whole budget on
the members whose ids sort first or whose press offices publish most.

## Resumable

Each verdict is appended, as it arrives, to `data/raw/triage/<prompt_version>.jsonl`
(gitignored, like every model output: the repository holds counts, never answers). A
re-run reads it and skips every statement that already has a verdict for the SAME text;
a statement whose text has since changed is asked again. The file is per prompt version,
so a new prompt starts from nothing rather than inheriting the old prompt's answers.

## How a run ends

  * `complete` — every eligible statement has a verdict. Exit 0.
  * `limit` — `--limit` calls were made (a deliberate smoke run). Exit 0.
  * `cap` — the run reached `per_run_cost_cap_usd`; `ai.py` refused the next call and the
    run stopped cleanly. Exit 3. Re-run with the owner's say-so to continue.
  * `api-error` — the API still failed after the SDK's own retries. Exit 2. Nothing is
    lost: re-run to resume.

A refusal, a truncated answer or malformed JSON (`AiResponseError`) is recorded against
that statement and the run carries on; the statement has no verdict, so a re-run asks it
again. `ai.py` has already logged the failed call, because it was billed.

## Output

`docs/research/<UTC date>-triage-run.md`: counts per member and per pilot cell, the spend,
and how the run ended. Counts only — no statement text, no verdict for any one statement.

    uv run ingest triage-run              # the run
    uv run ingest triage-run --limit 20   # at most 20 calls: a live smoke run
    uv run ingest triage-run --dry-run    # what would be asked; no call
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anthropic
import yaml

from ingest import ai, prefilter
from ingest.cache import atomic_write_text, repo_root

TASK = "triage_statement"
VERDICT_FIELD = "takes_policy_position"

EXIT_OK = 0
EXIT_API_ERROR = 2
EXIT_CAP = 3

# How often the run reports progress to its log. A full pass is ~15,000 calls.
PROGRESS_EVERY = 250


def statement_key(statement: dict[str, Any]) -> str:
    """One statement's identity across runs: member, source and the collector's own id."""
    return "|".join(
        (statement["member_id"], statement.get("source", ""), statement.get("granule_id", ""))
    )


def statement_text(statement: dict[str, Any]) -> str:
    """What the gate reads: the turns the pre-filter kept, and nothing else. Not the title,
    not the member's name — the prompt judges what the text says."""
    return "\n\n".join(statement["segments"])


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def queue(survivors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every AI-eligible survivor, each member newest first, taken one member at a time.

    Vote explanations are not here: R3 (2026-10-14) keeps them as record and never sends
    them to the AI.
    """
    per_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for statement in survivors:
        if statement.get("ai_eligible", True):
            per_member[statement["member_id"]].append(statement)
    for items in per_member.values():
        items.sort(key=lambda s: (s.get("date", ""), s.get("granule_id", "")), reverse=True)
    order: list[dict[str, Any]] = []
    depth = max((len(items) for items in per_member.values()), default=0)
    for rank in range(depth):
        for member_id in sorted(per_member):
            items = per_member[member_id]
            if rank < len(items):
                order.append(items[rank])
    return order


def load_ledger(path: Path) -> dict[str, dict[str, Any]]:
    """Every verdict already recorded under this prompt version, by statement key. A later
    line for the same key replaces an earlier one."""
    if not path.exists():
        return {}
    ledger: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            ledger[entry["key"]] = entry
    return ledger


def has_verdict(statement: dict[str, Any], ledger: dict[str, dict[str, Any]]) -> bool:
    """True when this exact text already has a verdict."""
    entry = ledger.get(statement_key(statement))
    return entry is not None and entry["text_sha256"] == text_sha256(statement_text(statement))


@dataclass
class Outcome:
    """How one invocation went."""

    status: str = "complete"
    triaged: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    stop_detail: str = ""


def triage(
    run: ai.Run,
    statements: list[dict[str, Any]],
    ledger_path: Path,
    *,
    limit: int = 0,
    progress: Callable[[str], None] = print,
) -> Outcome:
    """Ask the gate about each statement in order, appending each verdict as it arrives.

    `statements` is what is still to do — the caller has already dropped those with a
    verdict. `limit` > 0 caps the number of calls made by THIS invocation.
    """
    outcome = Outcome()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    attempted = 0
    with ledger_path.open("a", encoding="utf-8") as ledger:
        for statement in statements:
            if limit and attempted >= limit:
                outcome.status = "limit"
                break
            text = statement_text(statement)
            attempted += 1
            try:
                result = run.call(TASK, text)
            except ai.AiCapReached as exc:
                outcome.status = "cap"
                outcome.stop_detail = str(exc)
                break
            except ai.AiResponseError as exc:
                outcome.errors.append({"key": statement_key(statement), "error": str(exc)})
                continue
            except anthropic.APIError as exc:
                outcome.status = "api-error"
                outcome.stop_detail = f"{type(exc).__name__}: {exc}"
                outcome.errors.append(
                    {"key": statement_key(statement), "error": outcome.stop_detail}
                )
                break
            entry = {
                "key": statement_key(statement),
                "member_id": statement["member_id"],
                "date": statement.get("date", ""),
                "source": statement.get("source", ""),
                "text_sha256": text_sha256(text),
                "input_hash": result.input_hash,
                VERDICT_FIELD: bool(result.data[VERDICT_FIELD]),
                "cached": result.cached,
            }
            ledger.write(json.dumps(entry, sort_keys=True) + "\n")
            ledger.flush()
            outcome.triaged += 1
            if outcome.triaged % PROGRESS_EVERY == 0:
                progress(
                    f"  triaged {outcome.triaged}, ${run.spent_usd:.4f} spent, "
                    f"{len(outcome.errors)} error(s)"
                )
    return outcome


def _pilot_cells(data_dir: Path) -> dict[str, str]:
    """Member id -> `"<party> <chamber>"`, from the drawn pilot."""
    pilot = yaml.safe_load(
        (data_dir / "config" / "statement-pilot.yaml").read_text(encoding="utf-8")
    )
    return {
        member["id"]: f"{cell['party']} {cell['chamber']}"
        for cell in pilot["cells"]
        for member in cell["members"]
    }


def tally(
    order: list[dict[str, Any]], ledger: dict[str, dict[str, Any]]
) -> dict[str, dict[str, int]]:
    """Per member: eligible, triaged, passed (a `true`), not passed, remaining."""
    rows: dict[str, dict[str, int]] = defaultdict(
        lambda: {"eligible": 0, "triaged": 0, "passed": 0, "not_passed": 0, "remaining": 0}
    )
    for statement in order:
        row = rows[statement["member_id"]]
        row["eligible"] += 1
        if has_verdict(statement, ledger):
            row["triaged"] += 1
            if ledger[statement_key(statement)][VERDICT_FIELD]:
                row["passed"] += 1
            else:
                row["not_passed"] += 1
        else:
            row["remaining"] += 1
    return dict(rows)


_COUNTS = ("eligible", "triaged", "passed", "not_passed", "remaining")


def render_report(
    *,
    rows: dict[str, dict[str, int]],
    cells: dict[str, str],
    names: dict[str, str],
    outcome: Outcome,
    run: ai.Run,
    task: ai.TaskConfig,
    per_member_cap: int,
    generated: str,
) -> str:
    """The run's count report. Counts only."""
    total = {k: sum(r[k] for r in rows.values()) for k in _COUNTS}
    lines = [
        "# Triage run — the first pass (Haiku), counts only",
        "",
        f"Generated {generated} by `uv run ingest triage-run`. Task `{task.name}`, model "
        f"`{task.model}`, prompt `{task.prompt_version}` (a STUB: nothing here may be "
        "published or counted toward precision).",
        "",
        "**The Opus categorizer was NOT called** (owner ruling 2026-10-22, step 9 option b): "
        "it waits for a prompt tested against at least 50 hand-labeled statements.",
        "",
        "## This invocation",
        "",
        "| | |",
        "| --- | --- |",
        f"| How it ended | `{outcome.status}` |",
        f"| Verdicts recorded this time | {outcome.triaged} |",
        f"| API calls made (cache hits are free) | {run.calls} ({run.cache_hits} cache hits) |",
        f"| Spent this time | ${run.spent_usd:.4f} of a ${run.cap:.2f} cap |",
        f"| Statements with no verdict because of an error | {len(outcome.errors)} |",
    ]
    if outcome.stop_detail:
        lines += ["", f"Stopped: {outcome.stop_detail}"]
    lines += [
        "",
        "## All runs under this prompt version",
        "",
        f"{total['eligible']} statements are eligible (pre-filter survivors, less the vote "
        f"explanations R3 keeps out of the AI). {total['triaged']} have a verdict: "
        f"**{total['passed']} take a position on an identifiable policy**, "
        f"{total['not_passed']} do not. {total['remaining']} are still to do.",
        "",
        "## Per pilot cell",
        "",
        "| Cell | Eligible | Triaged | Passed | Not passed | Remaining |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    by_cell: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(_COUNTS, 0))
    for member_id, row in rows.items():
        cell = by_cell[cells.get(member_id, "unknown")]
        for k in _COUNTS:
            cell[k] += row[k]
    for cell_name in sorted(by_cell):
        c = by_cell[cell_name]
        lines.append(
            f"| {cell_name} | {c['eligible']} | {c['triaged']} | {c['passed']} "
            f"| {c['not_passed']} | {c['remaining']} |"
        )
    lines += [
        "",
        "## Per member",
        "",
        f"\"Short of {per_member_cap}\" flags a member with fewer than decision 7's "
        f"{per_member_cap} passed statements once triage is finished: the categorizer "
        "would get less from them than its allowance.",
        "",
        "| Member | Cell | Eligible | Triaged | Passed | Not passed | Remaining | Flag |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for member_id in sorted(rows):
        r = rows[member_id]
        short = r["remaining"] == 0 and r["passed"] < per_member_cap
        lines.append(
            f"| {names.get(member_id, member_id)} ({member_id}) "
            f"| {cells.get(member_id, 'unknown')} | {r['eligible']} | {r['triaged']} "
            f"| {r['passed']} | {r['not_passed']} | {r['remaining']} "
            f"| {f'short of {per_member_cap}' if short else ''} |"
        )
    if outcome.errors:
        lines += ["", "## Errors this time (no verdict; a re-run asks again)", ""]
        lines += [f"* `{e['key']}` — {e['error']}" for e in outcome.errors]
    return "\n".join(lines) + "\n"


def run(
    argv: list[str] | None = None,
    *,
    completer: ai.Completer | None = None,
    now: Callable[[], datetime] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="ingest triage-run",
        description="P3 step 9 — the Haiku first pass only. Never calls the categorizer.",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="at most this many calls (0 = no limit)"
    )
    parser.add_argument("--dry-run", action="store_true", help="counts only; no call")
    args = parser.parse_args(argv)
    clock = now if now is not None else (lambda: datetime.now(UTC))

    root = repo_root()
    data_dir = root / "data"
    records, _parties, names = prefilter.load_all(data_dir)
    result = prefilter.run_prefilter(records, prefilter.load_text_failures(data_dir))
    config = ai.load_config(data_dir)
    # The categorizer is not in this configuration, so it cannot be called from here.
    triage_only = replace(config, tasks={TASK: config.task(TASK)})
    task = triage_only.task(TASK)

    ledger_path = data_dir / "raw" / "triage" / f"{task.prompt_version}.jsonl"
    order = queue(result["statements"])
    ledger = load_ledger(ledger_path)
    todo = [s for s in order if not has_verdict(s, ledger)]
    print(
        f"triage-run: {len(order)} eligible, {len(order) - len(todo)} already triaged under "
        f"{task.prompt_version}, {len(todo)} to do; cap ${triage_only.per_run_cost_cap_usd:.2f}"
    )
    print("  the Opus categorizer is NOT called by this command")
    if args.dry_run:
        print("  --dry-run: no call made")
        return EXIT_OK

    session = ai.Run(
        config=triage_only,
        completer=completer if completer is not None else ai._live_completer,
        data_dir=data_dir,
        now=clock,
    )
    outcome = triage(session, todo, ledger_path, limit=args.limit)

    rows = tally(order, load_ledger(ledger_path))
    report_dir = root / "docs" / "research"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = clock()
    report = report_dir / f"{stamp.date().isoformat()}-triage-run.md"
    atomic_write_text(
        report,
        render_report(
            rows=rows,
            cells=_pilot_cells(data_dir),
            names=names,
            outcome=outcome,
            run=session,
            task=task,
            per_member_cap=triage_only.max_statements_per_member_per_run,
            generated=stamp.isoformat(timespec="seconds"),
        ),
    )
    print(
        f"  {outcome.status}: {outcome.triaged} verdict(s), {session.calls} call(s), "
        f"${session.spent_usd:.4f} spent, {len(outcome.errors)} error(s)"
    )
    if outcome.stop_detail:
        print(f"  stopped: {outcome.stop_detail}")
    print(f"  report: {report.relative_to(root)}")
    if outcome.status == "cap":
        return EXIT_CAP
    if outcome.status == "api-error":
        return EXIT_API_ERROR
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
