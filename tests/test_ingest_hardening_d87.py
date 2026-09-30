"""D87 — the code-review hardening batch (2026-09-30 surgical review, findings 2/3/4/7/9).

Every test here locks a path where ONE bad record from a government source used to
abort a whole nightly run, or where a secret reached a log. Offline: no network, no
writes outside tmp_path.
"""

from __future__ import annotations

import json

import httpx
import pytest

from ingest import bills, config, house_votes, incremental, senate_votes


class _Text:
    def __init__(self, text): self.text = text


class _Json:
    def __init__(self, payload): self._p = payload
    def json(self): return self._p


# --- Finding 2: a malformed Senate vote_date must quarantine, not abort ---------

@pytest.mark.parametrize(
    "raw,exc_name",
    [("garbage", "ValueError"),        # fails the regex
     ("Juli 1, 2025,  11:56 AM", "KeyError")],  # passes the regex, unknown month
)
def test_senate_bad_vote_date_quarantines_instead_of_aborting(
    raw, exc_name, monkeypatch, capsys
):
    """Before D87 the pre-parse guard caught only ET.ParseError, so `_parse_date`'s
    ValueError/KeyError escaped `run()` and every LATER roll that night went
    un-ingested with no quarantine file and no gap report."""
    quarantined: list[tuple[str, str]] = []
    monkeypatch.setattr(config, "CONGRESSES", [119])
    monkeypatch.setattr(senate_votes, "SESSIONS", {119: (1,)})
    monkeypatch.setattr(senate_votes, "_quarantine",
                        lambda rc_id, err: quarantined.append((rc_id, err)))
    monkeypatch.setattr(incremental, "roll_is_final", lambda *a, **k: False)
    # Empty accept-list: this id must be treated as a NEW quarantine so the run
    # fails loudly (h-119-1-0001 IS on the committed accept-list, D83).
    monkeypatch.setattr(incremental, "accepted_quarantines", lambda *a, **k: {})
    from ingest.sources import senate_xml
    monkeypatch.setattr(senate_xml, "vote_menu", lambda c, s: _Text("<menu/>"))
    monkeypatch.setattr(senate_xml, "parse_menu", lambda text: {1: {}})
    monkeypatch.setattr(
        senate_xml, "vote_detail",
        lambda c, s, r: _Text(f"<roll_call><vote_date>{raw}</vote_date></roll_call>"),
    )

    rc = senate_votes.run()  # must RETURN, not raise

    assert rc == 1, "a new, unaccepted quarantine still fails the run loudly"
    assert [q[0] for q in quarantined] == ["s-119-1-0001"]
    assert quarantined[0][1].startswith(exc_name)
    assert "s-119-1-0001" in capsys.readouterr().out


# --- Finding 3: a malformed House members response must quarantine, not abort ---

@pytest.mark.parametrize(
    "payload,exc_name",
    [({"houseRollCallVoteMemberVotes": {}}, "KeyError"),            # no startDate
     ({"houseRollCallVoteMemberVotes": {"startDate": None}}, "TypeError")],  # null date
)
def test_house_bad_members_response_quarantines_instead_of_aborting(
    payload, exc_name, monkeypatch, capsys
):
    """`startDate` used to be read OUTSIDE the try, so a missing key aborted the run
    and a null date raised TypeError inside `coverage.covered_on`'s `[:10]` slice."""
    quarantined: list[tuple[str, str]] = []
    monkeypatch.setattr(config, "CONGRESSES", [119])
    monkeypatch.setattr(house_votes, "SESSIONS", {119: (1,)})
    monkeypatch.setattr(house_votes, "_quarantine",
                        lambda rc_id, err: quarantined.append((rc_id, err)))
    monkeypatch.setattr(incremental, "roll_is_final", lambda *a, **k: False)
    # Empty accept-list: this id must be treated as a NEW quarantine so the run
    # fails loudly (h-119-1-0001 IS on the committed accept-list, D83).
    monkeypatch.setattr(incremental, "accepted_quarantines", lambda *a, **k: {})
    from ingest.sources import congress_gov
    monkeypatch.setattr(congress_gov, "house_vote_roll_numbers", lambda c, s: ([1], 1))
    monkeypatch.setattr(congress_gov, "house_vote_members",
                        lambda c, s, r: _Json(payload))

    rc = house_votes.run()  # must RETURN, not raise

    assert rc == 1
    assert [q[0] for q in quarantined] == ["h-119-1-0001"]
    assert quarantined[0][1].startswith(exc_name)
    assert "h-119-1-0001" in capsys.readouterr().out


# --- Finding 4: the LegiScan key must never reach an error message -------------

