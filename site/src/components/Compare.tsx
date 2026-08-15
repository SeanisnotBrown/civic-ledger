/** @jsxImportSource preact */
import { useEffect, useMemo, useState } from "preact/hooks";

// V2-5 Nocturne — the /compare island (README screen 4). Reads the embedded data blob
// (#cmp-data) + the ?m= query string and renders 2–4 members side by side. This is the
// one client-rendered view (D77 carve-out): the member set is in the URL, invisible to a
// static build. It prints only strings the blob carried (grade labels are verbatim from
// data/grades — no evaluative literal lives here), and colours are derived from the grade
// letter, so nothing evaluative is invented client-side. Cap 2–4; a single ?m= (the
// profile's "Compare with someone" link) lands on one member + a prompt to add.

const MAX = 4;
const GRADE_COLOR: Record<string, string> = {
  A: "--color-grade-a", B: "--color-grade-b", C: "--color-grade-c", D: "--color-grade-d", F: "--color-grade-f",
};
const COL_COLOR: Record<string, string> = {
  unity: "--color-accent-300", yea: "--color-pos-yea", spon: "--color-accent",
  cospon: "--color-accent", law: "--color-accent",
};
const PARTY_COLOR: Record<string, string> = {
  D: "--color-party-d", R: "--color-party-r", I: "--color-party-i",
};
const PARTY_LABEL: Record<string, string> = { D: "Democrat", R: "Republican", I: "Independent" };
// The three vote-derived measures are NOT comparable for a non-voting delegate (D66 —
// barred from final passage), so a delegate shows "—" on these and only their bill metrics.
const VOTE_METRICS = new Set(["att", "unity", "yea"]);

function barVar(key: string, gradeLetter: string | null): string {
  if (key === "att") return `var(${gradeLetter ? GRADE_COLOR[gradeLetter] : "--color-accent-700"})`;
  return `var(${COL_COLOR[key] ?? "--color-accent"})`;
}

interface Cell { display: string; fraction: string | null; fill: number }
interface Grade { letter: string | null; label: string }
interface Member {
  name: string; party: string; state: string; district: number | null; chamber: string;
  isDelegate: boolean;
  attRank: { rank: number; percentile: number; covered: number } | null;
  grade: Grade | null;
  cells: Record<string, Cell>;
}
interface Column { key: string; short: string; domain: string; def: string }
interface Blob { columns: Column[]; cThreshold: number | null; members: Record<string, Member> }

const ordinal = (n: number) => {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] ?? s[v] ?? s[0]);
};
const chamberWord = (c: string) => (c === "senate" ? "Senate" : "House");

