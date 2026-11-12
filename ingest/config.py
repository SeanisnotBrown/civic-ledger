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

# The scheduled bill-activity window (`--since-published`, 2026-11-11). The nightly
# covers everything since the LAST PUBLISHED nightly: hours since the committed
# data/manifest.json `generated_at` + MARGIN, never less than FLOOR. A night that
# fails publishes no manifest, so the next run widens by itself and no manual
# catch-up is needed (the fixed 36 h window lost 2026-11-07 11:57 -> 11-08 02:00 and
# 11-09 14:00 -> the next passing run). A stale manifest (a quiet night commits
# nothing) only widens the window; FLOOR keeps it from ever being narrower than the
# fixed 36 h it replaces.
#   FLOOR 36: the window every scheduled run used since 2026-10-08.
#   MARGIN 12: that window's slack over the 24 h cron (36 - 24). It must exceed the
#     gap between bill-activity and export in the published run (~12 min; ~3.5-4 h
#     on Sundays, when `legislation --full` runs between them).
#   MAX 192: the largest window ever run, the owner's 2026-10-29 catch-up: 843 bills,
#     whole job 2 h 47 min. Worst case at D88's 435 bills/day is ~3,480 bills: ~1 h
#     if held (1 request each at 1 req/s), ~3.9 h if all new (4 requests), inside
#     GitHub's 6 h job limit. The longest gap between published nightlies so far is
#     161 h (2026-10-23 -> 10-30), ~179 h with margin at the next scheduled run.
#     Above MAX the run fails loudly before fetching anything; a manual dispatch with
#     an explicit `since_hours` is the override and is not capped.
ACTIVITY_WINDOW_FLOOR_HOURS: float = 36.0
ACTIVITY_WINDOW_MARGIN_HOURS: float = 12.0
ACTIVITY_WINDOW_MAX_HOURS: float = 192.0

# The same ceiling for the nightly `ingest legislation` member sweep. 2026-10-07
# (nightly 37652899299): three of 639 member requests to api.congress.gov returned
# ReadTimeout — each already retried five times with 2s->60s backoff in
# ingest/cache.py — and `legislation` had NO ceiling at all, so one slow endpoint
# returned 1, `set -e` stopped the night, and a whole day published nothing. That
# is exactly the alarm-fatigue failure the ACTIVITY_* constants above exist to
# prevent; bills and bill-activity already absorbed it and legislation did not.
# A member whose fetch failed keeps the record it already has (export is never
# reached), and the next run retries it. 2% of the 639-member roster is ~12.
# IMPORTANT: this ceiling covers TRANSIENT FETCH failures only. A
# `_count_regressions` hit — a congress that had records dropping to zero — is a
# value-#1 truncation signal, never transient, and fails the run at any count.
LEGISLATION_FETCH_FAILURE_MAX_FRACTION: float = 0.02
LEGISLATION_FETCH_FAILURE_MIN_TOLERATED: int = 2

# How long `ingest senate-votes` tolerates a senate.gov block on its vote MENUS
# before failing the night again. Owner ruling 2026-10-29: from 2026-10-24
# senate.gov's firewall returned 403 to the nightly runner (even the homepage), and
# because `senate-votes` failed, six nights published nothing at all - House votes
# and bill activity included. While ONLY the four menu fetches fail with an HTTP
# status error, the run exits 0 and keeps data/quality/senate-outage.json, which
# puts the "Senate votes shown through ..." line on the site (rule 0: the reader is
# told the Senate record is behind). Past this many days in a row the run fails
# hard, so a block that never lifts cannot hide behind a green nightly. Tally,
# validation, gap and per-roll failures were never covered by this and stay fatal.
SENATE_MENU_OUTAGE_MAX_DAYS: int = 14

# --- vote_class (§A1) -----------------------------------------------------
# Acceptance ceiling for the `other` class (INC-5).
MAX_OTHER_RATE: float = 0.05
