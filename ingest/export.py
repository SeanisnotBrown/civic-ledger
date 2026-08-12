"""`export` console entrypoint + deterministic record serialization (§6.3).

Determinism guarantees (§6.3, verified by a double-export byte-compare in
tests): sorted keys, sorted lists by a stated sort key, LF endings, 2-space
indent, and NO wall-clock inside any record (the single "generated at" lives in
data/manifest.json, added later). `uv run export` on the same inputs twice must
be byte-identical so nightly git diffs show only real changes.

INC-2 exports `data/members/*.json`. The full SQLite → JSON export contracts for
every record type land in INC-7; the `ingest members` subcommand drives the
member export today.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ingest.cache import repo_root
from ingest.models import Absence, Member, MemberVote, RollCall

DATA_DIR = repo_root() / "data"
MEMBERS_DIR = DATA_DIR / "members"
VOTES_DIR = DATA_DIR / "votes"
ABSENCES_DIR = DATA_DIR / "absences"


def _dumps(obj: object) -> str:
    """Canonical JSON: sorted keys, 2-space indent, LF, trailing newline."""
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def export_members(members: list[Member], out_dir: Path = MEMBERS_DIR) -> list[Path]:
    """Write one deterministic JSON file per member: data/members/{bioguide}.json.
    `terms` is already start-sorted by the parser; `sort_keys` handles every dict
    (ids, and each term). Returns the written paths, sorted."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for member in members:
        path = out_dir / f"{member.id}.json"
        path.write_text(_dumps(member.model_dump()), encoding="utf-8", newline="\n")
        written.append(path)
    return sorted(written)


def export_rollcall(
    rollcall: RollCall, member_votes: list[MemberVote], out_dir: Path = VOTES_DIR
) -> Path:
    """Write data/votes/{id}.json: the chamber RollCall with the covered
    delegation's votes embedded (sorted by member_id for determinism)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{rollcall.id}.json"
    record = {
        "rollcall": rollcall.model_dump(),
        "member_votes": [mv.model_dump() for mv in sorted(member_votes, key=lambda m: m.member_id)],
    }
    path.write_text(_dumps(record), encoding="utf-8", newline="\n")
    return path


def export_absence(absence: Absence, out_dir: Path = ABSENCES_DIR) -> Path:
    """One file per absence: data/absences/{member_id}--{rollcall_id}.json. Kept
    separate from vote files so INC-6 curation can add a stated_reason without
    rewriting the (much larger) vote record."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{absence.member_id}--{absence.rollcall_id}.json"
    path.write_text(_dumps(absence.model_dump()), encoding="utf-8", newline="\n")
    return path


def main(argv: list[str] | None = None) -> int:
    _ = sys.argv[1:] if argv is None else argv
    print("civic-ledger export: member export runs via `ingest members` (INC-2).")
    print("Full SQLite → JSON export contracts land in INC-7.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
