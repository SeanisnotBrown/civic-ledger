# Correction process

How an error in the published record is reported, verified, and fixed. The
governing rule (brief 5.12): **corrections are ordinary commits — never a
force-push, never a silent edit.** Every correction is captured in the
repository's commit history and auto-listed on the site's `/corrections`
page, which links each entry to its exact commit. The repository has been
public since 2026-10-13 (`IMPLEMENTATIONv3.md` §2), so those links open for any
reader.

> Copilot-authored, not reviewed by Sean (copilot call 2026-11-26, preview
> branch, unmerged): this header and §1 were rewritten from the D59
> private-repo wording to match the repo as it is now.

## 1. Report

The repository's GitHub issue tracker is open, so a reader reports an error by
opening an issue against it, citing the official record (a free GitHub account
is needed). Nothing here promises a response time. A correction can also start
with the operator, on finding a discrepancy or hearing of one by some other
means (e.g. directly from the owner). In every case the published value is
checked against the **primary source** (the clerk/senate roll-call record, the
Congressional Record page, the Congress.gov bill detail) before changing
anything.

## 2. Verify

The maintainer checks the claim against the primary source — not against another
secondary aggregator. A correction is only made when the primary source disagrees
with what the site published. If the primary source itself changed (e.g. a clerk
re-tally), that is noted in the commit.

## 3. Fix

The fix is a normal commit whose subject line begins **`correction:`** and which
references the reporting issue, e.g.:

```
correction: h-119-1-0234 MS position was nay, clerk XML shows yea (#42)
```

For data errors the fix flows through the same pipeline as any change
(ingest/curation → export → checks), so the correction is validated by CI before
it lands. The commit is pushed as a fast-forward; the erroneous prior value stays
in history (that is the point — the record of what was shown and when is itself
public).

## 4. Publish

`uv run corrections` regenerates `data/corrections.json` from the git history
(every `correction:`-tagged commit), and the `/corrections` page renders it with a
link to the exact commit. The nightly job runs this with a full checkout so the
list is complete. No correction is ever removed from the log.

## Never

- Never force-push or rewrite history to hide an error.
- Never edit a published value in place without a `correction:` commit.
- Never "correct" toward a secondary source over the primary record.
