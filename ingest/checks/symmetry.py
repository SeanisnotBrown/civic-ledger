"""§6.5 — Symmetry checks (CI, blocking). INC-3 activates the **vote-coverage**
rule; the statement/specificity/challenge rules light up in later increments.

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


def house_coverage_gaps() -> list[str]:
    votes_dir = repo_root() / "data" / "votes"
    covered = _covered("house")
    gaps: list[str] = []
    for path in sorted(votes_dir.glob("h-*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        rc = rec["rollcall"]
        # Speaker elections carry no yea/nay positions → not coverage-eligible.
        if rc["vote_class_rule"] == "non_position":
            continue
        expected = covered.get(rc["congress"], set())
        got = {mv["member_id"] for mv in rec["member_votes"]}
        missing = expected - got
        if missing:
            gaps.append(f"{rc['id']}: missing {sorted(missing)}")
    return gaps


def main() -> int:
    votes_dir = repo_root() / "data" / "votes"
    if not any(votes_dir.glob("h-*.json")):
        print("symmetry: no roll-call data yet — vote-coverage rule inactive (no-op).")
        return 0

    gaps = house_coverage_gaps()
    report = {
        "vote_coverage": {
            "house": {"gaps": gaps, "status": "pass" if not gaps else "fail"},
        }
    }
    report_path = repo_root() / "data" / "quality" / "symmetry-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )

    if gaps:
        print(f"SYMMETRY FAILED — {len(gaps)} House vote-coverage gap(s):")
        for g in gaps[:20]:
            print(f"  {g}")
        return 1
    print("symmetry: OK (House vote coverage complete for all covered members).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
