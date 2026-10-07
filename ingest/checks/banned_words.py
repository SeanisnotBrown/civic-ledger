"""Banned-strings check (CI, blocking).

Case-insensitive scan of published data fields and site source/build for
partisan-lean framing. This is the mechanical edge of `IMPLEMENTATIONv3.md`
§1 rule 6: the site states facts, never motive. The list lives here as data;
extend only by PR, so extensions are themselves diffable.

Scope is EXACTLY these three trees:
    data/**            (published dataset)
    site/src/**        (site source)
    site/dist/**       (built output)
The repo root is deliberately out of scope — `IMPLEMENTATIONv3.md` and
`MISSION.md` quote banned words while specifying and explaining this check.

The glossary page is the single allowlisted file, for defining procedural
terms; it is manually reviewed. A hit anywhere else fails the build.
"""

from __future__ import annotations

import re
from pathlib import Path

# Motive-or-character framing. Rule 6 (`IMPLEMENTATIONv3.md` §1).
BANNED: tuple[str, ...] = (
    "hypocrisy",
    "hypocrite",
    "broke his promise",
    "broke her promise",
    "broke their promise",
    "flip-flop",
    "flip flop",
    "flipflop",
    "contradiction",
    "contradicts",
    "liar",
    "lied about",
)

# Directories scanned, relative to repo root.
SCAN_DIRS: tuple[str, ...] = ("data", "site/src", "site/dist")

# Extensions that hold human-readable published text. Binary/asset files skipped.
TEXT_SUFFIXES: frozenset[str] = frozenset(
    {
        ".json",
        ".yaml",
        ".yml",
        ".md",
        ".astro",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".html",
        ".css",
        ".txt",
    }
)

# The one allowlisted file (§6.4): the glossary defines procedural terms and is
# manually reviewed. Path is relative to repo root; created in INC-20.
ALLOWLIST: frozenset[str] = frozenset(
    {
        "site/src/content/glossary.md",
    }
)

# Excluded subtrees (ADR 2026-08-11): raw upstream source captures are verbatim
# government responses NOT authored or framed by the platform. §6.4 guards
# partisan-lean framing in our rendered content; nothing under these prefixes is
# ever rendered on the site.
#   * data/quality/samples/ — committed spike captures (audit/reproducibility, §6.2).
#   * data/raw/ — the gitignored raw fetch cache (§6.2); not a published field at
#     all. A large base64 dataset blob (e.g. LegiScan getDataset) will coincidentally
#     contain banned substrings like "liar" in its base64 alphabet — scanning it is a
#     scope error, since §6.4 targets *published* fields only.
#   * data/quality/absence-queue/ — UNAPPROVED verbatim CREC candidates (INC-6, D25).
#     This is a pre-publication review artifact, not published data; a member's own
#     verbatim words there must not fail CI before the owner has even seen them.
#     Once approved, the text lands in data/absences/ and IS scanned.
EXCLUDE_PREFIXES: tuple[str, ...] = (
    "data/quality/samples/", "data/quality/absence-queue/", "data/raw/",
)


# Match each banned term as a WHOLE WORD/PHRASE, not a substring — otherwise a real
# published title like "Junior Auxiliary of ..." trips "liar" (aux-i-LIAR-y), and
# "familiar"/"peculiar"/"conciliar" would too. §6.4 targets partisan FRAMING words we
# authored, which are always whole words; word boundaries keep that intent exact.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE), term) for term in BANNED
)


def repo_root() -> Path:
    # ingest/checks/banned_words.py -> repo root is two parents up from ingest/.
    return Path(__file__).resolve().parents[2]


def _iter_text_files(root: Path):
    for rel in SCAN_DIRS:
        base = root / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            relposix = path.relative_to(root).as_posix()
            if relposix in ALLOWLIST:
                continue
            if relposix.startswith(EXCLUDE_PREFIXES):
                continue
            yield path, relposix


def find_hits(root: Path | None = None) -> list[tuple[str, int, str]]:
    """Return (relpath, 1-based line, banned-term) for every violation."""
    root = root or repo_root()
    hits: list[tuple[str, int, str]] = []
    for path, relposix in _iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern, term in _PATTERNS:
                if pattern.search(line):
                    hits.append((relposix, lineno, term))
    return hits


def main() -> int:
    hits = find_hits()
    if hits:
        print("BANNED-WORDS CHECK FAILED — partisan-lean framing found:")
        for relpath, lineno, term in hits:
            print(f"  {relpath}:{lineno}  ->  {term!r}")
        return 1
    print("banned-words: OK (no partisan-lean framing in scanned trees)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
