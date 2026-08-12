"""Guards on the CI/nightly workflow definitions (R-2).

The roster refresh (`ingest members`) must run BEFORE the vote ingests: the
covered-member set drives vote coverage and the unknown-member alarms, so a
mid-Congress delegation change has to land before the vote parsers read it.
A plain-text ordering assertion keeps the step from being reordered away.
"""

from __future__ import annotations

from ingest.cache import repo_root

NIGHTLY = repo_root() / ".github" / "workflows" / "nightly.yml"


def test_nightly_refreshes_roster_before_votes() -> None:
    text = NIGHTLY.read_text(encoding="utf-8")
    members = text.index("uv run ingest members")
    house = text.index("uv run ingest house-votes")
    senate = text.index("uv run ingest senate-votes")
    assert members < house < senate, "roster refresh must precede the vote ingests"
