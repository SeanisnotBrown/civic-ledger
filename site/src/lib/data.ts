// Build-time data access over the committed dataset (../../../data/**). Runs in
// Node during `astro build` only — the site ships as static HTML with zero
// runtime data fetching (§10.1). Types mirror ingest/models.py exactly; the
// canonical machine contract is data/schema/*.schema.json (see docs/data-contract.md).

import fs from "node:fs";
import { resolvesMeasure } from "./motions";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { STATE_NAME } from "./states";

const DATA_DIR = fileURLToPath(new URL("../../../data/", import.meta.url));

// --- Types (mirror §5 / data-contract.md) --------------------------------

export type Party = "D" | "R" | "I";
export type Chamber = "house" | "senate";
export type Position = "yea" | "nay" | "present" | "not_voting";
export type VoteClass =
  | "passage" | "amendment" | "procedural" | "nomination" | "veto_override" | "other";

export type Jurisdiction = "us" | "ms";
export interface Term { start: string; end: string; party: Party; chamber: Chamber; }
export interface Member {
  id: string; ids: Record<string, string>; name: string; party: Party;
  state: string; district: number | null; chamber: Chamber; jurisdiction: Jurisdiction;
  serving: boolean; terms: Term[];
}
export interface RollCall {
  id: string; chamber: Chamber; jurisdiction: Jurisdiction; congress: number | null;
  session: number; number: number;
  date: string; question: string; vote_class: VoteClass; vote_class_rule: string;
  bill_id: string | null; result: string; totals: Record<string, number>;
  // Per-party position tallies (INC-10 aggregate; recomputable from member_votes).
  // Keyed by party letter → position → count. Present on every federal roll.
  party_totals: Record<string, Record<string, number>>;
  source_url: string;
  // Which amendment this roll call was on, when the record names one. The House
  // clerk carries both in its own fields; the Senate writes the number into the
  // question text and names no sponsor. Absent on every non-amendment roll, and
  // absent until `ingest vote-amendments` has run over the roll.
  amendment_number?: string | null;
  amendment_sponsor?: string | null;
}
export interface MemberVote { member_id: string; rollcall_id: string; position: Position; }
export interface VoteFile { rollcall: RollCall; member_votes: MemberVote[]; }
export interface Absence {
  member_id: string; rollcall_id: string;
  stated_reason: string | null; stated_reason_source: string | null;
  declared_position: "yea" | "nay" | null;
}
export interface CboRef { url: string; title: string; date: string; }

// V2-11: one step in a bill's official action timeline. Mirrors ingest/models.py
// BillAction exactly, including which fields are nullable (that list is MEASURED over
// 520 real actions, see the model's docstring). `text` is the government's own
// published sentence, stored and rendered VERBATIM — never summarised or reworded
// (§0.5). `committees` is not decoration: it is the only thing distinguishing several
// otherwise byte-identical rows on one day (hr2670-118 has five). `rollcall_id` is set
// only when the action's recorded vote resolves to a roll call this dataset holds.
export interface BillAction {
  date: string; time: string | null; text: string; type: string;
  action_code: string | null; source_system: string;
  committees: string[] | null; rollcall_id: string | null;
}

export interface Bill {
  id: string; jurisdiction: Jurisdiction; congress: number | null; type: string;
  number: number; title_official: string;
  policy_area: string | null; subjects: string[] | null; sponsor_id: string | null;
  cosponsor_ids: string[] | null;
  // NOT COLLECTED is the D27 `null` sentinel — and note the field is OPTIONAL here,
  // because the deterministic exporter omits a None field entirely rather than writing
  // `"actions": null`, so on a bill the activity backfill has not reached the key is
  // simply absent. Absent and null mean the same thing; both are distinct from `[]`,
  // which means collected and the government lists none. Rendering an empty timeline
  // for either of the first two would publish "this bill has had no actions", which is
  // false framing (Value #1) — so the cases get different copy wherever they surface.
  actions?: BillAction[] | null;
  latest_action: string; latest_action_date: string;
  cbo_estimates: CboRef[]; source_url: string;
}
export interface Manifest {
  generated_at: string; commit: string; congresses: number[];
  counts: Record<string, unknown>;
}
// `digest` is the metric function's formula identity (R-3/D45); `schema_version`
// on Metrics is the formula-generation stamp. Both are provenance for cross-time
// comparison — nothing on the site renders a score from them.
export interface MetricMethodology { label: string; text: string; digest: string; }
export interface Metrics {
  schema_version: number;
  // methodology keys == per-member metric keys == methods-page section ids.
  methodology: Record<string, MetricMethodology>;
  members: Record<string, Record<string, unknown>>;
}
// V2-2 rankings (data/rankings/{metric}.json). Pure per-chamber rank/percentile/
// mean context; no label/score (that is V2-4). `value` is a count (int) or a
// percentage (float) depending on the metric.
export interface RankingEntry { value: number; rank: number; percentile: number; }
export interface ChamberRanking {
  covered: number;
  mean: number | null;
  median: number | null;
  party_means: Record<string, number>;
  excluded_delegates: string[];
  members: Record<string, RankingEntry>;
}
export interface RankingsFile {
  metric: string; value_field: string; label: string; methodology: string;
  ranks_delegates: boolean;
  chambers: Record<string, ChamberRanking>;
}

// --- Low-level readers (memoized at module scope) -------------------------

function readJson<T>(rel: string): T {
  return JSON.parse(fs.readFileSync(path.join(DATA_DIR, rel), "utf-8")) as T;
}

function readDir(sub: string): string[] {
  const dir = path.join(DATA_DIR, sub);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((f) => f.endsWith(".json")).sort();
}

// V2-1: data/absences/ is sharded one level by congress (too many files for one
// flat directory at full-roster scale — ~35,000 stubs). Returns paths relative
// to `sub`, e.g. "118/E000235--h-118-1-0021.json".
function readNestedDir(sub: string): string[] {
  const dir = path.join(DATA_DIR, sub);
  if (!fs.existsSync(dir)) return [];
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      for (const f of fs.readdirSync(path.join(dir, entry.name))) {
        if (f.endsWith(".json")) out.push(`${entry.name}/${f}`);
      }
    } else if (entry.name.endsWith(".json")) {
      out.push(entry.name);
    }
  }
  return out.sort();
}

let _members: Member[] | null = null;
export function getMembers(): Member[] {
  if (_members) return _members;
  _members = readDir("members").map((f) => readJson<Member>(`members/${f}`));
  _members.sort((a, b) => a.name.localeCompare(b.name));
  return _members;
}
export function getMember(id: string): Member | undefined {
  return getMembers().find((m) => m.id === id);
}

let _votes: VoteFile[] | null = null;
export function getAllVotes(): VoteFile[] {
  if (_votes) return _votes;
  _votes = readDir("votes").map((f) => readJson<VoteFile>(`votes/${f}`));
  return _votes;
}

let _bills: Map<string, Bill> | null = null;
function billMap(): Map<string, Bill> {
  if (_bills) return _bills;
  _bills = new Map();
  for (const f of readDir("bills")) {
    const b = readJson<Bill>(`bills/${f}`);
    _bills.set(b.id, b);
  }
  return _bills;
}
export function getBills(): Bill[] {
  return [...billMap().values()].sort((a, b) => a.id.localeCompare(b.id));
}

let _votedBillIds: Set<string> | null = null;
/** Bill ids that reached a recorded vote. Built once: the naive form calls
 *  getVotesForBill() per bill, which is a full scan of every roll call each
 *  time — fine over 1,038 bills, O(bills x votes) over 38,756. */
