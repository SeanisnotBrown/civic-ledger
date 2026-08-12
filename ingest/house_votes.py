"""INC-3 — House roll-call parsing (pure) + the ingest pipeline.

The `/house-vote/{c}/{s}/{roll}/members` response is self-contained (verified in
the INC-1 spike + INC-3 probes): it carries `voteQuestion`, `voteType`, `result`,
`sourceDataURL` (the clerk XML), `startDate`, and every member's position — so one
fetch per roll yields the whole `RollCall` plus positions. Chamber totals are
computed from the full results list (independent of any per-party summary).

Covered positions are stored only for the MS delegation (`voteState == "MS"`); the
`RollCall` itself is a chamber-wide record. `vote_class` is a provisional
`other`/`unclassified` until the §A1 classifier lands in INC-5 (build order 3→4→5).
"""

from __future__ import annotations

import json
from collections import Counter

from pydantic import ValidationError

from ingest.models import Absence, Chamber, MemberVote, Position, RollCall

# House sessions per covered Congress (119/2 is ongoing; its count grows, so the
# ingest is re-runnable and picks up new rolls on each run).
SESSIONS: dict[int, tuple[int, ...]] = {118: (1, 2), 119: (1, 2)}

# Congress.gov `voteCast` → canonical position enum (SHAPES §3). The House uses
# Yea/Nay on "Yea-and-Nay" ballots (final passage) and Aye/No on "Recorded Vote"
# ballots (Committee of the Whole, amendments); both are the same yea/nay position.
VOTE_MAP: dict[str, Position] = {
    "Yea": "yea",
    "Aye": "yea",
    "Nay": "nay",
    "No": "nay",
    "Present": "present",
    "Not Voting": "not_voting",
}

PROVISIONAL_CLASS = "other"
PROVISIONAL_RULE = "unclassified"  # replaced by the §A1 classifier in INC-5
# Speaker-election rolls record a vote FOR A CANDIDATE (by surname), not a
# yea/nay position — so they get a RollCall (they count toward the session total)
# but no MemberVotes, and are excluded from vote-coverage symmetry.
NON_POSITION_RULE = "non_position"


class UnknownVoteCast(ValueError):
    """A `voteCast` string outside VOTE_MAP — forces quarantine (§6.1)."""


class UnknownMember(ValueError):
    """An MS voter with no Member record — the delegation changed and the roster
    hasn't caught up (R-2). Forces quarantine + run failure, like the Senate path's
    KeyError, so an orphan (votes on file, no page/metrics — value #2) never exports."""


def rollcall_id(chamber: Chamber, congress: int, session: int, roll: int) -> str:
    prefix = "h" if chamber == "house" else "s"
    return f"{prefix}-{congress}-{session}-{roll:04d}"


def _bill_id(mv: dict) -> str | None:
    # Quorum calls / Speaker elections have no legislation → None (never fabricate).
    btype = (mv.get("legislationType") or "").strip()
    bnum = (mv.get("legislationNumber") or "").strip()
    if not btype or not bnum:
        return None
    return f"{btype.lower()}{bnum}-{mv['congress']}"


def _position(vote_cast: str) -> Position:
    try:
        return VOTE_MAP[vote_cast]
    except KeyError as exc:
        raise UnknownVoteCast(f"unknown voteCast {vote_cast!r}") from exc


