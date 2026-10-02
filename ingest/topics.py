"""V2-11 task 6 — project `data/bills/**` into `data/topics/index.json`.

A PURE projection, same contract as `ingest/events.py`: no socket, no clock,
nothing invented. Every topic in this file is a label the GOVERNMENT already put
on a bill — the single `policy_area` it assigns, and the CRS legislative
`subjects` it tags. We add exactly one thing, a slug, and that is mechanical.

**SD-33 decision 4(a): official vocabulary only.** No owner-authored bundles this
release (H22 stays optional, not a blocker), so there is no curation step here and
nothing in this module reads owner config. Nothing is evaluative either, so §0.8
does not apply: a topic is not a judgement about a bill.

**Policy areas and subjects are kept apart on purpose.** A bill has exactly one
`policy_area` (31 exist) and many `subjects` (hundreds). "Health" the policy area
and "Health" the subject term are different claims, and merging the vocabularies
would publish one topic page that silently means both.

**No count in here is a cap.** SD-33 was ratified against a snapshot of 31 policy
areas and 872 CRS terms; 877 distinct terms were already on disk partway through
the backfill. The vocabulary is the government's to extend, so this module asserts
no total — it reports what the dataset holds.

**The D27 sentinel is respected.** `subjects is None` means NOT YET COLLECTED and
contributes nothing; `[]` means collected and the government tags none. Neither is
an error, and both are distinct from "this bill has no topics". The index therefore
grows as the backfill lands, which is exactly why it can be built today against
1,349 bills and behave identically at 38,756.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ingest.models import TopicEntry, TopicsFile

# Everything that is not a letter or a digit becomes a single hyphen. The official
# terms are full of punctuation a URL cannot carry verbatim -- "Veterans' pensions",
# "Labor, employment", "Alcoholic beverages and traffic safety (DUI/DWI)" -- so the
# rule has to be total, not a list of special cases.
_NOT_ALNUM = re.compile(r"[^a-z0-9]+")


class SlugCollision(Exception):
    """Two different official terms reduced to the same slug.

    This FAILS the run rather than picking a winner or appending a counter. A
    collision means one URL would have to stand for two different government
    labels, and whichever way it resolved, a topic page would list bills that the
    government did not put under the topic the reader asked for (value #1: fail
    loudly instead of publishing a quiet wrong answer). The fix when it happens is
    a decision about the slug rule, not a silent disambiguation -- so the message
    carries both terms."""


def slugify(name: str) -> str:
    """The mechanical slug rule, and the only transformation this module applies to
    a government string. Lowercase, every run of non-alphanumerics to one hyphen,
    no leading or trailing hyphen.

    Deliberately NOT reversible and never stored as the display text: `name` is
    what renders, `slug` is only ever a URL. Keeping them separate is what lets the
    rule change later (a redirect) without touching published government text."""
    return _NOT_ALNUM.sub("-", name.lower()).strip("-")


def _entries(by_name: dict[str, set[str]], *, vocabulary: str) -> list[TopicEntry]:
    """Turn `{official term: {bill ids}}` into sorted, slug-unique entries.

    Sorted by slug (not by name, not by count) so the file is byte-stable and the
    order does not move when a bill count changes. Counts belong in the entry, not
    in the ordering."""
    slugs: dict[str, str] = {}
    out: list[TopicEntry] = []
    for name in sorted(by_name):
        slug = slugify(name)
        if not slug:
            raise SlugCollision(
                f"{vocabulary}: the term {name!r} has no alphanumeric characters and "
                f"cannot be given a URL"
            )
        if slug in slugs:
            raise SlugCollision(
                f"{vocabulary}: {name!r} and {slugs[slug]!r} both slug to {slug!r} — "
                f"one URL cannot stand for two official terms; the slug rule needs a "
                f"decision, not a silent suffix"
            )
        slugs[slug] = name
        ids = sorted(by_name[name])
        out.append(
            TopicEntry(slug=slug, name=name, bill_count=len(ids), bill_ids=ids)
        )
    return sorted(out, key=lambda e: e.slug)


def compute(data_dir: Path) -> TopicsFile | None:
    """The whole index, or None when there are no bills to index yet.

    Bills are read in sorted filename order so the output cannot depend on
    directory iteration order even if a sort key below were wrong."""
    bills_dir = data_dir / "bills"
    if not bills_dir.exists():
        return None

    areas: dict[str, set[str]] = {}
    subjects: dict[str, set[str]] = {}
    n_bills = 0
    for path in sorted(bills_dir.glob("*.json")):
        bill = json.loads(path.read_text(encoding="utf-8"))
        n_bills += 1
        bill_id = bill["id"]
        if bill.get("policy_area"):
            areas.setdefault(bill["policy_area"], set()).add(bill_id)
        # D27: None = not collected (contributes nothing), [] = collected and none.
        for subject in bill.get("subjects") or []:
            subjects.setdefault(subject, set()).add(bill_id)

    area_entries = _entries(areas, vocabulary="policy_areas")
    subject_entries = _entries(subjects, vocabulary="subjects")
    return TopicsFile(
        policy_areas=area_entries,
        subjects=subject_entries,
        counts={
            "policy_areas": len(area_entries),
            "subjects": len(subject_entries),
            "bills": n_bills,
        },
    )


def run(argv: list[str] | None = None) -> int:
    """`uv run ingest topics` — write data/topics/index.json.

    Offline and idempotent. Writes through `export.export_topics`, so the file is
    byte-stable and atomically replaced."""
    from ingest.cache import repo_root
    from ingest.export import export_topics

    if argv:
        print(f"FAIL: unknown argument {argv[0]!r} (topics takes none)")
        return 2
    data_dir = repo_root() / "data"
    index = compute(data_dir)
    if index is None:
        print("civic-ledger topics: no bills on disk yet (no-op).")
        return 0
    export_topics(index, out_dir=data_dir / "topics")
    print(
        f"civic-ledger topics: {index.counts['policy_areas']} policy area(s) + "
        f"{index.counts['subjects']} subject term(s) over "
        f"{index.counts['bills']} bill(s) -> data/topics/index.json."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
