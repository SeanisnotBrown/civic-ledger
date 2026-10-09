// Representative page URLs, computed from the committed dataset so the E2E suite
// always targets pages that actually exist (no hardcoded ids that rot).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DATA = fileURLToPath(new URL("../../data/", import.meta.url));

// P2 acceptance names a HOUSE member page and a SENATE member page. `firstMemberId`
// happens to be a House member, so the Senate case is derived explicitly rather than
// left to the alphabet.
function firstByChamber(chamber: "house" | "senate"): string {
  const dir = path.join(DATA, "members");
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".json")).sort()) {
    const m = JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8"));
    if (m.chamber === chamber && m.jurisdiction === "us") return m.id;
  }
  throw new Error(`no ${chamber} member in the roster`);
}

// V2-3: a non-voting delegate's page — exercises the mixed ranked/unranked tile path
// (ranked on bill metrics, not on the vote metrics — D66) and the delegate caption.
// Derived from the ranking's own excluded list so it never rots.
function firstDelegateId(): string {
  const att = JSON.parse(
    fs.readFileSync(path.join(DATA, "rankings", "attendance.json"), "utf-8"));
  return [...att.chambers.house.excluded_delegates].sort()[0];
}

// A vote that carries delegation positions AND a bill link, so the vote page
// exercises every §6.7 branch (badge, positions, bill link, official record).
function richVote(): { roll: string; bill: string } {
  const dir = path.join(DATA, "votes");
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".json")).sort()) {
    const v = JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8"));
    if (v.member_votes.length > 0 && v.rollcall.bill_id) {
      // Only if the referenced bill was ingested (has a page).
      const billPath = path.join(DATA, "bills", `${v.rollcall.bill_id}.json`);
      if (fs.existsSync(billPath)) return { roll: v.rollcall.id, bill: v.rollcall.bill_id };
    }
  }
  throw new Error("no representative vote found");
}

const rv = richVote();

// Mississippi state layer (INC-12): representative pages from data/state/ms/.
function firstMsMemberId(): string {
  const dir = path.join(DATA, "state", "ms", "members");
  const f = fs.readdirSync(dir).filter((x) => x.endsWith(".json")).sort()[0];
  return JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8")).id;
}
function richMsVote(): { roll: string; bill: string } {
  const dir = path.join(DATA, "state", "ms", "votes");
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".json")).sort()) {
    const v = JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8"));
    if (v.member_votes.length > 0 && v.rollcall.bill_id) {
      const billPath = path.join(DATA, "state", "ms", "bills", `${v.rollcall.bill_id}.json`);
      if (fs.existsSync(billPath)) return { roll: v.rollcall.id, bill: v.rollcall.bill_id };
    }
  }
  throw new Error("no representative MS vote found");
}

const msv = richMsVote();

// V2-5 /compare: two GRADED members from different chambers, so the functional test
// exercises graded cards, the shared attendance axis, and the mixed-chamber disclosure.
// Derived from the committed grades + roster so the ids never rot.
export function compareIds(): { a: string; b: string } {
  const grades = JSON.parse(fs.readFileSync(path.join(DATA, "grades", "attendance.json"), "utf-8"));
  const gradedByChamber: Record<string, string[]> = { house: [], senate: [] };
  for (const id of Object.keys(grades.members)) {
    try {
      const m = JSON.parse(fs.readFileSync(path.join(DATA, "members", `${id}.json`), "utf-8"));
      if (m.chamber === "house" || m.chamber === "senate") gradedByChamber[m.chamber].push(id);
    } catch { /* skip */ }
  }
  gradedByChamber.house.sort();
  gradedByChamber.senate.sort();
  return { a: gradedByChamber.house[0], b: gradedByChamber.senate[0] };
}

// V2-5 /compare delegate case (D66/D77): a non-voting delegate paired with a GRADED House
// member, so the test proves the vote metrics (attendance/cross-aisle/yea) are suppressed for the
// delegate ONLY — the graded member's vote metrics still render. Both are House, so the pair
// carries no cross-chamber disclosure to confound the assertion. Derived from the committed
// delegate list + grades, so the ids never rot.
export function compareDelegatePair(): { delegate: string; graded: string } {
  return { delegate: firstDelegateId(), graded: compareIds().a };
}

// --- V2-11 task 7: activity, topics, feeds --------------------------------

/** Every bill id that reached a recorded vote, i.e. every bill with a /b/ page
 *  (SD-33 3(c)). One pass over the committed votes. */
