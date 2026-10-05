"""V2-7 acceptance — the privacy surface says what the code and config actually say.

The spec's acceptance for V2-7 (`IMPLEMENTATIONv2.md` §9 V2-7) is a grep-style
accuracy test: *"the deployed privacy page's stated storage list and K constant
match code/config. On failure: the accuracy test failing means site text and
system diverged — fix the text or the system, never the test."*

What these tests exist to pin, in order of how much damage getting them wrong
would do:

1. **The K number the reader is shown is the K the system enforces.** The page
   states "has to cover at least 50 people" as a hardcoded literal, and
   `config.K_ANON` is the constant that governs the gate. Nothing links them.
   Lower `K_ANON` to 25 and the page becomes a false claim about privacy —
   the single worst class of bug this project can ship (§0.5). This test is
   the link.
2. **The storage list keeps one item per table that will exist.** Spec §5
   names six D1 tables and the page describes six things in plain words. A
   seventh table arriving without a seventh bullet is undisclosed collection.
3. **SD-34's withdrawn guarantees stay withdrawn, and the three it did NOT
   withdraw stay stated.** SD-34 (2026-10-05) removed the no-tracking
   promises; it explicitly kept hard deletion, the K-anon render gate, and
   never-selling. Each needs its own dated decision to remove, so a silent
   sweep of any of the three fails here.

Scope caveat — **half of the spec's acceptance cannot be written yet, and the
blocker is not only the missing schema.** The acceptance compares the stated
list against the *Worker's D1 schema*, which V2-8 creates; there is no
`worker/`, no `.sql`, and no `d1_databases` binding in `site/wrangler.jsonc`
today. On top of that the canonical table list is itself unratified: §5 names
six tables, and `docs/plan-subscriptions-and-alerts.md` task 1 adds a seventh
(`email_verifications`) that is on neither §5 nor the page. Picking one by
guess would defeat the test, so `test_schema_half_is_still_deferred` names
both blockers rather than quietly skipping.

These tests read the committed `site/src/` **source**, not `site/dist/`: in CI
the Python job runs before the Node job's `npm run build`, so `dist/` does not
exist when pytest runs. The site-copy guards that do scan `dist/` are the
`npm run test:*` scripts (`site/scripts/check-grade-labels.mjs` is the
precedent for the render-side half of this pair).

Note that `/privacy` itself carries neither the storage list nor the K number —
both live on `/threat-model`, which `/privacy` links to as "the long version of
this page". The acceptance's "privacy page" is therefore read as the privacy
surface, both pages, and a test pins the link that joins them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ingest import config
from ingest.cache import repo_root

# The D1 tables spec §5 names under "Account model" (IMPLEMENTATIONv2.md:351-359).
# `/threat-model`'s "When accounts ship" list describes these in plain words,
# one bullet per table, in this order:
#   users         -> "Who you are: your email address, ... a scrambled form of your password"
#   subscriptions -> "What you follow: which bills, topics and members"
#   preferences   -> "Your settings and your answers to anything the site asks you"
#   deliveries    -> "Which alerts have already gone to you"
#   channels      -> "Where to reach you: your email address, and a phone number"
#   profiles      -> "A public profile, only if you choose to make one"
SPEC_TABLES: tuple[str, ...] = (
    "users",
    "preferences",
    "subscriptions",
    "deliveries",
    "channels",
    "profiles",
)

# Claims SD-34 withdrew. These were live copy once; they must never come back
# without a dated decision reversing SD-34. Each is matched as the *claim* it
# was, not as a topic — `/threat-model` legitimately discusses cookies in its
# "what is not promised" section, which is the opposite of promising.
WITHDRAWN_CLAIMS: tuple[str, ...] = (
    "collect as little as possible",
    "No cookies. No analytics",
    "No third-party fonts, scripts, or CDNs",
    "would produce only what that private repository contains",
)

SCANNED_SUFFIXES = frozenset({".astro", ".ts", ".tsx", ".md", ".mdx"})


def _page(name: str) -> str:
    return (repo_root() / "site" / "src" / "pages" / name).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Collapse whitespace so a claim that wraps across source lines still matches.

    Load-bearing: the K sentence is split as "...at least\n      50 people...",
    so any per-line scan (the shape `ingest/checks/banned_words.py` uses) finds
    nothing and passes silently.
    """
    return re.sub(r"\s+", " ", text)


def _storage_bullets() -> list[str]:
    """The <li> items of the "When accounts ship" list on /threat-model."""
    flat = _flat(_page("threat-model.astro"))
    start = flat.index("When accounts ship")
    block = flat[start : flat.index("<h2", start + 1)]
    return re.findall(r"<li>(.*?)</li>", block)


def _repo_sql() -> list[Path]:
    skip = {"node_modules", ".venv", "dist", ".git"}
    return [p for p in repo_root().rglob("*.sql") if not skip & set(p.parts)]


