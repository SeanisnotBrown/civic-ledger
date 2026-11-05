"""The run that fills the review queue (§5 Phase 3 tasks 3-5; owner decisions 2026-10-09
2-10): pre-filter -> triage gate -> archive capture -> categorizer -> review queue.

**Preview only (owner, 2026-11-04).** One capped run was approved so the owner can SEE
categorized statements locally. No valid Q-K measurement exists, so every queue item this
run writes carries `preview: copilot-run, owner-unreviewed`, and
`curation/review.py::export_approved` never exports a preview item, gate open or not.

## Count before spend (decision 4)

Every invocation first prints and saves, under `data/raw/categorize/`, the counts per
source, per member and after each filter step, the per-party drop rates at each step with
the fairness flag, and the estimated cost. Without `--approved-cap <usd>` it stops there,
having called nothing. With it, the run refuses when the estimate exceeds what is left of
that cap, and when live capture is not opted in: both before any AI call.

The estimate prices the worst case (every statement the gate has not answered passes) and
takes the HIGHER of two figures: each statement's length priced with the real prompt
size, and the mean cost of the live calls already in the audit log for this exact prompt
version. The second exists because the fixed constants in `prefilter.estimate_spend` were
measured on the first prompts: on 2026-11-04 the categorizer v3 calls logged $0.0245 each,
about twice what those constants give.

## Fairness (decision 4)

A step that drops one party's statements at a noticeably higher rate (`prefilter._uneven`)
stops the run for owner review. The pre-filter is checked before any spend, the triage
gate as soon as its verdicts are in and before the categorizer is called. Each step is
checked over all sources and per source, as the pre-filter report does. The procedural
rule's gap is the one the owner has accepted (R4, 2026-10-14). Any other flag stops the
run until `--fairness-reviewed <step>` says that step's flag has been reviewed; verdicts
already paid for stay in the ledger, so the re-run costs nothing to get back there.

## Who is asked

Decision 6: the pilot 40 only. Triage reads every eligible survivor. Decision 7: only each
member's newest `max_statements_per_member_per_run` statements the gate passed go on
(`--per-member` can lower it, never raise it); the rest stay cached. A text is queued once,
because a queue item's id is the text's fingerprint. Decision 8: those statements are
captured first, and only a statement with a live capture reaches the categorizer, so
nothing is paid for that could not publish later. The queue takes one statement from
every member in turn, so a run the cap stops has reached every member to about the same
depth.

## The cap (decisions 5 and 9)

`--approved-cap` is the owner's raise for one run, passed to `ai.Run` as its cap, so
`ai.yaml` stays at its default and nothing has to be restored. It covers the whole named
run: spend is saved to `data/raw/categorize/<run-name>-spend.json` and a resumed run gets
only what is left. The run stops at the cap and does not finish the batch.

## How a run ends

Exit 0 complete (or counted only); 2 api-error or an SPN2 429; 3 cap; 4 stopped
(`data/raw/triage.stop`); 5 live capture not opted in; 6 estimate over the cap; 7 a
fairness flag awaiting review; 8 archive.org unreachable. Every answer already received
is saved, and a re-run resumes: the ledger, the capture file and the queue are all skipped,
and the AI cache serves anything asked before. The exception is a failed capture among
this run's own statements, which every resume asks for again.

    uv run ingest categorize-run                                    # counts only, no call
    uv run ingest categorize-run --per-member 15                    # the same at 15
    uv run ingest categorize-run --approved-cap 20 --live-capture   # the paid run
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anthropic
import httpx

from curation import review
from ingest import ai, capture, prefilter, triage_run
from ingest.cache import atomic_write_text, repo_root

TRIAGE = triage_run.TASK
CATEGORIZE = "categorize_statement"
PREVIEW_MARK = "copilot-run, owner-unreviewed"
OUT_DIR = Path("raw") / "categorize"
DEFAULT_RUN_NAME = "preview-1"
# Most categorizer calls in flight. Few on purpose: each holds its upper-bound cost against
# the cap, and an Opus answer takes long enough that a small number already shortens the run.
DEFAULT_WORKERS = 4

# The one uneven rule the owner has accepted (R4, 2026-10-14).
OWNER_ACCEPTED_RULES = frozenset({"procedural"})
STEPS = ("prefilter", "triage")

EXIT_OK = 0
EXIT_API_ERROR = 2
EXIT_CAP = 3
EXIT_STOPPED = 4
EXIT_REFUSED = capture.EXIT_REFUSED
EXIT_OVER_CAP = 6
EXIT_FAIRNESS = 7
EXIT_UNREACHABLE = capture.EXIT_UNREACHABLE
_EXIT = {"cap": EXIT_CAP, "api-error": EXIT_API_ERROR, "stopped": EXIT_STOPPED}


# --- who is asked --------------------------------------------------------------------------


def pilot_only(records: list[dict[str, Any]], pilot: set[str]) -> list[dict[str, Any]]:
    """Decision 6: the 40-member sample and no one else."""
    return [r for r in records if r.get("member_id") in pilot]


def select(order: list[dict[str, Any]], verdicts: dict[str, dict[str, Any]], per_member: int,
           *, assume_pass: bool = False) -> list[dict[str, Any]]:
    """Each member's newest `per_member` statements the gate passed, in queue order (one
    member at a time), each text once. `assume_pass` counts an unanswered statement as
    passed: the worst case, for the estimate."""
    taken: Counter[str] = Counter()
    seen: set[str] = set()
    chosen: list[dict[str, Any]] = []
    for statement in order:
        sha = triage_run.fingerprint(statement)
        entry = verdicts.get(sha)
        passed = entry[triage_run.VERDICT_FIELD] if entry else assume_pass
        member = statement["member_id"]
        if passed and sha not in seen and taken[member] < per_member:
            seen.add(sha)
            taken[member] += 1
            chosen.append(statement)
    return chosen


# --- fairness ------------------------------------------------------------------------------


def prefilter_rows(result: dict[str, Any], parties: dict[str, str]) -> list[dict[str, Any]]:
    """Drop rate per party per rule, over all sources and per source."""
    judged = result["judged_records"]
    rows: list[dict[str, Any]] = []
    for source in (None, *sorted({r.get("source", "") for r in judged})):
        for row in prefilter.fairness(judged, result["drops"], parties, source=source):
            rows.append({**row, "scope": source or "all sources"})
    return rows


def triage_rows(order: list[dict[str, Any]], verdicts: dict[str, dict[str, Any]],
                parties: dict[str, str]) -> list[dict[str, Any]]:
    """The gate's drop rate per party, over the statements it has answered, over all
    sources and per source. Same shape and same test as the pre-filter's rows."""
    answered = [s for s in order if triage_run.fingerprint(s) in verdicts]
    rows: list[dict[str, Any]] = []
    if not answered:
        return rows
    for source in (None, *sorted({s.get("source", "") for s in answered})):
        scoped = [s for s in answered if source is None or s.get("source") == source]
        row: dict[str, Any] = {"rule": "triage-gate", "scope": source or "all sources"}
        for party in ("D", "R"):
            mine = [s for s in scoped if parties.get(s["member_id"]) == party]
            dropped = sum(not verdicts[triage_run.fingerprint(s)][triage_run.VERDICT_FIELD]
                          for s in mine)
            row[party] = dropped
            row[f"{party}_turns"] = len(mine)
            row[f"{party}_rate"] = round(dropped / len(mine) * 100, 1) if mine else 0.0
        row["turns"] = row["D"] + row["R"]
        # A party with nothing in this scope has no rate to compare.
        row["uneven"] = bool(row["D_turns"] and row["R_turns"]) and prefilter._uneven(
            row["D_rate"], row["R_rate"], row["turns"])
        rows.append(row)
    return rows


