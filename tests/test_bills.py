"""INC-8/INC-10 tests — bill_id parsing + pure `parse_bill` against the committed
hr1 sample (offline; never the network), plus the INC-10 sub-resource enrichment:
the paginated subjects/cosponsors enumerators and the anti-clobber guarantee that a
re-ingest re-exports the enriched lists rather than reverting them to the D27 `None`
"not collected" sentinel (the D35 clobber shape, applied to bills).
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ingest.bills import BadBillId, parse_bill, parse_bill_id
from ingest.cache import repo_root
from ingest.models import Bill

SAMPLE = repo_root() / "data" / "quality" / "samples" / "congress_bill_hr1_119.json"


def _sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def _parse(bill_id: str = "hr1-119", **kw) -> Bill:
    kw.setdefault("subjects", [])
    kw.setdefault("cosponsor_ids", [])
    return parse_bill(_sample(), bill_id, **kw)


@pytest.mark.parametrize(
    "bill_id,expected",
    [
        ("hr1-119", ("hr", 1, 119)),
        ("s1234-118", ("s", 1234, 118)),
        ("hconres108-119", ("hconres", 108, 119)),
        ("sjres5-118", ("sjres", 5, 118)),
    ],
)
def test_parse_bill_id(bill_id: str, expected: tuple[str, int, int]) -> None:
    assert parse_bill_id(bill_id) == expected


@pytest.mark.parametrize("bad", ["hr1", "119-hr1", "hr-119", "HR1-119", ""])
def test_parse_bill_id_rejects_garbage(bad: str) -> None:
    with pytest.raises(BadBillId):
        parse_bill_id(bad)


def test_parse_bill_core_fields() -> None:
    b = _parse()
    assert isinstance(b, Bill)
    assert b.id == "hr1-119"
    assert (b.congress, b.type, b.number) == (119, "hr", 1)
    assert b.policy_area == "Economics and Public Finance"
    assert b.sponsor_id == "A000375"
    assert b.latest_action_date == "2025-07-04"
    assert b.source_url.startswith("https://www.congress.gov/")
    assert len(b.cbo_estimates) >= 1


def test_subjects_cosponsors_incorporated_and_sorted() -> None:
    # INC-10: the caller-fetched lists are stored verbatim (parse is pure).
    b = parse_bill(
        _sample(), "hr1-119",
        subjects=["Taxation", "Abortion"],
        cosponsor_ids=["Z000001", "A000001"],
    )
    assert b.subjects == ["Taxation", "Abortion"]          # parse preserves given order
    assert b.cosponsor_ids == ["Z000001", "A000001"]       # sorting is the fetcher's job


def test_none_vs_empty_sentinel_preserved() -> None:
    # D27: None = not-yet-collected (distinct from [] = collected, none exist).
    # parse_bill records exactly what it's given — it never coerces one to the other.
    b_none = parse_bill(_sample(), "hr1-119", subjects=None, cosponsor_ids=None)
    assert b_none.subjects is None and b_none.cosponsor_ids is None
    b_empty = parse_bill(_sample(), "hr1-119", subjects=[], cosponsor_ids=[])
    assert b_empty.subjects == [] and b_empty.cosponsor_ids == []


def test_html_entities_decoded_in_titles() -> None:
    b = _parse()
    # The sample's CBO titles carry &#039; / &amp; — decoded, never raw entities.
    for c in b.cbo_estimates:
        assert "&#039;" not in c.title
        assert "&amp;" not in c.title
    assert "&#039;" not in b.title_official


def test_missing_latest_action_raises() -> None:
    data = _sample()
    del data["bill"]["latestAction"]
    with pytest.raises((KeyError, ValidationError)):
        parse_bill(data, "hr1-119", subjects=[], cosponsor_ids=[])


# --- INC-10 sub-resource enumerators (paginated) --------------------------


def test_bill_subjects_pages_and_sorts(monkeypatch: pytest.MonkeyPatch) -> None:
    from ingest.sources import congress_gov

    pages = [
        {"subjects": {"legislativeSubjects": [{"name": "Taxation"}, {"name": "Abortion"}]},
         "pagination": {"count": 3}},
        {"subjects": {"legislativeSubjects": [{"name": "Health"}]},
         "pagination": {"count": 3}},
        {"subjects": {"legislativeSubjects": []}, "pagination": {"count": 3}},
    ]
    calls: list[int] = []

    class _Resp:
        def __init__(self, i: int) -> None:
            self._i = i
        def json(self) -> dict:
            return pages[self._i]

    def fake_get(path: str, params: dict, **kw) -> _Resp:
        idx = int(params["offset"]) // 250
        calls.append(idx)
        return _Resp(min(idx, len(pages) - 1))

    monkeypatch.setattr(congress_gov, "_get", fake_get)
    # count=3 <= 250 stops after the first page; assert the single page is read + sorted.
    assert congress_gov.bill_subjects(119, "hr", 1) == ["Abortion", "Taxation"]


def test_bill_cosponsors_excludes_withdrawn(monkeypatch: pytest.MonkeyPatch) -> None:
    from ingest.sources import congress_gov

    page = {
        "cosponsors": [
            {"bioguideId": "B000001"},
            {"bioguideId": "A000001"},
            {"bioguideId": "W000001", "sponsorshipWithdrawnDate": "2024-01-01"},
        ],
        "pagination": {"count": 3},
    }

    class _Resp:
        def json(self) -> dict:
            return page

    monkeypatch.setattr(congress_gov, "_get", lambda *a, **k: _Resp())
    # Withdrawn cosponsor dropped; the rest sorted.
    assert congress_gov.bill_cosponsor_ids(119, "hr", 1) == ["A000001", "B000001"]


# --- anti-clobber: a re-ingest re-exports enrichment, never reverts to None ---


def test_reingest_reexports_enrichment_not_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """The D35 clobber shape applied to bills: `run()` must fetch + set the
    sub-resources on every export, so a nightly re-ingest of an already-enriched
    bill writes the lists again rather than the `None` sentinel."""
    from ingest import bills
    from ingest.sources import congress_gov

    monkeypatch.setattr(bills, "referenced_bill_ids", lambda: ["hr1-119"])
    monkeypatch.setattr(congress_gov, "bill_detail", lambda *a, **k: _DetailResp())
    monkeypatch.setattr(congress_gov, "bill_subjects", lambda *a, **k: ["Taxation"])
    monkeypatch.setattr(congress_gov, "bill_cosponsor_ids", lambda *a, **k: ["A000001"])

    captured: list[Bill] = []
    import ingest.export as export_mod
    monkeypatch.setattr(export_mod, "export_bill", lambda b, *a, **k: captured.append(b))

    # --all bypasses skip-if-final so the (already-exported) bill is re-processed.
    assert bills.run(["--all"]) == 0
    assert len(captured) == 1
    assert captured[0].subjects == ["Taxation"]        # NOT None
    assert captured[0].cosponsor_ids == ["A000001"]    # NOT None


class _DetailResp:
    def json(self) -> dict:
        return _sample()
