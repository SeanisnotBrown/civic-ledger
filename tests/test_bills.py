"""INC-8 tests — bill_id parsing + pure `parse_bill` against the committed hr1
sample (offline; never the network). The subjects/cosponsors deferral (D27) is
asserted so an empty list can never silently replace the None sentinel.
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
    b = parse_bill(_sample(), "hr1-119")
    assert isinstance(b, Bill)
    assert b.id == "hr1-119"
    assert (b.congress, b.type, b.number) == (119, "hr", 1)
    assert b.policy_area == "Economics and Public Finance"
    assert b.sponsor_id == "A000375"
    assert b.latest_action_date == "2025-07-04"
    assert b.source_url.startswith("https://www.congress.gov/")
    assert len(b.cbo_estimates) >= 1


def test_subjects_and_cosponsors_deferred_as_none() -> None:
    # D27: None = not-yet-collected, NEVER [] (which would assert "zero").
    b = parse_bill(_sample(), "hr1-119")
    assert b.subjects is None
    assert b.cosponsor_ids is None


def test_html_entities_decoded_in_titles() -> None:
    b = parse_bill(_sample(), "hr1-119")
    # The sample's CBO titles carry &#039; / &amp; — decoded, never raw entities.
    for c in b.cbo_estimates:
        assert "&#039;" not in c.title
        assert "&amp;" not in c.title
    assert "&#039;" not in b.title_official


def test_missing_latest_action_raises() -> None:
    data = _sample()
    del data["bill"]["latestAction"]
    with pytest.raises((KeyError, ValidationError)):
        parse_bill(data, "hr1-119")
