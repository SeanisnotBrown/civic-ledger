# DRAFT — V2-7 privacy claims, for the owner to approve

**Status: PROPOSAL. Nothing here is built, and no site file was changed to produce it.**
This document is the evidence pack for the V2-7 `/privacy` rewrite. It exists because a
privacy page makes factual claims about a reader's data, and a wrong claim is worse than no
claim. Every sentence proposed in §4 is traceable to a file and line, or to a decision the
owner has already ratified. Anything that is not traceable became a question in §5 instead
of prose.

Written 2026-10-05. Verified against the working tree at commit `55f69092c`.
Scope note: the threat-model page is V2-7 **task 2** and is a separate deliverable; it is
not drafted here (see §6).

---

## 1. What the live `/privacy` page claims today

Source: `site/src/pages/privacy.astro` (30 lines). Confirmed against the built output at
`site/dist/privacy/index.html`, which matches the source word for word.

| # | The claim, as the page words it | Where | Verdict |
|---|---|---|---|
| C1 | "This site is built to collect as little as possible." | `site/src/pages/privacy.astro:7` | **TRUE TODAY**, **WILL BECOME FALSE as worded**. See note C1 below. |
| C2 | "This is a summary; the full threat model lands with the interactive features that could otherwise gather data." | `privacy.astro:7-9` | **TRUE TODAY** (a promise, and V2-7 task 2 is the thing that keeps it). |
| C3a | "Static pages, built from a dataset the operator maintains." | `privacy.astro:14` | **TRUE TODAY.** `site/astro.config.mjs:11` is `output: "static"`; `site/wrangler.jsonc:11-17` serves `./dist` as static assets with no Worker script. |
| C3b | "No account, no login." | `privacy.astro:14` | **TRUE TODAY** (no `worker/` directory exists). **WILL BECOME FALSE at V2-8** (`IMPLEMENTATIONv2.md:662-669`). |
| C4 | "No cookies." | `privacy.astro:15` | **TRUE TODAY of this codebase** — zero hits for `document.cookie`, `localStorage`, `sessionStorage`, `indexedDB` anywhere in `site/src`, `site/public`, `site/scripts`. **Not verified at the hosting layer** (§2.3). **WILL BECOME FALSE as worded at V2-8** — a signed-in session is normally a cookie, and the spec's governing rule already anticipates that: "no cookies for the anonymous experience" (`IMPLEMENTATIONv2.md:761`). The promise that survives is the narrower one: readers without an account get no cookie from this site. |
| C5 | "No analytics." | `privacy.astro:15` | **TRUE TODAY.** **WILL BECOME FALSE at V2-9** — Cloudflare Web Analytics is the ratified plan (`IMPLEMENTATIONv2.md:680-687`, SD-17 as amended, `IMPLEMENTATIONv2.md:230`). |
| C6 | "No third-party fonts, scripts, or CDNs." | `privacy.astro:15` | **TRUE TODAY**, verified — see §2.1. **WILL BECOME FALSE at V2-8**, one increment earlier than most people would guess: Turnstile (H17, `docs/HUMAN-TASKS.md:26`) is a third-party script, and V2-9's analytics adds another. |
| C7 | "Every fact on a member, vote, or bill page links to the original government record it came from, so you can check it yourself." | `privacy.astro:20-22` | **TRUE TODAY**, and mechanically enforced — `npm run test:links` now checks every topic row and every feed entry in both directions (`docs/PROGRESS.md:122-126`). |
| C8 | "The dataset and source code are not currently published in a public repository; a legal demand to the operator would produce only what that private repository contains." | `privacy.astro:22-24` | **First half TRUE** (repo private, D59, `docs/decisions.md:1046`). **Second half is FALSE TODAY**, narrowly, and **decisively false at V2-8**. See note C8 below. **This is the most important finding in §1.** |
| C9 | "The full threat model will document every data-collecting surface before it ships." | `privacy.astro:27-28` | **TRUE TODAY** as a promise; V2-7 is the increment that has to honour it. |

