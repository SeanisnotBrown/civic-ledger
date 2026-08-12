"""`curate` console entrypoint.

INC-0 stub: the curation Flask app and CLI approvers land in INC-6 (absence
CLI) and INC-11 (full app). This entrypoint exists so the console script is
valid and importable now.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "absences":
        from curation import absences

        sub = args[1] if len(args) > 1 else "search"
        if sub == "search":
            return absences.search(args[2:])
        if sub == "approve":
            return absences.approve(args[2:])
        print(f"curate absences: unknown subcommand {sub!r} (use search | approve)")
        return 2
    print("civic-ledger curate — available subcommands:")
    print("  absences search    INC-6 CREC personal-explanation search -> review queue")
    print("  absences approve    INC-6 owner approval -> verbatim Absence.stated_reason")
    print("  (full Flask curation app lands in INC-11)")
    if args:
        print(f"unknown args: {args}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
