"""INC-10 tests — member legislation parsing + the covered-window pagination.
Offline: parse_items is pure; the paginator is driven by monkeypatched pages.
"""

from __future__ import annotations

import pytest

from ingest.legislation import parse_items


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
