"""Draw the held-out evaluation set the owner labels by hand (§5 Phase 3 task 4).

Reproducible from the seed: the same corpus, the same first-pass ledger and this script
give the same 60 rows in the same order. Light and offline: no AI call, no network.

    python -B docs/labeling/draw_eval_set.py --data <a checkout's data/ dir>

The corpus is the pre-filter's AI-eligible survivors (vote explanations, R3, are never
here), joined to the Haiku first pass (`data/raw/triage/v1-stub.jsonl`) by the same text
fingerprint `ingest/triage_run.py` keys its ledger on. Mechanical rules, none evaluative:

  * Excluded: texts with no first-pass verdict (the 3 refusals) and texts over
    `MAX_CHARS` (a hand-labeling limit: the longest Record text is ~311,000 characters).
    The same text under two statements is drawn at most once.
  * 15 rows per pilot cell (party x chamber): 3 Congressional Record + 12 press, the
    corpus's ~20% Record share (2,931 of 14,810 eligible).
  * Within a cell and source, a third are first-pass rejects: Record 2 passed + 1
    rejected, press 8 passed + 4 rejected. Two press rejects per cell "look substantive":
    first the rejects named in the step 9 notes, then rejects the pre-filter's own
    `argues_policy` rule (owner, 2026-10-14) flags as naming a bill or asking for a vote.
  * Rows are shuffled before they are written, so position says nothing about a verdict.

The committed CSV carries no verdict. The first pass is model output from a stub prompt,
which the repository never holds per statement, so the verdicts go to a gitignored sidecar
under `data/raw/labeling/`, joined by `text_sha256`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ingest import prefilter  # noqa: E402

SEED = 20261022
STAMP = "2026-10-22"
MAX_CHARS = 8000
PROMPT_VERSION = "v1-stub"
# (source, passed, rejected) per cell.
PER_CELL = (("congressional_record", 2, 1), ("member_press", 8, 4))
SUBSTANTIVE_REJECTS = 2
# Rejects named in the step 9 notes (STATUS, 2026-10-22). Al Green published two near-
# identical releases that day; the first by URL is taken.
NAMED_REJECTS = (
    "https://algreen.house.gov/media/press-releases/"
    "rep-al-green-addresses-how-presidents-racist-commentary-normalizing-racism",
    "https://mccollum.house.gov/media/press-releases/"
    "congresswoman-mccollum-introduces-resolution-recognize-national-nonprofit-day",
    "https://ezell.house.gov/news/documentsingle.aspx?DocumentID=1902",
)
LABEL_COLUMNS = (
    "takes_policy_position",
    "topic",
    "stance",
    "proposition",
    "specificity",
    "priority_signal",
    "notes",
)


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
                named = [r for r in pool if r["statement"]["url"] in NAMED_REJECTS]
                for row in named[:SUBSTANTIVE_REJECTS]:
                    chosen.append({**row, "draw_reason": "rejected; named in step 9 notes"})
                flagged = [r for r in pool if r["substantive"] and r not in named]
                room = SUBSTANTIVE_REJECTS - len(chosen)
                for row in rng.sample(flagged, room):
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


def write(picked: list[dict[str, Any]], names: dict[str, str]) -> tuple[Path, Path]:
    sheet = ROOT / "docs" / "labeling" / f"{STAMP}-eval-set.csv"
    sidecar = ROOT / "data" / "raw" / "labeling" / f"{STAMP}-eval-set-verdicts.csv"
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
                (f"EV{number:02d}", member, row["party"], row["chamber"], s["source"])
                + (s.get("date", ""), s.get("date_precision", ""), s["url"], row["text"])
                + ("",) * len(LABEL_COLUMNS)
                + (row["text_sha256"],)
            )
    with sidecar.open("w", encoding="utf-8-sig", newline="") as handle:
        out = csv.writer(handle)
        out.writerow(("id", "first_pass_takes_policy_position", "draw_reason", "text_sha256"))
        for number, row in enumerate(picked, start=1):
            verdict = "yes" if row["passed"] else "no"
            out.writerow((f"EV{number:02d}", verdict, row["draw_reason"], row["text_sha256"]))
    return sheet, sidecar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    args = parser.parse_args(argv)
    rows, names = candidates(args.data)
    picked = draw(rows, random.Random(SEED))
    sheet, sidecar = write(picked, names)
    print(f"{len(rows)} candidates; {len(picked)} drawn (seed {SEED})")
    print(f"  {sheet.relative_to(ROOT)}")
    print(f"  {sidecar.relative_to(ROOT)} (gitignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
