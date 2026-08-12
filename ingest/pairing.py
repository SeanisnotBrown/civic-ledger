"""INC-11 — Statement↔vote pairing key resolution (D9).

The bright line (brief §10, D9): a statement is paired to a measure by BILL ID and
nothing else — never by fuzzy text match. The one sanctioned exception is a formal
short title, and only when the owner has explicitly mapped that title to a bill id
in `data/statements/_title_allowlist.yaml`. That makes "no fuzzy matching"
mechanically true: resolution is a parse plus an exact dictionary lookup.

This module is the SINGLE place that resolution happens (D41). Curation calls
`resolve()` at save time and stores the result on the Statement (`paired_bill_ids`);
the metric layer and the site both READ that field and never re-resolve, so the
rule cannot drift between Python and TypeScript.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ingest.bills import parse_bill_id
from ingest.cache import repo_root

ALLOWLIST_PATH = repo_root() / "data" / "statements" / "_title_allowlist.yaml"


def _is_bill_id(measure: str) -> bool:
    """True iff `measure` already parses as a canonical bill id (hr2-119 form).
    Reuses the ingest parser so the accepted form never drifts from data/bills/."""
    try:
        parse_bill_id(measure.strip().lower())
        return True
    except Exception:
        return False


def load_allowlist(path: Path = ALLOWLIST_PATH) -> dict[str, str]:
    """The owner-curated short-title → bill-id map. Keys are compared
    case-insensitively (normalized to casefold). Missing file ⇒ empty map (the
    launch state — no titles are allowlisted until the owner adds them). Each
    mapped value MUST itself be a valid bill id, or the file is malformed and we
    fail loudly rather than silently drop a pairing."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name}: expected a title→bill-id mapping, got {type(raw).__name__}")
    out: dict[str, str] = {}
    for title, bill_id in raw.items():
        if not _is_bill_id(str(bill_id)):
            raise ValueError(
                f"{path.name}: title {title!r} maps to {bill_id!r}, which is not a bill id"
            )
        out[str(title).strip().casefold()] = str(bill_id).strip().lower()
    return out


def resolve(named_measures: list[str], allowlist: dict[str, str]) -> list[str]:
    """Resolve a statement's named measures to canonical bill ids by the D9 rule,
    in order per measure:

      1. the measure already IS a bill id (hr2-119 form) → itself, lowercased;
      2. else an EXACT (case-folded) key in the short-title allowlist → its bill id;
      3. else UNPAIRED — dropped (no fuzzy matching, ever).

    Returns the sorted, de-duplicated resolved bill ids. Pure — the allowlist is
    passed in, never read here, so the function is trivially testable and the same
    resolution is reproducible from the committed repo."""
    resolved: set[str] = set()
    for measure in named_measures:
        m = measure.strip()
        if _is_bill_id(m):
            resolved.add(m.lower())
        elif m.casefold() in allowlist:
            resolved.add(allowlist[m.casefold()])
    return sorted(resolved)
