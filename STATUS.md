# STATUS.md — live state (keep under 50 lines)
Read `MISSION.md`, then `IMPLEMENTATIONv3.md`, then this. Replace lines, never append. **Updated** 2026-10-07 (builder, at P2 acceptance; Q-B ratified).
## FIRST ACTION NEXT SESSION
**Start Phase 3 at §5 task 1** — `data/config/ai.yaml` and `ingest/ai.py`, the one module every AI
call goes through, logging model, prompt version and input hash. Only the archive.org keys block
Phase 3 (task 3). Q-B is ratified (§2): 5 approved statements across 3+ topics before a priorities
list shows; below the bar the timeline still shows each statement and no list appears.
## Current phase
**Phase 3 — Statements pipeline. Current, not started.** Phase 2 acceptance PASSED 2026-10-07
(the owner looked at `/` and a member page and said yes, after two rounds of fixes ratified in
§2). Q-B is ratified, so Phase 3 has no open evaluative question.
## Live facts
1. **Nothing is pushed; push is still PENDING OWNER APPROVAL** — he has never authorised one. 12
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
**Q-A and Q-B are both CLOSED** (§2; Q-B answered 2026-10-07). **Q-C arrives with Phase 4** (fixed
bars per category), unanswered. **Q-D gates the Phase 5 upcoming-votes block**: which
floor-schedule source to trust; nothing on the site claims a vote date today.
## Owed by a human (owner)
1. **archive.org keys.** Phase 3 task 3 needs them: no live capture, no published statement.
2. **Approve the first push.** 12 commits are waiting; run the gates below first.
3. **The statement source lists** — `data/config/statement-sources.yaml` is owner-maintained: the
   press-page and campaign-issue URLs per member. Later: Workers Paid ($5/mo) for Phases 6–7;
   Turnstile + Email Sending (P7).
## Before any data commit or push
`uv run ingest events && uv run ingest topics && uv run export` → `uv run verify-recompute` →
`uv run ruff check .` → the pytest gate below (~4 GB, ~22 min, never beside a site build) → `cd
site && npm run build` + its seven `test:*` scripts + `npx playwright test`.
```
CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov-branch --cov-fail-under=100
```
