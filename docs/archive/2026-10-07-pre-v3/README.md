# Archive — 2026-10-07 — pre-v3 documents

On 2026-10-07 the owner reset the project's direction after a review found
the build had drifted into bill-tracking plumbing while the core (what
politicians say versus what they do, graded) was unbuilt. The documents here
were written for the old direction. They are superseded, not deleted, and
keep their git history (`git mv`).

**Do not read these before work.** `MISSION.md`, `IMPLEMENTATIONv3.md`, and
`STATUS.md` at the repository root are the only required reading.

| Archived file | What it was | Replaced by |
|---|---|---|
| `IMPLEMENTATIONv2.md` | The second build spec (2026-08-13 to 2026-10-07). | `IMPLEMENTATIONv3.md` |
| `PROGRESS.md` | ~2,500-line session-state ledger. Its live operational facts (the running Congress 119 backfill, the stop loop, the CI gate line) were carried into `STATUS.md`. | `STATUS.md` |
| `HUMAN-TASKS.md` | Table of owner-only tasks, written in old increment names. Still-live items (paid hosting plan, Turnstile keys, email binding, optional archive.org keys) were carried into `STATUS.md`. | `STATUS.md` "Owed by a human" |
| `plan-subscriptions-and-alerts.md` | Plan for accounts, topic subscriptions, and alerts. Its ratified choices (daily digest, email first, official topic vocabulary, all bills tracked, pages only for voted bills) still hold and are reflected in `IMPLEMENTATIONv3.md` §4.7 and Phase 7. | `IMPLEMENTATIONv3.md` Phase 7 |
| `kickoff-v2.md` | Session kickoff prompt for the old spec. | `CLAUDE.md` / `AGENTS.md` |
| `draft-v2-7-privacy-claims.md` | Evidence pack for the old privacy-page rewrite. The page is rewritten again in Phase 1. | `IMPLEMENTATIONv3.md` §4.8, Phase 1 task 2 |

Kept in place because they describe the live system or are append-only
history: `docs/decisions.md` (archive, no longer required reading),
`docs/data-contract.md`, `docs/correction-process.md`, `CONTRIBUTING.md`
(rewritten in Phase 1).
