"""`verify-recompute` console entrypoint (INC-7; brief 5.2 "recompute and match").

A third party clones the public repo and re-derives figures from the published
files, matching what we ship. V2-1 (D61) is the credibility upgrade this was
always meant to reach: positions are now persisted for every result on every
roll (delegates included), so `RollCall.totals` — the *chamber-wide* tally as
published by the official source — is now fully, exactly recomputable from
`member_votes`, not merely a subset check. (Before V2-1, `member_votes` carried
only the 6-member Mississippi delegation, and D22/D26 recorded that the chamber
totals could not be re-derived from our data — that limit is retired; the old
docstring text is preserved in git history, not restated here since it is no
longer true.) What this script checks, over 100% of roll calls:

1. **Coverage** — every covered member (date-windowed per roll, D60, with the
   D61 exceptions — delegates, the Speaker, seating lag — excluded from
   "expected") has exactly one recorded position per eligible roll (a
   `MemberVote` OR a not_voting absence), skipping `non_position` rolls
   (Speaker elections carry no yea/nay). Reuses `ingest/coverage.py`, the same
   module `checks/symmetry.py` uses, so the two checks never drift.
2. **Exact reproduction** — for each position category, the count of embedded
   `member_votes` equals `RollCall.totals[category]` exactly. Every result is
   persisted now, so this is strict equality, not a subset bound.
3. **Absence reciprocity** — every `position == "not_voting"` MemberVote has a
   matching data/absences/{congress}/{member}--{roll}.json, and every absence
   file's (member, roll) has a matching not_voting MemberVote.
4. **Party-total consistency** — for every position roll, the per-party breakdown
   `party_totals` sums (over parties) to the chamber `totals` in each category, and
   `party_totals` is present exactly on position rolls (None on `non_position`).
5. **Rankings recompute** (V2-2) — every data/rankings/{metric}.json re-derives
   byte-for-byte from the committed data/metrics.json + data/members alone. A
   ranking that cannot be recomputed from published data may not ship (§7 V2-2
   "on failure"). No-op until data/rankings/ exists.
6. **Grades recompute** (V2-4) — every data/grades/{category}.json re-derives
   byte-for-byte from data/metrics.json + data/members + the ratified
   data/config/thresholds.yaml. A grade that cannot be re-derived from the public
   repo may not ship. No-op until data/grades/ exists.

8. **Events re-derive** (V2-11 task 5) — every data/events/{YYYY-MM}.json
   re-derives byte-for-byte from data/bills/ + data/votes/ alone. These files are
   the only machine-readable URLs the V2-12 alert Worker and the V2-13 push client
   read, so a feed that cannot be re-derived from the published dataset may not
   ship. Catches three distinct things: a stale month file left behind after the
   events that produced it changed, a hand-edit of government action text (which
   0.5 forbids outright), and any accidental non-determinism in the projection
   (an unstable sort, a wall-clock, a dict iteration order). No-op until
   data/events/ exists.

9. **Topics re-derive** (V2-11 task 6) — `data/topics/index.json` re-derives
   byte-for-byte from data/bills alone. Catches the same three classes invariant 8
   does: a stale index after bills moved, a hand-edit of an official government
   term (which 0.5 forbids), and any non-determinism in the projection. No-op until
   data/topics/ exists.

Exit 0 = every invariant holds for every roll; nonzero lists the failures. It is
also exercised as a pytest test so §8's "recompute-and-match script as a test" holds.
"""

from __future__ import annotations

import json

from ingest import coverage
from ingest.cache import repo_root

_POSITIONS = ("yea", "nay", "present", "not_voting")


