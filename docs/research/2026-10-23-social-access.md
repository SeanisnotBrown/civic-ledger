# Social accounts: can we read them? (Phase 3 task 2(d))

Research only. All sources were read on 2026-10-23 unless a line says otherwise. Nothing was signed up for. No keys were requested.

## Summary

We can only read members' official posts on two platforms without paying or getting approval. **Bluesky** has a free public API that needs no account. Its catch is that no official list of members' Bluesky handles exists: the congress-legislators file lists none. **YouTube** has a free API that needs a Google API key. It gives video titles and descriptions only. It does not give what was said in the video, and its terms say stored data must be refreshed or deleted every 30 days. **X** can be read now, for about $5 per 1,000 posts, once the owner opens a paid developer account. **Facebook, Instagram and Threads** can only be read after Meta checks the business and reviews the app. We can't know the outcome or how long that takes.

A second problem applies whether or not we get API access. Our rules say every statement must have a working Internet Archive copy. In one sample capture each, the archived **X and Facebook** pages held no post text: we got a JavaScript shell and a "browser not supported" page. The **Instagram** captures were all redirects (301/302; we did not check where they lead). **YouTube and Bluesky** captures did hold the text. The **Threads** sample had no text in the parts we checked (title and preview tags), so that result is unclear.

| Platform | Official read API? | Cost | Key blocker | Verdict |
|---|---|---|---|---|
| Bluesky | Yes: `app.bsky.feed.getAuthorFeed`, no login | Free | No official handle list (0 entries in congress-legislators) | Feasible now, once someone supplies verified handles |
| YouTube | Yes: YouTube Data API v3 | Free (10,000 units/day) | Titles and descriptions only, no speech; 30-day refresh-or-delete rule | Feasible with owner signup (free API key) |
| X (Twitter) | Yes: X API v2 user timeline | Pay-per-use: $0.005 per post read | Cost; delete-when-deleted terms; archived X pages had no post text | Feasible with owner signup + cost (archive rule likely unmet) |
| Facebook | Yes: Page Public Content Access (Graph API) | Not priced (no fee found) | Meta Business Verification + App Review; archived FB page had no post text | Feasible with owner signup, but approval is uncertain (archive rule likely unmet) |
| Instagram | Partly: `business_discovery` (Business/Creator accounts only) | Not priced (no fee found) | Meta Business Verification + App Review; owner needs their own IG professional account; archived profile redirected to login | Feasible with owner signup, but approval is uncertain (archive rule likely unmet) |
| Threads | Yes: Profile Discovery `profile_posts` | Not priced (no fee found) | Without Meta approval it reads only Meta's own accounts; not in congress-legislators | Feasible with owner signup, but approval is uncertain |

## The account list (congress-legislators)

- The repo has no copy. `data/raw/legislators/` holds `legislators-current.yaml` and the committee files, and no code mentions "social-media". We read the upstream file once: https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-social-media.yaml (HTTP 200, 105 KB). We did not save it to the repo.
- The file's header says it lists only **official** accounts: "taxpayer-funded accounts, and not campaign or personal accounts". The maintainers check accounts against the member's .gov site and sometimes phone the office. That is the kind of account task 2(d) wants.
- Fields in the file: `twitter`, `twitter_id`, `facebook`, `instagram`, `instagram_id`, `youtube`, `youtube_id`, `mastodon`. There is **no `bluesky` and no `threads` field** (zero matches in the file).
- Counts against our roster snapshot (`legislators-current.yaml`, fetched 2026-10-09, 539 members). 518 members have an entry:

| Field | All current members (of 539) | Pilot sample (of 40) |
|---|---|---|
| any entry | 518 | 39 |
| twitter | 505 | 36 |
| facebook | 489 | 37 |
| instagram | 407 | 31 |
| youtube or youtube_id | 317 (254 handle, 227 channel id) | 27 (19 handle, 22 channel id) |
| mastodon | 13 | 0 |
| bluesky / threads | 0 | 0 |

