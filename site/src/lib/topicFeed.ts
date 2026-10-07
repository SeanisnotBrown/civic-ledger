// One topic's Atom feed, shared by both vocabulary routes.
// `IMPLEMENTATIONv3.md` §4.7 (topics and alerts).
//
// The most recent official actions on every bill the government classified under this
// term. This is the "get an alert when a bill that affects X comes up" path, and it
// needs no account. Do NOT re-add a claim that it records nothing about the reader:
// the owner ruled on 2026-09-30 that this claim family be stripped, not reworded,
// because the no-logging claim is impossible for what the project needs to do, and
// feed polling makes it worse — a feed reader is a recurring request pattern the host
// sees. Stripped from the bill page 2026-10-05 on the owner's word, and the privacy
// surface now describes those logs rather than denying them: see /privacy,
// site/src/lib/storageDisclosure.ts, and tests/test_privacy_accuracy.py.
import { getTopicBills, getTopicPath, recentActions, votedBillIds } from "./data";
import type { Topic } from "./data";
import { actionEntries, atomFeed, atomResponse, FEED_LIMIT } from "./atom";

const VOCAB: Record<Topic["vocabulary"], string> = {
  policy_area: "policy area",
  subject: "legislative subject term",
};

export function topicFeedResponse(topic: Topic, site: URL | undefined): Response {
  const base = site ?? new URL("https://civicledger.net");
  const bills = getTopicBills(topic);
  const path = getTopicPath(topic);

  return atomResponse(
    atomFeed({
      selfUrl: new URL(`${path}/feed.xml`, base).href,
      alternateUrl: new URL(path, base).href,
      title: `${topic.name} — official actions`,
      subtitle: `Bills the government classified under the ${VOCAB[topic.vocabulary]} "${topic.name}".`,
      // Every bill in the topic may still be awaiting its timeline. The newest
      // latest-action date among them (getTopicBills sorts newest first) is then the
      // honest stamp — never a build clock, which would re-notify every subscriber on
      // a rebuild that changed nothing.
      fallbackUpdated: bills.length ? bills[0].latest_action_date : "",
      entries: actionEntries(recentActions(bills, FEED_LIMIT), base, votedBillIds()),
    }),
  );
}
