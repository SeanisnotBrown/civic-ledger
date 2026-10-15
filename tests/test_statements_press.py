"""§5 Phase 3 task 2a — collector (a), member press releases. No network in this file.

The properties under test are the ones that decide whether a member's page tells the
truth: a row the owner has not checked is REFUSED and said so out loud, a walk that
stopped early is reported as incomplete rather than as a total, a release with no
readable body is a recorded failure rather than a statement with no words, and the record
shape is the one the pre-filter reads.

Every HTML fixture here is the real markup of a real page family, trimmed — the five
shapes measured across the 32 accepted rows on 2026-10-14.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import yaml

from ingest import prefilter
from ingest import statements_press as press

# --- the five real page families, trimmed -------------------------------------------

# 22 of 32 rows: House Drupal. The date follows the title anchor.
HOUSE_DRUPAL = """
<div class="media-body"><div class="h3"><a
 href="/media/press-releases/bilirakis-introduces-bipartisan-bill-fix-medicare">
 Bilirakis Introduces Bipartisan Bill to Fix Medicare Advantage Payments</a></div>
 <div class="row"><div class="col-auto">October 13, 2026 </div></div></div>
<div class="media-body"><div class="h3"><a
 href="/media/press-releases/bilirakis-backed-change-act-improve-detection">
 Bilirakis-Backed CHANGE Act to Improve Early Detection Advances</a></div>
 <div class="row"><div class="col-auto">September 18, 2026 </div></div></div>
<a href="?page=1" rel="next">Next page</a>
"""

# 5 of 32: House ASPX. A machine-readable <time> follows the anchor.
HOUSE_ASPX = """
<div class="newsblocker"><h2 class="newsie-titler"><a
 href="documentsingle.aspx?DocumentID=405293">Castor, Schakowsky Introduce Legislation
 to Modernize FTC</a></h2><div class="newsie-details">
 <time datetime="2026-10-01">October 1, 2026</time></div></div>
<div class="newsblocker"><h2 class="newsie-titler"><a
 href="documentsingle.aspx?DocumentID=405001">Castor Champions Passage of Bipartisan
 Ratepayer Protection Act</a></h2><div class="newsie-details">
 <time datetime="2026-09-16">September 16, 2026</time></div></div>
"""

# 4 of 32: Senate WordPress. The date follows, inside the item.
SENATE_WORDPRESS = """
<h2 class="entry-title"><a
 href="https://www.hagerty.senate.gov/press-releases/2026/10/06/hagerty-joins-dialogue/">
 Hagerty Joins Trilateral Executive Dialogue as Distinguished Guest</a></h2>
<p class="post-meta"><span class="published">October 6, 2026</span></p>
<h2 class="entry-title"><a
 href="https://www.hagerty.senate.gov/press-releases/2026/10/01/hagerty-calls-disbarment/">
 Hagerty Formally Calls for Disbarment of Jack Smith</a></h2>
<p class="post-meta"><span class="published">October 1, 2026</span></p>
"""

# `L000583`: a dated permalink at the site root, not under the list path.
DATED_PERMALINK = """
<h3><a href="https://loudermilk.house.gov/2026/07/22/rep-loudermilk-on-passage-of-ndaa">
 Rep. Loudermilk on Passage of FY2027 NDAA</a></h3> <span>July 22, 2026</span>
<h3><a href="https://loudermilk.house.gov/2026/07/16/rep-loudermilks-bill-to-name-clinic">
 Rep. Loudermilk Bill to Name Cobb VA Clinic Advances</a></h3> <span>July 16, 2026</span>
"""

# `H001081`: the date sits ABOVE the title, and the release is keyed by query string on
# the list page's own path.
DATE_ABOVE_QUERY_KEYED = """
<div class="media-digest post-media-digest-item odd first"><div class="media-digest-body">
<div class="media-digest-header"><div class="post-media-digest-date">October 9, 2026</div>
 <div class="post-media-digest-type">Press Releases</div></div>
<div class="under-score"></div>
<a class="media-digest-body-link" href="/press-releases?ID=9146BD9B-C769-469A-8536">
 <div class="post-media-digest-title">Hayes, Landsman, Carter Introduce Bipartisan
 Clean School Bus Legislation</div><div class="post-media-digest-abstract"></div></a>
</div></div>
<div class="media-digest post-media-digest-item even"><div class="media-digest-body">
<div class="media-digest-header"><div class="post-media-digest-date">September 17, 2026</div>
 <div class="post-media-digest-type">Press Releases</div></div>
<div class="under-score"></div>
<a class="media-digest-body-link" href="/press-releases?ID=EAEB1A3F-7CEB-4169-BFC4">
 <div class="post-media-digest-title">Hayes Votes for Water Infrastructure Projects
 Supporting Danbury, New Britain and Thomaston</div></a>
</div></div>
"""

# `R000622` / `W000830`: the right <title>, and not one date in the body. The client-side
# wall of fact 7, on a row the owner marked accepted.
CLIENT_SIDE = """
<title>News | US Congressman Josh Riley</title>
<a href="https://riley.house.gov/services/help-with-federal-agency/">Help with a
 Federal Agency</a>
<a href="https://riley.house.gov/about/about-votes-and-legislation/">Votes and
 Legislation</a>
<div id="app"></div>
"""

RELEASE_PAGE = """
<html><head><title>A Release</title></head><body>
<nav><p>This navigation paragraph is long enough to pass the length floor but must not
 appear in the body text at all.</p></nav>
<script>var x = "a long string that must never reach the categorizer as a statement";</script>
<p>Share this</p>
<p>WASHINGTON, D.C. - Congressman Gus Bilirakis, joined by Representatives Raul Ruiz and
 Darren Soto, have introduced the Puerto Rico Medicare Advantage Fairness Act today.</p>
<p>This bipartisan bill would correct a long-standing formula error that has shortchanged
 the island for more than a decade, and it is a targeted fix.</p>
<footer><p>Office locations and hours are listed here for every district office we run.</p></footer>
</body></html>
"""


# A second page of real items for the multi-page walks: same family, different releases.
HOUSE_ASPX_PAGE_2 = """
<div class="media-body"><div class="h3"><a
 href="/media/press-releases/bilirakis-statement-on-the-appropriations-package">
 Bilirakis Statement on the Appropriations Package</a></div>
 <div class="row"><div class="col-auto">August 1, 2026 </div></div></div>
"""


def _row(
    member_id: str = "B001257",
    *,
    press_page: str = "https://bilirakis.house.gov/media/press-releases",
    checked: bool = True,
    name: str = "Gus M. Bilirakis",
) -> dict:
    return {
        "id": member_id,
        "name": name,
        "party": "R",
        "chamber": "house",
        "state": "FL",
        "official_site": "https://bilirakis.house.gov",
        "press_page": press_page,
        "rss": None,
        "campaign_site": None,
        "campaign_issues_page": None,
        "owner_checked": checked,
    }


# --- the extractor, per real family ---------------------------------------------------


@pytest.mark.parametrize(
    ("html", "list_url", "expected"),
    [
        (
            HOUSE_DRUPAL,
            "https://bilirakis.house.gov/media/press-releases",
            [
                ("2026-10-13", "Bilirakis Introduces Bipartisan Bill to Fix Medicare"),
                ("2026-09-18", "Bilirakis-Backed CHANGE Act to Improve Early Detection"),
            ],
        ),
        (
            HOUSE_ASPX,
            "https://castor.house.gov/news/documentquery.aspx?DocumentTypeID=821",
            [
                ("2026-10-01", "Castor, Schakowsky Introduce Legislation"),
                ("2026-09-16", "Castor Champions Passage of Bipartisan"),
            ],
        ),
        (
            SENATE_WORDPRESS,
            "https://www.hagerty.senate.gov/press-releases/",
            [
                ("2026-10-06", "Hagerty Joins Trilateral Executive Dialogue"),
                ("2026-10-01", "Hagerty Formally Calls for Disbarment"),
            ],
        ),
        (
            DATED_PERMALINK,
            "https://loudermilk.house.gov/category/press-releases/",
            [
                ("2026-07-22", "Rep. Loudermilk on Passage of FY2027 NDAA"),
                ("2026-07-16", "Rep. Loudermilk Bill to Name Cobb VA Clinic"),
            ],
        ),
        (
            DATE_ABOVE_QUERY_KEYED,
            "https://hayes.house.gov/press-releases",
            [
                ("2026-10-09", "Hayes, Landsman, Carter Introduce Bipartisan"),
                ("2026-09-17", "Hayes Votes for Water Infrastructure Projects"),
            ],
        ),
    ],
)
def test_every_real_page_family_yields_its_dated_releases(html, list_url, expected):
    releases = press.extract_releases(html, list_url, "B001257")
    assert len(releases) == len(expected)
    for release, (date, title_start) in zip(releases, expected, strict=True):
        assert release.date == date
        assert release.title.startswith(title_start)


def test_a_client_side_rendered_list_yields_nothing_rather_than_navigation():
    """The failure that matters most: a 200 with no items. Collecting this page's nav as
    a member's words would put "Help with a Federal Agency" on their statement list."""
    assert press.extract_releases(CLIENT_SIDE, "https://riley.house.gov/news/", "R000622") == []


def test_the_nearest_date_wins_over_the_neighbours():
    """The bug this rule exists for: on `H001081` the NEXT item's date sits inside the
    forward window, so forward-first gave every release its neighbour's date. Measured
    2026-10-14, the first Hayes release read 2026-09-17 when the page says October 9."""
    flat = press.flatten(DATE_ABOVE_QUERY_KEYED)
    first = next(m for m in press._ANCHOR.finditer(flat) if "9146BD9B" in m.group(1))
    assert press.nearest_date(flat, first.start(), first.end()) == "2026-10-09"


def test_a_date_inside_the_anchor_beats_one_outside_it():
    """`S001232` prints the date inside the title anchor; distance 0 always wins."""
    flat = '<span>January 1, 2020</span><a href="/x">September 29, 2026 A Title</a>'
    anchor = press._ANCHOR.search(flat)
    assert anchor is not None
    assert press.nearest_date(flat, anchor.start(), anchor.end()) == "2026-09-29"


def test_a_date_only_behind_the_anchor_is_found():
    flat = '<div>October 9, 2026</div><a href="/x">A Title Long Enough To Count</a>'
    anchor = press._ANCHOR.search(flat)
    assert anchor is not None
    assert press.nearest_date(flat, anchor.start(), anchor.end()) == "2026-10-09"


def test_no_date_either_side_is_no_date():
    flat = '<a href="/x">A Title Long Enough To Count</a>'
    anchor = press._ANCHOR.search(flat)
    assert anchor is not None
    assert press.nearest_date(flat, anchor.start(), anchor.end()) is None


def test_the_last_date_behind_the_anchor_is_the_nearest_one():
    """Two items above: the one just above is this item's, the one further up is the
    previous item's."""
    assert press._last_date("May 1, 2026 filler June 2, 2026 ")[1] == "2026-06-02"
    assert press._last_date("2026-05-01 then 2026-06-02 then")[1] == "2026-06-02"
    assert press._last_date("no date at all here") is None
    assert press._first_date("no date at all here") is None
    # ISO and printed at the same place: the publisher's machine-readable form wins.
    assert press._last_date("<time datetime=2026-10-01>October 1, 2026</time>")[1] == "2026-10-01"
    assert press._first_date("October 1, 2026 and 2026-12-25")[1] == "2026-10-01"
    assert press._last_date("2026-12-25 and October 1, 2026")[1] == "2026-10-01"


def test_an_undated_anchor_is_skipped_rather_than_dated_by_guesswork():
    """An undated row cannot be placed inside or outside the window, and a statement whose
    date is a guess cannot be compared against a vote."""
    html = (
        '<a href="/media/press-releases/a-real-looking-release-slug">'
        "A Release Title With No Date Anywhere Near It</a>"
    )
    assert press.extract_releases(html, "https://x.house.gov/media/press-releases", "X") == []


def test_navigation_anchors_are_too_short_to_be_titles():
    html = (
        '<a href="/media/press-releases/x-slug">Read more</a>'
        '<div class="col-auto">October 13, 2026</div>'
    )
    assert press.extract_releases(html, "https://x.house.gov/media/press-releases", "X") == []


def test_the_same_release_linked_twice_is_collected_once():
    html = (
        '<a href="/media/press-releases/one-slug">A Title Long Enough To Count</a>'
        "<span>October 13, 2026</span>"
        '<a href="/media/press-releases/one-slug">A Title Long Enough To Count</a>'
        "<span>October 13, 2026</span>"
    )
    assert len(press.extract_releases(html, "https://x.house.gov/media/press-releases", "X")) == 1


def test_a_date_printed_inside_the_title_anchor_is_not_left_in_the_title():
    """`S001232` wraps both in one anchor: "September 29, 2026 Sheehy's Protect ..."."""
    html = (
        '<a href="https://www.sheehy.senate.gov/news/press-releases/protect-act">'
        "September 29, 2026 Sheehy's Protect America Act Passes Committee</a>"
    )
    releases = press.extract_releases(
        html, "https://www.sheehy.senate.gov/newsroom/press-releases/", "S001232"
    )
    assert releases[0].date == "2026-09-29"
    assert releases[0].title == "Sheehy's Protect America Act Passes Committee"


def test_html_entities_in_a_title_are_resolved():
    html = (
        '<a href="/media/press-releases/guthrie-visit">BILIRAKIS TO HOST ENERGY &amp;'
        " COMMERCE CHAIRMAN</a><span>September 28, 2026</span>"
    )
    releases = press.extract_releases(html, "https://x.house.gov/media/press-releases", "X")
    assert "&" in releases[0].title and "&amp;" not in releases[0].title


# --- ordinal days -------------------------------------------------------------------

