"""INC-3 — House roll-call parsing (pure) + the ingest pipeline. V2-1 (D61)
expands covered positions from the 6-member MS delegation to every member of
the House, including the 6 non-voting delegates.

The `/house-vote/{c}/{s}/{roll}/members` response is self-contained (verified in
the INC-1 spike + INC-3 probes): it carries `voteQuestion`, `voteType`, `result`,
`sourceDataURL` (the clerk XML), `startDate`, and every member's position — so one
fetch per roll yields the whole `RollCall` plus positions. Chamber totals are
computed from the full results list (independent of any per-party summary).

Positions are persisted for EVERY result, with no state filter — delegates
included (D61: excluding them broke `totals` recomputability, since they cast
real votes in ~1/3 of rolls, Committee of the Whole). `ingest/coverage.py` keeps
delegates out of the "expected on every roll" set for gap-reporting, since the
Constitution bars them from final-passage rolls — a fact about coverage
EXPECTATIONS, not about what gets recorded. `vote_class` is a provisional
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
    """A voting-state voter with no Member record — the roster changed and hasn't
    caught up (R-2/D60). Forces quarantine + run failure, like the Senate path's
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
    """Parse one `/members` response into a chamber `RollCall`, every result's
    `MemberVote` (D61: no state filter — delegates included when the source
    includes them), and an `Absence` stub per `not_voting`. Raises on malformed
    data so the caller can quarantine the whole roll (§6.1).

    `covered` (the FULL roster serving ON THIS ROLL'S DATE — date-windowed, not
    just congress-windowed, D60 — pass `coverage.covered_on()`'s result, which
    includes delegates, NOT `expected_on()`'s gap-reporting subset) is the churn
    guard (R-2): when supplied, a voter outside it raises `UnknownMember`, so a
    roster change the ingest hasn't caught up to fails loudly instead of
    exporting an orphan. `None` (unit tests, backfill) skips the check."""
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
                f"{rc_id}: voter(s) {sorted(extra)} not in roster — run "
                f"`ingest members` to refresh the covered set, then re-ingest"
            )

    member_votes.sort(key=lambda m: m.member_id)
    absences.sort(key=lambda a: a.member_id)
    return rollcall, member_votes, absences


# --- ingest pipeline ------------------------------------------------------


def _quarantine(rc_id: str, error: str) -> None:
    """Record the failure AND remove any stale prior export for this roll (V2-1):
    a roll that fails to re-parse under the current data model must publish
    NOTHING rather than a stale file from an earlier architecture (e.g. a
    pre-V2-1 file with only 6 members' positions sitting next to 3,463 fully
    up-to-date ones, invisibly wrong under the new "every position" contract —
    found empirically when verify-recompute flagged exactly the 4 quarantined
    rolls). Absence stubs for the roll are removed too (they'd otherwise
    reciprocity-fail against a vote file that no longer exists)."""
    from ingest.cache import repo_root
    from ingest.export import ABSENCES_DIR, VOTES_DIR, congress_of

    qdir = repo_root() / "data" / "quality" / "quarantine"
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / f"{rc_id}.json").write_text(
        json.dumps({"rollcall_id": rc_id, "error": error}, indent=2, sort_keys=True),
        encoding="utf-8", newline="\n",
    )
    stale_votes = VOTES_DIR / f"{rc_id}.json"
    if stale_votes.exists():
        stale_votes.unlink()
    abs_dir = ABSENCES_DIR / congress_of(rc_id)
    if abs_dir.exists():
        for stale_abs in abs_dir.glob(f"*--{rc_id}.json"):
            stale_abs.unlink()


def _clear_quarantine(rc_id: str) -> None:
    """Remove this roll's quarantine file once it has exported cleanly (D87). Without
    this, data/quality/quarantine/ kept every id that ever failed, so it stopped
    describing what is ACTUALLY quarantined — the owner-facing signal it exists to be."""
    from ingest.cache import repo_root

    (repo_root() / "data" / "quality" / "quarantine" / f"{rc_id}.json").unlink(
        missing_ok=True
    )


