# Public-repo claims on /privacy and /corrections: preview

**Copilot call, preview only, not reviewed by Sean.** Built overnight 2026-11-26
under his standing grant (2026-11-25 23:38 CT). Branch
`site-public-repo-claims-preview`, from `origin/master` (`2b9028b93`). Not
merged, no PR, does not deploy. Every sentence below marked "copilot-authored,
not reviewed by Sean" is also marked in a code comment where it lives.

## The one decision

**Merge this branch, or don't.** Merging puts "the code and data are in a public
GitHub repository" and working GitHub links back on two pages. It follows the
open row in `IMPLEMENTATIONv3.md` §2 ("Repo visibility"). Nothing else changes.
Three smaller things to know first:

1. **Reports go to GitHub issues.** The page now tells readers to open an issue
   (needs a free GitHub account). The tracker is open today, but nobody has
   said it is watched. The page promises no reply time. If you would rather
   not offer that channel yet, delete the "Report a correction" link and the
   "open an issue" sentence and keep the rest.
2. **Two old claims were not restored, on purpose.** They are false today
   (details below).
3. **One doc changed too:** `docs/correction-process.md` still said "the
   repository is private, no issue tracker". Leaving that would contradict the
   page, so its header and §1 are rewritten (marked copilot-authored). It is the
   only file outside the two pages and the tests.

## What D59 took out, and what is on the pages now

D59 is commit `8c7980124` (2026-08-13, "repo is private"). The repo went public
2026-10-13. Since D59, `/privacy` was rewritten twice more (`1a1bc9e31`,
2026-10-05, and `2f72012a8`, P1), so most of its old repo wording was already
gone before this branch.

### /corrections

| # | D59 removed | Now (this branch) | True today because |
|---|---|---|---|
| 1 | "Corrections are made as ordinary **public** commits" | "Corrections are made as ordinary public commits — never silent edits, never force-pushes." | Repo is public, so every commit is. |
| 2 | "The full history of the dataset is in the public repository." | "The full history of the **published** dataset is in the [public repository]." (link to the repo) | `data/` is tracked (83,698 files); `data/raw/` is gitignored, hence "published". |
| 3 | Per-entry link to `/commit/<hash>` (became plain text) | Link restored: `https://github.com/SeanisnotBrown/civic-ledger/commit/<hash>`; intro adds "with a link to the exact change" | `ingest/corrections.py` writes the short hash (`%h`); a short-hash commit URL returned 200. |
| 4 | "To report an error, open an issue against the source, citing the official record." plus the "Report a correction" link (`/issues`) | "To report an error, open an issue on the repository (it needs a free GitHub account), citing the official record." plus the "Report a correction" link | Issues enabled (`gh repo view`: `hasIssuesEnabled: true`); `/issues` returned 200. |
| 5 | "Full change history" link (`/commits`) | Link restored | `/commits` returned 200. |
| 6 | "See the correction process" (no link in the original) | New link to `docs/correction-process.md` on master | File exists on master, URL returned 200. New, not a restoration. |

D59's own replacement sentences were removed: "The dataset's repository is not
currently public, so this log is the public record…" and "This site does not yet
have a public channel for submitting a correction report". Both are false now.

### /privacy

| # | Old claim (before D59) | Restored? | Reason |
|---|---|---|---|
| 1 | "Static pages served from a public repository." | **Rewritten** | Pages are served by Cloudflare, not from the repo. New sentence below. |
| 2 | "The entire dataset is the public repository — the same records everyone can see." | **No** | False: the raw source cache (`data/raw/`) and `build.db` are not in the repo. |
| 3 | "A legal demand to the operator produces only what is already public here." | **No** | False: `1a1bc9e31` already called a version of this false, and accounts will hold private data. `/threat-model` says so. |

New sentence, one paragraph after the "What is collected today" list
(copilot-authored, not reviewed by Sean):

> The site's source code and the published dataset it is built from are in a
> [public repository on GitHub]. Some working files used to build that dataset
> are not in it.

It describes; it promises nothing (rule 8). Link target
`https://github.com/SeanisnotBrown/civic-ledger`, same URL as `methods.astro`
already uses.

## Tests

- New `tests/test_public_repo_claims.py` (6 tests): both pages use the one repo
  URL; `/corrections` links commits, issues and history; every
  `/blob/master/<path>` link in `site/src/pages` names a tracked file; the two
  false claims and D59's replacement sentences stay off the pages; the
  correction-process doc no longer says "private" or "no issue tracker".
- `tests/test_privacy_accuracy.py` needed no change: nothing in it pinned
  repo wording, and the new paragraph trips none of its promise or
  withdrawn-claim checks.
- No test pinned the old `/corrections` wording.

Results (worktree `../Civic-Ledger-corrections`):

- `uv run ruff check .` — All checks passed.
- `pytest tests/test_public_repo_claims.py tests/test_privacy_accuracy.py tests/test_corrections.py` with `CI=true GITHUB_ACTIONS=true` — 25 passed, 1 skipped (the existing deferred D1-schema test).
- `npx astro check` — 0 errors, 0 warnings.
- Banned-words patterns run on the four changed files only — 0 hits (the full-repo check was not run, to stay off the gate).
- **Skipped:** `npm run test:links` (needs `site/dist`, i.e. a full build), `npm run build`, e2e, full pytest, full gate. A full gate was running in `../Civic-Ledger-rulings`.

## Detail: verification, 2026-11-26

- `gh repo view SeanisnotBrown/civic-ledger`: `visibility: PUBLIC`, `isPrivate: false`, `hasIssuesEnabled: true`, not archived, default branch `master`.
- HTTP 200 for the repo, `/issues`, `/commits`, `/commit/<short hash of master>`, and `/blob/master/docs/correction-process.md`.
- `data/corrections.json` is `[]`; no `correction:` commit exists on master. So the log renders "No corrections have been issued yet." and the commit links render only once one exists. Nothing in this branch was exercised against a real entry beyond the URL shape above.
- Only `/privacy` and `/corrections` repo wording was changed. `methods.astro` already links `docs/data-contract.md` (file exists).

## Things I noticed and did not change

1. **"never force-pushes" is a practice, not an enforced rule.** `master` has no branch protection and there are no rulesets (`gh api …/branches/master/protection`: 404; `rulesets`: `[]`). D59 kept the sentence and so does this branch. It describes how corrections are made; it is not a technical guarantee. Worth a look if you want it enforced.
2. **"…the primary source it was checked against"** (existing text, not D59's) is true only if the correction commit's subject names the source, as the process doc's example does. The page shows the subject line only.
3. `IMPLEMENTATIONv2.md`'s "open source" line and some internal docstrings still assume the old state; D59 listed them as not touched. Out of scope here.

## If you say yes

Merge the branch (it needs the full gate first, which was not run tonight). Merging to master deploys it through the normal pipeline. If you say no, the
two pages stay as they are today (no repo claims, no GitHub links).
