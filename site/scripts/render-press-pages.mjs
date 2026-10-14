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
//   * It does not click "load more" or scroll. Whether these sites need that is a
//     measurement, not an assumption; the driver reports what one render yields and
//     the owner decides from the numbers.
//
// Protocol — JSON Lines over stdin/stdout, one browser for the whole session:
//   in:  {"url": "https://..."}
//   out: {"url": "...", "ok": true,  "status": 200, "html": "<!doctype html>..."}
//        {"url": "...", "ok": false, "status": 404, "error": "..."}
// `ok: false` means DO NOT CACHE THIS. A render that timed out is not a page, and
// caching it would serve a 7-day-fresh empty list to the plain collector.
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

async function render(url) {
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
    const html = await page.content();
    return { url, ok: true, status, html };
  } catch (err) {
    return { url, ok: false, status: 0, error: `${err.name}: ${err.message.split("\n")[0]}` };
  } finally {
    await page.close();
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
  const result = await render(request.url);
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

await context.close();
await browser.close();
