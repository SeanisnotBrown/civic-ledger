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

A THIRD outcome, and it is not a refusal: `no_press_source` on a row is the owner's own
finding that the member's site publishes no press-release list AT ALL — `M001222` Miller,
whose `/press-releases` serves the home page and whose `/media/press-releases`, `/news`
and `/media` all 404. Those rows report as "no list exists", with the owner's reason and
every URL tried, and are never printed as empty, never as failed, and never counted as a
collection failure — not here and not in the count-before-spend report's coverage table.
See `sources`, which tests that flag before it tests `owner_checked`.

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

Four things wear that shape and are still not a member's statement — the list page
itself, an href still carrying an unrendered `${...}` template, a video page, and a
newsletter signup — and each is refused WITH ITS REASON, printed in the report by row and
URL. See `release_url_rejection`: a URL this collector takes out of a member's statement
list is never taken out silently.

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

Page two onwards is the page the SITE links to — its own `rel="next"`, its own "Next",
or its own numbered link (`next_page_url`). A URL guessed from the list URL (`page_url`)
is the fallback for a list that publishes no link at all, and the report names every row
still resting on it: measured 2026-10-14, the guess is wrong on three of the four rows it
was checked against, and a wrong pager URL does not fail loudly — it re-serves page one.

One row has no pager to follow at all. `K000377`'s list paginates through a JavaScript
filter widget that renders no control, so the owner ratified a different source for him
on 2026-10-15: the press-release SITEMAP his own site publishes (`press_sitemap` in the
source list). `walk_sitemap` reads it for URLs only — `<lastmod>` is when a page was last
edited, never when it was published, so it is used once as a skip filter and never
stored — and every date comes from the release page's own publication marker, exactly as
it does for the rows whose lists print no dates.

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
import calendar
import html as html_lib
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
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

# One tag's attributes, keyed by lowercased name. Every attribute this module reads is
# read through here rather than pattern-matched in place, because attribute ORDER varies
# between pages of the same CMS — see `release_page_date`'s `<meta>` markers, where the
# same publisher prints `name` before `content` on one page and after it on the next.
_TAG_ATTR = re.compile(r'([\w:.-]+)\s*=\s*"([^"]*)"')


def _attrs(tag: str) -> dict[str, str]:
    return {key.lower(): value for key, value in _TAG_ATTR.findall(tag)}


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
    # "day", or "month" for a date the publisher printed as a month only — `/2026/9/`.
    # Owner decision 5: month-only precision is stored verbatim, never padded to the 1st,
    # and is never matched against a single day's vote.
    date_precision: str = "day"
    # Where the date came from: the list page's own text, the permalink, or the release
    # page itself. Recorded because a conflict between two of them is reported by source.
    date_source: str = "list-page"
    # Set when two of the publisher's own dates disagree. Never resolved by guesswork —
    # the date stays as it was and the conflict is printed in the report, because a
    # disagreement can mean the WRONG PAGE was attached to this title.
    date_conflict: str = ""


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

# The date a dated permalink carries. On the rows measured 2026-10-14 it is the ONLY date
# on the page: `S001185` Sewell, `R000622` Riley, `W000830` Whitesides and `L000585`
# LaHood print nothing but the URL.
_PERMALINK_DATE = re.compile(r"/(20\d\d)/(\d{1,2})(?:/(\d{1,2}))?(?:/|$)")


def _real_date(year: int, month: int, day: int) -> str | None:
    """The date as ISO, or None when no such day exists. February 30th and April 31st are
    not dates, and a publisher that prints one has not told us when it published."""
    if not 1 <= month <= 12:
        return None
    if not 1 <= day <= calendar.monthrange(year, month)[1]:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def permalink_date(url: str) -> tuple[str, str] | None:
    """The publisher's own date out of the URL path, with its precision, or None.

    Owner decision 5, 2026-10-14: a permalink date counts as the release's date. Two
    shapes, and the second is why precision is carried at all:

      * `/2026/06/10/slug` — a day, stored as `2026-06-10`;
      * `/2026/9/slug` — a MONTH, stored as `2026-09` and NEVER padded to the 1st.
        Padding would put a day on the record the publisher never printed, and a day is
        what a statement is matched against a vote by.

    A month outside 1-12, or a day that does not exist in that month, is REFUSED rather
    than repaired: `/2026/13/` and `/2026/02/30/` are not dates, and guessing which half
    the publisher fumbled would invent one. There is no fallback guess — the release is
    left undated and skipped.
    """
    match = _PERMALINK_DATE.search(urlparse(url).path)
    if match is None:
        return None
    year, month, day = int(match.group(1)), int(match.group(2)), match.group(3)
    if not 1 <= month <= 12:
        return None
    if day is None:
        return f"{year:04d}-{month:02d}", "month"
    real = _real_date(year, month, int(day))
    return (real, "day") if real is not None else None


def _same_date(left: str, right: str) -> bool:
    """Whether two of the publisher's own dates agree, at the precision they share. A
    month-only `2026-10` agrees with `2026-10-07`: the month is all the publisher
    committed to, so a day inside it is not a contradiction."""
    width = min(len(left), len(right))
    return left[:width] == right[:width]


def date_upper_bound(date: str) -> str:
    """The LAST day a stored date could mean: a day-precision date is itself, and a
    month-only `2023-01` is `2023-01-31`.

    BOTH window comparisons go through this. Compared as the bare string it stores,
    month-only `2023-01` sorts BEFORE the window start `2023-01-03` — so a release the
    publisher dated inside the window would be dropped as too old, and a whole page of
    them would stop the walk one page early. The upper bound is the only comparison that
    cannot throw away a release that might be in the window.
    """
    if len(date) == 7:
        return f"{date}-{calendar.monthrange(int(date[:4]), int(date[5:7]))[1]:02d}"
    return date


# A pager link is not a release, and it passes every other test below: it is on the host,
# under the list path, and sits next to the dates of the items it pages past.
_PAGER = re.compile(r"/page/\d+/?$|[?&](?:page|Page)=\d+")


