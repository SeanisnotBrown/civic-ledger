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
