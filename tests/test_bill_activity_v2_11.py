"""V2-11 task 2 — `bill_actions()` and `bills_updated_since()` (source layer).

Offline: `congress_gov._get` is monkeypatched, so nothing here touches the live
API or the disk cache.

The pagination branch of `bill_actions` is the reason most of this file exists.
D88 probed four of the longest bills on record and the largest action list found
was 234 (`hr2670-118`, NDAA FY24) — under the 250 page ceiling — so
`pagination.next` has NEVER been returned by the live `/actions` endpoint. The
paginated loop therefore cannot be confirmed against the API and is covered here
against synthetic payloads instead. The D88 entry records that limitation; these
tests are the compensating control, not a substitute for it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ingest.sources import congress_gov
from ingest.sources.congress_gov import TruncatedFetchError


class _Resp:
    def __init__(self, page):
        self._page = page

    def json(self):
        return self._page


def _pager(pages, calls=None, seen=None):
    """A fake `_get` that serves `pages` keyed by the requested offset, and
    optionally records the offsets requested and the params sent."""

    def fake_get(path, params=None, **kw):
        params = params or {}
        if seen is not None:
            seen.update(params)
            seen["_path"] = path
        if calls is not None:
            calls.append(int(params.get("offset", 0)))
        return _Resp(pages[int(params.get("offset", 0))])

    return fake_get


def _action(date, text, *, time=None, code=None):
    """One action row in the live shape (SHAPES.md section 9). `actionTime`,
    `actionCode`, `committees` and `calendarNumber` are all optional there, so
    the helper omits rather than nulls them."""
    a = {
        "actionDate": date,
        "text": text,
        "type": "Floor",
        "sourceSystem": {"code": 9, "name": "Library of Congress"},
    }
    if time is not None:
        a["actionTime"] = time
    if code is not None:
        a["actionCode"] = code
    return a


def _bill(num, congress=119, btype="HR"):
    return {
        "congress": congress,
        "type": btype,
        "number": str(num),
        "title": f"Bill {num}",
        "introducedDate": "2025-02-14",
        "latestAction": {"actionDate": "2025-02-14", "text": "Referred."},
        "updateDate": "2026-10-01",
    }


# --- _iso_z ------------------------------------------------------------------
def test_iso_z_formats_naive_as_utc():
    assert congress_gov._iso_z(datetime(2026, 10, 1, 14, 9, 46)) == "2026-10-01T14:09:46Z"


def test_iso_z_converts_aware_and_drops_subseconds():
    # The API rejects sub-second precision; an aware input is converted, not assumed.
    when = datetime(2026, 10, 1, 14, 9, 46, 123456, tzinfo=UTC)
    assert congress_gov._iso_z(when) == "2026-10-01T14:09:46Z"


# --- bill_actions ------------------------------------------------------------
def test_bill_actions_single_page(monkeypatch):
    pages = {
        0: {
            "actions": [
                _action("2024-01-02", "Passed House.", time="15:45:30"),
                _action("2024-01-01", "Introduced."),
            ],
            "pagination": {"count": 2},
        }
    }
    monkeypatch.setattr(congress_gov, "_get", _pager(pages))
    got = congress_gov.bill_actions(118, "HR", 2670)
    assert [a["text"] for a in got] == ["Passed House.", "Introduced."]
    # Order is the API's (newest first) and is never re-sorted: actionTime is
    # absent on most rows (142/234 on the NDAA), so it cannot be a sort key.
    assert "actionTime" not in got[1]


def test_bill_actions_lowercases_bill_type_in_path(monkeypatch):
    seen = {}
    pages = {0: {"actions": [_action("2024-01-01", "Introduced.")], "pagination": {"count": 1}}}
    monkeypatch.setattr(congress_gov, "_get", _pager(pages, seen=seen))
    congress_gov.bill_actions(118, "HR", 2670)
    assert seen["_path"] == "bill/118/hr/2670/actions"


def test_bill_actions_paginates_past_the_250_ceiling(monkeypatch):
    """THE UNEXERCISED BRANCH (D88). No live bill has exceeded 250 actions, so
    this synthetic 300-action timeline is the only coverage the loop gets."""
    pages = {
        0: {
            "actions": [_action("2024-01-01", f"action {i}") for i in range(250)],
            "pagination": {"count": 300},
        },
        250: {
            "actions": [_action("2024-01-01", f"action {i}") for i in range(250, 300)],
            "pagination": {"count": 300},
        },
    }
    calls = []
    monkeypatch.setattr(congress_gov, "_get", _pager(pages, calls=calls))
    got = congress_gov.bill_actions(118, "hr", 1)
    assert calls == [0, 250]
    assert len(got) == 300
    assert got[-1]["text"] == "action 299"


def test_bill_actions_dedupes_a_row_reserved_across_pages(monkeypatch):
    """A re-serve means the second page carries one EXTRA row, not one fewer:
    301 rows served for a count of 300, of which 300 are unique."""
    dup = _action("2024-01-01", "Introduced.", code="H11100")
    pages = {
        0: {
            "actions": [_action("2024-02-01", f"a{i}") for i in range(249)] + [dup],
            "pagination": {"count": 300},
        },
        250: {
            "actions": [dup] + [_action("2024-03-01", f"b{i}") for i in range(50)],
            "pagination": {"count": 300},
        },
    }
    monkeypatch.setattr(congress_gov, "_get", _pager(pages))
    got = congress_gov.bill_actions(118, "hr", 1)
    assert len(got) == 300  # 301 rows served, one of them twice
    assert sum(1 for a in got if a["text"] == "Introduced.") == 1


def test_bill_actions_keeps_byte_identical_rows_the_api_serves(monkeypatch):
    """REGRESSION, D100. This payload used to RAISE, and that cost 15 bills.

    The old loop collapsed byte-identical rows inside a single page and then
    compared the surviving count against `pagination.count`, so any bill whose
    record repeats a row failed deterministically. Measured over the complete
    Congress 118 enumeration: 15 of 19,118 bills do repeat one (hr9748-118 four
    times), every one of them with `len(rows) == count` and no `next` page — so
    nothing was truncated. govinfo's authoritative BILLSTATUS XML carries the
    same repeats, i.e. they are the government's record, not our artefact.
    All rows served must survive, verbatim and in order."""
    dup = _action("2024-01-01", "Introduced.", code="H11100")
    pages = {
        0: {
            "actions": [_action("2024-02-01", f"a{i}") for i in range(248)] + [dup, dup],
            "pagination": {"count": 250},
        }
    }
    monkeypatch.setattr(congress_gov, "_get", _pager(pages))
    got = congress_gov.bill_actions(118, "hr", 1)
    assert len(got) == 250, "a page's own repeats are the record, not a dedupe target"
    assert sum(1 for a in got if a["text"] == "Introduced.") == 2


def test_bill_actions_keeps_a_within_page_repeat_once_across_a_re_serve(monkeypatch):
    """The two rules together: a page's repeats survive, a LATER page's re-serve
    of those same rows does not. Final multiplicity is the largest any single
    page claimed — two here, never one and never four."""
    dup = _action("2024-01-01", "Referred to the Subcommittee on Health.", code="H11000")
    pages = {
        0: {
            "actions": [_action("2024-02-01", f"a{i}") for i in range(248)] + [dup, dup],
            "pagination": {"count": 300},
        },
        250: {
            "actions": [dup, dup] + [_action("2024-03-01", f"b{i}") for i in range(50)],
            "pagination": {"count": 300},
        },
    }
    monkeypatch.setattr(congress_gov, "_get", _pager(pages))
    got = congress_gov.bill_actions(118, "hr", 1)
    assert len(got) == 300  # 302 rows served, the repeated pair served twice
    assert sum(1 for a in got if a["text"].startswith("Referred to")) == 2


def test_bill_actions_raises_when_a_single_page_is_short_of_its_own_count(monkeypatch):
    """The post-loop guard, which survives D100 unchanged in meaning: holding
    fewer rows than the government's own `count` is an incomplete timeline and
    must raise rather than publish short. No `next`, no empty page — the
    empty-page guard below cannot see this one."""
    pages = {
        0: {
            "actions": [_action("2024-01-01", f"a{i}") for i in range(21)],
            "pagination": {"count": 22},
        }
    }
    monkeypatch.setattr(congress_gov, "_get", _pager(pages))
    with pytest.raises(TruncatedFetchError, match="21 rows < count 22"):
        congress_gov.bill_actions(118, "hr", 9748)


def test_bill_actions_distinguishes_rows_differing_only_by_time(monkeypatch):
    # Two real actions can share a date and text but differ in actionTime;
    # collapsing them would undercount the timeline.
    pages = {
        0: {
            "actions": [
                _action("2024-01-01", "Considered.", time="10:00:00"),
                _action("2024-01-01", "Considered.", time="14:30:00"),
            ],
            "pagination": {"count": 2},
        }
    }
    monkeypatch.setattr(congress_gov, "_get", _pager(pages))
    assert len(congress_gov.bill_actions(118, "hr", 1)) == 2


def test_bill_actions_keeps_rows_differing_only_by_committee(monkeypatch):
    """REGRESSION, caught by the live smoke test, not by this suite.

    The first cut of this function keyed the dedupe on
    (actionDate, actionTime, actionCode, text). hr2670-118 has FIVE rows reading
    "Forwarded by Subcommittee to Full Committee by Voice Vote ." on 2023-06-13
    with code H23000, and SIX reading "Subcommittee Consideration and Mark-up
    Session Held." -- each a different subcommittee, distinguished only by
    `committees`. The narrow key silently collapsed 234 real actions to 225: a
    false undercount of a published timeline, which value #1 forbids. Dedupe is
    on the whole row for exactly this reason."""
    def _fwd(subcommittee, code):
        return {
            "actionCode": code,
            "actionDate": "2023-06-13",
            "committees": [{"name": subcommittee, "systemCode": f"hsas{len(subcommittee)}"}],
            "sourceSystem": {"code": 1, "name": "House committee actions"},
            "text": "Forwarded by Subcommittee to Full Committee by Voice Vote .",
            "type": "Committee",
        }

    rows = [
        _fwd("Cyber, Information Technologies, and Innovation Subcommittee", "H23000"),
        _fwd("Seapower and Projection Forces Subcommittee", "H23000"),
        _fwd("Military Personnel Subcommittee", "H23000"),
        _fwd("Tactical Air and Land Forces Subcommittee", "H23000"),
        _fwd("Intelligence and Special Operations Subcommittee", "H23000"),
    ]
    monkeypatch.setattr(
        congress_gov, "_get", _pager({0: {"actions": rows, "pagination": {"count": 5}}})
    )
    got = congress_gov.bill_actions(118, "hr", 2670)
    assert len(got) == 5, "rows differing only by committee must all survive"
    assert len({c["committees"][0]["name"] for c in got}) == 5


def test_bill_actions_empty_is_not_an_error(monkeypatch):
    # [] means the government lists no actions. Distinct from the Bill.actions
    # is None "not collected" sentinel (D27) that the caller owns.
    monkeypatch.setattr(
        congress_gov, "_get", _pager({0: {"actions": [], "pagination": {"count": 0}}})
    )
    assert congress_gov.bill_actions(119, "hr", 9999) == []


def test_bill_actions_raises_on_truncated_page(monkeypatch):
    """D64 contract: an empty page while offset < count is a corrupt 200 that
    would publish an incomplete timeline. It must raise, not return short."""
    pages = {
        0: {
            "actions": [_action("2024-01-01", f"a{i}") for i in range(250)],
            "pagination": {"count": 300},
        },
        250: {"actions": [], "pagination": {"count": 300}},
    }
    monkeypatch.setattr(congress_gov, "_get", _pager(pages))
    with pytest.raises(TruncatedFetchError, match="offset 250 < count 300"):
        congress_gov.bill_actions(118, "hr", 1)


def test_bill_actions_trusts_page_zero_count_not_a_later_page(monkeypatch):
    # A later page's own metadata is not trusted (same rule as member_legislation):
    # a corrupt count on page 2 must not end the loop early.
    pages = {
        0: {
            "actions": [_action("2024-01-01", f"a{i}") for i in range(250)],
            "pagination": {"count": 300},
        },
        250: {
            "actions": [_action("2024-01-01", f"b{i}") for i in range(50)],
            "pagination": {"count": 1},
        },
    }
    monkeypatch.setattr(congress_gov, "_get", _pager(pages))
    assert len(congress_gov.bill_actions(118, "hr", 1)) == 300


# --- bills_updated_since -----------------------------------------------------
def test_bills_updated_since_sends_the_working_sort_form(monkeypatch):
    """D88's headline trap: `sort=updateDate+desc` is SILENTLY ignored (it returns
    the same page as a bogus sort value). The literal-space form is the only one
    that sorts. A regression here would be invisible in the data."""
    seen = {}
    pages = {0: {"bills": [_bill(1)], "pagination": {"count": 1}}}
    monkeypatch.setattr(congress_gov, "_get", _pager(pages, seen=seen))
    congress_gov.bills_updated_since(congress=119)
    assert seen["sort"] == "updateDate desc"
    assert "+" not in seen["sort"]
    assert seen["limit"] == "250"


def test_bills_updated_since_window_becomes_iso_z_params(monkeypatch):
    seen = {}
    pages = {0: {"bills": [], "pagination": {"count": 0}}}
    monkeypatch.setattr(congress_gov, "_get", _pager(pages, seen=seen))
    congress_gov.bills_updated_since(
        datetime(2026, 9, 30, 14, 0, 0), datetime(2026, 10, 1, 14, 0, 0)
    )
    assert seen["fromDateTime"] == "2026-09-30T14:00:00Z"
    assert seen["toDateTime"] == "2026-10-01T14:00:00Z"
    assert seen["_path"] == "bill"  # no congress scope given


def test_bills_updated_since_scopes_to_one_congress(monkeypatch):
    seen = {}
    pages = {0: {"bills": [], "pagination": {"count": 0}}}
    monkeypatch.setattr(congress_gov, "_get", _pager(pages, seen=seen))
    congress_gov.bills_updated_since(congress=118)
    assert seen["_path"] == "bill/118"


def test_bills_updated_since_omits_absent_window_params(monkeypatch):
    # The backfill passes no window at all; sending empty strings would filter
    # to nothing rather than enumerate everything.
    seen = {}
    pages = {0: {"bills": [], "pagination": {"count": 0}}}
    monkeypatch.setattr(congress_gov, "_get", _pager(pages, seen=seen))
    congress_gov.bills_updated_since(congress=119)
    assert "fromDateTime" not in seen
    assert "toDateTime" not in seen


def test_bills_updated_since_pages_a_whole_congress(monkeypatch):
    """The backfill path: 19,315 bills in the 118th, no deep-offset ceiling
    (D88 follow-up). Scaled down to 3 pages here."""
    pages = {
        0: {"bills": [_bill(i) for i in range(250)], "pagination": {"count": 600}},
        250: {"bills": [_bill(i) for i in range(250, 500)], "pagination": {"count": 600}},
        500: {"bills": [_bill(i) for i in range(500, 600)], "pagination": {"count": 600}},
    }
    calls = []
    monkeypatch.setattr(congress_gov, "_get", _pager(pages, calls=calls))
    got = congress_gov.bills_updated_since(congress=118)
    assert calls == [0, 250, 500]
    assert len(got) == 600


def test_bills_updated_since_dedupes_a_bill_reserved_mid_crawl(monkeypatch):
    """Why UPDATE_SORT is descending: a bill touched mid-crawl jumps to page 0
    and the pages behind it shift down, so a crawl RE-READS rather than skips.
    The duplicate must not reach the caller twice."""
    pages = {
        0: {"bills": [_bill(i) for i in range(250)], "pagination": {"count": 300}},
        250: {
            "bills": [_bill(249)] + [_bill(i) for i in range(250, 299)],
            "pagination": {"count": 300},
        },
    }
    monkeypatch.setattr(congress_gov, "_get", _pager(pages))
    got = congress_gov.bills_updated_since(congress=119)
    assert len(got) == 299
    idents = [(b["congress"], b["type"], b["number"]) for b in got]
    assert len(idents) == len(set(idents))


def test_bills_updated_since_identity_is_case_insensitive_on_type(monkeypatch):
    # "HR" and "hr" are the same bill; a case flip must not duplicate it.
    pages = {
        0: {
            "bills": [_bill(1, btype="HR")] + [_bill(i) for i in range(2, 251)],
            "pagination": {"count": 300},
        },
        250: {
            "bills": [_bill(1, btype="hr")] + [_bill(i) for i in range(251, 300)],
            "pagination": {"count": 300},
        },
    }
    monkeypatch.setattr(congress_gov, "_get", _pager(pages))
    got = congress_gov.bills_updated_since(congress=119)
    assert sum(1 for b in got if str(b["number"]) == "1") == 1


def test_bills_updated_since_raises_on_truncated_page(monkeypatch):
    pages = {
        0: {"bills": [_bill(i) for i in range(250)], "pagination": {"count": 600}},
        250: {"bills": [], "pagination": {"count": 600}},
    }
    monkeypatch.setattr(congress_gov, "_get", _pager(pages))
    with pytest.raises(TruncatedFetchError, match="offset 250 < count 600"):
        congress_gov.bills_updated_since(congress=119)


def test_bills_updated_since_empty_window_is_not_an_error(monkeypatch):
    # A quiet hour legitimately matches nothing.
    monkeypatch.setattr(
        congress_gov, "_get", _pager({0: {"bills": [], "pagination": {"count": 0}}})
    )
    assert congress_gov.bills_updated_since(datetime(2026, 10, 1, 3, 0, 0)) == []


# --- the constants are load-bearing, not decoration --------------------------
def test_page_limit_matches_the_api_ceiling():
    # limit=251 silently clamps to 250 (D88) rather than erroring, so the
    # paginators bound on pagination.count and this constant must not drift up.
    assert congress_gov.PAGE_LIMIT == 250


def test_update_sort_uses_a_literal_space():
    assert congress_gov.UPDATE_SORT == "updateDate desc"
