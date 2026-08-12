"""INC-11 — D9 pairing resolution. The bright line: bill-id form passes through,
an EXACT allowlist title maps, everything else is unpaired. No fuzzy matching."""

from __future__ import annotations

import pytest

from ingest import pairing


def test_bill_id_form_passes_through_lowercased() -> None:
    assert pairing.resolve(["HR2-119", "s45-118"], {}) == ["hr2-119", "s45-118"]


def test_exact_allowlist_title_maps() -> None:
    al = {"the pact act": "s3373-117"}
    assert pairing.resolve(["The PACT Act"], al) == ["s3373-117"]


def test_unlisted_title_is_unpaired() -> None:
    al = {"the pact act": "s3373-117"}
    assert pairing.resolve(["some vague bill", "PACT"], al) == []  # no fuzzy match


def test_result_is_sorted_and_deduplicated() -> None:
    al = {"the pact act": "hr2-119"}  # title maps to the same id a measure names
    assert pairing.resolve(["hr2-119", "HR2-119", "The PACT Act", "s1-119"], al) == [
        "hr2-119", "s1-119"
    ]


def test_load_allowlist_missing_file_is_empty(tmp_path) -> None:
    assert pairing.load_allowlist(tmp_path / "nope.yaml") == {}


def test_load_allowlist_casefolds_keys(tmp_path) -> None:
    p = tmp_path / "al.yaml"
    p.write_text('"The PACT Act": s3373-117\n', encoding="utf-8")
    al = pairing.load_allowlist(p)
    assert al == {"the pact act": "s3373-117"}
    assert pairing.resolve(["THE PACT ACT"], al) == ["s3373-117"]


def test_load_allowlist_rejects_non_bill_id_value(tmp_path) -> None:
    p = tmp_path / "al.yaml"
    p.write_text('"Some Act": not-a-bill-id\n', encoding="utf-8")
    with pytest.raises(ValueError):
        pairing.load_allowlist(p)


def test_committed_allowlist_loads() -> None:
    # The shipped data/statements/_title_allowlist.yaml is valid + empty at launch.
    assert pairing.load_allowlist() == {}
