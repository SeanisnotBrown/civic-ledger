import { test, expect } from "@playwright/test";

// V2-5 drill-down: a dashboard headline number must click through to the list that
// reproduces it, and on to a member page. This exercises the click-through rule end
// to end (dashboard → pre-filtered federal browser → member page) and confirms the
// Preact island hydrates and honors the deep-link query param.
test("dashboard grade band → filtered federal list → member page", async ({ page }) => {
  await page.goto("/");

  // The attendance-grade distribution links each band to the federal list, pre-filtered.
  const bandLink = page.locator('a[href="/federal?grade=A&sort=grade"]');
  await expect(bandLink).toBeVisible();
  await bandLink.click();

  await expect(page).toHaveURL(/\/federal\?grade=A&sort=grade$/);

  // The island hydrates and applies the deep-link: the grade filter reads "A", sorted
  // by grade. (Before hydration the SSR'd selects read "all"/"name", so these waits
  // also prove the island came alive.)
  await expect(page.locator("#mb-grade")).toHaveValue("A");
  await expect(page.locator("#mb-sort")).toHaveValue("grade");

  // The filtered list reproduces the number: at least one member is shown.
  const memberLinks = page.locator('ul li a[href^="/m/"]');
  await expect(memberLinks.first()).toBeVisible();
  expect(await memberLinks.count()).toBeGreaterThan(0);

  // Click through to that member's page — it renders the record summary that holds the
  // graded attendance tile.
  await memberLinks.first().click();
  await expect(page).toHaveURL(/\/m\/[^/]+\/1$/);
  await expect(page.getByRole("heading", { name: "Record summary" })).toBeVisible();
});