# The sixth family, measured 2026-10-14 on `H001046` Heinrich: the date and the title sit
# INSIDE one anchor, and the date carries an ordinal suffix. Real markup, trimmed.
SENATE_ORDINAL = """
<ul class="PageList"><li class="PageList__item"><div class="ArticleBlock">
 <div class="ArticleBlock__titleContainer"><a target="_self"
 href="https://www.heinrich.senate.gov/newsroom/press-releases/heinrich-demands-answers"
 class="ArticleBlock__link"><div>
 <p class="Heading Heading--time mb-1">October 13th, 2026</p></div>
 <h2 class=" ArticleTitle">Heinrich Demands Answers on Trump Administration Draining
 Strategic Petroleum Reserves to Dangerous Low Levels</h2></a></div></div></li>
<li class="PageList__item"><div class="ArticleBlock">
 <div class="ArticleBlock__titleContainer"><a target="_self"
 href="https://www.heinrich.senate.gov/newsroom/press-releases/indigenous-peoples-day"
 class="ArticleBlock__link"><div>
 <p class="Heading Heading--time mb-1">October 1st, 2026</p></div>
 <h2 class=" ArticleTitle">Heinrich Leads Resolution Recognizing Indigenous
 Peoples Day</h2></a></div></div></li></ul>
"""


@pytest.mark.parametrize(
    ("day", "iso_day"),
    [
        ("1st", "01"),
        ("2nd", "02"),
        ("3rd", "03"),
        ("4th", "04"),
        ("11th", "11"),
        ("12th", "12"),
        ("13th", "13"),
        ("21st", "21"),
        ("22nd", "22"),
        ("23rd", "23"),
        ("31st", "31"),
    ],
)
def test_an_ordinal_day_is_read_by_both_date_patterns(day, iso_day):
    """Every suffix form, in both patterns. `_first_date` carries `_DATE_LONG` through
    `_iso_from_long`, which reads the day with `int()` — so a suffix captured inside the
    day group would raise here rather than simply fail to match."""
    assert press._first_date(f"October {day}, 2026") == (0, f"2026-10-{iso_day}")
    assert press._last_date(f"filler October {day}, 2026")[1] == f"2026-10-{iso_day}"
    assert press._LEADING_DATE.sub("", f"October {day}, 2026 A Title") == "A Title"


def test_an_ordinal_date_is_read_with_a_weekday_and_without_a_comma():
    """The shapes the two patterns already allowed around the day, now with a suffix."""
    assert press._LEADING_DATE.sub("", "Monday, October 13th, 2026 A Title") == "A Title"
    assert press._LEADING_DATE.sub("", "October 13th 2026 A Title") == "A Title"
    assert press._first_date("October 13th 2026")[1] == "2026-10-13"
    # Unchecked on purpose: the day comes from the digits, so a publisher's stray suffix
    # costs a real release nothing.
    assert press._first_date("October 13st, 2026")[1] == "2026-10-13"


def test_a_plain_day_still_reads_with_the_suffix_optional():
    assert press._first_date("October 13, 2026")[1] == "2026-10-13"
    assert press._LEADING_DATE.sub("", "October 13, 2026 A Title") == "A Title"


def test_heinrichs_ordinal_dates_are_read_and_stripped_from_his_titles():
    """`H001046`, the row this change exists for: 0 releases before it, because every
    date on his page carries a suffix. The leading date must come off the title too —
    both sit inside the same anchor, so the title text starts with the date."""
    releases = press.extract_releases(
        SENATE_ORDINAL, "https://www.heinrich.senate.gov/newsroom/press-releases", "H001046"
    )
    assert [r.date for r in releases] == ["2026-10-13", "2026-10-01"]
    assert releases[0].title.startswith("Heinrich Demands Answers on Trump Administration")
    assert releases[1].title.startswith("Heinrich Leads Resolution Recognizing Indigenous")
    assert not any("2026" in r.title for r in releases)


# --- the permalink date (owner decision 5) --------------------------------------------

# `S001185` Sewell, `R000622` Riley and `W000830` Whitesides, measured 2026-10-14: the
# list prints the title and nothing else, and the only date is the one in the URL.
PERMALINK_ONLY = """
<div class="listing">
 <a href="/2026/10/rep-sewell-leads-a-bipartisan-letter-to-the-mexican-government">
  Rep. Sewell Leads Bipartisan Letter To The Mexican Government</a>
 <a href="/2026/9/rep-sewell-marks-25-years-since-the-september-11-attacks">
  Rep. Sewell Marks 25 Years Since The September 11 Terrorist Attacks</a>
</div>
"""


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/2026/06/10/a-slug", ("2026-06-10", "day")),
        ("/2026/6/10/a-slug", ("2026-06-10", "day")),
        ("/2026/9/a-slug", ("2026-09", "month")),
        ("/2026/09/a-slug", ("2026-09", "month")),
        ("/news/2023/01/03/a-slug", ("2023-01-03", "day")),
        ("/2026/12/31/a-slug", ("2026-12-31", "day")),
        # Refused, with no fallback guess: an out-of-range month or day is not a date,
        # and repairing it would invent one.
        ("/2026/13/05/a-slug", None),
        ("/2026/13/a-slug", None),
        ("/2026/06/32/a-slug", None),
        ("/2026/00/a-slug", None),
        ("/2026/06/00/a-slug", None),
        # Not a date at all.
        ("/media/press-releases/a-slug", None),
        ("/2026/1234/a-slug", None),
        ("/1999/06/10/a-slug", None),
    ],
)
def test_the_permalink_date_and_what_it_refuses(path, expected):
    assert press.permalink_date(f"https://x.house.gov{path}") == expected


def test_a_month_only_permalink_is_never_written_as_a_full_day_date():
    """Owner decision 5: stored verbatim, NEVER padded to the 1st. A padded date would put
    a day on the record the publisher never printed, and a day is what a statement is
    matched against a vote by."""
    date, precision = press.permalink_date("https://x.house.gov/2026/9/a-slug")
    assert date == "2026-09"
    assert precision == "month"
    assert len(date) == 7
    releases = press.extract_releases(
        PERMALINK_ONLY, "https://sewell.house.gov/press-releases", "S001185"
    )
    assert [(r.date, r.date_precision) for r in releases] == [
        ("2026-10", "month"),
        ("2026-09", "month"),
    ]
    assert not any(len(r.date) == 10 for r in releases)


def test_a_permalink_dates_a_release_the_page_leaves_undated():
    """The rows this exists for: 10 release links on `S001185` and 20 on `W000830`, every
    one of them undated on the page and dated in its own URL."""
    html = (
        '<a href="/2026/10/13/a-release-with-its-date-in-the-url">'
        "A Release With Its Date Only In The URL</a>"
    )
    releases = press.extract_releases(html, "https://x.house.gov/press-releases", "X")
    assert [(r.date, r.date_precision) for r in releases] == [("2026-10-13", "day")]


def test_a_date_on_the_page_still_wins_over_the_permalink():
    """The permalink is a FALLBACK. (Which of the two wins when both exist and disagree is
    step 3's question — the release page's own date — and is not settled here.)"""
    html = (
        '<a href="/2026/10/13/a-release-dated-twice">A Release Dated On The Page And In '
        "Its URL</a><span>September 29, 2026</span>"
    )
    releases = press.extract_releases(html, "https://x.house.gov/press-releases", "X")
    assert [(r.date, r.date_precision) for r in releases] == [("2026-09-29", "day")]


def test_a_release_with_no_date_anywhere_is_still_skipped():
    """The permalink fallback must not become a guess: a URL carrying no date leaves the
    release undated, and an undated release cannot be placed inside the window."""
    html = (
        '<a href="/media/press-releases/no-date-in-this-url-at-all">'
        "A Release With No Date On The Page Or In Its URL</a>"
    )
    assert press.extract_releases(html, "https://x.house.gov/media/press-releases", "X") == []


# --- the window, compared by upper bound ----------------------------------------------


@pytest.mark.parametrize(
    ("date", "expected"),
    [
        ("2023-01", "2023-01-31"),
        ("2023-02", "2023-02-28"),
        ("2024-02", "2024-02-29"),
        ("2026-09", "2026-09-30"),
        ("2023-01-03", "2023-01-03"),
    ],
)
def test_the_upper_bound_of_a_stored_date(date, expected):
    assert press.date_upper_bound(date) == expected


def test_a_month_only_january_2023_release_is_in_the_window():
    """The trap this is written against: compared as the bare string it stores,
    "2023-01" sorts BEFORE the window start "2023-01-03", so a release the publisher
    dated inside the window would be dropped as too old."""
    html = (
        '<a href="/2023/1/a-release-from-the-first-month-of-the-window">'
        "A Release From The First Month Of The Window</a>"
    )
    releases = press.extract_releases(html, "https://x.house.gov/press-releases", "X")
    assert [(r.date, r.date_precision) for r in releases] == [("2023-01", "month")]
    result = press.walk_member(_row(), read_page=_pages(html), window_start="2023-01-03")
    assert [r.date for r in result.releases] == ["2023-01"]


def test_a_page_of_month_only_window_dates_does_not_stop_the_walk_early():
    """The same trap in the OTHER comparison: the walk-stop takes the newest date on the
    page, so a page of month-only January 2023 dates would read as entirely out of
    window and stop the walk one page early."""
    page_one = (
        '<a href="/2023/1/a-release-from-the-first-month-of-the-window">'
        "A Release From The First Month Of The Window</a>"
    )
    page_two = (
        '<a href="/2022/12/a-release-from-before-the-window-opened">'
        "A Release From Before The Window Opened</a>"
    )
    read = _pages(page_one, page_two)
    result = press.walk_member(_row(), read_page=read, window_start="2023-01-03")
    assert result.pages_read == 2
    assert [r.date for r in result.releases] == ["2023-01"]
    assert result.stopped == "window"
    assert result.complete is True


def test_a_month_only_december_2022_release_is_out_of_the_window():
    html = (
        '<a href="/2022/12/a-release-from-before-the-window-opened">'
        "A Release From Before The Window Opened</a>"
    )
    releases = press.extract_releases(html, "https://x.house.gov/press-releases", "X")
    assert [r.date for r in releases] == ["2022-12"]
    result = press.walk_member(_row(), read_page=_pages(html), window_start="2023-01-03")
    assert result.releases == []
    assert result.stopped == "window"


# --- the release page's own date (owner decision 5, STATUS step 3) --------------------

# One marker per family, measured 2026-10-15 by fetching one real release from every row
# that reaches a release page. Real markup, trimmed.
META_PUBLISHED = '<meta property="article:published_time" content="2026-10-07T04:00:00Z" />'
META_DATE_SPACED = '<meta name="date" content="2026-10-07 00:00:00.0" />'
META_DATE_REVERSED = '<meta content="2026-09-28 00:00:00.0" name="date" />'
JSON_LD = '{"@type":"Article","datePublished":"2026-10-13T17:31:21+00:00",'
TIME_LONG_ATTR = (
    '<time class="Heading--time" datetime="October 2, 2026">'
    '<span class="sr-only">Published: </span>10.02.2026</time>'
)


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        (META_PUBLISHED, "2026-10-07"),
        (META_DATE_SPACED, "2026-10-07"),
        # The same CMS prints the attributes in either order, so the tag is parsed.
        (META_DATE_REVERSED, "2026-09-28"),
        (JSON_LD, "2026-10-13"),
        (TIME_LONG_ATTR, "2026-10-02"),
        ("<time>October 13, 2026</time>", "2026-10-13"),
        # `R000622` Riley publishes no marker at all — so STATUS fact 7's "every release
        # page carries a date" is wrong for that row, and Riley keeps its permalink date.
        ("<html><body><p>No marker anywhere on this page.</p></body></html>", None),
        # An edit is not a publication.
        ('{"dateModified":"2026-10-14T00:00:00Z"}', None),
        ('<meta name="dateModified" content="2026-10-14">', None),
        # Not a date: no such day exists.
        ('<meta name="date" content="2026-02-30">', None),
        # The body is never read for a date: the first date a release mentions is usually
        # the date of the thing it is about.
        ("<p>The hearing was held on October 1, 2026 and ran for three hours.</p>", None),
    ],
)
def test_the_markers_a_release_page_publishes_its_own_date_in(markup, expected):
    assert press.release_page_date(markup) == expected


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        # A marker whose value is not a date must not stop the ladder.
        ('{"datePublished":"not a date at all"}<time>October 13, 2026</time>', "2026-10-13"),
        ('<meta name="date" content="undated"><time>October 13, 2026</time>', "2026-10-13"),
        # A month that does not exist is not a date either.
        ('<meta name="date" content="2026-13-01">', None),
        # `R000605` prints a bare `<time>` label above the dated one.
        ('<time class="label">Published</time><time>October 13, 2026</time>', "2026-10-13"),
    ],
)
def test_a_marker_that_holds_no_date_does_not_stop_the_ladder(markup, expected):
    assert press.release_page_date(markup) == expected


def test_the_marker_order_is_fixed_and_the_first_hit_wins():
    """Disagreeing markers are not averaged: the order is published-time, then the plain
    date, then JSON-LD, then `<time>`."""
    assert press.release_page_date(META_PUBLISHED + '<meta name="date" content="2026-10-09">') == (
        "2026-10-07"
    )
    assert press.release_page_date(META_DATE_SPACED + JSON_LD) == "2026-10-07"
    assert press.release_page_date(JSON_LD + "<time>October 20, 2026</time>") == "2026-10-13"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/2024/02/29/a-slug", ("2024-02-29", "day")),
        ("/2026/02/30/a-slug", None),
        ("/2023/02/29/a-slug", None),
        ("/2026/04/31/a-slug", None),
        ("/2026/04/30/a-slug", ("2026-04-30", "day")),
    ],
)
def test_a_permalink_day_must_be_a_real_calendar_day(path, expected):
    """February 30th and April 31st are not dates. 2024 is a leap year and 2023 is not."""
    assert press.permalink_date(f"https://x.house.gov{path}") == expected


def _month_release() -> press.Release:
    return press.Release(
        "L000585",
        "2026-10",
        "A Release Dated Only In Its URL",
        "https://lahood.house.gov/2026/10/a-slug",
        date_precision="month",
        date_source="permalink",
    )


def test_the_release_pages_date_upgrades_a_month_to_the_day_it_printed():
    """`L000585` and `S001185`, the 20 month-only releases: the permalink gives the month
    and the release page gives the day inside it."""
    upgraded = press.reconcile_date(_month_release(), "2026-10-07")
    assert (upgraded.date, upgraded.date_precision, upgraded.date_source) == (
        "2026-10-07",
        "day",
        "release-page",
    )
    assert upgraded.date_conflict == ""


