"""V2-11 task 5 — project `data/bills/**` into `data/events/{YYYY-MM}.json`.

A PURE projection. It opens no socket, reads no clock, and invents nothing: every
text field in an event is copied verbatim off a bill's official action timeline or
off the bill record itself. Run it twice on an unchanged dataset and the files are
byte-identical — that property is `verify-recompute` invariant 8, and it is what
makes the feed a published artifact rather than a render.

**Why a monthly file.** These are the only machine-readable URLs the V2-12 alert
Worker and the V2-13 push client read (task 5b serves them through an Astro static
endpoint). A single all-time file would be one ~38,756-bill blob re-downloaded for
every alert check; a file per day would be ~700 built files per Congress against
the 20,000-file free-plan ceiling (SD-33). One file per calendar month of ACTION
dates is the middle: a consumer fetches `/events/latest.json` for the current
month and never needs the rest.

**What is NOT in here.** No scoring, no classification, no grade, no owner wording
— §0.8 does not apply because nothing on this path is evaluative. The `type` field
is the government's own action type, not ours.

**The D27 sentinel is respected.** A bill whose `actions` is `None` has not been
collected yet (1,040 of them until the backfill finishes) and contributes nothing;
a bill whose `actions` is `[]` has been collected and the government lists no
actions, which also contributes nothing. Neither is an error — the projection
simply grows as the backfill lands, and that is why it can be built and tested
today against 73 bills and behave identically at 38,756.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ingest.models import BillEvent, EventsFile

# A bill's action date is YYYY-MM-DD, so the month key is a slice, never a parse.
# `BillAction._iso_date` already rejects every other ISO form (basic dates, week
# dates) precisely so this slice and the string sorts below are safe.
_MONTH = slice(0, 7)


def voted_bill_ids(data_dir: Path) -> set[str]:
    """Bill ids that reached a recorded vote — the set that gets a `/b/` page.

    This is the Python side of `votedBillIds()` in `site/src/lib/data.ts` and must
    stay the same rule (SD-33 3(c)): a bill gets a page if and only if some roll
    call in `data/votes/` names it. The duplication is deliberate and tested
    (`test_has_page_matches_the_sites_paged_set`) — the Worker and the push client
    cannot reach `data/votes/`, so the answer has to travel in the event row, and
    getting it wrong publishes a link to a `/b/` page that does not exist.

    Reads with plain `json` rather than `VoteFile(**...)`: this runs over ~3,500
    vote files and needs one field. A malformed vote file is not this module's
    business to report — `verify-recompute` and `uv run checks` already fail on it
    — but it must not make a bill silently pageless, so it raises rather than
    skipping quietly."""
    votes_dir = data_dir / "votes"
    out: set[str] = set()
    if not votes_dir.exists():
        return out
    for path in sorted(votes_dir.rglob("*.json")):
        bill_id = (json.loads(path.read_text(encoding="utf-8")).get("rollcall") or {}).get(
            "bill_id"
        )
        if bill_id:
            out.add(bill_id)
    return out


def event_id(bill_id: str, action: dict) -> str:
    """A stable id for one action: `{bill_id}--{date}--{12 hex}`.

    The hash covers the WHOLE action row, canonically serialised, not just the
    text. The plan specified an "action text hash"; that would collapse genuinely
    distinct actions, which is the exact bug D88 fixed in `bill_actions()` — on
    hr2670-118 five actions share a date, a text and an action code and differ
    only in `committees`, and a narrower hash published one event where the
    government recorded five. Widening it cannot collapse anything; narrowing it
    can. `sort_keys` is what makes the id stable across runs and field order.

    Making `BillAction.text` nullable (2026-10-05) does NOT disturb any existing
    id: the hash is taken over the action row AS STORED, and no stored row
    changes -- a row that has text keeps the same bytes. Only the rows that were
    previously unstorable (the bill was quarantined) gain an id, so no subscriber
    is re-notified. `ingest.export._dumps` writes `"text": null` rather than
    dropping the key, and `canonicalJson` in `site/src/lib/atom.ts` serialises
    `null` identically, so `entryId()` stays byte-equal to this function."""
    payload = json.dumps(action, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"{bill_id}--{action['date']}--{digest}"


def events_for_bill(bill: dict, *, has_page: bool) -> list[BillEvent]:
    """Every action on one bill as an event. `[]` when the timeline is absent
    (D27 `None` = not collected) or empty (`[]` = collected, none exist)."""
    actions = bill.get("actions")
    if not actions:
        return []
    return [
        BillEvent(
            id=event_id(bill["id"], action),
            bill_id=bill["id"],
            date=action["date"],
            # `.get`, not `[...]`: `BillAction.text` is nullable (congress.gov
            # omits the key on rare rows -- 1 bill in 19,125 on Congress 118), and
            # a bill exported before that change could also predate the key
            # entirely. Absent and null both project to null, which is what
            # `BillEvent.text` documents. Deliberately not an `if`: this module is
            # inside the 100%-branch coverage gate and `.get` adds no branch.
            text=action.get("text"),
            type=action["type"],
            action_code=action.get("action_code"),
            source_system=action["source_system"],
            committees=action.get("committees"),
            rollcall_id=action.get("rollcall_id"),
            policy_area=bill.get("policy_area"),
            subjects=bill.get("subjects"),
            source_url=bill["source_url"],
            has_page=has_page,
        )
        for action in actions
    ]


def _sort_key(event: BillEvent) -> tuple:
    """Newest action first, then a total order that does not depend on the
    filesystem: `id` already contains bill and date and distinguishes every action
    that differs in any field, so it alone breaks every tie. Without a total order
    a quiet re-run could reorder two same-day actions and invariant 8 would fail
    for no real reason.

    `id` is NOT unique per EVENT, and that is deliberate as of D100: 15 Congress 118
    bills carry a byte-for-byte repeat of an action row (hr9748-118 four copies of
    one), `bill_actions` now keeps every copy the government's list has, and
    byte-identical rows necessarily hash alike. The sort stays total in effect — the
    tied events are identical, so the output bytes are still deterministic. The
    consequence worth knowing is downstream: a feed reader may collapse entries that
    share an `atom:id`, so such a group can show as one entry. Open question for the
    owner, recorded in D100, not settled here."""
    return (_desc(event.date), event.bill_id, event.id)


def _desc(date: str) -> tuple[int, ...]:
    """Descending-by-date inside an otherwise ascending key: negate the parts
    rather than sorting twice or reversing (a reverse would also flip the
    tiebreakers, making the order depend on them in the wrong direction)."""
    y, m, d = date.split("-")
    return (-int(y), -int(m), -int(d))


def compute(data_dir: Path) -> dict[str, EventsFile]:
    """The whole projection: `{"YYYY-MM": EventsFile}` over every bill on disk.

    Deterministic and clock-free. Bills are read in sorted filename order so that
    even a bug in the sort key could not make the output depend on directory
    iteration order."""
    bills_dir = data_dir / "bills"
    if not bills_dir.exists():
        return {}
    voted = voted_bill_ids(data_dir)

    by_month: dict[str, list[BillEvent]] = {}
    for path in sorted(bills_dir.glob("*.json")):
        bill = json.loads(path.read_text(encoding="utf-8"))
        for event in events_for_bill(bill, has_page=bill["id"] in voted):
            by_month.setdefault(event.date[_MONTH], []).append(event)

    out: dict[str, EventsFile] = {}
    for month in sorted(by_month):
        rows = sorted(by_month[month], key=_sort_key)
        out[month] = EventsFile(month=month, count=len(rows), events=rows)
    return out


def run(argv: list[str] | None = None) -> int:
    """`uv run ingest events` — write data/events/{YYYY-MM}.json for every month.

    Writes through `export.export_events`, so the files are byte-stable and
    atomic. A month that no longer has any events (only possible if the
    government withdraws an action) leaves its stale file behind rather than
    being deleted silently; `verify-recompute` invariant 8 reports it as a
    mismatch, which is the loud failure §0 asks for."""
    from ingest.cache import repo_root
    from ingest.export import export_events

    if argv:
        print(f"FAIL: unknown argument {argv[0]!r} (events takes none)")
        return 2
    data_dir = repo_root() / "data"
    months = compute(data_dir)
    written = export_events(months, out_dir=data_dir / "events")
    total = sum(f.count for f in months.values())
    print(
        f"civic-ledger events: {total} event(s) across {len(written)} month file(s) "
        f"in data/events/."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
