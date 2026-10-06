"""V2-7 acceptance — the privacy surface says what the code and config actually say.

The spec's acceptance for V2-7 (`IMPLEMENTATIONv2.md` §9 V2-7) is a grep-style
accuracy test: *"the deployed privacy page's stated storage list and K constant
match code/config. On failure: the accuracy test failing means site text and
system diverged — fix the text or the system, never the test."*

What these tests exist to pin, in order of how much damage getting them wrong
would do:

1. **The K number the reader is shown is the K the system enforces.** Both
   pages now interpolate `K_ANON_PUBLISH_FLOOR` from
   `site/src/lib/storageDisclosure.ts`, so `site/` holds exactly one literal
   and this test pins that literal to `config.K_ANON`, the constant that
   governs the gate. Lower `K_ANON` to 25 and the page becomes a false claim
   about privacy — the single worst class of bug this project can ship (§0.5).
2. **The storage list keeps one item per table that will exist.** Spec §5
   names seven D1 tables and the shared list describes seven things in plain
   words. An eighth table arriving without an eighth sentence is undisclosed
   collection.
3. **SD-34's withdrawn guarantees stay withdrawn, and the three it did NOT
   withdraw stay stated.** SD-34 (2026-10-05) removed the no-tracking
   promises; it explicitly kept hard deletion, the K-anon render gate, and
   never-selling. Each needs its own dated decision to remove, so a silent
   sweep of any of the three fails here.
4. **The four things V2-7 task 1 owes `/privacy` are actually on `/privacy`**
   — the storage list, the public-profile carve-out in the spec's own words,
   deletion semantics, and the email sender named (SD-36).

**One list, two pages (changed 2026-10-06).** The seven sentences used to be
hand-written `<li>`s inside `threat-model.astro`, and V2-7 task 1 requires the
same list on `/privacy`. Two hand-maintained copies of a disclosure list drift,
and a privacy surface that disagrees with itself is the Value #1 failure this
increment exists to prevent — so the list moved into
`site/src/lib/storageDisclosure.ts` and both pages render it. These tests
therefore pin three joins rather than one: module → spec §5, module →
`config.K_ANON`, and each page → the module.

Scope caveat — **half of the spec's acceptance still cannot be written.** The
acceptance compares the stated list against the *Worker's D1 schema*, which
V2-8 creates; there is no `worker/`, no `.sql`, and no `d1_databases` binding in
`site/wrangler.jsonc` today. `test_schema_half_is_still_deferred` activates by
itself when any `.sql` appears. **The list is no longer unratified:** SD-38
(owner, 2026-10-06) settled the seventh table — `email_verifications` is
disclosed on its own line rather than folded into "your email address" — so
`SPEC_TABLES` below is a ratified list, not a guess.

These tests read the committed `site/src/` **source**, not `site/dist/`: in CI
the Python job runs before the Node job's `npm run build`, so `dist/` does not
exist when pytest runs. The site-copy guards that do scan `dist/` are the
`npm run test:*` scripts (`site/scripts/check-grade-labels.mjs` is the
precedent for the render-side half of this pair).

Note that `/privacy` is now the short version of the disclosure and
`/threat-model` the long one, but both carry the storage list and the K number.
The acceptance's "privacy page" is read as the privacy surface, both pages, and
a test pins the link that joins them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ingest import config
from ingest.cache import repo_root

# The D1 tables spec §5 names under "Account model"
# (IMPLEMENTATIONv2.md "Account model" bullet). `storageDisclosure.ts` carries
# one sentence per table and tags each with its table name, so the
# bullet-to-table mapping is machine-checked rather than living in this
# docstring. Seven since SD-38 (2026-10-06).
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

# Both pages of the privacy surface. Every promise SD-34 kept has to be on
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
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def _disclosed_tables() -> list[str]:
    return re.findall(r'table:\s*"(\w+)"', _disclosure_source(strip_comments=True))


def _disclosed_texts() -> list[str]:
    return re.findall(
        r'text:\s*"((?:[^"\\]|\\.)*)"', _disclosure_source(strip_comments=True)
    )


def _repo_sql() -> list[Path]:
    skip = {"node_modules", ".venv", "dist", ".git"}
    return [p for p in repo_root().rglob("*.sql") if not skip & set(p.parts)]


def test_rendered_k_threshold_equals_config_k_anon() -> None:
    # §10.3 + the V2-7 acceptance: the number the reader is shown IS the gate.
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
        assert not re.search(r"cover at least \d+ people", flat), (
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
    # Spec §5 names seven D1 tables; the shared list describes seven things. An
    # eighth table without an eighth sentence is collection the reader was not
    # told about.
    tables = _disclosed_tables()
    assert len(tables) == len(set(tables)), f"duplicate table in the list: {tables}"
    assert set(tables) == SPEC_TABLES, (
        f"{DISCLOSURE_MODULE.as_posix()} discloses {sorted(tables)}; spec §5 names "
        f"{sorted(SPEC_TABLES)}. Fix the page or the spec."
    )
    texts = _disclosed_texts()
    assert len(texts) == len(tables), (
        f"{len(tables)} tables but {len(texts)} sentences — every table needs "
        "exactly one sentence the reader can read."
    )
    assert all(t.strip() for t in texts), "a disclosed table has an empty sentence"


def test_spec_still_names_the_tables_the_page_describes() -> None:
    # The list's sentences are prose; the `table` field is what ties each one to
    # a table. If the spec renames or drops a table, that tie is stale and the
    # page may be describing storage that no longer exists.
    spec = (repo_root() / "IMPLEMENTATIONv2.md").read_text(encoding="utf-8")
    missing = [t for t in sorted(SPEC_TABLES) if f"{t}(" not in spec]
    assert not missing, f"spec §5 no longer names {missing}; the storage list mapping is stale"


def test_both_pages_render_the_shared_storage_list() -> None:
    # V2-7 task 1 requires the §5 table list in plain words on `/privacy`;
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


def test_promises_sd34_kept_are_still_stated() -> None:
    # SD-34 withdrew the no-tracking guarantees and explicitly kept these three.
    # Each needs its own dated decision to remove (docs/decisions.md SD-34).
    # All three are required on BOTH pages: never-sell because SD-34 says it
    # must appear on `/privacy`, the other two because V2-7 task 1 asks
    # `/privacy` for deletion semantics and the K rule in its own right.
    for name in PRIVACY_PAGES:
        flat = _flat(_page(name))
        assert "never sold" in flat, f"/{name}: the one standing promise is missing"
        assert "Deletion is real deletion" in flat, (
            f"/{name}: SD-34 kept hard deletion; the page dropped it"
        )
        assert "removes its rows" in flat, (
            f"/{name}: hard deletion must stay stated as row removal"
        )
        assert "cover at least" in flat, (
            f"/{name}: SD-34 kept the K-anon render gate; the page dropped it"
        )
    # Argon2id is NOT claimed on the site on purpose — the list says it in plain
    # words instead. Pin the plain-words version, and pin that the spec still
    # specifies the algorithm, so neither half drifts.
    assert any("scrambled form of your password" in t for t in _disclosed_texts())
    spec = (repo_root() / "IMPLEMENTATIONv2.md").read_text(encoding="utf-8")
    assert "argon2id" in spec.lower(), "SD-34 kept Argon2id; the spec no longer specifies it"


def test_privacy_states_the_public_profile_carve_out() -> None:
    # V2-7 task 1 quotes the required sentence itself, in bold: *"anything you
    # choose to publish on your profile is public"*. `published_json`'s shape is
    # unspecified, so the page describes the mechanism, never the contents.
    flat = _flat(_page("privacy.astro"))
    assert "anything you choose to publish on your profile" in flat
    assert "is public" in flat


def test_privacy_names_the_email_sender() -> None:
    # SD-36: `/privacy` names Cloudflare as both the deliverer of the site and
    # the sender of email — one company to disclose rather than two. Written in
    # the planned voice: H18 is decided, not finished (no email sends today).
    flat = _flat(_page("privacy.astro"))
    assert "Cloudflare" in flat, "the email sender is not named"
    assert "send the email" in flat, (
        "SD-36 requires /privacy to say who sends the email, not only who "
        "delivers the site"
    )


def test_privacy_says_anonymous_reading_needs_no_account() -> None:
    # V2-7 task 1: "that anonymous use and the feeds (V2-11) need no account".
    flat = _flat(_page("privacy.astro"))
    assert "needs no account" in flat
    assert "feed" in flat


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
    # The long version carries what a legal demand produces and what is no
    # longer promised, so `/privacy` is only complete while it points there.
    # D97's lesson: an orphaned page is a page nobody reads.
    assert '"/threat-model"' in _page("privacy.astro")


def test_schema_half_is_still_deferred() -> None:
    """The acceptance's schema comparison, written so it activates by itself.

    One blocker left, not two: V2-8 has not created the D1 schema. The
    canonical table list was the other blocker and SD-38 (2026-10-06) ratified
    it at seven — `email_verifications` disclosed on its own line.
    """
    sql = _repo_sql()
    if not sql:
        pytest.skip(
            "deferred: V2-8 has not created the D1 schema (no .sql, no worker/, "
            "no d1_databases in site/wrangler.jsonc). Nothing else blocks it — "
            "SD-38 ratified the seven tables and SD-39 the three retention "
            "periods (deliveries 90 days, signup code 24 h, reset token 1 h), "
            "both on 2026-10-06. V2-8 also owes a test pinning each of those "
            "three numbers to spec §5, the same shape as the K floor."
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