export function votedBillIds(): Set<string> {
  if (_votedBillIds) return _votedBillIds;
  _votedBillIds = new Set();
  for (const v of getAllVotes()) {
    if (v.rollcall.bill_id) _votedBillIds.add(v.rollcall.bill_id);
  }
  return _votedBillIds;
}

/** The bills that GET A PAGE — owner decision SD-33 3(c): the dataset tracks
 *  every bill in the covered Congresses (38,756), but only the ones that
 *  reached a recorded vote get a /b/ page. Everything else is reachable
 *  through its source_url on congress.gov.
 *
 *  This filter must stay AHEAD of the activity backfill: getStaticPaths used
 *  to map over every file in data/bills/, which was the same set as the voted
 *  set until the backfill started adding unvoted bills. */
export function getPagedBills(): Bill[] {
  const voted = votedBillIds();
  return getBills().filter((b) => voted.has(b.id));
}
export function getBill(id: string): Bill | undefined {
  return billMap().get(id);
}

// --- Topics (V2-11 tasks 6-7) --------------------------------------------
// data/topics/index.json, built by `uv run ingest topics` from data/bills/**.
// SD-33 4(a): the vocabulary is the GOVERNMENT'S — the 31 CRS policy areas and the
// CRS legislative subject terms, verbatim. The site invents no label and rewords
// none. `slug` is the only thing the pipeline adds, it is mechanical, and it is read
// from this file rather than re-derived here: two slug rules that drift by one
// character produce links to pages that do not exist.

export type TopicVocabulary = "policy_area" | "subject";

export interface TopicEntry {
  slug: string; name: string; bill_count: number; bill_ids: string[];
}
export interface TopicsIndex {
  counts: { bills: number; policy_areas: number; subjects: number };
  policy_areas: TopicEntry[];
  subjects: TopicEntry[];
}
/** A topic plus which official vocabulary it came from — the site states that
 *  provenance next to the term, because "Health" the policy area and a subject term
 *  are different government classifications and conflating them would misdescribe
 *  both. */
export type Topic = TopicEntry & { vocabulary: TopicVocabulary };

let _topicsIndex: TopicsIndex | null = null;
export function getTopicsIndex(): TopicsIndex {
  if (_topicsIndex) return _topicsIndex;
  try {
    _topicsIndex = readJson<TopicsIndex>("topics/index.json");
  } catch {
    // Absent on a checkout that never ran `ingest topics` — no topics, no pages.
    _topicsIndex = { counts: { bills: 0, policy_areas: 0, subjects: 0 }, policy_areas: [], subjects: [] };
  }
  return _topicsIndex;
}

/** Every topic across both vocabularies, policy areas first then subjects, each
 *  already slug-sorted by the Python projection. One flat list because `/topics/
 *  [slug]/` is one URL namespace. */
let _topics: Topic[] | null = null;
export function getTopics(): Topic[] {
  if (_topics) return _topics;
  const idx = getTopicsIndex();
  _topics = [
    ...idx.policy_areas.map((t) => ({ ...t, vocabulary: "policy_area" as const })),
    ...idx.subjects.map((t) => ({ ...t, vocabulary: "subject" as const })),
  ];
  return _topics;
}

/** The URL prefix for each official vocabulary, and the reason the two are separate
 *  URL namespaces at all.
 *
 *  `ingest/topics.py` keeps policy areas and subject terms apart ON PURPOSE, and
 *  `test_policy_areas_and_subjects_are_separate_vocabularies` pins it: "Health" the
 *  policy area and "Health" the subject term are different government claims about a
 *  bill, and both are valid output at once. A single flat `/topics/{slug}/` namespace
 *  would be exactly the merge that module's docstring forbids — one page silently
 *  meaning both — so the vocabulary is part of the path. (The V2-11 plan text says
 *  `/topics/[slug]/`; it was written before this separation was committed code, and
 *  the spec preamble makes the code authoritative. ADR D97.)
 */
export const TOPIC_PATH_SEGMENT: Record<TopicVocabulary, string> = {
  policy_area: "policy-area",
  subject: "subject",
};

/** The canonical path of a topic page. Every surface that links a topic goes through
 *  this — six files would otherwise each carry their own copy of the prefix rule. */
export function getTopicPath(topic: Topic): string {
  return `/topics/${TOPIC_PATH_SEGMENT[topic.vocabulary]}/${topic.slug}`;
}

/** Only the topics of one vocabulary — each vocabulary has its own route file, so a
 *  mistyped segment fails the build instead of quietly becoming a third namespace. */
export function getTopicsOf(vocabulary: TopicVocabulary): Topic[] {
  return getTopics().filter((t) => t.vocabulary === vocabulary);
}

let _topicBySlug: Map<string, Topic> | null = null;
export function getTopic(slug: string): Topic | undefined {
  if (!_topicBySlug) _topicBySlug = new Map(getTopics().map((t) => [t.slug, t]));
  return _topicBySlug.get(slug);
}

/** The topic for an official term as it appears on a bill (`policy_area`, or one of
 *  `subjects`). Looked up BY NAME in the committed index so the slug in a link is
 *  always the same string the page was built at — a second slug rule in TypeScript
 *  that drifted by one character would link to pages that do not exist. A term absent
 *  from the index (the index is regenerated by `ingest topics`, which can lag a bill
 *  write) returns undefined, and callers then render the term as plain text rather
 *  than a dead link. */
let _topicByName: Map<string, Topic> | null = null;
export function getTopicByName(name: string, vocabulary: TopicVocabulary): Topic | undefined {
  if (!_topicByName) {
    _topicByName = new Map(getTopics().map((t) => [`${t.vocabulary} ${t.name}`, t]));
  }
  return _topicByName.get(`${vocabulary} ${name}`);
}

/** A topic's bills as records, most recent official action first.
 *
 *  Sorted on `latest_action_date` (not on `actions`, which is null for every bill the
 *  activity backfill has not reached — see Bill.actions) with a bill-id tie-break so
 *  the page is byte-stable. Ids with no bill file are dropped: the index is projected
 *  from data/bills/, so that can only happen mid-regeneration, and a missing record
 *  must not take the build down. */
export function getTopicBills(topic: Topic): Bill[] {
  const bills: Bill[] = [];
  for (const id of topic.bill_ids) {
    const b = getBill(id);
    if (b) bills.push(b);
  }
  bills.sort((a, b) =>
    a.latest_action_date !== b.latest_action_date
      ? (a.latest_action_date < b.latest_action_date ? 1 : -1)
      : a.id.localeCompare(b.id),
  );
  return bills;
}

// --- Action streams for the feeds (V2-11 task 7) -------------------------

/** One action together with the bill it belongs to — what a feed entry is made of. */
export interface ActionRef { bill: Bill; action: BillAction; index: number }

/**
 * The most recent `limit` actions across `bills`, newest first.
 *
 * Ordering is `date` descending, then bill id, then the action's position in its
 * bill's stored array. That last key matters and is not arbitrary: the government
 * returns a bill's actions newest-first and the pipeline preserves that order
 * verbatim, so position ascending IS newest-first within a day — and `date` alone
 * cannot order the dozen actions a busy bill can collect on one day (`time` is
 * present on under half of all rows, so it is unusable as a sort key). Bill id in
 * the middle keeps the result byte-stable across runs.
 *
 * Bills whose `actions` is null (not collected yet) contribute nothing, which is
 * correct: a feed must not imply a bill has had no activity when the truth is that
 * this dataset has not looked yet.
 */
