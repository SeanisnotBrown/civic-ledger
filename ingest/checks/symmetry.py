"""§6.5 — Symmetry checks (CI, blocking). INC-3 activates the **vote-coverage**
rule (House); INC-4 generalizes it to the Senate. INC-10 activates the **statement
balance** rules (they stay vacuously green until statements are curated in INC-11).
V2-1 (D60/D61) moves vote coverage from per-Congress to date-windowed, via the
shared `ingest/coverage.py` — see that module's docstring for why (mid-congress
churn: resignations, deaths, expulsions, seat changes) and for the three
gap-reporting exceptions (delegates, the Speaker, seating lag).

Vote coverage (§6.5): every covered member has a `MemberVote` for every eligible
roll call of their chamber, on the dates they actually held the seat. Any
UNEXPLAINED gap = fail. This reads the *exported* dataset (data/votes/ +
data/members/), so it guards the published data, not just the ingest run.

Statement balance (§6.5, D1): once the per-member statement median reaches
`SYMMETRY_MEDIAN_ACTIVATION`, three balance rules gate the curated corpus so the
site can never present a lopsided watchlist — (a) every member carries at least
`SYMMETRY_MEMBER_MIN_FRACTION` of the median, (b) the two parties' mean counts are
within `SYMMETRY_PARTY_MEAN_MAX_REL_DIFF`, (c) the parties' specificity-scored
percentages are within `SYMMETRY_SPECIFICITY_MAX_POINT_GAP`. Below the activation
median the rule is INACTIVE (too little data to judge balance), never a failure —
that is its state at INC-10, where zero statements exist (INC-11 curates them).

Output: data/quality/symmetry-report.json (published).
"""

from __future__ import annotations

import json
from statistics import mean, median

from ingest import coverage
from ingest.cache import repo_root


