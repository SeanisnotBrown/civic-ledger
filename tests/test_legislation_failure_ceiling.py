"""The nightly `ingest legislation` failure ceiling (2026-10-08).

Nightly 37652899299 (2026-10-07) died on `FAIL: 3 issue(s): ['G000586: ReadTimeout',
'H001066: ReadTimeout', 'N000193: ReadTimeout']` — three of 639 member requests timing
out, each already retried five times with 2s->60s backoff in `ingest/cache.py`. The
whole night published nothing. `bills`/`bill-activity` had absorbed that case for
months via `config.ACTIVITY_FETCH_FAILURE_*`; `legislation` had no ceiling at all.

These tests pin the split that fixes it:
  * a transient fetch failure at or under max(2, 2% of roster) -> run returns 0 and
    the member keeps its committed record byte-for-byte;
  * over the ceiling -> returns 1 (a systemic failure still stops the night);
  * a count regression -> returns 1 at ANY count, ceiling or no ceiling, because
    bills do not un-sponsor and a drop to zero is a truncation signal (value #1).

Offline: the source module's probe and paginator are monkeypatched; data dir is tmp.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from ingest import legislation
from ingest.sources import congress_gov


def _item(bill_type: str, number: str, congress: int) -> dict:
    return {
        "type": bill_type, "number": number, "congress": congress, "title": "A Bill",
        "introducedDate": "2025-01-01", "latestAction": None,
        "url": f"https://api.congress.gov/v3/bill/{congress}/{bill_type}/{number}?format=json",
    }


def _record(mid: str, counts: dict) -> dict:
    """A committed record holding one 118 bill — the thing a regression would drop."""
    return {
        "member_id": mid,
        "source_url": f"https://api.congress.gov/v3/member/{mid}/sponsored-legislation",
        "sponsored": [{"bill_id": "hr9-118", "congress": 118, "title": "Old",
                       "introduced_date": None, "became_law": False, "enacted_action": None,
                       "source_url": "https://www.congress.gov/bill/118th-congress/house-bill/9"}],
        "cosponsored": [],
        "lifetime_counts": counts,
    }


def _write(rec, out_dir: Path) -> Path:
    from ingest.export import _dumps
    p = out_dir / f"{rec.member_id}.json"
    p.write_text(_dumps(rec.model_dump()), encoding="utf-8", newline="\n")
    return p


def _setup(tmp_path: Path, monkeypatch, *, member_ids: list[str], failing: set[str],
           drop_118: bool = False):
    """Roster of `member_ids`, each with a committed record and moved counts (so every
    member takes the re-page path). Members in `failing` raise ReadTimeout from the
    probe — the real 2026-10-07 shape. `drop_118` makes the fresh parse lose the 118
    bill the committed record holds, which is what `_count_regressions` exists to catch."""
    data = tmp_path / "data"
    (data / "members").mkdir(parents=True)
    (data / "legislation").mkdir()
    for mid in member_ids:
        (data / "members" / f"{mid}.json").write_text(json.dumps({"id": mid}), encoding="utf-8")
        (data / "legislation" / f"{mid}.json").write_text(
            json.dumps(_record(mid, {"sponsored": 5, "cosponsored": 50})), encoding="utf-8")

    import ingest.cache as cache
    import ingest.export as export
    monkeypatch.setattr(cache, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(export, "export_member_legislation",
                        lambda rec, out_dir=None: _write(rec, data / "legislation"))

    def fake_counts(mid):
        if mid in failing:
            raise httpx.ReadTimeout("api.congress.gov timed out")
        return {"sponsored": 6, "cosponsored": 50}  # moved -> re-page

    def fake_pages(mid, kind, congs, **kw):
        if kind.startswith("sponsored"):
            return [_item("hr", "1", 119)] if drop_118 else [
                _item("hr", "1", 119), _item("hr", "9", 118)]
        return [_item("s", "2", 119)]

    monkeypatch.setattr(congress_gov, "member_lifetime_counts", fake_counts)
    monkeypatch.setattr(congress_gov, "member_legislation", fake_pages)
    return data


def test_transient_fetch_failures_under_ceiling_do_not_fail_the_night(
        tmp_path, monkeypatch, capsys):
    """The 2026-10-07 case: a handful of ReadTimeouts, the rest of the roster fine."""
    ids = [f"A{i:06d}" for i in range(10)]
    failing = {ids[0], ids[1]}  # 2 of 10; ceiling is max(2, int(0.02*10)=0) = 2
    data = _setup(tmp_path, monkeypatch, member_ids=ids, failing=failing)
    before = (data / "legislation" / f"{ids[0]}.json").read_text(encoding="utf-8")

    assert legislation.run([]) == 0

    out = capsys.readouterr().out
    assert "2 transient fetch failure(s) (20.00%), at or under the ceiling of 2" in out
    assert "not a failure" in out
    assert "ReadTimeout" in out
    # The failed member published nothing new — its committed record is untouched.
    assert (data / "legislation" / f"{ids[0]}.json").read_text(encoding="utf-8") == before


def test_fetch_failures_over_ceiling_still_fail(tmp_path, monkeypatch, capsys):
    """A systemic failure — a dead key, a bad window — must still stop the night."""
    ids = [f"A{i:06d}" for i in range(10)]
    failing = {ids[0], ids[1], ids[2]}  # 3 > ceiling of 2
    _setup(tmp_path, monkeypatch, member_ids=ids, failing=failing)

    assert legislation.run([]) == 1

    out = capsys.readouterr().out
    assert "FAIL: 3 member(s) failed to fetch" in out
    assert "over the ceiling of 2" in out


def test_count_regression_fails_at_any_count(tmp_path, monkeypatch, capsys):
    """A congress dropping to zero is truncation, never transient: no ceiling applies.
    One regression, zero fetch failures — still a failed run."""
    ids = [f"A{i:06d}" for i in range(10)]
    _setup(tmp_path, monkeypatch, member_ids=ids, failing=set(), drop_118=True)

    assert legislation.run([]) == 1

    out = capsys.readouterr().out
    assert "count regression(s)" in out
    assert "sponsored" in out


def test_regression_outranks_a_tolerated_fetch_failure(tmp_path, monkeypatch, capsys):
    """Both kinds at once: the fetch failures are inside the ceiling, but the
    regression is reported and the run fails — the ceiling must never mask it."""
    ids = [f"A{i:06d}" for i in range(10)]
    _setup(tmp_path, monkeypatch, member_ids=ids, failing={ids[0]}, drop_118=True)

    assert legislation.run([]) == 1

    out = capsys.readouterr().out
    assert "count regression(s)" in out
    # The tolerated-fetch-failure line must not be what decided the exit code.
    assert "not a failure" not in out