export function recentActions(bills: Bill[], limit: number): ActionRef[] {
  const refs: ActionRef[] = [];
  for (const bill of bills) {
    if (!bill.actions) continue;
    for (let i = 0; i < bill.actions.length; i++) {
      refs.push({ bill, action: bill.actions[i], index: i });
    }
  }
  refs.sort((a, b) => {
    if (a.action.date !== b.action.date) return a.action.date < b.action.date ? 1 : -1;
    if (a.bill.id !== b.bill.id) return a.bill.id < b.bill.id ? -1 : 1;
    return a.index - b.index;
  });
  return refs.slice(0, limit);
}

/** Bills a member sponsored, most recent action first. Memoized as one index: the
 *  naive form scans every bill once per member, which is ~38,756 x ~541 at full
 *  scale. */
let _billsBySponsor: Map<string, Bill[]> | null = null;
export function getBillsBySponsor(memberId: string): Bill[] {
  if (!_billsBySponsor) {
    const index = new Map<string, Bill[]>();
    for (const b of getBills()) {
      if (!b.sponsor_id) continue;
      let list = index.get(b.sponsor_id);
      if (!list) { list = []; index.set(b.sponsor_id, list); }
      list.push(b);
    }
    for (const list of index.values()) {
      list.sort((a, b) =>
        a.latest_action_date !== b.latest_action_date
          ? (a.latest_action_date < b.latest_action_date ? 1 : -1)
          : a.id.localeCompare(b.id),
      );
    }
    _billsBySponsor = index;
  }
  return _billsBySponsor.get(memberId) ?? [];
}

// --- Events (V2-11 task 5b) ----------------------------------------------
// data/events/{YYYY-MM}.json, served verbatim by src/pages/events/[month].json.ts.
// These are the ONLY machine-readable URLs the V2-12 alert Worker and the V2-13
// push client read, so the endpoint must not reshape, filter or re-sort what the
// Python projection wrote — `verify-recompute` invariant 8 guarantees the bytes on
// disk, and anything this layer changed would be outside that guarantee.

export interface BillEvent {
  id: string; bill_id: string; date: string; text: string; type: string;
  action_code: string | null; source_system: string;
  committees: string[] | null; rollcall_id: string | null;
  policy_area: string | null; subjects: string[] | null;
  source_url: string;
  // SD-33 3(c): whether /b/{bill_id} exists. A consumer links to the page when
  // true and to source_url on congress.gov when false — never to a /b/ URL that
  // was never built, or `npm run test:links` fails on the first one.
  has_page: boolean;
}
export interface EventsFile { month: string; count: number; events: BillEvent[]; }

/** Every month that has an events file, oldest first ("2026-03"). */
export function getEventMonths(): string[] {
  return readDir("events").map((f) => f.replace(/\.json$/, ""));
}

export function getEventsFile(month: string): EventsFile {
  return readJson<EventsFile>(`events/${month}.json`);
}

/** The month `/events/latest.json` serves.
 *
 *  The NEWEST month that actually has events — deliberately not "the current
 *  calendar month". A build-time `new Date()` would put a wall-clock in a built
 *  artifact (§6.3 determinism), and in the first days of a quiet month it would
 *  serve an empty file while real activity sat in the previous one. Undefined
 *  only before the first events file exists. */
export function latestEventMonth(): string | undefined {
  const months = getEventMonths();
  return months.length ? months[months.length - 1] : undefined;
}

let _absences: Map<string, Absence> | null = null;
function absenceMap(): Map<string, Absence> {
  if (_absences) return _absences;
  _absences = new Map();
  for (const f of readNestedDir("absences")) {
    const a = readJson<Absence>(`absences/${f}`);
    _absences.set(`${a.member_id}--${a.rollcall_id}`, a);
  }
  return _absences;
}
export function getAbsence(memberId: string, rollId: string): Absence | undefined {
  return absenceMap().get(`${memberId}--${rollId}`);
}

let _manifest: Manifest | null = null;
export function getManifest(): Manifest {
  if (_manifest) return _manifest;
  _manifest = readJson<Manifest>("manifest.json");
  return _manifest;
}

let _metrics: Metrics | null = null;
export function getMetrics(): Metrics {
  if (_metrics) return _metrics;
  _metrics = readJson<Metrics>("metrics.json");
  return _metrics;
}

// V2-2: every data/rankings/{metric}.json, keyed by metric. Empty before V2-2's
// `ingest rankings` has run (readDir returns [] on a missing directory).
let _rankings: Record<string, RankingsFile> | null = null;
export function getRankings(): Record<string, RankingsFile> {
  if (_rankings) return _rankings;
  const out: Record<string, RankingsFile> = {};
  for (const f of readDir("rankings")) {
    const rf = readJson<RankingsFile>(`rankings/${f}`);
    out[rf.metric] = rf;
  }
  _rankings = out;
  return _rankings;
}

// V2-3: one member's rank context, per ranked metric, within their chamber — for the
// member-page stat tiles. A metric is present ONLY when the member is actually ranked
// on it: a null metric value, or a non-voting delegate on a vote metric (D66), yields
// no entry (the tile then shows the figure with no rank line). MS members have no
// federal rankings, so this returns {} for them.
export interface MemberRank { rank: number; percentile: number; covered: number; }
export function getMemberRanks(memberId: string, chamber: string): Record<string, MemberRank> {
  const out: Record<string, MemberRank> = {};
  for (const [metric, rf] of Object.entries(getRankings())) {
    const ch = rf.chambers[chamber];
    const entry = ch?.members[memberId];
    if (entry) out[metric] = { rank: entry.rank, percentile: entry.percentile, covered: ch.covered };
  }
  return out;
}

// V2-4 grades (data/grades/{category}.json). Computed only in ingest/scoring.py from
// the owner-ratified thresholds; every label here appears verbatim in that config.
export interface GradeBand { grade: string; min: number; label: string; }
export interface GradeEntry { value: number; grade: string; label: string; }
export interface GradesFile {
  category: string; metric: string; field: string; formula_version: number;
  ratified: string; min_eligible: number; bands: GradeBand[]; exception_label: string;
  members: Record<string, GradeEntry>; exceptions: Record<string, string>;
}
let _grades: Record<string, GradesFile> | null = null;
export function getGrades(): Record<string, GradesFile> {
  if (_grades) return _grades;
  const out: Record<string, GradesFile> = {};
  for (const f of readDir("grades")) {
    const gf = readJson<GradesFile>(`grades/${f}`);
    out[gf.category] = gf;
  }
  _grades = out;
  return _grades;
}
// Graded attendance values grouped by chamber (for the member-profile distribution
// strip). Memoized: computed once from the grades export + the member roster, not
// per page. Each entry is {value, grade} for a graded member of that chamber; the
// non-comparability of House vs Senate attendance (why ranks are per-chamber, D66)
// is why this is grouped rather than one pooled distribution.
let _gradedAtt: { house: { value: number; grade: string }[]; senate: { value: number; grade: string }[] } | null = null;
export function getGradedAttendanceByChamber(): {
  house: { value: number; grade: string }[]; senate: { value: number; grade: string }[];
} {
  if (_gradedAtt) return _gradedAtt;
  const out = { house: [] as { value: number; grade: string }[], senate: [] as { value: number; grade: string }[] };
  const g = getGrades().attendance;
  if (g) {
    const chamberOf = new Map(getMembers().map((m) => [m.id, m.chamber]));
    for (const [id, e] of Object.entries(g.members)) {
      const ch = chamberOf.get(id);
      if (ch === "house" || ch === "senate") out[ch].push({ value: e.value, grade: e.grade });
    }
    out.house.sort((a, b) => a.value - b.value);
    out.senate.sort((a, b) => a.value - b.value);
  }
  _gradedAtt = out;
  return out;
}

