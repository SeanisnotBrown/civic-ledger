"""Incremental-ingest policy (§6.1) — skip refetching finalized records.

The nightly job (INC-9) runs every ~24h, but the cache TTL is 20h, so without a
skip rule every cached vote detail would re-fetch nightly (~3,467 calls) — an API
hammer (§0.7). §6.1's actual rule: a vote is refreshed only while it is < 7 days
old (a clerk may still correct it); once final it is never re-fetched. We resolve
the chicken-and-egg (the date is in the response, not knowable before fetching) by
peeking at the ALREADY-EXPORTED file: if `data/votes/{id}.json` exists and its
`rollcall.date` is older than 7 days, skip the roll entirely — no fetch, no parse,
no re-export (so its `vote_class` is preserved and no spurious git diff appears).
Recent and brand-new rolls fall through to a normal fetch; the 20h TTL then gives
them correct refresh behavior without `force`.

Bills follow the same shape: skip if already exported, EXCEPT bills referenced by
any roll from the last 7 days (their `latest_action` may still be moving).

All functions are pure given their inputs (`cutoff` is injected), so the policy is
deterministically testable; only `now_utc()` reads the wall clock.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ingest.cache import repo_root

FINAL_AFTER_DAYS = 7


def _votes_dir() -> Path:
    return repo_root() / "data" / "votes"


def _bills_dir() -> Path:
    return repo_root() / "data" / "bills"


def now_utc() -> datetime:
    return datetime.now(UTC)


def final_cutoff(now: datetime | None = None) -> datetime:
    """Records dated strictly before this instant are final (skip-eligible)."""
    return (now or now_utc()) - timedelta(days=FINAL_AFTER_DAYS)


def is_final(date_iso: str, cutoff: datetime) -> bool:
    """True if `date_iso` is older than the cutoff. An unparseable/naive date is
    treated as NOT final (re-fetch — never skip on ambiguity; §0.4 correctness)."""
    try:
        dt = datetime.fromisoformat(date_iso)
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt < cutoff


def roll_is_final(rc_id: str, cutoff: datetime, votes_dir: Path | None = None) -> bool:
    """True if the roll is already exported AND final → the ingest may skip it."""
    path = (votes_dir or _votes_dir()) / f"{rc_id}.json"
    if not path.exists():
        return False
    date_iso = json.loads(path.read_text(encoding="utf-8"))["rollcall"]["date"]
    return is_final(date_iso, cutoff)


def accepted_quarantines(root: Path | None = None) -> dict[str, str]:
    """Roll-call ids the owner has reviewed and accepted as un-ingestable (a voter
    outside their roster term window, etc.), mapped to a factual reason. A quarantine
    on one of these is NOT a nightly failure (§6.1): the roll still publishes nothing,
    but the run stays green so the failure signal is reserved for NEW, unexpected
    quarantines. Missing file → empty (nothing accepted). Pure given `root`."""
    import yaml
    path = (root or repo_root()) / "data" / "quality" / "accepted-quarantine.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def bill_is_skippable(bill_id: str, recent: set[str], bills_dir: Path | None = None) -> bool:
    """True if the bill is already exported AND not referenced by a recent roll."""
    if bill_id in recent:
        return False
    return ((bills_dir or _bills_dir()) / f"{bill_id}.json").exists()


def recent_bill_ids(cutoff: datetime, votes_dir: Path | None = None) -> set[str]:
    """bill_ids referenced by any exported roll NEWER than the cutoff — their
    `latest_action` may still be changing, so refresh them even if already exported."""
    out: set[str] = set()
    for path in (votes_dir or _votes_dir()).glob("*.json"):
        rc = json.loads(path.read_text(encoding="utf-8"))["rollcall"]
        if rc["bill_id"] and not is_final(rc["date"], cutoff):
            out.add(rc["bill_id"])
    return out