def test_rendered_k_threshold_equals_config_k_anon() -> None:
    # §10.3 + the V2-7 acceptance: the number the reader is shown IS the gate.
    flat = _flat(_page("threat-model.astro"))
    stated = re.findall(r"cover at least (\d+) people", flat)
    assert stated == [str(config.K_ANON)], (
        f"/threat-model states k={stated}, config.K_ANON={config.K_ANON}. "
        "Fix the page text or fix the constant — never this test."
    )


def test_k_anon_is_defined_once_in_python() -> None:
    # A second definition is how the page and the gate drift apart silently.
    hits = sorted(
        path.relative_to(repo_root()).as_posix()
        for path in (repo_root() / "ingest").rglob("*.py")
        if re.search(r"^K_ANON\s*[:=]", path.read_text(encoding="utf-8"), re.MULTILINE)
    )
    assert hits == ["ingest/config.py"], f"K_ANON must have one definition; found {hits}"


def test_storage_list_states_one_item_per_spec_table() -> None:
    # Spec §5 names six D1 tables; the page describes six things. A seventh
    # table without a seventh bullet is collection the reader was not told about.
    bullets = _storage_bullets()
    assert len(bullets) == len(SPEC_TABLES), (
        f"/threat-model lists {len(bullets)} stored things; spec §5 names "
        f"{len(SPEC_TABLES)} tables {SPEC_TABLES}. Fix the page or the spec."
    )


def test_spec_still_names_the_six_tables_the_page_describes() -> None:
    # The page's bullets are prose, so the bullet-to-table mapping lives in this
    # file's header. If the spec renames or drops a table, that mapping is stale
    # and the page may be describing storage that no longer exists.
    spec = (repo_root() / "IMPLEMENTATIONv2.md").read_text(encoding="utf-8")
    missing = [t for t in SPEC_TABLES if f"{t}(" not in spec]
    assert not missing, f"spec §5 no longer names {missing}; the storage list mapping is stale"


def test_promises_sd34_kept_are_still_stated() -> None:
    # SD-34 withdrew the no-tracking guarantees and explicitly kept these three.
    # Each needs its own dated decision to remove (docs/decisions.md SD-34).
    flat = _flat(_page("threat-model.astro"))
    assert "never sold" in flat, "the one standing promise is missing"
    assert "Deletion is real deletion" in flat, "SD-34 kept hard deletion; the page dropped it"
    assert "removes its rows" in flat, "hard deletion must stay stated as row removal"
    assert "cover at least" in flat, "SD-34 kept the K-anon render gate; the page dropped it"
    # Argon2id is NOT claimed on the site on purpose — the page says it in plain
    # words instead. Pin the plain-words version, and pin that the spec still
    # specifies the algorithm, so neither half drifts.
    assert "scrambled form of your password" in flat
    spec = (repo_root() / "IMPLEMENTATIONv2.md").read_text(encoding="utf-8")
    assert "argon2id" in spec.lower(), "SD-34 kept Argon2id; the spec no longer specifies it"


def test_withdrawn_guarantees_are_not_reasserted() -> None:
    # SD-34: never write these onto the site again.
    offenders: list[str] = []
    for path in (repo_root() / "site" / "src").rglob("*"):
        if path.suffix not in SCANNED_SUFFIXES or not path.is_file():
            continue
        flat = _flat(path.read_text(encoding="utf-8", errors="replace"))
        offenders += [
            f"{path.relative_to(repo_root()).as_posix()}: {claim}"
            for claim in WITHDRAWN_CLAIMS
            if claim in flat
        ]
    assert not offenders, f"SD-34-withdrawn claims are back on the site: {offenders}"


def test_privacy_page_links_to_the_threat_model() -> None:
    # The storage list and the K number live on /threat-model, so /privacy is
    # only accurate while it points there. D97's lesson: an orphaned page is a
    # page nobody reads.
    assert '"/threat-model"' in _page("privacy.astro")


def test_schema_half_is_still_deferred() -> None:
    """The acceptance's schema comparison, written so it activates by itself.

    Two blockers, not one: V2-8 has not created the D1 schema, and the
    canonical table list is unratified (§5 says six; the subscriptions plan's
    task 1 adds `email_verifications`, which is on neither §5 nor the page).
    """
    sql = _repo_sql()
    if not sql:
        pytest.skip(
            "deferred twice over: V2-8 has not created the D1 schema (no .sql, no "
            "worker/, no d1_databases in site/wrangler.jsonc), and the canonical "
            "table list is unratified — spec §5 names 6 tables, "
            "docs/plan-subscriptions-and-alerts.md task 1 adds email_verifications. "
            "Ratify the list before comparing against it."
        )
    declared: set[str] = set()
    for path in sql:
        declared |= {
            name.lower()
            for name in re.findall(
                r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"'`\[]?(\w+)",
                path.read_text(encoding="utf-8"),
                re.IGNORECASE,
            )
        }
    assert declared == set(SPEC_TABLES), (
        f"D1 schema declares {sorted(declared)}; the privacy surface describes "
        f"{sorted(SPEC_TABLES)}. Fix the page or the schema — never this test."
    )
