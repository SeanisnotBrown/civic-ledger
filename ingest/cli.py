"""`ingest` console entrypoint.

INC-0 stub: the ingest pipeline lands in INC-1+ (source spike) and INC-2+
(canonical members onward). This entrypoint exists so the console script is
valid and importable now; it exits 0 with a status message.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    print("civic-ledger ingest: no ingest source is implemented yet (INC-0).")
    print("First real ingest lands in INC-1 (source feasibility spike).")
    if args:
        print(f"ignored args: {args}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