// One member's grade for a category: the ratified grade+label if graded, or the
// exception reason + rendered label if set aside. undefined if grades don't exist for
// this member (MS members have no federal grades) or the category is absent.
export interface MemberGrade {
  grade?: string; label?: string; exception?: string; exceptionLabel?: string;
}
export function getMemberGrade(memberId: string, category = "attendance"): MemberGrade | undefined {
  const gf = getGrades()[category];
  if (!gf) return undefined;
  const entry = gf.members[memberId];
  if (entry) return { grade: entry.grade, label: entry.label };
  const reason = gf.exceptions[memberId];
  if (reason) return { exception: reason, exceptionLabel: gf.exception_label };
  return undefined;
}

export interface Statement {
  id: string; member_id: string; text: string; date: string; venue: string;
  source_url: string; archive_url: string; archive_captured_at: string;
  named_measures: string[]; paired_bill_ids: string[];
  specificity_level: 0 | 1 | 2 | 3 | null;
  stated_position: "support" | "oppose" | null; curator_note: string | null;
  // P3 task 6: owner-approved policy area and Q-J priority signal (absent on records
  // curated before the fields existed — read as null).
  topic?: string | null; priority_signal?: boolean | null;
}

// --- Stated priorities (P3 task 6) ---------------------------------------
// Computed in Python (ingest/priorities.py) from the approved statements and the ratified
// Q-B / Q-J rules, re-derived by verify-recompute; the site only reads it. A member absent
// from the file has no approved statement on record. `priorities` exists only for a member
// who clears the Q-B bar: below it nothing is inferred, so nothing is published.
export interface StatedPriority {
  topic: string; stance: "support" | "oppose";
  routes: ("signal" | "repetition")[]; statement_ids: string[];
}
export interface MemberPriorities {
  approved_statements: number; distinct_topics: number; listed: boolean;
  priorities?: StatedPriority[]; conflicted_topics?: string[];
}
export interface PrioritiesFile {
  bar: { min_approved_statements: number; min_distinct_topics: number };
  // Owner ruling 9, 2026-10-23: false until the list wording (AES-14) is ratified; while
  // false no priorities list is rendered for anyone.
  list_wording_ratified: boolean;
  members: Record<string, MemberPriorities>;
}
let _priorities: PrioritiesFile | null = null;
export function getPrioritiesFile(): PrioritiesFile {
  if (!_priorities) _priorities = readJson<PrioritiesFile>("priorities.json");
  return _priorities;
}
export function getMemberPriorities(memberId: string): MemberPriorities {
  return getPrioritiesFile().members[memberId]
    ?? { approved_statements: 0, distinct_topics: 0, listed: false };
}

/**
 * Statement ids the weekly archive-link sweep flagged as having a dead archive_url
 * (checks/archive_links.py). A statement whose permanent capture no longer resolves
 * is UNPUBLISHABLE until recaptured — the build excludes it. Report absent (never
 * run, or a bare checkout) → nothing excluded.
 */
let _deadStatementIds: Set<string> | null = null;
function deadStatementIds(): Set<string> {
  if (_deadStatementIds) return _deadStatementIds;
  try {
    const report = readJson<{ dead_statement_ids?: string[] }>("quality/archive-status.json");
    _deadStatementIds = new Set(report.dead_statement_ids ?? []);
  } catch {
    _deadStatementIds = new Set();
  }
  return _deadStatementIds;
}

let _statements: Statement[] | null = null;
/**
 * Every PUBLISHABLE curated statement (dead-archive ones excluded), newest first.
 * This is the TypeScript MIRROR of the Python loader ingest/statements_io.py
 * (load_statements(exclude_dead=True)) — the same publishability rule (skip `_`-config,
 * drop dead-archive ids). That module is the semantic source of truth (R-1b/M-3); keep
 * the two in step.
 */
export function getStatements(): Statement[] {
  if (_statements) return _statements;
  const dead = deadStatementIds();
  _statements = readDir("statements")
    .filter((f) => !f.startsWith("_")) // _title_allowlist etc. are config, not records
    .map((f) => readJson<Statement>(`statements/${f}`))
    .filter((s) => !dead.has(s.id));
  _statements.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : a.id < b.id ? 1 : -1));
  return _statements;
}
export function getMemberStatements(memberId: string): Statement[] {
  return getStatements().filter((s) => s.member_id === memberId);
}

// --- Mississippi state layer (INC-12) ------------------------------------
// Read from the data/state/ms/ partition. Kept as separate loaders (not merged into
// the federal ones) so the federal site is byte-identical when no state data exists,
// and the two jurisdictions never accidentally cross-contaminate a page.

const MS_DIR = fileURLToPath(new URL("../../../data/state/ms/", import.meta.url));

function readMsJson<T>(rel: string): T {
  return JSON.parse(fs.readFileSync(path.join(MS_DIR, rel), "utf-8")) as T;
}
function readMsDir(sub: string): string[] {
  const dir = path.join(MS_DIR, sub);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter((f) => f.endsWith(".json")).sort();
}

let _msMembers: Member[] | null = null;
export function getMsMembers(): Member[] {
  if (_msMembers) return _msMembers;
  _msMembers = readMsDir("members").map((f) => readMsJson<Member>(`members/${f}`));
  _msMembers.sort((a, b) => a.name.localeCompare(b.name));
  return _msMembers;
}
export function getMsMember(id: string): Member | undefined {
  return getMsMembers().find((m) => m.id === id);
}

let _msVotes: VoteFile[] | null = null;
export function getAllMsVotes(): VoteFile[] {
  if (_msVotes) return _msVotes;
  _msVotes = readMsDir("votes").map((f) => readMsJson<VoteFile>(`votes/${f}`));
  return _msVotes;
}

let _msBills: Map<string, Bill> | null = null;
function msBillMap(): Map<string, Bill> {
  if (_msBills) return _msBills;
  _msBills = new Map();
  for (const f of readMsDir("bills")) {
    const b = readMsJson<Bill>(`bills/${f}`);
    _msBills.set(b.id, b);
  }
  return _msBills;
}
export function getMsBills(): Bill[] {
  return [...msBillMap().values()].sort((a, b) => a.id.localeCompare(b.id));
}
export function getMsBill(id: string): Bill | undefined {
  return msBillMap().get(id);
}

/** Every roll a MS member has a recorded position on (incl. Not voting), newest first. */
export function getMsMemberVotes(memberId: string): MemberVoteRow[] {
  const rows: MemberVoteRow[] = [];
  for (const v of getAllMsVotes()) {
    const mv = v.member_votes.find((x) => x.member_id === memberId);
    if (mv) rows.push({ rollcall: v.rollcall, position: mv.position });
  }
  rows.sort((a, b) => byRecency(a.rollcall, b.rollcall));
  return rows;
}

/** MS roll calls that reference a given bill, newest first. */
export function getMsVotesForBill(billId: string): RollCall[] {
  return getAllMsVotes()
    .map((v) => v.rollcall)
    .filter((rc) => rc.bill_id === billId)
    .sort(byRecency);
}

