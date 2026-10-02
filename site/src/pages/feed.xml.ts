// V2-11 task 7 — the site-wide activity feed.
//
// Every official action on every tracked bill, newest first, capped at FEED_LIMIT.
// Deliberately NOT filtered by action type: `type` is the government's field, and
// publishing only a chosen subset of its values would be this site deciding which
// government records count — an editorial judgment it has no basis to make. The feed
// is therefore named for what it actually contains, legislative activity, rather than
// claiming to be floor-only.
import { getBills, getManifest, recentActions, votedBillIds } from "../lib/data";
import { actionEntries, atomFeed, atomResponse, FEED_LIMIT } from "../lib/atom";

export function GET({ site }: { site: URL | undefined }) {
  const base = site ?? new URL("https://civicledger.net");
  const refs = recentActions(getBills(), FEED_LIMIT);

  return atomResponse(
    atomFeed({
      selfUrl: new URL("/feed.xml", base).href,
      alternateUrl: new URL("/federal", base).href,
      title: "Civic Ledger — legislative activity",
      subtitle: "Every official action recorded on tracked bills, newest first.",
      // An empty feed is only possible before the activity backfill has written
      // anything; the dataset's own export date is then the honest stamp.
      fallbackUpdated: getManifest().generated_at,
      entries: actionEntries(refs, base, votedBillIds()),
    }),
  );
}
