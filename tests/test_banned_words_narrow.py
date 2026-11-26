"""The faster banned-words scan must be the same check, not a weaker one.

`ingest/checks/banned_words.py` now asks "can this file hold any hit?" with one
whole-text pass before running the exact per-line scan. These tests pin the
promise that makes that safe:

* every published surface (data/**, site/src/**, site/dist/**) is still read in
  full, for every scanned suffix;
* a planted banned word on each surface still fails;
* on a fixture set the new `find_hits` returns exactly what the original
  algorithm returned (same hits, same order);
* the prefilter never calls a file clean when the exact scan would flag it.

`_reference_find_hits` below is the ORIGINAL algorithm, copied verbatim in
behaviour (read_text + per-line x per-pattern), so it stays an independent
yardstick even if the module is optimised further.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

import pytest

from ingest.checks import banned_words
from ingest.checks.banned_words import (
    _PATTERNS,
    BANNED,
    SCAN_DIRS,
    TEXT_SUFFIXES,
    _iter_text_files,
    _maybe_has_hit,
    _scan_text,
    find_hits,
)


def _reference_find_hits(root: Path) -> list[tuple[str, int, str]]:
    """The pre-narrowing algorithm: every pattern against every line of every file."""
    hits: list[tuple[str, int, str]] = []
    for path, relposix in _iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern, term in _PATTERNS:
                if pattern.search(line):
                    hits.append((relposix, lineno, term))
    return hits


def _write(root: Path, rel: str, content: str | bytes) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8", newline="")


SURFACES = ("data/members", "site/src/pages", "site/dist/m/x")


# --- every published surface is scanned --------------------------------------


def test_scan_dirs_are_still_the_three_published_trees():
    assert SCAN_DIRS == ("data", "site/src", "site/dist")


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("suffix", sorted(TEXT_SUFFIXES))
def test_planted_word_fails_on_every_surface_and_suffix(tmp_path, surface, suffix):
    _write(tmp_path, f"{surface}/deep/er/page{suffix}", "ok line\nthis is hypocrisy\nok\n")
    assert find_hits(tmp_path) == [(f"{surface}/deep/er/page{suffix}", 2, "hypocrisy")]


@pytest.mark.parametrize("term", BANNED)
@pytest.mark.parametrize("surface", SURFACES)
def test_every_banned_term_fails_on_every_surface(tmp_path, term, surface):
    _write(tmp_path, f"{surface}/f.json", f'{{"note": "a {term.upper()}!"}}\n')
    assert [(h[1], h[2]) for h in find_hits(tmp_path)] == [(1, term)]


@pytest.mark.parametrize(
    "rel",
    [
        "data/statements/s1.json",  # AI-written text, once approved and exported
        "data/absences/m--h-118-1-0001.json",
        "data/state/ms/bills/b.json",
        "site/src/content/notes.md",
        "site/dist/index.html",
    ],
)
def test_ai_and_site_text_surfaces_are_scanned(tmp_path, rel):
    _write(tmp_path, rel, '{"text": "he is a liar"}')
    assert [h[0] for h in find_hits(tmp_path)] == [rel]


def test_every_in_scope_file_is_read_in_full(tmp_path, monkeypatch):
    # The prefilter may skip the per-line loop, never the read: each file the
    # walker yields must be opened and decoded, so no published text goes unseen.
    for i, surface in enumerate(SURFACES):
        _write(tmp_path, f"{surface}/clean{i}.json", '{"a": 1}')
    seen: list[str] = []
    real = Path.read_bytes

    def spy(self):
        seen.append(self.relative_to(tmp_path).as_posix())
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", spy)
    find_hits(tmp_path)
    expected = [rel for _, rel in _iter_text_files(tmp_path)]
    assert sorted(seen) == sorted(expected) and len(expected) == len(SURFACES)


def test_exclusions_and_allowlist_unchanged(tmp_path):
    for rel in (
        "data/raw/x.json",
        "data/quality/samples/x.json",
        "data/quality/absence-queue/x.json",
        "site/src/content/glossary.md",
        "data/members/skipped.xml",  # suffix not in TEXT_SUFFIXES, as before
        "repo-root.md",
    ):
        _write(tmp_path, rel, "hypocrisy")
    assert find_hits(tmp_path) == []


# --- same answers as the original algorithm ----------------------------------


def _fixture_tree(root: Path) -> None:
    _write(root, "data/a.json", '{"x": "Hypocrisy and a HYPOCRITE, a LiAr", "y": "Flip-Flop"}\n')
    _write(root, "data/b.json", "clean\r\nbroke his promise\r\nclean\r\n")  # CRLF
    _write(root, "data/c.json", "one\rtwo contradicts\rthree\r")  # lone CR
    # U+2028/U+2029/form feed are line breaks to str.splitlines
    _write(root, "data/d.json", "a\u2028b lied about\u2029c flipflop\x0cd flip flop\n")
    _write(root, "data/e.json", "\ufeffcontradiction here\n")  # BOM
    _write(root, "data/f.json", b"ok \xff\xfe liar \xc3 end\n")  # invalid UTF-8 -> replaced
    _write(root, "data/g.json", "liar liar liar\nliar\n")  # same term repeated on a line
    _write(root, "data/h.json", "broke his\npromise\nflip\nflop\n")  # phrase split across lines
    _write(root, "data/i.json", "Auxiliary familiar peculiar conciliar liars\n")  # whole-word only
    _write(root, "data/j.json", "caf\u00e9 \u00fcber liar na\u00efve contradicts\n")
    _write(root, "data/k.json", "caf\u00e9 clean text only\n")
    _write(root, "data/l.json", "broKe her promise\n")  # KELVIN SIGN folds to k
    _write(root, "data/m.json", "contradicts\u017f\n\u017f is long s; hypocri\u017fy\n")  # U+017F
    minified = ", ".join('"lied about"' for _ in range(50))
    _write(root, "data/n.json", '{"minified": [' + minified + "]}")
    _write(root, "data/o.json", "")  # empty
    _write(root, "data/p.json", "x" * 100_000 + " flipflop " + "y" * 100_000)  # long single line
    _write(root, "site/src/pages/q.astro", "<p>contradicts</p>\n<p>fine</p>\n")
    _write(root, "site/dist/r.html", "<html>hypocrite</html>")
    _write(root, "site/dist/s.css", "a{color:red}")
    _write(root, "data/raw/t.json", "liar")  # excluded
    _write(root, "site/src/content/glossary.md", "contradiction")  # allowlisted


def test_find_hits_equals_the_original_algorithm_on_the_fixture_set(tmp_path):
    _fixture_tree(tmp_path)
    expected = _reference_find_hits(tmp_path)
    assert expected, "fixture must contain hits or the comparison proves nothing"
    assert find_hits(tmp_path) == expected  # same hits AND same order


def test_nothing_that_failed_before_passes_now(tmp_path):
    _fixture_tree(tmp_path)
    before = {(p, line) for p, line, _ in _reference_find_hits(tmp_path)}
    after = {(p, line) for p, line, _ in find_hits(tmp_path)}
    assert before <= after


def test_clean_tree_is_clean_in_both(tmp_path):
    _write(tmp_path, "data/a.json", '{"a": "nothing to see"}')
    _write(tmp_path, "site/dist/index.html", "<p>hello</p>")
    assert find_hits(tmp_path) == _reference_find_hits(tmp_path) == []


_FRAGMENTS = (
    list(BANNED)
    + [t.upper() for t in BANNED]
    + [t.title() for t in BANNED]
    + ["liars", "familiar", "Auxiliary", "contradictory", "broke", "his", "promise", "flip", "flop"]
    + ["contradict", "hypocri", "lied abo", "broke h", "flip-", "li"]  # partial words
    + ["\u212a", "\u017f", "\u0131", "\u00e9", "\u4e2d", "\u2028"]
    + ["\r\n", "\n", "\r", " ", "-", "_", "1", ".", "x"]
)


@pytest.mark.parametrize(
    "text",
    [
        "contradict\u017f",  # long s: IGNORECASE folds it to s, str.lower() does not
        "hypocri\u017fy",
        "bro\u212ae his promise",  # Kelvin sign folds to k
        "bro\u212ae her promise",
        "FL\u0131P-FLOP",  # dotless i: compare against the exact scan, whatever it says
        "l\u0131ar",
    ],
)
def test_case_folded_lookalikes_agree_with_the_original(tmp_path, text):
    # Each variant sits ALONE in its file, so a prefilter that wrongly calls
    # non-ASCII text clean cannot hide behind a plain banned word elsewhere.
    _write(tmp_path, "data/x.json", text + "\n")
    assert find_hits(tmp_path) == _reference_find_hits(tmp_path)


def test_at_least_one_folded_lookalike_is_a_real_hit(tmp_path):
    # Guards the test above against passing vacuously (all-clean on both sides).
    _write(tmp_path, "data/x.json", "contradict\u017f\n")
    assert [h[2] for h in find_hits(tmp_path)] == ["contradicts"]


def test_fold_character_set_is_complete_over_all_of_unicode():
    # The ASCII fast path is only safe if `_fold_chars()` lists EVERY non-ASCII
    # character IGNORECASE can match to a term character. Re-derive it here from
    # each term's own compiled pattern (an independent route to the same answer)
    # and require the module's set to match, plus the known members.
    letters = sorted(set("".join(BANNED)))
    singles = [re.compile(re.escape(c), re.IGNORECASE) for c in letters]
    expected = {
        chr(cp)
        for cp in range(128, 0x110000)
        if any(rx.fullmatch(chr(cp)) for rx in singles)
    }
    assert set(banned_words._fold_chars()) == expected
    assert {"ſ", "K"} <= expected  # long s, Kelvin sign


def test_only_fold_characters_change_length_under_lower():
    # The fast path relies on `str.lower()` keeping characters one-for-one so a
    # term cannot be split or merged by it.
    folds = set(banned_words._fold_chars())
    for cp in range(128, 0x110000):
        ch = chr(cp)
        assert len(ch.lower()) == 1 or ch in folds, hex(cp)


def test_prefilter_never_clears_a_text_the_exact_scan_flags():
    rng = random.Random(20261126)
    flagged = 0
    for _ in range(4000):
        text = "".join(rng.choice(_FRAGMENTS) for _ in range(rng.randint(1, 14)))
        reference = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern, term in _PATTERNS:
                if pattern.search(line):
                    reference.append((lineno, term))
        if reference:
            flagged += 1
            assert _maybe_has_hit(text), repr(text)
        assert _scan_text(text) == reference, repr(text)
    assert flagged > 200  # the fuzz actually produced hits


# --- unchanged output --------------------------------------------------------


def test_main_messages_unchanged(tmp_path, monkeypatch, capsys):
    _write(tmp_path, "data/a.json", "x\nliar\n")
    monkeypatch.setattr(banned_words, "repo_root", lambda: tmp_path)
    assert banned_words.main() == 1
    out = capsys.readouterr().out
    assert "BANNED-WORDS CHECK FAILED \u2014 partisan-lean framing found:" in out
    assert "  data/a.json:2  ->  'liar'" in out


def test_main_ok_message_unchanged(tmp_path, monkeypatch, capsys):
    _write(tmp_path, "data/a.json", "fine")
    monkeypatch.setattr(banned_words, "repo_root", lambda: tmp_path)
    assert banned_words.main() == 0
    assert "banned-words: OK (no partisan-lean framing in scanned trees)" in capsys.readouterr().out
