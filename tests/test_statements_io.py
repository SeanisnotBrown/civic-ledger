"""R-1b/M-3 — the single statement loader. One place decides "what is a statement,
and is it publishable"; these pin the two axes (config-file skip; dead-archive
exclusion) that four call sites used to disagree on. Offline; a tmp data dir."""

from __future__ import annotations

import json

from ingest import statements_io


def _write(sdir, sid, **over):
    rec = {"id": sid, "member_id": "M1", "text": "t", "date": "2024-01-01", "venue": "v",
           "source_url": "https://ex.com", "archive_url": "https://web.archive.org/x",
           "archive_captured_at": "2024-01-01T00:00:00Z", "named_measures": [],
           "paired_bill_ids": [], "specificity_level": None, "stated_position": None,
           "curator_note": None}
    rec.update(over)
    (sdir / f"{sid}.json").write_text(json.dumps(rec), encoding="utf-8")


def _seed(tmp_path, dead_ids=None):
    data = tmp_path / "data"
    sdir = data / "statements"
    sdir.mkdir(parents=True)
    _write(sdir, "alive")
    _write(sdir, "gone")
    # A `_`-prefixed json (a future config file) must never be read as a record.
    (sdir / "_config.json").write_text(json.dumps({"id": "_config"}), encoding="utf-8")
    if dead_ids is not None:
        qdir = data / "quality"
        qdir.mkdir(parents=True)
        (qdir / "archive-status.json").write_text(
            json.dumps({"dead_statement_ids": dead_ids}), encoding="utf-8"
        )
    return data


def test_config_files_are_never_records(tmp_path) -> None:
    data = _seed(tmp_path)
    ids = {r["id"] for r in statements_io.load_statements(data_dir=data)}
    assert ids == {"alive", "gone"}  # _config.json excluded
    assert [p.name for p in statements_io.statement_files(data)] == ["alive.json", "gone.json"]


def test_exclude_dead_drops_flagged_ids(tmp_path) -> None:
    data = _seed(tmp_path, dead_ids=["gone"])
    both = {r["id"] for r in statements_io.load_statements(data_dir=data, exclude_dead=False)}
    live = {r["id"] for r in statements_io.load_statements(data_dir=data, exclude_dead=True)}
    assert both == {"alive", "gone"}   # counting view keeps the dead record
    assert live == {"alive"}           # publishable view drops it
    assert statements_io.dead_statement_ids(data) == {"gone"}


def test_missing_report_excludes_nothing(tmp_path) -> None:
    data = _seed(tmp_path, dead_ids=None)  # no archive-status.json
    live = {r["id"] for r in statements_io.load_statements(data_dir=data, exclude_dead=True)}
    assert live == {"alive", "gone"}
    assert statements_io.dead_statement_ids(data) == set()


def test_no_statements_dir_is_empty(tmp_path) -> None:
    assert statements_io.load_statements(data_dir=tmp_path / "data") == []
    assert statements_io.statement_files(tmp_path / "data") == []