export interface MsSessionRow {
  session_id: number; session_name: string; year_start: number; year_end: number;
}
export interface MsManifest {
  jurisdiction: string; generated_at: string; session_id: number; session_name: string;
  dataset_hash: string; year_start: number; year_end: number; counts: Record<string, unknown>;
  // Every session in the committed partition, newest first (D87). `counts` spans all of
  // them, so anything labelling the counts must use this, not `session_name` alone.
  // Absent on manifests written before D87 — callers fall back to the single session.
  sessions?: MsSessionRow[];
}

/** Human label for the span `counts` actually covers: one session's name, or a year
 *  range once the partition holds more than one (D87). */
export function msCoverageLabel(m: MsManifest): string {
  const rows = m.sessions ?? [];
  if (rows.length <= 1) return m.session_name;
  const first = Math.min(...rows.map((r) => r.year_start));
  const last = Math.max(...rows.map((r) => r.year_end));
  return `${first}–${last} regular sessions`;
}
let _msManifest: MsManifest | null = null;
export function getMsManifest(): MsManifest {
  if (_msManifest) return _msManifest;
  _msManifest = readMsJson<MsManifest>("manifest.json");
  return _msManifest;
}

// MS Tier-2 metrics (data/state/ms/metrics.json, INC-13) — the same shape as the
// federal metrics minus the list-type ones. Absent on a bare checkout → {}.
export interface MsMetrics {
  schema_version: number;
  methodology: Record<string, MetricMethodology>;
  members: Record<string, Record<string, unknown>>;
}
let _msMetrics: MsMetrics | null = null;
export function getMsMetrics(): MsMetrics {
  if (_msMetrics) return _msMetrics;
  try {
    _msMetrics = readMsJson<MsMetrics>("metrics.json");
  } catch {
    _msMetrics = { schema_version: 0, methodology: {}, members: {} };
  }
  return _msMetrics;
}

export interface Correction { commit: string; date: string; subject: string; }
export function getCorrections(): Correction[] {
  // Generated from git history by `uv run corrections` (INC-9). Absent on a bare
  // checkout that never ran it → treat as no corrections yet.
  try {
    return readJson<Correction[]>("corrections.json");
  } catch {
    return [];
  }
}

// --- Derived views --------------------------------------------------------

/** Newest-first sort key for roll calls: date desc, then roll number desc. */
function byRecency(a: RollCall, b: RollCall): number {
  if (a.date !== b.date) return a.date < b.date ? 1 : -1;
  return b.number - a.number;
}

export interface MemberVoteRow { rollcall: RollCall; position: Position; }

// V2-1: one-pass member→votes index, memoized. Before this, getMemberVotes
// rescanned every vote file (with a linear .find over its member_votes) once per
// member — at full federal scale that is ~637 members × ~3,500 rolls × ~535
// positions/roll, which dominated the site build. Building the index once (a
// single pass over all votes, pushing each position into its member's list)
// turns per-member lookup into an O(1) map read. Output is identical: each
// member's list is sorted newest-first, same as the old per-call sort.
let _votesByMember: Map<string, MemberVoteRow[]> | null = null;
function votesByMember(): Map<string, MemberVoteRow[]> {
  if (_votesByMember) return _votesByMember;
  const index = new Map<string, MemberVoteRow[]>();
  for (const v of getAllVotes()) {
    for (const mv of v.member_votes) {
      let rows = index.get(mv.member_id);
      if (!rows) { rows = []; index.set(mv.member_id, rows); }
      rows.push({ rollcall: v.rollcall, position: mv.position });
    }
  }
  for (const rows of index.values()) rows.sort((a, b) => byRecency(a.rollcall, b.rollcall));
  _votesByMember = index;
  return index;
}

/** Every roll a member has a recorded position on, newest first. */
export function getMemberVotes(memberId: string): MemberVoteRow[] {
  return votesByMember().get(memberId) ?? [];
}

/** Roll calls that reference a given bill, newest first. */
export function getVotesForBill(billId: string): RollCall[] {
  return getAllVotes()
    .map((v) => v.rollcall)
    .filter((rc) => rc.bill_id === billId)
    .sort(byRecency);
}

/** Split rows into fixed-size pages (newest first already applied). */
export function paginate<T>(items: T[], size: number): T[][] {
  const pages: T[][] = [];
  for (let i = 0; i < items.length; i += size) pages.push(items.slice(i, i + size));
  return pages.length ? pages : [[]];
}

// --- Member timeline: statements + votes interleaved (INC-11) --------------

export interface PairedVote { rollcall: RollCall; position: Position; }
export type TimelineItem =
  | { kind: "vote"; day: string; rollcall: RollCall; position: Position }
  | { kind: "statement"; day: string; statement: Statement; pairedVotes: PairedVote[] };

/**
 * A member's statements and recorded votes on one newest-first timeline. Pairing is
 * READ from the statement's `paired_bill_ids` (resolved once in Python, D9/D41) — this
 * never re-resolves; it only joins those bill ids to the member's own votes so a paired
 * statement and vote render adjacent. With no curated statements the timeline is exactly
 * the vote list, so the zero-statement render is the vote page unchanged.
 */
export function getMemberTimeline(memberId: string): TimelineItem[] {
  const byMemberVote = getMemberVotes(memberId);
  const items: TimelineItem[] = byMemberVote.map((r) => ({
    kind: "vote" as const, day: r.rollcall.date.slice(0, 10),
    rollcall: r.rollcall, position: r.position,
  }));
  for (const s of getMemberStatements(memberId)) {
    const paired = new Set(s.paired_bill_ids);
    const pairedVotes = paired.size
      ? byMemberVote.filter((r) => r.rollcall.bill_id && paired.has(r.rollcall.bill_id))
      : [];
    items.push({ kind: "statement", day: s.date.slice(0, 10), statement: s, pairedVotes });
  }
  // Newest first by calendar day. Within a day: statements first, then votes by
  // recency; fully deterministic tie-break so the build is byte-stable.
  const rank = (it: TimelineItem) => (it.kind === "statement" ? 0 : 1);
  items.sort((a, b) => {
    if (a.day !== b.day) return a.day < b.day ? 1 : -1;
    if (rank(a) !== rank(b)) return rank(a) - rank(b);
    if (a.kind === "vote" && b.kind === "vote") return byRecency(a.rollcall, b.rollcall);
    if (a.kind === "statement" && b.kind === "statement")
      return a.statement.id < b.statement.id ? -1 : 1;
    return 0;
  });
  return items;
}

// --- P2: member legislation (data/legislation/{bioguide}.json) ------------
// The sponsored / cosponsored lists the congress.gov member endpoints publish, as
// exported by ingest. `became_law` + `enacted_action` are the government's own
// enactment record for that bill number; nothing here is computed.

export interface LegislationEntry {
  bill_id: string; congress: number; title: string;
  introduced_date: string; became_law: boolean;
  enacted_action: string | null; source_url: string;
}
export interface MemberLegislation {
  member_id: string; source_url: string;
  lifetime_counts: Record<string, number>;
  sponsored: LegislationEntry[]; cosponsored: LegislationEntry[];
}

/** One member's sponsored/cosponsored lists, or undefined when the file is absent
 *  (a member the legislation pull has not reached — distinct from sponsoring none). */
export function getMemberLegislation(memberId: string): MemberLegislation | undefined {
  const p = path.join(DATA_DIR, "legislation", `${memberId}.json`);
  if (!fs.existsSync(p)) return undefined;
  return JSON.parse(fs.readFileSync(p, "utf-8")) as MemberLegislation;
}

/** Newest-introduced first, with a deterministic bill-id tie-break. */
export function byIntroducedDesc(a: LegislationEntry, b: LegislationEntry): number {
  if (a.introduced_date !== b.introduced_date) return a.introduced_date < b.introduced_date ? 1 : -1;
  return a.bill_id.localeCompare(b.bill_id);
}

