import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { billWithActions, topicPaths } from "./fixtures";

// V2-11 task 7 — the bill action timeline, the topic pages, and the "Track this bill"
// affordance.
//
// What these assert that a build alone does not: the government's action text reaches
// the page VERBATIM (§0.5 — nothing summarised or reworded), the SD-33 3(c) link rule
// holds on a rendered topic row, and the track affordance works with JavaScript off.
// a11y and 380px coverage for the same pages comes from a11y.spec.ts / mobile.spec.ts,
// which read the new URLs out of PAGES.

const DATA = fileURLToPath(new URL("../../data/", import.meta.url));
const billId = billWithActions();
const topics = topicPaths();

test.describe("bill action timeline", () => {
  test.skip(
    billId === null,
    "no bill in this dataset has both a page and a collected timeline yet (D27 sentinel)",
  );

  test("renders the government's action text verbatim, newest first", async ({ page }) => {
    const bill = JSON.parse(
      fs.readFileSync(path.join(DATA, "bills", `${billId}.json`), "utf-8"));
    await page.goto(`/b/${billId}`);

    const section = page.locator("section", { hasText: "Action timeline" }).first();
    await expect(section).toBeVisible();

    // Every stored action's text appears on the page exactly as the government wrote
    // it. `toContainText` with a string matches literally, so a reworded or truncated
    // line fails here.
    const rows = section.locator("ol > li");
    await expect(rows).toHaveCount(bill.actions.length);
    for (const action of bill.actions) {
      await expect(section).toContainText(action.text);
    }

    // Stored order is newest-first and the page preserves it (no local re-sort: see
    // the route's comment — `date` alone cannot order same-day actions).
    const firstRow = rows.first();
    await expect(firstRow).toContainText(bill.actions[0].text);
  });

  test("a recorded-vote action links to the roll call", async ({ page }) => {
    const bill = JSON.parse(
      fs.readFileSync(path.join(DATA, "bills", `${billId}.json`), "utf-8"));
    const withRoll = bill.actions.find((a: any) => a.rollcall_id);
    test.skip(!withRoll, "this bill's timeline has no action resolved to a held roll call");
    await page.goto(`/b/${billId}`);
    await expect(
      page.locator(`a[href="/v/${withRoll.rollcall_id}"]`).first(),
    ).toBeVisible();
  });

  test("Track this bill works with JavaScript disabled", async ({ browser }) => {
    // The copy button is progressive enhancement and starts hidden; the link and the
    // selectable address are the no-JS path and must both be there.
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    await page.goto(`/b/${billId}`);

    const section = page.locator("section", { hasText: "Track this bill" }).first();
    await expect(section.locator(`a[href="/b/${billId}/feed.xml"]`)).toBeVisible();
    await expect(section.locator("[data-feed-url]")).toHaveValue(
      `https://civicledger.net/b/${billId}/feed.xml`,
    );
    // Hidden without JS, so no dead button is offered.
    await expect(section.locator("[data-copy-feed]")).toBeHidden();
    await context.close();
  });

  test("the copy button appears when JavaScript is on", async ({ page }) => {
    await page.goto(`/b/${billId}`);
    await expect(page.locator("[data-copy-feed]")).toBeVisible();
  });
});

test.describe("topic pages", () => {
  for (const [label, url] of Object.entries(topics)) {
    test(`${label}: the official term heads the page and every row obeys the link rule`, async ({
      page,
    }) => {
      await page.goto(url);

      // The term renders verbatim as the <h1>; the vocabulary is stated, because
      // "Health" the policy area and "Health" the subject term are different
      // government claims (ADR D97 — and why they are separate URL namespaces).
      const slug = url.split("/").pop()!;
      const idx = JSON.parse(
        fs.readFileSync(path.join(DATA, "topics", "index.json"), "utf-8"));
      const entry = [...idx.policy_areas, ...idx.subjects].find((t: any) => t.slug === slug);
      await expect(page.locator("h1")).toHaveText(entry.name);

      // Every rendered row links either to its /b/ page or to congress.gov — never to
      // a /b/ URL that was not built. (npm run test:links checks this over the whole
      // dist; here it is checked as the reader actually sees it.)
      const rows = page.locator("li[data-bill-id]");
      const count = await rows.count();
      expect(count).toBeGreaterThan(0);
      for (let i = 0; i < Math.min(count, 25); i++) {
        const row = rows.nth(i);
        const id = await row.getAttribute("data-bill-id");
        const href = await row.locator("a").first().getAttribute("href");
        if (href!.startsWith("/b/")) {
          expect(href).toBe(`/b/${id}`);
        } else {
          expect(href).toMatch(/^https:\/\/www\.congress\.gov\//);
        }
      }
    });
  }

  test("the index lists both vocabularies and links into each namespace", async ({ page }) => {
    await page.goto("/topics");
    await expect(page.getByRole("heading", { name: "Policy areas" })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Legislative subject terms" }),
    ).toBeVisible();
    await expect(page.locator('a[href^="/topics/policy-area/"]').first()).toBeVisible();
    await expect(page.locator('a[href^="/topics/subject/"]').first()).toBeVisible();
  });
});
