"""§6.3 / §8 — Integrity cross-check (CI, blocking on mismatch).

INC-3 role: sample House roll calls from the exported dataset, re-fetch each from
the INDEPENDENT clerk.house.gov XML (D6), and require the MS delegation's positions
to match the Congress.gov-derived positions we published — exactly.

INC-4 role: sample Senate roll calls and re-fetch each detail XML from its
source_url, re-parsing the MS positions through the `lis_member_id` crosswalk. The
Senate has no separate clerk; the primary cross-SOURCE guard (detail totals vs. the
menu tally) is enforced at ingest time (senate_votes.TallyMismatch), so this pass
catches export/serialization corruption between parse and published file.

A genuine mismatch fails CI (data corruption). A *network* failure only warns: a
source outage must never read as corruption.

Sampling is deterministic **per dataset**: the RNG is seeded from a hash of the
sorted roll-call-id set, so the same committed data always samples the same rolls,
but the sample re-rolls as the dataset grows.
"""

from __future__ import annotations

import ast
import hashlib
import json
import random

import httpx

from ingest.cache import repo_root

SAMPLE_SIZE = 10


# --- Tier-3 guard: disclosure, not prohibition (§6.8, V2-4; was §5 INC-10) -
# Old rule (INC-10): NO composite anywhere — no metric may fold in another. New rule
# (SD-26/§6.8): composites and grades exist, but ONLY in ingest/scoring.py, and every
# published evaluative output traces to a ratified data/config/thresholds.yaml entry.
# Two mechanical guards, both tripwires-backed-by-review (blind spots in §CS carry
# over — a lockstep edit to code+config passes; the recompute check + review are the
# real proof):
#   (1) Tier-2 metrics stay independent: `tier3_violations` still asserts no function
#       in metrics.py's `METRICS` registry calls another registered metric. scoring.py
#       is the sole permitted composer (and at V2-4 composes nothing — one metric per
#       grade); metrics.py must remain pure factual formulas.
#   (2) Grades disclose their source: `grades_disclosure` asserts every committed
#       data/grades/{category}.json carries EXACTLY the config's bands, labels,
#       exception_label, formula_version and ratified date — so no evaluative number
#       or wording ships unratified. The render-side half is site/scripts/
#       check-grade-labels.mjs (rendered grade strings ⊆ config labels).


