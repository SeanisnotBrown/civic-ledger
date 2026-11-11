# Owner questions, 2026-11-11 (nightly fix, branch `fix-nightly-senate-tally`)

Written by the copilot-driven builder while Sean was away. Nothing here is
evaluative; each question has a default that was taken (reversible) or that
waits on you.

## What broke, in one paragraph

The nightly has published nothing since 2026-11-09. Two new Senate votes (roll
257 on 2026-11-09, roll 258 on 2026-11-10, both on H.R. 2347) were refused
because two senators who voted on them, Jon Husted (OH) and Ashley Moody (FL),
look like they had already left office. They had not. Both were appointed to
their seats, and the roster we copy (congress-legislators) records their end
date as 2026-11-03, the day of the special election, which its own README says
is only the *expected* date: the real one replaces it after the winner is sworn
in. The vote counts themselves were fine (73-25 and 62-21, matching the
Senate's own summary). The log calls these "roll/tally validation failures",
but that is the generic label; the actual reason was "voter not in roster".

## Q1. How should the nightly handle an appointed senator still serving after the special election? (default TAKEN: A)

- **A (taken). Keep their votes coming in.** When the roster says a senator who
  is still serving was appointed and their end date is only the expected
  election date, the nightly treats that date as "not yet known" until the
  roster records the real one. Their member page keeps the roster's date as
  written. Consequence: Senate votes publish again; only these 2 of 639 member
  files change (one added field each).
- **B. Add each refused vote to the accepted-quarantine list.** Consequence:
  every new Senate vote this lame-duck session would need its own entry from
  you, night after night (all 100 senators vote on each roll), and none of those
  votes would publish until the roster catches up.
- **C. Skip such votes quietly and retry each night.** Consequence: Senate votes
  silently stop appearing on the site for weeks, with no notice to readers.

Recommended: A. Reversible: one commit to undo.

## Q2. Catch-up for the bill-activity window (WAITS ON YOU; nothing was run)

The nightly only looks back 36 hours for bill activity. Uncovered so far:
2026-11-07 11:57 UTC to 2026-11-08 02:00 UTC (the 11-08 senate.gov hard-fail),
and everything after 2026-11-09 14:00 UTC until the first passing run after
this fix lands. If the fix is on master before the 2026-11-12 run starts
(runs have been starting 11:39 to 13:47 UTC), that run's window starts about
2026-11-11 01:00 UTC: about 1.5 days missed (plus the 14 h hole). If it lands
after that run, about 2.5 days missed (plus the 14 h hole).

- **A. One manual run with a longer look-back** (`since_hours` = hours since
  2026-11-07 11:57 UTC, rounded up; about 122 if run around 2026-11-12 13:00
  UTC). Consequence: the gap is closed in one run; you start it.
- **B. Leave it.** Consequence: bills that changed in those hours keep their
  older record until something else touches them.

Recommended: A, after the fix is merged and one scheduled run has passed.

## Flag: fixed on the branch (copilot call, 2026-11-11)

Before the fix, the built site said "In office since 2025" then "No longer
serving." on the Husted (H001104) and Moody (M001244) pages, and the homepage
state finder listed only Moreno for Ohio and only Scott for Florida (537 members
"currently in office"). Cause: the site's `holdsSeatAsOf` compared the raw term
`end` (the projected 2026-11-03) with the dataset date. Both senators voted on
2026-11-09 and 2026-11-10, so this was a false statement (rule 0).

Copilot call: `holdsSeatAsOf` now treats an `end_projected` term as open, the same
rule as the ingest. No wording changed: the existing "No longer serving." line
simply stops appearing for them, and they return to the finder (539 in office).
Reversible in one commit.
