// INC-8 acceptance: "every rendered claim traces to a source_url present in
// data." Over the built static output, assert each vote page and each bill page
// contains its record's official source_url. A plain string check over dist/ —
// no browser, cheap enough to run on every page. Exit nonzero on any miss.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DATA = path.join(ROOT, "..", "data");
const DIST = path.join(ROOT, "dist");

// href attributes HTML-encode "&" as "&amp;"; match either form.
function htmlContains(html, url) {
  return html.includes(url) || html.includes(url.replaceAll("&", "&amp;"));
}

function readHtml(...segs) {
  const p = path.join(DIST, ...segs, "index.html");
  return fs.existsSync(p) ? fs.readFileSync(p, "utf-8") : null;
}

function listJson(sub) {
  const dir = path.join(DATA, sub);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((f) => f.endsWith(".json"));
}

let checked = 0;
const misses = [];

for (const f of listJson("votes")) {
  const rec = JSON.parse(fs.readFileSync(path.join(DATA, "votes", f), "utf-8"));
  const { id, source_url } = rec.rollcall;
  const html = readHtml("v", id);
  if (html === null) { misses.push(`v/${id}: no page built`); continue; }
  if (!htmlContains(html, source_url)) misses.push(`v/${id}: missing source_url ${source_url}`);
  checked++;
}

// Bills: owner decision SD-33 3(c) — the dataset TRACKS every bill in the
// covered Congresses (38,756), but only the ones that reached a recorded vote
// get a page. So the INC-8 guarantee is restated, not relaxed: "every rendered
// claim traces to a source_url" — a bill with no page renders no claim.
//
// The check is STRONGER than the one it replaces, because skipping absent pages
// alone would let a bill that SHOULD have a page lose it silently. It asserts
// the built set is EXACTLY the voted set, in both directions.
const votedBillIds = new Set();
for (const f of listJson("votes")) {
  const rec = JSON.parse(fs.readFileSync(path.join(DATA, "votes", f), "utf-8"));
  if (rec.rollcall.bill_id) votedBillIds.add(rec.rollcall.bill_id);
}

let pageless = 0;
for (const f of listJson("bills")) {
  const b = JSON.parse(fs.readFileSync(path.join(DATA, "bills", f), "utf-8"));
  const html = readHtml("b", b.id);
  if (!votedBillIds.has(b.id)) {
    // Tracked but never voted on: must NOT have a page (3(c)). Reachable
    // through its source_url on congress.gov instead.
    if (html !== null) misses.push(`b/${b.id}: page built for a bill with no recorded vote (SD-33 3(c))`);
    else pageless++;
    continue;
  }
  if (html === null) { misses.push(`b/${b.id}: no page built, but it HAS a recorded vote`); continue; }
  if (!htmlContains(html, b.source_url)) misses.push(`b/${b.id}: missing source_url ${b.source_url}`);
  checked++;
}

// Mississippi state layer (INC-12): the same guarantee over /ms/v and /ms/b pages.
function listStateJson(sub) {
  const dir = path.join(DATA, "state", "ms", sub);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((f) => f.endsWith(".json"));
}
for (const f of listStateJson("votes")) {
  const rec = JSON.parse(fs.readFileSync(path.join(DATA, "state", "ms", "votes", f), "utf-8"));
  const { id, source_url } = rec.rollcall;
  const html = readHtml("ms", "v", id);
  if (html === null) { misses.push(`ms/v/${id}: no page built`); continue; }
  if (!htmlContains(html, source_url)) misses.push(`ms/v/${id}: missing source_url ${source_url}`);
  checked++;
}
for (const f of listStateJson("bills")) {
  const b = JSON.parse(fs.readFileSync(path.join(DATA, "state", "ms", "bills", f), "utf-8"));
  const html = readHtml("ms", "b", b.id);
  if (html === null) { misses.push(`ms/b/${b.id}: no page built`); continue; }
  if (!htmlContains(html, b.source_url)) misses.push(`ms/b/${b.id}: missing source_url ${b.source_url}`);
  checked++;
}

if (misses.length) {
  console.error(`source-link check FAILED — ${misses.length} miss(es):`);
  for (const m of misses.slice(0, 40)) console.error(`  ${m}`);
  process.exit(1);
}
console.log(
  `source-link check OK — ${checked} vote+bill pages each cite their source_url` +
  (pageless ? `; ${pageless} tracked bill(s) with no recorded vote correctly have no page (SD-33 3(c)).` : ".")
);