**Note C1.** The page promises a superlative ("as little as possible"). The amended Value #3
promises something narrower: "collect nothing no scheduled feature needs"
(`IMPLEMENTATIONv2.md:161-163`, SD-32). Those are not the same sentence. Once accounts,
subscriptions, notification addresses, quiz answers and issue weights are stored
(`IMPLEMENTATIONv2.md:344-355`), "as little as possible" is a claim the project cannot
defend and does not need to make. Recommend replacing it with the ratified wording rather
than keeping a stronger promise than the owner actually made.

**Note C8 — why the second half is already wrong.** The sentence says a legal demand would
produce *only* what the private repository contains. On the operator's own machine today
there is material the repository does not contain and deliberately excludes: the raw API
cache `data/raw/` (gitignored, `IMPLEMENTATIONv2.md:264-265`), the SQLite intermediate
`build.db` (gitignored, same line), the backfill log `backfill-118.log` (gitignored,
`docs/PROGRESS.md:42`), and `.env` secrets. None of that is reader data — it is government
records and credentials — so the practical privacy harm today is low. But the sentence as
written is a factual claim about the limits of a legal demand, and it is not accurate. At
V2-8 it becomes decisively false: the D1 database holding emails and subscription lists is
not in any repository (`IMPLEMENTATIONv2.md:344-345`, "never exported to `data/`").

**Note on wording precedent.** On 2026-09-30 the owner ruled on exactly this family of
claim: "visiting this site leaves no record anywhere", "nothing you do here is sent to any
server the operator runs", and "results stay in your own browser" were **stripped, not
reworded**, because "the no-logging claim is impossible for what the project needs to do"
(`docs/decisions.md:2038-2045`; `docs/PROGRESS.md:659-661`). That ruling is the standard
this document applies.

---

## 2. What the site actually does with reader data today

Established from code. Where the repository cannot settle something, it says so and the
question moves to §5.

### 2.1 Analytics, telemetry, third-party scripts — none

- No analytics or telemetry code anywhere in `site/src`. No `fetch(`, no
  `XMLHttpRequest`, no `sendBeacon`, no `WebSocket`, no `EventSource`. The only
  `navigator.*` use in the whole site is `navigator.clipboard` at
  `site/src/pages/b/[bill].astro:199` and `:202`.
- No Cloudflare Web Analytics beacon, no `cloudflareinsights`, no `observability` or
  `logpush` key anywhere in `site/wrangler.jsonc`, `site/astro.config.mjs`, or `.github/`.
- **Built output checked, not just source.** Every `https://` reference in the built HTML
  and JS resolves to a government record site that the reader is *linked to*
  (`clerk.house.gov`, `www.senate.gov`, `legiscan.com`, `bioguide.congress.gov`,
  `www.congress.gov`, `billstatus.ls.state.ms.us`, `www.cbo.gov`). Those are hyperlinks in
  page text, not scripts, stylesheets, or images — nothing third-party loads when a page
  renders.
- Fonts are self-hosted: `site/public/fonts/` holds the file, preloaded from the site's own
  origin at `site/src/components/Layout.astro:47`.
- Client JavaScript is three things only: the Compare island
  (`site/src/pages/compare.astro:82`, `client:load`), the member browser
  (`site/src/pages/federal/index.astro:82`, `client:idle`), and one inline script on bill
  pages that reveals a clipboard button (`site/src/pages/b/[bill].astro:192-211`). All three
  run entirely in the reader's browser and send nothing anywhere.

### 2.2 Cookies and browser storage — none written by this site

Zero occurrences of `document.cookie`, `localStorage`, `sessionStorage`, or `indexedDB`
across `site/src`, `site/public`, and `site/scripts`. The site stores nothing in the
reader's browser. (Spec §10.1 at `IMPLEMENTATIONv2.md:761-765` permits `localStorage` with a
visible erase button; nothing has used it yet.)

### 2.3 What the hosting layer logs — INFERRED, not controlled by this codebase

**Be explicit about the epistemic status of this section: it is a platform behaviour
inferred from configuration, not something the repository decides.**

What the repository shows: `site/wrangler.jsonc` is a Cloudflare Workers Static Assets
project, name `civic-ledger`, serving `./dist`, with **no `main`** — i.e. no Worker script at
all (`site/wrangler.jsonc:1-18`). There is no `_headers`, no `_redirects`, no
`_routes.json`, and no `observability` or Logpush configuration anywhere in the repo. So
**nothing in this codebase turns any logging on or off.** V2-8's promise of "logging off,
config committed" (`IMPLEMENTATIONv2.md:669`, `docs/plan-subscriptions-and-alerts.md:165`)
is a *future* commitment; no such config exists today.

