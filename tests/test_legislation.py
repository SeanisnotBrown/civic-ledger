"""INC-10 tests — member legislation parsing + the covered-window pagination.
Offline: parse_items is pure; the paginator is driven by monkeypatched pages.
"""

from __future__ import annotations

import pytest

from ingest.legislation import _sponsored_gaps, parse_items
from ingest.models import LegItem

CONGS = [118, 119]
# 118th window is 2023-01-03..2025-01-03; 119th is 2025-01-03..2027-01-03.
TERMS_BOTH = [{"start": "2023-01-03", "end": "2027-01-03", "chamber": "house"}]
TERMS_119_ONLY = [{"start": "2025-01-03", "end": "2027-01-03", "chamber": "house"}]


def _leg(congress: int, bill_id: str = "hr1-119") -> LegItem:
    return LegItem(
        bill_id=bill_id, congress=congress, title="A Bill",
        introduced_date="2025-01-01", became_law=False,
        source_url="https://api.congress.gov/v3/bill/x",
    )


def test_sponsored_gaps_new_member_zero_prior_congress_is_ok():
    # R-2: terms begin in the 119th → the 118th is not served, so zero 118th bills is
    # legitimate (not a truncated fetch) and must not fail.
    assert _sponsored_gaps("N000001", TERMS_119_ONLY, [_leg(119)], CONGS) == []


def test_sponsored_gaps_served_congress_zero_still_fails():
    # Served both, but no 118th bill → truncated fetch, still flagged (guard intact).
    gaps = _sponsored_gaps("E000235", TERMS_BOTH, [_leg(119)], CONGS)
    assert len(gaps) == 1 and "congress 118" in gaps[0]


def test_sponsored_gaps_both_served_both_present_ok():
    assert _sponsored_gaps("E000235", TERMS_BOTH, [_leg(118), _leg(119)], CONGS) == []


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
