"""INC-11 — archive-link liveness sweep. A 4xx is a confirmed dead snapshot
(→ flagged unpublishable, fails); a network error / 5xx is a transient outage
(→ warn only, never excludes). No network; driven via httpx.MockTransport."""

from __future__ import annotations

import httpx

from ingest.checks import archive_links


def _stmt(sid, host):
    return {"id": sid, "archive_url": f"https://web.archive.org/web/1/https://{host}"}


def test_sweep_classifies_alive_dead_and_unreachable() -> None:
    def handler(req):
        u = str(req.url)
        if "gone" in u:
            return httpx.Response(404)
        if "flaky" in u:
            return httpx.Response(503)
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    report = archive_links.sweep(
        [_stmt("a", "ok"), _stmt("b", "gone"), _stmt("c", "flaky")], client
    )
    assert report["dead_statement_ids"] == ["b"]
    assert report["alive"] == 1
    assert [u["id"] for u in report["unreachable"]] == ["c"]


def test_network_error_is_unreachable_not_dead() -> None:
    def boom(req):
        raise httpx.ConnectError("no route")
    client = httpx.Client(transport=httpx.MockTransport(boom))
    assert archive_links.classify_head(client, "https://web.archive.org/x") == "unreachable"


def test_main_is_noop_without_statements(monkeypatch, capsys) -> None:
    monkeypatch.setattr(archive_links, "_load_statements", lambda: [])
    assert archive_links.main() == 0
    assert "no curated statements" in capsys.readouterr().out


def test_report_is_deterministic_and_sorted() -> None:
    def handler(req):
        return httpx.Response(404 if "gone" in str(req.url) else 200)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    stmts = [_stmt("z", "gone"), _stmt("a", "gone"), _stmt("m", "ok")]
    report = archive_links.sweep(stmts, client)
    assert report["dead_statement_ids"] == ["a", "z"]  # sorted, byte-stable
