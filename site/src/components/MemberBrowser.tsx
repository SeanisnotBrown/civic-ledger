/** @jsxImportSource preact */
import { useEffect, useRef, useState } from "preact/hooks";

// V2-5 (perf revision, D73): a CONTROLS-ONLY island. The 637-row member list is
// rendered as static HTML by the Astro page (/federal) — crawlable, usable with JS
// off, deterministic, and cheap to load. An earlier version rendered the whole roster
// inside this Preact island; that hydrated 637 rows AND serialized the roster a second
// time as JSON island props, which sank mobile performance (CI Lighthouse 0.8 < 0.9 on
// /federal). This island now hydrates only the controls and enhances the existing list
// in place: it filters by toggling each row's inline `display` and sorts by reordering
// rows, both driven by the rows' own `data-*` attributes. It never owns the rows.
//
// Filtering uses `li.style.display` (an inline style) rather than the `hidden`
// attribute on purpose: the rows carry Tailwind's `flex` class, and an author-stylesheet
// `display:flex` beats the user-agent `[hidden]{display:none}` in the cascade — so
// `hidden` would leave "filtered-out" rows visible while the count claimed otherwise.
// Inline style wins over any class, so it can't silently fail that way.

const GRADE_ORDER: Record<string, number> = { A: 0, B: 1, C: 2, D: 3, F: 4 };
type SortKey = "name" | "attendance" | "grade";

export default function MemberBrowser({ listId, total }: { listId: string; total: number }) {
  const [chamber, setChamber] = useState("all");
  const [party, setParty] = useState("all");
  const [grade, setGrade] = useState("all");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("name");
  const [count, setCount] = useState<number | null>(null);
  const first = useRef(true);

  // Deep-link support: dashboard tiles link here with query params (?grade=F, …) so a
  // headline number clicks straight through to the list that reproduces it. Client-only.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const ch = p.get("chamber");
    if (ch === "house" || ch === "senate") setChamber(ch);
    const pa = p.get("party");
    if (pa === "D" || pa === "R" || pa === "I") setParty(pa);
    const gr = p.get("grade");
    if (gr && gr in GRADE_ORDER) {
      setGrade(gr);
      setSort("grade");
    }
    const so = p.get("sort");
    if (so === "name" || so === "attendance" || so === "grade") setSort(so);
    const query = p.get("q");
    if (query) setQ(query);
  }, []);

  useEffect(() => {
    const list = document.getElementById(listId);
    if (!list) return;
    const items = Array.from(list.querySelectorAll<HTMLElement>("li[data-member]"));
    const needle = q.trim().toLowerCase();
    let shown = 0;
    for (const li of items) {
      const ok =
        (chamber === "all" || li.dataset.chamber === chamber) &&
        (party === "all" || li.dataset.party === party) &&
        (grade === "all" || li.dataset.grade === grade) &&
        (!needle || (li.dataset.search ?? "").includes(needle));
      li.style.display = ok ? "" : "none";
      if (ok) shown++;
    }
    setCount(shown);

    // The Astro page renders the list name-sorted, so on the first (perf-critical) pass
    // with the default name sort we skip the reorder entirely; we only pay for a reorder
    // when the user (or a deep-link) actually asks for a non-default sort.
    if (!(first.current && sort === "name")) {
      const cmpName = (a: HTMLElement, b: HTMLElement) =>
        (a.dataset.name ?? "").localeCompare(b.dataset.name ?? "");
      const sorted = items.slice().sort((a, b) => {
        if (sort === "attendance") {
          const av = a.dataset.att === "" ? null : Number(a.dataset.att);
          const bv = b.dataset.att === "" ? null : Number(b.dataset.att);
          if (av == null && bv == null) return cmpName(a, b);
          if (av == null) return 1; // no record sorts last
          if (bv == null) return -1;
          return bv !== av ? bv - av : cmpName(a, b); // high → low
        }
        if (sort === "grade") {
          const ao = a.dataset.grade ? GRADE_ORDER[a.dataset.grade] : 99;
          const bo = b.dataset.grade ? GRADE_ORDER[b.dataset.grade] : 99;
          return ao !== bo ? ao - bo : cmpName(a, b); // A → F, ungraded last
        }
        return cmpName(a, b);
      });
      for (const li of sorted) list.appendChild(li);
    }
    first.current = false;
  }, [chamber, party, grade, q, sort, listId]);

  const labelCls = "block text-xs font-medium text-neutral-500";
  // Nocturne (D74): dark controls. `color-scheme: dark` on <html> also darkens the
  // native <select> dropdowns and the search field's clear affordance.
  const inputCls =
    "mt-1 rounded-md border border-[rgba(233,233,237,0.16)] bg-surface px-2 py-1 text-sm text-text focus:border-accent";

  return (
    <div>
      <div class="flex flex-wrap items-end gap-3">
        <div class="grow">
          <label for="mb-q" class={labelCls}>Search name or state</label>
          <input
            id="mb-q"
            type="search"
            value={q}
            placeholder="e.g. Smith or OH"
            onInput={(e) => setQ((e.target as HTMLInputElement).value)}
            class={`${inputCls} w-full`}
          />
        </div>
        <div>
          <label for="mb-chamber" class={labelCls}>Chamber</label>
          <select id="mb-chamber" value={chamber} onChange={(e) => setChamber((e.target as HTMLSelectElement).value)} class={inputCls}>
            <option value="all">All</option>
            <option value="house">House</option>
            <option value="senate">Senate</option>
          </select>
        </div>
        <div>
          <label for="mb-party" class={labelCls}>Party</label>
          <select id="mb-party" value={party} onChange={(e) => setParty((e.target as HTMLSelectElement).value)} class={inputCls}>
            <option value="all">All</option>
            <option value="D">Democrat</option>
            <option value="R">Republican</option>
            <option value="I">Independent</option>
          </select>
        </div>
        <div>
          <label for="mb-grade" class={labelCls}>Attendance grade</label>
          <select id="mb-grade" value={grade} onChange={(e) => setGrade((e.target as HTMLSelectElement).value)} class={inputCls}>
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
        {count === null || count === total ? `${total} members` : `${count} of ${total} members`}
      </p>
    </div>
  );
}
