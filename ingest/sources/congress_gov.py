"""api.congress.gov v3 source (§3, D6). Auth: X-Api-Key header (never in URL).

Endpoints are the ones VERIFIED in the INC-1 spike, not the spec's assumptions:
  * Members by state is a PATH segment `/member/{stateCode}`, NOT a query param.
    The `?stateCode=` query form returns 503 (recorded in SHAPES.md + decisions).
  * House votes use the beta `/house-vote/{congress}/{session}` family; the list
    response carries each vote's clerk XML `sourceDataURL` for cross-checking.
  * Member positions live at `/house-vote/{c}/{s}/{roll}/members`, where the id
    field is `bioguideID` (capital ID) — the member-list endpoint uses `bioguideId`.

Every fetch is cached (ingest/cache.py). Rate ceiling ≤ 1 req/sec is enforced
there per host.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from ingest import env
from ingest.cache import DEFAULT_TTL_HOURS, CachedResponse, fetch

BASE = "https://api.congress.gov/v3"
SOURCE = "congress_gov"


class TruncatedFetchError(Exception):
    """A paginated fetch returned an empty page before reaching its official
    `pagination.count` — a premature/corrupt 200 that would silently undercount
    (value #1: never publish a false zero). Raised by `member_legislation` (D64)."""


def _headers() -> dict[str, str]:
    # Header-only auth; the key never enters a URL, param, or cache key.
    return {"X-Api-Key": env.require("CONGRESS_API_KEY")}


def _get(path: str, params: dict | None = None, **kw) -> CachedResponse:
    p = {"format": "json"}
    if params:
        p.update(params)
    return fetch(SOURCE, f"{BASE}/{path.lstrip('/')}", params=p, headers=_headers(), **kw)


# --- Members --------------------------------------------------------------
def members_by_state(state: str, current_only: bool = True, limit: int = 250) -> CachedResponse:
    params = {"limit": str(limit)}
    if current_only:
        params["currentMember"] = "true"
    return _get(f"member/{state}", params)


# --- House votes (beta) ---------------------------------------------------
def house_vote_list(
    congress: int, session: int, limit: int = 250, offset: int = 0
) -> CachedResponse:
    return _get(f"house-vote/{congress}/{session}", {"limit": str(limit), "offset": str(offset)})


def house_vote_detail(congress: int, session: int, roll: int) -> CachedResponse:
    return _get(f"house-vote/{congress}/{session}/{roll}")


def house_vote_roll_numbers(congress: int, session: int) -> tuple[list[int], int]:
    """Enumerate every roll-call number for a session via the paginated list.

    Returns (sorted unique roll numbers, official `pagination.count`). The count is
    the acceptance's "official session total"; the caller asserts the two agree so
    a pagination gap can never masquerade as a complete ingest.
    """
    page = house_vote_list(congress, session, limit=250, offset=0).json()
    count = int(page["pagination"]["count"])
    rolls: set[int] = set()
    offset = 0
    while True:
        data = house_vote_list(congress, session, limit=250, offset=offset).json()
        votes = data.get("houseRollCallVotes", [])
        if not votes:
            break
        rolls.update(int(v["rollCallNumber"]) for v in votes)
        offset += 250
        if offset >= count:
            break
    return sorted(rolls), count


def house_vote_members(congress: int, session: int, roll: int) -> CachedResponse:
    return _get(f"house-vote/{congress}/{session}/{roll}/members")


# --- Bills ----------------------------------------------------------------
def bill_detail(congress: int, bill_type: str, number: int) -> CachedResponse:
    return _get(f"bill/{congress}/{bill_type.lower()}/{number}")


def bill_committees(
    congress: int, bill_type: str, number: int, *, ttl_hours: float = DEFAULT_TTL_HOURS
) -> CachedResponse:
    """A bill/resolution's committees + per-committee activities. INC-5 R-RULE
    reads this to tell a Rules-Committee-reported special rule (→ procedural) from
    a substantive resolution (→ passage): the House Rules Committee is systemCode
    `hsru00` with a "Reported ..." activity.

    `ttl_hours` overrides the 20 h default. Unlike the legislation lists (where D86
    REJECTED a >24 h TTL, because those lists must keep refreshing), this answer is
    final once a roll exists: the Rules Committee reports a special rule BEFORE the
    floor vote it governs, so "was this reported by hsru00" cannot change afterwards."""
    return _get(f"bill/{congress}/{bill_type.lower()}/{number}/committees",
                ttl_hours=ttl_hours)


def bill_subjects(congress: int, bill_type: str, number: int, *, force: bool = False) -> list[str]:
    """Government-assigned legislative subject terms via the paginated
    `/bill/{c}/{type}/{number}/subjects` sub-resource (INC-10). Returns the sorted
    unique term names; `[]` means the government assigned none (distinct from the
    `Bill.subjects is None` "not yet collected" sentinel — D27). policyArea is a
    separate node already captured on the bill detail, so it is not folded in here.
    Mirrors `house_vote_roll_numbers`' count-bounded pagination."""
    names: set[str] = set()
    offset = 0
    while True:
        page = _get(
            f"bill/{congress}/{bill_type.lower()}/{number}/subjects",
            {"limit": "250", "offset": str(offset)},
            force=force,
        ).json()
        subs = (page.get("subjects") or {}).get("legislativeSubjects") or []
        if not subs:
            break
        names.update(s["name"] for s in subs)
        offset += 250
        if offset >= int(page.get("pagination", {}).get("count", 0)):
            break
    return sorted(names)


def bill_cosponsor_ids(
    congress: int, bill_type: str, number: int, *, force: bool = False
) -> list[str]:
    """Current cosponsors' bioguide ids via the paginated `/cosponsors`
    sub-resource (INC-10). Returns the sorted unique ids; `[]` means none. A
    cosponsor who WITHDREW (`sponsorshipWithdrawnDate` present) is no longer a
    cosponsor and is excluded — the API's `count` (vs `countIncludingWithdrawn`)
    reflects the same distinction; including them would be a false claim."""
    ids: set[str] = set()
    offset = 0
    while True:
        page = _get(
            f"bill/{congress}/{bill_type.lower()}/{number}/cosponsors",
            {"limit": "250", "offset": str(offset)},
            force=force,
        ).json()
        cos = page.get("cosponsors") or []
        if not cos:
            break
        ids.update(
            c["bioguideId"] for c in cos if not c.get("sponsorshipWithdrawnDate")
        )
        offset += 250
        if offset >= int(page.get("pagination", {}).get("count", 0)):
            break
    return sorted(ids)


# --- Bill actions + bill enumeration (V2-11 task 2; shapes from D88) ------
PAGE_LIMIT = 250
"""Hard page ceiling on every Congress.gov list endpoint. `limit=251` does NOT
error - it silently clamps to 250 (D88), so the paginators below bound
themselves on `pagination.count` and never on the length of a returned page."""

UPDATE_SORT = "updateDate desc"
"""The ONLY sort form that works, and the direction a crawl must use.

Two separate traps, both measured live (D88):
  * **`updateDate+desc` is silently ignored.** The documented `+` is transmitted
    as a literal `%2B`; the API discards the whole sort and returns the identical
    page as a deliberate `sort=BOGUSVALUE` control. The literal space (encoded
    `%20`) is what works. Never reintroduce the `+`.
  * **Descending is the safe crawl direction.** A bill updated mid-crawl gets a
    new `updateDate` and jumps to position 0, shifting the pages behind it DOWN
    - so an in-flight crawl re-reads an item it already has (idempotent, free)
    rather than stepping over one it has not. Ascending moves a touched bill to
    the END and shifts everything after it UP, which SKIPS an item at the cursor.
    Skips are silent undercounts (value #1); duplicates are not."""


def _iso_z(when: datetime) -> str:
    """Congress.gov's `fromDateTime`/`toDateTime` format: `YYYY-MM-DDTHH:MM:SSZ`.
    Naive input is read as UTC; aware input is converted. Sub-second precision is
    dropped - the API rejects it."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def bill_actions(
    congress: int, bill_type: str, number: int, *, force: bool = False
) -> list[dict]:
    """A bill's full official action timeline, via the paginated
    `/bill/{c}/{type}/{number}/actions` sub-resource (V2-11 task 2).

    Returns the raw action dicts in the order the API gives them (newest first),
    NOT reordered, reworded, or classified - 0.5 forbids summarising anything that
    publishes as fact, and `text` is the published string. Deduplication is on the
    WHOLE row and nothing narrower: several genuinely distinct actions can share a
    date, text and action code and differ only in `committees` (see the loop).
    `[]` means the government lists no actions, which is distinct from the
    `Bill.actions is None` "not yet collected" sentinel (D27).

    Field shape is recorded as SHAPES.md section 9 and sampled in
    `data/quality/samples/congress_bill_actions_hr2670_118.json`. Note that
    `actionTime`, `actionCode`, `committees` and `calendarNumber` are all
    OPTIONAL (D88: `actionTime` was present on only 142/234 actions of the
    largest timeline found), so no caller may assume them.

    **The paginated branch is UNEXERCISED against the live API.** The largest
    action list D88 could find is 234 (`hr2670-118`, NDAA FY24), under the 250
    ceiling, so `pagination.next` has never actually been returned here. The loop
    is written and unit-tested against a synthetic payload rather than left out;
    it cannot be confirmed live until some bill exceeds 250 actions.

    Truncation guard (D64, same contract as `member_legislation`): the loop breaks
    on `offset >= count` before it can page past the end, so an empty page while
    `offset < count` is never legitimate - it is a premature/corrupt 200 that
    would publish a bill as having fewer actions than it has. `count` is read once
    from page 0; a later corrupt page's own metadata is not trusted."""
    actions: list[dict] = []
    seen: set[str] = set()
    offset = 0
    count: int | None = None
    while True:
        page = _get(
            f"bill/{congress}/{bill_type.lower()}/{number}/actions",
            {"limit": str(PAGE_LIMIT), "offset": str(offset)},
            force=force,
        ).json()
        if count is None:
            count = int(page.get("pagination", {}).get("count", 0))
        batch = page.get("actions") or []
        if not batch:
            if offset < count:
                raise TruncatedFetchError(
                    f"{bill_type.lower()}{number}-{congress} actions: empty page at "
                    f"offset {offset} < count {count} (truncated fetch - would "
                    f"publish an incomplete timeline)"
                )
            break
        for a in batch:
            # Dedupe on the WHOLE row, never a chosen subset of fields. A narrower
            # key silently drops real actions: hr2670-118 has five rows reading
            # "Forwarded by Subcommittee to Full Committee by Voice Vote ." on
            # 2023-06-13 with the same actionCode, distinguished ONLY by which
            # subcommittee is in `committees` (and six more of a second such set).
            # Keying on (date, time, code, text) collapsed 234 real actions to 225
            # -- a false undercount, exactly what value #1 forbids.
            fingerprint = json.dumps(a, sort_keys=True, separators=(",", ":"))
            if fingerprint not in seen:
                seen.add(fingerprint)
                actions.append(a)
        offset += PAGE_LIMIT
        if offset >= count:
            break
    # Dedupe-undercount guard. Whole-row dedupe is lossless on every timeline
    # measured (234/234 on hr2670-118), but two byte-identical rows that are BOTH
    # real would collapse to one and nothing else would notice. Comparing against
    # page 0's `count` closes that: fewer unique rows than the government claims is
    # an incomplete timeline, which is the same false-undercount the D64 guard above
    # exists to refuse. Only `<` -- a mid-crawl append raises the LIVE count while
    # `count` stays at page 0's value, so a re-serve lands at `len == count` and does
    # not trip this. Task 4 quarantines the bill rather than committing short.
    if len(actions) < count:
        raise TruncatedFetchError(
            f"{bill_type.lower()}{number}-{congress} actions: {len(actions)} unique "
            f"rows < count {count} (dedupe collapsed real actions, or the API "
            f"over-reported its own count)"
        )
    return actions


def bills_updated_since(
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    *,
    congress: int | None = None,
    force: bool = False,
) -> list[dict]:
    """Enumerate bills from the `/bill` list endpoint, newest-updated first.

    Two callers, one function (V2-11 task 2):
      * **The nightly delta** passes a window - `from_dt`/`to_dt` become
        `fromDateTime`/`toDateTime`, which D88 verified are honored (435 bills in
        a probed 24 h, 1,954 over 7 d, against 430,715 unfiltered) and compose
        with the `/bill/{congress}` path form.
      * **The one-time backfill** passes `congress=` and no window, enumerating
        that Congress whole (118th = 19,315, 119th = 19,441 as of 2026-10-01).
        D88 follow-up confirmed there is NO deep-offset ceiling: offset 19,300
        still serves rows and offset >= count returns an empty page, so the
        count-bounded loop terminates cleanly.

    Returns the raw list items. Each already carries `congress`, `type`, `number`,
    `title`, `introducedDate`, `latestAction`, `updateDate` and the detail `url`,
    so an enumeration pass costs no per-bill request on its own.

    **This function must never drive a full backfill inside CI.** The enumeration
    itself is cheap (156 pages), but the per-bill detail/subjects/cosponsors/
    actions work its output feeds is at least ~43 h, about 2,590 GitHub Actions
    minutes for all 38,756 bills - more than an entire month's free allowance
    (SD-33, H24). The backfill runs locally and is committed.

    Truncation guard as `bill_actions`. Safe under concurrent updates in one
    direction only - see `UPDATE_SORT`."""
    path = f"bill/{congress}" if congress is not None else "bill"
    window: dict[str, str] = {}
    if from_dt is not None:
        window["fromDateTime"] = _iso_z(from_dt)
    if to_dt is not None:
        window["toDateTime"] = _iso_z(to_dt)

    bills: list[dict] = []
    seen: set[tuple] = set()
    offset = 0
    count: int | None = None
    while True:
        page = _get(
            path,
            {
                "limit": str(PAGE_LIMIT),
                "offset": str(offset),
                "sort": UPDATE_SORT,
                **window,
            },
            force=force,
        ).json()
        if count is None:
            count = int(page.get("pagination", {}).get("count", 0))
        batch = page.get("bills") or []
        if not batch:
            if offset < count:
                raise TruncatedFetchError(
                    f"bill list ({path}, window={window or 'none'}): empty page at "
                    f"offset {offset} < count {count} (truncated fetch - would "
                    f"silently drop bills from the ingest)"
                )
            break
        for b in batch:
            # A descending crawl re-serves rows when a bill is updated mid-crawl
            # (see UPDATE_SORT); dedupe on identity so that costs nothing.
            ident = (
                b.get("congress"),
                (b.get("type") or "").lower(),
                str(b.get("number")),
            )
            if ident not in seen:
                seen.add(ident)
                bills.append(b)
        offset += PAGE_LIMIT
        if offset >= count:
            break
    return bills


# --- Member legislation (INC-10) ------------------------------------------
def member_lifetime_counts(bioguide: str) -> dict[str, int]:
    """Lifetime sponsored/cosponsored item counts for a member, from ONE request to
    `/member/{bioguide}` (D86). The detail response carries
    `sponsoredLegislation.count` / `cosponsoredLegislation.count`, and each equals the
    corresponding list endpoint's `pagination.count` (verified live 2026-09-29:
    W000437 761/4,534 on both). The nightly uses it as a cheap change probe: an
    unchanged pair means no new sponsorship or cosponsorship since the committed
    record, so the multi-page list fetch (≈7 s per 250-item page) is skipped.
    Returns {"sponsored": n, "cosponsored": n}. A missing block reads as 0 — the
    caller then re-pages (a 0 never matches a committed non-zero), so a malformed
    detail response degrades to the full fetch, never to a stale reuse."""
    member = _get(f"member/{bioguide}").json().get("member") or {}
    return {
        "sponsored": int((member.get("sponsoredLegislation") or {}).get("count") or 0),
        "cosponsored": int((member.get("cosponsoredLegislation") or {}).get("count") or 0),
    }


def member_legislation(
    bioguide: str, kind: str, congresses: list[int], *, force: bool = False
) -> list[dict]:
    """Raw sponsored/cosponsored legislation items for a member, filtered to the
    covered `congresses`. `kind` ∈ {"sponsored-legislation", "cosponsored-legislation"}.

    The endpoints return items newest-first with a lifetime `pagination.count`
    (Wicker: 4,522 cosponsored), and offer no congress filter — so we page until a
    page yields ZERO in-window items, then stop. We deliberately do NOT stop on the
    first out-of-window item: the ordering is by action/introduced date, not
    strictly by congress, so a boundary page can interleave a covered and an
    uncovered item; stopping on the first uncovered one would silently drop covered
    tail items (an undercount — value #1). One page of slack removes that risk.

    Truncation guard (D64): the loop breaks on `offset >= count` before it can page
    past the end, so an *empty* page while `offset < count` is never legitimate — it
    is a premature/corrupt 200 that would publish a false zero. We raise
    `TruncatedFetchError` there rather than silently undercount. `count` is read once
    from page 0 (a later corrupt page's own metadata is not trusted). Residual blind
    spot (tripwire, not proof — §CS): a corrupt response returning `count: 0`/no
    pagination at offset 0 is indistinguishable from a member with zero lifetime
    items; the caller's zero-regression check (`legislation._count_regressions`) is
    the complementary guard for that case on the nightly refetch path."""
    key = "sponsoredLegislation" if kind.startswith("sponsored") else "cosponsoredLegislation"
    covered = set(congresses)
    items: list[dict] = []
    offset = 0
    count: int | None = None
    while True:
        page = _get(
            f"member/{bioguide}/{kind}",
            {"limit": "250", "offset": str(offset)},
            force=force,
        ).json()
        if count is None:
            count = int(page.get("pagination", {}).get("count", 0))
        batch = page.get(key) or []
        if not batch:
            if offset < count:
                raise TruncatedFetchError(
                    f"{bioguide} {kind}: empty page at offset {offset} < count "
                    f"{count} (truncated fetch — would publish a false zero)"
                )
            break
        in_window = [it for it in batch if it.get("congress") in covered]
        items.extend(in_window)
        # Stop only once a whole page is out of window (newest-first ⇒ nothing
        # covered remains beyond it). Never stop mid-page on a single old item.
        if not in_window:
            break
        offset += 250
        if offset >= count:
            break
    return items


# --- Congressional Record (index; full-text search is an INC-6 concern) ---
def congressional_record(limit: int = 20, **params) -> CachedResponse:
    extra = {k: str(v) for k, v in params.items()}
    return _get("congressional-record", {"limit": str(limit), **extra})
