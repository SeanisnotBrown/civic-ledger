"""Collector (b): Congressional Record floor speeches for the pilot 40 (§5 Phase 3 task 2).

What this is: the first half of the "say" side of say-vs-do, for the 40 members drawn by
owner decision 10 (`data/config/statement-pilot.yaml`). It reads the Congressional Record
and records, for each of those members, every granule the Record itself says they SPOKE
in — the date, the title, the Record's own class of the item, the public citation URL, and
the member's own words pulled out of the granule text.

What this is NOT, deliberately:

  * **No AI call of any kind.** The pre-filter (decision 2) and the Haiku triage gate
    (decision 3) are the next step, not this one. This run cannot spend a cent.
  * **No archive.org capture.** Decision 8 puts capture AFTER the pre-filter and the
    triage gate; a statement this collector drops later must never have been captured.
  * **No judgment about what a statement means or whether it is any good.** Everything
    collected is kept and counted, including ceremonial items the pre-filter will drop
    later. Nothing here is evaluative; nothing here publishes.

## Attribution: the Record's own `role`, not a name match

A sitting member's name appears in the Record hundreds of times a year without their
saying a word, because every roll-call tally prints all 435 names. Measured 2026-10-13,
`/search` with `member:<bioguide>` returned 1,066 granules for one House member over this
window and only 199 of them survived excluding the phrase "Roll No." — and that exclusion
is chamber-shaped (the Senate prints "Rollcall Vote No.", so it moved a senator's 1,484
hits not at all) and would silently drop real speech that shares a granule with a vote.

So attribution comes from the issue's MODS metadata instead, where GPO records each
member in a granule with a role:

    <congMember bioGuideId="B000490" ... role="SPEAKING" state="GA">
        <name type="parsed">Mr. BISHOP</name>

`role="SPEAKING"` versus `role="VOTED YES"` is the whole question, answered by the source
rather than by a guess, and the `parsed` name is the exact string the Record uses to open
that member's remarks. One fetch per ISSUE (790 across the window) covers all 40 members
at once; see `ingest/sources/govinfo.py` for why this beats searching per member.

## Window, and what gets collected

Window start is 2023-01-03 (owner decision 1: the 118th, because vote data starts there
and an older statement has nothing to be compared against). Collection covers the whole
window for every member: the index records every speaking granule, and the text of every
one of them is fetched and cached.

Nothing here caps collection. Decision 7 caps CATEGORIZATION at each member's newest 25
per run, which is a spend control applied later, and it says plainly that the rest stay
"collected, filtered and countable" — so a granule whose text is on disk costs nothing
until something asks the categorizer to read it. `--keep-limit` exists for smoke runs
(owner, 2026-10-13: a cap here was the builder's own, and wrong); 0, the default, means
every granule in the window.

## Output

  * `data/raw/crec/index.json` — every SPEAKING granule for the 40 in the window.
  * `data/raw/crec/statements/<bioguide>.json` — candidate statements with the member's
    own extracted words, for the pre-filter to read next.
  * `docs/research/<date>-crec-collection-counts.md` — the count report (decision 4),
    per member and per party, which is what the owner approves spend against.

`data/raw/` is gitignored by design (§6.2): the cache is a dev convenience, the report is
the committed artifact.

    uv run ingest statements-crec                  # index + text for the whole window
    uv run ingest statements-crec --index-only     # the count report, no text fetches
    uv run ingest statements-crec --limit-issues 5 --keep-limit 3   # a smoke run
"""

from __future__ import annotations

import argparse
import html
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from ingest.cache import RetryableHTTPError, atomic_write_text, repo_root
from ingest.sources import govinfo

# Owner decision 1, 2026-10-09: the 118th Congress convened on this date.
WINDOW_START = "2023-01-03"

# The Record's own classes. HOUSE and SENATE are the floor proceedings; EXTENSIONS is
# "Extensions of Remarks", written insertions a member submits rather than speaks. All
# three are the member's own words on the official record, so all three are collected and
# the class is recorded on every row — the report splits them, and whether Extensions
# count as a "statement" for grading is an owner call that this collector does not make.
# DAILYDIGEST is the day's summary written by GPO, not by any member, so it is not kept.
KEPT_CLASSES = ("HOUSE", "SENATE", "EXTENSIONS")

