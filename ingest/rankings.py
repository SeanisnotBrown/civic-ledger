"""V2-2 — rankings & percentile layer (pure math; no thresholds, no labels).

For each rankable Tier-2 metric, compute — within each chamber (House and Senate
separately) — every member's rank, percentile, and the chamber/party means. This
layer reads ONLY the committed data/metrics.json (plus data/members for chamber
and party), so a third party recomputes every ranking from the public repo (the
verify-recompute contract) exactly as they can recompute the metrics themselves.

Discipline (mirrors ingest/metrics.py):
  * PURE + OFFLINE — reads the committed dataset only, never the API and never
    another ranking's output. A rank is the ordinal position of a single metric's
    value; nothing here composes two metrics (Tier-3 is V2-4's scoring.py).
  * NO EVALUATIVE OUTPUT — rank is direction-neutral (by value, descending); this
    module writes no "best"/"worst"/grade wording. That framing, and any threshold,
    is V2-4 under §0.8. The methods copy here states only what is measured.

Two mechanical choices (builder ADRs, non-evaluative):
  * Ties: standard competition ranking (§5 pre-decided) — tied members share a
    rank and the next rank skips (values 100,90,90,80 → ranks 1,2,2,4).
  * Percentile: the share of the chamber's ranked set with a STRICTLY LOWER value,
    as a percentage (so a unique chamber leader of N sits at (N-1)/N). Defined in
    the rendered methods text so the denominator is visible (§0.4.2(d)).

Membership choices (documented, non-evaluative):
  * Chamber + party come from the member's CURRENT record (`Member.chamber`,
    `Member.party`); a chamber-switcher is ranked in the chamber they now sit in.
    (The metrics themselves use the per-roll party; rankings group by current
    party — stated on the methods page.)
  * A member with no value for a metric (attendance pct null before their first
    vote; enacted_rate null when they sponsored nothing) is not ranked on it —
    never ranked at a fabricated 0.

D66 (owner-ratified 2026-08-13): the non-voting House delegates are
constitutionally barred from final-passage rolls, so their attendance and
party-unity denominators are not comparable to a full member's — they are
excluded from those two rankings and listed in `excluded_delegates`. They
sponsor and cosponsor bills fully, so the three legislation rankings include
them. The exclusion is never silent: it is published on /methods.
"""

from __future__ import annotations

import json
import statistics

from ingest.cache import repo_root
from ingest.models import ChamberRanking, RankingEntry, RankingsFile
from ingest.sources.legislators import VOTING_STATES

# Rankable Tier-2 metrics → the scalar field of each that carries the value. The
# other three metrics (cosponsor_vote_gap, named_measure_mismatch, absence_context)
# are lists of records, not a single comparable number, and are not ranked.
RANKED_METRICS: dict[str, str] = {
    "attendance": "pct",
    "party_unity": "pct",
    "sponsored": "count",
    "cosponsored": "count",
    "enacted_rate": "pct",
}

# The two vote-based metrics delegates are excluded from (D66). The three
# legislation metrics (the rest of RANKED_METRICS) include delegates.
VOTE_METRICS: frozenset[str] = frozenset({"attendance", "party_unity"})

CHAMBERS: tuple[str, ...] = ("house", "senate")

# Rendered verbatim on /methods (the ranking family's methodology, the analogue of
# each metric function's docstring). Plain, non-evaluative, denominator visible.
RANKING_METHODOLOGY: str = (
    "Members are ranked within their own chamber — the House and the Senate are "
    "ranked separately, because their vote counts and calendars differ. For each "
    "metric a member's rank is their position when members are ordered by that "
    "metric's value, highest first, using standard competition ranking: members "
    "with the same value share a rank, and the next rank skips accordingly. A "
    "member's percentile is the percentage of the ranked members in their chamber "
    "whose value is lower than theirs, so the count behind every percentile is "
    "visible. The chamber mean and median, and the mean for each party (grouped by "
    "the member's current party), are published alongside. A rank is a position in "
    "an ordering, not a judgment; this layer attaches no label to it. Members "
    "with no value for a metric (for example, no enacted rate when they sponsored "
    "no bills) are not ranked on that metric. Non-voting House delegates are ranked "
    "only on bills sponsored, bills cosponsored, and enacted rate; they are left "
    "out of the attendance and party-unity rankings because they cannot vote on "
    "final passage, so those figures are measured over a different, smaller set of "
    "votes and are not comparable to a voting member's."
)


