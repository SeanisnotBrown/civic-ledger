import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { PAGES } from "./fixtures";

// axe-core a11y scan on representative pages (INC-8 acceptance). WCAG 2 A/AA.
//
// Generous timeout: axe.analyze() walks the whole DOM computing colour-contrast, and on
// the /federal explorer (~11k nodes) `content-visibility: auto` makes that SLOWER, not
// faster — reading each off-screen row's computed style forces the per-row layout that
// content-visibility otherwise defers, so the scan takes ~25s locally and timed out at the
// 30s default on the slower CI runner (run 31897336351). This is scan runtime, not a
// violation; 150s gives the CI runner headroom without masking a real hang (axe still
// completes and any violation still fails the test).
for (const url of PAGES) {
  test(`a11y: ${url}`, async ({ page }) => {
    test.setTimeout(150_000);
    await page.goto(url);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
  });
}
