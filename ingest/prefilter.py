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

    uv run ingest prefilter             # over the CREC corpus, writes the drop log
    uv run ingest prefilter --dry-run   # counts only, writes nothing
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ingest.cache import atomic_write_text, repo_root

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


def fairness(
    records: list[dict[str, Any]], drops: list[dict], parties: dict[str, str]
) -> list[dict[str, Any]]:
    """Drop rate per party per rule — decision 4's fairness check.

    The denominator is the turns that party brought to the filter, so the rates compare
    like with like: the pilot is equal by party in MEMBERS, not in turns, and the
    Democratic Senate rows alone are a 1,519-to-1,742 difference.
    """
    pool: dict[str, int] = defaultdict(int)
    for record in records:
        pool[parties.get(record.get("member_id", ""), "?")] += len(record.get("segments") or [])
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


def load_crec(data_dir: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """The collected Congressional Record corpus, with each member's party from the
    committed pilot sample rather than re-derived."""
    statements_dir = data_dir / "raw" / "crec" / "statements"
    if not statements_dir.is_dir():
        raise PrefilterError(
            f"no collected corpus at {statements_dir}; run `uv run ingest statements-crec`"
        )
    records: list[dict[str, Any]] = []
    parties: dict[str, str] = {}
    for path in sorted(statements_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        member = payload["member"]
        parties[member["id"]] = member["party"]
        records.extend(payload["statements"])
    return records, parties


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ingest prefilter",
        description="P3 decision 2 — the free rule-based pre-filter. No AI, no network.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="counts only; write no drop log"
    )
    args = parser.parse_args(argv)

    data_dir = repo_root() / "data"
    records, parties = load_crec(data_dir)
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
    print(f"  drop log: {path.relative_to(repo_root())}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
