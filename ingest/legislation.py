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

from ingest.models import LegItem, MemberLegislation
from ingest.sources.legislators import _term_overlaps


def _sponsored_gaps(
    mid: str, terms: list[dict], sponsored: list[LegItem], congresses: list[int]
) -> list[str]:
    """Sanity gaps (value #1): a member must have >= 1 sponsored bill in each covered
    congress THEY SERVED (from `terms`). A served-congress zero is a truncated fetch;
    a congress they didn't serve is legitimately empty and never checked (R-2 — a
    member who joined after the 118th has no 118th bills, and must not false-fail).
    Pure, so the churn relaxation is unit-testable without the fetch/export path."""
    served = [c for c in congresses if any(_term_overlaps(t, c) for t in terms)]
    return [
        f"{mid}: no sponsored bill in congress {c} (truncated fetch?)"
        for c in served
        if not any(li.congress == c for li in sponsored)
    ]

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
    Idempotent (cached fetches). Fails if a member has no sponsored bill in a
    covered congress THEY SERVED — an empty list for a served congress signals a
    broken fetch, not reality (value #1: never publish a false zero). A congress a
    member did not serve is legitimately empty and never checked (R-2: a member who
    joined after the 118th has no 118th bills — don't false-fail on churn)."""
    import httpx

    from ingest import config
    from ingest.cache import RetryableHTTPError, repo_root
    from ingest.export import export_member_legislation
    from ingest.sources import congress_gov

    fetch_errors = (RetryableHTTPError, httpx.HTTPError, OSError)
    members_dir = repo_root() / "data" / "members"
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

        # Sanity (value #1), churn-aware: served congresses only (see _sponsored_gaps).
        failures.extend(_sponsored_gaps(mid, members[mid]["terms"], sponsored, config.CONGRESSES))

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
