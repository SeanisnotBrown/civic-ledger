"""INC-4 — Senate roll-call parsing (pure) + the ingest pipeline.

Mirrors INC-3 (house_votes.py) against the senate.gov LIS XML (SHAPES §6). Two
files back each roll: the session `vote_menu` (enumeration + independent per-vote
tally) and the per-roll `vote_detail` (question, result, and every member's
`vote_cast` keyed by `lis_member_id`). The detail's member list is the canonical
record; totals are computed from it and cross-checked against the menu tally — a
genuine cross-SOURCE check (two different files), the Senate analogue of INC-3's
clerk cross-check (there is no separate clerk for the Senate).

Positions are stored only for the covered MS delegation; the `lis_member_id`→
bioguide join runs through the INC-2 member export (`Member.ids["lis"]`). VP
tie-break votes need no special handling: the VP is absent from the member list,
the detail `<count>` block, AND the menu tally, so member-computed totals agree
with the menu on a 50-50 roll — the tie-break itself is carried by `result`
(e.g. "Bill Passed"). `vote_class` is provisional until the §A1 classifier (INC-5).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from pydantic import ValidationError

from ingest.models import Absence, MemberVote, Position, RollCall
from ingest.sources import senate_xml

# Covered Senate sessions per Congress (mirrors house_votes.SESSIONS; 119/2 is
# ongoing so the ingest is re-runnable and picks up new rolls each run).
SESSIONS: dict[int, tuple[int, ...]] = {118: (1, 2), 119: (1, 2)}

PROVISIONAL_CLASS = "other"
PROVISIONAL_RULE = "unclassified"  # replaced by the §A1 classifier in INC-5

# Measure types that are real legislation (→ a Bill id). Nominations (PN),
# treaty docs, and quorum calls are not bills → bill_id stays None (never faked).
BILL_TYPES: frozenset[str] = frozenset(
    {"hr", "s", "hres", "sres", "hjres", "sjres", "hconres", "sconres"}
)


class UnknownVoteCast(ValueError):
    """A `vote_cast` string outside VOTE_MAP — forces quarantine (§6.1)."""


class TallyMismatch(ValueError):
    """Detail member-computed yea/nay disagrees with the menu tally (§6.3)."""


def _position(vote_cast: str) -> Position:
    try:
        return senate_xml.VOTE_MAP[vote_cast]  # type: ignore[return-value]
    except KeyError as exc:
        raise UnknownVoteCast(f"unknown vote_cast {vote_cast!r}") from exc


def _norm_type(raw: str) -> str:
    """"H.R." → "hr", "S.J.Res." → "sjres", "PN" → "pn"."""
    return re.sub(r"[.\s]", "", raw).lower()


def _measure_id(mtype: str, mnum: str, congress: int) -> str | None:
    t = _norm_type(mtype)
    mnum = mnum.strip()
    if t in BILL_TYPES and mnum:
        return f"{t}{mnum}-{congress}"
    return None


def _bill_id(root: ET.Element, congress: int) -> str | None:
    """Underlying-bill id for a roll, or None (nomination / treaty / quorum).

    Bill and passage votes carry it in `<document>`; amendment votes leave
    `<document>` half-empty (type "S.Amdt.", no number) and put the bill in
    `<amendment><amendment_to_document_number>` (e.g. "H.R. 1") — so fall back
    there before giving up (else every vote-a-rama roll loses its bill link)."""
    doc = root.find("document")
    if doc is not None:
        bid = _measure_id(
            doc.findtext("document_type") or "", doc.findtext("document_number") or "", congress
        )
        if bid:
            return bid
    amd = root.find("amendment")
    if amd is not None:
        # "H.R. 1" / "S.J.Res. 82" → split trailing digits into the number.
        ref = (amd.findtext("amendment_to_document_number") or "").strip()
        m = re.match(r"^(.*?)(\d+)\s*$", ref)
        if m:
            return _measure_id(m.group(1), m.group(2), congress)
    return None


_MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}


def _parse_date(raw: str) -> str:
    """"July 1, 2025,  11:56 AM" → "2025-07-01T11:56:00" (naive ISO, Senate ET).

    Hand-rolled (not strptime %B, which is locale-dependent) so CI is
    locale-proof and deterministic (§6.3). No timezone is fabricated — the wall
    time is as senate.gov publishes it (Eastern)."""
    m = re.match(
        r"^\s*([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4}),\s+(\d{1,2}):(\d{2})\s*(AM|PM)\s*$", raw
    )
    if not m:
        raise ValueError(f"unparseable vote_date {raw!r}")
    month_name, day, year, hh, mm, ap = m.groups()
    month = _MONTHS[month_name]
    hour = int(hh) % 12 + (12 if ap == "PM" else 0)
    return f"{int(year):04d}-{month:02d}-{int(day):02d}T{hour:02d}:{int(mm):02d}:00"


def parse_rollcall(
    detail_xml: str,
    congress: int,
    session: int,
    lis_to_bioguide: dict[str, str],
    menu_tally: tuple[int | None, int | None] | None = None,
) -> tuple[RollCall, list[MemberVote], list[Absence]]:
    """Parse one Senate detail XML into a chamber `RollCall`, the MS delegation's
    `MemberVote`s, and an `Absence` stub per MS `not_voting`. Totals are computed
    from the member list and, when `menu_tally` is given, cross-checked against it
    (raises TallyMismatch on disagreement). Raises on malformed data so the caller
    can quarantine the whole roll (§6.1)."""
    root = ET.fromstring(detail_xml)
    roll = int((root.findtext("vote_number") or "").strip())
    rc_id = f"s-{congress}-{session}-{roll:04d}"
    members = list(root.iter("member"))

    totals = {"yea": 0, "nay": 0, "present": 0, "not_voting": 0}
    for m in members:
        totals[_position((m.findtext("vote_cast") or "").strip())] += 1

    if menu_tally is not None:
        m_yea, m_nay = menu_tally
        if m_yea is not None and m_nay is not None and (
            totals["yea"] != m_yea or totals["nay"] != m_nay
        ):
            raise TallyMismatch(
                f"{rc_id}: detail {totals['yea']}-{totals['nay']} != menu {m_yea}-{m_nay}"
            )

    rollcall = RollCall(
        id=rc_id,
        chamber="senate",
        congress=congress,
        session=session,
        number=roll,
        date=_parse_date(root.findtext("vote_date") or ""),
        question=(root.findtext("vote_question_text") or "").strip(),
        vote_class=PROVISIONAL_CLASS,
        vote_class_rule=PROVISIONAL_RULE,
        bill_id=_bill_id(root, congress),
        result=(root.findtext("vote_result") or "").strip(),
        totals=totals,
        source_url=senate_xml.detail_url(congress, session, roll),
    )

    member_votes: list[MemberVote] = []
    absences: list[Absence] = []
    for m in members:
        if (m.findtext("state") or "").strip() != "MS":
            continue
        lis = (m.findtext("lis_member_id") or "").strip()
        bioguide = lis_to_bioguide.get(lis)
        if bioguide is None:
            # A covered MS senator whose lis is not in the crosswalk = a real gap
            # (bad export or roster drift); surface it, never silently drop.
            raise KeyError(f"{rc_id}: MS lis_member_id {lis!r} not in crosswalk")
        pos = _position((m.findtext("vote_cast") or "").strip())
        member_votes.append(MemberVote(member_id=bioguide, rollcall_id=rc_id, position=pos))
        if pos == "not_voting":
            absences.append(Absence(member_id=bioguide, rollcall_id=rc_id))

    member_votes.sort(key=lambda mv: mv.member_id)
    absences.sort(key=lambda a: a.member_id)
    return rollcall, member_votes, absences


# --- ingest pipeline ------------------------------------------------------


def _lis_to_bioguide() -> dict[str, str]:
    """{lis_member_id: bioguide} for every exported Senate member (INC-2), so the
    crosswalk is never hardcoded. Only covered senators are exported, which is all
    the Senate ingest needs (positions are stored for the covered delegation)."""
    import json

    from ingest.export import MEMBERS_DIR

    out: dict[str, str] = {}
    for path in sorted(MEMBERS_DIR.glob("*.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        if m["chamber"] != "senate":
            continue
        lis = m["ids"].get("lis")
        if lis:
            out[lis] = m["id"]
    return out


def _covered_senate(congresses: list[int]) -> dict[int, set[str]]:
    """{congress: covered Senate-member bioguides serving that congress}."""
    import json

    from ingest.export import MEMBERS_DIR
    from ingest.sources.legislators import _term_overlaps

    per_congress: dict[int, set[str]] = {c: set() for c in congresses}
    for path in sorted(MEMBERS_DIR.glob("*.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        if m["chamber"] != "senate":
            continue
        for c in congresses:
            if any(_term_overlaps(t, c) for t in m["terms"] if t["chamber"] == "senate"):
                per_congress[c].add(m["id"])
    return per_congress


def _quarantine(rc_id: str, error: str) -> None:
    import json

    from ingest.cache import repo_root

    qdir = repo_root() / "data" / "quality" / "quarantine"
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / f"{rc_id}.json").write_text(
        json.dumps({"rollcall_id": rc_id, "error": error}, indent=2, sort_keys=True),
        encoding="utf-8", newline="\n",
    )


def run(argv: list[str] | None = None) -> int:
    """Ingest every Senate roll call for the covered Congresses → data/votes/s-*
    + data/absences/. Idempotent/resumable (cached fetches). Fails (nonzero) on any
    covered-member gap, MS-row validation failure, or enumeration break (§6.1)."""
    import httpx

    from ingest import config, incremental
    from ingest.cache import RetryableHTTPError, repo_root
    from ingest.export import export_absence, export_rollcall
    from ingest.sources import senate_xml

    fetch_errors = (RetryableHTTPError, httpx.HTTPError, OSError)

    cutoff = incremental.final_cutoff()  # finalized rolls are skipped (§6.1)
    lis_to_bioguide = _lis_to_bioguide()
    covered = _covered_senate(config.CONGRESSES)
    gaps: list[str] = []          # completeness / covered-member gaps (correctness)
    ms_failures: list[str] = []   # MS-row / tally validation failures (hard fail)
    fetch_failures: list[str] = []
    n_votes = n_abs = n_skipped = 0
    session_counts: dict[str, tuple[int, int]] = {}

    for congress in config.CONGRESSES:
        expected_ms = covered[congress]
        for session in SESSIONS[congress]:
            try:
                menu = senate_xml.parse_menu(senate_xml.vote_menu(congress, session).text)
            except fetch_errors as exc:
                fetch_failures.append(f"menu {congress}/{session}: {type(exc).__name__}")
                continue
            rolls = sorted(menu)
            count = max(rolls) if rolls else 0
            session_counts[f"{congress}/{session}"] = (len(rolls), count)
            # Completeness oracle: Senate rolls are numbered 1..N contiguously, so
            # a hole or a short list can never masquerade as a complete ingest.
            if rolls != list(range(1, count + 1)):
                gaps.append(f"{congress}/{session}: rolls not contiguous 1..{count}")
            for roll in rolls:
                rc_id = f"s-{congress}-{session}-{roll:04d}"
                if incremental.roll_is_final(rc_id, cutoff):
                    n_skipped += 1
                    continue
                try:
                    detail = senate_xml.vote_detail(congress, session, roll).text
                except fetch_errors as exc:
                    fetch_failures.append(f"{rc_id}: {type(exc).__name__}")
                    continue
                try:
                    rc, mvs, absences = parse_rollcall(
                        detail, congress, session, lis_to_bioguide, menu[roll]
                    )
                except (ValidationError, KeyError, ValueError) as exc:
                    # ValueError covers UnknownVoteCast, TallyMismatch, and _parse_date.
                    _quarantine(rc_id, f"{type(exc).__name__}: {exc}")
                    ms_failures.append(rc_id)
                    continue
                missing = expected_ms - {mv.member_id for mv in mvs}
                if missing:
                    gaps.append(f"{rc_id}: missing MS members {sorted(missing)}")
                export_rollcall(rc, mvs)
                for ab in absences:
                    # overwrite=False: never clobber an owner-approved reason (D35).
                    export_absence(ab, overwrite=False)
                    n_abs += 1
                n_votes += 1

    gaps_path = repo_root() / "data" / "quality" / "senate-gaps.md"
    if gaps:
        gaps_path.parent.mkdir(parents=True, exist_ok=True)
        gaps_path.write_text(
            "# Senate ingest gaps (INC-4)\n\nCovered-member vote gaps + enumeration "
            "breaks — CI fails until this is empty for covered Congresses.\n\n"
            + "\n".join(f"- {g}" for g in gaps) + "\n",
            encoding="utf-8", newline="\n",
        )
    elif gaps_path.exists():
        gaps_path.unlink()

    for label, (got, count) in session_counts.items():
        print(f"  {label}: ingested {got} rolls (max roll {count})")
    print(f"civic-ledger senate-votes: {n_votes} new/refreshed roll calls, "
          f"{n_abs} absence stubs, {n_skipped} finalized rolls skipped.")
    if fetch_failures:
        print(f"FAIL: {len(fetch_failures)} fetch(es) failed (re-run to retry): "
              f"{fetch_failures[:10]}")
    if ms_failures:
        print(f"FAIL: {len(ms_failures)} MS/tally validation failures (quarantined): "
              f"{ms_failures[:10]}")
    if gaps:
        print(f"FAIL: {len(gaps)} covered-member/enumeration gap(s) -> data/quality/senate-gaps.md")
    return 1 if (fetch_failures or ms_failures or gaps) else 0
