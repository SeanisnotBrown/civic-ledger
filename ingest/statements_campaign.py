"""Collector (c): campaign issue pages for the pilot 40 (§5 Phase 3 task 2c).

The third half of the "say" side, and the one closest to the mission's own words: what a
member ran on. §2 "Statement sources" takes these from the member's most recent run. Both
other collectors feed the same pre-filter and the same categorizer, so this one emits the
same record shape.

What this is NOT, deliberately:

  * **No AI call of any kind,** and no archive.org capture (decision 8). This cannot spend.
  * **No headless browser, no new dependency, and no way round a block.** A plain GET with
    the project's own User-Agent, through `cache.fetch` and its one-request-a-second host
    throttle. A site that answers 403 is reported as `blocked`, by id: the same line the
    owner drew for `K000394`'s press page ("a bot wall, no workaround is in scope").
  * **No judgment about what a page means.** Every block of real length is kept and
    counted; the pre-filter and the triage gate decide what takes a position.

## The URLs are NOT the owner's, and the output says so

`campaign_site` and `campaign_issues_page` were researched by the copilot on 2026-11-04.
Each filled row carries `campaign_source`, and that mark rides on every record, into the
index and to the top of the report. `owner_checked` is not read here: it records the
owner's check of a row's PRESS page, and reading it as a check of a URL he has never seen
would be a false provenance in the one direction that matters. A row with a URL and no
`campaign_source` is refused: an unmarked URL is one nobody can account for.

A `.gov` address is refused whatever else the row says. Those are office sites and belong
to collector (a); an office page collected here would be labeled as something the member
ran on.

## Four outcomes that are not a statement, and each stays visible

  * `skipped`  — null in the source list: no site was found, or the site has no issues page.
    A null is an answer. It is printed by id and never as a member who said nothing.
  * `refused`  — the two rules above.
  * `blocked`  — a 403 or 429. The page exists; this collector may not read it.
  * `unread`   — a page answered and nothing came of it: a fetch error, `not-named` (below),
    or `empty` (a 200 with no text of real length, the client-side wall).

**`not-named`:** a page that does not carry the member's surname is not kept. A campaign
domain outlives its campaign: measured 2026-11-04, the domain the FEC still lists for
`D000628` Dunn now redirects through unrelated hosts to a casino, with a 200 at the end of
the chain. `cache.fetch` follows redirects, so the status cannot tell that from a real page.

## One page, or one page per issue

The categorizer returns ONE topic and ONE stance per statement, so a whole platform handed
over as a single statement would be scored as nothing. The unit is one issue:

  * **`index`** — the issues page links to two or more sub-pages of its own
    (`sub_page_urls`). Each sub-page is one statement, and the index's teasers are not
    collected, because they are truncated copies of the same words. Links are recognized by
    the stem of the list's own name: `/issues` claims `/issues/economy`, `/issue/economy`
    and `/issues-economy`; `/priorities` claims `/priority/economy`. A list whose sub-pages
    share no stem names them in `campaign_issue_pages` (`S001185`, `U000040`: `/issues/`
    links `/healthcare/`), because "every other link on the page" would take in Donate. A
    block on at least half of a row's sub-pages is the site's, not an issue's (`furniture`).
  * **`single`** — anything else. Each heading or `<summary>` opens a statement
    (`sections`); a page with none falls back to its short bold lines. A `#fragment` on the
    URL starts the read at that anchor, since a section of a home page is all some sites
    publish (`M001184`, `V000130`).

Body text is every block of at least `MIN_PARAGRAPH_CHARS`, read at block edges rather
than from `<p>` alone: `release_text` is right for press releases, but campaign sites put
position text in `<li>` and bare `<div>` too. Same limit in the same safe direction: a page
with nothing of that length reads as `empty`, never as a member with nothing to say.

## Window and date

Owner decision 1 sets the window for this source in its own sentence: "Campaign issue
pages: most recent run only." The row's `campaign_cycle` records which run that is, and a
row's cycle can precede 2023 (`S001181`'s is 2020): her term still runs on that platform,
which is the Q-J rule too (a priority lasts the term, until the next page replaces it).

**A campaign page has no date, and none is invented.** `date` is `""` and `date_precision`
is `"undated"`. The page's own marker is NOT its date: measured 2026-11-04, `F000454`'s
issues page reports 2016-05-11 and `M001238`'s 2023-05-23, the day each page was first
created, on text rewritten since. It is carried as `page_marker_date`, for information. The
retrieval day is carried as `retrieved`, and is not a date either: it says when the words
were on the page, not when they were said. Two consequences follow, and both fail closed:
`curation/review.py` will not export a statement with no date, and an undated record sorts
behind every dated one, so decision 7's newest-25 cap reaches it last.

## Output

  * `data/raw/campaign/index.json` — per-member walks, every skip, refusal and failure.
  * `data/raw/campaign/statements/<bioguide>.json` — candidate statements, the shape
    `prefilter` reads.
  * `docs/research/<date>-campaign-collection-counts.md` — the count report.

`data/raw/` is gitignored by design (§6.2): the report is the committed artifact.

    uv run ingest statements-campaign
    uv run ingest statements-campaign --members S001185,W000821
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
import yaml

from ingest import cache
from ingest.cache import RetryableHTTPError, atomic_write_text, repo_root
from ingest.statements_press import (
    _ANCHOR,
    _STRIP_BLOCKS,
    _TAGS,
    MIN_PARAGRAPH_CHARS,
    release_page_date,
    release_page_title,
    window_end,
)

SOURCE = "campaign_issue_page"
RAW_SUBDIR = ("raw", "campaign")

# A week's TTL, as collector (a): a re-run in the same week reads nothing twice.
CACHE_SOURCE = "campaign"
CACHE_TTL_HOURS = 24 * 7

# The most sub-pages one row may fetch. The widest index measured 2026-11-04 links 16, so
# this is a runaway guard rather than a collection limit.
MAX_SUB_PAGES = 60

# Fewer links than this is not an index: one match is a stray "see also".
MIN_SUB_PAGES = 2

SUB_PAGE_STEMS = ("issue", "priority")

# Below this many sub-pages, a block shared by half of them may be a real shared argument.
MIN_FURNITURE_PAGES = 4

# The undated value, one definition: see the module docstring.
UNDATED = "undated"

# Decision 1's own words, printed in the report and the index in place of a date range.
WINDOW = "most recent run only (owner decision 1)"

BLOCKED_STATUSES = (403, 429)

_COMMENT = re.compile(r"(?s)<!--.*?-->")
_HEAD = re.compile(r"(?is)<head\b.*?</head>")
_HEADING = re.compile(r"(?is)<(h[1-5]|summary)\b[^>]*>(.*?)</\1>")
_BLOCK_EDGE = re.compile(
    r"(?i)</?(?:p|div|li|ul|ol|dl|dd|dt|section|article|main|table|tr|td|blockquote|br)\b[^>]*>"
)
# Anchored where a position could use the same words: "Medicare should be paid for by..."
# is text, and a filter that took it would be a silent one.
_DISCLAIMER = re.compile(
    r"(?i)^(?:paid for|authorized) by\b|all rights reserved"
    r"|by providing your (?:phone|mobile)|message (?:and|&) data rates|contribute by mail"
)
_NOT_A_PAGE = re.compile(
    r"(?i)\.(?:pdf|jpe?g|png|gif|svg|webp|css|js|xml|ico)$|/(?:feed|page|wp-json|wp-content)(?:/|$)"
)
_ELLIPSIS = "…."


class CampaignError(RuntimeError):
    """The collector cannot run as the phase specifies."""


@dataclass(frozen=True)
class Section:
    """One issue as the page presents it."""

    title: str
    text: str


@dataclass
class MemberResult:
    member_id: str
    records: list[dict[str, Any]] = field(default_factory=list)
    layout: str = ""
    pages_read: int = 0
    # `complete`, or why not: see the module docstring.
    stopped: str = "complete"
    detail: str = ""
    # Sub-pages of an index that gave nothing, by URL. The row is still `complete`.
    text_failures: list[dict[str, str]] = field(default_factory=list)
    limit_hit: bool = False


# --- reading a page -------------------------------------------------------------------


def _clean(fragment: str) -> str:
    text = html_lib.unescape(_TAGS.sub(" ", fragment))
    return re.sub(r"\s+", " ", text).strip()


def _lines(fragment: str) -> list[str]:
    """Every run of text in this stretch of HTML, in order, whatever its length."""
    return [line for line in (_clean(p) for p in _BLOCK_EDGE.split(fragment)) if line]


def _is_text(line: str) -> bool:
    return len(line) >= MIN_PARAGRAPH_CHARS and not _DISCLAIMER.search(line)


def text_blocks(fragment: str) -> list[str]:
    """Every block of real length in this stretch of HTML, in order, minus the legal line
    a campaign site repeats under its text."""
    return [line for line in _lines(fragment) if _is_text(line)]


def _body(html: str, fragment: str = "") -> str:
    """The page with its furniture gone, from the `#fragment`'s anchor on when it has one.
    An anchor the page does not carry reads the whole page: the fragment narrows a read, it
    is not a reason to lose one."""
    if fragment:
        anchor = re.search(
            rf"""(?i)\b(?:id|name)\s*=\s*["']{re.escape(fragment)}["']""", html
        )
        if anchor is not None:
            html = html[html.rfind("<", 0, anchor.start()) :]
    return _STRIP_BLOCKS.sub(" ", _HEAD.sub(" ", _COMMENT.sub(" ", html)))


