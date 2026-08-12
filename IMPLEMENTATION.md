# IMPLEMENTATION.md — Civic Alignment Platform
### Complete build specification. Consumed by Claude Code. No follow-up conversation exists.

---

## §0 — Ground rules for the builder

These override any instinct to ask, pause, or simplify.

1. **Never ask the owner a question.** Every ambiguity in this document has a resolution rule: (a) if a Decision in §2 covers it, apply it; (b) if a runtime check can resolve it, run the check and follow the specified branch; (c) otherwise pick the option that best serves §0.4 and record it in `docs/decisions.md` as a dated one-line ADR. Continue building.
2. **Human-only tasks block by design.** When you hit one (§1), do everything possible around it: build the code path, stub the credential from `.env.example`, write the exact instruction for the human into `docs/HUMAN-TASKS.md` status table, and move to the next increment that isn't blocked. Increments are ordered so at least one is always unblocked.
3. **Every increment ends with its acceptance criteria demonstrably passing** — a command the owner (or CI) can run. Do not start increment N+1 with increment N's criteria failing, except where an increment is explicitly marked as parallelizable.
4. **The four load-bearing values, in priority order when they conflict:**
   1. Never publish something false or falsely framed (vote_class, sourcing, archive links)
   2. Never render partisan lean (symmetry, banned words, no spectrum, no Tier 3)
   3. Never collect what a subpoena could use (privacy architecture)
   4. Ship partial value early (a live correct MVP beats a complete unbuilt v1)
5. **No LLM output anywhere in the publishing path.** You are an LLM. You may write code, tests, UI copy templates, and documentation. You may NOT generate, summarize, classify, or paraphrase any political content that publishes as fact: no bill summaries, no vote characterizations, no statement scoring, no issue tagging beyond official government-assigned terms. Where this spec says "curated" or "manual," the data comes from the owner via the curation tools — you build the tool, you never fill it with political content. UI chrome text ("Data last updated", "No explanation on record") is yours to write; it is not political content.
6. **Windows 11 is the dev environment.** All scripts must run under PowerShell (`uv run`, `npm run` — no bash-isms in dev tooling). CI runs Ubuntu; scripts invoked by CI live in `pyproject.toml` / `package.json` entries so both platforms call the same commands.
7. **Raw API responses are cached to disk before parsing** (§6.2). Never re-fetch what's cached during development. Never hammer a government API.

---

## §1 — HUMAN-ONLY TASKS (complete checklist)

The owner should be able to knock these out in one or two sittings. Each is also flagged inline at the increment it blocks. Build order is arranged so that H1–H4 unblock everything through MVP launch; the rest can trail.

| # | Task | Blocks | Instructions |
|---|---|---|---|
| **H1** | Register Congress.gov / api.data.gov API key | INC-1 | https://api.congress.gov/sign-up/ → key arrives by email → put in `.env` as `CONGRESS_API_KEY` and in GitHub repo secret of same name |
| **H2** | Register LegiScan API key | INC-1 (state branch verdict only) | https://legiscan.com/legiscan → free tier → `.env` / secret `LEGISCAN_API_KEY` |
| **H3** | Create public GitHub repo + add secrets | INC-0 | Repo name owner's choice (suggest `civic-ledger`). Secrets: `CONGRESS_API_KEY`, `LEGISCAN_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `IA_S3_ACCESS`, `IA_S3_SECRET` |
| **H4** | Cloudflare account + Pages project + API token | INC-9 (deploy) | Create Pages project connected to the repo, root dir `site/`, build command `npm run build`, output `dist/`. Create API token with Pages+Workers+D1 edit scope → secret `CLOUDFLARE_API_TOKEN`; account ID → `CLOUDFLARE_ACCOUNT_ID` |
| **H5** | Purchase domain with WHOIS privacy | INC-9 | Any registrar with privacy default (Cloudflare Registrar keeps it in one place). Point at the Pages project. **Never** point any record at the homelab. |
| **H6** | archive.org account + S3-like API keys | INC-11 | https://archive.org/account/s3.php → `IA_S3_ACCESS` / `IA_S3_SECRET`. Enables authenticated Wayback Save-Page-Now (higher rate limits, capture status API). Until present, curation tool falls back to unauthenticated SPN with a warning. |
| **H7** | FEC API key *(optional increment INC-10b)* | INC-10b | Same api.data.gov key usually works; else register at https://api.open.fec.gov → `FEC_API_KEY` |
| **H8** | Statement watchlist + curation (recurring) | INC-11 content | Use the local curation tool (`uv run curate`). Owner selects, enters, and approves every statement. Symmetry CI will tell you when depth is unbalanced. |
| **H9** | Absence-explanation approvals (recurring) | INC-6 content | Ingest queues *candidate* personal-explanation excerpts from the Congressional Record; owner approves/rejects each in the curation tool. Nothing publishes unapproved. |
| **H10** | Candidate list + specificity scoring (recurring) | INC-13 content | Owner curates declared-candidate YAML from MS SoS qualifying filings (helper script assists) and manually scores every statement on the rubric. Double-score the 10% sample. |
| **H11** | Quiz question bank review (one-time + on change) | INC-14 content | Bank ships from published instruments (ANES/Pew/CCES) via the sourcing workflow; owner reviews every item, and recruits an external reviewer who disagrees with him for any original-wording items (surveillance/ALPR section per brief). |
| **H12** | Warrant canary signing (recurring, monthly) | INC-16 | Update `site/src/content/canary.md` date monthly. CI warns at 35 days stale, fails the *scheduled* build at 45 (never blocks a correction deploy). |
| **H13** | Byline decision (pre-launch, non-blocking) | — | Site builds unattributed per brief §10. Flip `SITE_ATTRIBUTION` in `site/config.ts` before launch if desired. |

---

## §2 — Decisions made in this spec

Ambiguities in the brief/roadmap, resolved. Do not re-open. One-line rationales as required by the handoff contract.

