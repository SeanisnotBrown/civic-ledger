"""V2-5 — the introduced-bill universe stat behind the dashboard headline.

The landing headline ("97% of bills introduced never got a floor vote") is a plain
factual count, not an evaluative grade: no cutoff, no ranking, no member singled out
(§0.8 — like the D81 metric swap, it needs no ratified threshold). It is derived
entirely from committed data, so it is recomputable offline and gated by
`verify_recompute` (invariant 7) exactly like every other published number.

Universe = every distinct bill SPONSORED by one of the covered members (the union of
`data/legislation/{member}.json` `sponsored` lists — one primary sponsor per bill, so
this is "bills our members introduced"). A bill "got a floor vote" iff its id appears
as a `RollCall.bill_id` in `data/votes` — i.e. a *recorded roll-call* vote. That is
the honest, precise claim: a bill can still reach the floor by voice vote or unanimous
consent with no roll call, which is why `became_law_without_rollcall` is published
alongside (232 of the 375 enacted bills took that path) — the methodology discloses it
so "never got a floor vote" is never read as "never got any consideration".

`compute` is pure (a data dir in, a counts dict out); `export` writes the result into
the manifest's `counts.legislation` block and `verify_recompute` re-derives it.
"""

from __future__ import annotations

import json
from pathlib import Path


def compute(data_dir: Path) -> dict[str, int]:
    """Deterministic legislation-universe counts over the committed dataset (no
    wall-clock, order-independent). Returns the five integers the manifest publishes.

    An empty/absent legislation or votes dir yields all-zero counts (pre-V2-1 no-op)."""
    legislation_dir = data_dir / "legislation"
    votes_dir = data_dir / "votes"

    voted: set[str] = set()
    if votes_dir.exists():
        for path in sorted(votes_dir.glob("*.json")):
            bill_id = json.loads(path.read_text(encoding="utf-8"))["rollcall"]["bill_id"]
            if bill_id:
                voted.add(bill_id)

    # bill_id -> became_law (one primary sponsor per bill, so distinct-by-id dedups
    # cleanly; the value is a fact of the bill, identical wherever it appears).
    sponsored: dict[str, bool] = {}
    if legislation_dir.exists():
        for path in sorted(legislation_dir.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            for bill in record.get("sponsored", []):
                sponsored[bill["bill_id"]] = bool(bill.get("became_law"))

    total = len(sponsored)
    with_rollcall = sum(1 for bid in sponsored if bid in voted)
    became_law = [bid for bid, law in sponsored.items() if law]
    became_law_no_rollcall = sum(1 for bid in became_law if bid not in voted)

    return {
        "sponsored_bills": total,
        "sponsored_with_rollcall": with_rollcall,
        "sponsored_without_rollcall": total - with_rollcall,
        "sponsored_became_law": len(became_law),
        "became_law_without_rollcall": became_law_no_rollcall,
    }
