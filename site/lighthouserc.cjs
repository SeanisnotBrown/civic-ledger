// Lighthouse CI — mobile performance gate (INC-9 acceptance, §6.7: mobile perf
// >= 90). Runs against `astro preview` (the static build). URLs are derived from
// committed data so the config never targets a page that doesn't exist. Lighthouse
// defaults to mobile emulation (Moto G4 / throttled), which is exactly "mobile".
const fs = require("node:fs");
const path = require("node:path");

const DATA = path.join(__dirname, "..", "data");
const BASE = "http://localhost:4321";

function firstJson(sub) {
  const dir = path.join(DATA, sub);
  const f = fs.readdirSync(dir).filter((x) => x.endsWith(".json")).sort()[0];
  return JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8"));
}

// A vote page with delegation positions + an ingested bill link (heaviest MVP page).
function richVote() {
  const dir = path.join(DATA, "votes");
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith(".json")).sort()) {
    const v = JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8"));
    if (v.member_votes.length && v.rollcall.bill_id &&
        fs.existsSync(path.join(DATA, "bills", `${v.rollcall.bill_id}.json`))) {
      return { roll: v.rollcall.id, bill: v.rollcall.bill_id };
    }
  }
  throw new Error("no representative vote for lighthouse");
}

const member = firstJson("members").id;
const rv = richVote();

// Heaviest MS page: a legislator's paginated vote list (INC-12).
function firstMsMember() {
  const dir = path.join(DATA, "state", "ms", "members");
  const f = fs.readdirSync(dir).filter((x) => x.endsWith(".json")).sort()[0];
  return JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8")).id;
}
const msMember = firstMsMember();

module.exports = {
  ci: {
    collect: {
      startServerCommand: "npm run preview -- --port 4321",
      url: [
        `${BASE}/`,
        `${BASE}/m/${member}/1`,
        `${BASE}/v/${rv.roll}`,
        `${BASE}/b/${rv.bill}`,
        `${BASE}/methods`,
        `${BASE}/ms`,
        `${BASE}/ms/m/${msMember}/1`,
      ],
      numberOfRuns: 3, // median smooths shared-runner CPU variance
    },
    assert: {
      assertions: {
        // Mobile performance is the INC-9 gate; a11y is already covered by axe,
        // asserted here too as a cheap belt-and-suspenders.
        "categories:performance": ["error", { minScore: 0.9 }],
        "categories:accessibility": ["error", { minScore: 0.9 }],
      },
    },
  },
};