def test_a_page_date_outside_the_permalinks_month_is_flagged_and_never_written():
    """The reason this is flagged rather than resolved: it can mean the WRONG PAGE was
    attached to this title, and then its date is not evidence of anything."""
    flagged = press.reconcile_date(_month_release(), "2026-09-30")
    assert (flagged.date, flagged.date_precision) == ("2026-10", "month")
    assert flagged.date_conflict == (
        "the release page says 2026-09-30, the permalink says 2026-10"
    )


def test_a_page_date_on_a_different_day_is_flagged_and_never_written():
    day = press.Release(
        "R000622",
        "2026-10-06",
        "A Release Dated To The Day In Its URL",
        "https://riley.house.gov/2026/10/06/a-slug",
        date_source="permalink",
    )
    flagged = press.reconcile_date(day, "2026-10-08")
    assert flagged.date == "2026-10-06"
    assert "the release page says 2026-10-08" in flagged.date_conflict


def test_an_agreeing_or_absent_page_date_changes_nothing():
    day = press.Release("X", "2026-10-06", "A Title", "https://x.house.gov/2026/10/06/a-slug")
    assert press.reconcile_date(day, "2026-10-06") == day
    assert press.reconcile_date(day, None) == day


def test_two_dates_agree_at_the_precision_they_share():
    assert press._same_date("2026-10", "2026-10-07") is True
    assert press._same_date("2026-10-07", "2026-10") is True
    assert press._same_date("2026-10", "2026-09") is False
    assert press._same_date("2026-10-07", "2026-10-08") is False


def test_a_list_date_that_disagrees_with_its_permalink_is_flagged_not_resolved():
    """The third conflict shape: both dates are on the LIST page, one in the text beside
    the title and one in the URL. The text still wins, and the disagreement is reported."""
    html = (
        '<a href="/2026/10/13/a-release-dated-twice-and-differently">'
        "A Release Dated Twice And Differently</a><span>September 29, 2026</span>"
    )
    releases = press.extract_releases(html, "https://x.house.gov/press-releases", "X")
    assert releases[0].date == "2026-09-29"
    assert releases[0].date_source == "list-page"
    assert releases[0].date_conflict == (
        "the list page says 2026-09-29, the permalink says 2026-10-13"
    )


def test_a_list_date_inside_its_permalinks_month_is_not_a_conflict():
    html = (
        '<a href="/2026/10/a-release-whose-url-carries-only-the-month">'
        "A Release Whose URL Carries Only The Month</a><span>October 7, 2026</span>"
    )
    releases = press.extract_releases(html, "https://x.house.gov/press-releases", "X")
    assert releases[0].date == "2026-10-07"
    assert releases[0].date_conflict == ""


# --- dating an anchor from its own release page (step 3b) -----------------------------

# `K000377`, `R000605` and `S001181`: the list prints titles and links and NO date, in the
# text or in the URL. Real shape, trimmed.
ROUNDS_LIST = "https://www.rounds.senate.gov/newsroom/press-releases"
UNDATED_LIST = """
<div class="PageList">
 <a href="/newsroom/press-releases/rounds-calls-for-a-federal-gas-tax-suspension">
  Rounds Calls For A Federal Gas And Diesel Tax Suspension</a>
 <a href="/newsroom/press-releases/rounds-issues-a-statement-on-the-usps-report">
  Rounds Issues Statement Following Release Of The USPS OIG Report</a>
</div>
"""
FIRST = f"{ROUNDS_LIST}/rounds-calls-for-a-federal-gas-tax-suspension"
SECOND = f"{ROUNDS_LIST}/rounds-issues-a-statement-on-the-usps-report"


def _undated_row() -> dict:
    return _row("R000605", press_page=ROUNDS_LIST, name="Mike Rounds")


def _release_pages(dates: dict[str, str], *, fail: tuple[str, ...] = ()):
    """A release-page reader: a date marker per URL, no marker where the date is None,
    and a connection error for any URL in `fail`."""
    read_urls: list[str] = []

    def read(url: str) -> str:
        read_urls.append(url)
        if url in fail:
            raise httpx.ConnectError("the release page could not be reached")
        marker = dates.get(url)
        if marker is None:
            return "<html><body><p>This page publishes no date marker at all.</p></body></html>"
        return f'<html><head><meta name="date" content="{marker}"></head></html>'

    read.urls = read_urls  # type: ignore[attr-defined]
    return read


def test_an_undated_anchor_is_a_candidate_but_never_a_release():
    """`extract_releases` is `extract_candidates` minus the ones no date could be found
    for, so every caller that cannot spend a fetch still gets today's answer."""
    candidates = press.extract_candidates(UNDATED_LIST, ROUNDS_LIST, "R000605")
    assert [(c.date, c.date_precision, c.date_source) for c in candidates] == [
        ("", "none", "none"),
        ("", "none", "none"),
    ]
    assert press.extract_releases(UNDATED_LIST, ROUNDS_LIST, "R000605") == []


def test_a_candidate_is_dated_from_its_own_release_page():
    candidate = press.extract_candidates(UNDATED_LIST, ROUNDS_LIST, "R000605")[0]
    dated, failure = press.date_from_release_page(
        candidate, _release_pages({FIRST: "2026-10-02"})
    )
    assert failure is None
    assert (dated.date, dated.date_precision, dated.date_source) == (
        "2026-10-02",
        "day",
        "release-page",
    )


def test_a_release_page_with_no_date_is_a_recorded_failure_not_an_undated_keep():
    candidate = press.extract_candidates(UNDATED_LIST, ROUNDS_LIST, "R000605")[0]
    kept, failure = press.date_from_release_page(candidate, _release_pages({}))
    assert kept.date == ""
    assert failure == {
        "id": "R000605",
        "url": FIRST,
        "error": "no date on release page",
    }


def test_a_release_page_that_cannot_be_fetched_is_a_different_failure():
    """Ours to retry, not the publisher's omission — so the reasons are not pooled."""
    candidate = press.extract_candidates(UNDATED_LIST, ROUNDS_LIST, "R000605")[0]
    kept, failure = press.date_from_release_page(
        candidate, _release_pages({}, fail=(FIRST,))
    )
    assert kept.date == ""
    assert failure is not None and failure["error"] == "ConnectError"


def test_the_walk_dates_undated_anchors_and_counts_what_that_cost():
    read = _release_pages({FIRST: "2026-10-02", SECOND: "2026-09-28"})
    result = press.walk_member(
        _undated_row(),
        read_page=_pages(UNDATED_LIST),
        read_release_page=read,
        window_start="2023-01-03",
    )
    assert [(r.date, r.date_source) for r in result.releases] == [
        ("2026-10-02", "release-page"),
        ("2026-09-28", "release-page"),
    ]
    assert result.release_page_fetches == 2
    assert result.date_failures == []


def test_the_window_still_holds_when_the_date_arrives_only_after_the_fetch():
    """The out-of-window release is left behind exactly as a list-page date would be."""
    read = _release_pages({FIRST: "2026-10-02", SECOND: "2022-12-01"})
    result = press.walk_member(
        _undated_row(),
        read_page=_pages(UNDATED_LIST),
        read_release_page=read,
        window_start="2023-01-03",
    )
    assert [r.date for r in result.releases] == ["2026-10-02"]


def test_the_walk_stop_still_holds_when_the_dates_arrive_only_after_the_fetch():
    """Every date on the page predates the window, so the walk stops — and stops
    COMPLETE, which it can only know because the fetched dates were compared."""
    read = _release_pages({FIRST: "2022-12-02", SECOND: "2022-12-01"})
    result = press.walk_member(
        _undated_row(),
        read_page=_pages(UNDATED_LIST),
        read_release_page=read,
        window_start="2023-01-03",
    )
    assert result.releases == []
    assert result.stopped == "window"
    assert result.complete is True


def test_a_page_whose_releases_cannot_be_dated_is_not_an_empty_page():
    """Not `empty` and not `exhausted`: both of those describe the member's archive, and
    this describes our reading of it. `exhausted` counts as COMPLETE, so reporting it
    here would print an under-collected member as collected in full."""
    read = _release_pages({})
    result = press.walk_member(
        _undated_row(),
        read_page=_pages(UNDATED_LIST),
        read_release_page=read,
        window_start="2023-01-03",
    )
    assert result.stopped == "undated"
    assert result.complete is False
    assert "2 release(s), none of which could be dated" in result.detail
    assert len(result.date_failures) == 2
    assert result.releases == []


def test_without_a_release_page_reader_nothing_changes():
    """The screening report and `--index-only` cannot spend a fetch per anchor, so they
    must still get today's answer: no dated releases on the first page."""
    result = press.walk_member(
        _undated_row(), read_page=_pages(UNDATED_LIST), window_start="2023-01-03"
    )
    assert result.stopped == "empty"
    assert result.detail == "no dated releases on the first page"
    assert result.release_page_fetches == 0


def test_an_undatable_release_is_not_fetched_twice():
    """A pager that re-serves a page must not re-spend a fetch on the same dead end."""
    read = _release_pages({FIRST: "2026-10-02"})
    result = press.walk_member(
        _undated_row(),
        read_page=_pages(UNDATED_LIST, UNDATED_LIST),
        read_release_page=read,
        window_start="2023-01-03",
    )
    assert result.release_page_fetches == 2
    assert read.urls.count(SECOND) == 1
    assert result.stopped == "repeat"


# --- a press-release sitemap as the URL source (owner ruling, 2026-10-15) ------------

KELLY_LIST = "https://www.kelly.senate.gov/newsroom/press-releases/"
KELLY_SITEMAP = "https://www.kelly.senate.gov/press_releases-sitemap.xml"


def _kelly_url(slug: str) -> str:
    return f"{KELLY_LIST}{slug}/"


# Yoast's real shape, trimmed: <loc> + <lastmod>, and one entry with no <lastmod>.
SITEMAP_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>{_kelly_url('kelly-on-the-newest-thing')}</loc>
 <lastmod>2026-10-13T17:31:21+00:00</lastmod></url>
<url><loc>{_kelly_url('kelly-on-a-thing-from-2022')}</loc>
 <lastmod>2022-11-02T10:00:00+00:00</lastmod></url>
<url><loc>{_kelly_url('kelly-on-a-thing-with-no-lastmod')}</loc></url>
<url><loc>{_kelly_url('kelly-on-a-thing-edited-late')}</loc>
 <lastmod>2026-09-01T00:00:00+00:00</lastmod></url>