What is already acknowledged: the owner's own 2026-09-30 ruling records that "Cloudflare
hosts the site and reports request counts" (`docs/decisions.md:2040`). That is the anchor
for saying plainly that a reader's visit is seen by the host.

**Three things the repository cannot settle** (they live in the Cloudflare dashboard, not
in git) — all three are §5 questions:

1. Whether any Cloudflare feature that sets a cookie is enabled on the zone (Bot Fight Mode
   sets a `__cf_bm` cookie, for example). This is why claim C4 can only be verified *as to
   the site's own code*.
2. Whether Logpush or any log retention is configured, and to where.
3. What Cloudflare retains by default under the plan in use, and for how long.

### 2.4 Forms, inputs, and outbound requests

- **No `<form>` element exists anywhere in the site.** No `action=` attribute, no
  `method="post"`.
- Exactly two `<input>` elements exist:
  - `site/src/pages/b/[bill].astro:175-182` — `readonly`, pre-filled with the bill's own
    feed address. It accepts no typing and submits nowhere.
  - `site/src/components/MemberBrowser.tsx:331-338` — a search box that filters a list
    already embedded in the page. It makes no request.
- **The one genuine finding here, and it is unflattering: the member browser writes the
  reader's typed search text into the page's own web address.**
  `site/src/components/MemberBrowser.tsx:137-144` builds a query string from the chamber,
  party, grade, **typed search text (`q`)** and sort, then calls
  `window.history.replaceState(...)`. `replaceState` itself sends nothing — but the address
  bar now contains what the reader typed. If they then reload, bookmark, or share that
  address, the typed text travels to the host in the request. The same applies to
  `/compare?m=...` links (`MemberBrowser.tsx:244-248`, `Compare.tsx:71-74`): choosing members
  to compare and clicking through is a real navigation, so the set of members a reader
  compared is in the address the host receives. The feature is good (shareable,
  deep-linkable views) and the mechanism is ordinary, but a truthful page should not pretend
  browsing is invisible.
- **Outbound source links.** Every link to a government record carries `rel="nofollow"`
  (14 occurrences across `site/src`) but **not** `noreferrer`, and the site sets no
  `Referrer-Policy`. Stated precisely: under modern browsers' default
  (`strict-origin-when-cross-origin`) the government site learns that the visitor came from
  `civicledger.net`, **not which page they came from**. This is browser default behaviour,
  not something the repository configures. *(Implementation option for whoever builds V2-7,
  not an owner question: add an explicit `Referrer-Policy` so the behaviour is stated rather
  than inherited.)*

### 2.5 "Track this bill" — PROGRESS's claim verified

PROGRESS records that the feature offers "the feed link and a selectable address" with "no
account" (`docs/PROGRESS.md:108-113`). **Verified against the code**, not repeated:
`site/src/pages/b/[bill].astro:164-190` renders a heading, a link to `/b/{id}/feed.xml`, a
`readonly` input holding the feed address, and a copy button that starts `hidden` and is
revealed by script only if `navigator.clipboard` exists. With JavaScript off the reader gets
a working link and a selectable address and no dead control. There is no account, no
subscription record, and no request to any server the operator runs. **That much of the
claim is accurate.**

**But the same section also says, at `site/src/pages/b/[bill].astro:170`: "No account, and
nothing about you is recorded."** That is the second half of a claim this codebase cannot
support, and it is the same claim-family the owner ordered stripped on 2026-09-30. It
renders on **every** bill page (the section sits outside the actions conditional), and it was
written on 2026-10-02 as part of V2-11 task 7 (D97) — **after** that ruling. Fetching the
feed is a request to the site, so it is seen by the host exactly as a page view is; a feed
reader polling on a schedule produces a *recurring, identifiable* request pattern, which is
more of a record than a single visit, not less.