| # | Decision | Rationale |
|---|---|---|
| D1 | **Symmetry is defined per-member, party-mean as secondary** (§6.5) | MS delegation is 5R/1D; party-total equality is either unpassable or forces 5× depth on one member. Per-member equal depth is what "no hostile reader can point at it" actually requires. |
| D2 | **One server component exists: a counter-only aggregates Worker** (§10.2) | Brief Goal 5 + "your own coalition" require a write path; counters-only with IP discard preserves "we cannot hand over what we never collected" literally. |
| D3 | Stack: Python 3.12 + uv + pydantic v2 + httpx → SQLite → JSON in-repo → Astro 5 + Tailwind + Preact islands → Cloudflare Pages; one Worker + D1 for aggregates | Matches owner's roadmap and skills; static-first satisfies privacy, cost, and abandonment-resilience constraints. |
| D4 | Monorepo, single public repo: `ingest/` + `data/` + `site/` + `worker/` | "Every fact has a public commit history" is simplest with data and code in one diffable place. |
| D5 | Federal depth: 119th (current) + 118th Congress | Brief §10 default; older House data via clerk.house.gov is specced (INC-3) but not scheduled. |
| D6 | House votes: Congress.gov `house-vote` endpoints primary, clerk.house.gov XML fallback/verification; Senate: senate.gov LIS XML | Official-source-first; clerk XML doubles as an integrity cross-check. |
| D7 | `vote_class` from an explicit rules table over the official question/action strings; unmapped → `other` + logged, surfaced in quality report | Total function, no LLM, no silent misclassification; `other` is a displayed label, satisfying principle 5.7. |
| D8 | Absence stated-reasons are **curated with tool assistance**, never auto-published | Personal-explanation extraction from CREC text is fuzzy; auto-attribution of a false reason is worse than a queue. Satisfies 5.6 strictly. |
| D9 | Pairing key: bill identifier (`hr2-119` form) only at launch; formal short titles matchable **only** via an explicit per-bill allowlist the owner populates | Brief §10 permits formal short title; making it opt-in allowlist keeps "no fuzzy matching" mechanically true. |
| D10 | Ballot builder: Census Geocoder (address → CD/SLDU/SLDL) + owner-curated race file from SoS filings | Google Civic *elections* API was retired (2025); Census geocoder is free, keyless, and district lookup + curated races covers federal+state scope. Verified at runtime in INC-21. |
| D11 | Drift reminders: downloadable `.ics` with quarterly RRULE linking to a bare `/retake` URL — no result code in the URL | Zero contact info collected; embedding a result code in a calendar URL would leak a political profile to the user's calendar provider. |
| D12 | Zero-knowledge sync accounts: **deferred post-v1**, specced as INC-22 stub | Brief §8 requires accounts only "where persistence is offered"; localStorage + portable code delivers full v1 functionality with strictly less liability. |
| D13 | Quiz result portability: `CAP1.`-prefixed base64url(deflate(JSON)), bank version embedded | Versioned, offline-reproducible, survives bank edits (old codes render against the bank version they carry). |
| D14 | Bill diff (INC-19): operate on USLM XML structure from govinfo, diff at section/paragraph node level, renumbering-aware | Brief 6.2 explicitly rules out line diffs; USLM is the only structure that supports attribution mapping. |
| D15 | CBO cost estimates via the `cboCostEstimates` field on Congress.gov bill detail | Official link-through; no scraping CBO's site. |
| D16 | FEC funding metrics moved out of MVP into optional INC-10b | Not in the brief's §6 surfaces or definition-of-done; highest attack-surface Tier 2 metric; nothing downstream depends on it. |
| D17 | Analytics: none at MVP; if ever added, Cloudflare Web Analytics (cookieless) only, behind a config flag default-off | "Cookieless and non-fingerprinting" is most safely satisfied by absence. |
| D18 | MS state (INC-12) runs the LegiScan verdict in INC-1; both branches fully written; a **defer** verdict does not touch any other increment | Brief §10 requires the build to continue on federal without stopping. |
| D19 | **Grades are computed in the reader's browser from visible, reader-adjustable weights; the build/publish path never computes or publishes a composite score** (§5 Tier discipline, INC-15) | "No thumb on the scale" stays literally true only if the site ships facts, not a chosen score; transparent adjustable weights deliver the grading/ranking experience while the weighting opinion stays the reader's. "Objective grading" is unachievable — the weights are opinions. |
| D20 | **Donations and votes render as an adjacency timeline, never a computed "cost per vote" / purchased-vote figure** (INC-10b) | A per-vote price asserts unprovable purchased intent (defamation shape); a side-by-side donation/vote sequence shows the pattern under the site's existing "adjacency, not conclusion" framing and asserts no motive. |

---

## §3 — Architecture & stack

```
┌─ SOURCES ────────────────────────────────────────────────────────┐
│ api.congress.gov v3   senate.gov LIS XML   clerk.house.gov XML  │
│ unitedstates/congress-legislators          govinfo (bill USLM)  │
│ LegiScan bulk (MS)    Census Geocoder      archive.org SPN2     │
└──────────────┬───────────────────────────────────────────────────┘
               ▼
  ingest/  (Python 3.12, uv, httpx, pydantic v2, tenacity)
    raw cache (data/raw/, gitignored) → validate → SQLite (build.db,
    gitignored) → deterministic JSON export → data/  (committed)
               ▼
  Curation tools (local Flask, never deployed):
    statements / absence approvals / candidates → YAML in data/ + SPN2 capture
               ▼
  site/  (Astro 5 static build, Tailwind, Preact islands for quiz/drift)
    reads data/**/*.json|yaml at build time only
               ▼
  Cloudflare Pages  (public, privacy-registered domain)

  worker/ (the ONLY server code): POST /v1/agg → Turnstile verify →
    validate → increment D1 counters → 204.  No rows. No IP writes.
    Weekly GH Action exports counters ≥ K_ANON into data/aggregates/.
```

**Version pins** (exact, so the build is reproducible): Python 3.12.x, uv latest, pydantic ^2.7, httpx ^0.27, tenacity ^9, PyYAML ^6, Flask ^3 (curation only), pytest ^8, ruff latest. Node 22 LTS, Astro ^5, @astrojs/preact, preact ^10, tailwindcss ^4, fflate ^0.8 (deflate for portable codes), wrangler ^4. Pin concrete versions in lockfiles at INC-0 and record them in `docs/decisions.md`.

