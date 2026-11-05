"""P3 task 3 — archive capture, AFTER the pre-filter and the triage gate and BEFORE the
review queue (§5 Phase 3 task 3; owner decision 8, which amends the §2 Snapshots row).

Every statement that survives the free pre-filter AND gets a `true` from the Haiku triage
gate has its source page captured by archive.org's Save Page Now (the existing client,
`ingest/sources/archive_org.py`), so nothing publishable is ever unarchived. A dropped
statement is never captured: archive quota is not spent on text that can never publish.

## Live capture is OFF until the owner turns it on (owner ruling 2026-11-04)

The step is built and tested behind fakes. It sends a real request only when
`data/config/archive.yaml` says `live_capture: true`, or the command line opts in for one
run with `--live-capture` (that file is committed, so it stays off and a local run uses the
flag); otherwise it reports what it would capture and refuses (exit 5) before any request
is built. With the IA S3 keys in `.env`
the client authenticates; without them it captures at most one page every 15 seconds.

## The capture file

`data/raw/archive/captures.jsonl` (gitignored), one JSON line per event, append-only, the
latest line for a URL wins:

  * `captured` — a verified capture: the snapshot HEAD-resolved or CDX listed it;
  * `pending`  — SPN2 made a snapshot that neither playback nor CDX shows yet. It is checked
    again at the end of the capture phase and on every resume, never saved again, and
    turns `failed` only when still missing `PENDING_WINDOW_S` after the save;
  * `failed`   — SPN2 reported an error, timed out, or the snapshot never appeared;
  * `dead`     — a capture that later stopped resolving (`uv run archive-links` writes it).

A capture is keyed on the statement's SOURCE URL, because that is what is archived and
what `curation/statements.py::build_statement` checks the capture against. Only a URL
whose latest line is `captured` has a live capture; the review export reads this file and
exports nothing else. A `failed` or `dead` URL is never exported. A `dead` one is asked
again on the next run (hidden until recaptured, §2 Snapshots); a `failed` one only with
`--retry-failed`, so a page archive.org cannot save is not re-sent every run. That flag
covers every URL the gate passed; `categorize-run` retries the failed URLs of its own
selection on every resume. A `failed` line that names a snapshot means SPN2 saved the page
and only the check failed, so a retry checks that snapshot again before any new save. A
line for a save that timed out, or whose poll drew a 429, asks CDX for a snapshot from that
save the same way. SPN2's `error:not-found` is asked at most once per US Eastern calendar
day: a later resume that day skips the URL and reports it.

The file names which source URLs passed the triage gate, a model output: like the triage
ledger it stays under `data/raw/` and never enters the public repository.

## Raw responses first (rule 4)

A capture is a mutating POST, so it never goes through `cache.py` and is never replayed.
Every SPN2 response (save, status, verify, cdx) is appended to
`data/raw/archive/responses/<sha256(url)[:16]>.jsonl` BEFORE the client parses it, and a
re-run skips every URL already captured, so a re-run sends nothing it already has.

## Rate limits

Each capture waits minutes on archive.org's queue, so several run at once: at most
`max_concurrent_captures` (`data/config/archive.yaml`) or the sessions SPN2 reports free,
whichever is lower, one at a time without keys, and saves stay 9 s apart for the account's
7 a minute. URLs are taken in the triage queue's order (each member newest first, one
member at a time), so a run cut short has captured every member to about the same depth,
and a line lands in the capture file when its capture ends. A 429
is not a failed capture: the run stops there (exit 2) and a re-run resumes. Neither is
archive.org staying out of reach past the client's backoff: exit 8, and a re-run resumes.

    uv run ingest capture --dry-run          # what would be captured; nothing sent
    uv run ingest capture --limit 20         # at most 20 captures (live only if opted in)
    uv run ingest capture --live-capture     # opt in to real requests for this run
    uv run ingest capture --retry-failed     # also ask again for URLs that failed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import yaml

from ingest import ai, prefilter, triage_run
from ingest.cache import repo_root
from ingest.sources.archive_org import (
    POLL_TIMEOUT_S,
    Capture,
    SpnClient,
    SpnError,
    SpnRateLimited,
    SpnSnapshotMissing,
    SpnUnreachable,
)
from ingest.statements_press import us_eastern_date

CONFIG = Path("config") / "archive.yaml"
LEDGER = Path("raw") / "archive" / "captures.jsonl"
RESPONSES = Path("raw") / "archive" / "responses"

CAPTURED = "captured"
FAILED = "failed"
DEAD = "dead"
PENDING = "pending"

EXIT_OK = 0
DEFAULT_MAX_CONCURRENT = 4

EXIT_RATE_LIMITED = 2
EXIT_REFUSED = 5
EXIT_UNREACHABLE = 8
STOP_EXIT = {"rate-limited": EXIT_RATE_LIMITED, "unreachable": EXIT_UNREACHABLE}

SNAPSHOT_IN_ERROR = re.compile(r"/web/(\d{14})/")
LOST_JOB_IN_ERROR = re.compile(r"timed out after (\d+)s|status returned 429")
NOT_FOUND = "error:not-found"
# How long after its save a snapshot may stay out of sight before the URL counts as failed.
PENDING_WINDOW_S = 1800
# A timed-out line is written after the save went out by the deadline and the save's own
# time on the wire, so the search for its snapshot starts this much further back.
SAVE_SLACK_S = 60


def ledger_path(data_dir: Path) -> Path:
    return data_dir / LEDGER


def _config(data_dir: Path) -> dict[str, Any]:
    path = data_dir / CONFIG
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def live_capture_enabled(data_dir: Path) -> bool:
    """True only when `archive.yaml` says `live_capture: true`. A missing file is off."""
    return _config(data_dir).get("live_capture") is True


def capture_workers(spn: SpnClient, data_dir: Path) -> int:
    """The captures to keep in flight: `max_concurrent_captures` or the sessions SPN2
    reports free, whichever is lower, and never fewer than one."""
    ceiling = int(_config(data_dir).get("max_concurrent_captures", DEFAULT_MAX_CONCURRENT))
    return max(1, min(ceiling, spn.available_sessions()))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _append(path: Path, line: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n")


# --- the capture file --------------------------------------------------------------------


def load_captures(path: Path) -> dict[str, dict[str, Any]]:
    """The latest line for every URL. A missing file holds nothing."""
    if not path.exists():
        return {}
    captures: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            captures[entry["url"]] = entry
    return captures


def verified_capture(url: str, captures: dict[str, dict[str, Any]]) -> Capture | None:
    """The live capture for `url`, or None when it was never captured, failed, or died."""
    entry = captures.get(url)
    if entry is None or entry["status"] != CAPTURED:
        return None
    return Capture(original_url=url, archive_url=entry["archive_url"],
                   timestamp=entry["timestamp"], captured_at=entry["captured_at"])


def mark_dead(path: Path, entries: list[dict[str, Any]], *, now: str | None = None) -> None:
    """Record captures whose snapshot no longer resolves. Each is hidden until recaptured."""
    stamp = now or _now()
    for entry in entries:
        _append(path, {"url": entry["url"], "status": DEAD,
                       "archive_url": entry["archive_url"], "ts": stamp})


# --- what to capture ---------------------------------------------------------------------


def select_urls(order: list[dict[str, Any]], verdicts: dict[str, dict[str, Any]]) -> list[str]:
    """Source URLs of the statements the triage gate said yes to, in queue order, once
    each. A statement with no verdict, a `false`, or no source URL is not captured."""
    urls: list[str] = []
    seen: set[str] = set()
    for statement in order:
        entry = verdicts.get(triage_run.fingerprint(statement))
        url = statement.get("url")
        if entry and entry[triage_run.VERDICT_FIELD] and url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def eastern_day(stamp: str) -> str:
    """The US Eastern calendar date of an ISO-8601 instant."""
    return us_eastern_date(datetime.fromisoformat(stamp).astimezone(UTC).replace(tzinfo=None))


def not_found_today(urls: list[str], captures: dict[str, dict[str, Any]],
                    today: str) -> list[str]:
    """The URLs SPN2 already answered `error:not-found` for on `today`."""
    return [u for u in urls
            if NOT_FOUND in (captures.get(u) or {}).get("error", "")
            and eastern_day(captures[u]["ts"]) == today]


def to_capture(urls: list[str], captures: dict[str, dict[str, Any]], *,
               retry_failed: bool = False, today: str = "") -> list[str]:
    """The URLs still to send: never captured, or dead; failed ones only on request, and
    not one SPN2 could not find `today`. A pending URL already has its snapshot."""
    wanted = {None, DEAD} | ({FAILED} if retry_failed else set())
    held = set(not_found_today(urls, captures, today))
    return [u for u in urls
            if (captures.get(u) or {}).get("status") in wanted and u not in held]


# --- the run -----------------------------------------------------------------------------


def response_writer(data_dir: Path, now: Callable[[], str] = _now
                    ) -> Callable[[str, str, httpx.Response], None]:
    """An `on_response` hook: every SPN2 response appended to disk before it is parsed."""
    def write(kind: str, url: str, resp: httpx.Response) -> None:
        name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        _append(data_dir / RESPONSES / f"{name}.jsonl", {
            "ts": now(), "kind": kind, "url": url, "request": str(resp.request.url),
            "status_code": resp.status_code, "body": resp.text,
        })
    return write


@dataclass
class Outcome:
    status: str = "complete"  # complete | limit | rate-limited | unreachable
    captured: int = 0
    failed: int = 0
    pending: int = 0
    skipped: int = 0


def _save_time(entry: dict[str, Any], seconds: float) -> str:
    """When a lost job's save went out, as a Wayback timestamp: its line was written at most
    `seconds` of polling later."""
    sent = datetime.fromisoformat(entry["ts"]) - timedelta(seconds=seconds + SAVE_SLACK_S)
    return sent.astimezone(UTC).strftime("%Y%m%d%H%M%S")


def _attempt(spn: SpnClient, url: str, entry: dict[str, Any] | None) -> Capture:
    """The capture for `url`: the snapshot its failed line points at if that one is there,
    else a new save. `entry` is the URL's latest line."""
    error = (entry or {}).get("error", "")
    snapshot = SNAPSHOT_IN_ERROR.search(error)
    lost = LOST_JOB_IN_ERROR.search(error)
    try:
        if snapshot:
            return spn.confirm(url, snapshot.group(1))
        if lost:
            seconds = float(lost.group(1) or POLL_TIMEOUT_S)
            return spn.recover(url, _save_time(entry or {}, seconds))
    except (SpnRateLimited, SpnUnreachable):
        raise
    except SpnError:
        pass
    return spn.capture(url)


