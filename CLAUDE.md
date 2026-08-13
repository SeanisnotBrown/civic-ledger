# CLAUDE.md
Read IMPLEMENTATIONv2.md in full before any work. It is the sole
specification (v1 is archived under docs/archive/2026-08-13-pre-v2/).

Rules:
- Follow §0 ground rules exactly. **Ask the owner when unsure — in plain,
  non-technical language** — especially anything evaluative (what counts as
  good/poor performance, thresholds, grade wording). Never publish an
  evaluative number he hasn't ratified (§0.8).
- Track state in docs/PROGRESS.md: current increment, acceptance status,
  blocked H-tasks. Update it before ending any session.
- One increment at a time (V2-N). Do not start V2-N+1 until V2-N acceptance
  passes, except increments marked ∥. Blocking gates: V2-1 before V2-2/V2-5;
  V2-7 (privacy truth) before V2-8/V2-9 (any collection).
- Commit at every passing acceptance criterion with message "V2-N: <what>".
- Secrets come from .env — never hardcode, never commit.
