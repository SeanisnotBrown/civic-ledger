"""The free rule-based pre-filter (§5 Phase 3 owner decision 2). No AI, no network.

Every statement a collector gathers passes through here BEFORE a cent is spent. The
decision says what it drops — ceremonial items, office logistics, procedural floor
remarks, and duplicates of the same announcement across sources — and says the thing
that matters more than the list: **every drop is logged with its reason**, because a
silent filter is a hidden editorial judgment.

## Source-agnostic by contract

The input is a list of statement records: the dict shape `statements_crec.statement_record`
emits, which collector (a) and every later collector also emit. Nothing in this module
branches on `source`. The fields read are:

    member_id  date  granule_id  source  title  segments  attribution   (required)
    granule_class  chamber  url  speakers  parsed_name  chars           (carried through)

`segments` is the list of the member's own turns, in order. A collector with one body of
text per statement passes a one-element list. `granule_class` is absent outside the
Congressional Record and defaults to `""`, which no rule branches on.

## The unit is the TURN, not the granule

One Congressional Record granule can hold a member's housekeeping request AND their
twenty-minute policy speech, as two consecutive turns. Measured 2026-10-13 on the pilot
corpus: 4,630 granules hold 7,611 turns. Filtering whole granules would either throw the
speech away with the request or pay the categorizer to read the request. So a rule
judges one turn; a statement survives with the turns that survived, and is dropped only
when none did.

## Rule order is fixed, and the first match wins

Reordering changes the per-rule counts and so changes the fairness table, which would
make the published numbers unreproducible. The order:

  1. `no-attributable-text`   the Record names the member but no words could be
                              attributed (`attribution == "none"`, or no turns). 48 rows
                              in the pilot corpus. Logged, never silently passed.
  2. `inserted-material`      NOT a drop: the cut of fact 5. See below.
  3. `vote-explanation`       kept, but marked ineligible for AI. See R3 below.
  4. `procedural`             housekeeping turns. See R2 below.
  5. `ceremonial`             tributes, memorials, congratulations. See R1 below.
  6. `office-logistics`       town halls, grant announcements, application deadlines.
  7. `duplicate`              the same member's same words already kept, from any
                              source. Keyed on normalized text, so it fires across
                              collectors as well as within one.

## The owner's four rulings, 2026-10-14

Everything evaluative here was ratified by the owner against real examples from this
corpus. The builder authored none of it (§1).

**R1 — ceremonial, EXCEPT when it argues policy.** A tribute is dropped unless the same
turn names a bill or urges a vote, in which case it survives whole. Measured: 1,456 of
7,611 turns match the ceremonial patterns (D 21.5% / R 17.3%) and 66 of those also argue
policy, skewed D 46 / R 20 — a real argument wrapped in a commemoration, which the
rescue keeps. Example the owner ruled on: a Holocaust-remembrance Extension closing
"Mr. Speaker, I urge my colleagues ... to go see this comparative analogy".

**R2 — a vote urge is a position, so procedural never eats one.** A turn is dropped as
procedural only when all three hold: it performs one of the named housekeeping acts in
`PROCEDURAL_SUB_RULES`, its content is under `PROCEDURAL_MAX_CHARS`, and it carries no
vote urge and names no bill. The length
guard stays because the alternative is eating a 40,000-character floor speech that opens
with a unanimous-consent request; the policy escape is what the owner added on top of it.
Both guards together drop strictly less than either alone. Example the owner ruled on,
now KEPT at 120 characters: "in closing, I encourage a ``yes'' vote on this particular
piece of legislation, and I yield back the balance of my time."

**R3 — vote explanations are kept, and never sent to the AI.** "Had I been present, I
would have voted YEA on Roll Call No. 559" is procedural in form and a recorded stance in
substance: 80 rows, 41,223 characters, D 55 / R 25. They stay in the record as statements
and carry `ai_eligible: False` with `ai_ineligible_reason: "vote-explanation"`, so the
triage gate and the categorizer skip them and spend nothing. Matching them to the roll
call they name is mechanical and belongs to a later task, not to this filter.

**R4 — the uneven procedural rate is accepted, with the sub-rule table published.** The
procedural rule drops Republican turns at roughly 2.3x the Democratic rate. The cause is
structural rather than editorial: the majority party's floor managers make the
housekeeping requests, so "revise and extend their remarks" runs R 270 / D 7 and bare
unanimous-consent requests run R 321 / D 72. Decision 4 stops the run on an uneven step;
the owner accepted it ON CONDITION that the drop log and the report break the gap down to
each sub-rule, so the explanation is checkable rather than asserted. `sub_rule` on every
procedural drop is that condition, and `fairness()` publishes the table.

## The inserted-material cut (fact 5, owner 2026-10-13)

"Mr. Speaker, I include in the Record the Tampa Bay Times article of December ..." is
followed by text the member did not write, stored as their words. Measured on the pilot
corpus: 71 rows, 1,575,308 characters — 7.8% of all collected text, D 7.2% / R 8.4%.

**The cut is at the member's own marker sentence, keeping everything up to and including
it** — the marker is his words; what follows is not. This is not a drop: the turn
survives, shortened, and the row records how many characters went.

Deliberately NOT a marker: "I ask unanimous consent that all Members may have 5
legislative days to revise and extend their remarks and insert extraneous material." That
is a floor manager granting everyone leave to file, not this member inserting anything —
it matched 278 rows and 15.9% of the corpus when the first draft of the pattern let it
through, which would have truncated hundreds of real speeches at their opening sentence.

## Output

  * `data/quality/statement-prefilter-drops.json` — the committed drop log. Sorted, no
    wall-clock anywhere in it, so a re-run over unchanged input is byte-identical
    (same discipline as `checks/archive_links.py`). One entry per dropped turn.
  * the surviving statements, returned to the caller, for the count report and the
    triage gate to read.

    uv run ingest prefilter             # every collector's output, writes the drop log
    uv run ingest prefilter --dry-run   # counts only, writes nothing
    uv run ingest prefilter --report    # and the count-before-spend report (decision 4)
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ingest.cache import atomic_write_text, repo_root
from ingest.statements_press import COMPLETE_STOPS

# R2's length guard, in characters of CONTENT (after the speaker's name and the
# salutation are stripped). 200 is where the pilot corpus separates pure housekeeping
# from argument: the 400-900 character band holds real substance ("I yield myself such
# time as I may consume. Mr. Speaker, I rise in support of H.R. 2269 ...").
PROCEDURAL_MAX_CHARS = 200

# A duplicate is only called on enough text to be sure. Two members both saying "I yield
# back the balance of my time" is not one announcement published twice.
DUPLICATE_MIN_CHARS = 200

# Decision 4's fairness check needs at least this many dropped turns before a party
# ratio is read as unevenness rather than noise. See `_uneven`.
UNEVEN_MIN_TURNS = 50

# Every rule that can drop a turn, in the order they are applied. `inserted-material` is
# not here: it shortens a turn rather than dropping it.
DROP_RULES = (
    "no-attributable-text",
    "procedural",
    "ceremonial",
    "office-logistics",
    "duplicate",
)


class PrefilterError(RuntimeError):
    """The pre-filter cannot run as the phase specifies."""


# --- reading a turn ------------------------------------------------------------------

# The Record opens a turn with the speaker's parsed name and then, on the floor, a
# salutation to the chair. Both are addressing furniture, not content, so a rule that
# asks "what does this turn SAY" must see past them.
_OPENER = re.compile(
    r"^\s*(?:(?:Mr|Mrs|Ms|Miss)\.?\s+[A-Z][A-Za-z'’\- ]{1,30}?"
    r"(?:\s+of\s+[A-Z][A-Za-z ]+)?\.\s*)?"
    r"(?:(?:Mr|Madam)\.?\s+(?:President|Speaker|Chair(?:man|woman)?)"
    r"(?:\s+pro\s+tempore)?\s*,?\s*)?",
    re.IGNORECASE,
)


def content(segment: str) -> str:
    """What a turn says, with the Record's hard line wraps flattened and the speaker's
    name and salutation removed. Flattening matters: the Record wraps at ~72 columns, so
    "I include in the\\nRecord" is one phrase that no pattern written with spaces in it
    would ever match."""
    return _OPENER.sub("", re.sub(r"\s+", " ", segment)).strip()


def normalize(text: str) -> str:
    """Text reduced to what a duplicate check compares: lower case, letters digits and
    single spaces. Punctuation and the Record's typographic quotes differ between a press
    release and the floor version of the same announcement; the words do not."""
    # Whitespace collapses AFTER the punctuation goes, not before: stripping `!'' --`
    # from "``Yes!'' -- twice" leaves a run of spaces, and a press release that writes
    # the same sentence without the dashes must still normalize to the same string.
    stripped = re.sub(r"[^a-z0-9 ]", "", text.lower())
    return re.sub(r"\s+", " ", stripped).strip()


# --- the patterns --------------------------------------------------------------------

# R1/R2's escape hatch: this turn argues policy, whatever else it looks like. A named
# bill or a call for a vote is the floor's own evidence that a position is being taken.
# A bill citation is matched case-SENSITIVELY and must carry its period, and nothing
# word-like may precede it. Measured 2026-10-14: a case-insensitive `S\.?\s?\d{1,4}`
# read the possessive in "Florida's 2024 Person of the Year" as bill "S. 2024" and
# rescued 56 pure tributes from the ceremonial rule on that basis.
_BILL = re.compile(
    r"(?<![A-Za-z0-9'’])(?:"
    r"H\.\s?R\.\s?\d+|HR\s\d+"
    r"|H\.\s?(?:Res|J\.\s?Res|Con\.\s?Res)\.\s?\d+"
    r"|S\.\s?\d{1,4}\b"
    r"|S\.\s?(?:Res|J\.\s?Res|Con\.\s?Res)\.\s?\d+"
    r")",
    re.IGNORECASE,
)

# The other half of the escape: the floor's own language for taking a position.
_POSITION = re.compile(
    r"\b(?:"
    r"I urge (?:my colleagues|a |an |support|passage|adoption|opposition|rejection)"
    r"|urge (?:my colleagues|all members|everyone) to (?:support|oppose|vote)"
    r"|vote (?:yes|no|yea|nay|for|against)"
    r"|encourage a (?:``)?(?:yes|no|yea|nay)"
    r"|this (?:bill|legislation|amendment|resolution|act) would"
    r"|cosponsor"
    r")",
    re.IGNORECASE,
)


def argues_policy(text: str) -> bool:
    """Whether this turn takes a position on policy — R1 and R2's escape hatch.

    A named bill or a call for a vote is the floor's own evidence that a position is
    being taken, so a turn that carries either survives both the ceremonial rule and the
    procedural rule whatever else it looks like (owner, 2026-10-14).
    """
    return bool(_BILL.search(text) or _POSITION.search(text))

# The housekeeping acts, each named so R4's sub-rule table can be built. These ARE the
# procedural register: every one names a specific act of floor housekeeping, so no
# separate "does this open procedurally" test is needed on top of them. Order
# is the reporting order; a turn is attributed to the first one it matches.
PROCEDURAL_SUB_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "leave-to-revise-and-extend",
        re.compile(r"\brevise and extend (?:their|his|her|my) remarks\b", re.IGNORECASE),
    ),
    (
        "adjournment-and-meeting-hour",
        re.compile(
            r"\b(?:do now adjourn|when the (?:House|Senate) adjourns"
            r"|hour of meeting|stand in recess|adjourn to meet)\b",
            re.IGNORECASE,
        ),
    ),
    ("quorum-call", re.compile(r"\bquorum call|absence of a quorum\b", re.IGNORECASE)),
    (
        "committee-authority-to-meet",
        re.compile(r"\brequests? for committees? to meet|authorized to meet\b", re.IGNORECASE),
    ),
    (
        "floor-privileges",
        re.compile(r"\bprivileges of the floor be granted\b", re.IGNORECASE),
    ),
    (
        "yielding-time",
        re.compile(
            r"\bI (?:yield back|yield the floor|yield myself|reserve the balance)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "calendar-and-morning-business",
        re.compile(
            r"\b(?:period of morning business|executive calendar|legislative session"
            r"|be discharged|proceed to (?:the )?(?:consideration|executive session))\b",
            re.IGNORECASE,
        ),
    ),
    ("unanimous-consent-request", re.compile(r"\bI ask unanimous consent\b", re.IGNORECASE)),
)

# R3: a vote explanation. Kept as a statement, never sent to the AI. The form is fixed
# enough to match on the body rather than the title, so a press release that explains a
# vote is caught too.
VOTE_EXPLANATION = re.compile(
    r"\b(?:"
    r"had I been (?:present|able to vote)"
    r"|I was (?:unable to (?:be present|attend|vote)|unavoidably absent|not present|absent)"
    r"[^.]{0,120}\b(?:vote|rollcall|roll call)"
    r"|I am not recorded (?:for|on)\b"
    r"|I would have voted\b"
    r"|my vote was (?:not |incorrectly )recorded"
    r")",
    re.IGNORECASE,
)

# Ceremonial: a tribute, a memorial, a congratulation, an anniversary. The owner ruled
# these out of the corpus (R1) unless `argues_policy` also fires on the same turn.
CEREMONIAL = re.compile(
    r"\b(?:"
    r"rise (?:today )?to (?:recognize|honor|congratulate|pay tribute|commemorate"
    r"|celebrate|remember|salute|thank|acknowledge|memorialize|mourn)"
    r"|pay tribute to"
    r"|extend my (?:deepest |heartfelt )?(?:condolences|sympathies)"
    r"|congratulate"
    r"|honor(?:ing)? the (?:life|memory|service|legacy)"
    r"|in loving memory"
    r"|on the (?:passing|occasion) of"
    r"|celebrating (?:the|his|her|their|its)"
    r"|happy \d+(?:st|nd|rd|th) (?:birthday|anniversary)"
    r"|wish (?:him|her|them) (?:well|all the best|the best)"
    r"|offer my congratulations"
    r"|a (?:proud|lifelong) (?:resident|member) of"
    r")\b",
    re.IGNORECASE,
)

# Office logistics. Near-absent from the Congressional Record (measured: no clean hits on
# the pilot corpus) and common in press releases, which is the source this rule is really
# for — written here because the filter is source-agnostic and collector (a) runs through
# it unchanged. Deliberately narrow: it must not fire on a tribute that happens to
# mention an internship.
OFFICE_LOGISTICS = re.compile(
    r"\b(?:"
    r"will host (?:a |an |his |her |their )?(?:town hall|telephone town hall|mobile office"
    r"|office hours|job fair|resource fair|coffee with)"
    r"|is (?:now )?accepting applications"
    r"|applications are (?:now )?(?:open|being accepted)"
    r"|the deadline to apply"
    r"|service academy nomination"
    r"|announced? (?:today )?that [^.]{0,80}(?:has been awarded|will receive) "
    r"(?:a |an )?\$[\d,.]+"
    r"|my (?:district|state|mobile) office will be"
    r"|constituent service"
    r")\b",
    re.IGNORECASE,
)

# Fact 5's marker: the member's OWN act of inserting material. The negative lookahead
# keeps the floor manager's "insert extraneous material" leave request out — that one is
# procedural, and treating it as a marker truncated 278 rows at their opening sentence.
INSERTED_MATERIAL = re.compile(
    r"\bI\b[^.]{0,60}\b(?:include|insert|submit|place|am submitting|offer)\b"
    r"(?![^.]{0,20}extraneous)[^.]{0,80}\bin the (?:Congressional )?Record\b",
    re.IGNORECASE,
)


# --- the rules -----------------------------------------------------------------------


def cut_inserted_material(segment: str) -> tuple[str, int]:
    """The turn cut at the member's own insertion marker: everything up to AND INCLUDING
    the marker sentence is his words and is kept; what follows is not his and goes
    (owner, 2026-10-13).

    Returns the kept text and how many characters were removed — 0 when no marker is
    present, which is the overwhelming majority of turns.
    """
    flat = re.sub(r"\s+", " ", segment)
    match = INSERTED_MATERIAL.search(flat)
    if match is None:
        return segment, 0
    # Where the member's own marker sentence ends. A colon or semicolon ends it outright
    # — "I include in the Record the following list of 2026 Inductees:" is the whole of
    # what he said, and everything after the colon is the list he did not write. A period
    # ends it only when a new sentence follows, because the Record's own abbreviations
    # ("H.R. 1", "Mr. Speaker", "Jan. 6") carry periods mid-sentence.
    # The terminator may sit INSIDE the Record's closing quote: a marker sentence that
    # names a quoted headline ends `... can be a crisis.''`, and a period followed by
    # `''` rather than by a capital is still the end of his sentence.
    tail = flat[match.end() :]
    end = re.search(r"[:;]|\.(?:''|\"|’’)?(?=\s+[`\"'A-Z]|\s*$)", tail)
    keep_to = match.end() + (end.end() if end else len(tail))
    kept = flat[:keep_to].strip()
    return kept, len(flat) - len(kept)


def procedural_sub_rule(text: str) -> str | None:
    """Which housekeeping act this turn performs, or None if it performs none. Named so
    R4's sub-rule table can show WHERE the party gap comes from."""
    for name, pattern in PROCEDURAL_SUB_RULES:
        if pattern.search(text):
            return name
    return None


