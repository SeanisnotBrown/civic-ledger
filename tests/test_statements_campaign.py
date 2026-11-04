"""§5 Phase 3 task 2c — collector (c), campaign issue pages. No network in this file.

The properties under test are the ones that decide whether a member's page tells the
truth: a URL nobody accounts for is refused, an office page is never filed as something a
member ran on, a domain that changed hands is not read as the member's words, every outcome
that is not a statement stays visible by id, no date is invented, and the record shape is
the one the pre-filter reads.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import yaml

from ingest import cache, prefilter, triage_run
from ingest import statements_campaign as campaign
from ingest.cache import RetryableHTTPError

MARK = "copilot-authored, not reviewed by Sean"
LONG = "Rivera will fight to lower the price of insulin for every family in the district."
LONG2 = "Rivera backs a federal permit reform bill so that clean power lines get built faster."


def _row(member_id: str = "R000001", **over) -> dict:
    row = {
        "id": member_id,
        "name": "Ana M. Rivera",
        "party": "D",
        "chamber": "house",
        "state": "CA",
        "campaign_site": "https://riveraforcongress.com/",
        "campaign_issues_page": "https://riveraforcongress.com/issues/",
        "campaign_cycle": "2026",
        "campaign_source": MARK,
    }
    row.update(over)
    return row


def _page(body: str, head: str = "<title>Rivera for Congress</title>") -> str:
    return f"<html><head>{head}</head><body><nav><a href='/x'>x</a></nav>{body}</body></html>"


SINGLE = _page(f"<h2>Health Care</h2><p>{LONG}</p><h2>Energy</h2><div>{LONG2}</div>")


def _reader(pages: dict[str, str]):
    def read(url: str) -> str:
        return pages[url]

    return read


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://riveraforcongress.com/issues/")
    return httpx.HTTPStatusError("no", request=request, response=httpx.Response(status))


# --- reading a page -------------------------------------------------------------------


def test_the_title_tag_and_the_legal_line_are_not_the_members_words():
    long_title = "Priorities | Ana Rivera for Congress | Fighting for the Central Valley every day"
    html = _page(
        f"<p>{LONG}</p><p>Paid for by Rivera for Congress, and not by any corporate PAC.</p>",
        head=f"<title>{long_title}</title>",
    )
    assert campaign.text_blocks(campaign._body(html)) == [LONG]


def test_the_legal_words_inside_a_position_are_the_members_words():
    position = "Rivera says the new benefit must be paid for by closing the carried interest gap."
    assert campaign.text_blocks(f"<p>{position}</p>") == [position]


def test_a_line_under_the_real_length_is_not_a_block():
    assert campaign.text_blocks("<p>Read more</p><li>" + LONG + "</li>") == [LONG]


def test_text_in_a_bare_div_or_a_list_item_is_read():
    assert campaign.text_blocks(f"<div>{LONG}</div><ul><li>{LONG2}</li></ul>") == [LONG, LONG2]


def test_a_fragment_starts_the_read_at_its_anchor():
    html = _page(f'<p>{LONG}</p><a id="Issues"></a><h2>Energy</h2><p>{LONG2}</p>')
    found = campaign.sections(html, fragment="Issues", page_title="Home")
    assert found == [campaign.Section("Energy", LONG2)]


def test_a_fragment_the_page_does_not_carry_reads_the_whole_page():
    found = campaign.sections(SINGLE, fragment="missing", page_title="Home")
    assert [s.title for s in found] == ["Health Care", "Energy"]


def test_a_repeat_is_kept_once_and_the_longest_copy_wins():
    teaser = LONG[:70] + "..."
    assert campaign._without_repeats([teaser, LONG, LONG2, LONG]) == [LONG, LONG2]


def test_each_heading_opens_a_statement_and_text_above_them_is_the_pages_own():
    html = _page(f"<p>{LONG}</p><h3>Energy</h3><p>{LONG2}</p>")
    assert campaign.sections(html, page_title="On the Issues") == [
        campaign.Section("On the Issues", LONG),
        campaign.Section("Energy", LONG2),
    ]


def test_a_summary_opens_a_statement_like_a_heading():
    html = _page(
        f"<details><summary>Health</summary><p>{LONG}</p></details>"
        f"<details><summary>Energy</summary><p>{LONG2}</p></details>"
    )
    assert [s.title for s in campaign.sections(html)] == ["Health", "Energy"]


def test_an_empty_heading_leaves_its_text_where_it_was():
    html = _page(f'<h2>Health</h2><h2><img src="a.png"></h2><p>{LONG}</p><h2>Energy</h2>'
                 f"<p>{LONG2}</p>")
    assert campaign.sections(html) == [
        campaign.Section("Health", LONG),
        campaign.Section("Energy", LONG2),
    ]


def test_a_repeated_title_is_one_section():
    html = _page(f"<h3>Health</h3><p>{LONG}</p><h3>Energy</h3><p>{LONG2}</p>"
                 f"<h3>Health</h3><p>{LONG}</p>")
    assert campaign.sections(html) == [
        campaign.Section("Health", LONG),
        campaign.Section("Energy", LONG2),
    ]


def test_a_page_with_no_headings_splits_on_short_lines():
    html = _page(f"<p><strong>Health</strong></p><p>{LONG}</p><p>See below:</p>"
                 f"<p>Paid for by Rivera for Congress, and by nobody else in the whole state.</p>"
                 f"<p><strong>Energy</strong></p><p>{LONG2}</p>")
    assert campaign.sections(html, page_title="Issues") == [
        campaign.Section("Health", LONG),
        campaign.Section("Energy", LONG2),
    ]


def test_on_a_page_with_headings_a_short_line_opens_nothing():
    html = _page(f"<h2>Health</h2><p>{LONG}</p><p>Read more</p><p>{LONG2}</p><h2>Energy</h2>"
                 f"<p>{LONG2} More.</p>")
    assert [s.title for s in campaign.sections(html)] == ["Health", "Energy"]


def test_a_page_with_nothing_of_real_length_has_no_sections():
    assert campaign.sections(_page("<h2>Issues</h2><p>Coming soon</p>")) == []


def test_a_page_with_one_section_and_no_short_lines_keeps_it():
    assert campaign.sections(_page(f"<p>{LONG}</p>"), page_title="Issues") == [
        campaign.Section("Issues", LONG)
    ]


def test_a_block_on_most_sub_pages_is_furniture():
    pages = [[LONG, "own one"], [LONG, "own two"], [LONG, "own three"], ["own four"]]
    assert campaign.furniture(pages) == {LONG}


def test_a_block_shared_by_a_few_pages_is_not_furniture():
    assert campaign.furniture([[LONG], [LONG], ["other"]]) == set()


# --- sub-pages ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://a.com/issues/", ("issue", "issue", "priority")),
        ("https://a.com/priorities", ("priority", "issue", "priority")),
        ("https://a.com/issues.html", ("issue", "issue", "priority")),
        ("https://a.com/#Issues", ("issue", "issue", "priority")),
        ("https://a.com/", ("issue", "priority")),
    ],
)
def test_a_lists_sub_pages_share_its_own_name(url, expected):
    assert campaign._stems(url) == expected


def test_sub_pages_are_this_lists_own_links_once_each():
    html = _page(
        '<a href="/issues/health">Health</a>'
        '<a href="/issues/health/">Health again</a>'
        '<a href="https://www.riveraforcongress.com/issue/energy/">Energy</a>'
        '<a href="/issues-taxes">Taxes</a>'
        '<a href="/issues/">The list itself</a>'
        '<a href="/donate">Donate</a>'
        '<a href="https://other.com/issues/health">Someone else</a>'
        '<a href="/issues/plan.pdf">A file</a>'
        '<a href="/issues/page/2">A pager</a>'
    )
    assert campaign.sub_page_urls(html, "https://riveraforcongress.com/issues/") == [
        "https://riveraforcongress.com/issues/health",
        "https://www.riveraforcongress.com/issue/energy/",
        "https://riveraforcongress.com/issues-taxes",
    ]


def test_one_matching_link_is_not_an_index():
    html = _page('<a href="/issues/health">Health</a>')
    assert campaign.sub_page_urls(html, "https://riveraforcongress.com/issues/") == []


def test_a_menu_is_not_an_index():
    html = '<nav><a href="/issues/a">a</a><a href="/issues/b">b</a></nav>'
    assert campaign.sub_page_urls(html, "https://riveraforcongress.com/issues/") == []


# --- the record -----------------------------------------------------------------------


def test_the_record_is_the_shape_the_prefilter_reads_and_carries_no_invented_date():
    record = campaign.statement_record(
        _row(), url="https://riveraforcongress.com/issues/", title="Health", text=LONG,
        section="health", page_marker_date="2016-05-11", retrieved="2026-11-04",
    )
    assert record["date"] == ""
    assert record["date_precision"] == campaign.UNDATED
    assert record["page_marker_date"] == "2016-05-11"
    assert record["retrieved"] == "2026-11-04"
    assert record["granule_id"] == "/issues#health"
    assert record["segments"] == [LONG] and record["chars"] == len(LONG)
    assert record["attribution"] == "campaign-site"
    assert record["source"] == campaign.SOURCE
    assert record["campaign_source"] == MARK and record["campaign_cycle"] == "2026"
    survivor, drops = prefilter.apply_to_statement(record, {})
    assert survivor is not None and drops == []
    assert triage_run.statement_text(survivor) == LONG


def test_a_sub_page_record_is_keyed_on_its_path():
    record = campaign.statement_record(
        _row(campaign_cycle=None), url="https://riveraforcongress.com/", title="t", text=LONG
    )
    assert record["granule_id"] == "/" and record["campaign_cycle"] == ""


# --- the walk -------------------------------------------------------------------------


def test_a_single_page_walk_gives_one_statement_per_issue():
    url = "https://riveraforcongress.com/issues/"
    result = campaign.walk_member(_row(), read_page=_reader({url: SINGLE}), retrieved="d")
    assert result.layout == "single" and result.stopped == "complete"
    assert [r["title"] for r in result.records] == ["Health Care", "Energy"]
    assert [r["granule_id"] for r in result.records] == ["/issues#health-care", "/issues#energy"]
    assert result.pages_read == 1


def test_a_fragment_is_not_sent_and_narrows_the_read():
    row = _row(campaign_issues_page="https://riveraforcongress.com/#Issues")
    html = _page(f'<p>{LONG}</p><div id="Issues"><h2>Energy</h2><p>{LONG2}</p></div>')
    result = campaign.walk_member(
        row, read_page=_reader({"https://riveraforcongress.com/": html})
    )
    assert [r["title"] for r in result.records] == ["Energy"]


def _index(n: int = 2) -> dict[str, str]:
    base = "https://riveraforcongress.com/issues/"
    links = "".join(f'<a href="/issues/p{i}">Page {i}</a>' for i in range(n))
    pages = {base: _page(f"<p>{LONG} Teaser.</p>{links}")}
    for i in range(n):
        pages[f"{base}p{i}"] = _page(f"<h1>Issue {i}</h1><p>{LONG} Page {i}.</p>")
    return pages


def test_an_index_walk_reads_each_sub_page_and_drops_the_teasers():
    result = campaign.walk_member(_row(), read_page=_reader(_index()))
    assert result.layout == "index" and result.pages_read == 3
    assert [r["title"] for r in result.records] == ["Issue 0", "Issue 1"]
    assert all("Teaser" not in r["segments"][0] for r in result.records)


def test_a_title_still_escaped_in_its_marker_reads_as_text():
    html = _page(f"<p>{LONG}</p>", head='<meta property="og:title" content="A &mdash; B">')
    assert campaign._title(html) == "A — B"


def test_sub_pages_named_in_the_row_beat_the_links():
    base = "https://riveraforcongress.com/"
    pages = {
        f"{base}issues/": _page('<a href="/donate">Donate</a>'),
        f"{base}healthcare/": _page(f"<h1>Healthcare</h1><p>{LONG}</p>"),
    }
    row = _row(campaign_issue_pages=[f"{base}healthcare/"])
    result = campaign.walk_member(row, read_page=_reader(pages))
    assert [r["url"] for r in result.records] == [f"{base}healthcare/"]


def test_furniture_is_cut_from_every_sub_page():
    base = "https://riveraforcongress.com/issues/"
    pages = _index(4)
    for i in range(4):
        pages[f"{base}p{i}"] = _page(f"<h1>Issue {i}</h1><p>{LONG2}</p><p>{LONG} Page {i}.</p>")
    result = campaign.walk_member(_row(), read_page=_reader(pages))
    assert len(result.records) == 4
    assert all(LONG2 not in r["segments"][0] for r in result.records)


def test_a_sub_page_that_was_all_furniture_is_a_recorded_failure():
    base = "https://riveraforcongress.com/issues/"
    pages = _index(4)
    pages[f"{base}p3"] = _page(f"<p>{LONG2}</p>")
    for i in range(3):
        pages[f"{base}p{i}"] = _page(f"<p>{LONG2}</p><p>{LONG} Page {i}.</p>")
    result = campaign.walk_member(_row(), read_page=_reader(pages))
    assert len(result.records) == 3
    assert result.text_failures == [
        {"id": "R000001", "url": f"{base}p3", "error": "no body text"}
    ]


def test_the_runaway_guard_caps_an_index(monkeypatch):
    monkeypatch.setattr(campaign, "MAX_SUB_PAGES", 2)
    result = campaign.walk_member(_row(), read_page=_reader(_index(3)))
    assert result.limit_hit is True and len(result.records) == 2


def test_a_403_on_the_list_is_blocked_and_not_a_silent_member():
    def read(url: str) -> str:
        raise _status_error(403)

    result = campaign.walk_member(_row(), read_page=read)
    assert (result.stopped, result.detail) == ("blocked", "HTTP 403")
    assert result.records == [] and result.pages_read == 0


@pytest.mark.parametrize(
    ("exc", "stopped", "detail"),
    [
        (_status_error(429), "blocked", "HTTP 429"),
        (_status_error(404), "error", "HTTP 404"),
        (RetryableHTTPError("503"), "error", "RetryableHTTPError"),
        (httpx.ConnectError("no"), "error", "ConnectError"),
    ],
)
def test_every_other_failure_keeps_its_name(exc, stopped, detail):
    assert campaign._failure(exc) == (stopped, detail)


def test_a_domain_that_changed_hands_is_not_read_as_the_members_words():
    url = "https://riveraforcongress.com/issues/"
    casino = _page("<h2>Bonus</h2><p>" + "Spin the wheel and collect a welcome bonus today. " * 3
                   + "</p>", head="<title>Lucky Casino</title>")
    result = campaign.walk_member(_row(), read_page=_reader({url: casino}))
    assert result.stopped == "not-named" and result.records == []
    assert url in result.detail


def test_a_failed_sub_page_is_recorded_and_the_walk_goes_on():
    base = "https://riveraforcongress.com/issues/"
    pages = _index(4)
    pages[f"{base}p1"] = _page("<p>No name here at all, only the words of somebody else.</p>",
                               head="<title>Other</title>")

    def read(url: str) -> str:
        if url == f"{base}p0":
            raise _status_error(403)
        return pages[url]

    result = campaign.walk_member(_row(), read_page=read)
    assert result.stopped == "complete" and len(result.records) == 2
    assert result.text_failures == [
        {"id": "R000001", "url": f"{base}p0", "error": "HTTP 403"},
        {"id": "R000001", "url": f"{base}p1", "error": "not-named"},
    ]


def test_a_200_with_nothing_of_real_length_is_empty_not_silent():
    url = "https://riveraforcongress.com/issues/"
    result = campaign.walk_member(
        _row(), read_page=_reader({url: _page("<div id='root'></div>")})
    )
    assert result.stopped == "empty" and result.records == []


# --- configuration --------------------------------------------------------------------


def _config(data_dir: Path, rows: list[dict]) -> None:
    path = data_dir / "config" / "statement-sources.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"members": rows}), encoding="utf-8")


def test_no_source_list_stops_the_run(tmp_path: Path):
    with pytest.raises(campaign.CampaignError, match="no source list"):
        campaign.sources(tmp_path)


def test_every_row_is_read_skipped_or_refused_with_its_reason(tmp_path: Path):
    _config(tmp_path, [
        _row("A000001"),
        _row("B000002", campaign_site=None, campaign_issues_page=None, campaign_source=None),
        _row("C000003", campaign_issues_page=None),
        _row("D000004", campaign_issues_page="https://rivera.house.gov/issues"),
        _row("E000005", campaign_source=None),
        _row("F000006", campaign_issue_pages=["https://www.rivera.senate.gov/issues"]),
    ])
    accepted, skipped, refused = campaign.sources(tmp_path)
    assert [r["id"] for r in accepted] == ["A000001"]
    assert [(s["id"], s["reason"]) for s in skipped] == [
        ("B000002", "no campaign site found"),
        ("C000003", "campaign site has no issues page"),
    ]
    assert [r["id"] for r in refused] == ["D000004", "E000005", "F000006"]
    assert "collector (a)" in refused[0]["reason"]
    assert "campaign_source" in refused[1]["reason"]


def test_a_row_the_owner_never_checked_is_still_read_because_that_flag_is_about_press(
    tmp_path: Path,
):
    _config(tmp_path, [_row(owner_checked=False)])
    accepted, _, _ = campaign.sources(tmp_path)
    assert len(accepted) == 1


def _shipped() -> tuple[str, list[dict]]:
    text = (campaign.repo_root() / "data" / "config" / "statement-sources.yaml").read_text(
        encoding="utf-8"
    )
    return text, yaml.safe_load(text)["members"]


def test_the_shipped_list_marks_every_campaign_line_as_unreviewed():
    text, rows = _shipped()
    assert all(row["campaign_source"] == MARK for row in rows)
    lines = [
        line for line in text.splitlines()
        if line.startswith(("  campaign_site:", "  campaign_issues_page:", "  campaign_cycle:"))
    ]
    assert len(lines) == 3 * len(rows)
    assert all(f"# {MARK}" in line for line in lines)


def test_every_null_in_the_shipped_list_says_why():
    text, _ = _shipped()
    nulls = [
        line for line in text.splitlines()
        if line.startswith("  campaign_site: null")
        or line.startswith("  campaign_issues_page: null")
    ]
    bare_after_a_null_site = 2  # the two rows with no site state it on `campaign_site`
    assert sum(f"# {MARK}: " in line for line in nulls) == len(nulls) - bare_after_a_null_site


def test_the_shipped_list_holds_no_office_address():
    _, rows = _shipped()
    urls = [
        url
        for row in rows
        for url in (row["campaign_site"], row["campaign_issues_page"],
                    *(row.get("campaign_issue_pages") or []))
        if url
    ]
    assert urls and not [u for u in urls if ".gov" in u]


# --- the report -----------------------------------------------------------------------


def test_the_report_accounts_for_every_row_and_prints_no_text():
    done = campaign.MemberResult(member_id="A000001", layout="single", pages_read=1)
    done.records = [campaign.statement_record(_row("A000001"), url="https://a.com/x",
                                              title="t", text=LONG)]
    done.text_failures = [{"id": "A000001", "url": "https://a.com/y", "error": "HTTP 403"}]
    done.limit_hit = True
    wall = campaign.MemberResult(member_id="B000002", stopped="blocked", detail="HTTP 403")
    dark = campaign.MemberResult(member_id="C000003", stopped="empty", pages_read=1)
    report = campaign.render_report(
        [done, wall, dark],
        [_row("A000001"), _row("B000002", party="R", campaign_cycle=None), _row("C000003")],
        [{"id": "D000004", "name": "Skip", "party": "R", "reason": "no campaign site found"}],
        [{"id": "E000005", "name": "Refuse", "party": "D", "reason": "a .gov address"}],
        generated="2026-11-04",
    )
    assert f"**URL provenance: {MARK}.**" in report
    assert f"| D | 2 | 1 | 1 | {len(LONG)} | 0 | 1 | 0 | 1 |" in report
    assert "| R | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 0 |" in report
    assert "blocked: HTTP 403" in report
    assert "1 sub-page(s) unread; stopped at the 60-page guard" in report
    assert "Skip (`D000004`, R): no campaign site found" in report
    assert "Refuse (`E000005`, D): a .gov address" in report
    assert "`A000001` https://a.com/y: HTTP 403" in report
    assert "not a member with no positions" in report
    assert LONG not in report


def test_a_report_with_nothing_to_skip_prints_no_empty_sections():
    report = campaign.render_report([], [], [], [], generated="2026-11-04")
    assert "**URL provenance: no URLs.**" in report
    assert "## Skipped" not in report and "## Refused" not in report
    assert "## Sub-pages unread" not in report


# --- the run --------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _config(tmp_path / "data", [
        _row("A000001"),
        _row("B000002", party="R", campaign_issues_page="https://blocked.com/issues"),
        _row("C000003", campaign_site=None, campaign_issues_page=None),
    ])
    monkeypatch.setattr(campaign, "repo_root", lambda: tmp_path)

    def read(url: str) -> str:
        if url == "https://blocked.com/issues":
            raise _status_error(403)
        return SINGLE

    monkeypatch.setattr(campaign, "_read_page", read)
    return tmp_path


def test_the_run_writes_the_shape_the_prefilter_loads_and_a_report(repo: Path, capsys):
    assert campaign.run([]) == 0
    data = repo / "data"
    records, parties, names = prefilter.load_all(data)
    assert [r["member_id"] for r in records] == ["A000001", "A000001"]
    assert parties == {"A000001": "D"} and names == {"A000001": "Ana M. Rivera"}
    index = json.loads((data / "raw" / "campaign" / "index.json").read_text(encoding="utf-8"))
    assert index["window"] == campaign.WINDOW
    assert [w["stopped"] for w in index["walks"]] == ["complete", "blocked"]
    assert [s["id"] for s in index["skipped"]] == ["C000003"]
    assert not (data / "raw" / "campaign" / "statements" / "B000002.json").exists()
    reports = list((repo / "docs" / "research").glob("*-campaign-collection-counts.md"))
    assert len(reports) == 1
    printed = capsys.readouterr().out
    assert "2 rows to read, 1 null, 0 refused" in printed
    assert "<-- blocked: HTTP 403" in printed


def test_members_narrows_the_run_and_cannot_read_a_refused_row(repo: Path, capsys):
    assert campaign.run(["--members", "A000001, C000003"]) == 0
    assert "1 rows to read" in capsys.readouterr().out


def test_a_page_is_read_through_the_cache(monkeypatch: pytest.MonkeyPatch):
    seen: dict = {}

    def fetch(source, url, **kwargs):
        seen.update(source=source, url=url, **kwargs)
        return cache.CachedResponse(path=Path("x"), text="<p>ok</p>", status=200,
                                    from_cache=False, ext="html")

    monkeypatch.setattr(campaign.cache, "fetch", fetch)
    assert campaign._read_page("https://a.com/") == "<p>ok</p>"
    assert seen == {"source": "campaign", "url": "https://a.com/", "ext": "html",
                    "ttl_hours": campaign.CACHE_TTL_HOURS}
