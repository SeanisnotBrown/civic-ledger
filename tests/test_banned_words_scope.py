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