def classify_turn(text: str) -> tuple[str | None, str | None]:
    """The rule that drops this turn and its sub-rule, or `(None, None)` to keep it.

    `text` is `content(segment)` — flattened, name and salutation stripped. Rule order is
    the module docstring's order and the first match wins.
    """
    if not text:
        return "no-attributable-text", None

    takes_a_position = argues_policy(text)

    # R2: a named housekeeping act, under the length guard, taking no position.
    if not takes_a_position and len(text) < PROCEDURAL_MAX_CHARS:
        sub = procedural_sub_rule(text)
        if sub is not None:
            return "procedural", sub

    # R1: a tribute survives whole when the same turn argues policy.
    if CEREMONIAL.search(text) and not takes_a_position:
        return "ceremonial", None

    if OFFICE_LOGISTICS.search(text):
        return "office-logistics", None

    return None, None


# --- the pass ------------------------------------------------------------------------


def _drop(record: dict[str, Any], turn_index: int, text: str, rule: str, sub: str | None) -> dict:
    """One line of the audit log. The excerpt is what makes a drop checkable without the
    gitignored cache in hand, so it carries the opening of the turn that matched."""
    entry = {
        "member_id": record.get("member_id", ""),
        "date": record.get("date", ""),
        "statement_id": record.get("granule_id", ""),
        "source": record.get("source", ""),
        "turn": turn_index,
        "rule": rule,
        "title": record.get("title", ""),
        "chars": len(text),
        "excerpt": text[:240],
    }
    if sub is not None:
        entry["sub_rule"] = sub
    return entry