<url><lastmod>2026-10-01T00:00:00+00:00</lastmod></url>
</urlset>
"""

RELEASE_PAGE_WITH_DATE = (
    '<html><head><title>A Release - Senator Mark Kelly</title></head><body>'
    '<h1>Kelly Introduces The Thing That Happened</h1>'
    '<script type="application/ld+json">{{"@type":"Article",'
    '"datePublished":"{date}T17:31:21+00:00","dateModified":"2026-10-14T00:00:00+00:00"}}</script>'
    "<p>WASHINGTON, D.C. - Senator Mark Kelly introduced the thing today, which is a "
    "paragraph long enough to pass the body floor and be stored as the statement.</p>"
    "</body></html>"
)


def _kelly_row(**over) -> dict:
    return {
        **_row("K000377", press_page=KELLY_LIST, name="Mark Kelly"),
        "press_sitemap": [KELLY_SITEMAP],
        **over,
    }


def _sitemap_reader(xml: str = SITEMAP_XML):
    def read(_url: str) -> str:
        return xml

    return read


def _release_reader(
    dates: dict[str, str], *, fail: tuple[str, ...] = (), undated: tuple[str, ...] = ()
):
    """A release-page reader keyed by slug, so a test reads like the sitemap does."""
    read_urls: list[str] = []

    def read(url: str) -> str:
        read_urls.append(url)
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if slug in fail:
            raise httpx.ConnectError("the release page could not be reached")
        if slug in undated:
            return "<html><body><p>This page publishes no date marker at all.</p></body></html>"
        return RELEASE_PAGE_WITH_DATE.format(date=dates[slug])

    read.urls = read_urls  # type: ignore[attr-defined]
    return read


def test_a_sitemap_is_read_for_its_urls_and_their_lastmod():
    entries = press.sitemap_entries(SITEMAP_XML)
    assert [(e.url.rstrip("/").rsplit("/", 1)[-1], e.lastmod) for e in entries] == [
        ("kelly-on-the-newest-thing", "2026-10-13"),
        ("kelly-on-a-thing-from-2022", "2022-11-02"),
        ("kelly-on-a-thing-with-no-lastmod", ""),
        ("kelly-on-a-thing-edited-late", "2026-09-01"),
    ]
    # The fifth <url> has no <loc>, so it is not a URL.
    assert len(entries) == 4


def test_a_lastmod_before_the_window_is_skipped_without_a_fetch():
    """The one safe direction: a page last EDITED before 2023-01-03 cannot have been
    PUBLISHED inside the window, so it costs nothing to skip."""
    read = _release_reader(
        {
            "kelly-on-the-newest-thing": "2026-10-13",
            "kelly-on-a-thing-with-no-lastmod": "2026-05-04",
            "kelly-on-a-thing-edited-late": "2026-09-01",
        }
    )
    result = press.walk_sitemap(
        _kelly_row(), read_sitemap=_sitemap_reader(), read_release_page=read
    )
    assert not any("2022" in url for url in read.urls)
    assert len(result.releases) == 3
    assert "1 outside the window" in result.detail
    assert result.stopped == "sitemap"
    assert result.complete is True


def test_a_missing_lastmod_is_fetched_rather_than_skipped():
    """"Unknown" is not "old". An entry with no `<lastmod>` is read, and it sorts FIRST
    so a limit that takes the newest can never drop it."""
    read = _release_reader(
        {
            "kelly-on-the-newest-thing": "2026-10-13",
            "kelly-on-a-thing-with-no-lastmod": "2026-05-04",
            "kelly-on-a-thing-edited-late": "2026-09-01",
        }
    )
    result = press.walk_sitemap(
        _kelly_row(), read_sitemap=_sitemap_reader(), read_release_page=read, limit_urls=1
    )
    assert [u.rstrip("/").rsplit("/", 1)[-1] for u in read.urls] == [
        "kelly-on-a-thing-with-no-lastmod"
    ]
    assert [r.date for r in result.releases] == ["2026-05-04"]
    assert result.stopped == "limit"
    assert result.complete is False
    assert "stopped at 1 of" in result.detail


def test_the_pages_own_date_beats_a_lastmod_that_said_it_was_in_the_window():
    """A page edited in 2026 and published in 2022 is OUT of the window. `<lastmod>` only
    ever gets a release considered; the publication date decides."""
    read = _release_reader(
        {
            "kelly-on-the-newest-thing": "2022-12-01",
            "kelly-on-a-thing-with-no-lastmod": "2026-05-04",
            "kelly-on-a-thing-edited-late": "2026-09-01",
        }
    )
    result = press.walk_sitemap(
        _kelly_row(), read_sitemap=_sitemap_reader(), read_release_page=read
    )
    # Walk order is newest `lastmod` first, with the no-`lastmod` entry ahead of all of
    # them; the run sorts the member's file by the dates that were actually read.
    assert [r.date for r in result.releases] == ["2026-05-04", "2026-09-01"]
    assert "2 outside the window" in result.detail


def test_a_lastmod_is_never_stored_on_the_record():
    """The rule this exists to keep: `dateModified` is refused from a release page, and
    `<lastmod>` is the same field by another name."""
    read = _release_reader({"kelly-on-the-newest-thing": "2026-10-07"})
    result = press.walk_sitemap(
        _kelly_row(press_sitemap=[KELLY_SITEMAP]),
        read_sitemap=_sitemap_reader(
            f"<urlset><url><loc>{_kelly_url('kelly-on-the-newest-thing')}</loc>"
            "<lastmod>2026-10-13T00:00:00+00:00</lastmod></url></urlset>"
        ),
        read_release_page=read,
    )
    release = result.releases[0]
    assert (release.date, release.date_precision, release.date_source) == (
        "2026-10-07",
        "day",
        "release-page",
    )
    record = press.statement_record(release, "body")
    assert "2026-10-13" not in json.dumps(record)
    assert "lastmod" not in json.dumps(record)


def test_a_sitemap_url_with_no_publication_marker_is_a_failure_never_a_keep():
    read = _release_reader(
        {
            "kelly-on-a-thing-with-no-lastmod": "2026-05-04",
            "kelly-on-a-thing-edited-late": "2026-09-01",
        },
        undated=("kelly-on-the-newest-thing",),
    )
    result = press.walk_sitemap(
        _kelly_row(), read_sitemap=_sitemap_reader(), read_release_page=read
    )
    assert [f["error"] for f in result.date_failures] == ["no date on release page"]
    assert len(result.releases) == 2


def test_a_sitemap_url_that_cannot_be_fetched_is_a_different_failure():
    read = _release_reader(
        {
            "kelly-on-a-thing-with-no-lastmod": "2026-05-04",
            "kelly-on-a-thing-edited-late": "2026-09-01",
        },
        fail=("kelly-on-the-newest-thing",),
    )
    result = press.walk_sitemap(
        _kelly_row(), read_sitemap=_sitemap_reader(), read_release_page=read
    )
    assert [f["error"] for f in result.date_failures] == ["ConnectError"]


def test_a_sitemap_that_cannot_be_fetched_stops_that_row_and_says_so():
    def boom(_url: str) -> str:
        raise httpx.ConnectError("refused")

    result = press.walk_sitemap(
        _kelly_row(), read_sitemap=boom, read_release_page=_release_reader({})
    )
    assert result.stopped == "error"
    assert "ConnectError" in result.detail and KELLY_SITEMAP in result.detail
    assert result.complete is False


def test_the_release_filter_applies_to_sitemap_urls_too():
    """A sitemap mentioning a video page does not make it a statement."""
    xml = (
        "<urlset>"
        f"<url><loc>{KELLY_LIST}multimedia/watch/a-clip/</loc></url>"
        f"<url><loc>{_kelly_url('kelly-on-the-newest-thing')}</loc></url>"
        "<url><loc>https://example.com/off-host/a-release/</loc></url>"
        "</urlset>"
    )
    read = _release_reader({"kelly-on-the-newest-thing": "2026-10-07"})
    result = press.walk_sitemap(
        _kelly_row(), read_sitemap=_sitemap_reader(xml), read_release_page=read
    )
    assert len(result.releases) == 1
    assert [e["url"] for e in result.url_rejections] == [f"{KELLY_LIST}multimedia/watch/a-clip/"]
    assert "`multimedia` path segment" in result.url_rejections[0]["reason"]
    # Off-host was never a candidate, so it is not a refusal to report either.
    assert not any("example.com" in url for url in read.urls)


def test_the_same_url_in_two_sitemaps_is_read_once():
    row = _kelly_row(press_sitemap=[KELLY_SITEMAP, f"{KELLY_SITEMAP}2"])
    read = _release_reader(
        {
            "kelly-on-the-newest-thing": "2026-10-13",
            "kelly-on-a-thing-with-no-lastmod": "2026-05-04",
            "kelly-on-a-thing-edited-late": "2026-09-01",
        }
    )
    result = press.walk_sitemap(row, read_sitemap=_sitemap_reader(), read_release_page=read)
    assert result.pages_read == 2
    assert len(read.urls) == 3
    assert len(result.releases) == 3


def test_without_a_release_page_reader_a_sitemap_row_reports_why_it_collected_nothing():
    """`--index-only` cannot spend a fetch per release, and a sitemap carries no date
    that may be stored. So the answer is "nothing", with the reason."""
    result = press.walk_sitemap(_kelly_row(), read_sitemap=_sitemap_reader())
    assert (result.stopped, result.releases) == ("undated", [])
    assert "`<lastmod>` is when the page was last edited" in result.detail
    assert result.complete is False


def test_a_sitemap_walk_records_the_sitemap_as_how_it_found_its_urls():
    """The report's "how page 2 was found" column would otherwise read `none`, which the
    column documents as "the walk ended on page one" — not true here."""
    read = _release_reader(
        {
            "kelly-on-the-newest-thing": "2026-10-13",
            "kelly-on-a-thing-with-no-lastmod": "2026-05-04",
            "kelly-on-a-thing-edited-late": "2026-09-01",
        }
    )
    result = press.walk_sitemap(
        _kelly_row(), read_sitemap=_sitemap_reader(), read_release_page=read
    )
    assert (result.page2_method, result.page2_url) == ("sitemap", KELLY_SITEMAP)
    assert result.release_page_fetches == 3


def test_a_row_with_no_sitemap_urls_at_all_reads_nothing():
    result = press.walk_sitemap(
        _kelly_row(press_sitemap=[]),
        read_sitemap=_sitemap_reader(),
        read_release_page=_release_reader({}),
    )
    assert (result.pages_read, result.releases, result.stopped) == (0, [], "sitemap")


# --- the title a release page gives itself --------------------------------------------


@pytest.mark.parametrize(
    ("html", "expected", "why"),
    [
        (
            '<h1>Kelly Introduces The Thing</h1><title>Kelly Introduces The Thing - Senator'
            " Mark Kelly</title>",
            "Kelly Introduces The Thing",
            "`<h1>` carries the headline alone; the other two carry the site name too",
        ),
        (
            '<meta property="og:title" content="A Headline - Senator Mark Kelly" />',
            "A Headline - Senator Mark Kelly",
            "a headline with a suffix beats no headline",
        ),
        ("<title>A Page Title</title>", "A Page Title", "last resort"),
        ("<h1>  Spread   over\n lines  </h1>", "Spread over lines", "one line, one space"),
        ("<h1></h1><title>A Page Title</title>", "A Page Title", "an empty h1 is no title"),
        ('<meta property="og:title" content="" /><title>A Page Title</title>', "A Page Title", ""),
        ("<h1><span>Nested</span> Markup</h1>", "Nested Markup", "tags come out"),
        ("<title></title>", "", "nothing to take"),
        ("<html><body><p>No heading at all.</p></body></html>", "", "nothing to take"),
    ],
)
def test_the_title_a_release_page_gives_itself(html, expected, why):
    assert press.release_page_title(html) == expected, why


def test_a_page_with_no_heading_falls_back_to_the_publishers_own_slug():
    """Not invented — the publisher's own words out of their own URL. A statement is
    never dropped for want of a label."""
    entry = press.SitemapEntry(_kelly_url("kelly-introduces-the-thing"), "2026-10-13")
    release, failure = press.sitemap_release(
        entry,
        "K000377",
        lambda _url: '<meta name="date" content="2026-10-07">',
    )
    assert failure is None
    assert release.title == "kelly introduces the thing"


def test_the_sitemap_row_in_the_owners_list_is_kelly_alone():
    """Read from the owner's own file, as data: the field is set on one row, with the
    ratification recorded, and his `owner_checked` is untouched."""
    rows = yaml.safe_load(
        (press.repo_root() / "data" / "config" / "statement-sources.yaml").read_text(
            encoding="utf-8"
        )
    )["members"]
    with_sitemap = [r for r in rows if r.get("press_sitemap")]
    assert [r["id"] for r in with_sitemap] == ["K000377"]
    kelly = with_sitemap[0]
    assert kelly["press_sitemap"] == [
        "https://www.kelly.senate.gov/press_releases-sitemap.xml",
        "https://www.kelly.senate.gov/press_releases-sitemap2.xml",
    ]
    assert "owner-ratified 2026-10-15" in kelly["press_sitemap_source"]
    assert kelly["owner_checked"] is True
    assert all(url.startswith("https://www.kelly.senate.gov/") for url in kelly["press_sitemap"])


# --- which hrefs are releases ---------------------------------------------------------


@pytest.mark.parametrize(
    ("candidate", "list_url"),
    [
        (
            "https://x.house.gov/media/press-releases/a-slug",
            "https://x.house.gov/media/press-releases",
        ),
        (
            "https://x.house.gov/news/documentsingle.aspx?DocumentID=1",
            "https://x.house.gov/news/documentquery.aspx?DocumentTypeID=821",
        ),
        ("https://x.house.gov/2026/07/22/a-slug", "https://x.house.gov/category/press-releases/"),
        ("https://x.house.gov/2026/2/a-slug", "https://x.house.gov/press-releases"),
        ("https://x.senate.gov/news/press-releases/a-slug", "https://x.senate.gov/newsroom/press-releases/"),
        ("https://x.house.gov/press-releases?ID=ABC-123", "https://x.house.gov/press-releases"),
    ],
)
def test_the_release_url_shapes_measured_on_the_real_rows(candidate, list_url):
    assert press._is_release_url(candidate, list_url) is True


@pytest.mark.parametrize(
    ("candidate", "list_url", "why"),
    [
        (
            "https://www.tampabay.com/news/2026/an-article",
            "https://x.house.gov/media/press-releases",
            "a newspaper's article is not the member's statement",
        ),
        (
            "https://x.house.gov/media/press-releases",
            "https://x.house.gov/media/press-releases",
            "the list page is not one of its own items",
        ),
        (
            "https://x.house.gov/media/press-releases?page=3",
            "https://x.house.gov/media/press-releases",
            "a pager link sits next to the dates of the items it pages past",
        ),
        (
            "https://x.senate.gov/press-releases/page/2/",
            "https://x.senate.gov/press-releases/",
            "the WordPress pager, same reason",
        ),
        (
            "https://x.house.gov/services/help-with-federal-agency/",
            "https://x.house.gov/news/",
            "office services are not press releases",
        ),
    ],
)
def test_what_is_never_a_release(candidate, list_url, why):
    assert press._is_release_url(candidate, list_url) is False, why


# --- the four refusals, each measured on a cached rendered page -----------------------


@pytest.mark.parametrize(
    ("candidate", "list_url", "reason"),
    [
        # `K000377` Kelly, under the title "Continue Reading on Medium".
        (
            "https://www.kelly.senate.gov/newsroom/press-releases/${item.link}",
            "https://www.kelly.senate.gov/newsroom/press-releases/",
            "template literal",
        ),
        # `S001181` Shaheen lists three of these among her ten "release" links.
        (
            "https://www.shaheen.senate.gov/news/multimedia/watch/the-time-is-now",
            "https://www.shaheen.senate.gov/news",
            "`multimedia` path segment",
        ),
        ("https://x.house.gov/news/watch/a-clip", "https://x.house.gov/news", "`watch` path"),
        ("https://x.house.gov/news/video/a-clip", "https://x.house.gov/news", "`video` path"),
        ("https://x.house.gov/news/videos/a-clip", "https://x.house.gov/news", "`videos` path"),
        # `R000622` Riley, at the top of every page of his news list.
        (
            "https://riley.house.gov/news/newsletter-subscribe/",
            "https://riley.house.gov/news/",
            "subscribe form",
        ),
        ("https://x.house.gov/news/subscribe", "https://x.house.gov/news", "subscribe form"),
        # The list page itself, in its three shapes.
        (
            "https://x.house.gov/media/press-releases",
            "https://x.house.gov/media/press-releases",
            "the list page itself",
        ),
        (
            "https://x.house.gov/news/documentquery.aspx?DocumentTypeID=821",
            "https://x.house.gov/news/documentquery.aspx?DocumentTypeID=821",
            "the list page itself",
        ),
        # The ASPX family's list URL carries a query; the query-less path is still the
        # list page, and used to pass the shape test unrefused.
        (
            "https://x.house.gov/news/documentquery.aspx",
            "https://x.house.gov/news/documentquery.aspx?DocumentTypeID=821",
            "the list page itself",
        ),
    ],
)
def test_the_release_filter_refuses_with_a_reason(candidate, list_url, reason):
    """Every refusal carries its reason: a URL dropped silently is indistinguishable from
    a URL nobody looked at, and the owner is the one who decides what counts as a
    member's own statement."""
    refused = press.release_url_rejection(candidate, list_url)
    assert refused is not None and reason in refused
    assert press._is_release_url(candidate, list_url) is False