def new_flags(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Uneven rows the owner has not already ruled on."""
    return [r for r in rows if r["uneven"] and r["rule"] not in OWNER_ACCEPTED_RULES]


# --- the estimate --------------------------------------------------------------------------


def measured(data_dir: Path, task: ai.TaskConfig) -> dict[str, float] | None:
    """Mean cost and output tokens of the live calls logged for this exact prompt."""
    costs: list[float] = []
    outputs: list[int] = []
    for path in sorted((data_dir / "quality" / "ai-calls").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line) if line.strip() else {}
            if (entry.get("task"), entry.get("prompt_version")) == (
                task.name, task.prompt_version
            ) and not entry.get("cached"):
                costs.append(entry["cost_usd"])
                outputs.append(entry["output_tokens"])
    if not costs:
        return None
    return {"calls": len(costs), "mean_usd": sum(costs) / len(costs),
            "mean_output_tokens": sum(outputs) / len(outputs)}


def _stage(config: ai.AiConfig, task_name: str, statements: list[dict[str, Any]],
           default_output: int, data_dir: Path) -> dict[str, Any]:
    """One stage's cost, by length and by the logged mean; the higher is the estimate."""
    task = config.task(task_name)
    logged = measured(data_dir, task)
    output = logged["mean_output_tokens"] if logged else default_output
    prompt = ai.prompt_text(task) + json.dumps(task.output_schema)
    overhead = len(prompt) // prefilter.CHARS_PER_TOKEN + ai.FRAMING_TOKENS
    tokens = sum(len(triage_run.statement_text(s)) // prefilter.CHARS_PER_TOKEN + overhead
                 for s in statements)
    by_length = ai.cost_usd(config.price(task.model), tokens, int(output * len(statements)))
    by_log = logged["mean_usd"] * len(statements) if logged else 0.0
    return {"statements": len(statements), "by_length_usd": round(by_length, 2),
            "by_logged_mean_usd": round(by_log, 2),
            "logged_calls": int(logged["calls"]) if logged else 0,
            "usd": round(max(by_length, by_log), 2)}


def estimate(config: ai.AiConfig, order: list[dict[str, Any]],
             verdicts: dict[str, dict[str, Any]], queued: set[str], per_member: int,
             data_dir: Path) -> dict[str, Any]:
    """What is left to pay for: texts the gate has not answered, plus the worst-case
    categorizer set less what is already queued."""
    bound = [s for s in select(order, verdicts, per_member, assume_pass=True)
             if triage_run.fingerprint(s) not in queued]
    triage = _stage(config, TRIAGE, triage_run.to_ask(order, verdicts),
                    prefilter.TRIAGE_OUTPUT_TOKENS, data_dir)
    categorize = _stage(config, CATEGORIZE, bound, prefilter.CATEGORIZE_OUTPUT_TOKENS,
                        data_dir)
    return {"triage": triage, "categorize": categorize, "per_member": per_member,
            "total_usd": round(triage["usd"] + categorize["usd"], 2)}


# --- the report ----------------------------------------------------------------------------


def counts(records: list[dict[str, Any]], result: dict[str, Any],
           order: list[dict[str, Any]], verdicts: dict[str, dict[str, Any]],
           parties: dict[str, str], per_member: int) -> dict[str, Any]:
    """Counts per source, per member and after each filter step."""
    survivors = result["statements"]
    passed = select(order, verdicts, per_member)
    bound = select(order, verdicts, per_member, assume_pass=True)
    rows = triage_run.tally(order, verdicts)
    sources = sorted({r.get("source", "") for r in records})
    members = sorted({r["member_id"] for r in records})

    def by(items: list[dict[str, Any]], key: str) -> Counter[str]:
        return Counter(i.get(key, "") for i in items)

    per_source = {
        source: {"collected": by(records, "source")[source],
                 "kept": by(survivors, "source")[source],
                 "eligible": by(order, "source")[source],
                 "to_categorizer_worst_case": by(bound, "source")[source]}
        for source in sources
    }
    per_member_rows = {
        member: {"party": parties.get(member, "?"),
                 "collected": by(records, "member_id")[member],
                 "kept": by(survivors, "member_id")[member],
                 "eligible": by(order, "member_id")[member],
                 "passed": rows.get(member, {}).get("passed", 0),
                 "not_passed": rows.get(member, {}).get("not_passed", 0),
                 "to_categorizer_worst_case": by(bound, "member_id")[member]}
        for member in members
    }
    steps = {
        "collected": len(records),
        "unreadable_set_aside": result["statements_unreadable"],
        "after_prefilter": len(survivors),
        "eligible_for_triage": len(order),
        "triage_answered": sum(r["triaged"] for r in rows.values()),
        "triage_passed": sum(r["passed"] for r in rows.values()),
        "triage_not_passed": sum(r["not_passed"] for r in rows.values()),
        "to_categorizer_known": len(passed),
        "to_categorizer_worst_case": len(bound),
    }
    return {"steps": steps, "per_source": per_source, "per_member": per_member_rows}


def _rate_line(row: dict[str, Any], flagged: bool) -> str:
    accepted = row["uneven"] and row["rule"] in OWNER_ACCEPTED_RULES
    mark = "  <-- UNEVEN, NEEDS REVIEW" if flagged else (
        "  (uneven, owner-accepted R4)" if accepted else "")
    return (f"    {row['scope']:22} {row['rule']:22} D {row['D_rate']:5.1f}% "
            f"({row['D']}/{row['D_turns']})  R {row['R_rate']:5.1f}% "
            f"({row['R']}/{row['R_turns']}){mark}")


def print_report(report: dict[str, Any]) -> None:
    print("  after each step:")
    for step, value in report["counts"]["steps"].items():
        print(f"    {step:28} {value}")
    print("  per source (collected / kept / eligible / to categorizer, worst case):")
    for source, row in report["counts"]["per_source"].items():
        print(f"    {source:22} {row['collected']} / {row['kept']} / {row['eligible']} / "
              f"{row['to_categorizer_worst_case']}")
    print("  per member (collected / kept / eligible / passed / not passed / to categorizer):")
    for member, row in report["counts"]["per_member"].items():
        print(f"    {member} {row['party']} {row['collected']} / {row['kept']} / "
              f"{row['eligible']} / {row['passed']} / {row['not_passed']} / "
              f"{row['to_categorizer_worst_case']}")
    for step in STEPS:
        rows = report["fairness"][step]
        flagged = new_flags(rows)
        print(f"  fairness, {step}: " + ("FLAGGED" if flagged else "no new flag")
              + ("" if rows else " (no verdicts yet: checked once the gate has answered)"))
        for row in rows:
            if row["turns"]:
                print(_rate_line(row, row in flagged))
    spend = report["estimate"]
    for name in ("triage", "categorize"):
        stage = spend[name]
        print(f"  estimate, {name}: {stage['statements']} calls, ${stage['usd']:.2f} "
              f"(by length ${stage['by_length_usd']:.2f}; by the mean of "
              f"{stage['logged_calls']} logged calls ${stage['by_logged_mean_usd']:.2f})")
    print(f"  estimate, total: ${spend['total_usd']:.2f} at {spend['per_member']} per member, "
          "worst case")


def _save(data_dir: Path, name: str, payload: dict[str, Any]) -> Path:
    path = data_dir / OUT_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def spend_path(data_dir: Path, run_name: str) -> Path:
    return data_dir / OUT_DIR / f"{run_name}-spend.json"


def prior_spend(data_dir: Path, run_name: str) -> float:
    path = spend_path(data_dir, run_name)
    if not path.exists():
        return 0.0
    return float(json.loads(path.read_text(encoding="utf-8"))["spent_usd"])


# --- the categorizer -----------------------------------------------------------------------


def queue_item(statement: dict[str, Any], party: str, result: ai.AiResult) -> dict[str, Any]:
    """One line of `data/raw/review/queue.jsonl`, in the shape `review._item` reads."""
    return {
        "id": triage_run.fingerprint(statement),
        "member_id": statement["member_id"],
        "party": party,
        "text": triage_run.statement_text(statement),
        "url": statement.get("url"),
        "date": statement.get("date"),
        "source": statement.get("source"),
        "input_hash": result.input_hash,
        "prompt_version": result.prompt_version,
        "suggestion": result.data,
        "preview": PREVIEW_MARK,
    }


@dataclass
class Outcome:
    status: str = "complete"
    categorized: int = 0
    limited: int = 0
    stop_detail: str = ""
    errors: list[dict[str, str]] = field(default_factory=list)

    def stop(self, status: str, detail: str = "") -> None:
        if self.status == "complete":
            self.status = status
            self.stop_detail = detail


def categorize(
    run: ai.Run,
    statements: list[dict[str, Any]],
    on_answer: Callable[[dict[str, Any], ai.AiResult], None],
    *,
    workers: int = DEFAULT_WORKERS,
    stop_file: Path | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Outcome:
    """Ask the categorizer, `workers` at a time, saving each answer as it arrives. A 429 is
    never a failed statement: it goes back to the front, and the batch waits. Rate-limit
    and error handling match `triage_run.triage`, without its ramp: at this concurrency
    there is nothing to ramp."""
    outcome = Outcome()
    pending = deque((s, 0) for s in statements)
    backoff = triage_run.BACKOFF_FIRST_SECONDS
    last_answer = clock()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while pending and outcome.status == "complete":
            if stop_file is not None and stop_file.exists():
                outcome.stop("stopped", f"{stop_file.name} found")
                break
            batch = [pending.popleft() for _ in range(min(workers, len(pending)))]
            calls = [(s, attempt, pool.submit(run.call, CATEGORIZE,
                                              triage_run.statement_text(s), reserve=True))
                     for s, attempt in batch]
            wait_for = 0.0
            for statement, attempt, future in calls:
                key = triage_run.statement_key(statement)
                try:
                    result = future.result()
                except ai.AiCapReached as exc:
                    outcome.stop("cap", str(exc))
                except ai.AiResponseError as exc:
                    outcome.errors.append({"key": key, "error": str(exc)})
                except triage_run.RATE_LIMITED as exc:
                    if triage_run.spend_cap_reached(exc):
                        outcome.stop("api-error", "the monthly spend cap was reached")
                        continue
                    outcome.limited += 1
                    pending.appendleft((statement, attempt))
                    wait_for = max(wait_for, triage_run.retry_after(exc) or backoff)
                    if clock() - last_answer > triage_run.STALL_SECONDS:
                        outcome.stop("api-error", "rate limited with no answer")
                except triage_run.TRANSIENT as exc:
                    if attempt + 1 >= triage_run.MAX_CONNECT_ATTEMPTS:
                        outcome.errors.append({"key": key, "error": type(exc).__name__})
                        outcome.stop("api-error", f"{type(exc).__name__}: {exc}")
                        continue
                    pending.appendleft((statement, attempt + 1))
                    wait_for = max(wait_for, backoff)
                except anthropic.APIError as exc:
                    outcome.errors.append({"key": key, "error": type(exc).__name__})
                    outcome.stop("api-error", f"{type(exc).__name__}: {exc}")
                else:
                    last_answer = clock()
                    on_answer(statement, result)
                    outcome.categorized += 1
            if wait_for and outcome.status == "complete":
                sleep(wait_for)
                backoff = min(triage_run.BACKOFF_MAX_SECONDS, backoff * 2)
            else:
                backoff = triage_run.BACKOFF_FIRST_SECONDS
    return outcome


# --- the run -------------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ingest categorize-run",
        description="P3: pre-filter, triage, capture, categorize, queue. Counts only unless "
                    "--approved-cap is passed.",
    )
    parser.add_argument("--approved-cap", type=float, default=None,
                        help="the owner's dollar cap for this whole named run; without it "
                             "nothing is called")
    parser.add_argument("--per-member", type=int, default=None,
                        help="statements per member to the categorizer (at most ai.yaml's)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"categorizer calls in flight (default {DEFAULT_WORKERS})")
    parser.add_argument("--live-capture", action="store_true",
                        help="send real captures to archive.org for this run")
    parser.add_argument("--fairness-reviewed", action="append", default=[], choices=STEPS,
                        help="this step's fairness flag has been reviewed; go on")
    parser.add_argument("--run-name", default=DEFAULT_RUN_NAME,
                        help=f"the run the cap covers (default {DEFAULT_RUN_NAME})")
    return parser


def _flagged(step: str, rows: list[dict[str, Any]], reviewed: list[str]) -> bool:
    """True when `step` has a flag still waiting for review. Says so if it does."""
    flags = new_flags(rows)
    if not flags or step in reviewed:
        return False
    print(f"  STOPPED: the {step} step is uneven by party ({len(flags)} row(s) above); it "
          f"waits for owner review (--fairness-reviewed {step} once reviewed)")
    return True


def run(
    argv: list[str] | None = None,
    *,
    completer: ai.Completer | None = None,
    client: httpx.Client | None = None,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """`completer` and `client` are for tests: a fake model and a fake archive.org."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    stamp = (now if now is not None else lambda: datetime.now(UTC))()

    data_dir = repo_root() / "data"
    full = ai.load_config(data_dir)
    config = replace(full, tasks={TRIAGE: full.task(TRIAGE), CATEGORIZE: full.task(CATEGORIZE)})
    per_member = args.per_member or config.max_statements_per_member_per_run
    if not 1 <= per_member <= config.max_statements_per_member_per_run:
        parser.error(f"--per-member must be 1 to {config.max_statements_per_member_per_run}")

    collected, parties, _names = prefilter.load_all(data_dir)
    pilot = set(triage_run._pilot_cells(data_dir))
    records = pilot_only(collected, pilot)
    result = prefilter.run_prefilter(records, prefilter.load_text_failures(data_dir))
    order = triage_run.queue(result["statements"])
    ledger_path = data_dir / "raw" / "triage" / f"{config.task(TRIAGE).prompt_version}.jsonl"
    verdicts = triage_run.load_ledger(ledger_path)
    queued = {item.id for item in review.load_queue(data_dir)}

    report = {
        "generated": stamp.isoformat(timespec="seconds"),
        "pilot_members": len(pilot),
        "outside_pilot_records_ignored": len(collected) - len(records),
        "counts": counts(records, result, order, verdicts, parties, per_member),
        "fairness": {"prefilter": prefilter_rows(result, parties),
                     "triage": triage_rows(order, verdicts, parties)},
        "estimate": estimate(config, order, verdicts, queued, per_member, data_dir),
    }
    print(f"categorize-run: count before spend (decision 4), {len(pilot)} pilot members")
    print_report(report)
    saved = _save(data_dir, f"{stamp.date().isoformat()}-count-before-spend.json", report)
    print(f"  saved: {saved.relative_to(repo_root())}")

    if args.approved_cap is None:
        print("  NO AI CALL MADE: nothing runs without --approved-cap <usd>")
        return EXIT_OK

    spent_before = prior_spend(data_dir, args.run_name)
    left = args.approved_cap - spent_before
    if report["estimate"]["total_usd"] > left:
        print(f"  REFUSED: the estimate ${report['estimate']['total_usd']:.2f} is over the "
              f"${left:.2f} left of the ${args.approved_cap:.2f} cap; nothing called")
        return EXIT_OVER_CAP
    if client is None and not (args.live_capture or capture.live_capture_enabled(data_dir)):
        print("  REFUSED: capture comes before the categorizer and live capture is off "
              "(--live-capture opts in for this run); nothing called")
        return EXIT_REFUSED
    if _flagged("prefilter", report["fairness"]["prefilter"], args.fairness_reviewed):
        return EXIT_FAIRNESS

    stop_file = data_dir / triage_run.STOP_FILE
    if stop_file.exists():
        stop_file.unlink()
        print(f"  removed a stale {stop_file.name}")
    session = ai.Run(config=config, completer=completer or ai._live_completer,
                     data_dir=data_dir, now=lambda: stamp, cap_usd=left)

    def save_spend(*_ignored: Any) -> None:
        _save(data_dir, f"{args.run_name}-spend.json",
              {"approved_cap_usd": args.approved_cap,
               "spent_usd": round(spent_before + session.spent_usd, 6)})

    try:
        return _spend(args, session, data_dir, order, verdicts, ledger_path, parties,
                      per_member, queued, client, stop_file, save_spend, sleep, clock)
    finally:
        save_spend()
        print(f"  spent this invocation ${session.spent_usd:.4f}; this run "
              f"${spent_before + session.spent_usd:.4f} of ${args.approved_cap:.2f}")


def _spend(args: argparse.Namespace, session: ai.Run, data_dir: Path,
           order: list[dict[str, Any]], verdicts: dict[str, dict[str, Any]], ledger_path: Path,
           parties: dict[str, str], per_member: int, queued: set[str],
           client: httpx.Client | None, stop_file: Path,
           save_spend: Callable[..., None], sleep: Callable[[float], None],
           clock: Callable[[], float]) -> int:
    """Everything after the checks: triage, fairness, capture, categorize, queue."""
    todo = triage_run.to_ask(order, verdicts)
    gate = triage_run.triage(session, todo, ledger_path, stop_file=stop_file, sleep=sleep,
                             clock=clock)
    print(f"  triage {gate.status}: {gate.triaged} verdict(s), {len(gate.errors)} error(s)")
    if gate.status != "complete":
        print(f"  stopped: {gate.stop_detail}")
        return _EXIT[gate.status]
    verdicts = triage_run.load_ledger(ledger_path)
    rows = triage_rows(order, verdicts, parties)
    for row in rows:
        print(_rate_line(row, row in new_flags(rows)))
    if _flagged("triage", rows, args.fairness_reviewed):
        return EXIT_FAIRNESS

    chosen = select(order, verdicts, per_member)
    path = capture.ledger_path(data_dir)
    urls = list(dict.fromkeys(s["url"] for s in chosen if s.get("url")))
    known = capture.load_captures(path)
    wanted = capture.to_capture(urls, known, retry_failed=True)
    print(f"  capture: {len(urls)} source URL(s), {len(wanted)} to send")
    spn = capture.SpnClient(client=client, sleep=sleep,
                            on_response=capture.response_writer(data_dir))
    try:
        archived = capture.capture_all(spn, wanted, path, known=known)
    finally:
        spn.close()
    print(f"  capture {archived.status}: {archived.captured} captured, "
          f"{archived.failed} failed")
    if archived.status != "complete":
        return capture.STOP_EXIT[archived.status]

    captures = capture.load_captures(path)
    live = [s for s in chosen if s.get("url")
            and capture.verified_capture(s["url"], captures) is not None]
    uncaptured = Counter(parties.get(s["member_id"], "?") for s in chosen if s not in live)
    print(f"  no live capture, not categorized: {dict(sorted(uncaptured.items()))}")
    ask = [s for s in live if triage_run.fingerprint(s) not in queued]

    queue_file = review.queue_path(data_dir)
    queue_file.parent.mkdir(parents=True, exist_ok=True)

    def write(statement: dict[str, Any], answer: ai.AiResult) -> None:
        item = queue_item(statement, parties.get(statement["member_id"], "?"), answer)
        with queue_file.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n")
        save_spend()

    outcome = categorize(session, ask, write, workers=args.workers, stop_file=stop_file,
                         sleep=sleep, clock=clock)
    print(f"  categorize {outcome.status}: {outcome.categorized} queued as preview, "
          f"{outcome.limited} rate-limited retries, {len(outcome.errors)} error(s)")
    if outcome.stop_detail:
        print(f"  stopped: {outcome.stop_detail}")
    return _EXIT.get(outcome.status, EXIT_OK)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
