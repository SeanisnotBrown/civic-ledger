"""INC-10 tests — the Tier-3 guard (§5). A metric function must never consume
another metric's output; the AST check over ingest/metrics.py enforces it. Tested
against source fixtures + the real committed metrics module.
"""

from __future__ import annotations

from ingest.checks.integrity import metrics_tier3_guard, tier3_violations

_CLEAN = '''
def attendance(votes): return len(votes)
def _helper(x): return x * 2          # shared helper, not a metric — allowed
def party_unity(votes): return _helper(len(votes))
METRICS = {"attendance": attendance, "party_unity": party_unity}
'''

_VIOLATION = '''
def attendance(votes): return len(votes)
def composite(votes): return attendance(votes) + 1   # consumes another metric
METRICS = {"attendance": attendance, "composite": composite}
'''

_RECURSION_OK = '''
def attendance(votes, i=0):
    return attendance(votes, i + 1) if i < 1 else len(votes)   # self-call is fine
METRICS = {"attendance": attendance}
'''

_NO_REGISTRY = '''
def attendance(votes): return len(votes)
def composite(votes): return attendance(votes)
'''


def test_clean_module_has_no_violations() -> None:
    assert tier3_violations(_CLEAN) == []


def test_metric_calling_metric_is_flagged() -> None:
    v = tier3_violations(_VIOLATION)
    assert len(v) == 1
    assert "composite() calls metric attendance()" in v[0]


def test_self_recursion_is_allowed() -> None:
    assert tier3_violations(_RECURSION_OK) == []


def test_no_registry_is_noop() -> None:
    # No METRICS dict → nothing to guard (e.g. metrics.py not written yet).
    assert tier3_violations(_NO_REGISTRY) == []


def test_real_metrics_module_is_clean() -> None:
    # Whatever exists in ingest/metrics.py today must pass (no-op if absent).
    assert metrics_tier3_guard() == []
