"""Collector (a): member press-release pages for the pilot 40 (§5 Phase 3 task 2).

The second half of the "say" side. Collector (b) reads what a member said on the floor;
this reads what their office published under their name. Both feed one pre-filter and one
categorizer, so both emit the same record shape.

What this is NOT, deliberately:

  * **No AI call of any kind,** and no archive.org capture. Decision 8 puts capture after
    the pre-filter and the triage gate; this run cannot spend a cent.
  * **No headless browser and no new dependency.** A plain GET and the standard library.
    The eight rows whose press lists render client-side are therefore out of reach, which
    is exactly why they are still `owner_checked: false` — see "Refusal" below.
  * **No judgment about what a statement means.** Everything collected is kept and
    counted, including the tributes and the town-hall notices the pre-filter drops later.

## Refusal is visible, never silent

`data/config/statement-sources.yaml` is owner-maintained and READ-ONLY here. Its own
provenance block says it plainly: "Collector (a) and (c) must refuse a row that still
says false." So this collector takes the 32 rows with `owner_checked: true` and refuses
the other 8, by id, in the index and in the report — and `--members` cannot override it.
A refusal that does not appear in the output is indistinguishable from a member who
published nothing, which would read as silence on the member's page.

The 8 refused (fact 7, STATUS.md): seven render their press list client-side — a plain
GET sees the right `<title>` and zero dated items — and `K000394` answers 403 to our
User-Agent and to a browser one alike. The owner's decision between an RSS feed (which
reaches back only 10-20 items, not to 2023-01-03) and a rendered fetch is still owed.

## One extractor, not three CMSs

The 32 accepted rows run on several page families: House Drupal (`/media/press-releases`,
`?page=N`, 0-based), House ASPX (`documentquery.aspx`, `&Page=N`, 1-based), Senate and
House WordPress (`/page/N/`, sometimes with dated permalinks at the site root), and one
that keys each release by query string on the list page's own path. Rather than a parser
per CMS, one pass reads what they have in common:

  * a release is an anchor whose href is under the list page's path, carries the list's
    own distinguishing segment deeper on the host, is a dated permalink, or is a
    `documentsingle.aspx?DocumentID=` link — see `_is_release_url`;
  * its title is the anchor's own text, which is why anchors under 20 characters are
    skipped — "Read more" and "Press Releases" are navigation, not titles;
  * its date is the NEAREST date to the anchor, measured from the anchor's own edges —
    see `nearest_date`, and the real bug that rule exists for.

**28 of the 32 accepted rows collect.** Four do not: `K000377`, `M001222`, `R000622` and
`W000830` return a 200 whose release list is not in the HTML — the same client-side wall
as the eight `owner_checked: false` rows, on rows the owner marked accepted. They are
reported as `empty` walks, by id, and need the same owner decision as fact 7's eight.

Body text is every `<p>` over 60 characters, after script, style, nav, header, footer,
form and aside are removed. Validated on one release from each family 2026-10-14: 4,283 /
3,001 / 2,195 characters of clean release text, no navigation and no footer.

**Known limit, accepted and the reason it is the safe direction:** a release whose body
is not in `<p>` elements reads as empty and is recorded as a text failure for that
member, never as a statement with no words. Under-collecting is visible in the report;
silently collecting a page's navigation as a member's words is not.

## Window and pagination

Window start is 2023-01-03 (owner decision 1), the same as collector (b). Press lists are
reverse-chronological, so pagination stops at the first page whose newest item predates
the window.

Six stop reasons are recorded per member, because they do not mean the same thing and the
report must not print one as the other (see `MemberResult.complete`):

  * `window`    — reached a page older than 2023-01-03. COMPLETE.
  * `exhausted` — the pager ran off the end, after two or more pages, of an archive that
                  BEGINS inside the window. Also COMPLETE: a member who started
                  publishing in 2025 can never reach 2023, and calling that incomplete
                  would misreport a full collection.
  * `single-page` — ran out after ONE page. A ten-release archive and a "load more"
                  button look identical to a plain GET, so this is reported as needing a
                  human look rather than as a total.
  * `empty`     — a 200 with no items on the FIRST page: the client-side wall.
  * `repeat`    — a pager that ignored its parameter and re-served a page already read.
  * `error`     — a fetch failed. What was already found is kept.
  * `limit`     — `--limit-pages`, or the `MAX_PAGES` runaway guard.

## Output

  * `data/raw/press/index.json` — every release found in the window, plus the refusals
    and the per-member failures.
  * `data/raw/press/statements/<bioguide>.json` — candidate statements in the shape
    `prefilter` reads, with the release body as the single segment.
  * `docs/research/<date>-press-collection-counts.md` — the count report.

`data/raw/` is gitignored by design (§6.2): the cache is a dev convenience, the report is
the committed artifact.

    uv run ingest statements-press                   # index + body text for the window
    uv run ingest statements-press --index-only      # the count report, no release bodies
    uv run ingest statements-press --limit-pages 2 --members B001257   # a smoke run
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import yaml

from ingest import cache
from ingest.cache import RetryableHTTPError, atomic_write_text, repo_root

# Owner decision 1, 2026-10-09: the 118th Congress convened on this date.
WINDOW_START = "2023-01-03"

SOURCE = "member_press"
RAW_SUBDIR = ("raw", "press")

# The cache subdir, and a week's TTL: a press list's newest page changes often enough
# that a month-old copy would miss releases, and rarely enough that a daily re-fetch of
# 3,000 pages would be rude.
CACHE_SOURCE = "press"
CACHE_TTL_HOURS = 24 * 7

# A page walk stops here whatever the dates say. The deepest in-window list measured
# 2026-10-14 is ~100 pages (Hagerty's archive runs to 251 pages in total), so 200 is a
# runaway guard rather than a collection limit.
MAX_PAGES = 200

# An anchor shorter than this is navigation, not a release title.
MIN_TITLE_CHARS = 20

# A paragraph shorter than this is a caption, a byline or a share prompt.
MIN_PARAGRAPH_CHARS = 60

# How far after an anchor its date may sit, and how far before. Measured 2026-10-14 on
# the 32 accepted rows: the widest forward gap is ~300 characters and the widest backward
# gap is 441 (`Y000064`, which prints the date above the title in a separate widget).
DATE_WINDOW_CHARS = 400
DATE_LOOKBACK_CHARS = 700

# A date the publisher printed INSIDE the title anchor, which is already a field of its
# own on the record. The ordinal suffix is optional and is not checked against the day:
# the day is read from the digits, so "October 13th" and a publisher's stray "13st" both
# give 13, and refusing the second would drop a real release over a typo. Measured
# 2026-10-14, `H001046` Heinrich prints every date as "October 13th, 2026", so without
# this his titles ship with the date glued to the front.
_LEADING_DATE = re.compile(
    r"^\s*(?:(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,?\s*)?"
    r"(?:January|February|March|April|May|June|July|August|September|October|November"
    r"|December)\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+20\d\d\s*",
    re.IGNORECASE,
)


class PressError(RuntimeError):
    """The collector cannot run as the phase specifies."""


# --- reading a list page --------------------------------------------------------------

_ANCHOR = re.compile(r'<a\s[^>]*?href="([^"#]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_STRIP_BLOCKS = re.compile(
    r"(?is)<(script|style|nav|header|footer|form|aside|svg|noscript)\b.*?</\1>"
)
_PARAGRAPH = re.compile(r"(?is)<p\b[^>]*>(.*?)</p>")

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_MONTH_NUMBER = {name.lower()[:3]: i for i, name in enumerate(_MONTHS, start=1)}
# The ordinal suffix sits OUTSIDE group 2: `_iso_from_long` reads the day with `int()`,
# which cannot parse "13th". Optional and unchecked, as in `_LEADING_DATE` above.
_DATE_LONG = re.compile(
    rf"\b({'|'.join(_MONTHS)})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(20\d\d)\b",
    re.IGNORECASE,
)
_DATE_ISO = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")


@dataclass(frozen=True)
class Release:
    """One press release as its list page announces it."""

    member_id: str
    date: str
    title: str
    url: str


def flatten(html: str) -> str:
    """The page as one line. Every pattern here is written with single spaces in it, so
    the page's own line breaks must go first or nothing matches."""
    return re.sub(r"\s+", " ", html)


