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

export const PAGES: string[] = [
  "/",
  `/m/${firstMemberId()}/1`,
  `/v/${rv.roll}`,
  `/b/${rv.bill}`,
  "/methods",
  "/corrections",
];
