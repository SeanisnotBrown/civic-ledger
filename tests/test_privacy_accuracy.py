"""The privacy surface says what the code and config actually say.

`IMPLEMENTATIONv3.md` §4.8: *"The site collects what its features need. The
privacy page states plainly what is collected and how it is used. It makes no
promises."* §1 rule 0 makes the page's accuracy blocking: site copy that
describes the system is copy that can be false, and it flips in the same commit
as the feature that makes it true.

These tests are a grep-style accuracy check. On failure: site text and system
diverged — fix the text or fix the system, never the test.

What they pin, in order of how much damage getting them wrong would do:

1. **The K number the reader is shown is the K the system enforces.** Both
   pages interpolate `K_ANON_PUBLISH_FLOOR` from
   `site/src/lib/storageDisclosure.ts`, so `site/` holds exactly one literal
   and this test pins that literal to `config.K_ANON`, the constant that
   governs the export gate. Lower `K_ANON` to 25 and the page becomes a false
   statement about privacy — the worst class of bug this project can ship
   (rule 0).
2. **The storage list keeps one item per table that will exist**, and each
   item says what the thing is used for. §3.2 names seven D1 tables for
   accounts and alerts; the shared list describes seven things in plain words.
   An eighth table arriving without an eighth sentence is undisclosed
   collection.
3. **The withdrawn promises stay withdrawn.** The owner withdrew the
   never-sell promise itself on 2026-10-07 (§2 "Never-sell"), along with the
   earlier no-tracking guarantees and the "collect as little as possible"
   line. Each is matched as the *claim* it was, not as a topic —
   `/threat-model` legitimately discusses cookies and onward sale in its "what
   is not promised" section, which is the opposite of promising.
4. **What §4.8 owes `/privacy` is actually on `/privacy`** — what is collected
   today, the storage list with a use per item, the public-profile carve-out,
   deletion semantics, and the email sender named.

**One list, two pages.** `/privacy` is the short version of the disclosure and
`/threat-model` the long one; both carry the storage list and the K number.
Two hand-maintained copies of a disclosure list drift, and a privacy surface
that disagrees with itself is the rule 0 failure this file exists to prevent —
so the list lives in `site/src/lib/storageDisclosure.ts` and both pages render
it. These tests therefore pin three joins rather than one: module → spec §3.2,
module → `config.K_ANON`, and each page → the module.

Scope caveat — **half of the acceptance still cannot be written.** It compares
the stated list against the Worker's D1 schema, which Phase 7 creates; there is
no `worker/`, no `.sql`, and no `d1_databases` binding in `site/wrangler.jsonc`
today. `test_schema_half_is_still_deferred` activates by itself when any `.sql`
appears.

These tests read the committed `site/src/` **source**, not `site/dist/`: in CI
the Python job runs before the Node job's `npm run build`, so `dist/` does not
exist when pytest runs. The site-copy guards that do scan `dist/` are the
`npm run test:*` scripts (`site/scripts/check-grade-labels.mjs` is the
precedent for the render-side half of this pair).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ingest import config
from ingest.cache import repo_root

SPEC = "IMPLEMENTATIONv3.md"

# The D1 tables `IMPLEMENTATIONv3.md` §3.2 names on the "Accounts / alerts"
# row. `storageDisclosure.ts` carries one sentence per table and tags each with
# its table name, so the row-to-table mapping is machine-checked rather than
# living in this docstring.
SPEC_TABLES: frozenset[str] = frozenset(
    {
        "users",
        "email_verifications",
        "preferences",
        "subscriptions",
        "deliveries",
        "channels",
        "profiles",
    }
)

# Claims the owner withdrew. These were live copy once; they must never come
# back without a dated decision reversing the withdrawal. The never-sell pair
# is the 2026-10-07 withdrawal (§2): the owner withdrew the promise itself, not
# only the sentence, so no wording of it may return.
WITHDRAWN_CLAIMS: tuple[str, ...] = (
    "never sold",
    "never sell",
    "collect as little as possible",
    "No cookies. No analytics",
    "No third-party fonts, scripts, or CDNs",
    "would produce only what that private repository contains",
)

SCANNED_SUFFIXES = frozenset({".astro", ".ts", ".tsx", ".md", ".mdx"})

# Both pages of the privacy surface. Everything the surface states has to be on
# both: a reader who lands on one of them is owed the same facts.
PRIVACY_PAGES: tuple[str, ...] = ("privacy.astro", "threat-model.astro")

DISCLOSURE_MODULE = Path("site") / "src" / "lib" / "storageDisclosure.ts"


def _page(name: str) -> str:
    return (repo_root() / "site" / "src" / "pages" / name).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Collapse whitespace so a claim that wraps across source lines still matches.

    Load-bearing: the K sentence is split as "...at least\n      50 people...",
    so any per-line scan (the shape `ingest/checks/banned_words.py` uses) finds
    nothing and passes silently.
    """
    return re.sub(r"\s+", " ", text)


