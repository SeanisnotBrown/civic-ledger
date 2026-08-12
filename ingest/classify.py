"""INC-5 — vote_class classifier (§A1). A TOTAL function over the official
question/action string, per Decision D7: an explicit ordered rules table, no LLM,
no silent misclassification. Every roll gets a `vote_class` (the §5 enum) and the
`vote_class_rule` id that fired (auditability; the table renders on the methodology
page in INC-10). Anything unmatched → `other`, logged to
`data/quality/unmapped_questions.json` — an honest `other` beats a speculative rule.

`classify()` is PURE and offline (golden-tested against real strings). The one
data-dependent rule, R-RULE, is kept pure by taking `is_rules_resolution` as an
argument: the pipeline (`run()`) computes it for House `hres` "On Agreeing to the
Resolution" rolls by asking Congress.gov which committee reported the resolution
(House Rules `hsru00` + a "Reported" activity ⇒ a special rule ⇒ procedural; else
the generic R-RES ⇒ passage).

Speaker-election `non_position` rolls (INC-3) are left untouched — they carry no
yea/nay position and are not §A1-classifiable.
"""

from __future__ import annotations

import re

from ingest.models import VoteClass

# Ordered §A1 rules table (+ sanctioned extensions from the unmapped-questions
# loop over real 118–119 strings — the spec says extend until `other` ≤ 5%). Each
# row: (rule_id, class, patterns, mode). `mode` "prefix" = normalized question
# starts with a pattern; "contains" = pattern appears anywhere (for motions the
# Senate embeds inside "On the Motion (… Motion to Commit)"). FIRST match wins, so
# order encodes precedence: specific phrases and cloture before the generic motion
# and resolution rules, so e.g. "On Cloture on the Motion to Proceed" audits as
# cloture, not motion-to-proceed. R-RES is special-cased in `classify()`.
Rule = tuple[str, VoteClass, tuple[str, ...], str]

RULES: tuple[Rule, ...] = (
    # Veto override — most specific first.
    ("R-VETO", "veto_override",
     ("objections of the president", "on overriding the veto"), "contains"),
    # Treaty ratification: explicit → other (logged), BEFORE the "on the resolution"
    # passage rule would otherwise swallow "On the Resolution of Ratification".
    ("R-TREATY", "other", ("on the resolution of ratification",), "prefix"),
    # Nominations / confirmations.
    ("R-NOM", "nomination", ("on the nomination", "on the confirmation"), "prefix"),
    # Cloture BEFORE the generic motion-to-proceed rule (so cloture audits as cloture).
    ("R-PROC-1", "procedural", ("on the cloture motion", "on cloture"), "prefix"),
    # Passage via the suspension calendar (before generic motion + pass/agree rules).
    ("R-PASS-2", "passage", ("suspend the rules and pass",), "contains"),
    ("R-PASS-SUSP-AGREE", "passage", ("suspend the rules and agree",), "contains"),
    ("R-PASS-SUSP-CONCUR", "passage", ("suspend the rules and concur",), "contains"),
    # Concurring in the other chamber's amendment = final disposition ⇒ passage.
    ("R-PASS-3", "passage",
     ("on concurring", "on agreeing to the senate amendment", "concur in the senate amendment",
      "concur in the house amendment", "motion to concur"), "contains"),
    # Procedural motions.
    ("R-PROC-2", "procedural", ("motion to proceed",), "contains"),
    ("R-PROC-3", "procedural", ("on ordering the previous question",), "prefix"),
    ("R-PROC-4", "procedural", ("motion to recommit", "motion to commit"), "contains"),
    ("R-PROC-5", "procedural", ("motion to table", "table motion to reconsider"), "contains"),
    ("R-PROC-6", "procedural",
     ("on the journal", "call of the house", "call by states", "quorum"), "prefix"),
    ("R-PROC-7", "procedural",
     ("motion to adjourn", "motion for adjournment", "motion to recess", "motion to discharge",
      "motion to refer", "motion to reconsider", "motion to instruct", "point of order",
      "decision of the chair", "motion to close the doors", "motion for attendance",
      "go to conference", "closing portions of the conference"), "contains"),
    # Budget-Act point-of-order waivers (the Senate's 60-vote procedural gate on an
    # amendment/measure) — a procedural motion, not the underlying amendment.
    ("R-PROC-WAIVE", "procedural", ("motion to waive",), "contains"),
    ("R-PROC-CONSIDER", "procedural", ("on consideration of the resolution",), "prefix"),
    # Passage of a measure.
    ("R-PASS-1", "passage", ("on passage", "on the passage"), "prefix"),
    ("R-PASS-JRES", "passage", ("on the joint resolution",), "prefix"),
    ("R-PASS-CONRES", "passage", ("on the concurrent resolution",), "prefix"),
    ("R-PASS-CONFREP", "passage", ("on the conference report",), "prefix"),
    # Amendments.
    ("R-AMDT-1", "amendment", ("on agreeing to the amendment", "on the amendment"), "prefix"),
    # Resolutions. R-RES is special-cased: a Rules-Committee-reported special rule
    # flips to procedural (R-RULE); every other resolution is substantive ⇒ passage.
    ("R-RES", "passage", ("on agreeing to the resolution",), "prefix"),
    ("R-RES-SENATE", "passage", ("on the resolution",), "prefix"),
)

_WS = re.compile(r"\s+")


def _normalize(question: str) -> str:
    return _WS.sub(" ", question).strip().lower()


