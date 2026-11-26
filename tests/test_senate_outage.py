"""senate.gov block on the vote menus (owner ruling 2026-10-29) and on single vote FILES
(owner ruling 2026-11-25, Q2 = B).

From 2026-10-24 senate.gov's firewall returned 403 to the nightly runner, and the
failing `senate-votes` stopped every night from publishing anything. Option A: a run
whose ONLY failures are HTTP status errors on the vote menus exits 0 and keeps
data/quality/senate-outage.json (the site's reader line is built from it); anything
else stays fatal; the first success deletes the notice; past
config.SENATE_MENU_OUTAGE_MAX_DAYS the run fails hard again. 2026-11-25 Q2 = B: a
refused vote FILE (an HTTP 403 on one roll's detail; any other status stays fatal) is
the same kind of block: that roll is skipped for the night, listed in the notice as
`missing_rolls`, retried the next night, and counted in the same 14 days. Offline: no
network, no writes outside tmp_path.
"""

from __future__ import annotations

import json

import httpx
import pytest

from ingest import config, coverage, export, incremental, senate_votes
from ingest.cache import RetryableHTTPError
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
    ["menu_timeout", "detail_timeout", "detail_429_exhausted", "tally_mismatch"],
)
def test_a_menu_block_mixed_with_any_other_failure_is_still_fatal(case, repo, monkeypatch):
    """Only status errors on the menus and 403s on the vote files are tolerated: a menu
    timeout, a vote-file timeout, a vote file whose 429/5xx retries ran out, or a
    validation failure still fails the night, even beside a menu block."""
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
    if case == "detail_timeout":
        monkeypatch.setattr(senate_xml, "vote_detail", _raise(httpx.ConnectTimeout("t")))
    elif case == "detail_429_exhausted":
        monkeypatch.setattr(
            senate_xml, "vote_detail", _raise(RetryableHTTPError("429 rate limited"))
        )
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


# --- single vote FILES (owner ruling 2026-11-25, Q2 = B) -------------------

FILE_URL = senate_xml.detail_url(119, 2, 2)
DETAIL = "<roll_call><vote_date>October 1, 2026,  10:00 AM</vote_date></roll_call>"


@pytest.fixture
def two_rolls(repo, monkeypatch):
    """119/1 lists no rolls; 119/2 lists rolls 1 and 2. Every roll that is fetched
    parses and is "exported" into `saved`; the vote files in `refused` (roll numbers of
    119/2) answer with status `code`."""
    state = {"refused": {2}, "code": 403, "fetched": [], "saved": []}
    menus = {"1": {}, "2": {1: (60, 40), 2: (60, 40)}}

    def detail(c, s, r):
        state["fetched"].append((s, r))
        if s == 2 and r in state["refused"]:
            raise _status(state["code"], senate_xml.detail_url(c, s, r))
        return _Text(DETAIL)

    def parse_rollcall(detail_xml, congress, session, lis, tally, covered=None):
        n = len(state["saved"]) + 1
        return type("RC", (), {"id": f"s-{congress}-{session}-{n:04d}"})(), [], []

    monkeypatch.setattr(senate_xml, "vote_menu", lambda c, s: _Text(str(s)))
    monkeypatch.setattr(senate_xml, "parse_menu", lambda text: menus[text])
    monkeypatch.setattr(senate_xml, "vote_detail", detail)
    monkeypatch.setattr(incremental, "roll_is_final", lambda *a, **k: False)
    monkeypatch.setattr(coverage, "expected_on", lambda *a, **k: set())
    monkeypatch.setattr(senate_votes, "parse_rollcall", parse_rollcall)
    monkeypatch.setattr(export, "export_rollcall", lambda rc, mvs: state["saved"].append(rc.id))
    return state


def test_one_refused_vote_file_exits_0_skips_it_and_writes_the_notice(
    two_rolls, repo, capsys
):
    """Q2 = B: roll 2's file is refused, 1 still ingests, the night passes. The refused
    file is asked for ONCE (rule 4), logged with its code and URL, and the notice lists it."""
    assert senate_votes.run() == 0
    assert two_rolls["saved"] == ["s-119-2-0001"]
    assert two_rolls["fetched"].count((2, 2)) == 1
    notice = json.loads(_notice(repo).read_text(encoding="utf-8"))
    assert notice["missing_rolls"] == ["s-119-2-0002"]
    assert notice["outage_start"] == "2026-10-29"
    out = capsys.readouterr().out
    warn = next(ln for ln in out.splitlines() if ln.startswith("WARN: senate.gov refused 1 "))
    assert f"s-119-2-0002: HTTPStatusError HTTP 403 {FILE_URL}" in warn
    assert "vote menu" not in out and "FAIL" not in out
    out.encode("ascii")  # plain ASCII on stdout


@pytest.mark.parametrize("code", [400, 401, 404, 410])
def test_a_vote_file_status_other_than_403_still_fails_the_night(
    code, two_rolls, repo, capsys
):
    """Copilot call (2026-11-26): only a 403 REFUSAL is tolerated. A 404 or any other
    status on a vote file fails the night as it did before Q2, logged with its code and
    URL (PR #5), and no outage notice is written for it."""
    two_rolls["code"] = code

    assert senate_votes.run() == 1
    out = capsys.readouterr().out
    fail = next(ln for ln in out.splitlines() if ln.startswith("FAIL: "))
    assert f"s-119-2-0002: HTTPStatusError HTTP {code} {FILE_URL}" in fail
    assert not _notice(repo).exists()
    assert "WARN" not in out