def _iso_from_long(match: re.Match[str]) -> str:
    month = _MONTH_NUMBER[match.group(1).lower()[:3]]
    return f"{match.group(3)}-{month:02d}-{int(match.group(2)):02d}"


def _first_date(window: str) -> tuple[int, str] | None:
    """The first date in a window, with its offset. ISO wins over the printed form at the
    same position: `<time datetime="2026-10-01">October 1, 2026</time>` carries both, and
    the machine-readable one is the publisher's own."""
    iso = _DATE_ISO.search(window)
    long = _DATE_LONG.search(window)
    if iso is not None and (long is None or iso.start() <= long.start()):
        return iso.start(), f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    if long is not None:
        return long.start(), _iso_from_long(long)
    return None


def _last_date(window: str) -> tuple[int, str] | None:
    """The last date in a window, with its offset."""
    isos = list(_DATE_ISO.finditer(window))
    longs = list(_DATE_LONG.finditer(window))
    iso = isos[-1] if isos else None
    long = longs[-1] if longs else None
    if iso is not None and (long is None or iso.start() >= long.start()):
        return iso.start(), f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    if long is not None:
        return long.start(), _iso_from_long(long)
    return None


def nearest_date(flat: str, start: int, end: int) -> str | None:
    """The date nearest to one title anchor, measured from the anchor's own edges.

    The three families print the date in three places, and NEAREST-WINS is the only rule
    that reads all three correctly:

      * inside the anchor's text (`S001232`) — distance 0, so it always wins;
      * just after the anchor (House Drupal, ASPX) — forward from the anchor's END;
      * above the anchor (`H001081` ~109 characters, `Y000064` ~441) — backward from the
        anchor's START, taking the LAST date in that window.

    Forward-first is NOT good enough and was a real bug: on `H001081` the NEXT item's
    date sits ~180 characters after this anchor closes, inside the forward window, so
    every release on the page took its neighbour's date. Measured 2026-10-14, the first
    Hayes release read 2026-09-17 when the page says October 9, 2026. A statement's date
    is the key it is compared against a vote by, so a one-item shift is not cosmetic.
    """
    inner = _first_date(flat[start:end])
    if inner is not None:
        return inner[1]
    forward = _first_date(flat[end : end + DATE_WINDOW_CHARS])
    back_window = flat[max(0, start - DATE_LOOKBACK_CHARS) : start]
    backward = _last_date(back_window)
    forward_distance = forward[0] if forward is not None else None
    backward_distance = len(back_window) - backward[0] if backward is not None else None
    if forward_distance is None:
        return backward[1] if backward is not None else None
    if backward_distance is None:
        return forward[1]
    return forward[1] if forward_distance <= backward_distance else backward[1]


