"""The Phase 3 pilot draw — owner decision 10, ratified 2026-10-09 (§5 Phase 3).

Which 40 members the first statement collection covers. Equal by party so task 4's
fairness measurement has an equal-n base on both sides, proportional by chamber so the
§6 symmetry baseline established on this 40 stays comparable when collection widens to
everyone:

    20 Democrats  — 16 House, 4 Senate
    20 Republicans — 16 House, 4 Senate

**No member is ever hand-picked.** The draw is random within each cell from a
deterministically sorted candidate list, and the committed sample records the seed AND
the roster snapshot's `fetched_at`. Both are needed: `legislators-current.yaml` is a live
file that changes whenever someone leaves office, so the seed alone does not make the
draw reproducible — re-running it next month against a 537-member roster would produce a
different 40 from the same seed.

Eligibility, and why each exclusion exists:

  * `serving` is TRUE **and** the member is in the live `legislators-current.yaml`.
    `serving` alone is not enough: it means "the latest term overlapped the latest covered
    Congress", which stays true for someone who resigned or died mid-term (it is
    deliberately wall-clock-free for §6.3 determinism). Measured 2026-10-09: 555 records
    carried `serving=true` against a 539-member roster, and the 16-member gap was exactly
    the mid-119th departures. Roster membership is the only signal that separates "served
    during the 119th" from "in office now".
  * **Delegates and the Puerto Rico resident commissioner are excluded** (6 House seats,
    detected with the existing `VOTING_STATES` set — no new roster logic). They are
    constitutionally barred from final-passage roll calls, so they have no full say-vs-do
    record for a statement to be compared against, which is the pilot's whole purpose.
    They stay fully covered everywhere else: D61 keeps them in the roster and in vote
    recomputation.
  * **Independents are not in the pilot draw** — a known gap recorded in `STATUS.md`, to
    be covered when collection widens past the 40.

Nothing here is evaluative. The draw decides WHOSE statements get collected first; what
any statement means is Q-J (ratified, §2) and Q-K (open, task 4).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ingest.cache import repo_root
from ingest.sources.legislators import VOTING_STATES

# Committed with the sample. A readable date-shaped integer rather than an opaque one, so
# a reader can see it was chosen once and not tuned until the draw looked agreeable.
SEED: int = 20261009

# Owner decision 10. 16:4 mirrors the real House:Senate ratio (435:100).
CELLS: dict[tuple[str, str], int] = {
    ("D", "house"): 16,
    ("D", "senate"): 4,
    ("R", "house"): 16,
    ("R", "senate"): 4,
}

PARTIES: tuple[str, ...] = ("D", "R")
CHAMBERS: tuple[str, ...] = ("house", "senate")

SAMPLE_PATH = ("config", "statement-pilot.yaml")


class PilotError(RuntimeError):
    """The draw cannot be made as decision 10 specifies."""


@dataclass(frozen=True)
class Candidate:
    """The fields the draw and the committed sample need. Nothing else."""

    id: str
    name: str
    party: str
    chamber: str
    state: str


def eligible(members: list[dict], current_ids: set[str]) -> list[Candidate]:
    """Apply decision 10's eligibility rules to the committed roster."""
    out: list[Candidate] = []
    for m in members:
        if m.get("jurisdiction") != "us":
            continue
        if not m.get("serving"):
            continue
        if m.get("id") not in current_ids:  # left office mid-term
            continue
        if m.get("state") not in VOTING_STATES:  # delegate / resident commissioner
            continue
        if m.get("party") not in PARTIES:  # independents, by decision
            continue
        if m.get("chamber") not in CHAMBERS:
            continue
        out.append(
            Candidate(
                id=m["id"],
                name=m.get("name", ""),
                party=m["party"],
                chamber=m["chamber"],
                state=m["state"],
            )
        )
    return sorted(out, key=lambda c: c.id)


def pools(candidates: list[Candidate]) -> dict[tuple[str, str], list[Candidate]]:
    """Candidates split into decision 10's four cells, each id-sorted."""
    out: dict[tuple[str, str], list[Candidate]] = {cell: [] for cell in CELLS}
    for c in candidates:
        cell = (c.party, c.chamber)
        if cell in out:
            out[cell].append(c)
    return out