def apply_to_statement(
    record: dict[str, Any], seen: dict[str, dict[str, str]]
) -> tuple[dict[str, Any] | None, list[dict]]:
    """One statement through every rule.

    Returns the surviving statement — the same record with `segments` replaced by the
    turns that survived, plus the pre-filter's own fields — or None when nothing
    survived, and the drop-log entries this statement produced.

    `seen` is the cross-source duplicate memory, keyed on normalized text and carrying
    where it was first kept. It is the caller's, so it spans sources and collectors.
    """
    drops: list[dict] = []
    kept: list[str] = []
    inserted_cut_chars = 0
    vote_explanation = False

    segments = record.get("segments") or []
    if not segments or record.get("attribution") == "none":
        # The Record names the member as speaking but no words could be attributed to
        # them. Logged at turn -1: there is no turn to point at.
        drops.append(_drop(record, -1, "", "no-attributable-text", None))
        return None, drops

    for index, segment in enumerate(segments):
        body, cut = cut_inserted_material(segment)
        inserted_cut_chars += cut
        text = content(body)

        if VOTE_EXPLANATION.search(text):
            # R3: kept, and marked so nothing downstream pays to read it.
            vote_explanation = True
            kept.append(body)
            continue

        rule, sub = classify_turn(text)
        if rule is not None:
            drops.append(_drop(record, index, text, rule, sub))
            continue

        key = normalize(text)
        if len(key) >= DUPLICATE_MIN_CHARS:
            member_key = f"{record.get('member_id', '')}\n{key}"
            first = seen.get(member_key)
            if first is not None:
                entry = _drop(record, index, text, "duplicate", None)
                entry["duplicate_of"] = first["statement_id"]
                entry["duplicate_of_date"] = first["date"]
                drops.append(entry)
                continue
            seen[member_key] = {
                "statement_id": record.get("granule_id", ""),
                "date": record.get("date", ""),
            }
        kept.append(body)

    if not kept:
        return None, drops

    survivor = {
        **record,
        "segments": kept,
        "chars": sum(len(s) for s in kept),
        "prefilter": {
            "turns_in": len(segments),
            "turns_kept": len(kept),
            "inserted_material_chars_cut": inserted_cut_chars,
        },
        "ai_eligible": not vote_explanation,
    }
    if vote_explanation:
        survivor["ai_ineligible_reason"] = "vote-explanation"
    return survivor, drops


