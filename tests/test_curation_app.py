"""INC-11 — local curation Flask app. The load-bearing guarantees: the app refuses
to bind a non-loopback host, and "no verified capture, no save" holds server-side —
the Save control only appears after a verified capture, and the save endpoint refuses
without the stored Capture. No network; SPN capture is faked."""

from __future__ import annotations

import pathlib
import re

import pytest

from curation import app as capp
from curation import statements
from curation.app import NonLoopbackBindError, assert_loopback, create_app
from ingest.sources.archive_org import Capture, SpnError


def test_assert_loopback_allows_loopback() -> None:
    for host in ("127.0.0.1", "localhost", "::1", "127.5.5.5"):
        assert_loopback(host)  # no raise


def test_assert_loopback_refuses_public_and_wildcard() -> None:
    for host in ("0.0.0.0", "192.168.1.5", "8.8.8.8", "example.com"):
        with pytest.raises(NonLoopbackBindError):
            assert_loopback(host)


def test_run_refuses_non_loopback_without_serving(monkeypatch, capsys) -> None:
    # create_app().run must never be reached for a public bind.
    monkeypatch.setattr(capp, "create_app", lambda: pytest.fail("must not build/serve"))
    assert capp.run(["--host", "0.0.0.0"]) == 2
    assert "non-loopback" in capsys.readouterr().out


class _FakeSpn:
    def __init__(self, *a, **k):
        pass

    def capture(self, url):
        return Capture(original_url=url, archive_url=f"https://web.archive.org/web/1/{url}",
                       timestamp="20240101000000", captured_at="2024-01-01T00:00:00Z")

    def close(self):
        pass


def _form(**over):
    f = {"member_id": "M1", "text": "We must pass this.", "date": "2024-03-05",
         "venue": "floor", "source_url": "https://ex.com/s", "named_measures": "hr2-119",
         "specificity_level": "3", "stated_position": "support"}
    f.update(over)
    return f


def test_capture_then_save_flow(monkeypatch):
    monkeypatch.setattr(capp, "SpnClient", _FakeSpn)
    monkeypatch.setattr(statements, "_covered_member_ids", lambda: {"M1"})
    saved = {}

    def _fake_save(stmt):
        saved["stmt"] = stmt
        return pathlib.Path("X.json")

    monkeypatch.setattr(capp.statements, "save_statement", _fake_save)
    client = create_app().test_client()

    # Step 1: capture → verified draft with a Save button + the archive_url.
    r1 = client.post("/statements/capture", data=_form())
    assert r1.status_code == 200
    assert "web.archive.org" in r1.get_data(as_text=True)
    token = re.search(r'name="token" value="([^"]+)"', r1.get_data(as_text=True)).group(1)

    # Step 2: save the verified draft.
    r2 = client.post("/statements/save", data={"token": token}, follow_redirects=False)
    assert r2.status_code == 302
    assert saved["stmt"].paired_bill_ids == ["hr2-119"]
    assert saved["stmt"].stated_position == "support"


def test_save_without_a_verified_capture_saves_nothing(monkeypatch):
    monkeypatch.setattr(capp, "SpnClient", _FakeSpn)
    called = {"n": 0}
    monkeypatch.setattr(capp.statements, "save_statement",
                        lambda stmt: called.__setitem__("n", called["n"] + 1))
    client = create_app().test_client()
    # A bogus token has no stored capture → nothing saved.
    r = client.post("/statements/save", data={"token": "bogus"}, follow_redirects=True)
    assert called["n"] == 0
    assert "nothing saved" in r.get_data(as_text=True).lower()


def test_capture_failure_does_not_save(monkeypatch):
    class _Boom(_FakeSpn):
        def capture(self, url):
            raise SpnError("error:invalid-host-resolution")

    monkeypatch.setattr(capp, "SpnClient", _Boom)
    monkeypatch.setattr(statements, "_covered_member_ids", lambda: {"M1"})
    monkeypatch.setattr(capp.statements, "save_statement",
                        lambda stmt: pytest.fail("must not save on capture failure"))
    client = create_app().test_client()
    r = client.post("/statements/capture", data=_form(), follow_redirects=True)
    assert "capture failed" in r.get_data(as_text=True).lower()
