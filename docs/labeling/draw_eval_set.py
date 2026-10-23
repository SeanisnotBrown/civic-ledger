"""Draw a held-out evaluation set to be labeled by hand (§5 Phase 3 task 4).

This is the SECOND set (2026-10-23). Owner ruling R3, 2026-10-23: the first 60 (seed
20261022, `2026-10-22-eval-set.csv`) are spent for any changed prompt, so triage v2 /
categorizer v3 are measured on a fresh 60. The first set's draw is reproducible from this
script as it stood at commit 89dc35914.

Reproducible from the seed: the same corpus, the same first-pass ledger, the same
`docs/research/` and this script give the same 60 rows in the same order. Light and
offline: no AI call, no network.

    python -B docs/labeling/draw_eval_set.py --data <a checkout's data/ dir> \
        [--research <that checkout's docs/research/>]

The corpus is the pre-filter's AI-eligible survivors (vote explanations, R3, are never
here), joined to the Haiku first pass (`data/raw/triage/v1-stub.jsonl`) by the same text
fingerprint `ingest/triage_run.py` keys its ledger on. Mechanical rules, none evaluative:

  * Excluded: texts with no first-pass verdict (the 3 refusals) and texts over
    `MAX_CHARS` (a hand-labeling limit: the longest Record text is ~311,000 characters).
    The same text under two statements is drawn at most once.
  * Also excluded before the draw (ruling R3: nothing already seen may grade a new
    prompt): the first set's 60 rows (which include the 10 smoke-test rows, EV01-EV10);
    the statements the step 9 notes name, with every same-member, same-day statement; and
    every statement quoted or sampled in `docs/research/*.md`, matched by the member id and
    date the doc cites, by URL or Record granule id, or by a quoted title it starts with.
    Matching is deliberately broad: a same-member, same-day statement the doc did not mean
    is excluded too, which only shrinks the pool. Every exclusion is written, with its
    reasons, to `<NAME>-excluded.csv` beside the sheet.
  * 15 rows per pilot cell (party x chamber): 3 Congressional Record + 12 press, the
    corpus's ~20% Record share (2,931 of 14,810 eligible).
  * Within a cell and source, a third are first-pass rejects: Record 2 passed + 1
    rejected, press 8 passed + 4 rejected. Two press rejects per cell "look substantive":
    rejects the pre-filter's own `argues_policy` rule (owner, 2026-10-14) flags as naming
    a bill or asking for a vote. (Set 1 took the step 9 rejects first; set 2 excludes them.)
  * Rows are shuffled before they are written, so position says nothing about a verdict.

The committed CSV carries no verdict. The first pass is model output from a stub prompt,
which the repository never holds per statement, so the verdicts go to a gitignored sidecar
under `<data>/raw/labeling/`, joined by `text_sha256`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ingest import prefilter  # noqa: E402

SEED = 2026102302  # the date, then set number 2
STAMP = "2026-10-23"
NAME = f"{STAMP}-eval-set-2"
ID_PREFIX = "HO"  # held-out set 2; EV01-EV60 stay the first set's ids
FIRST_SET = "2026-10-22-eval-set.csv"
# The smoke test scored EV01-EV10 of the first set
# (docs/research/2026-10-23-prompt-eval-smoke.md, on master).
SMOKE_IDS = frozenset(f"EV{n:02d}" for n in range(1, 11))
MAX_CHARS = 8000
PROMPT_VERSION = "v1-stub"
# (source, passed, rejected) per cell.
PER_CELL = (("congressional_record", 2, 1), ("member_press", 8, 4))
SUBSTANTIVE_REJECTS = 2
# Rejects named in the step 9 notes (STATUS, 2026-10-22). Set 1 drew them on purpose; set 2
# excludes them, with every same-member, same-day statement (Al Green published two
# near-identical releases that day).
NAMED_REJECTS = (
    "https://algreen.house.gov/media/press-releases/"
    "rep-al-green-addresses-how-presidents-racist-commentary-normalizing-racism",
    "https://mccollum.house.gov/media/press-releases/"
    "congresswoman-mccollum-introduces-resolution-recognize-national-nonprofit-day",
    "https://ezell.house.gov/news/documentsingle.aspx?DocumentID=1902",
)
STEP9_MEMBER_DATES = frozenset({("G000553", "2026-06-12"), ("M001143", "2025-08-15"),
                                ("E000235", "2025-08-29")})
LABEL_COLUMNS = (
    "takes_policy_position",
    "topic",
    "topic_secondary",  # owner ruling R1, 2026-10-23
    "stance",
    "proposition",
    "specificity",
    "priority_signal",
    "notes",
)

# What a docs/research file can use to point at one statement.
MEMBER_DATE = re.compile(r"\(`?([A-Z]\d{6})`?\),? (\d{4}-\d{2}-\d{2})")
QUOTED = re.compile(r'"([^"\n]{25,})"|“([^”\n]{25,})”')
URL = re.compile(r"https?://[^\s)>\"'`|\]]+")
GRANULE = re.compile(r"CREC-\d{4}-\d{2}-\d{2}-pt\d-Pg[A-Z]*\d+(?:-\d+)?")


def text_of(statement: dict[str, Any]) -> str:
    """What the first pass read: the kept turns only (`triage_run.statement_text`)."""
    return "\n\n".join(statement["segments"])


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_verdicts(path: Path) -> dict[str, bool]:
    verdicts: dict[str, bool] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            verdicts[entry["text_sha256"]] = entry["takes_policy_position"]
    return verdicts


def candidates(data_dir: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    records, _parties, names = prefilter.load_all(data_dir)
    result = prefilter.run_prefilter(records, prefilter.load_text_failures(data_dir))
    pilot = yaml.safe_load((data_dir / "config" / "statement-pilot.yaml").read_text("utf-8"))
    cells = {
        member["id"]: (cell["party"], cell["chamber"])
        for cell in pilot["cells"]
        for member in cell["members"]
    }
    verdicts = load_verdicts(data_dir / "raw" / "triage" / f"{PROMPT_VERSION}.jsonl")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    ordered = sorted(
        (s for s in result["statements"] if s.get("ai_eligible", True)),
        key=lambda s: (s["member_id"], s.get("date", ""), s.get("granule_id", ""), s["url"]),
    )
    for statement in ordered:
        text = text_of(statement)
        digest = sha(text)
        if digest in seen or digest not in verdicts or len(text) > MAX_CHARS:
            continue
        seen.add(digest)
        party, chamber = cells[statement["member_id"]]
        rows.append(
            {
                "statement": statement,
                "text": text,
                "text_sha256": digest,
                "party": party,
                "chamber": chamber,
                "passed": verdicts[digest],
                "substantive": prefilter.argues_policy(text),
            }
        )
    return rows, names


def _fold(text: str) -> str:
    return " ".join(text.split()).casefold()


def cited(research: Path) -> dict[str, dict[str, set[str]]]:
    """Everything `docs/research/*.md` cites that could name a statement, by kind, with the
    docs that cite it."""
    found: dict[str, dict[str, set[str]]] = {
        kind: defaultdict(set) for kind in ("member and date", "title", "url", "granule")
    }
    for doc in sorted(research.glob("*.md")):
        text = doc.read_text(encoding="utf-8")
        for member, day in MEMBER_DATE.findall(text):
            found["member and date"][f"{member} {day}"].add(doc.name)
        for straight, curly in QUOTED.findall(text):
            found["title"][_fold((straight or curly).rstrip(".… "))].add(doc.name)
        for url in URL.findall(text):
            found["url"][url.rstrip(".,;:")].add(doc.name)
        for granule in GRANULE.findall(text):
            found["granule"][granule].add(doc.name)
    return found


def exclusions(
    rows: list[dict[str, Any]], first_set: Path, research: Path
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """({text_sha256: reasons} for every candidate set 2 must not draw, how many items each
    source cites). Most cited items are never candidates: pre-filter drops, refusals, texts
    over MAX_CHARS, or press index pages."""
    with first_set.open(encoding="utf-8-sig", newline="") as handle:
        first = {r["text_sha256"]: r["id"] for r in csv.DictReader(handle)}
    docs = cited(research)
    excluded: dict[str, list[str]] = {}
    for row in rows:
        s, digest = row["statement"], row["text_sha256"]
        reasons: list[str] = []
        if digest in first:
            smoke = " (smoke test)" if first[digest] in SMOKE_IDS else ""
            reasons.append(f"first set {first[digest]}{smoke}")
        if s["url"] in NAMED_REJECTS or (s["member_id"], s.get("date", "")) in (
            STEP9_MEMBER_DATES
        ):
            reasons.append("step 9 notes")
        title = _fold(s.get("title") or "")
        keys = {
            "member and date": [f"{s['member_id']} {s.get('date', '')}"],
            "url": [s["url"]],
            "granule": [s.get("granule_id") or ""],
            "title": [q for q in docs["title"] if title and title.startswith(q)],
        }
        for kind, wanted in keys.items():
            for key in wanted:
                for name in sorted(docs[kind].get(key, ())):
                    reasons.append(f"{name}: {kind}")
        if reasons:
            excluded[digest] = reasons
    counts = {"first-set rows": len(first),
              **{f"docs/research cites by {kind}": len(v) for kind, v in docs.items()}}
    return excluded, counts


def draw(rows: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    strata: dict[tuple[str, str, str, bool], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row["party"], row["chamber"], row["statement"]["source"], row["passed"])
        strata[key].append(row)
    picked: list[dict[str, Any]] = []
    for party, chamber in sorted({(r["party"], r["chamber"]) for r in rows}):
        for source, n_passed, n_rejected in PER_CELL:
            for row in rng.sample(strata[(party, chamber, source, True)], n_passed):
                picked.append({**row, "draw_reason": "first pass: passed"})
            pool = strata[(party, chamber, source, False)]
            chosen: list[dict[str, Any]] = []
            if source == "member_press":
                flagged = [r for r in pool if r["substantive"]]
                for row in rng.sample(flagged, SUBSTANTIVE_REJECTS):
                    chosen.append(
                        {**row, "draw_reason": "rejected; names a bill or asks for a vote"}
                    )
            taken = {r["text_sha256"] for r in chosen}
            rest = [r for r in pool if r["text_sha256"] not in taken]
            for row in rng.sample(rest, n_rejected - len(chosen)):
                chosen.append({**row, "draw_reason": "rejected; random"})
            picked.extend(chosen)
    rng.shuffle(picked)
    return picked


def write(
    picked: list[dict[str, Any]],
    names: dict[str, str],
    excluded: dict[str, list[str]],
    data_dir: Path,
) -> tuple[Path, Path, Path]:
    sheet = ROOT / "docs" / "labeling" / f"{NAME}.csv"
    record = ROOT / "docs" / "labeling" / f"{NAME}-excluded.csv"
    # The sidecar goes under the data dir the corpus came from: a worktree has no data/raw.
    sidecar = data_dir / "raw" / "labeling" / f"{NAME}-verdicts.csv"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    with sheet.open("w", encoding="utf-8-sig", newline="") as handle:
        out = csv.writer(handle)
        out.writerow(
            ("id", "member", "party", "chamber", "source", "date", "date_precision", "url")
            + ("text",)
            + LABEL_COLUMNS
            + ("text_sha256",)
        )
        for number, row in enumerate(picked, start=1):
            s = row["statement"]
            member = f"{names.get(s['member_id'], s['member_id'])} ({s['member_id']})"
            out.writerow(
                (f"{ID_PREFIX}{number:02d}", member, row["party"], row["chamber"], s["source"])
                + (s.get("date", ""), s.get("date_precision", ""), s["url"], row["text"])
                + ("",) * len(LABEL_COLUMNS)
                + (row["text_sha256"],)
            )
    # Reasons only, never a verdict: which statements the draw was not allowed to take.
    with record.open("w", encoding="utf-8", newline="") as handle:
        out = csv.writer(handle, lineterminator="\n")
        out.writerow(("text_sha256", "reasons"))
        for digest in sorted(excluded):
            out.writerow((digest, "; ".join(excluded[digest])))
    with sidecar.open("w", encoding="utf-8-sig", newline="") as handle:
        out = csv.writer(handle)
        out.writerow(("id", "first_pass_takes_policy_position", "draw_reason", "text_sha256"))
        for number, row in enumerate(picked, start=1):
            verdict = "yes" if row["passed"] else "no"
            out.writerow((f"{ID_PREFIX}{number:02d}", verdict, row["draw_reason"],
                          row["text_sha256"]))
    return sheet, record, sidecar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--research", type=Path, default=None,
                        help="docs/research to exclude from (default: beside --data)")
    args = parser.parse_args(argv)
    data_dir = args.data.resolve()
    research = (args.research or data_dir.parent / "docs" / "research").resolve()
    rows, names = candidates(data_dir)
    excluded, counts = exclusions(rows, ROOT / "docs" / "labeling" / FIRST_SET, research)
    pool = [r for r in rows if r["text_sha256"] not in excluded]
    picked = draw(pool, random.Random(SEED))
    sheet, record, sidecar = write(picked, names, excluded, data_dir)
    print(f"{len(rows)} candidates; {len(excluded)} excluded; {len(pool)} in the pool; "
          f"{len(picked)} drawn (seed {SEED}); research from {research}")
    for name, n in counts.items():
        print(f"  {name}: {n}")
    by_kind: dict[str, int] = defaultdict(int)
    for reasons in excluded.values():
        kinds = {r.split(": ", 1)[1] if ": " in r else r.split(" EV")[0] for r in reasons}
        for kind in kinds:
            by_kind[kind] += 1
    for kind, n in sorted(by_kind.items()):
        print(f"  excluded candidates with a reason of kind '{kind}': {n}")
    strata: dict[tuple[str, str, str, bool], int] = defaultdict(int)
    for r in pool:
        strata[(r["party"], r["chamber"], r["statement"]["source"], r["passed"])] += 1
    print(f"  smallest pool stratum: {min(strata.values())}")
    print(f"  {sheet.relative_to(ROOT)}")
    print(f"  {record.relative_to(ROOT)}")
    print(f"  {sidecar} (gitignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
