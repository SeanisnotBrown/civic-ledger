// Mississippi pages state their own data date (COPILOT-AUTHORED, NOT REVIEWED BY SEAN;
// copilot call 2026-11-26, rule 0). After owner ruling 2026-11-25 Q3 a failed Mississippi
// refresh leaves those pages on older data while the federal footer date moves on, so
// every /ms page says when the Mississippi data last changed, taken from
// data/state/ms/manifest.json `generated_at` and never from the build clock.
//
// Part 1 (pure, no build needed) pins the wording and that the date follows the data.
// Part 2 runs after `npm run build`, like the other dist gates: every checked Mississippi
// page carries the line made from the committed manifest, and a federal page does not.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { msDataLine } from "../src/lib/display.ts";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DIST = path.join(ROOT, "dist");
const MANIFEST = path.join(ROOT, "..", "data", "state", "ms", "manifest.json");
const failures = [];

// Part 1: the wording, and the date follows the data.
const want1 = "Mississippi data last updated Aug 12, 2026.";
const got1 = msDataLine({ generated_at: "2026-08-12T23:47:54Z" });
if (got1 !== want1) failures.push(`wording drifted:\n  got:  ${got1}\n  want: ${want1}`);
const got2 = msDataLine({ generated_at: "2031-01-02T00:00:00Z" });
if (got2 !== "Mississippi data last updated Jan 2, 2031.") {
  failures.push(`date does not follow the data: ${got2}`);
}

// Part 2: the built pages.
const manifest = JSON.parse(readFileSync(MANIFEST, "utf-8"));
const line = msDataLine(manifest);
const first = (dir) => {
  const full = path.join(DIST, "ms", dir);
  if (!existsSync(full)) return null;
  const entry = readdirSync(full, { withFileTypes: true }).find((e) => e.isDirectory());
  return entry ? path.join("ms", dir, entry.name, "index.html") : null;
};
const msPages = ["ms/index.html", first("v"), first("b")].filter(Boolean);
for (const rel of msPages) {
  const file = path.join(DIST, rel);
  if (!existsSync(file)) {
    failures.push(`${rel}: not built`);
    continue;
  }
  const html = readFileSync(file, "utf-8");
  const n = html.split("Mississippi data last updated").length - 1;
  if (n !== 1) failures.push(`${rel}: Mississippi date line appears ${n} time(s), expected 1`);
  if (!html.includes(line)) failures.push(`${rel}: line from the manifest not found: ${line}`);
  if (!html.includes("Federal data last updated")) {
    failures.push(`${rel}: footer must say "Federal data last updated" beside it`);
  }
}
const fed = path.join(DIST, "methods", "index.html");
if (!existsSync(fed)) {
  failures.push("methods/index.html: not built");
} else {
  const html = readFileSync(fed, "utf-8");
  if (html.includes("Mississippi data last updated")) {
    failures.push("a federal page carries the Mississippi date line");
  }
  if (!html.includes("Data last updated")) failures.push("a federal page lost its footer date");
}

if (failures.length) {
  console.error("MS-DATE CHECK FAILED:");
  for (const f of failures) console.error(`  ${f}`);
  process.exit(1);
}
console.log(`ms-date: ${line} (${msPages.length} Mississippi page(s) checked)`);
