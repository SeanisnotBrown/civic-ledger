# Owner questions, 2026-11-17 (nightly gaps and failures)

**Copilot-authored while Sean was away. Sean has not reviewed any of this.** Nothing
below has been built or run. Where a choice is marked "(copilot recommendation)", that
is the copilot's suggestion only; today's behavior stays until you say otherwise.

## What happened, in one paragraph

Between 11-07 and 11-17 six nightly runs failed. Each failed night leaves a
hole in "bills updated recently", because the nightly only looks back 36 hours. There
are now four holes (UTC): 11-07 11:57 to 11-08 02:00; 11-09 14:00 to 11-11 02:31;
11-12 14:31 to 11-13 00:25; 11-15 12:54 to 11-16 02:32. Two of the failures were one
outside hiccup each: on 11-13 senate.gov refused two Senate vote files, and on 11-16
LegiScan (the Mississippi data source) returned a server error. PR #5 makes the
LegiScan client retry a few times before giving up, and makes a refused senate.gov file
show its error code in the log. PR #4 makes future scheduled runs reach back to the
last successful run, so a missed night no longer leaves a hole. Both are tested and
waiting for you; either merge order works.

## Q1. Fill the four holes with one catch-up run?

- **A. Merge PR #5, then PR #4, then run the nightly once by hand with a long
  look-back (copilot recommendation).** The look-back (`since_hours`) is worked out at
  launch to reach back to 2026-11-07 11:57 UTC: about 255 hours on the evening of
  11-17, plus 24 for each day later. Consequence: the bills that changed inside the
  holes are brought up to date; it takes about 3 to 4 hours of GitHub Actions time and
  publishes to the live site.
- **B. Wait.** Consequence: bills that changed inside the holes stay out of date until
  they happen to change again.

PR #4 alone does not fill these holes: it reaches back only to the last successful run.

## Q2. When senate.gov refuses one Senate vote file, should the whole night fail?

- **A. Yes, fail the night (today).** Consequence: nothing publishes that night and a
  new hole opens, as on 11-13.
- **B. Treat it like a refused vote list: publish without that one vote, under the same
  14-day limit and the same outage notice on the site (copilot
  recommendation).** Consequence: no new hole; the missing vote fills in on the next
  night senate.gov answers; past 14 days the night fails, as today.

Not offered: retrying a refused (403) file over and over. senate.gov is blocking us
when it does that, and rule 4 says never hammer a government source.

## Q3. Should a Mississippi (LegiScan) failure stop the federal site from updating?

- **A. Yes (today).** Consequence: a Mississippi outage costs a whole federal night, as
  on 11-16.
- **B. No: federal data still publishes, and the Mississippi pages keep their last good
  data that night (copilot recommendation).** Consequence: Mississippi pages can lag a
  day behind; no federal page is affected. Mississippi is not a federal page, and the
  States section is not linked from the site's navigation (its pages are still built
  and reachable by direct address).

## Q4. The banned-words check (Owner decisions 1 in STATUS.md): a new data point

Today, on `p3-categorize-queue`, the test file holding this check (`test_bootstrap`)
took 24 minutes 25 seconds on its own, while another full gate was running alongside.
Earlier measurements: 989 to 1,283 seconds inside a full test run, and one crash on
2026-10-29. No narrower version has been written up yet; the question is still only
whether to narrow it (keep it as is, or have a builder propose a narrower scan for your
OK). No copilot recommendation beyond the data.

## Still waiting on you (unchanged; details in STATUS.md)

1. Review the 579 preview items in the Review tab (STATUS FIRST ACTION 1; steps in `PREVIEW-HOW-TO.txt`).
2. Review the 19 set-2 rows where the AI and the label disagree, borderline first (STATUS FIRST ACTION 2).
3. The Record party gap, before any real (non-preview) run (STATUS Owner decisions 3).
4. PR #2, the campaign issue-page collector: held for you because a merge deploys (STATUS FIRST ACTION 4).
5. A private GitHub repo for the review-log backup (STATUS Owed by a human 2).
6. 13 statements left uncategorized at the $20 cap; about $0.35 more AI spend (STATUS Owner decisions 5).
