# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-07 (builder, end of the P2 review-round-2 session).
## FIRST ACTION NEXT SESSION
Ask the owner for his **yes or no on `/` and one member page**. It is the only thing left in
Phase 2 and nothing else may start before it. Serve the built site: `cd site && npm run preview`
→ `/`, `/m/A000055/1` (House), `/m/A000382/1` (Senate), `/congress`. If he says no he gives
fixes and the round repeats. If yes: commit `P2: acceptance`, then read §5 Phase 3 and stop at
its first open question.
## Current phase
**Phase 2 — acceptance PENDING, not passed.** Every mechanical criterion is green. The owner has
reviewed twice and said no twice; both rounds are applied and ratified in §2. Phase 3 is blocked.
## Live facts
1. **Nothing is pushed, and push is PENDING OWNER APPROVAL** — he has never authorised one.
   `git status` is clean. Run both gates first (§ below). **Lighthouse is the only gate never run
   locally** (Windows temp-dir permission error, not an assertion) and it gates CI on push.
2. **Build: ~13,120 pages, ~16,500 of the 20,000 free-plan file limit.** All seven `test:*` gates
   green, 64 e2e green (axe + 380px), ruff clean, banned-words 0, `verify-recompute` green.
3. **The Congress 119 backfill is FINISHED**, 0 fetch failures: 19,524 of 19,536 bills carry a
   timeline, 11 of the rest have no action on the official record (D104). The regenerate trio has
   run. A dirty `data/` now means something NEW is running — find it before touching anything.
4. **House amendment identities are collected**: `ingest vote-amendments` read 637 Clerk XMLs and
   those rows now name the amendment. **Senate amendment sponsors are a documented gap** (§2) —
   the Senate names no sponsor anywhere in its vote XML.
5. **Ratified this session, all in §2; nothing unratified anywhere:** headline B with the Q-A
   sentence beneath it; the 22-entry motion table and its per-position short lines ("Voted to kill
   it"), both read and approved line by line; the amendment display rule; the Senate gap; recorded
   roll calls leading "In Congress"; the resolving-roll rule; the restructured homepage; the
   two-line title clamp. Nav label is "Members" — the ROUTE stays `/federal`.
6. **A false number was found and fixed:** a passage line took the tally of ANY roll call on that
   bill that day, so `s4668-119` published an amendment's 96–1 as its passage margin. A tally may
   now only be a measure's margin when that roll call resolved the measure (§2).
7. **"This week" is deliberately NOT a heading.** 7 days from the record's last date holds 1
   enacted measure and ZERO recorded roll calls; 14 days holds 8 resolved, 2 on a recorded vote.
   The band keeps 14 days and prints its exact dates. Narrowing it is one constant.
## Open questions (§7)
**Q-A is CLOSED** — homepage intro and headline, ratified in §2. **Q-D gates the Phase 5
upcoming-votes block**: which floor-schedule source to trust. Nothing on the site claims a vote
date today. Q-B and Q-C arrive with Phase 3, unanswered.
## Owed by a human (owner)
1. **Yes or no on `/` and one member page.** The last Phase 2 criterion. See FIRST ACTION.
2. **Approve the first push.** Commits are waiting; run the gates below first.
3. Workers Paid ($5/mo), Phases 6–7; Turnstile + Email Sending (P7); archive.org keys (P3).
## Before any data commit or push
Order: `uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute`
→ `uv run ruff check .` → the pytest gate below (~4 GB, ~22 min, never beside a site build) →
`cd site && npm run build` + its seven `test:*` scripts + `npx playwright test`.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov-branch --cov-fail-under=100
```
