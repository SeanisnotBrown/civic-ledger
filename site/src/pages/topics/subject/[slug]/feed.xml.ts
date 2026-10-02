// V2-11 task 7 — the Atom feed for one CRS legislative subject term. Body in
// lib/topicFeed.ts.
import { getTopicsOf } from "../../../../lib/data";
import type { Topic } from "../../../../lib/data";
import { topicFeedResponse } from "../../../../lib/topicFeed";

export function getStaticPaths() {
  return getTopicsOf("subject").map((t) => ({ params: { slug: t.slug }, props: { topic: t } }));
}

export function GET({ props, site }: { props: { topic: Topic }; site: URL | undefined }) {
  return topicFeedResponse(props.topic, site);
}
