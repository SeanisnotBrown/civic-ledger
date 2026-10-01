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


# A backfilled bill we do not hold costs 4 requests (detail + subjects +
# cosponsors + actions) at the 1 req/s per-host ceiling — the ~43 h figure in
# D88/SD-33 over 38,756 bills. Used only to print a resume ETA.
SECONDS_PER_BILL = 4.0


def bills_with_actions() -> set[str]:
    """Bill ids whose committed record already HAS a timeline — the resume set
    for `--skip-existing`.

    D27 sentinel: `[]` means "collected, and this bill has no actions", which is
    DONE; only `None`/absent means "not collected". Read with plain `json` rather
    than `Bill(**...)` because this runs over up to 38,756 files and only one
    field is needed. A torn file (killed mid-`write_text`, see `export_bill`)
    fails to parse and is simply left out of the set, so the next run re-ingests
    it instead of skipping a truncated record."""
    out: set[str] = set()
    for path in _bills_dir().glob("*.json"):
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("actions") is not None:
                out.add(path.stem)
        except (ValueError, OSError):
            continue
    return out


def known_rollcall_ids() -> set[str]:
    """Every `RollCall.id` this dataset holds, read once from `data/votes/**`.

    Built ONCE per run and threaded through every `parse_actions()` call. It is a
    ~3,500-file scan; rebuilding it per bill would repeat that 38,756 times during
    the backfill. The filename IS the id (`export_rollcall` writes
    `{rollcall.id}.json`), so no file is opened."""
    from ingest.cache import repo_root

    votes_dir = repo_root() / "data" / "votes"
    return {p.stem for p in votes_dir.rglob("*.json")}


def bill_id_from_list_item(item: dict) -> str | None:
    """`{"type": "HR", "number": "1379", "congress": 119}` -> `"hr1379-119"`, the
    canonical id shape `parse_bill_id` round-trips. None if the item is malformed
    (the caller quarantines rather than inventing an id)."""
    try:
        btype = str(item["type"]).lower().strip()
        number = int(str(item["number"]).strip())
        congress = int(item["congress"])
    except (KeyError, TypeError, ValueError):
        return None
    if not btype:
        return None
    return f"{btype}{number}-{congress}"


def _bills_dir():
    from ingest.cache import repo_root

    return repo_root() / "data" / "bills"


def load_existing_bill(bill_id: str) -> Bill | None:
    """The committed record for a bill, or None if we do not hold it yet.
    A malformed committed file reads as None so the caller re-fetches it whole
    rather than merging into a broken record."""
    path = _bills_dir() / f"{bill_id}.json"
    if not path.exists():
        return None
    try:
        return Bill(**json.loads(path.read_text(encoding="utf-8")))
    except (ValidationError, ValueError, KeyError):
        return None


