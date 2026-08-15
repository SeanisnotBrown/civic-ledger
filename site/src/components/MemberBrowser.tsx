/** @jsxImportSource preact */
import { useEffect, useMemo, useRef, useState } from "preact/hooks";

// V2-5 Nocturne (explorer, D73/D74): a CONTROLS-ONLY island. The 637-row metric table is
// static HTML rendered by /federal (crawlable, works JS-off, cheap first paint). This
// island hydrates the search box + chip filters + column toggles and enhances the table in
// place: it filters by toggling each row's inline `display`, sorts by reordering rows, and
// hides a column by toggling `display` on every `[data-col=key]`. It reads only the rows'
// own `data-*` attributes — it never owns or re-serialises the rows (rendering rows in the
// island is what sank mobile perf at D73). Default sort stays `name` and matches the static
// order, so the first (perf-critical) pass does no reorder and adds no layout shift.
//
// Filtering uses `el.style.display` (inline) not the `hidden` attribute: table cells and
// rows carry author `display` values that beat the UA `[hidden]{display:none}` in the
// cascade, so `hidden` could leave a "filtered-out" row visible while the count disagreed.

const GRADE_ORDER: Record<string, number> = { A: 0, B: 1, C: 2, D: 3, F: 4 };
const LIST_ID = "member-list";

type Col = { key: string; short: string };
type SortKey = string; // "name" | "grade" | a column key

function num(v: string | undefined): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

