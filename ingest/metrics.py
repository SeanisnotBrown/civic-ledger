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

import hashlib
import inspect
import json
import subprocess
from dataclasses import dataclass, field

from ingest import statements_io
from ingest.cache import repo_root
from ingest.models import MetricMethodology, MetricsFile

# Formula-generation stamp (R-3/D45). Bump this integer by hand on any SEMANTIC
# change to how a metric is computed — including changes to the shared `_`-helpers
# the per-metric `digest` does not cover. It is the coarse, human-meaningful guard
# that says "numbers before and after this bump are not formula-comparable."
# v2 (R-1b/R-4a, D47): dead-archive statements are now excluded from the metric input
# universe (a shared-helper change the per-metric digest cannot see), and attendance
# reports a null pct on a zero denominator instead of a fabricated 0.
FORMULA_SCHEMA_VERSION: int = 2

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
    orphan_votes: dict[str, str] = {}  # member_id -> first rollcall it appears in (R-2)
    for p in sorted((data / "votes").glob("*.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        rc = rec["rollcall"]
        if rc["bill_id"]:
            voted_bill_ids.add(rc["bill_id"])
        for mv in rec["member_votes"]:
            if mv["member_id"] in positions:
                positions[mv["member_id"]].append((rc, mv["position"]))
            else:
                orphan_votes.setdefault(mv["member_id"], rc["id"])
    # A recorded position with no Member record = a covered official whose votes are
    # on file but who was never rostered (delegation churn). Silently dropping it
    # would publish a member with votes but no metrics — the asymmetric-coverage shape
    # value #2 forbids. Fail instead, mirroring the missing-legislation guard below.
    if orphan_votes:
        detail = ", ".join(f"{m} (e.g. {r})" for m, r in sorted(orphan_votes.items()))
        raise FileNotFoundError(
            f"vote positions for non-member(s) {detail} — run `ingest members` to "
            f"refresh the roster, then re-ingest votes"
        )

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
    # The single statement loader (R-1b/M-3). exclude_dead=True: a statement whose
    # archive died is unpublishable — the site hides it, so the metric layer must not
    # publish a mismatch from it either. `data` honors the monkeypatched repo_root.
    statements = statements_io.load_statements(data_dir=data, exclude_dead=True)
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
    """A factual list — never a score, adjacency language only — of cases where a
    member made a SPECIFIC public statement about a named measure and their own
    recorded passage vote on that measure took the opposite side.

    A statement qualifies only when the owner has curated it to specificity level 2
    or 3, assigned a stance (support or oppose), AND named a measure that resolves to
    a bill id (the D9 pairing rule; see paired_bill_ids). support means the member's
    expected passage vote is Yea, oppose means Nay. For every passage-class roll the
    member cast Yea or Nay on that bill, an entry is emitted when the recorded
    position is the OPPOSITE of the stated one.

    Deliberately excluded (never guessed at): statements with no owner-assigned stance
    (stated_position is null), measures that do not resolve to a bill id, and every
    non-passage vote class (a Nay on a procedural motion is not a vote against the
    bill). Each entry carries the statement, the roll call, and both dates so a reader
    can check the record directly; NO sequence or motive is claimed — the statement
    and the vote are simply placed adjacent. The site draws no conclusion. A statement
    whose archived source no longer resolves is unpublishable and is excluded here too,
    so this list never cites a statement the site itself withholds. This is empty until
    qualifying statements are curated (content = H8). Source: data/statements (stance +
    pairing) + data/votes (passage positions)."""
    member_votes = ctx.positions[mid]
    out: list[dict] = []
    for s in ctx.statements:
        if s.get("member_id") != mid:
            continue
        if s.get("specificity_level") not in (2, 3):
            continue
        stance = s.get("stated_position")
        if stance not in ("support", "oppose"):
            continue  # no owner-assigned stance → not comparable (excluded, not guessed)
        expected = "yea" if stance == "support" else "nay"
        paired = set(s.get("paired_bill_ids") or ())
        for rc, pos in member_votes:
            if rc["vote_class"] != "passage" or rc["bill_id"] not in paired:
                continue
            if pos in ("yea", "nay") and pos != expected:
                out.append({
                    "statement_id": s["id"],
                    "bill_id": rc["bill_id"],
                    "rollcall_id": rc["id"],
                    "statement_source_url": s["source_url"],
                    "statement_date": s["date"][:10],
                    "vote_date": rc["date"][:10],
                    "stated_position": stance,
                    "recorded_position": pos,
                })
    out.sort(key=lambda m: (m["statement_id"], m["rollcall_id"]))
    return out


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


def _formula_digest(fn) -> str:
    """Formula identity for one metric: sha256 of the function's source, truncated.

    Newlines are normalized to LF FIRST so the digest is identical on a Windows dev
    checkout (autocrlf → CRLF on disk) and on CI (Ubuntu, LF) — otherwise the digest,
    and therefore metrics.json, would differ per platform and break the D40
    `build() == committed` determinism contract. Covers this function's body only,
    not shared `_`-helpers (see FORMULA_SCHEMA_VERSION)."""
    src = inspect.getsource(fn).replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(src.encode("utf-8")).hexdigest()[:16]


def build() -> MetricsFile:
    """Compute every metric for every covered member from the committed dataset."""
    ctx = _load()
    members = {
        mid: {key: fn(mid, ctx) for key, fn in METRICS.items()}
        for mid in sorted(ctx.members)
    }
    methodology = {
        key: MetricMethodology(
            label=METRIC_LABELS[key],
            text=inspect.cleandoc(fn.__doc__ or ""),
            digest=_formula_digest(fn),
        )
        for key, fn in METRICS.items()
    }
    return MetricsFile(
        schema_version=FORMULA_SCHEMA_VERSION, methodology=methodology, members=members
    )


# --- Time-series extraction (R-3/D45) -------------------------------------
# git IS the series store: every nightly commit of data/metrics.json is a dated
# snapshot. This reads that series out for one member — a REPORTING tool, NOT part
# of the build/export path, so it is exempt from the no-network/no-wall-clock rules
# that bind build(); it only reads git and never writes the published dataset. It
# emits the RECORDED values verbatim (with each snapshot's schema_version + digests)
# and computes no composite, ranking, or score — the consumer decides what to trend.


def _git_commits_for(relpath: str) -> list[str]:
    """Commit shas that touched `relpath`, oldest→newest (empty if never tracked)."""
    out = subprocess.run(
        ["git", "log", "--follow", "--format=%H", "--", relpath],
        cwd=repo_root(), capture_output=True, text=True, check=True,
    )
    return list(reversed(out.stdout.split()))


def _git_show(sha: str, relpath: str) -> str | None:
    """Blob of `relpath` at `sha`, or None if it did not exist there."""
    out = subprocess.run(
        ["git", "show", f"{sha}:{relpath}"],
        cwd=repo_root(), capture_output=True, text=True, check=False,
    )
    return out.stdout if out.returncode == 0 else None


def history(member_id: str, metric: str | None = None) -> list[dict]:
    """Extract the `(commit, generated_at, schema_version, metrics)` series for one
    member across every committed snapshot of data/metrics.json, oldest→newest. A
    commit where the member is absent (or the file predates them) is skipped. Old
    snapshots predating R-3 simply carry `schema_version: null` and no per-metric
    digests — parsing stays lenient so the tool works across the schema change.
    `metric` narrows the emitted values to a single metric key."""
    series: list[dict] = []
    for sha in _git_commits_for("data/metrics.json"):
        blob = _git_show(sha, "data/metrics.json")
        if blob is None:
            continue
        try:
            snapshot = json.loads(blob)
        except json.JSONDecodeError:
            continue
        member = snapshot.get("members", {}).get(member_id)
        if member is None:
            continue  # member not covered in this snapshot
        if metric is not None:
            if metric not in member:
                continue
            values = {metric: member[metric]}
        else:
            values = member
        manifest = _git_show(sha, "data/manifest.json")
        generated_at = None
        if manifest is not None:
            try:
                generated_at = json.loads(manifest).get("generated_at")
            except json.JSONDecodeError:
                pass
        series.append({
            "commit": sha,
            "generated_at": generated_at,
            "schema_version": snapshot.get("schema_version"),
            "metrics": values,
        })
    return series


def run(argv: list[str] | None = None) -> int:
    args = argv or []
    if args and args[0] == "history":
        rest = args[1:]
        metric: str | None = None
        if "--metric" in rest:
            i = rest.index("--metric")
            metric = rest[i + 1] if i + 1 < len(rest) else None
            rest = rest[:i] + rest[i + 2:]
        if not rest:
            print("usage: ingest metrics history <bioguide> [--metric <key>]")
            return 2
        member_id = rest[0]
        if metric is not None and metric not in METRICS:
            print(f"unknown metric '{metric}'; keys: {', '.join(sorted(METRICS))}")
            return 2
        series = history(member_id, metric)
        print(json.dumps(series, indent=2, ensure_ascii=False))
        return 0

    from ingest.export import export_metrics

    path = export_metrics(build())
    print(f"civic-ledger metrics: wrote {path.name} "
          f"({len(METRICS)} metrics × committed members).")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
