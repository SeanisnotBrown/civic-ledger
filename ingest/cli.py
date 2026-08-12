"""`ingest` console entrypoint.

Subcommands land per increment. INC-1 adds `spike` (source feasibility); INC-2
adds `members` (congress-legislators → canonical `Member` records → deterministic
data/members/*.json). The canonical votes pipeline (INC-3+) attaches here as it
comes online.
"""

from __future__ import annotations

import sys


def _members() -> int:
    """Fetch congress-legislators, filter to the covered delegation, export."""
    import yaml

    from ingest import config
    from ingest.export import export_members
    from ingest.sources import legislators

    raw = yaml.safe_load(legislators.current().text)
    members = legislators.covered_members(raw, config.CONGRESSES, config.COVERED_STATE)
    paths = export_members(members)
    print(f"civic-ledger ingest members: exported {len(paths)} members to data/members/")
    for path in paths:
        print(f"  {path.name}")
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
    print("civic-ledger ingest — available subcommands:")
    print("  spike         INC-1 source feasibility spike (needs CONGRESS_API_KEY)")
    print("  members       INC-2 canonical members -> data/members/*.json")
    print("  house-votes   INC-3 House roll calls -> data/votes/ + data/absences/")
    print("  senate-votes  INC-4 Senate roll calls -> data/votes/ + data/absences/")
    print("  bills         INC-8 vote-referenced bills -> data/bills/ (--all forces the INC-10 subjects/cosponsors backfill)")
    print("  classify      INC-5 vote_class classifier (run AFTER an ingest)")
    if args:
        print(f"unknown args: {args}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
