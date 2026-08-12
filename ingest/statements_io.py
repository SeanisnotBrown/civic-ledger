"""Single source of truth for loading curated statement records (R-1b/M-3).

Statement loading used to be re-implemented four times with drifting semantics
(metrics, symmetry, archive_links, export) — so a statement the site refused to
publish still generated published metrics. This unifies the read so "what counts as
a statement, and is it publishable" is decided in exactly one place.

Two axes every caller is explicit about:

  * `_`-prefixed files (e.g. `_title_allowlist.yaml`) are CONFIG, never records —
    always skipped. They don't match `*.json` today, but a future `_*.json` would,
    and two of the old loaders would have miscounted it.
  * dead-archive statements: a statement whose permanent capture no longer resolves
    is flagged UNPUBLISHABLE by the weekly archive sweep (`checks/archive_links.py`,
    written to `data/quality/archive-status.json`) and withheld from the site
    (`site/src/lib/data.ts::getStatements`). `exclude_dead=True` makes a Python
    caller honor that same withholding.

Semantics chosen per caller (the M-3 decision):

  * metrics — `exclude_dead=True`. `named_measure_mismatch` is the single most
    sensitive published artifact; an unpublishable statement must not leak a mismatch
    (carrying its `source_url`) through the metric side door while the site hides it.
  * archive_links — `exclude_dead=False`. It IS the sweep that decides dead/alive, so
    it must re-check every statement (a recaptured one can come back alive).
  * symmetry — `exclude_dead=False`. Balance is about CURATION EFFORT, not
    publication; a curated-but-dead statement still counts toward even-handedness.
  * export manifest count — every record on disk minus the config files.
"""

from __future__ import annotations

import json
from pathlib import Path

from ingest.cache import repo_root


def _data_dir(data_dir: Path | None) -> Path:
    return data_dir if data_dir is not None else repo_root() / "data"


def statement_files(data_dir: Path | None = None) -> list[Path]:
    """Every statement RECORD file (data/statements/*.json), sorted, config excluded."""
    sdir = _data_dir(data_dir) / "statements"
    if not sdir.exists():
        return []
    return [p for p in sorted(sdir.glob("*.json")) if not p.name.startswith("_")]


def dead_statement_ids(data_dir: Path | None = None) -> set[str]:
    """Statement ids the archive sweep flagged as dead-archive (unpublishable). Empty
    when the sweep has never run (a bare checkout) or the report is unreadable."""
    path = _data_dir(data_dir) / "quality" / "archive-status.json"
    if not path.exists():
        return set()
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return set(report.get("dead_statement_ids", []))


def load_statements(data_dir: Path | None = None, *, exclude_dead: bool = False) -> list[dict]:
    """Load every curated statement record as a dict. With `exclude_dead=True`, drop
    the ones the archive sweep flagged unpublishable (see module docstring)."""
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in statement_files(data_dir)]
    if exclude_dead:
        dead = dead_statement_ids(data_dir)
        recs = [r for r in recs if r.get("id") not in dead]
    return recs
