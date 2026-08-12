"""§6.5 — Symmetry checks (CI, blocking). INC-3 activates the **vote-coverage**
rule (House); INC-4 generalizes it to the Senate. INC-10 activates the **statement
balance** rules (they stay vacuously green until statements are curated in INC-11).

Vote coverage (§6.5): every covered member has a `MemberVote` (or `Absence`) for
every eligible roll call of their chamber/congress. Any gap = fail. This reads the
*exported* dataset (data/votes/ + data/members/), so it guards the published data,
not just the ingest run.

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

from ingest.cache import repo_root


def _covered(chamber: str) -> dict[int, set[str]]:
    """{congress: covered bioguides of `chamber` serving that congress}."""
    from ingest import config
    from ingest.sources.legislators import _term_overlaps

    members_dir = repo_root() / "data" / "members"
    per_congress: dict[int, set[str]] = {c: set() for c in config.CONGRESSES}
    for path in sorted(members_dir.glob("*.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        if m["chamber"] != chamber:
            continue
        for c in config.CONGRESSES:
            if any(_term_overlaps(t, c) for t in m["terms"] if t["chamber"] == chamber):
                per_congress[c].add(m["id"])
    return per_congress


def coverage_gaps(chamber: str, prefix: str) -> list[str]:
    """Vote-coverage gaps for one chamber: every covered member of `chamber`
    serving a covered Congress must have a `MemberVote` for every eligible roll
    (files `data/votes/{prefix}-*.json`). Non-position rolls (Speaker elections)
    carry no yea/nay positions and are skipped."""
    votes_dir = repo_root() / "data" / "votes"
    covered = _covered(chamber)
    gaps: list[str] = []
    for path in sorted(votes_dir.glob(f"{prefix}-*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        rc = rec["rollcall"]
        if rc["vote_class_rule"] == "non_position":
            continue
        expected = covered.get(rc["congress"], set())
        got = {mv["member_id"] for mv in rec["member_votes"]}
        missing = expected - got
        if missing:
            gaps.append(f"{rc['id']}: missing {sorted(missing)}")
        # An EXTRA member (voted, but not in the covered set) is churn drift: an
        # official on the vote record with no page/metrics. Flag it too — expected−got
        # alone never catches it (R-2/H-1).
        extra = got - expected
        if extra:
            gaps.append(f"{rc['id']}: unknown member {sorted(extra)}")
    return gaps


# Chambers activate as their ingest lands: House at INC-3, Senate at INC-4.
_CHAMBERS: tuple[tuple[str, str], ...] = (("house", "h"), ("senate", "s"))


def _load_statements() -> list[dict]:
    """Every curated Statement record (data/statements/*.json). Empty until INC-11."""
    sdir = repo_root() / "data" / "statements"
    if not sdir.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(sdir.glob("*.json"))]


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
    report = {"vote_coverage": coverage, "statement_balance": statements}
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
    if failed:
        return 1

    covered_chambers = ", ".join(coverage)
    print(f"symmetry: OK (vote coverage complete: {covered_chambers}; "
          f"statement balance {statements['status']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