def _disclosure_source(*, strip_comments: bool) -> str:
    text = (repo_root() / DISCLOSURE_MODULE).read_text(encoding="utf-8")
    if not strip_comments:
        return text
    # The header comment names tables and quotes shipped wording on purpose.
    # Strip it so a table named only in prose cannot satisfy a disclosure test.
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def _disclosed_tables() -> list[str]:
    return re.findall(r'table:\s*"(\w+)"', _disclosure_source(strip_comments=True))


def _disclosed_texts() -> list[str]:
    return re.findall(r'text:\s*"((?:[^"\\]|\\.)*)"', _disclosure_source(strip_comments=True))


def _spec_text() -> str:
    return (repo_root() / SPEC).read_text(encoding="utf-8")


def _repo_sql() -> list[Path]:
    skip = {"node_modules", ".venv", "dist", ".git"}
    return [p for p in repo_root().rglob("*.sql") if not skip & set(p.parts)]


def test_rendered_k_threshold_equals_config_k_anon() -> None:
    # The number the reader is shown IS the gate the export step enforces.
    stated = re.findall(
        r"K_ANON_PUBLISH_FLOOR\s*=\s*(\d+)", _disclosure_source(strip_comments=True)
    )
    assert stated == [str(config.K_ANON)], (
        f"{DISCLOSURE_MODULE.as_posix()} publishes k={stated}, "
        f"config.K_ANON={config.K_ANON}. "
        "Fix the page text or fix the constant — never this test."
    )


def test_both_pages_render_the_k_floor_from_the_module() -> None:
    # A page that hardcodes the number again is a second literal, and a second
    # literal is how the page and the gate drift apart silently.
    for name in PRIVACY_PAGES:
        flat = _flat(_page(name))
        assert "{K_ANON_PUBLISH_FLOOR}" in flat, (
            f"/{name} does not interpolate the shared K floor; it must not "
            "state the number on its own."
        )
        assert not re.search(r"at least \d+ people", flat), (
            f"/{name} hardcodes a K number. Render "
            "{K_ANON_PUBLISH_FLOOR} from storageDisclosure.ts instead."
        )


def test_k_anon_is_defined_once_in_python() -> None:
    # A second definition is how the page and the gate drift apart silently.
    hits = sorted(
        path.relative_to(repo_root()).as_posix()
        for path in (repo_root() / "ingest").rglob("*.py")
        if re.search(r"^K_ANON\s*[:=]", path.read_text(encoding="utf-8"), re.MULTILINE)
    )
    assert hits == ["ingest/config.py"], f"K_ANON must have one definition; found {hits}"


def test_k_floor_is_defined_once_in_the_site() -> None:
    hits = sorted(
        path.relative_to(repo_root()).as_posix()
        for path in (repo_root() / "site" / "src").rglob("*")
        if path.suffix in SCANNED_SUFFIXES
        and path.is_file()
        and re.search(
            r"K_ANON_PUBLISH_FLOOR\s*=", path.read_text(encoding="utf-8", errors="replace")
        )
    )
    assert hits == [DISCLOSURE_MODULE.as_posix()], (
        f"the site's K floor must have one definition; found {hits}"
    )


