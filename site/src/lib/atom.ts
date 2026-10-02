// Atom 1.0 (RFC 4287) serialisation for the V2-11 task-7 feeds.
//
// Three rules this module exists to keep:
//
// 1. **No wall-clock, anywhere.** A feed's `<updated>` is the newest date in its own
//    entries (or the record's own latest-action date when it has none), never
//    `new Date()`. The build is byte-identical on a quiet day, which is what §6.3
//    determinism and `tests/test_export_contracts.py` require of everything the site
//    emits — a feed stamped with build time would change on every rebuild and would
//    re-notify every subscriber for nothing.
//
// 2. **Entry ids are stable and content-derived.** `entryId()` is the SAME rule as
//    `event_id()` in ingest/events.py: sha256 over the whole action row, canonically
//    serialised with sorted keys and no whitespace, first 12 hex, prefixed with the
//    bill id and date. So one government action has ONE identity whether a reader
//    meets it in a feed or the V2-12 alert Worker meets it in data/events. An index-
//    based id would shift every entry whenever an action is prepended and re-deliver
//    the whole feed to every subscriber.
//
// 3. **Verbatim text.** Action text reaches `<content type="text">` exactly as the
//    government published it, escaped for XML and otherwise untouched: not truncated,
//    not summarised, not reworded (§0.5).
import { createHash } from "node:crypto";

import type { ActionRef } from "./data";
import { billLabel } from "./display";

/** The five XML metacharacters. Attribute and text content both use this. */
export function xmlEscape(s: string): string {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

/** A stored `YYYY-MM-DD` record date as the RFC 3339 timestamp Atom requires.
 *  Midnight UTC, stated explicitly: the government publishes an action DATE, and
 *  `actionTime` exists on well under half of all rows, so inventing a time of day
 *  would be inventing precision the record does not have. */
export function rfc3339(date: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(date);
  return m ? `${m[1]}-${m[2]}-${m[3]}T00:00:00Z` : date;
}

/** Canonical JSON for hashing: keys sorted, no whitespace — the exact shape
 *  `json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`
 *  produces in ingest/events.py. Null-valued keys are INCLUDED, as they are in the
 *  stored record, because the hash covers the whole row. */
function canonicalJson(obj: Record<string, unknown>): string {
  return JSON.stringify(obj, Object.keys(obj).sort());
}

/** The identity of one action. Mirrors `ingest.events.event_id` exactly; see rule 2. */
export function entryId(billId: string, action: Record<string, unknown>): string {
  const digest = createHash("sha256").update(canonicalJson(action), "utf-8").digest("hex").slice(0, 12);
  return `${billId}--${String(action.date)}--${digest}`;
}

export interface AtomEntry {
  /** Stable, content-derived; turned into a tag: IRI by `atomFeed`. */
  id: string;
  title: string;
  /** A record date (`YYYY-MM-DD`) or a full RFC 3339 stamp. */
  updated: string;
  /** Absolute URL the entry points at. */
  link: string;
  /** Verbatim text content. */
  content: string;
}

export interface AtomFeedOptions {
  /** Absolute URL of the feed itself — also its `<id>`. */
  selfUrl: string;
  /** Absolute URL of the human page this feed belongs to. */
  alternateUrl: string;
  title: string;
  subtitle?: string;
  /** Fallback `<updated>` for a feed with no entries (a record's own date). */
  fallbackUpdated: string;
  entries: AtomEntry[];
}

/** How many entries any one feed carries.
 *
 *  Hard constraint, not taste: the site-wide feed spans ~190,000 actions at the full
 *  38,756-bill dataset, and an uncapped document would run past the 25 MiB-per-file
 *  Workers Static Assets limit that `npm run test:file-count` already checks. 50 is
 *  the Atom convention for a "recent items" feed. Mechanical choice — ADR D97. */
export const FEED_LIMIT = 50;

/**
 * One Atom 1.0 document. `entries` must already be newest-first; this applies the
 * FEED_LIMIT cap and derives `<updated>` from what survives it.
 */
export function atomFeed(opts: AtomFeedOptions): string {
  const entries = opts.entries.slice(0, FEED_LIMIT);
  // The feed's own timestamp is the newest it actually carries (entries are
  // newest-first), so it changes only when the data does.
  const updated = rfc3339(entries.length ? entries[0].updated : opts.fallbackUpdated);

  const lines: string[] = [
    '<?xml version="1.0" encoding="utf-8"?>',
    '<feed xmlns="http://www.w3.org/2005/Atom">',
    `  <id>${xmlEscape(opts.selfUrl)}</id>`,
    `  <title>${xmlEscape(opts.title)}</title>`,
    ...(opts.subtitle ? [`  <subtitle>${xmlEscape(opts.subtitle)}</subtitle>`] : []),
    `  <updated>${updated}</updated>`,
    `  <link rel="self" type="application/atom+xml" href="${xmlEscape(opts.selfUrl)}"/>`,
    `  <link rel="alternate" type="text/html" href="${xmlEscape(opts.alternateUrl)}"/>`,
    "  <author><name>Civic Ledger</name></author>",
    "  <rights>Official records of the United States Congress, reproduced verbatim.</rights>",
    `  <generator uri="https://civicledger.net">Civic Ledger</generator>`,
  ];

  for (const e of entries) {
    lines.push(
      "  <entry>",
      // A tag: IRI (RFC 4151) — permanent, and independent of the URL the entry is
      // served from, so moving a page never re-notifies a reader.
      `    <id>tag:civicledger.net,2026:${xmlEscape(e.id)}</id>`,
      `    <title>${xmlEscape(e.title)}</title>`,
      `    <updated>${rfc3339(e.updated)}</updated>`,
      `    <link rel="alternate" type="text/html" href="${xmlEscape(e.link)}"/>`,
      `    <content type="text">${xmlEscape(e.content)}</content>`,
      "  </entry>",
    );
  }

  lines.push("</feed>", "");
  return lines.join("\n");
}

/** The response every feed endpoint returns.
 *
 *  The content type is the registered Atom one, but note it is advisory in a STATIC
 *  build: the endpoint runs at build time and writes a `.xml` file, after which the
 *  serving layer decides the header from the extension (astro preview sends
 *  `text/xml`). Every feed reader accepts an XML type, so this is cosmetic — it is
 *  set because it states the intent and would be authoritative if these ever became
 *  server-rendered. */
export function atomResponse(body: string): Response {
  return new Response(body, {
    headers: { "content-type": "application/atom+xml; charset=utf-8" },
  });
}

/**
 * Action refs as Atom entries.
 *
 * `voted` is the set of bill ids that actually have a `/b/` page (SD-33 3(c)). An
 * entry for a bill without one links to the bill's own `source_url` on congress.gov,
 * never to a `/b/` URL that was never built — `npm run test:links` fails on the first
 * such link, by design, because a dead link to our own site is a broken promise in a
 * way an outbound link to the official record is not.
 *
 * The title carries the bill label plus the action text verbatim and is NOT truncated:
 * a shortened government sentence in a reader's notification list is a paraphrase the
 * government did not write (§0.5). The same text is in `<content>` for clients that
 * render bodies.
 */
export function actionEntries(refs: ActionRef[], base: URL, voted: Set<string>): AtomEntry[] {
  return refs.map((r) => ({
    id: entryId(r.bill.id, r.action as unknown as Record<string, unknown>),
    title: `${billLabel(r.bill.id)} — ${r.action.text}`,
    updated: r.action.date,
    link: voted.has(r.bill.id)
      ? new URL(`/b/${r.bill.id}`, base).href
      : r.bill.source_url,
    content: r.action.text,
  }));
}
