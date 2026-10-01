"""INC-8 — Bill ingest (pure parse + pipeline) for the bills referenced by votes.

Every `RollCall.bill_id` that isn't null must resolve to a real bill page on the
site, so the covered bill set = the distinct `bill_id`s across `data/votes/*.json`
(1,011 at INC-8). One Congress.gov `/bill/{congress}/{type}/{number}` fetch per
bill yields every field the schema needs INLINE (title, policyArea, sponsors,
cboCostEstimates, latestAction) — see SHAPES §4.

`subjects` and `cosponsor_ids` are paginated sub-resources (INC-10 consumes them
for metrics). They are fetched for EVERY bill this pipeline exports — not as a
one-time backfill — so a nightly re-export of a recent bill can never silently
revert an enriched list to the `None` "not collected" sentinel (the D35 clobber
shape). The one-time backfill of the existing 1,011 bills is just `ingest bills
--all` (force past the skip-if-final gate); every night after stays correct.

`parse_bill` is pure (JSON dict + the fetched lists -> Bill). `run()` enumerates,
fetches (cached, resumable), quarantines malformed/missing bills (§6.1), exports.
"""

from __future__ import annotations

import html
import json
import re

from pydantic import ValidationError

from ingest.house_votes import rollcall_id
from ingest.models import Bill, BillAction, CboRef

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


