# PROGRESS.md — Civic Alignment Platform build state

State-tracking file per `.claude` rules. Updated before ending any session.
Single source of truth for: current increment, acceptance status, blocked H-tasks.

**Last updated:** 2026-10-05, end of session. **V2-11 is COMPLETE** (tasks 1-8 + 5b,
D88-D100). **V2-7 is 3 of 4 tasks done** — `/privacy` and the new `/threat-model` are
written and truthful, H19 is closed. **Congress 118 is fully backfilled and committed;
Congress 119 is PARTLY backfilled and committed, and the owner stopped it deliberately to
shut the machine down.** Ten commits this session, all pushed.

## ▶▶▶ TASK 0 — THE FIRST THING YOU DO THIS SESSION (owner's instruction, 2026-10-05)

**RESTART THE CONGRESS 119 DATA PULL.** The owner stopped it himself at the end of the last
session because he was shutting the laptop down, and asked that the next session start it
again. **He has already approved this run — do not ask.**

One command, detached, from the repo root:

    nohup uv run ingest bill-activity --congress 119 > backfill-119.log 2>&1 &

Then confirm it is alive (do all three — the log is useless for this):

    tasklist | grep -i python                                  # the 60-90 MB one is it
    grep -l '"actions"' data/bills/*-119.json | wc -l           # 611 at last session's end
    ls -l --time-style=full-iso $(ls -t data/bills/*-119.json | head -1)   # should be seconds old

**What to expect.** Resume is the DEFAULT (D91/D95a) — it skips every bill that already has
a timeline before making any network call, at **zero API requests**. The run re-enumerates
Congress 119 first, which costs **~78 list pages / ~7 minutes** and prints nothing to the
log while it does, so **the log sits at 0 bytes and the disk count does not move for the
first ~7 minutes. That is normal.** Python buffers stdout when redirected; **read progress
off disk, never off the log.** Roughly **18,800 bills still to fetch at ~4.5 s each ≈ 23 h.**

**It is safe to kill at any moment** — `taskkill` from PowerShell (`Stop-Process -Id <pid>
-Force`; in Git Bash `/F` gets mangled into a path, use PowerShell or `//F`). Every write on
this path is atomic (D95a, measured against a real hard kill), and a resume costs 0.56 s and
zero requests. **Commit whatever is on disk with the four-command loop further down** —
and do not skip `uv run ingest events && uv run ingest topics && uv run export`, or the push
goes red on invariants 8 and 9 and the manifest counts.

**▶ The 119 bills fetched last session were fetched by the PRE-D100 code.** D100 fixed a
guard that wrongly rejected any bill whose action list contains a byte-identical repeat
(see live fact 3). The already-running process had imported the old module, so some 119
bills may have been skipped as "fetch failures" that the fixed code will now take. A plain
resume picks them up; nothing extra to do. If the restarted run reports fetch failures,
**do not assume they are transient** — check whether they are duplicate-row cases first.

## ▶▶ READ THIS FIRST — the three live facts

**1. NOTHING IS RUNNING. The tree is clean and everything is pushed.** The owner stopped the
Congress 119 backfill deliberately at 2026-10-05 ~16:40 CDT to shut the machine down. The
derived artifacts were regenerated and `verify-recompute` run with no concurrent writer, as
the D96 operational rule requires, **so the local test suite is honest again** — it is not
in the "3 failures, all the backfill" state earlier sessions describe.
- **Congress 118: COMPLETE.** 19,118 enumerated, 19,296 files, 19,292 with timelines.
- **Congress 119: PARTIAL.** 1,109 files, **611 with timelines**, of ~19,441. ~18,800 to go,
  ~23 h. Restart per TASK 0.
- **`backfill-119.log` is 0 bytes** and that is not a failure — the kill landed before
  Python flushed its buffer. The disk count is the record.

**2. ZERO quarantines were produced by the 119 run.** `data/quality/quarantine/` holds only
the four long-standing roll-call entries (`h-118-1-0001`, `h-119-1-0001`, `h-119-2-0130`,
`h-119-2-0131`) and the accept list matches them exactly. **`bill-s4869-118` is GONE from
both** — D98 made `BillAction.text` nullable, the bill now ingests with 3 actions (one with
`"text": null`), and its accept-list entry was removed in the same commit because
`test_committed_accept_list_matches_committed_quarantines` is bidirectional.

**3. ⚠ THE "15 UNFETCHABLE BILLS" WERE OUR BUG AND IT IS FIXED (D100). Earlier guidance in
this file was wrong and has been deleted.** `bill_actions` de-duplicated action rows WITHIN
a page and compared the survivors against `pagination.count`; congress.gov legitimately
repeats some rows byte-for-byte, so the guard raised `TruncatedFetchError` on valid
responses. **Nothing was ever truncated.** Measured from cache with zero API requests:
across 19,118 bills and 87,307 action rows there are **0 genuinely short pages** and exactly
**15 bills carrying a byte-identical repeat**, and the two sets coincide. Confirmed against
govinfo BILLSTATUS bulk XML on a second host — hr9748-118 really does carry the same
referral line four times. Twelve of the fifteen had **no record on disk at all**. Fixed:
dedupe now applies only to a copy already held from an EARLIER page.
**Do not spend a session retrying fetch failures as if they were network flakes** —
check for duplicate rows first.

## ⚠ TWO OWNER QUESTIONS ARE OPEN, and both have a recommendation waiting

**1. H18 — which company sends the email.** Blocks the rest of `/privacy` and all of V2-8.
**Recommendation already put to the owner: Cloudflare Email Sending.** Three reasons: the
$5/mo Workers Paid plan (H20) is required for V2-12 anyway so it is not an extra cost; one
company instead of two sees reader email addresses, which also shortens the honest privacy
page; same dashboard. The caveat he was given: 3,000 emails/month included, which a daily
digest exhausts at roughly 100 subscribers. He had not answered when the session ended.

**2. The duplicated action rows now render.** D100 means those 15 bills publish their
repeats — hr9748-118 shows four identical referral lines and `b/[bill].astro:125` reads
"22 actions". It is faithful to `pagination.count` and to BILLSTATUS, and it will read as a
bug. **Recommendation put to the owner: render the row ONCE with a line saying "The
official record lists this action 4 times."** — literally true, asserts nothing about why,
keeps the count honest, display-layer only, never changing what is on disk. Silently
collapsing would be editing the government's record (§0.5). Paired with it, the feeds should
emit one entry per distinct id: repeated rows hash identically, so `site/src/lib/atom.ts`
currently emits entries sharing an `atom:id` (measured: 1 duplicate each on hr1516-118,
hres712-118, s4072-118). He had not answered when the session ended.

## Where V2-7 stands (the current increment)

**3 of 4 tasks done, and the remaining one is blocked on H18 above.**
- **Task 1 — `/privacy` rewritten, partly.** The today-true half is live and honest.
  **Removed:** "built to collect as little as possible", "No cookies. No analytics. No
  third-party fonts, scripts, or CDNs", and "a legal demand to the operator would produce
  only what that private repository contains" — which was **already false**, since
  `data/raw/`, `build.db`, `backfill-*.log` and `.env` have always lived outside that repo.
  **Added** the owner's chosen plain sentence naming Cloudflare, and the one standing
  promise. **Still owed, blocked on H18:** the forward-looking half — the §5 table list in
  plain words, the public-profile carve-out, deletion semantics, and naming the email
  provider.
- **Task 2 — `/threat-model` is NEW and done.** What is true today, what accounts will
  hold, what a legal demand produces, then an explicit **"what is not promised"** section
  naming the withdrawn guarantees, and **"what is promised"**: never sold, hard delete,
  K-anon. It also discloses, verified rather than assumed, that `MemberBrowser.tsx:144`
  copies typed search text into the page address and that `/compare` carries the chosen
  members. Linked from `/privacy` and the footer — the `/topics` orphan (D97) is why that
  is a step and not an afterthought.
- **Task 3 — H19 canary: CLOSED. Retired, not reshaped (SD-35, owner).** Nothing to build.
- **Task 4 — done.** Spec §0.4.3 and `CONTRIBUTING.md` Value #3 both still promised things
  SD-34 withdrew; both now record the withdrawal with a do-not-reinstate note.
- **Acceptance still owed:** the drift-proof accuracy test (stated storage list and K
  constant match code/config). It cannot be fully written until V2-8 creates the D1 schema
  there is nothing yet to compare against.

**▶ SD-34 (2026-10-05) IS THE BIGGEST CHANGE THIS SESSION AND IT CHANGES WHAT YOU MAY
WRITE.** The owner withdrew the no-tracking guarantees: *"what this is going to evolve to, I
am going to have to track this info. My only promise is to never sell this data."* The
project MAY now log requests, keep IP columns, set cookies, hold per-submission rows, let
the anonymous reader's browsing reach the Worker, and store beyond the §5 tables. **Never
write any of those guarantees onto the site or back into the values.** Three things SD-34
did NOT withdraw, flagged in the ADR and the spec so nobody sweeps them away: **Argon2id**,
the **K-anon (=50) render gate**, and **hard deletion on request**. Each needs its own dated
decision to remove. `docs/draft-v2-7-privacy-claims.md` is the full claim-by-claim audit —
read it before writing privacy copy, but note its "no cookies"/"no analytics"/"no
third-party scripts" rows are now **moot as claims**, and its Q1 and Q6 are answered.

## Where the build actually stands

**V2-11 tasks 1-6 and 5b are DONE** (D88-D96). What exists and is verified:
- **Ingest:** `bill_actions()`, `bills_updated_since()`, the `BillAction` model,
  `uv run ingest bill-activity` with free resume, and **atomic writes on every write the
  backfill makes** (D95a — measured against a real `taskkill /F`).
- **Projections, both pure and both re-derived by `verify-recompute`:**
  `data/events/{YYYY-MM}.json` (**invariant 8**, D95b) and `data/topics/index.json`
  (**invariant 9**, D96). Nightly steps 3e and 3f. Both in the CI 100%-branch gate.
- **Served:** `/events/{month}.json` and `/events/latest.json` emit the month files
  verbatim (task 5b).

**V2-11 TASK 7 IS DONE** (D97, commits `8e65c8fbf` + `3d6c09414`). What is live:
1. `/b/{bill}` has an **Action timeline** — every official action verbatim, newest first,
   with committees, action code, `source_system`, and a `/v/` link where the action
   resolves to a held roll call. Plus **"Track this bill"**: the feed link and a
   selectable address, with the copy button revealed by script so JS-off gets no dead
   control.
2. **`/topics/`** index + a page per official term — **but the URLs are namespaced by
   vocabulary**: `/topics/policy-area/{slug}/` and `/topics/subject/{slug}/`, NOT the flat
   `/topics/{slug}/` the plan sketched. Reason in D97(a), and it is not cosmetic: a
   committed test pins that "Health" can be both a policy area and a subject term, so a
   flat namespace would be the vocabulary merge `ingest/topics.py` exists to prevent.
3. **Atom feeds**: `/feed.xml`, `/b/{bill}/feed.xml`,
   `/topics/{policy-area|subject}/{slug}/feed.xml`, and the new `/m/{member}/feed.xml`.
   `updated` comes from record dates everywhere — no build clock, pinned by an e2e test,
   because a build-clock stamp re-notifies every subscriber on every rebuild.
4. **`npm run test:links` now actually enforces the SD-33 3(c) rule on these surfaces.**
   It previously only checked `/b/` page presence, so the plan's claim was aspirational.
   Extended to every topic row (via `data-bill-id`) and every feed entry, both
   directions, and **verified by tampering with a built page**.

**Gates at task-7 acceptance:** `npm run build` 14,168 pages; `test:file-count`
**16,793 of 20,000** (warn 18,000 — 3,207 headroom, and the subject vocabulary is still
growing, so this is the number H14/H20 gets decided against); `test:links` OK over 23,032
topic rows + 48,306 feed entries; **60/60 Playwright e2e** including a11y + 380px on the
three new URLs and Atom validity on all five feed shapes; `astro check` 0 errors;
`uv run ruff check .` clean. Largest feed 53 KB, largest topic page 184 KB, topics index
260 KB; all 2,588 feeds parse as valid Atom.

**Two caps the owner may want to revisit (D97(b), neither urgent):** a feed carries 50
entries and a topic page lists 200 bills, both stated plainly on the page ("Showing the
200 with the most recent action, of 11,432"). Uncapped they break the 25 MiB-per-file
limit and the 20,000-file ceiling respectively. **Full browsable topic membership means
pagination, which needs H20 (Workers Paid).**

**▶ Playwright's browser had to be installed locally** (`npx playwright install chromium`,
114 MB) — a fresh machine has the package but not the binary, and every e2e test fails
with "Executable doesn't exist" until it is there.

**TASK 8 IS DONE (D99, commit `5755126f3`).** `nightly.yml` step 1b runs
`uv run ingest bill-activity --since 30`, after `ingest bills` and before
`ingest legislation` and steps 3e/3f. **V2-11 is therefore COMPLETE (tasks 1-8 + 5b).**
The one behaviour change worth knowing: a fetch-failure count at or under
`max(2, 2% of the window)` no longer fails the nightly, because the step runs under
`set -euo pipefail` and one `ConnectTimeout` used to abort the night before classify,
metrics, grades, events, topics, export and the commit. Full reasoning in D99.

**NEXT — V2-7 (privacy page true).** It is the blocking gate before V2-8/V2-9/V2-12/V2-13,
which store user data. **Read the ⚠ section at the top of this file first**: a false claim
is live on every bill page right now, and `docs/draft-v2-7-privacy-claims.md` is a
finished claim-by-claim audit with the owner questions already ranked.

## ⚠ OPERATIONAL RULE — invariants 8 and 9 cannot be verified while a backfill runs

Both re-derive from `data/bills/`, so a concurrent backfill adds bills between the
regeneration and the check. Observed exactly that this session: `events 2024-03 committed
218,068 vs recompute 229,022 bytes`. **It is not a bug and not a data problem.** CI never
sees it (no concurrent writer). Locally: **stop the run → regenerate → verify → commit →
relaunch.** Resume costs 0.56 s, so this is cheap, and it is why the chunk loop commits only
after the run is stopped.

## Two measured numbers the owner will have to decide on (neither is urgent)

Both were built as the plan specifies, with the number recorded rather than scope quietly
changed. The backfill is days from finishing, so there is time.
1. **The events feed projects to ~200 MB** (~190,000 events, ~4 MB per month file) because
   the plan puts `subjects` on every row — measured 4.86 actions/bill and 544 bytes of
   subjects per bill, max 17,202 (D95). A V2-12 Worker polling `/events/latest.json` hourly
   pulls that each time.
2. **`data/topics/index.json` projects to ~10.7 MB, rewritten WHOLE every nightly**
   (16.0 subjects/bill mean, max 620 → ~620,000 bill-id references) — so the repo grows
   ~10 MB per nightly that touches topics (D96). Cleanest fix when it binds is sharding to
   `data/topics/{slug}.json`, which also matches the one-file-per-record convention the rest
   of `data/` already uses.
**Neither affects alerts:** the V2-12 Worker needs neither file's membership, because every
event row already carries `policy_area` and `subjects`.

## One thing to tell the owner in plain language

**The "872 CRS subject terms" he ratified in SD-33 was a snapshot, not a limit.** 877 were
already on disk at 1,385 bills — about 1% into the backfill — and the number will keep
climbing as more bills land. That is the government's vocabulary growing, not a data error.
Nothing in the code asserts a total, and a test pins that.

**2026-10-02 (afternoon) — V2-11 TASK 7 DONE (D97). The activity data has a site.**
Bill action timelines, the `/topics/` tree, four shapes of Atom feed, and "Track this
bill". Committed as `8e65c8fbf` (code) + `3d6c09414` (ADR); **not pushed at session end.**
- **The plan's flat `/topics/{slug}/` was NOT built.** Namespaced by vocabulary instead
  (`/topics/policy-area/…`, `/topics/subject/…`) because
  `test_policy_areas_and_subjects_are_separate_vocabularies` pins that "Health" is valid
  as BOTH a policy area and a subject term, so one flat namespace is exactly the merge
  D96 forbade. The spec preamble (code beats document) settles it; `getTopicPath()` owns
  the prefix for all six linking surfaces. Full reasoning in D97(a).
- **Feed entry ids are byte-equal to `ingest.events.event_id`** — the TypeScript mirror
  was checked against the committed `data/events/` projection on **3,169 real actions,
  zero mismatches**. One government action therefore has one identity in both the feed
  and the V2-12 alert path.
- **Two bugs the build caught, both worth knowing:** (1) `actions` is *absent*, not
  `null`, on an uncollected bill — the exporter omits `None` fields — so `actions ===
  null` was false for `undefined` and `hconres108-119` took the build down on
  `.length`; the TS type is `actions?: BillAction[] | null` and readers use `?? null`.
  (2) Stored action order is **already newest-first**; the first version reversed it and
  rendered every timeline backwards. There is deliberately no local re-sort — `date`
  alone cannot order same-day actions and `actionTime` is on only 44% of rows.
- **`npm run test:links` was not enforcing what the plan said it enforced.** It only
  checked `/b/` page presence; a topic page or feed entry linking a pageless bill to
  `/b/` would have shipped. Now walks every topic page (via `data-bill-id`, both
  directions) and every built feed. Negative-tested by tampering with a built page.
- **Gates:** build 14,168 pages; **file-count 16,793 of 20,000** (warn 18,000);
  `test:links` OK over 23,032 topic rows + 48,306 feed entries; **60/60 e2e**;
  `astro check` 0 errors; `ruff check .` clean. Largest feed 53 KB, largest topic page
  184 KB. All 2,588 feeds parse as valid Atom.
- **`/topics` was ORPHANED on the first pass** and that is why `/federal` now links to it.
  Nothing on the homepage or the members explorer pointed at the topic tree, so a reader
  could only reach it from a bill page's policy-area link and then the breadcrumb. Caught
  by grepping the built output for `href="/topics"` — 908 hits, every one of them a topic
  page's own breadcrumb. Worth repeating as a habit: a new section is not shipped until
  something a reader already visits links to it.
- **Local pytest is RED with 4 failures, all four the running backfill** — see live
  fact 3 at the top. The fourth is `test_manifest_double_build_byte_identical`, which is
  the cleanest possible demonstration of the interference: two exports seconds apart
  disagree on the bill count because the backfill wrote more bills between them.
  **Coverage still reports 100.00%** on all seven gated modules. Zero Python and zero
  `data/` changed in this session.
- **One e2e flake observed once:** `380px layout: /privacy` failed in one full-suite run
  and passed on its own and in two subsequent full runs. The spec's own comment documents
  a font-load/screenshot race on this check. Not investigated further; noted so the next
  session does not treat a single occurrence as a regression.

**▶ A HAZARD THE QUARANTINE FILE EXPOSED, now guarded on the site side.**
`s4869-118` was quarantined with `KeyError: 'text'` — congress.gov served an action row
with no `text`. `ingest/models.py` records `text` as present on 520/520 sampled actions
and therefore **required**, and that measurement is now contradicted by real data. Today
the quarantine keeps the bill off the site entirely, so nothing is broken. **But whoever
fixes the ingest to tolerate it will make the field nullable, and at that moment any
string interpolation or XML-escaping of it throws at build time.** The site is already
guarded: `actionText()` in `site/src/lib/display.ts` is used by the timeline and by both
feed fields, and it renders "(no action text on the official record)" rather than a blank
line, because a blank line would publish an action with no content. **The ingest-side fix
is still owed** and the model docstring's "520/520 -> required" should be corrected when
it lands.

**`uv run checks`: ALL CHECKS PASSED** — banned-words and no-LLM over the new page copy
included, which is the check that matters for prose this session added ("word for word",
"no account", "this site did not write it or choose it"). It does not read bill counts,
so the backfill does not disturb it.

**Two Windows operational notes from this session, both likely to recur:**
- **`npm run build` failed twice with `EPERM ... dist\m`** while emptying `dist/` —
  something (indexer, Defender, or a just-finished preview server) holds handles on
  freshly written files, and `rm -rf dist` reported "Device or resource busy" on
  individual files. **Just retry; the third attempt succeeded.** It is not a code fault.
- **A bare `python ... <<'HEREDOC'` through the Bash tool choked repeatedly** on large
  mixed-quote TypeScript/Astro content (`unexpected EOF while looking for matching`).
  Writing those files with the editor tool instead worked first time.

**2026-10-02 — V2-11 TASK 6 DONE (D96). The topic index exists.**
`ingest/topics.py` + `uv run ingest topics` build `data/topics/index.json` from
`data/bills/**` — pure, no clock, no network. **31 policy areas + 877 CRS subject terms
over 1,385 bills.** SD-33 4(a) held exactly: official vocabulary only, verbatim, no owner
bundles (H22 still optional). `verify-recompute` gains **invariant 9**; nightly step 3f;
`ingest.topics` added to the CI coverage gate (100%, 33 tests).
- **A slug collision FAILS the run** rather than appending a counter — one URL cannot stand
  for two official terms. No collision exists in the 908 terms on disk.
- **▶ The "872 CRS terms" in SD-33 is a SNAPSHOT, not a cap.** 877 were on disk at 1,385
  bills, i.e. 1% into the backfill. The government extends the CRS list; a test pins that
  nothing asserts a total. Expect the number to keep climbing — that is the vocabulary
  growing, not a data error.
- **▶ MEASURED: the index projects to ~10.7 MB and is rewritten WHOLE every nightly**
  (16.0 subjects/bill mean, median 5, max 620 → ~620,000 bill-id references at 38,756
  bills). Built as the plan specifies and the number recorded, same as D95 did for events.
  Not urgent — the backfill is days from done. Options when it binds: shard to
  `data/topics/{slug}.json` (which matches the one-file-per-record convention the rest of
  `data/` uses, and means only changed topics rewrite), or keep counts only and let the
  site derive membership from bills it already loads. **The V2-12 Worker does not need this
  file at all** — events already carry `policy_area` and `subjects`.
- **Gates: 535 passed / 0 failed** under `CI=true GITHUB_ACTIONS=true` (two halves,
  291 + 244, for memory); `uv run checks` ALL CHECKS PASSED; `verify-recompute` OK through
  invariant 9; `npm run build` 13,259 pages / 48 s; `test:links` OK (345 pageless bills
  correctly linking to congress.gov); `test:file-count` 13,296 of 20,000; `astro check`
  0 errors.

**⚠ OPERATIONAL RULE LEARNED THE HARD WAY (D96): invariants 8 and 9 CANNOT be verified
while a backfill is running.** Both re-derive from `data/bills/`, and a concurrent backfill
adds bills between the regeneration and the check — observed exactly that (`events 2024-03
committed 218,068 vs recompute 229,022 bytes`). CI never sees it (no concurrent writer).
Locally: **stop the run, regenerate, verify, commit, relaunch.** Resume costs 0.56 s, so
this is cheap. It is why the chunk loop commits only after the run is stopped.

**▶▶ 2026-10-02 — A BACKFILL RUN IS IN FLIGHT ON THIS MACHINE (owner said "just start it").**
`uv run ingest bill-activity --congress 118` launched detached at ~01:50 UTC, full Congress
(no `--limit`), logging to `backfill-118.log` (gitignored). **Nothing is committed by the
run itself** — it only writes `data/bills/`.

**If you are a cold session reading this, do these two checks first:**
1. **Is it still running?** `tasklist | grep -i python` — the backfill is the ~80 MB one.
   If it is gone (laptop shut, run finished, or it was killed) that is FINE and expected:
   resume is the default and costs 0.56 s / zero requests (D95a).
2. **Is there uncommitted data?** `git status --short -- data/` — if yes, commit it with
   the FOUR-command loop below (the `uv run ingest events && uv run export` line is not
   optional; without it the push goes red on invariant 8 and the manifest counts).

Progress is read off disk, not the log (Python buffers stdout when redirected, so
`backfill-118.log` can sit empty for a long time while the run is working fine):
`grep -l '"actions"' data/bills/*.json | wc -l` — was **73** at launch, **240** a few
minutes in. Target for Congress 118 is **19,315**; at the measured 3.9 s/bill that is
~21 h for 118 alone, ~43 h with 119.

**2026-10-02 — PUSHED and CI IS GREEN.** `0924fc214` (code) + `afaae3808` (data) +
`c4b6d21d3` (this doc). **Run `36952060305` on `c4b6d21d3`: success, BOTH jobs**
(`python` + `site-and-checks`). That run covers all three commits, so D95 is validated on
GitHub and not only locally — the standing rule from D94 is satisfied.
Note for the log: run `36952028397` on `0924fc214` shows **cancelled**, which was NOT a
failure — the PROGRESS push 25 s later superseded it under the workflow's concurrency
group. Local evidence before the push: the full suite
**502 passed, 0 failed** under `CI=true GITHUB_ACTIONS=true`, run in two halves
(286 + 216) because the machine had ~1.2 GB free and a single 13-minute run kept being
killed by the memory watchdog. **Every test ran, in the CI environment** — the split was
for memory, not coverage. The coverage gate ran separately: **100% branch on all six
modules including the new `ingest.events`** (164 tests). Coverage is monotonic in tests,
so 100% on that subset implies 100% on the whole suite.

**2026-10-01 — D95a: THE BACKFILL IS INTERRUPTION-PROOF, and it was MEASURED, not asserted.**
The owner asked whether the machine can be shut down mid-backfill. Answer: yes, at any
moment, and here is the evidence rather than the claim.
- **A real run was hard-killed.** `uv run ingest bill-activity --congress 118 --limit 140`
  was started and `taskkill /F` fired while it was writing bills — the closest available
  simulation of the machine going down, and harsher than Ctrl+C. Audit afterwards: **0
  unparseable bill files, 0 unparseable cache bodies, 0 orphaned cache entries**, 30 fresh
  timelines intact.
- **The resume was timed.** `--congress 118 --limit 73` → **0.56 s, zero requests**, all 73
  finished bills counted as held. Resume is the DEFAULT (D91); there is no flag to remember.
- **Every write on that path is now ATOMIC** (`cache.atomic_write_text`: write to a temp
  sibling → `flush` → `fsync` → `os.replace`). Used by `export_bill`, both writes inside
  `cache.fetch`, and the quarantine writer. Ctrl+C and an orderly shutdown were already
  safe; the case that was NOT was a true power loss, where NTFS can journal a rename
  without the data blocks and leave a **zero-length cached body under a sidecar that still
  reads FRESH** — which `fetch` would then serve from cache for up to the 20 h TTL, killing
  every resume on that bill with a `JSONDecodeError` that `run_activity` does not catch.
  7 tests, one of them pinning the write ORDER inside `fetch` (body before sidecar).

**2026-10-01 — V2-11 TASK 5 + 5b DONE (D95b). The activity feed exists and is served.**
`ingest/events.py` (pure, no clock, no network) + `uv run ingest events` project
`data/bills/**` into `data/events/{YYYY-MM}.json`. **355 events across 22 month files**
from the 73 bills backfilled so far; byte-stable across runs (hash-verified).
- **`verify-recompute` invariant 8** re-derives every committed month file from
  data/bills + data/votes. Green on real data (3,519 roll calls, 22 month files).
- **Wired into `nightly.yml` as step 3e**, before the diff-gate. **Not optional:**
  `ingest bills` refreshes each exported bill's timeline every run (D90), so a stale
  `data/events/` would fail invariant 8 on the very next push.
- **5b: `site/src/pages/events/[month].json.ts` + `latest.json.ts`** serve each month file
  **verbatim** (the bytes invariant 8 guarantees, not a re-serialisation). Verified
  byte-identical to disk out of `dist/`.
- `ingest.events` added to the CI 100%-branch coverage gate (measured 100%, 57 statements).
- **Gates: 35 events tests + 7 atomic-write tests; `uv run checks` ALL CHECKS PASSED;
  `verify-recompute` OK; `npm run build` 13,259 pages in 50 s; `test:links` OK;
  `test:file-count` 13,293 files (limit 20,000); `astro check` 0 errors.**

**▶ `/events/latest.json` reads 2024-12 right now, and that is correct.** It serves the
newest month that HAS events, deliberately not the current calendar month — a build-time
`new Date()` would put a wall-clock in a built artifact (§6.3), and on the 1st of a month
the URL would serve an empty document while yesterday's floor votes sat in the previous
file. The backfill is walking Congress 118 (closed) **descending**, so the newest month it
has reached so far is 2024-12. It becomes current once Congress 119 data lands.

**▶ MEASURED SIZE RISK on this path — recorded, not fixed, and it needs a call before V2-12.**
Measured on real data: **4.86 actions/bill** (mean over 73, median 3, max 18) and **544
bytes of `subjects` JSON per bill** (mean over the 1,044 that have them, **max 17,202**).
The plan asks for `subjects` on every event row, so at full backfill this projects to
roughly **190,000 events ≈ 200 MB over ~48 month files, ~4 MB per month file** — and a
V2-12 Worker polling `/events/latest.json` hourly would pull that every time. Built as
specified and the number recorded rather than scope quietly changed (D95). Options when it
binds: a subjects-free "slim" feed, a per-day shard, or let the consumer join against the
task-6 topics index. Mechanical, not an owner decision.

**2026-10-01 — CI UNBLOCKED AND GREEN.** `gh run rerun 36743621950` on the reset allowance:
**success**, `python` 3m15s + `site-and-checks` 21m15s. That one run validates **D86 and D87
together** on GitHub — both had only ever passed locally, because every run since 09-28 died
on the billing block in under 8 s. The October allowance works. **Non-blocking annotation on
both jobs: `ubuntu-latest` migrates to Ubuntu 26 on 2026-10-19.** Nothing breaks today; worth
a pin or a test run before then. Not yet actioned.

**D86 is still only HALF accepted.** CI green proves the code compiles and the suites pass; it
says nothing about the re-paging behaviour. The behavioural acceptance is unchanged and still
needs two nightlies: the first run on/after 10-01 re-pages all 639 members once (~4 h, commits
`lifetime_counts` onto every `data/legislation/*.json`), and **the next non-Sunday run is the
test — PASS = < 1 h and the log prints `N re-fetched + M unchanged (kept) of 639 members`
with M in the hundreds.** Check with `gh run list --workflow=nightly.yml --limit 4`.

**2026-10-01 — V2-11 TASK 1 COMPLETE (D88). Measurement only; no ingest code written.**
The plan gates tasks 4 onward on owner decisions 3, 4 and 6, so the build stops here until he
answers. Probed live against `CONGRESS_API_KEY`; two samples committed; field shapes recorded
as **SHAPES.md §9**, which is the contract the parser gets written against.

What was measured:
- **38,756 covered bills** (118th = 19,315, 119th = 19,441) against the **1,038** that reach a
  roll call today — the plan's "15,000–20,000 per Congress" confirmed at the top of its range.
- **The update window works:** `fromDateTime`/`toDateTime` give **435 bills in 24 h** (427 of
  them in the covered Congresses) vs 430,715 unfiltered, and compose with `/bill/{congress}`.
- **DEVIATION — the documented `sort=updateDate+desc` is silently ignored.** It returns the
  identical page as a deliberate `sort=BOGUSVALUE` control. **The working form is
  `sort=updateDate desc`** (literal space). Caught only by running the bogus-value control.
- `/actions` shape fully recorded; `actionTime` is optional (142/234 on the NDAA), and
  `recordedVotes` carries the join to `RollCall.id`. **Pagination is UNEXERCISED** — the
  largest action list found is 234, under the 250 ceiling. Written and unit-tested against a
  synthetic payload; not confirmable live until some bill exceeds 250 actions.
- `limit=251` **clamps to 250 silently** rather than erroring — trust `pagination.count`.
- **H23 CLOSED.** `x-ratelimit-limit: 20000`, window not stated in any header and therefore
  not asserted. At the 1 req/s throttle the **nightly never binds** either way (~1,740 calls a
  normal night, ~14,400 on a Sunday `--full`). A daily window would only pinch the one-time
  backfill, which `cache.py` throttles through on `Retry-After` rather than crashing on.
  No raise to request.

**▶ THE NUMBER THAT CHANGES THE PLAN — this is a budget problem, not an API problem:**
at 4 requests per bill and 1 req/s, a **full backfill of all 38,756 bills is at least ~43
hours ≈ 2,590 GitHub Actions minutes — more than one entire month's 2,000-minute free
allowance** (H24); that is a floor set by the throttle, not an estimate. **It cannot run in
CI.** It can run locally over a sitting or two and be committed, at zero billed minutes. And
in steady state, refetching every updated bill costs **~19–29 min/night ≈ 560–870 min/month**
(280–435 bills/day: 1,954 over the probed week, 435 in the probed day), which **does not fit**
at either end alongside the D86 nightly's existing ~900–1,400. Fetching only `/actions` for
bills already known (the full 4 calls only for genuinely new ones) costs **~5–7 min/night
≈ 150–210 min/month**, which does fit. These three numbers are what owner
decisions 3 and 6 must now be asked against.

**2026-10-01 — OWNER ANSWERED ALL FIVE OPEN V2-11 DECISIONS (SD-33).** Asked in plain language
with D88's numbers; recorded in `IMPLEMENTATIONv2.md` §2, `docs/decisions.md`, and the plan doc.
- **Coverage = 3(c):** track all **38,756** bills for alerts/topics/feeds; `/b/` pages only for
  the **1,038** that reach a recorded vote. Pageless bills link to congress.gov, never to a
  `/b/` URL that does not exist (or `npm run test:links` fails).
- **Topics = 4(a):** official vocabulary only — 31 policy areas + 872 CRS terms, verbatim.
  No owner bundles this release; **H22 stays optional, not a blocker.**
- **Cadence = daily digest** on the existing nightly. No second intra-day workflow.
- **Channel = email first** → **H17, H18, H20 are the V2-12 blockers.** Text/push phase 2;
  **H21 untouched — phone numbers still not a permitted data class.**
- **Workers Paid NOT forced by V2-11** (build stays under the 20,000-file free limit at 13,161);
  the $5/mo upgrade moves to V2-12, where email sending needs it anyway.

**2026-10-01 — V2-11 TASK 2 DONE.** `bill_actions()` and `bills_updated_since()` are in
`ingest/sources/congress_gov.py`, with `PAGE_LIMIT` and `UPDATE_SORT` as tested constants.
23 new tests (`tests/test_bill_activity_v2_11.py`), suite **363 → 386**. Live smoke-tested:
234 actions on the NDAA, 26 on hjres104-119, ~420 bills in a 24 h window, genuinely
descending, no duplicates.

**One real bug, caught by the live smoke test and NOT by the unit suite** (the suite was
synthetic and shared the wrong assumption): actions have **no id**, and
`(actionDate, actionTime, actionCode, text)` is **not unique** — `hr2670-118` has five rows
differing only by which subcommittee is in `committees`. The first dedupe silently returned
**225 of 234** real actions. Fixed twice over: the dedupe hashes the whole row, **and** the
function raises if unique rows come in under `pagination.count`, so a future collapse fails
loudly instead of publishing a short timeline. Both regression-tested. Recorded as the
**D88 addendum** and in SHAPES.md §9. **The lesson generalises: synthetic tests written
from the same assumption as the code cannot catch a wrong assumption — every later V2-11
task needs one live smoke check before it is called done.**

Also measured in task 2 (D88 addendum (b), (c)): **no deep-offset ceiling** (offset 19,300
serves; `offset >= count` returns empty, not an error), so a count-bounded loop enumerates a
whole Congress with no cursor workaround; and **descending is the only safe crawl direction**
— ascending skips rows at the cursor when a bill is touched mid-crawl, descending merely
re-reads them.

**2026-10-01 — V2-11 TASK 3 DONE (D89).** `BillAction` in `ingest/models.py`;
`Bill.actions: list[BillAction] | None` under the D27 sentinel; pure `parse_actions()` and
`rollcall_id_for()` in `ingest/bills.py`; **30 tests, suite 386 → 416**; `bill.schema.json` regenerated. Live-
verified on the real NDAA timeline (234/234 rows, 18 roll-call links, all seven subcommittee
rows distinct) per the task-2 rule.

**Nullability was MEASURED first** — 520 real actions across six bills and four Congresses,
table in SHAPES.md §9. Three judgement calls recorded in D89:
- **`committees` added to the plan's field list.** Without it the five hr2670-118 rows that
  differ only by subcommittee render as one line repeated five times.
- **`type` is `str`, not a Literal** — the value set is the government's to extend.
- **`source_system` stores the name, not the code** — Senate rows have no `code` at all.
- **`rollcall_id` resolves against what this dataset HOLDS**, defaulting to resolving
  nothing. 40/58 hit; all 18 misses were 117th/116th, outside the covered window.

**2026-10-01 — V2-11 TASK 4 DONE (D90).** `uv run ingest bill-activity` exists;
`ingest bills` now fetches `/actions` for every bill it exports. 36 tests. SD-33's two cost
constraints are enforced in code, not comments: a bill already held costs **ONE** request
(merged, never refetched whole), and `--congress N` **refuses to run in CI** with the
arithmetic in the refusal. `--since` defaults to **30 h**, not 24, so a late nightly cannot
open a gap. Live-verified end to end.
**This commit went RED in CI, and so did the next one. Both are FIXED — master is green
(D94 + addendum).** Two failures, same class, opposite signs:
- **A variable CI LACKS.** Task 4's new `/actions` call was unstubbed in
  `test_reingest_reexports_enrichment_not_none`. The local `.env` key made it reach the
  LIVE API and pass; CI has no key, so it raised.
- **A variable CI HAS.** Three new resume tests exercise `--congress`, which D90's own
  guard refuses when `CI`/`GITHUB_ACTIONS` is set. Not set locally, so they passed here
  and returned exit 2 there.

Both were a test asserting something about an environment it never ran in.
`tests/conftest.py` now hides the credentials AND clears `CI`/`GITHUB_ACTIONS`, so every
test starts from the environment CI actually provides.

**⚠ STANDING RULE #2 (D96 addendum) — lint with the DOT.** CI runs `uv run ruff check .`;
`uv run ruff check ingest/` is not the same command and will not see a new file under
`tests/`. That is exactly how the task-6 push went red on two over-long lines after every
local gate passed. Both pre-push commands, together:

    uv run ruff check .
    CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov=ingest.events --cov=ingest.topics --cov-branch --cov-fail-under=100

**⚠ STANDING RULE — a bare `uv run pytest` is NOT evidence CI is green.** CI is
reproducible locally; two red pushes were two chances to run this. Before pushing:

    CI=true GITHUB_ACTIONS=true uv run pytest -q --cov=ingest.metrics       --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify       --cov=ingest.legislation_stats --cov-branch --cov-fail-under=100

**Gates for task 4 (measured):** 452 passed, ALL CHECKS PASSED, ruff clean.

**Two bugs fixed during the task:**
- **The new tests wrote into the REAL `data/bills/`** (two files modified, both reverted).
  `export.BILLS_DIR` is an import-time constant AND `export_bill`'s default argument, so
  patching `ingest.cache.repo_root` moved the reads but not the writes. `run_activity` now
  resolves `out_dir` per run. **Hazard for any future test: `export.*_DIR` and the defaults
  built from them do not follow a patched `repo_root`.**
- **`run()`'s `fetch_errors` tuple lacked `TruncatedFetchError`.** `bill_actions()` raises it
  on a short page and on its dedupe-undercount guard, so one bad `/actions` response would
  have aborted the whole nightly instead of recording a retryable per-bill failure.

**▶▶ NEXT SESSION STARTS HERE.** Two independent tracks — pick either, they do not block
each other:
- **(a) Continue the backfill.** `git pull --rebase`, then
  `uv run ingest bill-activity --congress 118`. **73 of 19,315 done**; Congress 119
  (19,441) not started. Resumes by itself, safe to kill at any moment (D95a), prints
  what is left. Run it in your OWN terminal window, not inside a Claude session, so it
  outlives the session.
- **(b) Start task 6 (topics index).** `data/topics/index.json` — every policy area and
  CRS subject term with its bill count and bill ids, official vocabulary only (SD-33 4a:
  31 policy areas + 872 CRS terms, verbatim, no owner bundles this release). Buildable
  against the bills already on disk; behaves identically at 38,756. Then task 7 (site:
  Actions timeline on `/b/`, `/topics/`, Atom feeds), then task 8 (fold
  `ingest bill-activity --since` into the nightly — the daily digest cadence SD-33 chose;
  only `ingest events` is wired in so far, not the delta fetch).

**Before starting the backfill (checks 1-3 are DONE, 4-5 are the actual gate):**
1. ✅ **Rate-limit window is HOURLY** — confirmed 2026-10-01 (27 used after hundreds of
   calls that day). D88 had left this open. It mattered: a DAILY window would have made the
   backfill ~8 days **and starved the nightly**, which shares the key.
2. ✅ **Downstream VERIFIED against real unvoted bills (D92).** A 300-bill chunk of 118
   was ingested and the whole pipeline run against it before pushing any data. Found and
   fixed two things nothing else would have: `/b/[bill]` built a page per FILE (would have
   published ~38,756 pages against 3(c)), and `check-source-links.mjs` asserted every bill
   record has a page. Now green: build 13,161 pages, **1,038 bill pages = exactly the voted
   set**, 43 tracked-but-unvoted bills correctly pageless.
   Still watched, not fixed: the loader holds every bill in memory
   (`site/src/lib/data.ts`) — fine at 1,081, unproven at 38,756. Build was 77 s here.
3. ⚠ **Banned-words scans `data/bills/` and action text is VERBATIM** (uneditable).
   Measured 0 hits across 520 real actions — the list is partisan-framing vocabulary absent
   from clerk prose. If one ever hits over 38,756 bills it is an **owner allowlist decision**,
   never an edit to government text.
4. ✅ **The nightly has landed** (`c14198c21 data: nightly 2026-10-01`) and the backfill
   now runs alongside it. It fires 09:15 UTC / 04:15 CDT daily and **stays ENABLED** — D91
   reversed D90's plan to disable it, because a chunked backfill may span two weeks and
   that is too long without fresh votes, metrics and grades.
   **It WILL conflict on `data/manifest.json` if it pushes mid-chunk** — it did on
   2026-10-01. That file is DERIVED: take either side, then `uv run export` to regenerate.
   Never hand-merge it. `test_committed_manifest_matches_regeneration` checks the COUNTS;
   the `commit`/`generated_at` fields are injected and are allowed to lag.
5. ✅ **Resume is free, and it is the DEFAULT (D91).** Was ~5 h (the 20 h cache TTL meant
   a resume refetched ~19k `/actions`). Now 1.787 s and zero requests, measured. A backfill
   skips finished bills unless you pass `--refresh-all`; the `--since` delta path never
   skips, by design, or the nightly would stop refreshing the timelines it exists for.

**THE BACKFILL — run it in chunks, it is interruption-proof (D91).** The laptop goes home
at the end of the day, so **a backfill now RESUMES BY DEFAULT**: it skips every finished
bill before any network call. **Measured: 1.787 s and zero requests** over already-held
bills. A chunked run costs the same as a continuous one, plus the re-enumeration below.

Each working session, three commands:
```
git pull --rebase                                   # take the nightly's commit first
uv run ingest bill-activity --congress 118          # resumes; kill it whenever, it is safe
uv run ingest events && uv run ingest topics && uv run export   # <- NOT optional
git add data/ && git commit -m "data: bill timelines (118)" && git push
```

**▶ The third line is new as of D95 and a chunk push WILL go red without it.** Two
committed artifacts are derived from `data/bills/` and are checked on every push:
`data/events/` (**invariant 8**), `data/topics/index.json` (**invariant 9**) and `data/manifest.json`'s counts
(`test_committed_manifest_matches_regeneration`). Commit fresh timelines without
regenerating both and CI fails on your own push — the next nightly would heal it, but the
red run in between is exactly the D94 lesson. Both commands are offline and take seconds.
Then the same with `--congress 119`. Do 118 first — it is a closed Congress, so nothing
drifts under the run. The startup line prints exactly how much is left and the ETA.

- **`git add data/`, not `data/bills/`.** A run can also write `data/quarantine/`; leaving
  that dirty makes the next morning's `git pull --rebase` refuse.
- **If `pull --rebase` refuses because the tree is dirty**, you stopped a chunk without
  committing. Commit first, then pull.
- **Ctrl+C is safe at any moment.** Each bill is exported as it finishes, and a file torn
  by a kill mid-write is re-ingested next run rather than counted as done.
- **`--refresh-all`** is the opt-out that re-does finished bills. You will not want it.

**Gates for 4b/4c (measured):** `uv run pytest` **460 passed**, `uv run checks`
**ALL CHECKS PASSED**, `verify-recompute` OK (3,507 roll calls), `npm run build` 13,161
pages in 77 s, `npm run test:links` OK — all run with 43 real unvoted bills on disk.
**CI: both jobs green on `019da1727`** (the authoritative gate; see the standing rule above about local pytest).

**Measured rates (2026-10-01, not estimated):** 3.91 s/bill (23 bills in 90 s) — so the
~42-43 h total holds. Congress 118 = 19,315 bills, 119 = 19,441. Each resume re-enumerates
the Congress first: **~78 pages, ~7 min**, because the 250-record list pages take ~4.5 s
each (API latency, not our 1 req/s throttle). That is the per-chunk overhead; it is why a
few long chunks beat many short ones. **Never in CI** — 2,590 Actions minutes is more than
a whole month's free allowance (H24).

**The nightly STAYS ENABLED** (this reverses the D90 note). It fires 09:15 UTC / 04:15 CDT,
when the laptop is shut and no chunk is running, so the collision never happens; `git pull
--rebase` before each chunk covers the rest. Disabling it was sized for a 2-day continuous
run — a chunked run may span two weeks, and two weeks with no fresh votes, metrics or
grades is not acceptable.

**Then tasks 5-7:** events projection + the Astro endpoint (5/5b), topics index (6), and the
site work — Actions timeline, `/topics/`, Atom feeds (7). Remember pageless bills must link
to congress.gov, never to a `/b/` URL that does not exist, or `npm run test:links` fails. **The two hard cost constraints from D88
still bind and are exactly what task 4 must be built around:**
These are build constraints, not preferences, and getting either wrong overruns the free
GitHub Actions allowance:
1. **The one-time 38,756-bill backfill runs LOCALLY and is committed. Never in CI.** It is
   ≥ ~43 h ≈ 2,590 Actions minutes — more than a whole month's 2,000-minute allowance (H24).
2. **The nightly delta fetches `/actions` only for bills already known**, with the full
   detail+subjects+cosponsors set only for genuinely new bills. ~5–7 min/night. A full refetch
   of every updated bill is ~19–29 min/night and **does not fit** beside the D86 nightly.

Build order within V2-11 is unchanged from the plan: task 2 (`bill_actions()` +
`bills_updated_since()`) → task 3 (`BillAction` model) → 4 (ingest) → 5/5b (events + the Astro
endpoint) → 6 (topics index) → 7 (site: Actions timeline, `/topics/`, Atom feeds). Write the
`/actions` paginated branch against a synthetic payload — D88 could not exercise it live.

**PRIOR (2026-09-30):** D87 remediation committed + pushed as `64f34bbc5`; D86 state unchanged. **2026-09-29, D86 session — nightly cost fix.** Owner reported the GitHub
Actions bill; both nightlies since 09-28 died in 5 s (*"job was not started because recent
account payments have failed or your spending limit needs to be increased"*). The free
2,000-minute private-repo allowance was exhausted: `uv run ingest legislation` re-fetched all
639 members' lists every night — 3h35m of a 3h50m run — and only started running at all on
09-21 when D83 fixed the 2-minute crash that had hidden it. **Owner decisions (2026-09-29):
stay on free plans; option 1 = probe lifetime counts, re-page only changed members, weekly
full refresh.** Built as **D86** (`docs/decisions.md`): `congress_gov.member_lifetime_counts()`
(one `/member/{id}` call), `lifetime_counts` stored on each legislation record (schema
regenerated), `legislation.should_refetch()` (pure), `uv run ingest legislation --full`, and
`nightly.yml` passes `--full` on Sundays. Not evaluative, not a V2-N acceptance. Allowance
resets **2026-10-01** (owner read it in Billing); nightly resumes on its own.

**2026-09-30 — code review + full remediation (D87). COMMITTED + PUSHED: `64f34bbc5`**
(22 files, +1,096/−93; working tree clean, `master` in sync with `origin/master`).
Audit written to `code-reviews/review-2026-09-30.md` (0 Critical, 1 High, 5 Medium, 5 Low;
leave that file alone — the next review reads it as the baseline). **All 11 findings and the
dead-code inventory are fixed**; see `docs/decisions.md` D87 for the full record. Not a V2-N
increment and not evaluative: no metric, threshold, formula, or grade wording changed, and the
only `data/` diff is a comment in `accepted-quarantine.yaml`.

Gates all green locally: `pytest` **363 passed** (was 341), `ruff` clean, `uv run checks` ALL
CHECKS PASSED, `astro check` 0 errors, `astro build` 13,161 pages.

**Owner decisions taken 2026-09-30 (all three asked in plain language):**
1. **Mississippi is a CAREER grade.** Owner: numbers and trends must span a legislator's whole
   career, not just the newest session. So the High finding's proposed fix (delete the old
   session on rollover) was REJECTED — deleting would have reset every MS member to 2027-only.
   The partition now ACCUMULATES, matching the federal side (118th + 119th). `ingest ms` merges
   terms, keeps earlier sponsorship, marks departed members `serving: false` in place, keeps
   the crosswalk, counts the whole partition, and lists every session in the manifest.
2. **Privacy page: strip the no-logging claims** (owner: "impossible for what I need to do…
   getting stripped in a later session"). Removed, not reworded — no Cloudflare copy added,
   since he did not pick that option. **V2-7 still owns the full rewrite.**
3. **Absence explanations stay Mississippi-only** and `/methods` now says so plainly, rather
   than widening the search (~50× the H9 review queue).

**▶ OWNER TASKS this opens (both before January, when LegiScan publishes the 2027 session):**
- **Threshold review for career-span MS numbers (§0.8).** No formula changed, but once two
  sessions are on disk the numbers MEAN a career span. He ratifies whether
  `data/config/thresholds.yaml` still reads right for that.
- **Per-session browsing / trend display is DEFERRED to its own increment.** The MS index
  still lists every member file, departed legislators included, with no year labels and no
  trend view. That is the gap between "career numbers are correct" and "career trends are
  visible", which is what he actually asked for.

**Spec/code disagreement, recorded not fixed:** `banned_words.ALLOWLIST` allowlists
`site/src/content/glossary.md`, which does not exist (spec §CS and Appendix B describe the
glossary as existing). Harmless today. Owner decides: build the glossary page, or drop the
allowlist entry.

**Not confirmed, stated as unconfirmed:** whether Congress.gov's `cosponsoredLegislation.count`
moves when a cosponsorship is withdrawn (needs one live `/member/{id}` call). The D86 probe's
blind spot is documented either way and bounded to 7 days by the Sunday `--full` run.

**D86 acceptance (as recorded 2026-09-30; the CI half is now DONE — see head):**
`gh run list --workflow=nightly.yml --limit 4`
- The **first** nightly on/after 10-01 re-pages everyone once (no record has counts yet):
  expect ~4 h and a commit touching all 639 `data/legislation/*.json` (adds `lifetime_counts`).
- The **next non-Sunday** nightly is the acceptance: **PASS = < 1 h and the log prints
  `N re-fetched + M unchanged (kept) of 639 members`** with M in the hundreds. FAIL = read the
  legislation lines; if every member re-fetched, the stored counts are not matching the live
  probe (compare one member's `lifetime_counts` to `/member/{id}` by hand).
- Sundays run `--full` (~4 h) by design. Budget: ≈ 900–1,400 min/month vs 2,000 free.
- **(SUPERSEDED 2026-10-01: `36743621950` was rerun and passed — see head.) As of 09-30, CI had validated neither D86 nor D87; two runs were waiting on the reset:**
  - `36743621950` (commit `64f34bbc5`, D87) — failed in **3 s**, both jobs, no log retrievable.
  - `36616400293` (commit `7fdb5289d`, D86) — failed in 8 s, same shape.
  Both died on the billing block before executing a single step, so neither says anything
  about the code. Today's 15:56 nightly (`36740496981`) died the same way in 4 s.
  **After 10-01: `gh run rerun 36743621950` first** (it contains D86 + D87 together, so one
  green run covers both), then confirm green before trusting the nightly. Local gates were
  green for both: ruff, pytest 363, `uv run checks`, `astro check`, `astro build`.

**D84 + D85 acceptances: both PASSED** (checked 2026-09-29). Nightly green 09-24 (dispatch),
09-25, 09-26, 09-27 with data pushed 09-24/25/26 (09-27 quiet); ci run `36016184179` green on
the bumped actions (the `36015693164` run was superseded/cancelled, not failed).

**V2-11 task 1 remains the next increment** (unchanged; `.env` has a working key). Neither
the D86 nor the D87 session touched it. Priority is still V2-11 → V2-7 → V2-8 → V2-12 → V2-13,
and note that **V2-7 (truthful /privacy) now has less to undo**: D87 deleted the three false
claims, so V2-7 is a rewrite on a page that is currently silent rather than wrong.

**PRIOR (2026-09-24): CI repair session (D84 + D85)** — owner reported recurring
`nightly: All jobs have failed` emails. Two separate causes found; both fixed and pushed; both
acceptances were still in flight when the session ended.

**Acceptance checks as they stood at that handoff (both since PASSED — see head):**
`gh run list --workflow=nightly.yml --limit 3 && gh run list --workflow=ci.yml --limit 3`
- **D84 acceptance — nightly run `36015043828`** (workflow_dispatch, on `368dbf088`, started
  2026-09-24T14:44:59Z, expect ~5h → done by ~19:45Z). **PASS = it commits AND pushes a data
  diff** (`data: nightly 2026-09-24`, sweeping up the lost 09-23 data too). That push step is
  the exact thing that failed 09-21 and 09-23. FAIL = read the log's last 20 lines; if it is
  still a push rejection the rebase loop did not work and D84 needs rethinking.
- **D85 acceptance — ci run `36015693164`** (push, on `19cb27466`, started 14:50:14Z, minutes
  not hours). PASS = green. **FAIL = revert `19cb27466`, do not debug forward** — the action
  bump is the only variable in it.
- The earlier ci run `36014530868` (D84's push) shows `cancelled`: superseded by the D85 push
  moments later. Not a failure; the D85 run covers both commits.

**What was wrong (both fixed):**
1. **D84 — the nightly threw away green nights.** Last instruction was a bare `git push`; the
   job runs 4–6h between checkout and push, so any commit landing on `master` in that window
   made it non-fast-forward. Runs `35622111686` (09-21) and `35872806073` (09-23) both died
   there **after every gate had passed** — 09-23 discarded commit `b7e65fbfb`, 258 files, two
   new Senate rolls, `ALL CHECKS PASSED` + `verify-recompute: OK` on 3,503 roll calls. Fixed
   with fetch + rebase + bounded 3-attempt retry, never `--force`. Commit `368dbf088`.
2. **D85 — actions were on the deprecated Node 20 runtime.** The `Node.js 20 is deprecated`
   line in the failure emails was NOT the cause (it prints on green runs too), but the grace
   period ends, so all 11 refs across all 3 workflows were bumped. Commit `19cb27466`.
   **DO NOT "fix" `astral-sh/setup-uv@<sha> # v10.2.0` back to `@v10`** — setup-uv stopped
   publishing major tags at v8 on purpose and `@v10` 404s. See D85.

**Also this session:** the scheduled run `36011225686` was cancelled (it checked out `master`
at ~14:14Z, three minutes before the doc-sync push `6188ac17d` landed, so it was already doomed
and predated the fix). No data is lost either way — ingest is incremental against the live
record. **`.env` now exists on the build machine** with a working `CONGRESS_API_KEY` (verified
live: HTTP 200, HR 1 / 119th, and the `/actions` sub-resource V2-11 needs is reachable — 59
actions on that bill). **V2-11 is now unblocked and is still the next increment.**

**Known gap, not a blocker:** `CachedResponse` (`ingest/cache.py`) exposes only
`path/text/status/from_cache/ext` — no headers. H23 (the per-key hourly rate limit) is reported
in `X-RateLimit-*` response headers, so V2-11 task 1 needs either header capture added to the
cache layer or a one-off raw `httpx` probe outside it.

**Failure history, disambiguated:** 09-18/19/20 (2-minute failures) = the D83 quarantine issue,
FIXED. 09-21 + 09-23 (multi-hour failures) = the D84 push collision, FIXED. 09-22 green.

**PRIOR (2026-09-24, same day — detail behind D84 above): nightly push-collision fix**
session — the owner reported recurring `nightly: All jobs have failed` emails. **Root cause found and fixed; the
Node 20 deprecation line in those emails is NOT the cause** (it is a runner warning that also
appears on green runs). The job's last instruction was a bare `git push`; steps 1–5 run 4–6
hours between checkout and that push, so any commit landing on `master` in that window makes
the push non-fast-forward. Runs `35622111686` (09-21) and `35872806073` (09-23) both died there
**after every gate had passed** — 09-23 threw away commit `b7e65fbfb`, 258 files, two new Senate
rolls, `ALL CHECKS PASSED` + `verify-recompute: OK`. Fixed with fetch + rebase + bounded
3-attempt retry, never `--force` (D84, `docs/decisions.md`). Not a V2-N acceptance; nothing
evaluative changed.
- **ACCEPTANCE PENDING:** one green `nightly` run that commits and pushes a data diff. The fix
  cannot be verified this session (a run takes ~5h). **Next session: check it.**
- **Tonight's in-flight run `36011225686` will still fail** — it checked out `master` at
  ~14:14Z, and the D82/doc-sync push `6188ac17d` landed at 14:17Z, three minutes later, so it
  is already carrying a doomed push and predates the fix. Nothing to do about it; the fix only
  takes effect on runs that start after it. No data is lost: ingest is incremental against the
  live record, so the next green run re-collects 09-23 and 09-24 together.
- **Failure history, disambiguated:** 09-18/19/20 (2-minute failures) = the D83 quarantine
  issue, FIXED. 09-21 + 09-23 (multi-hour failures) = this push collision, D84. 09-22 was green.

**PRIOR (2026-09-24, earliest): orientation + doc-sync** session — no code, no data, no
increment work. Read-only cross-check of this file against the tree; three stale annotations
corrected (flagged `[corrected 2026-09-24]` below). Tree clean and in sync with
`origin/master`; `uv run pytest` re-run **330 passed** (unchanged). **One new blocker found,
recorded in START HERE below: there is no `.env` on the build machine**, so
`CONGRESS_API_KEY` is unset locally and V2-11 task 1 cannot run until the owner supplies it
(H1 is ✅ — the key exists as a GitHub repo secret, but GitHub cannot display it back;
re-request at https://api.congress.gov/sign-up/ or take it from the api.data.gov account).
No other finding: no hardcoded D82 counts exist in `site/src` (checked), so the live copy
tracks `data/manifest.json` and has not drifted.

**PRIOR (2026-09-23, evening): SD-32 doctrine + priority** session — the owner
asked for **profiles, topic subscriptions, bill tracking, and email/text alerts**, reviewed the
plan, and ratified **SD-32: the site may read and collect the user data its features need**
("change anything in the plans or other docs that stop the site from reading or collecting
data"). Every doc that forbade reading/encryption-only storage was amended (spec §0.4.3, SD-28,
§3, §5, §7 V2-7/V2-8, §8, §10, build order; CLAUDE/AGENTS/CONTRIBUTING/kickoff; full list in
`docs/decisions.md` SD-32). **Priority is now V2-11 → V2-7 → V2-8 → V2-12 → V2-13** per
`docs/plan-subscriptions-and-alerts.md`; **V2-6 deferred.** V2-5 remains CLOSED (owner-ratified
earlier today, D82/D83 green). Docs-only session: no code, no data, nothing built. Gates re-run on the amended tree:
`uv run checks` ALL PASSED, `uv run pytest` 330 passed. Committed + pushed as
`SD-32: ...` (docs-only; not a V2-N acceptance).
- **Left TRUE on purpose:** the live `/privacy` page still says nothing is collected. That is
  true today; Value #1 (unamended) means it is rewritten in V2-7, atomically with the first
  collecting feature — not before.
- **Spec doc-sync still open (not blocking):** §7 V2-5's "lowest N%" headline sentence and the
  metric table's "Party unity %" row are stale; owner has not yet authorized those two edits.

**▶ NEXT SESSION — START HERE: V2-11 task 1** (`docs/plan-subscriptions-and-alerts.md` §5).
**BLOCKED on one owner action** *[corrected 2026-09-24 — this line previously read "No owner
input is needed to begin", which was wrong]*: step 1 makes live authenticated Congress.gov
calls and there is **no `.env` on this machine**, so `CONGRESS_API_KEY` is unset (H1 is ✅ done
— the key is a GitHub repo secret, unreadable after the fact). Unblock either way:
`cp .env.example .env` + paste the key (source: https://api.congress.gov/sign-up/, free, by
email; or the existing api.data.gov account), **or** run step 1's probe as a
`workflow_dispatch` in CI where the secret already lives. Steps:
1. Verify the Congress.gov `/bill` list (update-date filter/sort, page size) and
   `/bill/{c}/{type}/{n}/actions` endpoints live through the existing cached client; confirm
   the key's hourly limit (H23).
2. Measure: bill universe for the 118th–119th; bills updated per day; projected built file
   count for each option of plan decision 3 (site was **13,093 files / 20,000** at the last
   measured build, 2026-08-14 — re-measure with `npm run test:file-count` before projecting).
3. Put plan decisions 2, 3, 4, 6, 7 to the owner in ONE plain-language message with those
   numbers. Then build V2-11 tasks 2–9 on his answers; commit `V2-11: <what>` per gate.
V2-11 is zero-collection (static feeds/topics/timelines), so the V2-7 privacy gate does not
apply to it; it applies to V2-8/V2-12/V2-13 (the site MAY store readable data — SD-32 — but
`/privacy` must be true first).

**Still open, lower priority:** homepage redesign (owner brainstorming; three layout
concepts drafted, none chosen; buildable under the standing restructure authorization once he
picks). Grade-over-time V2-6: only two commits of `data/grades/attendance.json` exist
(2026-08-13, 2026-09-21) — deferred by SD-32 until history is worth charting.

**PRIOR (2026-09-23, earlier): V2-5 CLOSE** — owner ratified V2-5 COMPLETE: IA restructure
(D72), Nocturne (CP1–CP9), D81 metric swap, the factual headline "97% of bills introduced never
got a floor vote" (D82), D83 nightly accept-list; nightly ran GREEN 2026-09-22 (run
`35737604333`). The original "lowest N%" blocker was resolved by shipping a plain count (no H15
round two). Doctrine thread 1 from that sitting (relax "no collecting") is now RESOLVED by
SD-32; thread 2 (homepage) stays open above.

**PRIOR:** 2026-09-21, **nightly-failure fix** session — the `nightly` workflow had
failed every night since V2-1 on 4 permanently-quarantined House rolls (voters outside the
covered roster on the roll date). Fixed with an owner-ratified **accept-list** (D83):
`data/quality/accepted-quarantine.yaml` makes KNOWN quarantines non-fatal while a NEW one
still fails loudly. Wired into house + senate ingest; gates green (ruff, pytest 330, §8
100%-branch, checks, verify-recompute). NOT a data fix — the 4 votes stay unpublished; whether
to correct the roster so they ingest is a separate owner call, left open.
- **NIGHTLY FIX (D83, 2026-09-21) — accept-list for known-quarantined rolls.** `nightly` ran
  `uv run ingest house-votes`, which returns nonzero on ANY quarantine; 4 rolls (`h-118-1-0001`
  M001200, `h-119-1-0001` G000578, `h-119-2-0130` + `h-119-2-0131` S001157) have been quarantined
  as `UnknownMember` since V2-1 (`2cedc532`) and re-quarantine nightly (quarantine deletes the
  votes file → `roll_is_final` False → re-fetch → re-fail). Committed data was byte-stable and
  `ci.yml` green throughout — the only symptom was the recurring failure email. Owner chose the
  accept-list (over: fix roster / investigate source / silence emails). `incremental.
  accepted_quarantines()` loads the reviewed id→reason map; a listed id → `accepted` (printed
  `note:`, run stays green), an unlisted id → `ms_failures` (still fatal). Both house + senate
  `run()` wired (senate empty today, prevents the same future loop). Acceptance = a green
  `workflow_dispatch` run of nightly.yml (quiet-night path: 4 rolls re-quarantine → note → no
  data diff → exit 0).

**PRIOR (2026-08-16) — V2-5 wide-eyed headline** session — the deferred landing
headline is now BUILT and owner-ratified (factual, no H15): **"97% of bills introduced never
got a floor vote" (D82).** Also that session: the D81 CI-red fix (§8 coverage, `675d9464`,
CI-green run 31956907062). Prior: Nocturne complete (CP1–CP9); the D81 metric swap.
- **V2-5 HEADLINE (D82, 2026-08-16) — owner-ratified, factual (no H15).** The long-deferred
  "wide-eyed" landing headline (H15 round two) turned out NOT to need a ratified threshold:
  orientation found it computable from EXISTING committed data (no data pull — the owner had
  authorized one, found moot). Of the **37,669** distinct bills covered members SPONSORED
  (union of `data/legislation/*.json`), only **1,011 (2.7%)** ever appear as a `RollCall.bill_id`
  → **36,658 (97.3%) never got a recorded roll-call vote**; 375 became law. Owner picked the
  "all measures / 97%" framing from three options (also offered law-track-only 97.7%, 118th-only
  97.2%). **Truth caveat, disclosed on `/methods#floor-votes`:** "floor vote" = recorded
  roll-call vote; **232 of the 375 enacted bills became law with NO roll call** (voice/UC), so
  the copy says "recorded floor votes," never "any consideration." A plain count (no cutoff, no
  grade, no member singled out) → §0.8 satisfied like the D81 swap; owner ratified the wording.
  - *[annotated 2026-09-24] The five counts above are the values AS RATIFIED on 2026-08-16
    and are kept verbatim as the record of what the owner approved. Nightlies have since
    grown the dataset; `data/manifest.json` `counts.legislation` reads, today:
    **38,303** sponsored bills, **1,038** with a roll call, **37,265**
    (97.3%) without, **384** became law, **237** of those with no roll
    call. **The ratified "97%" framing still holds** (97.29%) and no re-ratification is
    due. Nothing in `site/src` hardcodes any of these numbers (grep-verified 2026-09-24) —
    the dashboard and `/methods` read the manifest, so published copy has not drifted.*
  **Build:** `ingest/legislation_stats.py` (pure `compute(data_dir)`) → new recompute-gated
  `manifest.counts.legislation` block; `verify_recompute` **invariant 7** re-derives it byte-
  exact; dashboard flagship band (88px "97%", exact counts inline, methods link — non-clickable,
  see nuance below) + `/methods` "Bills and floor votes" disclosure. legislation_stats.py joined
  the **§8 coverage gate** (now 5 modules, 100% branch, 326 passed). **Gates green:** §8 cov,
  ruff, `uv run checks` (10/10 clerk + MS), verify-recompute (inv 7 named), export determinism
  (re-export adds ONLY the block), build 13,085, e2e (`/` + `/methods` axe/380px pass; one
  PRE-EXISTING `/federal` hydration-race flake, passes in isolation, untouched page).
  - **⚠ SPEC-ACCEPTANCE NUANCE to confirm with owner:** spec §7 V2-5 says "a headline number
    that cannot be clicked through to its full list may not render." This headline is a SYSTEMIC
    bill count (no per-member "who"), so no member-list reproduces it and a literal list = 36,658
    dead-bill rows (huge surface + file-count risk). Shipped as a **non-clickable flagship stat**
    with exact counts inline + a methodology link — consistent with the D72-shipped precedent
    ("Roll calls"/"Individual votes" are non-clickable factual stats). Flagged to owner: is that
    sufficient, or does he want a bill drill-down list? NOT built pending his call.
  - **⚠ OWNER TO-DO (spec text):** IMPLEMENTATIONv2.md §7 V2-5 still frames the headline as
    "the 'lowest N%' cut is a ratified threshold — H15 round two." The adopted headline is a
    FACTUAL count, not a lowest-N% cut, so H15-round-two was not needed; the spec line is now
    stale (like the D81 "Party unity %" row). Owner to amend or authorize the edit.
- **METRIC CHANGE (D81, 2026-08-15) — owner-directed, factual (no H15).** While preparing
  the H15 round-two headline options the owner said *"delete the party unity. This is a dumb
  stat."* and picked the cross-aisle definition *"option two."* Built `cross_aisle_support`
  (of the OTHER party's final-passage bills the member voted on, share voted Yea; floor-
  control caveat published in the docstring) and retired `party_unity` from the FEDERAL set.
  **Federal-only** by owner choice — MS keeps party unity (its `metrics.json` is byte-
  unchanged); `party_unity` stays in `METRICS`/`METRIC_LABELS` for the MS layer, federal
  build uses a new `FEDERAL_METRICS` subset. `FORMULA_SCHEMA_VERSION` 2→3. Gates green
  (checks, verify-recompute, pytest 319 + the known git-history transient, build, e2e 40).
- **D81 CI FIX (2026-08-16, `675d9464`, pushed).** D81 shipped **CI-red twice**: first ruff
  E501 (`ec49607a`), then the **§8 100%-branch coverage gate at 99.35%** — `metrics.py:273`
  (`cross_aisle_support`'s unattributable-sponsor `continue`, a new D81 branch never unit-
  tested) and `metrics.py:215` (`party_unity`'s no-own-party-totals `continue`, previously
  covered only *incidentally* by the federal recompute, which stopped computing party_unity
  once D81 dropped it from `FEDERAL_METRICS`). D81's "pytest 319 green" missed this because
  the §8 gate is a **separate invocation, not in pytest addopts**. Fixed with two dedicated
  unit tests (`test_party_unity_skips_roll_with_no_own_party_totals`,
  `test_cross_aisle_support_skips_bill_with_no_attributable_sponsor`) — coverage back to 100%
  on all 4 gated modules, 322 passed, ruff clean (verified with the exact CI command).
  **CI GREEN — confirmed run `31956907062` on `675d9464`** (python + site-and-checks both
  pass). D81 is now fully landed and green; the last-green before it was `dd3d8477` (CP9/D80).
  **⚠ OWNER TO-DO:** IMPLEMENTATIONv2.md's metric table still lists "Party unity %" — the
  builder did not edit the spec; the owner should amend that row (or authorize the edit).
  **Still open from that conversation:** the wide-eyed headline itself (owner unsure what it
  should be; open to pulling more data — e.g. full introduced-bill universe → "X% of bills
  never got a vote"), and whether to authorize that data pull (also enables a cosponsorship-
  based cross-aisle metric, the cleaner but data-hungry "option B").

**V2-1..V2-4 are COMPLETE and PUSHED** (through `4bb77d56`; CI green; live). V2-4 put
the first **attendance letter grades** (A–F, owner-ratified) live. **V2-5 is PARTIAL:**
the site's information architecture was rebuilt (landing dashboard + Federal/States
tabs + a filterable federal browser island) under the owner's standing authorization to
restructure and push without a per-change ask. But V2-5's own evaluative headline (the
"lowest N%" wide-eyed cut) is a NEW ratified threshold (**H15 round two**) and is
**DEFERRED to an owner sitting** — so **V2-5 stays OPEN; do not start V2-6.**
- **V2-5 DESIGN PASS (2026-08-14, IN PROGRESS) — Nocturne (owner's "Claude design"
  step).** The owner handed off `claudedesign/` (README + prototypes) — the parked
  visual-direction step — and asked to implement it: Nocturne dark theme, build-time
  charts, a multi-metric members explorer, `/compare`, and redesigned member/roll-call/
  methodology/MS views. Governance (D74, full detail in `decisions.md`): the pass is
  **design only within the still-OPEN V2-5** — it authors **no new evaluative constant**
  (colour is added *around* already-ratified V2-4 grade labels; the §6.8 grade-labels
  guard is untouched), so it needs no H15, and it does **not** close V2-5 (the "lowest
  N%" headline, H15 round two, stays owner-gated). Implementation order per the README's
  suggested sequence; committing green at each checkpoint.
  - **CHECKPOINT 1 — foundation (this commit).** `@theme` tokens + neutral-ramp remap in
    `global.css` (legacy pages carried to dark with no per-file churn; text shades kept
    ≥ WCAG-AA on ground + surface); **self-hosted Inter** (`site/public/fonts/`, latin +
    latin-ext variable woff2, OFL, preloaded, `swap`) replacing the prototype's Google
    Fonts link (§10.1); `Layout.astro` reshelled (1180px container, sticky dark nav,
    footer); `Badge.astro` recoloured (vote-class stays neutral — procedural, not
    evaluative); `MemberStats.astro` grade badge now tinted with its ratified band colour
    (colour-as-meaning reversal, D74); `MemberBrowser.tsx` controls recoloured (contract
    unchanged — drilldown intact). **Green:** `npm run build` 13,084 pages; grade-labels
    (5 pages/6 labels), metrics-sections (8+5), file-count (13,093/20,000); **e2e 31/31**
    (axe a11y + 380px on all 15 representative pages + the drill-down flow). Python suite
    unaffected (site-only). Lighthouse NOT re-run locally (CI≠local proxy, D73); the
    foundation is CSS+font only (no new JS/DOM weight), so perf delta is negligible — the
    real Lighthouse risk is the heavy redesigned views (later checkpoints), which will be
    calibrated against a known-passing baseline before commit.
  - **CHECKPOINT 2 — roll-call view + SplitBar (`44a7c59a`).** `charts/SplitBar.astro`
    (stacked position bar, contrast-adaptive inline counts). `/v/[roll]` rebuilt:
    chamber split + margin, per-party bars, tinted individual-positions grid; fixed the
    stale "Mississippi delegation" heading (member_votes has been chamber-wide since
    V2-1); absence disclosure preserved. `party_totals` typed on RollCall.
  - **CHECKPOINT 3 — overview dashboard + Histogram/BandLegend (`a17874e1`).**
    `charts/Histogram.astro` (21 index-based bins, band-coloured, index-math axis ticks;
    bins sum to 627, verified) + `charts/BandLegend.astro` (band chips → filtered federal
    list, drilldown href + verbatim labels kept). `index.astro` Nocturne hero + stat
    tiles (Members/Graded clickable; Roll calls/Individual votes non-clickable per §0.8)
    + histogram + by-class + chamber split + the single saturated States card. Every
    number derived; no new evaluative constant.
  - **CHECKPOINT 4 — two Tier-2 metrics (this commit).** `position_mix` (Yea/Nay share)
    and `cosponsor_enacted_rate` (cosponsored→law %) added to `ingest/metrics.py` +
    pydantic models — factual, no H15. Needed by the explorer + profile. metrics.json
    (10) + metrics.schema.json regenerated (manifest byte-stable). 100% branch coverage
    held on the 4 gated modules; checks (Tier-3 guard) + verify-recompute + metrics-
    sections (10) + ruff green. "Laws enacted"/"Became law" columns reuse enacted_rate.
  - **CHECKPOINT 5 — member profile + DotStrip (`0df1f1a4`).** `charts/DotStrip.astro`
    (linear distribution strip, deterministic scatter — no Math.random, byte-stable,
    focus marker). `/m/[member]` header rebuilt: identity + party dot, grade card (72px
    letter, band-colour tint, verbatim `data-grade-label`), per-CHAMBER rank line via
    `getMemberRanks().covered` (NOT 627), chamber attendance distribution strip, six fact
    tiles (incl. the new Yea/Nay share `position_mix`), state-delegation chart. Vote
    record + pagination unchanged; `MemberStats.astro` kept for MS pages. `data.ts` gains
    memoized `getGradedAttendanceByChamber()`. Percentile now renders on-page (**ADR
    D75**, reverses D69 safely — published value read verbatim, per-chamber denominator).
    Green: astro check 0, build 13,084, grade-labels, e2e 31/31 (a11y + 380px on graded
    + delegate pages). **✅ Lighthouse gate on `/m/A000055/1` (the ~440-dot DotStrip page)
    CONFIRMED GREEN — resolved 2026-08-15.** The DotStrip commit's own CI run
    (`0df1f1a4`) was cancelled when the D75 docs push superseded it, but HEAD `2192e879`
    (a superset — the DotStrip is present in its tree) ran the "Lighthouse (mobile perf +
    a11y >= 90)" step to a ✓ (CI run `31842462403`, job `site-and-checks`). CI's
    Lighthouse targets `/m/${firstMember}/1` = `/m/A000055/1`, so the real gate (the
    slower CI runner — the one that matters per D73/[[civic-ledger-ci-lighthouse-proxy]])
    passed WITH the DotStrip present. No DotStrip→SVG/bin change needed.
  - **CHECKPOINT 6 — members explorer (this commit; ADR D76).** `/federal` is now a
    multi-metric TABLE (attendance, party unity, yea share, sponsored, cosponsored,
    became-law), one row per member, static HTML + a controls-only island (chip filters,
    sortable headers, column-toggle). `lib/columns.ts` (`getExplorerColumns`) computes
    every cell + pulls each column's definition from the `ingest/metrics.py` docstring.
    **DOM budget was measured, not guessed** (the biggest risk): a throwaway 10-column
    spike hit **23,662 nodes / perf 93**; the shipped **6-column** lean table (bar as a
    `::before` pseudo = 0 nodes; value span dropped) is **10,964 nodes / perf 98 LOCAL**.
    ⚠ **That perf 98 was LOCAL only and it FAILED CI at 0.77** (D78 — the D73 trap again;
    `content-visibility` on `<tr>` is a no-op). **Fixed by D78** (block-row ARIA grid);
    checkpoint-6's original "full CI Lighthouse green" claim was a local-only overclaim.
    The four extra
    metrics (nay share, laws enacted, cospon→law, percentile) stay on the member profile
    (D76 §1 — perf carve-out, no evaluative number). Kept the fraction denominator a real
    `<i>` (SR-readable/copyable) over a leaner `::after` (D76 §2). Default sort = `name`
    (static == island default → zero reorder → CLS 0 on the Lighthouse page; deviates from
    the README's attendance-desc, D76 §3). `.sub` median line 38%-opacity → neutral-500
    (WCAG-AA contrast fix the axe e2e caught, D76 §4). e2e migrated (`li`→`tr`, select→chip
    active-state; kept `#member-list`, `data-grade`, `a[href^="/m/"]`, computed visibility,
    the `?grade=A&sort=grade` deep-link) + a header-click sort test added. **DEFERRED to
    the `/compare` checkpoint:** the explorer's exclude ("set aside") + compare-select
    per-row controls (they pair with `/compare`, best injected on hydration).

  - **CHECKPOINT 6b — /federal CI Lighthouse fix (this commit; ADR D78).** D76 shipped
    perf 0.77 on CI (local said 0.98). Root cause: `content-visibility` is a no-op on
    `<tr>` (table-internal boxes can't be containment contexts), so all ~11k nodes laid
    out on the slow CI runner. Rebuilt `/federal` as a `role="table"` grid of `<div>`s so
    `content-visibility` skips the ~620 off-screen rows. Validated by the NEW gate (local
    score is saturated/useless): **Style & Layout 83 ms vs the CI-green `/m/A000055/1`
    anchor's 258 ms** (was 663 ms). Same columns/cells/`data-*`; island row selector
    `tr[data-member]`→`[data-member]` + `aria-sort` on the columnheader; header-sort e2e
    hydration-race fixed with a `data-mb-ready` marker. **Follow-on (2nd fix push):** CI
    then failed at the E2E step — `axe.analyze()` on `/federal` TIMED OUT (>30s) on the CI
    runner. `content-visibility` makes axe SLOWER: reading each off-screen row's computed
    style for the colour-contrast rule forces the per-row layout cv defers (~25s local, >30s
    CI). Not a violation — bumped the a11y test timeout to 150s (`e2e/a11y.spec.ts`). Pushed
    ALONE, **CI GREEN — confirmed run `31898469095`** (build + checks + E2E + Lighthouse all
    pass; the S&L-83ms gate correctly predicted the Lighthouse pass). Lesson in
    [[civic-ledger-ci-lighthouse-proxy]].
  - **CHECKPOINT 7 — /compare (this commit; ADR D77).** New `/compare` view (README screen
    4): the site's ONE client-rendered page — the member set (`?m=A&m=B`, 2–4) is in the
    URL, invisible to a static build, so `Compare.tsx` renders it from a data blob embedded
    by `compare.astro` (server-rendered shell + 637-option picker + `<noscript>`→`/federal`).
    Reuses `getExplorerColumns`. Value-#1 care (D77): cross-chamber attendance is disclosed
    (shared-axis caption fires when chambers mix), delegates get grade-null cards + their 3
    vote metrics suppressed (D66), the C-grade tick reads the band min from data (not "95"),
    grade labels pass through the blob verbatim (§6.8 holds by construction — the label
    scanner can't see client-rendered HTML). Fixes the profile's dead "Compare with someone"
    link. Verified: build 13,085, astro check 0, e2e 36 (bare `/compare` a11y+380px + a
    `compare.spec.ts` that drives `?m=house&m=senate`, waits for the render, axe-scans it,
    checks remove-updates-URL). `/compare` deliberately NOT in `lighthouserc.cjs` (client-
    rendered → noisy gate). **Still deferred:** the explorer's multi-select "compare selected"
    → `/compare?m=…` and the exclude ("set aside") per-row controls (inject on hydration).
  - **CHECKPOINT 8 — methodology + Mississippi redesign (this commit; ADR D79).** The LAST
    Nocturne view. Converts methods.astro + states/ + ms/* from the neutral-ramp fallback to
    named Nocturne tokens + weights (font-semibold→font-medium — the ramp doesn't fix weight).
    **Methodology:** Grades section → a bands TABLE (dot + verbatim `data-grade-label` +
    range + population bar + count) + a "Set aside" card naming all 10 exceptions with
    human-readable reasons. Band counts = the dashboard's already-published distribution (no
    new evaluative constant, §0.8). Preserved: `data-metric`/`data-ranking` sections,
    `#grade-attendance` + `#mississippi` anchors, grade-labels. **Mississippi (`/ms`):** four
    count tiles + roll-calls-by-chamber (SplitBar) + roll-calls-by-category bars from the
    committed manifest counts, above the roster. HARD constraint kept: MS does NOT show
    federal grades (the "grades do not extend to the states" paragraph stays). Two a11y fixes
    the e2e caught: the bands table wrapped in an `overflow-x-auto` region (380px overflow),
    made `tabindex="0"`+labelled (`scrollable-region-focusable` — no focusable children).
    Green: astro check 0, build 13,085, grade-labels, metrics-sections (10+5), e2e 36.

  ### ▶ NEXT SESSION — start here (V2-5 Nocturne design pass — COMPLETE: views + polish)
  - **State:** CP1–CP9 done + pushed + CI-green. **Every Nocturne view is redesigned AND the
    polish items are done:** dashboard, roll-call, member profile, members explorer (CP6 +
    block-row grid CP6b + CP9 per-row controls), `/compare` (CP7), methodology + Mississippi
    (CP8). The `claudedesign/` handoff's view list is fully implemented.
    - **CP9 (D80): the explorer's per-row selection controls — DONE.** compare-select +
      exclude, INJECTED on hydration into statically-reserved 30px/24px gutters (absolutely
      positioned → CLS 0.0000; role="cell" wrappers → axe-clean; one delegated listener).
      Heading "Compare selected (n)" link + filter-card "Set aside by you" restore row.
      Perf re-measured the D78 way: `/federal` Style & Layout 81 ms vs anchor 153 ms
      (below), perf 0.98, TBT 5 ms. e2e 40 (exclude/restore, select-2→compare, axe scan).
    - **The two `/compare` next-touch fixes — DONE** (commit `2de090cd`): delegate flag is now
      data-sourced (`getMemberGrade → exception==="delegate"`); compare.spec.ts has a
      delegate-in-set case proving the D66 vote-metric suppression.
  - **Nocturne design pass is now COMPLETE — no Nocturne work remains.** One documented
    **spec gap, deliberately not built** (out of the polish scope): README screen 2 lists a
    "Not graded" grade filter chip that `MemberBrowser` lacks (its grade chips are A–F only).
    Small, self-contained if a future session wants it: add `{ v: "none", l: "Not graded" }`
    to the grade chip group + handle `grade==="none"` → rows with empty `data-grade` in the
    filter effect. NOT started; no owner input needed for it (it's a UI filter, not evaluative).
  - **V2-5 still OPEN + owner-gated:** the design pass adds NO evaluative constant so it does
    NOT close V2-5 — the "lowest N%" wide-eyed headline (H15 round two) is still the owner's
    to ratify. Do NOT start V2-6. Blocking gate ahead: V2-7 (privacy truth) before V2-8/9.
  - **Design source:** `claudedesign/README.md` (the spec) + `Civic Ledger - Redesign.dc.html`
    (reference; read the relevant view's inline styles per screen). Tokens: `@theme` in
    `site/src/styles/global.css` (named Nocturne tokens + the neutral-ramp remap that
    carries un-redesigned pages to dark). Charts live in `site/src/components/charts/`
    (SplitBar, Histogram, BandLegend, DotStrip — pure props in, markup out).
  - **REMAINING views (README order):**
    1. ✅ **Members explorer** (`/federal`, README screen 2) — DONE, CHECKPOINT 6 / D76,
       and the per-row **exclude** ("set aside by you") + **compare-select** controls now
       DONE too (CHECKPOINT 9 / D80) — injected on hydration into statically-reserved gutters
       (CLS 0, S&L 81 ms vs anchor 153 ms, axe-clean). Only screen-2 item not built: the
       "Not graded" grade chip (spec gap noted above; deliberately out of scope).
    2. ✅ **`/compare`** (README screen 4) — DONE, CHECKPOINT 7 / D77, plus the two
       next-touch fixes (data-sourced delegate flag + delegate test, `2de090cd`). The
       explorer's "compare selected" → `/compare?m=…&m=…` wiring and the exclude controls
       shipped with CHECKPOINT 9 / D80 (see item 1). Nothing outstanding on `/compare`.
    3. ✅ **Methodology + Mississippi** — DONE, CHECKPOINT 8 / D79 (see above). methods.astro
       + states/ + ms/* converted to named Nocturne tokens + weights; /methods gained the
       bands table + set-aside card; /ms gained count tiles + roll-call charts; MS keeps the
       no-federal-grades paragraph.
  - **Not committed (owner's call):** `claudedesign/` bundle + the untracked review docs
    stay untracked — do not push without asking.
- **V2-5 (prior session, PARTIAL) — information architecture restructure (D72).** The
  old flat ~540-name landing page + two-item nav became: **four-tab nav** (Home ·
  Federal · States · Methodology, active-aware); **`/` overview dashboard** (plain-count
  coverage line — 637 members / 3,463 rolls / 966,261 votes, facts not evaluative;
  Federal/States entry cards; a NEUTRAL A→F attendance-grade distribution, each band
  deep-linking into the filtered federal list, no band promoted to a headline number —
  §0.8 held); **`/federal`** browsable all-members list via the repo's first **Preact
  island** (`MemberBrowser.tsx`, `client:visible` — the full 637-row list is SSR'd into
  static HTML so it works JS-off, is crawlable + deterministic; hydration adds
  filter/search/sort and reads `?grade/?chamber/?party/?sort/?q` for tile deep-links);
  **`/states`** thin MS card → existing `/ms` (MS URLs unchanged). **Nav-truth fixes
  (D71 family):** federal breadcrumbs Members→Federal (`/`→`/federal`); `/ms`
  breadcrumb "U.S. delegation"→"States"; 404 updated; footer **"Source" link to the
  private repo removed** (false-availability, like D71). `check-grade-labels.mjs`
  extended to scan the dashboard + federal island (regex broadened for Preact's
  `data-grade-label=""`). **DEFERRED (H15 round two, owner away):** the "lowest N%"
  wide-eyed headline is a new evaluative threshold, not made here; V2-5 stays OPEN.
  **Green:** astro check 0, build 13,084 pages, grade-labels (5 pages / 6 labels),
  metrics-sections (8+5), links (7,104), file-count (13,090/20,000), e2e **31** (incl.
  `/federal` + `/states` a11y + 380px, and the dashboard→filtered-list→member
  drill-down); `uv run checks` all-passed. Python suite unaffected (site-only).
  **Lighthouse correction (D73):** the first `/federal` build passed local Lighthouse
  but FAILED CI (run `31769853844`, `/federal` mobile perf 0.8 < 0.9 — the island
  hydrated all 637 rows). Fixed by making the roster static Astro HTML with a
  controls-only island; re-verified. Visual/design polish is the owner's separate
  later "Claude design" pass.
- **V2-4 (this session) — attendance grade (D70, owner-ratified H15 round one).**
  Propose→ratify→commit (§0.8): the owner picked, in two plain-language sittings with
  the data, to grade **attendance only** (overall composite DEFERRED — "a formula I
  will have to work on"; no unratified formula publishes); **letter grades A–F**;
  **fixed bars** A ≥99 · B ≥97 · C ≥95 · D ≥90 · F <90; **labels** Strong/Good/Fair/
  Weak/Poor; **min-service** < 50 eligible → "Too few votes to grade". Ratified values
  live in `data/config/thresholds.yaml`. `ingest/scoring.py` (Tier-3 module) →
  `data/grades/attendance.json` (627 graded, 10 excepted = delegate/min_service/
  no_record — every member graded ∪ excepted, §6.5). No wall-clock (§6.3). §6.8 guard
  rewritten prohibition→disclosure (`grades_disclosure` + `check-grade-labels.mjs`);
  `verify-recompute` inv 6; §8 gate gains scoring.py + **classify.py** (D68 paid).
  Member pages show a grade badge on the attendance tile (delegates: none — caption
  explains); `/methods` gains a Grades section. **§6.7 doctrine flipped partially**
  (only attendance graded): index/methods intros flip; MemberStats caption splits
  ("combines nothing into an overall score" stays, "draws no conclusion" flips for
  federal); metrics.py site-level "draws no conclusion" scoped (churned 2 digests →
  metrics.json regen, values unchanged, NO formula-version bump). **D71: two live
  Value-#1 falsehoods fixed** — the home page said "Mississippi delegation" while
  listing all 637 members (V2-1 miss); methods.astro claimed "source code is public"
  (false since D59). **Green:** checks 6/6 (grading-coverage + disclosure pass),
  coverage gate 100% on 4 modules, verify-recompute (grades + rankings + 3,463 rolls),
  export (10 schemas), ruff, build 13,082 pages, grade-labels/metrics-sections/
  file-count/links, e2e 26, astro check 0. (pytest full-suite: the git-history test
  goes green once the metrics.json regen is committed, as in V2-1.)
- **V2-3 (this session):** member pages' five stat tiles now show each metric's
  rank within the chamber — `"{ordinal} of {N} in the {House/Senate}"`, linking to
  the ranking methodology (`MemberStats.astro` + `getMemberRanks` in `data.ts`).
  Factual position only, NO grade/label (D69). Percentile deliberately not on the
  tile (would print "0th percentile" on worst-ranked pages + round a published
  number at render time); it stays in the JSON + `/methods`. Non-voting delegates
  show ranks only on the bill metrics + an on-page caption explaining the vote-metric
  exclusion (D66, made visible where the reader sees it). MS members unchanged (no
  MS rankings until V2-10). The `§6.7` "combines nothing into an overall score"
  caption is KEPT (flips at V2-4). e2e gains a delegate page. **Green:** `astro
  check` (0), `npm run build` (13,082 pages — V2-3 enriches pages, adds none),
  `npm run test:e2e` (26, incl. delegate a11y + 380px), `npm run test:lighthouse`
  (7 URLs, 21 runs, perf/a11y ≥ 90, exit 0 — ran cleanly locally this time),
  python suite unaffected (site-only change; still 301 green). Design in **D69**.
- **V2-2 feature (this session):** `ingest/rankings.py` → `data/rankings/
  {metric}.json` (the 5 scalar Tier-2 metrics: attendance/party_unity/
  enacted_rate as pct, sponsored/cosponsored as count), ranked WITHIN chamber,
  standard competition ranking, percentile = % of chamber strictly below, chamber
  + party means (R-vs-D and R-vs-R) rendered on `/methods`. Recomputable from
  `data/metrics.json` alone — `verify-recompute` gains invariant 5 (byte-match).
  `check-metrics-sections.mjs` extended to the ranking sections; `nightly.yml`
  regenerates rankings after metrics. **Owner decision D66:** non-voting delegates
  are ranked on the 3 bill metrics only, excluded from attendance/party-unity
  (barred from final passage — not comparable), exclusion published on `/methods`.
  Design in **D66/D67**; `data-contract.md` documents `data/rankings/`.
  **Green:** `uv run checks` (6/6), `uv run pytest` (292 passed), `uv run
  verify-recompute` (rankings recompute + 3,463 rolls), `uv run export` (9
  schemas), ruff, `npm run build` (13,082 pages), `test:metrics-sections` (8
  metrics + 5 rankings), `astro check` (0).
- **§8 coverage tooling — DONE (D68).** pytest-cov added; a CI step enforces
  **100% branch** on `ingest/metrics.py` + `ingest/rankings.py` (both driven to
  100% with real tests — no pragma-ing plumbing, no metric-body edits). Gate is a
  dedicated invocation, NOT in pytest addopts (plain/subset pytest stays fast); the
  exact command is in "How to resume" above. `classify.py` joins the gate at V2-4
  with `scoring.py` (its pure `classify()` is covered; only the live-fetch `run()`
  isn't — spec-faithful per §7 V2-2's task line naming only metrics+rankings). The
  one coverage exclusion is `if __name__ == "__main__":` (documented, §8).
- **Doctrine (§6.7):** `methods.astro:26` ("nothing is summarized, characterized,
  or scored") is KEPT — a rank is a position, not a score; it flips at V2-4 with
  grades, not now.
- **Still owner-gated / open:** P4 build.db (SD-29 vs measured "flat files fine" —
  D63, do NOT build unilaterally). V2-1's D64 (legislation truncation guard —
  10 verified genuine zeros) is in git history / decisions.md.
Previous: 2026-08-13, end of the **V2-0 —
docs-truth pass** session (plus a same-session follow-up, D59: the repo was
found private, the owner chose to keep it that way, so `/privacy` +
`/corrections` + `docs/correction-process.md` were rewritten to stop claiming
a public repository). Before that: 2026-08-13, end of the **spec v2 adoption**
session (constitutional amendment — see "Spec v2 adopted" below). Before that:
2026-08-12, end of the **member-page stats rendering** session (D57 federal +
D58 Mississippi) — the review's post-INC-12 item. (Same day, earlier: INC-12
all 6 phases; and post-review hardening round 2 — R-1/R-4/R-6/R-5.)
**Git:** INC-1..INC-12 + member-stats closed & pushed. Sequence today: R-1..R-6
(`17ea5be`/`4ef6e3b`/`65f36b7`/`92702ac`); **INC-12** six commits
(`803e3044` P1 schema/partition, `5826ac62` P2 LegiScan ingest, `14b15cab` P3 checks,
`feebe206` P4 site, `0ec9051b` P5 nightly, `8ac74cb1` P6 docs) + `9096c1b5` (PROGRESS) +
`5876f838` (e2e screenshot flake fix, non-fatal); then **member-page stats**:
`5002e641` (**D57** — render the 8 federal Tier-2 metrics as a KPI stat-tile row on member
pages, no composite/score) and `aa16914c` (**D58** — compute + render the 5 MS metrics; new
committed `data/state/ms/legislation/` from all 4,006 bills + `data/state/ms/metrics.json`).
**Local == origin/master; CI GREEN on HEAD `aa16914c`** — **live site deployed** (verified
`/m/W000437/1` and `/ms/m/ms-12068/1` both render their Record summary). Now **6 checks**
(incl. `ms`, with MS metrics recompute-and-match), **254 py tests**, ruff, verify-recompute,
Astro build (**7,919 pages**), **24/24 Playwright e2e**, Lighthouse, `astro check` 0 errors.
Classify verified byte-stable on the jurisdiction-migrated federal files (no phantom nightly
diff). The e2e 380px screenshot artifact is now fully non-fatal (a CI Chromium capture flake
had failed a passing layout check once).
**H4 + H5 DONE:** the site is **live at `civicledger.net`** via **Cloudflare Workers**
(Static Assets, deployed by **Workers Builds** on push — no `CLOUDFLARE_*` secret in GitHub
CI). Planned `.org` was taken → `.net`. Only remaining INC-9 acceptance box: observe one
untouched nightly commit + deploy on the next real data-change night (a real nightly was
**not** triggered this session — this local env has no secrets, so only GitHub Actions /
the owner's machine can run the live pipeline; confirm the first `data: nightly …` build's
author reads `github-actions[bot]`).
**Remote:** https://github.com/SeanisnotBrown/civic-ledger.git — **private, by
owner decision (D59, 2026-08-13).** Found private (not the public repo the spec
assumed) during the V2-0 session; owner chose to keep it private and have the
builder rewrite the site copy that had claimed a public repository (`/privacy`,
`/corrections`, `docs/correction-process.md`) instead of flipping visibility —
see the V2-0 section below and `docs/decisions.md` D59. Do not describe this
repo as public anywhere else in the docs or site.
**Untracked, local-only (NOT committed):** `TECHNICAL_REVIEW.md`,
`TECHNICAL_REVIEW_SUMMARY.md`, `civic-ledger-review-directive.md`, and
`PROMPT-A-fable5-spec-author.md` — the code review + directive that drove the
2026-08-12 session, and the spec-authoring prompt that drove the 2026-08-13 v2
adoption. The remediation backlog (R-1..R-6) is summarized below so it survives
even if these stay local. **Publishing them to the public repo is the owner's
call — do not commit without asking.**

> **PIPELINE ORDER (load-bearing, D24 + INC-7/8/10 + R-2/D46 + V2-2/D67):** `ingest members`
> (roster refresh FIRST — R-2, so vote coverage + unknown-member alarms read a fresh
> covered set) → `ingest {house,senate}-votes`
> → `ingest bills` → `ingest legislation` → `ingest classify` → `corrections` →
> `ingest metrics` → `ingest rankings` → `ingest grades` → `uv run export` → `uv run
> checks`. An ingest re-export resets every roll to the provisional `unclassified`, so
> **classify must run after any vote ingest**; **metrics must run after classify**
> (party-unity reads final `vote_class`) **+ after legislation**; **rankings (V2-2) and
> grades (V2-4) must run after metrics** (both derived from `data/metrics.json`; grades
> also read the ratified `data/config/thresholds.yaml`), and metrics/rankings/grades all
> run **before the nightly diff-gate** (derived — a change that only moves a rank or a
> grade must still reach the gate, D40/D67/D70); **export must run after any ingest** or
> manifest/schema drift fails. (`bills`/`legislation` are independent of classify;
> export/checks come last.)

---

## V2-1 — Federal data expansion (✅ COMPLETE — acceptance met 2026-08-13)

**Goal (unchanged from spec):** positions persisted for every serving member of
both chambers, 118th-119th; dataset fully recomputable; build scaled. Full
rationale/numbers/design in the `2cedc532` commit message and ADRs **D60-D63**
(`docs/decisions.md`). Two owner-ratified spec-adjacent decisions (fold into
`IMPLEMENTATIONv2.md` in a future session): **D61** (the 6 non-voting delegates
ARE included — excluding them broke full recomputability) and the roster-source
fix (merge `legislators-historical.yaml`, or 88 departed-118th members go
invisible to every check, reading green on a real gap).

**Scale now committed:** **637 members** (was 6), **966,261 member-vote rows**
(was 10,626), 3,463 rollcalls (4 quarantined rolls correctly publish nothing),
35,124 absence stubs sharded by congress.

**DONE + VERIFIED GREEN this session:**
- **P1-P3** (committed `2cedc532`): full roster + House (1,882/1,886, 4
  quarantined at 0.2%, 0 unexplained gaps) + Senate (1,581/1,581, 0/0) votes;
  new `ingest/coverage.py` (shared date-windowed eligibility + D61 exceptions:
  delegates, Speaker, 21-day seating-lag — all empirical/cited); `data/absences/`
  sharded by congress. Bug found+fixed: chamber-switchers invisible to their
  former chamber.
- **P5 (site) — DONE:** CI **file-count gate** (`site/scripts/check-file-count.mjs`
  → `test:file-count`, wired into `ci.yml` + `nightly.yml`, H14) — prints the
  built count, fails before the 20,000 Workers-Free limit; currently **13,082
  files, 6,918 of headroom**. `data.ts:getMemberVotes` moved from an
  O(members × rolls) per-page rescan to a one-pass memoized `Map` index (pure
  perf, identical output). Member-page pagination **NOT restructured** — file
  count is well under limit, so `PAGE_SIZE=200` stays (mechanical choice, D63).
  Site build green (13,082 pages), **24/24 e2e**, file-count gate green.
- **P6 (checks/docs) — MOSTLY DONE:** `checks/symmetry.py` + `verify_recompute.py`
  now use `coverage.py`/`expected_on()` (ingest + checks share one module, never
  drift) and the **subset (`<=`) invariant is upgraded to strict equality** —
  `member_votes` reconstructs `RollCall.totals` EXACTLY on every roll (the
  credibility payoff, D62). `checks/integrity.py` state="MS" hardcode removed —
  now cross-checks EVERY member against the clerk/detail XML (**10/10 House +
  10/10 Senate verified** against the independent official source). Quarantine
  now deletes any stale prior export (found via verify-recompute: the 4
  quarantined rolls were still publishing pre-V2-1 MS-only data). `party_unity`
  docstring flipped; manifest `covered_state` field removed (D62);
  `data/state/ms/metrics.json` + `data/manifest.json` regenerated. ADRs
  **D60-D63** written; `docs/data-contract.md` inverted (recomputability
  section + absence sharding path + member_votes scope). **`uv run checks`
  ALL PASSED; `uv run verify-recompute` green.**

**DONE this session (V2-1 finish) — the last gates closed:**
- **Federal legislation backfill COMPLETE — 637/637 members.** `ingest
  legislation` finished the 53-member tail from Congress.gov (cache-resumable).
  The exit gate flagged 10 members "no sponsored bill in congress {c}" — all
  **verified GENUINE zeros, not truncations**, and the unsound check was fixed
  (**D64**, see below). `data/metrics.json` regenerated over all 637 (the
  `sponsored`/`cosponsored` metrics count the whole 118–119 record, so e.g.
  Rubio reads 270, never a per-congress 0).
- **D64 — legislation truncation guard replaced** (commit `699f859b`). The 10
  flags were false positives of the `_sponsored_gaps` heuristic ("a served-
  congress zero can only be a broken fetch" — false). Causes: 4 served only days
  of the flagged congress (`S001197` Sasse 5d, `V000137` Vance 6d→VP, `R000595`
  Rubio 17d→State, `W000823` Waltz 17d→NSA), 4 late special-election seatings
  (`L000605`, `W000829`, `R000619`, `M001246`), 2 low-output former leaders
  (`P000197` Pelosi, `H000874` Hoyer — each 2 sponsored in 118–119, both 118th,
  **verified against the live API by a forced re-fetch**). Fix moves the Value-#1
  guard to where it is sound: `congress_gov.member_legislation` raises
  `TruncatedFetchError` on a premature-empty page (`offset < count`), and
  `legislation._count_regressions` fails on any congress that had records last
  run and now parses to zero. Catches a strict superset of the old heuristic,
  false-positives on none. Re-run after fix: exit 0, 637/637, no FAIL.
- **All acceptance gates GREEN** (working tree): `uv run checks` 6/6; `uv run
  verify-recompute` **exact** on 3,463 rolls; `uv run pytest` 282 passed (the
  git-history test flips green once the metrics commit lands — by construction);
  `uv run export`; `uv run ruff check ingest tests` (also fixed a pre-existing
  I001/E501 in house/senate_votes — commit `3851e0eb`); `npm run build` 13,082
  pages; `test:file-count` 13,086 files (6,914 under limit); `test:links` 7,104
  pages. Non-MS member page (`B001320`) renders the Tier-2 tiles with real values.
- **D65 — repo-size observation (spec V2-1 task 9):** `.git` grew 27→48 MB
  (134 MB legislation JSON packs to ~21 MB); `data/raw` (699 MB) stays gitignored.
  Well under the "few-hundred-MB" escalation line — no LFS/split, nothing for the
  owner on size.

**Still open / owner-gated (unchanged):**
- **P4 — build.db (SD-29) — NOT built; owner decision (D63).** Flat files hold
  at full scale (all gates green). SD-29 says build it at V2-1; the archived
  `inc-12-plan.md` framed adoption as trigger-based. Owner's call — do NOT build
  unilaterally, do NOT treat as done.
- **`git push`** of this session's three commits (`699f859b`, `3851e0eb`, + the
  V2-1 data commit) — private repo, owner's call whether/when to push to origin.

**Acceptance: MET.** `uv run checks` ✅ · `uv run verify-recompute` ✅ · `uv run
pytest` ✅ (post-commit) · `npm run build`/file-count/links ✅. V2-1 is the
blocking gate for V2-2/V2-5 — now clear.

---

## V2-0 — Docs-truth pass (2026-08-13) — ✅ COMPLETE

First v2 implementation increment (hand-off from `docs/kickoff-v2.md`), all 7
tasks from `IMPLEMENTATIONv2.md` §7 V2-0 done, zero behavior change:

- `docs/data-contract.md` — `named_measure_mismatch` fail-closed text (stale
  since D42 superseded D39) rewritten to describe the shipped stance-vs-
  passage-vote mechanism. The "deliberately NOT recomputable" section is
  untouched per the task (still true until V2-1).
- `CONTRIBUTING.md` — four-values paragraph replaced with the §0.4 amended
  values (evaluative-label disclosure standard, collect-minimum/encrypt-belief);
  `§6.11` → `§6.9`; both the LLM-policy and values sections now point at
  `IMPLEMENTATIONv2.md`.
- `docs/PROGRESS.md` (this file) — the stale "Current increment: INC-11"
  heading converted to `**(historical — INC-11)**` (matching the INC-10..
  INC-5 style below it); the four stale "Next: INC-N — NOT STARTED" lines
  (INC-10/INC-9/INC-8/INC-6) deleted; the stale "no CLAUDE.md file" note
  corrected; untracked-file list corrected to 4 files (added
  `PROMPT-A-fable5-spec-author.md`).
- `ingest/config.py` — module docstring's false claim of an existing
  worker↔ingest `K_ANON` equality test reworded to state the Worker (V2-8)
  doesn't exist yet.
- `docs/HUMAN-TASKS.md` — H14–H19 rows added (§1 of `IMPLEMENTATIONv2.md`);
  impact narrative refreshed with which v2 increment each blocks.
- `ingest/checks/banned_words.py` — module docstring's `IMPLEMENTATION.md`
  citation (now archived) reworded to `IMPLEMENTATIONv2.md` §6.4.
- **H16 (branch protection)** — NOT enabled; per the task, the owner does the
  click (GitHub → Settings → Branches). The builder's read-only pre-check
  (`gh api repos/.../branches/master/protection`) 403'd — see the flag below.

**Unplanned but load-bearing finding, resolved same session:** while
pre-checking H16, `gh repo view` showed the GitHub repo is **PRIVATE**,
contradicting `IMPLEMENTATIONv2.md` §3 ("the client is open source"),
`docs/correction-process.md`, and — most importantly — the LIVE site:
`site/src/pages/privacy.astro` and `corrections.astro` both asserted "the
public repository" as fact. Flagged to the owner as a possible Value #1
issue. **Owner decision (D59): keep the repo private; rewrite the site copy
instead of making it public.** Done same session: `privacy.astro` +
`corrections.astro` rewritten to drop every public-repository claim (the
corrections log itself stays genuinely public — it's rendered from
committed `data/corrections.json` regardless of repo visibility — but the
now-dead GitHub issue/commit links were removed, since a private repo 404s
them for a visitor); `docs/correction-process.md` §1 reworded (no public
issue tracker exists today — a real, currently-unbuilt gap, not decided
whether/how to fill); `docs/HUMAN-TASKS.md` H3/H16 corrected. Full detail in
`docs/decisions.md` D59. **Left alone, on purpose:** `IMPLEMENTATIONv2.md`
§3's "open source" line (spec text — the owner's call to amend, not the
builder's) and the internal (non-public-facing) "public repo" docstrings in
`ingest/verify_recompute.py`/`models.py`/`legislation.py`/`ms_metrics.py`
(lower priority — nothing rendered publicly reads them).

**Acceptance met:** `uv run checks` (6/6) + `uv run pytest` (254 passed) +
`uv run ruff check ingest tests` all green; `git status` shows only the six
files above touched, nothing under `data/`; `cd site && npm run build`
green, 7,919 pages (unchanged count — confirms zero behavior/data change).

---

## Spec v2 adopted (2026-08-13) — constitutional amendment, docs-only session

The owner amended the founding values (evaluative grading in scope; user-data
collection in scope; never-ask rule scrapped; federal-first pivot with a
dashboard landing page). This session (Fable 5, spec-author role — no code):

- **`IMPLEMENTATIONv2.md`** authored at the repo root — the sole spec going
  forward. Its §CS states what exists (don't rebuild) and what doesn't (don't
  assume); Appendix B is the disposition table proving nothing true was lost.
- **Archived unchanged via `git mv`** to `docs/archive/2026-08-13-pre-v2/`:
  `IMPLEMENTATION.md` (v1), `civic-ledger-scope.md`, `docs/inc-12-plan.md`
  (+ archive README explaining supersession).
- **ADRs SD-21..SD-31** appended to `docs/decisions.md`: the four amendments,
  the five owner-resolved decision gates (grading = category grades + fixed
  overall, SD-26; threshold propose→ratify→commit, SD-27; client-side-encrypted
  accounts, SD-28; JSON contract + build.db, SD-29; MS preserved then folded in,
  SD-30), and the SD/D renumbering that ends the D19 collision (SD-31).
- **`.claude` → `CLAUDE.md`** (git mv; the bare `.claude` filename was never
  auto-loaded by Claude Code) and rewritten for v2; `docs/kickoff-v2.md` added
  for the implementing session.
- **Verified after the moves:** `uv run pytest` 254 passed; `uv run checks`
  ALL PASSED — nothing reads the archived paths.

**V2-0 is now done — see the "V2-0 — Docs-truth pass" section above.** Next
actionable is **V2-1** (federal data expansion, the blocking gate for V2-2/
V2-5) — but it opens with a delegate/territory-coverage question that
`IMPLEMENTATIONv2.md` §0.1 flags as a MUST-ask, so it waits on the owner
(see this session's message). This ledger continues in this file (v2
increments log here, newest-first, same conventions).

---

## Post-review hardening (this session, 2026-08-12)

A code review (`TECHNICAL_REVIEW.md`, local/untracked) graded the INC-0..INC-11 build
(no Blockers; dataset verifies green) and proposed remediations **R-1..R-6** plus two
owner decisions. **Done this session:**

- **Grading reframe** (owner decision — commit `3847950`, ADRs **D19/D20** in
  IMPLEMENTATION.md): grading is transparent + **reader-adjustable** — weights live in
  the reader's browser; the site **never publishes a score it chose**. "objective"
  language removed where it implied the site grades. PAC "cost per vote" replaced with a
  donation↔vote **adjacency timeline** (adjacency, not conclusion). Guard clarifications:
  the §5 Tier-3 / INC-15 "no composite" ban is on the *build/publish* path only — the
  reader's browser may compute a grade client-side (D19). Also edited
  `civic-ledger-scope.md`. No code/data change.
- **R-3 — historical-retention scaffolding** (commit `fd9a108`, ADR **D45**):
  `data/metrics.json` now carries `schema_version` (manual formula-generation stamp) +
  per-metric `digest` (newline-normalized `sha256(source)[:16]` — formula identity, so a
  number states which formula produced it; CRLF/LF-normalized to hold D40 determinism
  cross-platform). Git is the supported metric time-series: `ingest metrics history
  <bioguide> [--metric <key>]` extracts the `(commit, generated_at, schema_version,
  metrics)` series; recompute-at-a-past-commit documented in `data-contract.md`.
  Materialized `data/metrics/history/` deferred until a trend UI needs it. Member metric
  values byte-unchanged.
- **R-2 — membership-churn resilience** (commit `f0c0f70`, ADR **D46**): nightly runs
  `ingest members` **first**; House `parse_rollcall(covered=…)` raises `UnknownMember` on
  an unrostered MS voter → quarantine → fail (parity with the Senate path); `metrics._load`
  raises on an orphan position (backstop); `symmetry.coverage_gaps` +
  `verify_recompute.check_dataset` now flag `got−expected` too; `legislation` sanity check
  relaxed to congresses the member actually **served** (pure `_sponsored_gaps`). Also
  fixed a latent `E501` in the R-3 `metrics history` help line. No data change.

### Round-2 remediations — DONE this session (R-1, R-4, R-6, R-5)

Whole review backlog (R-1..R-6) is now closed. Sequencing per the review was R-1 first
(gates H8), then R-4/R-6/R-5. None blocked INC-12.

- **R-1 (M-1/M-2/M-3/M-6) — curation hardening, GATES H8 — DONE (`17ea5be`, ADR D47):**
  (a) statement id now `{member}-{date}-{sha8(source)}-{sha6(text)}` so two different
  quotes from one source+date no longer overwrite (done now — corpus empty — so never a
  published-id migration); (b) `Statement.date` gets an ISO validator, the Flask app
  validates date+specificity at CAPTURE time (never burns an SPN save) and pops the draft
  only on a successful save; (c) single statement loader `ingest/statements_io.py` — metrics
  EXCLUDE dead-archive statements (no `named_measure_mismatch` leak through the metric side
  door), symmetry/archive_links include them, export counts records; `data.ts` is the
  documented TS mirror. `FORMULA_SCHEMA_VERSION` **1 → 2**. (d) CSRF/loopback-Origin guard
  on every curation POST. Removed zero-caller `capture_and_save`.
- **R-4 (M-4/M-5) — truth guards — DONE (`4ef6e3b`, ADR D48):** `attendance.pct → None`
  when `eligible == 0` (`AttendanceValue.pct: float | None`; metrics.schema.json → number/
  null); absence edit path is trim-only (edited reason must be a non-empty, whitespace-
  normalized substring of the verbatim CREC text). metrics.json regenerated; no current
  member value changes.
- **R-6 (L-1/L-2/L-3, §4 delete) — DONE (`65f36b7`, ADR D49):** manifest counts
  `non_position` under its own key (`other` now reads 4, not 24); `corrections.parse_log`
  keeps only `correction:`-SUBJECT commits; `bills.run` prints the fetch-failure list once;
  deleted unused `clerk_house.roll_xml`. Manifest + data-contract updated.
- **R-5 (M-7) — nightly efficiency — DONE (ADR D50):** `nightly.yml` persists `data/raw/`
  with `actions/cache` (unique-key save + `restore-keys` prefix restore; the 20h cache TTL
  handles staleness). **OPEN — runtime verification:** the first run only SAVES; the
  cache-hit skip count shows on the SECOND scheduled run.

**Round-1 remediations (prior session):** grading reframe (D19/D20), **R-3** retention
scaffolding (`fd9a108`, D45), **R-2** membership-churn resilience (`f0c0f70`, D46).

**Owner escalations parked (do NOT build without explicit reprioritization):** the
**grading engine itself** (§7 — the reader-weight UI that computes a grade over the D19
line) and **PAC funding metrics** (INC-10b, needs H7). R-3/R-2 built the *scaffolding*
for the former; the engine is a separate owner decision.

---

## Increment history (INC-5..INC-11 detail — INC-12 + v2 status is in "Spec v2
adopted" and "Post-review hardening" above)

**(historical — INC-11)**
**INC-11 — Statement ledger + curation tool + pairing — ✅ BUILD COMPLETE;
content = H8 (owner), H6 optional.**
Machinery shipped and proven end-to-end; the published corpus is **empty by design**
(a statement is an owner-selected verbatim quote with a verified archive — principle 5;
the builder never authors one, exactly as INC-6 shipped the absence pipeline with zero
published reasons). **Acceptance is split:** the BUILD acceptance (below) is met by the
builder; the CONTENT acceptance (Phase-3: 20+ statements, ≥5 pairs rendering,
per-member/party symmetry green, every archive link live, banned-words green on curated
text) is owner-gated on **H8** and is a recurring content task, not a build gap.

What shipped:
- **`Statement` model** gains owner-assigned `stated_position` (support/oppose, D42) +
  published `paired_bill_ids` (D41); `data/statements/{id}.json` + `statement.schema.json`
  + `export_statement`; manifest `counts.statements`.
- **`ingest/pairing.py`** — the SINGLE D9 resolver (bill-id form / exact
  `_title_allowlist.yaml` title / else unpaired). Curation resolves once and stores it;
  the metric layer and site READ `paired_bill_ids` and never re-resolve (D41).
- **`named_measure_mismatch` un-fails-closed** (D42): stance vs the member's own
  **passage** vote on a resolved measure; no-stance / unresolved / non-passage excluded,
  never guessed. Docstring (= methodology) rewritten → `data/metrics.json` regenerated;
  recompute-and-match still green.
- **SPN2 capture** (`ingest/sources/archive_org.py`): POST /save → poll → **HEAD-verify**
  the archive_url before it counts (value #1); mutating POST so it bypasses `cache.py`;
  IA S3 keys (H6) with unauth ≤ 1/15 s fallback. **`curation/statements.py`** save path:
  "no verified capture, no save" enforced server-side (requires a real `Capture`); pairing
  resolved at save; `git add` staging; `curate statements repair` re-resolves after an
  allowlist edit (D43).
- **`curation/app.py`** — loopback-only Flask app (`assert_loopback` refuses non-loopback;
  the Save control appears only after a verified capture) with a Statements tab and an
  Absence-approval tab that supersedes the INC-6 CLI. `curate app` / `curate statements`.
- **Site:** `getMemberTimeline` interleaves statements + votes newest-first (zero
  statements ⇒ the vote page unchanged); `StatementCard` renders a paired vote adjacent
  with ZERO relational language; new **`/pairing`** page (bright line + draws-no-conclusion)
  linked from every timeline. Dead-archive statements excluded at build via the committed
  report (D44).
- **`checks/archive_links.py`** + **`archive-links.yml`** (weekly): HEAD every archive_url;
  4xx → committed `data/quality/archive-status.json` + nonzero exit (unpublishable); 5xx /
  network → warn only. Kept OUT of the offline `uv run checks` suite.
- Design in **D41–D44**; data-contract + HUMAN-TASKS (H6 optional, H8 tool-shipped)
  updated. **187 py tests** green; ruff clean; full checks + cross-check 10/10;
  verify-recompute green; 4,540 pages build; a fixture pair renders end-to-end (statement
  + paired roll + `/pairing` link) then removed. See "INC-11 output".

**BUILD acceptance met:** curation captures→verifies→saves with no-capture-no-save enforced
server-side; loopback-only bind; pairing resolves once (D9) and both metric + site consume
it; mismatch computes stance vs passage vote; archive-links sweep flags dead links → build
excludes; symmetry statement rules live (inactive at 0); banned-words scans curated text.

**(historical — INC-10)**
**INC-10 — Metrics layer + methodology page — ✅ COMPLETE.**
Eight Tier-2 metrics (`ingest/metrics.py`, pure/offline) → **`data/metrics.json`**:
attendance, party_unity (substantive classes; majority from new aggregate
`RollCall.party_totals`; ties/procedural/absent excluded), sponsored/cosponsored,
enacted_rate (own-number "Became Public Law"), cosponsor_vote_gap (factual list, never
a score), named_measure_mismatch (fail-closed until INC-11), absence_context (same-day
participation, vote-record-only). Each metric **docstring IS the methodology** —
extracted to `metrics.json` and rendered as one section per metric on `/methods`
(`check-metrics-sections.mjs` asserts section-set == metric-key set). Backfilled bill
`subjects`/`cosponsor_ids` for all 1,011 bills; new **`data/legislation/{member}.json`**
(sponsored/cosponsored, quiet-night-safe shape); new aggregate **`party_totals`** on all
3,467 rolls (re-parsed from cache, offline). **Tier-3 AST guard** active (no metric
consumes another); **symmetry statement-balance rules activated** (vacuously green at
zero statements). verify-recompute gains a 4th invariant (party splits sum to totals) +
a full metrics recompute-and-match test. Design in **D36–D40**. **149 py tests** green;
full checks + cross-check 10/10; 4,539 pages build; metrics-sections + source-links green.
See "INC-10 output". **Acceptance met** (recompute covers every metric + matches; methods
section-set == metric-key-set; Tier-3 guard active).

**(historical — INC-9)**
**INC-9 — Automation + deploy — ✅ COMPLETE (site live; one nightly-observation box open).**
The unattended pipeline is built and CI-green. **`nightly.yml`** (cron `15 09 * * *`
UTC + `workflow_dispatch`): incremental ingest → conditional classify → corrections →
**diff-gate** → (on real change) export → site build → checks → verify-recompute →
commit `data: nightly {date}` → push. A push triggers **Cloudflare Workers Builds**
(D32, the deploy); the workflow holds no Cloudflare secret and never commits on a
failed check (last good deploy stays live). **Incremental ingest** (`incremental.py`,
D31): finalized rolls (>7d, already exported) are skipped — measured 3,454 skip / 13
refetch today — so nightly is API-polite (§0.7); recent + new rolls refresh, and a
re-fetched recent roll is restored to byte-identical by classify so it triggers no
commit (D33). **Corrections** are data (`data/corrections.json` from `git log --grep
correction:`, rendered by `/corrections`; D34) + `docs/correction-process.md`.
`/privacy` + `404.astro` stubs added; footer already carries data-last-updated. **New
gate: Lighthouse mobile perf + a11y ≥ 90** (`lighthouserc.cjs`, CI). Deploy target
moved to **Workers** (`site/wrangler.jsonc`, `assets.directory: ./dist`). Design in
**D31–D34**. See "INC-9 output".

**Owner (INC-9) — DONE:** H4 (Cloudflare **Workers** project, connected via **Workers
Builds**: root `site/`, build `npm run build`, deploy `npx wrangler deploy` default) and
H5 (domain `civicledger.net`, custom domain on the Worker) are complete — the site is
live and auto-deploys on push, no `CLOUDFLARE_*` secret in GitHub CI. Only remaining
acceptance is to **observe one untouched nightly run commit + live deploy** on the next
real data-change night. If branch protection is enabled on `master`, the
`github-actions[bot]` push needs a ruleset bypass (H4 note). Lighthouse ≥ 90 passes CI.

**(historical — INC-8)**
**INC-8 — Site MVP — ✅ COMPLETE.**
The static site renders the record: **member index** (`/`), **member detail** with a
paginated vote list (`/m/[member]/[page]`, 200 rows/page), **single-vote page**
(`/v/[roll]`), **single-bill page** (`/b/[bill]`), plus `/methods` + `/corrections`
stubs. **4,537 pages build from committed `data/**` with no network.** §6.7 copy rules
are enforced via shared components (`VoteRow`, `Badge`, `Layout`): every vote row shows
position, date, roll #, always-visible vote_class badge (neutral tooltip), verbatim
question, bill link, official-record link; absences render the verbatim reason + CREC
link or the EXACT "No explanation on record."; bill titles carry the ⓘ drafter-title
affordance; the footer carries data-last-updated (manifest) + methodology/corrections
links + build commit (`PUBLIC_BUILD_COMMIT`=CI sha). Data layer = `site/src/lib/data.ts`
(`node:fs` over `data/**`, memoized). **Bill ingest** (`ingest bills`, D27) landed first
as its own concern: 1,011 vote-referenced bills, detail-only, `subjects`/`cosponsor_ids`
deferred to INC-10 as `None` (schema widened to `list[str] | None`); 0 quarantined.
Acceptance enforced by 3 CI gates (D30): `astro build` offline; `check-source-links.mjs`
(4,478 vote/bill pages each cite their `source_url`); Playwright `@axe-core` WCAG2 A/AA +
380px no-overflow on 6 representative pages. Design in **D27–D30**. See "INC-8 output".

**(historical — INC-7)**
**INC-7 — JSON export contracts — ✅ COMPLETE.**
The published dataset is now a stable, documented, deterministic contract.
`ingest/export.py` gains `export_bill()`, JSON-Schema generation from the pydantic
models (`data/schema/{member,vote,bill,absence}.schema.json` — the vote file maps
to a composite `VoteFile` wrapper, not a bare `RollCall`), and a manifest builder.
`uv run export` is **offline** and regenerates only the DERIVED artifacts (schemas +
`data/manifest.json`) from the committed dataset — it never re-ingests (that would
reset `vote_class`, D24). The manifest is the single wall-clock/commit carrier (§6.3);
both are injected (`build_manifest(generated_at, commit)`), `main()` resolves real
UTC + `git rev-parse --short HEAD` (env overrides `CIVIC_GENERATED_AT`/`CIVIC_COMMIT`).
New `uv run verify-recompute` (`ingest/verify_recompute.py`, also a pytest test)
checks **coverage + subset + absence-reciprocity** over 100% of 3,467 rolls — the
honest recompute-and-match given MS-only `member_votes` vs chamber-wide `totals`
(**D26** resolves the D22 tension; full rationale in `docs/data-contract.md`).
`docs/data-contract.md` documents every file + field, the `non_position` special
case, the absence filename convention, and what is/isn't recomputable. Design in
**D26**. See "INC-7 output" below.

**(historical — INC-6)**
**INC-6 — Absences & personal explanations — ✅ COMPLETE (build); content = H9.**
Queue → approve → publish pipeline for stated absence reasons. `uv run curate
absences search` searches CREC (govinfo) for the covered delegation's "Personal
Explanation" insertions, **hard-verifies each byline** (`HON. {NAME}` + `of {state}`
— rejects wrong-state surname collisions like Glenn Thompson of PA), extracts the
VERBATIM statement, auto-matches the roll by **absence-stub existence** (not date
arithmetic), and parks candidates in `data/quality/absence-queue/`. `uv run curate
absences approve [--granule <id>]` (interactive y/n/edit or owner-scriptable) writes
the verbatim `stated_reason` + CREC `stated_reason_source` + `declared_position`
onto the matching Absence. **Real MS candidate set = exactly 1** (Guest, `h-118-1-0031`,
YEA), queued and committed **pending owner approval (H9)** — per principle 5 the
builder ships the tool, the owner supplies content (D25); the machinery is proven
end-to-end by a test approving the real Guest granule onto a tmp stub. `data/absences/`
stays `stated_reason: null` until the owner acts. Banned-words excludes the queue
(D25). Design in **D25**. See "INC-6 output" below.

**(historical — INC-5)**
**INC-5 — vote_class classifier (§A1) — ✅ COMPLETE.**
Total classification of all **3,447** non-`non_position` rolls (both chambers) via
an ordered pure rules table (`ingest/classify.py`): procedural 1285, passage 886,
amendment 811, nomination 447, veto_override 14, **other 4 (0.12%)**. Ships the §A1
table + sanctioned extensions from the unmapped-questions loop over real 118–119
strings; the 4 `other` are honest one-offs (treaty ratification, a conference-insist
motion, 2 division-retention votes). R-RULE splits House "On Agreeing to the
Resolution" into `procedural` (Rules-Committee-`hsru00`-reported special rules, via
a committees fetch) vs `passage` (substantive) — the split INC-10 party-unity
depends on. `classify()` is pure/offline; golden test `tests/fixtures/questions.yaml`
(52 real strings) 100% pass. New CI gate `checks/classification.py` fails on any
`unclassified` roll or other-rate > 5%. Design in **D24**. See "INC-5 output" below.

> **RESOLVED (2026-08-11): MS state verdict flipped DEFER → GO.** Owner chose
> option A — ran the 5-bill Journal cross-check now. **5/5 votes matched** (470
> per-person positions, zero mismatches; both chambers, contested votes). Evidence:
> `data/quality/ms-state-verdict.md` + `data/quality/samples/ms_vote_xcheck/`;
> rationale D21 in `decisions.md`. **INC-12 branch A is unlocked but the build
> order does NOT change — the next increment is still INC-3.** INC-12 activates
> when reached, carrying two notes: bundle the billstatus intermediate CA (CI/Linux
> has no AIA chasing), and route LegiScan through a TTL'd cache path.

---

## How to resume (read this first in a new session)

1. **`uv` is not on PATH by default in a fresh shell.** It is installed at
   `C:\Users\SB\AppData\Roaming\Python\Python314\Scripts\uv.exe` and was added
   to the **user** PATH (takes effect in new shells). If `uv` is not found:
   - PowerShell: it should be on PATH now; if not, prepend that Scripts dir.
   - Bash tool: `export PATH="$PATH:/c/Users/SB/AppData/Roaming/Python/Python314/Scripts"`.
2. **Re-verify the tree is still green before starting new work:**
   `uv run checks && uv run pytest && (cd site && npm run build)` (Bash tool —
   PowerShell 5.1 rejects `&&`). Expect (as of `f0c0f70`): **5 checks** pass
   (banned_words, no_llm, symmetry, classification, integrity), **200 tests** pass,
   ~4,540 pages built, `verify-recompute` green. Also run `uv run ruff check ingest tests`
   (CI runs ruff separately from `checks`; keep lines ≤ 100 — an `E501` reddened CI once).
   (`uv run ingest house-votes` re-syncs `data/votes/` + `data/absences/` — cached,
   re-runnable, resumes on interruption; `ingest members` / `spike` likewise cached.)
   Note: the `integrity` check makes ~10 live clerk.house.gov fetches; a clerk
   outage warns (not a failure).
   **§8 coverage gate (V2-2/V2-4/V2-5) — CI runs this; plain `uv run pytest` does NOT
   measure coverage (kept fast/subset-usable), so run the gate explicitly before a
   change to any of the five gated modules:**
   `uv run pytest --cov=ingest.metrics --cov=ingest.rankings --cov=ingest.scoring --cov=ingest.classify --cov=ingest.legislation_stats --cov-branch --cov-fail-under=100 --cov-report=term-missing`
   (must stay 100% branch on all five — legislation_stats.py, the dashboard-headline
   source, joined at V2-5). `ingest rankings` → `data/rankings/*.json` and
   `ingest grades` → `data/grades/*.json` are both pure/offline, derived from
   `data/metrics.json` (grades also read `data/config/thresholds.yaml`), run after
   `ingest metrics`.
3. Python is uv-managed **3.12.13** (system Python is 3.14; project pins 3.12 via
   `.python-version`). `uv sync --frozen` is what CI runs; lockfile is consistent.
4. **Secrets:** `.env` holds `CONGRESS_API_KEY` (H1 done) and empty
   `LEGISCAN_API_KEY` (H2 pending). `.env` is gitignored — never commit it.
   Read keys from `.env`; do not hardcode.

---

## INC-1 output (done — read `SHAPES.md` before writing any parser)

`data/quality/samples/SHAPES.md` is the **authoritative field-shape contract**
for INC-2/3/4/5/6. Key discovered deviations from IMPLEMENTATION.md's assumptions
(all in SHAPES.md + `decisions.md`):
- **Members by state = PATH `/member/{stateCode}`, NOT `?stateCode=` (503).** (D19)
- **`bioguideId` (member list) vs `bioguideID` (house-vote positions)** — case differs.
- **Senate menu & detail are in different dirs**; the spec's `vote_menu` path
  301-redirects. Menu `roll_call_lists/`, detail `roll_call_votes/vote{c}{s}/`.
- **CREC full-text search RESOLVED** — Congress.gov `/congressional-record` is a
  date index only, but **govinfo `POST /search` does full-text with the SAME
  api.data.gov key** (15,998 "personal explanation" CREC hits). INC-6 has a real
  source; no risk carried forward.
- **Crosswalk joins:** house `bioguideID`→`id.bioguide`; senate `lis_member_id`→
  `id.lis` (both in `legislators_current_ms.yaml`).

Modules created: `ingest/env.py` (`.env` reader), `ingest/cache.py` (header-auth
disk cache; **credential never in URL/key/meta**), `ingest/spike.py` (`ingest
spike`, with secret-guard), sources `congress_gov.py` / `senate_xml.py` /
`legislators.py` / `clerk_house.py` (stub) / `legiscan.py` (state, DEFER path) /
`govinfo.py` (CREC search, INC-6). Tests: `tests/test_cache.py` (6) +
`tests/test_banned_words_scope.py` (2), all offline. MS verdict: initially DEFER
at INC-1; **flipped to GO on 2026-08-11** (5/5 Journal cross-check — see the
RESOLVED callout above). 11 samples committed.

## INC-2 output (done — the schema layer INC-3+ import from)

`ingest/models.py` = the complete §5 layer. Reuse these; do not redefine records.
- **`Member`** exported to `data/members/{bioguide}.json` (6 files, committed).
  `id`=bioguide; `ids`=curated string crosswalk (D20 — `fec` comma-joined,
  `lis`/`fec` are the join keys INC-4/INC-10b need); `terms` = full history,
  start-sorted, party switches preserved; `serving` = latest term overlaps
  congress 119 (deterministic, no wall-clock).
- `legislators.party_code(word)` — shared "Democrat"/"Democratic"→"D" mapper;
  **INC-3 reuses it for `voteParty`.** Raises on unmapped (→ quarantine, §6.1).
- `legislators.congress_window(N)` / `_term_overlaps` — congress↔date helpers;
  **INC-3 uses these to bucket roll calls into 118 vs 119.**
- `export._dumps(obj)` — the canonical serializer (sorted keys, 2-space, LF,
  trailing newline). Every INC-7 export contract should route through it.
- Tier-1 records (`Member`, `Bill`, `RollCall`, `MemberVote`, `Absence`, …) set
  `extra="forbid"` — an unexpected upstream field raises `ValidationError`
  (→ quarantine), it never silently rides into the published dataset.

## INC-3 output (done — the vote layer INC-4/5/6 build on)

- **`ingest/house_votes.py`** — `parse_rollcall(members_json, congress, session)`
  (pure) → `(RollCall, list[MemberVote], list[Absence])`, and `run()` (the
  `ingest house-votes` pipeline: enumerate → fetch `/members` per roll → quarantine
  → gaps → export). **Re-runnable/resumable** (cache); fault-tolerant per roll.
  - `VOTE_MAP` maps **both** Yea/Nay **and** Aye/No → yea/nay. **INC-4 senate
    parsing should reuse this insight** (LIS XML `vote_cast` is Yea/Nay; SHAPES §6).
  - Speaker elections = **`non_position`** rolls: a `RollCall` (counts) with a raw
    candidate tally in `totals`, **no** `member_votes`, excluded from symmetry +
    integrity. Detected by majority-unmappable `voteCast`.
  - `vote_class` provisional `other`/`unclassified` (INC-5 §A1 rewrites; leaves
    `non_position` alone).
- **`data/votes/{h-c-s-NNNN}.json`** = `{"rollcall": {...}, "member_votes": [...]}`
  (MS only, sorted). **`data/absences/{member}--{rollcall}.json`** = one stub per
  not_voting. `source_url` = clerk `sourceDataURL`.
- **`ingest/sources/clerk_house.py::parse_positions(xml, state)`** — bioguide→
  position from clerk XML (maps Aye/No too); the D6 independent cross-check source.
- **`checks/symmetry.py`** (vote coverage, §6.5) + **`checks/integrity.py`**
  (seeded 10-sample clerk cross-check; mismatch fails, unreachable warns) — both
  registered in `run.py`, both no-op on empty data.
- **`cache.py`** now retries timeouts/network errors (§6.1 bug fix) — reuse holds
  for every future source.

## INC-4 output (done — the Senate vote layer, mirrors INC-3)

- **`ingest/senate_votes.py`** — `parse_rollcall(detail_xml, congress, session,
  lis_to_bioguide, menu_tally)` (pure) → `(RollCall, list[MemberVote],
  list[Absence])`, and `run()` (the `ingest senate-votes` pipeline: parse menu →
  fetch each detail → cross-check tally → quarantine → gaps → export).
  Re-runnable/resumable (cache); idempotency re-verified (re-run byte-identical).
  - **Cross-SOURCE tally check** replaces INC-3's clerk: member-computed yea/nay
    must equal the menu's `vote_tally` (a different file) → else `TallyMismatch`.
  - **`_bill_id` handles 3 measure shapes** — `<document>` bill (`hr1-119`),
    amendment fallback to `<amendment><amendment_to_document_number>`, and
    nomination/treaty/quorum → `None`. Whitelist of real bill types.
  - **`_parse_date`** hand-rolls month parsing (locale-proof) → naive ISO ET.
  - **No `non_position` branch** (Senate has no candidate-surname rolls); VP
    tie-breaks handled by arithmetic that already agrees (D23).
- **`ingest/sources/senate_xml.py`** — added `parse_menu` (→ `{roll: (yeas,nays)}`,
  the enumeration + tally source), `detail_url`, and `parse_positions(detail_xml,
  lis_to_bioguide, state)` (the D6-style independent re-parse for integrity).
- **`data/votes/s-{c}-{s}-NNNN.json`** (1,581 files) + **`data/absences/`** (87
  Senate stubs; 243 total with House). Same export contract as INC-3.
- **`checks/symmetry.py`** generalized: `coverage_gaps(chamber, prefix)` runs House
  + Senate; report gains a `"senate"` key. **`checks/integrity.py`** runs a House
  clerk pass + a Senate detail-reparse pass (each no-op until its data exists).
- **`cli.py`** `senate-votes` subcommand.
- Tests: **`tests/test_senate_votes.py` (18)** — menu contiguity, all 4 real shape
  variants, tally-mismatch, crosswalk join, bill-id normalization, determinism.
  Committed 3 new detail samples (371/372/659). Test count 47 → 65.

## INC-5 output (done — the classified vote layer INC-8/10 render + score on)

- **`ingest/classify.py`** — `classify(question, *, is_rules_resolution=False) ->
  (VoteClass, rule_id)` is a PURE, offline, ordered rules table (`RULES` =
  module-level tuples, renderable on the INC-10 methodology page). FIRST match wins;
  order encodes precedence. `run()` = the `ingest classify` pipeline: rewrites
  `vote_class`/`vote_class_rule` in place on every non-`non_position`
  `data/votes/*.json`, regenerates `data/quality/unmapped_questions.json`
  (deterministic sorted regen, D24), fails if other-rate > `MAX_OTHER_RATE`.
  Idempotent (re-run byte-identical).
- **R-RULE** kept pure via the `is_rules_resolution` arg; `run()` computes it by
  fetching `bill/{c}/hres/{n}/committees` (`congress_gov.bill_committees`, new) and
  checking for House Rules `hsru00` + a "Reported" activity.
- **`checks/classification.py`** (new, registered in `run.py`) — CI gate: fails on
  any `unclassified` roll or other-rate > ceiling. **`cli.py`** `classify` subcommand.
- Tests: **`tests/test_classify.py` (9)** + golden **`tests/fixtures/questions.yaml`**
  (52 verbatim real strings, every rule id, both R-RULE branches, treaty). 65 → 74.
- **⚠ ORDER: ingest → classify → checks** (D24). Re-running an ingest resets rolls to
  `unclassified`; the classification gate then fails until `classify` re-runs.

## INC-6 output (done — the absence-explanation curation pipeline)

- **`curation/absences.py`** — pure `parse_granule` (byline, verbatim statement,
  roll refs, declared position), `verify_member` (the wrong-state gate), stub-
  existence `match_rollcall`, `search()` (CREC → verified queue) and `approve()` /
  `approve_one()` (owner approval → verbatim Absence). `_publish` refuses an
  unmatched roll (an Absence is keyed member+roll).
- **`ingest/sources/govinfo.py`** — `crec_personal_explanations(state, start, end)`
  (title+byline-scoped search), `granule_text(pkg, gid)` (header-auth), `granule_url`
  (the public `govinfo.gov/app/details/...` citation, verified 200).
- **`curation/cli.py`** — `curate absences {search|approve}` (`approve --granule <id>`
  is the owner's non-interactive path). **`banned_words.py`** excludes
  `data/quality/absence-queue/` (D25).
- Tests: **`tests/test_absences.py` (12)** + the queue-exclusion case in
  `test_banned_words_scope.py`; committed real fixture
  `data/quality/samples/crec_personal_explanation_guest.htm`. 74 → 86.
- **Queued, pending H9:** `data/quality/absence-queue/CREC-2023-01-13-pt1-PgE29-4.json`
  (Guest). Owner approval is H9; `data/absences/` reasons stay null until then.

## INC-7 output (done — the public export contract)

- **`ingest/export.py`** — `export_bill()` (+ the `Bill` schema; no bill data yet,
  ships so the contract is complete for every Tier-1 type — bill ingest = INC-8);
  `export_schemas()` writes `data/schema/{member,vote,bill,absence}.schema.json` from
  the pydantic models (the vote file maps to a composite **`VoteFile`** wrapper, not a
  bare `RollCall`); `build_manifest(generated_at, commit)` / `export_manifest()` with
  both wall-clock values **injected**; offline `main()` regenerates schemas + manifest
  from committed data (resolves real UTC + `git rev-parse --short HEAD`; env overrides
  `CIVIC_GENERATED_AT` / `CIVIC_COMMIT`). `main()` never re-ingests (D24 reset trap).
- **`ingest/verify_recompute.py`** (new `verify-recompute` console entry) —
  `check_dataset()` runs 3 invariants over 100% of rolls: (1) coverage (member_votes
  accounts every covered member per eligible roll), (2) subset (MS position count <=
  chamber `totals[cat]`), (3) absence reciprocity (not_voting vote <-> absence stub,
  both ways). **D26** = the resolution of the D22 recompute tension (chamber totals
  are not re-derivable from MS-only member_votes; the subset check is the honest tie).
  Reuses `checks/symmetry._covered` so covered-set logic never drifts.
- **`data/manifest.json`** — generated_at, commit, congresses, covered_state, and a
  `counts` block (members 6, rollcalls 3,467 [house 1,886 / senate 1,581], member_votes
  10,626, absences 243, bills 0, non_position 20, by-vote-class). The ONE wall-clock file.
- **`data/schema/*.schema.json`** — 4 committed JSON Schemas; a test fails if they
  drift from a fresh `export` (re-run `uv run export` to refresh).
- **`docs/data-contract.md`** — every file + field, the `non_position` sentinel, the
  `{member}--{roll}` absence filename, and the recompute-and-match definition + limit.
- Tests: **`tests/test_export_contracts.py` (9)** — manifest determinism + injected
  fields + committed-manifest-matches-recount, schema determinism + composite vote
  schema + committed-schemas-current, bill export round-trip, verify-recompute green
  on the committed dataset (× entrypoint). 86 → 95. Design in **D26**.

## INC-8 output (done — the public site MVP + bill ingest)

- **`ingest/bills.py`** (new `ingest bills` subcommand) — pure `parse_bill` +
  `parse_bill_id` + `run()`. Covered set = `referenced_bill_ids()` (distinct non-null
  `RollCall.bill_id`, 1,011). Detail-only fetch; `subjects`/`cosponsor_ids` = None
  (D27); titles `html.unescape`d; `source_url` = `legislationUrl`. Quarantine + §6.1
  ceiling. **0 quarantined.** `models.Bill.subjects`/`cosponsor_ids` widened to
  `list[str] | None`; `data/bills/*.json` (1,011) committed; manifest bills 0 → 1,011.
- **`site/src/lib/data.ts`** — build-time `node:fs` readers over `data/**` (memoized),
  typed to mirror §5; derived views `getMemberVotes` (newest-first), `getVotesForBill`,
  `paginate`. **`site/src/lib/display.ts`** — vote_class labels + neutral tooltips
  (UI chrome), `formatDate`, `billLabel`, `ordinal`.
- **Components** (`site/src/components/`): `Layout.astro` (shell + §6.7 footer),
  `Badge.astro` (vote_class + tooltip), `VoteRow.astro` (the full §6.7 vote row incl.
  absence rendering). **Pages**: `index.astro` (member index), `m/[member]/[page].astro`
  (paginated, 200/page — ⚠ `getStaticPaths` is scope-isolated, keep locals inside it),
  `v/[roll].astro`, `b/[bill].astro` (ⓘ affordance + CBO link-throughs + rolls-on-bill),
  `methods.astro` + `corrections.astro` stubs. **4,537 pages, built offline in ~25s.**
- **Acceptance harness**: `site/scripts/check-source-links.mjs` (`npm run test:links` —
  4,478 pages cite their source_url), Playwright `site/e2e/` (`@axe-core` WCAG2 A/AA +
  380px overflow, 6 data-derived representative pages; fullPage screenshot is
  best-effort — chromium can't capture a rule-resolution page listing hundreds of votes).
  `playwright.config.ts` webServer = `astro preview`. **12/12 e2e pass.**
- **CI** (`.github/workflows/ci.yml`): python job adds `verify-recompute`; site job adds
  `PUBLIC_BUILD_COMMIT=github.sha` on build, `test:links`, `playwright install chromium`,
  `test:e2e`. **`@types/node` + astro.config tailwind-plugin cast** make `astro check`
  clean (0 errors). Tests: **`tests/test_bills.py` (13)** — id parsing, core-field parse,
  D27 None assertion, entity-decode, missing-field raise. 95 → 108 (python). Design in
  **D27–D30**.

## INC-9 output (done — the unattended pipeline; site LIVE at civicledger.net)

- **`ingest/incremental.py`** (D31) — `final_cutoff(now)`, `is_final(date, cutoff)`,
  `roll_is_final`, `recent_bill_ids`, `bill_is_skippable`. Wired into `house_votes.run`,
  `senate_votes.run` (skip finalized rolls before fetch), `bills.run` (skip exported
  bills except those on recent rolls). All take an injected cutoff → 7 deterministic
  tests (`tests/test_incremental.py`). Ingest prints "N new/refreshed, M skipped".
- **`.github/workflows/nightly.yml`** (D32/D33) — cron + `workflow_dispatch`;
  `permissions: contents: write`; `fetch-depth: 0`; `CONGRESS_API_KEY` from secret.
  Ordering: ingest votes+bills → (if votes moved) classify → corrections → diff-gate on
  `data/` → real change: export → `npm run build` → checks → verify-recompute →
  commit+push; quiet night: build+checks for drift, exit 0 (no commit). Holds NO
  Cloudflare secret — push triggers Workers Builds.
- **`site/wrangler.jsonc`** — assets-only Worker, `assets.directory: ./dist`,
  `not_found_handling: 404-page`; **`site/src/pages/404.astro`**. `wrangler ^4` pinned
  in site devDeps. Layout footer build-commit now reads `WORKERS_CI_COMMIT_SHA`.
- **`ingest/corrections.py`** (`corrections` console entry, D34) — `git log --grep
  '^correction:'` → `data/corrections.json` (committed `[]`); `corrections.astro`
  renders it (`getCorrections` in `data.ts`); **`docs/correction-process.md`** (§A4).
- **`site/src/pages/privacy.astro`** — privacy summary stub (full threat model = INC-16).
- **Lighthouse** (`site/lighthouserc.cjs`, `npm run test:lighthouse`, CI step) — mobile
  perf + a11y ≥ 90, URLs derived from data, median of 3 vs `astro preview`. **Passes**
  (MVP pages carry no client JS). `/privacy` added to the e2e page set (**14/14 e2e**).
- **Docs**: H4/H5 → Workers, marked 🟨; `.env.example` H4 note; PIPELINE ORDER callout
  extended (ingest → bills → classify → export → checks). Tests 108 → **115** (python).

**INC-9 acceptance status:** procedural classification displayed ✅; missed votes show
reason/absence ✅; methodology stub live ✅; mobile Lighthouse ≥ 90 ✅ (local + CI);
six members complete ✅. **Nightly pipeline REHEARSED green** (`gh workflow run
nightly.yml`, run 31606758399, 2026-08-12): house 0 refreshed / 1,886 skipped, senate
11 refreshed / 1,570 skipped, bills 4 fetched / 1,007 skipped — classify restored the 11
re-fetched senate rolls byte-identical, so the diff-gate saw no change → **quiet night,
no commit** (validates D33); checks + verify-recompute green. **H4/H5 now DONE:** site
live at `civicledger.net` via Workers Builds. Only open box: observe a nightly that
actually commits new data + its deploy (next real data-change night). **D33 assumption
resolved by mechanism:** a `GITHUB_TOKEN`/bot push DOES trigger Workers Builds — the
Cloudflare GitHub App listens on the `push` webhook, which (unlike GitHub Actions
workflow triggers) is not suppressed for the default token; confirm empirically when the
first `data: nightly …` build shows author `github-actions[bot]` in Cloudflare Deployments.

**D35 (bugfix this session):** the ingest now re-exports absence stubs with
`overwrite=False`, so a nightly re-fetch of a recent roll never clobbers an owner-
approved `stated_reason` into a false "No explanation on record." (value #1). Landed +
CI-green before the rehearsal.

## INC-10 output (done)

- **`ingest/metrics.py`** — 8 pure/offline Tier-2 metrics (docstring == methodology):
  attendance, party_unity, sponsored, cosponsored, enacted_rate, cosponsor_vote_gap,
  named_measure_mismatch, absence_context → **`data/metrics.json`** (`ingest metrics`).
  `METRICS` registry drives the Tier-3 AST guard.
- **`data/legislation/{member}.json`** (`ingest legislation`) — sponsored/cosponsored
  bills, 118–119; quiet-night-safe (`LegItem` has no live latest-action; only frozen
  `enacted_action`); amendments excluded; covered-window paginator.
- **Bill backfill** — all 1,011 bills now carry `subjects` + `cosponsor_ids`
  (`ingest bills --all`); fetched for every exported bill so a re-export never reverts.
- **`RollCall.party_totals`** — aggregate per-party split on all 3,467 rolls
  (re-parsed from cache, offline, `--all`); `None` on non_position; verify-recompute
  invariant 4. **classify** round-trips it.
- **`/methods`** auto-built: one `data-metric` section per methodology key;
  `check-metrics-sections.mjs` (CI) asserts section-set == metric-key-set.
- **Symmetry** statement-balance rules activated (inactive/green at 0 statements);
  **Tier-3 guard** in `checks/integrity.py`; ci.yml + nightly.yml wired
  (`legislation` after bills, `metrics` after corrections before the diff-gate).
- Design in **D36–D40**; data-contract.md updated. **149 py tests**; full checks +
  cross-check 10/10; 4,539 pages; metrics-sections + source-links green.

**Next — INC-11 (Statement ledger + curation + pairing; content = H8, H6 for SPN).**
Load-bearing carry-overs from INC-10: (1) `named_measure_mismatch` FAILS CLOSED — it
raises the moment a specificity-2/3 statement naming a voted measure is curated, so
INC-11 MUST build the statement-STANCE comparison (a Statement has no stance field
today) before curating qualifying statements (D39). (2) Member-page rendering of the
metrics (esp. `cosponsor_vote_gap`) must follow D38: never a bare count, always against
its denominator, never a headline. (3) Statement symmetry rules are live and will gate
the curated corpus once the median reaches 5 (config.SYMMETRY_MEDIAN_ACTIVATION).

**INC-8 acceptance (met):** `astro build` from data alone ✅; axe-core a11y ✅ (14/14
Playwright); 380px layout + screenshot ✅; every rendered claim traces to a `source_url`
✅ (source-link trace, 4,478 pages).

---

## Increment status

| INC | Title | Status | Acceptance |
|-----|-------|--------|------------|
| INC-0 | Repo bootstrap | ✅ done (CI green) | `uv run checks && uv run pytest && (cd site && npm run build)` — local + CI green 2026-08-11 |
| INC-1 | Source feasibility spike | ✅ done | samples + SHAPES.md committed; all 6 federal sources reached; MS verdict **GO** (cross-check run 2026-08-11) |
| INC-2 | Canonical members & schema | ✅ done | models.py complete + 6 MS members exported + double-export determinism; 35 tests green |
| INC-3 | House vote ingest | ✅ done | 1,886 rolls (counts match, contiguous), 10/10 clerk cross-check, symmetry OK; 47 tests |
| INC-4 | Senate vote ingest ∥ | ✅ done | 1,581 rolls (contiguous 1..N per session, 119/1=659), 10/10 detail cross-check + menu-tally check, symmetry OK both chambers; 65 tests |
| INC-5 | vote_class classifier | ✅ done | 3,447 rolls classified, other 0.12% (≤5%); golden 52-string fixture 100%; R-RULE via Rules-Cmte fetch; classification CI gate; 74 tests |
| INC-6 | Absences & explanations | ✅ done (build); content = H9 | pipeline green (search→verify→queue→approve), byline gate, stub-existence match, queue banned-words-excluded; 1 candidate queued pending owner approval; 86 tests |
| INC-7 | JSON export contracts | ✅ done | double-export byte-identical (manifest + 4 schemas); `verify-recompute` matches 100% of 3,467 rolls (coverage+subset+reciprocity, D26); manifest + data-contract.md committed; 95 tests |
| INC-8 | Site MVP | ✅ done | 4,539 pages build offline; 1,011 bills ingested (0 quarantine); source-link trace 4,478 pages; axe WCAG2 A/AA + 380px 14/14 Playwright; §6.7 via shared components; 117 py tests + e2e |
| INC-9 | Automation + deploy (PUBLIC MVP) | ✅ done — **site LIVE at `civicledger.net`** (Workers Builds) | nightly.yml (incremental skip-if-final, diff-gated commit, Workers Builds deploy); corrections-as-data; Lighthouse mobile ≥ 90 (local+CI); nightly rehearsed green; 117 py tests. H4/H5 done. Open box: observe one real-data nightly commit + deploy |
| INC-10 | Metrics + methodology | ✅ done | 8 Tier-2 metrics → data/metrics.json; methods page auto-built from docstrings (section-set == metric-key-set); bill subjects/cosponsors backfilled; data/legislation/ + aggregate party_totals; Tier-3 AST guard + symmetry statement rules active; verify-recompute 4th invariant + metrics recompute-match; 149 py tests, D36–D40 |
| INC-10b | FEC funding (optional) | not started | blocked by H7 |
| INC-11 | Statement ledger + curation | ✅ build done; content = H8 | curation Flask app (loopback-only, no-capture-no-save server-side) + SPN2 verified capture; Statement stance + D9 single-source pairing (paired_bill_ids); named_measure_mismatch un-failed-closed (stance vs passage vote); member timeline interleave + /pairing page; weekly archive-links sweep (dead → build-excluded); 187 py tests at close (217 after R-1/R-4/R-6 hardening), D41–D44 + D47–D50. Phase-3 content acceptance (20+ statements, ≥5 pairs) is H8 |
| INC-12 | Mississippi state layer | ✅ done (branch A) | LegiScan bulk ingest → data/state/ms/ (174 members, 1,725 rolls, 905 voted bills, 144,007 member votes, 0 quarantined); jurisdiction schema + partitioned storage (D51); MS classifier + TTL cache (D52); checks/ms consistency + 5/5 official-PDF spot-check (D53); /ms site pages, site 4,540→7,919 (D54); hash-gated nightly (D55); /methods#mississippi limitations page (D56). **Member-page Tier-2 stats: federal (D57) + MS (D58 — legislation layer from all 4,006 bills + metrics.json).** 254 py tests; checks + 24/24 e2e + astro-check green |
| — | Member-page stat rendering | ✅ done (D57/D58) | 8 federal + 5 MS Tier-2 metrics rendered as a KPI stat-tile row atop each member page (`MemberStats.astro`, jurisdiction-aware) — each with its denominator, NO composite/score. The review's post-INC-12 item |
| INC-13 | Candidate Tracker | not started | content = H10 |
| INC-14 | Alignment Quiz engine | not started | content = H11 |
| INC-15 | Alignment outputs | not started | — |
| INC-16 | Aggregates Worker + privacy | not started | H4 done (Workers live); canary = H12 |
| INC-17 | Challenge & Calibration | not started | — |
| INC-18 | Longitudinal drift | not started | — |
| INC-19 | Bill diff viewer | not started | — |
| INC-20 | "Nobody Told You" feed + glossary ∥ | not started | — |
| INC-21 | Ballot builder + share cards | not started | — |
| INC-22 | Zero-knowledge sync (post-v1 stub) | deferred | Decision D12 — do not build this pass |

## Blocked human tasks (see docs/HUMAN-TASKS.md for full table)

| H | Blocks | Status |
|---|--------|--------|
| H1 | INC-1 | ✅ done — CONGRESS_API_KEY in .env + GitHub secret |
| H2 | INC-1 state branch | ✅ done — LegiScan key present; **Journal cross-check run 2026-08-11 → verdict GO (5/5)**; INC-12 branch A unlocked |
| H3 | INC-0 push / all CI | ✅ done — repo live, pushed, CI green |
| H4 | INC-9, INC-16 | ✅ done — Cloudflare **Workers** via Workers Builds (root `site/`, build `npm run build`, deploy `npx wrangler deploy`); no `CLOUDFLARE_*` GitHub secret; site live. Enable `github-actions[bot]` push bypass if branch protection is added |
| H5 | INC-9 | ✅ done — **`civicledger.net`** (`.org` was taken) custom domain on the Worker; live |
| H6 | INC-11 auth SPN | ⬜ pending — archive.org S3 keys (falls back to unauth SPN) |
| H7 | INC-10b | ⬜ pending — FEC key (optional increment) |
| H8–H12 | recurring content | ⬜ pending |
| H13 | pre-launch byline | ⬜ pending (non-blocking) |

## What exists in the repo now (INC-0..INC-9 output)

**INC-9 additions:** `ingest/incremental.py` (skip-if-final) wired into house/senate/
bills run(); `ingest/corrections.py` (+ `corrections` console entry) → `data/corrections.json`;
`.github/workflows/nightly.yml`; `site/wrangler.jsonc` + `site/src/pages/404.astro` +
`privacy.astro`; corrections rewired to data (`getCorrections` in `data.ts`,
`corrections.astro`); `site/lighthouserc.cjs` + `test:lighthouse` script + CI step;
`wrangler` devDep; `docs/correction-process.md`; H4/H5→Workers in HUMAN-TASKS + `.env.example`;
Layout `WORKERS_CI_COMMIT_SHA`; `tests/test_incremental.py` (7). D31–D34 in `decisions.md`.
Test count 108 → 117 (python) + 14 Playwright e2e.

**INC-8 additions:** `ingest/bills.py` (+ `bills` subcommand); `Bill.subjects`/
`cosponsor_ids` widened to `list[str] | None` in `models.py`; `data/bills/*.json`
(1,011); the full Astro site — `site/src/lib/{data,display}.ts`,
`site/src/components/{Layout,Badge,VoteRow}.astro`, pages `index`/`m/[member]/[page]`/
`v/[roll]`/`b/[bill]`/`methods`/`corrections`; `site/scripts/check-source-links.mjs`;
`site/e2e/{fixtures,a11y,mobile}` + `playwright.config.ts`; `@types/node` +
`@playwright/test` + `@axe-core/playwright` devDeps; the astro.config tailwind cast;
CI additions (verify-recompute, source-link, playwright, `PUBLIC_BUILD_COMMIT`);
`tests/test_bills.py` (13). D27–D30 in `decisions.md`. Test count 95 → 108 (python)
+ 12 Playwright e2e.

**INC-7 additions:** `ingest/verify_recompute.py` (the `verify-recompute` console
entry + `check_dataset`), the `VoteFile` wrapper + `export_bill`/`export_schemas`/
`build_manifest`/`export_manifest`/offline `main()` in `ingest/export.py`, the
`verify-recompute` script in `pyproject.toml`, `docs/data-contract.md`,
`tests/test_export_contracts.py` (9), and the committed derived artifacts
`data/manifest.json` + `data/schema/{member,vote,bill,absence}.schema.json`. D26 in
`decisions.md`. Test count 86 → 95.

**INC-6 additions:** `curation/absences.py` (search→verify→queue→approve pipeline),
`crec_personal_explanations`/`granule_text`/`granule_url` in `ingest/sources/govinfo.py`,
the `absences` subcommands in `curation/cli.py`, the `absence-queue/` exclusion in
`ingest/checks/banned_words.py`, `tests/test_absences.py` (12) + a queue-exclusion
test, the committed `data/quality/samples/crec_personal_explanation_guest.htm` fixture,
and one pending queue file `data/quality/absence-queue/*.json`. Also swept printed
U+2192 arrows → ASCII (Windows cp1252 crash). D25 in `decisions.md`. Test count 74 → 86.

**INC-5 additions:** `ingest/classify.py` (pure §A1 rules table + `classify`
pipeline, `classify` subcommand), `congress_gov.bill_committees`,
`ingest/checks/classification.py` (registered in `run.py`), `tests/test_classify.py`
(9) + `tests/fixtures/questions.yaml` (52 real strings), the `classify` wiring in
`cli.py`, `data/quality/unmapped_questions.json`, and the in-place re-classification
of all **3,447** `data/votes/*.json` (vote_class/vote_class_rule rewritten). D24 in
`decisions.md`. Test count 65 → 74.

**INC-4 additions:** `ingest/senate_votes.py` (parser + `run()` pipeline,
`senate-votes` subcommand), `parse_menu`/`detail_url`/`parse_positions`/`VOTE_MAP`
in `ingest/sources/senate_xml.py`, both-chamber generalization of
`checks/symmetry.py`, the Senate re-parse pass in `checks/integrity.py`, the
`senate-votes` wiring in `cli.py`, `tests/test_senate_votes.py` (18) + 3 committed
detail samples (371/372/659), and the committed dataset: **1,581 `data/votes/s-*.json`
+ 87 Senate `data/absences/*.json`** + the updated `data/quality/symmetry-report.json`.
D23 in `decisions.md`. Test count 47 → 65.

**INC-3 additions:** `ingest/house_votes.py` (parser + `run()` pipeline,
`house-votes` subcommand), `parse_positions` in `ingest/sources/clerk_house.py`,
`house_vote_roll_numbers` enumeration in `congress_gov.py`, `export_rollcall`/
`export_absence` in `export.py`, `checks/symmetry.py` + `checks/integrity.py`
(registered in `run.py`), the `cache.py` timeout-retry fix,
`tests/test_house_votes.py` (10) + a cache retry test, and the committed dataset:
**1,886 `data/votes/*.json` + 156 `data/absences/*.json`** +
`data/quality/symmetry-report.json`. D22 in `decisions.md`. Test count 36 → 47.

**INC-2 additions:** `ingest/models.py` (full §5 schema layer), the raw→`Member`
parser in `ingest/sources/legislators.py` (`party_code`, `congress_window`,
`is_covered`, `covered_members`), the deterministic serializer + `export_members`
in `ingest/export.py`, the `members` subcommand in `cli.py`, `tests/test_models.py`
(11 offline tests), and 6 committed `data/members/*.json`. D20 in `decisions.md`.
Test count 23 → 35.

**INC-1 additions:** `ingest/env.py`, `ingest/cache.py`, `ingest/spike.py`,
`ingest/sources/{congress_gov,senate_xml,legislators,clerk_house,legiscan}.py`,
`tests/test_cache.py` (6) + `tests/test_banned_words_scope.py` (2) offline tests,
`ingest/sources/govinfo.py`, and the committed `data/quality/samples/`
(11 samples + `SHAPES.md`) + `data/quality/ms-state-verdict.md`.
`banned_words.py` now excludes `data/quality/samples/` (ADR). `ingest spike`
subcommand wired in `cli.py`. Test count 15 → 23.

## Prior state (INC-0 output)

- **Python (uv):** `pyproject.toml` (console scripts `ingest`/`export`/`curate`/
  `checks`; hatchling ships two packages `ingest` + `curation`), `uv.lock`,
  `.python-version`=3.12.
- `ingest/config.py` — `K_ANON=50`, `CONGRESSES=[118,119]`, `COVERED_STATE="MS"`,
  symmetry + quarantine + max-other-rate thresholds.
- `ingest/checks/` — `banned_words.py` (§6.4), `no_llm.py` (§6.6, self-match
  defended two ways + tested), `run.py` (the `checks` entrypoint).
- Stub entrypoints: `ingest/cli.py`, `ingest/export.py`, `curation/cli.py`
  (all print a status + exit 0; real logic lands in later increments).
- `tests/test_bootstrap.py` — 15 tests (entrypoints importable, K_ANON, congress
  coverage, banned-words detect/clean, no_llm self-non-match + detection).
- **Site (Node/npm):** `site/` Astro 5 static scaffold, Tailwind v4 via
  `@tailwindcss/vite`, Preact islands, placeholder `index.astro`,
  `site/package-lock.json`. `dist/` is gitignored (CI builds it).
- **CI:** `.github/workflows/ci.yml` — Node 22, `astral-sh/setup-uv`, `uv sync
  --frozen`, **build-before-checks** so §6.4 scans real `site/dist/**`.
- **Docs:** `docs/HUMAN-TASKS.md`, `docs/decisions.md` (version pins + builder
  ADRs), `CONTRIBUTING.md` (no-LLM policy), `.env.example`, this file.
- **Repo hygiene:** `.gitattributes` forces LF everywhere (protects §6.3
  export determinism); `.gitignore` covers `.env`, `data/raw/`, `build.db`,
  caches, `node_modules/`, `dist/`.

## Notes / open items / ADR pointers

- **Post-review ADRs:** grading reframe = **D19/D20** (IMPLEMENTATION.md §2); R-3 = **D45**,
  R-2 = **D46**, R-1 = **D47**, R-4 = **D48**, R-6 = **D49**, R-5 = **D50** (all
  `docs/decisions.md`). **The whole review backlog R-1..R-6 is now CLOSED** (source: local
  `TECHNICAL_REVIEW.md`). H8 statement curation is unblocked (R-1 landed).
- **INC-12 (MS state layer) ADRs: D51–D56** (`docs/decisions.md`); full plan in
  `docs/inc-12-plan.md`; contract in `docs/data-contract.md` (state section). **INC-12 is
  DONE** (all 6 phases). **Member-page stats: D57 (federal) + D58 (Mississippi) — DONE:**
  both jurisdictions render the Tier-2 stat tiles on member pages (attendance, party unity,
  sponsored/authored, cosponsored/co-authored, enacted/became-law), each with its
  denominator, NO composite score (Tier-3 rule holds). **Next actionable = the
  reader-adjustable scorecard** (the overall-grade experience, client-side weights per D19 —
  the remaining big item the owner flagged) OR **INC-13** (Candidate Tracker, content = H10)
  — owner's pick. Open runtime-verification boxes (not blockers): R-5 cache-hit on the 2nd
  nightly; INC-9 first-real-data nightly commit + deploy; the first MS nightly hash-gate no-op.
- **Deferred (later increments):** backfill prior MS sessions; the flat-file→SQLite
  build-accelerator decision (review §6 — revisit before a 2nd state; MS kept flat-file,
  ~7,900 pages, still fine).
- Version pins recorded in `docs/decisions.md` (Python + Node) at INC-0.
- Dev environment: Windows 11 + PowerShell. `uv` at
  `%APPDATA%\Python\Python314\Scripts` on user PATH. Local Python 3.14 → project
  pins 3.12 (uv-managed). Local Node 24 → CI pins Node 22 LTS (logged in decisions.md).
- **Non-blocking CI warning:** logs show "Node.js 20 is deprecated" for
  `actions/checkout@v4` / `setup-node@v4` / `setup-uv@v5`. This is GitHub
  *runner-infra* deprecation of the actions' own Node runtime, **not** our Node
  22 pin. Does not fail CI; resolves when those actions ship Node-24 releases.
  No action needed; revisit only if it ever turns into a hard failure.
- **CLAUDE.md note (historical):** through the v1 build, there was no `CLAUDE.md`
  file — its content lived in the bare `.claude` file (never auto-loaded by
  Claude Code), pointing at `IMPLEMENTATION.md`. Fixed at v2 adoption: `.claude`
  → `CLAUDE.md` (git mv), rewritten to point at `IMPLEMENTATIONv2.md`.
- **Watch in INC-1:** (a) the `/house-vote` beta endpoint may 404 → clerk XML
  fallback + log deviation; (b) Senate vote filename must be discovered from the
  `vote_menu` XML, not assumed; (c) H2 absence forces the state verdict to DEFER.
