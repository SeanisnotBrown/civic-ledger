"""INC-13 — Mississippi Tier-2 metrics. The metrics reuse the federal formulas over an
MS-loaded Ctx; these pin recompute-and-match against the committed data/state/ms/
metrics.json and the published-model validity (offline, over committed data)."""

from __future__ import annotations

import json

import pytest

from ingest import ms_metrics
from ingest.export import MS_METRICS_PATH
from ingest.models import MsMemberMetrics, MsMetricsFile


def _committed():
    if not MS_METRICS_PATH.exists():
        pytest.skip("no committed data/state/ms/metrics.json in this checkout")
    return json.loads(MS_METRICS_PATH.read_text(encoding="utf-8"))


def test_ms_metrics_recompute_matches_committed():
    committed = _committed()
    fresh = ms_metrics.build().model_dump()
    assert fresh == committed, "data/state/ms/metrics.json is stale — re-run `ingest ms --force`"


def test_committed_ms_metrics_schema_valid():
    MsMetricsFile.model_validate(_committed())


def test_ms_metric_keys_equal_model_fields():
    assert set(ms_metrics.MS_METRIC_KEYS) == set(MsMemberMetrics.model_fields)


def test_ms_metrics_have_formula_identity():
    built = ms_metrics.build().model_dump()
    assert isinstance(built["schema_version"], int)
    for key, meth in built["methodology"].items():
        assert len(meth["digest"]) == 16, key
        assert meth["text"] and "Source:" in meth["text"], key


def test_ms_enacted_rate_is_bounded_and_real():
    # Sanity: at least one member has enacted bills (a committee chair), and every pct is
    # a valid share or null (R-4) — never a fabricated value.
    members = ms_metrics.build().model_dump()["members"]
    enacted_any = any(m["enacted_rate"]["enacted"] > 0 for m in members.values())
    assert enacted_any
    for m in members.values():
        p = m["enacted_rate"]["pct"]
        assert p is None or (0.0 <= p <= 100.0)
