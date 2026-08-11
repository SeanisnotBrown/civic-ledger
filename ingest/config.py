"""Global constants. Single source of truth for cross-module thresholds.

K_ANON is asserted equal to the Worker's copy by a test (§10.3). Symmetry
thresholds are read by checks/symmetry.py. Congress coverage per Decision D5.
"""

from __future__ import annotations

# --- Coverage -------------------------------------------------------------
# Decision D5: 119th (current) + 118th Congress.
CONGRESSES: list[int] = [118, 119]

# Covered member set: the Mississippi delegation (5R House, 1 varies; 2 Senate).
# Membership is derived at ingest from congress-legislators filtered on state.
COVERED_STATE: str = "MS"

# --- Privacy (§10) --------------------------------------------------------
# k-anonymity threshold for aggregate export. MUST equal the Worker's copy;
# a test asserts equality (§10.3).
K_ANON: int = 50

# --- Symmetry thresholds (§6.5, Decision D1) ------------------------------
# Statement curation checks activate once the watchlist median reaches this.
SYMMETRY_MEDIAN_ACTIVATION: int = 5
# Each member's statement count must be >= this fraction of the median.
SYMMETRY_MEMBER_MIN_FRACTION: float = 0.60
# Party mean counts must be within this relative difference.
SYMMETRY_PARTY_MEAN_MAX_REL_DIFF: float = 0.25
# Specificity-scored percentage must be within this many points across parties.
SYMMETRY_SPECIFICITY_MAX_POINT_GAP: float = 10.0

# --- Quality gates (§6.1) -------------------------------------------------
# CI fails if quarantined records exceed this fraction of a run.
QUARANTINE_MAX_FRACTION: float = 0.02

# --- vote_class (§A1) -----------------------------------------------------
# Acceptance ceiling for the `other` class (INC-5).
MAX_OTHER_RATE: float = 0.05
