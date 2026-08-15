// V2-5 Nocturne — the members-explorer column model (README screen 2). One source of
// truth for what each metric column shows, shared by the /federal table and (later)
// /compare. Every definition sentence is READ from ingest/metrics.py via
// getMetrics().methodology — never retyped (acceptance criterion). Cells are computed
// here so the Astro page stays declarative and the numbers can't drift between views.
//
// DOM budget (D73 + the V2-5 spike): the /federal table is ~637 rows, and node count —
// not bytes — drives mobile FCP/LCP. So the visible column set is deliberately the
// README's six defaults, rendered lean (bar as a ::before pseudo = 0 DOM nodes). The
// four extra metrics the prototype could toggle in (nay share, laws enacted,
// cosponsored→law, attendance percentile) live on each member's profile instead; this
// carve-out is documented in docs/decisions.md.

import { getMetrics, getMemberGrade } from "./data";

const GRADE_COLOR: Record<string, string> = {
  A: "var(--color-grade-a)", B: "var(--color-grade-b)", C: "var(--color-grade-c)",
  D: "var(--color-grade-d)", F: "var(--color-grade-f)",
};

export interface ExplorerCell {
  display: string;          // "97%" | "21" | "—"
  sort: number | null;      // numeric sort key; null sorts LAST in both directions
  fraction: string | null;  // "1814/1862" | null — the always-visible denominator
  fill: number;             // 0..100, bar length within the column's own domain
  barColor: string | null;  // per-row colour (attendance grade band); null → column class supplies it
}

export interface ExplorerColumn {
  key: string;              // stable id: data-* attr, sort key, column-toggle chip
  short: string;            // header label
  full: string;             // methodology label (getMetrics().methodology[*].label)
  def: string;              // methodology sentence (the docstring text)
  domain: string;           // printed under the header, e.g. "50–100%" or "0–271"
  barClass: string;         // css class that sets --bar for this column ("" = per-row inline)
  median: string;           // formatted median across the dataset (header sub-line)
  cellFor(memberId: string): ExplorerCell;
}

const num = (v: unknown): number | null => (typeof v === "number" ? v : null);
const asPct = (v: number | null) => (v == null ? "—" : `${Math.round(v)}%`);
const asCount = (v: number | null) => (v == null ? "—" : `${v}`);
const clampFill = (v: number | null, lo: number, hi: number) =>
  v == null || hi <= lo ? 0 : Math.max(0, Math.min(100, ((v - lo) / (hi - lo)) * 100));

function median(values: number[]): number | null {
  if (!values.length) return null;
  const s = values.slice().sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

/**
 * The six explorer columns, with dataset-wide maxima (for the observed-max domains) and
 * medians precomputed once over `memberIds`. Definition text is pulled from the metric
 * docstrings so the column and the number it labels share one sentence.
 */
export function getExplorerColumns(memberIds: string[]): ExplorerColumn[] {
  const metrics = getMetrics();
  const meth = metrics.methodology;
  const M = (id: string) => metrics.members[id] ?? {};

  // dataset maxima for count / observed-max-% domains
  let maxSpon = 1, maxCospon = 1, maxLawPct = 1;
  const vAtt: number[] = [], vCross: number[] = [], vYea: number[] = [],
    vSpon: number[] = [], vCospon: number[] = [], vLaw: number[] = [];
  for (const id of memberIds) {
    const m = M(id);
    const s = num((m.sponsored as any)?.count), c = num((m.cosponsored as any)?.count),
      lp = num((m.enacted_rate as any)?.pct), a = num((m.attendance as any)?.pct),
      x = num((m.cross_aisle_support as any)?.pct), y = num((m.position_mix as any)?.yea_pct);
    if (s != null) { maxSpon = Math.max(maxSpon, s); vSpon.push(s); }
    if (c != null) { maxCospon = Math.max(maxCospon, c); vCospon.push(c); }
    if (lp != null) { maxLawPct = Math.max(maxLawPct, lp); vLaw.push(lp); }
    if (a != null) vAtt.push(a);
    if (x != null) vCross.push(x);
    if (y != null) vYea.push(y);
  }
  const medPct = (vals: number[]) => { const m = median(vals); return m == null ? "—" : `${Math.round(m)}%`; };
  const medCount = (vals: number[]) => { const m = median(vals); return m == null ? "—" : `${Math.round(m)}`; };

  return [
    {
      key: "att", short: "Attendance", full: meth.attendance?.label ?? "Attendance",
      def: meth.attendance?.text ?? "", domain: "50–100%", barClass: "",
      median: medPct(vAtt),
      cellFor(id) {
        const a = M(id).attendance as any;
        const p = num(a?.pct);
        const g = getMemberGrade(id);
        return {
          display: asPct(p), sort: p,
          fraction: a && a.eligible != null ? `${a.cast}/${a.eligible}` : null,
          fill: clampFill(p, 50, 100),
          barColor: g?.grade ? GRADE_COLOR[g.grade] : "var(--color-accent-700)",
        };
      },
    },
    {
      key: "cross", short: "Cross-aisle", full: meth.cross_aisle_support?.label ?? "Cross-aisle support",
      def: meth.cross_aisle_support?.text ?? "", domain: "0–100%", barClass: "bar-cross",
      median: medPct(vCross),
      cellFor(id) {
        const x = M(id).cross_aisle_support as any;
        const p = num(x?.pct);
        return { display: asPct(p), sort: p, fraction: x ? `${x.opposing_yea}/${x.opposing_considered}` : null, fill: clampFill(p, 0, 100), barColor: null };
      },
    },
    {
      key: "yea", short: "Yea share", full: meth.position_mix?.label ?? "Yea / Nay share",
      def: meth.position_mix?.text ?? "", domain: "0–100%", barClass: "bar-yea",
      median: medPct(vYea),
      cellFor(id) {
        const pm = M(id).position_mix as any;
        const p = num(pm?.yea_pct);
        return { display: asPct(p), sort: p, fraction: pm ? `${pm.yea}/${pm.cast}` : null, fill: clampFill(p, 0, 100), barColor: null };
      },
    },
    {
      key: "spon", short: "Sponsored", full: meth.sponsored?.label ?? "Bills sponsored",
      def: meth.sponsored?.text ?? "", domain: `0–${maxSpon}`, barClass: "bar-acc",
      median: medCount(vSpon),
      cellFor(id) {
        const c = num((M(id).sponsored as any)?.count);
        return { display: asCount(c), sort: c, fraction: null, fill: clampFill(c, 0, maxSpon), barColor: null };
      },
    },
    {
      key: "cospon", short: "Cosponsored", full: meth.cosponsored?.label ?? "Bills cosponsored",
      def: meth.cosponsored?.text ?? "", domain: `0–${maxCospon}`, barClass: "bar-acc",
      median: medCount(vCospon),
      cellFor(id) {
        const c = num((M(id).cosponsored as any)?.count);
        return { display: asCount(c), sort: c, fraction: null, fill: clampFill(c, 0, maxCospon), barColor: null };
      },
    },
    {
      key: "law", short: "Became law", full: meth.enacted_rate?.label ?? "Enacted rate",
      def: meth.enacted_rate?.text ?? "", domain: `0–${Math.round(maxLawPct)}%`, barClass: "bar-acc",
      median: medPct(vLaw),
      cellFor(id) {
        const er = M(id).enacted_rate as any;
        const p = num(er?.pct);
        return { display: asPct(p), sort: p, fraction: er ? `${er.enacted}/${er.sponsored}` : null, fill: clampFill(p, 0, maxLawPct), barColor: null };
      },
    },
  ];
}