def _has_release_shape(candidate: str, list_url: str) -> bool:
    """Whether this href has the SHAPE of a release on this list.

    Four shapes cover all the families measured on the 32 accepted rows:

      * a path UNDER the list page's own path (House Drupal, Senate WordPress);
      * a path elsewhere on the host that carries the list's own distinguishing segment
        — `S001232` lists at `/newsroom/press-releases/` and links to
        `/news/press-releases/<slug>`, which no "under the list path" test can reach;
      * a dated permalink anywhere on the host (`L000583`, `H001081`);
      * the ASPX CMS's `documentsingle.aspx?DocumentID=`.

    Anything off-host is never a release: a member's press page links to news coverage,
    and a newspaper's article is not the member's own statement.

    Shape alone is not enough — see `release_url_rejection` for the four things that wear
    this shape and are still not a release. The split is so that a URL refused on content
    can be reported WITH ITS REASON, while a URL that never looked like a release is not
    reported at all: a page carries dozens of those, and a report nobody can read is a
    report nobody reads.
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
        # `/press-releases?ID=9146BD9B-...`. The list's own path IS release-shaped here;
        # which of these is the list page itself is `release_url_rejection`'s to say, so
        # that refusing it leaves a line in the report rather than nothing.
        return True
    if "documentsingle.aspx" in path.lower() or _DATED_PERMALINK.search(path):
        return True
    if base and path.startswith(base):
        return True
    # The list's own last segment, e.g. "press-releases", seen anywhere deeper on the
    # host. Requires a slug after it so the section index itself is not a release.
    segment = base.rsplit("/", 1)[-1]
    return bool(segment) and re.search(rf"/{re.escape(segment)}/[^/]", path) is not None


# Whole path SEGMENTS that are never a press release. Matched as segments and never as
# substrings, which is the difference between refusing `/news/multimedia/watch/<clip>`
# and refusing `senator-calls-for-watchdog` — a real release whose slug happens to carry
# the letters of a rule.
_NEVER_A_RELEASE_SEGMENT = frozenset({"multimedia", "watch", "video", "videos"})
_SUBSCRIBE = "subscribe"
# The ASPX CMS's own query endpoint. `documentquery.aspx?DocumentTypeID=…` is a list of
# documents of one type and `?IssueID=…` is a list by topic; a single release on that CMS
# is always `documentsingle.aspx?DocumentID=…`. Owner ruling, 2026-10-15.
_ASPX_LIST = "documentquery.aspx"
# A `${...}` left in an href is a JavaScript template whose loop never ran: markup the
# renderer handed back as-is, not a page that exists.
_TEMPLATE_LITERAL = "$" + "{"


def release_url_rejection(candidate: str, list_url: str) -> str | None:
    """Why a release-SHAPED href is not a release after all, or None when nothing is.

    Four refusals, each one measured 2026-10-15 against the cached rendered pages, where
    each was being collected as a member's own words before this existed:

      * **the list page itself** — "View All Press Releases" points back at the list, and
        the list is not one of its own items. A link on the list's own path carrying a
        DIFFERENT query is still a release: `H001081` keys every release that way.
      * **an unrendered template literal** — `K000377` Kelly's rendered page carries
        `.../press-releases/${item.link}` under the title "Continue Reading on Medium".
        That is a template, not a URL, and fetching it would fetch nothing.
      * **a `multimedia`, `watch`, `video` or `videos` segment** — `S001181` Shaheen
        lists three `/news/multimedia/watch/<clip>` video pages among her ten "release"
        links. A clip is not the member's words on the record, and its page carries no
        release text to read.
      * **a `subscribe` segment** — `R000622` Riley opens every page of his news list
        with "Subscribe to the Riley Report" → `/news/newsletter-subscribe/`. A signup
        form is not a statement.
      * **a `documentquery.aspx` link** (owner ruling, 2026-10-15) — on the ASPX family
        the list page's own path IS `documentquery.aspx`, so the "a different query means
        a release" rule below, written for `H001081`, read every other list on the page
        as a release: `C001066` collected "Speeches and Floor Statements"
        (`?DocumentTypeID=817`) and "Protecting Consumers" (`?IssueID=111866`) as two of
        her twelve, each wearing a neighbouring release's date. That is the worst shape
        of leak — it does not fail visibly, it becomes a statement. A single release on
        that CMS is `documentsingle.aspx`, which is untouched.

    A REASON rather than a bare `False`, because a URL dropped silently is
    indistinguishable from a URL nobody looked at. Every one of these is printed in the
    count report, by row and URL.
    """
    if _TEMPLATE_LITERAL in candidate:
        return "an unrendered template literal (`${`) — markup, not a page"
    here, there = urlparse(list_url), urlparse(candidate)
    if there.netloc != here.netloc:
        # Off-host was never a candidate (see `_has_release_shape`), so it is not a
        # refusal to report either: a press page links to news coverage, and that is
        # ordinary, not a leak.
        return None
    path = there.path.rstrip("/")
    if path == here.path.rstrip("/") and (not there.query or there.query == here.query):
        # The bare list URL, the list URL complete with its own query, and — for the ASPX
        # family, whose list URL carries `?DocumentTypeID=` — the query-less list path.
        return "the list page itself"
    if _ASPX_LIST in path.lower():
        # Any OTHER query on that endpoint: a different document type, or an issue
        # category. Both are lists of releases, not releases.
        return (
            "a `documentquery.aspx` link — the ASPX CMS's own LIST endpoint, not a "
            "release (a single release there is `documentsingle.aspx`)"
        )
    segments = [segment.lower() for segment in path.split("/") if segment]
    named = next((s for s in segments if s in _NEVER_A_RELEASE_SEGMENT), None)
    if named is not None:
        return f"a `{named}` path segment — a video page, not a release"
    subscribing = next((s for s in segments if _SUBSCRIBE in s), None)
    if subscribing is not None:
        return f"a `{subscribing}` path segment — a subscribe form, not a release"
    return None


def _is_release_url(candidate: str, list_url: str) -> bool:
    """Whether this href is a release rather than navigation: release-shaped, and not
    refused by the filter. The bare verdict, for callers that do not report a reason."""
    return (
        _has_release_shape(candidate, list_url)
        and release_url_rejection(candidate, list_url) is None
    )


def extract_candidates(
    html: str,
    list_url: str,
    member_id: str,
    *,
    rejections: list[dict[str, str]] | None = None,
) -> list[Release]:
    """Every release-shaped anchor one list page announces, dated where the LIST page can
    date it, in page order and deduplicated.

    A date printed near the anchor wins. Failing that the publisher's own permalink date
    is read (owner decision 5), carrying its precision. An anchor with NEITHER comes back
    carrying `date=""` and `date_precision="none"`: it is not a release yet, because an
    undated row cannot be placed inside or outside the collection window. Dating it needs
    its own release page, which is a fetch — see `date_from_release_page`, and
    `extract_releases` for every caller that cannot spend one.

    `rejections`, when given, is appended to with every release-SHAPED anchor the filter
    refused and the reason it was refused (`release_url_rejection`). The walk always
    passes one, so a URL the collector dropped is never dropped silently: it is in the
    index and in the report, with its reason, where the owner can see what was taken out
    of a member's statement list and disagree.
    """
    flat = flatten(html)
    out: list[Release] = []
    seen: set[str] = set()
    for match in _ANCHOR.finditer(flat):
        title = html_lib.unescape(_TAGS.sub("", match.group(2))).strip()
        if len(title) < MIN_TITLE_CHARS:
            continue
        url = urljoin(list_url, html_lib.unescape(match.group(1)))
        if url in seen or not _has_release_shape(url, list_url):
            continue
        refused = release_url_rejection(url, list_url)
        if refused is not None:
            # Recorded, not merely skipped — and added to `seen` so the same refusal is
            # printed once however many times the page links it (Riley lists his
            # newsletter signup twice at the top of every page).
            seen.add(url)
            if rejections is not None:
                rejections.append({"id": member_id, "url": url, "reason": refused})
            continue
        date = nearest_date(flat, match.start(), match.end())
        precision, source, conflict = "day", "list-page", ""
        from_url = permalink_date(url)
        if date is None:
            if from_url is None:
                # Undated by the list page. Kept as a candidate rather than dropped, so
                # a caller holding a release-page reader can date it instead of guessing.
                date, precision, source = "", "none", "none"
            else:
                date, precision, source = *from_url, "permalink"
        elif from_url is not None and not _same_date(date, from_url[0]):
            # Both of the publisher's own dates, disagreeing. The list page's text still
            # wins — it is the date printed beside the title the reader clicks — and the
            # disagreement is reported rather than resolved by guesswork.
            conflict = (
                f"the list page says {date}, the permalink says {from_url[0]}"
            )
        seen.add(url)
        # A title whose anchor swallowed the date reads "September 29, 2026 Sheehy's
        # Protect America Act ..."; the date is already a field of its own.
        out.append(
            Release(
                member_id=member_id,
                date=date,
                title=_LEADING_DATE.sub("", title).strip() or title,
                url=url,
                date_precision=precision,
                date_source=source,
                date_conflict=conflict,
            )
        )
    return out


def extract_releases(html: str, list_url: str, member_id: str) -> list[Release]:
    """Every DATED release one list page announces — `extract_candidates` without the
    anchors the list page could not date. A statement whose date is a guess cannot be
    compared against a vote, so an undated row is left out rather than dated by
    guesswork."""
    return [c for c in extract_candidates(html, list_url, member_id) if c.date]


def date_from_release_page(
    candidate: Release, read_release_page: Callable[[str], str]
) -> tuple[Release, dict[str, str] | None]:
    """One undated candidate, dated from its OWN release page (owner decision 5).

    Returns the candidate and a failure record, exactly one of which carries the news. A
    page that cannot be FETCHED, and a page fetched fine that publishes no date MARKER,
    are different failures and say so: the first is ours to retry and the second is the
    publisher's. Neither is ever kept as a release — an undated statement cannot be placed
    in the window, and `release_page_date` never guesses from the body.

    This is the one step of the collection that costs a fetch the list page did not
    already pay for, which is why the count is reported per row.
    """
    try:
        html = read_release_page(candidate.url)
    except (RetryableHTTPError, httpx.HTTPError, OSError) as exc:
        return candidate, {
            "id": candidate.member_id,
            "url": candidate.url,
            "error": type(exc).__name__,
        }
    found = release_page_date(html)
    if found is None:
        return candidate, {
            "id": candidate.member_id,
            "url": candidate.url,
            "error": "no date on release page",
        }
    return (
        replace(candidate, date=found, date_precision="day", date_source="release-page"),
        None,
    )


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
    """The `page`-th list page GUESSED from the list URL, counting from 0 for the first
    one, in whichever scheme this family uses. The fallback for a list that publishes no
    pager link of its own — `next_page_url` is tried first and wins.

    The SCHEME comes from the list URL, so a redesigned pager cannot silently restart the
    walk at page 1. The `?page=` OFFSET comes from the first page's own links, because
    the two Drupal-shaped families disagree about it — see `zero_based_pager`.

    Measured 2026-10-14, this guess is WRONG on three of the four rows it was checked
    against: `H001046` and `R000605` page by `?pagenum_rs=`, `R000622` by
    `/page/2/?et_blog`, and only `S001185`'s `?page=2` matches. That is what
    `next_page_url` exists for; this stays for the rows that print no link at all.
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


