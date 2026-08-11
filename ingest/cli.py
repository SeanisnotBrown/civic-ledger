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
    print("civic-ledger ingest — available subcommands:")
    print("  spike     INC-1 source feasibility spike (needs CONGRESS_API_KEY)")
    print("  members   INC-2 canonical members → data/members/*.json")
    if args:
        print(f"unknown args: {args}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