function votedBillIds(): Set<string> {
  const dir = path.join(DATA, "votes");
  const out = new Set<string>();
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".json"))) {
    const v = JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8"));
    if (v.rollcall.bill_id) out.add(v.rollcall.bill_id);
  }
  return out;
}

/**
 * A bill that has BOTH a /b/ page and a collected action timeline — the only kind
 * that exercises the rendered timeline and a non-empty bill feed.
 *
 * Returns null when the dataset has none. That is a real state, not a broken
 * fixture: `actions` is the D27 "not collected" sentinel until the one-time activity
 * backfill reaches a bill, so a fresh checkout can legitimately have zero. Specs skip
 * rather than fail on null — a fixture that threw would turn "the backfill has not run
 * here" into a red build.
 */
export function billWithActions(): string | null {
  const voted = votedBillIds();
  const dir = path.join(DATA, "bills");
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".json")).sort()) {
    const b = JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8"));
    if (b.actions && b.actions.length > 0 && voted.has(b.id)) return b.id;
  }
  return null;
}

/** One page per official vocabulary, each with bills on it. The two are separate URL
 *  namespaces (ADR D97), so both shapes need covering. */
export function topicPaths(): { policyArea: string; subject: string } {
  const idx = JSON.parse(
    fs.readFileSync(path.join(DATA, "topics", "index.json"), "utf-8"));
  const pick = (list: any[]) =>
    [...list].sort((a, b) => b.bill_count - a.bill_count || a.slug.localeCompare(b.slug))[0];
  return {
    policyArea: `/topics/policy-area/${pick(idx.policy_areas).slug}`,
    subject: `/topics/subject/${pick(idx.subjects).slug}`,
  };
}

const topics = topicPaths();

/** Rule-0 fixture (2026-10-09). A member whose terms do NOT cover the dataset's own
 *  date — i.e. one who left mid-Congress — and one who still holds a seat. Both are
 *  derived from the committed roster plus the manifest date so neither id can rot, and
 *  the departed case prefers C001078 (Connolly, died in office 2025-05-21) when it is
 *  present, since that is the case the owner named.
 *
 *  These exist because `member.serving` stays TRUE for a mid-term departure: it means
 *  "the latest term overlapped the latest covered Congress". 16 members matched that on
 *  2026-10-09, and the member page's "No longer serving." note was suppressed for every
 *  one of them. */
function membersBySeatStatus(): { departed: string; sitting: string } {
  const asOf = JSON.parse(
    fs.readFileSync(path.join(DATA, "manifest.json"), "utf-8")).generated_at.slice(0, 10);
  const dir = path.join(DATA, "members");
  const departed: string[] = [];
  const sitting: string[] = [];
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".json")).sort()) {
    const m = JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8"));
    if (m.jurisdiction !== "us") continue;
    const holds = (m.terms ?? []).some((t: { start: string; end: string }) =>
      t.start <= asOf && asOf <= t.end);
    // Only members the page actually prints the line for (it needs an in-office-since date).
    if ((m.terms ?? []).length === 0) continue;
    (holds ? sitting : departed).push(m.id);
  }
  if (departed.length === 0 || sitting.length === 0) {
    throw new Error("roster has no departed/sitting pair to test the seat-status note");
  }
  return {
    departed: departed.includes("C001078") ? "C001078" : departed[0],
    sitting: sitting[0],
  };
}

export const SEAT_STATUS = membersBySeatStatus();

export const PAGES: string[] = [
  "/",
  "/congress", // P2: the full ranked "In Congress" list
  "/federal", // V2-5: the filterable federal-members browser (Preact island)
  "/topics", // V2-11: the topic index (both official vocabularies)
  topics.policyArea, // V2-11: the largest policy area
  topics.subject, // V2-11: the largest subject term
  "/compare", // V2-5: the compare view (bare — the picker + prompt, JS-rendered)
  "/states", // V2-5: the States tab
  `/m/${firstByChamber("house")}/1`, // P2 acceptance: a House member page
  `/m/${firstByChamber("senate")}/1`, // P2 acceptance: a Senate member page
  `/m/${firstDelegateId()}/1`, // V2-3: a delegate page (mixed ranked/unranked tiles)
  `/v/${rv.roll}`,
  `/b/${rv.bill}`,
  "/methods",
  "/corrections",
  "/privacy",
  "/pairing",
  "/ms",
  `/ms/m/${firstMsMemberId()}/1`,
  `/ms/v/${msv.roll}`,
  `/ms/b/${msv.bill}`,
];