def test_storage_list_states_one_item_per_spec_table() -> None:
    # §3.2 names seven D1 tables; the shared list describes seven things. An
    # eighth table without an eighth sentence is collection the reader was not
    # told about.
    tables = _disclosed_tables()
    assert len(tables) == len(set(tables)), f"duplicate table in the list: {tables}"
    assert set(tables) == SPEC_TABLES, (
        f"{DISCLOSURE_MODULE.as_posix()} discloses {sorted(tables)}; {SPEC} §3.2 names "
        f"{sorted(SPEC_TABLES)}. Fix the page or the spec."
    )
    texts = _disclosed_texts()
    assert len(texts) == len(tables), (
        f"{len(tables)} tables but {len(texts)} sentences — every table needs "
        "exactly one sentence the reader can read."
    )
    assert all(t.strip() for t in texts), "a disclosed table has an empty sentence"


def test_every_disclosed_item_says_what_it_is_used_for() -> None:
    # §4.8 owes the reader two things per item: what is collected AND how it is
    # used. A sentence that only names the data is half an answer.
    missing = [t for t in _disclosed_texts() if "used" not in t.lower()]
    assert not missing, (
        "every disclosure sentence must state the use of the thing it "
        f"discloses (§4.8); these do not: {missing}"
    )


def test_spec_still_names_the_tables_the_page_describes() -> None:
    # The list's sentences are prose; the `table` field is what ties each one to
    # a table. If the spec renames or drops a table, that tie is stale and the
    # page may be describing storage that no longer exists. §3.2 writes the
    # table names in reader prose ("email verifications"), not in code form.
    spec = _spec_text().lower()
    missing = [t for t in sorted(SPEC_TABLES) if t.replace("_", " ") not in spec]
    assert not missing, f"{SPEC} §3.2 no longer names {missing}; the storage list mapping is stale"


def test_both_pages_render_the_shared_storage_list() -> None:
    # §4.8 requires the table list in plain words on `/privacy`;
    # `/threat-model` is the long version and carries it too. Neither may
    # hand-write a second copy.
    for name in PRIVACY_PAGES:
        flat = _flat(_page(name))
        assert "storageDisclosure" in flat, f"/{name} does not import the storage list"
        assert "STORED_WHEN_ACCOUNTS_SHIP.map" in flat, (
            f"/{name} imports the storage list but does not render it"
        )
        for text in _disclosed_texts():
            assert text not in flat, (
                f"/{name} hand-writes a disclosure sentence that the shared "
                f"module already carries: {text!r}"
            )


def test_both_pages_describe_deletion_and_the_publish_floor() -> None:
    # Neither is a promise; both are descriptions of what the software does,
    # and both are facts the reader of either page is owed. Deletion removes
    # rows; a reader-derived figure below the floor is not written at all.
    for name in PRIVACY_PAGES:
        flat = _flat(_page(name))
        assert "Deletion is real deletion" in flat, (
            f"/{name}: the page no longer describes what deletion does"
        )
        assert "removes its rows" in flat, (
            f"/{name}: deletion must stay described as row removal"
        )
        assert "at least" in flat and "{K_ANON_PUBLISH_FLOOR}" in flat, (
            f"/{name}: the page no longer describes the publish floor"
        )
    # The password algorithm is deliberately not named on the site — the list
    # says it in plain words instead. Pin the plain-words version.
    assert any("scrambled form of your password" in t for t in _disclosed_texts())


