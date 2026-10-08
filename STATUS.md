# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-07 (builder, at Phase 2 acceptance).
## FIRST ACTION NEXT SESSION
Phase 3 (statements pipeline) is open and carries an **evaluative question that must be answered
before any statement publishes: Q-B — the minimum approved statements a member needs before their
"stated priorities" list shows at all.** Ask the owner in plain words, each option's consequence
in one line, and ratify it in §2 before Phase 3's member-page half. Tasks 1–5 (collectors,
archive capture, categorizer) do not depend on Q-B and may start first.
## Current phase
**Phase 2 — ACCEPTANCE PASSED 2026-10-07.** The owner looked at `/` and a member page and said
yes after two rounds of fixes, both ratified in §2. **Phase 3 — Statements pipeline — is now the
current phase**, not started.
## Live facts
1. **Nothing is pushed; push is still PENDING OWNER APPROVAL** — he has never authorised one. 11
   commits wait; run the gates below first. **Lighthouse is the only gate never run locally**
   (Windows temp-dir permission error, not an assertion) and it gates CI on push.
2. **Build: ~13,120 pages, ~16,500 of the 20,000 free-plan file limit.** All seven `test:*` gates
   green, 64 e2e green (axe + 380px), ruff clean, banned-words 0, `verify-recompute` green.
3. **The Congress 119 backfill is FINISHED**, 0 fetch failures: 19,524 of 19,536 bills carry a
   timeline, 11 of the rest have no action on the official record (D104); the regenerate trio has
   run. A dirty `data/` means something NEW is running — find it before touching anything.
4. **House amendment identities are collected**: `ingest vote-amendments` read 637 Clerk XMLs and
   those rows now name the amendment. **Senate amendment sponsors are a documented gap** (§2) —
   the Senate names no sponsor anywhere in its vote XML.
5. **Phase 2 wording is all ratified in §2; nothing unratified anywhere:** headline B + the Q-A
   sentence, the 22-entry motion table and its short lines ("Voted to kill it"), the amendment
   display rule, the Senate gap, recorded roll calls leading "In Congress", the resolving-roll
   rule, the homepage restructure, the title clamp. Nav says "Members"; route stays `/federal`.
6. **A false number was found and fixed:** a passage line took the tally of ANY roll call on that
   bill that day, so `s4668-119` published an amendment's 96–1 as its passage margin. A tally may
   only be a measure's margin when that roll call resolved the measure (§2).
7. **"This week" is deliberately NOT a heading.** 7 days from the record's last date holds 1
   enacted measure and ZERO recorded roll calls; 14 days holds 8 resolved, 2 on a recorded vote,
   so the band keeps 14 days and prints its exact dates. Narrowing it is one constant.
## Open questions (§7)
**Q-A is CLOSED** (§2). **Q-B is live and gates Phase 3's member-page output** — see FIRST
ACTION. **Q-C arrives with Phase 3**, unanswered. **Q-D gates the Phase 5 upcoming-votes block**:
which floor-schedule source to trust; nothing on the site claims a vote date today.
## Owed by a human (owner)
1. **Answer Q-B** (see FIRST ACTION). Blocks the visible half of Phase 3.
2. **Approve the first push.** 11 commits are waiting; run the gates below first.
3. **archive.org keys** — Phase 3 needs them: no live capture, no published statement. Later:
   Workers Paid ($5/mo) for Phases 6–7; Turnstile + Email Sending (P7).
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` →
`uv run ruff check .` → the pytest gate below (~4 GB, ~22 min, never beside a site build) → `cd
site && npm run build` + its seven `test:*` scripts + `npx playwright test`.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov-branch --cov-fail-under=100
```