# A tag that can carry `rel="next"`: the `<a>` the reader clicks, and the `<link>` in the
# head that WordPress writes for the same page (`H000601` Hagerty publishes both).
_REL_TAG = re.compile(r"<(?:a|link)\b[^>]*>", re.IGNORECASE)
# An anchor's text reduced to its letters, so "Next >", "Next »" and "Next page››" are
# one word and "Last »" is a different one. Deliberately only these two words: "older"
# and the bare arrows are not on any row measured, and `page_url` already covers a row
# with no link at all, so a guess here would be a guess with nothing behind it.
_LETTERS_ONLY = re.compile(r"[^a-z]+")
_NEXT_WORDS = frozenset({"next", "nextpage"})


def _pager_target(href: str, current_url: str) -> str | None:
    """One pager href as an absolute URL, or None where it cannot be followed: empty,
    off-host, or the page we are already on (which every "next" link on the LAST page of
    an archive is, on the families that keep rendering one)."""
    if not href:
        return None
    url = urljoin(current_url, html_lib.unescape(href))
    if urlparse(url).netloc != urlparse(current_url).netloc:
        return None
    return None if url.rstrip("/") == current_url.rstrip("/") else url


def next_page_url(html: str, current_url: str, page_number: int) -> str | None:
    """The site's OWN link to its next list page, or None if it publishes none.

    `page_number` is the human number of the page being asked for — 2 while reading page
    one. Three rules, in this order, every one of them measured on a real row 2026-10-15:

      * `rel="next"`, on an `<a>` or the head's `<link>`: `B001257` and the 21 other
        House Drupal rows (`<a href="?page=1" rel="next">`), `H000601`, `L000583`,
        `R000622` and `W000830` (`/page/2/?et_blog`);
      * an anchor whose text is NEXT: `C001066` and the 4 other ASPX rows ("Next »" →
        `&Page=2`), `H001046` and `R000605` ("Next" → `?pagenum_rs=2`), `L000585` and
        `S001185` ("Next >" → `?page=2`). Reduced to its letters, so "Last »" is not it;
      * an anchor whose text is the next page's NUMBER: `H001081` prints `1`…`55` and no
        `rel="next"`.

    Why it is the site's link and not a guess: `page_url`'s guess is wrong on three of
    the four rows it was measured against, and a wrong pager URL does not fail loudly —
    it re-serves page one, which the duplicate rule reads as the end of the archive. That
    is how `H001081` came back collected 10 releases deep instead of 251.

    The number rule is also why the site's own link beats a guess on the 0-vs-1-based
    question entirely: Drupal's "2" points at `?page=1` and Hayes's "2" at `?page=2`, and
    each is right about its own site.
    """
    flat = flatten(html)
    for tag in _REL_TAG.findall(flat):
        attrs = _attrs(tag)
        if "next" not in attrs.get("rel", "").lower().split():
            continue
        found = _pager_target(attrs.get("href", ""), current_url)
        if found is not None:
            return found
    numbered: str | None = None
    for match in _ANCHOR.finditer(flat):
        text = html_lib.unescape(_TAGS.sub("", match.group(2))).strip()
        if _LETTERS_ONLY.sub("", text.lower()) in _NEXT_WORDS:
            found = _pager_target(match.group(1), current_url)
            if found is not None:
                return found
        if numbered is None and text == str(page_number):
            # Held rather than returned: a numbered pager usually prints "1 2 3 … Next >"
            # so the numbers come first, and a word the site chose to call "next" is the
            # better evidence of what it considers next.
            numbered = _pager_target(match.group(1), current_url)
    return numbered


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


