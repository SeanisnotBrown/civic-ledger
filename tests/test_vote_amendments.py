"""`ingest vote-amendments`: which amendment a House amendment vote was on.

The two things worth pinning: the selection rule (a vote on a Senate amendment
to the MEASURE is not an amendment vote of this chamber's, and the Senate names
its amendments in the question already) and the parse, which must return None
rather than an empty string when the Clerk's document carries no amendment.
"""

from __future__ import annotations

import pytest

from ingest.vote_amendments import is_house_amendment, parse_amendment

_WITH_AMENDMENT = """<?xml version="1.0"?>
<rollcall-vote><vote-metadata>
  <rollcall-num>669</rollcall-num>
  <amendment-num>57</amendment-num>
  <amendment-author>Lawler of New York Part B Amendment No. 114</amendment-author>
</vote-metadata></rollcall-vote>
"""

_WITHOUT = """<?xml version="1.0"?>
<rollcall-vote><vote-metadata>
  <rollcall-num>93</rollcall-num>
  <vote-question>On Passage</vote-question>
</vote-metadata></rollcall-vote>
"""

_EMPTY_FIELDS = """<?xml version="1.0"?>
<rollcall-vote><vote-metadata>
  <amendment-num></amendment-num>
  <amendment-author></amendment-author>
</vote-metadata></rollcall-vote>
"""


@pytest.mark.parametrize(
    ("rollcall", "expected"),
    [
        ({"chamber": "house", "question": "On Agreeing to the Amendment"}, True),
        ({"chamber": "house", "question": "on agreeing to the amendment"}, True),
        (
            {"chamber": "house", "question": "On Agreeing to the Amendment, as Modified"},
            True,
        ),
        # A vote on the MEASURE that happens to mention an amendment is not one.
        (
            {
                "chamber": "house",
                "question": "On Motion to Suspend the Rules and Concur in the Senate Amendment",
            },
            False,
        ),
        ({"chamber": "house", "question": "On Passage"}, False),
        # The Senate writes the designation into the question and names no sponsor.
        ({"chamber": "senate", "question": "On Agreeing to the Amendment"}, False),
        ({"chamber": "house", "question": None}, False),
        ({"chamber": "house"}, False),
    ],
)
def test_selection_rule(rollcall: dict, expected: bool) -> None:
    assert is_house_amendment(rollcall) is expected


def test_parse_returns_the_clerks_own_wording() -> None:
    number, author = parse_amendment(_WITH_AMENDMENT)
    assert number == "Amendment No. 57"
    assert author == "Lawler of New York Part B Amendment No. 114"


def test_parse_returns_none_when_the_document_has_no_amendment() -> None:
    assert parse_amendment(_WITHOUT) == (None, None)


def test_parse_treats_empty_fields_as_absent() -> None:
    """An empty element is the record saying nothing, not a claim of its own:
    returning "" would publish an "Amendment:" line with no amendment in it."""
    assert parse_amendment(_EMPTY_FIELDS) == (None, None)
