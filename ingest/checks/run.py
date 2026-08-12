"""`checks` console entrypoint — runs the blocking CI suite (§6, §8).

Exits nonzero if any check fails. At INC-0 the active checks are the two
structural/global guards that apply with or without data:
    banned_words (§6.4)   no_llm (§6.6)

The data-dependent checks — symmetry (§6.5), archive_links (§6.11 write-time
+ weekly), integrity (§6.3) — are registered here as they come online in
their increments (INC-3/7/10/11). On an empty dataset they are no-ops, so
they are safe to add early; they are wired in as each increment implements
its real logic.
"""

from __future__ import annotations

from collections.abc import Callable

from ingest.checks import banned_words, classification, integrity, ms, no_llm, symmetry

# (name, callable-returning-exit-code). Ordered; all run even if one fails so
# the operator sees every problem in a single pass. symmetry + integrity are
# no-ops until their data exists (INC-3 activates House vote coverage + the clerk
# cross-check); they stay green on an empty dataset.
CHECKS: list[tuple[str, Callable[[], int]]] = [
    ("banned_words", banned_words.main),
    ("no_llm", no_llm.main),
    ("symmetry", symmetry.main),
    ("classification", classification.main),
    ("integrity", integrity.main),
    ("ms", ms.main),
]


def main() -> int:
    failed: list[str] = []
    for name, fn in CHECKS:
        print(f"== check: {name} ==")
        rc = fn()
        if rc != 0:
            failed.append(name)
        print()
    if failed:
        print(f"CHECKS FAILED: {', '.join(failed)}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
