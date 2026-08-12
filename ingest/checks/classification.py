"""§A1 / §6 — vote_class classification gate (CI, blocking).

Guards the PUBLISHED dataset (data/votes/*.json), not the classify run: every
non-`non_position` roll must carry a real `vote_class` (never the provisional
`unclassified`), and the `other` rate must stay within config.MAX_OTHER_RATE. This
is what fails CI if someone commits vote data without re-running `ingest classify`
after an ingest (D24), or if new upstream questions push `other` over the ceiling.
No-op on an empty dataset.
"""

from __future__ import annotations

import json

from ingest import config
from ingest.cache import repo_root


def main() -> int:
    votes_dir = repo_root() / "data" / "votes"
    files = sorted(votes_dir.glob("*.json"))
    if not files:
        print("classification: no roll-call data yet — gate inactive (no-op).")
        return 0

    unclassified: list[str] = []
    other = 0
    n = 0
    for path in files:
        rc = json.loads(path.read_text(encoding="utf-8"))["rollcall"]
        if rc["vote_class_rule"] == "non_position":
            continue
        n += 1
        if rc["vote_class_rule"] == "unclassified":
            unclassified.append(rc["id"])
        elif rc["vote_class"] == "other":
            other += 1

    other_rate = other / n if n else 0.0
    if unclassified:
        print(f"CLASSIFICATION FAILED — {len(unclassified)} roll(s) still provisional "
              f"(run `ingest classify`): {unclassified[:10]}")
        return 1
    if other_rate > config.MAX_OTHER_RATE:
        print(f"CLASSIFICATION FAILED — other rate {other_rate:.4%} exceeds "
              f"{config.MAX_OTHER_RATE:.0%} ceiling (extend §A1).")
        return 1
    print(f"classification: OK ({n} rolls classified, other rate {other_rate:.4%} "
          f"<= {config.MAX_OTHER_RATE:.0%}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
