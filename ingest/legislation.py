"""INC-10 — member sponsored/cosponsored legislation (the metrics input).

Each covered member's sponsored + cosponsored bills over the covered Congresses
are fetched from the `/member/{id}/{sponsored,cosponsored}-legislation` endpoints
and written to data/legislation/{member}.json. The metrics layer reads ONLY this
committed artifact (never the live API), so a third party can recompute every
legislation metric from the public repo (the verify-recompute contract).

`parse_items` is pure (raw API items -> list[LegItem]); `run()` fetches and exports.
See `LegItem` for why no live latest-action field is stored (quiet-night diff-gate).
"""

from __future__ import annotations

import html
from collections import Counter

from ingest.models import LegItem, MemberLegislation


def _count_regressions(
    mid: str,
    prior_sponsored: Counter[int],
    prior_cosponsored: Counter[int],
    fresh_sponsored: Counter[int],
    fresh_cosponsored: Counter[int],
    congresses: list[int],
) -> list[str]:
    """Regression guard (value #1, D64): if the previously-committed record had >0
    items for a congress and the fresh parse now has 0, that is a truncated/corrupt
    refetch — bills do not un-sponsor. Fires ONLY on a real drop-to-zero, so it is
    quiet on the unattended nightly path (a genuine served-congress zero — a member
    who resigned days into the term, a late special-election seating, or a low-output
    former leader — was zero last run too and never trips it). This complements the
    fetch-level `TruncatedFetchError`, which catches an *empty* premature page; this
    catches a *non-empty-but-corrupt* page whose items parse to zero in-window. Pure,
    so it is unit-testable without the fetch/export path. On a first-ever ingest (no
    prior record) both prior counters are empty and nothing fires.

    (This replaces the pre-D64 `_sponsored_gaps` heuristic, which inferred "truncated
    fetch" from any served-congress zero and so false-failed on ten legitimate 2026
    cases — see D64 for the roster and the soundness argument.)"""
    out: list[str] = []
    for kind, prior, fresh in (
        ("sponsored", prior_sponsored, fresh_sponsored),
        ("cosponsored", prior_cosponsored, fresh_cosponsored),
    ):
        for c in congresses:
            if prior.get(c, 0) > 0 and fresh.get(c, 0) == 0:
                out.append(
                    f"{mid}: {kind} count in congress {c} regressed "
                    f"{prior[c]}→0 (truncated fetch?)"
                )
    return out


def _prior_counts(path) -> tuple[Counter[int], Counter[int]]:
    """(sponsored, cosponsored) per-congress counts from the previously-committed
    export at `path`, or empty counters if it does not exist yet (first ingest).
    The committed file is in export shape (LegItem dumps), so we count `congress`
    directly rather than re-parsing raw API items."""
    import json

    if not path.exists():
        return Counter(), Counter()
    rec = json.loads(path.read_text(encoding="utf-8"))
    return (
        Counter(it["congress"] for it in rec.get("sponsored", [])),
        Counter(it["congress"] for it in rec.get("cosponsored", [])),
    )

# Bill-type code -> congress.gov URL segment, for a human-checkable source_url.
_URL_TYPE: dict[str, str] = {
    "hr": "house-bill", "s": "senate-bill",
    "hres": "house-resolution", "sres": "senate-resolution",
    "hjres": "house-joint-resolution", "sjres": "senate-joint-resolution",
    "hconres": "house-concurrent-resolution", "sconres": "senate-concurrent-resolution",
}


def _bill_id(item: dict) -> str:
    return f"{item['type'].lower()}{item['number']}-{item['congress']}"


def _source_url(item: dict) -> str:
    btype = item["type"].lower()
    seg = _URL_TYPE.get(btype)
    if seg:
        return f"https://www.congress.gov/bill/{item['congress']}th-congress/{seg}/{item['number']}"
    # Unknown type: fall back to the API url the endpoint gave (always present).
    return item["url"].replace("?format=json", "")


