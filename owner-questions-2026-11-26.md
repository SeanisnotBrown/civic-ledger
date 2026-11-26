# Questions for Sean, 2026-11-26

Copilot-authored overnight 2026-11-25/26 while Sean slept. Sean granted at 23:38 CT: the copilot makes the best reversible call on anything pending his input; he reviews in the morning.

Nothing here publishes anything evaluative. Items marked "LIVE" are already on the site and can be changed or undone.

## A. What landed on the live site tonight (all merged to master)

1. **PR #5, nightly retries.** When LegiScan has a short outage (a 5xx or timeout), the nightly update now tries again a few times before giving up. Before, one bad minute killed the whole night (it did on 11-16).
2. **PR #4, no more holes after a missed night.** The bill-activity update now reaches back to the last night that actually published. A missed night no longer leaves bills stale.
3. **The catch-up run (you approved it).** One manual run reached back 463 hours. It saw 3,288 bills (2 new, 3,286 refreshed), had 0 fetch failures, and published as `1ecc9b7e8`. The four old holes are filled.
4. **PR #2, campaign issue-page collector (task 2c).** It collects what members' campaign sites say about issues. The campaign URLs were researched by the copilot and **you have not reviewed them** (see B4).
5. **PR #6, your rulings on questions 2 and 3.** A refused Senate vote file no longer fails the night, and a Mississippi failure no longer stops the federal update. Details of the copilot's wording choices are in B.

## B. Copilot calls already LIVE, to confirm or change

1. **A refused Senate vote file is skipped only when the Senate site answers "403" (refused).** Any other error still fails the night. Consequence of changing it: skipping more kinds of errors would hide real breakage; skipping fewer fails more nights.
2. **Site sentence when a vote is skipped:** "Our record is also missing N Senate vote(s) for the same reason." It appears next to the existing Senate notice. Consequence: you can reword it.
3. **Mississippi footer:** "Federal data last updated <date>." and "Mississippi data last updated <date>." The Mississippi date is when the Mississippi data last *changed*, not when we last checked. Consequence: a quiet Mississippi week shows an older date, which is accurate.
4. **The campaign URLs in PR #2.** Consequence: if any URL is wrong, a member's campaign statements could be filed under the wrong person. Nothing from them can publish without your review; they are collected, not shown.

## C. Decisions that move Phase 3, ranked by what they unblock

1. **Review the 60 set-2 labels (about 1 hour).** This unblocks the quality check (Q-K) on the new AI prompts, and with it everything below.
   - Sheet: `data/raw/labeling/2026-11-26-set-2-review-sheet.md`. You edit the copy `data/raw/labeling/2026-11-26-eval-set-2-for-owner.csv`.
   - The sheet walks you through the 19 rows where the AI and the label disagree, close calls first.
   - **A real result needs ALL 60 rows marked.** If even one row is unmarked, the report says "not assessed". How many of the 41 agreeing rows you look at before marking them is your call. Only mark rows you looked at.
   - **To mark a row: in its `notes` cell, DELETE the text `owner-unreviewed (...)` and type `OWNER-REVIEWED` in its place.** Adding the word alone does nothing, because the old flag wins.
   - Save as "CSV UTF-8". Then run, from the project folder:
     `uv run ingest prompt-eval --labels data/raw/labeling/2026-11-26-eval-set-2-for-owner.csv --cap 0.25 --out docs/research/2026-11-26-prompt-eval-set-2-owner.md`
     It should cost $0 (the AI answers are saved). It also overwrites the saved measurement file `data/quality/categorizer-precision.json`.
   - Consequence: pass with no party-gap flag = the new prompts can merge; fail = the prompts get changed, nothing publishes.
2. **The Record party gap.** The new AI first-pass check rejects more Republican than Democratic Congressional Record statements: it keeps 80.9% of Democrats' and 68.7% of Republicans' (a 12.2-point gap). Rejected, that is D 19.1% / R 31.3%. The run's own stop rule fires because R is rejected 1.64 times as often as D (the stop is at 1.5). Press releases are even (D 73.4%, R 75.5%). Facts: `docs/research/2026-11-26-triage-party-gap-v2.md` (branch `p3-party-gap-v2`). The gap sits in three places: Senate floor speeches (D 70.0% vs R 42.1% kept), Extensions of Remarks (D 64.7% vs R 5.8%), and Senate amendment filings (D 88.4% vs R 69.9%). The House floor is even. Only 4 senators per party sit behind the Senate rows, so the 12.2 is not a tight number. Five options:
   1. **Leave it and rely on the 60-row checks.** Fastest. Consequence: the second labeled set has only 6 D and 6 R Record rows, so it cannot settle a Record-only gap, and a real run stops at the fairness check unless you accept the flag.
   2. **You hand-label a small Record-only sample.** Settles whether the rejections are right. Consequence: your time (20 rows is good to about plus or minus 22 points, 50 rows to 14, 100 rows to 10); no number can be computed without your labels.
   3. **Re-run the breakdown on the real prompt's results.** Already done, $0 (it is that document). Consequence: nothing more to compute; whether the AI is *right* is only answered by your labels.
   4. **A free rule that drops tribute-style Record items before any AI.** Consequence: the gap narrows only from 12.2 to 8.7 points, the stop still fires, it moves just 4 to 7 statements, and it is a filter change that needs your ratification.
   5. **Report Record and press separately, and Extensions apart from floor speech.** Consequence: no statement or dollar changes; the stop still fires unless you accept it.
   - **Copilot recommendation, not reviewed by you:** do option 5 now (free), do option 2 on only the Senate-floor and Extensions rows before a real run, and skip option 4.
