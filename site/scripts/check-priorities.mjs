// P3 task 6 render-side guard: the "Stated priorities" panel on every member page agrees
// with data/priorities.json, which applies the owner's Q-B bar and Q-J rules in Python.
//
//   * A member BELOW the Q-B bar (or with no approved statement, i.e. absent from the
//     file) shows the empty state and never a list: below the bar nothing is inferred.
//   * A member at or above it shows the list, or the plain "none meets the rule yet" line —
//     but only once the list wording (AES-14) is ratified (`list_wording_ratified`, owner
//     ruling 9, 2026-10-23). Until then NO page renders a list; a qualifying member shows
//     the "held for review" line.
//   * No member page promises a statement "beside how they voted": say-vs-do comparison
//     is Phase 6, and copy may not claim it before it exists (rule 0).
//
// Run after `npm run build`, like the other dist gates.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DIST_M = path.join(ROOT, "dist", "m");
const PRIORITIES = path.join(ROOT, "..", "data", "priorities.json");

const file = JSON.parse(readFileSync(PRIORITIES, "utf-8"));
const failures = [];
let pages = 0;
let listed = 0;

for (const id of existsSync(DIST_M) ? readdirSync(DIST_M) : []) {
  const page = path.join(DIST_M, id, "1", "index.html");
  if (!existsSync(page)) continue;
  pages += 1;
  const html = readFileSync(page, "utf-8");
  const entry = file.members[id];
  if (!file.list_wording_ratified && html.includes("data-priorities-list")) {
    failures.push(`${id}: a priorities list renders before its wording (AES-14) is ratified`);
  }
  if (entry?.listed) {
    listed += 1;
    const want = file.list_wording_ratified
      ? html.includes("data-priorities-list") || html.includes("data-priorities-none")
      : html.includes("data-priorities-held");
    if (!want) failures.push(`${id}: clears the Q-B bar but shows the wrong panel`);
  } else {
    if (!html.includes("data-priorities-empty")) {
      failures.push(`${id}: below the Q-B bar but the empty state is missing`);
    }
    if (html.includes("data-priorities-list")) {
      failures.push(`${id}: below the Q-B bar but a priorities list is rendered`);
    }
  }
  if (/beside how they voted/i.test(html)) {
    failures.push(`${id}: copy claims a say-vs-do comparison that does not exist yet`);
  }
}

if (pages === 0) failures.push("no member pages found under dist/m/ — run `npm run build` first");
if (failures.length) {
  console.error(`check-priorities: ${failures.length} failure(s)`);
  for (const f of failures.slice(0, 40)) console.error(`  ${f}`);
  process.exit(1);
}
console.log(`check-priorities: OK (${pages} member pages; ${listed} with a list, ` +
  `${pages - listed} showing the Q-B empty state)`);
