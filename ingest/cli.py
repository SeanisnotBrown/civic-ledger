"""`ingest` console entrypoint.

Subcommands land per increment. INC-1 adds `spike` (source feasibility); INC-2
adds `members` (congress-legislators → canonical `Member` records → deterministic
data/members/*.json). The canonical votes pipeline (INC-3+) attaches here as it
comes online.
"""

from __future__ import annotations

import sys


def _members() -> int:
    """Fetch congress-legislators (current + historical, merged so a member who
    left office between the 118th and 119th is still covered — D60), filter to
    the covered voting-state delegation of both chambers, export."""
    import yaml

    from ingest import config
    from ingest.export import export_members
    from ingest.sources import legislators

    current_raw = yaml.safe_load(legislators.current().text)
    historical_raw = yaml.safe_load(legislators.historical().text)
    raw = legislators.merge_raw(current_raw, historical_raw)
    members = legislators.covered_members(raw, config.CONGRESSES)

    by_chamber = {"house": 0, "senate": 0}
    for m in members:
        by_chamber[m.chamber] += 1
    # Sanity bounds (D61): 435 voting House seats + 6 non-voting delegates / 100
    # Senate seats, with headroom for mid-congress churn (resignations, deaths,
    # special elections) across two congresses — a filter bug should never pass
    # silently as a plausible count.
    if not (435 <= by_chamber["house"] <= 545):
        raise ValueError(
            f"house member count {by_chamber['house']} outside sane bounds [435, 545]"
        )
    if not (95 <= by_chamber["senate"] <= 130):
        raise ValueError(
            f"senate member count {by_chamber['senate']} outside sane bounds [95, 130]"
        )

    paths = export_members(members)
    print(f"civic-ledger ingest members: exported {len(paths)} members to data/members/")
    print(f"  house={by_chamber['house']} senate={by_chamber['senate']} total={len(paths)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "spike":
        from ingest import spike

        return spike.run()
    if args and args[0] == "members":
        return _members()
    if args and args[0] == "house-votes":
        from ingest import house_votes

        return house_votes.run(args[1:])
    if args and args[0] == "senate-votes":
        from ingest import senate_votes

        return senate_votes.run(args[1:])
    if args and args[0] == "bills":
        from ingest import bills

        return bills.run(args[1:])
    if args and args[0] == "classify":
        from ingest import classify

        return classify.run(args[1:])
    if args and args[0] == "legislation":
        from ingest import legislation

        return legislation.run(args[1:])
    if args and args[0] == "metrics":
        from ingest import metrics

        return metrics.run(args[1:])
    if args and args[0] == "rankings":
        from ingest import rankings

        return rankings.run(args[1:])
    if args and args[0] == "ms":
        from ingest import ms_legislature

        return ms_legislature.run(args[1:])
    print("civic-ledger ingest — available subcommands:")
    print("  spike         INC-1 source feasibility spike (needs CONGRESS_API_KEY)")
    print("  members       INC-2 canonical members -> data/members/*.json")
    print("  house-votes   INC-3 House roll calls -> data/votes/ + data/absences/")
    print("  senate-votes  INC-4 Senate roll calls -> data/votes/ + data/absences/")
    print("  bills         INC-8 bills -> data/bills/ (--all: subjects/cosponsors backfill)")
    print("  classify      INC-5 vote_class classifier (run AFTER an ingest)")
    print("  legislation   INC-10 member sponsored/cosponsored -> data/legislation/")
    print("  metrics       INC-10 Tier-2 metrics -> data/metrics.json (after ingest+legislation)")
    print("                  metrics history <bioguide> [--metric <key>] — git series (R-3)")
    print("  rankings      V2-2 per-metric rank/percentile/mean -> data/rankings/ (after metrics)")
    print("  ms            INC-12 Mississippi state legislature (LegiScan) -> data/state/ms/")
    if args:
        print(f"unknown args: {args}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