def capture_all(spn: SpnClient, urls: list[str], path: Path, *, limit: int = 0,
                known: dict[str, dict[str, Any]] | None = None, workers: int = 1,
                now: Callable[[], str] = _now,
                progress: Callable[[str], None] = print) -> Outcome:
    """Capture the URLs with at most `workers` in flight, recording every result as it
    arrives. `known` is the capture file as loaded, so a failed URL's snapshot is checked
    before a new save. A stop lets the captures in flight finish and starts no more."""
    known = known or {}
    outcome = Outcome()
    pending = iter(urls[:limit] if limit else urls)
    lock = threading.Lock()
    stop = threading.Event()

    def halt(status: str, exc: SpnError) -> None:
        stop.set()
        with lock:
            outcome.status = status
        progress(f"  stopped: {exc}; a re-run resumes")

    def record(line: dict[str, Any]) -> None:
        with lock:
            _append(path, line)
            if line["status"] == CAPTURED:
                outcome.captured += 1
            elif line["status"] == PENDING:
                outcome.pending += 1
            else:
                outcome.failed += 1

    def work() -> None:
        while not stop.is_set():
            with lock:
                url = next(pending, None)
            if url is None:
                return
            try:
                cap = _attempt(spn, url, known.get(url))
            except SpnRateLimited as exc:
                halt("rate-limited", exc)
            except SpnUnreachable as exc:
                halt("unreachable", exc)
            except SpnSnapshotMissing as exc:
                record({"url": url, "status": PENDING, "timestamp": exc.timestamp,
                        "error": str(exc), "ts": now()})
            except SpnError as exc:
                record({"url": url, "status": FAILED, "error": str(exc), "ts": now()})
            except Exception:
                stop.set()
                raise
            else:
                record({"url": url, "status": CAPTURED, "archive_url": cap.archive_url,
                        "timestamp": cap.timestamp, "captured_at": cap.captured_at,
                        "ts": now()})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for running in [pool.submit(work) for _ in range(workers)]:
            running.result()
    if outcome.status == "complete" and limit and len(urls) > limit:
        outcome.status = "limit"
    return outcome


