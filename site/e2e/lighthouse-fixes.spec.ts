import { test, expect } from "@playwright/test";

// The behaviour the two mobile-performance fixes must not change (STATUS fact 2,
// owner-approved 2026-10-14). Both fixes move WHEN work happens, never what the
// reader ends up looking at:
//
//   * `/` ships all 56 state delegations so the page works with JavaScript off.
//     global.css now hides them BEFORE first paint instead of letting the picker
//     script collapse them after it, so the browser never lays out 539 links to
//     paint a headline. A <noscript> override restores them for a reader with no
//     script.
//   * The shared clamp script in Layout.astro measures in three passes (write all
//     the classes, read all the sizes, write all the results) instead of writing
//     and reading per element, which on `/m/A000055/1` was 283 forced layouts of a
//     5,474-element document.
//
// None of this was covered before: the e2e suite tested axe and 380px layout, so
// nothing would have caught the picker or the clamp silently changing. These are the
// invariants, written so they survive the nightly's data growing — counts come from
// the page itself rather than being hard-coded.

const HOME = "/";
const MEMBER = "/m/A000055/1";

test.describe("the homepage state picker", () => {
  test("hides every delegation until one is picked, and shows exactly that one", async ({
    page,
  }) => {
    await page.goto(HOME);
    const panels = page.locator("[data-reps-panels] > [data-state]");
    const total = await panels.count();
    expect(total, "the page should ship every delegation").toBeGreaterThan(50);

    // Nothing picked: nothing shown. This is what keeps the 539 links off the
    // critical path, and it is asserted on COMPUTED visibility, not the attribute —
    // a cascade regression (D73) would otherwise pass silently.
    await expect(page.locator("[data-reps-panels] > [data-state]:visible")).toHaveCount(0);

    await page.selectOption("#state-pick", "TX");
    const shown = page.locator("[data-reps-panels] > [data-state]:visible");
    await expect(shown).toHaveCount(1);
    await expect(shown.first()).toHaveAttribute("data-state", "TX");
    // Picking again replaces rather than accumulates.
    await page.selectOption("#state-pick", "AL");
    await expect(shown).toHaveCount(1);
    await expect(shown.first()).toHaveAttribute("data-state", "AL");
  });
});

test.describe("the homepage with JavaScript off", () => {
  test.use({ javaScriptEnabled: false });

  test("shows every delegation, because the <noscript> override un-hides them", async ({
    page,
  }) => {
    await page.goto(HOME);
    const panels = page.locator("[data-reps-panels] > [data-state]");
    const total = await panels.count();
    expect(total).toBeGreaterThan(50);
    // Every one of them, visible. Hiding them in CSS would make this page useless
    // without script if the <noscript> override were ever dropped, and that is
    // exactly the regression this test exists to catch.
    await expect(page.locator("[data-reps-panels] > [data-state]:visible")).toHaveCount(total);
    await expect(page.locator('[data-reps-panels] a[href^="/m/"]:visible').first()).toBeVisible();
  });
});

test.describe("the member timeline", () => {
  test("shows one chunk of the rows the URL carries", async ({ page }) => {
    await page.goto(MEMBER);
    const rows = page.locator("[data-activity-list] li[data-kind]");
    const total = await rows.count();
    const chunk = Number(
      await page.locator("[data-activity-list]").getAttribute("data-chunk"),
    );
    expect(total, "the URL carries more rows than it shows").toBeGreaterThan(chunk);
    await expect(page.locator("[data-activity-list] li[data-kind]:visible")).toHaveCount(chunk);
  });

  test("clamps exactly the titles that overflow two lines, and no others", async ({ page }) => {
    await page.goto(MEMBER);
    // The invariant the three-pass rewrite has to preserve: the clamp class is on an
    // element if and only if its text really does overflow. Batching the reads must
    // not change a single decision, and measuring it here is what proves that.
    const wrong = await page.evaluate(() => {
      const bad: string[] = [];
      for (const el of document.querySelectorAll<HTMLElement>("[data-clamp]")) {
        if (el.offsetParent === null) continue; // hidden rows have no geometry to judge
        const clamped = el.classList.contains("line-clamp-2");
        const expanded =
          el.nextElementSibling?.getAttribute("aria-expanded") === "true";
        if (expanded) continue;
        // A clamped element reports a scrollHeight taller than its box; an unclamped
        // one must not have been clampable in the first place.
        const overflows = el.scrollHeight > el.clientHeight + 1;
        if (clamped !== overflows) bad.push(`${clamped ? "clamped" : "bare"}: ${el.textContent?.slice(0, 40)}`);
      }
      return bad;
    });
    expect(wrong, "clamp decisions must match real overflow").toEqual([]);
  });

  test("an expand control reveals the full title and gives it back", async ({ page }) => {
    await page.goto(MEMBER);
    // Anchor on an INDEX into every [data-clamp], which does not change. A locator
    // like `getByRole("Show the full title").first()` re-resolves after the click —
    // the button it matched is now called "Show less" — so it would silently start
    // pointing at the next, still-clamped row and the assertion would be meaningless.
    const titles = page.locator("[data-activity-list] [data-clamp]");
    const total = await titles.count();
    let index = -1;
    for (let i = 0; i < total; i++) {
      const candidate = titles.nth(i);
      if (!(await candidate.isVisible())) continue;
      if (((await candidate.getAttribute("class")) ?? "").includes("line-clamp-2")) {
        index = i;
        break;
      }
    }
    test.skip(index < 0, "no visible title overflows two lines at this viewport");

    const title = titles.nth(index);
    const button = title.locator("xpath=following-sibling::button[1]");
    await expect(button).toHaveAttribute("aria-expanded", "false");
    await button.click();
    await expect(title).not.toHaveClass(/line-clamp-2/);
    await expect(button).toHaveAttribute("aria-expanded", "true");
    await expect(button).toHaveText("Show less");
    // And back: the control gives the clamp back rather than being one-way.
    await button.click();
    await expect(title).toHaveClass(/line-clamp-2/);
    await expect(button).toHaveText("Show the full title");
  });
});

test.describe("the member timeline with JavaScript off", () => {
  test.use({ javaScriptEnabled: false });

  test("shows every row the URL carries, and clamps none of them", async ({ page }) => {
    await page.goto(MEMBER);
    const rows = page.locator("[data-activity-list] li[data-kind]");
    const total = await rows.count();
    expect(total).toBeGreaterThan(0);
    // More than asked for, never less: with no script there is no chunking, and
    // nothing is clamped server-side, so every title reads in full.
    await expect(page.locator("[data-activity-list] li[data-kind]:visible")).toHaveCount(total);
    await expect(page.locator("[data-clamp].line-clamp-2")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Show the full title" })).toHaveCount(0);
  });
});