def rollcall_id_for(recorded_vote: dict) -> str | None:
    """Build the canonical `RollCall.id` a `recordedVotes` entry points at, or
    None if the entry is malformed. Pure; existence is the caller's business.

    Mirrors `house_votes.rollcall_id` exactly -- the same zero-padded
    `{h|s}-{congress}-{session}-{roll:04d}` shape -- because a near-miss here
    would produce a link to a page that does not exist."""
    try:
        chamber = "house" if recorded_vote["chamber"] == "House" else "senate"
        return rollcall_id(
            chamber,
            int(recorded_vote["congress"]),
            int(recorded_vote["sessionNumber"]),
            int(recorded_vote["rollNumber"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def parse_actions(
    raw_actions: list[dict], *, known_rollcall_ids: set[str] | None = None
) -> list[BillAction]:
    """Raw `/actions` rows -> `BillAction`s, in the order given (newest first).
    Pure: no fetching, no wall-clock, no reordering.

    `known_rollcall_ids` is the set of roll calls this dataset actually holds. An
    action's `recordedVotes` resolves to a `rollcall_id` only on a hit; a real
    vote outside the covered Congresses resolves to None rather than a link to a
    `/v/` page that was never built (40 of 58 resolved in the task-3 survey; all
    18 misses were 117th/116th). Passing None means "resolve nothing" -- the
    conservative default, never "assume everything exists".

    Text is passed through verbatim except for `html.unescape`, the same lossless
    entity decode `parse_bill` applies to titles: Congress.gov delivers `&amp;`
    and `&#039;` encoded, and storing the raw entity would double-escape when the
    site renders it as text. That is a normalization to the true string, not a
    paraphrase (0.5)."""
    known = known_rollcall_ids or set()
    out: list[BillAction] = []
    for a in raw_actions:
        rc_id = None
        for rv in a.get("recordedVotes") or []:
            candidate = rollcall_id_for(rv)
            if candidate and candidate in known:
                rc_id = candidate
                break

        committees = [
            html.unescape(c["name"])
            for c in (a.get("committees") or [])
            if c.get("name")
        ] or None

        out.append(
            BillAction(
                date=a["actionDate"],
                time=a.get("actionTime") or None,
                text=html.unescape(a["text"]),
                type=a["type"],
                action_code=a.get("actionCode") or None,
                source_system=(a.get("sourceSystem") or {})["name"],
                committees=committees,
                rollcall_id=rc_id,
            )
        )
    return out


def parse_bill(
    detail_json: dict,
    bill_id: str,
    *,
    subjects: list[str] | None,
    cosponsor_ids: list[str] | None,
) -> Bill:
    """Parse a `/bill/{c}/{type}/{number}` response into a `Bill`. Raises on
    malformed data so the caller quarantines the whole bill (§6.1).

    `subjects` / `cosponsor_ids` come from the paginated sub-resources (fetched by
    the caller); passing `None` records "not collected" (D27), a real list (incl.
    `[]`) records the collected value. Pure: no fetching happens here."""
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
        subjects=subjects,  # fetched sub-resource (INC-10); None only if uncollected
        sponsor_id=sponsor_id,
        cosponsor_ids=cosponsor_ids,  # fetched sub-resource (INC-10)
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


def _clear_quarantine(bill_id: str) -> None:
    """Remove this bill's quarantine file once it has exported cleanly (D87). Same
    reason as the roll-call version: a directory that only ever grows stops telling
    the owner what is actually quarantined."""
    from ingest.cache import repo_root

    (repo_root() / "data" / "quality" / "quarantine" / f"bill-{bill_id}.json").unlink(
        missing_ok=True
    )


def run(argv: list[str] | None = None) -> int:
    """Ingest every vote-referenced bill -> data/bills/*.json, INCLUDING the
    `/subjects` + `/cosponsors` sub-resources for every bill exported. Idempotent:
    cached fetches are reused, so a crashed run resumes cleanly. A malformed or
    missing bill is quarantined and the run continues; CI fails only if quarantined
    bills exceed the §6.1 fraction of the set.

    `ingest bills --all` forces past the skip-if-final gate — the one-time backfill
    that enriches the already-exported bills; without it the nightly touches only
    new/recent bills (whose enrichment refreshes on every re-export, never reverts)."""
    import httpx

    from ingest import config, incremental
    from ingest.cache import RetryableHTTPError
    from ingest.export import export_bill
    from ingest.sources import congress_gov

    fetch_errors = (RetryableHTTPError, httpx.HTTPError, OSError)
    force_all = bool(argv) and "--all" in argv

    accepted_ids = incremental.accepted_quarantines()  # owner-reviewed, non-fatal (§6.1)
    bill_ids = referenced_bill_ids()
    total = len(bill_ids)
    # Incremental (§6.1): skip bills already exported, EXCEPT those referenced by a
    # roll from the last 7 days (their latest_action may still be moving). `--all`
    # overrides the skip so the sub-resource backfill reaches every bill once.
    cutoff = incremental.final_cutoff()
    recent = incremental.recent_bill_ids(cutoff)
    exported = 0
    skipped = 0
    quarantined: list[str] = []
    fetch_failures: list[str] = []
    accepted_missing: list[str] = []

    for bill_id in bill_ids:
        if not force_all and incremental.bill_is_skippable(bill_id, recent):
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
            # Sub-resources fetched for EVERY exported bill (anti-clobber, see
            # module docstring) — never left as the None "uncollected" sentinel.
            subjects = congress_gov.bill_subjects(congress, btype, number)
            cosponsor_ids = congress_gov.bill_cosponsor_ids(congress, btype, number)
        except fetch_errors as exc:
            # A 404 surfaces as RetryableHTTPError only on 5xx/429; a real 404 is
            # an HTTPStatusError -> httpx.HTTPError. Either way, record + continue.
            if (isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code == 404
                    and bill_id in accepted_ids):
                # Owner-accepted permanent 404 (D87): a retry can never fix it, so
                # it is a printed note, not a nightly failure. The bill still
                # publishes nothing.
                accepted_missing.append(bill_id)
                continue
            fetch_failures.append(f"{bill_id}: {type(exc).__name__}")
            continue
        try:
            bill = parse_bill(data, bill_id, subjects=subjects, cosponsor_ids=cosponsor_ids)
        except (ValidationError, KeyError, BadBillId) as exc:
            _quarantine(bill_id, f"{type(exc).__name__}: {exc}")
            quarantined.append(bill_id)
            continue
        export_bill(bill)
        _clear_quarantine(bill_id)
        exported += 1

    print(f"civic-ledger bills: {exported} fetched, {skipped} skipped (already "
          f"final), of {total} referenced bills in data/bills/.")
    if quarantined:
        frac = len(quarantined) / total if total else 0.0
        print(f"  {len(quarantined)} quarantined ({frac:.2%}): {quarantined[:10]}")
        if frac > config.QUARANTINE_MAX_FRACTION:
            print(f"FAIL: quarantine {frac:.2%} exceeds {config.QUARANTINE_MAX_FRACTION:.0%}")
            return 1
    if accepted_missing:
        print(f"  {len(accepted_missing)} owner-accepted missing bill(s), not a failure "
              f"(data/quality/accepted-quarantine.yaml): {accepted_missing[:10]}")
    # Persistent fetch failures fail the run (re-runnable); the quarantine gate
    # above is the §6.1 ceiling for genuinely-bad bills. One message (L-3).
    if fetch_failures:
        print(f"FAIL: {len(fetch_failures)} bill(s) failed to fetch (re-run to retry): "
              f"{fetch_failures[:10]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
