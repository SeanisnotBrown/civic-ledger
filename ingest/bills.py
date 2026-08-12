"""INC-8 — Bill ingest (pure parse + pipeline) for the bills referenced by votes.

Every `RollCall.bill_id` that isn't null must resolve to a real bill page on the
site, so the covered bill set = the distinct `bill_id`s across `data/votes/*.json`
(1,011 at INC-8). One Congress.gov `/bill/{congress}/{type}/{number}` fetch per
bill yields every field the schema needs INLINE (title, policyArea, sponsors,
cboCostEstimates, latestAction) — see SHAPES §4. `subjects` and `cosponsor_ids`
are paginated sub-resources consumed by INC-10, not INC-8, so they are left as
None (NOT [] — D27); INC-10 backfills them.

`parse_bill` is pure (JSON dict -> Bill). `run()` enumerates, fetches (cached,
resumable), quarantines malformed/missing bills (§6.1), and exports.
"""

from __future__ import annotations

import html
import json
import re

from pydantic import ValidationError

from ingest.models import Bill, CboRef

# "hr1-119" / "hconres108-119" / "sjres5-118" -> (type, number, congress).
_BILL_ID_RE = re.compile(r"^([a-z]+)(\d+)-(\d+)$")


class BadBillId(ValueError):
    """A bill_id that doesn't parse to type+number+congress — quarantine."""


def parse_bill_id(bill_id: str) -> tuple[str, int, int]:
    m = _BILL_ID_RE.match(bill_id)
    if not m:
        raise BadBillId(f"unparseable bill_id {bill_id!r}")
    btype, number, congress = m.group(1), int(m.group(2)), int(m.group(3))
    return btype, number, congress


def parse_bill(detail_json: dict, bill_id: str) -> Bill:
    """Parse a `/bill/{c}/{type}/{number}` response into a `Bill`. Raises on
    malformed data so the caller quarantines the whole bill (§6.1)."""
    btype, number, congress = parse_bill_id(bill_id)
    bill = detail_json["bill"]

    policy_area = None
    if isinstance(bill.get("policyArea"), dict):
        policy_area = bill["policyArea"].get("name") or None

    # First sponsor's bioguide (bills have one primary sponsor; may be absent).
    sponsor_id = None
    sponsors = bill.get("sponsors") or []
    if sponsors:
        sponsor_id = sponsors[0].get("bioguideId") or None

    # Congress.gov delivers titles HTML-entity-encoded (&#039; &amp; &lt;). The
    # faithful verbatim text is the decoded character, and storing the raw entity
    # would double-escape when the site renders it as text. html.unescape is a
    # lossless normalization to the true string, not a paraphrase.
    cbo = [
        CboRef(url=c["url"], title=html.unescape(c["title"]), date=c["pubDate"])
        for c in (bill.get("cboCostEstimates") or [])
    ]

    latest = bill.get("latestAction") or {}

    return Bill(
        id=bill_id,
        congress=congress,
        type=btype,
        number=number,
        title_official=html.unescape(bill["title"]),
        policy_area=policy_area,
        subjects=None,  # deferred to INC-10 (D27)
        sponsor_id=sponsor_id,
        cosponsor_ids=None,  # deferred to INC-10 (D27)
        latest_action=latest["text"],
        latest_action_date=latest["actionDate"],
        cbo_estimates=cbo,
        source_url=bill.get("legislationUrl")
        or f"https://www.congress.gov/bill/{congress}th-congress/{btype}/{number}",
    )


# --- ingest pipeline ------------------------------------------------------


def referenced_bill_ids() -> list[str]:
    """The distinct non-null bill_ids across all exported roll calls, sorted."""
    from ingest.cache import repo_root

    votes_dir = repo_root() / "data" / "votes"
    ids: set[str] = set()
    for path in votes_dir.glob("*.json"):
        bid = json.loads(path.read_text(encoding="utf-8"))["rollcall"]["bill_id"]
        if bid:
            ids.add(bid)
    return sorted(ids)


def _quarantine(bill_id: str, error: str) -> None:
    from ingest.cache import repo_root

    qdir = repo_root() / "data" / "quality" / "quarantine"
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / f"bill-{bill_id}.json").write_text(
        json.dumps({"bill_id": bill_id, "error": error}, indent=2, sort_keys=True),
        encoding="utf-8", newline="\n",
    )


def run(argv: list[str] | None = None) -> int:
    """Ingest every vote-referenced bill -> data/bills/*.json. Idempotent: cached
    fetches are reused, so a crashed run resumes cleanly. A malformed or missing
    bill is quarantined and the run continues; CI fails only if quarantined bills
    exceed the §6.1 fraction of the set."""
    import httpx

    from ingest import config, incremental
    from ingest.cache import RetryableHTTPError
    from ingest.export import export_bill
    from ingest.sources import congress_gov

    fetch_errors = (RetryableHTTPError, httpx.HTTPError, OSError)

    bill_ids = referenced_bill_ids()
    total = len(bill_ids)
    # Incremental (§6.1): skip bills already exported, EXCEPT those referenced by a
    # roll from the last 7 days (their latest_action may still be moving).
    cutoff = incremental.final_cutoff()
    recent = incremental.recent_bill_ids(cutoff)
    exported = 0
    skipped = 0
    quarantined: list[str] = []
    fetch_failures: list[str] = []

    for bill_id in bill_ids:
        if incremental.bill_is_skippable(bill_id, recent):
            skipped += 1
            continue
        try:
            btype, number, congress = parse_bill_id(bill_id)
        except BadBillId as exc:
            _quarantine(bill_id, f"{type(exc).__name__}: {exc}")
            quarantined.append(bill_id)
            continue
        try:
            data = congress_gov.bill_detail(congress, btype, number).json()
        except fetch_errors as exc:
            # A 404 surfaces as RetryableHTTPError only on 5xx/429; a real 404 is
            # an HTTPStatusError -> httpx.HTTPError. Either way, record + continue.
            fetch_failures.append(f"{bill_id}: {type(exc).__name__}")
            continue
        try:
            bill = parse_bill(data, bill_id)
        except (ValidationError, KeyError, BadBillId) as exc:
            _quarantine(bill_id, f"{type(exc).__name__}: {exc}")
            quarantined.append(bill_id)
            continue
        export_bill(bill)
        exported += 1

    print(f"civic-ledger bills: {exported} fetched, {skipped} skipped (already "
          f"final), of {total} referenced bills in data/bills/.")
    if fetch_failures:
        print(f"  {len(fetch_failures)} fetch failure(s) (re-run to retry): "
              f"{fetch_failures[:10]}")
    if quarantined:
        frac = len(quarantined) / total if total else 0.0
        print(f"  {len(quarantined)} quarantined ({frac:.2%}): {quarantined[:10]}")
        if frac > config.QUARANTINE_MAX_FRACTION:
            print(f"FAIL: quarantine {frac:.2%} exceeds {config.QUARANTINE_MAX_FRACTION:.0%}")
            return 1
    # Persistent fetch failures fail the run (re-runnable); the quarantine gate
    # above is the §6.1 ceiling for genuinely-bad bills.
    if fetch_failures:
        print(f"FAIL: {len(fetch_failures)} bill(s) failed to fetch.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