**Hard boundaries the stack must never violate** (from brief §7): no homelab hosting or DNS records; quiz scoring 100% client-side; all published data diffable in the public repo; no LLM in the publishing path (enforced in CI, §6.6); symmetry checks capable of failing the build; no statement publishes without a working archive URL (enforced at write time in the curation tool AND at build time); K_ANON threshold enforced in code before any aggregate renders; mobile-first; entire client open source (it's the public repo).

---

## §4 — Repository layout

```
civic-ledger/
├── pyproject.toml            # uv-managed; console entrypoints: ingest, curate, export, checks
├── .env.example              # every credential named, with the H-task that supplies it
├── ingest/
│   ├── config.py             # all constants incl. K_ANON=50, congresses=[118,119], symmetry thresholds
│   ├── models.py             # pydantic schemas (§5)
│   ├── cache.py              # disk cache keyed by sha256(url+params)
│   ├── sources/
│   │   ├── congress_gov.py   # members, bills, house votes, CREC search
│   │   ├── senate_xml.py
│   │   ├── clerk_house.py
│   │   ├── legislators.py    # unitedstates/congress-legislators
│   │   ├── legiscan.py       # built only if INC-1 verdict = GO
│   │   └── govinfo.py        # bill text versions (USLM) for diff viewer
│   ├── classify.py           # vote_class rules table (§A1)
│   ├── metrics.py            # Tier 2 formulas — each function docstring IS the methodology text
│   ├── export.py             # SQLite → deterministic sorted JSON
│   └── checks/
│       ├── symmetry.py       # §6.5 — exit nonzero on violation
│       ├── banned_words.py   # §6.4 — scans data/ + site/src + site/dist
│       ├── no_llm.py         # §6.6
│       ├── archive_links.py  # every statement has archive_url; HEAD-check 200/302
│       └── integrity.py      # cross-check sample vs clerk/senate XML; export determinism
├── curation/                 # local-only Flask app (statements, absences, candidates)
├── data/                     # THE PUBLISHED DATASET — everything here is public record
│   ├── members/  votes/  bills/  absences/
│   ├── statements/           # YAML, one file per statement
│   ├── candidates/
│   ├── quiz/bank/            # versioned YAML question bank + CHANGELOG.md
│   ├── challenges/           # challenge inventory YAML
│   ├── elections/            # curated race files for ballot builder
│   ├── aggregates/           # weekly k-anonymous counter exports
│   └── quality/              # unmapped_questions.json, quarantine/, coverage-gaps.md
├── site/                     # Astro
│   ├── src/pages/            # index, m/[member], v/[roll], b/[bill], quiz, ballot, methods,
│   │                         #   privacy, canary, corrections, glossary, feed, diff/[bill]
│   ├── src/islands/          # quiz.tsx, drift.tsx, ballot.tsx, sharecard.tsx (Preact)
│   ├── src/lib/scoring.ts    # pure functions, golden-vector tested
│   └── src/content/          # methodology, threat model, canary, pairing-rules, glossary
├── worker/                   # wrangler project: agg counter Worker + D1 schema
├── docs/                     # HUMAN-TASKS.md status, decisions.md (ADRs), rubric.md, correction-process.md
└── .github/workflows/        # ci.yml (PR checks), nightly.yml (ingest+build+deploy),
                              #   archive-recapture.yml (weekly), agg-export.yml (weekly)
```

`data/raw/` and `build.db` are gitignored: raw cache is a dev convenience; the *published* dataset is the exported JSON/YAML, which is what must be diffable.

---

## §5 — Data schemas (pydantic; JSON export mirrors field names exactly)

All IDs are strings. All dates ISO-8601. Every published record carries `source_url`. Export is deterministic: sorted keys, sorted lists by stated sort key, LF endings, 2-space indent — so nightly diffs show only real changes.

```python
VoteClass = Literal["passage", "amendment", "procedural", "nomination",
                    "veto_override", "other"]

class Member(BaseModel):
    id: str                     # bioguide id — canonical key everywhere
    ids: dict[str, str]         # crosswalk: govtrack, fec, opensecrets, legiscan (from congress-legislators)
    name: str
    party: Literal["D", "R", "I"]
    state: str; district: int | None   # None = Senate
    chamber: Literal["house", "senate"]
    serving: bool
    terms: list[Term]           # start, end, party, chamber — party switches preserved

class Bill(BaseModel):
    id: str                     # "hr2-119", "s1234-118" (type+number+congress, lowercase)
    congress: int; type: str; number: int
    title_official: str         # displayed with an "official short title — may be promotional" affordance
    policy_area: str | None     # government-assigned ONLY (D5/brief §10 — never invent taxonomy)
    subjects: list[str]         # legislative subject terms, government-assigned
    sponsor_id: str | None
    cosponsor_ids: list[str]
    latest_action: str; latest_action_date: str
    cbo_estimates: list[CboRef]     # url + title + date, link-through only
    source_url: str

class RollCall(BaseModel):
    id: str                     # "h-119-1-0234" chamber-congress-session-roll
    chamber: Literal["house", "senate"]
    congress: int; session: int; number: int
    date: str
    question: str               # official question text, verbatim
    vote_class: VoteClass       # REQUIRED — classifier §A1; never null
    vote_class_rule: str        # id of the rule that fired (auditability)
    bill_id: str | None
    result: str
    totals: dict[str, int]      # yea/nay/present/not_voting
    source_url: str

class MemberVote(BaseModel):
    member_id: str; rollcall_id: str
    position: Literal["yea", "nay", "present", "not_voting"]

class Absence(BaseModel):
    member_id: str; rollcall_id: str
    stated_reason: str | None       # ONLY owner-approved, verbatim quote from CREC
    stated_reason_source: str | None  # CREC page URL — required when reason present
    declared_position: Literal["yea", "nay"] | None  # "had I been present" — verbatim source only
    # stated_reason is None → UI renders exactly: "No explanation on record."

class Statement(BaseModel):
    id: str
    member_id: str
    text: str                   # verbatim; no paraphrase field exists on purpose
    date: str; venue: str
    source_url: str
    archive_url: str            # REQUIRED — curation tool refuses to save without a verified capture
    archive_captured_at: str
    named_measures: list[str]   # bill ids; ONLY basis for pairing (D9)
    specificity_level: Literal[0, 1, 2, 3] | None   # owner-assigned; None = unscored
    curator_note: str | None    # internal, never rendered

class Candidate(BaseModel):
    id: str; name: str; party: str
    office: str; election_year: int
    incumbent_member_id: str | None
    filing_source_url: str          # SoS qualifying filing
    issues_claimed: list[str]
    statements: list[Statement]     # same schema, same archive rule
    page_captures: list[PageCapture]  # url, captured_at, archive_url, text_sha256
    # recurring recapture (INC-13) appends here; diffs derived from text hashes

class QuizQuestion(BaseModel):
    id: str; bank_version: str
    dimension: str              # maps to policy_area terms via data/quiz/dimension_map.yaml
    ladder: Literal["position", "reason", "tradeoff", "calibration"]
    text: str
    options: list[QuizOption]   # each option: id, text, provenance
    provenance: Provenance      # instrument ("ANES 2024 V241234" | "Pew ..." | "original"),
                                # source_url; "original" flag MUST surface in UI (brief §10)
    # "I don't know" is injected as a first-class option at render on every position/reason item
```

**Tier discipline, structurally:** Tier 1 = the records above. Tier 2 = outputs of `ingest/metrics.py` only; every function's docstring is extracted verbatim into the methodology page at build time, so a formula cannot publish without its documentation. **Tier 3 has no schema; nothing in the codebase may compute a cross-metric composite about an official** — `checks/no_llm.py`'s sibling assertion in `checks/integrity.py` greps `metrics.py` for any function consuming another metric's output about the same member and fails CI if found. (D19: the *reader's browser* may combine Tier-2 metrics into a grade from visible, reader-adjustable weights — a client-side, zero-network computation like `scoring.ts`; the guard forbids only the *build/publish* path computing or shipping a composite the site chose.)

