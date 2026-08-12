"""`verify-recompute` console entrypoint (INC-7; brief 5.2 "recompute and match").

A third party clones the public repo and re-derives figures from the published
files, matching what we ship. The genuine limit (D22/D26): `RollCall.totals` is
the *chamber-wide* tally as published by the official source, while our
`member_votes` carry ONLY the covered Mississippi delegation — we deliberately
don't collect the other ~429 members' positions, so the chamber totals are not
recomputable from our data. What IS recomputable-and-matchable over 100% of roll
calls, and what this script checks:

1. **Coverage** — every covered member (per chamber/congress) has exactly one
   recorded position per eligible roll (a `MemberVote` OR a not_voting absence),
   skipping `non_position` rolls (Speaker elections carry no yea/nay).
2. **Subset consistency** — for each position category, the count of embedded MS
   `member_votes` never exceeds `RollCall.totals[category]` (MS positions are a
   subset of the chamber tally).
3. **Absence reciprocity** — every `position == "not_voting"` MemberVote has a
   matching data/absences/{member}--{roll}.json, and every absence file's
   (member, roll) has a matching not_voting MemberVote.
4. **Party-total consistency** — for every position roll, the per-party breakdown
   `party_totals` sums (over parties) to the chamber `totals` in each category, and
   `party_totals` is present exactly on position rolls (None on `non_position`). The
   raw per-member party isn't committed, so this is what proves the aggregates that
   feed party-unity are internally honest (INC-10, §A).

Exit 0 = every invariant holds for every roll; nonzero lists the failures. It is
also exercised as a pytest test so §8's "recompute-and-match script as a test" holds.
"""

from __future__ import annotations

import json

from ingest.cache import repo_root

_POSITIONS = ("yea", "nay", "present", "not_voting")


def _covered_by_chamber() -> dict[str, dict[int, set[str]]]:
    """{chamber: {congress: covered bioguides serving it}} — reuses the symmetry
    check's covered-set logic so the two never drift."""
    from ingest.checks.symmetry import _covered

    return {chamber: _covered(chamber) for chamber in ("house", "senate")}


def check_dataset() -> list[str]:
    """Run all three invariants over the whole exported dataset. Returns the list
    of failures (empty = everything matched)."""
    votes_dir = repo_root() / "data" / "votes"
    absences_dir = repo_root() / "data" / "absences"
    covered = _covered_by_chamber()
    failures: list[str] = []

    # Absence files present on disk, keyed (member, roll) — for reciprocity.
    absence_keys: set[tuple[str, str]] = set()
    if absences_dir.exists():
        for path in absences_dir.glob("*.json"):
            rec = json.loads(path.read_text(encoding="utf-8"))
            absence_keys.add((rec["member_id"], rec["rollcall_id"]))

    seen_notvoting: set[tuple[str, str]] = set()

    for path in sorted(votes_dir.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        rc = rec["rollcall"]
        rc_id = rc["id"]
        mvs = rec["member_votes"]

        if rc["vote_class_rule"] != "non_position":
            # (1) Coverage — every covered member has exactly one recorded
            # position. A not_voting member IS in member_votes (and additionally
            # carries an absence stub, checked by reciprocity below), so coverage
            # is accounted by member_votes alone.
            expected = covered.get(rc["chamber"], {}).get(rc["congress"], set())
            voted = [mv["member_id"] for mv in mvs]
            voted_set = set(voted)
            missing = expected - voted_set
            if missing:
                failures.append(f"{rc_id}: coverage — no position for {sorted(missing)}")
            # A position for a member NOT in the covered set = roster churn drift
            # (votes on record, no page/metrics). expected−got alone misses it (R-2).
            extra = voted_set - expected
            if extra:
                failures.append(f"{rc_id}: coverage — unknown member {sorted(extra)}")
            if len(voted) != len(voted_set):
                dups = sorted({m for m in voted if voted.count(m) > 1})
                failures.append(f"{rc_id}: coverage — duplicate positions for {dups}")

            # (2) Subset consistency — MS position counts <= chamber totals.
            tallied: dict[str, int] = {p: 0 for p in _POSITIONS}
            for mv in mvs:
                tallied[mv["position"]] = tallied.get(mv["position"], 0) + 1
            for pos in _POSITIONS:
                if tallied[pos] > rc["totals"].get(pos, 0):
                    failures.append(
                        f"{rc_id}: subset — MS {pos}={tallied[pos]} exceeds "
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


def main(argv: list[str] | None = None) -> int:
    votes_dir = repo_root() / "data" / "votes"
    if not votes_dir.exists() or not any(votes_dir.glob("*.json")):
        print("verify-recompute: no roll-call data yet (no-op).")
        return 0
    failures = check_dataset()
    n_rolls = sum(1 for _ in votes_dir.glob("*.json"))
    if failures:
        print(f"VERIFY-RECOMPUTE FAILED — {len(failures)} mismatch(es):")
        for f in failures[:40]:
            print(f"  {f}")
        if len(failures) > 40:
            print(f"  ... and {len(failures) - 40} more")
        return 1
    print(
        f"verify-recompute: OK — coverage, subset, and reciprocity match "
        f"on {n_rolls} roll calls."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
