// The bill-page half of SD-37 (owner decision, 2026-10-05).
//
// congress.gov legitimately lists some actions more than once, byte for byte —
// a resolution's "Submitted in House" row twice, hr9748-118's referral line
// four times. D100 established that nothing is truncated and nothing is our
// bug: the repeats are in the government's record. The owner was asked how a
// repeat should render and chose: **show the action once, with a line
// underneath saying how many times the record lists it.**
//
// Two constraints come with that choice, both of them load-bearing:
//
// 1. **The identity is `entryId()`** — the same sha256-over-the-whole-row rule
//    as `ingest.events.event_id` and the Atom feeds (D101). One government
//    action is therefore one thing on all three surfaces: this page, the feed,
//    and `data/events`. A looser identity here (date + text, say) would collapse
//    two rows the feed keeps apart, and the page would disagree with the feed it
//    links to.
// 2. **The count stays the record's count.** `actions.length` on the page
//    header keeps counting what the record lists, NOT the number of rows
//    rendered — SD-37's scope guard, verbatim: "the number and the note are
//    both true only if they disagree." A page that says "41 actions" over 41
//    rows has silently edited the official record down.
import { entryId } from "./atom";
import type { BillAction } from "./data";

export interface TimelineRow {
  /** The action as published. Rendered verbatim (§0.5). */
  readonly action: BillAction;
  /** How many times the official record lists this exact action. 1 for nearly all. */
  readonly listed: number;
}

/** Collapse byte-identical repeats, keeping the record's order.
 *
 *  Stored order is the government's order (newest-first from the /actions
 *  sub-resource, never re-sorted — see the note in `/b/[bill].astro`), so a
 *  repeat is folded into its FIRST appearance and the sequence a reader sees is
 *  still the sequence the chamber published. */
export function timelineRows(
  billId: string,
  actions: readonly BillAction[],
): TimelineRow[] {
  const rows: TimelineRow[] = [];
  const at = new Map<string, number>();
  for (const action of actions) {
    const id = entryId(billId, action as unknown as Record<string, unknown>);
    const seen = at.get(id);
    if (seen === undefined) {
      at.set(id, rows.length);
      rows.push({ action, listed: 1 });
    } else {
      rows[seen] = { action: rows[seen].action, listed: rows[seen].listed + 1 };
    }
  }
  return rows;
}

/** The ratified sentence, or null when there is nothing to disclose.
 *
 *  The wording is the owner's, quoted in SD-37: *"The official record lists
 *  this action 4 times."* It is not UI copy to tune — it is the sentence that
 *  makes the collapsed row honest. */
export function repeatNote(listed: number): string | null {
  return listed > 1 ? `The official record lists this action ${listed} times.` : null;
}