def run_prefilter(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Every statement through the filter, in a fixed order, with the full audit.

    Records are sorted by (member, date, id) first so the duplicate rule always keeps the
    EARLIEST occurrence of a repeated announcement and the drop log is byte-identical on
    a re-run — a duplicate pair whose order depends on a directory listing would otherwise
    flip which one is logged.
    """
    ordered = sorted(
        records,
        key=lambda r: (
            r.get("member_id", ""),
            r.get("date", ""),
            r.get("granule_id", ""),
            r.get("source", ""),
        ),
    )
    seen: dict[str, dict[str, str]] = {}
    survivors: list[dict[str, Any]] = []
    drops: list[dict] = []
    for record in ordered:
        survivor, record_drops = apply_to_statement(record, seen)
        drops.extend(record_drops)
        if survivor is not None:
            survivors.append(survivor)
    return {
        "statements_in": len(ordered),
        "statements_kept": len(survivors),
        "turns_in": sum(len(r.get("segments") or []) for r in ordered),
        "turns_kept": sum(len(s["segments"]) for s in survivors),
        "statements": survivors,
        "drops": drops,
    }


# --- the audit ------------------------------------------------------------------------


def rule_counts(drops: list[dict]) -> dict[str, int]:
    """Turns dropped per rule, every rule present even at zero — a rule that fired
    nothing is a fact about the corpus and must not vanish from the report."""
    counts = Counter(d["rule"] for d in drops)
    return {rule: counts.get(rule, 0) for rule in DROP_RULES}


def sub_rule_counts(drops: list[dict], parties: dict[str, str]) -> list[dict[str, Any]]:
    """R4's condition: the procedural gap broken down to each housekeeping act, with the
    party split, so the structural explanation is checkable rather than asserted."""
    rows: list[dict[str, Any]] = []
    for name, _ in PROCEDURAL_SUB_RULES:
        hits = [d for d in drops if d.get("sub_rule") == name]
        by_party = Counter(parties.get(d["member_id"], "?") for d in hits)
        rows.append(
            {
                "sub_rule": name,
                "turns": len(hits),
                "D": by_party.get("D", 0),
                "R": by_party.get("R", 0),
            }
        )
    return rows


def judged_units(record: dict[str, Any]) -> int:
    """How many things the filter judged in one statement — its denominator share.

    Normally this is the number of turns. A statement with NO turns still gets judged
    once, as `no-attributable-text`, so it counts as one: with `len(segments)` alone such
    a record contributes 1 to a rule's numerator and 0 to the denominator, and the rate
    goes above 100%. Measured 2026-10-14 on a part-collected corpus, the
    `no-attributable-text` row read **112.8%** for Democrats — a number that cannot mean
    anything, in the table the owner is asked to judge fairness by.
    """
    return len(record.get("segments") or []) or 1


def fairness(
    records: list[dict[str, Any]],
    drops: list[dict],
    parties: dict[str, str],
    *,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """Drop rate per party per rule — decision 4's fairness check.

    The denominator is the turns that party brought to the filter, so the rates compare
    like with like: the pilot is equal by party in MEMBERS, not in turns, and the
    Democratic Senate rows alone are a 1,519-to-1,742 difference.

    `source` narrows both the numerator and the denominator to one collector, which the
    report needs because the rules do not bite equally on the two sources and the two
    sources are not equally distributed between the parties. The Congressional Record
    speaks in the first person ("I rise today to recognize"), which is what the ceremonial
    patterns match; a press office writes in the third ("Rep. X Honors a Local Lineman"),
    so the same rule fires far less there. Press VOLUMES also differ sharply by member —
    one member of the 40 published 604 releases — so a combined rate can show a party
    skew that is really a source skew, and that would be read as bias in the one report
    the owner approves spend against.
    """
    if source is not None:
        records = [r for r in records if r.get("source") == source]
        drops = [d for d in drops if d.get("source") == source]
    pool: dict[str, int] = defaultdict(int)
    for record in records:
        pool[parties.get(record.get("member_id", ""), "?")] += judged_units(record)
    rows: list[dict[str, Any]] = []
    for rule in DROP_RULES:
        hits = Counter(
            parties.get(d["member_id"], "?") for d in drops if d["rule"] == rule
        )
        row: dict[str, Any] = {"rule": rule, "turns": sum(hits.values())}
        for party in ("D", "R"):
            total = pool.get(party, 0)
            row[party] = hits.get(party, 0)
            row[f"{party}_rate"] = round(hits.get(party, 0) / total * 100, 1) if total else 0.0
        row["uneven"] = _uneven(row["D_rate"], row["R_rate"], row["turns"])
        rows.append(row)
    return rows


def _uneven(d_rate: float, r_rate: float, turns: int = UNEVEN_MIN_TURNS) -> bool:
    """Whether a step's party rates differ enough to need the owner's eye.

    Decision 4 says "noticeably higher". Two guards make that measurable: a 1.5x ratio
    between the party rates, and a floor of `UNEVEN_MIN_TURNS` turns before a ratio means
    anything at all. The floor is why the duplicate rule does not trip the stop: 17 turns
    split 14/3 is a 3x ratio and a 0.2-percentage-point difference, which is noise, not a
    biased filter. The procedural gap (2.3x over hundreds of turns) still flags.
    """
    if turns < UNEVEN_MIN_TURNS:
        return False
    low, high = sorted((d_rate, r_rate))
    if high == 0.0:
        return False
    return low == 0.0 or high / low >= 1.5


def write_drop_log(result: dict[str, Any], data_dir: Path) -> Path:
    """The committed audit. Sorted and wall-clock-free, so an unchanged corpus produces a
    byte-identical file and a real change shows as a real diff."""
    path = data_dir / "quality" / "statement-prefilter-drops.json"
    drops = sorted(
        result["drops"],
        key=lambda d: (d["member_id"], d["date"], d["statement_id"], d["turn"], d["rule"]),
    )
    payload = {
        "rule_order": list(DROP_RULES),
        "procedural_max_chars": PROCEDURAL_MAX_CHARS,
        "statements_in": result["statements_in"],
        "statements_kept": result["statements_kept"],
        "turns_in": result["turns_in"],
        "turns_kept": result["turns_kept"],
        "rule_counts": rule_counts(result["drops"]),
        "drops": drops,
    }
    return atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=False) + "\n")


# --- the run --------------------------------------------------------------------------


def _load_dir(statements_dir: Path) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    """Every collected statement under one collector's output directory, with each
    member's party and name as that collector recorded them."""
    records: list[dict[str, Any]] = []
    parties: dict[str, str] = {}
    names: dict[str, str] = {}
    for path in sorted(statements_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        member = payload["member"]
        parties[member["id"]] = member["party"]
        names[member["id"]] = member["name"]
        records.extend(payload["statements"])
    return records, parties, names


def load_all(data_dir: Path) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    """Every collected statement from EVERY collector that has run, in one list.

    The pre-filter is source-agnostic and the cross-source duplicate rule only works if
    both sources are in the same pass, so the count-before-spend report reads them
    together. A collector that has not run yet contributes nothing and is not an error:
    (c) waits on campaign URLs and (d) on platform access.
    """
    raw = data_dir / "raw"
    records: list[dict[str, Any]] = []
    parties: dict[str, str] = {}
    names: dict[str, str] = {}
    found = False
    for subdir in ("crec", "press"):
        statements_dir = raw / subdir / "statements"
        if not statements_dir.is_dir():
            continue
        found = True
        more, more_parties, more_names = _load_dir(statements_dir)
        records.extend(more)
        parties.update(more_parties)
        names.update(more_names)
    if not found:
        raise PrefilterError(
            f"no collected corpus under {raw}; run `uv run ingest statements-crec` "
            "and `uv run ingest statements-press`"
        )
    return records, parties, names


# A rough characters-per-token for English prose, used ONLY to estimate a bill before it
# is incurred. The cap in `ai.yaml` is enforced on MEASURED spend by `ingest/ai.py`, so an
# estimate that is off by a fifth cannot overspend anything — it can only mis-advise the
# owner about whether to raise the cap.
CHARS_PER_TOKEN = 4

# What one call adds beyond the statement itself: the prompt, the schema, and the model's
# own thinking plus JSON on the way out. Measured against the four live calls of
# 2026-10-09 (STATUS fact 8), which came to $0.0095-$0.014 per categorized statement.
PROMPT_OVERHEAD_TOKENS = 900
TRIAGE_OUTPUT_TOKENS = 30
CATEGORIZE_OUTPUT_TOKENS = 700


def _cost(prices: dict[str, float], in_tokens: int, out_tokens: int) -> float:
    return (in_tokens * prices["input"] + out_tokens * prices["output"]) / 1_000_000


def estimate_spend(
    survivors: list[dict[str, Any]], config: dict[str, Any]
) -> dict[str, Any]:
    """What the next run would cost, from the same prices the cap enforces.

    Two stages, each priced on what actually reaches it:

      * the Haiku triage gate (decision 3) reads every surviving statement EXCEPT the
        vote explanations R3 marks ineligible;
      * the Opus categorizer reads only each member's newest
        `max_statements_per_member_per_run` (decision 7) of those that a triage `true`
        would pass — and because the triage verdict is not knowable before the run, this
        prices the WORST case, every one passing.
    """
    cap = int(config["max_statements_per_member_per_run"])
    eligible = [s for s in survivors if s.get("ai_eligible", True)]

    triage_in = sum(
        len("".join(s["segments"])) // CHARS_PER_TOKEN + PROMPT_OVERHEAD_TOKENS
        for s in eligible
    )
    triage = _cost(
        config["prices"][config["tasks"]["triage_statement"]["model"]],
        triage_in,
        TRIAGE_OUTPUT_TOKENS * len(eligible),
    )

    # Newest first, per member, then the cap — decision 7's own order.
    per_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for statement in eligible:
        per_member[statement["member_id"]].append(statement)
    categorized: list[dict[str, Any]] = []
    for items in per_member.values():
        items.sort(key=lambda s: (s.get("date", ""), s.get("granule_id", "")), reverse=True)
        categorized.extend(items[:cap])

    categorize_in = sum(
        len("".join(s["segments"])) // CHARS_PER_TOKEN + PROMPT_OVERHEAD_TOKENS
        for s in categorized
    )
    categorize = _cost(
        config["prices"][config["tasks"]["categorize_statement"]["model"]],
        categorize_in,
        CATEGORIZE_OUTPUT_TOKENS * len(categorized),
    )

    total = triage + categorize
    cap_usd = float(config["per_run_cost_cap_usd"])
    return {
        "triage_statements": len(eligible),
        "triage_usd": round(triage, 4),
        "categorize_statements": len(categorized),
        "categorize_usd": round(categorize, 2),
        "total_usd": round(total, 2),
        "cap_usd": cap_usd,
        "over_cap": total > cap_usd,
        "per_member_cap": cap,
        "ineligible": len(survivors) - len(eligible),
    }


# The seed for the audit sample below. Committed with the report so the owner can re-draw
# the identical 20 turns and satisfy himself that nothing was curated into the sample.
PROCEDURAL_AUDIT_SEED = 20261014
PROCEDURAL_AUDIT_SIZE = 20

# A surviving statement this short is a one-liner: a bare vote urge with no reasoning
# behind it. Same threshold as R2's length guard, measured the same way, so "the
# procedural rule kept it" and "it is a one-liner" are the same measurement.
SHORT_STATEMENT_CHARS = PROCEDURAL_MAX_CHARS


def statement_content_chars(statement: dict[str, Any]) -> int:
    """How much the member actually said in this statement, measured the way the rules
    measure a turn — speaker name and salutation stripped, line wraps flattened."""
    return sum(len(content(segment)) for segment in statement.get("segments") or [])


def sample_procedural_drops(
    records: list[dict[str, Any]],
    drops: list[dict],
    parties: dict[str, str],
    *,
    party: str = "R",
    seed: int = PROCEDURAL_AUDIT_SEED,
    size: int = PROCEDURAL_AUDIT_SIZE,
) -> list[dict[str, Any]]:
    """A seeded random sample of procedural drops from one party, with the FULL text.

    This is the owner's own check on the R4 ruling he made on 2026-10-14. He accepted a
    procedural drop rate roughly 2.3x higher for Republicans on the explanation that the
    majority party's floor managers make the housekeeping requests. The explanation is
    checkable only if he can read the turns themselves: **if any of these argue policy,
    the rule is too wide and the ruling should be revisited.**

    Random and seeded, not "the first 20" and not hand-picked: a curated sample would
    prove nothing, and an unseeded one could not be re-drawn to check that it wasn't.
    The excerpt in the drop log is capped for readability, so the text here is read back
    from the corpus and is the whole turn.
    """
    by_key = {
        (r.get("member_id", ""), r.get("granule_id", "")): r for r in records
    }
    pool = [
        d
        for d in drops
        if d["rule"] == "procedural" and parties.get(d["member_id"]) == party
    ]
    pool.sort(key=lambda d: (d["member_id"], d["date"], d["statement_id"], d["turn"]))
    drawn = random.Random(seed).sample(pool, min(size, len(pool)))
    drawn.sort(key=lambda d: (d["member_id"], d["date"], d["statement_id"], d["turn"]))

    out: list[dict[str, Any]] = []
    for drop in drawn:
        record = by_key.get((drop["member_id"], drop["statement_id"]))
        segments = (record or {}).get("segments") or []
        turn = drop["turn"]
        text = (
            content(cut_inserted_material(segments[turn])[0])
            if 0 <= turn < len(segments)
            else drop["excerpt"]
        )
        out.append(
            {
                "member_id": drop["member_id"],
                "date": drop["date"],
                "statement_id": drop["statement_id"],
                "sub_rule": drop.get("sub_rule", ""),
                "title": drop.get("title", ""),
                "text": text,
            }
        )
    return out


def short_statement_load(
    survivors: list[dict[str, Any]], cap: int
) -> list[dict[str, Any]]:
    """Per member, how much of decision 7's first-run allowance is spent on one-liners.

    Decision 7 sends each member's NEWEST `cap` surviving statements to the categorizer.
    A member whose newest statements are mostly bare vote urges — "I encourage a yes vote
    on this bill, and I yield back" — spends that allowance on text with no reasoning in
    it, and the run buys far less for them than for a member with argued speeches. R2
    keeps those one-liners on purpose (a vote urge IS a position), so this does not
    propose dropping them; it says plainly where the first run's money is going.
    """
    per_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for statement in survivors:
        if statement.get("ai_eligible", True):
            per_member[statement["member_id"]].append(statement)
    rows: list[dict[str, Any]] = []
    for member_id, items in per_member.items():
        items.sort(key=lambda s: (s.get("date", ""), s.get("granule_id", "")), reverse=True)
        newest = items[:cap]
        short = [s for s in newest if statement_content_chars(s) < SHORT_STATEMENT_CHARS]
        rows.append(
            {
                "member_id": member_id,
                "to_categorizer": len(newest),
                "short": len(short),
                # "More than half" of what the member actually brings, not of the cap:
                # a member with 6 statements is not flagged for having 4 short ones out
                # of a 25 allowance they never filled.
                "majority_short": len(newest) > 0 and len(short) * 2 > len(newest),
            }
        )
    return sorted(rows, key=lambda r: r["member_id"])


def press_coverage(data_dir: Path) -> dict[str, Any]:
    """Press-release coverage per pilot cell (party x chamber), and every row that is not
    collecting, by id.

    The pilot was drawn equal by party and proportional by chamber precisely so the
    fairness measurement has an equal-n base (decision 10). Press coverage can undo that
    after the draw, silently: a cell whose rows all fail to collect has its say-vs-do
    comparison resting on the Congressional Record alone, and no per-party drop rate
    computed over collected text can show it — the rate is computed over what WAS
    collected. So it goes at the top of the report.

    A row the owner has marked `no_press_source` is counted in its own column and NEVER
    as a collection failure: the member's site publishes no press-release list, so there
    is nothing to collect and nothing went wrong. It is read from the collector's own
    index (`no_list`) rather than from the source config, for the same reason every other
    number here is: this table reports what the collection RUN found, and the run is what
    wrote that list.
    """
    pilot_path = data_dir / "config" / "statement-pilot.yaml"
    index_path = data_dir / "raw" / "press" / "index.json"
    if not pilot_path.exists() or not index_path.exists():
        return {"cells": [], "non_collecting": [], "no_list": [], "available": False}

    pilot = yaml.safe_load(pilot_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    walks = {w["member_id"]: w for w in index.get("walks", [])}
    refused = {r["id"]: r for r in index.get("refused", [])}
    # An index written before the collector honoured the flag simply has no such rows.
    no_press_list = {r["id"]: r for r in index.get("no_list", [])}

    cells: list[dict[str, Any]] = []
    non_collecting: list[dict[str, Any]] = []
    no_list: list[dict[str, Any]] = []
    for cell in pilot["cells"]:
        counts = {
            "collected": 0,
            "single_page": 0,
            "empty": 0,
            "refused": 0,
            "no_list": 0,
            "other": 0,
        }
        releases = 0
        for member in cell["members"]:
            member_id = member["id"]
            walk = walks.get(member_id)
            if member_id in no_press_list:
                # First, and it is not a failure: no list exists to collect from. Its
                # reason never goes into `non_collecting`, which is the failure list.
                counts["no_list"] += 1
                entry = no_press_list[member_id]
                no_list.append(
                    {
                        "id": member_id,
                        "name": member["name"],
                        "party": cell["party"],
                        "chamber": cell["chamber"],
                        "reason": entry.get("reason", "no press-release list"),
                        "urls_tried": list(entry.get("urls_tried") or []),
                    }
                )
                reason = ""
            elif member_id in refused:
                counts["refused"] += 1
                reason = f"refused — {refused[member_id]['reason']}"
            elif walk is None:
                counts["other"] += 1
                reason = "not walked in this run"
            elif walk["stopped"] == "empty":
                counts["empty"] += 1
                reason = "empty — the release list is not in the HTML a plain GET returns"
            elif walk["stopped"] == "single-page":
                counts["single_page"] += 1
                releases += walk["releases"]
                reason = ""
            elif walk["stopped"] in COMPLETE_STOPS:
                # The collector's own definition, imported rather than repeated: a
                # sitemap walk enumerates the publisher's whole index, and listing that
                # member under "not collecting" would be the worst misreport this table
                # can make.
                counts["collected"] += 1
                releases += walk["releases"]
                reason = ""
            else:
                counts["other"] += 1
                releases += walk["releases"]
                reason = f"{walk['stopped']} — {walk.get('detail', '')}"
            if reason:
                non_collecting.append(
                    {
                        "id": member_id,
                        "name": member["name"],
                        "party": cell["party"],
                        "chamber": cell["chamber"],
                        "reason": reason,
                    }
                )
        cells.append(
            {
                "party": cell["party"],
                "chamber": cell["chamber"],
                "members": len(cell["members"]),
                "releases": releases,
                **counts,
                "zero_coverage": releases == 0,
            }
        )
    return {
        "cells": cells,
        "non_collecting": sorted(non_collecting, key=lambda r: r["id"]),
        "no_list": sorted(no_list, key=lambda r: r["id"]),
        "available": True,
    }


def _coverage_section(coverage: dict[str, Any] | None) -> list[str]:
    """Press coverage per pilot cell, at the TOP, because a cell with none of it has a
    say-vs-do comparison the rest of this report cannot see."""
    if not coverage or not coverage.get("available"):
        return [
            "## Press coverage per pilot cell",
            "",
            "Not available: collector (a) has not run, so there is no press index to read.",
            "",
        ]
    cells = coverage["cells"]
    lines = [
        "## Press coverage per pilot cell — read this first",
        "",
        "The pilot was drawn equal by party and proportional by chamber (decision 10) so "
        "the fairness measurement has an equal-n base on both sides. **Press coverage can "
        "undo that after the draw, and no drop rate in this report can show it** — every "
        "rate below is computed over text that WAS collected.",
        "",
        "| Cell | Rows | Collected | Single-page | Empty by markup | Refused "
        "| No list exists | Releases |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cell in cells:
        lines.append(
            f"| {cell['party']} {cell['chamber']} | {cell['members']} "
            f"| {cell['collected']} | {cell['single_page']} | {cell['empty']} "
            f"| {cell['refused']} | {cell['no_list']} | {cell['releases']} |"
        )
    zero = [c for c in cells if c["zero_coverage"]]
    lines.append("")
    if zero:
        for cell in zero:
            # "No list exists" is held out of the failure count on purpose: a member
            # whose site has no press-release list did not fail to collect, and counting
            # him among the failures would make the cell look worse than it is while
            # hiding the one thing that is actually true about him.
            failing = cell["members"] - cell["no_list"]
            lines.append(
                f"**The {cell['party']} {cell['chamber']} cell has ZERO press coverage.** "
                f"{failing} of its {cell['members']} rows fail to collect "
                f"({cell['refused']} refused, {cell['empty']} empty by markup), so for "
                f"these members the \"say\" side of say-vs-do rests on the Congressional "
                f"Record alone. Anything the pilot concludes about them is a conclusion "
                f"about their floor speech, not about what their offices publish — and a "
                f"press office and a floor speech are not the same voice."
            )
            if cell["no_list"]:
                lines.append("")
                lines.append(
                    f"{cell['no_list']} of that cell's rows publish no press-release "
                    f"list at all. That is not one of the failures above and is not "
                    f"counted as one: there is nothing to collect and nothing to fix, "
                    f"and the cell's coverage cannot be improved by trying harder on "
                    f"them. They are listed with the owner's reason below."
                )
            lines.append("")
    else:
        lines += ["Every cell has some press coverage.", ""]

    lines += ["### Every row that is not collecting", ""]
    if coverage["non_collecting"]:
        lines += [
            "| Member | Party | Chamber | Reason |",
            "| --- | --- | --- | --- |",
        ]
        for row in coverage["non_collecting"]:
            lines.append(
                f"| {row['name']} (`{row['id']}`) | {row['party']} | {row['chamber']} "
                f"| {row['reason']} |"
            )
    else:
        lines.append("None: every row in the pilot collects.")
    lines.append("")

    lines += ["### Rows with no press-release list at all", ""]
    if coverage.get("no_list"):
        lines.append(
            "**Not a collection failure, and not counted as one in the table above.** "
            "The owner looked and these members' sites publish no press-release list, so "
            "there is nothing to collect: a zero here is the site's, not ours. Every URL "
            "tried is listed so the finding can be checked, and so a site that adds a "
            "list later reads as a change rather than as a discovery."
        )
        lines.append("")
        for row in coverage["no_list"]:
            lines.append(
                f"* **{row['name']}** (`{row['id']}`) — {row['party']} {row['chamber']} — "
                f"{row['reason']}. Tried:"
            )
            lines.extend(f"    * <{url}>" for url in row["urls_tried"])
        lines.append("")
    else:
        lines += ["None: every row in the pilot has a press-release list to read.", ""]
    return lines


def _short_statement_section(
    rows: list[dict[str, Any]], names: dict[str, str], parties: dict[str, str], cap: int
) -> list[str]:
    """Where decision 7's first-run allowance actually goes, per member."""
    flagged = [r for r in rows if r["majority_short"]]
    lines = [
        "",
        f"## One-liners in the first run's allowance (under {SHORT_STATEMENT_CHARS} "
        f"characters)",
        "",
        f"Decision 7 sends each member's newest **{cap}** surviving statements to the "
        f"categorizer. R2 deliberately KEEPS a bare vote urge — \"I encourage a yes vote "
        f"on this bill, and I yield back the balance of my time\" — because a vote urge is "
        f"a position. This is not a proposal to drop them. It is where the first run's "
        f"money goes: a member whose allowance is mostly one-liners buys far less "
        f"analysis than a member with argued speeches, and that is worth knowing before "
        f"the run rather than after it.",
        "",
        "| Member | Party | To the categorizer | Under the threshold | Flag |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        flag = "**MOSTLY ONE-LINERS**" if row["majority_short"] else ""
        lines.append(
            f"| {names.get(row['member_id'], '?')} (`{row['member_id']}`) "
            f"| {parties.get(row['member_id'], '?')} | {row['to_categorizer']} "
            f"| {row['short']} | {flag} |"
        )
    lines.append("")
    if flagged:
        lines.append(
            f"**{len(flagged)} member(s) flagged**: more than half of what they send to "
            f"the categorizer is under {SHORT_STATEMENT_CHARS} characters. The threshold "
            f"is \"more than half of what they actually bring\", not of the {cap} "
            f"allowance — a member with six statements is not flagged for having four "
            f"short ones out of an allowance they never filled."
        )
    else:
        lines.append(
            "No member is flagged: nobody's allowance is mostly one-liners."
        )
    lines.append("")
    return lines


def _audit_sample_section(
    sample: list[dict[str, Any]], names: dict[str, str]
) -> list[str]:
    """The owner's own check on the R4 ruling, in full text."""
    lines = [
        "",
        f"## Audit sample — {len(sample)} Republican procedural drops, at random, in full",
        "",
        "On 2026-10-14 the owner accepted a procedural drop rate roughly 2.3x higher for "
        "Republicans, on the explanation that the majority party's floor managers make "
        "the housekeeping requests. **This is the check on that.** Read them: *if any of "
        "these argue policy, the rule is too wide and the ruling should be revisited.*",
        "",
        f"Drawn at random with seed `{PROCEDURAL_AUDIT_SEED}`, committed here so the same "
        f"20 can be re-drawn — a hand-picked sample would prove nothing, and an unseeded "
        f"one could not be checked for having been picked. The text is the WHOLE turn, "
        f"read back from the corpus, not the drop log's shortened excerpt.",
        "",
    ]
    if not sample:
        lines += ["No Republican procedural drops in this corpus.", ""]
        return lines
    for n, drop in enumerate(sample, start=1):
        lines += [
            f"{n}. **{names.get(drop['member_id'], drop['member_id'])}** "
            f"(`{drop['member_id']}`), {drop['date']} — `{drop['sub_rule']}` — "
            f"{drop['title']}",
            "",
            f"   > {drop['text']}",
            "",
        ]
    return lines


def render_spend_report(
    records: list[dict[str, Any]],
    result: dict[str, Any],
    parties: dict[str, str],
    names: dict[str, str],
    estimate: dict[str, Any],
    coverage: dict[str, Any] | None = None,
) -> str:
    """The count-before-spend report (owner decision 4).

    Its whole job is to be the thing the owner approves spend against, so it carries the
    counts per source, per member and after each filter step, the per-party drop rate at
    each step with an explicit flag, and the estimated bill against the cap. **Nothing in
    this repository may make an AI call until the owner has read it and said yes.**

    Three sections exist because the owner asked for them on 2026-10-14, each one a check
    on a decision he had already made rather than a restatement of it: press coverage per
    pilot cell (which can undo decision 10's equal-n draw after the fact), the seeded
    audit sample of Republican procedural drops (his check on the R4 ruling), and the
    one-liner load on decision 7's first-run allowance.
    """
    survivors = result["statements"]
    by_source_in = Counter(r.get("source", "?") for r in records)
    by_source_out = Counter(s.get("source", "?") for s in survivors)
    lines = [
        "# Count before spend — the report the owner approves an AI run against",
        "",
        "Owner decision 4 (§5 Phase 3): *\"Collectors cache raw only. Before any AI call "
        "the run reports counts per source, per member, and after each filter step, plus "
        "estimated cost — then WAITS for the owner's approval.\"*",
        "",
        "**No AI call has been made. Nothing in this repository has spent a cent.** The "
        "pre-filter is free and rule-based; the two gates below are priced, not run.",
        "",
    ]

    lines += _coverage_section(coverage)

    lines += [
        "## The funnel",
        "",
        "| Step | Statements | Member turns |",
        "| --- | --- | --- |",
        f"| Collected | {result['statements_in']} | {result['turns_in']} |",
        f"| After the free pre-filter (decision 2) | {result['statements_kept']} "
        f"| {result['turns_kept']} |",
        f"| Of those, eligible for the AI | {estimate['triage_statements']} | — |",
        f"| Reaching the Haiku triage gate (decision 3) | {estimate['triage_statements']} "
        f"| — |",
        f"| Reaching the Opus categorizer (decision 7 cap: "
        f"{estimate['per_member_cap']}/member) | {estimate['categorize_statements']} | — |",
        "",
        f"{estimate['ineligible']} surviving statements are marked **ineligible for the "
        f"AI** and are never priced: they are the vote explanations the owner ruled on "
        f"(R3, 2026-10-14) — kept as record, matched to their roll call mechanically, "
        f"never categorized.",
        "",
        "## Per source",
        "",
        "| Source | Collected | Kept | Dropped |",
        "| --- | --- | --- | --- |",
    ]
    for source in sorted(by_source_in):
        kept = by_source_out.get(source, 0)
        lines.append(
            f"| `{source}` | {by_source_in[source]} | {kept} "
            f"| {by_source_in[source] - kept} |"
        )

    lines += [
        "",
        "## Fairness at each filter step (decision 4)",
        "",
        "Rates are per party, over the turns that party brought to the filter — the pilot "
        "is equal by party in MEMBERS, not in turns. A step is flagged when the party "
        "rates differ by 1.5x or more over at least "
        f"{UNEVEN_MIN_TURNS} dropped turns.",
        "",
        "| Rule | Turns dropped | D | R | D rate | R rate | Flag |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    rows = fairness(records, result["drops"], parties)
    for row in rows:
        flag = "**UNEVEN**" if row["uneven"] else "even"
        lines.append(
            f"| `{row['rule']}` | {row['turns']} | {row['D']} | {row['R']} "
            f"| {row['D_rate']}% | {row['R_rate']}% | {flag} |"
        )

    sources = sorted({r.get("source", "?") for r in records})
    if len(sources) > 1:
        lines += [
            "",
            "### The same rates, per source",
            "",
            "The rules do not bite equally on the two sources and the two sources are not "
            "equally distributed between the parties, so the combined table above can "
            "show a party skew that is really a source skew. The Congressional Record "
            "speaks in the first person (\"I rise today to recognize\"), which is what the "
            "ceremonial patterns match; a press office writes in the third (\"Rep. X "
            "Honors a Local Lineman\"), so the same rule fires far less there. Press "
            "volumes also differ sharply by member. Both tables are here so the two "
            "effects cannot be mistaken for each other.",
            "",
            "| Source | Rule | Turns | D rate | R rate | Flag |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for source in sources:
            for row in fairness(records, result["drops"], parties, source=source):
                flag = "**UNEVEN**" if row["uneven"] else "even"
                lines.append(
                    f"| `{source}` | `{row['rule']}` | {row['turns']} "
                    f"| {row['D_rate']}% | {row['R_rate']}% | {flag} |"
                )

    flagged = [row for row in rows if row["uneven"]]
    lines += ["", "### The flagged step, broken down to each sub-rule", ""]
    if flagged:
        lines += [
            "The owner accepted the procedural gap on 2026-10-14 **on condition that the "
            "drop log and this report break it down to each sub-rule**, so the structural "
            "explanation is checkable rather than asserted (R4). The cause is that the "
            "majority party's floor managers make the housekeeping requests.",
            "",
            "| Sub-rule | Turns | D | R |",
            "| --- | --- | --- | --- |",
        ]
        for row in sub_rule_counts(result["drops"], parties):
            lines.append(f"| `{row['sub_rule']}` | {row['turns']} | {row['D']} | {row['R']} |")
    else:
        lines.append("No step is flagged.")

    lines += [
        "",
        "## Per member",
        "",
        "| Member | Party | Collected | Kept | To the categorizer |",
        "| --- | --- | --- | --- | --- |",
    ]
    collected_by_member = Counter(r.get("member_id", "?") for r in records)
    kept_by_member = Counter(s["member_id"] for s in survivors)
    eligible_by_member = Counter(
        s["member_id"] for s in survivors if s.get("ai_eligible", True)
    )
    for member_id in sorted(collected_by_member):
        capped = min(eligible_by_member.get(member_id, 0), estimate["per_member_cap"])
        lines.append(
            f"| {names.get(member_id, '?')} ({member_id}) | {parties.get(member_id, '?')} "
            f"| {collected_by_member[member_id]} | {kept_by_member.get(member_id, 0)} "
            f"| {capped} |"
        )

    lines += _short_statement_section(
        short_statement_load(survivors, estimate["per_member_cap"]),
        names,
        parties,
        estimate["per_member_cap"],
    )
    lines += _audit_sample_section(
        sample_procedural_drops(records, result["drops"], parties), names
    )

    verdict = (
        "**OVER THE CAP.** The run would stop part-way. The owner raises the cap for a "
        "run, or the builder does not run it — the builder never raises it unasked "
        "(decision 9)."
        if estimate["over_cap"]
        else "**Under the cap.** The run would complete without stopping on spend."
    )
    lines += [
        "",
        "## Estimated cost",
        "",
        "| Stage | Statements | Estimated |",
        "| --- | --- | --- |",
        f"| Haiku triage gate | {estimate['triage_statements']} "
        f"| ${estimate['triage_usd']:.4f} |",
        f"| Opus categorizer | {estimate['categorize_statements']} "
        f"| ${estimate['categorize_usd']:.2f} |",
        f"| **Total** | | **${estimate['total_usd']:.2f}** |",
        f"| Cap (`per_run_cost_cap_usd`) | | ${estimate['cap_usd']:.2f} |",
        "",
        verdict,
        "",
        "Priced from `data/config/ai.yaml` — the same prices `ingest/ai.py` enforces the "
        "cap on — at roughly four characters per token, plus prompt and schema overhead "
        "and the model's own thinking tokens on the way out. The categorizer line prices "
        "the WORST case: every statement passing the triage gate. Measured against four "
        "live calls on 2026-10-09, a categorized statement ran $0.0095-$0.014.",
        "",
        "## What a yes authorises, and what it does not",
        "",
        "A yes here authorises **one run** of the triage gate and the categorizer under "
        "the cap above. It does not authorise publishing anything: Q-K, the precision "
        "launch bar, is still open, and nothing categorized publishes before it is "
        "answered. Archive capture (decision 8) happens after both gates and before the "
        "review queue, and the archive sweep's own keys are still owed.",
    ]
    return "\n".join(lines) + "\n"


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ingest prefilter",
        description="P3 decision 2 — the free rule-based pre-filter. No AI, no network.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="counts only; write no drop log"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="read EVERY collector's output and write the count-before-spend report "
        "(decision 4) to docs/research/",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    data_dir = root / "data"
    # ALWAYS every collector, report or not: the drop log is one committed file, so a
    # CREC-only pass and a combined pass would overwrite each other with different
    # `rule_counts` depending on which command ran last. `load_all` tolerates a collector
    # that has not run yet, so there is no reason for a narrower path.
    records, parties, names = load_all(data_dir)
    result = run_prefilter(records)

    print(
        f"pre-filter: {result['statements_in']} statements "
        f"({result['turns_in']} turns) -> {result['statements_kept']} kept "
        f"({result['turns_kept']} turns)"
    )
    for rule, count in rule_counts(result["drops"]).items():
        print(f"  {rule:22} {count:5}")
    print("  fairness (drop rate per party):")
    for row in fairness(records, result["drops"], parties):
        flag = "  <-- UNEVEN" if row["uneven"] else ""
        print(
            f"    {row['rule']:22} D {row['D_rate']:5.1f}%  R {row['R_rate']:5.1f}%{flag}"
        )
    cut = sum(s["prefilter"]["inserted_material_chars_cut"] for s in result["statements"])
    print(f"  inserted material cut: {cut:,} characters")

    if args.dry_run:
        print("  --dry-run: no drop log written")
        return 0
    path = write_drop_log(result, data_dir)
    print(f"  drop log: {path.relative_to(root)}")

    if args.report:
        config = yaml.safe_load((data_dir / "config" / "ai.yaml").read_text(encoding="utf-8"))
        estimate = estimate_spend(result["statements"], config)
        coverage = press_coverage(data_dir)
        report_dir = root / "docs" / "research"
        report_dir.mkdir(parents=True, exist_ok=True)
        report = report_dir / f"{datetime.now(UTC).date().isoformat()}-count-before-spend.md"
        atomic_write_text(
            report,
            render_spend_report(records, result, parties, names, estimate, coverage),
        )
        print(
            f"  estimate: ${estimate['total_usd']:.2f} against a "
            f"${estimate['cap_usd']:.2f} cap"
            + ("  <-- OVER THE CAP" if estimate["over_cap"] else "")
        )
        print(f"  report:   {report.relative_to(root)}")
        print("  NO AI CALL MADE. Nothing runs until the owner approves this report.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