def test_legiscan_http_error_omits_the_api_key(tmp_path, monkeypatch):
    """LegiScan requires the key as a QUERY param, and `raise_for_status()`'s message
    embeds the request URL — so a 4xx/5xx used to print `key=<secret>` in the
    traceback (GitHub masks its own secrets; a local run and a pasted log do not)."""
    from ingest.sources import legiscan

    secret = "SECRETXYZ0123456789"
    monkeypatch.setattr(legiscan, "RAW_DIR", tmp_path)
    monkeypatch.setattr(legiscan.env, "require", lambda name: secret)
    monkeypatch.setattr(
        legiscan.httpx, "get",
        lambda *a, **kw: httpx.Response(
            500,
            request=httpx.Request("GET", f"https://api.legiscan.com/?key={secret}&op=x"),
        ),
    )

    with pytest.raises(legiscan.LegiScanHTTPError) as ei:
        legiscan._get("getDatasetList", state="MS")

    assert secret not in str(ei.value)
    assert secret not in repr(ei.value)
    assert "getDatasetList" in str(ei.value) and "500" in str(ei.value)


def test_legiscan_success_still_caches(tmp_path, monkeypatch):
    """The guard must not change the happy path: a 200 still writes data + meta."""
    from ingest.sources import legiscan

    monkeypatch.setattr(legiscan, "RAW_DIR", tmp_path)
    monkeypatch.setattr(legiscan.env, "require", lambda name: "k")
    monkeypatch.setattr(
        legiscan.httpx, "get",
        lambda *a, **kw: httpx.Response(
            200, text='{"status":"OK"}',
            request=httpx.Request("GET", "https://api.legiscan.com/"),
        ),
    )
    assert legiscan._get("getSessionList", state="MS") == {"status": "OK"}
    assert len(list((tmp_path / "legiscan").glob("*.json"))) == 1


# --- Finding 7: an owner-accepted permanent bill 404 is a note, not a failure ---

def _bill_404(bill_id: str):
    def _raise(*a, **kw):
        raise httpx.HTTPStatusError(
            "404", request=httpx.Request("GET", "https://api.congress.gov/v3/bill/119/hr/1"),
            response=httpx.Response(404),
        )
    return _raise


def test_accepted_bill_404_is_a_note_not_a_failure(tmp_path, monkeypatch, capsys):
    """A bill the vote record cites but Congress.gov never publishes cannot be fixed
    by a retry, so before D87 it turned EVERY nightly red with no accept path."""
    monkeypatch.setattr(bills, "referenced_bill_ids", lambda: ["hr9999-119"])
    monkeypatch.setattr(incremental, "bill_is_skippable", lambda *a, **k: False)
    monkeypatch.setattr(incremental, "recent_bill_ids", lambda cutoff: set())
    monkeypatch.setattr(incremental, "accepted_quarantines",
                        lambda *a, **k: {"hr9999-119": "never published by Congress.gov"})
    from ingest.sources import congress_gov
    monkeypatch.setattr(congress_gov, "bill_detail", _bill_404("hr9999-119"))

    assert bills.run() == 0
    assert "owner-accepted missing bill" in capsys.readouterr().out


def test_unaccepted_bill_404_still_fails_the_run(tmp_path, monkeypatch, capsys):
    """The accept-list must not weaken the default: a NEW missing bill fails loudly."""
    monkeypatch.setattr(bills, "referenced_bill_ids", lambda: ["hr9999-119"])
    monkeypatch.setattr(incremental, "bill_is_skippable", lambda *a, **k: False)
    monkeypatch.setattr(incremental, "recent_bill_ids", lambda cutoff: set())
    monkeypatch.setattr(incremental, "accepted_quarantines", lambda *a, **k: {})
    from ingest.sources import congress_gov
    monkeypatch.setattr(congress_gov, "bill_detail", _bill_404("hr9999-119"))

    assert bills.run() == 1
    assert "failed to fetch" in capsys.readouterr().out


def test_accept_list_loads_roll_and_bill_ids_from_one_file(tmp_path):
    """One flat file for both kinds — roll ids and bill ids cannot collide."""
    from ingest import incremental

    qdir = tmp_path / "data" / "quality"
    qdir.mkdir(parents=True)
    (qdir / "accepted-quarantine.yaml").write_text(
        'h-119-1-0001: "voter outside roster"\nhr9999-119: "never published"\n',
        encoding="utf-8",
    )
    got = incremental.accepted_quarantines(root=tmp_path)
    assert got == {"h-119-1-0001": "voter outside roster", "hr9999-119": "never published"}


# --- Finding 9: a quarantine file is removed once the record exports cleanly ----

@pytest.mark.parametrize(
    "mod,record_id,filename",
    [(house_votes, "h-119-1-0001", "h-119-1-0001.json"),
     (senate_votes, "s-119-1-0001", "s-119-1-0001.json"),
     (bills, "hr1-119", "bill-hr1-119.json")],
)
def test_clear_quarantine_removes_the_stale_file(mod, record_id, filename,
                                                 tmp_path, monkeypatch):
    """data/quality/quarantine/ only ever grew, so it stopped describing what is
    ACTUALLY quarantined — the owner-facing signal it exists to be."""
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    qdir = tmp_path / "data" / "quality" / "quarantine"
    qdir.mkdir(parents=True)
    stale = qdir / filename
    stale.write_text(json.dumps({"error": "old"}), encoding="utf-8")

    mod._clear_quarantine(record_id)
    assert not stale.exists()
    mod._clear_quarantine(record_id)  # idempotent: no file, no error
