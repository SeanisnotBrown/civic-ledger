"""D86 — the nightly legislation count probe.

A full legislation fetch is ~3,500 list pages at ~7 s each (3.5 h of the nightly's
4 h) and exhausted the free GitHub Actions allowance in 2026-09. `run()` now spends
ONE `/member/{id}` request per member and re-pages the lists only when the lifetime
sponsored/cosponsored counts moved since the committed record. Offline: the source
module's `_get` and the paginator are monkeypatched; the data dir is a tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest import legislation
from ingest.legislation import should_refetch
from ingest.sources import congress_gov


# --- should_refetch (pure) -----------------------------------------------------
def test_refetch_when_prior_record_predates_d86():
    assert should_refetch(None, {"sponsored": 1, "cosponsored": 2}) is True


def test_no_refetch_when_counts_identical():
    same = {"sponsored": 7, "cosponsored": 40}
    assert should_refetch(same, dict(same)) is False


@pytest.mark.parametrize(
    "live",
    [
        {"sponsored": 8, "cosponsored": 40},   # new sponsorship
        {"sponsored": 7, "cosponsored": 41},   # new cosponsorship
        {"sponsored": 7, "cosponsored": 39},   # withdrawn cosponsorship (count DOWN)
        {"sponsored": 0, "cosponsored": 0},    # malformed probe reads as 0 → refetch
    ],
)
def test_refetch_on_any_movement_either_direction(live):
    assert should_refetch({"sponsored": 7, "cosponsored": 40}, live) is True


# --- member_lifetime_counts (source) ---------------------------------------------
class _Resp:
    def __init__(self, page): self._page = page
    def json(self): return self._page


def test_member_lifetime_counts_reads_detail_blocks(monkeypatch):
    seen = []

    def fake_get(path, params=None, **kw):
        seen.append(path)
        return _Resp({"member": {
            "sponsoredLegislation": {"count": 761, "url": "…"},
            "cosponsoredLegislation": {"count": 4534, "url": "…"},
        }})

    monkeypatch.setattr(congress_gov, "_get", fake_get)
    assert congress_gov.member_lifetime_counts("W000437") == {"sponsored": 761, "cosponsored": 4534}
    assert seen == ["member/W000437"]  # exactly one request, the detail endpoint


def test_member_lifetime_counts_malformed_reads_zero(monkeypatch):
    # A detail response missing the blocks must not raise; 0/0 can never equal a real
    # committed non-zero pair, so the caller falls through to the full fetch.
    monkeypatch.setattr(congress_gov, "_get", lambda *a, **k: _Resp({"member": {}}))
    assert congress_gov.member_lifetime_counts("X") == {"sponsored": 0, "cosponsored": 0}
    monkeypatch.setattr(congress_gov, "_get", lambda *a, **k: _Resp({}))
    assert congress_gov.member_lifetime_counts("X") == {"sponsored": 0, "cosponsored": 0}


# --- run(): reuse vs re-page --------------------------------------------------------
def _item(bill_type, number, congress):
    return {
        "type": bill_type, "number": number, "congress": congress, "title": "A Bill",
        "introducedDate": "2025-01-01", "latestAction": None,
        "url": f"https://api.congress.gov/v3/bill/{congress}/{bill_type}/{number}?format=json",
    }


def _setup(tmp_path: Path, monkeypatch, *, prior_records: dict, live_counts: dict):
    """Data dir with two members; `prior_records` are pre-existing legislation files;
    `live_counts` is what the detail probe returns per member. Returns a recorder of
    which members had their LISTS paged (the expensive path)."""
    data = tmp_path / "data"
    (data / "members").mkdir(parents=True)
    (data / "legislation").mkdir()
    for mid in ("A000001", "B000002"):
        (data / "members" / f"{mid}.json").write_text(json.dumps({"id": mid}), encoding="utf-8")
    for mid, rec in prior_records.items():
        (data / "legislation" / f"{mid}.json").write_text(json.dumps(rec), encoding="utf-8")

    import ingest.cache as cache
    import ingest.export as export
    monkeypatch.setattr(cache, "repo_root", lambda: tmp_path)
    # run() imports the exporter from the module at call time, so patching the module
    # attribute redirects the write into the tmp data dir (never the real data/).
    monkeypatch.setattr(export, "export_member_legislation",
                        lambda rec, out_dir=None: _write(rec, data / "legislation"))

    paged: list[str] = []
    monkeypatch.setattr(congress_gov, "member_lifetime_counts", lambda mid: live_counts[mid])

    def fake_pages(mid, kind, congs, **kw):
        paged.append(f"{mid}:{kind}")
        # Keep the prior record's 118 item present so the D64 zero-regression guard
        # (a real congress dropping to 0 = truncation) stays quiet, as on a real night.
        if kind.startswith("sponsored"):
            return [_item("hr", "1", 119), _item("hr", "9", 118)]
        return [_item("s", "2", 119)]

    monkeypatch.setattr(congress_gov, "member_legislation", fake_pages)
    return data, paged


def _write(rec, out_dir: Path):
    from ingest.export import _dumps
    p = out_dir / f"{rec.member_id}.json"
    p.write_text(_dumps(rec.model_dump()), encoding="utf-8", newline="\n")
    return p


def _record(mid, counts):
    return {
        "member_id": mid, "source_url": f"https://api.congress.gov/v3/member/{mid}/sponsored-legislation",
        "sponsored": [{"bill_id": "hr9-118", "congress": 118, "title": "Old",
                       "introduced_date": None, "became_law": False, "enacted_action": None,
                       "source_url": "https://www.congress.gov/bill/118th-congress/house-bill/9"}],
        "cosponsored": [],
        "lifetime_counts": counts,
    }


def test_run_keeps_unchanged_member_and_repages_changed_one(tmp_path, monkeypatch, capsys):
    data, paged = _setup(
        tmp_path, monkeypatch,
        prior_records={
            "A000001": _record("A000001", {"sponsored": 5, "cosponsored": 50}),  # unchanged
            "B000002": _record("B000002", {"sponsored": 5, "cosponsored": 50}),  # will move
        },
        live_counts={
            "A000001": {"sponsored": 5, "cosponsored": 50},
            "B000002": {"sponsored": 6, "cosponsored": 50},
        },
    )
    before_a = (data / "legislation" / "A000001.json").read_text(encoding="utf-8")
    assert legislation.run([]) == 0
    # Only B paged its two lists; A never touched the expensive endpoints.
    assert paged == ["B000002:sponsored-legislation", "B000002:cosponsored-legislation"]
    # A's committed file is byte-identical (quiet-night diff-gate).
    assert (data / "legislation" / "A000001.json").read_text(encoding="utf-8") == before_a
    # B was rewritten with the fresh items AND the new counts for next night's probe.
    b = json.loads((data / "legislation" / "B000002.json").read_text(encoding="utf-8"))
    assert [i["bill_id"] for i in b["sponsored"]] == ["hr1-119", "hr9-118"]
    assert b["lifetime_counts"] == {"sponsored": 6, "cosponsored": 50}
    out = capsys.readouterr().out
    assert "1 re-fetched + 1 unchanged (kept) of 2 members" in out


def test_run_pre_d86_record_is_refetched_once_then_carries_counts(tmp_path, monkeypatch):
    rec = _record("A000001", None)
    del rec["lifetime_counts"]  # a record written before D86 has no such key at all
    data, paged = _setup(
        tmp_path, monkeypatch,
        prior_records={"A000001": rec},
        live_counts={"A000001": {"sponsored": 5, "cosponsored": 50},
                     "B000002": {"sponsored": 1, "cosponsored": 1}},  # B: no prior → fetch
    )
    assert legislation.run([]) == 0
    assert sorted(paged) == sorted([
        "A000001:sponsored-legislation", "A000001:cosponsored-legislation",
        "B000002:sponsored-legislation", "B000002:cosponsored-legislation",
    ])
    a = json.loads((data / "legislation" / "A000001.json").read_text(encoding="utf-8"))
    assert a["lifetime_counts"] == {"sponsored": 5, "cosponsored": 50}


def test_run_full_flag_repages_everyone(tmp_path, monkeypatch, capsys):
    data, paged = _setup(
        tmp_path, monkeypatch,
        prior_records={
            "A000001": _record("A000001", {"sponsored": 5, "cosponsored": 50}),
            "B000002": _record("B000002", {"sponsored": 5, "cosponsored": 50}),
        },
        live_counts={"A000001": {"sponsored": 5, "cosponsored": 50},
                     "B000002": {"sponsored": 5, "cosponsored": 50}},
    )
    assert legislation.run(["--full"]) == 0
    assert len(paged) == 4  # both members, both kinds — the weekly refresh
    assert "[--full]" in capsys.readouterr().out