def _without_repeats(blocks: list[str]) -> list[str]:
    """Each block once, the longest copy of it. Sites print a teaser and then the same
    words in a pop-up: `F000454` prints each issue three times, the first one cut short."""
    kept: list[str] = []
    for block in blocks:
        stem = block.rstrip(_ELLIPSIS + " ")
        if any(other.startswith(stem) for other in kept):
            continue
        kept = [other for other in kept if not block.startswith(other.rstrip(_ELLIPSIS + " "))]
        kept.append(block)
    return kept


def _merged(parts: list[tuple[str, list[str]]]) -> list[Section]:
    """A title repeated down the page (a tab and its pop-up) is one section, not two, and
    a title with nothing under it opens no statement."""
    merged: dict[str, list[str]] = {}
    for title, blocks in parts:
        if blocks:
            merged.setdefault(title, []).extend(blocks)
    return [
        Section(title=title, text="\n\n".join(_without_repeats(blocks)))
        for title, blocks in merged.items()
    ]


def _by_headings(body: str, page_title: str) -> list[Section]:
    parts: list[tuple[str, list[str]]] = []
    title = page_title
    position = 0
    for match in _HEADING.finditer(body):
        heading = _clean(match.group(2))
        if heading:  # an image in an <h2>: the text under it stays where it was
            parts.append((title, text_blocks(body[position : match.start()])))
            title = heading
            position = match.end()
    parts.append((title, text_blocks(body[position:])))
    return _merged(parts)


