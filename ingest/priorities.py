"""Stated priorities per member, from APPROVED statements (§5 Phase 3 task 6).

Two owner rulings, applied mechanically — no AI, no judgment here:

  * **Q-B (2026-10-07), whether a member has a list at all:** at least
    `priorities_list.min_approved_statements` approved statements covering at least
    `min_distinct_topics` different policy areas. Below that bar the member has NO list and
    the page says there are not yet enough statements on record. The individual statements
    still publish in the timeline: the thing withheld is the inference, never the record.
    Nothing about a below-bar member's priorities is written here — not even an empty list —
    because a published inference the page does not show is still a published inference.
  * **Q-J (2026-10-09), which topics are priorities:** a topic + stance becomes a stated
    priority when ANY of (1) it is on the member's most recent campaign issue page — NOT
    COLLECTED YET (task 2c waits on the owner's URLs), so this route never fires today;
    (2) one approved statement signals it as a priority (`priority_signal`); (3)
    `stated_priority.repetition_statements` approved statements share the topic and stance,
    spread across at least `repetition_distinct_months` calendar months. Only statements
    from the member's CURRENT term count. If the member has approved statements on both
    sides of a topic in the term, NO priority is set on that topic.

"Approved" = a publishable record in `data/statements/` (dead-archive ones excluded, the
same rule the site applies): every record there was approved by the owner. A record counts
toward a topic only when it carries `topic`, and toward a priority only when it also carries
`stated_position` (`support` / `oppose`); a record without them still counts toward Q-B's
statement total.

Output: `data/priorities.json`, deterministic (sorted keys, no wall-clock), written by
`uv run export` and re-derived byte-for-byte by `verify-recompute`. Members with no approved
statement are absent; the page treats absence as zero statements on record.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ingest import statements_io
from ingest.cache import repo_root

STANCES = ("support", "oppose")


@dataclass(frozen=True)
class Rules:
    min_approved_statements: int
    min_distinct_topics: int
    repetition_statements: int
    repetition_distinct_months: int


def load_rules(data_dir: Path | None = None) -> Rules:
    base = data_dir if data_dir is not None else repo_root() / "data"
    raw = yaml.safe_load((base / "config" / "thresholds.yaml").read_text(encoding="utf-8"))
    qb, qj = raw["priorities_list"], raw["stated_priority"]
    return Rules(
        min_approved_statements=int(qb["min_approved_statements"]),
        min_distinct_topics=int(qb["min_distinct_topics"]),
        repetition_statements=int(qj["repetition_statements"]),
        repetition_distinct_months=int(qj["repetition_distinct_months"]),
    )


def member_priorities(
    statements: list[dict[str, Any]], term_start: str | None, rules: Rules
) -> dict[str, Any]:
    """One member's entry. `statements` are that member's approved records."""
    topics = {s["topic"] for s in statements if s.get("topic")}
    entry: dict[str, Any] = {
        "approved_statements": len(statements),
        "distinct_topics": len(topics),
        "listed": (len(statements) >= rules.min_approved_statements
                   and len(topics) >= rules.min_distinct_topics),
    }
    if not entry["listed"]:
        return entry

    in_term = [s for s in statements
               if term_start is None or s["date"][:10] >= term_start[:10]]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for s in in_term:
        if s.get("topic") and s.get("stated_position") in STANCES:
            groups[(s["topic"], s["stated_position"])].append(s)
    sides: dict[str, set[str]] = defaultdict(set)
    for topic, stance in groups:
        sides[topic].add(stance)
    conflicted = sorted(t for t, st in sides.items() if len(st) > 1)

    priorities = []
    for (topic, stance), items in sorted(groups.items()):
        if topic in conflicted:
            continue
        routes = []
        if any(s.get("priority_signal") is True for s in items):
            routes.append("signal")
        months = {s["date"][:7] for s in items}
        if (len(items) >= rules.repetition_statements
                and len(months) >= rules.repetition_distinct_months):
            routes.append("repetition")
        if routes:
            priorities.append({
                "topic": topic,
                "stance": stance,
                "routes": routes,
                "statement_ids": sorted(s["id"] for s in items),
            })
    entry["priorities"] = priorities
    entry["conflicted_topics"] = conflicted
    return entry


def _term_starts(data_dir: Path) -> dict[str, str]:
    starts: dict[str, str] = {}
    members = data_dir / "members"
    if members.exists():
        for path in members.glob("*.json"):
            member = json.loads(path.read_text(encoding="utf-8"))
            terms = member.get("terms") or []
            if terms:
                starts[member["id"]] = max(t["start"] for t in terms)
    return starts


def compute(data_dir: Path | None = None) -> dict[str, Any]:
    base = data_dir if data_dir is not None else repo_root() / "data"
    rules = load_rules(base)
    by_member: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in statements_io.load_statements(base, exclude_dead=True):
        by_member[s["member_id"]].append(s)
    starts = _term_starts(base)
    return {
        "bar": {
            "min_approved_statements": rules.min_approved_statements,
            "min_distinct_topics": rules.min_distinct_topics,
        },
        "members": {
            member_id: member_priorities(items, starts.get(member_id), rules)
            for member_id, items in sorted(by_member.items())
        },
    }


def path(data_dir: Path | None = None) -> Path:
    return (data_dir if data_dir is not None else repo_root() / "data") / "priorities.json"


def write(data_dir: Path | None = None) -> Path:
    from ingest.export import _dumps

    out = path(data_dir)
    out.write_text(_dumps(compute(data_dir)), encoding="utf-8", newline="\n")
    return out
