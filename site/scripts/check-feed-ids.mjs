// SD-37 render-side guard. Every built Atom feed must carry each `<id>` AT MOST ONCE.
//
// Why this is a build gate and not a unit test: congress.gov lists some action rows
// twice byte-for-byte (D100), `bill_actions` keeps every copy the government's list
// has, and `entryId()` hashes the whole row — so byte-identical rows necessarily
// produce the same `atom:id`. Two entries sharing an id is malformed in effect: a
// reader may collapse them into one, or notify twice, and `entryId()` is byte-equal
// to `ingest.events.event_id`, the identity the V2-12 alert path keys on (D97). A
// duplicate therefore becomes a subscriber notified twice for one government action.
//
// `actionEntries()` in src/lib/atom.ts de-duplicates, and this script is the proof
// that it actually did on every one of the five feed shapes (/feed.xml,
// /b/{bill}/feed.xml, /m/{member}/feed.xml, and both topic vocabularies) rather than
// on the shapes someone remembered to check. It scans dist/, so it runs AFTER
// `npm run build` — the same pair-of-halves pattern as check-grade-labels.mjs.
//
// The feed `<id>` element also appears once per FEED, not only per entry, and that
// one is the feed's own self URL. Only ids inside an <entry> are checked.
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DIST = path.join(ROOT, "dist");

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (name.endsWith("feed.xml")) out.push(full);
  }
  return out;
}

let feeds;
try {
  feeds = walk(DIST);
} catch {
  console.error(`FAIL: ${DIST} not found — run \`npm run build\` first.`);
  process.exit(1);
}

if (feeds.length === 0) {
  console.error("FAIL: no feed.xml files found in dist/ — the feeds stopped building.");
  process.exit(1);
}

let entries = 0;
const offenders = [];
for (const file of feeds) {
  const xml = readFileSync(file, "utf-8");
  const seen = new Map();
  // One <entry> block at a time, so a feed's own self-<id> is never counted.
  for (const block of xml.matchAll(/<entry>([\s\S]*?)<\/entry>/g)) {
    const m = block[1].match(/<id>([^<]+)<\/id>/);
    if (!m) {
      offenders.push(`${path.relative(ROOT, file)}: an <entry> has no <id>`);
      continue;
    }
    entries += 1;
    seen.set(m[1], (seen.get(m[1]) ?? 0) + 1);
  }
  for (const [id, n] of seen) {
    if (n > 1) offenders.push(`${path.relative(ROOT, file)}: <id>${id}</id> appears ${n}x`);
  }
}

if (offenders.length > 0) {
  console.error(`FAIL: duplicate Atom entry ids in ${offenders.length} place(s) (SD-37):`);
  for (const line of offenders.slice(0, 20)) console.error(`  ${line}`);
  if (offenders.length > 20) console.error(`  … and ${offenders.length - 20} more`);
  process.exit(1);
}

console.log(`OK: ${entries} entries across ${feeds.length} feed(s), no duplicate ids.`);
