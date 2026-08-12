"""§6.4 — Banned-strings check (CI, blocking).

Case-insensitive scan of published data fields and site source/build for
partisan-lean framing. The list lives here as data; extend only by PR (§A3),
so extensions are themselves diffable.

Scope is EXACTLY the three trees named in §6.4:
    data/**            (published dataset)
    site/src/**        (site source)
    site/dist/**       (built output)
The repo root is deliberately out of scope — IMPLEMENTATION.md quotes every
banned word while specifying this check.

The glossary page is the single allowlisted file, for defining procedural
terms; it is manually reviewed (§6.4). A hit anywhere else fails the build.
"""

from __future__ import annotations

from pathlib import Path

# Brief 5.4 verbatim plus the obvious adjacents (§6.4).
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
EXCLUDE_PREFIXES: tuple[str, ...] = ("data/quality/samples/", "data/raw/")


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
            low = line.lower()
            for term in BANNED:
                if term in low:
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
