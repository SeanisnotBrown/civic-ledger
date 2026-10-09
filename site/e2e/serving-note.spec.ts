import { expect, test } from "@playwright/test";

import { SEAT_STATUS } from "./fixtures";

// Rule 0, 2026-10-09. The member page's "No longer serving." note used
// `member.serving`, which means "the member's latest term overlapped the latest
// covered Congress" — still TRUE for the 16 members who resigned or died during the
// 119th. The note was therefore suppressed for exactly the people it exists for, and
// their pages read as though they still held the seat. The page now uses
// `holdsSeatAsOf(member, asOfDate())`, the same helper the homepage state finder uses,
// so there is ONE definition of "currently in office" site-wide.
//
// Both ids are derived from the committed roster and the manifest date (see
// fixtures.ts), so neither rots; the departed case prefers C001078 (Connolly, died in
// office 2025-05-21) when the dataset carries him.

test("a departed member's page says they are no longer serving", async ({ page }) => {
  await page.goto(`/m/${SEAT_STATUS.departed}/1`);
  await expect(page.getByText("No longer serving.")).toBeVisible();
});

test("a sitting member's page does not", async ({ page }) => {
  await page.goto(`/m/${SEAT_STATUS.sitting}/1`);
  await expect(page.getByText("No longer serving.")).toHaveCount(0);
});
