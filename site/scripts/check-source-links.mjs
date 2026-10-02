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

// V2-11 task 7 — the SD-33 3(c) link rule on every surface that lists bills.
//
// The rule: a bill that reached a recorded vote has a /b/ page and must be linked to
// it; a bill without one must be linked to its own source_url on congress.gov, NEVER
// to a /b/ URL that was never built. The plan makes this check the enforcement ("fails
// on the first violation"), so it has to cover the new surfaces, not just /b/ pages.
//
// Topic pages carry `data-bill-id` on each row precisely so this can check both
// directions per row rather than only spotting a wrong /b/ link.
const billIdShape = /^[a-z]+\d+-\d+$/;
const billSourceUrl = new Map();
for (const f of listJson("bills")) {
  const b = JSON.parse(fs.readFileSync(path.join(DATA, "bills", f), "utf-8"));
  billSourceUrl.set(b.id, b.source_url);
}

function distFiles(sub, predicate) {
  const out = [];
  const root = path.join(DIST, sub);
  if (!fs.existsSync(root)) return out;
  (function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(p);
      else if (predicate(entry.name)) out.push(p);
    }
  })(root);
  return out;
}

let topicRows = 0;
const topicPages = distFiles("topics", (n) => n === "index.html");
for (const file of topicPages) {
  const html = fs.readFileSync(file, "utf-8");
  const rel = path.relative(DIST, file);
  for (const m of html.matchAll(/data-bill-id="([^"]+)"/g)) {
    const id = m[1];
    topicRows++;
    const linksToPage = html.includes(`href="/b/${id}"`);
    if (votedBillIds.has(id)) {
      if (!linksToPage) misses.push(`${rel}: ${id} has a page but the row does not link to /b/${id}`);
    } else {
      if (linksToPage) misses.push(`${rel}: ${id} has NO page but the row links to /b/${id} (SD-33 3(c))`);
      const src = billSourceUrl.get(id);
      if (src && !htmlContains(html, src)) {
        misses.push(`${rel}: ${id} has no page and the row does not cite its source_url ${src}`);
      }
    }
  }
}

// Feeds: every entry's alternate link obeys the same rule. An entry id is
// `{bill_id}--{date}--{hash}` for an action and `{rollcall_id}--{member_id}` for a
// vote, so only the ones whose first segment is shaped like a bill id are bill rows.
let feedEntries = 0;
const feeds = [
  ...(fs.existsSync(path.join(DIST, "feed.xml")) ? [path.join(DIST, "feed.xml")] : []),
  ...distFiles("b", (n) => n === "feed.xml"),
  ...distFiles("topics", (n) => n === "feed.xml"),
  ...distFiles("m", (n) => n === "feed.xml"),
];
for (const file of feeds) {
  const xml = fs.readFileSync(file, "utf-8");
  const rel = path.relative(DIST, file);
  for (const entry of xml.matchAll(/<entry>([\s\S]*?)<\/entry>/g)) {
    const body = entry[1];
    const idm = /<id>tag:civicledger\.net,\d+:([^<]+)<\/id>/.exec(body);
    const linkm = /<link rel="alternate" type="text\/html" href="([^"]+)"\/>/.exec(body);
    if (!idm || !linkm) { misses.push(`${rel}: an entry is missing its id or alternate link`); continue; }
    const billId = idm[1].split("--")[0];
    if (!billIdShape.test(billId)) continue; // a vote entry, checked by the /v/ pages
    feedEntries++;
    const href = linkm[1];
    if (votedBillIds.has(billId)) {
      if (!href.endsWith(`/b/${billId}`)) {
        misses.push(`${rel}: ${billId} has a page but its entry links to ${href}`);
      }
    } else {
      if (/\/b\//.test(href)) {
        misses.push(`${rel}: ${billId} has NO page but its entry links to ${href} (SD-33 3(c))`);
      }
      const src = billSourceUrl.get(billId);
      if (src && href !== src) {
        misses.push(`${rel}: ${billId} has no page; entry links to ${href}, not its source_url ${src}`);
      }
    }
  }
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
  (pageless ? `; ${pageless} tracked bill(s) with no recorded vote correctly have no page (SD-33 3(c))` : "") +
  `; ${topicRows} topic-page row(s) across ${topicPages.length} topic page(s) and ` +
  `${feedEntries} bill entry/entries across ${feeds.length} feed(s) link by the same rule.`
);