3. **Look at the 579-item preview queue.** It is the first batch of statements the AI categorized, for your approve / edit / reject. **It cannot publish**: preview items never reach member pages. To open it: in PowerShell in the project folder run `uv run curate app`, then open http://127.0.0.1:5000/review (steps in `PREVIEW-HOW-TO.txt`; this worked at 02:40 CT: 579 waiting). Stop with Ctrl+C. Consequence: your answers are the first real approvals and show whether the AI's suggestions are worth your time.
4. **A capped real categorizer run, after C1 and C2.** At 25 statements per member it is about 982 calls, about $25.5 in all, of which 579 are already in the preview queue and **403 are not yet queued (about $10.5)**. It is over the default $5 cap, so it needs your OK and a cap for that one run. Consequence: until you say yes nothing is spent.

## D. Preview branches waiting for a merge yes/no

None of these deploy. Each is on GitHub as a branch and was built by the copilot.

1. **`p3-party-gap-v2`** (`b42c60f41`): the party-gap analysis above. Docs only. Read: `docs/research/2026-11-26-triage-party-gap-v2.md`.
2. **`checks-banned-words-narrow`** (`c3e4a3b74`): a narrower banned-words scan. About 9 to 11 times faster on a 5,521-file sample (about 17 to 19 s down to 1.6 to 1.9 s), same coverage. The full-repo timing is still "TBD" in the doc, so it needs one more copilot turn before you merge. Side question: `.xml` files (2,695 in the build, including `feed.xml`) are not scanned today; adding them would be stricter. Consequence: yes = faster gate (the old check was 16 to 21 min of a 25-min test run); the `.xml` addition could flag new wording. Read: `docs/research/2026-11-26-banned-words-narrowing.md` (on that branch).
3. **`p3-aes-14-29-preview`** (`fea51025a`): AES-14 puts the four "Not yet graded" cards and the stated-priorities panel into two closed sections after the recorded work. AES-29 gives action rows one pattern: status and date, the bill title in bold, the government's action text, then links. The only new wording is "Show the full action" (copilot-authored). Sub-choice: the bars sit before the activity timeline. Consequence: you choose apply, change or reject; bill titles add about 100 bytes to each member-page row. Read: `docs/design/2026-11-26-aes-14-29-preview.md` (16 before/after screenshots).
4. **`site-public-repo-claims-preview`** (`75e9ece4e`): restores sentences on /privacy and /corrections that are true now that the repo is public (since 2026-10-13): public-commit wording, the repo link, per-commit links, issue and history links. Two old claims were deliberately not restored because they are false today. Two things you should know: **reports now go to GitHub issues, and nobody may be watching that tracker**; and "never force-pushes" is a practice, not an enforced rule, because `master` has no branch protection. Consequence: merging makes the site promise a way to report errors; if you won't watch issues, delete the "Report a correction" link and the "open an issue" sentence. Read: `docs/research/2026-11-26-public-repo-claims-preview.md` (on that branch).

## E. Still owed by you (unchanged)

1. A private GitHub repo for the review-log backup (`REVIEW_LOG_BACKUP_REMOTE`). Consequence: until then your review answers exist only on this computer.
2. 13 eligible statements left uncategorized at the $20 cap: about $0.35 more AI spend, your call.
3. AES wording (D3's new phrase and the other preview wording above).
4. Social media (task 2d): nothing built.

## F. Housekeeping

1. Worktrees on disk (removing any needs your OK): `../Civic-Ledger` (this branch), `../Civic-Ledger-aes`, `../Civic-Ledger-corrections`, `../Civic-Ledger-flag`, `../Civic-Ledger-gap`, `../Civic-Ledger-label`, `../Civic-Ledger-label2`, `../Civic-Ledger-nightly`, `../Civic-Ledger-retry`, `../Civic-Ledger-rulings`, `../Civic-Ledger-words`. The flag, nightly, retry and rulings ones are finished (their PRs merged).
2. The folder move broke the old launchers inside `.venv`. The main worktree's venv was rebuilt in place (`uv sync --reinstall`), and `uv run pytest`, `uv run curate` and `uv run ingest` work again. The local gate script uses `uv run python -m pytest`. The other worktrees were not touched; if one fails with "uv trampoline failed to canonicalize script path", run `uv sync --reinstall` in it.
