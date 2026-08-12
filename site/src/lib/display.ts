// UI chrome text (§0.5: not political content — labels, tooltips, format helpers).
// vote_class tooltips are one-line MECHANICAL descriptions of a procedure. The
// glossary page (INC-20) is the banned-words-allowlisted file; this copy is not
// allowlisted, so it stays strictly neutral and procedural.

import type { Position, VoteClass } from "./data";

export const VOTE_CLASS_LABEL: Record<VoteClass, string> = {
  passage: "Passage",
  amendment: "Amendment",
  procedural: "Procedural",
  nomination: "Nomination",
  veto_override: "Veto override",
  other: "Other",
};

export const VOTE_CLASS_TOOLTIP: Record<VoteClass, string> = {
  passage: "A vote on final passage of a measure.",
  amendment: "A vote on a proposed change to a measure's text.",
  procedural: "A vote on how the chamber handles a measure (e.g. cloture, motion to proceed, previous question), not on the measure itself.",
  nomination: "A vote to confirm a nomination.",
  veto_override: "A vote to override a presidential veto.",
  other: "A recorded vote that does not fall under the categories above; the official question text is shown verbatim.",
};

export const POSITION_LABEL: Record<Position, string> = {
  yea: "Yea",
  nay: "Nay",
  present: "Present",
  not_voting: "Not voting",
};

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** ISO date (possibly with time/offset) -> "Jan 3, 2025". Date-only, no locale
 *  dependence, no time zone math (the ISO date field is already the record date). */
export function formatDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  const [, y, mo, d] = m;
  return `${MONTHS[Number(mo) - 1]} ${Number(d)}, ${y}`;
}

/** "hr2-119" -> "H.R. 2 (119th)" for display; unknown shapes pass through. */
export function billLabel(billId: string): string {
  const m = /^([a-z]+)(\d+)-(\d+)$/.exec(billId);
  if (!m) return billId;
  const [, type, num, congress] = m;
  const TYPES: Record<string, string> = {
    hr: "H.R.", s: "S.", hres: "H.Res.", sres: "S.Res.",
    hjres: "H.J.Res.", sjres: "S.J.Res.", hconres: "H.Con.Res.", sconres: "S.Con.Res.",
  };
  return `${TYPES[type] ?? type.toUpperCase()} ${num} (${congress}th)`;
}

export function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] ?? s[v] ?? s[0]);
}
