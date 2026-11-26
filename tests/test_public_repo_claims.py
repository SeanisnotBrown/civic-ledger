"""The public-repository claims on /privacy and /corrections are true today.

Copilot-authored, not reviewed by Sean (copilot call 2026-11-26, preview
branch, unmerged). D59 (2026-08-13) stripped these claims while the repo was
private; it went public 2026-10-13 (`IMPLEMENTATIONv3.md` §2). §1 rule 0 says
copy that describes the system flips with the thing that makes it true, so
this file pins the parts that can be checked offline:

* both pages point at the one repository URL, and every `/blob/master/<path>`
  link into it names a file that exists in the working tree;
* `/corrections` links each log entry to its commit, and offers the issues and
  commits pages the report-an-error text relies on;
* two claims that would be FALSE today stay off the pages: that the whole
  dataset is the repository (`data/raw/` is gitignored) and that a legal demand
  would produce only what is already public (it would not).

What it cannot check offline: that GitHub still reports the repo public with
issues enabled. That was verified by hand on 2026-11-26 (`gh repo view`:
PUBLIC, issues enabled; the repo, /issues, /commits, the commit and the
correction-process URLs all answered 200) and is recorded in
`docs/research/2026-11-26-public-repo-claims-preview.md`.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ingest.cache import repo_root

REPO_URL = "https://github.com/SeanisnotBrown/civic-ledger"
PAGES = ("privacy.astro", "corrections.astro")


def _page(name: str) -> str:
    return (repo_root() / "site" / "src" / "pages" / name).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_corrections_page_points_at_the_repository_and_links_each_commit() -> None:
    page = _page("corrections.astro")
    assert f'const repo = "{REPO_URL}"' in page
    assert "{`${repo}/commit/${c.commit}`}" in page, "log entries must link to their commit"
    assert "{`${repo}/issues`}" in page, "the report-an-error link is gone"
    assert "{`${repo}/commits`}" in page, "the change-history link is gone"
    assert "public repository" in _flat(page)


def test_privacy_page_states_where_the_code_and_dataset_live() -> None:
    flat = _flat(_page("privacy.astro"))
    assert f'href="{REPO_URL}"' in flat
    assert "published dataset" in flat
    # The sentence must not claim the repository is the whole dataset.
    assert "Some working files used to build that dataset are not in it" in flat


def test_pages_use_one_repository_url() -> None:
    for name in PAGES:
        urls = set(re.findall(r"https://github\.com/[\w.-]+/[\w.-]+", _page(name)))
        assert urls <= {REPO_URL}, f"/{name} links a repository other than {REPO_URL}: {urls}"


def test_every_blob_link_into_the_repo_names_an_existing_file() -> None:
    # "A link must point at a path that exists on master." The working tree is
    # master plus this branch; a link to a file that only exists here would
    # still 404 for readers, so also check the path is tracked by git.
    pages = repo_root() / "site" / "src" / "pages"
    pattern = re.compile(r"(?:\$\{repo\}|" + re.escape(REPO_URL) + r")/blob/master/([\w./-]+)")
    seen: list[str] = []
    for page in pages.rglob("*.astro"):
        seen += pattern.findall(page.read_text(encoding="utf-8"))
    assert "docs/correction-process.md" in seen and "docs/data-contract.md" in seen
    tracked = set(
        subprocess.run(
            ["git", "ls-files", "docs"], cwd=repo_root(), capture_output=True, text=True, check=True
        ).stdout.splitlines()
    )
    missing = sorted({p for p in seen if p not in tracked})
    assert not missing, f"site links to repository paths that are not tracked: {missing}"


def test_false_claims_stay_off_the_pages() -> None:
    for name in PAGES:
        flat = _flat(_page(name)).lower()
        for claim in (
            "the entire dataset is the public repository",
            "produces only what is already public here",
            "not currently public",
            "no public channel for submitting",
        ):
            assert claim not in flat, f"/{name} states something false today: {claim!r}"


def test_correction_process_doc_matches_the_pages() -> None:
    # The doc and /corrections describe one process. The D59 wording said the
    # repo was private and had no issue tracker; the page now says the opposite.
    doc = Path(repo_root() / "docs" / "correction-process.md").read_text(encoding="utf-8")
    flat = _flat(doc).lower()
    assert "currently private" not in flat
    assert "no public issue tracker" not in flat
    assert "issue tracker is open" in flat
