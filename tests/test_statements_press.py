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
    """Detected from the list URL, so a redesigned pager cannot silently restart the walk
    at page 1 and collect the newest page over and over."""
    assert press.page_url(list_url, page) == expected


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
    """The H001081 regression, end to end: page 0 advertises a 1-based pager, so the
    walk must ask for `?page=2` second and find new releases."""
    served: list[str] = []

    def read(url: str) -> str:
        served.append(url)
        if "page=" not in url:
            return HOUSE_DRUPAL + '<a href="?page=1">1</a><a href="?page=9">9</a>'
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
    accepted, refused = press.sources(tmp_path / "data")
    assert [r["id"] for r in accepted] == ["B001257"]
    assert refused == [
        {"id": "J000299", "name": "Dusty Johnson", "reason": "owner_checked: false"}
    ]


def test_a_checked_row_with_no_press_page_is_refused_too(tmp_path: Path):
    """Accepting it would walk `None`."""
    _sources_yaml(tmp_path / "data", [_row("X000001", press_page=None, checked=True)])
    accepted, refused = press.sources(tmp_path / "data")
    assert accepted == []
    assert refused[0]["reason"] == "no press_page"


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


def test_the_cli_routes_to_the_press_collector(monkeypatch):
    from ingest import cli

    called: dict = {}

    def _record_argv(argv: list[str]) -> int:
        called["argv"] = argv
        return 0

    monkeypatch.setattr(press, "run", _record_argv)
    assert cli.main(["statements-press", "--index-only"]) == 0
    assert called["argv"] == ["--index-only"]