SPEAKING = "SPEAKING"

# Per-member ceiling on granule TEXT fetches, for smoke runs only. 0 = no ceiling, which
# is the default: collection covers the window (owner, 2026-10-13).
DEFAULT_KEEP_LIMIT = 0

RAW_SUBDIR = ("raw", "crec")

# A speaker turn opens an indented paragraph with the speaker's parsed name and a period:
# "  Ms. CRAIG. Mr. Speaker, I rise today...". The chair and the clerk open the same way
# ("  The SPEAKER pro tempore."), which is what lets one member's turn be cut at wherever
# the next speaker starts. The name is a title, then an upper-case surname (sometimes two
# words, "Mr. VAN DREW"), then optionally the state qualifier the Record adds when two
# members share a surname ("Mr. KELLY of Mississippi").
#
# Known limit, accepted: a quoted letter inside a member's remarks that opens a line with
# "The Honorable John Smith." reads as a new speaker and ends the segment early. That
# loses the tail of a quotation; it never attributes one member's words to another, which
# is the error that would matter.
_TURN = re.compile(
    r"^[ \t]{1,8}("
    r"(?:(?:Mr|Mrs|Ms|Miss|Madam|Mme)\.\s+|The\s+)"
    r"[A-Z][A-Za-z'’\-]*"
    r"(?:\s+(?:pro\s+tempore|of\s+[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*"
    r"|[A-Z][A-Za-z'’\-]*))*"
    r")\.(?=\s)",
    re.MULTILINE,
)

# The header the Record prints above a written insertion: the item's title, a rule,
# "HON. <NAME>", the state, the chamber line, the date. That is GPO's framing rather than
# the member's words, so a sole-speaker insertion is reported from the chamber line on.
_INSERTION_HEADER = re.compile(
    r"(?is)\A.*?^[ \t]*in the (?:house of representatives|senate)[ \t]*$"
    r"(?:\s*^[ \t]*\w+day,\s+\w+\s+\d{1,2},\s+\d{4}[ \t]*$)?",
    re.MULTILINE,
)

# Boilerplate the htm rendition puts above every granule's body.
_HEADER_LINE = re.compile(
    r"^(?:\[.*\]|Congressional Record, Volume.*|From the Congressional Record Online.*)$",
    re.MULTILINE,
)


class CrecError(RuntimeError):
    """The collector cannot run as the phase specifies."""


@dataclass(frozen=True)
class Speaking:
    """One granule one pilot member spoke in, as the issue's MODS records it."""

    member_id: str
    date: str
    granule_id: str
    package_id: str
    granule_class: str
    sub_granule_class: str
    chamber: str
    title: str
    parsed_name: str
    url: str
    # How many members the Record records as SPEAKING in this granule — ALL of them, not
    # just the pilot 40. It decides whether a granule whose text carries no turn marker
    # (the normal shape of a written insertion) can be attributed to this member whole.
    # Counting only pilot members here would hand one member a five-speaker debate.
    speakers: int = 1


