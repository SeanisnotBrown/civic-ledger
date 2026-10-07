// What a Yea and a Nay on this motion actually do.
//
// Why this file exists: a roll call's question is the chamber's own wording, and
// the chamber's wording is procedural. "On Motion to Table" on an impeachment
// resolution records a Yea from a member who wanted the resolution set aside —
// read without the procedure, the row looks like a vote FOR the thing tabled.
// Rule 6 (state facts, never motive) does not let us say why a member voted; it
// does let us state, from the chamber's own rules, what the vote did.
//
// The rules of construction, all four binding:
//   1. FIXED TABLE, first match wins. Nothing here is generated, inferred at
//      build time, or produced by a model. A question that matches nothing gets
//      NO meaning line at all — silence, never a guess (Rule 0).
//   2. Both sides, always. A line that explains only a Yea invites the reader to
//      invert it wrongly, which is the exact misreading this file fixes.
//   3. No number we cannot source. The Senate's cloture threshold is three
//      fifths for legislation and a simple majority for nominations, and our
//      vote records do not carry the requirement, so no threshold is printed for
//      cloture. Suspension's two thirds is a House rule that holds for every
//      motion of that name, so that one is stated.
//   4. What the motion does, never why it was moved. No "used to delay", no
//      "tactic", no "designed to".
//
// Order is load-bearing: the OUTER motion must match first. "On Motion to Table
// the Motion to Discharge Committee" is a tabling vote; "On Cloture on the
// Motion to Proceed" is a cloture vote. Entries are ordered accordingly and
// `npm run test:motions` prints every question the table does not match.

export type MotionKind =
  | "table" | "table_reconsider" | "veto_override" | "cloture"
  | "previous_question" | "recommit"
  | "discharge" | "instruct_conferees" | "commit" | "reconsider" | "suspension"
  | "concur" | "proceed" | "nomination" | "amendment" | "adjourn" | "passage"
  | "resolution" | "point_of_order" | "waiver" | "conference_report"
  | "housekeeping";

export interface MotionEntry {
  kind: MotionKind;
  /** Matched against the verbatim question text, first match wins. */
  test: RegExp;
  /** Plain-English effect, both sides. Empty when the renderer supplies it. */
  meaning: string;
  /** True when a Yea on this motion resolves the MEASURE (as opposed to an
   *  amendment to it, or a step on the way). Decides whether a roll call may be
   *  published as the margin a bill passed or failed by. */
  resolvesMeasure?: boolean;
  /** What THIS member did, in one short clause, for a yea and for a nay
   *  ("Voted to kill it"). Both or neither: a motion whose direction cannot be
   *  stated plainly gets no short line at all, the same silence the `meaning`
   *  table keeps for an unmatched question. Rendered above `meaning`, so it
   *  leads with the member's own act and the procedure explains it. */
  yea?: string;
  nay?: string;
}

