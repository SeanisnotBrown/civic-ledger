"""Smoke tests — the tooling skeleton is wired correctly.

These give pytest something to collect (pytest exits 5 with zero tests, which
would fail the acceptance chain) and pin the invariants that hold in every
phase: the console entrypoints import, the shared constants have one
definition, and the banned-words check (the mechanical edge of
`IMPLEMENTATIONv3.md` §1 rule 6) works on the real tree.
"""

from __future__ import annotations

import importlib

import pytest

from ingest import config


def test_console_entrypoints_importable():
    # Every [project.scripts] target must import and expose `main`.
    for module_path in (
        "ingest.cli",
        "ingest.export",
        "curation.cli",
        "ingest.checks.run",
    ):
        mod = importlib.import_module(module_path)
        assert callable(mod.main)


def test_k_anon_is_fifty():
    # §10.3: single constant; a later test asserts the Worker copy equals this.
    assert config.K_ANON == 50


def test_congress_coverage():
    # Decision D5.
    assert config.CONGRESSES == [118, 119]


def test_banned_words_list_nonempty_and_lowercase():
    from ingest.checks import banned_words

    assert len(banned_words.BANNED) >= 12
    # Scan is case-insensitive via .lower(); the list itself must be lowercase.
    assert all(term == term.lower() for term in banned_words.BANNED)


def test_banned_words_passes_on_clean_repo():
    from ingest.checks import banned_words

    # The committed repo (data/**, site/src/**, site/dist/**) must be clean.
    assert banned_words.find_hits() == []


def test_banned_words_detects_a_hit(tmp_path):
    from ingest.checks import banned_words

    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x.md").write_text("this is pure hypocrisy\n", encoding="utf-8")
    hits = banned_words.find_hits(root=tmp_path)
    assert any(term == "hypocrisy" for _, _, term in hits)


def test_checks_suite_does_not_register_the_retired_no_llm_guard():
    # IMPLEMENTATIONv3.md §1 retired the no-AI-in-the-publishing-path rule and
    # its CI guard on 2026-10-07 ("do not reinstate"). AI text is now governed
    # by rule 7 (labeled + human-approved) instead of a structural ban.
    from ingest.checks import run

    assert "no_llm" not in {name for name, _ in run.CHECKS}


@pytest.mark.parametrize("suffix", [".json", ".yaml", ".md", ".astro", ".ts"])
def test_banned_words_scans_expected_suffixes(suffix):
    from ingest.checks import banned_words

    assert suffix in banned_words.TEXT_SUFFIXES