# The markers a release page publishes its OWN date in, measured 2026-10-15 on one real
# release from each row that reaches a release page: `<meta property=
# "article:published_time">` and `<meta name="date">` (`L000585`, `S001185`, `R000605`,
# `S001181`), JSON-LD `"datePublished"` (`K000377`), and `<time datetime="...">` whose
# attribute holds the LONG form rather than ISO (`R000605`, `S001181`). Attribute order
# varies between the same CMS's own pages, so the tag is parsed rather than pattern-matched
# whole. `dateModified` is deliberately not read: it is when the office last edited the
# page, not when the member said this.
_META_TAG = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_JSON_LD_PUBLISHED = re.compile(r'"datePublished"\s*:\s*"([^"]{4,40})"')
_TIME_TAG = re.compile(r"<time\b([^>]*)>(.*?)</time>", re.IGNORECASE | re.DOTALL)


# A marker's own ISO date. `_DATE_ISO` cannot be reused here: it ends in a word boundary,
# and a timestamp like `2026-10-07T04:00:00Z` puts a word character straight after the
# day, so the boundary fails and the date is silently missed. Measured 2026-10-15, three
# of the five marker families publish exactly that shape.
_MARKER_ISO = re.compile(r"(20[0-9][0-9])-([0-9]{1,2})-([0-9]{1,2})")


def _marker_date(value: str) -> str | None:
    """A date out of one marker's value, validated as a real calendar date."""
    iso = _MARKER_ISO.search(value)
    if iso is not None:
        return _real_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    found = _first_date(value)
    if found is None:
        return None
    year, month, day = found[1].split("-")
    return _real_date(int(year), int(month), int(day))


def release_page_date(html: str) -> str | None:
    """The date the RELEASE page itself publishes, or None.

    Only the publisher's own machine-readable markers count, in a fixed order, first hit
    wins. There is deliberately NO fallback to the body text: the first date a release
    happens to mention is usually the date of the thing it is about — a hearing, a
    deadline, a bill's passage — and attaching that to the member's words would be a
    guess dressed as a source. `R000622` Riley publishes no marker at all, so Riley keeps
    the date in its permalink; STATUS fact 7's "every release page carries a date" is
    wrong for that row.
    """
    flat = flatten(html)
    metas = [_attrs(tag) for tag in _META_TAG.findall(flat)]
    for key in ("article:published_time", "date"):
        for attrs in metas:
            if key not in {attrs.get("property", "").lower(), attrs.get("name", "").lower()}:
                continue
            found = _marker_date(attrs.get("content", ""))
            if found is not None:
                return found
    ld = _JSON_LD_PUBLISHED.search(flat)
    if ld is not None:
        found = _marker_date(ld.group(1))
        if found is not None:
            return found
    for attr_text, inner in _TIME_TAG.findall(flat):
        found = _marker_date(_attrs(attr_text).get("datetime", "")) or _marker_date(
            html_lib.unescape(_TAGS.sub(" ", inner))
        )
        if found is not None:
            return found
    return None


