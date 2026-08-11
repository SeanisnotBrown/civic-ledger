"""§6.6 — No-LLM structural guard (CI, blocking).

Makes "no LLM in the publishing path" mechanically true (brief 5.10):
  (a) dependency lockfiles contain no LLM SDK packages;
  (b) no source file under ingest/ site/ worker/ contains an LLM API endpoint;
  (c) CONTRIBUTING.md states the policy.

Self-reference note: this module must scan the very tree it lives in without
matching itself. Two defenses are used together — the endpoint fragments are
assembled from concatenated parts (so the literal strings never appear in this
file), and this file is excluded from the scan explicitly.
"""

from __future__ import annotations

import re
from pathlib import Path

# --- (a) forbidden dependency package names -------------------------------
# langchain* and llama-index* are prefix families.
FORBIDDEN_PACKAGES: tuple[str, ...] = (
    "anthropic",
    "openai",
    "google-genai",
    "google-generativeai",
    "generativeai",
    "mistralai",
    "cohere",
    "ollama",
    "litellm",
    "langchain",
    "llama-index",
    "llama_index",
)

LOCKFILES: tuple[str, ...] = ("uv.lock", "site/package-lock.json")

# --- (b) forbidden endpoint fragments, assembled to avoid self-match ------
_ANTHROPIC = "api." + "anthropic" + ".com"
_OPENAI = "api." + "openai" + ".com"
_GEMINI = "generativelanguage." + "googleapis"
_OLLAMA = ":" + "11434"
FORBIDDEN_ENDPOINTS: tuple[str, ...] = (_ANTHROPIC, _OPENAI, _GEMINI, _OLLAMA)

SCAN_DIRS: tuple[str, ...] = ("ingest", "site/src", "worker")
CODE_SUFFIXES: frozenset[str] = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".astro", ".mjs", ".cjs", ".json", ".toml"}
)

_SELF = Path(__file__).resolve()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _package_pattern(name: str) -> re.Pattern[str]:
    # Match the package name as a delimited token (allow it to be a prefix
    # family, e.g. langchain-core, llama-index-core), not a random substring.
    esc = re.escape(name)
    return re.compile(rf"(?<![a-z0-9])({esc})(?![a-z0-9])", re.IGNORECASE)


def check_lockfiles(root: Path) -> list[str]:
    problems: list[str] = []
    patterns = {p: _package_pattern(p) for p in FORBIDDEN_PACKAGES}
    for rel in LOCKFILES:
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pat in patterns.items():
            if pat.search(text):
                problems.append(f"lockfile {rel} references forbidden LLM package {name!r}")
    return problems


def check_endpoints(root: Path) -> list[str]:
    problems: list[str] = []
    for rel in SCAN_DIRS:
        base = root / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in CODE_SUFFIXES:
                continue
            if path.resolve() == _SELF:
                continue  # never scan this guard's own source
            text = path.read_text(encoding="utf-8", errors="replace")
            for frag in FORBIDDEN_ENDPOINTS:
                if frag in text:
                    relposix = path.relative_to(root).as_posix()
                    problems.append(f"{relposix} contains forbidden LLM endpoint {frag!r}")
    return problems


def check_contributing(root: Path) -> list[str]:
    path = root / "CONTRIBUTING.md"
    if not path.exists():
        return ["CONTRIBUTING.md missing — must state the no-LLM policy (§6.6c)"]
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    if "no llm" not in text and "no-llm" not in text:
        return ["CONTRIBUTING.md does not state the no-LLM policy (§6.6c)"]
    return []


def find_problems(root: Path | None = None) -> list[str]:
    root = root or repo_root()
    return check_lockfiles(root) + check_endpoints(root) + check_contributing(root)


def main() -> int:
    problems = find_problems()
    if problems:
        print("NO-LLM CHECK FAILED:")
        for p in problems:
            print(f"  {p}")
        return 1
    print("no-llm: OK (no LLM SDKs, no LLM endpoints, policy documented)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
