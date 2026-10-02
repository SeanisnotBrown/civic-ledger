// Build-time data access over the committed dataset (../../../data/**). Runs in
// Node during `astro build` only — the site ships as static HTML with zero
// runtime data fetching (§10.1). Types mirror ingest/models.py exactly; the
// canonical machine contract is data/schema/*.schema.json (see docs/data-contract.md).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

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
