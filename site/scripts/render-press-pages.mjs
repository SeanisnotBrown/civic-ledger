// Renders a congressional press-release LIST page with a real browser and hands the
// HTML back, for the rows a plain GET cannot read (STATUS fact 7).
//
// Why this exists: eleven of the forty pilot rows publish their release list from
// JavaScript. The HTML a plain GET returns carries the right <title> and ZERO dated
// items, so `ingest/statements_press.py`'s extractor reads nothing and the member
// contributes no press statements at all. Playwright and its Chromium are already in
// this package for `test:e2e`, so rendering costs no new dependency — and none is
// added on the Python side either.
//
// WHAT THIS SCRIPT DOES NOT DO, deliberately:
//   * It does not paginate. `page_url`, `zero_based_pager` and `extract_releases` are
//     rules that live in statements_press.py, and a second copy here would be a second
//     thing to keep right. The Python driver (`ingest/press_render.py`) owns the walk
//     and feeds this script one URL at a time.
//   * It does not write the cache. The driver writes it through `ingest/cache.py`, so
//     the cache key and the `.meta` shape have exactly one definition. A plain
//     `uv run ingest statements-press` then consumes those entries unchanged.
//   * It does not decide WHEN to stop clicking "load more". It clicks ONCE per request
//     and reports what changed; the driver owns the stop rules, because they are date
//     rules (is the oldest item older than 2023-01-03?) and dates have one definition,
//     in statements_press.py. A copy of them here would be a second one to keep right.
//
// Protocol — JSON Lines over stdin/stdout, one browser for the whole session:
//   in:  {"url": "https://..."}        render a page; it stays OPEN for `more`
//   out: {"url": "...", "ok": true,  "status": 200, "html": "...", "anchors": 41,
//         "templated": 0}
//        {"url": "...", "ok": false, "status": 404, "error": "..."}
//   in:  {"more": true}                advance the page that is already open, once
//   out: {"ok": true, "clicked": true, "grew": true, "anchors": 61, "control": "...",
//         "nearby": ["<button …>", …], "html": "..."}
// `ok: false` means DO NOT CACHE THIS. A render that timed out is not a page, and
// caching it would serve a 7-day-fresh empty list to the plain collector.
//
// `more` is one "advance": scroll to the bottom (several of these lists only build
// their control once it is in view), click the row's own load-more control if there is
// one, and wait for the anchor count to change. `grew: false` is how the driver learns
// the control has stopped adding items — or was never there, which `control: null` and
// the `nearby` diagnostic distinguish, so a row that cannot be clicked says what it has
// instead rather than coming back as a silent zero.
//
// Run on demand only. CI cannot run it: the `python` job has no Node, and the pages
// are live third-party sites. The entries it produces are refreshed by hand.
import { chromium } from "@playwright/test";
import { createInterface } from "node:readline";

// Long enough for a client-side list to fetch and paint, short enough that a dead
// site does not hold the walk. The driver's own retry is the backstop.
const NAV_TIMEOUT_MS = 45_000;
// After load, wait for the XHR that fills the list to settle. `networkidle` alone can
// fire before a late render, so a short fixed settle follows it.
const IDLE_TIMEOUT_MS = 15_000;
const SETTLE_MS = 1_200;
// `K000377` Kelly's list is a client-side template: its first paint carries hrefs that
// are still `${item.link}`, which is markup rather than a URL. Wait for the template to
// resolve before reading the page, and if it never does, report the count so the driver
// can record that as the row's failure reason instead of collecting the templates.
const TEMPLATE_TIMEOUT_MS = 10_000;
// After a scroll or a click, how long the new items get to arrive, and the settle that
// follows so a half-painted batch is not what gets read.
const GROWTH_TIMEOUT_MS = 8_000;
const GROWTH_SETTLE_MS = 800;
// The attribute the chosen control is marked with, so Playwright clicks it for real —
// scrolled into view, visibility-checked, a trusted event — rather than this script
// calling `.click()` on a node that may be covered or not yet listening.
const MARK = "data-civic-loadmore";

const browser = await chromium.launch();
// A realistic desktop UA: these are ordinary public pages, and the default headless
// UA is the thing some of them answer differently to. This is not a bot-wall
// workaround — K000394's 403 refuses a browser UA too and stays out of scope.
const context = await browser.newContext({
  viewport: { width: 1280, height: 900 },
  userAgent:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " +
    "Chrome/141.0.0.0 Safari/537.36",
});

// Counted in the page: every anchor with an href, and every href still carrying an
// unresolved template. The driver reports both, and compares the first across a click.
const COUNTS = () => {
  const hrefs = [...document.querySelectorAll("a[href]")].map((a) => a.getAttribute("href"));
  return {
    anchors: hrefs.length,
    templated: hrefs.filter((h) => h.includes("${")).length,
  };
};

