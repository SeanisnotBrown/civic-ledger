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

/** ISO date -> "Oct 24" (no year). Same parsing rules as formatDate. */
export function formatMonthDay(iso: string): string {
  return formatDate(iso).replace(/, \d{4}$/, "");
}

/**
 * The reader line shown while data/quality/senate-outage.json exists (owner's wording,
 * verbatim, ruling 2026-10-29). Both dates come from the notice, which `ingest
 * senate-votes` writes from the record: the newest Senate roll held and the first night
 * senate.gov refused us. Rendered beside "Data last updated" (footer) and "Dataset last
 * updated" (homepage) only; site/scripts/check-senate-notice.mjs pins the wording.
 */
export function senateOutageLine(notice: { last_roll_date: string; outage_start: string }): string {
  return `Senate votes shown through ${formatDate(notice.last_roll_date)}. ` +
    `Since ${formatMonthDay(notice.outage_start)}, senate.gov has blocked our automated ` +
    `requests, so newer Senate votes may not appear yet.`;
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

/** "ms-hb1-2249" -> "HB 1"; unknown shapes pass through. MS uses HB/SB/HR/SR and
 *  concurrent/resolution variants — the alpha prefix is shown verbatim, uppercased. */
export function msBillLabel(billId: string): string {
  const m = /^ms-([a-z]+)(\d+)-\d+$/.exec(billId);
  if (!m) return billId;
  return `${m[1].toUpperCase()} ${m[2]}`;
}

export function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] ?? s[v] ?? s[0]);
}

/** An action's published text, for rendering.
 *
 *  The parameter type is deliberately looser than `BillAction.text` (a required
 *  `string`), and the fallback is deliberately not an empty string.
 *  `ingest/models.py` records `text` as present on 520/520 sampled actions and
 *  therefore required — but the activity backfill has since QUARANTINED a real bill,
 *  `s4869-118`, with `KeyError: 'text'`: congress.gov served an action row without
 *  one. Today the quarantine keeps that bill off the site entirely. When the ingest is
 *  fixed to tolerate it (and it will be — the government's record is the government's
 *  to shape), the field becomes nullable and anything doing string interpolation or
 *  XML-escaping on it would throw at build time. So the guard goes in before the data
 *  change arrives, and it SAYS what happened rather than rendering a blank line, which
 *  would imply an action with no content (Value #1). */
export function actionText(action: { text?: string | null }): string {
  return action.text ?? "(no action text on the official record)";
}
