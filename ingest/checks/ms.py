"""INC-12 phase 3 — Mississippi state-layer checks (CI, blocking; offline).

Three guards over data/state/ms/, no-ops until `ingest ms` has run:

  * CONSISTENCY (verify-recompute analog): for every MS roll, the per-person
    member_votes recompute the stored `totals`; `party_totals` sum to `totals`; every
    voter is in the roster; and no roll is `unclassified`/`other` (the MS classification
    gate). This is the MS equivalent of verify-recompute + classification + the
    party-split invariant, and — because LegiScan gives every position — coverage is
    exact (every roster member of a chamber appears, or the miss is reported).

  * INTEGRITY spot-check (scrape fidelity): the GO verdict (D21) matched LegiScan to the
    official billstatus per-vote PDFs 5/5 (470 per-person positions). This re-runs that
    at the tally level in CI, OFFLINE, against the committed sample PDFs: each sample's
    official Yeas/Nays/Absent `Total--N` (parsed from the verbatim record) must equal our
    ingested roll's totals. Proves our published MS tallies still match the official
    record. (The per-person 470-position match is recorded in the verdict; this is the
    automated regression guard.)

Registered in checks/run.py. Reads only committed data — safe in the offline suite.
"""

from __future__ import annotations

import json
import re

from ingest.cache import repo_root
from ingest.export import MS_MEMBERS_DIR, MS_VOTES_DIR

# Sample roll -> committed official PDF text (the GO-verdict cross-check set, D21). The
# roll_call_ids are from data/quality/samples/ms_vote_xcheck/README.md.
_SAMPLE_DIR = repo_root() / "data" / "quality" / "samples" / "ms_vote_xcheck"
_SAMPLES: dict[str, str] = {
    "ms-h-2249-1614160": "HB2_house_61-59.txt",
    "ms-h-2249-1659549": "SB2436_house_50-60.txt",
    "ms-h-2249-1630454": "HB362_house_64-51.txt",
    "ms-s-2249-1625251": "SB2232_senate_26-26.txt",
    "ms-s-2249-1632993": "SB2587_senate_24-25.txt",
}
# Buckets end with "Total--N". NV = "Absent or/and those not voting" + (House) "Present".
_YEA_RE = re.compile(r"Yeas--.*?Total--(\d+)", re.S)
_NAY_RE = re.compile(r"Nays--.*?Total--(\d+)", re.S)
_NV_RE = re.compile(r"(?:Absent (?:or|and) those not voting|Present)--.*?Total--(\d+)", re.S)


def parse_official_totals(text: str) -> dict[str, int]:
    """Official billstatus PDF text -> {yea, nay, not_voting} from the Total--N lines.
    not_voting sums the Absent bucket and (House) the Present bucket."""
    yea = _YEA_RE.search(text)
    nay = _NAY_RE.search(text)
    return {
        "yea": int(yea.group(1)) if yea else -1,
        "nay": int(nay.group(1)) if nay else -1,
        "not_voting": sum(int(m.group(1)) for m in _NV_RE.finditer(text)),
    }


def _load_votes() -> list[dict]:
    if not MS_VOTES_DIR.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(MS_VOTES_DIR.glob("*.json"))]


def _roster() -> set[str]:
    if not MS_MEMBERS_DIR.exists():
        return set()
    return {p.stem for p in MS_MEMBERS_DIR.glob("*.json")}


def consistency_failures(votes: list[dict], roster: set[str]) -> list[str]:
    """verify-recompute + classification + party-split invariants over MS rolls."""
    fails: list[str] = []
    for rec in votes:
        rc = rec["rollcall"]
        rid = rc["id"]
        recomputed = {"yea": 0, "nay": 0, "present": 0, "not_voting": 0}
        for mv in rec["member_votes"]:
            if mv["member_id"] not in roster:
                fails.append(f"{rid}: voter {mv['member_id']} not in the MS roster")
            recomputed[mv["position"]] += 1
        if recomputed != rc["totals"]:
            fails.append(f"{rid}: member_votes recompute {recomputed} != totals {rc['totals']}")
        # party_totals must sum to totals per category (the invariant-4 analog).
        pt = rc.get("party_totals") or {}
        for cat in ("yea", "nay", "present", "not_voting"):
            s = sum(p.get(cat, 0) for p in pt.values())
            if s != rc["totals"][cat]:
                fails.append(f"{rid}: party_totals[{cat}] sum {s} != totals {rc['totals'][cat]}")
        if rc["vote_class"] == "other" or rc["vote_class_rule"] == "MS-OTHER":
            fails.append(f"{rid}: unclassified roll (desc {rc['question']!r})")
    return fails


def integrity_failures(votes_by_id: dict[str, dict]) -> list[str]:
    """Each committed official-PDF sample's tally must equal our ingested roll's."""
    fails: list[str] = []
    for rid, fname in sorted(_SAMPLES.items()):
        path = _SAMPLE_DIR / fname
        if not path.exists() or rid not in votes_by_id:
            fails.append(f"{rid}: sample {fname} or ingested roll missing")
            continue
        official = parse_official_totals(path.read_text(encoding="utf-8"))
        ours = votes_by_id[rid]["rollcall"]["totals"]
        ours3 = {k: ours[k] for k in ("yea", "nay", "not_voting")}
        if official != ours3:
            fails.append(f"{rid}: official PDF {official} != ingested {ours3}")
    return fails


def metrics_failures() -> list[str]:
    """MS metrics recompute-and-match: build() from the committed partition must equal
    the committed data/state/ms/metrics.json (the MS analog of the federal test)."""
    from ingest.export import MS_METRICS_PATH
    if not MS_METRICS_PATH.exists():
        return []
    from ingest import ms_metrics
    committed = json.loads(MS_METRICS_PATH.read_text(encoding="utf-8"))
    fresh = ms_metrics.build().model_dump()
    if fresh != committed:
        return ["data/state/ms/metrics.json is stale — re-run `ingest ms --force`"]
    return []


def main() -> int:
    votes = _load_votes()
    if not votes:
        print("ms: no data/state/ms/ votes yet — MS checks inactive (no-op).")
        return 0
    roster = _roster()
    votes_by_id = {rec["rollcall"]["id"]: rec for rec in votes}

    cfails = consistency_failures(votes, roster)
    ifails = integrity_failures(votes_by_id)
    mfails = metrics_failures()

    for label, fails in (("consistency", cfails), ("integrity spot-check", ifails),
                         ("metrics recompute", mfails)):
        if fails:
            print(f"MS CHECK FAILED — {len(fails)} {label} failure(s):")
            for f in fails[:20]:
                print(f"  {f}")
    if cfails or ifails or mfails:
        return 1
    print(f"ms: OK ({len(votes)} rolls recompute; party splits sum; all classified; "
          f"{len(_SAMPLES)} official-PDF tallies match; metrics recompute).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
