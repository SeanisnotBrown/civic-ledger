"""V2-4 — grades: the designated Tier-3 scoring module (§6.8, SD-26).

This is the ONLY place a published evaluative label is produced. It reads the
owner-ratified thresholds (`data/config/thresholds.yaml`, §0.8) plus the committed
`data/metrics.json` + `data/members`, and writes `data/grades/{category}.json`.
Every label it emits appears verbatim in the config — the §6.8 guard
(`checks/integrity.py` + `site/scripts/check-grade-labels.mjs`) enforces it, so no
grade wording can ship that the owner did not ratify.

Discipline:
  * PURE + OFFLINE — reads only the committed dataset + config, never the API, so a
    third party recomputes every grade from the public repo (verify-recompute
    invariant 6). No wall-clock: provenance is `formula_version` + the `ratified`
    date, so a grade record is byte-stable and the nightly quiet-night gate holds.
  * RATIFIED VALUES ONLY — this module contains NO evaluative number of its own. The
    cutoffs, the minimum-service line, and the exact label words all come from the
    committed config. Change a grade → change the config (with the owner), not code.

V2-4 grades ONE category, attendance, on fixed bars. Members who served too few
eligible rolls (`min_eligible`), non-voting delegates (inherited D66 — their eligible
set is not comparable), and members with no attendance value are NOT graded off a
thin/absent record: they go in the published `exceptions` map with a mechanical
reason, so §6.5 grading-coverage holds (every covered member graded OR excepted,
never silently dropped). The overall composite grade is deferred until its formula is
ratified (§0.8) — this module composes nothing across metrics yet.
"""

from __future__ import annotations

import json

from ingest.cache import repo_root
from ingest.models import GradeBand, GradeEntry, GradesFile
from ingest.sources.legislators import VOTING_STATES


def _load_thresholds() -> dict:
    """The committed, owner-ratified evaluative config. `yaml` is a project dep."""
    import yaml

    path = repo_root() / "data" / "config" / "thresholds.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_inputs() -> tuple[dict, dict]:
    """(metrics.members, members-by-bioguide) from the committed dataset."""
    root = repo_root()
    metrics = json.loads((root / "data" / "metrics.json").read_text(encoding="utf-8"))["members"]
    members: dict[str, dict] = {}
    for path in sorted((root / "data" / "members").glob("*.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        members[m["id"]] = m
    return metrics, members


def _band_for(value: float, bands: list[dict]) -> dict:
    """The first band (config order is top-down, highest `min` first) whose `min` the
    value meets. The last band's `min` is 0, so this always returns a band."""
    for band in bands:
        if value >= band["min"]:
            return band
    return bands[-1]


def build(metrics: dict | None = None, members: dict | None = None,
          config: dict | None = None) -> GradesFile:
    """Grade the attendance category for every covered member from ratified thresholds.
    Loads the committed dataset + config unless fixtures are injected (tests)."""
    if config is None:
        config = _load_thresholds()
    if metrics is None or members is None:
        metrics, members = _load_inputs()

    cfg = config["grades"]["attendance"]
    metric, field, min_eligible = cfg["metric"], cfg["field"], cfg["min_eligible"]
    bands = cfg["bands"]

    graded: dict[str, GradeEntry] = {}
    exceptions: dict[str, str] = {}
    for bid, m in members.items():
        mv = metrics.get(bid, {}).get(metric) or {}
        value = mv.get(field)
        eligible = mv.get("eligible")
        if m.get("state") not in VOTING_STATES:
            exceptions[bid] = "delegate"          # inherited D66 — not comparable
        elif value is None:
            exceptions[bid] = "no_record"         # no eligible rolls yet (pct is null)
        elif eligible < min_eligible:             # value is present ⇒ eligible >= 1
            exceptions[bid] = "min_service"       # served too briefly to grade
        else:
            band = _band_for(value, bands)
            graded[bid] = GradeEntry(value=value, grade=band["grade"], label=band["label"])

    return GradesFile(
        category="attendance",
        metric=metric,
        field=field,
        formula_version=config["formula_version"],
        ratified=cfg["ratified"],
        min_eligible=min_eligible,
        bands=[GradeBand(grade=b["grade"], min=b["min"], label=b["label"]) for b in bands],
        exception_label=cfg["exception_label"],
        members=graded,
        exceptions=dict(sorted(exceptions.items())),
    )


def build_all(metrics: dict | None = None, members: dict | None = None,
              config: dict | None = None) -> dict[str, GradesFile]:
    """Every graded category → its GradesFile. One category (attendance) in V2-4."""
    return {"attendance": build(metrics, members, config)}


def run(argv: list[str] | None = None) -> int:
    """Write data/grades/{category}.json for every graded category (pure/offline)."""
    from ingest.export import export_grades

    paths = export_grades(build_all())
    print(f"civic-ledger grades: wrote {len(paths)} grade file(s) to data/grades/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