def run(argv: list[str] | None = None) -> int:
    """Ingest every House roll call for the covered Congresses → data/votes/ +
    data/absences/. Idempotent: cached fetches are reused, so a crashed run
    resumes cleanly on re-invocation. Fails (nonzero) on any covered-member gap
    or MS-delegation validation failure (§6.1)."""
    import httpx

    from ingest import config, coverage, incremental
    from ingest.cache import RetryableHTTPError, repo_root
    from ingest.export import (
        ABSENCES_DIR,
        MEMBERS_DIR,
        congress_of,
        export_absence,
        export_rollcall,
    )
    from ingest.sources import congress_gov

    # Any fetch failure that survives tenacity's retries (persistent 5xx/429 →
    # RetryableHTTPError, timeouts/network → httpx.HTTPError, disk → OSError).
    fetch_errors = (RetryableHTTPError, httpx.HTTPError, OSError)

    force_all = bool(argv) and "--all" in argv  # re-parse finalized rolls (schema backfill)
    cutoff = incremental.final_cutoff()  # rolls older than this are skipped if final
    # Loaded once (D60): per-roll eligibility is date-windowed, not congress-windowed
    # (see ingest/coverage.py), so it's computed fresh per roll from these terms
    # rather than a single set reused across a whole congress.
    terms = coverage.member_terms(MEMBERS_DIR, "house")
    delegates = coverage.delegate_bioguides(MEMBERS_DIR)  # D61: never a gap, always accepted
    accepted_ids = incremental.accepted_quarantines()  # owner-reviewed, non-fatal (§6.1)
    gaps: list[str] = []          # rolls missing a covered member on that roll's date
    ms_failures: list[str] = []   # NEW/unexpected validation failures (hard fail, §6.1)
    accepted: list[str] = []      # quarantines on the owner's accept-list (not a failure)
    fetch_failures: list[str] = []  # rolls whose fetch failed after retries
    n_votes = n_abs = n_skipped = 0
    session_counts: dict[str, tuple[int, int]] = {}

    for congress in config.CONGRESSES:
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
                    # Inside the try: a response missing either key, or a null
                    # `startDate` (TypeError on the `[:10]` slice in `covered_on`),
                    # must quarantine THIS roll, not abort the run (same shape as
                    # the Senate pre-parse guard).
                    date = data["houseRollCallVoteMemberVotes"]["startDate"]
                    roster = coverage.covered_on(terms, date)  # full roster incl. delegates
                    rc, mvs, absences = parse_rollcall(data, congress, session, roster)
                except (ValidationError, KeyError, TypeError,
                        UnknownVoteCast, UnknownMember) as exc:
                    _quarantine(rc_id, f"{type(exc).__name__}: {exc}")
                    # Can't confirm rows → publish nothing. A NEW id fails the run;
                    # an owner-accepted id (accept-list) stays green (§6.1).
                    (accepted if rc_id in accepted_ids else ms_failures).append(rc_id)
                    continue
                if rc.vote_class_rule != NON_POSITION_RULE:
                    # D61: gap-reporting subtracts delegates/Speaker/seating-lag —
                    # narrower than `roster`, which stays the full churn-guard set.
                    expected = coverage.expected_on(terms, date, delegates)
                    missing = expected - {mv.member_id for mv in mvs}
                    if missing:
                        gaps.append(f"{rc_id}: missing members {sorted(missing)}")
                export_rollcall(rc, mvs)
                _clear_quarantine(rc_id)
                abs_dir = ABSENCES_DIR / congress_of(rc_id)  # V2-1: sharded by congress
                for ab in absences:
                    # overwrite=False: never clobber an owner-approved reason (D35).
                    export_absence(ab, out_dir=abs_dir, overwrite=False)
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
        print(f"FAIL: {len(ms_failures)} roll validation failures "
              f"(quarantined): {ms_failures[:10]}")
    if accepted:
        print(f"note: {len(accepted)} known-quarantined roll(s) accepted, not a "
              f"failure (data/quality/accepted-quarantine.yaml): {accepted[:10]}")
    if gaps:
        print(f"FAIL: {len(gaps)} covered-member gap(s) -> data/quality/house-gaps.md")
    return 1 if (fetch_failures or ms_failures or gaps) else 0
