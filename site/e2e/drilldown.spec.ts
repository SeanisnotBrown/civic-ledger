import { test, expect } from "@playwright/test";

// V2-5 drill-down: a dashboard headline number must click through to the list that
// reproduces it, and on to a member page. Exercises the click-through rule end to end
// (dashboard → pre-filtered federal explorer → member page) and confirms the controls
// island hydrates, honors the deep-link query param, and actually hides non-matching
// rows (computed visibility — not merely a data attribute, which would pass even if the
// filter's CSS silently lost the cascade).
//
// The federal roster is now a metric TABLE (V2-5 Nocturne explorer): rows are <tr
// data-grade>, filters are chips (data-chip/data-value/aria-pressed), sort is a header
// button (data-sort). The invariant asserted here is unchanged — deep-link → filtered,
// grade-sorted list → member page.
test("dashboard grade band → filtered federal list → member page", async ({ page }) => {
  await page.goto("/");

  // The attendance-grade distribution links each band to the federal list, pre-filtered.
  const bandLink = page.locator('a[href="/federal?grade=A&sort=grade"]');
  await expect(bandLink).toBeVisible();
  await bandLink.click();

  await expect(page).toHaveURL(/\/federal\?grade=A&sort=grade$/);

  // The island hydrates and applies the deep-link: grade chip "A" active, grade sort on.
  await expect(page.locator('[data-chip="grade"][data-value="A"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('#member-list .hdr-btn[data-sort="grade"]')).toHaveAttribute("data-active", "");

  // The filter really hides non-A rows (computed visibility), and A rows remain shown.
  await expect(page.locator('#member-list tr[data-grade="F"]').first()).toBeHidden();
  const firstA = page.locator('#member-list tr[data-grade="A"] a[href^="/m/"]').first();
  await expect(firstA).toBeVisible();

  // Click through to that member's page — it renders the record summary that holds the
  // graded attendance tile.
  await firstA.click();
  await expect(page).toHaveURL(/\/m\/[^/]+\/1$/);
  await expect(page.getByRole("heading", { name: "Record summary" })).toBeVisible();
});

// The metric column headers sort the table client-side (deep-link path above only covers
// grade). Clicking the Attendance header opens it descending and reorders the rows.
test("clicking a metric column header sorts the table", async ({ page }) => {
  await page.goto("/federal");
  const attHdr = page.locator('#member-list .hdr-btn[data-sort="att"]');
  await attHdr.click();
  await expect(attHdr).toHaveAttribute("data-active", "");
  await expect(attHdr).toHaveAttribute("data-dir", "desc");

  // First two visible rows are in descending attendance order (nulls sort last, so the
  // top rows always carry a value).
  const vals = await page
    .locator('#member-list tr[data-member]:visible')
    .evaluateAll((rows) =>
      rows.slice(0, 2).map((r) => Number((r as HTMLElement).dataset.att)),
    );
  expect(vals[0]).toBeGreaterThanOrEqual(vals[1]);
});
