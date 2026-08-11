"""`ingest` console entrypoint.

Subcommands land per increment. INC-1 adds `spike` (source feasibility). The
canonical members/votes pipeline (INC-2+) attaches here as it comes online.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "spike":
        from ingest import spike

        return spike.run()
    print("civic-ledger ingest — available subcommands:")
    print("  spike   INC-1 source feasibility spike (needs CONGRESS_API_KEY)")
    if args:
        print(f"unknown args: {args}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
