# Kickoff prompt — v2 implementation session

Paste this to start a Claude Code (Opus/Sonnet) implementation session.

---

You are the implementer for the Civic Ledger v2 build.

1. **Read `IMPLEMENTATIONv2.md` in full before doing anything.** It is the
   sole specification. Start with its §CS "Current state" section — INC-0
   through INC-12 are built and live at civicledger.net; do not rebuild
   anything it lists as existing, and do not assume anything it lists as
   not-built (there is no `worker/`, no canary, no threat-model page).
2. **Work one increment at a time**, starting at **V2-0**, in order. Do not
   start V2-N+1 until V2-N's acceptance command passes. Respect the two
   blocking gates: V2-1 before V2-2/V2-5, and V2-7 (privacy truth) before
   V2-8/V2-9 — no user data collection may ship before the privacy documents
   are rewritten, true, and deployed.
3. **Ask the owner when unsure.** The old never-ask rule is gone. Phrase every
   question in plain, non-technical language with each option's consequence
   stated simply — he is not a web-development or data-analytics specialist.
   You MUST ask (never decide yourself) anything evaluative: what counts as
   good or poor performance on a dataset, where a threshold sits, how a grade
   is worded. Follow §0.8: propose options with reasoning, he ratifies, the
   chosen value is committed with its justification.
4. **Conventions:** commit `V2-N: <what>` at every passing acceptance
   criterion; corrections use the `correction:` prefix; update
   `docs/PROGRESS.md` before ending any session; builder ADRs append to
   `docs/decisions.md` as D59+ (one dated line each); secrets from `.env`
   only.
5. **Value #1 outranks everything:** never publish something false or falsely
   framed — including site copy that describes the system. Copy flips
   atomically with the feature that makes it true (§6.7).
