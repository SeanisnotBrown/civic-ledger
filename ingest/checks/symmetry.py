"""§6.5 — Symmetry checks (CI, blocking). INC-3 activates the **vote-coverage**
rule (House); INC-4 generalizes it to the Senate. The statement/specificity/
challenge rules light up in later increments.

Vote coverage (§6.5): every covered member has a `MemberVote` (or `Absence`) for
every eligible roll call of their chamber/congress. Any gap = fail. This reads the
*exported* dataset (data/votes/ + data/members/), so it guards the published data,
not just the ingest run. Output: data/quality/symmetry-report.json (published).
"""

from __future__ import annotations

import json

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
    return gaps


# Chambers activate as their ingest lands: House at INC-3, Senate at INC-4.
_CHAMBERS: tuple[tuple[str, str], ...] = (("house", "h"), ("senate", "s"))


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

    report = {"vote_coverage": coverage}
    report_path = repo_root() / "data" / "quality" / "symmetry-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )

    if all_gaps:
        print(f"SYMMETRY FAILED — {len(all_gaps)} vote-coverage gap(s):")
        for chamber, g in all_gaps[:20]:
            print(f"  [{chamber}] {g}")
        return 1
    covered_chambers = ", ".join(coverage)
    print(f"symmetry: OK (vote coverage complete for all covered members: {covered_chambers}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
