// @ts-check
import { defineConfig } from "astro/config";
import preact from "@astrojs/preact";
import tailwindcss from "@tailwindcss/vite";

// Static build only — the site reads data/**/*.json|yaml at build time and
// ships zero third-party runtime requests (§10.1). Preact islands power the
// quiz/drift/ballot interactions; Tailwind v4 via the Vite plugin (not the
// legacy @astrojs/tailwind integration).
export default defineConfig({
  output: "static",
  // Canonical origin. Atom requires every <id> to be an absolute IRI (V2-11 task 7),
  // and the V2-12 alert Worker fetches https://civicledger.net/events/latest.json by
  // this same name, so the value is the deployed origin, not a build-time guess.
  // `.ts` endpoints read it from their GET(context) arg as `context.site`.
  site: "https://civicledger.net",
  integrations: [preact()],
  vite: {
    // Cast: @tailwindcss/vite's plugin type lags Vite's PluginOption union
    // (a version-skew typing quirk); the plugin runs correctly at build.
    plugins: [/** @type {any} */ (tailwindcss())],
  },
});