# A dated permalink: `/2026/07/22/rep-loudermilk-on-passage-of-fy2027-ndaa`, and the
# single-digit-month, no-day variant `/2026/2/hayes-secures-over-10-million`. Measured
# 2026-10-14: `L000583` and `H001081` list their releases at the site root under these
# shapes rather than under their own list path, so the "under the list path" test alone
# found zero items on pages holding nine and ten.
_DATED_PERMALINK = re.compile(r"/20\d\d/\d{1,2}/(?:\d{1,2}/)?[^/]")

# A pager link is not a release, and it passes every other test below: it is on the host,
# under the list path, and sits next to the dates of the items it pages past.
_PAGER = re.compile(r"/page/\d+/?$|[?&](?:page|Page)=\d+")


def _is_release_url(candidate: str, list_url: str) -> bool:
    """Whether this href is a release rather than navigation.

    Four shapes cover all the families measured on the 32 accepted rows:

      * a path UNDER the list page's own path (House Drupal, Senate WordPress);
      * a path elsewhere on the host that carries the list's own distinguishing segment
        — `S001232` lists at `/newsroom/press-releases/` and links to
        `/news/press-releases/<slug>`, which no "under the list path" test can reach;
      * a dated permalink anywhere on the host (`L000583`, `H001081`);
      * the ASPX CMS's `documentsingle.aspx?DocumentID=`.

    Anything off-host is never a release: a member's press page links to news coverage,
    and a newspaper's article is not the member's own statement.
    """
    here, there = urlparse(list_url), urlparse(candidate)
    if there.netloc != here.netloc:
        return False
    path = there.path.rstrip("/")
    base = here.path.rstrip("/")
    if _PAGER.search(candidate):
        return False
    if path == base:
        # `H001081` keys each release by query string on the list's own path:
        # `/press-releases?ID=9146BD9B-...`. A query the list page does not itself carry
        # is what separates an item from the list, so the bare list URL is still refused.
        return bool(there.query) and there.query != here.query
    if "documentsingle.aspx" in path.lower() or _DATED_PERMALINK.search(path):
        return True
    if base and path.startswith(base):
        return True
    # The list's own last segment, e.g. "press-releases", seen anywhere deeper on the
    # host. Requires a slug after it so the section index itself is not a release.
    segment = base.rsplit("/", 1)[-1]
    return bool(segment) and re.search(rf"/{re.escape(segment)}/[^/]", path) is not None


