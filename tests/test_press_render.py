"""§5 Phase 3 task 2a — the rendered fetch for the press lists a plain GET cannot read.

No network and no Node here. CI's `python` job has no Node at all (`setup-node` runs
only in `site-and-checks`), so a test that spawned the real renderer would fail the §8
gate on a machine that is configured correctly. The subprocess TRANSPORT is still tested
for real, against a Python stub that speaks the same JSON-Lines protocol — which is the
part that can break — while the walk and the report are tested through an injected
reader, the same pattern `statements_press` uses.

What matters most here and is pinned below:
  * a failed render is NEVER cached (a cached empty list would tell the plain collector
    the member published nothing, and stay fresh for a week);
  * `statement-sources.yaml` is never written, and the seven unchecked rows are read
    without being accepted;
  * K000394 cannot be rendered even if asked for by id.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest
import yaml

from ingest import cache, press_render
from ingest import statements_press as press

# A stub renderer: reads {"url": ...} lines, answers from a scripted table, and
# otherwise reports a failure the way the real script does.
STUB = """
import json, sys
TABLE = json.loads(sys.argv[1])
# `for line in sys.stdin` reads a BLOCK, not a line, when stdin is a pipe, so it
# yields nothing until the pipe closes — and the parent is waiting for an answer
# before it closes anything. An explicit readline loop is the only shape that works
# for a request/response protocol; the real renderer's readline interface is
# line-based for the same reason.
while True:
    line = sys.stdin.readline()
    if not line:
        break
    line = line.strip()
    if not line:
        continue
    request = json.loads(line)
    if request.get("more"):
        queue = TABLE.get("__more__") or []
        out = queue.pop(0) if queue else {"ok": False, "error": "no page is open to advance"}
    else:
        url = request["url"]
        if url in TABLE:
            out = dict(TABLE[url]); out["url"] = url
        else:
            out = {"url": url, "ok": False, "status": 404, "error": "HTTP 404"}
    sys.stdout.write(json.dumps(out) + "\\n")
    sys.stdout.flush()
"""

LIST_PAGE = """<!doctype html><html><body><div class="listing">
  <article><a href="/news/one-thing">A Statement On One Thing That Happened</a>
    <time>October 9, 2026</time></article>
  <article><a href="/news/two-thing">A Statement On Another Thing Entirely</a>
    <time>October 2, 2026</time></article>
</div></body></html>"""

OLD_PAGE = """<!doctype html><html><body><div class="listing">
  <article><a href="/news/old-thing">Something From Before The Window Opened</a>
    <time>December 1, 2022</time></article>
</div></body></html>"""

EMPTY_PAGE = "<!doctype html><html><head><title>Press Releases</title></head><body></body></html>"


def _stub_command(table: dict[str, dict]) -> list[str]:
    return [sys.executable, "-c", STUB, json.dumps(table)]


def _sources(
    tmp_path: Path, rows: list[dict] | None = None, *, no_list: tuple[str, ...] = ()
) -> Path:
    """A minimal `statement-sources.yaml` carrying the eleven approved rows."""
    data_dir = tmp_path / "data"
    (data_dir / "config").mkdir(parents=True, exist_ok=True)
    if rows is None:
        rows = [
            {
                "id": member_id,
                "name": f"Member {member_id}",
                "party": "D" if member_id < "M" else "R",
                "chamber": "house",
                "press_page": f"https://{member_id.lower()}.house.gov/news/",
                "owner_checked": member_id in press_render.EMPTY_BY_MARKUP,
            }
            for member_id in press_render.RENDER_ROWS
        ]
    for row in rows:
        if row["id"] in no_list:
            row["no_press_source"] = True
            row["no_press_reason"] = "site has no press-release list"
    (data_dir / "config" / "statement-sources.yaml").write_text(
        yaml.safe_dump({"members": rows}), encoding="utf-8"
    )
    return data_dir


def _row(member_id: str = "R000622", **over) -> dict:
    return {
        "id": member_id,
        "name": f"Member {member_id}",
        "party": "D",
        "chamber": "house",
        "press_page": "https://example.house.gov/news/",
        "owner_checked": False,
        **over,
    }


# --- which rows may be rendered -------------------------------------------------------


def test_the_approved_rows_are_read_including_the_unchecked_ones(tmp_path: Path):
    """An unchecked row is unchecked BECAUSE a plain fetch could not read it. Reading a
    row's URL is not accepting the row."""
    rows = press_render.rows_to_render(_sources(tmp_path))
    assert [r["id"] for r in rows] == list(press_render.RENDER_ROWS)
    assert len(rows) == 8
    assert sum(1 for r in rows if not r["owner_checked"]) == 4


def test_the_rows_that_left_the_render_set_are_recorded_rather_than_deleted():
    """Three rows left on 2026-10-15 because the owner ratified a URL whose page is plain
    HTML — they never needed a browser, they needed the right URL. The record stays so a
    future session can see this was measured."""
    assert set(press_render.LEFT_THE_RENDER_SET) == {"J000299", "M001184", "S001181"}
    assert not set(press_render.LEFT_THE_RENDER_SET) & set(press_render.RENDER_ROWS)
    assert all("2026-10-15" in why for why in press_render.LEFT_THE_RENDER_SET.values())


