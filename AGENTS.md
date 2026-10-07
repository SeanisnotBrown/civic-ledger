# AGENTS.md

Read, in this order, before any work:
1. `MISSION.md` — what the site is and why. Before any action ask: does this serve the mission? If not, it does not happen.
2. `IMPLEMENTATIONv3.md` — the only spec. §1 ground rules, §2 ratified decisions, §5 phases.
3. `STATUS.md` — live state: current phase, whether a local data pull is running, what a human owes.

Rules (full text in `IMPLEMENTATIONv3.md` §1):
- Ask the owner when unsure, in plain non-technical language, with each option's consequence in one line. Always for anything evaluative. Nothing evaluative publishes unratified.
- One phase at a time. Acceptance passes before the next phase starts.
- A dirty `git status` here is often a RUNNING local data pull. Read `STATUS.md` "Live facts" before touching anything under `data/`.
- Before pushing run both gates: `uv run ruff check .` and the full pytest line with `CI=true GITHUB_ACTIONS=true` from `STATUS.md`, then the site build and its `test:*` scripts.
- Commit at every passing acceptance: `P<N>: <what>`.
- Update `STATUS.md` before ending any session. Under 50 lines; replace, never append.
- Secrets come from `.env`. Never hardcode, never commit.

Do not read `docs/archive/` or `docs/decisions.md` unless a task sends you there.
