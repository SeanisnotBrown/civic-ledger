"""INC-11 — statement curation core: the no-verified-capture-no-save rule (enforced
server-side), pairing resolution stored on the record, id determinism, and the
allowlist-repair re-resolution. No network; the Capture is constructed directly."""

from __future__ import annotations

import json

import pytest

from curation import statements
from ingest.sources.archive_org import Capture


def _cap(url="https://ex.com/s"):
    return Capture(original_url=url, archive_url=f"https://web.archive.org/web/20240101000000/{url}",
                   timestamp="20240101000000", captured_at="2024-01-01T00:00:00Z")


def _build(monkeypatch, **over):
    monkeypatch.setattr(statements, "_covered_member_ids", lambda: {"M1"})
    kw = dict(member_id="M1", text="We must pass this.", date="2024-03-05", venue="floor",
              source_url="https://ex.com/s", named_measures=["HR2-119"], capture=_cap())
    kw.update(over)
    return statements.build_statement(**kw)


def test_build_refuses_without_a_verified_capture(monkeypatch) -> None:
    monkeypatch.setattr(statements, "_covered_member_ids", lambda: {"M1"})
    with pytest.raises(ValueError, match="no verified capture"):
        statements.build_statement(member_id="M1", text="t", date="2024-01-01", venue="v",
                                   source_url="https://ex.com/s", named_measures=[], capture=None)


def test_build_refuses_capture_for_a_different_source(monkeypatch) -> None:
    monkeypatch.setattr(statements, "_covered_member_ids", lambda: {"M1"})
    with pytest.raises(ValueError, match="mismatched archive"):
        statements.build_statement(member_id="M1", text="t", date="2024-01-01", venue="v",
                                   source_url="https://OTHER", named_measures=[], capture=_cap())


def test_build_refuses_unknown_member(monkeypatch) -> None:
    monkeypatch.setattr(statements, "_covered_member_ids", lambda: {"M1"})
    with pytest.raises(ValueError, match="not a covered member"):
        _build(monkeypatch, member_id="NOPE")


def test_build_resolves_pairing_and_stores_it(monkeypatch) -> None:
    s = _build(monkeypatch, named_measures=["HR2-119", "some vague title"],
               stated_position="support", specificity_level=3)
    assert s.paired_bill_ids == ["hr2-119"]  # bill-id resolved, vague title dropped
    assert s.named_measures == ["HR2-119", "some vague title"]  # names kept verbatim
    assert s.stated_position == "support"
    assert s.archive_url == _cap().archive_url


def test_statement_id_is_deterministic(monkeypatch) -> None:
    a = _build(monkeypatch)
    b = _build(monkeypatch)
    assert a.id == b.id  # same member+date+source → stable id (idempotent re-curation)


def test_save_writes_deterministic_json(monkeypatch, tmp_path) -> None:
    from ingest.export import export_statement
    monkeypatch.setattr(statements, "export_statement",
                        lambda stmt: export_statement(stmt, out_dir=tmp_path))
    monkeypatch.setattr(statements, "_git_add", lambda p: None)
    s = _build(monkeypatch)
    path = statements.save_statement(s)
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["id"] == s.id and rec["paired_bill_ids"] == ["hr2-119"]


def test_repair_reresolves_against_the_current_allowlist(monkeypatch, tmp_path) -> None:
    from ingest.export import export_statement

    # Seed one statement whose named title is not yet paired.
    monkeypatch.setattr(statements, "STATEMENTS_DIR", tmp_path)
    monkeypatch.setattr(statements, "export_statement",
                        lambda stmt: export_statement(stmt, out_dir=tmp_path))
    monkeypatch.setattr(statements, "_git_add", lambda p: None)
    s = _build(monkeypatch, named_measures=["The Example Act"])
    export_statement(s, out_dir=tmp_path)
    assert json.loads((tmp_path / f"{s.id}.json").read_text())["paired_bill_ids"] == []

    # Owner adds the title to the allowlist → repair re-resolves it.
    monkeypatch.setattr(statements.pairing, "load_allowlist",
                        lambda: {"the example act": "hr9-119"})
    statements.repair()
    assert json.loads((tmp_path / f"{s.id}.json").read_text())["paired_bill_ids"] == ["hr9-119"]
