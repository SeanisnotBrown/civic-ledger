"""INC-0 smoke tests — the tooling skeleton is wired correctly.

These give pytest something to collect (pytest exits 5 with zero tests, which
would fail the acceptance chain) and pin the invariants INC-0 must hold.
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


def test_no_llm_does_not_flag_itself():
    # The guard's own source must not trip its endpoint scan (the classic
    # self-match bug). Run the real endpoint scan over the real tree.
    from ingest.checks import no_llm

    assert no_llm.check_endpoints(no_llm.repo_root()) == []


def test_no_llm_detects_endpoint(tmp_path):
    from ingest.checks import no_llm

    (tmp_path / "ingest").mkdir()
    # Assemble the forbidden endpoint from parts so THIS test file does not
    # itself contain the literal (it lives outside the scanned dirs anyway).
    endpoint = "https://api." + "openai" + ".com/v1/chat"
    (tmp_path / "ingest" / "leak.py").write_text(f'URL = "{endpoint}"\n', encoding="utf-8")
    problems = no_llm.check_endpoints(tmp_path)
    assert problems, "endpoint scan should have flagged the planted URL"


def test_no_llm_detects_forbidden_package(tmp_path):
    from ingest.checks import no_llm

    (tmp_path / "uv.lock").write_text('name = "openai"\nversion = "1.0"\n', encoding="utf-8")
    problems = no_llm.check_lockfiles(tmp_path)
    assert any("openai" in p for p in problems)


def test_no_llm_contributing_policy_present():
    from ingest.checks import no_llm

    assert no_llm.check_contributing(no_llm.repo_root()) == []


@pytest.mark.parametrize("suffix", [".json", ".yaml", ".md", ".astro", ".ts"])
def test_banned_words_scans_expected_suffixes(suffix):
    from ingest.checks import banned_words

    assert suffix in banned_words.TEXT_SUFFIXES
