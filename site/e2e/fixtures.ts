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

export const PAGES: string[] = [
  "/",
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