def _by_short_lines(body: str, page_title: str) -> list[Section]:
    """A page styled with bold text instead of headings: a short line with no closing
    punctuation opens the block under it. `M001222`, `G000553` and `V000130` publish their
    whole platform this way."""
    parts: list[tuple[str, list[str]]] = [(page_title, [])]
    for line in _lines(body):
        if _is_text(line):
            parts[-1][1].append(line)
        elif len(line) < MIN_PARAGRAPH_CHARS and line[-1] not in ".!?:;,":
            parts.append((line, []))
    return _merged(parts)


def sections(html: str, *, fragment: str = "", page_title: str = "") -> list[Section]:
    """A single-page platform, one section per heading. Text above the first heading
    belongs to the page's own title. The short-line reading is only a fallback: on a page
    with real headings, a "Read more" must not open a statement."""
    body = _body(html, fragment)
    found = _by_headings(body, page_title)
    return found if len(found) > 1 else _by_short_lines(body, page_title) or found


def page_blocks(html: str) -> list[str]:
    """One sub-page's blocks, whole: it is already one issue."""
    return _without_repeats(text_blocks(_body(html)))


def furniture(pages: list[list[str]]) -> set[str]:
    """Blocks printed on at least half of a row's sub-pages. An issue's words are on its
    own page; a block on most of them is the site's: `H001046` prints one sibling's title
    at the top of all fourteen."""
    if len(pages) < MIN_FURNITURE_PAGES:
        return set()
    counts = Counter(block for page in pages for block in set(page))
    return {block for block, n in counts.items() if n * 2 >= len(pages)}


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _stems(url: str) -> tuple[str, ...]:
    """What a list's sub-pages may start with: the list's own name, singular, and the two
    names sites swap: `S001181`'s `/priorities/` links `/issue/economy/`, and `C001119`'s
    `/issues/` links `/priority/...`."""
    parsed = urlparse(url)
    name = (parsed.fragment or parsed.path.rstrip("/").rsplit("/", 1)[-1]).lower()
    name = name.rsplit(".", 1)[0]
    name = name[:-3] + "y" if name.endswith("ies") else name.removesuffix("s")
    return (name, *SUB_PAGE_STEMS) if name else SUB_PAGE_STEMS


