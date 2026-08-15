// Representative page URLs, computed from the committed dataset so the E2E suite
// always targets pages that actually exist (no hardcoded ids that rot).
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DATA = fileURLToPath(new URL("../../data/", import.meta.url));

function firstJson(sub: string): any {
  const dir = path.join(DATA, sub);
  const f = fs.readdirSync(dir).filter((x) => x.endsWith(".json")).sort()[0];
  return JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8"));
}

function firstMemberId(): string {
  return firstJson("members").id;
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

export const PAGES: string[] = [
  "/",
  "/federal", // V2-5: the filterable federal-members browser (Preact island)
  "/compare", // V2-5: the compare view (bare — the picker + prompt, JS-rendered)
  "/states", // V2-5: the States tab
  `/m/${firstMemberId()}/1`,
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
