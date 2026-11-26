"""Guards on the CI/nightly workflow definitions (R-2).

The roster refresh (`ingest members`) must run BEFORE the vote ingests: the
covered-member set drives vote coverage and the unknown-member alarms, so a
mid-Congress delegation change has to land before the vote parsers read it.
A plain-text ordering assertion keeps the step from being reordered away.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

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


def test_nightly_window_is_since_last_published_with_a_dispatch_override() -> None:
    """2026-11-11: the scheduled run covers everything since the last published
    nightly (`--since-published`); a dispatch `since_hours` is an explicit override
    (owner ruling 2026-10-29's catch-up). The input reaches the script through env,
    never interpolated into it."""
    text = NIGHTLY.read_text(encoding="utf-8")
    dispatch = text[text.index("workflow_dispatch:"):text.index("concurrency:")]
    assert "since_hours:" in dispatch
    assert 'default: ""' in dispatch
    assert "SINCE_HOURS: ${{ github.event.inputs.since_hours || '' }}" in text
    assert 'uv run ingest bill-activity --since "$SINCE_HOURS"' in text
    assert "uv run ingest bill-activity --since-published" in text
    assert 'if [ -n "$SINCE_HOURS" ]; then' in text
    assert "--since ${{" not in text


def _ms_guard_line(text: str) -> str:
    return next(ln.strip() for ln in text.splitlines() if ln.strip().startswith("uv run ingest ms"))


def test_nightly_mississippi_failure_does_not_stop_the_federal_publish() -> None:
    """Owner ruling 2026-11-25 (Q3 = B): a LegiScan/Mississippi failure is logged and
    data/state/ms/ is restored, and the night goes on. Only `ingest ms` is guarded: every
    federal step is still unguarded under `set -e`, and the commit still follows."""
    text = NIGHTLY.read_text(encoding="utf-8")
    guard = _ms_guard_line(text)
    assert guard.startswith("uv run ingest ms || {")
    assert "::warning::" in guard and "federal data still publishes" in guard
    assert "git checkout -- data/state/ms/" in guard
    assert "git clean -fdq -- data/state/ms/" in guard
    assert "set -euo pipefail" in text
    # Every other `uv run ingest ...` and the gates stay bare (a federal failure still
    # fails the night): no other `||` fallback on a run line.
    run_lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("uv run ")]
    assert [ln for ln in run_lines if "||" in ln] == [guard]
    ms = text.index(guard)
    for later in ("uv run ingest classify", "uv run corrections", "uv run export",
                  "uv run checks", "uv run verify-recompute", 'git commit -m "data: nightly'):
        assert text.index(later, ms) > ms, f"{later} must still follow the Mississippi step"


@pytest.mark.skipif(sys.platform == "win32", reason="needs POSIX bash (Windows bash may be WSL)")
@pytest.mark.parametrize("ms_exit", [0, 7])
def test_the_mississippi_guard_restores_last_good_data_and_keeps_going(
    ms_exit: int, tmp_path
) -> None:
    """Run the real guard line under the nightly's `set -euo pipefail` with a stand-in
    `uv`: a failing `ingest ms` that left a half-written partition (an edited tracked
    file and a new one) ends with the committed state back, a warning, and the next
    (federal) command running; a passing one is left alone."""
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    ms = tmp_path / "data" / "state" / "ms"
    ms.mkdir(parents=True)
    (ms / "manifest.json").write_text("good\n", encoding="utf-8")
    votes = tmp_path / "data" / "votes"
    votes.mkdir()
    (votes / "s-1.json").write_text("old\n", encoding="utf-8")
    subprocess.run([*git, "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run([*git, "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "x"], cwd=tmp_path, check=True)

    script = (
        "set -euo pipefail\n"
        "echo federal-new > data/votes/s-1.json\n"  # federal output earlier in the night
        "uv() { echo half > data/state/ms/manifest.json; echo new > data/state/ms/new.json; "
        f"return {ms_exit}; }}\n"
        f"{_ms_guard_line(NIGHTLY.read_text(encoding='utf-8'))}\n"
        "echo FEDERAL-STEP-RAN\n"
    )
    done = subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True)

    assert done.returncode == 0, done.stderr
    assert "FEDERAL-STEP-RAN" in done.stdout
    # Federal output written earlier in the night is untouched, failure or not.
    assert (votes / "s-1.json").read_text(encoding="utf-8") == "federal-new\n"
    if ms_exit:
        assert f"::warning::ingest ms failed (exit {ms_exit})" in done.stdout
        assert (ms / "manifest.json").read_text(encoding="utf-8") == "good\n"
        assert not (ms / "new.json").exists()
    else:
        assert "::warning::" not in done.stdout
        assert (ms / "manifest.json").read_text(encoding="utf-8") == "half\n"
