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
  integrations: [preact()],
  vite: {
    // Cast: @tailwindcss/vite's plugin type lags Vite's PluginOption union
    // (a version-skew typing quirk); the plugin runs correctly at build.
    plugins: [/** @type {any} */ (tailwindcss())],
  },
});
