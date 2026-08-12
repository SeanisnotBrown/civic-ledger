"""§6.3 / §8 — Integrity cross-check (CI, blocking on mismatch).

INC-3 role: sample House roll calls from the exported dataset, re-fetch each from
the INDEPENDENT clerk.house.gov XML (D6), and require the MS delegation's positions
to match the Congress.gov-derived positions we published — exactly. A genuine
mismatch fails CI (data corruption). A clerk *network* failure only warns: a clerk
outage must never read as corruption.

Sampling is deterministic **per dataset**: the RNG is seeded from a hash of the
sorted roll-call-id set, so the same committed data always samples the same rolls,
but the sample re-rolls as the dataset grows.
"""

from __future__ import annotations

import hashlib
import json
import random

import httpx

from ingest.cache import repo_root

SAMPLE_SIZE = 10


def _sample_ids(ids: list[str]) -> list[str]:
    seed = int(hashlib.sha256(",".join(sorted(ids)).encode()).hexdigest(), 16)
    rng = random.Random(seed)
    return sorted(rng.sample(ids, min(SAMPLE_SIZE, len(ids))))


def cross_check(sample_ids: list[str]) -> tuple[list[str], list[str]]:
    """Return (mismatches, unreachable). Compares each sampled vote's MS positions
    against the clerk XML at its source_url."""
    from ingest.sources import clerk_house

    votes_dir = repo_root() / "data" / "votes"
    mismatches: list[str] = []
    unreachable: list[str] = []
    for rc_id in sample_ids:
        rec = json.loads((votes_dir / f"{rc_id}.json").read_text(encoding="utf-8"))
        published = {mv["member_id"]: mv["position"] for mv in rec["member_votes"]}
        url = rec["rollcall"]["source_url"]
        try:
            xml = clerk_house.roll_xml_url(url).text
        except (httpx.HTTPError, OSError) as exc:
            unreachable.append(f"{rc_id}: {type(exc).__name__}")
            continue
        clerk_ms = clerk_house.parse_positions(xml, state="MS")
        for bioguide, pos in published.items():
            if clerk_ms.get(bioguide) != pos:
                mismatches.append(
                    f"{rc_id} {bioguide}: published={pos} clerk={clerk_ms.get(bioguide)}"
                )
    return mismatches, unreachable


def main() -> int:
    votes_dir = repo_root() / "data" / "votes"
    # Sample only rolls that carry MS positions (skip Speaker-election rolls, which
    # have no per-member positions to cross-check).
    ids = [
        p.stem
        for p in votes_dir.glob("h-*.json")
        if json.loads(p.read_text(encoding="utf-8"))["member_votes"]
    ]
    if not ids:
        print("integrity: no roll-call data yet — clerk cross-check inactive (no-op).")
        return 0

    sample = _sample_ids(ids)
    mismatches, unreachable = cross_check(sample)
    print(f"integrity: clerk cross-check on {len(sample)} sampled House rolls.")
    if unreachable:
        print(f"  WARN: {len(unreachable)} clerk fetch(es) unreachable (not a failure): "
              f"{unreachable}")
    if mismatches:
        print(f"INTEGRITY FAILED — {len(mismatches)} position mismatch(es):")
        for m in mismatches:
            print(f"  {m}")
        return 1
    checked = len(sample) - len(unreachable)
    print(f"integrity: OK ({checked}/{len(sample)} rolls verified against clerk XML).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
