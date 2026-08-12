import { test, expect } from "@playwright/test";
import { PAGES } from "./fixtures";

// §6.7 mobile-first: designed at 380px. Assert no horizontal overflow (the page
// body must never scroll sideways) and capture a screenshot artifact per page.
test.use({ viewport: { width: 380, height: 800 } });

for (const url of PAGES) {
  test(`380px layout: ${url}`, async ({ page }, testInfo) => {
    await page.goto(url);
    const overflow = await page.evaluate(() => {
      const el = document.documentElement;
      return { scrollWidth: el.scrollWidth, clientWidth: el.clientWidth };
    });
    // Allow a 1px rounding slack.
    expect(overflow.scrollWidth, `horizontal overflow on ${url}`).toBeLessThanOrEqual(
      overflow.clientWidth + 1,
    );
    // Best-effort screenshot artifact — it NEVER gates the test (the overflow
    // assertion above is the gate). fullPage capture can exceed chromium's max
    // surface on very tall pages (a rule resolution referenced by hundreds of votes),
    // and on CI the capture itself occasionally errors mid-run ("Unable to capture
    // screenshot / waiting for fonts to load" — a font-load race). Fall back to a
    // viewport shot, and if even that fails, skip the artifact silently: a debug
    // screenshot failing must not fail a passing layout check.
    try {
      let shot: Buffer;
      try {
        shot = await page.screenshot({ fullPage: true });
      } catch {
        shot = await page.screenshot({ fullPage: false });
      }
      await testInfo.attach(`screenshot-${url.replace(/\W+/g, "_")}`, {
        body: shot,
        contentType: "image/png",
      });
    } catch {
      // Screenshot unavailable this run — artifact skipped, the layout test still passes.
    }
  });
}
