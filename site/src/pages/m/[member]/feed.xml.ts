// V2-11 task 7 — one member's feed: their recorded votes and the official actions on
// the bills they sponsored, on one newest-first stream.
//
// A NEW route beside the paginated /m/{id}/{page} pages (the plan's wording). It does
// not collide with them: [page] only ever emits "1", "2", ... as params, and a static
// `feed.xml` segment is matched before a dynamic one either way.
import {
  getMembers, getMemberVotes, getBillsBySponsor, getManifest, recentActions, votedBillIds,
} from "../../../lib/data";
import type { Member } from "../../../lib/data";
import { actionEntries, atomFeed, atomResponse, FEED_LIMIT, rfc3339 } from "../../../lib/atom";
import type { AtomEntry } from "../../../lib/atom";
import { POSITION_LABEL } from "../../../lib/display";

export function getStaticPaths() {
  return getMembers().map((m) => ({ params: { member: m.id }, props: { member: m } }));
}

export function GET({ props, site }: { props: { member: Member }; site: URL | undefined }) {
  const base = site ?? new URL("https://civicledger.net");
  const { member } = props;

  // Votes. The title states the member, their recorded position, and the official
  // question verbatim — all three are facts on the record, and nothing interprets
  // them. `id` is the roll call plus the member, which is unique and stable.
  const voteEntries: AtomEntry[] = getMemberVotes(member.id)
    .slice(0, FEED_LIMIT)
    .map((row) => ({
      id: `${row.rollcall.id}--${member.id}`,
      title: `${member.name} voted ${POSITION_LABEL[row.position]} — ${row.rollcall.question}`,
      updated: row.rollcall.date,
      link: new URL(`/v/${row.rollcall.id}`, base).href,
      content: `${POSITION_LABEL[row.position]} on ${row.rollcall.question} (result: ${row.rollcall.result}).`,
    }));

  // Actions on bills this member sponsored.
  const sponsoredEntries = actionEntries(
    recentActions(getBillsBySponsor(member.id), FEED_LIMIT),
    base,
    votedBillIds(),
  );

  // One stream, newest first. The tie-break is the entry id, so the merge is
  // byte-stable when a vote and a sponsored-bill action land on the same day.
  const entries = [...voteEntries, ...sponsoredEntries].sort((a, b) => {
    const da = rfc3339(a.updated);
    const db = rfc3339(b.updated);
    if (da !== db) return da < db ? 1 : -1;
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  });

  return atomResponse(
    atomFeed({
      selfUrl: new URL(`/m/${member.id}/feed.xml`, base).href,
      alternateUrl: new URL(`/m/${member.id}/1`, base).href,
      title: `${member.name} — votes and sponsored bills`,
      subtitle: "Recorded votes, and official actions on bills this member sponsored.",
      // A member with no votes and no sponsored-bill timelines yet: the dataset's own
      // export date, not a build clock and not a made-up epoch date.
      fallbackUpdated: entries.length ? entries[0].updated : getManifest().generated_at,
      entries,
    }),
  );
}
