// V2-11 task 5b — `/events/latest.json`, the one URL an alert consumer polls.
//
// The V2-12 Worker and the V2-13 push client should not have to compute a month
// name to find current activity, so this serves the newest month verbatim, under a
// stable URL.
//
// "Newest month that HAS events", not "the current calendar month" — see
// `latestEventMonth()`. Two reasons, both load-bearing: a build-time `new Date()`
// would put a wall-clock into a built artifact (§6.3 determinism), and on the 1st
// of a month this URL would otherwise serve an empty document while yesterday's
// floor votes sat in the previous month's file.
//
// Before the first events file exists this 404s rather than serving `{}`: an empty
// feed and a missing feed are different facts, and a consumer that cannot tell them
// apart would report "no activity" when the truth is "not published yet" (value #1).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { latestEventMonth } from "../../lib/data";

const EVENTS_DIR = fileURLToPath(new URL("../../../../data/events/", import.meta.url));

export function GET() {
  const month = latestEventMonth();
  if (!month) return new Response("No activity feed published yet.", { status: 404 });
  const body = fs.readFileSync(path.join(EVENTS_DIR, `${month}.json`), "utf-8");
  return new Response(body, {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
