// V2-1 acceptance (task 4 / H14): the built static output must stay under the
// Cloudflare Workers Static Assets file-count limit, or the deploy itself fails.
// Limits verified 2026-08-13 (re-verify at deploy, H14):
//   * Workers Free: 20,000 files/version
//   * Workers Paid: 100,000 files/version (requires wrangler >= 4.34.0)
//   * 25 MiB/file either way
// This gate PRINTS the count on every CI run (so the trend is visible before it
// bites) and FAILS the build before the ceiling, giving headroom to react.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DIST = path.join(ROOT, "dist");

// The active plan's hard ceiling. Bump to 100_000 (and log it) if/when the
// project moves to Workers Paid — H14 is the owner decision that flips it.
const LIMIT = 20_000;
// Warn here so the count is surfaced well before the ceiling (H14: "when the
// build's file count reports >= 18,000, decide: upgrade or hold state expansion").
const WARN_AT = 18_000;
// The largest file Workers Static Assets will serve.
const MAX_FILE_BYTES = 25 * 1024 * 1024;

if (!fs.existsSync(DIST)) {
  console.error(`file-count check FAILED — no dist/ at ${DIST}; run \`npm run build\` first.`);
  process.exit(1);
}

let files = 0;
const oversize = [];
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(p);
    } else {
      files++;
      const { size } = fs.statSync(p);
      if (size > MAX_FILE_BYTES) oversize.push(`${path.relative(DIST, p)} (${size} bytes)`);
    }
  }
}
walk(DIST);

console.log(`file-count: ${files} built files in dist/ (limit ${LIMIT}, warn ${WARN_AT}).`);

if (oversize.length) {
  console.error(`file-count check FAILED — ${oversize.length} file(s) exceed ${MAX_FILE_BYTES} bytes:`);
  for (const o of oversize.slice(0, 20)) console.error(`  ${o}`);
  process.exit(1);
}

if (files >= LIMIT) {
  console.error(
    `file-count check FAILED — ${files} >= ${LIMIT} (Workers plan file limit). ` +
    `Restructure the vote record (fewer pages) or move to Workers Paid (H14).`
  );
  process.exit(1);
}

if (files >= WARN_AT) {
  console.warn(
    `file-count WARNING — ${files} >= ${WARN_AT}. Approaching the ${LIMIT}-file limit; ` +
    `decide before the next state/coverage expansion (H14).`
  );
}

console.log(`file-count check OK — ${files} files, ${LIMIT - files} under the limit.`);
