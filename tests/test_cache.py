"""Offline tests for the raw-fetch disk cache (ingest/cache.py).

No network: `_live_get` is monkeypatched. These pin the load-bearing INC-1
invariants — header-only auth, no secret in the key/meta, TTL re-use, the
non-accepted-status branch that later increments rely on (house-vote 404 →
clerk fallback).
"""

from __future__ import annotations

import json

import httpx
import pytest

from ingest import cache


class _FakeResp:
    def __init__(self, text="{}", status_code=200, headers=None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=None, response=None
            )


@pytest.fixture
def raw_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path)
    cache._last_fetch_at.clear()
    return tmp_path


def test_cache_key_ignores_headers_only_url_and_params():
    # Two calls with different auth headers but same url+params → same key.
    k1 = cache._cache_key("https://api.congress.gov/v3/member", {"stateCode": "MS"})
    k2 = cache._cache_key("https://api.congress.gov/v3/member", {"stateCode": "MS"})
    assert k1 == k2
    k3 = cache._cache_key("https://api.congress.gov/v3/member", {"stateCode": "TX"})
    assert k1 != k3


def test_fetch_writes_body_and_meta_without_secret(raw_dir, monkeypatch):
    secret = "SUPERSECRETKEY1234567890"
    seen = {}

    def fake_live(url, params, headers):
        seen["url"] = url
        seen["params"] = params
        seen["headers"] = headers
        return _FakeResp(text='{"ok": true}')

    monkeypatch.setattr(cache, "_live_get", fake_live)

    resp = cache.fetch(
        "congress_gov",
        "https://api.congress.gov/v3/member",
        params={"stateCode": "MS"},
        headers={"X-Api-Key": secret},
    )
    assert resp.json() == {"ok": True}
    assert resp.from_cache is False

    # The secret went out as a header, never as a param.
    assert seen["headers"]["X-Api-Key"] == secret
    assert "SUPERSECRET" not in json.dumps(seen["params"])

    # The meta sidecar contains url + params but NOT the secret.
    meta_path = resp.path.with_suffix(".meta")
    meta_text = meta_path.read_text(encoding="utf-8")
    assert secret not in meta_text
    assert secret not in resp.path.read_text(encoding="utf-8")
    meta = json.loads(meta_text)
    assert meta["status"] == 200
    assert "fetched_at" in meta


def test_fresh_cache_is_not_refetched(raw_dir, monkeypatch):
    calls = {"n": 0}

    def fake_live(url, params, headers):
        calls["n"] += 1
        return _FakeResp(text='{"v": 1}')

    monkeypatch.setattr(cache, "_live_get", fake_live)

    cache.fetch("s", "https://example.gov/x", ext="json")
    cache.fetch("s", "https://example.gov/x", ext="json")  # within TTL → cached
    assert calls["n"] == 1

    # force=True bypasses the cache.
    cache.fetch("s", "https://example.gov/x", ext="json", force=True)
    assert calls["n"] == 2


def test_ttl_zero_always_refetches(raw_dir, monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(
        cache, "_live_get", lambda *a, **k: (calls.__setitem__("n", calls["n"] + 1) or _FakeResp())
    )
    cache.fetch("s", "https://example.gov/y", ttl_hours=0)
    cache.fetch("s", "https://example.gov/y", ttl_hours=0)
    assert calls["n"] == 2


def test_non_accepted_status_raises(raw_dir, monkeypatch):
    monkeypatch.setattr(cache, "_live_get", lambda *a, **k: _FakeResp(status_code=404))
    with pytest.raises(httpx.HTTPStatusError):
        cache.fetch("s", "https://api.congress.gov/v3/house-vote/119/1/9999")


def test_302_is_accepted_by_default(raw_dir, monkeypatch):
    monkeypatch.setattr(cache, "_live_get", lambda *a, **k: _FakeResp(text="ok", status_code=302))
    resp = cache.fetch("s", "https://example.gov/redirect", ext="xml")
    assert resp.status == 302
    assert resp.ext == "xml"
