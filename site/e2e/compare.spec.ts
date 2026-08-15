import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { compareIds } from "./fixtures";

// V2-5 /compare (D77): the one client-rendered view. Its markup exists only after the
// island renders, so this is the ONLY axe coverage the comparison ever gets — run it here
// after the cards appear, not via the generic PAGES sweep (which analyses too early).
const { a, b } = compareIds();

test("compare renders both members, the shared axis, and every-measure rows", async ({ page }) => {
  await page.goto(`/compare?m=${a}&m=${b}`);

  // The island reads ?m= and renders a card per member (wait for the client render).
  await expect(page.getByText("Attendance, on one axis")).toBeVisible();
  await expect(page.getByText("Every measure, side by side")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open full record →" })).toHaveCount(2);

  // A House + Senate pair triggers the cross-chamber non-comparability disclosure (D66/D77).
  await expect(page.getByText(/does not rank attendance across chambers/)).toBeVisible();

  // axe on the fully rendered comparison — the real a11y gate for the island markup.
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test("removing a member updates the comparison and the URL", async ({ page }) => {
  await page.goto(`/compare?m=${a}&m=${b}`);
  await expect(page.getByRole("link", { name: "Open full record →" })).toHaveCount(2);

  // Remove the first member; the card and its ?m= entry drop.
  await page.getByRole("button", { name: /^Remove / }).first().click();
  await expect(page.getByRole("link", { name: "Open full record →" })).toHaveCount(1);
  await expect(page).toHaveURL(new RegExp(`\\?m=${b}$`));
});
