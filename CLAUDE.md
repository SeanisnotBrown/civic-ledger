# CLAUDE.md
Read IMPLEMENTATIONv2.md in full before any work. It is the sole
specification (v1 is archived under docs/archive/2026-08-13-pre-v2/).

Rules:
- Follow §0 ground rules exactly. **Ask the owner when unsure — in plain,
  non-technical language** — especially anything evaluative (what counts as
  good/poor performance, thresholds, grade wording). Never publish an
  evaluative number he hasn't ratified (§0.8).
- Track state in docs/PROGRESS.md: current increment, acceptance status,
  blocked H-tasks. Update it before ending any session. **Read its
  "READ THIS FIRST — the three live facts" section at the top BEFORE touching
  anything**: it says whether a long-running local ingest is currently writing
  `data/`, whether uncommitted data in the tree is deliberate, and what the last
  CI run did. A dirty `git status` in this repo is often a RUNNING PROCESS, not
  abandoned work — do not clean it up or commit it without reading that section.
- Before pushing, run BOTH gates (each has drawn blood — D94, D96 addendum):
  `uv run ruff check .` (with the dot — a directory you edited is not enough) and
  the full pytest line with `CI=true GITHUB_ACTIONS=true` that PROGRESS.md
  records. A green local `uv run pytest` is not evidence CI is green.
- One increment at a time (V2-N). Do not start the next until the current
  acceptance passes, except increments marked ∥. **Current priority (owner,
  2026-09-23, SD-32): V2-11 → V2-7 → V2-8 → V2-12 → V2-13** per
  docs/plan-subscriptions-and-alerts.md (read it after the spec); V2-6 is
  deferred. Blocking gates: V2-1 before V2-2/V2-5; V2-7 (privacy page true)
  before anything that stores user data (V2-8/V2-9/V2-12/V2-13). The site
  MAY read and collect the user data its features need (SD-32); the gate
  only orders the truthful /privacy rewrite ahead of the storage.
- Commit at every passing acceptance criterion with message "V2-N: <what>".
- Secrets come from .env — never hardcode, never commit.