def test_a_row_with_no_press_release_list_leaves_the_render_set(tmp_path: Path):
    """`M001222` Miller. There is no list to render, and a rendered report that printed
    "STILL EMPTY" beside him is the one label the owner's ruling forbids. Read from the
    owner's own file, so a row marked tomorrow needs no edit in that module."""
    rows = press_render.rows_to_render(_sources(tmp_path, no_list=("M001222",)))
    assert "M001222" not in [r["id"] for r in rows]
    assert len(rows) == 7


def test_asking_by_name_for_a_row_with_no_press_release_list_is_refused_out_loud(
    tmp_path: Path,
):
    """Refused the way `K000394` is refused: by name, with the reason, rather than
    quietly handed back an empty list of rows."""
    data_dir = _sources(tmp_path, no_list=("M001222",))
    with pytest.raises(press_render.RenderError, match="nothing to render: M001222"):
        press_render.rows_to_render(data_dir, ["M001222"])


def test_kim_cannot_be_rendered_even_when_asked_for_by_id(tmp_path: Path):
    """A 403 to a browser User-Agent is a bot wall. The owner put it out of scope and
    this is the code that refuses to go round it."""
    data_dir = _sources(tmp_path)
    with pytest.raises(press_render.RenderError, match="out of scope"):
        press_render.rows_to_render(data_dir, ["K000394"])


def test_an_explicit_subset_renders_only_those_rows(tmp_path: Path):
    rows = press_render.rows_to_render(_sources(tmp_path), ["R000622", "W000830"])
    assert [r["id"] for r in rows] == ["R000622", "W000830"]


def test_an_id_that_is_not_in_the_owners_list_is_an_error(tmp_path: Path):
    with pytest.raises(press_render.RenderError, match="not in the source list"):
        press_render.rows_to_render(_sources(tmp_path), ["Z999999"])


def test_a_row_with_no_press_page_is_an_error_rather_than_a_walk_of_none(tmp_path: Path):
    rows = [_row("R000622", press_page=None)]
    with pytest.raises(press_render.RenderError, match="no press_page"):
        press_render.rows_to_render(_sources(tmp_path, rows), ["R000622"])


def test_a_missing_source_list_says_which_file(tmp_path: Path):
    with pytest.raises(press_render.RenderError, match="no source list"):
        press_render.rows_to_render(tmp_path / "data")


def test_the_renderer_never_writes_the_owners_list(tmp_path: Path):
    data_dir = _sources(tmp_path)
    path = data_dir / "config" / "statement-sources.yaml"
    before = path.read_bytes()
    press_render.rows_to_render(data_dir)
    assert path.read_bytes() == before


# --- the subprocess transport ---------------------------------------------------------


def test_a_page_comes_back_through_the_pipe_intact():
    table = {"https://x/1": {"ok": True, "status": 200, "html": LIST_PAGE}}
    with press_render.Renderer(_stub_command(table)) as renderer:
        assert renderer.render("https://x/1")["html"] == LIST_PAGE


def test_a_renderer_that_cannot_start_says_so():
    with pytest.raises(press_render.RenderError, match="could not start"):
        with press_render.Renderer([str(Path("no-such-binary-zzz"))]):
            pass