def test_privacy_makes_no_promises() -> None:
    # §4.8: "It makes no promises." The page describes; it does not pledge. The
    # word may appear only where the page says what it is NOT doing.
    flat = _flat(_page("privacy.astro"))
    assert "description, not a list of promises" in flat, (
        "/privacy must say plainly that it is a description rather than a promise"
    )
    # Phrasings that make a pledge rather than describe one. The withdrawn
    # never-sell sentence was "the one promise"; the heading went with it.
    for phrasing in ("the one promise", "standing promise", "we promise", "is promised"):
        assert phrasing not in flat.lower(), (
            f"/privacy offers a promise ({phrasing!r}); §4.8 says the page "
            "describes and promises nothing"
        )


def test_privacy_states_what_is_collected_today() -> None:
    # Phase 1 task 2: "what is collected today (nothing beyond server logs at
    # the host)". The host is named, the logs are named, and the page does not
    # claim a visit leaves no record anywhere.
    flat = _flat(_page("privacy.astro"))
    assert "What is collected today" in flat, "/privacy has no today section"
    assert "Cloudflare" in flat, "/privacy does not name the host that holds the logs"
    assert "server logs" in flat, (
        "/privacy does not say the host keeps server logs of the requests your "
        "browser makes"
    )
    assert "no account system yet" in flat, (
        "/privacy does not state that the site itself keeps nothing today"
    )


def test_privacy_states_the_public_profile_carve_out() -> None:
    # The one part of the stored list other people can see. `published_json`'s
    # shape is unspecified, so the page describes the mechanism, never the
    # contents.
    flat = _flat(_page("privacy.astro"))
    assert "anything you choose to publish on your profile" in flat
    assert "is public" in flat


def test_privacy_names_the_email_sender() -> None:
    # `/privacy` names Cloudflare as both the deliverer of the site and the
    # sender of email — one company to disclose rather than two. Written in the
    # planned voice: the choice is decided, not finished (no email sends today).
    flat = _flat(_page("privacy.astro"))
    assert "Cloudflare" in flat, "the email sender is not named"
    assert "send the email" in flat, (
        "/privacy must say who sends the email, not only who delivers the site"
    )


def test_privacy_says_anonymous_reading_needs_no_account() -> None:
    # §4.7: accounts are for readers who want alerts; reading the record is
    # open, and the per-topic feeds need no account either.
    flat = _flat(_page("privacy.astro"))
    assert "needs no account" in flat
    assert "feed" in flat


def test_withdrawn_guarantees_are_not_reasserted() -> None:
    # The never-sell promise and the earlier no-tracking guarantees are
    # withdrawn. Never write these onto the site again. This is also the
    # mechanical half of the Phase 1 acceptance grep.
    offenders: list[str] = []
    for path in (repo_root() / "site" / "src").rglob("*"):
        if path.suffix not in SCANNED_SUFFIXES or not path.is_file():
            continue
        flat = _flat(path.read_text(encoding="utf-8", errors="replace"))
        offenders += [
            f"{path.relative_to(repo_root()).as_posix()}: {claim}"
            for claim in WITHDRAWN_CLAIMS
            if claim.lower() in flat.lower()
        ]
    assert not offenders, f"withdrawn claims are back on the site: {offenders}"


def test_privacy_page_links_to_the_threat_model() -> None:
    # The long version carries what a legal demand produces and what is no
    # longer claimed, so `/privacy` is only complete while it points there. An
    # orphaned page is a page nobody reads.
    assert '"/threat-model"' in _page("privacy.astro")


def test_schema_half_is_still_deferred() -> None:
    """The schema comparison, written so it activates by itself.

    One blocker left: Phase 7 has not created the D1 schema. The table list is
    not a blocker — `IMPLEMENTATIONv3.md` §3.2 names the seven tables.
    """
    sql = _repo_sql()
    if not sql:
        pytest.skip(
            "deferred: Phase 7 (accounts, topics, alerts) has not created the "
            "D1 schema — no .sql, no worker/, no d1_databases in "
            "site/wrangler.jsonc. Nothing else blocks it; IMPLEMENTATIONv3.md "
            "§3.2 names the seven tables. Phase 7 also owes a test pinning "
            "each retention period to the spec, the same shape as the K floor."
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
