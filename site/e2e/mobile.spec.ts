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
    // Best-effort screenshot artifact. fullPage capture can exceed chromium's
    // max surface on very tall pages (e.g. a rule resolution referenced by
    // hundreds of votes); fall back to a viewport shot. The assertion above —
    // not the artifact — is what gates the test.
    try {
      const shot = await page.screenshot({ fullPage: true });
      await testInfo.attach(`screenshot-${url.replace(/\W+/g, "_")}`, {
        body: shot,
        contentType: "image/png",
      });
    } catch {
      const shot = await page.screenshot({ fullPage: false });
      await testInfo.attach(`screenshot-${url.replace(/\W+/g, "_")}-viewport`, {
        body: shot,
        contentType: "image/png",
      });
    }
  });
}