def window_end(today: datetime | None = None) -> str:
    """The window's inclusive end: today, UTC. A collector's window is wall-clock by
    nature (it asks "what has been published?"), unlike the §6.3 determinism rules that
    govern computed metrics."""
    return (today or datetime.now(UTC)).date().isoformat()


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_issue(
    mods_xml: str, wanted: set[str], *, package_id: str | None = None
) -> list[Speaking]:
    """Every (granule, wanted member) pair in one issue's MODS where the member's role is
    SPEAKING and the granule is one of `KEPT_CLASSES`.

    Returns rows sorted by (date, granule id, member) so a re-parse of the same issue
    always yields the same order — the index is a committed-shaped artifact even though
    it lives in the cache.
    """
    try:
        root = ET.fromstring(mods_xml)
    except ET.ParseError as exc:  # a truncated cache entry, not a source bug
        raise CrecError(f"unparseable MODS: {exc}") from exc

    rows: list[Speaking] = []
    for ext in root.iter():
        if _local(ext.tag) != "extension":
            continue
        fields = {_local(child.tag): child for child in ext}
        granule_id = _text(fields.get("accessId"))
        granule_class = _text(fields.get("granuleClass"))
        if not granule_id or granule_class not in KEPT_CLASSES:
            continue
        date = _text(fields.get("granuleDate"))
        title = _text(fields.get("searchTitle")).split("; Congressional Record Vol.")[0]
        # The caller knows the issue it asked for; the "-pt1-Pg..." tail of a granule id
        # is a fallback for a direct call with no issue in hand.
        pkg = package_id or granule_id.split("-pt", 1)[0]
        speaking = [
            m for m in ext
            if _local(m.tag) == "congMember" and m.get("role") == SPEAKING
        ]
        for member in speaking:
            bioguide = member.get("bioGuideId", "")
            if bioguide not in wanted:
                continue
            parsed = ""
            for name in member:
                if _local(name.tag) == "name" and name.get("type") == "parsed":
                    parsed = (name.text or "").strip()
                    break
            rows.append(
                Speaking(
                    member_id=bioguide,
                    date=date,
                    granule_id=granule_id,
                    package_id=pkg,
                    granule_class=granule_class,
                    sub_granule_class=_text(fields.get("subGranuleClass")),
                    chamber=_text(fields.get("chamber")),
                    title=title,
                    parsed_name=parsed,
                    url=govinfo.granule_url(pkg, granule_id),
                    speakers=len(speaking),
                )
            )
    return sorted(rows, key=lambda r: (r.date, r.granule_id, r.member_id))


def plain_text(htm: str) -> str:
    """The granule's body as text: tags stripped, entities resolved, the htm rendition's
    citation header removed. Line breaks and indentation are PRESERVED, because the
    indentation is what marks a speaker turn."""
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", htm)
    body = re.sub(r"(?s)<[^>]+>", "", body)
    body = html.unescape(body).replace("\r\n", "\n").replace("\r", "\n")
    body = _HEADER_LINE.sub("", body)
    return body.strip("\n")


def speaker_segments(text: str, parsed_name: str) -> list[str]:
    """The member's own turns in a granule, verbatim.

    Each turn runs from the member's own opening ("  Mr. BISHOP.") to whoever speaks
    next. A name may carry a state qualifier in the Record where two members share a
    surname ("Mr. KELLY of Mississippi"), so the match is a prefix match on the parsed
    name with an optional " of <State>" tail — and nothing else, so "Mr. KELLY" never
    collects "Mr. KELLY of Pennsylvania".
    """
    if not parsed_name:
        return []
    wanted = re.compile(
        rf"^{re.escape(parsed_name)}(?:\s+of\s+[A-Z][A-Za-z ]+)?$", re.IGNORECASE
    )
    turns = [(m.start(), m.group(1).strip()) for m in _TURN.finditer(text)]
    out: list[str] = []
    for i, (start, speaker) in enumerate(turns):
        if not wanted.match(speaker):
            continue
        # The turn runs to whoever speaks next, or to the end of the granule. A matched
        # turn always carries at least the member's own name, so it is never empty.
        stop = turns[i + 1][0] if i + 1 < len(turns) else len(text)
        out.append(text[start:stop].strip())
    return out


def statement_record(row: Speaking, text: str, *, sole_speaker: bool) -> dict[str, Any]:
    """One candidate statement, as the pre-filter will read it.

    `attribution` says HOW the member's words were identified, because the two cases are
    not equally strong and the next step should be able to tell them apart:

      * `turn` — the Record opens the member's own turn with their parsed name.
      * `sole-speaker` — no turn marker, and MODS records exactly one speaking member for
        the whole granule, which is the normal shape of an Extension of Remarks. The body
        is theirs.
      * `none` — a granule MODS says they spoke in, where neither held. Kept with no
        text, counted in the report, never silently dropped.
    """
    segments = speaker_segments(text, row.parsed_name)
    attribution = "turn"
    if not segments:
        attribution = "sole-speaker" if sole_speaker else "none"
        body = _INSERTION_HEADER.sub("", text).strip() if sole_speaker else ""
        segments = [body] if body else []
    return {
        **asdict(row),
        "source": "congressional_record",
        "attribution": attribution,
        "segments": segments,
        "chars": sum(len(s) for s in segments),
    }