def parse_rollcall(
    members_json: dict, congress: int, session: int, covered: set[str] | None = None
) -> tuple[RollCall, list[MemberVote], list[Absence]]:
    """Parse one `/members` response into a chamber `RollCall`, the MS delegation's
    `MemberVote`s, and an `Absence` stub per MS `not_voting`. Raises on malformed
    data so the caller can quarantine the whole roll (§6.1).

    `covered` (the bioguides rostered for this congress, from the INC-2 export) is the
    churn guard (R-2): when supplied, an MS voter outside it raises `UnknownMember`, so
    a delegation change the roster hasn't caught up to fails loudly instead of exporting
    an orphan. `None` (unit tests, backfill) skips the check."""
    mv = members_json["houseRollCallVoteMemberVotes"]
    roll = int(mv["rollCallNumber"])
    rc_id = rollcall_id("house", congress, session, roll)
    results = mv["results"]

    # A roll is "non-position" when a MAJORITY of votes are unmappable — i.e. an
    # election where members vote for a candidate by surname (Speaker elections).
    # A lone stray cast on an otherwise yea/nay roll is NOT non-position: it falls
    # through to `_position` below and quarantines (a real data glitch, not scope).
    unmappable = sum(1 for r in results if r["voteCast"] not in VOTE_MAP)
    non_position = unmappable * 2 > len(results)

    party_totals: dict[str, dict[str, int]] | None = None
    if non_position:
        totals: dict[str, int] = dict(Counter(r["voteCast"] for r in results))
        rule = NON_POSITION_RULE
    else:
        totals = {"yea": 0, "nay": 0, "present": 0, "not_voting": 0}
        # party_totals: the same tally split by the source's party letter (D/R/I).
        # Aggregate only — the per-member party is read from the raw response but
        # never stored per person (value #3); it feeds the party-unity metric.
        party_totals = {}
        for r in results:
            pos = _position(r["voteCast"])
            totals[pos] += 1
            party = (r.get("voteParty") or "").strip() or "?"
            bucket = party_totals.setdefault(
                party, {"yea": 0, "nay": 0, "present": 0, "not_voting": 0}
            )
            bucket[pos] += 1
        rule = PROVISIONAL_RULE

    rollcall = RollCall(
        id=rc_id,
        chamber="house",
        congress=congress,
        session=session,
        number=roll,
        date=mv["startDate"],
        question=mv["voteQuestion"],
        vote_class=PROVISIONAL_CLASS,
        vote_class_rule=rule,
        bill_id=_bill_id(mv),
        result=mv["result"],
        totals=totals,
        party_totals=party_totals,
        source_url=mv["sourceDataURL"],
    )

    member_votes: list[MemberVote] = []
    absences: list[Absence] = []
    if not non_position:
        for r in results:
            if r.get("voteState") != "MS":
                continue
            pos = _position(r["voteCast"])
            member_votes.append(
                MemberVote(member_id=r["bioguideID"], rollcall_id=rc_id, position=pos)
            )
            if pos == "not_voting":
                # Seed an Absence stub; INC-6 may attach a verbatim CREC explanation.
                absences.append(Absence(member_id=r["bioguideID"], rollcall_id=rc_id))

    if covered is not None and not non_position:
        extra = {mv.member_id for mv in member_votes} - covered
        if extra:
            raise UnknownMember(
                f"{rc_id}: MS voter(s) {sorted(extra)} not in roster — run "
                f"`ingest members` to refresh the covered set, then re-ingest"
            )

    member_votes.sort(key=lambda m: m.member_id)
    absences.sort(key=lambda a: a.member_id)
    return rollcall, member_votes, absences


# --- ingest pipeline ------------------------------------------------------