def merge_activity(
    existing: Bill, *, actions: list[BillAction], list_item: dict
) -> Bill:
    """Fold a fresh action timeline into a bill we already hold, WITHOUT refetching
    its detail/subjects/cosponsors (SD-33 cost constraint 2).

    Anti-clobber (the D35 shape, same rule `run()` documents for subjects): fields
    not being refreshed are carried through untouched, so a bill that already has
    enriched subjects can never be written back with the `None` "not collected"
    sentinel just because this cheaper path did not fetch them.

    `latest_action` / `latest_action_date` ARE refreshed, from the list item the
    enumeration already returned (no extra request). The list item is the same
    `latestAction` block the detail endpoint serves. If it is absent or malformed
    the committed values are kept rather than blanked."""
    latest = list_item.get("latestAction") or {}
    text = latest.get("text")
    date = latest.get("actionDate")
    return existing.model_copy(
        update={
            "actions": actions,
            "latest_action": text if text else existing.latest_action,
            "latest_action_date": date if date else existing.latest_action_date,
        }
    )


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
    actions: list[BillAction] | None = None,
) -> Bill:
    """Parse a `/bill/{c}/{type}/{number}` response into a `Bill`. Raises on
    malformed data so the caller quarantines the whole bill (§6.1).

    `subjects` / `cosponsor_ids` / `actions` come from the paginated sub-resources
    (fetched by the caller); passing `None` records "not collected" (D27), a real
    list (incl. `[]`) records the collected value. Pure: no fetching happens here."""
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
        actions=actions,  # fetched sub-resource (V2-11); None only if uncollected
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
    new/recent bills (whose enrichment refreshes on every re-export, never reverts).

    V2-11: `/actions` joins subjects and cosponsors as a per-bill sub-resource,
    fetched for every bill this pipeline exports under the same never-revert rule.
    That is one extra request per exported bill. This command still covers only the
    ~1,000 vote-referenced bills; the 38,756-bill universe is `ingest bill-activity`."""
    import httpx

    from ingest import config, incremental
    from ingest.cache import RetryableHTTPError
    from ingest.export import export_bill
    from ingest.sources import congress_gov

    # TruncatedFetchError joins the tuple with V2-11: `bill_actions()` raises it on a
    # short page AND on its dedupe-undercount guard. Either must record a per-bill
    # fetch failure (re-runnable) like any other, never abort the whole nightly.
    fetch_errors = (
        RetryableHTTPError, httpx.HTTPError, OSError, congress_gov.TruncatedFetchError
    )
    force_all = bool(argv) and "--all" in argv

    accepted_ids = incremental.accepted_quarantines()  # owner-reviewed, non-fatal (§6.1)
    bill_ids = referenced_bill_ids()
    total = len(bill_ids)
    # Incremental (§6.1): skip bills already exported, EXCEPT those referenced by a
    # roll from the last 7 days (their latest_action may still be moving). `--all`
    # overrides the skip so the sub-resource backfill reaches every bill once.
    cutoff = incremental.final_cutoff()
    recent = incremental.recent_bill_ids(cutoff)
    known_rolls = known_rollcall_ids()  # once per run, not once per bill
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
            raw_actions = congress_gov.bill_actions(congress, btype, number)
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
            bill = parse_bill(
                data, bill_id,
                subjects=subjects,
                cosponsor_ids=cosponsor_ids,
                actions=parse_actions(raw_actions, known_rollcall_ids=known_rolls),
            )
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


# --- V2-11: bill activity across the whole covered universe ---------------


class CiRefusal(Exception):
    """A full-Congress backfill was started inside CI. See `run_activity`."""


def _in_ci() -> bool:
    import os

    return bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def _parse_activity_args(argv: list[str]) -> dict:
    """`--congress N` (enumerate that Congress whole) | `--since HOURS` (default
    30) | `--limit N` | `--allow-ci` | `--refresh-all`. Raises ValueError on
    anything else so a typo'd flag can never silently become a 43-hour run.

    **A backfill RESUMES by default** (`skip_existing` True whenever `--congress`
    is given): it fills in what is missing and never re-does a finished bill.
    That is both the semantics you want from a backfill and the safe default for
    a run that will be interrupted a dozen times — the flag has to be remembered
    on every single resume, and forgetting it once costs ~5 h of refetching
    (D91). `--refresh-all` opts out. `--skip-existing` is still accepted as a
    no-op alias, because it is what the first draft of the docs said to type."""
    opts = {
        "congress": None, "since": 30.0, "limit": None,
        "allow_ci": False, "refresh_all": False,
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--skip-existing":  # now the default for a backfill; kept as a no-op
            i += 1
            continue
        if a in ("--allow-ci", "--refresh-all"):
            opts[a[2:].replace("-", "_")] = True
            i += 1
            continue
        if a in ("--congress", "--since", "--limit"):
            if i + 1 >= len(argv):
                raise ValueError(f"{a} needs a value")
            raw = argv[i + 1]
            try:
                opts[a[2:]] = float(raw) if a == "--since" else int(raw)
            except ValueError:
                raise ValueError(f"{a} needs a number, got {raw!r}") from None
            i += 2
            continue
        raise ValueError(f"unknown argument {a!r}")
    if opts["congress"] is not None and opts["congress"] not in config_congresses():
        raise ValueError(
            f"--congress {opts['congress']} is outside the covered set "
            f"{config_congresses()}"
        )
    if opts["since"] <= 0:
        raise ValueError("--since must be positive")
    if opts["refresh_all"] and opts["congress"] is None:
        raise ValueError(
            "--refresh-all is a backfill flag and needs --congress N; the --since "
            "delta path already refreshes every bill in its window."
        )
    # Resume unless told otherwise. Never on the delta path: there, skipping bills
    # we already hold would silently stop refreshing the timelines the nightly
    # exists to refresh.
    opts["skip_existing"] = opts["congress"] is not None and not opts["refresh_all"]
    return opts


def config_congresses() -> list[int]:
    from ingest import config

    return list(config.CONGRESSES)


def run_activity(argv: list[str] | None = None) -> int:
    """V2-11 task 4 — ingest bill ACTIVITY across the full covered universe
    (38,756 bills), not just the ~1,000 that reached a roll call.

    Two modes, both enumerating through `congress_gov.bills_updated_since`:

    * **`--congress N`: the one-time backfill.** Enumerates that Congress whole
      and ingests every bill it has not got. **REFUSES TO RUN IN CI.** At 4
      requests per new bill and the 1 req/s ceiling this is >= ~43 h, about 2,590
      GitHub Actions minutes -- more than an entire month's 2,000-minute free
      allowance (SD-33, D88, H24). It runs locally and the result is committed.
      `--allow-ci` overrides, and exists for exactly one case: a self-hosted
      runner, where minutes are not billed (the escape hatch H24 documents).
    * **`--since HOURS` (default 30): the nightly delta.** Enumerates bills whose
      `updateDate` moved in the window. 30 h rather than 24 so a late or retried
      nightly cannot open a gap between runs; re-seeing a bill is idempotent.

    **The cost rule that shapes this command (SD-33 constraint 2):** a bill we
    ALREADY HOLD costs ONE request -- its `/actions` -- and is merged into the
    committed record by `merge_activity`, which carries every other field through
    untouched. Only a genuinely NEW bill pays the full four (detail + subjects +
    cosponsors + actions). Refetching everything for every updated bill would be
    ~19-29 min/night (~560-870/month) and would not fit beside the D86 nightly;
    actions-only is ~5-7 min/night (~150-210/month), which does.

    Idempotent and resumable: every fetch is cached and every bill is exported as
    it is finished, so an interrupted 43-hour backfill resumes where it stopped.
    Malformed bills are quarantined under the existing §6.1 ceiling."""
    import httpx

    from ingest import config
    from ingest.cache import RetryableHTTPError
    from ingest.export import export_bill
    from ingest.sources import congress_gov

    try:
        opts = _parse_activity_args(list(argv or []))
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    backfill = opts["congress"] is not None
    if backfill and _in_ci() and not opts["allow_ci"]:
        print(
            "FAIL: a full-Congress backfill must not run in CI.\n"
            "  At 1 request/second this is >= ~43 h (~2,590 Actions minutes) for all\n"
            "  38,756 bills -- more than a whole month's 2,000-minute free allowance\n"
            "  (SD-33, H24). Run it locally and commit the result.\n"
            "  --allow-ci overrides, and is meant only for a self-hosted runner."
        )
        return 2

    fetch_errors = (
        RetryableHTTPError, httpx.HTTPError, OSError, congress_gov.TruncatedFetchError
    )
    known_rolls = known_rollcall_ids()  # once per run, not once per bill
    # Resolved per run, not bound at import: `export.BILLS_DIR` is a module-level
    # constant baked in at import time, so a test (or any caller) that redirects
    # the repo root would otherwise still write into the real data/bills.
    out_dir = _bills_dir()

    if backfill:
        scope = f"congress {opts['congress']} (whole)"
        items = congress_gov.bills_updated_since(congress=opts["congress"])
    else:
        from datetime import UTC, datetime, timedelta

        now = datetime.now(UTC).replace(microsecond=0)
        since = now - timedelta(hours=opts["since"])
        scope = f"updated in the last {opts['since']:g} h"
        items = [
            it
            for it in congress_gov.bills_updated_since(since, now)
            if it.get("congress") in set(config.CONGRESSES)
        ]

    if opts["limit"] is not None:
        items = items[: opts["limit"]]

    total = len(items)
    print(f"civic-ledger bill-activity: {total} bill(s) {scope}.")

    done_ids: set[str] = bills_with_actions() if opts["skip_existing"] else set()
    if opts["skip_existing"]:
        held = sum(1 for it in items if bill_id_from_list_item(it) in done_ids)
        left = total - held
        print(
            f"  resume: {held}/{total} already have timelines, {left} to go "
            f"(~{left * SECONDS_PER_BILL / 3600:.1f} h at 1 request/second)."
        )

    new_bills = 0
    refreshed = 0
    skipped = 0
    quarantined: list[str] = []
    fetch_failures: list[str] = []

    for n, item in enumerate(items, 1):
        bill_id = bill_id_from_list_item(item)
        if bill_id is None:
            quarantined.append(repr(item)[:80])
            continue
        try:
            btype, number, congress = parse_bill_id(bill_id)
        except BadBillId as exc:
            _quarantine(bill_id, f"{type(exc).__name__}: {exc}")
            quarantined.append(bill_id)
            continue

        if bill_id in done_ids:  # --skip-existing: zero requests, see bills_with_actions
            skipped += 1
            continue

        existing = load_existing_bill(bill_id)
        try:
            raw_actions = congress_gov.bill_actions(congress, btype, number)
            actions = parse_actions(raw_actions, known_rollcall_ids=known_rolls)
            if existing is not None:
                # SD-33 constraint 2: one request for a bill we already hold.
                bill = merge_activity(existing, actions=actions, list_item=item)
            else:
                data = congress_gov.bill_detail(congress, btype, number).json()
                bill = parse_bill(
                    data, bill_id,
                    subjects=congress_gov.bill_subjects(congress, btype, number),
                    cosponsor_ids=congress_gov.bill_cosponsor_ids(congress, btype, number),
                    actions=actions,
                )
        except fetch_errors as exc:
            fetch_failures.append(f"{bill_id}: {type(exc).__name__}")
            continue
        except (ValidationError, KeyError, BadBillId) as exc:
            _quarantine(bill_id, f"{type(exc).__name__}: {exc}")
            quarantined.append(bill_id)
            continue

        export_bill(bill, out_dir=out_dir)
        _clear_quarantine(bill_id)
        if existing is None:
            new_bills += 1
        else:
            refreshed += 1
        if n % 500 == 0:
            print(f"  ... {n}/{total} ({new_bills} new, {refreshed} refreshed, "
                  f"{skipped} already held)")

    print(
        f"bill-activity: {new_bills} new + {refreshed} refreshed + {skipped} "
        f"already held of {total} ({len(quarantined)} quarantined, "
        f"{len(fetch_failures)} fetch failures)."
    )
    if quarantined:
        frac = len(quarantined) / total if total else 0.0
        print(f"  {len(quarantined)} quarantined ({frac:.2%}): {quarantined[:10]}")
        if frac > config.QUARANTINE_MAX_FRACTION:
            print(f"FAIL: quarantine {frac:.2%} exceeds {config.QUARANTINE_MAX_FRACTION:.0%}")
            return 1
    if fetch_failures:
        print(f"FAIL: {len(fetch_failures)} bill(s) failed to fetch (re-run to retry): "
              f"{fetch_failures[:10]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
