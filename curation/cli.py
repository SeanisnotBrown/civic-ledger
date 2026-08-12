"""`curate` console entrypoint (INC-6 absence CLI + INC-11 statement ledger + app)."""

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
    if args and args[0] == "statements":
        from curation import statements

        sub = args[1] if len(args) > 1 else "repair"
        if sub == "repair":
            return statements.repair(args[2:])
        print(f"curate statements: unknown subcommand {sub!r} (use repair; curate via `app`)")
        return 2
    if args and args[0] == "app":
        from curation import app

        return app.run(args[1:])
    print("civic-ledger curate — available subcommands:")
    print("  app                 INC-11 local Flask curation app (statements + absences)")
    print("  absences search     INC-6 CREC personal-explanation search -> review queue")
    print("  absences approve    INC-6 owner approval -> verbatim Absence.stated_reason")
    print("  statements repair   INC-11 re-resolve pairings after editing the allowlist")
    if args:
        print(f"unknown args: {args}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