def _covered_house(congresses: list[int]) -> dict[int, set[str]]:
    """{congress: set of covered House-member bioguides serving that congress},
    read from the INC-2 export so the covered set is never hardcoded."""
    from ingest.export import MEMBERS_DIR
    from ingest.sources.legislators import _term_overlaps

    per_congress: dict[int, set[str]] = {c: set() for c in congresses}
    for path in sorted(MEMBERS_DIR.glob("*.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        if m["chamber"] != "house":
            continue
        for c in congresses:
            if any(_term_overlaps(t, c) for t in m["terms"] if t["chamber"] == "house"):
                per_congress[c].add(m["id"])
    return per_congress


def _quarantine(rc_id: str, error: str) -> None:
    from ingest.cache import repo_root

    qdir = repo_root() / "data" / "quality" / "quarantine"
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / f"{rc_id}.json").write_text(
        json.dumps({"rollcall_id": rc_id, "error": error}, indent=2, sort_keys=True),
        encoding="utf-8", newline="\n",
    )


def run(argv: list[str] | None = None) -> int:
    """Ingest every House roll call for the covered Congresses → data/votes/ +
    data/absences/. Idempotent: cached fetches are reused, so a crashed run
    resumes cleanly on re-invocation. Fails (nonzero) on any covered-member gap
    or MS-delegation validation failure (§6.1)."""
    import httpx

    from ingest import config, incremental
    from ingest.cache import RetryableHTTPError, repo_root
    from ingest.export import export_absence, export_rollcall
    from ingest.sources import congress_gov

    # Any fetch failure that survives tenacity's retries (persistent 5xx/429 →
    # RetryableHTTPError, timeouts/network → httpx.HTTPError, disk → OSError).
    fetch_errors = (RetryableHTTPError, httpx.HTTPError, OSError)

    force_all = bool(argv) and "--all" in argv  # re-parse finalized rolls (schema backfill)
    cutoff = incremental.final_cutoff()  # rolls older than this are skipped if final
    covered = _covered_house(config.CONGRESSES)
    gaps: list[str] = []          # rolls missing a covered MS member (correctness)
    ms_failures: list[str] = []   # MS-row validation failures (hard fail, §6.1)
    fetch_failures: list[str] = []  # rolls whose fetch failed after retries
    n_votes = n_abs = n_skipped = 0
    session_counts: dict[str, tuple[int, int]] = {}

    for congress in config.CONGRESSES:
        expected_ms = covered[congress]
        for session in SESSIONS[congress]:
            rolls, count = congress_gov.house_vote_roll_numbers(congress, session)
            session_counts[f"{congress}/{session}"] = (len(rolls), count)
            if len(rolls) != count:
                gaps.append(f"{congress}/{session}: enumerated {len(rolls)} != count {count}")
            for roll in rolls:
                rc_id = rollcall_id("house", congress, session, roll)
                # Incremental (§6.1): a finalized, already-exported roll is never
                # re-fetched — the nightly job only touches new/recent rolls. `--all`
                # forces every roll (used once to backfill party_totals from cache).
                if not force_all and incremental.roll_is_final(rc_id, cutoff):
                    n_skipped += 1
                    continue
                try:
                    data = congress_gov.house_vote_members(congress, session, roll).json()
                except fetch_errors as exc:
                    # Persistent fetch failure (past tenacity's 5 retries). Don't
                    # discard the run — record it and continue; a re-run retries it
                    # (cached rolls are instant). Fails the run at the end.
                    fetch_failures.append(f"{rc_id}: {type(exc).__name__}")
                    continue
                try:
                    rc, mvs, absences = parse_rollcall(data, congress, session, expected_ms)
                except (ValidationError, KeyError, UnknownVoteCast, UnknownMember) as exc:
                    _quarantine(rc_id, f"{type(exc).__name__}: {exc}")
                    ms_failures.append(rc_id)  # can't confirm MS rows → treat as MS failure
                    continue
                if rc.vote_class_rule != NON_POSITION_RULE:
                    missing = expected_ms - {mv.member_id for mv in mvs}
                    if missing:
                        gaps.append(f"{rc_id}: missing MS members {sorted(missing)}")
                export_rollcall(rc, mvs)
                for ab in absences:
                    # overwrite=False: never clobber an owner-approved reason (D35).
                    export_absence(ab, overwrite=False)
                    n_abs += 1
                n_votes += 1

    # Report
    gaps_path = repo_root() / "data" / "quality" / "house-gaps.md"
    if gaps:
        gaps_path.parent.mkdir(parents=True, exist_ok=True)
        gaps_path.write_text(
            "# House ingest gaps (INC-3)\n\nCovered-member vote gaps — CI fails until "
            "this is empty for covered Congresses.\n\n"
            + "\n".join(f"- {g}" for g in gaps) + "\n",
            encoding="utf-8", newline="\n",
        )
    elif gaps_path.exists():
        gaps_path.unlink()  # no gaps → remove any stale report

    for label, (got, count) in session_counts.items():
        print(f"  {label}: ingested {got} rolls (official count {count})")
    print(f"civic-ledger house-votes: {n_votes} new/refreshed roll calls, "
          f"{n_abs} absence stubs, {n_skipped} finalized rolls skipped.")
    if fetch_failures:
        print(f"FAIL: {len(fetch_failures)} roll(s) failed to fetch (re-run to retry): "
              f"{fetch_failures[:10]}")
    if ms_failures:
        print(f"FAIL: {len(ms_failures)} MS-delegation validation failures "
              f"(quarantined): {ms_failures[:10]}")
    if gaps:
        print(f"FAIL: {len(gaps)} covered-member gap(s) -> data/quality/house-gaps.md")
    return 1 if (fetch_failures or ms_failures or gaps) else 0