def sub_page_urls(html: str, list_url: str) -> list[str]:
    """The issue pages this list links to, in page order, once each. Read from the page
    body only: a site's menu links every section whether or not the list does."""
    stems = _stems(list_url)
    own_path = urlparse(list_url).path.rstrip("/")
    found: dict[str, str] = {}
    for href, _inner in _ANCHOR.findall(_body(html)):
        candidate = urldefrag(urljoin(list_url, html_lib.unescape(href))).url
        path = urlparse(candidate).path.rstrip("/")
        if (
            _host(candidate) == _host(list_url)
            and path != own_path
            and path.lstrip("/").lower().startswith(stems)
            and not _NOT_A_PAGE.search(path)
        ):
            # Keyed on the path: `K000394` links the same page with and without its slash.
            found.setdefault(path, candidate)
    return list(found.values()) if len(found) >= MIN_SUB_PAGES else []


def names_member(html: str, row: dict[str, Any]) -> bool:
    return row["name"].split()[-1].casefold() in html.casefold()


# --- the record -----------------------------------------------------------------------


def statement_record(
    row: dict[str, Any],
    *,
    url: str,
    title: str,
    text: str,
    section: str = "",
    page_marker_date: str | None = None,
    retrieved: str = "",
) -> dict[str, Any]:
    """One candidate statement in the shape `prefilter` reads.

    `attribution` is `campaign-site`: the member's campaign published this, which is what
    the source is and no stronger. `granule_id` is the page's path, plus the section where
    one page holds several issues, so it stays unique and checkable by eye.
    """
    path = urlparse(url).path.rstrip("/") or "/"
    return {
        "member_id": row["id"],
        "date": "",
        "date_precision": UNDATED,
        "granule_id": f"{path}#{section}" if section else path,
        "package_id": "",
        "granule_class": "",
        "sub_granule_class": "",
        "chamber": "",
        "title": title,
        "parsed_name": "",
        "url": url,
        "speakers": 1,
        "source": SOURCE,
        "attribution": "campaign-site",
        "segments": [text],
        "chars": len(text),
        # Beyond the shared shape, and carried through: see the module docstring.
        "campaign_cycle": str(row.get("campaign_cycle") or ""),
        "campaign_source": row["campaign_source"],
        "page_marker_date": page_marker_date,
        "retrieved": retrieved,
    }


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _title(html: str) -> str:
    # `og:title` arrives still escaped ("Issues &mdash; John Moolenaar for Congress").
    return html_lib.unescape(release_page_title(html))


# --- the walk -------------------------------------------------------------------------


