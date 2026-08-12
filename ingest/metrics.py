"""INC-10 — Tier-2 metrics (§5). Each metric function's DOCSTRING is the
methodology text: it is extracted verbatim into data/metrics.json and rendered as
that metric's section on the methods page, so the formula, inclusions/exclusions,
and source always match the code that computes the number.

Discipline:
  * PURE + OFFLINE — every function reads only the committed dataset passed in via
    `Ctx` (never the API), so a third party recomputes every figure from the public
    repo (the verify-recompute contract).
  * TIER-2 ONLY — each metric is an independent factual formula. No function
    consumes another metric's output; the Tier-3 guard (checks/integrity.py) parses
    the `METRICS` registry below and fails if one metric function calls another.
    Shared read-only helpers (the `_`-prefixed functions) are not metrics.

Nothing here characterizes, ranks, or scores a member. The site draws no
conclusions; it publishes the recorded facts and how each was computed.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field

from ingest.cache import repo_root
from ingest.models import MetricMethodology, MetricsFile

# Substantive vote classes for party unity (§A1; excludes `procedural` — the
# R-RULE/R-RES split in INC-5 exists precisely so special rules don't count here).
SUBSTANTIVE: frozenset[str] = frozenset({"passage", "amendment", "veto_override", "nomination"})

# Human labels for the methods-page section headings (keys == METRICS keys).
METRIC_LABELS: dict[str, str] = {
    "attendance": "Attendance",
    "party_unity": "Party unity",
    "sponsored": "Bills sponsored",
    "cosponsored": "Bills cosponsored",
    "enacted_rate": "Enacted rate",
    "cosponsor_vote_gap": "Cosponsor-to-vote gap",
    "named_measure_mismatch": "Named-measure mismatch",
    "absence_context": "Missed-vote context",
}


# --- loaded dataset (read once, passed to every metric) -------------------


@dataclass
class Ctx:
    members: dict[str, dict]                        # id -> Member record
    positions: dict[str, list[tuple[dict, str]]]    # id -> [(rollcall, position), …]
    legislation: dict[str, dict]                    # id -> MemberLegislation record
    statements: list[dict]                          # curated Statements (empty pre-INC-11)
    voted_bill_ids: set[str]                        # every bill_id that got a floor roll
    ended_congresses: frozenset[int] = field(default_factory=frozenset)


def _load() -> Ctx:
    data = repo_root() / "data"
    members = {
        (m := json.loads(p.read_text(encoding="utf-8")))["id"]: m
        for p in sorted((data / "members").glob("*.json"))
    }
    positions: dict[str, list[tuple[dict, str]]] = {mid: [] for mid in members}
    voted_bill_ids: set[str] = set()
    for p in sorted((data / "votes").glob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        rc = rec["rollcall"]
        if rc["bill_id"]:
            voted_bill_ids.add(rc["bill_id"])
        for mv in rec["member_votes"]:
            if mv["member_id"] in positions:
                positions[mv["member_id"]].append((rc, mv["position"]))

    legislation = {
        (r := json.loads(p.read_text(encoding="utf-8")))["member_id"]: r
        for p in sorted((data / "legislation").glob("*.json"))
    }
    # Every covered member MUST have a legislation record. A missing file (bad
    # checkout, partial ingest) would otherwise publish `sponsored: 0` — the exact
    # false-zero claim D27 forbids. Fail the build instead of inventing a zero.
    missing = set(members) - set(legislation)
    if missing:
        raise FileNotFoundError(
            f"no data/legislation record for {sorted(missing)} — run `ingest legislation`"
        )
    sdir = data / "statements"
    statements = (
        [json.loads(p.read_text(encoding="utf-8")) for p in sorted(sdir.glob("*.json"))]
        if sdir.exists() else []
    )
    from ingest import config
    # The ongoing Congress is the newest covered one; every older covered Congress
    # has ended. Static + deterministic (no wall-clock), auto-correct when the next
    # Congress is added to config.CONGRESSES.
    ended = frozenset(c for c in config.CONGRESSES if c != max(config.CONGRESSES))
    return Ctx(members, positions, legislation, statements, voted_bill_ids, ended)


def _party_on(member: dict, date: str) -> str:
    """The member's party for the term overlapping `date` (roll dates may carry a
    time; the calendar day is compared). Falls back to current party if no term
    brackets the date (should not happen for a covered roll)."""
    day = date[:10]
    for t in member["terms"]:
        if t["start"][:10] <= day <= t["end"][:10]:
            return t["party"]
    return member["party"]


# --- metrics (each docstring is the published methodology) ----------------


def attendance(mid: str, ctx: Ctx) -> dict:
    """Share of eligible roll calls on which the member recorded any position.

    Formula: cast / eligible, as a percentage. `eligible` = every roll call the
    member was present-and-covered for (their chamber and Congress), excluding
    Speaker-election / candidate-surname rolls, which carry no yea/nay position.
    `cast` = votes of Yea, Nay, or Present. `missed` = Not Voting. A member has
    exactly one recorded position per eligible roll (coverage is verified), so the
    denominator is unambiguous. Source: the roll-call record (data/votes)."""
    rows = ctx.positions[mid]
    eligible = len(rows)
    missed = sum(1 for _, pos in rows if pos == "not_voting")
    cast = eligible - missed
    return {
        "eligible": eligible, "cast": cast, "missed": missed,
        "pct": round(100 * cast / eligible, 2) if eligible else 0.0,
    }


def party_unity(mid: str, ctx: Ctx) -> dict:
    """Share of substantive votes on which the member voted with the majority of
    their own party.

    Substantive votes are the classes passage, amendment, veto_override, and
    nomination — procedural votes are excluded (a party's floor-management votes
    are not policy agreement). For each such roll the member cast Yea or Nay on
    (Present and Not Voting are excluded — attendance owns those), the member's
    party's majority is the larger of that party's Yea vs Nay among the members who
    cast a position (from the aggregate party_totals). A member is counted as
    agreeing when their Yea/Nay matches that majority side. Rolls where the
    member's party split evenly are excluded (no majority) and reported as
    `excluded_ties`. The member's party is the one they held on the roll's date.
    pct is null when the member has no substantive votes. Source: data/votes
    (positions + aggregate party_totals). We do not collect individual non-Mississippi
    members' positions; only the per-party aggregate makes this recomputable."""
    substantive = agreed = ties = 0
    member = ctx.members[mid]
    for rc, pos in ctx.positions[mid]:
        if rc["vote_class"] not in SUBSTANTIVE or pos not in ("yea", "nay"):
            continue
        pt = rc.get("party_totals") or {}
        party = _party_on(member, rc["date"])
        if party not in pt:
            continue
        y, n = pt[party]["yea"], pt[party]["nay"]
        if y == n:
            ties += 1
            continue
        substantive += 1
        if pos == ("yea" if y > n else "nay"):
            agreed += 1
    return {
        "substantive": substantive, "agreed": agreed,
        "pct": round(100 * agreed / substantive, 2) if substantive else None,
        "excluded_ties": ties,
    }


