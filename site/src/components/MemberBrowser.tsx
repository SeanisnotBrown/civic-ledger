/** @jsxImportSource preact */
import { useEffect, useMemo, useState } from "preact/hooks";

// V2-5: the federal-members browser island. The page (/federal) passes the FULL
// roster as props and mounts this with `client:visible`, so Astro renders the
// complete, sorted list to static HTML at build time (crawlable by the links
// check, byte-deterministic, and fully usable with JavaScript off). Hydration
// only layers filtering/sorting on top — it never fetches and never removes a
// member from the no-JS render.
//
// Discipline carried from the member pages: the attendance grade is shown as the
// exact ratified band label inside a `data-grade-label` span (check-grade-labels
// verifies every such string against data/config/thresholds.yaml). Non-voting
// delegates (D66) and thin records are shown as "Not graded", never scored.

export interface MemberRow {
  id: string;
  name: string;
  party: "D" | "R" | "I";
  state: string;
  district: number | null;
  chamber: "house" | "senate";
  attendancePct: number | null;
  gradeLetter: string | null; // "A".."F" — data-bound from the grades export, or null
  gradeLabel: string | null; // full ratified band label, e.g. "B — Good attendance"
  gradeExceptionLabel: string | null; // set only for a gradeable-but-set-aside record
}

const PARTY_LABEL: Record<string, string> = {
  D: "Democrat",
  R: "Republican",
  I: "Independent",
};
const GRADE_ORDER: Record<string, number> = { A: 0, B: 1, C: 2, D: 3, F: 4 };

type Chamber = "all" | "house" | "senate";
type Party = "all" | "D" | "R" | "I";
type Grade = "all" | "A" | "B" | "C" | "D" | "F";
type SortKey = "name" | "attendance" | "grade";

export default function MemberBrowser({ members }: { members: MemberRow[] }) {
  const [chamber, setChamber] = useState<Chamber>("all");
  const [party, setParty] = useState<Party>("all");
  const [grade, setGrade] = useState<Grade>("all");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("name");

  // Deep-link support: dashboard tiles link here with query params (?grade=F,
  // ?chamber=senate, …) so a headline number clicks straight through to the list
  // that reproduces it (V2-5's click-through rule). Runs after hydration only.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const ch = p.get("chamber");
    if (ch === "house" || ch === "senate") setChamber(ch);
    const pa = p.get("party");
    if (pa === "D" || pa === "R" || pa === "I") setParty(pa);
    const gr = p.get("grade");
    if (gr && gr in GRADE_ORDER) {
      setGrade(gr as Grade);
      setSort("grade");
    }
    const so = p.get("sort");
    if (so === "name" || so === "attendance" || so === "grade") setSort(so);
    const query = p.get("q");
    if (query) setQ(query);
  }, []);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const filtered = members.filter((m) => {
      if (chamber !== "all" && m.chamber !== chamber) return false;
      if (party !== "all" && m.party !== party) return false;
      if (grade !== "all" && m.gradeLetter !== grade) return false;
      if (needle && !`${m.name} ${m.state}`.toLowerCase().includes(needle)) return false;
      return true;
    });
    return filtered.sort((a, b) => {
      if (sort === "attendance") {
        const av = a.attendancePct;
        const bv = b.attendancePct;
        if (av == null && bv == null) return a.name.localeCompare(b.name);
        if (av == null) return 1; // no record sorts last
        if (bv == null) return -1;
        if (bv !== av) return bv - av; // high → low
        return a.name.localeCompare(b.name);
      }
      if (sort === "grade") {
        const ao = a.gradeLetter ? GRADE_ORDER[a.gradeLetter] : 99;
        const bo = b.gradeLetter ? GRADE_ORDER[b.gradeLetter] : 99;
        if (ao !== bo) return ao - bo; // A → F, ungraded last
        return a.name.localeCompare(b.name);
      }
      return a.name.localeCompare(b.name);
    });
  }, [members, chamber, party, grade, q, sort]);

  const labelCls = "block text-xs font-medium text-neutral-500";
  const inputCls =
    "mt-1 rounded-md border border-neutral-300 bg-white px-2 py-1 text-sm text-neutral-900";

  return (
    <div>
      <div class="flex flex-wrap items-end gap-3">
        <div class="grow">
          <label for="mb-q" class={labelCls}>Search name or state</label>
          <input
            id="mb-q"
            type="search"
            value={q}
            placeholder="e.g. Smith or Ohio"
            onInput={(e) => setQ((e.target as HTMLInputElement).value)}
            class={`${inputCls} w-full`}
          />
        </div>
        <div>
          <label for="mb-chamber" class={labelCls}>Chamber</label>
          <select id="mb-chamber" value={chamber} onChange={(e) => setChamber((e.target as HTMLSelectElement).value as Chamber)} class={inputCls}>
            <option value="all">All</option>
            <option value="house">House</option>
            <option value="senate">Senate</option>
          </select>
        </div>
        <div>
          <label for="mb-party" class={labelCls}>Party</label>
          <select id="mb-party" value={party} onChange={(e) => setParty((e.target as HTMLSelectElement).value as Party)} class={inputCls}>
            <option value="all">All</option>
            <option value="D">Democrat</option>
            <option value="R">Republican</option>
            <option value="I">Independent</option>
          </select>
        </div>
        <div>
          <label for="mb-grade" class={labelCls}>Attendance grade</label>
          <select id="mb-grade" value={grade} onChange={(e) => setGrade((e.target as HTMLSelectElement).value as Grade)} class={inputCls}>
            <option value="all">All</option>
            <option value="A">A</option>
            <option value="B">B</option>
            <option value="C">C</option>
            <option value="D">D</option>
            <option value="F">F</option>
          </select>
        </div>
        <div>
          <label for="mb-sort" class={labelCls}>Sort by</label>
          <select id="mb-sort" value={sort} onChange={(e) => setSort((e.target as HTMLSelectElement).value as SortKey)} class={inputCls}>
            <option value="name">Name (A–Z)</option>
            <option value="attendance">Attendance (high to low)</option>
            <option value="grade">Attendance grade (A to F)</option>
          </select>
        </div>
      </div>

      <p aria-live="polite" class="mt-4 text-xs text-neutral-500">
        {rows.length} {rows.length === 1 ? "member" : "members"}
      </p>

      <ul class="mt-1 divide-y divide-neutral-100">
        {rows.map((m) => (
          <li key={m.id} class="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-3">
            <a href={`/m/${m.id}/1`} class="font-medium text-neutral-900 underline hover:text-neutral-700">
              {m.name}
            </a>
            <span class="text-sm text-neutral-500">
              {PARTY_LABEL[m.party]} · {m.state}
              {m.district != null ? `-${m.district}` : ""}
            </span>
            <span class="text-sm text-neutral-500">
              Attendance {m.attendancePct == null ? "—" : `${m.attendancePct}%`}
            </span>
            <span class="ml-auto text-sm">
              {m.gradeLetter ? (
                <span
                  data-grade-label=""
                  class="rounded border border-neutral-300 px-1.5 py-0.5 text-xs font-medium text-neutral-700"
                >
                  {m.gradeLabel}
                </span>
              ) : m.gradeExceptionLabel ? (
                <span data-grade-label="" class="text-xs italic text-neutral-400">
                  {m.gradeExceptionLabel}
                </span>
              ) : (
                <span class="text-xs text-neutral-400">Not graded</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