# --- the run -------------------------------------------------------------------------


def pilot_members(data_dir: Path) -> list[dict[str, str]]:
    """The drawn 40, with the party and chamber the draw recorded for each — the report's
    per-party counts come from the committed sample, not from a re-derivation."""
    path = data_dir / "config" / "statement-pilot.yaml"
    if not path.exists():
        raise CrecError(f"no committed pilot sample at {path}; run `uv run ingest pilot-draw`")
    sample = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: list[dict[str, str]] = []
    for cell in sample["cells"]:
        for member in cell["members"]:
            out.append(
                {
                    "id": member["id"],
                    "name": member["name"],
                    "state": member["state"],
                    "party": cell["party"],
                    "chamber": cell["chamber"],
                }
            )
    return sorted(out, key=lambda m: m["id"])


def build_index(
    package_ids: list[str],
    wanted: set[str],
    *,
    read_mods: Callable[[str], str],
    on_progress: Callable[[int, int, int], None] | None = None,
) -> tuple[list[Speaking], list[str]]:
    """Index every issue. Returns (rows, failures).

    One unreadable issue costs that issue's rows, never the run: the cache makes a
    re-run free for everything already read, so a transient failure is retried by
    running the command again rather than by abandoning 790 fetches.
    """
    rows: list[Speaking] = []
    failures: list[str] = []
    for i, pkg in enumerate(package_ids, start=1):
        try:
            rows.extend(parse_issue(read_mods(pkg), wanted, package_id=pkg))
        except (CrecError, RetryableHTTPError, httpx.HTTPError, OSError) as exc:
            failures.append(f"{pkg}: {type(exc).__name__}")
        if on_progress is not None:
            on_progress(i, len(package_ids), len(rows))
    return rows, failures


def by_member(rows: list[Speaking]) -> dict[str, list[Speaking]]:
    """Rows per member, newest first — the order the text fetch and the per-member cap
    both work in."""
    out: dict[str, list[Speaking]] = defaultdict(list)
    for row in rows:
        out[row.member_id].append(row)
    return {
        mid: sorted(items, key=lambda r: (r.date, r.granule_id), reverse=True)
        for mid, items in out.items()
    }


# The three honest things the report can say about the text column, so a 0 in it is never
# ambiguous: the counts come from the index and are final the moment indexing ends, while
# the text pull over the same window takes hours.
_TEXT_PHASE_LINES = {
    "none": (
        "* **No granule text was pulled in this run** (`--index-only`). The counts above "
        "are the index's own and are final; the text column reads 0 because nothing was "
        "read, not because nothing is there."
    ),
    "pending": (
        "* **The text pull was still running when this was written.** The counts above "
        "are final; the text column is not, and the run rewrites this file when it "
        "finishes."
    ),
}


def _text_phase_line(text_phase: str, keep_limit: int) -> str:
    if text_phase in _TEXT_PHASE_LINES:
        return _TEXT_PHASE_LINES[text_phase]
    if not keep_limit:
        return "* Granule text was pulled for **every** granule counted above."
    return (
        f"* Granule text was pulled for the newest **{keep_limit}** per member "
        "(`--keep-limit`, a smoke-run knob); the rest are indexed and countable, "
        "not yet read."
    )


