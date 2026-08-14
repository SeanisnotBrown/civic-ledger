"""INC-10 tests — member legislation parsing + the covered-window pagination.
Offline: parse_items is pure; the paginator is driven by monkeypatched pages.
"""

from __future__ import annotations

from collections import Counter

import pytest

from ingest.legislation import _count_regressions, parse_items

CONGS = [118, 119]


# --- D64 zero-regression guard (replaces the pre-D64 _sponsored_gaps heuristic) ---
def test_count_regressions_present_to_zero_flagged():
    # 119th had 3 sponsored last run, now 0 → truncation (bills don't un-sponsor).
    gaps = _count_regressions(
        "X", Counter({118: 2, 119: 3}), Counter(), Counter({118: 2}), Counter(), CONGS
    )
    assert len(gaps) == 1 and "sponsored" in gaps[0] and "congress 119" in gaps[0]


def test_count_regressions_genuine_zero_not_flagged():
    # Pelosi/Hoyer-like: 0 sponsored in the 119th before AND after → a true zero, not
    # a regression. Must NOT fail (this is exactly the pre-D64 false positive).
    assert _count_regressions(
        "P000197", Counter({118: 2}), Counter(), Counter({118: 2}), Counter(), CONGS
    ) == []


def test_count_regressions_no_prior_baseline_ok():
    # First-ever ingest: no prior record → empty baseline → nothing fires on a zero.
    assert _count_regressions(
        "N000001", Counter(), Counter(), Counter(), Counter(), CONGS
    ) == []


def test_count_regressions_cosponsored_side_too():
    gaps = _count_regressions(
        "X", Counter(), Counter({119: 5}), Counter(), Counter(), CONGS
    )
    assert len(gaps) == 1 and "cosponsored" in gaps[0] and "congress 119" in gaps[0]


def _item(bill_type, number, congress, action=None, title="A Bill", introduced="2025-01-01"):
    return {
        "type": bill_type, "number": number, "congress": congress,
        "title": title, "introducedDate": introduced,
        "latestAction": {"text": action} if action else None,
        "url": f"https://api.congress.gov/v3/bill/{congress}/{bill_type}/{number}?format=json",
    }


def test_amendments_excluded() -> None:
    raw = [
        _item("S", "10", 119),
        {"type": None, "amendmentNumber": "6568", "congress": 119,
         "url": "https://api.congress.gov/v3/amendment/119/samdt/6568?format=json"},
        {"number": None, "type": None, "congress": 118},  # malformed / amendment
    ]
    items = parse_items(raw)
    assert [i.bill_id for i in items] == ["s10-119"]  # only the bill survives


def test_became_law_and_enacted_action() -> None:
    raw = [
        _item("s", "3959", 118, action="Became Public Law No: 118-202."),
        _item("hr", "5", 119, action="Referred to committee."),
    ]
    items = {i.bill_id: i for i in parse_items(raw)}
    assert items["s3959-118"].became_law is True
    assert items["s3959-118"].enacted_action == "Became Public Law No: 118-202."
    assert items["hr5-119"].became_law is False
    assert items["hr5-119"].enacted_action is None  # frozen text only when enacted


def test_sorted_by_bill_id_and_html_unescaped() -> None:
    raw = [_item("s", "9", 119), _item("hr", "1", 119, title="Ways &amp; Means Act")]
    items = parse_items(raw)
    assert [i.bill_id for i in items] == ["hr1-119", "s9-119"]  # sorted
    assert items[0].title == "Ways & Means Act"  # entities decoded


def test_bill_id_normalization() -> None:
    items = parse_items([_item("HR", "82", 118)])
    assert items[0].bill_id == "hr82-118"  # type lowercased
    assert items[0].source_url == "https://www.congress.gov/bill/118th-congress/house-bill/82"


def test_paginator_stops_on_first_empty_window_page(monkeypatch: pytest.MonkeyPatch) -> None:
    from ingest.sources import congress_gov

    # Page 0: two in-window (119, 118). Page 1: interleaved 118 + old 117 (must NOT
    # stop here — one page of slack). Page 2: all out of window -> stop.
    pages = [
        {"sponsoredLegislation": [_item("s", "1", 119), _item("s", "2", 118)],
         "pagination": {"count": 600}},
        {"sponsoredLegislation": [_item("s", "3", 118), _item("s", "4", 117)],
         "pagination": {"count": 600}},
        {"sponsoredLegislation": [_item("s", "5", 116), _item("s", "6", 115)],
         "pagination": {"count": 600}},
    ]

    class _Resp:
        def __init__(self, i): self._i = i
        def json(self): return pages[self._i]

    def fake_get(path, params, **kw):
        return _Resp(int(params["offset"]) // 250)

    monkeypatch.setattr(congress_gov, "_get", fake_get)
    got = congress_gov.member_legislation("X", "sponsored-legislation", [118, 119])
    congs = sorted(it["congress"] for it in got)
    assert congs == [118, 118, 119]  # kept the page-1 118 item; dropped 117/116/115


class _Resp:
    def __init__(self, page): self._page = page
    def json(self): return self._page


def _patched(monkeypatch, pages_by_offset):
    from ingest.sources import congress_gov

    def fake_get(path, params, **kw):
        return _Resp(pages_by_offset[int(params["offset"])])

    monkeypatch.setattr(congress_gov, "_get", fake_get)
    return congress_gov


def test_member_legislation_raises_on_premature_empty_page(monkeypatch):
    # D64: page 0 is full (count=600), page 1 comes back EMPTY while offset 250 < 600.
    # That can only be a truncated/corrupt 200 — must raise, never publish a false 0.
    cg = _patched(monkeypatch, {
        0: {"sponsoredLegislation": [_item("s", "1", 119), _item("s", "2", 118)],
            "pagination": {"count": 600}},
        250: {"sponsoredLegislation": [], "pagination": {"count": 600}},
    })
    with pytest.raises(cg.TruncatedFetchError):
        cg.member_legislation("X", "sponsored-legislation", [118, 119])


def test_member_legislation_out_of_window_first_page_returns_empty(monkeypatch):
    # A member whose newest bills are all pre-window (e.g. served days of the term):
    # page 0 is non-empty but wholly out of window → clean stop, [] — NOT a truncation.
    cg = _patched(monkeypatch, {
        0: {"sponsoredLegislation": [_item("s", "9", 117), _item("s", "8", 116)],
            "pagination": {"count": 400}},
    })
    assert cg.member_legislation("X", "sponsored-legislation", [118, 119]) == []


def test_member_legislation_zero_lifetime_returns_empty(monkeypatch):
    # count == 0 at offset 0: a member with no lifetime legislation — empty is real,
    # offset(0) < count(0) is False, so it returns [] without raising.
    cg = _patched(monkeypatch, {
        0: {"sponsoredLegislation": [], "pagination": {"count": 0}},
    })
    assert cg.member_legislation("X", "sponsored-legislation", [118, 119]) == []
