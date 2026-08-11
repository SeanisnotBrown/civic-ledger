"""`export` console entrypoint — SQLite → deterministic JSON (§6.3).

INC-0 stub: real export contracts land in INC-7. Determinism guarantees
(sorted keys, sorted lists, LF endings, 2-space indent) will be implemented
and verified by checks/integrity.py double-export.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    _ = sys.argv[1:] if argv is None else argv
    print("civic-ledger export: nothing to export yet (INC-0).")
    print("Deterministic JSON export contracts land in INC-7.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