export default function MemberBrowser({ total, columns }: { total: number; columns: Col[] }) {
  const [chamber, setChamber] = useState("all");
  const [party, setParty] = useState("all");
  const [grade, setGrade] = useState("all");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("name");
  const [dir, setDir] = useState<"asc" | "desc">("asc");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [count, setCount] = useState<number | null>(null);
  const first = useRef(true);

  const colKeys = useMemo(() => columns.map((c) => c.key), [columns]);

  // Deep-link support: dashboard tiles/band chips link here with query params so a headline
  // number clicks straight through to the list that reproduces it (?grade=A&sort=grade, …).
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const ch = p.get("chamber");
    if (ch === "house" || ch === "senate") setChamber(ch);
    const pa = p.get("party");
    if (pa === "D" || pa === "R" || pa === "I") setParty(pa);
    const gr = p.get("grade");
    if (gr && gr in GRADE_ORDER) { setGrade(gr); setSort("grade"); setDir("asc"); }
    const so = p.get("sort");
    if (so === "name") { setSort("name"); setDir("asc"); }
    else if (so === "grade") { setSort("grade"); setDir("asc"); }
    else if (so && colKeys.includes(so)) { setSort(so); setDir("desc"); }
    const query = p.get("q");
    if (query) setQ(query);
  }, [colKeys]);

  // The one effect that touches the DOM: filter → sort → column visibility → header state.
  useEffect(() => {
    const list = document.getElementById(LIST_ID);
    if (!list) return;
    const isFirst = first.current;
    const rows = Array.from(list.querySelectorAll<HTMLElement>("tr[data-member]"));
    const needle = q.trim().toLowerCase();
    let shown = 0;
    for (const tr of rows) {
      const ok =
        (chamber === "all" || tr.dataset.chamber === chamber) &&
        (party === "all" || tr.dataset.party === party) &&
        (grade === "all" || tr.dataset.grade === grade) &&
        (!needle || (tr.dataset.search ?? "").includes(needle));
      tr.style.display = ok ? "" : "none";
      if (ok) shown++;
    }
    setCount(shown);

    // Sort. Skip entirely on the first pass while at the default name sort (static order
    // already matches) — that keeps the perf-critical initial render reorder-free.
    if (!(isFirst && sort === "name")) {
      const cmpName = (a: HTMLElement, b: HTMLElement) =>
        (a.dataset.name ?? "").localeCompare(b.dataset.name ?? "");
      const sign = dir === "asc" ? 1 : -1;
      const sorted = rows.slice().sort((a, b) => {
        if (sort === "name") return sign * cmpName(a, b);
        if (sort === "grade") {
          const ao = a.dataset.grade ? GRADE_ORDER[a.dataset.grade] : 99;
          const bo = b.dataset.grade ? GRADE_ORDER[b.dataset.grade] : 99;
          if (ao === 99 && bo === 99) return cmpName(a, b);
          if (ao === 99) return 1; // ungraded last, both directions
          if (bo === 99) return -1;
          return ao !== bo ? sign * (ao - bo) : cmpName(a, b);
        }
        const av = num(a.dataset[sort]);
        const bv = num(b.dataset[sort]);
        if (av == null && bv == null) return cmpName(a, b);
        if (av == null) return 1; // missing values sort LAST in both directions
        if (bv == null) return -1;
        return av !== bv ? sign * (av - bv) : cmpName(a, b);
      });
      const body = rows[0]?.parentNode;
      if (body) for (const tr of sorted) body.appendChild(tr);
    }

    // Column visibility — hide/show every header, cell, and definition entry by data-col.
    for (const key of colKeys) {
      const on = !hidden.has(key);
      for (const el of list.querySelectorAll<HTMLElement>(`[data-col="${key}"]`)) {
        el.style.display = on ? "" : "none";
      }
      const def = document.querySelector<HTMLElement>(`#defs-h ~ div [data-col="${key}"]`);
      if (def) def.style.display = on ? "" : "none";
    }

    // Header active/direction markers (CSS renders the ↑/↓ arrow from these).
    for (const btn of list.querySelectorAll<HTMLElement>(".hdr-btn")) {
      const active = btn.dataset.sort === sort;
      if (active) { btn.dataset.active = ""; btn.dataset.dir = dir; }
      else { delete btn.dataset.active; delete btn.dataset.dir; }
    }

    // Reflect filter/sort state in the URL so a filtered view is linkable. Skip on the
    // very first pass so an incoming deep-link (?grade=A&sort=grade) is not clobbered
    // before its state has been applied.
    if (!isFirst) {
      const p = new URLSearchParams();
      if (chamber !== "all") p.set("chamber", chamber);
      if (party !== "all") p.set("party", party);
      if (grade !== "all") p.set("grade", grade);
      if (q.trim()) p.set("q", q.trim());
      if (sort !== "name") p.set("sort", sort);
      const qs = p.toString();
      window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
    }

    first.current = false;
  }, [chamber, party, grade, q, sort, dir, hidden, colKeys]);

  // Wire the static column-header buttons to sorting (they live in the Astro table). The
  // listener re-binds when sort/dir change so it closes over fresh state — that lets the
  // handler use plain setState calls (never a side-effect inside a functional updater,
  // which Preact may drop or replay). Clicking the active column flips direction; a new
  // column opens ascending for name/grade, descending (high→low) for the metric columns.
  useEffect(() => {
    const list = document.getElementById(LIST_ID);
    if (!list) return;
    const btns = Array.from(list.querySelectorAll<HTMLButtonElement>(".hdr-btn"));
    const onClick = (e: Event) => {
      const key = (e.currentTarget as HTMLElement).dataset.sort;
      if (!key) return;
      if (key === sort) {
        setDir(dir === "asc" ? "desc" : "asc");
      } else {
        setSort(key);
        setDir(key === "name" || key === "grade" ? "asc" : "desc");
      }
    };
    for (const b of btns) b.addEventListener("click", onClick);
    return () => { for (const b of btns) b.removeEventListener("click", onClick); };
  }, [sort, dir]);

  const toggleCol = (key: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else if (colKeys.length - next.size > 1) next.add(key); // never hide the last column
      return next;
    });
  };

  const chipBase =
    "rounded-md border px-2.5 py-1 text-[12px] whitespace-nowrap transition-colors";
  const chip = (active: boolean) =>
    `${chipBase} ${active
      ? "border-accent bg-[rgba(145,132,217,0.15)] text-text"
      : "border-[rgba(233,233,237,0.16)] text-neutral-500 hover:text-text hover:border-[rgba(233,233,237,0.28)]"}`;

  const group = (
    label: string,
    name: string,
    value: string,
    set: (v: string) => void,
    opts: { v: string; l: string }[],
  ) => (
    <div>
      <div class="mb-1 text-[11px] font-medium uppercase tracking-[0.06em] text-neutral-500">{label}</div>
      <div class="flex flex-wrap gap-1.5">
        {opts.map((o) => (
          <button
            type="button"
            data-chip={name}
            data-value={o.v}
            aria-pressed={value === o.v}
            onClick={() => set(o.v)}
            class={chip(value === o.v)}
          >{o.l}</button>
        ))}
      </div>
    </div>
  );

  return (
    <div class="mt-6 rounded-lg border border-line bg-surface p-4">
      <div class="flex flex-col gap-3.5">
        <div class="flex flex-wrap items-end gap-x-5 gap-y-3">
          <div class="min-w-[220px] grow">
            <label for="mb-q" class="mb-1 block text-[11px] font-medium uppercase tracking-[0.06em] text-neutral-500">Search name or state</label>
            <input
              id="mb-q"
              type="search"
              value={q}
              placeholder="e.g. Smith or OH"
              onInput={(e) => setQ((e.target as HTMLInputElement).value)}
              class="w-full rounded-md border border-[rgba(233,233,237,0.16)] bg-bg px-2.5 py-1.5 text-[13px] text-text placeholder:text-neutral-500 focus:border-accent"
            />
          </div>
          {group("Chamber", "chamber", chamber, setChamber, [
            { v: "all", l: "All" }, { v: "house", l: "House" }, { v: "senate", l: "Senate" },
          ])}
          {group("Party", "party", party, setParty, [
            { v: "all", l: "All" }, { v: "D", l: "Dem" }, { v: "R", l: "Rep" }, { v: "I", l: "Ind" },
          ])}
          {group("Attendance grade", "grade", grade, setGrade, [
            { v: "all", l: "All" }, { v: "A", l: "A" }, { v: "B", l: "B" },
            { v: "C", l: "C" }, { v: "D", l: "D" }, { v: "F", l: "F" },
          ])}
        </div>

        <div class="border-t border-line-soft pt-3">
          <div class="mb-1 text-[11px] font-medium uppercase tracking-[0.06em] text-neutral-500">Columns</div>
          <div class="flex flex-wrap gap-1.5">
            {columns.map((c) => {
              const on = !hidden.has(c.key);
              return (
                <button
                  type="button"
                  data-chip="col"
                  data-value={c.key}
                  aria-pressed={on}
                  onClick={() => toggleCol(c.key)}
                  class={chip(on)}
                >{c.short}</button>
              );
            })}
          </div>
        </div>
      </div>

      <p aria-live="polite" class="mt-3 text-[12px] text-neutral-500">
        {count === null || count === total ? `${total} members` : `${count} of ${total} members`}
      </p>
    </div>
  );
}