export const MOTIONS: MotionEntry[] = [
  {
    // Tabling a motion to RECONSIDER is the one tabling vote that settles
    // something rather than setting it aside: it closes off a second vote on a
    // decision already taken. The general tabling line below would read
    // backwards here, so this entry sits above it.
    kind: "table_reconsider",
    yea: "Voted to make the earlier vote final",
    nay: "Voted to leave it open to being reconsidered",
    test: /motion to table(\s+the)?\s+motion to reconsider|^table motion to reconsider/i,
    meaning:
      "Tabling a motion to reconsider closes off a second vote on a decision the " +
      "chamber has already taken. A Yea makes the earlier vote final; a Nay leaves " +
      "it open to being reconsidered.",
  },
  {
    kind: "table",
    yea: "Voted to kill it",
    nay: "Voted to keep it alive",
    test: /\bmotion to table\b|^table motion\b/i,
    meaning:
      "Tabling disposes of the matter without a vote on its merits — in practice, " +
      "it kills it. A Yea kills it; a Nay keeps it alive.",
  },
  {
    kind: "waiver",
    yea: "Voted to set the rule aside",
    nay: "Voted to keep the rule in force",
    test: /\bmotion to waive\b|waive all applicable/i,
    meaning:
      "Sets aside one of the chamber's own rules that would otherwise stop the " +
      "measure being considered. A Yea sets the rule aside; a Nay leaves it in " +
      "force.",
  },
  {
    kind: "veto_override",
    yea: "Voted to enact it over the veto",
    nay: "Voted against enacting it over the veto",
    test: /objections of the president|overriding the veto/i,
    meaning:
      "A vote to enact the bill over the President's veto, which takes two thirds " +
      "of those voting. A Yea enacts it; a Nay leaves the veto standing.",
    resolvesMeasure: true,
  },
  {
    kind: "cloture",
    yea: "Voted to limit debate",
    nay: "Voted to keep debate open",
    test: /\bcloture\b/i,
    meaning:
      "Cloture limits further debate so the chamber can reach a vote on the matter " +
      "itself. A Yea limits debate; a Nay leaves it open.",
  },
  {
    kind: "previous_question",
    yea: "Voted to end debate",
    nay: "Voted to keep debate open",
    test: /previous question/i,
    meaning:
      "Ordering the previous question ends debate and amendments and brings the " +
      "pending matter to an immediate vote. A Yea ends debate; a Nay keeps it open.",
  },
  {
    kind: "recommit",
    yea: "Voted to send it back to committee",
    nay: "Voted against sending it back to committee",
    test: /motion to recommit/i,
    meaning:
      "A motion to recommit sends the bill back to committee instead of holding the " +
      "final vote now. A Yea returns it to committee; a Nay keeps it on course for " +
      "the final vote.",
  },
  {
    kind: "discharge",
    yea: "Voted to force it out of committee",
    nay: "Voted to leave it in committee",
    test: /motion to discharge/i,
    meaning:
      "A discharge motion takes a measure away from a committee that has not acted " +
      "on it and brings it to the floor. A Yea brings it to the floor; a Nay leaves " +
      "it in committee.",
  },
  {
    kind: "instruct_conferees",
    yea: "Voted for the instruction to the negotiators",
    nay: "Voted against the instruction to the negotiators",
    test: /instruct conferees|go to conference|closing portions of the conference/i,
    meaning:
      "A vote about the negotiation that turns the House and Senate versions into " +
      "one bill. It does not change the bill's text.",
  },
  {
    kind: "commit",
    yea: "Voted to send it to committee",
    nay: "Voted to keep it on the floor",
    test: /motion to (commit|refer)\b|motion \([^)]*motion to (commit|refer)/i,
    meaning:
      "Hands the measure to a committee rather than voting on it now. A Yea sends it " +
      "to committee; a Nay keeps it on the floor.",
  },
  {
    kind: "reconsider",
    yea: "Voted to vote on it again",
    nay: "Voted to let the decision stand",
    test: /motion to reconsider/i,
    meaning:
      "Asks the chamber to vote again on something it has already decided. A Yea " +
      "reopens that decision; a Nay leaves it standing.",
  },
  {
    kind: "suspension",
    yea: "Voted to pass it",
    nay: "Voted against passing it",
    test: /suspend the rules/i,
    meaning:
      "Suspension of the rules is a fast route for a measure: no amendments, limited " +
      "debate, and two thirds of those voting must agree. This is the vote on the " +
      "measure itself. A Yea passes it; a Nay blocks it.",
    resolvesMeasure: true,
  },
  {
    kind: "concur",
    yea: "Voted to accept the other chamber's changes",
    nay: "Voted against accepting the other chamber's changes",
    test: /concur in (the )?(senate|house)|motion to concur|concur in senate/i,
    meaning:
      "Accepts the other chamber's changes to the bill. A Yea agrees to their text; " +
      "a Nay does not.",
    resolvesMeasure: true,
  },
  {
    kind: "proceed",
    yea: "Voted to take it up",
    nay: "Voted against taking it up",
    test: /motion to proceed|motion \([^)]*motion to proceed/i,
    meaning:
      "Decides whether the chamber takes the measure up at all. A Yea begins " +
      "consideration; a Nay leaves it off the floor.",
  },
  {
    kind: "nomination",
    yea: "Voted to confirm them",
    nay: "Voted against confirming them",
    test: /on the nomination/i,
    meaning:
      "A vote to confirm someone the President nominated. A Yea confirms them; a " +
      "Nay does not.",
  },
  {
    kind: "amendment",
    yea: "Voted to change the text",
    nay: "Voted to leave the text as it stood",
    test: /amendment|\bamdt\b|retaining division/i,
    meaning:
      "A vote to change the text of the measure, not a vote on the measure itself. " +
      "A Yea makes the change; a Nay leaves the text as it stands.",
  },
  {
    kind: "adjourn",
    yea: "Voted to adjourn for the day",
    nay: "Voted against adjourning",
    test: /motion to adjourn/i,
    meaning: "Ends the day's session. It is not a vote on legislation.",
  },
  {
    kind: "conference_report",
    yea: "Voted to adopt the negotiated version",
    nay: "Voted against the negotiated version",
    test: /conference report/i,
    meaning:
      "The vote on the single version of the bill that House and Senate " +
      "negotiators agreed on. No amendments are possible at this point. A Yea " +
      "adopts that version; a Nay does not.",
    resolvesMeasure: true,
  },
  {
    kind: "passage",
    yea: "Voted to pass it",
    nay: "Voted against passing it",
    test: /^on passage|passage of the bill|on the (joint|concurrent) resolution/i,
    meaning:
      "The final vote on the measure itself. A Yea passes it out of this chamber; a " +
      "Nay does not.",
    resolvesMeasure: true,
  },
  {
    // "On Agreeing to the Resolution" is both a House rule setting the terms of
    // debate for another bill AND the vote on a standalone resolution. The
    // question text cannot tell them apart, so the line is chosen from the
    // measure's own official title (see motionMeaning).
    kind: "resolution",
    test: /^on (agreeing to|consideration of) the (concurrent )?resolution|^on the resolution/i,
    meaning: "",
    resolvesMeasure: true,
  },
  {
    kind: "point_of_order",
    test: /point of order|decision of the chair/i,
    meaning:
      "A ruling on whether the chamber's own rules allow what is pending. It is not " +
      "a vote on the measure.",
  },
  {
    kind: "housekeeping",
    test: /call of the house|motion for attendance|close the doors|election of the speaker|motion to recess|presence of absentee/i,
    meaning: "A vote on the chamber's own proceedings, not on legislation.",
  },
];