def recheck_pending(spn: SpnClient, urls: list[str], path: Path, *,
                    now: Callable[[], str] = _now,
                    progress: Callable[[str], None] = print) -> Outcome:
    """Check each pending snapshot in `urls` again. Found is captured; still missing past
    `PENDING_WINDOW_S` is failed; otherwise the line stands. Sends no save."""
    outcome = Outcome()
    captures = load_captures(path)
    for url in urls:
        entry = captures.get(url) or {}
        if entry.get("status") != PENDING:
            continue
        stamp = entry["timestamp"]
        try:
            cap = spn.confirm(url, stamp)
        except (SpnRateLimited, SpnUnreachable) as exc:
            progress(f"  stopped: {exc}; a re-run resumes")
            outcome.status = ("rate-limited" if isinstance(exc, SpnRateLimited)
                              else "unreachable")
            break
        except SpnError:
            saved = datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
            age = (datetime.fromisoformat(now()) - saved).total_seconds()
            if age < PENDING_WINDOW_S:
                outcome.pending += 1
                continue
            _append(path, {"url": url, "status": FAILED, "ts": now(), "error": (
                f"snapshot {stamp} still missing {PENDING_WINDOW_S // 60} minutes after "
                "the save")})
            outcome.failed += 1
        else:
            _append(path, {"url": url, "status": CAPTURED, "archive_url": cap.archive_url,
                           "timestamp": cap.timestamp, "captured_at": cap.captured_at,
                           "ts": now()})
            outcome.captured += 1
    return outcome