def classify(question: str, *, is_rules_resolution: bool = False) -> tuple[VoteClass, str]:
    """(vote_class, vote_class_rule) for one official question string. Total: an
    unmatched question returns ("other", "R-DEFAULT"). `is_rules_resolution` flips
    the generic resolution rule to R-RULE (procedural) for a Rules-Committee-
    reported special rule; it is ignored by every other rule."""
    q = _normalize(question)
    for rule_id, cls, patterns, mode in RULES:
        for p in patterns:
            hit = q.startswith(p) if mode == "prefix" else p in q
            if not hit:
                continue
            if rule_id == "R-RES" and is_rules_resolution:
                return "procedural", "R-RULE"
            return cls, rule_id
    return "other", "R-DEFAULT"


# --- pipeline -------------------------------------------------------------

_HRES_RE = re.compile(r"^hres(\d+)-(\d+)$")


def _is_rules_reported(bill_id: str) -> bool:
    """True if `bill_id` (an `hres…`) was REPORTED by the House Rules Committee
    (`hsru00`) — i.e. it is a special rule (rule adoption), not a substantive
    resolution. Reads the committees sub-resource from Congress.gov."""
    from ingest.sources import congress_gov

    m = _HRES_RE.match(bill_id)
    if not m:
        return False
    number, congress = int(m.group(1)), int(m.group(2))
    data = congress_gov.bill_committees(congress, "hres", number).json()
    for c in data.get("committees", []):
        if c.get("systemCode") == "hsru00":
            if any("report" in (a.get("name") or "").lower() for a in c.get("activities", [])):
                return True
    return False


def run(argv: list[str] | None = None) -> int:
    """Classify every exported roll in place: rewrite `vote_class`/`vote_class_rule`
    on data/votes/*.json (non-`non_position` only), regenerate
    data/quality/unmapped_questions.json, and fail if the `other` rate exceeds
    config.MAX_OTHER_RATE. Deterministic + idempotent (re-run is byte-identical).

    MUST run AFTER an ingest and BEFORE `uv run checks` — an ingest re-export resets
    every roll to the provisional `unclassified` (D24). Resumable: a committee-fetch
    failure is recorded and fails the run (a re-run retries only the cached miss)."""
    import json
    from collections import Counter

    import httpx

    from ingest import config
    from ingest.cache import RetryableHTTPError, repo_root
    from ingest.export import _dumps

    fetch_errors = (RetryableHTTPError, httpx.HTTPError, OSError)
    votes_dir = repo_root() / "data" / "votes"
    files = sorted(votes_dir.glob("*.json"))
    if not files:
        print("classify: no roll-call data yet — nothing to classify (no-op).")
        return 0

    # Pass 1: which hres "On Agreeing to the Resolution" rolls need a Rules check.
    resolutions: set[str] = set()
    for path in files:
        rc = json.loads(path.read_text(encoding="utf-8"))["rollcall"]
        if rc["vote_class_rule"] == "non_position":
            continue
        bid = rc["bill_id"] or ""
        q = _normalize(rc["question"])
        if _HRES_RE.match(bid) and q.startswith("on agreeing to the resolution"):
            resolutions.add(bid)

    rules_reported: dict[str, bool] = {}
    fetch_failures: list[str] = []
    for bid in sorted(resolutions):
        try:
            rules_reported[bid] = _is_rules_reported(bid)
        except fetch_errors as exc:
            fetch_failures.append(f"{bid}: {type(exc).__name__}")
            rules_reported[bid] = False  # provisional; the run fails below → re-run

    # Pass 2: classify + rewrite in place.
    counts: Counter[str] = Counter()
    other_questions: Counter[str] = Counter()
    n = 0
    for path in files:
        rec = json.loads(path.read_text(encoding="utf-8"))
        rc = rec["rollcall"]
        if rc["vote_class_rule"] == "non_position":
            continue
        irr = rules_reported.get(rc["bill_id"] or "", False)
        cls, rule = classify(rc["question"], is_rules_resolution=irr)
        rc["vote_class"] = cls
        rc["vote_class_rule"] = rule
        path.write_text(_dumps(rec), encoding="utf-8", newline="\n")
        counts[cls] += 1
        n += 1
        if cls == "other":
            other_questions[rc["question"]] += 1

    # Deterministic unmapped log (spec says "append"; a sorted regen is the §6.3
    # determinism-preserving equivalent — D24).
    unmapped_path = repo_root() / "data" / "quality" / "unmapped_questions.json"
    unmapped_path.parent.mkdir(parents=True, exist_ok=True)
    unmapped_path.write_text(
        _dumps({"questions": dict(sorted(other_questions.items())), "count": counts["other"]}),
        encoding="utf-8", newline="\n",
    )

    other_rate = counts["other"] / n if n else 0.0
    for cls, c in sorted(counts.items()):
        print(f"  {cls}: {c}")
    print(f"classify: {n} rolls classified; other rate {other_rate:.4%} "
          f"(ceiling {config.MAX_OTHER_RATE:.0%}).")
    if fetch_failures:
        print(f"FAIL: {len(fetch_failures)} committee fetch(es) failed (re-run to retry): "
              f"{fetch_failures[:10]}")
    if other_rate > config.MAX_OTHER_RATE:
        print(f"FAIL: other rate {other_rate:.4%} exceeds ceiling — extend §A1 "
              f"(see data/quality/unmapped_questions.json).")
    return 1 if (fetch_failures or other_rate > config.MAX_OTHER_RATE) else 0
