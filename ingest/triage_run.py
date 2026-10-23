"""The first pass: every pre-filtered statement through the Haiku triage gate (§5 Phase 3
decision 3), and NOTHING after it.

**Owner ruling 2026-10-22 (step 9, option b): triage only.** The Opus categorizer waits
until its prompt has been tested against a held-out hand-labeled set of at least 50
statements (spec task 4). So this command can reach exactly
one AI task. It builds its `ai.Run` over a configuration holding `triage_statement` ALONE,
so a categorizer call is not merely avoided but impossible: `ai.py` would refuse it as an
unknown task before any request was built. `tests/test_triage_run.py` fails if a request
for any other task or model ever leaves this module.

Every call goes through `ingest/ai.py`, so each one is hashed, cached, written to the
tracked audit log and counted against the per-run cap — this module adds the batch, not a
second way to call the API.

## Concurrent, and paced by the API's own rate-limit headers (owner, 2026-10-22)

Up to `--workers` calls run at once (default `DEFAULT_WORKERS`). The run does not start
there: it starts at `START_WORKERS` and lets the API say how far to go. Every answer
carries the organization's remaining requests and input tokens; while both have plenty of
room the allowed concurrency rises by one, when either runs low it falls by a quarter,
and a 429 or 529 halves it and holds every new call back for the `retry-after` the API
sent. A sudden jump in traffic can itself draw 429s (the docs' "acceleration limits"),
which is why it ramps rather than opening at full width.

**A 429 is never a failed statement.** The statement goes back to the FRONT of the queue
and is asked again, so the members' order is kept. Only two things end a run on rate
limits: the monthly spend cap (a 429 with no `retry-after` and the error code
`enforced_spend_limit_reached` — retrying cannot help until the month turns), and
`STALL_SECONDS` with not one successful answer. Both stop the run as `api-error`, and a
re-run resumes.

Workers do nothing but `run.call`. Every verdict save, every pacing decision and every
progress line happens on the main thread as answers come back, so the ledger is written
by one thread only; `ai.py` locks its own spend and audit log. The cap is exact under
concurrency: each call reserves an upper bound on its cost before it is sent
(`ai.Run.call(reserve=True)`).

## Order: newest first, one member at a time

Each member's statements are sorted newest first (decision 7's own order), then the queue
takes one from every member in turn, by member id. A run the cap stops part-way has
therefore triaged every member to roughly the same depth, instead of spending the whole
budget on the members whose ids sort first or whose press offices publish most.

## Resumable

Each verdict is appended, as it arrives, to `data/raw/triage/<prompt_version>.jsonl`
(gitignored, like every model output: the repository holds counts, never answers). The
verdict belongs to the exact TEXT that was asked, so the ledger is indexed by the text's
fingerprint: a re-run skips every statement whose text already has one, and asks again
when a text has changed. (It is not indexed by statement id: measured 2026-10-22, eight
members' press releases share one `granule_id` each — an ASPX path with its
`?DocumentID=` dropped — and four Record granules hold two different texts.) The same
text is asked once per run, however many statements carry it. The file is per prompt
version, so a new prompt starts from nothing.

## How a run ends

  * `complete` — every eligible statement has a verdict. Exit 0.
  * `limit` — `--limit` statements were sent (a deliberate smoke run). Exit 0.
  * `cap` — the next call's reservation would pass `per_run_cost_cap_usd`; nothing more
    is sent, the calls in flight finish. Exit 3.
  * `api-error` — a non-retryable API error, the monthly spend cap, a statement that
    kept failing to connect, or a rate-limit stall. Exit 2.
  * `stopped` — `data/raw/triage.stop` appeared: nothing more is sent, the calls in
    flight finish, the report is written. Exit 4. This is the clean stop: a detached run
    cannot receive Ctrl+C. A stale stop file is removed when a run starts.

In every case each answer already received is saved, and a re-run resumes.

A refusal, a truncated answer or malformed JSON (`AiResponseError`) is recorded against
that statement and the run carries on; the statement has no verdict, so a re-run asks it
again. `ai.py` has already logged the failed call, because it was billed.

## Output

`docs/research/<UTC date>-triage-run.md`: counts per member and per pilot cell, the spend,
the rate limits the API reported, and how the run ended. Counts only — no statement text,
no verdict for any one statement.

    uv run ingest triage-run              # the run
    uv run ingest triage-run --workers 8  # at most 8 calls at once
    uv run ingest triage-run --limit 20   # at most 20 statements: a live smoke run
    uv run ingest triage-run --dry-run    # what would be asked; no call
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict, deque
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
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
EXIT_STOPPED = 4

# The most calls ever in flight. Sized for the documented Haiku 5.5 limits
# (platform.claude.com/docs/en/api/rate-limits, read 2026-10-22) at the latency measured
# on this run's first 648 calls (~1.5 s each, ~1,500 input tokens): the Start tier's
# 1,000 RPM needs ~25 in flight, the Build tier's 5M ITPM ~80, so 96 lets a Build- or
# Scale-tier account reach its ceiling. The pacer, not this number, keeps a smaller
# account inside its limits.
DEFAULT_WORKERS = 96
# Where the run opens: low, because a sudden jump in traffic can itself draw 429s.
START_WORKERS = 4
# Remaining-capacity fractions that move the pacer.
HEADROOM_HIGH = 0.5
HEADROOM_LOW = 0.1
# Backoff when a limited or failed call carries no retry-after.
BACKOFF_FIRST_SECONDS = 1.0
BACKOFF_MAX_SECONDS = 60.0
# A statement that keeps failing to connect (not rate limits) stops the run after this.
MAX_CONNECT_ATTEMPTS = 8
# No successful answer for this long while every attempt is limited: stop, resumable.
STALL_SECONDS = 900.0
# How often the run reports progress to its log.
PROGRESS_EVERY = 250
# The clean stop. Its presence stops dispatch; calls in flight finish.
STOP_FILE = Path("raw") / "triage.stop"

# Retried, never counted against the statement.
RATE_LIMITED = (anthropic.RateLimitError, anthropic.OverloadedError)
# Retried up to MAX_CONNECT_ATTEMPTS.
TRANSIENT = (
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
    anthropic.ServiceUnavailableError,
)


def statement_key(statement: dict[str, Any]) -> str:
    """A readable identity for the report: member, source, and the URL where there is one
    (a press release's `granule_id` can be a bare path shared by a whole site)."""
    where = statement.get("url") or statement.get("granule_id", "")
    return "|".join((statement["member_id"], statement.get("source", ""), where))


def statement_text(statement: dict[str, Any]) -> str:
    """What the gate reads: the turns the pre-filter kept, and nothing else. Not the title,
    not the member's name — the prompt judges what the text says."""
    return "\n\n".join(statement["segments"])


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint(statement: dict[str, Any]) -> str:
    return text_sha256(statement_text(statement))


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
    """Every verdict already recorded under this prompt version, by text fingerprint. A
    later line for the same text replaces an earlier one."""
    if not path.exists():
        return {}
    ledger: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            ledger[entry["text_sha256"]] = entry
    return ledger


def has_verdict(statement: dict[str, Any], ledger: dict[str, dict[str, Any]]) -> bool:
    """True when this exact text already has a verdict."""
    return fingerprint(statement) in ledger


def to_ask(order: list[dict[str, Any]], ledger: dict[str, dict[str, Any]]) -> list[dict]:
    """The statements still to send, in queue order, each distinct text once."""
    seen: set[str] = set()
    todo: list[dict[str, Any]] = []
    for statement in order:
        sha = fingerprint(statement)
        if sha not in ledger and sha not in seen:
            seen.add(sha)
            todo.append(statement)
    return todo


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def headroom(rate_limits: dict[str, str]) -> float | None:
    """The smallest remaining/limit fraction across requests and input tokens, or None
    when the answer carried no usable header (a cache hit carries none)."""
    fractions = []
    for kind in ("requests", "input-tokens"):
        limit = _int(rate_limits.get(f"anthropic-ratelimit-{kind}-limit"))
        remaining = _int(rate_limits.get(f"anthropic-ratelimit-{kind}-remaining"))
        if limit and remaining is not None:
            fractions.append(remaining / limit)
    return min(fractions) if fractions else None


def retry_after(exc: Exception) -> float | None:
    """The `retry-after` the API sent with an error, in seconds, if any."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    try:
        return float(headers["retry-after"]) if "retry-after" in headers else None
    except ValueError:
        return None


def spend_cap_reached(exc: Exception) -> bool:
    """The organization's MONTHLY spend cap: a 429 that retrying cannot clear."""
    if not isinstance(exc, anthropic.RateLimitError) or retry_after(exc) is not None:
        return False
    body = exc.body if isinstance(exc.body, dict) else {}
    error = body.get("error") if isinstance(body.get("error"), dict) else body
    details = error.get("details") if isinstance(error.get("details"), dict) else {}
    return details.get("error_code") == "enforced_spend_limit_reached"


@dataclass
class Pacer:
    """How many calls may be in flight, and how long new ones must wait."""

    ceiling: int
    limit: int = 0
    not_before: float = 0.0
    backoff: float = BACKOFF_FIRST_SECONDS

    def __post_init__(self) -> None:
        self.limit = min(START_WORKERS, self.ceiling)

    def on_answer(self, rate_limits: dict[str, str]) -> None:
        self.backoff = BACKOFF_FIRST_SECONDS
        room = headroom(rate_limits)
        if room is None:
            return
        if room >= HEADROOM_HIGH:
            self.limit = min(self.ceiling, self.limit + 1)
        elif room < HEADROOM_LOW:
            self.limit = max(1, min(self.limit - 1, int(self.limit * 0.75)))

    def on_limited(self, wait_seconds: float | None, now: float) -> None:
        self.limit = max(1, self.limit // 2)
        delay = wait_seconds if wait_seconds is not None else self.backoff
        if wait_seconds is None:
            self.backoff = min(BACKOFF_MAX_SECONDS, self.backoff * 2)
        self.not_before = max(self.not_before, now + delay)


@dataclass
class Outcome:
    """How one invocation went."""

    status: str = "complete"
    triaged: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    stop_detail: str = ""
    limited: int = 0
    reconnects: int = 0
    peak_workers: int = 0
    rate_limits: dict[str, str] = field(default_factory=dict)


def triage(
    run: ai.Run,
    statements: list[dict[str, Any]],
    ledger_path: Path,
    *,
    limit: int = 0,
    workers: int = DEFAULT_WORKERS,
    stop_file: Path | None = None,
    progress: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Outcome:
    """Ask the gate about each statement, up to `workers` at a time, saving each verdict as
    it arrives. `statements` is what is still to do (`to_ask`). `limit` > 0 caps how many
    statements THIS invocation sends (a retry does not count twice)."""
    outcome = Outcome()
    pacer = Pacer(ceiling=workers)
    pending: deque[tuple[dict[str, Any], int]] = deque((s, 0) for s in statements)
    in_flight: dict[Future, tuple[dict[str, Any], int]] = {}
    sent = 0
    stopping = False
    last_answer = clock()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def stop(status: str, detail: str = "") -> None:
        nonlocal stopping
        if not stopping:
            stopping = True
            outcome.status = status
            outcome.stop_detail = detail

    with (
        ThreadPoolExecutor(max_workers=workers) as pool,
        ledger_path.open("a", encoding="utf-8") as ledger,
    ):
        while in_flight or (pending and not stopping):
            if stop_file is not None and stop_file.exists():
                stop("stopped", f"{stop_file.name} found; calls in flight were let finish")
            now = clock()
            while (
                not stopping
                and pending
                and len(in_flight) < pacer.limit
                and now >= pacer.not_before
            ):
                statement, attempt = pending[0]
                if attempt == 0 and limit and sent >= limit:
                    stop("limit")
                    break
                pending.popleft()
                if attempt == 0:
                    sent += 1
                future = pool.submit(run.call, TASK, statement_text(statement), reserve=True)
                in_flight[future] = (statement, attempt)
            outcome.peak_workers = max(outcome.peak_workers, len(in_flight))
            if not in_flight:
                if stopping or not pending:
                    break
                sleep(max(0.0, pacer.not_before - clock()))
                continue
            waiting_on_pacer = pending and not stopping and pacer.not_before > now
            done, _ = wait(
                in_flight,
                timeout=(pacer.not_before - now) if waiting_on_pacer else None,
                return_when=FIRST_COMPLETED,
            )
            for future in done:
                statement, attempt = in_flight.pop(future)
                try:
                    result = future.result()
                except ai.AiCapReached as exc:
                    stop("cap", str(exc))
                except ai.AiResponseError as exc:
                    outcome.errors.append({"key": statement_key(statement), "error": str(exc)})
                except RATE_LIMITED as exc:
                    if spend_cap_reached(exc):
                        stop("api-error", "the organization's monthly spend cap was reached")
                        continue
                    outcome.limited += 1
                    pacer.on_limited(retry_after(exc), clock())
                    pending.appendleft((statement, attempt))
                    if clock() - last_answer > STALL_SECONDS:
                        stop("api-error", f"rate limited with no answer for {STALL_SECONDS:.0f}s")
                except TRANSIENT as exc:
                    outcome.reconnects += 1
                    if attempt + 1 >= MAX_CONNECT_ATTEMPTS:
                        detail = f"{type(exc).__name__} after {attempt + 1} attempts: {exc}"
                        outcome.errors.append({"key": statement_key(statement), "error": detail})
                        stop("api-error", detail)
                        continue
                    pacer.on_limited(retry_after(exc), clock())
                    pending.appendleft((statement, attempt + 1))
                except anthropic.APIError as exc:
                    detail = f"{type(exc).__name__}: {exc}"
                    outcome.errors.append({"key": statement_key(statement), "error": detail})
                    stop("api-error", detail)
                else:
                    last_answer = clock()
                    text = statement_text(statement)
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
                    if result.rate_limits:
                        if not outcome.rate_limits:
                            reported = _limits(result.rate_limits)
                            progress(f"  rate limits reported by the API: {reported}")
                        outcome.rate_limits = result.rate_limits
                    pacer.on_answer(result.rate_limits)
                    if outcome.triaged % PROGRESS_EVERY == 0:
                        progress(
                            f"  triaged {outcome.triaged}, ${run.spent_usd:.4f} spent, "
                            f"{pacer.limit} allowed in flight, {outcome.limited} rate-limited "
                            f"retries, {len(outcome.errors)} error(s)"
                        )
    return outcome


def _limits(rate_limits: dict[str, str]) -> str:
    """The configured limits, shortest form: what tier this account is on."""
    parts = [
        f"{kind} {rate_limits[f'anthropic-ratelimit-{kind}-limit']}/min"
        for kind in ("requests", "input-tokens", "output-tokens")
        if f"anthropic-ratelimit-{kind}-limit" in rate_limits
    ]
    return ", ".join(parts) or "none in the headers"


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
        entry = ledger.get(fingerprint(statement))
        if entry is None:
            row["remaining"] += 1
            continue
        row["triaged"] += 1
        if entry[VERDICT_FIELD]:
            row["passed"] += 1
        else:
            row["not_passed"] += 1
    return dict(rows)


_COUNTS = ("eligible", "triaged", "passed", "not_passed", "remaining")


def prompt_status(task: ai.TaskConfig) -> str:
    """What the report may truthfully say about the prompt that produced its verdicts. A
    `-stub` version was never written to be evaluated; any other version is untested
    until `uv run ingest prompt-eval` scores it on the held-out labeled set."""
    if task.prompt_version.endswith("stub"):
        return "a STUB: nothing here may be published or counted toward precision"
    return (
        "untested until scored against the held-out hand-labeled set; nothing here may "
        "be published until the precision bar, Q-K, is ratified"
    )


def render_report(
    *,
    rows: dict[str, dict[str, int]],
    cells: dict[str, str],
    names: dict[str, str],
    outcome: Outcome,
    run: ai.Run,
    task: ai.TaskConfig,
    per_member_cap: int,
    workers: int,
    generated: str,
) -> str:
    """The run's count report. Counts only."""
    total = {k: sum(r[k] for r in rows.values()) for k in _COUNTS}
    lines = [
        "# Triage run — the first pass (Haiku), counts only",
        "",
        f"Generated {generated} by `uv run ingest triage-run`. Task `{task.name}`, model "
        f"`{task.model}`, prompt `{task.prompt_version}` ({prompt_status(task)}).",
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
        f"| Most calls in flight at once | {outcome.peak_workers} (ceiling {workers}) |",
        f"| Rate-limited calls retried (never errors) | {outcome.limited} |",
        f"| Connection or server errors retried | {outcome.reconnects} |",
        f"| Rate limits the API reported | {_limits(outcome.rate_limits)} |",
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


_EXIT = {"cap": EXIT_CAP, "api-error": EXIT_API_ERROR, "stopped": EXIT_STOPPED}


def run(
    argv: list[str] | None = None,
    *,
    completer: ai.Completer | None = None,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    parser = argparse.ArgumentParser(
        prog="ingest triage-run",
        description="P3 step 9 — the Haiku first pass only. Never calls the categorizer.",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="at most this many statements (0 = no limit)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"most calls in flight at once (default {DEFAULT_WORKERS}; the run starts at "
        f"{START_WORKERS} and ramps on the API's rate-limit headers)",
    )
    parser.add_argument("--dry-run", action="store_true", help="counts only; no call")
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    stamp_clock = now if now is not None else (lambda: datetime.now(UTC))

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
    todo = to_ask(order, ledger)
    done = sum(1 for s in order if has_verdict(s, ledger))
    print(
        f"triage-run: {len(order)} eligible, {done} already triaged under "
        f"{task.prompt_version} ({len(ledger)} distinct texts), {len(todo)} distinct texts "
        f"to ask; cap ${triage_only.per_run_cost_cap_usd:.2f}; up to {args.workers} in flight"
    )
    print("  the Opus categorizer is NOT called by this command")
    if args.dry_run:
        print("  --dry-run: no call made")
        return EXIT_OK

    stop_file = data_dir / STOP_FILE
    if stop_file.exists():
        stop_file.unlink()
        print(f"  removed a stale {stop_file.name}")
    session = ai.Run(
        config=triage_only,
        completer=completer if completer is not None else ai._live_completer,
        data_dir=data_dir,
        now=stamp_clock,
    )
    outcome = triage(
        session,
        todo,
        ledger_path,
        limit=args.limit,
        workers=args.workers,
        stop_file=stop_file,
        sleep=sleep,
        clock=clock,
    )

    rows = tally(order, load_ledger(ledger_path))
    report_dir = root / "docs" / "research"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp_clock()
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
            workers=args.workers,
            generated=stamp.isoformat(timespec="seconds"),
        ),
    )
    print(
        f"  {outcome.status}: {outcome.triaged} verdict(s), {session.calls} call(s), "
        f"${session.spent_usd:.4f} spent, {outcome.limited} rate-limited retries, "
        f"{len(outcome.errors)} error(s), at most {outcome.peak_workers} in flight"
    )
    if outcome.stop_detail:
        print(f"  stopped: {outcome.stop_detail}")
    print(f"  report: {report.relative_to(root)}")
    return _EXIT.get(outcome.status, EXIT_OK)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