def run_captures(spn: SpnClient, urls: list[str], path: Path, *, retry_failed: bool,
                 workers: int, limit: int = 0, now: Callable[[], str] = _now,
                 progress: Callable[[str], None] = print) -> Outcome:
    """One capture phase over `urls`: pending snapshots checked, what is due sent, pending
    snapshots checked again."""
    first = recheck_pending(spn, urls, path, now=now, progress=progress)
    if first.status != "complete":
        return first
    known = load_captures(path)
    today = eastern_day(now())
    outcome = capture_all(spn, to_capture(urls, known, retry_failed=retry_failed, today=today),
                          path, limit=limit, known=known, workers=workers, now=now,
                          progress=progress)
    outcome.captured += first.captured
    outcome.failed += first.failed
    outcome.pending += first.pending
    outcome.skipped = len(not_found_today(urls, known, today)) if retry_failed else 0
    if outcome.status == "complete":
        last = recheck_pending(spn, urls, path, now=now, progress=progress)
        outcome.status = last.status
        outcome.captured += last.captured
        outcome.failed += last.failed
        outcome.pending = last.pending
    return outcome


def today() -> str:
    """Today's US Eastern calendar date."""
    return eastern_day(_now())


def run(argv: list[str] | None = None, *, client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep) -> int:
    """`client` is for tests only: a fake transport. With no client, a real request is
    built only when `archive.yaml` or `--live-capture` opts in."""
    parser = argparse.ArgumentParser(
        prog="ingest capture",
        description="P3 task 3: archive the statements the triage gate passed.",
    )
    parser.add_argument("--limit", type=int, default=0,
                        help="at most this many captures (0 = no limit)")
    parser.add_argument("--retry-failed", action="store_true",
                        help="also ask again for URLs whose capture failed")
    parser.add_argument("--live-capture", action="store_true",
                        help="send real captures to archive.org for this run")
    parser.add_argument("--dry-run", action="store_true", help="counts only; nothing sent")
    args = parser.parse_args(argv)

    data_dir = repo_root() / "data"
    records, _parties, _names = prefilter.load_all(data_dir)
    result = prefilter.run_prefilter(records, prefilter.load_text_failures(data_dir))
    version = ai.load_config(data_dir).task(triage_run.TASK).prompt_version
    verdicts_path = data_dir / "raw" / "triage" / f"{version}.jsonl"
    verdicts = triage_run.load_ledger(verdicts_path)
    urls = select_urls(triage_run.queue(result["statements"]), verdicts)
    path = ledger_path(data_dir)
    captures = load_captures(path)
    todo = to_capture(urls, captures, retry_failed=args.retry_failed, today=today())
    status = [(captures.get(u) or {}).get("status") for u in urls]
    print(f"capture: {len(urls)} source URL(s) passed the triage gate under {version}; "
          f"{status.count(CAPTURED)} captured, {status.count(FAILED)} failed, "
          f"{status.count(DEAD)} dead, {status.count(PENDING)} pending; "
          f"{len(todo)} to capture")
    if not verdicts:
        print(f"  no triage verdicts under {version} yet: `uv run ingest triage-run` first")
    if args.dry_run or not (todo or PENDING in status):
        print("  nothing sent")
        return EXIT_OK
    if client is None and not (args.live_capture or live_capture_enabled(data_dir)):
        print(f"  REFUSED: live capture is off ({CONFIG.as_posix()} live_capture: false, "
              "owner ruling 2026-11-04); nothing sent")
        return EXIT_REFUSED

    spn = SpnClient(client=client, sleep=sleep, on_response=response_writer(data_dir))
    print("  authenticated (IA S3 keys)" if spn.authenticated
          else "  unauthenticated: at most 1 capture every 15 s")
    try:
        workers = capture_workers(spn, data_dir)
        print(f"  up to {workers} capture(s) at a time")
        outcome = run_captures(spn, urls, path, retry_failed=args.retry_failed,
                               limit=args.limit, workers=workers)
    finally:
        spn.close()
    print(f"  {outcome.status}: {outcome.captured} captured, {outcome.failed} failed, "
          f"{outcome.pending} pending, {outcome.skipped} skipped ({NOT_FOUND} today)")
    return STOP_EXIT.get(outcome.status, EXIT_OK)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
