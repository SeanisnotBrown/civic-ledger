"""Lock the INC-1 ADR: banned_words scans published data but EXCLUDES the raw
upstream captures in data/quality/samples/ (verbatim government responses, not
platform framing). A future refactor must not silently re-include them and turn
CI red on Congressional floor speech.
"""

from __future__ import annotations

from ingest.checks import banned_words


def _seed(root, relpath: str, text: str):
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def test_samples_excluded_but_published_data_scanned(tmp_path):
    # Same banned word in both trees: excluded under samples/, caught elsewhere.
    _seed(tmp_path, "data/quality/samples/crec.txt", "the gentleman contradicts himself")
    _seed(tmp_path, "data/members/x.json", '{"note": "contradicts"}')

    hits = banned_words.find_hits(tmp_path)
    hit_paths = {h[0] for h in hits}

    assert "data/members/x.json" in hit_paths  # published field → caught
    assert "data/quality/samples/crec.txt" not in hit_paths  # raw capture → excluded


def test_exclusion_prefix_is_the_samples_dir():
    assert "data/quality/samples/" in banned_words.EXCLUDE_PREFIXES


def test_raw_cache_excluded(tmp_path):
    # data/raw/ is the gitignored fetch cache (§6.2), not a published field. A
    # large base64 blob coincidentally contains banned substrings; scanning it
    # would be a scope error. (Regression: LegiScan getDataset blob had "liar".)
    _seed(tmp_path, "data/raw/legiscan/blob.json", '{"zip": "xxliarxx"}')
    _seed(tmp_path, "data/members/y.json", '{"note": "liar"}')

    hit_paths = {h[0] for h in banned_words.find_hits(tmp_path)}
    assert "data/raw/legiscan/blob.json" not in hit_paths  # raw cache → excluded
    assert "data/members/y.json" in hit_paths  # published field → still caught
    assert "data/raw/" in banned_words.EXCLUDE_PREFIXES


def test_curated_statement_text_is_scanned(tmp_path):
    # INC-11 acceptance: banned-words must be green on all curated statement text —
    # i.e. statements are PUBLISHED records and ARE scanned (unlike the absence queue).
    _seed(tmp_path, "data/statements/s1.json", '{"text": "the gentleman contradicts himself"}')
    hit_paths = {h[0] for h in banned_words.find_hits(tmp_path)}
    assert "data/statements/s1.json" in hit_paths  # curated text → scanned
    assert not any(p.startswith("data/statements/") for p in banned_words.EXCLUDE_PREFIXES)


def test_banned_terms_match_whole_words_not_substrings(tmp_path):
    # Regression (INC-12): "liar" must not match inside "Auxiliary" / "familiar" /
    # "peculiar" — real MS bill titles carry these. The banned framing words are
    # matched as whole words, but a real standalone "liar" is still caught.
    _seed(tmp_path, "data/state/ms/bills/b.json",
          '{"title": "Junior Auxiliary; a familiar peculiar contradictory matter."}')
    _seed(tmp_path, "data/members/z.json", '{"note": "you are a liar"}')

    hit_paths = {h[0] for h in banned_words.find_hits(tmp_path)}
    assert "data/state/ms/bills/b.json" not in hit_paths  # no substring false positive
    assert "data/members/z.json" in hit_paths  # a real standalone banned word is caught


def test_absence_queue_excluded_but_published_absences_scanned(tmp_path):
    # INC-6 (D25): unapproved verbatim CREC candidates in the review queue are a
    # pre-publication artifact — a member's own words there must not fail CI before
    # the owner has approved them. Once approved they land in data/absences/ and ARE
    # scanned.
    _seed(tmp_path, "data/quality/absence-queue/CREC-x.json", '{"verbatim_text": "contradicts"}')
    _seed(tmp_path, "data/absences/m--h-118-1-0001.json", '{"stated_reason": "contradicts"}')

    hit_paths = {h[0] for h in banned_words.find_hits(tmp_path)}
    assert "data/quality/absence-queue/CREC-x.json" not in hit_paths  # queue → excluded
    assert "data/absences/m--h-118-1-0001.json" in hit_paths  # published → caught
    assert "data/quality/absence-queue/" in banned_words.EXCLUDE_PREFIXES
