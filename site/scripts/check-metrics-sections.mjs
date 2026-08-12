// INC-10 acceptance: "the methodology page contains one section per exported
// metric." Assert SET EQUALITY between the metric keys in data/metrics.json and the
// `data-metric` sections rendered on the built /methods page — so a metric can
// never ship without its methodology, and no orphan section can linger. Exit
// nonzero on any asymmetry.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DATA = path.join(ROOT, "..", "data");
const DIST = path.join(ROOT, "dist");

const metrics = JSON.parse(fs.readFileSync(path.join(DATA, "metrics.json"), "utf-8"));
const metricKeys = new Set(Object.keys(metrics.methodology));

const html = fs.readFileSync(path.join(DIST, "methods", "index.html"), "utf-8");
const sections = new Set(
  [...html.matchAll(/data-metric="([^"]+)"/g)].map((m) => m[1]),
);

const missingSections = [...metricKeys].filter((k) => !sections.has(k));
const orphanSections = [...sections].filter((k) => !metricKeys.has(k));

if (missingSections.length || orphanSections.length) {
  console.error("metrics-sections check FAILED — page/metric set mismatch:");
  if (missingSections.length) console.error(`  metrics with no section: ${missingSections.join(", ")}`);
  if (orphanSections.length) console.error(`  sections with no metric: ${orphanSections.join(", ")}`);
  process.exit(1);
}
console.log(`metrics-sections check OK — ${metricKeys.size} metrics, each with exactly one section.`);
