// The one list of what this site will store about a reader once accounts exist
// and what each item is used for, and the one place the published
// K-anonymity floor is written down in `site/`.
//
// Rendered by BOTH `/privacy` (the short version) and `/threat-model` (the long
// one). It is a module and not prose on each page for one reason: two
// hand-written copies of a disclosure list drift, and a privacy page that
// disagrees with itself is a rule 0 failure (`IMPLEMENTATIONv3.md` §1).
//
// One entry per D1 table in `IMPLEMENTATIONv3.md` §3.2 "Accounts / alerts"
// (built in Phase 7; see §4.7). The `table` field is not decoration —
// `tests/test_privacy_accuracy.py` asserts that the set of tables named here
// equals the set the spec names, so a table added to the spec without a
// sentence here fails the build rather than quietly shipping as undisclosed
// collection.
//
// Wording rules (`IMPLEMENTATIONv3.md` §4.8 and §1 rule 8):
//   - The page DESCRIBES; it does not promise. This list says what is stored
//     and what it is used for. It is not a claim that nothing else is kept.
//   - The never-sell promise was withdrawn by the owner on 2026-10-07 — the
//     promise itself, not just the sentence. Do not write it back onto the
//     site in any wording.
//   - Every sentence names a use. "What is collected and how it is used" is
//     what §4.8 owes the reader; a sentence that only names the data is half
//     an answer.
//   - Password hashing uses a memory-hard algorithm; the site says "a
//     scrambled form of your password" rather than naming it, because the
//     algorithm is an implementation detail the reader cannot check.
//   - No retention period appears here. The numbers live in the spec, not on
//     the page: a number on the page is a description of a cron job that does
//     not exist yet, and rule 0 says copy flips in the same commit as the
//     feature.

export type StoredThing = {
  /** The D1 table from `IMPLEMENTATIONv3.md` §3.2 this sentence discloses. */
  readonly table: string;
  /**
   * The reader-facing sentence. Plain words, no jargon, no promise. Says what
   * is stored AND what it is used for (§4.8).
   */
  readonly text: string;
};

export const STORED_WHEN_ACCOUNTS_SHIP: readonly StoredThing[] = [
  {
    table: "users",
    text: "Who you are: your email address, whether it has been confirmed, a scrambled form of your password, and when you signed up. Used to let you sign in and to tie everything below to you.",
  },
  {
    table: "email_verifications",
    text: "An email address you have given but not yet confirmed, and the one-time code sent to confirm it. Used to check the address belongs to you; the code is deleted once you use it.",
  },
  {
    table: "subscriptions",
    text: "What you follow: which bills, topics and members, and how often you want to hear about them. Used to decide which alerts to send you and which to leave out.",
  },
  {
    table: "preferences",
    text: "Your settings and your answers to anything the site asks you — including the grade weights you choose and the stance questions you answer. Used to show you the site the way you set it up and to show you your own answers back over time.",
  },
  {
    table: "deliveries",
    text: "Which alerts have already gone to you and when. Used so the same alert is not sent twice, and so a failed send can be retried.",
  },
  {
    table: "channels",
    text: "Where to reach you: your email address, and a phone number only if text alerts are ever added. Used to address the message.",
  },
  {
    table: "profiles",
    text: "A public profile, only if you choose to make one. Used to show what you chose to publish to anyone who visits it. Published means public.",
  },
];

// The floor every published figure derived from reader data has to clear. One
// literal in `site/`, pinned by `tests/test_privacy_accuracy.py` against
// `ingest.config.K_ANON` — the constant the render gate actually enforces.
export const K_ANON_PUBLISH_FLOOR = 50;