def draw(
    candidates: list[Candidate], *, seed: int = SEED
) -> dict[tuple[str, str], list[Candidate]]:
    """Draw each cell at random from its id-sorted pool, with one seeded RNG.

    Cells are drawn in a fixed order from one `Random`, so the whole 40 is a function of
    (seed, roster) and nothing else. A short cell raises rather than quietly returning a
    smaller sample: a 15-member cell would silently break the equal-n property the whole
    decision exists for.
    """
    by_cell = pools(candidates)
    rng = random.Random(seed)
    picked: dict[tuple[str, str], list[Candidate]] = {}
    for cell in CELLS:  # insertion order, fixed in this module
        want = CELLS[cell]
        pool = by_cell[cell]
        if len(pool) < want:
            raise PilotError(
                f"cell {cell[0]}/{cell[1]} has {len(pool)} eligible member(s), "
                f"decision 10 needs {want}"
            )
        picked[cell] = sorted(rng.sample(pool, want), key=lambda c: c.id)
    return picked


def render(
    picked: dict[tuple[str, str], list[Candidate]],
    all_pools: dict[tuple[str, str], list[Candidate]],
    *,
    seed: int,
    roster_url: str,
    roster_fetched_at: str,
) -> dict[str, Any]:
    """The committed sample, as the mapping written to statement-pilot.yaml."""
    return {
        "decision": "IMPLEMENTATIONv3.md §5 Phase 3 owner decision 10",
        "ratified": "2026-10-09",
        "seed": seed,
        "roster_snapshot": {"url": roster_url, "fetched_at": roster_fetched_at},
        "excluded_by_decision": [
            "members not in the live legislators-current.yaml (left office mid-term)",
            "the 5 non-voting delegates and the PR resident commissioner",
            "independents (known gap, to be covered when collection widens)",
        ],
        "cells": [
            {
                "party": party,
                "chamber": chamber,
                "drawn": CELLS[(party, chamber)],
                "eligible_pool": len(all_pools[(party, chamber)]),
                "members": [
                    {"id": c.id, "name": c.name, "state": c.state}
                    for c in picked[(party, chamber)]
                ],
            }
            for (party, chamber) in CELLS
        ],
    }


def sample_ids(sample: dict[str, Any]) -> list[str]:
    """Every member id in a committed sample, sorted. What the collectors iterate."""
    return sorted(m["id"] for cell in sample["cells"] for m in cell["members"])


def _load_members(data_dir: Path) -> list[dict]:
    mdir = data_dir / "members"
    if not mdir.exists():
        raise PilotError(f"no committed roster at {mdir}; run `uv run ingest members` first")
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(mdir.glob("*.json"))]


def _roster_snapshot() -> tuple[set[str], str, str]:
    """The live current roster: its bioguide ids, its URL, and the snapshot's fetched_at.

    Fetched through the project cache like every other source, so the committed
    `fetched_at` is the cache's own record of when these bytes were retrieved.
    """
    from ingest.sources import legislators

    resp = legislators.current()
    meta_path = resp.path.with_suffix(".meta")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    entries = yaml.safe_load(resp.text)
    ids = {e["id"]["bioguide"] for e in entries if "bioguide" in (e.get("id") or {})}
    return ids, meta.get("url", legislators.CURRENT_URL), meta.get("fetched_at", "")


def run(argv: list[str] | None = None) -> int:
    """`uv run ingest pilot-draw [--force]`. Refuses to overwrite an existing sample
    without `--force`: the drawn 40 is a committed decision, not a derived artifact, and
    silently redrawing it would change who the site has statements for."""
    args = list(argv or [])
    force = "--force" in args
    data_dir = repo_root() / "data"
    out_path = data_dir.joinpath(*SAMPLE_PATH)

    if out_path.exists() and not force:
        print(f"pilot-draw: {out_path.relative_to(repo_root())} already exists — "
              f"re-draw with --force only if the owner asked for a new sample.")
        return 0

    members = _load_members(data_dir)
    current_ids, roster_url, fetched_at = _roster_snapshot()
    candidates = eligible(members, current_ids)
    all_pools = pools(candidates)
    picked = draw(candidates, seed=SEED)
    sample = render(
        picked, all_pools, seed=SEED, roster_url=roster_url, roster_fetched_at=fetched_at
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(sample, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )

    print(f"pilot-draw: {len(sample_ids(sample))} members -> "
          f"{out_path.relative_to(repo_root())}")
    print(f"  seed {SEED}, roster snapshot {fetched_at}")
    for cell in sample["cells"]:
        print(f"  {cell['party']}/{cell['chamber']:7s} drew {cell['drawn']:2d} "
              f"of {cell['eligible_pool']:3d} eligible")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
