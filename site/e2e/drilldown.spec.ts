import { test, expect } from "@playwright/test";

// V2-5 drill-down: a dashboard headline number must click through to the list that
// reproduces it, and on to a member page. Exercises the click-through rule end to end
// (dashboard → pre-filtered federal browser → member page) and confirms the controls
// island hydrates, honors the deep-link query param, and actually hides non-matching
// rows (computed visibility — not merely a data attribute, which would pass even if the
// filter's CSS silently lost the cascade).
test("dashboard grade band → filtered federal list → member page", async ({ page }) => {
  await page.goto("/");

  // The attendance-grade distribution links each band to the federal list, pre-filtered.
  const bandLink = page.locator('a[href="/federal?grade=A&sort=grade"]');
  await expect(bandLink).toBeVisible();
  await bandLink.click();

  await expect(page).toHaveURL(/\/federal\?grade=A&sort=grade$/);

  // The island hydrates and applies the deep-link: grade filter "A", sorted by grade.
  await expect(page.locator("#mb-grade")).toHaveValue("A");
  await expect(page.locator("#mb-sort")).toHaveValue("grade");

  // The filter really hides non-A rows (computed visibility), and A rows remain shown.
  await expect(page.locator('#member-list li[data-grade="F"]').first()).toBeHidden();
  const firstA = page.locator('#member-list li[data-grade="A"] a[href^="/m/"]').first();
  await expect(firstA).toBeVisible();

  // Click through to that member's page — it renders the record summary that holds the
  // graded attendance tile.
  await firstA.click();
  await expect(page).toHaveURL(/\/m\/[^/]+\/1$/);
  await expect(page.getByRole("heading", { name: "Record summary" })).toBeVisible();
});
