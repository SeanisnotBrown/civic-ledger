// SD-37 render-side guard, bill-page half. On every built /b/ page, the action
// timeline must list each action AT MOST ONCE, and any collapsed row must carry
// the owner's ratified sentence.
//
// Why a dist gate and not a unit test: `timelineRows()` in src/lib/actions.ts
// does the collapsing, but what the reader sees is HTML, and the two halves of
// SD-37 have to agree — the feed emits one entry per distinct action id
// (check-feed-ids.mjs) and the page it links to must show the same action once.
// The companion to that script, same pattern, same place in CI (after
// `npm run build`).
//
// The teeth are data-independent on purpose. A test pinned to "hr1516-118 has
// one repeat" stops meaning anything the day the government edits that record;
// this asserts the invariant instead — no two rendered rows in one timeline are
// byte-identical — so it keeps working as the backfill brings in bills nobody
// has looked at. The wording check is the other half: a collapsed row with no
// note, or a note that is not the sentence the owner ratified, is the page
// quietly editing the record down.
//
// What it does NOT check, deliberately: that the header count equals the number
// of rows. SD-37's scope guard is that those two numbers DISAGREE whenever a
// repeat exists — the count is what the record lists, the rows are what is
// shown.
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DIST = path.join(ROOT, "dist");
const BILLS = path.join(DIST, "b");

// The ratified sentence, SD-37: "The official record lists this action 4 times."
const NOTE = /The official record lists this action (\d+) times\./;

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (name === "index.html") out.push(full);
  }
  return out;
}

let pages;
try {
  pages = walk(BILLS);
} catch {
  console.error(`FAIL: ${BILLS} not found — run \`npm run build\` first.`);
  process.exit(1);
}

if (pages.length === 0) {
  console.error("FAIL: no /b/ pages found in dist/ — the bill pages stopped building.");
  process.exit(1);
}

let rowCount = 0;
let collapsed = 0;
let timelines = 0;
const offenders = [];
for (const file of pages) {
  const html = readFileSync(file, "utf-8");
  const where = path.relative(DIST, file);
  // The timeline is the only <ol> on the page, and each action is one <li>.
  const list = html.match(/<ol class="mt-2 divide-y[^"]*">([\s\S]*?)<\/ol>/);
  if (!list) continue; // a bill whose timeline is uncollected renders a <p>, not a list
  timelines += 1;
  const seen = new Map();
  for (const li of list[1].matchAll(/<li class="py-2 text-sm">([\s\S]*?)<\/li>/g)) {
    const row = li[1];
    rowCount += 1;
    // Strip the note before hashing: two rows that differ ONLY in their counts
    // are still the same action rendered twice, which is the bug being hunted.
    const identity = row.replace(NOTE, "").replace(/\s+/g, " ").trim();
    seen.set(identity, (seen.get(identity) ?? 0) + 1);
    const note = row.match(NOTE);
    if (note) {
      collapsed += 1;
      if (Number(note[1]) < 2) {
        offenders.push(`${where}: a row says the record lists it ${note[1]} times`);
      }
    }
  }
  for (const [identity, n] of seen) {
    if (n > 1) {
      offenders.push(
        `${where}: an identical action row is rendered ${n}x — ` +
          `${identity.slice(0, 120)}…`,
      );
    }
  }
}

// A markup change that defeats the selectors above would make this script find
// nothing and exit 0. A gate that passes by seeing nothing is worse than no gate,
// so seeing nothing is itself the failure. Negative-tested by changing one class.
if (timelines === 0 || rowCount === 0) {
  console.error(
    `FAIL: parsed ${timelines} timeline(s) and ${rowCount} action row(s) out of ` +
      `${pages.length} bill page(s). Hundreds of those pages carry a timeline, so ` +
      "this means the selectors in this script no longer match the markup — not " +
      "that the repeats are gone. Fix the selectors.",
  );
  process.exit(1);
}

if (offenders.length > 0) {
  console.error(`FAIL: SD-37 violations on ${offenders.length} row(s):`);
  for (const line of offenders.slice(0, 20)) console.error(`  ${line}`);
  if (offenders.length > 20) console.error(`  … and ${offenders.length - 20} more`);
  process.exit(1);
}

console.log(
  `OK: ${rowCount} action rows across ${timelines} timeline(s) of ` +
    `${pages.length} bill page(s), ` +
    `no action rendered twice; ${collapsed} row(s) carry the repeat note.`,
);
