"""INC-13 — Mississippi Tier-2 metrics (data/state/ms/metrics.json).

Deliberately REUSES the federal metric FORMULAS (ingest/metrics.py) — attendance,
party_unity, sponsored, cosponsored, enacted_rate compute identically over an MS-loaded
`Ctx`, so the numbers carry the same meaning and the same audited digest. Only the source
data (the committed MS partition) and the methodology TEXT are MS-specific; the list-type
federal metrics (cosponsor_vote_gap, named_measure_mismatch, absence_context) are not
computed for MS in this pass.

Pure + offline: reads only the committed data/state/ms/{members,votes,legislation}, so a
third party recomputes every figure from the public repo (the MS recompute-and-match check
in checks/ms.py). No wall-clock.
"""

from __future__ import annotations

import json

from ingest import metrics as fed
from ingest.models import MetricMethodology, MsMemberMetrics, MsMetricsFile

# Bump on any semantic change to how an MS metric is computed (mirrors R-3/D45).
MS_FORMULA_SCHEMA_VERSION: int = 1

MS_METRIC_KEYS: tuple[str, ...] = (
    "attendance", "party_unity", "sponsored", "cosponsored", "enacted_rate",
)

# MS-specific methodology text (the federal docstrings say "covered Congresses" — wrong
# for a state session). Formula IS the reused federal function; text describes it for MS.
MS_METHODOLOGY_TEXT: dict[str, str] = {
    "attendance": (
        "Share of the session's roll-call votes on which the member recorded a position. "
        "cast (Yea/Nay/Present) divided by eligible roll calls of their chamber, as a "
        "percentage. Source: data/state/ms/votes."
    ),
    "party_unity": (
        "Share of substantive votes (final passage and veto overrides; procedural motions "
        "excluded) on which the member voted with the majority of their own party. Rolls "
        "where the member did not cast Yea/Nay, or where their party split evenly, are "
        "excluded. Source: data/state/ms/votes (positions + aggregate party_totals)."
    ),
    "sponsored": (
        "Count of bills on which the member is the principal (first-listed) author this "
        "session. LegiScan does not distinguish primary from co-authors for Mississippi, so "
        "the first-listed author is taken as the principal. Source: data/state/ms/legislation."
    ),
    "cosponsored": (
        "Count of bills on which the member is an additional (non-first-listed) author this "
        "session. Source: data/state/ms/legislation."
    ),
    "enacted_rate": (
        "Of the bills the member principally authored, the share approved by the Governor "
        "this session (official history action \"Approved by Governor\"). Source: "
        "data/state/ms/legislation."
    ),
}


def _load_ctx() -> fed.Ctx:
    """Build the federal `Ctx` from the committed MS partition so the reused federal
    metric functions can run over MS data."""
    from ingest.export import MS_LEGISLATION_DIR, MS_MEMBERS_DIR, MS_VOTES_DIR

    members = {
        (m := json.loads(p.read_text(encoding="utf-8")))["id"]: m
        for p in sorted(MS_MEMBERS_DIR.glob("*.json"))
    }
    positions: dict[str, list[tuple[dict, str]]] = {mid: [] for mid in members}
    for p in sorted(MS_VOTES_DIR.glob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        rc = rec["rollcall"]
        for mv in rec["member_votes"]:
            if mv["member_id"] in positions:
                positions[mv["member_id"]].append((rc, mv["position"]))
    legislation = {
        (r := json.loads(p.read_text(encoding="utf-8")))["member_id"]: r
        for p in sorted(MS_LEGISLATION_DIR.glob("*.json"))
    }
    missing = set(members) - set(legislation)
    if missing:
        raise FileNotFoundError(f"no MS legislation record for {sorted(missing)}")
    # ended_congresses / voted_bill_ids / statements are only used by the list-type
    # metrics we do not compute for MS — safe to leave empty.
    return fed.Ctx(members, positions, legislation, statements=[],
                   voted_bill_ids=set(), ended_congresses=frozenset())


def build() -> MsMetricsFile:
    """Compute the MS metric subset for every MS member from the committed partition."""
    ctx = _load_ctx()
    members = {
        mid: MsMemberMetrics(
            attendance=fed.attendance(mid, ctx),
            party_unity=fed.party_unity(mid, ctx),
            sponsored=fed.sponsored(mid, ctx),
            cosponsored=fed.cosponsored(mid, ctx),
            enacted_rate=fed.enacted_rate(mid, ctx),
        )
        for mid in sorted(ctx.members)
    }
    methodology = {
        key: MetricMethodology(
            label=fed.METRIC_LABELS[key],
            text=MS_METHODOLOGY_TEXT[key],
            digest=fed._formula_digest(fed.METRICS[key]),  # same formula → same digest
        )
        for key in MS_METRIC_KEYS
    }
    return MsMetricsFile(
        schema_version=MS_FORMULA_SCHEMA_VERSION, methodology=methodology, members=members
    )


def export() -> object:
    from ingest.export import MS_METRICS_PATH, _dumps

    MS_METRICS_PATH.write_text(_dumps(build().model_dump()), encoding="utf-8", newline="\n")
    return MS_METRICS_PATH


def main(argv: list[str] | None = None) -> int:
    path = export()
    print(f"ms-metrics: wrote {path.name} ({len(MS_METRIC_KEYS)} metrics x MS members).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