@pytest.mark.parametrize(
    ("candidate", "list_url", "why"),
    [
        (
            "https://x.house.gov/media/press-releases/senator-calls-for-watchdog",
            "https://x.house.gov/media/press-releases",
            "a rule matches whole segments, so a slug carrying its letters is a release",
        ),
        (
            "https://x.house.gov/media/press-releases/video-game-safety-act-advances",
            "https://x.house.gov/media/press-releases",
            "`video-game-safety-act-advances` is not the segment `video`",
        ),
        (
            "https://x.house.gov/press-releases?ID=9146BD9B-C769",
            "https://x.house.gov/press-releases",
            "`H001081` keys every release by query on the list's own path",
        ),
    ],
)
def test_the_release_filter_refuses_nothing_it_was_not_asked_to(candidate, list_url, why):
    assert press.release_url_rejection(candidate, list_url) is None, why
    assert press._is_release_url(candidate, list_url) is True, why


CASTOR_LIST = "https://castor.house.gov/news/documentquery.aspx?DocumentTypeID=821"
PERRY_LIST = "https://perry.house.gov/news/documentquery.aspx?DocumentTypeID=2608"
MASSIE_LIST = "https://massie.house.gov/news/documentquery.aspx?DocumentTypeID=2362"


@pytest.mark.parametrize(
    ("candidate", "list_url", "what_it_really_is"),
    [
        # Both of these were counted among Castor's twelve page-one releases in the
        # owner-approved 2026-10-14 count report, each wearing a neighbour's date.
        (
            "https://castor.house.gov/news/documentquery.aspx?DocumentTypeID=817",
            CASTOR_LIST,
            "Speeches and Floor Statements — another document type's list",
        ),
        (
            "https://castor.house.gov/news/documentquery.aspx?IssueID=111866",
            CASTOR_LIST,
            "Protecting Consumers — an issue category's list",
        ),
        (
            "https://perry.house.gov/news/documentquery.aspx?IssueID=119133",
            PERRY_LIST,
            "Defense and National Security — an issue category's list",
        ),
        (
            "https://massie.house.gov/news/documentquery.aspx?IssueID=112050",
            MASSIE_LIST,
            "Defense and National Security, on Massie's newly ratified list page",
        ),
        (
            "https://massie.house.gov/news/documentquery.aspx?DocumentTypeID=2365",
            MASSIE_LIST,
            "Speeches and Floor Statements, which the Record already collects",
        ),
    ],
)
def test_an_aspx_query_link_is_a_list_and_never_a_release(
    candidate, list_url, what_it_really_is
):
    """Owner ruling, 2026-10-15. The leak this closes did not fail visibly — it took a
    neighbouring release's date and became a statement in the member's own list."""
    refused = press.release_url_rejection(candidate, list_url)
    assert refused is not None and "documentquery.aspx" in refused, what_it_really_is
    assert press._is_release_url(candidate, list_url) is False


def test_the_aspx_rule_leaves_a_real_release_and_the_query_keyed_family_alone():
    """`documentsingle.aspx` is the single release on that CMS, and `H001081` — the row
    the "a different query means a release" rule was written for — keys every release by
    query on its own list path. Neither may be touched by this."""
    single = "https://castor.house.gov/news/documentsingle.aspx?DocumentID=405293"
    assert press.release_url_rejection(single, CASTOR_LIST) is None
    assert press._is_release_url(single, CASTOR_LIST) is True
    hayes = "https://hayes.house.gov/press-releases?ID=9146BD9B-C769"
    assert press.release_url_rejection(hayes, "https://hayes.house.gov/press-releases") is None
    assert press._is_release_url(hayes, "https://hayes.house.gov/press-releases") is True
    # And the list page itself still answers with the more precise reason.
    assert press.release_url_rejection(CASTOR_LIST, CASTOR_LIST) == "the list page itself"


def test_the_subscribe_rule_matches_inside_a_segment_and_the_video_rules_do_not():
    """The two rules are deliberately different widths, as ruled: `watch` and its three
    siblings must equal a whole segment, because `senator-calls-for-watchdog` is a real
    release; `subscribe` matches anywhere INSIDE a segment, because the shapes measured
    are `newsletter-subscribe` and `subscribe-to-the-report`. The cost of the wider rule
    is that a release whose own slug carries the word would go with them — visible in the
    report, by URL, which is why the refusals are printed."""
    base = "https://x.house.gov/media/press-releases"
    assert press.release_url_rejection(f"{base}/subscribe-to-the-weekly-report", base) is not None
    assert press.release_url_rejection(f"{base}/a-bill-to-subscribe-rural-clinics", base) is not (
        None
    )
    assert press.release_url_rejection(f"{base}/senator-calls-for-watchdog", base) is None


def test_an_off_host_url_is_not_a_release_and_not_a_refusal_to_report():
    """A press page links to news coverage. That is ordinary, not a leak, so it is not
    release-shaped and carries no reason — otherwise every page's refusal list would be
    its outbound links and nobody would read it."""
    article = "https://www.tampabay.com/news/2026/an-article"
    assert press.release_url_rejection(article, "https://x.house.gov/news") is None
    assert press._has_release_shape(article, "https://x.house.gov/news") is False
    assert press._is_release_url(article, "https://x.house.gov/news") is False


def test_every_refusal_is_logged_with_its_reason_and_only_once():
    html = (
        '<a href="/news/newsletter-subscribe/">Subscribe to the Riley Report</a>'
        '<a href="/news/newsletter-subscribe/">Subscribe to the Riley Report</a>'
        '<a href="/news/multimedia/watch/the-time-is-now">A Clip Of The Floor Speech</a>'
        '<a href="/news/a-real-release-about-the-landline-shutoffs">'
        "Riley Demands Answers From Verizon Over Landline Shutoffs</a>"
        "<span>October 9, 2026</span>"
    )
    rejections: list[dict] = []
    releases = press.extract_candidates(
        html, "https://riley.house.gov/news/", "R000622", rejections=rejections
    )
    assert [r.title for r in releases] == [
        "Riley Demands Answers From Verizon Over Landline Shutoffs"
    ]
    assert [e["url"] for e in rejections] == [
        "https://riley.house.gov/news/newsletter-subscribe/",
        "https://riley.house.gov/news/multimedia/watch/the-time-is-now",
    ]
    assert "subscribe form" in rejections[0]["reason"]
    assert "`multimedia` path segment" in rejections[1]["reason"]
    assert all(e["id"] == "R000622" for e in rejections)


def test_a_caller_that_reports_nothing_still_gets_the_same_verdict():
    """`extract_releases` and the screening smoke pass take no rejection list — they are
    not writing the count report. The URL is still refused; it is only unreported."""
    html = (
        '<a href="/news/newsletter-subscribe/">Subscribe to the Riley Report</a>'
        "<span>October 9, 2026</span>"
    )
    assert press.extract_releases(html, "https://riley.house.gov/news/", "R000622") == []
    assert press.extract_candidates(html, "https://riley.house.gov/news/", "R000622") == []


def test_a_url_that_never_looked_like_a_release_is_not_logged():
    """The logging gate is the SHAPE test: `/videos/clip` off the list's path was never a
    candidate, and listing it would bury the refusals that matter in page furniture."""
    html = (
        '<a href="/videos/a-clip-from-the-floor">A Clip From The Floor Today</a>'
        '<a href="/news/videos/a-clip-from-the-floor">A Clip From The Floor Today</a>'
    )
    rejections: list[dict] = []
    assert press.extract_candidates(
        html, "https://riley.house.gov/news/", "R000622", rejections=rejections
    ) == []
    assert [e["url"] for e in rejections] == [
        "https://riley.house.gov/news/videos/a-clip-from-the-floor"
    ]


def test_the_walk_reports_every_refusal_once_across_pages():
    """Riley links his newsletter signup at the top of all 55 pages of his archive. That
    is one refusal to print, not 55."""
    page = (
        '<a href="/news/newsletter-subscribe/">Subscribe to the Riley Report</a>'
        '<a href="/news/a-release-about-the-landline-shutoffs-{n}">'
        "Riley Demands Answers From Verizon Over Landline Shutoffs {n}</a>"
        "<span>October {n}, 2026</span>"
    )
    row = _row("R000622", press_page="https://riley.house.gov/news/", name="Josh Riley")
    result = press.walk_member(
        row,
        read_page=_pages(page.replace("{n}", "9"), page.replace("{n}", "8"), "<html></html>"),
        window_start="2023-01-03",
    )
    assert len(result.releases) == 2
    assert [e["url"] for e in result.url_rejections] == [
        "https://riley.house.gov/news/newsletter-subscribe/"
    ]


def test_a_walk_with_nothing_refused_reports_nothing_refused():
    result = press.walk_member(_row(), read_page=_pages(HOUSE_DRUPAL), window_start="2023-01-03")
    assert result.url_rejections == []


@pytest.mark.parametrize(
    ("list_url", "page", "expected"),
    [
        (
            "https://x.house.gov/media/press-releases",
            0,
            "https://x.house.gov/media/press-releases",
        ),
        (
            "https://x.house.gov/media/press-releases",
            2,
            "https://x.house.gov/media/press-releases?page=2",
        ),
        (
            "https://x.house.gov/news/documentquery.aspx?DocumentTypeID=821",
            1,
            "https://x.house.gov/news/documentquery.aspx?DocumentTypeID=821&Page=2",
        ),
        (
            "https://x.senate.gov/press-releases/",
            1,
            "https://x.senate.gov/press-releases/page/2/",
        ),
        (
            "https://x.house.gov/category/press-releases/",
            1,
            "https://x.house.gov/category/press-releases/page/2/",
        ),
    ],
)
def test_each_family_pages_in_its_own_scheme(list_url, page, expected):
    """The FALLBACK, for a list that publishes no pager link of its own. Detected from the
    list URL, so a redesigned pager cannot silently restart the walk at page 1 and collect
    the newest page over and over."""
    assert press.page_url(list_url, page) == expected


# --- the site's own next link (step 4b) -----------------------------------------------

# The real pager markup of every family, measured 2026-10-15 off the cached pages. The
# `page_url` guess is wrong for three of these five.
DRUPAL_PAGER = (
    '<a href="?page=0">Current page 1</a><a href="?page=1">Page 2</a>'
    '<a href="?page=1" title="Go to next page" rel="next" class="page-link">Next page››</a>'
    '<a href="?page=154">Last pageLast »</a>'
)
ASPX_PAGER = (
    '<a href="/news/documentquery.aspx?DocumentTypeID=821&amp;Page=2">Next »</a>'
)
WORDPRESS_PAGER = (
    '<link rel="next" href="https://www.hagerty.senate.gov/press-releases/page/2/" />'
    '<a class="nextpostslink" rel="next" aria-label="Next Page"'
    ' href="https://www.hagerty.senate.gov/press-releases/page/2/?et_blog"></a>'
    '<a href="https://www.hagerty.senate.gov/press-releases/page/251/?et_blog">Last »</a>'
)
PAGENUM_PAGER = '<a href="?pagenum_rs=2">Next</a>'
NUMBERED_PAGER = (
    '<a href="/press-releases?page=1">1</a><a href="/press-releases?page=2">2</a>'
    '<a href="/press-releases?page=55">Last</a>'
)


@pytest.mark.parametrize(
    ("html", "current", "expected", "row"),
    [
        (
            DRUPAL_PAGER,
            "https://bilirakis.house.gov/media/press-releases",
            "https://bilirakis.house.gov/media/press-releases?page=1",
            "`B001257` and 21 other House Drupal rows: rel=next, and 0-based",
        ),
        (
            ASPX_PAGER,
            "https://castor.house.gov/news/documentquery.aspx?DocumentTypeID=821",
            "https://castor.house.gov/news/documentquery.aspx?DocumentTypeID=821&Page=2",
            "`C001066` and 4 other ASPX rows: no rel=next, the word 'Next »'",
        ),
        (
            WORDPRESS_PAGER,
            "https://www.hagerty.senate.gov/press-releases/",
            "https://www.hagerty.senate.gov/press-releases/page/2/",
            "`H000601`, `L000583`, `R000622`, `W000830`: the head's own <link rel=next>",
        ),
        (
            PAGENUM_PAGER,
            "https://www.rounds.senate.gov/newsroom/press-releases",
            "https://www.rounds.senate.gov/newsroom/press-releases?pagenum_rs=2",
            "`R000605` and `H001046`: a param no guess would have produced",
        ),
        (
            NUMBERED_PAGER,
            "https://hayes.house.gov/press-releases",
            "https://hayes.house.gov/press-releases?page=2",
            "`H001081`: numbered only, and 1-based — the site settles that itself",
        ),
    ],
)
def test_the_sites_own_next_link_is_followed_in_every_measured_family(
    html, current, expected, row
):
    assert press.next_page_url(html, current, 2) == expected, row


def test_the_word_next_beats_a_number_printed_before_it():
    """A numbered pager prints "1 2 3 … Next >", so the numbers come first. A word the
    site itself calls "next" is the better evidence of what it considers next."""
    html = '<a href="?page=9">2</a><a href="?page=2">Next ></a>'
    assert press.next_page_url(html, "https://x.house.gov/p", 2) == "https://x.house.gov/p?page=2"


def test_the_last_link_is_not_the_next_link():
    """`R000622` prints "Last »" pointing at page 6 of 6. Reduced to its letters that is
    "last", which is not "next" — and following it would skip four pages of releases."""
    html = '<a href="/news/page/6/?et_blog">Last »</a>'
    assert press.next_page_url(html, "https://riley.house.gov/news/", 2) is None


@pytest.mark.parametrize(
    ("html", "why"),
    [
        ("<html><body><p>No pager at all.</p></body></html>", "nothing to follow"),
        ('<a href="/p">3</a>', "the wrong number: page 3 is not page 2"),
        ('<a rel="next" href="https://elsewhere.com/p/2">Next</a>', "off-host"),
        ('<a rel="next" href="">Next</a>', "an empty href"),
        ('<link rel="prefetch" href="/p?page=2">', "rel is not next"),
    ],
)
def test_what_is_not_a_next_link(html, why):
    assert press.next_page_url(html, "https://x.house.gov/p", 2) is None, why


