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

export interface Term { start: string; end: string; party: Party; chamber: Chamber; }
export interface Member {
  id: string; ids: Record<string, string>; name: string; party: Party;
  state: string; district: number | null; chamber: Chamber; serving: boolean; terms: Term[];
}
export interface RollCall {
  id: string; chamber: Chamber; congress: number; session: number; number: number;
  date: string; question: string; vote_class: VoteClass; vote_class_rule: string;
  bill_id: string | null; result: string; totals: Record<string, number>; source_url: string;
}
export interface MemberVote { member_id: string; rollcall_id: string; position: Position; }
export interface VoteFile { rollcall: RollCall; member_votes: MemberVote[]; }
export interface Absence {
  member_id: string; rollcall_id: string;
  stated_reason: string | null; stated_reason_source: string | null;
  declared_position: "yea" | "nay" | null;
}
export interface CboRef { url: string; title: string; date: string; }
export interface Bill {
  id: string; congress: number; type: string; number: number; title_official: string;
  policy_area: string | null; subjects: string[] | null; sponsor_id: string | null;
  cosponsor_ids: string[] | null; latest_action: string; latest_action_date: string;
  cbo_estimates: CboRef[]; source_url: string;
}
export interface Manifest {
  generated_at: string; commit: string; congresses: number[]; covered_state: string;
  counts: Record<string, unknown>;
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
export function getVote(rollId: string): VoteFile | undefined {
  return getAllVotes().find((v) => v.rollcall.id === rollId);
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
export function getBill(id: string): Bill | undefined {
  return billMap().get(id);
}

let _absences: Map<string, Absence> | null = null;
function absenceMap(): Map<string, Absence> {
  if (_absences) return _absences;
  _absences = new Map();
  for (const f of readDir("absences")) {
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

// --- Derived views --------------------------------------------------------

/** Newest-first sort key for roll calls: date desc, then roll number desc. */
function byRecency(a: RollCall, b: RollCall): number {
  if (a.date !== b.date) return a.date < b.date ? 1 : -1;
  return b.number - a.number;
}

export interface MemberVoteRow { rollcall: RollCall; position: Position; }

/** Every roll a member has a recorded position on, newest first. */
export function getMemberVotes(memberId: string): MemberVoteRow[] {
  const rows: MemberVoteRow[] = [];
  for (const v of getAllVotes()) {
    const mv = v.member_votes.find((x) => x.member_id === memberId);
    if (mv) rows.push({ rollcall: v.rollcall, position: mv.position });
  }
  rows.sort((a, b) => byRecency(a.rollcall, b.rollcall));
  return rows;
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