def extract_releases(html: str, list_url: str, member_id: str) -> list[Release]:
    """Every dated release one list page announces, in page order and deduplicated.

    An anchor with no date near it is skipped rather than dated by guesswork: an undated
    row cannot be placed inside or outside the collection window, and a statement whose
    date is a guess cannot be compared against a vote.
    """
    flat = flatten(html)
    out: list[Release] = []
    seen: set[str] = set()
    for match in _ANCHOR.finditer(flat):
        title = html_lib.unescape(_TAGS.sub("", match.group(2))).strip()
        if len(title) < MIN_TITLE_CHARS:
            continue
        url = urljoin(list_url, html_lib.unescape(match.group(1)))
        if url in seen or not _is_release_url(url, list_url):
            continue
        date = nearest_date(flat, match.start(), match.end())
        if date is None:
            continue
        seen.add(url)
        # A title whose anchor swallowed the date reads "September 29, 2026 Sheehy's
        # Protect America Act ..."; the date is already a field of its own.
        out.append(
            Release(
                member_id=member_id,
                date=date,
                title=_LEADING_DATE.sub("", title).strip() or title,
                url=url,
            )
        )
    return out


# A `?page=` pager link that starts at zero. Its presence on the first page is how the
# site itself tells us whether `?page=1` is the SECOND page or a second copy of the first.
_ZERO_BASED_PAGER = re.compile(r"[?&]page=0\b", re.IGNORECASE)


def zero_based_pager(html: str) -> bool:
    """Whether this site's `?page=` parameter counts from zero, asked of the site itself.

    Measured 2026-10-14: House Drupal prints `?page=0` next to `?page=1`, so `?page=1` is
    the second page. `H001081` prints `?page=1` through `?page=14` and no `?page=0`, so
    `?page=1` IS the first page — and guessing wrong there cost the whole walk: the second
    request returned the first page again, the duplicate rule found nothing new, and the
    member was collected 10 releases deep instead of hundreds.
    """
    return bool(_ZERO_BASED_PAGER.search(html))