def test_a_refused_file_beside_a_fatal_failure_still_fails_the_night(
    two_rolls, repo, monkeypatch, capsys
):
    """The refused file excuses nothing else: a vote-file timeout the same night fails
    the run (exit 1), the FAIL line names only the timeout, and the notice is still
    written because the block itself is real."""
    real = senate_xml.vote_detail

    def detail(c, s, r):
        if r == 1:
            raise httpx.ConnectTimeout("timed out")
        return real(c, s, r)

    monkeypatch.setattr(senate_xml, "vote_detail", detail)

    assert senate_votes.run() == 1
    out = capsys.readouterr().out
    fail = next(ln for ln in out.splitlines() if ln.startswith("FAIL: "))
    assert "s-119-2-0001: ConnectTimeout" in fail and "0002" not in fail
    notice = json.loads(_notice(repo).read_text(encoding="utf-8"))
    assert notice["missing_rolls"] == ["s-119-2-0002"]


def test_the_notice_keeps_a_missing_roll_until_it_is_on_disk(two_rolls, repo):
    """A repeat blocked night rewrites the notice byte for byte (no churn). A roll the
    last notice listed that is not on disk stays listed even when tonight did not ask for
    it; one that has since been saved drops off."""
    assert senate_votes.run() == 0
    path = _notice(repo)
    first = path.read_bytes()
    assert senate_votes.run() == 0  # the next night, still refused
    assert path.read_bytes() == first

    prior = json.loads(first)
    prior["missing_rolls"] = ["s-119-2-0002", "s-119-2-0003", "s-119-2-0004"]
    path.write_text(json.dumps(prior), encoding="utf-8")
    (export.VOTES_DIR / "s-119-2-0004.json").write_text(
        json.dumps({"rollcall": {**LAST, "id": "s-119-2-0004"}}), encoding="utf-8"
    )
    assert senate_votes.run() == 0
    assert json.loads(path.read_text(encoding="utf-8"))["missing_rolls"] == [
        "s-119-2-0002", "s-119-2-0003",
    ]


def test_the_vote_file_answering_deletes_the_notice_and_fills_the_roll(two_rolls, repo):
    """The next night senate.gov answers: the missing vote ingests, the notice goes."""
    assert senate_votes.run() == 0
    assert _notice(repo).exists()

    two_rolls["refused"] = set()
    two_rolls["saved"].clear()
    assert senate_votes.run() == 0
    assert len(two_rolls["saved"]) == 2  # rolls 1 and 2 both fetched and saved
    assert not _notice(repo).exists()


@pytest.mark.parametrize("today,rc", [("2026-11-07", 0), ("2026-11-08", 1)])
def test_a_vote_file_block_fails_hard_after_the_same_14_days(
    today, rc, two_rolls, repo, monkeypatch, capsys
):
    """Blocked since 2026-10-24, the 2026-11-07 night (day 14) still passes with a
    refused vote file; 2026-11-08 (day 15) fails. The same counter, the same limit."""
    assert config.SENATE_MENU_OUTAGE_MAX_DAYS == 14
    path = _notice(repo)
    path.parent.mkdir(parents=True)
    path.write_text('{"outage_start": "2026-10-24"}\n', encoding="utf-8")
    monkeypatch.setattr(senate_votes, "_today", lambda: today)

    assert senate_votes.run() == rc
    notice = json.loads(path.read_text(encoding="utf-8"))
    assert notice["outage_start"] == "2026-10-24"
    assert notice["missing_rolls"] == ["s-119-2-0002"]
    out = capsys.readouterr().out
    assert ("FAIL: senate.gov has refused the Senate vote files for 15 days" in out) == bool(rc)


def test_a_menu_block_and_a_file_block_together_share_one_deadline(
    two_rolls, repo, monkeypatch, capsys
):
    """119/1's menu and 119/2's file 2 are both refused on day 15: one failure line
    names both, and the notice carries both facts."""
    path = _notice(repo)
    path.parent.mkdir(parents=True)
    path.write_text('{"outage_start": "2026-10-14"}\n', encoding="utf-8")
    real = senate_xml.vote_menu

    def menu(c, s):
        if s == 1:
            raise _status(403)
        return real(c, s)

    monkeypatch.setattr(senate_xml, "vote_menu", menu)

    assert senate_votes.run() == 1
    out = capsys.readouterr().out
    assert "refused the Senate vote menus and vote files for 15 days" in out
    assert "WARN: senate.gov refused 1 vote menu(s)" in out
    assert json.loads(path.read_text(encoding="utf-8"))["missing_rolls"] == ["s-119-2-0002"]


def test_a_notice_with_no_senate_roll_on_disk_has_no_shown_through_fields(repo):
    """Nothing held at all: the notice carries the start and the missing ids only, and a
    menu-only notice never gains a `missing_rolls` key."""
    (export.VOTES_DIR / f"{LAST['id']}.json").unlink()

    assert senate_votes.write_outage_notice(missing_rolls=["s-119-2-0002"]) == {
        "outage_start": "2026-10-29",
        "missing_rolls": ["s-119-2-0002"],
    }
    _notice(repo).unlink()
    assert senate_votes.write_outage_notice() == {"outage_start": "2026-10-29"}


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