def test_a_renderer_that_dies_is_fatal_rather_than_a_page_that_failed():
    """Either side of the race is fatal and says which: the write can find the pipe
    already broken, or it succeeds and the read comes back empty."""
    command = [sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(1)"]
    with press_render.Renderer(command) as renderer:
        with pytest.raises(press_render.RenderError, match="closed its output|died while"):
            renderer.render("https://x/1")


def test_a_renderer_that_accepts_the_request_then_closes_its_output_carries_the_stderr():
    """Deterministically the second half of the race above: the write lands, the read
    comes back empty, and the renderer's own stderr is what explains why."""
    command = [
        sys.executable,
        "-c",
        "import sys, time\n"
        "sys.stdin.readline()\n"
        "sys.stdout.close()\n"
        "sys.stderr.write('playwright blew up')\n"
        "sys.stderr.close()\n"
        "time.sleep(10)\n",
    ]
    monkeypatch = pytest.MonkeyPatch()
    # The stub sleeps so stdout really is closed while it lives; don't sit through it.
    monkeypatch.setattr(press_render, "EXIT_TIMEOUT_S", 0.5)
    try:
        with press_render.Renderer(command) as renderer:
            with pytest.raises(press_render.RenderError, match="playwright blew up"):
                renderer.render("https://x/1")
    finally:
        monkeypatch.undo()


def test_writing_to_a_renderer_that_has_already_exited_is_fatal():
    """The other half: the request cannot even be delivered. Waiting for the child
    first makes the broken pipe certain rather than a race."""
    command = [sys.executable, "-c", "pass"]
    with press_render.Renderer(command) as renderer:
        renderer._proc.wait()
        broken = "died while rendering|closed its output"
        with pytest.raises(press_render.RenderError, match=broken):
            renderer.render("https://x/1")


def test_a_renderer_that_returns_non_json_is_fatal():
    command = [
        sys.executable,
        "-c",
        "import sys\nwhile sys.stdin.readline():\n sys.stdout.write('not json\\n')\n"
        " sys.stdout.flush()",
    ]
    with press_render.Renderer(command) as renderer:
        with pytest.raises(press_render.RenderError, match="non-JSON"):
            renderer.render("https://x/1")


def test_rendering_before_the_session_is_open_is_an_error():
    with pytest.raises(press_render.RenderError, match="not running"):
        press_render.Renderer(_stub_command({})).render("https://x/1")


def test_closing_a_session_that_never_opened_is_harmless():
    press_render.Renderer(_stub_command({})).__exit__()


def test_a_renderer_that_will_not_exit_is_killed(monkeypatch):
    monkeypatch.setattr(press_render, "EXIT_TIMEOUT_S", 0.5)
    command = [sys.executable, "-c", "import time\nwhile True: time.sleep(0.2)"]
    renderer = press_render.Renderer(command)
    with renderer:
        pass  # __exit__ closes stdin; the stub ignores it, so wait() times out.
    assert renderer._proc is None


def test_the_real_renderer_runs_from_site_so_playwright_resolves():
    """The default command is node + the script, run from `site/`, because
    `@playwright/test` lives in site/node_modules."""
    renderer = press_render.Renderer()
    assert renderer.command[0] == "node"
    assert renderer.command[1].endswith("render-press-pages.mjs")
    assert renderer._cwd is not None and renderer._cwd.name == "site"


def test_a_stub_command_brings_its_own_working_directory():
    assert press_render.Renderer(_stub_command({}))._cwd is None


# --- the cache contract ---------------------------------------------------------------


def test_a_rendered_page_is_cached_where_a_plain_fetch_would_look(tmp_path, monkeypatch):
    """The whole point: `statements_press` consumes these unchanged, because it reads
    through `cache.fetch` and finds a fresh entry."""
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    table = {"https://x/1": {"ok": True, "status": 200, "html": LIST_PAGE}}
    stats = press_render.RenderStats()
    with press_render.Renderer(_stub_command(table)) as renderer:
        read_page = press_render.make_read_page(renderer, stats)
        assert read_page("https://x/1") == LIST_PAGE
    key = cache._cache_key("https://x/1", None)
    body, meta_path = cache._paths(press_render.CACHE_SOURCE, key, "html")
    assert body.read_text(encoding="utf-8") == LIST_PAGE
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["renderer"] == "playwright"
    assert meta["status"] == 200
    assert meta["url"] == "https://x/1"
    assert stats.rendered == 1 and stats.cached == 0


def test_a_failed_render_is_never_cached(tmp_path, monkeypatch):
    """A cached empty list would tell the plain collector this member published
    nothing, and would stay fresh for a week."""
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    stats = press_render.RenderStats()
    with press_render.Renderer(_stub_command({})) as renderer:
        read_page = press_render.make_read_page(renderer, stats)
        with pytest.raises(httpx.HTTPStatusError):
            read_page("https://x/missing")
    key = cache._cache_key("https://x/missing", None)
    body, meta_path = cache._paths(press_render.CACHE_SOURCE, key, "html")
    assert not body.exists() and not meta_path.exists()
    assert stats.failed == 1 and stats.rendered == 0


def test_a_404_is_raised_as_the_same_error_a_plain_fetch_raises(tmp_path, monkeypatch):
    """So `walk_member`'s 404-is-the-end-of-the-archive branch fires identically."""
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    with press_render.Renderer(_stub_command({})) as renderer:
        read_page = press_render.make_read_page(renderer, press_render.RenderStats())
        with pytest.raises(httpx.HTTPStatusError) as caught:
            read_page("https://x/page/9")
    assert caught.value.response.status_code == 404


def test_a_render_that_timed_out_is_a_transport_error_not_a_status(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    table = {"https://x/1": {"ok": False, "status": 0, "error": "TimeoutError: slow"}}
    with press_render.Renderer(_stub_command(table)) as renderer:
        read_page = press_render.make_read_page(renderer, press_render.RenderStats())
        with pytest.raises(httpx.ConnectError, match="slow"):
            read_page("https://x/1")


def test_a_cached_page_is_not_rendered_twice(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    cache.store(
        press_render.CACHE_SOURCE, "https://x/1", LIST_PAGE, ext="html",
        renderer=press_render.RENDERER_NAME,
    )
    stats = press_render.RenderStats()
    # An empty stub table: a cache miss here would 404, so a pass proves the hit.
    with press_render.Renderer(_stub_command({})) as renderer:
        read_page = press_render.make_read_page(renderer, stats)
        assert read_page("https://x/1") == LIST_PAGE
    assert stats.cached == 1 and stats.rendered == 0


def test_refresh_re_renders_a_page_already_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    cache.store(
        press_render.CACHE_SOURCE, "https://x/1", "stale", ext="html",
        renderer=press_render.RENDERER_NAME,
    )
    table = {"https://x/1": {"ok": True, "status": 200, "html": LIST_PAGE}}
    stats = press_render.RenderStats()
    with press_render.Renderer(_stub_command(table)) as renderer:
        read_page = press_render.make_read_page(renderer, stats, refresh=True)
        assert read_page("https://x/1") == LIST_PAGE
    assert stats.rendered == 1 and stats.cached == 0


def test_a_plain_get_entry_is_a_miss_so_the_useless_page_is_never_reused(tmp_path, monkeypatch):
    """These rows already HAVE fresh plain-GET entries: the right title and zero dated
    items. Reusing one would report the problem page as a success."""
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    cache.store(press_render.CACHE_SOURCE, "https://x/1", EMPTY_PAGE, ext="html")
    assert press_render._cached_body("https://x/1") is None


def test_a_corrupt_sidecar_is_a_miss_via_the_freshness_check(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    cache.store(
        press_render.CACHE_SOURCE, "https://x/1", LIST_PAGE, ext="html",
        renderer=press_render.RENDERER_NAME,
    )
    key = cache._cache_key("https://x/1", None)
    _, meta_path = cache._paths(press_render.CACHE_SOURCE, key, "html")
    meta_path.write_text("{not json", encoding="utf-8")
    assert press_render._cached_body("https://x/1") is None


def test_a_stale_cache_entry_is_a_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    cache.store(
        press_render.CACHE_SOURCE, "https://x/1", "old", ext="html",
        renderer=press_render.RENDERER_NAME,
    )
    key = cache._cache_key("https://x/1", None)
    _, meta_path = cache._paths(press_render.CACHE_SOURCE, key, "html")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["fetched_at"] = "2020-01-01T00:00:00+00:00"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    assert press_render._cached_body("https://x/1") is None


def test_the_node_binary_goes_through_the_path():
    assert press_render._node_binary() == "node"


# --- clicking the page's own load-more control (step 5) -------------------------------

# A list page with its newest items, and the same shape again with an older batch
# appended — what one click adds.
CLICK_PAGE_1 = """<!doctype html><html><body><div class="listing">
  <article><a href="/news/one-thing">A Statement On One Thing That Happened</a>
    <time>October 9, 2026</time></article>
</div><button class="load-more">Load more</button></body></html>"""

CLICK_PAGE_2 = """<!doctype html><html><body><div class="listing">
  <article><a href="/news/one-thing">A Statement On One Thing That Happened</a>
    <time>October 9, 2026</time></article>
  <article><a href="/news/old-thing">Something From Before The Window Opened</a>
    <time>December 1, 2022</time></article>
</div><button class="load-more">Load more</button></body></html>"""

CONTROL = '<button class="load-more"> "Load more" visible=true'


class _ClickingRenderer:
    """A renderer double that speaks the two-message protocol: one page, then whatever
    each `advance` was scripted to answer."""

    def __init__(self, first: dict, steps: list[dict] | None = None):
        self.first = first
        self.steps = list(steps or [])
        self.advances = 0

    def render(self, _url: str) -> dict:
        return self.first

    def advance(self) -> dict:
        self.advances += 1
        return self.steps.pop(0) if self.steps else {"ok": True, "clicked": False, "grew": False}


def _rendered(html: str, *, anchors: int = 1, templated: int = 0) -> dict:
    return {"ok": True, "status": 200, "html": html, "anchors": anchors, "templated": templated}


def _grew(html: str, anchors: int, *, control: str | None = CONTROL) -> dict:
    return {
        "ok": True,
        "clicked": True,
        "grew": True,
        "anchors": anchors,
        "templated": 0,
        "control": control,
        "nearby": [CONTROL],
        "html": html,
    }


@pytest.fixture()
def cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    return tmp_path


def _click(renderer, row=None, **kw) -> press_render.LoadMore:
    return press_render.click_through(
        renderer, row or _row("S001181"), press_render.RenderStats(), **kw
    )


def test_clicking_stops_when_the_oldest_item_shown_predates_the_window(cached):
    """Stop (a), the owner's first: the list now reaches back past 2023-01-03, so there
    is nothing deeper worth a click."""
    renderer = _ClickingRenderer(_rendered(CLICK_PAGE_1), [_grew(CLICK_PAGE_2, 2)])
    record = _click(renderer)
    assert record.clicks == 1
    assert record.stop == "window"
    assert (record.oldest, record.newest) == ("2022-12-01", "2026-10-09")
    assert (record.anchors_before, record.anchors_after) == (1, 2)
    assert record.failure == ""


def test_clicking_stops_when_the_control_stops_adding_items(cached):
    """Stop (b): the control is still on the page and the list did not grow."""
    renderer = _ClickingRenderer(
        _rendered(CLICK_PAGE_1),
        [{"ok": True, "clicked": True, "grew": False, "control": CONTROL, "nearby": [CONTROL]}],
    )
    record = _click(renderer)
    assert (record.clicks, record.stop) == (0, "exhausted")
    assert record.control == CONTROL
    assert record.failure == ""


def test_a_page_with_no_control_says_so_and_says_what_it_has_instead(cached):
    """The measured answer for all four rows, 2026-10-15. A zero that does not say why
    is indistinguishable from a page nobody looked at."""
    renderer = _ClickingRenderer(
        _rendered(CLICK_PAGE_1),
        [{"ok": True, "clicked": False, "grew": False, "control": None,
          "nearby": ['<div class="jet-smart-filters-pagination"> "" visible=false']}],
    )
    record = _click(renderer)
    assert (record.clicks, record.stop) == (0, "no-control")
    assert record.control == ""
    assert record.failure == "the page has no load-more control to click"
    assert "jet-smart-filters-pagination" in record.nearby[0]


def test_clicking_stops_at_the_click_ceiling(cached):
    """Stop (c). The cap is a config value, and a row that hits it is reported as having
    hit it — step 7's rule then flags it for not reaching 2023-01-03."""
    renderer = _ClickingRenderer(
        _rendered(CLICK_PAGE_1), [_grew(CLICK_PAGE_1, 2), _grew(CLICK_PAGE_1, 3)]
    )
    record = _click(renderer, max_clicks=2)
    assert (record.clicks, record.stop) == (2, "cap")
    assert renderer.advances == 2


def test_a_list_with_no_dates_at_all_can_only_be_stopped_by_the_control_or_the_cap(cached):
    """`S001181` and `K000377` print no date on the list, so stop (a) has nothing to
    read. Those rows are dated from their own release pages later; the clicking does not
    guess a date to stop on."""
    undated = '<a href="/news/a-release-with-no-date-anywhere-near-it">A Release With No Date</a>'
    renderer = _ClickingRenderer(_rendered(undated), [_grew(undated, 2)])
    record = _click(renderer, max_clicks=1)
    assert (record.oldest, record.newest) == ("", "")
    assert (record.clicks, record.stop) == (1, "cap")


def test_a_first_render_that_failed_is_an_error_and_is_never_cached(cached):
    renderer = _ClickingRenderer({"ok": False, "status": 500, "error": "HTTP 500"})
    stats = press_render.RenderStats()
    record = press_render.click_through(renderer, _row("S001181"), stats)
    assert (record.stop, record.detail) == ("error", "HTTP 500")
    assert stats.failed == 1
    assert press_render._cached_body("https://example.house.gov/news/") is None
    assert record.failure.startswith("the renderer could not advance")


def test_an_advance_that_failed_keeps_what_was_already_collected(cached):
    renderer = _ClickingRenderer(
        _rendered(CLICK_PAGE_1), [_grew(CLICK_PAGE_1, 2), {"ok": False, "error": "Timeout"}]
    )
    record = _click(renderer)
    assert (record.clicks, record.stop, record.detail) == (1, "error", "Timeout")
    assert press_render._cached_body("https://example.house.gov/news/") == CLICK_PAGE_1


def test_an_advance_that_grew_without_returning_html_keeps_the_page_it_had(cached):
    """Defensive: the accumulated page is what gets cached, so a step with no HTML must
    not replace it with nothing."""
    renderer = _ClickingRenderer(
        _rendered(CLICK_PAGE_1),
        [{"ok": True, "clicked": True, "grew": True, "anchors": 2, "control": CONTROL}],
    )
    record = _click(renderer, max_clicks=1)
    assert record.clicks == 1
    assert press_render._cached_body("https://example.house.gov/news/") == CLICK_PAGE_1


def test_the_accumulated_page_is_what_the_plain_collector_reads(cached):
    """The contract: every batch the clicking added lands in ONE cached list page, so
    `ingest statements-press` needs no knowledge that a browser was involved."""
    renderer = _ClickingRenderer(_rendered(CLICK_PAGE_1), [_grew(CLICK_PAGE_2, 2)])
    _click(renderer)
    stored = press_render._cached_body("https://example.house.gov/news/")
    assert stored == CLICK_PAGE_2
    assert len(press.extract_releases(stored, "https://example.house.gov/news/", "S001181")) == 2


def test_hrefs_still_holding_a_template_are_the_rows_failure_reason(cached):
    """`K000377`'s `${item.link}`: a page whose links are still markup has not been read,
    and that is reported rather than collected."""
    renderer = _ClickingRenderer(_rendered(CLICK_PAGE_1, templated=8))
    record = _click(renderer, max_clicks=0)
    assert record.templated_hrefs == 8
    assert "8 release link(s) are still unrendered" in record.failure


def test_a_clean_stop_has_no_failure_reason():
    assert press_render.LoadMore(stop="window").failure == ""
    assert press_render.LoadMore(stop="cap").failure == ""


def test_the_click_ceiling_is_a_named_config_value_not_a_number_in_the_loop():
    assert press_render.MAX_LOAD_MORE_CLICKS == 40
    assert press_render.LOAD_MORE_ROWS == ("J000299", "K000377", "M001184", "S001181")


def test_advance_speaks_the_same_protocol_as_render():
    """The transport, for real, against the stub: `{"more": true}` in, one answer out."""
    table = {"__more__": [{"ok": True, "clicked": True, "grew": True, "anchors": 7}]}
    with press_render.Renderer(_stub_command(table)) as renderer:
        assert renderer.advance()["anchors"] == 7
        # The queue is empty now, which is how a renderer with no open page answers.
        assert renderer.advance()["ok"] is False


def test_refresh_does_not_re_render_a_page_this_run_just_built(cached):
    """`--refresh` must not replace a clicked-together list with one unclicked batch —
    the walk would then read one tenth of what was collected."""
    cache.store(
        press_render.CACHE_SOURCE, "https://x/news/", CLICK_PAGE_2, ext="html",
        renderer=press_render.RENDERER_NAME,
    )
    stats = press_render.RenderStats()
    renderer = _ClickingRenderer(_rendered("<html>a single unclicked batch</html>"))
    read = press_render.make_read_page(
        renderer, stats, refresh=True, already_fresh=frozenset({"https://x/news/"})
    )
    assert read("https://x/news/") == CLICK_PAGE_2
    assert stats.cached == 1 and stats.rendered == 0


# --- the walk and the screening report ------------------------------------------------


def test_a_rendered_list_walks_to_the_window_and_screens(tmp_path):
    pages = {
        "https://example.house.gov/news/": LIST_PAGE,
        # `page_url` yields `?page=2` for this shape (not senate.gov, no /category/,
        # and the page carries no `?page=0` marker, so the pager is 1-based).
        "https://example.house.gov/news/?page=2": OLD_PAGE,
    }
    row = _row()
    result = press_render.walk_member(row, read_page=lambda url: pages[url])
    entry = press_render.screen(row, result)
    assert entry["releases"] == 2
    assert entry["stopped"] == "window"
    assert entry["complete"] is True
    assert entry["latest"] == "2026-10-09"
    assert len(entry["sample_titles"]) == 2
    assert entry["sample_titles"][0].startswith("A Statement On One Thing")


def test_a_list_that_still_renders_empty_is_reported_as_such(tmp_path):
    row = _row()
    result = press_render.walk_member(row, read_page=lambda _url: EMPTY_PAGE)
    entry = press_render.screen(row, result)
    assert entry["releases"] == 0
    assert entry["stopped"] == "empty"
    assert entry["earliest"] == "" and entry["latest"] == ""
    assert entry["sample_titles"] == []
    assert entry["reaches_window_start"] is False


def test_walk_rows_reports_progress_and_keeps_going(tmp_path):
    rows = [_row("R000622"), _row("W000830")]
    seen: list[str] = []
    results = press_render.walk_rows(
        rows, read_page=lambda _url: EMPTY_PAGE, progress=seen.append
    )
    assert len(results) == 2
    assert len(seen) == 2 and "R000622" in seen[0]


def test_walk_rows_without_a_progress_callback_is_silent(capsys):
    results = press_render.walk_rows([_row()], read_page=lambda _url: EMPTY_PAGE)
    assert len(results) == 1
    assert capsys.readouterr().out == ""


def test_the_report_separates_the_seven_from_the_four():
    screens = [
        {
            "id": "R000622", "name": "Josh Riley", "party": "D", "chamber": "house",
            "press_page": "https://riley.house.gov/news/", "releases": 40, "pages_read": 5,
            "stopped": "window", "detail": "", "complete": True, "earliest": "2023-02-01",
            "latest": "2026-10-09", "reaches_window_start": False,
            "sample_titles": ["One", "Two"], "owner_checked": True,
            "diagnosis": {"rendered": True, "bytes": 1000, "release_links": 40,
                          "dated_permalinks": 0, "long_dates": 40, "iso_dates": 0,
                          "ordinal_dates": 0, "titles": []},
            "verdict": "collected",
        },
        {
            "id": "S001185", "name": "Terri A. Sewell", "party": "D", "chamber": "house",
            "press_page": "https://sewell.house.gov/press-releases", "releases": 0,
            "pages_read": 1, "stopped": "empty", "detail": "no dated releases",
            "complete": False, "earliest": "", "latest": "",
            "reaches_window_start": False, "sample_titles": [], "owner_checked": False,
            "diagnosis": {"rendered": False}, "verdict": "the page was never rendered",
        },
    ]
    text = press_render.render_report(
        screens, press_render.RenderStats(rendered=6, cached=1, failed=0), window_start="2023-01-03"
    )
    assert "still `owner_checked: false` — these need your screening" in text
    assert "Terri A. Sewell (`S001185`)" in text
    assert "**STILL EMPTY**" in text
    assert "Josh Riley (`R000622`)" in text
    assert "**COLLECTS**" in text
    assert "nothing a render could read" in text
    assert "does not reach the window start" in text
    assert "a floor, not a total" in text
    assert "**complete**" in text
    assert "statement-sources.yaml` was changed" in text
    assert "K000394" in text
    assert "Rendered 6 page(s), 1 already cached, 0 failed" in text


def test_the_report_says_none_when_a_group_is_empty():
    text = press_render.render_report([], press_render.RenderStats(), window_start="2023-01-03")
    assert text.count("*(none)*") == 2


# --- the smoke pass -------------------------------------------------------------------


def test_the_smoke_pass_measures_page_one_before_a_long_walk_is_spent():
    rows = [_row()]
    out = press_render.smoke(rows, read_page=lambda _url: LIST_PAGE)
    assert out[0]["releases"] == 2
    assert out[0]["newest"] == "2026-10-09"
    assert out[0]["oldest"] == "2026-10-02"
    assert out[0]["bytes"] == len(LIST_PAGE)
    assert out[0]["first_title"].startswith("A Statement On One Thing")


def test_the_smoke_pass_records_a_failure_without_stopping():
    def boom(_url: str) -> str:
        raise httpx.ConnectError("nope", request=httpx.Request("GET", "https://x"))

    out = press_render.smoke([_row("R000622"), _row("W000830")], read_page=boom)
    assert len(out) == 2
    assert out[0]["releases"] == 0 and "ConnectError" in out[0]["error"]


# --- the runner -----------------------------------------------------------------------


class _FakeRenderer:
    """Stands in for the Node session in the runner's tests."""

    def __init__(self, pages: dict[str, str]):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return None

    def render(self, url: str) -> dict:
        if url in self.pages:
            return {"url": url, "ok": True, "status": 200, "html": self.pages[url]}
        return {"url": url, "ok": False, "status": 404, "error": "HTTP 404"}

    def advance(self) -> dict:
        """No control on the page — the measured answer for all four load-more rows."""
        return {
            "ok": True,
            "clicked": False,
            "grew": False,
            "control": None,
            "nearby": ['<div class="jet-smart-filters-pagination"> "" visible=false'],
        }


def _runner(tmp_path, monkeypatch, pages: dict[str, str], rows: list[dict] | None = None):
    _sources(tmp_path, rows)
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(press_render, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(press_render, "Renderer", lambda *a, **k: _FakeRenderer(pages))


def test_the_smoke_run_prints_a_line_per_row(tmp_path, monkeypatch, capsys):
    rows = [_row("R000622", press_page="https://x/news/", owner_checked=True)]
    _runner(tmp_path, monkeypatch, {"https://x/news/": LIST_PAGE}, rows)
    assert press_render.run(["--smoke", "--members", "R000622"]) == 0
    out = capsys.readouterr().out
    assert "smoke, page one only" in out
    assert "2 releases" in out
    assert "rendered 1, cached 0, failed 0" in out


def test_the_smoke_run_prints_a_failure_line(tmp_path, monkeypatch, capsys):
    rows = [_row("R000622", press_page="https://x/gone/", owner_checked=True)]
    _runner(tmp_path, monkeypatch, {}, rows)
    assert press_render.run(["--smoke", "--members", "R000622"]) == 0
    assert "FAILED" in capsys.readouterr().out


def test_the_full_run_writes_the_screening_report(tmp_path, monkeypatch, capsys):
    rows = [_row("R000622", press_page="https://x/news/", owner_checked=True)]
    pages = {"https://x/news/": LIST_PAGE, "https://x/news/page/2/": OLD_PAGE}
    _runner(tmp_path, monkeypatch, pages, rows)
    assert press_render.run(["--members", "R000622"]) == 0
    out = capsys.readouterr().out
    assert "statement-sources.yaml NOT touched" in out
    reports = list((tmp_path / "docs" / "research").glob("*-rendered-press.md"))
    assert len(reports) == 1
    assert "Josh Riley" not in reports[0].read_text(encoding="utf-8")  # name comes from the row
    assert "Member R000622" in reports[0].read_text(encoding="utf-8")


def test_the_run_clicks_the_load_more_rows_and_reports_what_it_found(
    tmp_path, monkeypatch, capsys
):
    """End to end on the four rows that have no pager URL at all: the clicking owns page
    one, the walk reads the accumulated page back, and the report says per row how many
    clicks, why it stopped, and what the page has instead of a control."""
    rows = [
        _row("K000377", press_page="https://y/news/", owner_checked=True),
        _row("S001181", press_page="https://x/news/", owner_checked=True),
    ]
    pages = {"https://x/news/": CLICK_PAGE_1, "https://y/news/": CLICK_PAGE_2}
    _runner(tmp_path, monkeypatch, pages, rows)
    assert press_render.run(["--members", "K000377,S001181"]) == 0
    out = capsys.readouterr().out
    assert "S001181   load-more:   0 click(s), no-control" in out
    assert "jet-smart-filters-pagination" in out
    assert "FAILURE: the page has no load-more control to click" in out
    # K000377's first page already reaches past the window, so it stops on (a) with no
    # click and no failure — the branch that prints neither line.
    assert "K000377   load-more:   0 click(s), window" in out
    text = next((tmp_path / "docs" / "research").glob("*-rendered-press.md")).read_text(
        encoding="utf-8"
    )
    assert "* Load-more: **0 click(s)**, stopped on (b) there is no load-more control" in text
    assert "stopped on (a) the oldest item shown is older than the window's start" in text
    assert "**Failure: the page has no load-more control to click**" in text
    assert "What the page has instead, or alongside:" in text


def test_the_run_names_the_row_it_did_not_render_and_leaves_it_out_of_the_report(
    tmp_path, monkeypatch, capsys
):
    """Never silent: a row that leaves the render set says why, and the screening report
    does not carry it at all — the count report accounts for it instead."""
    _sources(tmp_path, no_list=("M001222",))
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(press_render, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(press_render, "Renderer", lambda *a, **k: _FakeRenderer({}))
    assert press_render.run([]) == 0
    out = capsys.readouterr().out
    assert "rendered fetch: 7 row(s)" in out
    assert "not rendered, no press-release list exists: M001222" in out
    text = next((tmp_path / "docs" / "research").glob("*-rendered-press.md")).read_text(
        encoding="utf-8"
    )
    assert "M001222" not in text


def test_the_full_run_defaults_to_every_row_in_the_render_set(tmp_path, monkeypatch, capsys):
    _runner(tmp_path, monkeypatch, {})
    assert press_render.run([]) == 0
    out = capsys.readouterr().out
    assert "8 row(s)" in out


def test_the_run_honours_refresh_and_a_page_limit(tmp_path, monkeypatch, capsys):
    rows = [_row("R000622", press_page="https://x/news/", owner_checked=True)]
    _runner(tmp_path, monkeypatch, {"https://x/news/": LIST_PAGE}, rows)
    assert press_render.run(["--members", "R000622", "--refresh", "--limit-pages", "1"]) == 0
    assert "1 page(s)" in capsys.readouterr().out


# --- why a rendered page yielded nothing ----------------------------------------------

ORDINAL_PAGE = """<!doctype html><html><body><div class="listing">
  <a href="/newsroom/press-releases/heinrich-demands-answers-on-the-reserve">October 13th, 2026
    Heinrich Demands Answers On The Strategic Reserve</a>
  <a href="/newsroom/press-releases/heinrich-leads-a-resolution-today">October 12th, 2026
    Heinrich Leads A Resolution Recognizing The Day</a>
</div></body></html>"""

PERMALINK_PAGE = """<!doctype html><html><body><div class="listing">
  <a href="/2026/10/lahood-urges-a-major-disaster-declaration">LaHood Urges A Presidential Major
    Disaster Declaration</a>
  <a href="/2026/9/lahood-change-act-passes-the-committee">LaHood's CHANGE Act Passes Out Of
    The Committee</a>
</div></body></html>"""

NAV_ONLY_PAGE = """<!doctype html><html><body><nav>
  <a href="/services">Additional Services and Resources</a>
  <a href="/academy">U.S. Service Academy Nominations</a>
</nav></body></html>"""


def _cached_row(tmp_path, monkeypatch, html: str, url: str = "https://x.house.gov/press-releases"):
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    cache.store(
        press_render.CACHE_SOURCE, url, html, ext="html",
        renderer=press_render.RENDERER_NAME,
    )
    return _row("L000585", press_page=url)


def test_a_row_that_was_never_rendered_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "RAW_DIR", tmp_path / "raw")
    d = press_render.diagnose(_row())
    assert d == {"rendered": False}
    assert "never rendered" in press_render.date_verdict(d)


def test_an_ordinal_date_counts_as_a_date_on_the_page(tmp_path, monkeypatch):
    """Since the step-1 regex change `_DATE_LONG` matches "October 13th, 2026" as well as
    "October 13, 2026", so an ordinal date is counted as a date the page carries. The
    ordinal count stays: it still tells the owner which shape the publisher prints."""
    row = _cached_row(tmp_path, monkeypatch, ORDINAL_PAGE)
    d = press_render.diagnose(row)
    assert d["release_links"] == 2
    assert d["ordinal_dates"] == 2
    assert d["long_dates"] == 2
    assert "dates ARE on the page" in press_render.date_verdict(d)


def test_a_row_that_collects_is_not_given_something_standing_in_its_way(tmp_path, monkeypatch):
    """`H001046` Heinrich collects 20 releases since step 1. A report that prints "COLLECTS"
    and then names an obstacle under it contradicts itself where the owner reads it."""
    row = _cached_row(tmp_path, monkeypatch, ORDINAL_PAGE)
    d = press_render.diagnose(row)
    assert press_render.date_verdict(d, collected=True).startswith("nothing —")


def test_a_permalink_only_date_is_no_longer_an_open_owner_decision(tmp_path, monkeypatch):
    """Decision 5 answered it and step 2 reads the permalink date, so the line must no
    longer put the question to the owner a second time. The page's two releases are dated
    from their URLs — one a day, one a month only."""
    row = _cached_row(tmp_path, monkeypatch, PERMALINK_PAGE)
    d = press_render.diagnose(row)
    assert d["release_links"] == 2 and d["dated_permalinks"] == 2
    verdict = press_render.date_verdict(d)
    assert "only in the URL" in verdict
    assert "owner decision 5" in verdict
    assert "Owner decision" not in verdict
    assert [
        (r.date, r.date_precision)
        for r in press.extract_releases(PERMALINK_PAGE, "https://x.house.gov/press-releases", "X")
    ] == [("2026-10", "month"), ("2026-09", "month")]


def test_a_page_with_no_release_links_is_not_blamed_on_dates(tmp_path, monkeypatch):
    row = _cached_row(tmp_path, monkeypatch, NAV_ONLY_PAGE)
    d = press_render.diagnose(row)
    assert d["release_links"] == 0
    assert "not a date problem" in press_render.date_verdict(d)


def test_dates_on_the_page_but_not_near_an_anchor_are_reported_as_such(tmp_path, monkeypatch):
    page = (
        '<!doctype html><html><body><p>Posted October 9, 2026</p>'
        + "<p>filler</p>" * 60
        + '<div><a href="/press-releases/a-statement-about-the-thing">'
        "A Statement About The Thing That Happened</a></div></body></html>"
    )
    row = _cached_row(tmp_path, monkeypatch, page)
    d = press_render.diagnose(row)
    assert d["release_links"] == 1 and d["long_dates"] == 1
    assert "none landed near enough" in press_render.date_verdict(d)


def test_release_links_with_no_date_anywhere_are_reported_as_such(tmp_path, monkeypatch):
    page = (
        '<!doctype html><html><body><div>'
        '<a href="/newsroom/press-releases/rounds-calls-for-a-tax-suspension">'
        "Rounds Calls For A Federal Gas Tax Suspension</a></div></body></html>"
    )
    row = _cached_row(
        tmp_path, monkeypatch, page, url="https://www.rounds.senate.gov/newsroom/press-releases"
    )
    d = press_render.diagnose(row)
    assert d["release_links"] == 1
    assert "NO date anywhere" in press_render.date_verdict(d)


def test_the_diagnosis_caps_its_sample_and_skips_short_titles(tmp_path, monkeypatch):
    links = "".join(
        f'<a href="/2026/10/a-release-number-{i}-about-something">'
        f"A Release Number {i} About Something Specific</a>"
        for i in range(9)
    )
    page = (
        '<!doctype html><html><body><div><a href="/2026/10/x">tiny</a>'
        f"{links}</div></body></html>"
    )
    row = _cached_row(tmp_path, monkeypatch, page)
    d = press_render.diagnose(row)
    assert d["release_links"] == 9  # the 4-character title is skipped
    assert len(d["titles"]) == press_render.SAMPLE_TITLES


def test_the_screening_report_carries_the_verdict_and_the_pages_own_titles(tmp_path, monkeypatch):
    row = _cached_row(tmp_path, monkeypatch, PERMALINK_PAGE)
    result = press_render.walk_member(row, read_page=lambda _u: EMPTY_PAGE)
    entry = press_render.screen(row, result)
    assert entry["releases"] == 0
    # No releases were extracted, so the titles come from the page's own links.
    assert entry["sample_titles"]
    text = press_render.render_report(
        [entry], press_render.RenderStats(), window_start="2023-01-03"
    )
    assert "owner decision 5" in text
    assert "release-shaped link(s)" in text
    assert "LaHood Urges" in text