---

## §6 — Global engineering rules (apply to every increment)

### 6.1 Error handling & failure modes
- **Network:** tenacity retry — 5 attempts, exponential backoff 2s→60s, retry on 429/5xx/timeouts. On final failure: mark that source **stale**, keep last-good data, continue the build. Site truthfully shows per-page "Data last updated"; staleness is visible, never hidden, never fatal.
- **Validation:** a record failing pydantic validation is written to `data/quality/quarantine/` with the error, and skipped. Build continues. CI **fails** only if quarantined records exceed 2% of the run or include any MS-delegation member vote (a covered member's missing vote is a correctness failure, not noise).
- **Rate limits:** honor `Retry-After`; hard client-side ceilings — Congress.gov ≤ 1 req/sec sustained; SPN2 ≤ 1 capture/15s unauthenticated, per archive.org guidance authenticated. All fetches go through `cache.py`; a cached URL is never re-fetched within 20h except vote-detail pages for votes < 7 days old.
- **Nightly job failure:** exit nonzero → GitHub Actions failure notification is the alert channel. No pager, no third-party service. The previous deploy stays live (Pages keeps last successful build).
- **Partial API outage:** each source module is independent; one source down must never block export of the others' data.

### 6.2 Raw cache
`data/raw/{source}/{sha256(url+params)[:16]}.json|xml` + a sidecar `.meta` (url, fetched_at, status). Gitignored. INC-1's samples are the exception: copied into `data/quality/samples/` and committed, because the verdict must be reviewable.

### 6.3 Determinism
`uv run export` twice on the same DB must produce byte-identical output (`checks/integrity.py` verifies in CI). No timestamps inside exported records except real data dates; "generated at" lives in one `data/manifest.json`.

### 6.4 Banned-strings check (CI, blocking)
Case-insensitive scan of `data/**` published fields, `site/src/**`, and built `site/dist/**` for: `hypocrisy`, `hypocrite`, `broke his promise`, `broke her promise`, `broke their promise`, `flip-flop`, `flip flop`, `flipflop`, `contradiction`, `contradicts`, `liar`, `lied about`. List lives in `ingest/checks/banned_words.py` as data; the glossary page is the single allowlisted file **only** for defining procedural terms, and is manually reviewed. A hit anywhere else fails the build. (Brief 5.4 verbatim plus the obvious adjacents.)

### 6.5 Symmetry (CI, blocking) — precise definitions (Decision D1)
Computed by `checks/symmetry.py` from exported data; thresholds in `config.py`:
- **Vote coverage:** every covered member has a `MemberVote` or `Absence` for every eligible roll call of their chamber/congress. Any gap = fail.
- **Statement curation:** once the watchlist median ≥ 5 statements: (a) every watchlist member's count ≥ 60% of the median, and (b) party mean counts within 25% relative difference. Below median 5, checks warn but don't fail (cold-start).
- **Specificity scoring:** % of statements scored must be within 10 points across parties (prevents scoring one side's statements and leaving the other's "unscored").
- **Challenge inventory (INC-17):** for every quiz dimension, the count of challenge items per position-direction must be **exactly equal**. Curated content; exact equality is achievable and required.
- **Candidate coverage:** every declared candidate for a covered race has a page, or the race is listed in `data/quality/coverage-gaps.md`. Silent omission = fail; documented gap = pass.
- Output: `data/quality/symmetry-report.json`, published. The check that would fail also renders the reason, so the public can see what the CI enforces.

### 6.6 No-LLM structural guard (CI, blocking)
`checks/no_llm.py`: (a) dependency lockfiles contain none of: anthropic, openai, google-genai/generativeai, mistralai, cohere, ollama, litellm, langchain\*, llama-index\*; (b) grep of `ingest/ site/ worker/` for `api.anthropic.com|api.openai.com|generativelanguage.googleapis|:11434` fails on hit; (c) `CONTRIBUTING.md` states the policy. This makes the constraint structural per brief 5.10 — an LLM call cannot merge.

### 6.7 UI copy rules (all increments)
- Every vote row: position, date, roll #, **vote_class badge** (always visible, tooltip from the glossary), official question text, bill link, official record link.
- Bill titles render with a superscript ⓘ: "Official short title — titles are written by the bill's drafters." Never used as a description of effect.
- Absences: stated reason verbatim + CREC link, or the exact string "No explanation on record."
- Paired statement/vote: visually adjacent, connected marker, **zero relational language**. The pairing-rules page link sits on every timeline.
- Every page footer: data-last-updated, link to methodology, corrections page, and the repo commit that produced the page (`git rev-parse --short HEAD` injected at build).
- Mobile-first: all layouts designed at 380px, enhanced upward. Lighthouse mobile perf ≥ 90 is an INC-9 acceptance criterion.

---

## §7 — Build increments

Each: **Goal → Tasks → Acceptance (a runnable check) → On failure.** Sequential unless marked ∥ (parallel-safe with the previous).

---

### INC-0 — Repo bootstrap
**Goal:** Tooling skeleton; CI green on empty project.
- uv project + pyproject entrypoints (`ingest`, `export`, `curate`, `checks`); ruff + pytest configured
- Astro scaffold in `site/` with Tailwind, Preact integration, placeholder index
- `.github/workflows/ci.yml`: ruff, pytest, banned-words, no-llm, `astro build` on PR/push
- `.env.example`, `docs/HUMAN-TASKS.md` (status table for H1–H13), `docs/decisions.md`, `CONTRIBUTING.md`
- **Blocked-by:** H3 for pushing; build everything locally regardless.
**Acceptance:** `uv run checks && uv run pytest && (cd site && npm run build)` all pass locally and in CI.
**On failure:** fix before proceeding; nothing else starts on red tooling.

### INC-1 — Source feasibility spike  *(needs H1; H2 for step 4)*
**Goal:** Raw samples on disk from every federal source; written MS-state verdict.
1. Pull member list (Congress.gov `/member?currentMember=true&stateCode=MS`), one House roll call (`/house-vote/119/1/{n}` — if the beta path 404s, fall back to `https://clerk.house.gov/evs/2025/roll{NNN}.xml` and record the deviation in decisions.md), one Senate vote (`https://www.senate.gov/legislative/LIS/roll_call_votes/vote1191/vote_119_1_{NNNNN}.xml` — discover exact filename pattern from the session's `vote_menu` XML first, don't assume), one bill detail with `cboCostEstimates`, one CREC search hit for `"personal explanation"`.
2. Copy each into `data/quality/samples/` with a `SHAPES.md` documenting observed field names. **Parsers in later increments are written against these observed shapes, not against this spec's assumptions.**
3. Pull `legislators-current.yaml` from `unitedstates/congress-legislators`.
4. LegiScan: `getSessionList(MS)` → `getDataset` for the current session → **verdict test:** do `roll_call` records contain per-person vote positions with resolvable `people_id`s? Sample 5 bills; compare against the corresponding chamber Journal PDF pages (download 2 Journal excerpts for the comparison; a 5-of-5 match on the sampled votes = GO).
5. Write `data/quality/ms-state-verdict.md`: **GO** (LegiScan carries positions; INC-12 branch A) or **DEFER** (positions absent/unverifiable; INC-12 branch B activates *only as documentation*, federal build continues untouched — Decision D18). No third option; if ambiguous, verdict is DEFER (correctness outranks scope, §0.4).
**Acceptance:** samples committed; SHAPES.md complete; verdict file exists with an unambiguous GO/DEFER and the evidence table.
**On failure:** any single federal source unreachable → note in SHAPES.md, continue; the source's ingest increment carries the risk forward. LegiScan unreachable → DEFER.

### INC-2 — Canonical members & schema layer
**Goal:** `models.py` complete; six MS members exported.
- Implement §5 schemas; ingest `congress-legislators` → `Member` records with full ID crosswalk; filter covered set = MS delegation, congresses per `config.py`
- Export `data/members/*.json`
**Acceptance:** `uv run pytest tests/test_models.py` (validation edge cases incl. party switch in `terms`); 6 member files exported; determinism check passes.

### INC-3 — House vote ingest
**Goal:** Every House roll call, 118th–119th, with MS member positions.
- Enumerate roll calls per session; fetch detail; parse to `RollCall` + `MemberVote` per observed SHAPES; `not_voting` also creates an `Absence` stub (reason None)
- clerk.house.gov XML module: used (a) as fallback for anything the API lacks pre-118th *if ever scheduled*, and (b) as the integrity cross-check source
- `checks/integrity.py`: sample 10 random roll calls, re-fetch from clerk XML, positions must match exactly
**Acceptance:** count of ingested House roll calls per session matches the official session total (from the clerk's index page for that year); 10-sample cross-check passes; no covered-member gaps (symmetry check, vote coverage rule).
**On failure:** count mismatch → produce `data/quality/house-gaps.md` listing missing roll numbers; fail CI until zero for covered congresses.

### INC-4 — Senate vote ingest  ∥
Same structure against senate.gov LIS XML (`vote_menu_{congress}_{session}.xml` → detail files). Cross-check source: the same XML re-fetched + the printed vote number totals.
**Acceptance:** mirrors INC-3 for the Senate; both MS senators complete.

### INC-5 — vote_class classifier
**Goal:** Total classification per §A1 rules table.
- Implement table; every RollCall gets `vote_class` + `vote_class_rule`; unmapped questions → `other` + append to `data/quality/unmapped_questions.json`
- Special rule R-RULE: H.Res whose bill record shows Rules Committee report → `procedural` (rule adoption), overriding the generic "On Agreeing to the Resolution" ambiguity
**Acceptance:** golden test file `tests/fixtures/questions.yaml` with ≥ 40 real question strings (taken from ingested data) and expected classes — 100% pass; `other` rate ≤ 5% of all roll calls, else extend the table until true.

### INC-6 — Absences & personal explanations  *(content = H9)*
**Goal:** Queue → approve → publish pipeline for stated absence reasons.
- CREC search (Congress.gov `/congressional-record` + query) for `"personal explanation"` and covered member names; extract candidate excerpt + page URL into a **review queue** (`data/quality/absence-queue/`)
- Curation tool view (INC-11's Flask app grows this tab; ship a minimal CLI approver now: `uv run curate absences` — shows excerpt, y/n/edit-verbatim, writes `Absence.stated_reason` + source)
- Auto-match approved explanations to roll calls **only** when the explanation names the roll call or measure; else it attaches at member+date level with the verbatim text
**Acceptance:** ≥ 1 real approved example rendering end-to-end; every `not_voting` position renders either a sourced reason or "No explanation on record."; nothing publishes from the queue without approval (test asserts queue files are excluded from export).

### INC-7 — JSON export contracts
**Goal:** Stable, documented, deterministic public dataset.
- `export.py` complete for members/votes/bills/absences; `data/manifest.json` (counts, congress coverage, generated_at, commit)
- `docs/data-contract.md` documenting every file and field for third-party recomputation (brief 5.2's "recompute and match")
**Acceptance:** double-export byte-identical; JSON Schema files generated from pydantic and committed; a fresh-clone script (`uv run verify-recompute`) recomputes vote totals from MemberVotes and matches RollCall.totals for 100% of roll calls.

### INC-8 — Site MVP
**Goal:** Member index, member detail (vote list w/ class badges), single-vote page, single-bill page. §6.7 copy rules in full.
**Acceptance:** `astro build` succeeds from data alone (no network at build); axe-core CI a11y check passes; 380px layout screenshot test; every rendered claim traces to a `source_url` present in data.

### INC-9 — Automation + deploy → **PUBLIC MVP**  *(needs H4, H5)*
- `nightly.yml`: cron `15 09 * * *` UTC → ingest (incremental: current congress only) → checks → export → commit data diff with message `data: nightly {date}` → Pages deploy (Pages auto-builds on push; Worker deploys via wrangler only when `worker/` changes)
- "Data last updated" per page from manifest; corrections page + `docs/correction-process.md` (corrections = new commits, PR-visible, never force-push — brief 5.12)
- Basic `/privacy` page (full threat model at INC-16)
**Acceptance = the brief's MVP definition of done:** six members complete + auto-updating; procedural classification displayed; missed votes show reason or explicit absence of one; methodology stub live; real domain, mobile-usable (Lighthouse mobile ≥ 90), updates unattended — verified by observing one untouched nightly run commit + deploy.

### INC-10 — Metrics layer + methodology page
- `metrics.py`: attendance %, missed votes; party-unity % (substantive only — `passage|amendment|veto_override|nomination`; exclusions stated); sponsored/cosponsored/enacted-rate; **cosponsor-to-vote gap** (cosponsored then voted nay on passage, or cosponsored + no floor action ≥ 1 session — rendered as a factual list, never a score); **named-measure mismatch list** (statement with `named_measures` + specificity 2–3 vs. opposite recorded position — list only, adjacency language only); absence-vs-chamber-calendar context
- Methodology page auto-built from docstrings: formula, inclusion/exclusion, source per metric (§5 Tier discipline)
- Symmetry check full activation (§6.5) in CI
**Acceptance:** third-party recompute script covers every metric and matches; methodology page contains one section per exported metric (test: set equality between exported metric keys and page sections); Tier-3 grep guard active.

### INC-10b — FEC funding metrics *(optional, needs H7; Decision D16)*
In-state vs out-of-state %, PAC vs individual % from api.open.fec.gov, formulas on the methodology page like any Tier 2 metric. Build only after INC-13 unless the owner reprioritizes via HUMAN-TASKS.md. Any donation↔vote presentation is an **adjacency timeline** (donations and related votes side by side over time, the same "adjacency, not conclusion" framing INC-18 uses for statements/votes) — never a computed cost-per-vote or purchased-vote figure (D20).

### INC-11 — Statement ledger, curation tool, pairing  *(content = H8; needs H6 for authenticated SPN)*
- Flask curation app (localhost only; assert-refuse to bind non-loopback): paste text+URL → SPN2 capture → poll capture status → verified archive_url → YAML written → `git add` staged. **No verified capture, no save** — the button is disabled, not warned.
- Absence-approval tab (supersedes the INC-6 CLI)
- Pairing: exact `named_measures` bill-id match; short-title allowlist per D9 (`data/statements/_title_allowlist.yaml`, owner-edited)
- Member timeline: statements + votes interleaved; paired items linked; "How We Pair Statements" content page stating the bright line and that the site draws no conclusions
- `checks/archive_links.py` in CI: HEAD every archive_url weekly; dead link → statement flagged unpublishable until recaptured
**Acceptance:** brief Phase-3 criteria: 20+ statements, per-member/party symmetry green, every archive link verified live, ≥ 5 pairs rendering under the strict rule, banned-words green on all curated text.

### INC-12 — Mississippi state layer *(branch chosen by INC-1 verdict)*
**Branch A (GO):** LegiScan ingest module → map `people_id`→state-member records (new `ms_leg` id namespace, crosswalk file), bills/roll calls to canonical schema with `jurisdiction: "ms"`; district lookup; state member pages; 10-vote spot check vs Journal PDFs; public data-limitations page documenting anything LegiScan lacks. **Acceptance:** roadmap Phase-4 criteria (both chambers' current session; spot check passes; gaps documented publicly).
**Branch B (DEFER):** produce `data/quality/ms-state-verdict.md` expansion: Journal PDF parseability assessment (text-layer vs scanned, one sample parsed), effort estimate, and a `/methodology#mississippi` public note that state coverage is deferred and why. **No other increment changes.** Build proceeds to INC-13.

### INC-13 — Candidate Tracker  *(content = H10)*
- `data/candidates/` schema + curation-tool candidate tab (add candidate, add statement w/ archive capture, assign rubric level)
- Helper: `uv run curate sos-import` — parses the SoS qualifying list if machine-readable; else opens a manual-entry form (owner verifies either way; the filing URL is required per record)
- `archive-recapture.yml`: weekly recapture of every candidate `page_captures[].url` during the config-defined campaign window; text-extraction hash comparison → change events appended, diffs viewable on the candidate page ("this page changed on {date}" + both archive links)
- Candidate page: "Issues they say matter" ‖ "What they've committed to do"; headline metric **% of issue statements at Level 0–1**; incumbent framing exactly per brief 6.4 ("Of N statements, M were specific enough to check — here they are, with the corresponding vote")
- `docs/rubric.md` published with 3 worked examples per level (owner supplies examples — H10); double-score workflow: tool marks a random 10% for second-pass scoring, disagreement rate exported and published
**Acceptance:** roadmap Phase-5 criteria verbatim, symmetry (candidate-coverage rule) green.

### INC-14 — Alignment Quiz engine  *(content = H11)*
- `data/quiz/bank/` YAML per §5, versioned + CHANGELOG; provenance required per item; "original" provenance renders a visible badge in the UI
- Ladder flow (Preact island): category → position → reasons (multi-select) → trade-off allocator (100 points across 6 policies, touch-first slider/stepper UI) → per-answer confidence (3-bucket: low/med/high) → "I don't know" always present, styled as a normal option
- Never references parties, politicians, or identity — test asserts the bank contains no member names/party strings
- `scoring.ts`: pure, deterministic; result = per-dimension {position, reason_ids, confidence, weight}
- Portable code per D13: `CAP1.` + base64url(deflate(JSON{bank_version, answers})); decode path renders old codes against their carried bank_version (bank versions are retained forever in `data/quiz/bank/`)
- Question-wording challenge mechanism: every question links "Challenge this wording" → prefilled GitHub issue template; bank CHANGELOG documents every wording change
**Acceptance:** golden vectors — 10 fixed answer sets → exact expected outputs, run in CI via vitest; encode→decode round-trip property test; a network-log test (Playwright) proving **zero requests** during quiz answer/score/decode; completes on a 380px viewport in a scripted run < 5 min of interaction steps; no output anywhere contains a spectrum coordinate (grep of rendered output for axis/compass/left-right scale markup patterns + manual assertion list).

### INC-15 — Alignment outputs
- `data/quiz/dimension_map.yaml`: quiz dimension ↔ official policy areas / subject terms (mechanical mapping table, owner-reviewable, no invented taxonomy — D5/brief §10)
- Per-issue alignment vs named officials: for each dimension, member positions derived **only** from substantive recorded votes on bills mapped to that dimension; alignment = agreement rate, shown per-issue per-member with the underlying vote list one tap away. **No aggregation across issues into any single number per member in the build/publish path** (that's a spectrum by the back door — Tier-3 guard extended to cover it); any single grade is computed client-side from the reader's own visible, adjustable weights per D19 — never shipped as a site-chosen score
- Bill alignment view: "matches your stated positions on 7 of 9 dimensions" with the 9 dimensions listed
**Acceptance:** every alignment figure click-through reproduces from listed votes; cross-issue aggregate guard test; works entirely from a portable code with no network (Playwright network-log again).

### INC-16 — Aggregates Worker + privacy pages  *(needs H4; canary = H12)*
Per §10. **Acceptance:** §10.4.

### INC-17 — Challenge & Calibration
Build strictly in brief-6.6 order: (1) calibration quiz — shared question set, real figure + source, shareable image card; (2) consequence disclosure — CBO link-throughs + measured outcomes *with sources*, attached to supported AND opposed policies symmetrically; (3) steelman — verbatim quotes from named advocates, archive-linked, never paraphrased (curated content, same tool, same archive rule); (4) confidence-gated correction — fires ONLY on low-confidence answers (test asserts a high-confidence answer can never receive one); (5) "who else voted this way" cross-party coalition view, zero commentary; (6) "show me someone I'd disagree with" opt-in button; (7) direct correction last, all users all directions by rule.
**Acceptance:** challenge inventory exported + published; exact-equality symmetry rule green; confidence-gate test; the calibration card renders correctly via iOS/Android share-sheet dimensions (1200×630 + 1080×1920 variants).

### INC-18 — Longitudinal drift
- Client-side: prior results in localStorage (+ importable portable codes); retake → local diff view — "what you moved on, and when," framed by the exact copy: changing your mind is presented as normal (copy reviewed against banned list; no "flip" language, obviously)
- Reminders: `.ics` download per D11 (quarterly RRULE + election-proximate VEVENTs from `data/elections/`), plain `/retake` URL, nothing embedded
- Transition aggregates: on retake, client submits per-dimension `{from_position, to_position}` transition counters to the Worker (§10) — no identifier, no thread; aggregate curve = counter time series
- Event timeline overlay: `data/timeline/` — dated public events (legislation enacted, elections, court rulings, CPI releases) each with source_url, curated. Two curves rendered adjacent; **no causal copy anywhere**; the page states "adjacency, not causation" explicitly
**Acceptance:** retake diff works offline from codes alone; K_ANON gate test (49 respondents → nothing renders; 50 → renders); timeline entries all sourced.

### INC-19 — Bill diff viewer
- govinfo USLM XML for bill versions (`ingest/sources/govinfo.py`); structural diff at section/subsection node identity (D14): match nodes by structural path + fuzzy-stable identifiers, so renumbering cascades don't mark unchanged text
- Unified view, additions/removals distinguished, version toggle
- Attribution: floor amendments (recorded votes, named sponsors) map to change blocks where the amendment text locates them; everything else labeled **unattributed**; headline ratio rendered: "N% of text changes in this bill cannot be attributed to any named member" — computed, methodology-page formula like any Tier 2 metric
**Acceptance:** golden test on one real bill with a known floor amendment: the amendment's block attributes, a committee-substitute block shows unattributed, ratio recomputes; a renumbering-only change produces zero changed blocks in the test fixture.

### INC-20 — "Nobody Told You" feed + glossary  ∥
- Feed rule (mechanical, published): passage-class votes with ≥ 85% yea in both chambers within the covered congress, enacted, sorted recent-first. That's the whole algorithm; it's on the methodology page. (Coverage volume is NOT measured — measuring "media coverage" would import an editorial judgment; the feed's honest claim is "overwhelming bipartisan support," and the name is framing the owner chose.)
- Plain-language glossary: cloture, motion to recommit, discharge petition, rule adoption, suspension of the rules, unanimous consent, quorum call — the allowlisted file per §6.4, manually reviewed
**Acceptance:** feed reproducible from data by the recompute script; every glossary term linked from at least the vote_class badge tooltips.

### INC-21 — Ballot builder + share cards + mobile pass
- Ballot: address → Census Geocoder (`geocoding.geo.census.gov/geocoder/geographies/onelineaddress`, benchmark/vintage current; **runtime verification step:** fetch once for a D'Iberville address at build of this increment; if CD/SLDU/SLDL fields absent from the response, fall back to Census TIGERweb layer query — both branches coded) → districts → match against `data/elections/{year}.yaml` (owner-curated race file from SoS filings — extends H10) → rendered ballot, every name linking to Ledger/Candidate pages. Address is used in-browser for the geocoder call and never sent to our Worker or stored; the privacy page says so.
- Shareable per-issue card: client-side canvas render → PNG → `navigator.share` with download fallback; correct rendering iOS + Android share sheets
- Site-wide mobile pass: Lighthouse mobile ≥ 90 on the six heaviest pages
**Acceptance:** roadmap Phase-8 criteria: correct ballot for a D'Iberville test address (fixture the geocoder response so the test is hermetic), share card renders on both platforms' dimensions, perf budget met.

### INC-22 — Zero-knowledge sync accounts *(post-v1 stub — Decision D12; do not build in this pass)*
Design recorded for the future: random UUID account, no email/phone/IdP; client derives an encryption key from a user passphrase (Argon2id) that never leaves the browser; server stores only `{uuid, ciphertext, updated_at}`; loss-of-passphrase = permanent loss, stated at creation; localStorage remains source of truth, server is sync. Threat-model page already written to cover it when activated.

---

## §8 — Testing requirements (summary of what CI runs)
- **Python:** pytest — model validation, classifier golden file (≥40 real strings), metric formula unit tests with hand-computed fixtures, export determinism, recompute-and-match script as a test
- **TypeScript:** vitest — scoring golden vectors, portable-code round-trip property tests, K_ANON render gate
- **E2E:** Playwright — quiz zero-network assertion, offline portable-code render, confidence-gate, 380px flows
- **Checks suite (blocking):** symmetry, banned words, no-LLM, archive links (weekly schedule), Tier-3 guards, a11y (axe)
- Coverage floor: `ingest/metrics.py`, `classify.py`, `scoring.ts` at 100% branch coverage — these are the credibility-bearing modules; everything else ≥ 80% line.

## §9 — CI/CD
- `ci.yml` (PR + main): lint, tests, checks, site build. Any red blocks merge.
- `nightly.yml` (cron): ingest → checks → export → commit → Pages deploy. Failure = GH notification; last deploy stays live.
- `archive-recapture.yml` (weekly, campaign-window aware) and `agg-export.yml` (weekly, §10.3).
- Branch protection on main: CI required, no force-push (corrections history is load-bearing — brief 5.12).

---

## §10 — Privacy engineering (Decision D2)

### 10.1 Client rules
No cookies. No analytics (D17). No fonts/scripts from third-party CDNs — everything self-hosted in the build. localStorage only for the user's own results; a visible "erase everything" button. Quiz, scoring, decode, ballot lookup: no requests to any server we operate (the geocoder call goes browser→Census directly and is disclosed).

### 10.2 The aggregates Worker — the only server code
- `POST /v1/agg` body: `{bank_version, events:[{dim, position, reason_id, confidence_bucket}], transitions:[{dim, from, to}]}` + Cloudflare Turnstile token (invisible mode).
- Worker: verify Turnstile → schema-validate → for each event/transition, `UPDATE counters SET n = n + 1` on D1 keyed by `(bank_version, iso_week, dim, position, reason_id)` / `(bank_version, iso_week, dim, from, to)` → `204`.
- **Structural guarantees:** no per-submission rows exist; no IP, UA, timestamp-finer-than-week, or header is written anywhere (code-reviewed assertion + a test that the D1 schema has no such columns); Worker logging disabled (`logpush` off, `observability` config committed showing it). A subpoena yields weekly integer counters that are already public in `data/aggregates/`.
- Turnstile is the abuse control **because** it needs no IP retention on our side. Losing some submissions to strict bot-filtering is acceptable; collecting identifiers is not.

### 10.3 Publication path
`agg-export.yml` weekly: pull counters where week is complete AND `n_total_for_cell_group ≥ K_ANON (=50, single constant in worker+ingest config, asserted equal by a test)` → write `data/aggregates/` → commit. Cells below threshold are not exported, not "hidden in the UI" — they never leave D1. Small-district views (drift × MS districts × issue combos) inherit the gate automatically because they render only from exported cells; early unpublishability is expected per brief 6.7.

### 10.4 Pages (= INC-16 acceptance)
- **/privacy — threat model page:** exactly what is stored (repo contents + weekly counters), what a legal demand produces (the same public data), what the operator is technically incapable of producing (any individual's answers, identity, IP, or history), the ballot-address disclosure, and the localStorage model. Accurate against the code — CI test greps the page for the K_ANON constant and current storage list so it can't drift silently.
- **/canary:** dated statement, template provided, H12 recurring; staleness CI rule per H12.
- **Acceptance:** Worker deployed; a scripted 50-submission test populates a cell and it exports, 49 does not; threat-model accuracy test green; canary live.

---

## §A1 — vote_class rules table (initial; extend via unmapped-questions loop)

| Rule id | Match on official question/action text (case-insens., prefix ok) | Class |
|---|---|---|
| R-PASS-1 | "On Passage", "On the Passage" | passage |
| R-PASS-2 | "On Motion to Suspend the Rules and Pass" | passage |
| R-PASS-3 | "On Concurring", "On Agreeing to the Senate Amendment" (final-passage context flagged in action data) | passage |
| R-AMDT-1 | "On Agreeing to the Amendment", "On the Amendment" | amendment |
| R-PROC-1 | "On the Cloture Motion", "On Cloture" | procedural |
| R-PROC-2 | "On the Motion to Proceed" | procedural |
| R-PROC-3 | "On Ordering the Previous Question" | procedural |
| R-PROC-4 | "On the Motion to Recommit", "On Motion to Commit" | procedural |
| R-PROC-5 | "On the Motion to Table" | procedural |
| R-PROC-6 | "On the Journal", "Call of the House", "Quorum" | procedural |
| R-RULE | "On Agreeing to the Resolution" AND resolution reported by the Rules Committee | procedural |
| R-RES | "On Agreeing to the Resolution" otherwise | passage |
| R-NOM | "On the Nomination", "On the Confirmation" | nomination |
| R-VETO | "Passage, Objections of the President to the Contrary Notwithstanding", "On Overriding the Veto" | veto_override |
| R-DEFAULT | anything else | other → log |

Every classification stores its rule id (`vote_class_rule`) for auditability; the table itself renders on the methodology page.

## §A2 — Threat-model page outline
What we publish (all of it) · What the server can see (nothing per-person; counters only) · What we never receive (answers, identity, IP-at-write, addresses) · What a subpoena produces (this repo + the counters, both already public) · What you risk locally (your own device's localStorage; erase button) · Ballot address disclosure · Canary link · Contact for corrections.

## §A3 — Banned-strings list
See §6.4 — the list is code, quoted there in full; extend only by PR so extensions are themselves diffable.

## §A4 — Correction process (docs/correction-process.md skeleton)
Report path (GH issue template + email alias) → verify against primary source → fix as a normal commit referencing the issue → corrections page auto-lists commits tagged `correction:` with date, what changed, and why. Never a force-push, never a silent edit.

---

*End of specification. Build order: INC-0 → INC-21 sequentially except marked ∥. MVP is live at INC-9. Every stop-point after INC-9 is a coherent public product.*