def _load_inputs() -> tuple[dict, dict]:
    """(metrics.members, members-by-bioguide) from the committed dataset."""
    root = repo_root()
    metrics = json.loads(
        (root / "data" / "metrics.json").read_text(encoding="utf-8")
    )["members"]
    members: dict[str, dict] = {}
    for path in sorted((root / "data" / "members").glob("*.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        members[m["id"]] = m
    return metrics, members


def _rank_and_percentile(pairs: list[tuple[str, float]]) -> dict[str, tuple[int, float]]:
    """[(bioguide, value)] -> {bioguide: (competition_rank, percentile)}.

    Competition rank = 1 + (# of members with a strictly greater value). Percentile
    = 100 * (# with a strictly lower value) / N. Pure; no ordering assumption on the
    input (each member is scored against the whole set)."""
    values = [v for _, v in pairs]
    n = len(values)
    out: dict[str, tuple[int, float]] = {}
    for bid, v in pairs:
        greater = sum(1 for x in values if x > v)
        lower = sum(1 for x in values if x < v)
        out[bid] = (greater + 1, round(100 * lower / n, 1))
    return out


def build_metric(
    metric: str, value_field: str, metrics: dict, members: dict, label: str
) -> RankingsFile:
    """Rank one metric across both chambers from the loaded metrics + members."""
    ranks_delegates = metric not in VOTE_METRICS
    chambers: dict[str, ChamberRanking] = {}
    for chamber in CHAMBERS:
        pairs: list[tuple[str, float]] = []
        excluded: list[str] = []
        for bid, m in members.items():
            if m.get("chamber") != chamber:
                continue
            value = (metrics.get(bid, {}).get(metric) or {}).get(value_field)
            is_delegate = m.get("state") not in VOTING_STATES
            if not ranks_delegates and is_delegate:
                if value is not None:
                    excluded.append(bid)  # a real, comparable-elsewhere member, held out
                continue
            if value is None:
                continue  # no value for this metric — never ranked at a fabricated 0
            pairs.append((bid, value))

        rp = _rank_and_percentile(pairs) if pairs else {}
        values = [v for _, v in pairs]
        party_values: dict[str, list[float]] = {}
        for bid, v in pairs:
            party_values.setdefault(members[bid]["party"], []).append(v)

        chambers[chamber] = ChamberRanking(
            covered=len(pairs),
            mean=round(statistics.fmean(values), 2) if values else None,
            median=round(statistics.median(values), 2) if values else None,
            party_means={
                p: round(statistics.fmean(vs), 2) for p, vs in sorted(party_values.items())
            },
            excluded_delegates=sorted(excluded),
            members={
                bid: RankingEntry(value=v, rank=rp[bid][0], percentile=rp[bid][1])
                for bid, v in pairs
            },
        )

    return RankingsFile(
        metric=metric,
        value_field=value_field,
        label=label,
        methodology=RANKING_METHODOLOGY,
        ranks_delegates=ranks_delegates,
        chambers=chambers,
    )


def build_all(metrics: dict | None = None, members: dict | None = None) -> dict[str, RankingsFile]:
    """Every ranked metric → its RankingsFile. Loads the committed dataset unless
    `metrics`/`members` are supplied (tests inject fixtures)."""
    if metrics is None or members is None:
        metrics, members = _load_inputs()
    from ingest.metrics import METRIC_LABELS

    return {
        metric: build_metric(metric, vf, metrics, members, METRIC_LABELS[metric])
        for metric, vf in RANKED_METRICS.items()
    }


def run(argv: list[str] | None = None) -> int:
    """Write data/rankings/{metric}.json for every ranked metric (pure/offline)."""
    from ingest.export import export_rankings

    paths = export_rankings(build_all())
    print(
        f"civic-ledger rankings: wrote {len(paths)} ranking file(s) to "
        f"data/rankings/ ({', '.join(sorted(RANKED_METRICS))})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