_H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_TITLE_TAG = re.compile(r"<title\b[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def release_page_title(html: str) -> str:
    """The title a release page gives itself, or "".

    `<h1>` first, measured 2026-10-15 on `K000377`'s own release pages: it carries the
    headline alone, while `og:title` and `<title>` both carry it with " - Senator Mark
    Kelly" glued on the end, and stripping a site's name off its own title is a guess
    that would have to be made per site. The two suffixed markers are still read after
    it, because a headline with a suffix beats no headline at all.

    Needed only by the sitemap path: a sitemap gives a URL and no title, while a list
    page gives the title in the anchor the reader clicks.
    """
    flat = flatten(html)
    heading = _H1.search(flat)
    if heading is not None:
        text = html_lib.unescape(_TAGS.sub(" ", heading.group(1))).strip()
        if text:
            return re.sub(r"\s+", " ", text)
    for tag in _META_TAG.findall(flat):
        attrs = _attrs(tag)
        if attrs.get("property", "").lower() == "og:title" and attrs.get("content", "").strip():
            return attrs["content"].strip()
    title = _TITLE_TAG.search(flat)
    if title is not None:
        text = html_lib.unescape(_TAGS.sub(" ", title.group(1))).strip()
        if text:
            return re.sub(r"\s+", " ", text)
    return ""


def reconcile_date(release: Release, page_date: str | None) -> Release:
    """The release page's own date against the date the list page gave (decision 5).

    Where they AGREE the page date wins, which is what upgrades a month-only permalink
    date to the day the publisher actually printed. Where they DISAGREE the stored date
    is left exactly as it was and the disagreement is recorded on the record: a page date
    outside the permalink's month, or a different day where the URL carried one, can mean
    the WRONG PAGE was attached to this title, and in that case its date is not evidence
    of anything. Owner rule: flag every conflict, resolve none by guesswork.
    """
    if page_date is None or page_date == release.date:
        return release
    if not _same_date(release.date, page_date):
        return replace(
            release,
            date_conflict=(
                f"the release page says {page_date}, the {release.date_source} says "
                f"{release.date}"
            ),
        )
    # They agree at the precision they share and are not the same string, which can only
    # mean the stored date is month-only and the release page supplied the day inside it.
    return replace(release, date=page_date, date_precision="day", date_source="release-page")


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
        # Explicit rather than inferred from `len(date)`: owner decision 5 is that a
        # month-only date is never matched against a single day's vote, and a Phase 6
        # rule that depends on counting characters is a rule that gets missed. CREC
        # records do not carry this field at all and are always day-precision.
        "date_precision": release.date_precision,
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
    stopped: str  # window|exhausted|sitemap|single-page|empty|undated|repeat|error|limit
    detail: str = ""
    # Releases whose own page could not date them, with the reason, and the count of
    # release-page fetches the dating cost. Both empty when no reader was given.
    date_failures: list[dict[str, str]] = field(default_factory=list)
    release_page_fetches: int = 0
    # Every release-shaped URL the filter refused, with the reason, once per URL however
    # many pages link it. Reported rather than dropped: the owner is the one who decides
    # what counts as a member's own statement, so a URL this code takes out of a member's
    # list has to be visible to be disagreed with.
    url_rejections: list[dict[str, str]] = field(default_factory=list)
    # How page 2 was reached: `link` — the site's own Next or numbered link; `page_url` —
    # guessed from the list URL because the site published no such link; `none` — page 2
    # was never asked for, because the walk ended on page one; `sitemap` — there were no
    # list pages at all, the URLs came from the site's own sitemap. Recorded per row
    # because the guess is wrong on three of the four rows it was measured against, and
    # the report has to say which rows are still resting on it.
    page2_method: str = "none"
    page2_url: str = ""

    @property
    def complete(self) -> bool:
        """Whether every release in the window was collected.

        Three stops mean complete, for different reasons: `window` — the walk reached a
        page older than 2023-01-03, so everything in the window is behind us;
        `exhausted` — the pager ran off the end of the archive, which is what happens to
        a member whose press archive BEGINS inside the window; and `sitemap` — every URL
        in the member's own press-release sitemap was considered, which is the strongest
        enumeration available, since it is the publisher's own index of the archive
        rather than a walk of what their pager chose to show. Calling any of those
        incomplete would print INCOMPLETE beside a member who was collected in full, in
        the one report decision 4 exists to make trustworthy.

        Everything else (`single-page`, `empty`, `undated`, `repeat`, `error`, `limit`)
        stopped the
        walk before its natural end, or could not tell whether it had, and those counts
        are a floor rather than a total.
        """
        return self.stopped in ("window", "exhausted", "sitemap")


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
    read_release_page: Callable[[str], str] | None = None,
    window_start: str = WINDOW_START,
    limit_pages: int = 0,
) -> MemberResult:
    """One member's press list, page by page, until the window's start.

    Stops at the first page whose NEWEST item predates the window (reverse-chronological
    lists, so everything deeper is older), at a page the extractor reads nothing from,
    or at `limit_pages`. The stop reason travels with the result because "complete" and
    "we gave up" must never read the same in the report.

    Page two onwards is the page the SITE links to (`next_page_url`), and `page_url`'s
    guess is used only where the site publishes no such link. Once a site has shown its
    own pager, a page that carries no next link is the end of its archive and the walk
    stops there rather than guessing past it: asking for a page the site says does not
    exist is how a Drupal pager that clamps to its last page comes back as a page already
    read, which the duplicate rule reports as `repeat` — INCOMPLETE printed beside a
    member who was collected in full.

    `read_release_page`, when given, dates the anchors the list page left undated by
    reading their own release pages — the three rows (`K000377`, `R000605`, `S001181`)
    whose lists print no date at all. It is OPTIONAL because it costs one fetch per
    undated anchor, and a caller that cannot spend those (the screening report, and
    `--index-only`) must still get today's answer rather than a slower one.
    """
    member_id = row["id"]
    list_url = row["press_page"]
    ceiling = min(limit_pages, MAX_PAGES) if limit_pages else MAX_PAGES
    found: list[Release] = []
    seen: set[str] = set()
    undatable: set[str] = set()
    failures: list[dict[str, str]] = []
    refusals: list[dict[str, str]] = []
    refused_urls: set[str] = set()
    fetches = 0
    pages = 0
    page2 = ["none", ""]

    def finish(result: MemberResult) -> MemberResult:
        """Every exit carries what the dating cost and what it could not do."""
        result.date_failures = failures
        result.release_page_fetches = fetches
        result.url_rejections = refusals
        result.page2_method, result.page2_url = page2
        return result

    zero_based = True
    linked: str | None = None
    site_pages_itself = False
    for page in range(ceiling):
        if page == 0:
            url = list_url
        else:
            url = linked or page_url(list_url, page, zero_based=zero_based)
            if page == 1:
                page2 = ["link" if linked else "page_url", url]
        try:
            html = read_page(url)
        except httpx.HTTPStatusError as exc:
            if page > 0 and exc.response.status_code == 404:
                # A pager URL that 404s is how most of these sites say "there is no page
                # N" — the end of the archive, not a failed fetch, and reporting it as an
                # error would print INCOMPLETE beside a member collected in full.
                return finish(
                    MemberResult(member_id, found, pages, *_end_of_archive(page))
                )
            return finish(
                MemberResult(member_id, found, pages, "error", f"HTTP {exc} on {url}")
            )
        except (RetryableHTTPError, httpx.HTTPError, OSError) as exc:
            return finish(
                MemberResult(
                    member_id, found, pages, "error", f"{type(exc).__name__} on {url}"
                )
            )
        pages += 1
        if page == 0:
            # Asked of the site itself, once, before the second request is built. Only
            # the `page_url` fallback reads it; a site that links its own next page has
            # already answered the 0-vs-1-based question by linking it.
            zero_based = zero_based_pager(html)
        linked = next_page_url(html, url, page + 2)
        site_pages_itself = site_pages_itself or linked is not None
        page_refusals: list[dict[str, str]] = []
        candidates = extract_candidates(
            html, list_url, member_id, rejections=page_refusals
        )
        for refusal in page_refusals:
            # Once per URL per member: a newsletter signup linked at the top of all 55
            # pages of an archive is one refusal to report, not 55.
            if refusal["url"] not in refused_urls:
                refused_urls.add(refusal["url"])
                refusals.append(refusal)
        # What this page would have to beat to be new. Captured BEFORE the dating loop,
        # which adds to `undatable` as it goes.
        known = seen | undatable
        if read_release_page is not None:
            dated: list[Release] = []
            for candidate in candidates:
                if candidate.date or candidate.url in seen or candidate.url in undatable:
                    dated.append(candidate)
                    continue
                fetches += 1
                candidate, failure = date_from_release_page(candidate, read_release_page)
                if failure is not None:
                    undatable.add(candidate.url)
                    failures.append(failure)
                dated.append(candidate)
            candidates = dated
        releases = [c for c in candidates if c.date]
        fresh = [r for r in releases if r.url not in seen]
        if not releases:
            if candidates and all(c.url in known for c in candidates):
                # Every anchor on it was read on an earlier page. Judged on the ANCHORS
                # rather than on the dated releases, because a page whose releases are
                # dated from their own pages has nothing dated on it the second time
                # round — those fetches are deliberately not spent twice — and that must
                # not read as a page with no dates on it.
                return finish(
                    MemberResult(
                        member_id,
                        found,
                        pages,
                        "repeat",
                        f"page {page} repeats a page already read",
                    )
                )
            if candidates and read_release_page is not None:
                # The page HELD releases and not one of them could be dated. Neither stop
                # below fits: both of those describe the member's archive, and this
                # describes our reading of it. Its own incomplete stop, so an
                # under-collected member is never printed as collected in full.
                return finish(
                    MemberResult(
                        member_id,
                        found,
                        pages,
                        "undated",
                        f"page {page}: {len(candidates)} release(s), none of which could "
                        "be dated from their own pages",
                    )
                )
            if page == 0:
                # A 200 with no items at all: the client-side wall of fact 7, on a row
                # the owner marked accepted. Not a member who published nothing.
                return finish(
                    MemberResult(
                        member_id, found, pages, "empty", "no dated releases on the first page"
                    )
                )
            # The pager ran past the end of the archive.
            return finish(MemberResult(member_id, found, pages, *_end_of_archive(page)))
        if not fresh:
            # Items, but every one already seen: the pager ignored its parameter and
            # re-served a page we have. Incomplete, and silently collecting page 1 two
            # hundred times is what this stops.
            return finish(
                MemberResult(
                    member_id,
                    found,
                    pages,
                    "repeat",
                    f"page {page} repeats a page already read",
                )
            )
        for release in fresh:
            seen.add(release.url)
            # By UPPER bound in both places: a month-only `2023-01` is in the window,
            # and a page of month-only dates must not stop the walk early. See
            # `date_upper_bound`.
            if date_upper_bound(release.date) >= window_start:
                found.append(release)
        if max(date_upper_bound(r.date) for r in fresh) < window_start:
            return finish(MemberResult(member_id, found, pages, "window"))
        if site_pages_itself and linked is None:
            # The site has shown us its own pager and this page carries no next link:
            # that is the archive's own end, said in the publisher's words, and the walk
            # does not guess past it. `page_url` here would ask for a page the site says
            # is not there — and a pager that clamps to its last page would answer with a
            # page already read, which `repeat` would print as INCOMPLETE beside a member
            # collected in full. This can only be reached from page 2 onwards (the flag is
            # only set by a page that HAD a link), so it is never the single-page case.
            return finish(MemberResult(member_id, found, pages, *_end_of_archive(pages)))

    return finish(
        MemberResult(member_id, found, pages, "limit", f"stopped at {ceiling} pages")
    )


