# Plan — profiles, topic subscriptions, bill tracking, and alerts

**Status:** RATIFIED PRIORITY (owner, 2026-09-23, SD-32). Nothing here is built
yet. Decision 1 below is settled: the site may read and collect the user data
its features need; `IMPLEMENTATIONv2.md` §0.4.3, SD-28, §3, §5, §7 V2-7/V2-8,
§8, §10 and its build order were amended the same day. Build order is
V2-11 → V2-7 → V2-8 → V2-12 → V2-13; V2-6 deferred. Decisions 2–7 are still
open and are asked with real numbers at the end of V2-11 task 1. Written in
the spec's increment form (Goal → Tasks → Acceptance → On failure).

**The request (owner, 2026-09-23):** create profiles; let a user say what matters
to them; subscribe to topics; get a text or email when something happens on a
topic (e.g. a bill that affects gun rights); live-track specific bills.

---

## 0. What exists today that this builds on (verified 2026-09-23)

| Piece | State | Consequence for this plan |
|---|---|---|
| Bills | 1,038 committed in `data/bills/`, **only bills that reached a roll call**. Each carries `policy_area` (31 seen) and CRS `subjects` (872 distinct terms, e.g. "Firearms and explosives"), sponsor, cosponsors, `latest_action` + date. | Topic vocabulary already exists and is **government-assigned** (no LLM, no builder-authored labels). But a bill "coming up" at introduction/committee stage is not in the dataset. |
| Bill actions | Only the single `latest_action` string is stored. No action history. | "Live track a bill" needs the full action timeline. Congress.gov exposes it as a `/bill/{c}/{type}/{n}/actions` sub-resource (fields: actionDate, actionTime, text, type, actionCode, sourceSystem, recordedVotes). |
| Member legislation | 37,669 distinct sponsored bills across `data/legislation/`, but each item is title + introduced date + became-law only. No subjects, no actions. | Not usable as the topic index without a per-bill fetch. |
| Refresh cadence | One `nightly.yml` run at 09:15 UTC; ingest at ≤ 1 request/second; commit → Workers Builds deploy. | Any alert built on today's pipeline is **next-day** at best. Faster alerts need a second, lighter workflow or a Worker cron. |
| Server side | None. `site/wrangler.jsonc` is static assets only. No `worker/`, no D1, no email. | Accounts, subscriptions, and sending are all new (spec V2-8 already sketches `worker/` + D1). |
| Published data on the web | **`data/` is not served.** `site/src/lib/data.ts` reads JSON from disk at build time; `site/public/` holds only fonts; `dist/` has no data directory. The repo is private (D59), so GitHub raw URLs are closed too. | Anything a Worker or a browser must read (the events feed) has to be emitted as a static asset by the build, counted against the file gate. |
| Privacy page | Live `/privacy` says: no account, no cookies, no analytics, no per-visitor data. **True today.** | Hard gate: V2-7 rewrites it truthfully **before** any collection ships (§0.4 Value #3, Value #1). |
| Hosting plan | Workers Free: 20,000 static files/version (site is at 13,093 files), 100k requests/day, 5 cron triggers. D1 free tier daily limits are now hard-enforced (since 2026-09-01): 5M rows read/day, 100k rows written/day, 5 GB. **Email Sending requires Workers Paid** ($5/mo; 3,000 emails/month included, then $0.35 per 1,000). | Sending email from Cloudflare needs the paid plan. A page per introduced bill would also blow the free file limit. |
| Spec V2-8 (SD-28, now amended by SD-32) | Was: accounts = email + password; quiz answers and weights encrypted on the device, unreadable by the operator. **Now (2026-09-23): the server stores user data readable**; encryption requirement retired. | Server-sent alerts can read the subscription list. Resolved (decision 1 = yes). |

---

## 1. Decisions for the owner (plain language, each option's consequence)

Nothing below is a builder call. Answer these and the increments in §2 become buildable.

**1. Can the site keep a readable list of what you subscribe to? — RATIFIED YES (SD-32, 2026-09-23).**
The owner directed that nothing in the docs may stop the site from reading or
collecting the data its features need. Consequence, stated plainly: what each
account follows, its preferences, quiz answers, and notification addresses are
stored readable by the operator and can be produced under a legal demand. The
spec's §10 records this trade. Guardrails that remain: collect nothing no
scheduled feature needs; list every stored table on `/privacy` before it exists
(V2-7); never sell; K-anon for anything published; hard delete.

**2. Which delivery channel first?**
- **Email first (recommended).** Cheapest, no registration hurdles, one vendor (Cloudflare Email Service on the domain the site already uses, or a third party like Resend). The vendor sees recipient addresses; `/privacy` names it.
- **Text messages.** Phone numbers are a **new kind of data the spec does not list** (§0.4 Value #3 lists email, quiz answers, weights, analytics). Adding them is a spec amendment. US application-to-person texting also requires carrier registration (business identity and campaign vetting; fees and multi-week timelines vary by provider and must be verified, not assumed), per-message cost, and STOP-keyword handling. The carrier and the provider see the message text, which names the topic. Recommend: phase 2, after email works.
- **Browser push.** The server stores a push endpoint per browser and can send the matched alert directly (SD-32). Works on phones. No cost. Dies when the user clears the browser.

**3. Which bills should the site cover?**
- **(a) Bills with floor activity (today's 1,038 and growing).** No new fetch volume, stays under the free file limit. But a bill is only "seen" once it gets a recorded vote, which is late for "a bill comes up."
- **(b) Every bill introduced in the covered Congresses.** Roughly 15,000–20,000 bills per Congress (to be measured with one list call before committing). Catches introduction, committee referral, and reporting. Costs: a longer ingest, a Workers Paid upgrade if every bill gets a page (or no page per bill, feed-only), and a much larger `data/bills/`.
- **(c) Middle: (b) for the data and feeds, (a) for pages.** *Recommended.* All bills tracked for alerts; only floor-activity bills get their own page until the plan upgrade is decided.

**4. What are "topics"?**
- **(a) Official terms only (recommended for the first release).** The 31 policy areas and the CRS legislative subject terms, verbatim. "Gun rights" is not a term; "Firearms and explosives" is. The site never invents or reworded a label (§0.5 no-LLM; Value #1 framing). Users search the official list.
- **(b) Owner-curated bundles on top.** A plain name ("Guns") mapping to a set of official terms, authored by the owner in a committed YAML file with a date, exactly like statement curation. This is editorial authorship; it is disclosed on `/methods`. Can come later without changing anything else.

**5. Order of work — RATIFIED (SD-32).** **V2-11 (bill activity + topics + feeds, zero collection) → V2-7 (privacy truth) → V2-8 (accounts) → V2-12 (subscriptions + email) → V2-13 (text / push)**; V2-6 deferred until enough nightly history exists. Recorded in the spec's §7 and end-of-document build order.

**6. How fast should alerts arrive?**
- **Daily digest** (one email per day, if anything happened): fits the existing nightly, cheapest, least noisy.
- **Every few hours:** a second lightweight workflow polling Congress.gov for updated bills; more commits and deploys per day (Workers Builds has monthly build-minute quotas to verify). Alerts within hours, not days.
- **Both** (user picks per subscription). Recommended eventual state; digest-only first.

**7. Cloudflare Workers Paid ($5/month).** Needed for Email Sending regardless, and for the 100,000-file limit if all bills get pages. Yes/no.

---

## 2. Increments

### V2-11 — Bill activity, topics, and feeds (ZERO collection; no privacy gate)
**Goal:** every covered bill has its full official action timeline; a `/topics/`
index built from the government's own subject vocabulary; per-bill, per-topic,
and per-member Atom feeds so anyone can "live track" without an account; and a
committed, recomputable `data/events/` record of what changed. Ships under the
current `/privacy` page unchanged (static, nothing collected).
**Depends on:** decisions 3, 4, 6.
**Tasks:**
1. **Verify the API surface first (one session, one authenticated call each):**
   the `/bill` list endpoint's update-date filtering/sorting parameters and page
   size (the public docs defer to the OpenAPI spec; confirm live), the `/actions`
   sub-resource shape and pagination, and the per-key hourly rate limit. Record
   in `docs/decisions.md`. Do not size the ingest from memory.
2. `ingest/sources/congress_gov.py`: add `bill_actions()` (cached, paginated)
   and `bills_updated_since(from, to)` (list endpoint). Same cache + ≤ 1 req/s.
3. `ingest/models.py`: `BillAction(date, time|None, text, type, action_code|None,
   source_system, rollcall_id|None)`; `Bill.actions: list[BillAction] | None`
   (`None` = not collected, D27 sentinel). Action text is stored **verbatim**;
   nothing is summarized or classified (§0.5). `recordedVotes` resolved to an
   existing `RollCall.id` where it matches, else left null.
4. `ingest/bills.py`: fetch actions for every exported bill (same "every run,
   never revert to None" rule as subjects). If decision 3 = (b)/(c): a new
   `ingest bill-activity` command that enumerates bills updated in the window
   and ingests them (detail + subjects + actions), quarantining malformed ones
   under the existing ceiling.
5. `ingest/events.py` (pure): project `data/bills/**` into `data/events/
   {YYYY-MM}.json` — one row per (bill_id, action date, action text hash) with
   type, policy_area, subjects, and the bill's source URL. Deterministic, no
   wall-clock, byte-stable on a quiet run. `verify-recompute` gains **invariant
   8** (events re-derive byte-exact from bills).
5b. **Serve the feed.** `data/` is not on the web today (build-time reads only,
   private repo). Add an Astro static endpoint `site/src/pages/events/
   [month].json.ts` that emits each month file verbatim, plus `/events/latest.json`
   (the current month). These are the only machine-readable URLs the V2-12 Worker
   and the V2-13 push client read. Each is one built file (file gate).
6. `data/topics/index.json`: every policy area and subject term with its bill
   count and bill ids. Slugs are mechanical (lowercase, hyphens); display text
   is the official term verbatim. If decision 4(b): `data/config/topic-bundles.yaml`
   (owner-authored, dated) rendered as its own section with the authorship stated.
7. Site: `/b/[bill]` gains an **Actions** timeline (date, verbatim text, source
   link; roll-call actions link to `/v/`); `/topics/` index + `/topics/[slug]/`
   (bills in the topic, most recent action first); Atom feeds at
   `/b/[bill]/feed.xml`, `/topics/[slug]/feed.xml`, `/m/[member]/feed.xml`
   (a NEW route beside the paginated `/m/[member]/[page]/` pages; their votes
   and sponsored-bill actions), and `/feed.xml` (all floor activity).
   **Pageless bills (decision 3c):** a topic page or feed entry for a bill that
   has no `/b/` page links to the bill's `source_url` on congress.gov, never to
   a `/b/` URL that does not exist — otherwise `npm run test:links` fails on the
   first one. A stub page per bill is the alternative and reopens decision 7.
   Feed `updated` = latest action date (no build wall-clock; determinism holds).
   A "Track this bill" affordance on bill pages that is, in this increment, the
   feed link plus a copy button, JS-off friendly.
8. Cadence (decision 6): either fold into `nightly.yml` after `ingest bills`, or
   add `bill-activity.yml` on a 4–6 hour cron that runs only the bill-activity
   ingest + export + checks + commit (`data: activity YYYY-MM-DDTHH`). **Push
   collision:** the nightly runs 4–5 hours between its checkout and its push;
   a second workflow committing to `master` in that window makes the nightly's
   push non-fast-forward and fails a green night. Mitigation, required: both
   workflows share `concurrency: group: nightly` (queued, never cancelled), and
   the light workflow does `git pull --rebase` immediately before `git push`.
   Every extra commit is also an extra Workers Builds deploy. Measure build
   minutes on the first week; report.
9. File-count gate: every feed and topic page is a built file. Project the count
   before building; if decision 3 puts it over 18,000, stop and take decision 7
   to the owner (H14 already says so).
**Which tests break legitimately:** manifest counts, bill schema tests, links
count, file-count. **Must stay green:** determinism, banned-words, no-LLM,
recompute, grade labels.
**Acceptance:** `uv run checks && uv run pytest && uv run verify-recompute &&
npm run build && npm run test:file-count && npm run test:links && npm run
test:e2e` (new e2e: bill timeline renders, topics page a11y + 380px, feed
validates against the Atom schema).
**On failure:** an action not traceable to a Congress.gov record may not
render; a topic label that is not a verbatim government term (or a dated
owner bundle) fails the build.
**Estimate:** 3–4 sessions. Half a session if the API verification in task 1
contradicts the assumptions above (then re-plan).

### V2-7 — Privacy truth gate (as amended in the spec, 2026-09-23)
The spec's §7 V2-7 now carries the SD-32 wording. The `/privacy` rewrite and
the threat-model page state, in plain words: every table the Worker will hold
(§5 list), that the operator can read it, that a legal demand can yield it;
the email vendor (decision 2) and what it sees; phone numbers and the texting
provider/carrier (only if text alerts are chosen); the browser-push model (only
if chosen); that feeds (V2-11) and the whole public record need no account.
Acceptance and on-failure as in the spec (the drift-proof accuracy test asserts
the stated table list against the Worker schema). H19 canary decision is taken
here. **Estimate:** 1–2 sessions.

### V2-8 — Accounts + preference sync (as amended in the spec; needs H17, H18)
Per the spec's amended §7 V2-8: `worker/` (wrangler project; Hono or plain
fetch handler), readable D1 tables per §5, Argon2id, email verification,
password reset by email (no data loss), Turnstile, hard delete, logging off.
No client-side crypto, no recovery code (retired by SD-32). If the owner picks
Cloudflare Email Service for H18, the domain onboarding (SPF/DKIM/DMARC)
happens here because signup verification needs it. **Estimate:** 3–5 sessions
(down from 4–6: the crypto layer is gone).

### V2-12 — Subscriptions + email alerts (needs V2-7, V2-8, decision 7)
**Goal:** a signed-in user follows bills, topics, and members; receives an email
digest (and optionally immediate emails) when a followed thing has a new event;
every email has a one-click unsubscribe; the Worker reads **only published
data** plus the subscription table.
**Tasks:**
1. D1: `subscriptions(user_id, kind ∈ {bill, topic, member}, key, cadence ∈
   {digest, immediate}, created_at)`; `deliveries(user_id, event_key, sent_at)`
   for idempotency; `email_verifications` (double opt-in before any alert).
2. Worker cron (hourly; free-plan cron is fine, sending needs Paid): fetch the
   published `https://civicledger.net/events/latest.json` (V2-11 task 5b; the
   month files for catch-up), diff against `deliveries`, group per user, render plain-text +
   minimal-HTML email from the same templates the site uses (verbatim action
   text, bill link, source link; no summaries), send via the `send_email`
   binding, record deliveries. Daily digest at a fixed UTC hour; immediate mode
   sends on the next hourly tick.
3. Unsubscribe: signed token link per email (no login needed to stop mail); a
   List-Unsubscribe header; account deletion cascades.
4. Site: "Follow" buttons on `/b/`, `/topics/`, `/m/` pages as a small island
   (JS-off shows the feed link); an account page listing subscriptions with
   per-row cadence and remove.
5. Caps: max subscriptions per account (mechanical, ADR), max emails per user
   per day, and a global daily send ceiling below the plan's included quota
   with an alert to the owner when 80% is reached.
6. Aggregate exposure: the site publishes **no** subscription counts unless
   they pass the existing K-anon (= 50) gate; default is publish nothing.
**Tests:** delivery idempotency (same event never sent twice); unsubscribe e2e;
schema test (tables == the `/privacy` storage list); Playwright network
assertion that follow/unfollow requests carry only the documented fields; email
template renders banned-words clean.
**Acceptance:** full python + `npm run build && npm run test:e2e` against
`wrangler dev` with a stubbed email binding; one real end-to-end email to a
verified owner address. **On failure:** an email that would contain any text
not present verbatim in the published record may not send.
**Estimate:** 3–4 sessions.

### V2-13 — Text messages and/or browser push (needs a spec amendment for phone)
- **Push:** service worker + push subscription stored on the Worker (a
  `channels` row of kind `push`); on each hourly tick the Worker sends the
  matched alert payload (same text as the email). **Estimate:** 2 sessions.
- **SMS:** only after the owner amends Value #3 to list phone numbers and
  ratifies the provider. Provider account, sender registration, and consent
  wording (express opt-in, STOP handling) are human tasks; the builder should
  not promise a date until the provider confirms registration timing. Message
  body is minimal (bill label, event type, short link). **Estimate:** 2 sessions
  of build plus the provider's registration wait.

### Profiles — "input what is important to you"
A profile = an account (V2-8) + what it follows (V2-12) + a readable
`preferences` record (V2-8) that can hold issue priorities now and quiz answers
when the parked INC-14 quiz is scheduled. Since SD-32 there is no encrypted
layer; every field is listed on `/privacy`. A per-subscription priority that
orders the digest is a small V2-12 add-on if the owner wants it (a column on
`subscriptions`, mechanical ADR).

---

## 3. Human tasks this plan adds or reuses

| # | Task | Blocks |
|---|---|---|
| H17 (existing) | Turnstile keys | V2-8 |
| H18 (existing) | Email provider. Option now available: Cloudflare Email Service on `civicledger.net` (needs Workers Paid, domain onboarding in the dashboard). Or Resend etc. | V2-8, V2-12 |
| H19 (existing) | Warrant-canary decision | V2-7 |
| H20 (new) | Workers Paid upgrade decision ($5/mo) | V2-12 (email); V2-11 only if per-bill pages exceed 18,000 files |
| H21 (new) | Spec amendment: phone numbers as a collected data class; SMS provider account + sender registration + consent wording | V2-13 SMS |
| H22 (new) | Topic bundle curation (only if decision 4b) | V2-11 bundles section |
| H23 (new) | Congress.gov API key hourly limit: confirm the current per-key limit in the api.data.gov account, request a raise if the bill-activity ingest needs it | V2-11 |

---

## 4. Risks and how each is caught

- **Static file limit.** Feeds + topic pages + bill pages can cross 20,000.
  Caught by the existing CI file-count gate before deploy. Mitigation: decision
  3(c) and/or H20.
- **Determinism of events and feeds.** No wall-clock anywhere; `updated` from
  data. Caught by `tests/test_export_contracts.py` and recompute invariant 8.
- **Two workflows, one branch.** A bill-activity cron committing while the
  nightly is mid-run rejects the nightly's push. Caught by the shared
  concurrency group + pull-rebase in V2-11 task 8; symptom if missed is a
  failure email on a night with a valid dataset.
- **API assumptions.** List-endpoint parameters and rate limit are unverified
  in this plan. Caught by V2-11 task 1 before any code.
- **Deliverability.** SPF/DKIM/DMARC on the sending domain; start with the
  provider's ramping quota; digest-first keeps volume low.
- **D1 free-tier daily limits** (100k writes/day) are hard-enforced now. One
  `deliveries` row per sent email is far below that at launch; the Paid plan
  removes it anyway.
- **Legal wording.** Commercial-email and texting consent rules exist (one-click
  unsubscribe; express opt-in for texts). The plan builds the mechanisms;
  the owner should confirm the wording with someone qualified. Not legal advice.
- **Value #1 drift.** Every user-facing sentence about what is collected must
  land in the same increment as the collection (§6.7 atomic flip). The V2-7
  accuracy test enforces it.

---

## 5. Next session — start here (V2-11 task 1)

Decision 1 and the order are ratified (SD-32). Nothing else is needed to begin.
1. V2-11 task 1: verify the Congress.gov list/actions endpoints live (one
   authenticated call each, via the existing cached client); measure the bill
   universe size for the 118th–119th and the daily update volume; project the
   built file count for each option of decision 3. Record in `docs/decisions.md`.
2. Put decisions 2, 3, 4, 6, 7 to the owner in plain language **with those
   numbers** (one message, each option's consequence stated).
3. On his answers, build V2-11 tasks 2–9. Commit `V2-11: <what>` at each
   passing gate.
