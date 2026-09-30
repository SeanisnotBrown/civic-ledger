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