def render_report(
    members: list[dict[str, str]],
    grouped: dict[str, list[Speaking]],
    *,
    window: tuple[str, str],
    issues: int,
    failures: list[str],
    keep_limit: int,
    text_fetched: dict[str, int],
    text_phase: str = "done",
) -> str:
    """The count report (owner decision 4), per member and per party.

    It reports what was COLLECTED, by Record class. It does not estimate AI cost, because
    nothing here has been through the pre-filter or the triage gate yet — the spend
    estimate belongs to the run that actually proposes to spend, with the drop rates per
    party at each filter step beside it.
    """
    start, end = window
    lines = [
        "# Congressional Record collection counts — the pilot 40",
        "",
        f"Generated {datetime.now(UTC).date().isoformat()} by "
        "`uv run ingest statements-crec`.",
        "",
        f"Window **{start} → {end}** (owner decision 1), **{issues}** Record issues read. "
        "Counts are granules the Record's own MODS metadata records the member as "
        "**SPEAKING** in — not name matches. Nothing has been filtered, categorized or "
        "captured: no AI call was made and no archive snapshot was taken.",
        "",
        "`EXTENSIONS` is Extensions of Remarks — written insertions rather than floor "
        "speech. They are collected and counted separately because whether they count as "
        "a statement for grading is an owner call, not the collector's.",
        "",
        "| Member | Party | Chamber | House | Senate | Extensions | Total | Text pulled |",
        "|---|---|---|---|---|---|---|---|",
    ]
    totals: dict[str, dict[str, int]] = {
        "D": defaultdict(int),
        "R": defaultdict(int),
    }
    for member in members:
        rows = grouped.get(member["id"], [])
        counts = defaultdict(int)
        for row in rows:
            counts[row.granule_class] += 1
        party = totals[member["party"]]
        for cls in KEPT_CLASSES:
            party[cls] += counts[cls]
        party["total"] += len(rows)
        party["members"] += 1
        party["text"] += text_fetched.get(member["id"], 0)
        lines.append(
            f"| {member['name']} ({member['id']}) | {member['party']} | "
            f"{member['chamber']} | {counts['HOUSE']} | {counts['SENATE']} | "
            f"{counts['EXTENSIONS']} | {len(rows)} | "
            f"{text_fetched.get(member['id'], 0)} |"
        )

    lines += ["", "## Per party", "",
              "| Party | Members | House | Senate | Extensions | Total | Mean per member |",
              "|---|---|---|---|---|---|---|"]
    for party in ("D", "R"):
        t = totals[party]
        mean = t["total"] / t["members"] if t["members"] else 0.0
        lines.append(
            f"| {party} | {t['members']} | {t['HOUSE']} | {t['SENATE']} | "
            f"{t['EXTENSIONS']} | {t['total']} | {mean:.1f} |"
        )

    zero = [m["id"] for m in members if not grouped.get(m["id"])]
    lines += [
        "",
        "## What a reader should check before approving any spend",
        "",
        _text_phase_line(text_phase, keep_limit),
        f"* Members with **no** speaking granule in the window: "
        f"{', '.join(zero) if zero else 'none'}.",
        "* **No cost is estimated here, by design.** Nothing has been through the "
        "pre-filter (decision 2) or the triage gate (decision 3), so a per-statement "
        "estimate taken off these counts would be meaningless. For scale only, the known "
        "CEILING is decision 7's cap — 40 members x 25 newest = 1,000 categorized at the "
        "$0.0095-$0.014 measured on 2026-10-09, so $10-14, which exceeds the $5 per-run "
        "cap and will stop for owner approval. That is the flow working, not a surprise.",
        f"* Issues that could not be read: {len(failures)}"
        + (f" — {', '.join(failures[:10])}" if failures else ""),
        "",
    ]
    return "\n".join(lines)


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ingest statements-crec")
    ap.add_argument("--since", default=WINDOW_START, help="window start (owner decision 1)")
    ap.add_argument("--until", default=None, help="window end (default: today, UTC)")
    ap.add_argument("--keep-limit", type=int, default=DEFAULT_KEEP_LIMIT,
                    help="smoke-run ceiling on granule TEXT fetches per member "
                         "(0 = every granule, the default)")
    ap.add_argument("--index-only", action="store_true",
                    help="index + count report, no granule text")
    ap.add_argument("--limit-issues", type=int, default=0,
                    help="read only the newest N issues (smoke run)")
    ap.add_argument("--members", default="",
                    help="comma-separated bioguide ids, a subset of the drawn 40")
    args = ap.parse_args(argv or [])

    root = repo_root()
    data_dir = root / "data"
    members = pilot_members(data_dir)
    if args.members:
        asked = {m.strip() for m in args.members.split(",") if m.strip()}
        unknown = asked - {m["id"] for m in members}
        if unknown:
            raise CrecError(f"not in the drawn 40: {', '.join(sorted(unknown))}")
        members = [m for m in members if m["id"] in asked]
    wanted = {m["id"] for m in members}
    end = args.until or window_end()

    print(f"civic-ledger ingest statements-crec: {len(members)} member(s), "
          f"window {args.since} to {end}")
    issues = [p["packageId"] for p in govinfo.published_packages(args.since, end)]
    issues = sorted(issues, reverse=True)
    if args.limit_issues:
        issues = issues[: args.limit_issues]
    print(f"  {len(issues)} Congressional Record issue(s) to read")

    def progress(done: int, total: int, found: int) -> None:
        if done % 25 == 0 or done == total:
            print(f"  indexed {done}/{total} issues, {found} speaking granule(s)")

    rows, failures = build_index(
        issues, wanted, read_mods=govinfo.package_mods, on_progress=progress
    )
    grouped = by_member(rows)

    raw_dir = data_dir.joinpath(*RAW_SUBDIR)
    atomic_write_text(
        raw_dir / "index.json",
        json.dumps(
            {
                "window": {"start": args.since, "end": end},
                "issues_read": len(issues),
                "generated_at": datetime.now(UTC).isoformat(),
                "failures": failures,
                "granules": [asdict(r) for r in rows],
            },
            indent=2,
            sort_keys=True,
        ),
    )

    def write_report(text_fetched: dict[str, int], phase: str) -> Path:
        """The count report. Written once as soon as the index is complete — the counts
        are already final at that point, and a text pull over the whole window takes
        hours — then again with the text column filled."""
        path = (
            root / "docs" / "research"
            / f"{datetime.now(UTC).date().isoformat()}-crec-collection-counts.md"
        )
        atomic_write_text(
            path,
            render_report(
                members, grouped, window=(args.since, end), issues=len(issues),
                failures=failures, keep_limit=args.keep_limit,
                text_fetched=text_fetched, text_phase=phase,
            ),
        )
        return path

    report_path = write_report({}, "none" if args.index_only else "pending")

    text_fetched: dict[str, int] = {}
    if not args.index_only:
        for member in members:
            mine = grouped.get(member["id"], [])
            if args.keep_limit:
                mine = mine[: args.keep_limit]
            records: list[dict[str, Any]] = []
            for row in mine:
                try:
                    text = plain_text(govinfo.granule_text(row.package_id, row.granule_id))
                except (RetryableHTTPError, httpx.HTTPError, OSError) as exc:
                    failures.append(f"{row.granule_id}: {type(exc).__name__}")
                    continue
                records.append(
                    statement_record(row, text, sole_speaker=row.speakers == 1)
                )
            text_fetched[member["id"]] = len(records)
            atomic_write_text(
                raw_dir / "statements" / f"{member['id']}.json",
                json.dumps(
                    {"member": member, "window": {"start": args.since, "end": end},
                     "generated_at": datetime.now(UTC).isoformat(),
                     "statements": records},
                    indent=2, sort_keys=True,
                ),
            )
            print(f"  {member['id']} {member['name'][:24]:24s} "
                  f"{len(grouped.get(member['id'], [])):5d} indexed, "
                  f"{len(records):4d} text")

    if not args.index_only:
        report_path = write_report(text_fetched, "done")

    print(f"  {len(rows)} speaking granule(s) across {len(grouped)} member(s)")
    print(f"  index  -> {(raw_dir / 'index.json').relative_to(root)}")
    print(f"  report -> {report_path.relative_to(root)}")
    if failures:
        print(f"  {len(failures)} fetch failure(s) — re-run to retry only those")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