// --- P2: find your representatives, by state -----------------------------

export interface StateDelegation { state: string; senate: Member[]; house: Member[]; }

/** The date the published dataset describes: the export timestamp in the manifest.
 *  This is the site's "now" — a real wall clock in the build would make the output
 *  non-deterministic (§6.3), and the dataset cannot describe a seat later than the
 *  day it was exported anyway. */
export function asOfDate(): string {
  return getManifest().generated_at.slice(0, 10);
}

/** Whether a member actually holds a seat as of the dataset's own date.
 *
 *  NOT the `serving` flag on the record. That flag means "their latest term
 *  overlaps the latest covered Congress", which is the right definition for vote
 *  coverage (a member who resigned in March still had rolls to be present for) and
 *  the WRONG one for "find your representatives": it keeps 16 members whose terms
 *  have since ended, which showed up as Florida, Ohio, Oklahoma and South Carolina
 *  each listing three senators. A seat is held only while a term covers the date. */
export function holdsSeatAsOf(member: Member, asOf: string): boolean {
  return member.terms.some((t) => t.start <= asOf && asOf <= t.end);
}

/** Members currently holding a federal seat, grouped by state: senators by name,
 *  then House members by district (at-large / unknown district last). Ordered by
 *  the state's NAME, which is the order a reader scans for their own state —
 *  postal-code order puts Arizona before Alaska. */
let _byState: StateDelegation[] | null = null;
export function getDelegationsByState(): StateDelegation[] {
  if (_byState) return _byState;
  const asOf = asOfDate();
  const index = new Map<string, StateDelegation>();
  for (const m of getMembers()) {
    if (m.jurisdiction !== "us" || !holdsSeatAsOf(m, asOf)) continue;
    let d = index.get(m.state);
    if (!d) { d = { state: m.state, senate: [], house: [] }; index.set(m.state, d); }
    (m.chamber === "senate" ? d.senate : d.house).push(m);
  }
  for (const d of index.values()) {
    d.senate.sort((a, b) => a.name.localeCompare(b.name));
    d.house.sort((a, b) => {
      const ad = a.district ?? Number.MAX_SAFE_INTEGER;
      const bd = b.district ?? Number.MAX_SAFE_INTEGER;
      return ad !== bd ? ad - bd : a.name.localeCompare(b.name);
    });
  }
  _byState = [...index.values()].sort((a, b) =>
    (STATE_NAME[a.state] ?? a.state).localeCompare(STATE_NAME[b.state] ?? b.state));
  return _byState;
}

/** The calendar year of a member's earliest term start, or null. Rendered as a
 *  year, not a count of years: a count needs a wall-clock "now", and a wall clock
 *  in a built artifact breaks determinism (§6.3). */
export function inOfficeSince(member: Member): number | null {
  const starts = member.terms.map((t) => t.start).filter(Boolean).sort();
  return starts.length ? Number(starts[0].slice(0, 4)) : null;
}

/** True when some later term starts more than ~400 days after the previous one
 *  ended, i.e. service has not been continuous since `inOfficeSince`. The header
 *  then says "first took office in" instead of "in office since", so the year is
 *  never read as unbroken service. */
export function hasServiceGap(member: Member): boolean {
  const terms = [...member.terms].sort((a, b) => a.start.localeCompare(b.start));
  for (let i = 1; i < terms.length; i++) {
    const prevEnd = Date.parse(terms[i - 1].end);
    const start = Date.parse(terms[i].start);
    if (Number.isFinite(prevEnd) && Number.isFinite(start)
        && start - prevEnd > 400 * 24 * 3600 * 1000) return true;
  }
  return false;
}

// --- P2: party-majority placement of a vote (ratified, §2) ---------------
// "A vote is placed by which party's majority the member sided with." Computed
// ONLY from the roll call's own party_totals and the member's own position — no
// outside score, no model, and no derived single "lean" number.
//
// Per roll call, mechanically:
//   * a party's majority side is "yea" when its yea count exceeds its nay count,
//     "nay" when its nay exceeds its yea, and nothing at all on a tie;
//   * the member sided with a party when their position equals that side;
//   * a position of present / not_voting places nothing — there is no side taken;
//   * a roll with no party_totals (a Speaker election has no yea/nay) places nothing.
// Only D and R totals are read: "the other party's majority" is defined only for
// the two caucusing majorities. An Independent member is placed by the same rule.

export type PartySide = "both" | "d_only" | "r_only" | "neither";
export const PARTY_SIDE_LABEL: Record<PartySide, string> = {
  both: "With both party majorities",
  d_only: "With the Democratic majority only",
  r_only: "With the Republican majority only",
  neither: "Against both party majorities",
};
export const PARTY_SIDE_ORDER: PartySide[] = ["d_only", "both", "r_only", "neither"];

/** The majority side of one party on one roll call, or null on a tie / no totals. */
export function partyMajoritySide(rc: RollCall, party: "D" | "R"): "yea" | "nay" | null {
  const t = rc.party_totals?.[party];
  if (!t) return null;
  const yea = Number(t.yea ?? 0);
  const nay = Number(t.nay ?? 0);
  if (yea === nay) return null;
  return yea > nay ? "yea" : "nay";
}

/** Where a member's vote falls under the ratified rule, or null when the roll
 *  places nothing (no party_totals, both parties tied, or present / not voting). */
export function placeVote(rc: RollCall, position: Position): PartySide | null {
  if (position !== "yea" && position !== "nay") return null;
  const d = partyMajoritySide(rc, "D");
  const r = partyMajoritySide(rc, "R");
  if (d === null && r === null) return null;
  const withD = d !== null && position === d;
  const withR = r !== null && position === r;
  if (withD && withR) return "both";
  if (withD) return "d_only";
  if (withR) return "r_only";
  return "neither";
}

export interface PartySideTally {
  counts: Record<PartySide, number>;
  placed: number;
  unplaced: number;
}
/** Bin counts for one member's votes, plus how many votes the rule places at all. */
export function tallyPartySides(rows: MemberVoteRow[]): PartySideTally {
  const counts: Record<PartySide, number> = { both: 0, d_only: 0, r_only: 0, neither: 0 };
  let placed = 0, unplaced = 0;
  for (const r of rows) {
    const side = placeVote(r.rollcall, r.position);
    if (side === null) { unplaced++; continue; }
    counts[side]++; placed++;
  }
  return { counts, placed, unplaced };
}

// --- P2: chamber activity for the homepage "In Congress" band -----------
// Buckets are the government's OWN summary wording, not a reading of it:
// congress.gov writes the paired labels "Passed/agreed to in {chamber}: ..." and
// "Failed of passage/not agreed to in {chamber}: ..." on the action that resolves a
// measure on the floor, and stamps enactment with action type "BecameLaw". Calendar
// placements are shown as exactly that — placed on a calendar — because nothing in
// the action record states a scheduled vote date (that source is Q-D, Phase 5).
//
// ORDER (owner-ratified 2026-10-07, "consequence then contested"): the band leads
// with what the record itself shows to be most consequential, not with four
// equal-weight boxes. Every key below comes from the official record, and nothing
// is weighted by topic:
//   1 failed on the floor on a recorded roll call — members are on the record
//     against it, and the measure is dead
//   2 passed on a recorded roll call, closest tally first — members are on the
//     record, and the closer the tally the more divided the chamber was
//   3 became law — the final outcome, but almost always reached without anyone
//     going on the record (voice vote or unanimous consent)
//   4 failed on the floor with no roll call in the record
//   5 passed with no roll call in the record — nobody divided
//   6 placed on a calendar — eligible to be called up, no date in the record
// Within a tier, newest first; the event id breaks ties so the build is byte-stable.

