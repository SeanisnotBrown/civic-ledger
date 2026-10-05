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


def test_nightly_fetches_the_bill_activity_delta_before_the_projections() -> None:
    """V2-11 task 8 (SD-33 decision 6: daily digest, carried by this nightly).

    Three orderings in one assertion, each load-bearing:
      * after `ingest bills` — a newly-voted bill exists before the delta
        refreshes it, and the /actions responses `ingest bills` just fetched are
        still in the raw cache, so the voted bills cost zero extra requests;
      * before `ingest legislation` — the Sunday `--full` re-page (~3.5 h) must
        not shift this step's wall-clock, or consecutive runs drift apart and the
        30 h window stops covering the 24 h cron;
      * before `ingest events` / `ingest topics`, which PROJECT data/bills into
        data/events and data/topics (verify-recompute invariants 8 and 9) — a
        delta landing after them commits a stale projection and fails the push.
    """
    text = NIGHTLY.read_text(encoding="utf-8")
    bills = text.index("uv run ingest bills")
    # `--since` pinned, not a bare call: it is what makes the nightly's window
    # explicit at the call site, and `--congress` here would exit 2 (no backfill
    # in CI, D90).
    activity = text.index("uv run ingest bill-activity --since")
    legislation = text.index("uv run ingest legislation")
    events = text.index("uv run ingest events")
    topics = text.index("uv run ingest topics")
    assert bills < activity < legislation, (
        "the bill-activity delta runs after `ingest bills` and before `ingest "
        "legislation`"
    )
    assert activity < events < topics, (
        "the delta must land before the data/events and data/topics projections"
    )
