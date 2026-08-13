"""INC-7 tests — the public export contract: deterministic manifest + JSON
Schema generation, the offline `export` entrypoint, bill export, and the
`verify-recompute` recompute-and-match invariants run over the committed dataset
(§8: "recompute-and-match script as a test"). All offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from ingest import config, export, verify_recompute
from ingest.cache import repo_root
from ingest.models import Absence, Bill, CboRef

FIXED_TS = "2020-01-01T00:00:00Z"
FIXED_COMMIT = "0000000"


# --- Manifest determinism -------------------------------------------------


def test_manifest_double_build_byte_identical() -> None:
    a = export._dumps(export.build_manifest(FIXED_TS, FIXED_COMMIT))
    b = export._dumps(export.build_manifest(FIXED_TS, FIXED_COMMIT))
    assert a == b


def test_manifest_injects_wall_clock_only_here() -> None:
    # generated_at / commit come from the injected args, never read internally.
    m = export.build_manifest(FIXED_TS, FIXED_COMMIT)
    assert m["generated_at"] == FIXED_TS
    assert m["commit"] == FIXED_COMMIT
    # Counts reflect the real committed dataset (V2-1: no fixed member count —
    # the full roster churns; compare against what's actually on disk instead).
    assert m["counts"]["members"] == len(list((repo_root() / "data" / "members").glob("*.json")))
    assert m["counts"]["rollcalls"] == m["counts"]["rollcalls_by_chamber"]["house"] + \
        m["counts"]["rollcalls_by_chamber"]["senate"]
    assert m["congresses"] == list(config.CONGRESSES)
    # "covered_state" was removed from the manifest (D61): federal coverage is no
    # longer state-scoped, so the field would misstate scope.
    assert "covered_state" not in m
    # non_position rolls are counted under their own key, not lumped into `other`
    # (L-1): `other` reads as the genuine one-off rate, and the two keys agree with
    # the standalone non_position count.
    by_class = m["counts"]["rollcalls_by_vote_class"]
    assert by_class["non_position"] == m["counts"]["non_position_rollcalls"]
    assert by_class.get("other", 0) < by_class["non_position"]


def test_committed_manifest_matches_regeneration() -> None:
    # The committed manifest's *counts* must equal a fresh recount (the
    # timestamp/commit are allowed to differ — they're the injected fields).
    committed = json.loads((repo_root() / "data" / "manifest.json").read_text(encoding="utf-8"))
    fresh = export.build_manifest(committed["generated_at"], committed["commit"])
    assert committed == fresh


# --- Schema generation determinism ----------------------------------------


def test_schemas_double_export_byte_identical(tmp_path: Path) -> None:
    d1, d2 = tmp_path / "a", tmp_path / "b"
    p1 = export.export_schemas(d1)
    p2 = export.export_schemas(d2)
    assert [p.name for p in p1] == [p.name for p in p2]
    for x, y in zip(p1, p2, strict=True):
        assert x.read_text(encoding="utf-8") == y.read_text(encoding="utf-8")


def test_committed_schemas_up_to_date(tmp_path: Path) -> None:
    fresh = export.export_schemas(tmp_path)
    for f in fresh:
        committed = repo_root() / "data" / "schema" / f.name
        assert committed.exists(), f"missing committed schema {f.name}"
        assert committed.read_text(encoding="utf-8") == f.read_text(encoding="utf-8"), \
            f"{f.name} out of date — re-run `uv run export`"


def test_vote_schema_is_composite() -> None:
    # The vote file is {rollcall, member_votes}, not a bare RollCall.
    schema = export.VoteFile.model_json_schema()
    assert set(schema["properties"]) == {"rollcall", "member_votes"}


# --- Bill export ----------------------------------------------------------


def test_export_bill_roundtrip(tmp_path: Path) -> None:
    bill = Bill(
        id="hr2-119",
        congress=119,
        type="hr",
        number=2,
        title_official="An Act",
        policy_area=None,
        subjects=[],
        sponsor_id=None,
        cosponsor_ids=[],
        latest_action="Referred",
        latest_action_date="2025-01-03",
        cbo_estimates=[CboRef(url="https://cbo.gov/x", title="Est", date="2025-02-01")],
        source_url="https://api.congress.gov/v3/bill/119/hr/2",
    )
    path = export.export_bill(bill, tmp_path)
    assert path.name == "hr2-119.json"
    reloaded = Bill.model_validate_json(path.read_text(encoding="utf-8"))
    assert reloaded == bill
    # Deterministic: re-export is byte-identical.
    text = path.read_text(encoding="utf-8")
    export.export_bill(bill, tmp_path)
    assert path.read_text(encoding="utf-8") == text


# --- verify-recompute -----------------------------------------------------


def test_verify_recompute_matches_committed_dataset() -> None:
    # The headline INC-7 acceptance: recompute-and-match holds for every roll.
    failures = verify_recompute.check_dataset()
    assert failures == [], f"verify-recompute failures: {failures[:10]}"


def test_verify_recompute_entrypoint_green() -> None:
    assert verify_recompute.main([]) == 0


# --- absence overwrite guard (D35) ----------------------------------------


def test_export_absence_overwrite_false_preserves_owner_reason(tmp_path: Path) -> None:
    # Simulate an owner-approved absence on disk (H9), then a nightly ingest stub.
    approved = Absence(
        member_id="G000591",
        rollcall_id="h-118-1-0031",
        stated_reason="I was unavoidably absent.",
        stated_reason_source="https://www.congress.gov/crec/...",
        declared_position="yea",
    )
    export.export_absence(approved, tmp_path)
    # The ingest re-emits a bare stub for the same roll (reason=None).
    stub = Absence(member_id="G000591", rollcall_id="h-118-1-0031")
    export.export_absence(stub, tmp_path, overwrite=False)
    reloaded = Absence.model_validate_json(
        (tmp_path / "G000591--h-118-1-0031.json").read_text(encoding="utf-8")
    )
    assert reloaded == approved  # the approval survived the re-ingest


def test_export_absence_default_overwrites(tmp_path: Path) -> None:
    export.export_absence(Absence(member_id="X", rollcall_id="r"), tmp_path)
    export.export_absence(Absence(member_id="X", rollcall_id="r"), tmp_path)  # no error
    # overwrite=False creates when absent (a brand-new not_voting stub).
    p = export.export_absence(Absence(member_id="Y", rollcall_id="r"), tmp_path, overwrite=False)
    assert p.exists()