def page_url(list_url: str, page: int, *, zero_based: bool = True) -> str:
    """The `page`-th list page, counting from 0 for the first one, in whichever scheme
    this family uses.

    The SCHEME comes from the list URL, so a redesigned pager cannot silently restart the
    walk at page 1. The `?page=` OFFSET comes from the first page's own links, because
    the two Drupal-shaped families disagree about it — see `zero_based_pager`.
    """
    if page == 0:
        return list_url
    parsed = urlparse(list_url)
    if "documentquery.aspx" in parsed.path.lower():
        # House ASPX: 1-based, and page 1 IS the list URL, so page N is &Page=N+1.
        joiner = "&" if parsed.query else "?"
        return f"{list_url}{joiner}Page={page + 1}"
    if parsed.netloc.endswith("senate.gov") or "/category/" in parsed.path:
        # WordPress: /press-releases/page/2/
        return f"{list_url.rstrip('/')}/page/{page + 1}/"
    joiner = "&" if parsed.query else "?"
    return f"{list_url}{joiner}page={page if zero_based else page + 1}"


# --- reading a release page -----------------------------------------------------------


def release_text(html: str) -> str:
    """The release body: every paragraph of real length, once the page's furniture is
    gone. See the module docstring for why an empty result is a recorded failure rather
    than a statement with no words."""
    stripped = _STRIP_BLOCKS.sub(" ", html)
    paragraphs = [
        html_lib.unescape(_TAGS.sub("", block)).strip()
        for block in _PARAGRAPH.findall(stripped)
    ]
    kept = [p for p in paragraphs if len(p) >= MIN_PARAGRAPH_CHARS]
    return "\n\n".join(kept)


def statement_record(release: Release, text: str) -> dict[str, Any]:
    """One candidate statement in the shape `prefilter` reads.

    `attribution` is `press-office` and says so honestly: the member's office published
    this under their name, which is weaker than the Congressional Record opening their
    own turn and stronger than a guess. It is deliberately not `none` — `none` is the
    pre-filter's "no words could be attributed" drop, and these words are attributable.

    `granule_id` carries the collector's own id for the statement, which for a press
    release is its URL path: unique, stable, and checkable by eye against the source.
    """
    return {
        "member_id": release.member_id,
        "date": release.date,
        "granule_id": urlparse(release.url).path.rstrip("/") or release.url,
        "package_id": "",
        "granule_class": "",
        "sub_granule_class": "",
        "chamber": "",
        "title": release.title,
        "parsed_name": "",
        "url": release.url,
        "speakers": 1,
        "source": SOURCE,
        "attribution": "press-office",
        "segments": [text] if text else [],
        "chars": len(text),
    }


# --- the walk -------------------------------------------------------------------------


@dataclass
class MemberResult:
    """What the walk found for one member, and why it stopped."""

    member_id: str
    releases: list[Release]
    pages_read: int
    stopped: str  # window | exhausted | single-page | empty | repeat | error | limit
    detail: str = ""

    @property
    def complete(self) -> bool:
        """Whether every release in the window was collected.

        Two stops mean complete, for different reasons: `window` — the walk reached a
        page older than 2023-01-03, so everything in the window is behind us; and
        `exhausted` — the pager ran off the end of the archive, which is what happens to
        a member whose press archive BEGINS inside the window. Calling that second case
        incomplete would print INCOMPLETE beside a member who was collected in full, in
        the one report decision 4 exists to make trustworthy.

        Everything else (`single-page`, `empty`, `repeat`, `error`, `limit`) stopped the
        walk before its natural end, or could not tell whether it had, and those counts
        are a floor rather than a total.
        """
        return self.stopped in ("window", "exhausted")


def _end_of_archive(page: int) -> tuple[str, str]:
    """How to report a pager that ran out at `page`, which depends on whether it ever
    paged. `page` is the index of the page that had nothing, so it is also the count of
    pages that DID have releases — the empty page is not one of them.

    After two or more pages, running out is the archive genuinely ending — a member whose
    press archive BEGINS inside the window can never reach 2023-01-03, and that walk is
    complete.

    After exactly ONE page it is ambiguous, and the ambiguity matters: a member who has
    published ten releases and a member whose deeper pages are behind a "load more"
    button look identical to a plain GET. Measured 2026-10-14: `Y000064` yields 20
    releases and answers 404 on `/page/2/`, which for a senator over three and a half
    years is not plausibly their whole output. So a single-page archive is reported as
    needing a human look rather than as a total — under-claiming completeness is the only
    safe direction in the report the owner approves spend against.
    """
    if page > 1:
        return "exhausted", f"archive ends at page {page}"
    return (
        "single-page",
        "one page only, and no page 2 — a short archive and a JavaScript "
        "'load more' are indistinguishable to a plain GET",
    )


