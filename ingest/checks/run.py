"""`checks` console entrypoint — runs the blocking CI suite.

Exits nonzero if any check fails. The ground rules these enforce are in
`IMPLEMENTATIONv3.md` §1; the CI checks kept at the 2026-10-07 reset are
listed in §2 ("CI checks kept").

Active checks:
    banned_words   the mechanical edge of rule 6 (facts, never motive)
    symmetry       equal treatment across parties
    classification roll-call classification coverage
    integrity      cross-source agreement on the published dataset
    ms             Mississippi dataset guards (back burner, §4.10)

The data-dependent checks are no-ops on an empty dataset, so they are safe to
run at any phase.

The `no_llm` structural guard was removed on 2026-10-07: `IMPLEMENTATIONv3.md`
§1 retires the no-AI-in-the-publishing-path rule (AI summaries and statement
categorization are now labeled and human-approved instead, §4.6 / rule 7).
Do not reinstate it.
"""

from __future__ import annotations

from collections.abc import Callable

from ingest.checks import banned_words, classification, integrity, ms, symmetry

# (name, callable-returning-exit-code). Ordered; all run even if one fails so
# the operator sees every problem in a single pass.
CHECKS: list[tuple[str, Callable[[], int]]] = [
    ("banned_words", banned_words.main),
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
