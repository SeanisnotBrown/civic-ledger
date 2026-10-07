"""Global constants. Single source of truth for cross-module thresholds.

Spec: `IMPLEMENTATIONv3.md`. Evaluative constants do NOT live here — every
threshold, weight, grade cutoff and grade label is ratified by the owner and
committed to `data/config/thresholds.yaml` with its reason and date (§1 rule
5). What lives here is mechanical: coverage, the k-anonymity floor, and the
symmetry and quality gates.

K_ANON is the single source of truth for k-anonymity; the Worker (Phase 7, not
yet built) must import/mirror this value, and a test will assert equality once
it exists. `tests/test_privacy_accuracy.py` already pins the site's published
copy to it. Symmetry thresholds are read by checks/symmetry.py.
"""

from __future__ import annotations

# --- Coverage -------------------------------------------------------------
# 119th (current) + 118th Congress (`IMPLEMENTATIONv3.md` §3.1).
CONGRESSES: list[int] = [118, 119]

# Covered member set: the Mississippi delegation (5R House, 1 varies; 2 Senate).
# Membership is derived at ingest from congress-legislators filtered on state.
COVERED_STATE: str = "MS"

# --- Privacy (§4.8) -------------------------------------------------------
# k-anonymity floor for any published figure derived from reader data. NOTHING
# READS THIS YET - no reader data is collected, so no gate consumes it. It is
# the ratified number the Phase 7 Worker must mirror, and it equals the figure
# the site publishes today (pinned by tests/test_privacy_accuracy.py).
K_ANON: int = 50

# --- Symmetry thresholds --------------------------------------------------
# Statement curation checks activate once the watchlist median reaches this.
SYMMETRY_MEDIAN_ACTIVATION: int = 5
# Each member's statement count must be >= this fraction of the median.
SYMMETRY_MEMBER_MIN_FRACTION: float = 0.60
# Party mean counts must be within this relative difference.
SYMMETRY_PARTY_MEAN_MAX_REL_DIFF: float = 0.25
# Specificity-scored percentage must be within this many points across parties.
SYMMETRY_SPECIFICITY_MAX_POINT_GAP: float = 10.0

# --- Quality gates --------------------------------------------------------
# CI fails if quarantined records exceed this fraction of a run.
QUARANTINE_MAX_FRACTION: float = 0.02

# V2-11 task 8 — how many TRANSIENT per-bill fetch failures the nightly
# bill-activity DELTA may absorb before the run is called failed. The §6.1
# "nightly failure = last deploy stays live" alarm is reserved for new and
# unexpected problems (the accepted-quarantine.yaml header states that rule;
# D87 is what happens when it is not honored), and a bill that failed to fetch
# keeps the record it already has — nothing false publishes, the projections
# still re-derive, and the next run retries it. A SYSTEMIC failure (a dead API
# key, a bad window) blows through both ceilings and still fails loudly.
# Measured basis: the one-time 19,125-bill backfill ended with 16 transient
# failures (15 TruncatedFetchError, 1 ConnectTimeout) = 0.08%, so a ~400-bill
# night expects ~0.3. The fraction is QUARANTINE_MAX_FRACTION's value on
# purpose (~25x the observed rate); the floor keeps one blip on a thin night
# (20 bills updated) from turning the night red. The ceiling applies to the
# `--since` delta ONLY: a local `--congress` backfill keeps failing nonzero so
# the owner re-runs it.
ACTIVITY_FETCH_FAILURE_MAX_FRACTION: float = 0.02
ACTIVITY_FETCH_FAILURE_MIN_TOLERATED: int = 2

# --- vote_class (§A1) -----------------------------------------------------
# Acceptance ceiling for the `other` class (INC-5).
MAX_OTHER_RATE: float = 0.05
