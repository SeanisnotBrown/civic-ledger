// V2-11 task 5b — serve the activity feed.
//
// `data/` is not on the web: the repo is private and the loader reads it at BUILD
// time only (§10.1). So the monthly event files need a route, and this is it —
// `/events/2026-03.json` emits `data/events/2026-03.json`.
//
// **Verbatim, byte-for-byte.** The body is the file's own text, not a re-serialised
// object: `verify-recompute` invariant 8 guarantees the BYTES on disk re-derive from
// data/bills + data/votes, and any reshaping here (a re-sort, a different separator,
// a dropped null) would put the served document outside that guarantee. A consumer
// validating against data/schema/events.schema.json must get what Python wrote.
//
// One built file per month (the SD-33 file gate: the build is at 13,161 of the
// 20,000-file free-plan ceiling, and this adds one file per calendar month of
// activity — 22 today, ~48 for two whole Congresses).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { getEventMonths } from "../../lib/data";

const EVENTS_DIR = fileURLToPath(new URL("../../../../data/events/", import.meta.url));

export function getStaticPaths() {
  return getEventMonths().map((month) => ({ params: { month } }));
}

export function GET({ params }: { params: { month: string } }) {
  const body = fs.readFileSync(path.join(EVENTS_DIR, `${params.month}.json`), "utf-8");
  return new Response(body, {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