export type ActivityBucket = "became_law" | "passed" | "failed" | "calendared";

/** One place for each tier's slug, heading and the rule that fills it, so the
 *  homepage band and the full list can never describe a tier differently. */
export interface ActivityBucketMeta {
  key: ActivityBucket; slug: string; heading: string; note: string;
}
export const ACTIVITY_BUCKETS: ActivityBucketMeta[] = [
  { key: "became_law", slug: "became-law", heading: "Became law",
    note: "Signed by the President, or enacted without signature." },
  { key: "failed", slug: "failed", heading: "Failed on the floor",
    note: "The chamber's own “Failed of passage/not agreed to” action line." },
  { key: "passed", slug: "passed", heading: "Passed a chamber",
    note: "The chamber's own “Passed/agreed to” action line." },
  { key: "calendared", slug: "calendared", heading: "Placed on a calendar",
    note: "Eligible to be called up. The action record gives no vote date." },
];

/** The margin of the roll call that resolved a measure, when one exists. */
export interface ActivityMargin {
  rollcallId: string; yea: number; nay: number;
  /** Winning side's share of yea+nay, to 0.1 — lower means more divided. */
  sharePct: number;
}

export interface ActivityRow {
  event: BillEvent;
  title: string | null;
  bucket: ActivityBucket;
  /** 1–6, the ratified order above. */
  tier: number;
  /** Short factual label, e.g. "Passed — recorded vote 212–206". */
  tierLabel: string;
  margin: ActivityMargin | null;
}
export interface ChamberActivity {
  /** Inclusive window, taken from the record itself — never from a wall clock. */
  from: string; to: string; days: number;
  /** Every row in the window, in the ratified order. */
  ranked: ActivityRow[];
  /** The leading rows, for the homepage band. */
  lead: ActivityRow[];
  totals: Record<ActivityBucket, number>;
  total: number;
}

const ACTIVITY_DAYS = 14;

function activityBucket(e: BillEvent): ActivityBucket | null {
  if (!e.text) return null; // a null action text has no wording to bucket on
  if (e.type === "BecameLaw") return "became_law";
  if (e.text.startsWith("Passed/agreed to in ")) return "passed";
  if (e.text.startsWith("Failed of passage/not agreed to in ")) return "failed";
  if (e.type === "Calendars") return "calendared";
  return null;
}

/** The roll call that resolved this action, if the dataset holds one.
 *
 *  `rollcall_id` is set on an event only when the action's own record named a roll
 *  this dataset holds, which is rare in the projection (2 of 111 in the window this
 *  shipped on). The fallback join is deliberately narrow and mechanical: the SAME
 *  bill, on the SAME calendar day. A looser join — any roll on the bill, ever —
 *  would attach a procedural vote from weeks earlier to a passage line and publish
 *  its margin as the passage margin, which would be false. */
function resolvingRoll(e: BillEvent): RollCall | undefined {
  if (e.rollcall_id) {
    const direct = getAllVotes().find((v) => v.rollcall.id === e.rollcall_id);
    if (direct && resolvesMeasure(direct.rollcall.question)) return direct.rollcall;
  }
  // Same bill, same calendar day, AND a question that decides the measure. The
  // last condition is not optional: s4668-119 passed on 2026-09-30 and the only
  // roll that day on that bill was "On the Amendment S.Amdt. 6828", 96-1.
  // Without the check, that amendment's tally publishes as the bill's passage
  // margin -- a false number attached to a true event (Rule 0).
  return getVotesForBill(e.bill_id).find(
    (rc) => rc.date.slice(0, 10) === e.date && resolvesMeasure(rc.question),
  );
}

function marginOf(rc: RollCall | undefined): ActivityMargin | null {
  if (!rc) return null;
  const yea = Number(rc.totals?.yea ?? 0);
  const nay = Number(rc.totals?.nay ?? 0);
  const cast = yea + nay;
  if (cast === 0) return null;
  const sharePct = Math.round((Math.max(yea, nay) / cast) * 1000) / 10;
  return { rollcallId: rc.id, yea, nay, sharePct };
}

/** The most recent `ACTIVITY_DAYS` days of floor-resolving bill actions in the
 *  record, in the ratified order. One row per bill per tier: congress.gov writes a
 *  passage twice (its summary line and the vote line) and both carry the bill id. */
