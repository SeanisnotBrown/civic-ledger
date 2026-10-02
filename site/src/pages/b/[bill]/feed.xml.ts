// V2-11 task 7 — one bill's feed. The "Track this bill" affordance on /b/{id} points
// here, and it needs no account and records nothing about the reader.
//
// Built for the SAME set of bills that get pages (getPagedBills — SD-33 3(c)). A feed
// per tracked bill would be 38,756 extra built files and would blow the 20,000-file
// Workers Free ceiling on its own; a reader following an unvoted bill follows it on
// congress.gov, which is where its page is.
import { getPagedBills, recentActions, votedBillIds } from "../../../lib/data";
import type { Bill } from "../../../lib/data";
import { actionEntries, atomFeed, atomResponse, FEED_LIMIT } from "../../../lib/atom";
import { billLabel } from "../../../lib/display";

export function getStaticPaths() {
  return getPagedBills().map((b) => ({ params: { bill: b.id }, props: { bill: b } }));
}

export function GET({ props, site }: { props: { bill: Bill }; site: URL | undefined }) {
  const base = site ?? new URL("https://civicledger.net");
  const { bill } = props;
  const refs = recentActions([bill], FEED_LIMIT);

  return atomResponse(
    atomFeed({
      selfUrl: new URL(`/b/${bill.id}/feed.xml`, base).href,
      alternateUrl: new URL(`/b/${bill.id}`, base).href,
      title: `${billLabel(bill.id)} — official actions`,
      subtitle: bill.title_official,
      // `actions` is null until the backfill reaches this bill. The bill's own
      // latest-action date is then the stamp — never a build clock, so a subscriber
      // is not re-notified by a rebuild that changed nothing.
      fallbackUpdated: bill.latest_action_date,
      entries: actionEntries(refs, base, votedBillIds()),
    }),
  );
}