def coverage_gaps(chamber: str, prefix: str) -> list[str]:
    """Vote-coverage gaps for one chamber: every covered member of `chamber`
    must have a `MemberVote` for every eligible roll they were expected on
    (files `data/votes/{prefix}-*.json`), date-windowed per roll (D60) with the
    three D61 exceptions subtracted from "expected" (never from "covered" — an
    UNEXPECTED voter, e.g. a delegate on a Committee-of-the-Whole roll, is still
    a legitimate covered member, not an `UnknownMember` — only someone outside
    the full roster is). Non-position rolls (Speaker elections) carry no
    yea/nay positions and are skipped."""
    votes_dir = repo_root() / "data" / "votes"
    members_dir = repo_root() / "data" / "members"
    terms = coverage.member_terms(members_dir, chamber)
    delegates = coverage.delegate_bioguides(members_dir)
    gaps: list[str] = []
    for path in sorted(votes_dir.glob(f"{prefix}-*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        rc = rec["rollcall"]
        if rc["vote_class_rule"] == "non_position":
            continue
        date = rc["date"]
        roster = coverage.covered_on(terms, date)
        expected = coverage.expected_on(terms, date, delegates)
        got = {mv["member_id"] for mv in rec["member_votes"]}
        missing = expected - got
        if missing:
            gaps.append(f"{rc['id']}: missing {sorted(missing)}")
        # An EXTRA member (voted, but not in the full roster) is churn drift: an
        # official on the vote record with no page/metrics. Flag it too — expected−got
        # alone never catches it (R-2/H-1). Compared against `roster`, not `expected`,
        # so a delegate or the Speaker voting is never mistaken for an unknown member.
        extra = got - roster
        if extra:
            gaps.append(f"{rc['id']}: unknown member {sorted(extra)}")
    return gaps


# Chambers activate as their ingest lands: House at INC-3, Senate at INC-4.
_CHAMBERS: tuple[tuple[str, str], ...] = (("house", "h"), ("senate", "s"))


def _load_statements() -> list[dict]:
    """Every curated Statement record for balance counting (R-1b/M-3: the shared
    loader). `exclude_dead=False` deliberately: balance is about CURATION EFFORT, so a
    curated-but-dead-archive statement still counts toward even-handedness even though
    the site withholds it. Empty until statements are curated (INC-11)."""
    from ingest import statements_io

    return statements_io.load_statements(exclude_dead=False)


def statement_balance(members: list[dict], statements: list[dict]) -> dict:
    """Evaluate the three statement-balance rules (§6.5, D1) over the curated
    corpus. Pure: takes the member + statement records, returns a report dict with
    `status` ∈ {inactive, pass, fail} and, when active, the per-rule findings.
    INACTIVE (never a failure) until the per-member statement median reaches
    `config.SYMMETRY_MEDIAN_ACTIVATION` — the honest state when too few statements
    exist to judge balance (all of INC-10, where zero statements exist)."""
    from ingest import config

    if not members:
        return {"status": "inactive", "reason": "no members"}

    counts = {m["id"]: 0 for m in members}
    scored = {m["id"]: 0 for m in members}  # statements with a specificity_level assigned
    for s in statements:
        mid = s.get("member_id")
        if mid in counts:
            counts[mid] += 1
            if s.get("specificity_level") is not None:
                scored[mid] += 1

    med = median(sorted(counts.values())) if counts else 0
    if med < config.SYMMETRY_MEDIAN_ACTIVATION:
        return {
            "status": "inactive",
            "reason": f"median {med} < activation {config.SYMMETRY_MEDIAN_ACTIVATION}",
            "total_statements": len(statements),
        }

    findings: list[str] = []
    # (a) per-member floor: every member >= fraction * median.
    floor = config.SYMMETRY_MEMBER_MIN_FRACTION * med
    for mid, c in sorted(counts.items()):
        if c < floor:
            findings.append(f"member {mid}: {c} statements < floor {floor:.1f} ({med} median)")

    # (b) party mean counts within a relative difference.
    party_of = {m["id"]: m["party"] for m in members}
    by_party: dict[str, list[int]] = {}
    for mid, c in counts.items():
        by_party.setdefault(party_of[mid], []).append(c)
    means = {p: mean(v) for p, v in by_party.items() if v}
    if len(means) >= 2:
        lo, hi = min(means.values()), max(means.values())
        rel = (hi - lo) / hi if hi else 0.0
        if rel > config.SYMMETRY_PARTY_MEAN_MAX_REL_DIFF:
            findings.append(
                f"party mean gap {rel:.0%} > {config.SYMMETRY_PARTY_MEAN_MAX_REL_DIFF:.0%} "
                f"(means {means})"
            )

    # (c) party specificity-scored percentage within a point gap.
    pct_scored: dict[str, float] = {}
    for p, mids in {pp: [mm for mm in counts if party_of[mm] == pp] for pp in by_party}.items():
        tot = sum(counts[m] for m in mids)
        sc = sum(scored[m] for m in mids)
        if tot:
            pct_scored[p] = 100.0 * sc / tot
    if len(pct_scored) >= 2:
        gap = max(pct_scored.values()) - min(pct_scored.values())
        if gap > config.SYMMETRY_SPECIFICITY_MAX_POINT_GAP:
            findings.append(
                f"specificity-scored gap {gap:.1f}pts > "
                f"{config.SYMMETRY_SPECIFICITY_MAX_POINT_GAP}pts ({pct_scored})"
            )

    return {
        "status": "fail" if findings else "pass",
        "median": med,
        "total_statements": len(statements),
        "findings": findings,
    }


def grading_coverage(members: list[dict]) -> dict:
    """§6.5 grading-coverage (V2-4): for every committed grade category, each covered
    member is either GRADED or in the published exceptions list with a mechanical
    reason — never silently dropped, and no grade points at a member who is gone
    (roster churn). Set equality: `members ∪ exceptions == the roster`. The best/worst
    symmetry rule (any surface listing worst performers renders best performers with
    equal prominence) activates with the V2-5 dashboard; no such surface exists yet,
    so it is vacuously satisfied. INACTIVE (no-op) until grades exist."""
    grades_dir = repo_root() / "data" / "grades"
    files = sorted(grades_dir.glob("*.json")) if grades_dir.exists() else []
    if not files:
        return {"status": "inactive", "reason": "no grades yet"}
    roster = {m["id"] for m in members}
    findings: list[str] = []
    for path in files:
        gf = json.loads(path.read_text(encoding="utf-8"))
        accounted = set(gf.get("members", {})) | set(gf.get("exceptions", {}))
        dropped = roster - accounted
        if dropped:
            findings.append(
                f"{path.stem}: {len(dropped)} covered member(s) neither graded nor "
                f"excepted (silent exemption), e.g. {sorted(dropped)[:5]}"
            )
        stale = accounted - roster
        if stale:
            findings.append(
                f"{path.stem}: {len(stale)} graded/excepted id(s) with no member record "
                f"(roster churn), e.g. {sorted(stale)[:5]}"
            )
    return {
        "status": "fail" if findings else "pass",
        "findings": findings,
        "categories": [p.stem for p in files],
    }


def main() -> int:
    votes_dir = repo_root() / "data" / "votes"
    if not any(votes_dir.glob("*.json")):
        print("symmetry: no roll-call data yet — vote-coverage rule inactive (no-op).")
        return 0

    coverage: dict[str, dict] = {}
    all_gaps: list[tuple[str, str]] = []
    for chamber, prefix in _CHAMBERS:
        if not any(votes_dir.glob(f"{prefix}-*.json")):
            continue  # this chamber's ingest hasn't run yet
        gaps = coverage_gaps(chamber, prefix)
        coverage[chamber] = {"gaps": gaps, "status": "pass" if not gaps else "fail"}
        all_gaps.extend((chamber, g) for g in gaps)

    members_dir = repo_root() / "data" / "members"
    members = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(members_dir.glob("*.json"))
    ]
    statements = statement_balance(members, _load_statements())
    grading = grading_coverage(members)
    report = {"vote_coverage": coverage, "statement_balance": statements,
              "grading_coverage": grading}
    report_path = repo_root() / "data" / "quality" / "symmetry-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )

    failed = False
    if all_gaps:
        failed = True
        print(f"SYMMETRY FAILED — {len(all_gaps)} vote-coverage gap(s):")
        for chamber, g in all_gaps[:20]:
            print(f"  [{chamber}] {g}")
    if statements["status"] == "fail":
        failed = True
        print(f"SYMMETRY FAILED — {len(statements['findings'])} statement-balance finding(s):")
        for f in statements["findings"][:20]:
            print(f"  {f}")
    if grading["status"] == "fail":
        failed = True
        print(f"SYMMETRY FAILED — {len(grading['findings'])} grading-coverage finding(s):")
        for f in grading["findings"][:20]:
            print(f"  {f}")
    if failed:
        return 1

    covered_chambers = ", ".join(coverage)
    print(f"symmetry: OK (vote coverage complete: {covered_chambers}; "
          f"statement balance {statements['status']}; grading coverage {grading['status']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
