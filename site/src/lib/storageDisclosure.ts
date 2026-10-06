// The one list of what this site will store about a reader once accounts exist,
// and the one place the published K-anonymity floor is written down in `site/`.
//
// Rendered by BOTH `/privacy` (the short version, mandated by IMPLEMENTATIONv2
// §7 V2-7 task 1: "the §5 table list, in plain words") and `/threat-model` (the
// long version). It is a module and not prose on each page for one reason: two
// hand-written copies of a disclosure list drift, and a privacy page that
// disagrees with itself is the Value #1 failure V2-7 exists to prevent.
//
// One entry per D1 table in IMPLEMENTATIONv2.md §5 "Account model". The `table`
// field is not decoration — `tests/test_privacy_accuracy_v2_7.py` asserts that
// the set of tables named here equals the set §5 names, so a table added to the
// spec without a sentence here fails the build rather than quietly shipping as
// undisclosed collection.
//
// Wording rules that are owner decisions, not style (docs/decisions.md):
//   - SD-34: never reinstate the withdrawn no-tracking guarantees. This list
//     describes what is stored; it is NOT a promise that nothing else is.
//   - SD-34: Argon2id is deliberately not named on the site. "a scrambled form
//     of your password" is the pinned plain-words version.
//   - SD-38: the unconfirmed address and its one-time code are disclosed as
//     their own line rather than folded into "your email address".
//   - SD-39: the MECHANISM may be stated (the code is deleted once used); the
//     DURATION may not. Retention periods are ratified (90 days / 24 h / 1 h)
//     and live in spec §5, not here — a number on the page is a promise about a
//     cron job, and §6.7 says copy flips atomically with the feature.
//   - H21: phone stays hypothetical until the owner ratifies it.
//   - No retention period appears here. Both are now RATIFIED (SD-39) and both
//     stay off the page by the same decision: see spec §5 for the numbers.

export type StoredThing = {
  /** The D1 table from IMPLEMENTATIONv2.md §5 this sentence discloses. */
  readonly table: string;
  /** The reader-facing sentence. Plain words, no jargon, no promise. */
  readonly text: string;
};

export const STORED_WHEN_ACCOUNTS_SHIP: readonly StoredThing[] = [
  {
    table: "users",
    text: "Who you are: your email address, whether it has been confirmed, a scrambled form of your password, and when you signed up.",
  },
  {
    table: "email_verifications",
    text: "An email address you have given but not yet confirmed, and the one-time code sent to confirm it, which is deleted once you confirm.",
  },
  {
    table: "subscriptions",
    text: "What you follow: which bills, topics and members, and how often you want to hear about them.",
  },
  {
    table: "preferences",
    text: "Your settings and your answers to anything the site asks you.",
  },
  {
    table: "deliveries",
    text: "Which alerts have already gone to you, so the same one is not sent twice.",
  },
  {
    table: "channels",
    text: "Where to reach you: your email address, and a phone number only if that is ever added.",
  },
  {
    table: "profiles",
    text: "A public profile, only if you choose to make one. Published means public.",
  },
];

// The floor every published figure derived from reader data has to clear. One
// literal in `site/`, pinned by the V2-7 accuracy test against `ingest.config
// .K_ANON` — the constant the render gate actually enforces. SD-34 kept this
// when it withdrew the other privacy guarantees; it needs its own dated
// decision to change.
export const K_ANON_PUBLISH_FLOOR = 50;