def sponsored(mid: str, ctx: Ctx) -> dict:
    """Count of bills and resolutions the member sponsored (was the primary
    sponsor of) in the covered Congresses. Floor amendments are not counted (they
    are not bills). Source: the member's sponsored-legislation record
    (data/legislation)."""
    return {"count": len(ctx.legislation[mid]["sponsored"])}


def cosponsored(mid: str, ctx: Ctx) -> dict:
    """Count of bills and resolutions the member cosponsored (added their name to,
    and had not withdrawn) in the covered Congresses. Floor amendments are not
    counted. Source: the member's cosponsored-legislation record (data/legislation)."""
    return {"count": len(ctx.legislation[mid]["cosponsored"])}


def enacted_rate(mid: str, ctx: Ctx) -> dict:
    """Of the bills the member sponsored in the covered Congresses, the share that
    became law UNDER THEIR OWN BILL NUMBER (official latest action "Became Public
    Law"). This understates a member's legislative influence: much enacted text
    moves by being folded into another vehicle (an omnibus, an appropriations act,
    the NDAA), which this figure cannot and does not attribute. pct is null when
    the member sponsored nothing. Source: data/legislation."""
    spon = ctx.legislation[mid]["sponsored"]
    enacted = sum(1 for li in spon if li["became_law"])
    return {
        "sponsored": len(spon), "enacted": enacted,
        "pct": round(100 * enacted / len(spon), 2) if spon else None,
    }