def check_dataset() -> list[str]:
    """Run all four invariants over the whole exported dataset. Returns the list
    of failures (empty = everything matched)."""
    votes_dir = repo_root() / "data" / "votes"
    absences_dir = repo_root() / "data" / "absences"
    members_dir = repo_root() / "data" / "members"
    terms_by_chamber = {c: coverage.member_terms(members_dir, c) for c in ("house", "senate")}
    delegates = coverage.delegate_bioguides(members_dir)
    failures: list[str] = []

    # Absence files present on disk, keyed (member, roll) — for reciprocity.
    absence_keys: set[tuple[str, str]] = set()
    if absences_dir.exists():
        for path in absences_dir.glob("*/*.json"):  # V2-1: sharded by congress
            rec = json.loads(path.read_text(encoding="utf-8"))
            absence_keys.add((rec["member_id"], rec["rollcall_id"]))

    seen_notvoting: set[tuple[str, str]] = set()

    for path in sorted(votes_dir.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        rc = rec["rollcall"]
        rc_id = rc["id"]
        mvs = rec["member_votes"]

        if rc["vote_class_rule"] != "non_position":
            # (1) Coverage — every EXPECTED member has exactly one recorded
            # position. A not_voting member IS in member_votes (and additionally
            # carries an absence stub, checked by reciprocity below), so coverage
            # is accounted by member_votes alone. Date-windowed (D60); the three
            # D61 exceptions are subtracted from `expected` only, never from
            # `roster` (the full covered set), so a delegate or the Speaker
            # voting is correctly accepted, never flagged unknown.
            terms = terms_by_chamber[rc["chamber"]]
            roster = coverage.covered_on(terms, rc["date"])
            expected = coverage.expected_on(terms, rc["date"], delegates)
            voted = [mv["member_id"] for mv in mvs]
            voted_set = set(voted)
            missing = expected - voted_set
            if missing:
                failures.append(f"{rc_id}: coverage — no position for {sorted(missing)}")
            # A position for a member NOT in the full roster = roster churn drift
            # (votes on record, no page/metrics). expected−got alone misses it (R-2).
            extra = voted_set - roster
            if extra:
                failures.append(f"{rc_id}: coverage — unknown member {sorted(extra)}")
            if len(voted) != len(voted_set):
                dups = sorted({m for m in voted if voted.count(m) > 1})
                failures.append(f"{rc_id}: coverage — duplicate positions for {dups}")

            # (2) Exact reproduction (D61) — every position is persisted now, so
            # embedded counts must equal the chamber totals exactly, not just
            # bound them from below.
            tallied: dict[str, int] = {p: 0 for p in _POSITIONS}
            for mv in mvs:
                tallied[mv["position"]] = tallied.get(mv["position"], 0) + 1
            for pos in _POSITIONS:
                if tallied[pos] != rc["totals"].get(pos, 0):
                    failures.append(
                        f"{rc_id}: exact-reproduction — recomputed {pos}={tallied[pos]} != "
                        f"chamber total {rc['totals'].get(pos, 0)}"
                    )

            # (4) Party-total consistency — present on position rolls, and the
            # per-party breakdown sums to the chamber totals per category.
            pt = rc.get("party_totals")
            if pt is None:
                failures.append(f"{rc_id}: party_totals — missing on a position roll")
            else:
                for pos in _POSITIONS:
                    summed = sum(party.get(pos, 0) for party in pt.values())
                    if summed != rc["totals"].get(pos, 0):
                        failures.append(
                            f"{rc_id}: party_totals — {pos} sums to {summed} != "
                            f"chamber total {rc['totals'].get(pos, 0)}"
                        )
        else:
            # non_position rolls carry no yea/nay to split → party_totals is None.
            if rec["rollcall"].get("party_totals") is not None:
                failures.append(f"{rc_id}: party_totals — set on a non_position roll")

        # (3) Absence reciprocity (both directions), all rolls.
        for mv in mvs:
            if mv["position"] == "not_voting":
                key = (mv["member_id"], rc_id)
                seen_notvoting.add(key)
                if key not in absence_keys:
                    failures.append(
                        f"{rc_id}: reciprocity — {mv['member_id']} not_voting but no absence file"
                    )

    # Every absence file must correspond to a recorded not_voting position.
    for member_id, rc_id in sorted(absence_keys):
        if (member_id, rc_id) not in seen_notvoting:
            failures.append(
                f"{rc_id}: reciprocity — absence file for {member_id} with no not_voting vote"
            )

    return failures


def check_rankings() -> list[str]:
    """(5) Rankings recompute exactly from published data. Each committed
    data/rankings/{metric}.json must equal a fresh `rankings.build_all()` (which
    reads only data/metrics.json + data/members) byte-for-byte, and the set of
    ranking files must be exactly the ranked metrics — no stale file, no missing
    one. No-op until data/rankings/ exists (pre-V2-2)."""
    from ingest import rankings
    from ingest.export import _dumps

    rankings_dir = repo_root() / "data" / "rankings"
    if not rankings_dir.exists() or not any(rankings_dir.glob("*.json")):
        return []
    failures: list[str] = []
    recomputed = rankings.build_all()  # reads committed metrics.json + members
    committed = {p.stem for p in rankings_dir.glob("*.json")}
    if committed != set(recomputed):
        failures.append(
            f"rankings — file set {sorted(committed)} != ranked metrics {sorted(recomputed)}"
        )
    for metric, rf in recomputed.items():
        path = rankings_dir / f"{metric}.json"
        if not path.exists():
            continue  # reported above as a set mismatch
        if path.read_text(encoding="utf-8") != _dumps(rf.model_dump()):
            failures.append(f"rankings — {metric}.json does not match a fresh recompute")
    return failures


def check_grades() -> list[str]:
    """(6) Grades recompute exactly from published data + ratified config (V2-4). Each
    committed data/grades/{category}.json must equal a fresh `scoring.build_all()`
    (which reads only data/metrics.json + data/members + data/config/thresholds.yaml)
    byte-for-byte — a grade that cannot be re-derived from the public repo may not
    ship. No-op until data/grades/ exists (pre-V2-4)."""
    from ingest import scoring
    from ingest.export import _dumps

    grades_dir = repo_root() / "data" / "grades"
    if not grades_dir.exists() or not any(grades_dir.glob("*.json")):
        return []
    failures: list[str] = []
    recomputed = scoring.build_all()
    committed = {p.stem for p in grades_dir.glob("*.json")}
    if committed != set(recomputed):
        failures.append(
            f"grades — file set {sorted(committed)} != graded categories {sorted(recomputed)}"
        )
    for category, gf in recomputed.items():
        path = grades_dir / f"{category}.json"
        if not path.exists():
            continue
        if path.read_text(encoding="utf-8") != _dumps(gf.model_dump()):
            failures.append(f"grades — {category}.json does not match a fresh recompute")
    return failures


def check_legislation_stats() -> list[str]:
    """(7) The dashboard headline recomputes exactly from published data (V2-5). The
    manifest's `counts.legislation` block (the introduced-bill universe vs recorded
    roll-call votes) must equal a fresh `legislation_stats.compute()` over
    data/legislation + data/votes — a landing-page number that cannot be re-derived
    from the public dataset may not ship. No-op until data/legislation/ exists."""
    from ingest import legislation_stats

    data = repo_root() / "data"
    legislation_dir = data / "legislation"
    manifest_path = data / "manifest.json"
    if not legislation_dir.exists() or not manifest_path.exists():
        return []
    committed = json.loads(manifest_path.read_text(encoding="utf-8"))
    published = (committed.get("counts") or {}).get("legislation")
    if published is None:
        return []  # pre-V2-5 manifest without the block
    recomputed = legislation_stats.compute(data)
    if published != recomputed:
        return [f"legislation stats — manifest {published} != recompute {recomputed}"]
    return []


def check_events() -> list[str]:
    """(8) The activity feed re-derives byte-for-byte from bills + votes (V2-11).

    Compares the committed bytes against a fresh `events.compute()` put through the
    same `_dumps` the exporter uses, so this fails on a reordering or a changed
    separator as well as on changed content. Both directions are checked: a month
    file on disk that the projection no longer produces is a failure, not a
    curiosity — `export_events` deliberately never deletes one (a published feed
    URL vanishing silently is worse than a loud mismatch)."""
    from ingest import events
    from ingest.export import _dumps

    data = repo_root() / "data"
    events_dir = data / "events"
    if not events_dir.exists():
        return []
    recomputed = events.compute(data)
    committed = {p.stem: p for p in sorted(events_dir.glob("*.json"))}
    failures: list[str] = []
    for month in sorted(set(committed) | set(recomputed)):
        if month not in committed:
            failures.append(f"events {month} — recomputed but no committed file")
            continue
        if month not in recomputed:
            failures.append(
                f"events {month} — committed file no longer re-derives from "
                f"data/bills (stale month, or an edited action)"
            )
            continue
        want = _dumps(recomputed[month].model_dump())
        got = committed[month].read_text(encoding="utf-8")
        if got != want:
            failures.append(
                f"events {month} — committed bytes != recompute "
                f"({len(got)} vs {len(want)} bytes)"
            )
    return failures


def check_topics() -> list[str]:
    """(9) The topic index re-derives byte-for-byte from the bills (V2-11 task 6).

    Same shape as `check_events`: compare committed BYTES against a fresh
    `topics.compute()` put through the exporter's own `_dumps`, so a reordering or a
    changed separator fails as loudly as changed content. A topic page is built from
    this file, so an index that drifts from data/bills publishes a topic whose bill
    list is not what the government actually tagged."""
    from ingest import topics
    from ingest.export import _dumps

    data = repo_root() / "data"
    path = data / "topics" / "index.json"
    if not path.exists():
        return []
    recomputed = topics.compute(data)
    if recomputed is None:
        return ["topics — index.json is committed but there are no bills to derive it from"]
    want = _dumps(recomputed.model_dump())
    got = path.read_text(encoding="utf-8")
    if got != want:
        return [
            f"topics — committed bytes != recompute ({len(got)} vs {len(want)} bytes)"
        ]
    return []


def check_priorities() -> list[str]:
    """(10) The stated-priorities file re-derives byte-for-byte from the approved
    statements, the members' terms and the ratified Q-B/Q-J constants (P3 task 6). A
    drifted file would show a priority list the rules no longer support."""
    from ingest import priorities
    from ingest.export import _dumps

    data = repo_root() / "data"
    path = priorities.path(data)
    if not path.exists():
        return []
    want = _dumps(priorities.compute(data))
    got = path.read_text(encoding="utf-8")
    if got != want:
        return [
            f"priorities — committed bytes != recompute ({len(got)} vs {len(want)} bytes); "
            "run `uv run export`"
        ]
    return []


def main(argv: list[str] | None = None) -> int:
    votes_dir = repo_root() / "data" / "votes"
    if not votes_dir.exists() or not any(votes_dir.glob("*.json")):
        print("verify-recompute: no roll-call data yet (no-op).")
        return 0
    failures = (
        check_dataset()
        + check_rankings()
        + check_grades()
        + check_legislation_stats()
        + check_events()
        + check_topics()
        + check_priorities()
    )
    n_rolls = sum(1 for _ in votes_dir.glob("*.json"))
    if failures:
        print(f"VERIFY-RECOMPUTE FAILED — {len(failures)} mismatch(es):")
        for f in failures[:40]:
            print(f"  {f}")
        if len(failures) > 40:
            print(f"  ... and {len(failures) - 40} more")
        return 1
    def _count(sub: str) -> int:
        d = repo_root() / "data" / sub
        return sum(1 for _ in d.glob("*.json")) if d.exists() else 0

    n_rankings, n_grades = _count("rankings"), _count("grades")
    derived = []
    if n_rankings:
        derived.append(f"{n_rankings} ranking files")
    if n_grades:
        derived.append(f"{n_grades} grade file(s)")
    if _count("legislation"):
        derived.append("the legislation-universe headline")
    n_events = _count("events")
    if n_events:
        derived.append(f"{n_events} month(s) of the activity feed")
    if (repo_root() / "data" / "topics" / "index.json").exists():
        derived.append("the topic index")
    if (repo_root() / "data" / "priorities.json").exists():
        derived.append("the stated-priorities file")
    tail = f"; {' and '.join(derived)} recompute exactly." if derived else "."
    print(
        f"verify-recompute: OK — coverage, exact reproduction, and reciprocity match "
        f"on {n_rolls} roll calls{tail}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