- How current: the latest commits to the file are 2026-08-19 ("Fix Tuberville's Facebook handle"), 2026-07-12, 2026-04-22, 2026-04-15 and 2026-04-14 (GitHub commits API for that path). It is being maintained, at least when members leave or handles break.

## X (Twitter)

1. **API.** The X API v2 user Post timeline, `GET /2/users/:id/tweets`, reads any public account by user ID. The file above already has `twitter_id` for 30 of the 40 pilot members. It returns only the "3,200 most recent" posts, or "800 most recent" with replies excluded (https://docs.x.com/x-api/posts/timelines/integrate). A member who posts often may have more than 3,200 posts since 2023-01-03, so the timeline alone may not reach back that far. Full-archive search (`/2/tweets/search/all`) exists, but the pricing page doesn't mention it, so we couldn't confirm it is included in pay-per-use.
2. **Terms.**
   - Showing excerpts on our own site is allowed: you may "Copy a reasonable amount of and display the X Content on and through your Services to Users". Source: Developer Agreement, last updated 2026-04-27, https://docs.x.com/developer-terms/agreement.
   - Stored posts must track X. "If you store X Content offline, you must keep it up to date with the current state of that content on X." And: "If displayed content ceases to be available through the X API, then you must remove it from your service" within 24 hours of a request (https://docs.x.com/developer-terms/policy, no date shown). This means a member deleting a post would oblige us to drop it.
   - Sharing a dataset: if we pass X content to third parties, "you may only distribute Post IDs" (same policy page).
   - Unclear point: Agreement XIV.B bars, unless X approves in writing, "targeting, segmenting, or profiling individuals based on sensitive personal information", and that list includes "political affiliation or beliefs". Comparing an official's public words with their public votes may or may not count as this. Only the owner, or a lawyer, can decide that.
   - Agreement XIV.C restricts making content available to "Government End User[s]". We are not a government, so that clause probably doesn't apply.
3. **Cost and limits.** "The X API uses pay-per-usage pricing. No subscriptions." Post read: **$0.005 per post returned**. User lookup: $0.010. The same post read twice in one UTC day is charged once ("soft guarantee"). There is a cap of "3 million Post reads per monthly billing cycle" (https://docs.x.com/x-api/getting-started/pricing). Some third-party write-ups say the cap is 2 million; we went with X's own page. Rate limit for the timeline: 10,000 requests per 15 minutes per app (https://docs.x.com/x-api/fundamentals/rate-limits).
   - Rough cost, from our own assumptions rather than a measurement. The ceiling for a one-time backfill is 36 pilot members × 3,200 posts × $0.005 = **about $576**. The real figure is lower if members posted less. Keeping stored posts in sync with deletions means reading them again, which costs extra.
4. **Access.** Create a developer account at console.x.com, accept the Developer Agreement, describe the use, and create an app (https://docs.x.com/x-api/getting-started/getting-access). That page describes no review wait. Credits are bought upfront with a saved card, with "No contracts, subscriptions, or minimum spend" (pricing page).
5. **Wayback.** Captures of member post URLs exist. For example, CDX shows HTTP 200 captures of `x.com/SenToddYoung/status/...` from 2025-07. But the one capture we opened was the "JavaScript is not available" / "Something went wrong" shell, with no post text. Treat X as **not reliably archivable** until a capture of our own is checked.

## Facebook

1. **API.** The Graph API with the **Page Public Content Access** feature lets an app "read public data for Pages for which you lack the pages_read_engagement permission". That includes "public comments and posts". Its allowed use: "Analyze and/or display posts and engagement on Pages." Source: https://developers.facebook.com/docs/features-reference/page-public-content-access.
2. **Terms.** Meta Platform Terms, last updated 2026-02-03 (https://developers.facebook.com/terms/):
   - They require deleting Platform Data when it is no longer needed or when "you stop operating the product or service" (3.d.i).
   - They ban "surveillance" (3.a.iii), discrimination, and eligibility decisions (3.a.i–ii).
   - Sharing with third parties is limited (3.c).
   - We found no clause about political use or publishing.
3. **Cost and limits.** We found no fee on Meta's pages. We did not check the rate limits for this feature, so they are unknown.
4. **Access.** It is "only available with business verification" and "requires successful completion of the App Review process". You "may also need to sign additional contracts" (feature page). "Business Verification is required to get Advanced Access" (https://developers.facebook.com/docs/graph-api/overview/access-levels; that page's dated note is from 2023, so it may be out of date). We found no published approval time.
   - **Meta Content Library** is an alternative for researchers. Applications go through ICPSR, are open to academic institutions and non-profits whose core purpose is research, and are free. That comes from a search summary of https://developers.facebook.com/docs/content-library-and-api/support/faqs and transparency.meta.com; we did not read those pages directly. A public website that names politicians is probably not that kind of research. Unconfirmed.
5. **Wayback.** A 2026-05-08 capture of a @SenatorToddYoung post (HTTP 200) was Facebook's "browser not supported" page ("Deze browser wordt niet ondersteund"), with no post text. Treat as **not reliably archivable**.

## Instagram

1. **API.** Instagram Graph API **`business_discovery`** "Returns data about another Instagram Business or Creator IG User". Its `/media` edge returns their posts (https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/business_discovery). The request must come from our own Instagram Business or Creator account. It needs the `instagram_basic`, `instagram_manage_insights` and `pages_read_engagement` permissions. Personal accounts are not mentioned, so they probably can't be read. We don't know how many members' accounts are Business or Creator accounts.
2. **Terms.** The same Meta Platform Terms as Facebook apply.
3. **Cost and limits.** We found no fee. The page gives no rate limit or count of posts returned, so both are unknown.
4. **Access.** The owner needs an Instagram professional account and a linked Facebook Page. Reading accounts outside our app needs Advanced Access, which means App Review and Business Verification (access-levels page above).
5. **Wayback.** CDX shows captures of `instagram.com/sentoddyoung/` from 2025, all 301/302 redirects. Instagram usually sends logged-out visitors to its login page. **Probably not archivable**; we could not check a capture of a single post because the CDX service was offline when we tried.

## YouTube

1. **API.** YouTube Data API v3. List a channel's uploads with `playlistItems.list` and get details with `videos.list`. The file above has a channel for 27 of the 40 pilot members. What we get is the **title and description only**. Downloading captions "requires the user to have permission to edit the video" (https://developers.google.com/youtube/v3/docs/captions/download). Copying the video or audio is banned without written approval (III.E.1.a, below).
2. **Terms.** YouTube API Services Developer Policies, last updated 2026-10-15 (https://developers.google.com/youtube/terms/developer-policies):
   - Data read without a user's login (our case) may be kept only temporarily, and for no more than 30 calendar days. After that it must be deleted or refreshed (III.E.4.c–d), and kept "consistent with the current data" (III.E.4.e).
   - We must "make clear to the viewer that YouTube is the source" (III.F.2.a) and "display a link to YouTube's Terms of Service" (III.A.1).
   - We found no rule about political use.
3. **Cost and limits.** Free. The default is "10,000 units per day" (https://developers.google.com/youtube/v3/getting-started, updated 2026-10-15). `playlistItems.list`, `videos.list` and `channels.list` each cost 1 unit. `search.list` costs 1 unit, but only 100 calls a day are allowed. `captions.list` costs 50 units (https://developers.google.com/youtube/v3/determine_quota_cost, updated 2026-10-15). The pilot would use a small fraction of the daily quota.
4. **Access.** A Google account, a Google Cloud project, and an API key. We found no review step for basic read access.
5. **Wayback.** A sample `youtube.com/watch?v=` capture (2025-01-01) held the video title in its page metadata. **Archivable** for title and description.

## Bluesky

1. **API.** `app.bsky.feed.getAuthorFeed`, called at `public.api.bsky.app` with no login. Parameters are `actor`, `limit` (up to 100), `cursor` and `filter`. Sources: https://docs.bsky.app/docs/api/app-bsky-feed-get-author-feed (now redirects to https://endpoints.bsky.app/) and a search summary of the same page. We checked it with one request, `getAuthorFeed?actor=bsky.app&limit=1`, which returned HTTP 200 with a post.
2. **Terms.**
   - Developer Guidelines (https://bsky.network/docs/developer-guidelines/, no date shown): "All services must have a method for deleting content a user has requested to be deleted." They also ban "automated or bulk interactions". Nothing in them limits reading public posts.
   - Bluesky Terms of Service (https://bsky.social/about/support/tos), effective 14 Aug 2025, which is more than 12 months ago, so possibly out of date even though it is the version served today: nothing about API use or scraping. "the terms and conditions of that Developer Application will govern your experience" for third-party apps.
3. **Cost and limits.** Free. For the public read service: "These API services have generous rate-limits. Please contact us if you encounter rate-limiting." No number is given. Logged-in requests to Bluesky's own servers: "3000 per 5 minutes" per IP (https://bsky.network/docs/rate-limits).
4. **Access.** None. The real blocker is **which accounts are official**. congress-legislators lists no Bluesky handles, so someone has to make and check that list, the same way the press-page URLs are owner-maintained.
5. **Wayback.** A 2025-08-14 capture of a `bsky.app/profile/.../post/...` page (HTTP 200) held the post text in its `og:description` tag. **Archivable.**

## Threads

1. **API.** The Threads Profile Discovery endpoint `GET /profile_posts?username=...` returns a public profile's posts. It needs the `threads_basic` and `threads_profile_discovery` permissions. "Only returns public profiles with at least 100 followers" (https://developers.facebook.com/documentation/threads/retrieve-and-discover-posts/retrieve-posts).
2. **Terms.** The Meta Platform Terms apply, as for Facebook.
3. **Cost and limits.** We found no fee. "A user can send a maximum of 1,000 requests within a rolling 24-hour period" (same page).
4. **Access.** Without approval, "only posts from some of the official Meta accounts can be retrieved" (@meta, @threads, @instagram, @facebook; same page). Reading members' accounts would need Advanced Access, which means App Review and Business Verification (access-levels page). The documents did not state this step for this permission in so many words. congress-legislators lists no Threads handles.
5. **Wayback.** We opened one archived Threads post (`threads.net/@zuck/post/C-3yWvVyPVv`, 2024-11-20). Its title was just "Threads" and it had no preview text. Unclear: the page shown in the archive viewer might still show the post.

## Things the owner must decide (not technical)

- **Deleted posts.** The terms for X, YouTube, Bluesky and Meta all expect us to drop or refresh content that the author deletes or changes. The site exists to hold officials to what they said. Should a statement the member later deleted stay on the site, for example by citing the Internet Archive copy instead of our API copy? That is an editorial and legal question, and these findings don't settle it.
- **The X "profiling" clause** (XIV.B, above). Decide whether to ask X in writing or get advice before relying on X.
- **The archive rule.** As tested, X, Facebook and Instagram fail the "every statement has a working archive copy" rule. Options: drop those platforms, or accept a different kind of proof. Accepting different proof would change a ratified rule.

## What the owner would have to do

- **Bluesky:** supply or approve a list of members' official Bluesky handles. No signup, no cost. *Consequence: Bluesky collection can start as soon as the list exists.*
- **YouTube:** create a free Google Cloud project and API key, and put it in `.env`. *Consequence: titles and descriptions only, re-checked every 30 days; no video speech.*
- **X:** open a developer account at console.x.com, add a card and buy credits. That is $0.005 per post; the pilot backfill is up to about $576 at the 3,200-post cap, plus ongoing reads. *Consequence: posts readable, but archive copies likely lack the text, and deletions must be honoured.*
- **Facebook / Instagram / Threads:** create a Meta developer app, complete Meta Business Verification (which needs a registered business), and apply through App Review. Instagram also needs an Instagram professional account. No fee was found. *Consequence: a wait of unknown length with an unknown outcome, and even if approved, archive copies likely lack the text.*

**Recommended order:** (1) Bluesky, (2) YouTube, which are free and archivable. (3) X only after the owner decides on the archive rule and the deleted-post question, and approves the spend. (4) Meta platforms last, or record them as "not available" in STATUS.md and ship without them, as task 2(d) allows.