def test_a_next_link_that_points_at_the_page_we_are_on_is_not_followed():
    """The last page of some archives keeps rendering a "next" that points at itself.
    Following it would re-read the page and read that as the end of the archive."""
    html = '<a rel="next" href="/press-releases">Next</a><a href="/press-releases">2</a>'
    assert press.next_page_url(html, "https://x.house.gov/press-releases", 2) is None
    assert press.next_page_url(html, "https://x.house.gov/press-releases/", 2) is None


def test_a_numbered_link_that_points_at_the_page_we_are_on_falls_through():
    html = '<a href="/press-releases">2</a>'
    assert press.next_page_url(html, "https://x.house.gov/press-releases", 2) is None


def test_the_walk_follows_the_link_and_records_that_it_did():
    served: list[str] = []

    def read(url: str) -> str:
        served.append(url)
        if url.endswith("?pagenum_rs=2"):
            return HOUSE_ASPX_PAGE_2
        return HOUSE_DRUPAL.replace('<a href="?page=1" rel="next">Next page</a>', PAGENUM_PAGER)

    row = _row("R000605", press_page="https://www.rounds.senate.gov/newsroom/press-releases")
    result = press.walk_member(row, read_page=read)
    assert served[1] == "https://www.rounds.senate.gov/newsroom/press-releases?pagenum_rs=2"
    assert result.page2_method == "link"
    assert result.page2_url == served[1]
    assert len(result.releases) == 3


def test_a_row_with_no_link_of_its_own_falls_back_to_the_guess_and_says_so():
    """`page_url`'s guess is not removed — it is what is left for a list that publishes no
    pager link, and the report names the rows resting on it."""
    plain = HOUSE_DRUPAL.replace('<a href="?page=1" rel="next">Next page</a>', "")
    result = press.walk_member(_row(), read_page=_pages(plain, HOUSE_ASPX_PAGE_2, "<html></html>"))
    assert result.page2_method == "page_url"
    assert result.page2_url == "https://bilirakis.house.gov/media/press-releases?page=2"
    assert len(result.releases) == 3


def test_a_walk_that_ends_on_page_one_asked_for_no_page_two():
    result = press.walk_member(_row(), read_page=_pages(CLIENT_SIDE))
    assert (result.page2_method, result.page2_url) == ("none", "")


def test_a_site_that_stops_linking_has_reached_the_end_of_its_archive():
    """The pager's own evidence, in both directions: page 1 links page 2, page 2 links
    nothing, so the archive ends at page 2. Guessing `?page=2` here would ask for a page
    the site says is not there — and a Drupal pager that clamps to its last page would
    answer with a page already read, printing INCOMPLETE beside a member collected in
    full."""
    served: list[str] = []

    def read(url: str) -> str:
        served.append(url)
        return HOUSE_DRUPAL if len(served) == 1 else HOUSE_ASPX_PAGE_2

    result = press.walk_member(_row(), read_page=read)
    assert len(served) == 2
    assert result.stopped == "exhausted"
    assert result.detail == "archive ends at page 2"
    assert result.complete is True
    assert len(result.releases) == 3


# --- the body -------------------------------------------------------------------------


def test_the_release_body_is_the_paragraphs_and_nothing_else():
    text = press.release_text(RELEASE_PAGE)
    assert text.startswith("WASHINGTON, D.C. - Congressman Gus Bilirakis")
    assert "formula error" in text
    assert "navigation paragraph" not in text
    assert "Office locations" not in text
    assert "var x" not in text
    assert "Share this" not in text


def test_a_page_with_no_paragraphs_reads_as_empty_not_as_navigation():
    assert press.release_text("<html><body><div>Just a div</div></body></html>") == ""


# --- the record contract --------------------------------------------------------------


def test_the_record_is_the_shape_the_prefilter_reads():
    release = press.Release("B001257", "2026-10-13", "A Title", "https://x.house.gov/p/a-slug")
    record = press.statement_record(release, "Some body text.")
    assert record["source"] == "member_press"
    assert record["attribution"] == "press-office"
    assert record["granule_id"] == "/p/a-slug"
    assert record["segments"] == ["Some body text."]
    assert record["chars"] == len("Some body text.")
    # The contract: the pre-filter reads this record without knowing where it came from.
    survivor, drops = prefilter.apply_to_statement(record, {})
    assert drops == []
    assert survivor is not None


def test_press_office_attribution_is_not_the_no_words_drop():
    """`none` is the pre-filter's "no words could be attributed" rule. A press release's
    words ARE attributable, so the attribution must not collide with it."""
    release = press.Release("B001257", "2026-10-13", "A Title", "https://x.house.gov/p/s")
    record = press.statement_record(release, "A long enough body of real text here.")
    assert record["attribution"] != "none"
    assert prefilter.apply_to_statement(record, {})[0] is not None


def test_the_record_carries_its_dates_precision_explicitly():
    """Owner decision 5 is a Phase 6 rule — a month-only date is never matched against a
    single day's vote — so the precision is a field rather than something a reader has to
    work out by counting the characters of `date`."""
    month = press.Release(
        "L000585",
        "2026-09",
        "A Release Dated Only To Its Month",
        "https://lahood.house.gov/2026/9/a-slug",
        date_precision="month",
        date_source="permalink",
    )
    record = press.statement_record(month, "A long enough body of real text here.")
    assert (record["date"], record["date_precision"]) == ("2026-09", "month")
    # And the pre-filter still reads the shape, with the new field on it.
    assert prefilter.apply_to_statement(record, {})[0] is not None

    day = press.Release("B001257", "2026-09-28", "A Title", "https://x.house.gov/p/s")
    assert press.statement_record(day, "body")["date_precision"] == "day"


def test_a_release_with_no_body_carries_no_segments():
    release = press.Release("B001257", "2026-10-13", "A Title", "https://x.house.gov/p/s")
    record = press.statement_record(release, "")
    assert record["segments"] == []
    assert record["chars"] == 0


# --- the walk -------------------------------------------------------------------------


def _pages(*htmls: str):
    """A reader that serves one HTML per page request, in order, then empty pages."""
    served: list[str] = []

    def read(url: str) -> str:
        served.append(url)
        index = len(served) - 1
        return htmls[index] if index < len(htmls) else "<html></html>"

    read.served = served  # type: ignore[attr-defined]
    return read


def test_the_walk_stops_at_the_first_page_older_than_the_window():
    old = (
        '<a href="/media/press-releases/an-old-one">A Release From Before The Window</a>'
        "<span>December 1, 2022</span>"
    )
    read = _pages(HOUSE_DRUPAL, old)
    result = press.walk_member(_row(), read_page=read, window_start="2023-01-03")
    assert result.stopped == "window"
    assert result.complete is True
    assert result.pages_read == 2
    assert [r.date for r in result.releases] == ["2026-10-13", "2026-09-18"]


def test_a_release_older_than_the_window_on_a_mixed_page_is_not_collected():
    mixed = HOUSE_DRUPAL + (
        '<a href="/media/press-releases/an-old-one">A Release From Before The Window</a>'
        "<span>December 1, 2022</span>"
    )
    result = press.walk_member(_row(), read_page=_pages(mixed), window_start="2023-01-03")
    assert [r.date for r in result.releases] == ["2026-10-13", "2026-09-18"]
    # The out-of-window release on the page is left behind; the walk goes on to page 2
    # and finds nothing, which after a single page of content is the ambiguous case.
    assert result.stopped == "single-page"


def test_a_first_page_with_no_items_is_an_incomplete_walk_not_an_empty_member():
    """`K000377`, `M001222`, `R000622`, `W000830` — rows the owner accepted whose lists a
    plain GET cannot read. "0 releases" and "we could not read the page" must not look
    the same in the report."""
    result = press.walk_member(_row(), read_page=_pages(CLIENT_SIDE))
    assert result.releases == []
    assert result.stopped == "empty"
    assert result.complete is False
    assert result.detail == "no dated releases on the first page"


def test_an_archive_that_ends_inside_the_window_is_complete_not_incomplete():
    """A member whose press archive BEGINS after 2023-01-03 can never reach the window's
    start. Calling that INCOMPLETE would print it beside a member collected in full, in
    the one report decision 4 exists to make trustworthy."""
    result = press.walk_member(
        _row(), read_page=_pages(HOUSE_DRUPAL, HOUSE_ASPX_PAGE_2, "<html></html>")
    )
    assert result.stopped == "exhausted"
    assert result.complete is True
    assert result.detail == "archive ends at page 2"


def test_one_page_and_no_page_two_is_reported_as_needing_a_look():
    """`Y000064` yields 20 releases and 404s on `/page/2/`. For a senator over three and a
    half years that is not plausibly their whole output, and a short archive is
    indistinguishable from a "load more" button to a plain GET. Under-claiming
    completeness is the only safe direction in a spend-approval report."""
    result = press.walk_member(_row(), read_page=_pages(HOUSE_DRUPAL, "<html></html>"))
    assert result.stopped == "single-page"
    assert result.complete is False
    assert "load more" in result.detail
    assert len(result.releases) == 2


def test_a_404_on_a_pager_url_is_the_end_of_the_archive_not_a_failed_fetch():
    def read(url: str) -> str:
        if "page=" in url or "/page/" in url:
            raise httpx.HTTPStatusError(
                "404", request=httpx.Request("GET", url), response=httpx.Response(404)
            )
        return HOUSE_DRUPAL

    result = press.walk_member(_row(), read_page=read)
    assert result.stopped == "single-page"
    assert len(result.releases) == 2


def test_a_404_on_the_first_page_is_still_an_error():
    """There is no archive to have ended."""

    def read(url: str) -> str:
        raise httpx.HTTPStatusError(
            "404", request=httpx.Request("GET", url), response=httpx.Response(404)
        )

    result = press.walk_member(_row(), read_page=read)
    assert result.stopped == "error"
    assert result.complete is False


def test_a_non_404_http_status_is_an_error_not_an_ended_archive():
    def read(url: str) -> str:
        if "page=" in url:
            raise httpx.HTTPStatusError(
                "500", request=httpx.Request("GET", url), response=httpx.Response(500)
            )
        return HOUSE_DRUPAL

    result = press.walk_member(_row(), read_page=read)
    assert result.stopped == "error"
    assert "HTTP" in result.detail


def test_the_pager_offset_is_asked_of_the_site_itself():
    """Drupal prints `?page=0` next to `?page=1`, so `?page=1` is the SECOND page.
    `H001081` prints `?page=1` to `?page=14` and no `?page=0`, so `?page=1` IS the first
    page — and guessing wrong cost that member 251 releases, collected 10 deep, because
    the second request returned the first page again."""
    assert press.zero_based_pager('<a href="?page=0">1</a><a href="?page=1">2</a>') is True
    assert press.zero_based_pager('<a href="?page=1">1</a><a href="?page=14">14</a>') is False
    base = "https://x.house.gov/press-releases"
    assert press.page_url(base, 1, zero_based=True) == f"{base}?page=1"
    assert press.page_url(base, 1, zero_based=False) == f"{base}?page=2"


def test_a_one_based_pager_is_walked_without_re_reading_the_first_page():
    """The H001081 regression, end to end, on the FALLBACK path: this page publishes no
    `rel="next"`, no "Next" and no link numbered 2, so the URL is guessed — and page 0
    advertises a 1-based pager, so the guess must be `?page=2` and not `?page=1`."""
    served: list[str] = []
    no_next = HOUSE_DRUPAL.replace('<a href="?page=1" rel="next">Next page</a>', "")

    def read(url: str) -> str:
        served.append(url)
        if "page=" not in url:
            return no_next + '<a href="?page=1">1</a><a href="?page=9">9</a>'
        if "page=2" in url:
            return HOUSE_ASPX_PAGE_2
        return "<html></html>"

    result = press.walk_member(_row(), read_page=read)
    assert "https://bilirakis.house.gov/media/press-releases?page=2" in served
    assert len(result.releases) == 3


def test_a_pager_that_ignores_its_parameter_is_incomplete_not_complete():
    """Re-serving page 1 is a different thing from running off the end of the archive:
    this member is under-collected and the report must say so."""
    result = press.walk_member(_row(), read_page=lambda _url: HOUSE_DRUPAL)
    assert result.stopped == "repeat"
    assert result.complete is False
    assert result.pages_read == 2
    assert len(result.releases) == 2


def test_a_fetch_failure_stops_that_member_and_says_so():
    def boom(url: str) -> str:
        raise httpx.ConnectError("refused")

    result = press.walk_member(_row(), read_page=boom)
    assert result.stopped == "error"
    assert result.complete is False
    assert "ConnectError" in result.detail


def test_a_fetch_failure_mid_walk_keeps_what_was_already_found():
    def read(url: str) -> str:
        if "page=" in url:
            raise OSError("socket died")
        return HOUSE_DRUPAL

    result = press.walk_member(_row(), read_page=read)
    assert result.stopped == "error"
    assert len(result.releases) == 2


def test_limit_pages_is_a_smoke_knob_and_reports_itself_as_incomplete():
    result = press.walk_member(_row(), read_page=lambda _u: HOUSE_DRUPAL, limit_pages=1)
    assert result.stopped == "limit"
    assert result.complete is False
    assert result.detail == "stopped at 1 pages"


def test_the_runaway_guard_caps_a_walk_that_never_reaches_the_window(monkeypatch):
    monkeypatch.setattr(press, "MAX_PAGES", 3)
    pages = [
        f'<a href="/media/press-releases/slug-{i}">A Release Title Number {i} Here</a>'
        f"<span>October {i + 1}, 2026</span>"
        for i in range(3)
    ]
    result = press.walk_member(_row(), read_page=_pages(*pages))
    assert result.stopped == "limit"
    assert result.pages_read == 3


def test_limit_pages_cannot_raise_the_runaway_guard(monkeypatch):
    monkeypatch.setattr(press, "MAX_PAGES", 2)
    result = press.walk_member(_row(), read_page=lambda _u: HOUSE_DRUPAL, limit_pages=99)
    assert result.pages_read <= 2


