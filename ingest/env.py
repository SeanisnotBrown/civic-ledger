"""Minimal `.env` reader — no third-party dependency (keeps the lockfile clean).

Decision (INC-1 ADR): python-dotenv is not added; a ~10-line hand-rolled reader
loads `.env` into a dict. Values are read on demand; secrets are never logged and
never placed into URLs or cache keys (see cache.py header-auth design).

Precedence: a real process environment variable wins over the `.env` file, so CI
(which injects secrets as env vars, no file) and local dev (a `.env` file) both work.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def _dotenv_values() -> dict[str, str]:
    """Parse `.env` at the repo root. Missing file → empty dict (CI has no file)."""
    values: dict[str, str] = {}
    path = _repo_root() / ".env"
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            values[key] = val
    return values


def get(name: str, default: str | None = None) -> str | None:
    """Return a credential/config value. Process env overrides the `.env` file."""
    if name in os.environ and os.environ[name] != "":
        return os.environ[name]
    val = _dotenv_values().get(name)
    if val:
        return val
    return default


def require(name: str) -> str:
    """Return a value that must be present and non-empty, else raise."""
    val = get(name)
    if not val:
        raise RuntimeError(
            f"required credential {name!r} is missing or empty "
            f"(set it in .env or as an environment variable; see .env.example)"
        )
    return val
