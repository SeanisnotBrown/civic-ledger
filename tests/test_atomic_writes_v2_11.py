"""V2-11 — the writes on the backfill path are atomic (D95).

The one-time 38,756-bill backfill runs ~43 hours on a laptop that gets shut, so it
is interrupted by design. These tests pin the property that makes a resume safe:
no reader ever sees a PARTIAL file, whatever moment the process dies at.

They do not kill a real process (a unit test cannot schedule a SIGKILL inside a
syscall). Instead each one asserts the mechanism that makes the kill harmless:
the bytes land on a temp file and appear at the real path only by `os.replace`,
so the real path holds either the whole old file or the whole new one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest import bills, cache
from ingest.cache import atomic_write_text


def test_atomic_write_creates_the_file_with_lf_endings(tmp_path: Path) -> None:
    path = atomic_write_text(tmp_path / "deep" / "x.json", '{"a": 1}\n')
    assert path.read_bytes() == b'{"a": 1}\n'  # LF, not CRLF, on every platform


def test_atomic_write_leaves_no_temp_file_behind(tmp_path: Path) -> None:
    atomic_write_text(tmp_path / "x.json", "body")
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]


def test_a_failed_write_leaves_the_previous_file_intact(tmp_path: Path, monkeypatch) -> None:
    """The whole point: an interrupted write must not destroy what was there."""
    path = tmp_path / "x.json"
    atomic_write_text(path, "original")

    def boom(*a, **k):
        raise KeyboardInterrupt  # what Ctrl+C actually raises mid-write

    monkeypatch.setattr(cache.os, "replace", boom)
    with pytest.raises(KeyboardInterrupt):
        atomic_write_text(path, "replacement")

    assert path.read_text(encoding="utf-8") == "original"
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]  # temp cleaned up


def test_the_partial_bytes_are_never_visible_at_the_real_path(tmp_path: Path, monkeypatch) -> None:
    """Interrupt between the body write and the rename: the half-written bytes are
    on the temp file, and the real path does not exist at all. That is why a torn
    bill file does not happen — `bills_with_actions` sees no file, not a bad one."""
    path = tmp_path / "x.json"
    seen: dict[str, bool] = {}

    def check_then_fail(src, dst):
        seen["real_path_exists_mid_write"] = Path(dst).exists()
        seen["temp_has_the_bytes"] = Path(src).read_text(encoding="utf-8") == "half"
        raise OSError("power loss")

    monkeypatch.setattr(cache.os, "replace", check_then_fail)
    with pytest.raises(OSError):
        atomic_write_text(path, "half")

    assert seen == {"real_path_exists_mid_write": False, "temp_has_the_bytes": True}


def test_export_bill_writes_atomically(tmp_path: Path, monkeypatch) -> None:
    """`export_bill` is the per-bill write of the backfill — one per bill, 38,756
    times. If it stops going through the helper, a kill can tear a record again."""
    from ingest import export

    calls: list[Path] = []
    real = cache.atomic_write_text

    def spy(path, text):
        calls.append(Path(path))
        return real(path, text)

    monkeypatch.setattr(export, "atomic_write_text", spy)
    bill = _a_bill()
    out = export.export_bill(bill, out_dir=tmp_path)
    assert calls == [out]
    assert json.loads(out.read_text(encoding="utf-8"))["id"] == bill.id


def test_quarantine_writes_atomically(tmp_path: Path, monkeypatch) -> None:
    """A torn quarantine file would fail `uv run checks` on a parse error instead
    of reporting the quarantine it exists to report."""
    monkeypatch.setattr(cache, "repo_root", lambda: tmp_path)
    bills._quarantine("hr1-118", "ValidationError: nope")
    written = tmp_path / "data" / "quality" / "quarantine" / "bill-hr1-118.json"
    assert json.loads(written.read_text(encoding="utf-8"))["bill_id"] == "hr1-118"
    assert sorted(p.name for p in written.parent.iterdir()) == ["bill-hr1-118.json"]


def test_cache_writes_the_body_before_the_sidecar_and_both_atomically(
    tmp_path: Path, monkeypatch
) -> None:
    """Order matters as much as atomicity: `_fresh` trusts the `.meta`, so the
    sidecar must not exist until the body it describes is whole. If that order
    ever flips, a kill between the two writes leaves a FRESH sidecar over a body
    that is missing or short — and `fetch` would serve it from cache for the next
    20 hours, failing every resume on the same bill."""
    order: list[str] = []
    real = cache.atomic_write_text

    def spy(path, text):
        order.append(Path(path).suffix)
        return real(path, text)

    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(cache, "atomic_write_text", spy)
    monkeypatch.setattr(cache, "_live_get", lambda url, params, headers: _a_response())

    got = cache.fetch("congress_gov", "https://example.test/bill", ext="json")
    assert order == [".json", ".meta"]  # body first, sidecar second
    assert got.json() == {"ok": True}


# --- helpers --------------------------------------------------------------


def _a_response():
    import httpx

    return httpx.Response(200, text='{"ok": true}', request=httpx.Request("GET", "https://e.test"))


def _a_bill():
    from ingest.models import Bill

    return Bill(
        id="hr1-118", congress=118, type="hr", number=1, title_official="A Bill",
        policy_area="Health", subjects=["Health care costs"], sponsor_id="A000001",
        cosponsor_ids=[], actions=None, latest_action="Referred to Committee.",
        latest_action_date="2025-01-03", cbo_estimates=[],
        source_url="https://www.congress.gov/bill/118/hr/1",
    )