# --- a press-release sitemap as the URL source (owner ruling, 2026-10-15) -------------

_SITEMAP_ENTRY = re.compile(r"<url\b[^>]*>(.*?)</url>", re.IGNORECASE | re.DOTALL)
_SITEMAP_LOC = re.compile(r"<loc\b[^>]*>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)
_SITEMAP_LASTMOD = re.compile(r"<lastmod\b[^>]*>\s*([^<\s]+)\s*</lastmod>", re.IGNORECASE)

# An entry with no `<lastmod>` must never be dropped by a limit that takes the newest
# first: nothing is known about its age, and "unknown" is not "old".
_NO_LASTMOD_SORTS_FIRST = "9999-99-99"


@dataclass(frozen=True)
class SitemapEntry:
    """One `<url>` from a press-release sitemap.

    `lastmod` is the publisher's LAST-MODIFIED date and is never stored as a statement's
    date: `release_page_date` already refuses `dateModified` from a release page for
    exactly that reason — an edit is not a publication. Its only use here is as a skip
    filter, in the one direction that is safe: a page last EDITED before the window
    opened cannot have been PUBLISHED inside it.
    """

    url: str
    lastmod: str = ""


def sitemap_entries(xml: str) -> list[SitemapEntry]:
    """Every `<url>` in one sitemap, with its `<lastmod>` where it has one. An entry with
    no `<loc>` is not a URL and is skipped."""
    out: list[SitemapEntry] = []
    for block in _SITEMAP_ENTRY.findall(xml):
        loc = _SITEMAP_LOC.search(block)
        if loc is None:
            continue
        lastmod = _SITEMAP_LASTMOD.search(block)
        out.append(
            SitemapEntry(
                html_lib.unescape(loc.group(1)),
                lastmod.group(1)[:10] if lastmod is not None else "",
            )
        )
    return out


def sitemap_release(
    entry: SitemapEntry, member_id: str, read_release_page: Callable[[str], str]
) -> tuple[Release, dict[str, str] | None]:
    """One sitemap URL as a dated release, read from its OWN page.

    The sitemap supplies the URL and nothing else that may be stored. The date comes
    from the page's own publication marker — `release_page_date`, the same ladder the
    list-page rows use — and the title from the page's own heading, both out of the one
    fetch. A page that cannot be fetched and a page with no publication marker are
    different failures and say so; NEITHER is kept, because an undated statement cannot
    be placed inside or outside the window.
    """
    blank = Release(member_id, "", "", entry.url, date_precision="none", date_source="none")
    try:
        html = read_release_page(entry.url)
    except (RetryableHTTPError, httpx.HTTPError, OSError) as exc:
        return blank, {"id": member_id, "url": entry.url, "error": type(exc).__name__}
    date = release_page_date(html)
    if date is None:
        return blank, {"id": member_id, "url": entry.url, "error": "no date on release page"}
    # A slug is the publisher's own words too, and a statement is never dropped for want
    # of a label — but a page that gives a heading gives a better one.
    slug = urlparse(entry.url).path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
    return (
        Release(
            member_id,
            date,
            release_page_title(html) or slug or entry.url,
            entry.url,
            date_precision="day",
            date_source="release-page",
        ),
        None,
    )


def walk_sitemap(
    row: dict[str, Any],
    *,
    read_sitemap: Callable[[str], str],
    read_release_page: Callable[[str], str] | None = None,
    window_start: str = WINDOW_START,
    limit_urls: int = 0,
) -> MemberResult:
    """One member's releases enumerated from the sitemap their own site publishes.

    For `K000377` Kelly, whose list page paginates through a JavaScript filter widget
    that renders no pager at all: his `robots.txt` points at a Yoast sitemap index, and
    two of its files are nothing but press releases — 1,495 URLs, every one with a
    `<lastmod>`. That is the whole archive, from the publisher's own index, where the
    list page could only ever show seven items.

    What this does NOT do is treat the sitemap as a source of dates. `<lastmod>` is used
    once, as a skip filter in the only safe direction — a page last edited before
    2023-01-03 cannot have been published inside the window — and an entry with no
    `<lastmod>` is fetched rather than skipped, because "unknown" is not "old". Every
    date stored comes from the release page's own publication marker.

    The same release-URL filter applies as to a list page's anchors, so a sitemap entry
    that is a video page, a subscribe form or another list is refused with its reason
    rather than collected because a sitemap mentioned it.

    `read_release_page` is optional for the same reason it is in `walk_member`: a caller
    that cannot spend a fetch per release must still get an answer. Here the answer is
    that there is nothing to collect — the sitemap carries no date this collector may
    store — and that is reported rather than guessed around.
    """
    member_id = row["id"]
    list_url = row["press_page"]
    if read_release_page is None:
        return MemberResult(
            member_id,
            [],
            0,
            "undated",
            "a sitemap carries no date that may be stored — `<lastmod>` is when the page "
            "was last edited — so every release needs its own page, and this run cannot "
            "fetch one",
        )

    found: list[Release] = []
    failures: list[dict[str, str]] = []
    refusals: list[dict[str, str]] = []
    seen: set[str] = set()
    entries: list[SitemapEntry] = []
    pages = 0
    skipped = 0

    for sitemap in row.get("press_sitemap") or []:
        try:
            xml = read_sitemap(sitemap)
        except (RetryableHTTPError, httpx.HTTPError, OSError) as exc:
            return MemberResult(
                member_id, found, pages, "error", f"{type(exc).__name__} on {sitemap}"
            )
        pages += 1
        entries.extend(sitemap_entries(xml))

    candidates: list[SitemapEntry] = []
    for entry in entries:
        if entry.url in seen or not _has_release_shape(entry.url, list_url):
            continue
        seen.add(entry.url)
        refused = release_url_rejection(entry.url, list_url)
        if refused is not None:
            refusals.append({"id": member_id, "url": entry.url, "reason": refused})
            continue
        if entry.lastmod and entry.lastmod < window_start:
            # Edited before the window opened, so published before it too.
            skipped += 1
            continue
        candidates.append(entry)

    candidates.sort(key=lambda e: e.lastmod or _NO_LASTMOD_SORTS_FIRST, reverse=True)
    in_window = len(candidates)
    limited = bool(limit_urls) and limit_urls < in_window
    if limited:
        candidates = candidates[:limit_urls]

    for entry in candidates:
        release, failure = sitemap_release(entry, member_id, read_release_page)
        if failure is not None:
            failures.append(failure)
            continue
        if date_upper_bound(release.date) >= window_start:
            found.append(release)
        else:
            # `<lastmod>` said it might be in the window and the page's own publication
            # date says it is not. The page wins — it is the only date here that means
            # "published".
            skipped += 1

    detail = (
        f"{len(entries)} URL(s) in {pages} sitemap(s); {skipped} outside the window; "
        f"{in_window} to read"
    )
    result = MemberResult(
        member_id,
        found,
        pages,
        "limit" if limited else "sitemap",
        f"stopped at {limit_urls} of {detail}" if limited else detail,
    )
    result.date_failures = failures
    result.release_page_fetches = len(candidates)
    result.url_rejections = refusals
    result.page2_method = "sitemap"
    result.page2_url = (row.get("press_sitemap") or [""])[0]
    return result


# --- configuration --------------------------------------------------------------------


def sources(
    data_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, Any]]]:
    """The accepted rows, the refused ones, and the rows with NO PRESS-RELEASE LIST at
    all, from the owner-maintained list.

    Read-only, and neither of the other two groups is filtered away, so the report can
    name them. A row with `owner_checked: true` and no `press_page` is a refusal too —
    accepting it would walk `None`.

    `no_press_source` is the owner's own finding that a member's site publishes no
    press-release list: `M001222` Miller, where `/press-releases` serves the HOME page
    and `/media/press-releases`, `/news` and `/media` all 404. Such a row is a THIRD
    thing, not a quiet member and not a failure of ours, and it is reported as "no list
    exists" with the reason and every URL that was tried.

    Tested FIRST, before `owner_checked`, for two reasons. It is a fact about the site
    rather than a stage of screening, so it does not become untrue when a row is checked;
    and the interim `owner_checked: false` that stood in for this flag while no code read
    it is now gone, so the outcome must not depend on that guard being there.
    """
    path = data_dir / "config" / "statement-sources.yaml"
    if not path.exists():
        raise PressError(f"no source list at {path}")
    rows = yaml.safe_load(path.read_text(encoding="utf-8"))["members"]
    accepted: list[dict[str, Any]] = []
    refused: list[dict[str, str]] = []
    no_list: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: r["id"]):
        if row.get("no_press_source"):
            no_list.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    # The owner's words, printed as the owner wrote them.
                    "reason": row.get("no_press_reason") or "no press-release list",
                    "urls_tried": list(row.get("no_press_urls_tried") or []),
                }
            )
        elif not row.get("owner_checked"):
            refused.append({"id": row["id"], "name": row["name"], "reason": "owner_checked: false"})
        elif not row.get("press_page"):
            refused.append({"id": row["id"], "name": row["name"], "reason": "no press_page"})
        else:
            accepted.append(row)
    return accepted, refused, no_list


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
    date_conflicts: list[dict[str, str]] | None = None,
    no_list: list[dict[str, Any]] | None = None,
) -> str:
    """The count report (decision 4's per-source, per-member half, for this source).

    Every member appears, including one the walk found nothing for, and every refusal
    appears by id: a missing row would read as "collected, published nothing".

    `no_list` is the rows whose site publishes no press-release list at all. They are
    counted separately from the refusals and from the walks, because they are neither:
    nothing was refused and nothing failed, and the one thing the owner ruled out is
    printing them as empty.
    """
    by_id = {row["id"]: row for row in rows}
    lines = [
        "# Collector (a) — member press releases: the count report",
        "",
        f"Window **{window['start']} to {window['end']}** (owner decision 1). "
        f"Source list: `data/config/statement-sources.yaml`, owner-maintained and read "
        f"only. **No AI call, no archive capture, no spend.**",
        "",
        f"**{len(results)} rows collected, {len(refused)} refused, "
        f"{len(no_list or [])} with no press-release list at all.** "
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

    if results:
        lines += [
            "",
            "## How page 2 was found, per row",
            "",
            "`link` is the site's own Next or numbered link, which is what the walk "
            "follows. `page_url` is the URL GUESSED from the list URL, used only where "
            "the site publishes no such link — measured 2026-10-14, that guess is wrong "
            "on three of the four rows it was checked against, so a row sitting on it is "
            "a row whose deeper pages are not proven. `none` means page 2 was never "
            "asked for: the walk ended on page one.",
            "",
            "| Member | Page 2 found by | Page 2 URL |",
            "| --- | --- | --- |",
        ]
        for result in sorted(results, key=lambda r: r.member_id):
            lines.append(
                f"| {by_id[result.member_id]['name']} ({result.member_id}) | "
                f"`{result.page2_method}` | "
                f"{f'<{result.page2_url}>' if result.page2_url else '—'} |"
            )

    costly = [r for r in results if r.release_page_fetches]
    if costly:
        lines += [
            "",
            "## Release pages read for their dates",
            "",
            "These rows print no date on the list page at all, so each release's own page "
            "was read to date it — the one fetch the list page does not already pay for. "
            "A page that could not be fetched, and a page with no date marker on it, are "
            "both recorded below as failures and NEITHER is kept as a release: an undated "
            "statement cannot be placed inside or outside the window.",
            "",
            "| Member | Pages read for dates | Undatable |",
            "| --- | --- | --- |",
        ]
        for result in sorted(costly, key=lambda r: r.member_id):
            lines.append(
                f"| {by_id[result.member_id]['name']} ({result.member_id}) | "
                f"{result.release_page_fetches} | {len(result.date_failures)} |"
            )
        failures = [f for r in costly for f in r.date_failures]
        if failures:
            lines += ["", "Every undatable release, with the reason:", ""]
            for entry in sorted(failures, key=lambda e: (e["id"], e["url"])):
                lines.append(f"* `{entry['id']}` — {entry['error']} — <{entry['url']}>")

    lines += ["", "## Date conflicts — two of the publisher's own dates disagree", ""]
    if date_conflicts:
        lines.append(
            "Nothing below was resolved: the stored date is the one the list page or the "
            "permalink gave, and the release page's disagreeing date is reported rather "
            "than written. A page date outside the permalink's month, or a different day "
            "where the URL carried one, can mean the WRONG PAGE was attached to this "
            "title — which is a thing to check by eye, not to average."
        )
        lines.append("")
        for entry in sorted(date_conflicts, key=lambda e: (e["id"], e["url"])):
            lines.append(f"* `{entry['id']}` — {entry['detail']} — <{entry['url']}>")
    else:
        lines.append(
            "None: where a release page published its own date it agreed with the date "
            "the list page gave, to the precision they share."
        )

    rejections = [entry for result in results for entry in result.url_rejections]
    lines += ["", "## URLs the release filter refused, and why", ""]
    if rejections:
        lines.append(
            "Each of these has the SHAPE of a release on its member's list and was taken "
            "out anyway, for the reason given. Nothing here is a silent drop: the owner "
            "decides what counts as a member's own statement, so a URL this collector "
            "removes from a statement list is printed where it can be disagreed with. A "
            "URL linked on every page of an archive appears once."
        )
        lines.append("")
        for entry in sorted(rejections, key=lambda e: (e["id"], e["url"])):
            lines.append(f"* `{entry['id']}` — {entry['reason']} — <{entry['url']}>")
    else:
        lines.append("None: every release-shaped URL on every page read was collected.")

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

    lines += ["", "## No press-release list exists, by id", ""]
    if no_list:
        lines.append(
            "**These are not a collection failure and are not counted as one anywhere in "
            "this report.** The owner looked, and the member's site publishes no "
            "press-release list at all — so there is nothing to collect, nothing to fix, "
            "and no reading of this report in which these rows are members who said "
            "nothing. Every URL that was tried is listed, so the finding can be checked "
            "rather than taken on trust, and so a site that adds a list later is "
            "recognised as a change rather than as a discovery."
        )
        lines.append("")
        for entry in no_list:
            lines.append(f"* `{entry['id']}` {entry['name']} — {entry['reason']}. Tried:")
            lines.extend(f"    * <{url}>" for url in entry["urls_tried"])
    else:
        lines.append("None: every row in the source list has a press-release list to read.")
    return "\n".join(lines) + "\n"


# --- the run --------------------------------------------------------------------------


def _read_page(url: str) -> str:
    return cache.fetch(
        CACHE_SOURCE, url, ext="html", ttl_hours=CACHE_TTL_HOURS, accept_status=(200, 301, 302)
    ).text


def _read_sitemap(url: str) -> str:
    """A sitemap through the same cache and the same 1/s host throttle as everything
    else. Stored as `xml` so a sitemap is not filed on disk as a page."""
    return cache.fetch(
        CACHE_SOURCE, url, ext="xml", ttl_hours=CACHE_TTL_HOURS, accept_status=(200, 301, 302)
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
    accepted, refused, no_list = sources(data_dir)

    if args.members:
        wanted = {m.strip() for m in args.members.split(",") if m.strip()}
        refused_ids = {entry["id"] for entry in refused}
        asked_for_refused = sorted(wanted & refused_ids)
        if asked_for_refused:
            # The source list's rule is not a default that a flag may override.
            print(f"refusing {', '.join(asked_for_refused)}: owner_checked is not true")
        for entry in no_list:
            if entry["id"] in wanted:
                # Asked for by name, and still not walked — but the answer is not a
                # refusal. There is no list on the site to read.
                print(f"no press-release list exists for {entry['id']}: {entry['reason']}")
        accepted = [row for row in accepted if row["id"] in wanted]

    window = {"start": WINDOW_START, "end": window_end()}
    print(
        f"collector (a): {len(accepted)} accepted rows, {len(refused)} refused, "
        f"{len(no_list)} with no press-release list"
    )

    results: list[MemberResult] = []
    for n, row in enumerate(accepted, start=1):
        # `--index-only` is the no-fetch path, so it leaves an undated anchor undated.
        read_release_page = None if args.index_only else _read_page
        if row.get("press_sitemap"):
            # The row's list page cannot be paged (`K000377`), and the site publishes its
            # own index of the archive. Same filter, same throttle, same record shape.
            result = walk_sitemap(
                row,
                read_sitemap=_read_sitemap,
                read_release_page=read_release_page,
            )
        else:
            result = walk_member(
                row,
                read_page=_read_page,
                read_release_page=read_release_page,
                limit_pages=args.limit_pages,
            )
        results.append(result)
        flag = "" if result.complete else f"  <-- {result.stopped}: {result.detail}"
        cost = (
            f"  (+{result.release_page_fetches} release pages read for their dates)"
            if result.release_page_fetches
            else ""
        )
        print(
            f"  [{n}/{len(accepted)}] {result.member_id} {len(result.releases):4} releases "
            f"over {result.pages_read} pages{cost}{flag}"
        )

    out_dir = data_dir.joinpath(*RAW_SUBDIR)
    statements_dir = out_dir / "statements"
    statements_dir.mkdir(parents=True, exist_ok=True)

    text_counts: dict[str, int] = {}
    text_failures: list[dict[str, str]] = []
    date_conflicts: list[dict[str, str]] = []
    collected: list[Release] = []
    by_id = {row["id"]: row for row in accepted}
    for result in results:
        records: list[dict[str, Any]] = []
        for release in sorted(result.releases, key=lambda r: (r.date, r.url), reverse=True):
            text = ""
            if not args.index_only:
                try:
                    html = _read_page(release.url)
                    text = release_text(html)
                    # Decision 5, at no extra fetch: this page is already in hand for its
                    # body, and its own date beats the permalink's where the two agree.
                    release = reconcile_date(release, release_page_date(html))
                except (RetryableHTTPError, httpx.HTTPError, OSError) as exc:
                    text_failures.append(
                        {"id": result.member_id, "url": release.url, "error": type(exc).__name__}
                    )
                if not text:
                    text_failures.append(
                        {"id": result.member_id, "url": release.url, "error": "no body text"}
                    )
            if release.date_conflict:
                date_conflicts.append(
                    {
                        "id": result.member_id,
                        "url": release.url,
                        "detail": release.date_conflict,
                    }
                )
            collected.append(release)
            records.append(statement_record(release, text))
        # A date upgraded from its release page can move a record inside its own month, so
        # the file is ordered after reconciliation rather than before it.
        records.sort(key=lambda r: (r["date"], r["url"]), reverse=True)
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
                # Read by the count-before-spend report's coverage table, which must not
                # count these as a collection failure.
                "no_list": no_list,
                "releases": [asdict(r) for r in collected],
                "date_conflicts": date_conflicts,
                "walks": [
                    {
                        "member_id": r.member_id,
                        "releases": len(r.releases),
                        "pages_read": r.pages_read,
                        "stopped": r.stopped,
                        "detail": r.detail,
                        "page2_method": r.page2_method,
                        "page2_url": r.page2_url,
                    }
                    for r in results
                ],
                "text_failures": text_failures,
                "date_failures": [f for r in results for f in r.date_failures],
                "url_rejections": [e for r in results for e in r.url_rejections],
                "release_page_fetches": {
                    r.member_id: r.release_page_fetches
                    for r in results
                    if r.release_page_fetches
                },
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
            date_conflicts=date_conflicts,
            no_list=no_list,
        ),
    )
    print(f"  index:  {(out_dir / 'index.json').relative_to(root)}")
    print(f"  report: {report.relative_to(root)}")
    if text_failures:
        print(f"  text failures: {len(text_failures)}")
    if date_conflicts:
        print(f"  date conflicts: {len(date_conflicts)} — see the report, nothing was resolved")
    date_failures = [f for r in results for f in r.date_failures]
    if date_failures:
        print(f"  undatable releases: {len(date_failures)} — recorded as failures, not kept")
    rejections = [e for r in results for e in r.url_rejections]
    if rejections:
        print(f"  URLs refused by the release filter: {len(rejections)} — each with its reason")
    if no_list:
        print(
            f"  no press-release list: {len(no_list)} row(s) — reported as 'no list exists', "
            "never as empty and never as a failure"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