Two code comments carry the same wording — `site/src/lib/topicFeed.ts:5` and
`site/src/pages/b/[bill]/feed.xml.ts:2` ("needs no account and records nothing about the
reader"). Those are comments, not claims to readers, but they will mislead the next builder
and should be corrected in the same pass.

One related fact the page's current wording predates: as of V2-11 task 5b the dataset is
**partly on the web** — a month file at `/events/{month}.json` for every month, plus
`/events/latest.json`, are served
(`docs/PROGRESS.md:103-105`, `docs/plan-subscriptions-and-alerts.md:103-107`). The repository
is still private, so C8's first half holds, but "the dataset is not published" is no longer
the whole picture.

---

## 3. What the planned features will store

Drawn from `IMPLEMENTATIONv2.md:344-355` (the §5 account model) and
`docs/plan-subscriptions-and-alerts.md`. **Nothing in this section is built.**

| Table | Fields as specified | Where it lives | Retention | Specified, or open? |
|---|---|---|---|---|
| `users` | `id, email, email_verified_at, pw_hash` (Argon2id), `created_at` | Cloudflare D1, **never exported to `data/`** (`IMPLEMENTATIONv2.md:344-345`) | Until the user deletes; hard delete cascades (`IMPLEMENTATIONv2.md:668`) | **Specified** |
| `preferences` | `user_id, json, updated_at` — quiz answers, issue weights, settings | D1 | Same as `users` | **Specified** that it exists and is readable; the JSON's own shape is open |
| `subscriptions` | `user_id, kind ∈ {bill, topic, member}, key, cadence, created_at` | D1 | Same as `users` | **Specified.** The plan adds `cadence ∈ {digest, immediate}` (`plan:177-179`); the spec leaves `cadence` bare |
| `deliveries` | `user_id, event_key, sent_at` — alert idempotency | D1 | **NOT SPECIFIED.** As written this grows forever: one row per alert ever sent to that person, which is a dated history of what they were told about | **GAP — owner decision** |
| `channels` | `user_id, kind ∈ {email, phone, push}, address, verified_at` | D1 | Same as `users` | **Specified** that it exists; phone only after the owner ratifies it (H21) |
| `profiles` | `user_id, published_json, updated_at` — the opt-in public profile | D1, and **whatever is published is public** (`IMPLEMENTATIONv2.md:353-354`) | Same as `users` | **Specified** |
| `email_verifications` | not enumerated | D1 | **NOT SPECIFIED** — no token lifetime stated | **GAP — and it is also a list mismatch, see below** |
| K-anon counters | integer counts only, K = 50 gate before anything renders | D1, exported to `data/aggregates/` only above threshold | not stated | K = 50 is **ratified** (SD-28; `ingest/config.py` `K_ANON`) |
| Analytics (V2-9) | aggregate traffic + state of origin; "IP read transiently for geo by the edge, never written" | Cloudflare Web Analytics + optional Worker counter `(iso_week, region)` | not stated | **Specified as aggregate and cookieless**; retention open |

### Three gaps that block the page, not the build

**▶ STATUS 2026-10-06: gap 1 is CLOSED and gap 3 no longer blocks.** The owner ratified the table list at SEVEN (SD-38) — `email_verifications` is disclosed on its own line — and SD-36 named the email sender, so `/privacy`'s forward-looking half shipped the same day (D102). **Gap 2 (`deliveries` retention) is still open**, and so is the confirmation-code lifetime that rides with it: Q4. Read the rest of this section as the record of why the page waited, not as work outstanding.

1. **The two table lists disagree.** — **ANSWERED: seven, SD-38 (2026-10-06).** The spec's §5 names six tables. The plan's V2-12 task 1
   adds a seventh, `email_verifications` (`docs/plan-subscriptions-and-alerts.md:177-179`).
   The V2-7 acceptance test asserts that the page's stated storage list **equals** the Worker
   schema (`IMPLEMENTATIONv2.md:655-658`, `:672`). So the page cannot be written until
   someone declares which list is canonical. **This is not a reconciliation a builder should
   make silently** — the whole point of the test is that the page and the schema agree, and
   picking the list by guess defeats it.
2. **`deliveries` has no retention period.** An unspecified retention period is an owner
   decision, not a builder's. §5 below asks it.
3. **Verification and password-reset tokens have no stated lifetime.**

### What is already ratified and therefore citable

- **Never sold.** `IMPLEMENTATIONv2.md:165` and SD-32 both say it. The exact ratified
  wording is "never **sold or shared beyond the named service providers**" — so the "not
  sold" half is citable now, and the "shared with" half is blocked on H18, because no
  provider has been chosen (`docs/HUMAN-TASKS.md:27`, still pending).
- **Deletion hard-deletes, cascading every table** (`IMPLEMENTATIONv2.md:668`).
- **Anonymous use of the whole public record stays available forever**
  (`IMPLEMENTATIONv2.md:162-163`); feeds need no account (`IMPLEMENTATIONv2.md:644`).
- **The operator can read the stored user data**, and a legal demand can produce it
  (SD-32; `IMPLEMENTATIONv2.md:747-759`).
- **K = 50** for anything published from user data.

---

## 4. The proposed page, claim by claim

**Not prose. One row per claim, for the owner to approve, strike, or reword line by line.**
Plain language; where a technical term is unavoidable it is defined in the same sentence.
A claim with no evidence column does not exist — it is a question in §5 instead.

### 4a. What is true today (the page as it could ship now)

| Proposed claim, in plain words | Evidence | Status |
|---|---|---|
| "You can read every page on this site without an account. There is nothing to sign up for." | no `worker/` exists; `IMPLEMENTATIONv2.md:54-56` | `VERIFIED TODAY` |
| "The pages are built in advance and handed to you as finished files. Nothing on a page is assembled from anything about you." | `site/astro.config.mjs:11`; `site/wrangler.jsonc:11-17` (no Worker script) | `VERIFIED TODAY` |
| "If you do not have an account, this site puts nothing in your browser's storage — no cookies, nothing saved between visits." | zero `document.cookie` / `localStorage` / `sessionStorage` / `indexedDB` hits in `site/src`, `site/public`, `site/scripts`; wording matches the spec's own surviving rule, `IMPLEMENTATIONv2.md:761` | `VERIFIED TODAY` **as to this site's own code.** Hosting layer unverified — §5 Q1 |
| "No part of a page is loaded from anyone else's server. The typeface, the styles and the small amount of code all come from this site." | `site/public/fonts/`; `site/src/components/Layout.astro:47`; built output scan, §2.1 | `VERIFIED TODAY` |
| "There is no analytics or measurement code on this site." | no beacon, no `fetch`/`sendBeacon`, no `observability` key, §2.1 | `VERIFIED TODAY` |
| "There is no form on this site. There is nowhere to type something that gets sent to us." | no `<form>` anywhere; the only two inputs are read-only or filter-only, §2.4 | `VERIFIED TODAY` |
| "Every fact on a member, vote or bill page links to the government record it came from, so you can check it yourself." | `privacy.astro:20-22`; enforced by `npm run test:links`, `docs/PROGRESS.md:122-126` | `VERIFIED TODAY` |
| "You can follow a bill or a topic with a feed — a web address your reader checks for updates. It needs no account and we keep no list of who follows what." | `site/src/pages/b/[bill].astro:164-190`; no server exists to keep a list | `VERIFIED TODAY` — but **only in this narrowed form**; see the next row |
| "Like every website, this one is delivered by a hosting company. Cloudflare, which hosts it, sees and counts the requests your browser makes — including when your feed reader checks for updates." | `site/wrangler.jsonc`; owner's own ruling, `docs/decisions.md:2038-2045` | `NEEDS OWNER DECISION` on **wording** — §5 Q1. The fact is settled; he declined to add Cloudflare copy on 09-30, and that declining was about a deletion, not about the rewrite |
| "When you filter the member list or build a comparison, your choices — including anything you type in the search box — appear in the page's web address. That is what makes the view shareable. If you reload or share that address, those choices are part of the request the host sees." | `site/src/components/MemberBrowser.tsx:137-144`, `:244-248`; `Compare.tsx:71-74` | `VERIFIED TODAY` — awkward and worth saying anyway, §5 Q1 |
| "Clicking a government source link takes you to that government site, which can see that you arrived from this one." | `rel="nofollow"` only, no `noreferrer`, no `Referrer-Policy`; §2.4 | `VERIFIED TODAY`, stated at the right precision: origin only, not which page |
| "The source code and the dataset are not published in a public repository today." | D59, `docs/decisions.md:1046` | `VERIFIED TODAY` |
| "Machine-readable files of legislative activity are published on the site — one per month, plus one for the current month." | `/events/{month}.json` (one file per month) and `/events/latest.json`, `docs/PROGRESS.md:103-105` | `VERIFIED TODAY` |
| "We will never sell what we collect." | `IMPLEMENTATIONv2.md:165`; SD-32 | `VERIFIED TODAY` (ratified) |
| *(STRIKE — do not carry forward)* "a legal demand to the operator would produce only what that private repository contains" | §1 note C8 — false today, decisively false at V2-8 | **REMOVE** |
| *(STRIKE — do not carry forward)* "nothing about you is recorded" on every bill page | `site/src/pages/b/[bill].astro:170`; owner's 2026-09-30 ruling | **REMOVE** — §5 Q2 asks when |
| *(REWORD)* "built to collect as little as possible" → "we collect only what a feature we have actually decided to build needs" | `IMPLEMENTATIONv2.md:161-163` (the ratified wording) | `VERIFIED TODAY` once reworded |

### 4b. What the page must say before the next features ship — all `PLANNED — not yet true`

Every row here describes something that **does not exist yet**. Per §6.7 atomicity
(`IMPLEMENTATIONv2.md:687`), each sentence lands in the same increment as the thing it
describes. They are listed now so the owner approves the wording once.

| Proposed claim, in plain words | Evidence | Status |
|---|---|---|
| "If you make an account, we store your email address and a scrambled form of your password." | `IMPLEMENTATIONv2.md:346` (`users`, Argon2id) | `PLANNED — not yet true` |
| "We store the bills, topics and members you choose to follow, and how often you want to hear about them." | `IMPLEMENTATIONv2.md:349` (`subscriptions`) | `PLANNED — not yet true` |
| "We store your settings, and — if you answer them — your quiz answers and how much weight you give each issue." | `IMPLEMENTATIONv2.md:347-348` (`preferences`) | `PLANNED — not yet true` |
| "We store the email address, and later the phone number or browser, you ask us to send alerts to." | `IMPLEMENTATIONv2.md:353-354` (`channels`); phone needs H21 | `PLANNED — not yet true`; phone wording blocked on H21 |
| "**The operator can read all of it.** It is not scrambled or hidden from him. A court order could require him to hand it over." | SD-32; `IMPLEMENTATIONv2.md:747-759` | `PLANNED — not yet true`, and **the single most important sentence on the page.** Deliberately unflattering; do not soften |
| "Anything you choose to publish on your profile is public. Published means public." | `IMPLEMENTATIONv2.md:353-354`; `:643` | `PLANNED — not yet true` |
| "We keep a record of which alerts we have already sent you, so you are not told the same thing twice." | `IMPLEMENTATIONv2.md:350` (`deliveries`) | `PLANNED — not yet true`; **how long we keep it is §5 Q4** |
| "Deleting your account deletes it — every row, everywhere, not a flag that hides it." | `IMPLEMENTATIONv2.md:668` | `PLANNED — not yet true` |
| "To send you email we use [provider]. That company sees your email address and the contents of the message." | H18, `docs/HUMAN-TASKS.md:27`; `IMPLEMENTATIONv2.md:186` | `NEEDS OWNER DECISION` — §5 Q3. Cannot be written with a blank |
| "If we ever publish a number drawn from what people follow, we publish it only when at least 50 people are in the group, so no one person can be picked out." | SD-28; `ingest/config.py` `K_ANON`; `IMPLEMENTATIONv2.md:163-164` | `PLANNED — not yet true` (ratified number, nothing published from it yet) |
| "You will always be able to read the whole public record, and use the feeds, without an account." | `IMPLEMENTATIONv2.md:162-163`, `:644` | `VERIFIED TODAY` and stays true |
| "We do not share what we collect with anyone except the companies that deliver our email [and texts]." | `IMPLEMENTATIONv2.md:165` | `NEEDS OWNER DECISION` — the "except" list is empty until H18, §5 Q3 |
| "We will count visits and which pages are read, in totals only, and which state visitors are in — not individual people." | `IMPLEMENTATIONv2.md:680-687` (V2-9) | `PLANNED — not yet true`. Note: this breaks claims C5 **and** C6 |
| The exact list of what is stored, table by table | `IMPLEMENTATIONv2.md:344-355` vs `plan:177-179` | `NEEDS OWNER DECISION` — the two lists disagree, §5 Q5 |
| Warrant canary — retire, or "no demand received as of {date}" | H19, `docs/HUMAN-TASKS.md:28` | `NEEDS OWNER DECISION` — §5 Q6 |

### Status counts

Counting rule: the `REWORD` row counts once, as `VERIFIED TODAY` (it is true once reworded);
the 4b "stays true without an account" row is counted once, in `VERIFIED TODAY`.

- `VERIFIED TODAY` — **15** = 13 rows in §4a (all of it except the Cloudflare row and the
  two `REMOVE` rows) + the `REWORD` row + the §4b "no account needed" row
- `PLANNED — not yet true` — **10**, all in §4b
- `NEEDS OWNER DECISION` — **5**: the Cloudflare wording row in §4a, and in §4b the email
  provider's name, the "shared with" list, the canonical table list, and the canary
- Existing claims to change: **2** `REMOVE`, **1** `REWORD`

---

## 5. Questions only the owner can answer

Plain language. Ranked: the ones that block V2-8 come first. Each option has its
consequence on one line.

---

**Q1 — How do we describe the company that hosts the site? (blocks the whole page)**

The site is delivered by Cloudflare. Like any host, Cloudflare sees the requests your
readers' browsers make and counts them. On 2026-09-30 you told us to **delete** the
"no record anywhere" claims rather than add Cloudflare wording — but that was a deletion
decision, not a decision about what the rewritten page should say. Now we have to say
something.

- **(a) One plain sentence naming Cloudflare and what it sees.** Most honest. Reads as
  ordinary — every site has a host. Slight cost: a reader who did not think about it now
  does.
- **(b) A general sentence without naming the company** ("the company that delivers this
  site sees the requests your browser makes"). Still true, slightly vaguer, nothing to
  update if you ever change host.
- **(c) Say nothing about the host.** Cheapest to write, and the page is then silent on the
  one record that actually exists about a reader. We do not recommend this: silence here is
  how the page got into its current state.

**Follow-on, and we cannot answer it from the code:** three things live in your Cloudflare
dashboard, not in the repository, and the page's accuracy depends on them. Please check or
tell us to ask you later: **(i)** is any bot-protection feature switched on? (some of them
put a cookie in the reader's browser, which would make "no cookies" wrong); **(ii)** is any
log export ("Logpush") configured? **(iii)** is traffic analytics switched on for the
domain? Until we know (i), the page can only honestly say *this site's own code* stores
nothing in your browser.

---

**Q2 — A sentence on every bill page says "nothing about you is recorded." It is the same
claim you ruled impossible on 2026-09-30. Strip it now, or at V2-7?**

It was written on 2026-10-02, after your ruling, and it is live on every bill page.

- **(a) Strip it now, in its own small commit** — one line, same treatment you gave the
  other three. The page is then silent rather than wrong, immediately.
- **(b) Fix it inside V2-7** with the rest of the rewrite. Nothing is collected today so no
  reader is harmed in the meantime — but the sentence is still a claim the project cannot
  defend, sitting on every bill page (1,038 of them today).

We recommend **(a)**: it is one line and it matches what you already decided.

---

**Q3 — Which company will send the email? (blocks V2-8; it is human task H18)**

Account signup needs a verification email, so this is needed before accounts exist, not
when alerts start. Whoever we pick **sees your readers' email addresses and the text of
every message**, and the privacy page has to name them.

- **(a) Cloudflare Email Service**, on the domain the site already uses. One company
  instead of two. Needs the $5/month Workers Paid plan (that is question H20 anyway) and
  some domain setup.
- **(b) A separate provider (Resend, or similar).** Free tier to start; a second company now
  sees your readers' addresses, and the page names two companies instead of one.

Consequence either way: the page cannot be finished with a blank where the name goes.

---

**Q4 — How long do we keep the record of alerts already sent? (blocks V2-12; decide now so
the page is written once)**

To avoid telling someone the same news twice, we keep a row saying "we sent this person
this alert on this date." Nothing in the plan says when those rows are deleted, so as
written they are kept forever — which is a dated history of what each person was told
about.

- **(a) Keep them forever.** Simplest. The honest sentence is "we keep a permanent record of
  every alert we have sent you."
- **(b) Delete them after a set period** (90 days, say). The page can say "we keep it for
  about three months." Small risk: a very delayed re-run could re-send something old.
- **(c) Keep only the most recent one per thing followed.** Smallest record. Slightly more
  code; the same duplicate protection in practice.

Same question, smaller: **how long should a signup-verification or password-reset link stay
valid?** (a) 24 hours — standard. (b) 1 hour — safer, more "the link expired" complaints.

---

**Q5 [ANSWERED 2026-10-06 — SD-38: seven tables; the unconfirmed address and its one-time code are disclosed on their own line] — Two of our own documents list different sets of stored tables. Which is right?
(blocks V2-8)**

The specification lists six things we will store. The subscriptions plan lists a seventh (a
short-lived record used to confirm an email address). There is an automatic test whose whole
job is to check that the privacy page's list matches what the database actually holds — so
if the page is written from the wrong list, the test fails, and if we quietly pick one, the
test stops meaning anything.

- **(a) Seven (include the email-confirmation record).** Most likely correct — confirming an
  email address genuinely needs somewhere to keep the code. The page lists it and says it is
  deleted once used.
- **(b) Six, and fold email confirmation into an existing record.** Shorter list on the page;
  a little more care in the code.

We do not think a builder should pick this one quietly, which is why it is here.

---

**Q6 — The "warrant canary". Retire the idea, or reshape it? (human task H19; needed for the
threat-model page, not for V2-8)**

The old idea was a notice saying "we could not hand your data over even if ordered to,
because we hold nothing." Once accounts exist that is no longer true. No such notice was
ever published, so retiring it costs nothing visible.

- **(a) Retire it.** Nothing to maintain; nothing to get wrong.
- **(b) Reshape it** to "we have received no legal demand as of {date}". It only means
  something if you keep the date current by hand, and an unmaintained one that goes stale
  reads as a signal you did not intend.
- **(c) Decide later.** Fine — the threat-model page can ship without it; nothing else waits.

---

## 6. Recommendation

**V2-7 is partly writable today and genuinely blocked on the rest.** The fifteen
`VERIFIED TODAY` claims (thirteen of them in §4a) can be written now from facts in the code,
with one exception
that is a wording choice rather than a fact: **Q1**, how to describe Cloudflare. That single
answer unblocks a complete, accurate, today-true `/privacy` page — which is worth shipping
on its own, because the page currently carries a claim about legal demands that is already
wrong (C8) and the bill pages carry one you have already ruled impossible (Q2).

The forward-looking half of the page — the part the blocking gate actually exists for — is
**blocked on Q3 (the email company's name), Q5 (which list of stored tables is canonical),
and Q4 (how long the alert-sent record is kept)**. — **Q3 answered by SD-36 and Q5 by
SD-38; the page shipped 2026-10-06 (D102). Only Q4 remains, and it blocks no page: the
site states what is held, never how long.** Q3 and Q5 block V2-8 specifically: the
page cannot name a provider that has not been chosen, and the V2-7 accuracy test compares
the page's table list against the database schema, so writing the page from the wrong list
would either fail the test or hollow it out. Q4 blocks V2-12 but should be answered in the
same sitting so the page is written once rather than twice. Q6 (the canary) blocks only the
threat-model page and can be answered last.

Two process notes. First, the threat-model page is V2-7 **task 2** and is deliberately not
drafted here; it restates the same facts at more length — what a legal demand can yield, and
what mitigations remain — and it needs Q6 before it can be finished. Second, the honest
version of several sentences is unflattering and has been left that way on purpose: the host
sees your readers' requests; filter and comparison choices ride in shareable web addresses;
and once accounts exist, the operator can read what every account follows and a court can
compel it. The gate exists so those sentences are accurate, not comfortable. How to phrase
them is yours to decide.
