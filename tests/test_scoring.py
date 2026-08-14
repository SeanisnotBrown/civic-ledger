"""V2-4 tests — grades (ingest/scoring.py). Offline; build() is pure over injected
config + metrics + members fixtures. §8 gate: 100% branch on scoring.py."""

from __future__ import annotations

from ingest import scoring
from ingest.scoring import _band_for, build, build_all

# The ratified attendance config, mirrored as a fixture (not read from disk).
CONFIG = {
    "formula_version": 1,
    "grades": {
        "attendance": {
            "metric": "attendance", "field": "pct", "ratified": "2026-08-13",
            "citation": None, "justification": "x", "min_eligible": 50,
            "exception_label": "Too few votes to grade",
            "bands": [
                {"grade": "A", "min": 99, "label": "A — Strong attendance"},
                {"grade": "B", "min": 97, "label": "B — Good attendance"},
                {"grade": "C", "min": 95, "label": "C — Fair attendance"},
                {"grade": "D", "min": 90, "label": "D — Weak attendance"},
                {"grade": "F", "min": 0, "label": "F — Poor attendance"},
            ],
        }
    },
}
BANDS = CONFIG["grades"]["attendance"]["bands"]


def _mem(bid, state="CA", chamber="house"):
    return {"id": bid, "state": state, "chamber": chamber}


def _att(pct, eligible=500):
    return {"attendance": {"pct": pct, "eligible": eligible}}


def test_each_band_is_assigned():
    members = {b: _mem(b) for b in ("A1", "B1", "C1", "D1", "F1")}
    metrics = {"A1": _att(99.0), "B1": _att(97.0), "C1": _att(95.0),
               "D1": _att(90.0), "F1": _att(85.0)}
    gf = build(metrics, members, CONFIG)
    got = {b: gf.members[b].grade for b in members}
    assert got == {"A1": "A", "B1": "B", "C1": "C", "D1": "D", "F1": "F"}
    assert gf.members["A1"].label == "A — Strong attendance"
    assert gf.members["F1"].label == "F — Poor attendance"
    assert gf.exceptions == {}
    assert gf.formula_version == 1 and gf.ratified == "2026-08-13"


def test_delegate_no_record_and_min_service_exceptions():
    members = {
        "DEL": _mem("DEL", state="PR"),       # non-voting delegate → inherited D66
        "NEW": _mem("NEW"),                     # null pct → no eligible rolls
        "SHORT": _mem("SHORT"),                 # served too briefly
        "OK": _mem("OK"),                       # graded normally
    }
    metrics = {
        "DEL": _att(95.0), "NEW": _att(None, eligible=0),
        "SHORT": _att(100.0, eligible=40), "OK": _att(98.0, eligible=500),
    }
    gf = build(metrics, members, CONFIG)
    assert gf.exceptions == {"DEL": "delegate", "NEW": "no_record", "SHORT": "min_service"}
    assert set(gf.members) == {"OK"} and gf.members["OK"].grade == "B"
    assert gf.exception_label == "Too few votes to grade"


def test_band_for_boundaries():
    assert _band_for(99, BANDS)["grade"] == "A"      # exactly the A cutoff
    assert _band_for(98.99, BANDS)["grade"] == "B"   # just under A
    assert _band_for(90, BANDS)["grade"] == "D"      # exactly the D cutoff
    assert _band_for(89.99, BANDS)["grade"] == "F"   # just under D → the min-0 band
    assert _band_for(0, BANDS)["grade"] == "F"
    assert _band_for(-1, BANDS)["grade"] == "F"      # below all bands → clamps, never crashes


def test_bands_echoed_from_config():
    gf = build({}, {}, CONFIG)
    assert [(b.grade, b.min, b.label) for b in gf.bands] == [
        (b["grade"], b["min"], b["label"]) for b in BANDS
    ]
    assert gf.members == {} and gf.exceptions == {}  # empty roster → empty grade file


def test_build_all_has_attendance_only():
    all_g = build_all({}, {}, CONFIG)
    assert set(all_g) == {"attendance"}


def test_run_loads_committed_config_and_writes(monkeypatch):
    # run() reads the committed thresholds + dataset (covering _load_thresholds /
    # _load_inputs) then exports; stub only the writer so the test touches no files.
    from ingest import export

    captured: dict[str, list[str]] = {}
    monkeypatch.setattr(
        export, "export_grades",
        lambda built, **kw: captured.setdefault("keys", sorted(built)) and [],
    )
    assert scoring.run() == 0
    assert captured["keys"] == ["attendance"]
