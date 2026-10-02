import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { billWithActions, topicPaths } from "./fixtures";

// V2-11 task 7 acceptance: "feed validates against the Atom schema".
//
// Parsed with the browser's own XML parser rather than a schema library, because a
// feed reader's failure mode IS a parse failure: a stray `&` in a government action
// text, or an unescaped quote in a title, produces a document no client can read.
// `DOMParser` surfaces exactly that as a <parsererror> node.
//
// Two things beyond well-formedness are asserted, and both are rules this build can
// silently break:
//   * `<updated>` is RFC 3339 — Atom requires it, and the stored record dates are
//     plain `YYYY-MM-DD`, so the conversion has to happen.
//   * `<updated>` is NOT today. The feeds carry no build wall-clock (§6.3): a feed
//     stamped at build time changes on every rebuild and re-notifies every subscriber
//     for nothing. A date equal to today is the symptom.

const DATA = fileURLToPath(new URL("../../data/", import.meta.url));
const RFC3339 = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;

function firstMemberId(): string {
  const dir = path.join(DATA, "members");
  const f = fs.readdirSync(dir).filter((x) => x.endsWith(".json")).sort()[0];
  return JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8")).id;
}

const billId = billWithActions();
const topics = topicPaths();

const FEEDS: { label: string; url: string }[] = [
  { label: "site-wide", url: "/feed.xml" },
  { label: "policy area", url: `${topics.policyArea}/feed.xml` },
  { label: "subject term", url: `${topics.subject}/feed.xml` },
  { label: "member", url: `/m/${firstMemberId()}/feed.xml` },
  ...(billId ? [{ label: "bill", url: `/b/${billId}/feed.xml` }] : []),
];

/** Fetch a feed as text and parse it in the page context. */
async function parseFeed(page: any, url: string) {
  const res = await page.request.get(url);
  expect(res.status(), `${url} should be served`).toBe(200);
  // An XML content type, not specifically application/atom+xml: this is a STATIC
  // build, so the endpoint's own header is a build-time artifact and the serving
  // layer decides what a .xml file is sent as (astro preview says text/xml). Feed
  // readers sniff the document, and every one of them accepts an XML type — what
  // must not happen is text/html or application/octet-stream.
  expect(res.headers()["content-type"]).toMatch(/xml/);
  const xml = await res.text();

  return page.evaluate((text: string) => {
    const NS = "http://www.w3.org/2005/Atom";
    const doc = new DOMParser().parseFromString(text, "application/xml");
    const err = doc.querySelector("parsererror");
    if (err) return { parseError: err.textContent ?? "unknown parse error" };
    const feed = doc.documentElement;
    const get = (el: Element, tag: string) =>
      el.getElementsByTagNameNS(NS, tag)[0]?.textContent ?? null;
    const entries = Array.from(doc.getElementsByTagNameNS(NS, "entry")).map((e) => ({
      id: get(e, "id"),
      title: get(e, "title"),
      updated: get(e, "updated"),
      content: get(e, "content"),
      link: e.getElementsByTagNameNS(NS, "link")[0]?.getAttribute("href") ?? null,
    }));
    return {
      parseError: null,
      root: feed.localName,
      ns: feed.namespaceURI,
      id: get(feed, "id"),
      title: get(feed, "title"),
      updated: get(feed, "updated"),
      author: feed.getElementsByTagNameNS(NS, "author")[0]?.textContent?.trim() ?? null,
      entries,
    };
  }, xml);
}

for (const { label, url } of FEEDS) {
  test(`${label} feed is valid Atom: ${url}`, async ({ page }) => {
    // DOMParser lives in the page, so a document has to be loaded first.
    await page.goto("/topics");
    const feed = await parseFeed(page, url);

    expect(feed.parseError, `${url} did not parse as XML`).toBeNull();
    expect(feed.root).toBe("feed");
    expect(feed.ns).toBe("http://www.w3.org/2005/Atom");

    // RFC 4287 requires id, title, updated and an author on the feed.
    expect(feed.id).toBeTruthy();
    expect(feed.id).toMatch(/^https:\/\/civicledger\.net\//);
    expect(feed.title).toBeTruthy();
    expect(feed.author).toBeTruthy();
    expect(feed.updated, `${url} <updated> must be RFC 3339`).toMatch(RFC3339);

    // No build wall-clock anywhere (§6.3). Published data is at least a day old by
    // the time it is built and deployed, so an <updated> of today is the signature of
    // a `new Date()` that should not exist.
    const today = new Date().toISOString().slice(0, 10);
    expect(feed.updated!.slice(0, 10), `${url} is stamped with the build date`).not.toBe(today);

    for (const e of feed.entries) {
      expect(e.id, `${url} entry needs an id`).toBeTruthy();
      expect(e.id).toMatch(/^tag:civicledger\.net,\d{4}:/);
      expect(e.title).toBeTruthy();
      expect(e.updated, `${url} entry <updated> must be RFC 3339`).toMatch(RFC3339);
      expect(e.link, `${url} entry needs an alternate link`).toBeTruthy();
    }
  });
}

test("a bill feed carries the government's action text verbatim", async ({ page }) => {
  test.skip(billId === null, "no bill in this dataset has both a page and a timeline yet");
  const bill = JSON.parse(
    fs.readFileSync(path.join(DATA, "bills", `${billId}.json`), "utf-8"));
  await page.goto("/topics");
  const feed = await parseFeed(page, `/b/${billId}/feed.xml`);

  expect(feed.parseError).toBeNull();
  expect(feed.entries.length).toBeGreaterThan(0);
  // The newest stored action is the first entry, and its content is the stored text
  // character for character — not shortened, not reworded (§0.5).
  expect(feed.entries[0].content).toBe(bill.actions[0].text);
  expect(feed.entries[0].updated.slice(0, 10)).toBe(bill.actions[0].date);
});

test("feeds are byte-identical across two fetches (no wall-clock)", async ({ page }) => {
  await page.goto("/topics");
  const a = await page.request.get("/feed.xml");
  const b = await page.request.get("/feed.xml");
  expect(await a.text()).toBe(await b.text());
});