export default function Compare() {
  const [blob, setBlob] = useState<Blob | null>(null);
  const [ids, setIds] = useState<string[]>([]);

  // Load the blob + initial selection on the client (the component is SSR'd with no
  // document, so this can't run during render).
  useEffect(() => {
    const el = document.getElementById("cmp-data");
    if (!el?.textContent) return;
    let data: Blob;
    try { data = JSON.parse(el.textContent); } catch { return; }
    setBlob(data);
    const wanted = new URLSearchParams(window.location.search).getAll("m")
      .filter((id) => data.members[id]);
    setIds([...new Set(wanted)].slice(0, MAX));
  }, []);

  // Keep the URL in step so a comparison is shareable.
  useEffect(() => {
    if (!blob) return;
    const p = new URLSearchParams();
    for (const id of ids) p.append("m", id);
    const qs = p.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [ids, blob]);

  // Wire the server-rendered picker (#cmp-add). Functional update avoids a stale closure.
  useEffect(() => {
    const sel = document.getElementById("cmp-add") as HTMLSelectElement | null;
    if (!sel) return;
    const onChange = () => {
      const id = sel.value;
      sel.value = "";
      if (!id) return;
      setIds((prev) => (prev.includes(id) || prev.length >= MAX ? prev : [...prev, id]));
    };
    sel.addEventListener("change", onChange);
    return () => sel.removeEventListener("change", onChange);
  }, []);

  const remove = (id: string) => setIds((prev) => prev.filter((x) => x !== id));

  const members = useMemo(
    () => (blob ? ids.map((id) => ({ id, m: blob.members[id] })).filter((x) => x.m) : []),
    [blob, ids],
  );
  const mixedChamber = useMemo(
    () => new Set(members.map((x) => x.m.chamber)).size > 1,
    [members],
  );

  if (!blob) return <p class="mt-6 text-[13px] text-neutral-500">Loading…</p>;

  if (members.length === 0) {
    return (
      <p class="mt-6 rounded-lg border border-line bg-surface p-5 text-[14px] text-neutral-600">
        Add a member above to start. You can compare up to four at once — attendance, party
        unity, vote mix, and legislative output, each on its own stated scale.
      </p>
    );
  }

  const cThreshPos = blob.cThreshold != null ? ((blob.cThreshold - 50) / 50) * 100 : null;

  return (
    <div class="mt-4">
      {/* Selection chips */}
      <div class="flex flex-wrap gap-2">
        {members.map(({ id, m }) => (
          <span class="inline-flex items-center gap-2 rounded-md border border-accent bg-[rgba(145,132,217,0.15)] px-2.5 py-1 text-[12px] text-text">
            <span aria-hidden="true" class="inline-block h-2 w-2 rounded-full" style={`background:var(${PARTY_COLOR[m.party]})`}></span>
            {m.name}
            <button type="button" aria-label={`Remove ${m.name}`} onClick={() => remove(id)} class="text-neutral-500 hover:text-text">✕</button>
          </span>
        ))}
        {members.length < MAX && (
          <span class="text-[12px] text-neutral-500">· add up to {MAX - members.length} more</span>
        )}
      </div>

      {/* Cards */}
      <div class="mt-5 grid gap-3.5" style={`grid-template-columns:repeat(${members.length},minmax(0,1fr))`}>
        {members.map(({ id, m }) => {
          const gc = m.grade?.letter ? `var(${GRADE_COLOR[m.grade.letter]})` : "var(--color-accent-700)";
          const att = m.cells.att;
          return (
            <div class="rounded-lg border p-4" style={`border-color:rgba(233,233,237,0.1)`}>
              <div class="text-[15px] font-medium text-text">{m.name}</div>
              <div class="mt-1 flex items-center gap-2 text-[12px] text-neutral-500">
                <span aria-hidden="true" class="inline-block h-2 w-2 rounded-full" style={`background:var(${PARTY_COLOR[m.party]})`}></span>
                {PARTY_LABEL[m.party]} · {chamberWord(m.chamber)}, {m.state}{m.district != null ? `-${m.district}` : ""}
              </div>
              {m.grade?.letter ? (
                <div class="mt-3 rounded-md p-3" style={`background:${gc}1f;border:1px solid ${gc}59`}>
                  <div class="flex items-baseline gap-2">
                    <span class="text-[46px] font-medium leading-none tracking-[-0.04em] text-text">{m.grade.letter}</span>
                    <span class="text-[20px] tabular-nums text-text">{att.display}</span>
                  </div>
                  <div class="mt-1 text-[12px] text-neutral-600">{m.grade.label}</div>
                  {m.attRank && (
                    <div class="mt-1 text-[11px] leading-relaxed text-neutral-500">
                      {ordinal(m.attRank.rank)} of {m.attRank.covered} in the {chamberWord(m.chamber)} — higher attendance than {m.attRank.percentile}% of them.
                    </div>
                  )}
                </div>
              ) : (
                <div class="mt-3 rounded-md border border-line p-3 text-[12px] text-neutral-500">
                  {m.isDelegate
                    ? "Non-voting delegate — cannot vote on final passage, so attendance is not graded or ranked."
                    : (m.grade?.label || "Not graded on attendance.")}
                </div>
              )}
              <a href={`/m/${id}/1`} class="mt-3 inline-block text-[12px] text-accent-300 hover:underline">Open full record →</a>
            </div>
          );
        })}
      </div>

      {/* Attendance, on one axis */}
      <section class="mt-6 rounded-lg border border-line bg-surface p-5" aria-labelledby="cmp-att-h">
        <h2 id="cmp-att-h" class="text-[11px] font-medium uppercase tracking-[0.1em] text-neutral-500">Attendance, on one axis</h2>
        <div class="mt-4 space-y-2.5">
          {members.map(({ m }) => {
            const att = m.cells.att;
            const has = att.display !== "—" && !m.isDelegate;
            return (
              <div class="grid items-center gap-3" style="grid-template-columns:130px minmax(0,1fr) 46px">
                <span class="truncate text-[12px] text-neutral-600">{m.name}</span>
                <span class="relative block h-4 rounded" style="background:var(--color-track)">
                  {cThreshPos != null && (
                    <span class="absolute top-0 h-4 w-px bg-[rgba(233,233,237,0.35)]" style={`left:${cThreshPos}%`}></span>
                  )}
                  {has && (
                    <span class="absolute top-1/2 h-2.5 w-2.5 -translate-y-1/2 -translate-x-1/2 rounded-full" style={`left:${att.fill}%;background:${m.grade?.letter ? `var(${GRADE_COLOR[m.grade.letter]})` : "var(--color-accent-700)"}`}></span>
                  )}
                </span>
                <span class="text-right text-[12px] tabular-nums text-neutral-600">{m.isDelegate ? "—" : att.display}</span>
              </div>
            );
          })}
        </div>
        <p class="mt-3 text-[11px] leading-relaxed text-neutral-500">
          Axis: 50–100%{blob.cThreshold != null ? `; the tick marks the C grade (≥${blob.cThreshold}%)` : ""}. Attendance is the share of each
          member's own eligible roll calls.{mixedChamber ? " House and Senate members are shown together here for reference, but each figure is measured against that member's own chamber; the site does not rank attendance across chambers." : ""}
        </p>
      </section>

      {/* Every measure, side by side */}
      <section class="mt-4 rounded-lg border border-line bg-surface p-5" aria-labelledby="cmp-all-h">
        <h2 id="cmp-all-h" class="text-[11px] font-medium uppercase tracking-[0.1em] text-neutral-500">Every measure, side by side</h2>
        <div class="mt-4 space-y-3.5">
          {blob.columns.map((c) => (
            <div class="grid items-center gap-3" style={`grid-template-columns:150px repeat(${members.length},minmax(0,1fr))`}>
              <div>
                <div class="text-[12px] text-text" title={c.def}>{c.short}</div>
                <div class="text-[10px] text-neutral-500">scale {c.domain}</div>
              </div>
              {members.map(({ m }) => {
                const cell = m.cells[c.key];
                const suppressed = m.isDelegate && VOTE_METRICS.has(c.key);
                return (
                  <div>
                    <div class="flex items-baseline justify-between gap-1">
                      <span class="text-[12px] tabular-nums text-text/85" title={suppressed ? "Non-voting delegate — not comparable on vote measures (D66)" : undefined}>
                        {suppressed ? "—" : cell.display}
                      </span>
                      {!suppressed && cell.fraction && <span class="text-[10px] tabular-nums text-neutral-500">{cell.fraction}</span>}
                    </div>
                    <div class="mt-1 h-1.5 rounded" style="background:var(--color-track)">
                      {!suppressed && (
                        <div class="h-1.5 rounded" style={`width:${cell.fill}%;background:${barVar(c.key, m.grade?.letter ?? null)};opacity:0.9`}></div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
        <p class="mt-3 text-[11px] leading-relaxed text-neutral-500">
          Each row is scaled within its own stated range, so a count column can't look like a
          percentage. Counts and rates run to the dataset's own maximum where a fixed 0–100
          scale would render every bar invisible.
        </p>
      </section>
    </div>
  );
}
