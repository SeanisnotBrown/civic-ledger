"""`curate` console entrypoint.

INC-0 stub: the curation Flask app and CLI approvers land in INC-6 (absence
CLI) and INC-11 (full app). This entrypoint exists so the console script is
valid and importable now.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    print("civic-ledger curate: curation tools are not implemented yet (INC-0).")
    print("Absence CLI approver lands in INC-6; full Flask app in INC-11.")
    if args:
        print(f"requested subcommand: {' '.join(args)} (not available yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
