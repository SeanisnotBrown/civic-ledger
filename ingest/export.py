"""`export` console entrypoint + deterministic record serialization (§6.3).

Determinism guarantees (§6.3, verified by a double-export byte-compare in
tests): sorted keys, sorted lists by a stated sort key, LF endings, 2-space
indent, and NO wall-clock inside any record. The single "generated at" (and the
producing commit) live only in data/manifest.json, whose timestamp/commit are
*injected* — never read at import — so the record-level export stays byte-stable
and nightly git diffs show only real data changes.

INC-2 exports data/members/*.json; INC-3/4 export data/votes/ + data/absences/
via their ingests. INC-7 completes the public *contract*: per-record write
helpers for all Tier-1 file types (members/votes/bills/absences), JSON Schema
files generated from the pydantic models (data/schema/), a manifest, and the
offline `uv run export` that regenerates the derived artifacts (manifest +
schemas) from the committed dataset alone — no network, no re-ingest (a re-ingest
would reset vote_class and force a reclassify, D24; export must never do that).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel

from ingest.cache import repo_root
from ingest.models import Absence, Bill, Member, MemberVote, RollCall

DATA_DIR = repo_root() / "data"
MEMBERS_DIR = DATA_DIR / "members"
VOTES_DIR = DATA_DIR / "votes"
ABSENCES_DIR = DATA_DIR / "absences"
BILLS_DIR = DATA_DIR / "bills"
SCHEMA_DIR = DATA_DIR / "schema"
MANIFEST_PATH = DATA_DIR / "manifest.json"


def _dumps(obj: object) -> str:
    """Canonical JSON: sorted keys, 2-space indent, LF, trailing newline."""
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


class VoteFile(BaseModel):
    """The composite shape of one data/votes/*.json file: a chamber `RollCall`
    with the covered delegation's positions embedded. Exists so the file's JSON
    Schema documents the wrapper, not just the inner `RollCall`."""

    rollcall: RollCall
    member_votes: list[MemberVote]


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


def export_bill(bill: Bill, out_dir: Path = BILLS_DIR) -> Path:
    """Write one deterministic JSON file per bill: data/bills/{id}.json. No bill
    ingest runs yet (bills land with the INC-8 bill pages); the helper + schema
    exist now so the export contract is complete for every Tier-1 file type."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{bill.id}.json"
    path.write_text(_dumps(bill.model_dump()), encoding="utf-8", newline="\n")
    return path


def export_absence(
    absence: Absence, out_dir: Path = ABSENCES_DIR, *, overwrite: bool = True
) -> Path:
    """One file per absence: data/absences/{member_id}--{rollcall_id}.json. Kept
    separate from vote files so INC-6 curation can add a stated_reason without
    rewriting the (much larger) vote record.

    `overwrite=False` (used by the ingest) preserves an existing file untouched:
    an ingest stub carries nothing a re-fetch can update, but the reason fields are
    OWNER-OWNED (H9 approvals). Nightly re-fetches recent rolls (D31), so an
    unconditional write would silently reset an approved `stated_reason` to null —
    a false "No explanation on record." (value #1). The curation tool writes the
    approved Absence directly (not via this helper), so it is unaffected (D35)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{absence.member_id}--{absence.rollcall_id}.json"
    if not overwrite and path.exists():
        return path
    path.write_text(_dumps(absence.model_dump()), encoding="utf-8", newline="\n")
    return path


# --- JSON Schema (data/schema/) -------------------------------------------
# One schema per published file type. The vote file is composite, so it maps to
# `VoteFile`, not `RollCall`; the others map to their Tier-1 model directly.
_SCHEMAS: tuple[tuple[str, type[BaseModel]], ...] = (
    ("member", Member),
    ("vote", VoteFile),
    ("bill", Bill),
    ("absence", Absence),
)


def export_schemas(out_dir: Path = SCHEMA_DIR) -> list[Path]:
    """Generate data/schema/{type}.schema.json from the pydantic models. Dumped
    through `_dumps` so the schema files are byte-stable across runs (they change
    only when a model changes — i.e. when the published contract itself changes)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in _SCHEMAS:
        path = out_dir / f"{name}.schema.json"
        path.write_text(_dumps(model.model_json_schema()), encoding="utf-8", newline="\n")
        written.append(path)
    return sorted(written)


# --- Manifest (data/manifest.json) ----------------------------------------


def _count_dataset() -> dict[str, object]:
    """Deterministic counts over the committed dataset (no wall-clock)."""
    from ingest import config

    members = sorted(MEMBERS_DIR.glob("*.json")) if MEMBERS_DIR.exists() else []
    votes = sorted(VOTES_DIR.glob("*.json")) if VOTES_DIR.exists() else []
    absences = sorted(ABSENCES_DIR.glob("*.json")) if ABSENCES_DIR.exists() else []
    bills = sorted(BILLS_DIR.glob("*.json")) if BILLS_DIR.exists() else []

    by_chamber: dict[str, int] = {}
    by_class: dict[str, int] = {}
    member_vote_total = 0
    non_position = 0
    for path in votes:
        rec = json.loads(path.read_text(encoding="utf-8"))
        rc = rec["rollcall"]
        by_chamber[rc["chamber"]] = by_chamber.get(rc["chamber"], 0) + 1
        by_class[rc["vote_class"]] = by_class.get(rc["vote_class"], 0) + 1
        member_vote_total += len(rec["member_votes"])
        if rc["vote_class_rule"] == "non_position":
            non_position += 1

    return {
        "congresses": list(config.CONGRESSES),
        "covered_state": config.COVERED_STATE,
        "counts": {
            "members": len(members),
            "rollcalls": len(votes),
            "rollcalls_by_chamber": dict(sorted(by_chamber.items())),
            "rollcalls_by_vote_class": dict(sorted(by_class.items())),
            "non_position_rollcalls": non_position,
            "member_votes": member_vote_total,
            "absences": len(absences),
            "bills": len(bills),
        },
    }


def build_manifest(generated_at: str, commit: str) -> dict[str, object]:
    """The manifest is the ONE place a wall-clock/commit value lives (§6.3), so
    both are *injected* (never read here) to keep the double-export test stable.
    `commit` is HEAD at generation time — the code state that produced the export,
    not the commit that will contain this manifest (that sha can't exist yet)."""
    manifest = {"generated_at": generated_at, "commit": commit}
    manifest.update(_count_dataset())
    return manifest


def export_manifest(generated_at: str, commit: str, path: Path = MANIFEST_PATH) -> Path:
    path.write_text(_dumps(build_manifest(generated_at, commit)), encoding="utf-8", newline="\n")
    return path


def _git_head() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root(),
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    """Offline export of the DERIVED artifacts (schemas + manifest) from the
    committed dataset. Per-record files are written by the ingests; this
    regenerates what depends on the whole dataset. Real generated_at/commit are
    resolved here (the manifest is where they belong); records stay wall-clock-free.
    """
    import os
    from datetime import UTC, datetime

    _ = sys.argv[1:] if argv is None else argv
    schemas = export_schemas()
    now = datetime.now(UTC).replace(microsecond=0)
    generated_at = os.environ.get(
        "CIVIC_GENERATED_AT", now.isoformat().replace("+00:00", "Z")
    )
    commit = os.environ.get("CIVIC_COMMIT") or _git_head()
    export_manifest(generated_at, commit)
    print(f"export: wrote {len(schemas)} schema(s) to {SCHEMA_DIR.relative_to(repo_root())}/")
    print(f"export: wrote manifest (commit {commit}) to {MANIFEST_PATH.relative_to(repo_root())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
