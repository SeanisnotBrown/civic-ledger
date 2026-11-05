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
  * `failed`   — SPN2 reported an error, timed out, or the snapshot did not resolve;
  * `dead`     — a capture that later stopped resolving (`uv run archive-links` writes it).

A capture is keyed on the statement's SOURCE URL, because that is what is archived and
what `curation/statements.py::build_statement` checks the capture against. Only a URL
whose latest line is `captured` has a live capture; the review export reads this file and
exports nothing else. A `failed` or `dead` URL is never exported. A `dead` one is asked
again on the next run (hidden until recaptured, §2 Snapshots); a `failed` one only with
`--retry-failed`, so a page archive.org cannot save is not re-sent every run. That flag
covers every URL the gate passed; `categorize-run` retries the failed URLs of its own
selection on every resume. A `failed` line that names a snapshot means SPN2 saved the page
and only the check failed, so a retry checks that snapshot again before any new save.

The file names which source URLs passed the triage gate, a model output: like the triage
ledger it stays under `data/raw/` and never enters the public repository.

## Raw responses first (rule 4)

A capture is a mutating POST, so it never goes through `cache.py` and is never replayed.
Every SPN2 response (save, status, verify, cdx) is appended to
`data/raw/archive/responses/<sha256(url)[:16]>.jsonl` BEFORE the client parses it, and a
re-run skips every URL already captured, so a re-run sends nothing it already has.

## Rate limits

One capture at a time, in the triage queue's order (each member newest first, one member
at a time), so a run cut short has captured every member to about the same depth. A 429
is not a failed capture: the run stops there (exit 2) and a re-run resumes.

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
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from ingest import ai, prefilter, triage_run
from ingest.cache import repo_root
from ingest.sources.archive_org import Capture, SpnClient, SpnError, SpnRateLimited

CONFIG = Path("config") / "archive.yaml"
LEDGER = Path("raw") / "archive" / "captures.jsonl"
RESPONSES = Path("raw") / "archive" / "responses"

CAPTURED = "captured"
FAILED = "failed"
DEAD = "dead"

EXIT_OK = 0
EXIT_RATE_LIMITED = 2
EXIT_REFUSED = 5

SNAPSHOT_IN_ERROR = re.compile(r"/web/(\d{14})/")


def ledger_path(data_dir: Path) -> Path:
    return data_dir / LEDGER


def live_capture_enabled(data_dir: Path) -> bool:
    """True only when `archive.yaml` says `live_capture: true`. A missing file is off."""
    path = data_dir / CONFIG
    if not path.exists():
        return False
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw.get("live_capture") is True


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


def to_capture(urls: list[str], captures: dict[str, dict[str, Any]], *,
               retry_failed: bool = False) -> list[str]:
    """The URLs still to send: never captured, or dead; failed ones only on request."""
    wanted = {None, DEAD} | ({FAILED} if retry_failed else set())
    return [u for u in urls if (captures.get(u) or {}).get("status") in wanted]


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
    status: str = "complete"  # complete | limit | rate-limited
    captured: int = 0
    failed: int = 0


def _attempt(spn: SpnClient, url: str, entry: dict[str, Any] | None) -> Capture:
    """The capture for `url`: the snapshot its failed line names if that one is there,
    else a new save. `entry` is the URL's latest line."""
    found = SNAPSHOT_IN_ERROR.search((entry or {}).get("error", ""))
    if found:
        try:
            return spn.confirm(url, found.group(1))
        except SpnRateLimited:
            raise
        except SpnError:
            pass
    return spn.capture(url)


def capture_all(spn: SpnClient, urls: list[str], path: Path, *, limit: int = 0,
                known: dict[str, dict[str, Any]] | None = None,
                now: Callable[[], str] = _now,
                progress: Callable[[str], None] = print) -> Outcome:
    """Capture each URL in turn, recording every result as it arrives. `known` is the
    capture file as loaded, so a failed URL's snapshot is checked before a new save."""
    known = known or {}
    outcome = Outcome()
    for sent, url in enumerate(urls):
        if limit and sent >= limit:
            outcome.status = "limit"
            break
        try:
            cap = _attempt(spn, url, known.get(url))
        except SpnRateLimited as exc:
            progress(f"  stopped: {exc}; a re-run resumes")
            outcome.status = "rate-limited"
            break
        except SpnError as exc:
            _append(path, {"url": url, "status": FAILED, "error": str(exc), "ts": now()})
            outcome.failed += 1
            continue
        _append(path, {"url": url, "status": CAPTURED, "archive_url": cap.archive_url,
                       "timestamp": cap.timestamp, "captured_at": cap.captured_at,
                       "ts": now()})
        outcome.captured += 1
    return outcome


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
    todo = to_capture(urls, captures, retry_failed=args.retry_failed)
    status = [(captures.get(u) or {}).get("status") for u in urls]
    print(f"capture: {len(urls)} source URL(s) passed the triage gate under {version}; "
          f"{status.count(CAPTURED)} captured, {status.count(FAILED)} failed, "
          f"{status.count(DEAD)} dead; {len(todo)} to capture")
    if not verdicts:
        print(f"  no triage verdicts under {version} yet: `uv run ingest triage-run` first")
    if args.dry_run or not todo:
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
        outcome = capture_all(spn, todo, path, limit=args.limit, known=captures)
    finally:
        spn.close()
    print(f"  {outcome.status}: {outcome.captured} captured, {outcome.failed} failed")
    return EXIT_RATE_LIMITED if outcome.status == "rate-limited" else EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