def parse_items(raw: list[dict]) -> list[LegItem]:
    """Pure: raw sponsored/cosponsored items -> sorted list[LegItem]. `became_law`
    is a deterministic substring match on the official latest-action text; the
    frozen enacting text is kept only when enacted (see LegItem).

    Floor AMENDMENTS are excluded: the endpoints interleave sponsored/cosponsored
    amendments (`type: null`, an `amendmentNumber`, an `/amendment/` url) with
    bills, but an amendment is not a bill — it can't become law under its own
    number and lives in our vote record as an amendment-class roll, not the bill
    space. "Sponsored/cosponsored" here means bills and resolutions only (stated on
    the methodology page)."""
    out: list[LegItem] = []
    for it in raw:
        if not it.get("type") or not it.get("number"):
            continue  # amendment (or malformed) — not a bill; see docstring
        action = (it.get("latestAction") or {}).get("text") or ""
        became_law = "Became Public Law" in action
        out.append(
            LegItem(
                bill_id=_bill_id(it),
                congress=int(it["congress"]),
                title=html.unescape(it.get("title") or ""),
                introduced_date=it.get("introducedDate"),
                became_law=became_law,
                enacted_action=action if became_law else None,
                source_url=_source_url(it),
            )
        )
    out.sort(key=lambda x: x.bill_id)
    return out


def run(argv: list[str] | None = None) -> int:
    """Fetch + export data/legislation/{member}.json for every covered member.
    Idempotent (cached fetches). Two value-#1 truncation guards (D64): the fetch
    raises `TruncatedFetchError` on a premature-empty page, and `_count_regressions`
    fails the run if any congress that had records before now parses to zero (bills
    do not un-sponsor). A genuine served-congress zero — a member who served only
    days of a congress, or a low-output leader — is a true fact and does NOT fail."""
    import httpx

    from ingest import config
    from ingest.cache import RetryableHTTPError, repo_root
    from ingest.export import export_member_legislation
    from ingest.sources import congress_gov
    from ingest.sources.congress_gov import TruncatedFetchError

    fetch_errors = (RetryableHTTPError, httpx.HTTPError, OSError, TruncatedFetchError)
    data_dir = repo_root() / "data"
    members_dir = data_dir / "members"
    leg_dir = data_dir / "legislation"
    import json

    members = {
        (m := json.loads(p.read_text(encoding="utf-8")))["id"]: m
        for p in members_dir.glob("*.json")
    }
    member_ids = sorted(members)

    failures: list[str] = []
    exported = 0
    for mid in member_ids:
        try:
            congs = config.CONGRESSES
            sponsored_raw = congress_gov.member_legislation(mid, "sponsored-legislation", congs)
            cosponsored_raw = congress_gov.member_legislation(mid, "cosponsored-legislation", congs)
        except fetch_errors as exc:
            failures.append(f"{mid}: {type(exc).__name__}")
            continue
        sponsored = parse_items(sponsored_raw)
        cosponsored = parse_items(cosponsored_raw)

        # Sanity (value #1): a previously-present congress must not drop to zero on a
        # refetch (truncation). Read the prior committed record BEFORE overwriting it.
        prior_sp, prior_co = _prior_counts(leg_dir / f"{mid}.json")
        failures.extend(_count_regressions(
            mid, prior_sp, prior_co,
            Counter(li.congress for li in sponsored),
            Counter(li.congress for li in cosponsored),
            config.CONGRESSES,
        ))

        rec = MemberLegislation(
            member_id=mid,
            sponsored=sponsored,
            cosponsored=cosponsored,
            source_url=f"https://api.congress.gov/v3/member/{mid}/sponsored-legislation",
        )
        export_member_legislation(rec)
        exported += 1
        print(f"  {mid}: {len(sponsored)} sponsored, {len(cosponsored)} cosponsored "
              f"(118–119); {sum(li.became_law for li in sponsored)} enacted.")

    print(f"civic-ledger legislation: exported {exported}/{len(member_ids)} members "
          f"to data/legislation/.")
    if failures:
        print(f"FAIL: {len(failures)} issue(s): {failures[:10]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
