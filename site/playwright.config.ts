import { defineConfig, devices } from "@playwright/test";

// E2E runs against the STATIC build (astro preview serves dist/). The suite is
// small and deterministic: axe a11y + a 380px no-horizontal-overflow layout
// check on representative pages (§6.7 mobile-first; INC-8 acceptance).
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: "http://localhost:4321",
    trace: "off",
  },
  projects: [
    { name: "mobile", use: { ...devices["Pixel 5"] } },
  ],
  webServer: {
    command: "npm run preview -- --port 4321 --host",
    url: "http://localhost:4321",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