def walk_member(
    row: dict[str, Any],
    *,
    read_page: Callable[[str], str],
    window_start: str = WINDOW_START,
    limit_pages: int = 0,
) -> MemberResult:
    """One member's press list, page by page, until the window's start.

    Stops at the first page whose NEWEST item predates the window (reverse-chronological
    lists, so everything deeper is older), at a page the extractor reads nothing from,
    or at `limit_pages`. The stop reason travels with the result because "complete" and
    "we gave up" must never read the same in the report.
    """
    member_id = row["id"]
    list_url = row["press_page"]
    ceiling = min(limit_pages, MAX_PAGES) if limit_pages else MAX_PAGES
    found: list[Release] = []
    seen: set[str] = set()
    pages = 0

    zero_based = True
    for page in range(ceiling):
        url = page_url(list_url, page, zero_based=zero_based)
        try:
            html = read_page(url)
        except httpx.HTTPStatusError as exc:
            if page > 0 and exc.response.status_code == 404:
                # A pager URL that 404s is how most of these sites say "there is no page
                # N" — the end of the archive, not a failed fetch, and reporting it as an
                # error would print INCOMPLETE beside a member collected in full.
                return MemberResult(member_id, found, pages, *_end_of_archive(page))
            return MemberResult(member_id, found, pages, "error", f"HTTP {exc} on {url}")
        except (RetryableHTTPError, httpx.HTTPError, OSError) as exc:
            return MemberResult(member_id, found, pages, "error", f"{type(exc).__name__} on {url}")
        pages += 1
        if page == 0:
            # Asked of the site itself, once, before the second request is built.
            zero_based = zero_based_pager(html)
        releases = extract_releases(html, list_url, member_id)
        fresh = [r for r in releases if r.url not in seen]
        if not releases:
            if page == 0:
                # A 200 with no items at all: the client-side wall of fact 7, on a row
                # the owner marked accepted. Not a member who published nothing.
                return MemberResult(
                    member_id, found, pages, "empty", "no dated releases on the first page"
                )
            # The pager ran past the end of the archive.
            return MemberResult(member_id, found, pages, *_end_of_archive(page))
        if not fresh:
            # Items, but every one already seen: the pager ignored its parameter and
            # re-served a page we have. Incomplete, and silently collecting page 1 two
            # hundred times is what this stops.
            return MemberResult(
                member_id, found, pages, "repeat", f"page {page} repeats a page already read"
            )
        for release in fresh:
            seen.add(release.url)
            if release.date >= window_start:
                found.append(release)
        if max(r.date for r in fresh) < window_start:
            return MemberResult(member_id, found, pages, "window")

    return MemberResult(member_id, found, pages, "limit", f"stopped at {ceiling} pages")


# --- configuration --------------------------------------------------------------------


def sources(data_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """The accepted rows and the refused ones, from the owner-maintained list.

    Read-only, and the refusals are returned rather than filtered away so the report can
    name them. A row with `owner_checked: true` and no `press_page` is a refusal too —
    accepting it would walk `None`.
    """
    path = data_dir / "config" / "statement-sources.yaml"
    if not path.exists():
        raise PressError(f"no source list at {path}")
    rows = yaml.safe_load(path.read_text(encoding="utf-8"))["members"]
    accepted: list[dict[str, Any]] = []
    refused: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda r: r["id"]):
        if not row.get("owner_checked"):
            refused.append({"id": row["id"], "name": row["name"], "reason": "owner_checked: false"})
        elif not row.get("press_page"):
            refused.append({"id": row["id"], "name": row["name"], "reason": "no press_page"})
        else:
            accepted.append(row)
    return accepted, refused


def window_end(today: datetime | None = None) -> str:
    """The window's inclusive end: today, UTC. A collector's window is wall-clock by
    nature — it asks "what has been published?" — unlike the §6.3 determinism rules."""
    return (today or datetime.now(UTC)).date().isoformat()