def _failure(exc: Exception) -> tuple[str, str]:
    """(stop reason, detail) for a fetch that raised."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return ("blocked" if status in BLOCKED_STATUSES else "error"), f"HTTP {status}"
    return "error", type(exc).__name__


def walk_member(
    row: dict[str, Any], *, read_page: Callable[[str], str], retrieved: str = ""
) -> MemberResult:
    """One member's issues page and whatever it links to. A failure on the list page stops
    the row; a failure on one sub-page is recorded and the walk goes on."""
    result = MemberResult(member_id=row["id"])
    list_url, fragment = urldefrag(row["campaign_issues_page"])
    try:
        html = read_page(list_url)
    except (RetryableHTTPError, httpx.HTTPError, OSError) as exc:
        result.stopped, result.detail = _failure(exc)
        return result
    result.pages_read = 1
    if not names_member(html, row):
        result.stopped = "not-named"
        result.detail = f"{list_url} does not carry the member's surname"
        return result

    named = list(row.get("campaign_issue_pages") or [])
    subs = named or sub_page_urls(html, row["campaign_issues_page"])
    if len(subs) > MAX_SUB_PAGES:
        result.limit_hit = True
        subs = subs[:MAX_SUB_PAGES]
    if subs:
        result.layout = "index"
        pages = [page for url in subs if (page := _read_sub_page(row, url, read_page, result))]
        shared = furniture([blocks for _url, _html, blocks in pages])
        for url, sub_html, blocks in pages:
            text = "\n\n".join(block for block in blocks if block not in shared)
            if not text:
                result.text_failures.append(
                    {"id": row["id"], "url": url, "error": "no body text"}
                )
                continue
            result.records.append(
                statement_record(
                    row,
                    url=url,
                    title=_title(sub_html),
                    text=text,
                    page_marker_date=release_page_date(sub_html),
                    retrieved=retrieved,
                )
            )
    else:
        result.layout = "single"
        for section in sections(html, fragment=fragment, page_title=_title(html)):
            result.records.append(
                statement_record(
                    row,
                    url=list_url,
                    title=section.title,
                    text=section.text,
                    section=_slug(section.title),
                    page_marker_date=release_page_date(html),
                    retrieved=retrieved,
                )
            )
    if not result.records:
        result.stopped = "empty"
        result.detail = "no text of real length in the HTML"
    return result


def _read_sub_page(
    row: dict[str, Any],
    url: str,
    read_page: Callable[[str], str],
    result: MemberResult,
) -> tuple[str, str, list[str]] | None:
    """(url, html, blocks), or None with the reason recorded."""
    try:
        html = read_page(url)
    except (RetryableHTTPError, httpx.HTTPError, OSError) as exc:
        result.text_failures.append({"id": row["id"], "url": url, "error": _failure(exc)[1]})
        return None
    result.pages_read += 1
    if not names_member(html, row):
        result.text_failures.append({"id": row["id"], "url": url, "error": "not-named"})
        return None
    return url, html, page_blocks(html)


# --- configuration --------------------------------------------------------------------


def sources(
    data_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]]]:
    """The rows to walk, the rows skipped as null, and the rows refused. Read-only, and
    nothing is filtered away unnamed, so the report can account for all 40."""
    path = data_dir / "config" / "statement-sources.yaml"
    if not path.exists():
        raise CampaignError(f"no source list at {path}")
    rows = yaml.safe_load(path.read_text(encoding="utf-8"))["members"]
    accepted: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    refused: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda r: r["id"]):
        who = {"id": row["id"], "name": row["name"], "party": row["party"]}
        site, page = row.get("campaign_site"), row.get("campaign_issues_page")
        urls = [u for u in (site, page, *(row.get("campaign_issue_pages") or [])) if u]
        if any(urlparse(u).netloc.lower().endswith(".gov") for u in urls):
            refused.append({**who, "reason": "a .gov address: collector (a)'s, not a campaign's"})
        elif urls and not row.get("campaign_source"):
            refused.append({**who, "reason": "no campaign_source: nobody accounts for this URL"})
        elif not site:
            skipped.append({**who, "reason": "no campaign site found"})
        elif not page:
            skipped.append({**who, "reason": "campaign site has no issues page"})
        else:
            accepted.append(row)
    return accepted, skipped, refused


# --- the report -----------------------------------------------------------------------


def render_report(
    results: list[MemberResult],
    accepted: list[dict[str, Any]],
    skipped: list[dict[str, str]],
    refused: list[dict[str, str]],
    *,
    generated: str,
) -> str:
    by_id = {row["id"]: row for row in accepted}
    marks = sorted({row["campaign_source"] for row in accepted})
    lines = [
        "# Campaign issue pages — collection counts (P3 task 2c)",
        "",
        f"Generated {generated} by `uv run ingest statements-campaign`. Window: {WINDOW}. "
        "No AI call and no spend. Counts only: the page text stays in the gitignored "
        "`data/raw/campaign/`.",
        "",
        f"**URL provenance: {'; '.join(marks) or 'no URLs'}.** A count here says what the "
        "pages held, not that a URL is right.",
        "",
        "## By party",
        "",
        "| Party | Rows with a URL | Rows collected | Statements | Characters | Skipped (null) "
        "| Refused | Blocked | Other unread |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    parties = sorted({r["party"] for r in accepted} | {r["party"] for r in skipped + refused})
    for party in parties:
        mine = [r for r in results if by_id[r.member_id]["party"] == party]
        lines.append(
            f"| {party} | {len(mine)} | {sum(1 for r in mine if r.records)} | "
            f"{sum(len(r.records) for r in mine)} | "
            f"{sum(rec['chars'] for r in mine for rec in r.records):,} | "
            f"{sum(1 for s in skipped if s['party'] == party)} | "
            f"{sum(1 for s in refused if s['party'] == party)} | "
            f"{sum(1 for r in mine if r.stopped == 'blocked')} | "
            f"{sum(1 for r in mine if r.stopped not in ('complete', 'blocked'))} |"
        )
    lines += [
        "",
        "## By member",
        "",
        "| Member | Party | Cycle | Layout | Pages read | Statements | Characters | Outcome |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        row = by_id[r.member_id]
        outcome = r.stopped if not r.detail else f"{r.stopped}: {r.detail}"
        if r.text_failures:
            outcome += f"; {len(r.text_failures)} sub-page(s) unread"
        if r.limit_hit:
            outcome += f"; stopped at the {MAX_SUB_PAGES}-page guard"
        lines.append(
            f"| {row['name']} (`{r.member_id}`) | {row['party']} | "
            f"{row.get('campaign_cycle') or '—'} | {r.layout or '—'} | {r.pages_read} | "
            f"{len(r.records)} | {sum(rec['chars'] for rec in r.records):,} | {outcome} |"
        )
    if skipped:
        lines += ["", "## Skipped: null in the source list", ""]
        lines += [f"- {s['name']} (`{s['id']}`, {s['party']}): {s['reason']}" for s in skipped]
    if refused:
        lines += ["", "## Refused", ""]
        lines += [f"- {s['name']} (`{s['id']}`, {s['party']}): {s['reason']}" for s in refused]
    failures = [f for r in results for f in r.text_failures]
    if failures:
        lines += ["", "## Sub-pages unread", ""]
        lines += [f"- `{f['id']}` {f['url']}: {f['error']}" for f in failures]
    lines += [
        "",
        "## What this does not say",
        "",
        "Every statement here is undated (`date_precision: undated`): a campaign page "
        "carries no date for its words, so none is stored, the export refuses it, and "
        "decision 7's newest-25 cap reaches it last. A skipped or blocked row is not a "
        "member with no positions.",
    ]
    return "\n".join(lines) + "\n"


# --- the run --------------------------------------------------------------------------


def _read_page(url: str) -> str:
    return cache.fetch(CACHE_SOURCE, url, ext="html", ttl_hours=CACHE_TTL_HOURS).text


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ingest statements-campaign",
        description="P3 task 2c — campaign issue pages for the pilot 40. No AI.",
    )
    parser.add_argument("--members", default="", help="comma-separated bioguide ids")
    args = parser.parse_args(argv)

    root = repo_root()
    data_dir = root / "data"
    accepted, skipped, refused = sources(data_dir)
    if args.members:
        wanted = {m.strip() for m in args.members.split(",") if m.strip()}
        accepted = [row for row in accepted if row["id"] in wanted]
    print(
        f"collector (c): {len(accepted)} rows to read, {len(skipped)} null, "
        f"{len(refused)} refused"
    )

    today = window_end()
    out_dir = data_dir.joinpath(*RAW_SUBDIR)
    statements_dir = out_dir / "statements"
    statements_dir.mkdir(parents=True, exist_ok=True)
    results: list[MemberResult] = []
    for n, row in enumerate(accepted, start=1):
        result = walk_member(row, read_page=_read_page, retrieved=today)
        results.append(result)
        flag = "" if result.stopped == "complete" else f"  <-- {result.stopped}: {result.detail}"
        print(
            f"  [{n}/{len(accepted)}] {row['id']} {len(result.records):3} statements "
            f"over {result.pages_read} pages ({result.layout or 'unread'}){flag}"
        )
        if result.records:
            atomic_write_text(
                statements_dir / f"{row['id']}.json",
                json.dumps(
                    {
                        "generated_at": datetime.now(UTC).isoformat(),
                        "member": {k: row[k] for k in ("id", "name", "party", "chamber", "state")},
                        "window": WINDOW,
                        "statements": result.records,
                    },
                    indent=2,
                ),
            )

    atomic_write_text(
        out_dir / "index.json",
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "window": WINDOW,
                "accepted": len(accepted),
                "skipped": skipped,
                "refused": refused,
                "walks": [
                    {
                        "member_id": r.member_id,
                        "statements": len(r.records),
                        "pages_read": r.pages_read,
                        "layout": r.layout,
                        "stopped": r.stopped,
                        "detail": r.detail,
                    }
                    for r in results
                ],
                "text_failures": [f for r in results for f in r.text_failures],
            },
            indent=2,
        ),
    )
    report_dir = root / "docs" / "research"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / f"{today}-campaign-collection-counts.md"
    atomic_write_text(
        report, render_report(results, accepted, skipped, refused, generated=today)
    )
    print(f"  index:  {(out_dir / 'index.json').relative_to(root)}")
    print(f"  report: {report.relative_to(root)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
