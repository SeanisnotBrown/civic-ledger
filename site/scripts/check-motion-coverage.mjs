// Gate: every roll-call question in data/votes/ either matches the fixed motion
// table (src/lib/motions.ts) or is reported here with its count.
//
// An unmatched question is NOT a failure — the table is deliberately silent
// rather than guessing (Rule 0), and a new motion type can appear in the record
// at any time. What this gate fails on is a REGRESSION: coverage below the
// ratified floor, or one of the known traps mapping to the wrong kind.
//
// Run: npm run test:motions
import { readdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { motionMeaning, resolvesMeasure } from "../src/lib/motions.ts";

const here = dirname(fileURLToPath(import.meta.url));
const votesDir = join(here, "..", "..", "data", "votes");

// Share of roll calls that must carry a meaning line. Measured at 99.7% when
// the table shipped; the floor leaves room for new motion types in the record.
const MIN_COVERAGE = 0.985;

// The traps. Each must map to this kind or the ordering of the table has broken.
const TRAPS = [
  ["Passage, Objections of the President To The Contrary Notwithstanding", "veto_override"],
  ["On Motion to Table the Motion to Discharge Committee", "table"],
  ["Table Motion to Reconsider", "table_reconsider"],
  ["On Motion to Table the Motion to Reconsider", "table_reconsider"],
  ["On Motion to Table", "table"],
  ["On Cloture on the Motion to Proceed H.R. 5371", "cloture"],
  ["On Motion to Suspend the Rules and Concur in the Senate Amendment", "suspension"],
  ["On Motion to Concur in the Senate Amendment", "concur"],
  ["On Agreeing to the Amendment", "amendment"],
  ["On Motion to Recommit", "recommit"],
  ["On Ordering the Previous Question", "previous_question"],
  ["On the Motion (Wyden Motion to Commit S. 1582)", "commit"],
  ["On Passage", "passage"],
  ["On the Nomination PN27", "nomination"],
  ["On the Conference Report H.R. 2670", "conference_report"],
  ["On the Motion (Motion to Waive the Rule 28 Point of Order Re: Section 7902 of the Conference Report to Accompany H.R. 2670)", "waiver"],
  ["On Agreeing to the Resolution", "resolution"],
];

// A roll call whose question does NOT resolve the measure must never be
// publishable as a bill's passage margin.
const NOT_RESOLVING = [
  "On Agreeing to the Amendment",
  "On the Amendment S.Amdt. 6828 to S.Amdt. 6776 to S. 4668",
  "On Ordering the Previous Question",
  "On Motion to Recommit",
  "On the Cloture Motion H.R. 815",
  "On the Motion to Proceed H.R. 3935",
];

let failures = 0;
const fail = (msg) => { console.log(`FAIL: ${msg}`); failures++; };

for (const [q, want] of TRAPS) {
  const got = motionMeaning(q)?.kind ?? null;
  if (got !== want) fail(`"${q}" -> ${got}, expected ${want}`);
}
for (const q of NOT_RESOLVING) {
  if (resolvesMeasure(q)) fail(`"${q}" is treated as resolving the measure`);
}
// Every meaning line must name both sides, or a reader can invert it wrongly.
for (const q of TRAPS.map(([q]) => q)) {
  const m = motionMeaning(q);
  if (m && m.meaning && !/\bNay\b/.test(m.meaning) && !/not a vote|proceedings|does not change/i.test(m.meaning)) {
    fail(`"${q}" meaning line does not say what a Nay does`);
  }
}

const counts = new Map();
let total = 0;
let matched = 0;
for (const f of readdirSync(votesDir)) {
  if (!f.endsWith(".json")) continue;
  const rc = JSON.parse(readFileSync(join(votesDir, f), "utf8")).rollcall;
  const q = rc.question ?? "";
  total++;
  if (motionMeaning(q)) matched++;
  else counts.set(q, (counts.get(q) ?? 0) + 1);
}

const coverage = total ? matched / total : 1;
console.log(`motions: ${matched} of ${total} roll calls carry a meaning line (${(coverage * 100).toFixed(1)}%)`);
if (counts.size) {
  const rows = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  const shown = rows.slice(0, 20);
  console.log(`no line (${counts.size} distinct questions, ${rows.reduce((t, r) => t + r[1], 0)} roll calls):`);
  for (const [q, n] of shown) console.log(`  ${String(n).padStart(4)} | ${q}`);
  if (rows.length > shown.length) console.log(`  ... and ${rows.length - shown.length} more`);
}
if (coverage < MIN_COVERAGE) {
  fail(`coverage ${(coverage * 100).toFixed(1)}% is below the ${(MIN_COVERAGE * 100).toFixed(1)}% floor`);
}

if (failures) {
  console.log(`\n${failures} failure(s).`);
  process.exit(1);
}
console.log("OK");