# --- the report -----------------------------------------------------------------------


def render_report(
    results: list[MemberResult],
    rows: list[dict[str, Any]],
    refused: list[dict[str, str]],
    text_counts: dict[str, int],
    *,
    window: dict[str, str],
    text_phase: str,
    text_failures: int = 0,
) -> str:
    """The count report (decision 4's per-source, per-member half, for this source).

    Every member appears, including one the walk found nothing for, and every refusal
    appears by id: a missing row would read as "collected, published nothing".
    """
    by_id = {row["id"]: row for row in rows}
    lines = [
        "# Collector (a) — member press releases: the count report",
        "",
        f"Window **{window['start']} to {window['end']}** (owner decision 1). "
        f"Source list: `data/config/statement-sources.yaml`, owner-maintained and read "
        f"only. **No AI call, no archive capture, no spend.**",
        "",
        f"**{len(results)} rows collected, {len(refused)} refused.** "
        f"{sum(len(r.releases) for r in results)} releases in the window.",
        "",
    ]
    if text_phase == "none":
        lines += [
            "* **No release bodies were pulled in this run** (`--index-only`). The counts "
            "below are the index's own and are final; the text column reads 0 because "
            "nothing was read, not because nothing is there.",
            "",
        ]
    elif text_failures:
        lines += [
            f"* Release bodies were pulled for every release counted below; "
            f"**{text_failures} could not be read** and are listed in "
            f"`data/raw/press/index.json` under `text_failures`. A release with no "
            f"readable body is recorded as a failure, never as a statement with no words.",
            "",
        ]
    else:
        lines += ["* Release bodies were pulled for every release counted below.", ""]

    lines += [
        "## Per member",
        "",
        "| Member | Party | Releases | Text | Pages | Walk |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in sorted(results, key=lambda r: r.member_id):
        row = by_id[result.member_id]
        walk = "complete" if result.complete else f"**INCOMPLETE — {result.stopped}**"
        lines.append(
            f"| {row['name']} ({result.member_id}) | {row['party']} | "
            f"{len(result.releases)} | {text_counts.get(result.member_id, 0)} | "
            f"{result.pages_read} | {walk} |"
        )

    totals: dict[str, int] = {}
    for result in results:
        totals[by_id[result.member_id]["party"]] = totals.get(
            by_id[result.member_id]["party"], 0
        ) + len(result.releases)
    lines += [
        "",
        "## Per party",
        "",
        "| Party | Releases |",
        "| --- | --- |",
        *(f"| {party} | {count} |" for party, count in sorted(totals.items())),
        "",
    ]

    incomplete = [r for r in results if not r.complete]
    lines += ["## Walks that did not reach the window's start", ""]
    if incomplete:
        lines.append(
            "These members' counts are a floor, not a total. `window` (the walk reached "
            "2023) and `exhausted` (the pager ran off the end of an archive that begins "
            "inside the window) both mean COMPLETE and are not listed here. Everything "
            "below stopped early, so the member is under-collected."
        )
        lines.append("")
        for result in sorted(incomplete, key=lambda r: r.member_id):
            lines.append(
                f"* `{result.member_id}` {by_id[result.member_id]['name']} — "
                f"**{result.stopped}**: {result.detail}"
            )
    else:
        lines.append("None: every walk reached the window's start.")

    lines += ["", "## Refused, by id", ""]
    if refused:
        lines.append(
            "The source list's own rule: collector (a) must refuse a row that still says "
            "`owner_checked: false` (fact 7, STATUS.md). These are listed so a refusal is "
            "never mistaken for a member who published nothing."
        )
        lines.append("")
        for entry in refused:
            lines.append(f"* `{entry['id']}` {entry['name']} — {entry['reason']}")
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


# --- the run --------------------------------------------------------------------------


def _read_page(url: str) -> str:
    return cache.fetch(
        CACHE_SOURCE, url, ext="html", ttl_hours=CACHE_TTL_HOURS, accept_status=(200, 301, 302)
    ).text


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ingest statements-press",
        description="P3 task 2a — member press releases for the pilot 40. No AI.",
    )
    parser.add_argument("--index-only", action="store_true", help="no release bodies")
    parser.add_argument(
        "--limit-pages", type=int, default=0, help="list pages per member (0 = the window)"
    )
    parser.add_argument("--members", default="", help="comma-separated bioguide ids")
    args = parser.parse_args(argv)

    root = repo_root()
    data_dir = root / "data"
    accepted, refused = sources(data_dir)

    if args.members:
        wanted = {m.strip() for m in args.members.split(",") if m.strip()}
        refused_ids = {entry["id"] for entry in refused}
        asked_for_refused = sorted(wanted & refused_ids)
        if asked_for_refused:
            # The source list's rule is not a default that a flag may override.
            print(f"refusing {', '.join(asked_for_refused)}: owner_checked is not true")
        accepted = [row for row in accepted if row["id"] in wanted]

    window = {"start": WINDOW_START, "end": window_end()}
    print(f"collector (a): {len(accepted)} accepted rows, {len(refused)} refused")

    results: list[MemberResult] = []
    for n, row in enumerate(accepted, start=1):
        result = walk_member(row, read_page=_read_page, limit_pages=args.limit_pages)
        results.append(result)
        flag = "" if result.complete else f"  <-- {result.stopped}: {result.detail}"
        print(
            f"  [{n}/{len(accepted)}] {result.member_id} {len(result.releases):4} releases "
            f"over {result.pages_read} pages{flag}"
        )

    out_dir = data_dir.joinpath(*RAW_SUBDIR)
    statements_dir = out_dir / "statements"
    statements_dir.mkdir(parents=True, exist_ok=True)

    text_counts: dict[str, int] = {}
    text_failures: list[dict[str, str]] = []
    by_id = {row["id"]: row for row in accepted}
    for result in results:
        records: list[dict[str, Any]] = []
        for release in sorted(result.releases, key=lambda r: (r.date, r.url), reverse=True):
            text = ""
            if not args.index_only:
                try:
                    text = release_text(_read_page(release.url))
                except (RetryableHTTPError, httpx.HTTPError, OSError) as exc:
                    text_failures.append(
                        {"id": result.member_id, "url": release.url, "error": type(exc).__name__}
                    )
                if not text:
                    text_failures.append(
                        {"id": result.member_id, "url": release.url, "error": "no body text"}
                    )
            records.append(statement_record(release, text))
        text_counts[result.member_id] = sum(1 for r in records if r["segments"])
        row = by_id[result.member_id]
        atomic_write_text(
            statements_dir / f"{result.member_id}.json",
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "member": {
                        "id": row["id"],
                        "name": row["name"],
                        "party": row["party"],
                        "chamber": row["chamber"],
                        "state": row["state"],
                    },
                    "window": window,
                    "statements": records,
                },
                indent=2,
            ),
        )

    atomic_write_text(
        out_dir / "index.json",
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "window": window,
                "accepted": len(accepted),
                "refused": refused,
                "releases": [asdict(r) for result in results for r in result.releases],
                "walks": [
                    {
                        "member_id": r.member_id,
                        "releases": len(r.releases),
                        "pages_read": r.pages_read,
                        "stopped": r.stopped,
                        "detail": r.detail,
                    }
                    for r in results
                ],
                "text_failures": text_failures,
            },
            indent=2,
        ),
    )

    report_dir = root / "docs" / "research"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / f"{window['end']}-press-collection-counts.md"
    atomic_write_text(
        report,
        render_report(
            results,
            accepted,
            refused,
            text_counts,
            window=window,
            text_phase="none" if args.index_only else "full",
            text_failures=len(text_failures),
        ),
    )
    print(f"  index:  {(out_dir / 'index.json').relative_to(root)}")
    print(f"  report: {report.relative_to(root)}")
    if text_failures:
        print(f"  text failures: {len(text_failures)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