def _metric_names(tree: ast.Module, registry: str = "METRICS") -> set[str]:
    """Function names bound as values in the module-level `{registry}` dict literal."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == registry for t in node.targets
        ):
            if isinstance(node.value, ast.Dict):
                return {v.id for v in node.value.values if isinstance(v, ast.Name)}
    return set()


def tier3_violations(source: str, registry: str = "METRICS") -> list[str]:
    """Registered metric functions that directly call another registered metric
    function (Tier-3 aggregation). Empty = clean. Pure over source text."""
    tree = ast.parse(source)
    metrics = _metric_names(tree, registry)
    if not metrics:
        return []
    defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    violations: list[str] = []
    for name in sorted(metrics):
        fn = defs.get(name)
        if fn is None:
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                f = node.func
                callee = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
                if callee in metrics and callee != name:
                    violations.append(
                        f"{name}() calls metric {callee}() — Tier-3 aggregation forbidden (§5)"
                    )
    return violations


def grades_disclosure() -> list[str]:
    """§6.8 disclosure guard (V2-4): every published grade traces to the owner-ratified
    thresholds. Each committed data/grades/{category}.json must carry EXACTLY the
    config's bands (grade/min/label), exception_label, formula_version and ratified
    date, and every rendered member label must be one of the config's strings — so no
    evaluative number or wording can ship that the owner did not ratify. Empty = clean.
    No-op until grades exist. Tripwire, not proof (see the section comment)."""
    import yaml

    root = repo_root()
    grades_dir = root / "data" / "grades"
    files = sorted(grades_dir.glob("*.json")) if grades_dir.exists() else []
    if not files:
        return []
    config = yaml.safe_load(
        (root / "data" / "config" / "thresholds.yaml").read_text(encoding="utf-8")
    )
    violations: list[str] = []
    for path in files:
        gf = json.loads(path.read_text(encoding="utf-8"))
        cfg = (config.get("grades") or {}).get(gf.get("category"))
        if cfg is None:
            violations.append(f"{path.stem}: category not in thresholds.yaml (unratified grade)")
            continue
        want = [(b["grade"], b["min"], b["label"]) for b in cfg["bands"]]
        got = [(b["grade"], b["min"], b["label"]) for b in gf.get("bands", [])]
        if got != want:
            violations.append(f"{path.stem}: bands differ from the ratified thresholds")
        if gf.get("exception_label") != cfg.get("exception_label"):
            violations.append(f"{path.stem}: exception_label is not the ratified string")
        if gf.get("min_eligible") != cfg.get("min_eligible"):
            violations.append(f"{path.stem}: min_eligible does not match the config")
        if gf.get("formula_version") != config.get("formula_version"):
            violations.append(f"{path.stem}: formula_version does not match the config")
        if gf.get("ratified") != cfg.get("ratified"):
            violations.append(f"{path.stem}: ratified date does not match the config")
        allowed = {b["label"] for b in cfg["bands"]} | {cfg["exception_label"]}
        stray = {e["label"] for e in gf.get("members", {}).values()} - allowed
        if stray:
            violations.append(f"{path.stem}: member label(s) not in config: {sorted(stray)[:3]}")
    return violations


def metrics_tier3_guard() -> list[str]:
    """Run the Tier-3 guard over the real ingest/metrics.py (no-op if absent)."""
    src = repo_root() / "ingest" / "metrics.py"
    if not src.exists():
        return []
    return tier3_violations(src.read_text(encoding="utf-8"))


def _sample_ids(ids: list[str]) -> list[str]:
    seed = int(hashlib.sha256(",".join(sorted(ids)).encode()).hexdigest(), 16)
    rng = random.Random(seed)
    return sorted(rng.sample(ids, min(SAMPLE_SIZE, len(ids))))


def cross_check(sample_ids: list[str]) -> tuple[list[str], list[str]]:
    """Return (mismatches, unreachable). Compares each sampled vote's positions
    (V2-1: every member, not just MS's) against the clerk XML at its source_url."""
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
        # No state filter (V2-1): `published` now covers every member, so the
        # independent re-parse must too, or every non-MS bioguide compares
        # against a None clerk lookup and spuriously mismatches.
        clerk_all = clerk_house.parse_positions(xml)
        for bioguide, pos in published.items():
            if clerk_all.get(bioguide) != pos:
                mismatches.append(
                    f"{rc_id} {bioguide}: published={pos} clerk={clerk_all.get(bioguide)}"
                )
    return mismatches, unreachable


def senate_cross_check(sample_ids: list[str]) -> tuple[list[str], list[str]]:
    """Return (mismatches, unreachable). Re-fetch each sampled Senate roll's detail
    XML at its source_url and re-parse positions (V2-1: every senator, not just
    MS's) through the crosswalk, comparing to what we published."""
    from ingest.senate_votes import _lis_to_bioguide
    from ingest.sources import senate_xml

    votes_dir = repo_root() / "data" / "votes"
    lis_to_bioguide = _lis_to_bioguide()
    mismatches: list[str] = []
    unreachable: list[str] = []
    for rc_id in sample_ids:
        rec = json.loads((votes_dir / f"{rc_id}.json").read_text(encoding="utf-8"))
        published = {mv["member_id"]: mv["position"] for mv in rec["member_votes"]}
        url = rec["rollcall"]["source_url"]
        try:
            xml = senate_xml.fetch(senate_xml.SOURCE, url, ext="xml").text
        except (httpx.HTTPError, OSError) as exc:
            unreachable.append(f"{rc_id}: {type(exc).__name__}")
            continue
        # No state filter (V2-1) — see cross_check() above for why.
        reparsed = senate_xml.parse_positions(xml, lis_to_bioguide)
        for bioguide, pos in published.items():
            if reparsed.get(bioguide) != pos:
                mismatches.append(
                    f"{rc_id} {bioguide}: published={pos} detail={reparsed.get(bioguide)}"
                )
    return mismatches, unreachable


def _ids_with_positions(prefix: str) -> list[str]:
    votes_dir = repo_root() / "data" / "votes"
    return [
        p.stem
        for p in votes_dir.glob(f"{prefix}-*.json")
        if json.loads(p.read_text(encoding="utf-8"))["member_votes"]
    ]


def main() -> int:
    failed = False

    # Tier-3 guard runs with or without vote data (it inspects source, not data).
    tier3 = metrics_tier3_guard()
    if tier3:
        failed = True
        print(f"integrity: TIER-3 GUARD FAILED — {len(tier3)} violation(s):")
        for v in tier3:
            print(f"    {v}")
    else:
        print("integrity: Tier-3 guard OK (no metric consumes another metric's output).")

    # §6.8 disclosure guard: published grades trace to the ratified thresholds.
    disclosure = grades_disclosure()
    if disclosure:
        failed = True
        print(f"integrity: DISCLOSURE GUARD FAILED — {len(disclosure)} violation(s):")
        for v in disclosure:
            print(f"    {v}")
    else:
        print("integrity: disclosure guard OK (grades trace to ratified thresholds.yaml).")

    # (prefix, human label, cross-check fn). Sample only rolls that carry MS
    # positions (skip Speaker-election rolls, which have none to cross-check).
    passes = (
        ("h", "House rolls against clerk XML", cross_check),
        ("s", "Senate rolls against detail XML", senate_cross_check),
    )
    ran = False
    for prefix, label, checker in passes:
        ids = _ids_with_positions(prefix)
        if not ids:
            continue
        ran = True
        sample = _sample_ids(ids)
        mismatches, unreachable = checker(sample)
        print(f"integrity: cross-check on {len(sample)} sampled {label}.")
        if unreachable:
            print(f"  WARN: {len(unreachable)} fetch(es) unreachable (not a failure): "
                  f"{unreachable}")
        if mismatches:
            failed = True
            print(f"  INTEGRITY FAILED — {len(mismatches)} position mismatch(es):")
            for m in mismatches:
                print(f"    {m}")
        else:
            checked = len(sample) - len(unreachable)
            print(f"  OK ({checked}/{len(sample)} verified).")
    if not ran:
        print("integrity: no roll-call data yet — cross-check inactive (no-op).")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
