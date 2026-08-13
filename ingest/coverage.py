"""V2-1 (D60/D61) — the shared "who was expected to vote on date D" computation.

Before V2-1, coverage was per-Congress (`legislators._term_overlaps`): fine
when the covered set was 6 members with zero mid-congress turnover. At full
roster scale that granularity is wrong — the 118th Congress alone saw a
Speaker resign, a member expelled, two members die in office, and a Senate
seat change hands twice mid-term. A per-Congress "expected" set puts every one
of them on the roster for the WHOLE congress, so a naive coverage check would
flag them "missing" on every roll outside their actual service window: false
positives, permanently red CI (D60).

This module is the ONE place that computes "who was covered, and who was
EXPECTED to have a recorded position, on this exact date" — vote parsing
(`house_votes.py`, `senate_votes.py`) and the CI checks that verify coverage
(`checks/symmetry.py`, `verify_recompute.py`) all import it, so ingest-time
filtering and check-time verification can never drift against each other (the
same failure mode `checks/symmetry.py`'s original `_covered` was already
written to avoid, just at congress granularity).

`covered_on()` answers "who held this seat on this date" — used as the roster
for the R-2 `UnknownMember` churn guard (a delegate or the Speaker showing up
in a roll's results is never "unknown," they simply may not be EXPECTED on
every roll). `expected_on()` narrows that to "who should have a position on
this specific roll" by subtracting three empirically-found, non-evaluative
exceptions (D61), each real and none a guess:

  1. **Delegates** (`legislators.VOTING_STATES`) are constitutionally barred
     from voting on final-passage House rolls; they cast real recorded votes
     on ~1/3 of rolls (Committee of the Whole — verified empirically, V2-1:
     623 of 1,886 House rolls, all 6 delegates present together every time).
     They are never "expected," but when the source includes them they are
     persisted like anyone else — `expected_on` only affects gap-reporting,
     never what gets recorded.
  2. **The Speaker** customarily does not vote on routine business — a
     150-year House norm, not a data error (`SPEAKER_EXCEPTIONS`, cited).
  3. **Seating lag** (`SEATING_LAG_DAYS`): a short, empirically-measured gap
     between a member's recorded term-start/end date and when Congress.gov's
     per-roll results actually reflect their seating or departure (found via
     a special-election member whose gaps traced exactly to his first two
     weeks in office).
"""

from __future__ import annotations

import json
from datetime import date as _date
from pathlib import Path

from ingest.sources.legislators import VOTING_STATES


def member_terms(members_dir: Path, chamber: str) -> dict[str, list[tuple[str, str]]]:
    """{bioguide: [(start, end), ...]} for every committed member's `chamber`
    terms. Read once by a caller and reused across many `covered_on` calls —
    this function itself does the only file I/O.

    Filters on each TERM's chamber, never on `Member.chamber` (the member's
    latest/current chamber) — a person who moved chambers (e.g. a House member
    in the 118th who won a Senate seat for the 119th) has real terms in BOTH
    chambers, and `Member.chamber` only reflects the latest one. Filtering on
    it here silently dropped every one of their House rolls and misfired the
    churn guard as `UnknownMember` (found empirically, V2-1 P2 — every member
    who ever switched chambers was invisible to the chamber they left)."""
    out: dict[str, list[tuple[str, str]]] = {}
    if not members_dir.exists():
        return out
    for path in sorted(members_dir.glob("*.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        terms = [(t["start"], t["end"]) for t in m["terms"] if t["chamber"] == chamber]
        if terms:
            out[m["id"]] = terms
    return out


def covered_on(terms: dict[str, list[tuple[str, str]]], date: str) -> set[str]:
    """Bioguides whose term inclusively covers `date` (an ISO 8601 string; only
    the leading YYYY-MM-DD is compared, so a full timestamp is fine to pass in).
    Term boundaries are dates from congress-legislators, which record real
    resignation/death/seating dates, not congress-window defaults."""
    day = date[:10]
    return {
        mid for mid, spans in terms.items() if any(start <= day <= end for start, end in spans)
    }


def delegate_bioguides(members_dir: Path) -> set[str]:
    """Bioguides whose seat is one of the 6 non-voting House delegate
    territories (D61) — `Member.state` not in `legislators.VOTING_STATES`."""
    out: set[str] = set()
    if not members_dir.exists():
        return out
    for path in sorted(members_dir.glob("*.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        if m.get("state") not in VOTING_STATES:
            out.add(m["id"])
    return out


# Speaker bioguides + the (inclusive) date range they held the gavel — a
# maintained, cited exceptions list (D61), not a guess. The Speaker customarily
# doesn't vote on routine business; extend this tuple when a new Congress
# convenes or the gavel changes hands.
#   McCarthy: elected Speaker 2023-01-07 (after 15 ballots); removed 2023-10-03.
#   Johnson: elected Speaker 2023-10-25; serving through the 119th as of writing.
SPEAKER_EXCEPTIONS: tuple[tuple[str, str, str], ...] = (
    ("M001165", "2023-01-07", "2023-10-03"),  # Kevin McCarthy
    ("J000299", "2023-10-25", "2027-01-03"),  # Mike Johnson
)


def speaker_on(date: str) -> set[str]:
    """The sitting Speaker's bioguide on `date`, if any (empty most of the
    time — only nonempty for the two dated ranges in SPEAKER_EXCEPTIONS)."""
    day = date[:10]
    return {bio for bio, start, end in SPEAKER_EXCEPTIONS if start <= day <= end}


# Days of tolerance around a member's term start/end during which a missing
# roll position is not flagged as a gap. Sized from real data (V2-1 P2): members
# seated via special election (Rulli, OH-06, 2024-06-11; Suozzi, NY-03,
# 2024-02-13) were missing from results for up to 15 days after their recorded
# term-start date, then appeared normally — 21 gives margin. Mechanical (not
# evaluative) — a data-lag allowance, not a leniency toward any member's actual
# attendance.
SEATING_LAG_DAYS = 21


def seating_lag_on(terms: dict[str, list[tuple[str, str]]], date: str) -> set[str]:
    """Bioguides whose nearest term boundary to `date` is within
    SEATING_LAG_DAYS — see module docstring point 3."""
    day = _date.fromisoformat(date[:10])
    out: set[str] = set()
    for mid, spans in terms.items():
        for start, end in spans:
            if abs((day - _date.fromisoformat(start)).days) <= SEATING_LAG_DAYS:
                out.add(mid)
                break
            if abs((day - _date.fromisoformat(end)).days) <= SEATING_LAG_DAYS:
                out.add(mid)
                break
    return out


def expected_on(
    terms: dict[str, list[tuple[str, str]]], date: str, delegates: set[str]
) -> set[str]:
    """The gap-checking set for `date`: `covered_on()` minus the three D61
    exceptions (delegates, the sitting Speaker, seating lag). Never used for
    the R-2 churn guard — that stays `covered_on()`, the full roster, so a
    delegate or Speaker showing up in real results is always accepted, never
    flagged `UnknownMember`."""
    return covered_on(terms, date) - delegates - speaker_on(date) - seating_lag_on(terms, date)
