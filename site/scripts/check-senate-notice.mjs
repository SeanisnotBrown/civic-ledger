// Senate outage notice (owner ruling 2026-10-29). While data/quality/senate-outage.json
// exists, the owner's line is rendered, word for word, beside "Data last updated" in
// the footer and beside "Dataset last updated" on the homepage, with both dates taken
// from the notice. Without the file, no page carries it (rule 0: the line must stop
// the night the Senate ingest succeeds again).
//
// Run after `npm run build`, like the other dist gates.
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { senateOutageLine } from "../src/lib/display.ts";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DIST = path.join(ROOT, "dist");
const NOTICE = path.join(ROOT, "..", "data", "quality", "senate-outage.json");
// Pages that must carry the line: the homepage (both spots) and one ordinary page
// (footer only).
const PAGES = ["index.html", path.join("methods", "index.html")];
const MARK = "senate.gov has blocked our automated requests";

const failures = [];

// The wording, pinned to the owner's sentence for the outage that prompted the ruling.
const OWNER =
  "Senate votes shown through Sep 30, 2026. Since Oct 24, senate.gov has blocked our " +
  "automated requests, so newer Senate votes may not appear yet.";
const got = senateOutageLine({ last_roll_date: "2026-09-30", outage_start: "2026-10-24" });
if (got !== OWNER) failures.push(`wording drifted:\n  got:  ${got}\n  want: ${OWNER}`);

const notice = existsSync(NOTICE) ? JSON.parse(readFileSync(NOTICE, "utf-8")) : null;
const line = notice ? senateOutageLine(notice) : null;
for (const rel of PAGES) {
  const file = path.join(DIST, rel);
  if (!existsSync(file)) {
    failures.push(`${rel}: not built`);
    continue;
  }
  const html = readFileSync(file, "utf-8");
  const count = html.split(MARK).length - 1;
  const want = !notice ? 0 : rel === "index.html" ? 2 : 1;
  if (count !== want) failures.push(`${rel}: notice appears ${count} time(s), expected ${want}`);
  if (line && !html.includes(line)) failures.push(`${rel}: full line from the notice not found`);
}

if (failures.length) {
  console.error("SENATE-NOTICE CHECK FAILED:");
  for (const f of failures) console.error(`  ${f}`);
  process.exit(1);
}
console.log(
  notice
    ? `senate-notice: line rendered from the notice on ${PAGES.length} page(s): ${line}`
    : "senate-notice: no notice file, no line on any checked page.",
);
