// §6.8 render-side disclosure guard (V2-4). Every grade label the site RENDERS must
// be a string the owner ratified. The allowed set is every band label + exception
// label in the committed data/grades/*.json (the python integrity guard ties those,
// in turn, to data/config/thresholds.yaml). This catches an evaluative string typed
// straight into a template that never went through the ratified config. Rendered
// labels are marked `<span data-grade-label>…</span>` so extraction is exact.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DATA = path.join(ROOT, "..", "data");
const DIST = path.join(ROOT, "dist");
const GRADES_DIR = path.join(DATA, "grades");

const gradeFiles = fs.existsSync(GRADES_DIR)
  ? fs.readdirSync(GRADES_DIR).filter((f) => f.endsWith(".json"))
  : [];
if (!gradeFiles.length) {
  console.log("grade-labels check: no grades yet (no-op).");
  process.exit(0);
}

// Allowed strings + representative pages to scan (one graded + one excepted member).
const allowed = new Set();
const memberPages = [];
for (const f of gradeFiles) {
  const g = JSON.parse(fs.readFileSync(path.join(GRADES_DIR, f), "utf-8"));
  for (const b of g.bands) allowed.add(b.label);
  allowed.add(g.exception_label);
  const graded = Object.keys(g.members).sort();
  const excepted = Object.keys(g.exceptions).sort();
  if (graded.length) memberPages.push(graded[0]);
  if (excepted.length) memberPages.push(excepted[0]);
}

// The MemberStats component is shared by every member page, so a stray hardcoded label
// would appear on all of them — scanning /methods + a graded + an excepted page is
// enough to catch it.
const pages = ["methods/index.html", ...memberPages.map((b) => path.join("m", b, "1", "index.html"))];

const stray = new Set();
let scanned = 0;
for (const rel of pages) {
  const p = path.join(DIST, rel);
  if (!fs.existsSync(p)) continue;
  scanned++;
  const html = fs.readFileSync(p, "utf-8");
  for (const m of html.matchAll(/data-grade-label>([^<]+)</g)) {
    const label = m[1].trim();
    if (!allowed.has(label)) stray.add(label);
  }
}

if (stray.size) {
  console.error("grade-labels check FAILED — rendered grade label(s) not in the ratified config:");
  for (const s of stray) console.error(`  ${JSON.stringify(s)}`);
  process.exit(1);
}
console.log(
  `grade-labels check OK — ${scanned} page(s) scanned; every rendered grade label is a ` +
    `ratified string (${allowed.size} allowed).`,
);