export function recentChamberActivity(limit = 8): ChamberActivity | null {
  const months = getEventMonths();
  if (!months.length) return null;
  // Two months, so a window straddling a month boundary is still whole.
  const events = months.slice(-2).flatMap((m) => getEventsFile(m).events);
  if (!events.length) return null;
  const to = events.reduce((acc, e) => (e.date > acc ? e.date : acc), events[0].date);
  const from = new Date(
    Date.parse(`${to}T00:00:00Z`) - (ACTIVITY_DAYS - 1) * 24 * 3600 * 1000,
  ).toISOString().slice(0, 10);

  const totals: Record<ActivityBucket, number> = {
    became_law: 0, passed: 0, failed: 0, calendared: 0,
  };
  const inWindow = events
    .filter((e) => e.date >= from && e.date <= to)
    .sort((a, b) => (a.date !== b.date ? (a.date < b.date ? 1 : -1) : a.id.localeCompare(b.id)));

  const seen = new Set<string>();
  const rows: ActivityRow[] = [];
  for (const e of inWindow) {
    const bucket = activityBucket(e);
    if (bucket === null) continue;
    const key = `${bucket}::${e.bill_id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    totals[bucket]++;

    const margin = bucket === "passed" || bucket === "failed" ? marginOf(resolvingRoll(e)) : null;
    let tier: number;
    let tierLabel: string;
    if (bucket === "failed" && margin) {
      tier = 1;
      tierLabel = `Failed — recorded vote ${margin.yea}–${margin.nay}`;
    } else if (bucket === "passed" && margin) {
      tier = 2;
      tierLabel = `Passed — recorded vote ${margin.yea}–${margin.nay}`;
    } else if (bucket === "became_law") {
      tier = 3;
      tierLabel = "Became law";
    } else if (bucket === "failed") {
      tier = 4;
      tierLabel = "Failed on the floor";
    } else if (bucket === "passed") {
      tier = 5;
      // "no roll call IN THE RECORD", not "no recorded vote": the join above is
      // deliberately narrow (same bill, same calendar day), so the honest claim is
      // about what this dataset holds, not about what the chamber did. In the window
      // this shipped on, 95 of the 97 resolved measures had no roll call on that bill
      // at all and none had one a day either side, but the label must stay true in a
      // window where the action and its roll land on different dates.
      tierLabel = "Passed — no roll call in the record";
    } else {
      tier = 6;
      tierLabel = "Placed on a calendar";
    }

    rows.push({
      event: e, title: getBill(e.bill_id)?.title_official ?? null,
      bucket, tier, tierLabel, margin,
    });
  }

  rows.sort((a, b) => {
    if (a.tier !== b.tier) return a.tier - b.tier;
    // Tier 2 only: the closer the tally, the more divided the chamber, so that row
    // leads. `sharePct` is the winning side's share, so ascending is closest first.
    if (a.tier === 2 && a.margin && b.margin && a.margin.sharePct !== b.margin.sharePct) {
      return a.margin.sharePct - b.margin.sharePct;
    }
    if (a.event.date !== b.event.date) return a.event.date < b.event.date ? 1 : -1;
    return a.event.id.localeCompare(b.event.id);
  });

  return {
    from, to, days: ACTIVITY_DAYS,
    ranked: rows, lead: rows.slice(0, limit), totals, total: rows.length,
  };
}

// --- P2: bill actions on a member's own bills, for their timeline ---------

/** Action rows on the bills a member sponsored, newest first. `actions` absent or
 *  null on a bill is the D27 "not collected" sentinel, not "no actions", so those
 *  bills simply contribute nothing here rather than an empty timeline. */
export interface MemberBillAction { bill: Bill; action: BillAction; }
let _actionsBySponsor: Map<string, MemberBillAction[]> | null = null;
export function getSponsoredBillActions(memberId: string): MemberBillAction[] {
  if (!_actionsBySponsor) {
    const index = new Map<string, MemberBillAction[]>();
    for (const b of getBills()) {
      if (!b.sponsor_id || !b.actions || !b.actions.length) continue;
      let list = index.get(b.sponsor_id);
      if (!list) { list = []; index.set(b.sponsor_id, list); }
      for (const a of b.actions) {
        // 30 actions in the dataset carry a null `text` (the government published the
        // action code and date with no sentence). A row with no text would render as a
        // dated blank that says nothing, so those are skipped rather than shown.
        if (!a.text || !a.date) continue;
        list.push({ bill: b, action: a });
      }
    }
    _actionsBySponsor = index;
  }
  return _actionsBySponsor.get(memberId) ?? [];
}

// --- P2: the member activity timeline (§4.2 scroll 3) --------------------
// Votes (absences included — an absence is a vote row with a not_voting position,
// which is where the stated reason or "No explanation on record" is rendered),
// statements, and official actions on the bills the member sponsored, on one
// newest-first list, each row carrying the policy area it can be filtered by.

export type ActivityKind = "vote" | "statement" | "action";
export const ACTIVITY_KIND_LABEL: Record<ActivityKind, string> = {
  vote: "Votes", statement: "Statements", action: "Actions on their bills",
};

export type MemberActivityItem =
  | { kind: "vote"; day: string; policyArea: string | null; billTitle: string | null;
      rollcall: RollCall; position: Position }
  | { kind: "statement"; day: string; policyArea: string | null; statement: Statement;
      pairedVotes: PairedVote[] }
  | { kind: "action"; day: string; policyArea: string | null; bill: Bill; action: BillAction };

/** The member's full activity, newest first. Ordering within a calendar day is
 *  fixed (statements, then votes by recency, then bill actions by bill id) so the
 *  build is byte-stable. */
export function getMemberActivity(memberId: string): MemberActivityItem[] {
  const items: MemberActivityItem[] = [];
  for (const it of getMemberTimeline(memberId)) {
    if (it.kind === "vote") {
      const bill = it.rollcall.bill_id ? getBill(it.rollcall.bill_id) : undefined;
      items.push({
        ...it,
        policyArea: bill?.policy_area ?? null,
        billTitle: bill?.title_official ?? null,
      });
    } else {
      const paired = it.statement.paired_bill_ids
        .map((id) => getBill(id)?.policy_area)
        .find((p) => p);
      items.push({ ...it, policyArea: it.statement.topic ?? paired ?? null });
    }
  }
  for (const { bill, action } of getSponsoredBillActions(memberId)) {
    items.push({
      kind: "action", day: action.date.slice(0, 10),
      policyArea: bill.policy_area ?? null, bill, action,
    });
  }
  const rank: Record<ActivityKind, number> = { statement: 0, vote: 1, action: 2 };
  items.sort((a, b) => {
    if (a.day !== b.day) return a.day < b.day ? 1 : -1;
    if (rank[a.kind] !== rank[b.kind]) return rank[a.kind] - rank[b.kind];
    if (a.kind === "vote" && b.kind === "vote") return byRecency(a.rollcall, b.rollcall);
    if (a.kind === "statement" && b.kind === "statement")
      return a.statement.id < b.statement.id ? -1 : 1;
    if (a.kind === "action" && b.kind === "action") {
      if (a.bill.id !== b.bill.id) return a.bill.id.localeCompare(b.bill.id);
      return a.action.text.localeCompare(b.action.text);
    }
    return 0;
  });
  return items;
}

/** Policy areas present on one page of activity rows, alphabetical. Drives the
 *  topic filter's options, so the filter never offers a value that filters to
 *  nothing on the page the reader is looking at. */
export function policyAreasOf(items: MemberActivityItem[]): string[] {
  const set = new Set<string>();
  for (const it of items) if (it.policyArea) set.add(it.policyArea);
  return [...set].sort((a, b) => a.localeCompare(b));
}

// --- P2: member photos (task 6) ------------------------------------------
// Photos live in site/public/photos/{bioguide}.jpg, fetched by
// scripts/fetch_member_photos.py from the unitedstates/images project (source and
// licence recorded in docs/data-contract.md). The roster covers members of two
// Congresses and that project does not carry every one of them, so a missing file
// is an ordinary state: the header falls back to initials. Checked at build time,
// once, so a page never links an image that is not there.
let _photoIds: Set<string> | null = null;
function photoIds(): Set<string> {
  if (_photoIds) return _photoIds;
  const dir = fileURLToPath(new URL("../../public/photos/", import.meta.url));
  _photoIds = new Set(
    fs.existsSync(dir)
      ? fs.readdirSync(dir).filter((f) => f.endsWith(".jpg")).map((f) => f.slice(0, -4))
      : [],
  );
  return _photoIds;
}
export function memberPhotoUrl(memberId: string): string | null {
  return photoIds().has(memberId) ? `/photos/${memberId}.jpg` : null;
}

// --- P2: committee assignments (task 7) ----------------------------------
// data/committees/membership.json, written by `uv run ingest committees` from the
// unitedstates/congress-legislators project. Absent until that ingest has run, in
// which case the member page says the section is coming rather than implying the
// member sits on nothing.
export interface CommitteeSeat {
  committee_id: string; name: string; parent_name: string | null;
  rank: number | null; title: string | null; source_url: string;
}
// Present only while senate.gov refuses our vote-menu requests (ingest/senate_votes.py,
// owner ruling 2026-10-29); the first successful Senate ingest deletes it. Absent -> null
// -> no notice line anywhere.
export interface SenateOutage {
  outage_start: string; last_roll_id: string; last_roll_date: string; source_url: string;
}
let _senateOutage: SenateOutage | null | undefined;
export function getSenateOutage(): SenateOutage | null {
  if (_senateOutage !== undefined) return _senateOutage;
  const p = path.join(DATA_DIR, "quality", "senate-outage.json");
  _senateOutage = fs.existsSync(p)
    ? (JSON.parse(fs.readFileSync(p, "utf-8")) as SenateOutage)
    : null;
  return _senateOutage;
}

export interface CommitteeMembership {
  source_url: string; seat_count: number; members: Record<string, CommitteeSeat[]>;
}
let _committees: CommitteeMembership | null | undefined;
export function getCommitteeMembership(): CommitteeMembership | null {
  if (_committees !== undefined) return _committees;
  const p = path.join(DATA_DIR, "committees", "membership.json");
  _committees = fs.existsSync(p)
    ? (JSON.parse(fs.readFileSync(p, "utf-8")) as CommitteeMembership)
    : null;
  return _committees;
}
export function getMemberCommittees(memberId: string): CommitteeSeat[] | null {
  const m = getCommitteeMembership();
  if (!m) return null;
  return m.members[memberId] ?? [];
}
