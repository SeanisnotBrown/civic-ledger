// Screenshot helper for the AES-14 / AES-29 preview (copilot, 2026-11-26).
// Usage (from site/):  node ../docs/design/2026-11-26-aes-14-29-preview/shoot.mjs <before|after> [baseUrl]
// Needs the Astro DEV server running (npm run dev -- --port 4399). Uses the Playwright
// already installed under site/node_modules; downloads nothing.
// Each shot is clipped from the top of the page to a fixed height that covers the part
// under review (member pages: the grades, work and the first rows of the timeline), so the
// PNGs stay a reasonable size. Pass `--full` to skip the clip.
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(path.resolve(process.cwd(), "package.json"));
const { chromium } = require("@playwright/test");

const OUT = path.dirname(fileURLToPath(import.meta.url));
const label = process.argv[2];
const base = process.argv[3]?.startsWith("http") ? process.argv[3] : "http://127.0.0.1:4399";
if (!["before", "after"].includes(label)) throw new Error("first arg must be before|after");

const PAGES = [
  { slug: "home", url: "/", clip: { 1440: 3000, 390: 4200 } },
  { slug: "congress", url: "/congress", clip: { 1440: 3200, 390: 5200 } },
  { slug: "house-member", url: "/m/A000055/1", clip: { 1440: 4600, 390: 6800 } },
  { slug: "senate-member", url: "/m/A000382/1", clip: { 1440: 4600, 390: 6800 } },
];

const browser = await chromium.launch();
for (const width of [1440, 390]) {
  const ctx = await browser.newContext({
    viewport: { width, height: width === 1440 ? 900 : 844 },
    deviceScaleFactor: 1,
  });
  for (const p of PAGES) {
    const page = await ctx.newPage();
    await page.goto(base + p.url, { waitUntil: "networkidle", timeout: 180_000 });
    await page.waitForTimeout(600); // let the clamp script and the 50-row chunking settle
    const total = await page.evaluate(() => document.documentElement.scrollHeight);
    const h = Math.min(total, p.clip[width]);
    const file = path.join(OUT, `${label}-${p.slug}-${width}.png`);
    await page.screenshot({ path: file, fullPage: true, clip: { x: 0, y: 0, width, height: h } });
    console.log(`${path.basename(file)}  ${width}x${h} (page ${total}px)`);
    await page.close();
  }
  await ctx.close();
}
await browser.close();
