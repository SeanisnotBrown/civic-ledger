"""senate.gov block on the vote menus (owner ruling 2026-10-29).

From 2026-10-24 senate.gov's firewall returned 403 to the nightly runner, and the
failing `senate-votes` stopped every night from publishing anything. Option A: a run
whose ONLY failures are HTTP status errors on the vote menus exits 0 and keeps
data/quality/senate-outage.json (the site's reader line is built from it); anything
else stays fatal; the first success deletes the notice; past
config.SENATE_MENU_OUTAGE_MAX_DAYS the run fails hard again. Offline: no network, no
writes outside tmp_path.
"""

from __future__ import annotations

import json

import httpx
import pytest

from ingest import config, export, incremental, senate_votes
from ingest.sources import senate_xml

LAST = {
    "id": "s-119-2-0256",
    "date": "2026-09-30T21:29:00",
    "source_url": senate_xml.detail_url(119, 2, 256),
}


class _Text:
    def __init__(self, text): self.text = text


def _status(code: int, url: str = "https://www.senate.gov/x.xml") -> httpx.HTTPStatusError:
    req = httpx.Request("GET", url)
    return httpx.HTTPStatusError(
        f"{code}", request=req, response=httpx.Response(code, request=req)
    )


def _raise(exc):
    def f(*_a, **_k):
        raise exc
    return f


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Two covered menus (119/1, 119/2), the repo rooted in tmp_path, one Senate roll
    on disk, today pinned to 2026-10-29."""
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    votes = tmp_path / "data" / "votes"
    votes.mkdir(parents=True)
    (votes / f"{LAST['id']}.json").write_text(
        json.dumps({"rollcall": LAST, "member_votes": []}), encoding="utf-8"
    )
    monkeypatch.setattr(export, "VOTES_DIR", votes)
    monkeypatch.setattr(config, "CONGRESSES", [119])
    monkeypatch.setattr(senate_votes, "SESSIONS", {119: (1, 2)})
    monkeypatch.setattr(senate_votes, "_today", lambda: "2026-10-29")
    monkeypatch.setattr(incremental, "accepted_quarantines", lambda *a, **k: {})
    return tmp_path


def _notice(root):
    return root / "data" / "quality" / "senate-outage.json"


def test_menu_403_only_exits_0_and_writes_the_notice(repo, monkeypatch, capsys):
    monkeypatch.setattr(senate_xml, "vote_menu", _raise(_status(403)))

    assert senate_votes.run() == 0
    path = _notice(repo)
    first = path.read_bytes()
    assert json.loads(first) == {
        "outage_start": "2026-10-29",
        "last_roll_id": "s-119-2-0256",
        "last_roll_date": "2026-09-30",
        "source_url": LAST["source_url"],
    }
    assert first.endswith(b"}\n") and b"\r" not in first
    assert "WARN: senate.gov refused 2 vote menu(s)" in capsys.readouterr().out

    # The next blocked night keeps the first night as the start: no daily churn.
    monkeypatch.setattr(senate_votes, "_today", lambda: "2026-10-30")
    assert senate_votes.run() == 0
    assert path.read_bytes() == first


@pytest.mark.parametrize(
    "case",
    ["menu_timeout", "detail_403", "tally_mismatch"],
)
def test_a_menu_block_mixed_with_any_other_failure_is_still_fatal(case, repo, monkeypatch):
    """Only HTTP status errors on the menus are tolerated: a menu timeout, a 403 on a
    roll's detail, or a validation failure still fails the night."""
    def menu(c, s):
        if s == 1:
            raise _status(403)
        if case == "menu_timeout":
            raise httpx.ConnectTimeout("timed out")
        return _Text("<menu/>")

    monkeypatch.setattr(senate_xml, "vote_menu", menu)
    monkeypatch.setattr(senate_xml, "parse_menu", lambda text: {1: (60, 40)})
    monkeypatch.setattr(incremental, "roll_is_final", lambda *a, **k: False)
    monkeypatch.setattr(senate_votes, "_quarantine", lambda rc_id, err: None)
    if case == "detail_403":
        monkeypatch.setattr(senate_xml, "vote_detail", _raise(_status(403)))
    else:
        detail = "<roll_call><vote_date>October 1, 2026,  10:00 AM</vote_date></roll_call>"
        monkeypatch.setattr(senate_xml, "vote_detail", lambda c, s, r: _Text(detail))
        monkeypatch.setattr(
            senate_votes, "parse_rollcall", _raise(senate_votes.TallyMismatch("x"))
        )

    assert senate_votes.run() == 1
    assert _notice(repo).exists(), "the block itself is still recorded"


def test_success_after_an_outage_deletes_the_notice(repo, monkeypatch):
    path = _notice(repo)
    path.parent.mkdir(parents=True)
    path.write_text('{"outage_start": "2026-10-24"}\n', encoding="utf-8")
    monkeypatch.setattr(senate_xml, "vote_menu", lambda c, s: _Text("<menu/>"))

    assert senate_votes.run() == 0
    assert not path.exists()


@pytest.mark.parametrize(
    "today,rc", [("2026-11-07", 0), ("2026-11-08", 1)],
)
def test_the_block_fails_hard_after_the_deadline(today, rc, repo, monkeypatch, capsys):
    """Ruling 2026-10-29: 14 days. Blocked since 2026-10-24, the 2026-11-07 night (day
    14) still passes; 2026-11-08 (day 15) fails, and the notice stays (it is true)."""
    assert config.SENATE_MENU_OUTAGE_MAX_DAYS == 14
    path = _notice(repo)
    path.parent.mkdir(parents=True)
    path.write_text('{"outage_start": "2026-10-24"}\n', encoding="utf-8")
    monkeypatch.setattr(senate_votes, "_today", lambda: today)
    monkeypatch.setattr(senate_xml, "vote_menu", _raise(_status(403)))

    assert senate_votes.run() == rc
    assert json.loads(path.read_text(encoding="utf-8"))["outage_start"] == "2026-10-24"
    out = capsys.readouterr().out
    assert ("FAIL: senate.gov has refused the Senate vote menus for 15 days" in out) == bool(rc)


def test_the_committed_notice_matches_the_record():
    """The seeded notice (2026-10-29) carries the newest Senate roll actually on disk,
    so the site's "shown through" date comes from the record, not a typed value."""
    path = senate_votes.outage_notice_path()
    if not path.exists():
        pytest.skip("no outage in progress")
    notice = json.loads(path.read_text(encoding="utf-8"))
    rc_id, date, url = senate_votes._last_senate_roll()
    assert (notice["last_roll_id"], notice["last_roll_date"], notice["source_url"]) == (
        rc_id, date, url
    )
