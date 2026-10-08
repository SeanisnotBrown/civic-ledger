# Aesthetics audit — GPT-6.1 Sol, 2026-10-08

Reference input only. Reviewed the live site at 1440px and 390px. Nothing here is ratified; each item is applied only in the phase IMPLEMENTATIONv3.md assigns it to, and only after the owner approves it at that phase.

Overall verdict (Sol): restrained and serious, but hierarchy is not deliberate. Navy + muted panels + lavender repeated everywhere reads generic. Explanatory text, future features, controls, and evidence get similar prominence. Biggest wins: stronger typography, fewer competing containers, put the useful record earlier.

## Site-wide
- **AES-01 Title hierarchy** (all pages) — one scale: desktop titles ~36–40px, phone ~28–32px, section heads ~22–24px; small uppercase only for metadata. Style. High.
- **AES-02 Fewer panels** (home, /federal, member pages) — filled panels only for principal result, controls, charts; supporting content uses spacing/dividers; drop redundant wrappers. Structural. High.
- **AES-03 Accent colors get distinct jobs** (/federal, /congress, /v/, member pages) — Sol says keep lavender for interaction; grade colors only for grades, party colors only for party, labeled restrained outcome badges (passed/failed/became law currently look alike). Style. High.
- **AES-04 Readable secondary text** (/federal, member, roll call) — denominators, chart labels, captions at 11–13px muted gray; raise to 13–14px, stronger contrast. Style. High.
- **AES-05 Buttons vs selections vs links** (/federal, member, bill, /congress) — filter buttons 28px tall; define primary/secondary/selected; ~44px phone tap targets; filled selected state. Style. High.
- **AES-06 Wordmark + active nav** (header) — wordmark reads as a small link; active item only lavender text; phone header wraps to two rows. Give wordmark proportions, active underline, intentional phone header. Style. Medium.
- **AES-07 Reading widths + spacing scale** (home, bill, topic results, /pairing) — prose 65–75ch, wider region for tables/charts, repeatable spacing scale, headings closer to their content. Layout. Medium.

## Home
- **AES-08 Hero around the state selector** — big empty right side on desktop; selector input narrower than its panel; on phone several paragraphs precede it. Selector directly under headline + lead; longer paragraph below; smaller top gap. Layout. High.
- **AES-09 Demote the three shortcut cards** — make member lookup prominent; "How grades work" and "Where the data comes from" become quiet text links. Structural. High.

## Members explorer (/federal)
- **AES-10 Lookup before the chart** — order: title, search + essential filters, results, then distribution + explanation (explanation in a disclosure). Layout. High.
- **AES-11 Phone rows expose the grade** — on phone, grade and numbers are offscreen to the right. Compact row: name/seat left, grade/attendance right, expandable secondary measures. Keep desktop table. Structural. High.
- **AES-12 Quieter desktop table** — grade cells, bars, %, denominators, medians, + and × all compete. Strongest weight on name, grade, attendance; dedicated cells for compare/set-aside controls. Style. High.
- **AES-13 Histogram on phone** — bar counts crowd; five boxed legend entries make it tall. Fewer permanent labels on narrow screens; compact wrapping legend. Same bins/scale. Layout. Medium.

## Member pages (/m/B001314/1, /m/P000145/1)
- **AES-14 Recorded work before planned categories** — four "Not yet graded" cards and "Not collected yet" panel sit before the real record. Collapse into compact disclosures after it; keep wording. Structural. High.
- **AES-15 Identity + attendance as one header** — grade panel sits apart, blank area under portrait; phone grade panel holds a long future-feature note. One balanced header: grade, %, eligible votes, rank together. Layout. High.
- **AES-16 Fixed-width bars instead of wrapping vote dots** — dot rows wrap to different heights; height becomes an accidental signal. Four aligned bars, shared scale, same counts/%. Structural. Medium.
- **AES-17 Member marker in attendance scatter** — points cluster at right edge; 90/95/100 ticks crowd on phone; label sits over dense region. Responsive ticks, stronger marker, offset label. Style. Medium.

## Bill page (/b/s2403-119)
- **AES-18 Title vs metadata** — small title above a text block; "Latest action" label wraps on phone. Full heading prominence; latest action as its own row; quieter metadata; labels above values on phone. Layout. High.
- **AES-19 Action timeline structure** — entries look alike. Group by date, date gutter + rule on desktop, date above action on phone; action text primary, codes/sources secondary. Layout. High.
- **AES-20 Feed controls on phone** — "Open the feed", URL input, Copy squeezed on one row; URL clipped. URL full width, buttons below. Layout. Medium.

## Roll call (/v/h-119-2-0314)
- **AES-21 Lead with the result** — "House Roll #314" dominates; outcome and tally sit under the chart. Outcome + tally above chart; tie the bill to the question; demote session metadata. Layout. High.
- **AES-22 Party-chart totals** — small segments have no counts; Independents row fills its track for one vote. Exact counts beside every party row; label the within-party % scale. Layout. Medium.
- **AES-23 Individual positions list** — dense 5-column tile grid, truncated names; hundreds of tiles on phone. List/table with full names, search + position filter. Structural. Medium.

## Methodology (/methods)
- **AES-24 Section index** — sticky index on desktop, expandable on phone, from existing headings. Structural. High.
- **AES-25 Grade-band panel on phone** — horizontal scrollbar at 390px; counts/bars past the edge. Stack grade/threshold/count per row, bar beneath; set-aside list one row per member. Layout. High.

## Topics (/topics)
- **AES-26 Browsing structure** — 33 policy areas + 974 subject terms as long link lists. Topic search, alphabet jump for subject terms, clear split between the two. Exact government labels. Structural. High.
- **AES-27 Scannable rows/results** — tight underlined rows, bare counts; results lead with bill number. Padding + aligned count badges; title primary, number/date secondary; action text at readable width. Layout. Medium.

## Legislative activity (/congress)
- **AES-28 Ordering explanation behind a disclosure** — six-point explanation precedes the list (over a screen on phone). Keep date window + count visible; explanation in a closed disclosure. Structural. High.
- **AES-29 One action-row pattern** (home, /congress, member pages) — status/date, prominent title, official action, then record links; clear title disclosures. Layout. High.

## Compare (/compare)
- **AES-30 Identities beside measures** — phone cards side by side in narrow columns. Compact identity/grade summaries; repeat names atop measure columns; labeled comparison blocks on phone. Layout. Medium.

## Supporting pages (/corrections, /privacy, /pairing)
- **AES-31 Article template** — shared title scale, subsection spacing, list indentation, footer divider. Style. Medium.

Sol's top five for first impressions: AES-01, AES-08, AES-02, AES-10/11, AES-14.
Not assessed: /feed.xml (blocked by Chrome).
