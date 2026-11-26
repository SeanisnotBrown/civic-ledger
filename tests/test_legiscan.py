"""LegiScan client (ingest/sources/legiscan.py): the transient-error retry and the TTL'd
disk cache. The 2026-11-16 nightly died on ONE `getDatasetList` HTTP 526 (Cloudflare);
the client had no retry, so a single edge blip failed the whole federal nightly.
Offline: no network, no writes outside tmp_path.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from ingest.sources import legiscan

SECRET = "SECRETXYZ0123456789"


def _resp(status, text="{}"):
    return httpx.Response(
        status, text=text,
        request=httpx.Request("GET", f"https://api.legiscan.com/?key={SECRET}&op=x"),
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A keyed client caching into tmp_path, with backoff waits recorded, not slept."""
    monkeypatch.setattr(legiscan, "RAW_DIR", tmp_path)
    monkeypatch.setattr(legiscan.env, "require", lambda name: SECRET)
    sleeps: list[float] = []
    monkeypatch.setattr(legiscan._live_get.retry, "sleep", sleeps.append)
    return sleeps


def _serve(monkeypatch, *outcomes):
    """httpx.get answers with each outcome in turn (a status code or an exception)."""
    calls = {"n": 0}

    def fake_get(*a, **kw):
        outcome = outcomes[calls["n"]]
        calls["n"] += 1
        if isinstance(outcome, Exception):
            raise outcome
        return _resp(outcome, text='{"status":"OK"}')

    monkeypatch.setattr(legiscan.httpx, "get", fake_get)
    return calls


# --- retry ---------------------------------------------------------------------

@pytest.mark.parametrize("status", [500, 502, 503, 520, 522, 524, 526])
def test_5xx_retries_then_succeeds(client, monkeypatch, status):
    calls = _serve(monkeypatch, status, status, 200)
    assert legiscan._get("getDatasetList", state="MS") == {"status": "OK"}
    assert calls["n"] == 3
    assert client == [2, 2]  # backoff between attempts (min 2 s)


@pytest.mark.parametrize("exc", [
    httpx.ReadTimeout("timed out"),
    httpx.ConnectError("connection refused"),
    httpx.RemoteProtocolError("peer closed connection"),  # a reset mid-response
])
def test_timeout_or_reset_retries_then_succeeds(client, monkeypatch, exc):
    calls = _serve(monkeypatch, exc, 200)
    assert legiscan._get("getDatasetList", state="MS") == {"status": "OK"}
    assert calls["n"] == 2


def test_5xx_gives_up_after_five_attempts_and_fails_as_before(client, monkeypatch):
    calls = _serve(monkeypatch, *[526] * 5)
    with pytest.raises(legiscan.LegiScanHTTPError) as ei:
        legiscan._get("getDatasetList", state="MS")
    assert calls["n"] == 5
    assert client == [2, 2, 4, 8]  # 16 s of waiting in all, then it gives up
    assert str(ei.value) == "LegiScan getDatasetList returned HTTP 526"
    assert SECRET not in str(ei.value) and SECRET not in repr(ei.value)
    assert not list((legiscan.RAW_DIR / "legiscan").glob("*"))  # nothing cached


def test_timeout_gives_up_after_five_attempts(client, monkeypatch):
    calls = _serve(monkeypatch, *[httpx.ReadTimeout("timed out")] * 5)
    with pytest.raises(httpx.ReadTimeout):
        legiscan._get("getDatasetList", state="MS")
    assert calls["n"] == 5


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429])
def test_4xx_is_not_retried(client, monkeypatch, status):
    calls = _serve(monkeypatch, status, 200)
    with pytest.raises(legiscan.LegiScanHTTPError) as ei:
        legiscan._get("getDatasetList", state="MS")
    assert not isinstance(ei.value, legiscan.LegiScanServerError)
    assert calls["n"] == 1 and client == []
    assert str(ei.value) == f"LegiScan getDatasetList returned HTTP {status}"


# --- cache and wrappers ------------------------------------------------------------

def test_fresh_cache_is_served_without_a_request(client, monkeypatch):
    calls = _serve(monkeypatch, 200)
    legiscan._get("getSessionList", state="MS")
    assert legiscan._get("getSessionList", state="MS") == {"status": "OK"}
    assert calls["n"] == 1


def test_stale_or_unreadable_meta_is_not_fresh(tmp_path):
    meta = tmp_path / "x.meta"
    assert not legiscan._is_fresh(meta, 20)  # absent
    meta.write_text("not json", encoding="utf-8")
    assert not legiscan._is_fresh(meta, 20)
    old = (datetime.now(UTC) - timedelta(hours=21)).isoformat()
    meta.write_text(json.dumps({"fetched_at": old}), encoding="utf-8")
    assert not legiscan._is_fresh(meta, 20)
    assert legiscan._is_fresh(meta, 22)


def test_available_follows_the_key(monkeypatch):
    monkeypatch.setattr(legiscan.env, "get", lambda name: "k")
    assert legiscan.available()
    monkeypatch.setattr(legiscan.env, "get", lambda name: None)
    assert not legiscan.available()


def test_wrappers_name_their_operation(monkeypatch):
    seen = []
    monkeypatch.setattr(legiscan, "_get", lambda op, **p: seen.append((op, p)) or {})
    legiscan.session_list()
    legiscan.dataset_list("MS")
    legiscan.get_dataset(2150, "abc")
    assert seen == [
        ("getSessionList", {"state": "MS"}),
        ("getDatasetList", {"state": "MS"}),
        ("getDataset", {"id": 2150, "access_key": "abc"}),
    ]