def cosponsor_vote_gap(mid: str, ctx: Ctx) -> list[dict]:
    """A factual list — never a score — of two adjacencies between a member's
    cosponsorships and their floor record, each linking to the underlying record:

      * cosponsored_and_voted_nay — the member was a cosponsor of a bill and voted
        Nay on its passage. (The data establishes cosponsorship and a Nay passage
        vote; it does not establish which came first, so no sequence is claimed.)
      * cosponsored_no_floor_action — the member cosponsored a bill in a Congress
        that HAS ENDED, and that bill never received any recorded floor vote. Bills
        from the ongoing Congress are never listed (a bill cosponsored in the first
        session routinely gets its vote in the second, so listing mid-Congress would
        be a false "went nowhere").

    Read this list with its base rate: MOST introduced bills never receive a floor
    vote in any Congress, and floor scheduling is controlled by chamber leadership,
    not by a bill's cosponsors. This list is therefore expected to contain most of
    any member's cosponsorships; it is provided for inspection, not as an indicator
    about the member, and must always be shown against its denominator (of N bills
    cosponsored), never as a bare count or a headline. The site draws no conclusion.
    Source: data/legislation (cosponsorships) + data/votes (rolls)."""
    cospon = ctx.legislation[mid]["cosponsored"]
    cospon_ids = {li["bill_id"] for li in cospon}
    gaps: list[dict] = []
    for rc, pos in ctx.positions[mid]:
        if pos == "nay" and rc["vote_class"] == "passage" and rc["bill_id"] in cospon_ids:
            gaps.append({
                "bill_id": rc["bill_id"], "kind": "cosponsored_and_voted_nay",
                "rollcall_id": rc["id"],
            })
    for li in cospon:
        if li["congress"] in ctx.ended_congresses and li["bill_id"] not in ctx.voted_bill_ids:
            gaps.append({
                "bill_id": li["bill_id"], "kind": "cosponsored_no_floor_action",
                "rollcall_id": None,
            })
    gaps.sort(key=lambda g: (g["kind"], g["bill_id"]))
    return gaps


def named_measure_mismatch(mid: str, ctx: Ctx) -> list[dict]:
    """A list — never a score, adjacency language only — intended to surface cases
    where a member made a SPECIFIC public statement naming a measure (a curated
    Statement with named_measures and a specificity level of 2–3) and their recorded
    passage vote on that measure took the OPPOSITE position.

    That opposite-position test needs the statement's STANCE, which is deliberately
    not stored today (a Statement is verbatim text with no paraphrase or position
    field). Curation attaches the stance in INC-11; until then no qualifying
    statement exists and this is empty BY CONSTRUCTION. It fails closed: if a
    qualifying statement is ever curated before the stance comparison is built, this
    raises rather than publish an unverified mismatch (value #1). Source:
    data/statements + data/votes."""
    qualifying = [
        s for s in ctx.statements
        if s.get("member_id") == mid
        and s.get("specificity_level") in (2, 3)
        and s.get("named_measures")
    ]
    if qualifying:
        raise NotImplementedError(
            f"{mid}: named_measure_mismatch requires a curated statement stance "
            "(INC-11) — implement the opposite-position comparison before curating "
            "qualifying statements; refusing to publish an unverified mismatch."
        )
    return []


def absence_context(mid: str, ctx: Ctx) -> list[dict]:
    """For each roll the member missed (Not Voting), the member's own participation
    on the same calendar day: how many recorded position rolls occurred in their
    chamber that day (`same_day_total`) and how many of those the member cast
    (`same_day_cast`). This reports the VOTE RECORD ONLY — it does not infer whether
    the member was physically present or absent; a member may miss a roll while in
    the building, and the site never claims otherwise. Source: data/votes."""
    by_day: dict[str, list[str]] = {}
    for rc, pos in ctx.positions[mid]:
        by_day.setdefault(rc["date"][:10], []).append(pos)
    out: list[dict] = []
    for rc, pos in ctx.positions[mid]:
        if pos != "not_voting":
            continue
        day_positions = by_day[rc["date"][:10]]
        out.append({
            "rollcall_id": rc["id"], "date": rc["date"][:10],
            "same_day_total": len(day_positions),
            "same_day_cast": sum(1 for p in day_positions if p != "not_voting"),
        })
    out.sort(key=lambda a: a["rollcall_id"])
    return out


# The Tier-3 guard reads this registry: no listed function may call another.
METRICS = {
    "attendance": attendance,
    "party_unity": party_unity,
    "sponsored": sponsored,
    "cosponsored": cosponsored,
    "enacted_rate": enacted_rate,
    "cosponsor_vote_gap": cosponsor_vote_gap,
    "named_measure_mismatch": named_measure_mismatch,
    "absence_context": absence_context,
}


def build() -> MetricsFile:
    """Compute every metric for every covered member from the committed dataset."""
    ctx = _load()
    members = {
        mid: {key: fn(mid, ctx) for key, fn in METRICS.items()}
        for mid in sorted(ctx.members)
    }
    methodology = {
        key: MetricMethodology(label=METRIC_LABELS[key], text=inspect.cleandoc(fn.__doc__ or ""))
        for key, fn in METRICS.items()
    }
    return MetricsFile(methodology=methodology, members=members)


def run(argv: list[str] | None = None) -> int:
    from ingest.export import export_metrics

    path = export_metrics(build())
    print(f"civic-ledger metrics: wrote {path.name} "
          f"({len(METRICS)} metrics × committed members).")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
