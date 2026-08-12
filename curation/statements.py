"""INC-11 — Statement ledger: capture → resolve pairing → save (content = H8).

Principle 5 (no builder-authored political content): this module is the tool. The
OWNER pastes a verbatim quote + its source URL into the curation app; this code
captures a permanent Wayback copy, resolves the D9 pairing, and writes the record.
Nothing here writes, paraphrases, or scores a statement's content.

The load-bearing rule (brief §5.10): NO VERIFIED CAPTURE, NO SAVE. It is enforced
server-side here, not just by a disabled button — `build_statement` requires a
`Capture` object, and the only producer of one is `SpnClient.capture`, which
HEAD-verifies the archive_url actually resolves. A raw archive_url string cannot get
in. Pairing is resolved once (ingest/pairing.py) and stored on the record.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Literal

from ingest import pairing
from ingest.cache import repo_root
from ingest.export import MEMBERS_DIR, STATEMENTS_DIR, export_statement
from ingest.models import Statement
from ingest.sources.archive_org import Capture, SpnClient


def _covered_member_ids() -> set[str]:
    if not MEMBERS_DIR.exists():
        return set()
    return {p.stem for p in MEMBERS_DIR.glob("*.json")}


def _statement_id(member_id: str, date: str, source_url: str) -> str:
    """Stable, filesystem-safe id: member + date + a short hash of the source URL.
    Deterministic (no wall-clock) so re-curating the same source is idempotent."""
    digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:8]
    return f"{member_id}-{date[:10]}-{digest}"


def resolve_pairs(named_measures: list[str]) -> list[str]:
    """The D9 pairing result for a statement, resolved against the CURRENT
    owner-curated allowlist. Single source of resolution (ingest/pairing.py)."""
    return pairing.resolve(named_measures, pairing.load_allowlist())


def build_statement(
    *,
    member_id: str,
    text: str,
    date: str,
    venue: str,
    source_url: str,
    named_measures: list[str],
    capture: Capture,
    specificity_level: Literal[0, 1, 2, 3] | None = None,
    stated_position: Literal["support", "oppose"] | None = None,
    curator_note: str | None = None,
) -> Statement:
    """Assemble a Statement from owner input + a VERIFIED capture. Refuses without a
    real `Capture` (the no-verified-capture-no-save rule, server-side) and without a
    known covered member. `paired_bill_ids` is resolved here, never by the caller."""
    if not isinstance(capture, Capture):
        raise ValueError(
            "no verified capture — a Statement cannot be built without a completed "
            "SpnClient.capture() (no verified capture, no save)"
        )
    if capture.original_url != source_url:
        raise ValueError(
            f"capture is for {capture.original_url!r}, not the statement source "
            f"{source_url!r} — refusing to attach a mismatched archive"
        )
    covered = _covered_member_ids()
    if covered and member_id not in covered:
        raise ValueError(f"{member_id!r} is not a covered member")
    return Statement(
        id=_statement_id(member_id, date, source_url),
        member_id=member_id,
        text=text,
        date=date,
        venue=venue,
        source_url=source_url,
        archive_url=capture.archive_url,
        archive_captured_at=capture.captured_at,
        named_measures=list(named_measures),
        paired_bill_ids=resolve_pairs(named_measures),
        specificity_level=specificity_level,
        stated_position=stated_position,
        curator_note=curator_note,
    )


def _git_add(path: Path) -> None:
    """Stage the written record (spec: "YAML written → git add staged"). Best-effort:
    a git failure is warned, not fatal — the file is already written."""
    try:
        subprocess.run(
            ["git", "add", str(path)], cwd=repo_root(), capture_output=True, check=True
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  warning: could not `git add` {path.name}: {exc}")


def save_statement(statement: Statement) -> Path:
    """Write the statement record (deterministic JSON) and stage it for commit."""
    path = export_statement(statement)
    _git_add(path)
    return path


def capture_and_save(
    *,
    member_id: str,
    text: str,
    date: str,
    venue: str,
    source_url: str,
    named_measures: list[str],
    specificity_level: Literal[0, 1, 2, 3] | None = None,
    stated_position: Literal["support", "oppose"] | None = None,
    curator_note: str | None = None,
    client: SpnClient | None = None,
) -> Path:
    """The full owner action: capture the source, build the record, save + stage.
    Any capture failure raises `SpnError` and NOTHING is written."""
    spn = client or SpnClient()
    try:
        capture = spn.capture(source_url)
    finally:
        if client is None:
            spn.close()
    statement = build_statement(
        member_id=member_id,
        text=text,
        date=date,
        venue=venue,
        source_url=source_url,
        named_measures=named_measures,
        capture=capture,
        specificity_level=specificity_level,
        stated_position=stated_position,
        curator_note=curator_note,
    )
    return save_statement(statement)


def repair(argv: list[str] | None = None) -> int:
    """Re-resolve `paired_bill_ids` for every committed statement against the current
    `_title_allowlist.yaml`, rewriting only the records whose pairing changed. Run
    this after editing the allowlist (D9 resolution is otherwise frozen at save time).
    Idempotent; does not touch any owner-authored field or the archive capture."""
    if not STATEMENTS_DIR.exists():
        print("curate statements repair: no statements yet.")
        return 0
    allowlist = pairing.load_allowlist()
    changed = 0
    for path in sorted(STATEMENTS_DIR.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        new_pairs = pairing.resolve(rec.get("named_measures", []), allowlist)
        if new_pairs != rec.get("paired_bill_ids"):
            rec["paired_bill_ids"] = new_pairs
            # Round-trip through the model so the write stays schema-valid + canonical.
            save_statement(Statement.model_validate(rec))
            changed += 1
    print(f"curate statements repair: re-resolved {changed} statement(s) against the allowlist.")
    return 0
