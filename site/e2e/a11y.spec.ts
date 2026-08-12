import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { PAGES } from "./fixtures";

// axe-core a11y scan on representative pages (INC-8 acceptance). WCAG 2 A/AA.
for (const url of PAGES) {
  test(`a11y: ${url}`, async ({ page }) => {
    await page.goto(url);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
  });
}