# --- refusal --------------------------------------------------------------------------


def _sources_yaml(data_dir: Path, rows: list[dict]) -> None:
    (data_dir / "config").mkdir(parents=True, exist_ok=True)
    (data_dir / "config" / "statement-sources.yaml").write_text(
        yaml.safe_dump({"purpose": "test", "members": rows}), encoding="utf-8"
    )


def test_a_row_the_owner_has_not_checked_is_refused_by_id(tmp_path: Path):
    """The source list's own rule: "Collector (a) and (c) must refuse a row that still
    says false." """
    _sources_yaml(
        tmp_path / "data",
        [_row("B001257", checked=True), _row("J000299", checked=False, name="Dusty Johnson")],
    )
    accepted, refused, no_list = press.sources(tmp_path / "data")
    assert [r["id"] for r in accepted] == ["B001257"]
    assert refused == [
        {"id": "J000299", "name": "Dusty Johnson", "reason": "owner_checked: false"}
    ]
    assert no_list == []


def test_a_checked_row_with_no_press_page_is_refused_too(tmp_path: Path):
    """Accepting it would walk `None`."""
    _sources_yaml(tmp_path / "data", [_row("X000001", press_page=None, checked=True)])
    accepted, refused, _ = press.sources(tmp_path / "data")
    assert accepted == []
    assert refused[0]["reason"] == "no press_page"


# --- a row whose site publishes no press-release list (STATUS step 6) -----------------

MILLER_REASON = "site has no press-release list"
MILLER_URLS = [
    "https://maxmiller.house.gov/press-releases",
    "https://maxmiller.house.gov/media/press-releases",
    "https://maxmiller.house.gov/media",
    "https://maxmiller.house.gov/news",
]


def _miller(*, checked: bool = True, **over) -> dict:
    """`M001222` Miller as the owner's own list carries him."""
    return {
        **_row("M001222", name="Max L. Miller", checked=checked),
        "press_page": "https://maxmiller.house.gov/press-releases",
        "no_press_source": True,
        "no_press_reason": MILLER_REASON,
        "no_press_urls_tried": list(MILLER_URLS),
        **over,
    }


def test_the_real_source_list_still_carries_millers_permanent_record():
    """The flag, the reason and the tried URLs are the permanent record of what was
    found; only the interim `owner_checked: false` came out. Read from the owner's own
    file, as data — this asserts the config, not the network."""
    rows = yaml.safe_load(
        (press.repo_root() / "data" / "config" / "statement-sources.yaml").read_text(
            encoding="utf-8"
        )
    )["members"]
    miller = next(r for r in rows if r["id"] == "M001222")
    assert miller["no_press_source"] is True
    assert miller["no_press_reason"] == MILLER_REASON
    assert miller["no_press_urls_tried"] == MILLER_URLS
    assert miller["owner_checked"] is True


@pytest.mark.parametrize("checked", [True, False])
def test_a_row_with_no_press_source_is_neither_accepted_nor_refused(
    tmp_path: Path, checked: bool
):
    """A third outcome. Tested before `owner_checked` and so unchanged by it: "no list
    exists" is a fact about the site, not a stage of screening, and the interim
    `owner_checked: false` that stood in for this flag is gone."""
    _sources_yaml(tmp_path / "data", [_row("B001257"), _miller(checked=checked)])
    accepted, refused, no_list = press.sources(tmp_path / "data")
    assert [r["id"] for r in accepted] == ["B001257"]
    assert refused == []
    assert no_list == [
        {
            "id": "M001222",
            "name": "Max L. Miller",
            "reason": MILLER_REASON,
            "urls_tried": MILLER_URLS,
        }
    ]


def test_a_no_press_source_row_with_no_reason_still_says_what_it_is(tmp_path: Path):
    _sources_yaml(
        tmp_path / "data",
        [_miller(no_press_reason=None, no_press_urls_tried=None)],
    )
    _, _, no_list = press.sources(tmp_path / "data")
    assert no_list[0]["reason"] == "no press-release list"
    assert no_list[0]["urls_tried"] == []


def test_a_missing_source_list_is_a_refusal_not_an_empty_run(tmp_path: Path):
    with pytest.raises(press.PressError, match="no source list"):
        press.sources(tmp_path / "data")


def test_the_window_ends_today():
    from datetime import UTC, datetime

    assert press.window_end(datetime(2026, 10, 14, tzinfo=UTC)) == "2026-10-14"
    assert press.window_end() >= press.WINDOW_START


# --- the report -----------------------------------------------------------------------


def _report(results, rows, refused, text_counts=None, text_phase="full") -> str:
    return press.render_report(
        results,
        rows,
        refused,
        text_counts or {},
        window={"start": press.WINDOW_START, "end": "2026-10-14"},
        text_phase=text_phase,
    )


def test_the_report_names_every_refusal_so_it_is_not_read_as_silence():
    text = _report(
        [],
        [],
        [{"id": "J000299", "name": "Dusty Johnson", "reason": "owner_checked: false"}],
    )
    assert "0 rows collected, 1 refused" in text
    assert "`J000299` Dusty Johnson — owner_checked: false" in text


def test_the_report_marks_an_incomplete_walk_as_a_floor_not_a_total():
    result = press.MemberResult("B001257", [], 1, "empty", "no dated releases on the first page")
    text = _report([result], [_row()], [], text_counts={"B001257": 0})
    assert "INCOMPLETE — empty" in text
    assert "counts are a floor, not a total" in text
    assert "`B001257` Gus M. Bilirakis — **empty**" in text


def test_the_report_says_so_when_every_walk_reached_the_window():
    release = press.Release("B001257", "2026-10-13", "A Title", "https://x/p/a")
    result = press.MemberResult("B001257", [release], 4, "window")
    text = _report([result], [_row()], [], text_counts={"B001257": 1})
    assert "None: every walk reached the window's start." in text
    assert "| complete |" in text
    assert "None." in text  # no refusals


def test_the_report_always_says_why_the_text_column_is_zero():
    result = press.MemberResult("B001257", [], 1, "window")
    index_only = _report([result], [_row()], [], text_phase="none")
    assert "No release bodies were pulled in this run" in index_only
    full = _report([result], [_row()], [], text_phase="full")
    assert "Release bodies were pulled for every release" in full


def test_the_report_counts_per_party():
    release = press.Release("B001257", "2026-10-13", "A Title", "https://x/p/a")
    text = _report(
        [press.MemberResult("B001257", [release], 1, "window")], [_row()], [], {"B001257": 1}
    )
    assert "| R | 1 |" in text


def test_the_report_flags_every_date_conflict_by_row_and_url():
    text = press.render_report(
        [],
        [],
        [],
        {},
        window={"start": press.WINDOW_START, "end": "2026-10-15"},
        text_phase="full",
        date_conflicts=[
            {
                "id": "L000585",
                "url": "https://lahood.house.gov/2026/10/a-slug",
                "detail": "the release page says 2026-09-30, the permalink says 2026-10",
            }
        ],
    )
    assert "## Date conflicts" in text
    assert "`L000585` — the release page says 2026-09-30, the permalink says 2026-10" in text
    assert "<https://lahood.house.gov/2026/10/a-slug>" in text
    assert "WRONG PAGE" in text


def test_the_report_names_what_the_dating_cost_and_every_undatable_release():
    result = press.MemberResult(
        "R000605",
        [],
        1,
        "undated",
        "page 0: 2 release(s), none of which could be dated from their own pages",
        date_failures=[
            {"id": "R000605", "url": FIRST, "error": "no date on release page"},
            {"id": "R000605", "url": SECOND, "error": "ConnectError"},
        ],
        release_page_fetches=2,
    )
    text = _report([result], [_row("R000605", press_page=ROUNDS_LIST, name="Mike Rounds")], [])
    assert "## Release pages read for their dates" in text
    assert "| Mike Rounds (R000605) | 2 | 2 |" in text
    assert f"`R000605` — no date on release page — <{FIRST}>" in text
    assert f"`R000605` — ConnectError — <{SECOND}>" in text
    assert "NEITHER is kept as a release" in text


def test_the_report_says_so_plainly_when_no_date_conflicted():
    assert "None: where a release page published its own date it agreed" in _report([], [], [])


def test_the_report_names_how_page_two_was_found_for_every_row():
    """The guess is wrong on three of the four rows it was measured against, so a row
    still resting on it is a row whose deeper pages are not proven — and the owner reads
    that per row, not as a footnote."""
    linked = press.MemberResult(
        "R000605",
        [],
        2,
        "window",
        page2_method="link",
        page2_url="https://www.rounds.senate.gov/newsroom/press-releases?pagenum_rs=2",
    )
    guessed = press.MemberResult("B001257", [], 2, "window", page2_method="page_url",
                                 page2_url="https://bilirakis.house.gov/p?page=2")
    never = press.MemberResult("H001081", [], 1, "empty", "no dated releases")
    rows = [
        _row("R000605", name="Mike Rounds"),
        _row(),
        _row("H001081", name="Jahana Hayes"),
    ]
    text = _report([linked, guessed, never], rows, [])
    assert "## How page 2 was found, per row" in text
    assert "| Mike Rounds (R000605) | `link` | <https://www.rounds.senate.gov" in text
    assert "| Gus M. Bilirakis (B001257) | `page_url` | <https://bilirakis.house.gov" in text
    assert "| Jahana Hayes (H001081) | `none` | — |" in text


def test_the_report_prints_every_refused_url_with_its_reason():
    """Never silent: the owner decides what counts as a member's own statement, so a URL
    this collector removes from a statement list is printed where it can be argued with."""
    result = press.MemberResult(
        "R000622",
        [],
        1,
        "window",
        url_rejections=[
            {
                "id": "R000622",
                "url": "https://riley.house.gov/news/newsletter-subscribe/",
                "reason": "a `newsletter-subscribe` path segment — a subscribe form, not a release",
            }
        ],
    )
    text = _report([result], [_row("R000622", name="Josh Riley")], [])
    assert "## URLs the release filter refused, and why" in text
    assert "`R000622` — a `newsletter-subscribe` path segment" in text
    assert "<https://riley.house.gov/news/newsletter-subscribe/>" in text


def test_the_report_prints_no_list_exists_with_the_reason_and_every_url_tried():
    """STATUS step 6, the ruling in full: never as empty, never as failed, never counted
    as a collection failure — and the owner's reason and tried URLs are what it prints."""
    text = press.render_report(
        [],
        [],
        [],
        {},
        window={"start": press.WINDOW_START, "end": "2026-10-15"},
        text_phase="full",
        no_list=[
            {
                "id": "M001222",
                "name": "Max L. Miller",
                "reason": MILLER_REASON,
                "urls_tried": MILLER_URLS,
            }
        ],
    )
    assert "0 rows collected, 0 refused, 1 with no press-release list at all." in text
    assert "## No press-release list exists, by id" in text
    assert "not a collection failure and are not counted as one" in text
    assert f"`M001222` Max L. Miller — {MILLER_REASON}. Tried:" in text
    assert "    * <https://maxmiller.house.gov/media/press-releases>" in text
    # Not in the refusals, and not in any walk count.
    assert "`M001222` Max L. Miller — owner_checked" not in text
    assert "INCOMPLETE" not in text


def test_the_report_says_so_plainly_when_every_row_has_a_list():
    assert (
        "None: every row in the source list has a press-release list to read."
        in _report([], [], [])
    )


def test_the_report_says_so_plainly_when_nothing_was_refused():
    assert "None: every release-shaped URL on every page read was collected." in _report(
        [], [], []
    )


# --- the runner -----------------------------------------------------------------------


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo root with a two-row source list and every fetch faked."""
    _sources_yaml(
        tmp_path / "data",
        [_row("B001257", checked=True), _row("J000299", checked=False, name="Dusty Johnson")],
    )
    monkeypatch.setattr(press, "repo_root", lambda: tmp_path)

    def read(url: str) -> str:
        if url.endswith("/media/press-releases"):
            return HOUSE_DRUPAL
        if "/media/press-releases/" in url:
            return RELEASE_PAGE
        return "<html></html>"

    monkeypatch.setattr(press, "_read_page", read)
    return tmp_path


def _index(repo: Path) -> dict:
    return json.loads((repo / "data" / "raw" / "press" / "index.json").read_text(encoding="utf-8"))


def _statements(repo: Path, member_id: str) -> dict:
    path = repo / "data" / "raw" / "press" / "statements" / f"{member_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_run_writes_the_index_the_statements_and_the_report(repo: Path, capsys):
    assert press.run([]) == 0
    out = capsys.readouterr().out
    assert "32 accepted" not in out  # the fixture has one accepted row, not the real 32
    assert "1 accepted rows, 1 refused" in out

    index = _index(repo)
    assert index["accepted"] == 1
    assert index["refused"][0]["id"] == "J000299"
    assert len(index["releases"]) == 2
    assert index["walks"][0]["member_id"] == "B001257"

    statements = _statements(repo, "B001257")
    assert statements["member"]["name"] == "Gus M. Bilirakis"
    # Newest first, like collector (b)'s per-member order.
    assert [s["date"] for s in statements["statements"]] == ["2026-10-13", "2026-09-18"]
    assert statements["statements"][0]["segments"][0].startswith("WASHINGTON, D.C.")

    assert (repo / "docs" / "research" / "2026-10-14-press-collection-counts.md").exists() or list(
        (repo / "docs" / "research").glob("*-press-collection-counts.md")
    )


def test_the_run_records_every_refused_url_in_the_index_and_the_report(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    listing = HOUSE_DRUPAL + (
        '<a href="/media/press-releases/newsletter-subscribe">'
        "Subscribe To Our Weekly Newsletter</a>"
    )

    def read(url: str) -> str:
        if url.endswith("/media/press-releases"):
            return listing
        if "/media/press-releases/" in url:
            return RELEASE_PAGE
        return "<html></html>"

    monkeypatch.setattr(press, "_read_page", read)
    assert press.run([]) == 0
    assert [e["url"] for e in _index(repo)["url_rejections"]] == [
        "https://bilirakis.house.gov/media/press-releases/newsletter-subscribe"
    ]
    assert "URLs refused by the release filter: 1" in capsys.readouterr().out
    report = next((repo / "docs" / "research").glob("*-press-collection-counts.md"))
    assert "newsletter-subscribe" in report.read_text(encoding="utf-8")


MONTH_ONLY_LIST = """
<div class="listing"><a href="/2026/10/a-release-dated-only-in-its-own-permalink">
 A Release Dated Only In Its Own Permalink</a></div>