/** The two fixed lines for "On Agreeing to the Resolution", chosen from the
 *  measure's own official title. A House rule's title always opens "Providing
 *  for consideration of"; anything else is the resolution itself. */
const RULE_TITLE = /^providing for (the )?(further )?consideration of/i;
const RESOLUTION_RULE_MEANING =
  "This resolution sets the terms for debating another bill — how long the House " +
  "debates it and which amendments may be offered. A Yea adopts those terms; a Nay " +
  "rejects them.";
const RESOLUTION_RULE_YEA = "Voted to adopt those debate terms";
const RESOLUTION_RULE_NAY = "Voted against those debate terms";
const RESOLUTION_YEA = "Voted to adopt it";
const RESOLUTION_NAY = "Voted against adopting it";
const RESOLUTION_MEANING =
  "The vote on the resolution itself. A resolution states the chamber's position or " +
  "changes its own rules; it does not become law. A Yea adopts it; a Nay does not.";

export interface MotionMeaning { kind: MotionKind; meaning: string }

/** Position as the vote records write it. Only yea and nay have a direction to
 *  state: "present" takes no side, and an absence is not a vote at all. */
export type VotePosition = "yea" | "nay" | "present" | "not_voting";

/** What this member did, in one short clause — "Voted to kill it". Null when
 *  the position has no direction (present, absent) or when the motion has no
 *  pair in the table. Never inferred: the clause is written beside the motion's
 *  own explanation so the two cannot drift apart. */
export function positionEffect(
  question: string | null | undefined,
  position: VotePosition,
  billTitle?: string | null,
): string | null {
  if (!question) return null;
  if (position !== "yea" && position !== "nay") return null;
  for (const m of MOTIONS) {
    if (!m.test.test(question)) continue;
    if (m.kind === "resolution") {
      const isRule = Boolean(billTitle && RULE_TITLE.test(billTitle));
      if (position === "yea") return isRule ? RESOLUTION_RULE_YEA : RESOLUTION_YEA;
      return isRule ? RESOLUTION_RULE_NAY : RESOLUTION_NAY;
    }
    return (position === "yea" ? m.yea : m.nay) ?? null;
  }
  return null;
}

/** The plain-English effect of this question, or null when the fixed table has
 *  no entry for it. `billTitle` is consulted only for the resolution case. */
export function motionMeaning(
  question: string | null | undefined,
  billTitle?: string | null,
): MotionMeaning | null {
  if (!question) return null;
  for (const m of MOTIONS) {
    if (!m.test.test(question)) continue;
    if (m.kind === "resolution") {
      return {
        kind: m.kind,
        meaning: billTitle && RULE_TITLE.test(billTitle)
          ? RESOLUTION_RULE_MEANING
          : RESOLUTION_MEANING,
      };
    }
    return { kind: m.kind, meaning: m.meaning };
  }
  return null;
}

/** True when a Yea on this question decides the MEASURE. A roll call's tally may
 *  only be published as the margin a bill passed or failed by when this holds:
 *  an amendment or procedural roll on the same bill on the same day is a
 *  different question with a different tally. */
export function resolvesMeasure(question: string | null | undefined): boolean {
  if (!question) return false;
  for (const m of MOTIONS) {
    if (m.test.test(question)) return m.resolvesMeasure === true;
  }
  return false;
}
