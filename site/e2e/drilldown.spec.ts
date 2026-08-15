import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

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
  await expect(page.locator('#member-list [data-grade="F"]').first()).toBeHidden();
  const firstA = page.locator('#member-list [data-grade="A"] a[href^="/m/"]').first();
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
  // Wait for the controls island to finish wiring the headers (client:idle) before
  // clicking, so the test doesn't race hydration.
  await expect(page.locator("#member-list[data-mb-ready]")).toBeAttached();
  const attHdr = page.locator('#member-list .hdr-btn[data-sort="att"]');
  await attHdr.click();
  await expect(attHdr).toHaveAttribute("data-active", "");
  await expect(attHdr).toHaveAttribute("data-dir", "desc");

  // First two visible rows are in descending attendance order (nulls sort last, so the
  // top rows always carry a value).
  const vals = await page
    .locator('#member-list [data-member]:visible')
    .evaluateAll((rows) =>
      rows.slice(0, 2).map((r) => Number((r as HTMLElement).dataset.att)),
    );
  expect(vals[0]).toBeGreaterThanOrEqual(vals[1]);
});

// The per-row selection controls (compare-toggle + exclude) are INJECTED by the island on
// hydration into statically-reserved gutters (they're absent JS-off by design). These two
// tests cover the flows end to end so the injection + delegated-listener wiring can't rot.
test("setting a member aside hides the row, shows a restore chip, and restores", async ({ page }) => {
  await page.goto("/federal");
  await expect(page.locator("#member-list[data-mb-ready]")).toBeAttached();

  const firstRow = page.locator("#member-list [data-member]").first();
  const id = await firstRow.getAttribute("data-id");
  const name = (await firstRow.getAttribute("data-name")) ?? "";

  // Exclude via the injected ✕ control.
  await firstRow.locator('button[data-act="excl"]').click();

  // The row is hidden, a "Set aside by you" chip names them, and the count drops.
  await expect(page.locator(`#member-list [data-id="${id}"]`)).toBeHidden();
  const chip = page.getByRole("button", { name: `Restore ${name}` });
  await expect(chip).toBeVisible();
  await expect(page.getByText(/\bof \d+ members$/)).toBeVisible();

  // Restore via the chip → the row returns and the chip disappears.
  await chip.click();
  await expect(page.locator(`#member-list [data-id="${id}"]`)).toBeVisible();
  await expect(chip).toHaveCount(0);
});

test("selecting two members reveals the compare link with both ids", async ({ page }) => {
  await page.goto("/federal");
  await expect(page.locator("#member-list[data-mb-ready]")).toBeAttached();

  const rows = page.locator("#member-list [data-member]");
  const id1 = await rows.nth(0).getAttribute("data-id");
  const id2 = await rows.nth(1).getAttribute("data-id");

  // The heading compare link stays hidden until a second member is picked.
  const compareLink = page.locator("#mb-compare");
  await expect(compareLink).toBeHidden();
  await rows.nth(0).locator('button[data-act="cmp"]').click();
  await expect(compareLink).toBeHidden();
  await rows.nth(1).locator('button[data-act="cmp"]').click();

  // Now visible, counted, and pointing at /compare with both ids — and it navigates there.
  await expect(compareLink).toBeVisible();
  await expect(compareLink).toContainText("Compare selected (2)");
  await expect(compareLink).toHaveAttribute("href", `/compare?m=${id1}&m=${id2}`);
  await compareLink.click();
  await expect(page).toHaveURL(new RegExp(`/compare\\?m=${id1}&m=${id2}$`));
});

// The controls are injected as role="cell"/columnheader wrappers precisely so the ARIA grid
// keeps a valid child structure (a bare <button> child of role="row" fails axe's
// aria-required-children). The generic a11y sweep can race the client:idle injection, so
// assert axe-cleanliness here AFTER the controls are provably present. content-visibility
// makes the scan slow (see a11y.spec.ts), hence the raised timeout.
test("the injected per-row controls keep the ARIA grid axe-clean", async ({ page }) => {
  test.setTimeout(150_000);
  await page.goto("/federal");
  await expect(page.locator("#member-list[data-mb-ready]")).toBeAttached();
  await expect(page.locator('#member-list button[data-act="cmp"]').first()).toBeAttached();
  await expect(page.locator('#member-list button[data-act="excl"]').first()).toBeAttached();
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});