// Find the row's own load-more control, mark it, and describe what was found. Run in
// the page, so the choice is made against the live DOM rather than against markup.
//
// Chosen on the publisher's own words first (a control labelled "Load more", "Show
// more", "View more"), then on its class or data attributes. A numbered pager is
// deliberately NOT chosen: a page the SITE gives a URL for is `next_page_url`'s to
// follow, and clicking it here would replace the list rather than extend it.
//
// `nearby` is the diagnostic: anything on the page that mentions more/load/pagination,
// visible or not. A row with no control has to say what it has instead, or a zero is
// indistinguishable from a page nobody looked at.
const FIND_CONTROL = (mark) => {
  const TEXT =
    /^(?:load|show|view|see)\s+(?:\d+\s+)?more\b|^more(?:\s+(?:news|posts|results|releases|articles|stories))?$/i;
  const ATTR = /load[-_ ]?more|loadmore|show[-_ ]?more|infinite[-_ ]?scroll/i;
  const DIAG = /\bmore\b|\bload\b|pagination|paginate|pager/i;
  const describe = (n) => {
    const text = (n.innerText || n.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40);
    const cls = (n.getAttribute("class") || "").slice(0, 70);
    const box = n.getBoundingClientRect();
    const visible = box.width > 0 && box.height > 0;
    return `<${n.tagName.toLowerCase()} class="${cls}"> ${JSON.stringify(text)} visible=${visible}`;
  };
  document.querySelectorAll(`[${mark}]`).forEach((n) => n.removeAttribute(mark));
  const nodes = [
    ...document.querySelectorAll(
      "button, a, [role=button], [class*=load], [class*=more], [class*=pagination], [class*=pager]",
    ),
  ];
  const nearby = [];
  let chosen = null;
  for (const n of nodes) {
    const text = (n.innerText || n.textContent || "").trim();
    const attrs = [...n.attributes].map((a) => `${a.name}=${a.value}`).join(" ");
    if (!DIAG.test(text) && !DIAG.test(attrs)) continue;
    nearby.push(describe(n));
    if (chosen || n.disabled) continue;
    const box = n.getBoundingClientRect();
    if (box.width === 0 || box.height === 0) continue;
    if (TEXT.test(text) || ATTR.test(attrs)) chosen = n;
  }
  if (chosen) chosen.setAttribute(mark, "1");
  return { control: chosen ? describe(chosen) : null, nearby: [...new Set(nearby)].slice(0, 8) };
};

// The page the last `url` request left open, so `more` can act on it.
let open = null;

async function closeOpen() {
  if (open === null) return;
  const page = open;
  open = null;
  try {
    await page.close();
  } catch {
    // A page whose browser already went away cannot be closed and does not need to be.
  }
}

async function render(url) {
  await closeOpen();
  const page = await context.newPage();
  try {
    const response = await page.goto(url, {
      timeout: NAV_TIMEOUT_MS,
      waitUntil: "domcontentloaded",
    });
    const status = response ? response.status() : 0;
    // A non-OK status is reported, not rendered: the driver turns it into the same
    // HTTPStatusError a plain fetch would raise, so walk_member's existing
    // 404-is-the-end-of-the-archive branch fires identically.
    if (status >= 400) {
      await page.close();
      return { url, ok: false, status, error: `HTTP ${status}` };
    }
    try {
      await page.waitForLoadState("networkidle", { timeout: IDLE_TIMEOUT_MS });
    } catch {
      // Some of these pages hold a long-poll or an analytics socket open, so idle
      // never arrives. The content is usually already there; the settle below is
      // what the list actually needs.
    }
    await page.waitForTimeout(SETTLE_MS);
    try {
      await page.waitForFunction(
        () => ![...document.querySelectorAll("a[href]")].some((a) => a.getAttribute("href").includes("${")),
        { timeout: TEMPLATE_TIMEOUT_MS },
      );
    } catch {
      // The template never resolved. Reported through `templated` below, never hidden:
      // `${item.link}` is markup, and the driver records it as the row's failure.
    }
    const counts = await page.evaluate(COUNTS);
    const html = await page.content();
    open = page;
    return { url, ok: true, status, html, ...counts };
  } catch (err) {
    await page.close();
    return { url, ok: false, status: 0, error: `${err.name}: ${err.message.split("\n")[0]}` };
  }
}

async function advance() {
  const page = open;
  if (page === null) {
    return { ok: false, error: "no page is open to advance" };
  }
  try {
    const before = await page.evaluate(COUNTS);
    // Several of these lists only build their control once it is in view.
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(GROWTH_SETTLE_MS);
    const found = await page.evaluate(FIND_CONTROL, MARK);
    let clicked = false;
    if (found.control !== null) {
      try {
        await page.click(`[${MARK}]`, { timeout: GROWTH_TIMEOUT_MS });
        clicked = true;
      } catch (err) {
        // A control that cannot be clicked (covered, detached mid-click) is reported as
        // not clicked rather than as a click that did nothing.
        found.error = `${err.name}: ${err.message.split("\n")[0]}`;
      }
    }
    try {
      await page.waitForFunction(
        (n) => document.querySelectorAll("a[href]").length > n,
        before.anchors,
        { timeout: GROWTH_TIMEOUT_MS },
      );
    } catch {
      // No growth inside the timeout: the control has stopped adding items, or the
      // scroll alone was never going to add any. `grew: false` says so.
    }
    await page.waitForTimeout(GROWTH_SETTLE_MS);
    const after = await page.evaluate(COUNTS);
    await page.evaluate((mark) => {
      document.querySelectorAll(`[${mark}]`).forEach((n) => n.removeAttribute(mark));
    }, MARK);
    const html = await page.content();
    return {
      ok: true,
      clicked,
      grew: after.anchors > before.anchors,
      anchors: after.anchors,
      templated: after.templated,
      control: found.control,
      nearby: found.nearby,
      error: found.error ?? null,
      html,
    };
  } catch (err) {
    return { ok: false, error: `${err.name}: ${err.message.split("\n")[0]}` };
  }
}

const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of lines) {
  const trimmed = line.trim();
  if (!trimmed) continue;
  let request;
  try {
    request = JSON.parse(trimmed);
  } catch (err) {
    process.stdout.write(
      `${JSON.stringify({ url: null, ok: false, status: 0, error: `bad request: ${err.message}` })}\n`,
    );
    continue;
  }
  const result = request.more ? await advance() : await render(request.url);
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

await closeOpen();
await context.close();
await browser.close();