"""


def _run_with_release_page(repo: Path, monkeypatch, marker: str) -> None:
    def read(url: str) -> str:
        if url.endswith("/media/press-releases"):
            return MONTH_ONLY_LIST
        return marker + RELEASE_PAGE

    monkeypatch.setattr(press, "_read_page", read)
    assert press.run([]) == 0


def test_the_run_upgrades_a_month_only_date_from_the_page_it_already_fetched(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    """Decision 5 at no extra fetch: the body phase has the release page in hand."""
    _run_with_release_page(repo, monkeypatch, META_DATE_SPACED)
    statements = _statements(repo, "B001257")
    assert [s["date"] for s in statements["statements"]] == ["2026-10-07"]
    index = _index(repo)
    assert index["date_conflicts"] == []
    assert [r["date_precision"] for r in index["releases"]] == ["day"]
    assert [r["date_source"] for r in index["releases"]] == ["release-page"]


def test_the_run_writes_the_list_pages_date_and_flags_the_page_that_disagrees(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    """A conflict is reported, never resolved — the stored date stays the permalink's."""
    _run_with_release_page(repo, monkeypatch, '<meta name="date" content="2026-09-30">')
    statements = _statements(repo, "B001257")
    assert [s["date"] for s in statements["statements"]] == ["2026-10"]
    index = _index(repo)
    assert len(index["date_conflicts"]) == 1
    assert index["date_conflicts"][0]["id"] == "B001257"
    assert "2026-09-30" in index["date_conflicts"][0]["detail"]
    assert "date conflicts: 1" in capsys.readouterr().out
    report = next((repo / "docs" / "research").glob("*-press-collection-counts.md"))
    text = report.read_text(encoding="utf-8")
    assert "## Date conflicts" in text
    assert "a-release-dated-only-in-its-own-permalink" in text


def test_index_only_reads_no_release_page_so_no_date_is_upgraded(
    repo: Path, monkeypatch: pytest.MonkeyPatch
):
    """`--index-only` is the no-spend, no-fetch path: the month-only date stands."""
    def read(url: str) -> str:
        if "/2026/" in url:
            raise AssertionError(f"no release page may be fetched: {url}")
        return MONTH_ONLY_LIST if url.endswith("/media/press-releases") else "<html></html>"

    monkeypatch.setattr(press, "_read_page", read)
    assert press.run(["--index-only"]) == 0
    assert [s["date"] for s in _statements(repo, "B001257")["statements"]] == ["2026-10"]


UNDATED_RUN_LIST = """
<div><a href="/media/press-releases/a-release-with-no-date-on-the-list-page">
 A Release With No Date On The List Page At All</a></div>
"""


def test_the_run_dates_an_undated_anchor_and_records_what_it_cost(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    def read(url: str) -> str:
        if url.endswith("/media/press-releases"):
            return UNDATED_RUN_LIST
        if "/media/press-releases/" in url:
            return '<meta name="date" content="2026-10-02">' + RELEASE_PAGE
        return "<html></html>"

    monkeypatch.setattr(press, "_read_page", read)
    assert press.run([]) == 0
    assert [s["date"] for s in _statements(repo, "B001257")["statements"]] == ["2026-10-02"]
    index = _index(repo)
    assert index["release_page_fetches"] == {"B001257": 1}
    assert index["date_failures"] == []
    assert "+1 release pages read for their dates" in capsys.readouterr().out


def test_the_run_records_an_undatable_release_as_a_failure_and_keeps_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    def read(url: str) -> str:
        if url.endswith("/media/press-releases"):
            return UNDATED_RUN_LIST
        if "/media/press-releases/" in url:
            return RELEASE_PAGE  # a real body, and no date marker anywhere on it
        return "<html></html>"

    monkeypatch.setattr(press, "_read_page", read)
    assert press.run([]) == 0
    assert _statements(repo, "B001257")["statements"] == []
    index = _index(repo)
    assert [f["error"] for f in index["date_failures"]] == ["no date on release page"]
    assert "undatable releases: 1" in capsys.readouterr().out
    report = next((repo / "docs" / "research").glob("*-press-collection-counts.md"))
    assert "no date on release page" in report.read_text(encoding="utf-8")


def test_index_only_never_pays_for_a_date(repo: Path, monkeypatch: pytest.MonkeyPatch):
    """The no-spend path: an undated anchor stays undated rather than costing a fetch."""

    def read(url: str) -> str:
        if url.endswith("/media/press-releases"):
            return UNDATED_RUN_LIST
        if "/media/press-releases/" in url:
            raise AssertionError(f"no release page may be fetched: {url}")
        return "<html></html>"

    monkeypatch.setattr(press, "_read_page", read)
    assert press.run(["--index-only"]) == 0
    assert _statements(repo, "B001257")["statements"] == []
    assert _index(repo)["release_page_fetches"] == {}


def test_a_refused_row_is_never_fetched(repo: Path, monkeypatch: pytest.MonkeyPatch):
    seen: list[str] = []
    inner = press._read_page

    def watched(url: str) -> str:
        seen.append(url)
        return inner(url)

    monkeypatch.setattr(press, "_read_page", watched)
    assert press.run([]) == 0
    assert not any("johnson" in url.lower() for url in seen)
    assert not (repo / "data" / "raw" / "press" / "statements" / "J000299.json").exists()


def test_the_run_never_walks_a_row_with_no_press_release_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    """End to end: no fetch, no statements file, no walk, no failure — and the index and
    the report both say "no list exists" with the owner's reason."""
    _sources_yaml(tmp_path / "data", [_row("B001257"), _miller()])
    monkeypatch.setattr(press, "repo_root", lambda: tmp_path)
    seen: list[str] = []

    def read(url: str) -> str:
        seen.append(url)
        if url.endswith("/media/press-releases"):
            return HOUSE_DRUPAL
        if "/media/press-releases/" in url:
            return RELEASE_PAGE
        return "<html></html>"

    monkeypatch.setattr(press, "_read_page", read)
    assert press.run([]) == 0
    out = capsys.readouterr().out
    assert "1 accepted rows, 0 refused, 1 with no press-release list" in out
    assert "no press-release list: 1 row(s) — reported as 'no list exists'" in out
    assert not any("maxmiller" in url for url in seen)
    assert not (tmp_path / "data" / "raw" / "press" / "statements" / "M001222.json").exists()

    index = _index(tmp_path)
    assert index["no_list"] == [
        {
            "id": "M001222",
            "name": "Max L. Miller",
            "reason": MILLER_REASON,
            "urls_tried": MILLER_URLS,
        }
    ]
    assert index["refused"] == []
    assert [w["member_id"] for w in index["walks"]] == ["B001257"]

    report = next((tmp_path / "docs" / "research").glob("*-press-collection-counts.md"))
    text = report.read_text(encoding="utf-8")
    assert f"`M001222` Max L. Miller — {MILLER_REASON}. Tried:" in text
    assert "| Max L. Miller (M001222) |" not in text  # not a row in the per-member table


def test_members_asking_for_a_row_with_no_list_is_told_so_not_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    """"Refusing M001222: owner_checked is not true" was the old, wrong answer. There is
    no refusal here: there is no list on the site to read."""
    _sources_yaml(tmp_path / "data", [_row("B001257"), _miller()])
    monkeypatch.setattr(press, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(press, "_read_page", lambda _url: "<html></html>")
    assert press.run(["--members", "M001222"]) == 0
    out = capsys.readouterr().out
    assert f"no press-release list exists for M001222: {MILLER_REASON}" in out
    assert "refusing" not in out
    assert "0 accepted rows" in out

    # And asking for someone else does not mention him: the line answers the question
    # that was asked, rather than reciting the source list.
    assert press.run(["--members", "B001257"]) == 0
    assert "no press-release list exists for" not in capsys.readouterr().out


def test_members_cannot_force_a_refused_row(repo: Path, capsys):
    """The source list's rule is not a default that a flag may override."""
    assert press.run(["--members", "J000299"]) == 0
    out = capsys.readouterr().out
    assert "refusing J000299: owner_checked is not true" in out
    assert not (repo / "data" / "raw" / "press" / "statements" / "J000299.json").exists()


def test_members_narrows_to_the_accepted_row(repo: Path):
    assert press.run(["--members", "B001257"]) == 0
    assert _index(repo)["accepted"] == 1


def test_members_ignores_blank_entries(repo: Path):
    assert press.run(["--members", "B001257,, "]) == 0
    assert _index(repo)["accepted"] == 1


def test_index_only_fetches_no_release_bodies(repo: Path, monkeypatch: pytest.MonkeyPatch):
    def read(url: str) -> str:
        if "/media/press-releases/" in url:  # pragma: no cover - must not be called
            raise AssertionError("--index-only must not fetch a release body")
        return HOUSE_DRUPAL if url.endswith("/media/press-releases") else "<html></html>"

    monkeypatch.setattr(press, "_read_page", read)
    assert press.run(["--index-only"]) == 0
    assert all(s["segments"] == [] for s in _statements(repo, "B001257")["statements"])


def test_a_release_whose_body_cannot_be_read_is_a_recorded_failure(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    """Under-collecting is visible in the report; silently storing a page's navigation as
    a member's words is not."""

    def read(url: str) -> str:
        if url.endswith("/media/press-releases"):
            return HOUSE_DRUPAL
        if "medicare" in url:
            raise httpx.ConnectError("refused")
        return "<html><body><div>no paragraphs here</div></body></html>"

    monkeypatch.setattr(press, "_read_page", read)
    assert press.run([]) == 0
    failures = _index(repo)["text_failures"]
    assert {f["error"] for f in failures} == {"ConnectError", "no body text"}
    assert "text failures: 3" in capsys.readouterr().out


def test_limit_pages_reaches_the_walk(repo: Path):
    assert press.run(["--limit-pages", "1"]) == 0
    assert _index(repo)["walks"][0]["stopped"] == "limit"


def test_the_collected_output_runs_through_the_prefilter_unchanged(repo: Path):
    """Source-agnostic, end to end: collector (a)'s own files are what the pre-filter
    reads, with no press-specific branch anywhere in it."""
    assert press.run([]) == 0
    records = _statements(repo, "B001257")["statements"]
    result = prefilter.run_prefilter(records)
    assert result["statements_in"] == 2
    assert result["statements_kept"] >= 1
    assert all(s["source"] == "member_press" for s in result["statements"])


def test_a_page_read_goes_through_the_disk_cache(monkeypatch):
    """Every fetch is cached (§6.2), so a re-run of a part-done walk is free and a
    throttled collector does not re-ask a member's server for page 1 forty times."""
    seen: dict = {}

    class _Response:
        text = "<html>cached</html>"

    def fake_fetch(source: str, url: str, **kwargs):
        seen.update({"source": source, "url": url, **kwargs})
        return _Response()

    monkeypatch.setattr(press.cache, "fetch", fake_fetch)
    assert press._read_page("https://x.house.gov/media/press-releases") == "<html>cached</html>"
    assert seen["source"] == press.CACHE_SOURCE
    assert seen["ext"] == "html"
    assert seen["ttl_hours"] == press.CACHE_TTL_HOURS
    # A press list that has moved must not read as an unreadable page.
    assert 301 in seen["accept_status"] and 302 in seen["accept_status"]


def test_a_sitemap_read_goes_through_the_disk_cache_as_xml(monkeypatch):
    """Same cache, same 7-day TTL, same 1/s host throttle as every other fetch — and
    filed as `xml`, so a sitemap is not stored on disk as a page."""
    seen: dict = {}

    class _Response:
        text = "<urlset></urlset>"

    def fake_fetch(source: str, url: str, **kwargs):
        seen.update({"source": source, "url": url, **kwargs})
        return _Response()

    monkeypatch.setattr(press.cache, "fetch", fake_fetch)
    assert press._read_sitemap(KELLY_SITEMAP) == "<urlset></urlset>"
    assert seen["source"] == press.CACHE_SOURCE
    assert seen["ext"] == "xml"
    assert seen["ttl_hours"] == press.CACHE_TTL_HOURS


def test_the_run_collects_a_sitemap_row_through_the_sitemap_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """`K000377` end to end: the sitemap supplies the URLs, each release is dated from
    its own page, and the record that lands is the shape the pre-filter reads."""
    _sources_yaml(tmp_path / "data", [_kelly_row()])
    monkeypatch.setattr(press, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(press, "_read_sitemap", _sitemap_reader())
    monkeypatch.setattr(
        press,
        "_read_page",
        _release_reader(
            {
                "kelly-on-the-newest-thing": "2026-10-13",
                "kelly-on-a-thing-with-no-lastmod": "2026-05-04",
                "kelly-on-a-thing-edited-late": "2026-09-01",
            }
        ),
    )
    assert press.run([]) == 0
    statements = _statements(tmp_path, "K000377")["statements"]
    assert [s["date"] for s in statements] == ["2026-10-13", "2026-09-01", "2026-05-04"]
    assert statements[0]["title"] == "Kelly Introduces The Thing That Happened"
    assert statements[0]["segments"][0].startswith("WASHINGTON, D.C.")
    assert all(s["date_precision"] == "day" for s in statements)
    walk = _index(tmp_path)["walks"][0]
    assert (walk["stopped"], walk["page2_method"]) == ("sitemap", "sitemap")
    assert prefilter.run_prefilter(statements)["statements_kept"] >= 1


def test_the_cli_routes_to_the_press_collector(monkeypatch):
    from ingest import cli

    called: dict = {}

    def _record_argv(argv: list[str]) -> int:
        called["argv"] = argv
        return 0

    monkeypatch.setattr(press, "run", _record_argv)
    assert cli.main(["statements-press", "--index-only"]) == 0
    assert called["argv"] == ["--index-only"]
