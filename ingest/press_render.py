"""Rendered fetch for the press-release lists a plain GET cannot read (STATUS fact 7).

Eleven of the forty pilot rows publish their release list from JavaScript: the HTML a
plain GET returns carries the right `<title>` and ZERO dated items, so
`statements_press.extract_releases` reads nothing and the member brings no press
statements at all. Four of those rows the owner had already accepted and they came back
`empty` from the real run (K000377 Kelly, M001222 Miller, R000622 Riley, W000830
Whitesides); the other seven are still `owner_checked: false` precisely BECAUSE a plain
fetch could not read them — not because their content was screened and failed.

Owner decision, 2026-10-14: render all eleven; `K000394` Kim stays out (a 403 to our
User-Agent AND to a browser one, so it is a bot wall, and no workaround is in scope).

FOUR of those eleven have since left the set, and both reasons are worth keeping:

  * `M001222` Miller — the owner's screening found his site publishes no press-release
    list at all, so `rows_to_render` honours his `no_press_source` flag and drops him.
    There is nothing to render, and "STILL EMPTY" beside a member with no list is the one
    label the ruling forbids.
  * `J000299`, `M001184` and `S001181` — the owner ratified a different URL for each on
    2026-10-15, and the new page is PLAIN HTML. A plain GET now reads all three: 10, 11
    and 20 release-shaped anchors on page one, and page two by the site's own link. They
    never needed a browser; they needed the right URL, and what a render was standing in
    for was a landing page with no pager. See `LEFT_THE_RENDER_SET`.
  * `K000377` — his releases come from the press-release sitemap his own site publishes
    (`press_sitemap`, owner-ratified 2026-10-15), not from the list page whose filter
    widget renders no pager. Rendering that page would spend fourteen seconds on a list
    nobody collects from.

HOW THIS FITS TOGETHER, and why the split is where it is:

  * `site/scripts/render-press-pages.mjs` renders ONE URL at a time and returns the
    HTML. Playwright and its Chromium are already in `site/package.json` for
    `test:e2e`, so the renderer costs no new dependency, and nothing is added here
    either — `subprocess` is stdlib.
  * THIS module owns the walk and the cache write. `page_url`, `zero_based_pager` and
    `extract_releases` are rules with one definition in `statements_press`, and the
    cache key and sidecar shape have one definition in `cache`. Rendering in Node and
    deciding in Python keeps it that way; a pure-Node renderer would have needed a
    second copy of all four.
  * Rendered pages land in the SAME cache a plain fetch writes, so
    `ingest statements_press` consumes them unchanged. It still only ever reads through
    `cache.fetch()` and simply finds a fresh entry waiting.

WHAT THIS MODULE DOES NOT DO:

  * It does not touch `statement-sources.yaml`. It READS the eleven rows (including the
    seven unchecked ones — reading is not accepting) and never writes `owner_checked`.
    Flipping a row is the owner's, after screening the rendered output.
  * It does not fetch release BODIES. List pages only. Bodies for an unscreened row
    would be thousands of fetches against a source the owner has not accepted yet.
  * It never caches a failed render. A timeout is not a page, and a cached empty list
    would serve the plain collector a 7-day-fresh "this member published nothing".
  * It does not decide when to stop clicking a load-more control. The renderer clicks
    once per request and says what changed; `click_through` here decides, because the
    stop is a date rule and the date rules live in `statements_press`.

LOAD-MORE (step 5): four rows have no pager URL to follow at all — `S001181` and
`K000377`, plus `J000299` and `M001184`, whose friendly `/media/press-releases` path
made `page_url` guess `?page=2` and get page one back. For those, `click_through` renders
the list and clicks the page's OWN control until the oldest item shown predates
2023-01-03, the control stops adding items, or `MAX_LOAD_MORE_CLICKS`. Every batch stays
in one accumulated page, and THAT is what goes into the cache — so a plain
`uv run ingest statements-press` reads one list page holding everything and still needs
no knowledge that a browser was involved.

CI cannot run this: the `python` job has no Node, and these are live third-party sites.
The renderer is on-demand, and its cache entries expire on the same 7-day TTL as any
press fetch — so these eleven rows go back to reading `empty` about a week after a
render unless it is re-run. That is recorded in STATUS, not left to memory.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import subprocess
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
import yaml

from ingest import cache
from ingest.cache import repo_root
from ingest.statements_press import (
    _ANCHOR,
    _DATE_ISO,
    _DATE_LONG,
    _DATED_PERMALINK,
    _TAGS,
    CACHE_SOURCE,
    CACHE_TTL_HOURS,
    MIN_TITLE_CHARS,
    WINDOW_START,
    MemberResult,
    _is_release_url,
    date_upper_bound,
    extract_releases,
    flatten,
    walk_member,
)

# The eleven rows the owner approved for a rendered fetch, 2026-10-14. Four were already
# accepted and came back `empty`; seven are unchecked because a plain fetch could not
# read them. K000394 (Kim) is deliberately absent: bot wall, not a rendering problem.
EMPTY_BY_MARKUP = ("K000377", "M001222", "R000622", "W000830")
CLIENT_SIDE_UNCHECKED = ("H001046", "L000585", "R000605", "S001185")

# Rows that have LEFT the render set, with the date and the reason. A record rather than
# a deletion: "a plain GET cannot read this list" was TRUE of each of them, and what
# changed is which URL they point at — so a future session that finds one of these back
# in a client-rendered state can see that this was measured, not assumed.
LEFT_THE_RENDER_SET = {
    "J000299": (
        "owner-ratified 2026-10-15 — /news/documentquery.aspx?DocumentTypeID=27 is plain "
        "HTML: a plain GET extracts 10 dated releases on page one and follows the site's "
        "own 'Next »' to &Page=2 for 10 more"
    ),
    "M001184": (
        "owner-ratified 2026-10-15 — /news/documentquery.aspx?DocumentTypeID=2362 is "
        "plain HTML: 11 dated releases on page one, page two by the site's own link"
    ),
    "S001181": (
        "owner-ratified 2026-10-15 — /news/press is plain HTML: 20 release-shaped "
        "anchors on page one, page two by the site's own link to ?pagenum_rs=2. The "
        "anchors are dated from their own release pages, as `R000605`'s are"
    ),
    "K000377": (
        "owner-ratified 2026-10-15 — collected from `press_sitemap`, the two "
        "press-release sitemaps his own site publishes (1,495 URLs, 1,082 inside the "
        "window), because his list page's filter widget renders no pager to click and "
        "no pager URL to follow"
    ),
}

RENDER_ROWS = tuple(sorted(EMPTY_BY_MARKUP + CLIENT_SIDE_UNCHECKED))
OUT_OF_SCOPE = {"K000394": "403 to our User-Agent and to a browser one — a bot wall"}

RENDERER_SCRIPT = Path("site") / "scripts" / "render-press-pages.mjs"
RENDERER_NAME = "playwright"
# Rendering is ~3-8s a page against a live site, and a list walk is tens of pages per
# member, so a stalled renderer must not hold the whole run. Generous, then fatal.
RENDER_TIMEOUT_S = 120.0
# How long to let the renderer shut down cleanly after its stdin closes before killing
# it. Chromium takes a moment to release its profile directory on Windows, so this is
# generous; a test shrinks it rather than sitting through it.
EXIT_TIMEOUT_S = 30.0
SAMPLE_TITLES = 5

# The rows whose list page is walked by CLICKING its own load-more control, because it
# publishes no pager URL to follow (STATUS build-order step 5).
#
# EMPTY TODAY, and that is the measurement rather than an omission. Four rows were
# screened this way on 2026-10-15 — `J000299`, `K000377`, `M001184`, `S001181` — and not
# one of them had a control to click: 0 clicks, `no-control`, anchors unchanged on all
# four. Each has since been given the source it actually needed, and none of them is a
# clicked list page: the ASPX query list for Johnson and Massie, `/news/press` for
# Shaheen, and the sitemap his own site publishes for Kelly. The clicking stays built and
# tested because the next row that needs it needs only this tuple, and because a
# measurement that found nothing is worth keeping where the next session can see it.
LOAD_MORE_ROWS: tuple[str, ...] = ()

# How many times one row's load-more control may be clicked in a single run. Not a
# magic number and not a limit on the archive: it is how deep a by-hand render goes
# before the owner is asked to approve going deeper. At the 10-20 items a click these
# lists add, 40 clicks is 400-800 releases — more than a year of a senator's output —
# and each click costs a browser round trip of a second or two, so a row that needs more
# than this is a row to decide about rather than to sit through. A row that stops here
# is reported as stopped HERE, and step 7's rule already flags every row that cannot
# reach 2023-01-03.
MAX_LOAD_MORE_CLICKS = 40


class RenderError(RuntimeError):
    """A renderer that could not be started, or died mid-session."""


@dataclass
class RenderStats:
    """What the renderer did, for the report's honesty rather than for logic."""

    rendered: int = 0
    failed: int = 0
    cached: int = 0


class Renderer:
    """A long-lived Node/Playwright subprocess, one URL in, one page out.

    One browser for the whole session: launching Chromium costs seconds, and a list
    walk asks for tens of pages per member. The protocol is JSON Lines so a page's HTML
    (which contains every character a page can contain) survives the pipe intact.
    """

    def __init__(self, command: list[str] | None = None, *, cwd: Path | None = None) -> None:
        root = repo_root()
        self.command = command or [_node_binary(), str(root / RENDERER_SCRIPT)]
        # The real renderer runs from `site/` so `@playwright/test` resolves out of
        # site/node_modules. A test's stub command brings its own cwd (or none).
        self._cwd = cwd if cwd is not None else (root / "site" if command is None else None)
        self._proc: subprocess.Popen[str] | None = None

    def __enter__(self) -> Renderer:
        try:
            self._proc = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self._cwd) if self._cwd else None,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except (OSError, ValueError) as exc:
            raise RenderError(f"could not start the renderer: {exc}") from exc
        return self

    def __exit__(self, *_exc: object) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            # `stdin=PIPE` guarantees proc.stdin; closing it is the renderer's cue to
            # finish, and closing an already-closed pipe is a no-op, not an error.
            proc.stdin.close()
            proc.wait(timeout=EXIT_TIMEOUT_S)
        except (subprocess.TimeoutExpired, OSError):
            proc.kill()

    def render(self, url: str) -> dict[str, Any]:
        """One page. Returns the renderer's own verdict; never raises on a bad page.

        The page stays OPEN in the browser afterwards, which is what `advance` acts on.
        """
        return self._exchange({"url": url}, url)

    def advance(self) -> dict[str, Any]:
        """One more batch on the page `render` left open: the renderer scrolls to the
        bottom, clicks the page's own load-more control if it has one, and reports
        whether the list grew. WHEN to stop is this module's decision, not the
        renderer's — the stop rules are date rules, and those live in one place."""
        return self._exchange({"more": True}, "the open page")

    def _exchange(self, request: dict[str, Any], what: str) -> dict[str, Any]:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdout is None:
            raise RenderError("the renderer is not running")
        try:
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
        except (BrokenPipeError, OSError) as exc:
            raise RenderError(f"the renderer died while rendering {what}: {exc}") from exc
        if not line:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RenderError(f"the renderer closed its output on {what}. stderr: {stderr[:800]}")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise RenderError(f"the renderer returned non-JSON on {what}: {line[:200]}") from exc


def _node_binary() -> str:
    """`node` as the shell would find it. Windows needs the `.exe`-less name to go
    through the PATH lookup, which `subprocess` does for us on both platforms."""
    return "node"


def rows_to_render(data_dir: Path, ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """The approved rows, read straight from the owner's list.

    Deliberately NOT `statements_press.sources()`: that refuses every
    `owner_checked: false` row, which is seven of the eleven here. Reading a row's URL
    is not accepting the row — nothing in this module writes `owner_checked`, and the
    seven stay refused to the plain collector until the owner flips them by hand.

    Two flags ARE honoured, the same way `OUT_OF_SCOPE` honours the owner's ruling on
    `K000394`, because for both of them this module's own page is no longer the row's
    source: `no_press_source` (`M001222` — the site publishes no list at all) and
    `press_sitemap` (`K000377` — his releases come from the sitemap his site publishes,
    not from the list page whose filter widget renders no pager). Asked for by name,
    such a row is refused out loud; present only in the default set — both are among the
    historical eleven — it is dropped, and `run` names it. A rendered report that printed
    "STILL EMPTY" beside either of them would be reporting on a page nobody collects
    from.
    """
    path = data_dir / "config" / "statement-sources.yaml"
    if not path.exists():
        raise RenderError(f"no source list at {path}")
    wanted = set(ids) if ids else set(RENDER_ROWS)
    out_of_scope = wanted & set(OUT_OF_SCOPE)
    if out_of_scope:
        named = ", ".join(f"{i} ({OUT_OF_SCOPE[i]})" for i in sorted(out_of_scope))
        raise RenderError(f"out of scope by owner decision: {named}")
    rows = yaml.safe_load(path.read_text(encoding="utf-8"))["members"]
    # Read from the owner's own file rather than listed here, so a row marked tomorrow
    # needs no second edit in this module to be honoured.
    not_ours = {
        r["id"]: (
            r.get("no_press_reason") or "no press-release list"
            if r.get("no_press_source")
            else "its releases come from the sitemap its own site publishes"
        )
        for r in rows
        if r.get("no_press_source") or r.get("press_sitemap")
    }
    asked_by_name = (set(ids) if ids else set()) & set(not_ours)
    if asked_by_name:
        named = ", ".join(f"{i} ({not_ours[i]})" for i in sorted(asked_by_name))
        raise RenderError(f"nothing to render for: {named}")
    wanted -= set(not_ours)
    found = [r for r in sorted(rows, key=lambda r: r["id"]) if r["id"] in wanted]
    missing = wanted - {r["id"] for r in found}
    if missing:
        raise RenderError(f"not in the source list: {', '.join(sorted(missing))}")
    no_page = [r["id"] for r in found if not r.get("press_page")]
    if no_page:
        raise RenderError(f"no press_page to render: {', '.join(no_page)}")
    return found


@dataclass
class LoadMore:
    """What clicking one row's own load-more control did.

    Every field is in the report, because "0 releases" is the one answer this must never
    give without saying why: a control that was never there, a control that stopped
    adding items, and a cap the owner can raise are three different things, and the
    fourth — `K000377`'s list still holding `${item.link}` templates — is not a
    pagination problem at all.
    """

    clicks: int = 0
    # window — the oldest item shown is now older than 2023-01-03 (owner's stop a);
    # exhausted — the control stopped adding items (b); no-control — there was none to
    # click (b, and the `nearby` list says what the page has instead); cap — the click
    # ceiling (c); error — the renderer could not do it.
    stop: str = "not-attempted"
    detail: str = ""
    anchors_before: int = 0
    anchors_after: int = 0
    control: str = ""
    nearby: list[str] = field(default_factory=list)
    # Hrefs still carrying an unresolved `${...}` template after the renderer waited for
    # them. `K000377`'s failure reason, in a number.
    templated_hrefs: int = 0
    oldest: str = ""
    newest: str = ""
    seconds: float = 0.0

    @property
    def failure(self) -> str:
        """The row's failure reason in one line, or "" where there is none."""
        if self.templated_hrefs:
            return (
                f"{self.templated_hrefs} release link(s) are still unrendered "
                "`${...}` templates — the page never finished building its list"
            )
        if self.stop == "no-control":
            return "the page has no load-more control to click"
        if self.stop == "error":
            return f"the renderer could not advance the page: {self.detail}"
        return ""


def _date_span(html: str, list_url: str, member_id: str) -> tuple[str, str]:
    """The oldest and newest date the LIST page itself can date, as the publisher wrote
    them, ordered by UPPER bound — the same comparison the walk makes, so a month-only
    `2023-01` is never read as older than the window it sits inside.

    Both are "" for a list that prints no date at all (`S001181`, `R000605`): those rows
    are dated from their own release pages later, and the clicking cannot use a date it
    does not have. That is reported, not guessed around.
    """
    releases = extract_releases(html, list_url, member_id)
    if not releases:
        return "", ""
    by_bound = sorted(releases, key=lambda r: date_upper_bound(r.date))
    return by_bound[0].date, by_bound[-1].date


def click_through(
    renderer: Renderer,
    row: dict[str, Any],
    stats: RenderStats,
    *,
    window_start: str = WINDOW_START,
    max_clicks: int = MAX_LOAD_MORE_CLICKS,
) -> LoadMore:
    """Render one row's list and click its OWN load-more control until the window is
    reached, the control stops adding items, or the cap.

    The accumulated page — every batch the clicking added — is what goes into the cache,
    so `ingest statements-press` reads one list page holding everything and needs no
    knowledge that a browser was involved. That is the same contract the unclicked
    renders already keep.

    The three stops are the owner's, 2026-10-15: (a) the oldest date shown is before
    2023-01-03, (b) the control disappears or stops adding items, (c) `max_clicks`. (a)
    is decided HERE rather than in the renderer because it is a date rule, and the date
    rules — month-only precision, comparison by upper bound — have one definition, in
    `statements_press`. The renderer clicks once per request and reports what changed.
    """
    url = row["press_page"]
    started = time.monotonic()
    record = LoadMore()
    first = renderer.render(url)
    if not first.get("ok"):
        stats.failed += 1
        record.stop = "error"
        record.detail = str(first.get("error") or "render failed")
        record.seconds = round(time.monotonic() - started, 1)
        return record
    stats.rendered += 1
    html = first.get("html") or ""
    record.anchors_before = int(first.get("anchors") or 0)
    record.anchors_after = record.anchors_before
    record.templated_hrefs = int(first.get("templated") or 0)
    while True:
        record.oldest, record.newest = _date_span(html, url, row["id"])
        if record.oldest and date_upper_bound(record.oldest) < window_start:
            record.stop = "window"
            break
        if record.clicks >= max_clicks:
            record.stop = "cap"
            break
        step = renderer.advance()
        if not step.get("ok"):
            record.stop = "error"
            record.detail = str(step.get("error") or "advance failed")
            break
        record.control = step.get("control") or record.control
        record.nearby = step.get("nearby") or record.nearby
        if not step.get("grew"):
            # The control is gone, or was never there. Those read differently in the
            # report: one is an archive that ended, the other is a page we cannot page.
            record.stop = "exhausted" if step.get("control") else "no-control"
            record.detail = str(step.get("error") or "")
            break
        record.clicks += 1
        html = step.get("html") or html
        record.anchors_after = int(step.get("anchors") or 0)
        record.templated_hrefs = int(step.get("templated") or 0)
    cache.store(
        CACHE_SOURCE,
        url,
        html,
        ext="html",
        status=int(first.get("status") or 200),
        renderer=RENDERER_NAME,
    )
    record.seconds = round(time.monotonic() - started, 1)
    return record


def make_read_page(
    renderer: Renderer,
    stats: RenderStats,
    *,
    refresh: bool = False,
    already_fresh: frozenset[str] = frozenset(),
) -> Callable[[str], str]:
    """A `read_page` for `walk_member` that renders instead of plain-fetching.

    Cache first, so re-running a walk after a crash costs nothing and so the same page
    is never rendered twice inside one walk. On a miss the renderer produces it and the
    body lands in the cache through `cache.store`, which is what later lets the plain
    collector read it.

    A non-OK status is raised as the `httpx.HTTPStatusError` a plain fetch would raise,
    so `walk_member`'s existing branches — 404 on page >= 1 is the end of the archive,
    anything else is an error — fire exactly as they do for a plain GET. A page that
    could not be rendered at all is NEVER cached.

    `already_fresh` names URLs this run has just produced, which `--refresh` must not
    re-render: a load-more row's list page was built by `click_through` out of every
    batch it clicked, and rendering it again would replace that with a single unclicked
    batch — the walk would then read one tenth of what was collected.
    """

    def read_page(url: str) -> str:
        if not refresh or url in already_fresh:
            cached = _cached_body(url)
            if cached is not None:
                stats.cached += 1
                return cached
        result = renderer.render(url)
        if not result.get("ok"):
            stats.failed += 1
            status = int(result.get("status") or 0)
            detail = result.get("error") or "render failed"
            request = httpx.Request("GET", url)
            if status >= 400:
                raise httpx.HTTPStatusError(
                    f"{status} {detail}",
                    request=request,
                    response=httpx.Response(status, request=request),
                )
            raise httpx.ConnectError(detail, request=request)
        html = result.get("html") or ""
        cache.store(
            CACHE_SOURCE,
            url,
            html,
            ext="html",
            status=int(result.get("status") or 200),
            renderer=RENDERER_NAME,
        )
        stats.rendered += 1
        return html

    return read_page


def _cached_body(url: str) -> str | None:
    """The cached RENDERED page for `url`, or None.

    A plain-GET entry is deliberately a MISS. These eleven rows already have fresh
    plain-GET entries from the real collector run — pages with the right `<title>` and
    zero dated items, which is the whole problem — so accepting any cached body here
    would hand back the useless page and report it as a success. Only an entry the
    renderer wrote (`"renderer": "playwright"` in the sidecar) counts, which is what
    that field is for.
    """
    key = cache._cache_key(url, None)
    data_path, meta_path = cache._paths(CACHE_SOURCE, key, "html")
    if not (cache._fresh(meta_path, CACHE_TTL_HOURS) and data_path.exists()):
        return None
    # `_fresh` has already parsed the sidecar, so an unreadable one is a miss before
    # this line and does not need handling twice.
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("renderer") != RENDERER_NAME:
        return None
    return data_path.read_text(encoding="utf-8")


_ORDINAL_DATE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November"
    r"|December)\.?\s+\d{1,2}(?:st|nd|rd|th),?\s+20\d\d\b",
    re.IGNORECASE,
)


def diagnose(row: dict[str, Any]) -> dict[str, Any]:
    """Why a rendered page yielded what it yielded, read back off the cache.

    A row that renders 150 KB and extracts nothing is not self-explanatory, and the
    owner is being asked to screen these — so the report has to distinguish "the
    renderer failed", "the list is not on the page even rendered", and "the list is
    there but every item is missing the one thing the extractor requires: a date".

    `extract_releases` deliberately skips an anchor with no date rather than guessing
    one, because a statement whose date is a guess cannot be compared against a vote.
    That rule is doing exactly what it should here; what it reveals is that these
    pages carry their dates somewhere it does not look.
    """
    url = row["press_page"]
    key = cache._cache_key(url, None)
    data_path, _ = cache._paths(CACHE_SOURCE, key, "html")
    if not data_path.exists():
        return {"rendered": False}
    html = data_path.read_text(encoding="utf-8")
    flat = flatten(html)
    shaped, permalink, titles = 0, 0, []
    for match in _ANCHOR.finditer(flat):
        title = html_lib.unescape(_TAGS.sub("", match.group(2))).strip()
        candidate = urljoin(url, html_lib.unescape(match.group(1)))
        if len(title) < MIN_TITLE_CHARS or not _is_release_url(candidate, url):
            continue
        shaped += 1
        if _DATED_PERMALINK.search(candidate):
            permalink += 1
        if len(titles) < SAMPLE_TITLES:
            titles.append(title)
    return {
        "rendered": True,
        "bytes": len(html),
        "release_links": shaped,
        "dated_permalinks": permalink,
        "long_dates": len(_DATE_LONG.findall(flat)),
        "iso_dates": len(_DATE_ISO.findall(flat)),
        "ordinal_dates": len(_ORDINAL_DATE.findall(flat)),
        "titles": titles,
    }


def date_verdict(d: dict[str, Any], collected: bool = False) -> str:
    """One line naming what stands between this row and collection."""
    if not d.get("rendered"):
        return "the page was never rendered"
    if collected:
        return "nothing — the rendered page reads, and this row collects from it"
    if d["release_links"] == 0:
        return (
            "**the release list is still not in the page, even rendered** — no link on it "
            "has the shape of a release, so this is not a date problem"
        )
    if d["long_dates"] or d["iso_dates"]:
        return (
            f"{d['release_links']} release links and dates ARE on the page "
            f"({d['long_dates']} long, {d['iso_dates']} ISO), but none landed near enough "
            "to an anchor for the extractor to attach"
        )
    if d["dated_permalinks"]:
        # Owner decision 5 answered the question this line used to ask, and step 2 reads
        # the permalink date — so no date stands in the way of these rows any more. What
        # can still leave one empty is the window: a list whose newest release predates
        # 2023-01-03 collects nothing, and `Walk stopped` is where that is reported.
        return (
            f"{d['release_links']} release links, {d['dated_permalinks']} of them dated "
            "**only in the URL** (`/2026/10/…`), which counts as the release's own date "
            "(owner decision 5) — so the date is not what stands in the way here"
        )
    return f"{d['release_links']} release links and NO date anywhere on the page"


def screen(
    row: dict[str, Any], result: MemberResult, load_more: LoadMore | None = None
) -> dict[str, Any]:
    """What the owner needs to screen one row: the list's URL, what came back, a few
    titles in the source's own words, and how far back the walk actually reached."""
    dates = sorted(r.date for r in result.releases)
    diag = diagnose(row)
    # With no extracted releases there are no release titles, but the page's own
    # release-shaped links still carry them — which is what the owner screens.
    titles = [r.title for r in result.releases][:SAMPLE_TITLES] or diag.get("titles", [])
    return {
        "id": row["id"],
        "name": row["name"],
        "party": row.get("party", "?"),
        "chamber": row.get("chamber", "?"),
        "press_page": row["press_page"],
        "releases": len(result.releases),
        "pages_read": result.pages_read,
        "stopped": result.stopped,
        "detail": result.detail,
        "complete": result.complete,
        "earliest": dates[0] if dates else "",
        "latest": dates[-1] if dates else "",
        "reaches_window_start": bool(dates) and dates[0] <= WINDOW_START,
        "sample_titles": titles,
        "owner_checked": bool(row.get("owner_checked")),
        # Why the row yielded what it did, so a zero is explained rather than asserted.
        "diagnosis": diag,
        "verdict": date_verdict(diag, collected=bool(result.releases)),
        # Absent for the rows that page by URL; present for the four that can only go
        # deeper by clicking (`LOAD_MORE_ROWS`).
        "load_more": asdict(load_more) if load_more is not None else None,
        "load_more_failure": load_more.failure if load_more is not None else "",
    }


def render_report(screens: list[dict[str, Any]], stats: RenderStats, *, window_start: str) -> str:
    """The screening report. One section per row, because the owner is deciding row by
    row and a table cannot hold five titles legibly."""
    checked = [s for s in screens if s["owner_checked"]]
    unchecked = [s for s in screens if not s["owner_checked"]]
    lines = [
        "# Rendered press lists — the eleven rows a plain GET cannot read",
        "",
        f"Rendered {stats.rendered} page(s), {stats.cached} already cached, "
        f"{stats.failed} failed. Window start `{window_start}`.",
        "",
        "Playwright rendered these list pages and the HTML went into the same cache a "
        "plain fetch writes, so `ingest statements-press` consumes it unchanged. "
        "**Nothing in `statement-sources.yaml` was changed, and no release body was "
        "fetched for an unscreened row.**",
        "",
        "`K000394` (Kim) is out of scope by owner decision: a 403 to our User-Agent and "
        "to a browser one is a bot wall, not a rendering problem.",
        "",
        "## The seven still `owner_checked: false` — these need your screening",
        "",
        "These were never rejected on content. They are unchecked because a plain fetch "
        "returned a page with zero dated items, so there was nothing to screen. Here is "
        "what each list actually contains now that it renders.",
        "",
    ]
    lines.extend(_row_sections(unchecked))
    lines += [
        "## The four already accepted, which came back `empty` from the real run",
        "",
        "`owner_checked` is already true on these, so a plain `statements-press` run "
        "will collect them from the cache with no further decision.",
        "",
    ]
    lines.extend(_row_sections(checked))
    return "\n".join(lines) + "\n"


def _row_sections(screens: list[dict[str, Any]]) -> list[str]:
    if not screens:
        return ["*(none)*", ""]
    lines: list[str] = []
    for s in screens:
        verdict = "COLLECTS" if s["releases"] else "STILL EMPTY"
        lines += [
            f"### {s['name']} (`{s['id']}`) — {s['party']} {s['chamber']} — **{verdict}**",
            "",
            f"* List: <{s['press_page']}>",
            f"* Releases in the window: **{s['releases']}** over {s['pages_read']} page(s)",
            f"* Dates: {s['earliest'] or '—'} to {s['latest'] or '—'}"
            + ("" if s["reaches_window_start"] else " (does not reach the window start)"),
            f"* What stands in the way: {s['verdict']}",
            f"* Walk stopped: `{s['stopped']}`"
            + (f" — {s['detail']}" if s["detail"] else "")
            + (" — **complete**" if s["complete"] else " — **a floor, not a total**"),
        ]
        d = s["diagnosis"]
        if d.get("rendered"):
            lines.append(
                f"* Rendered {d['bytes']:,} bytes carrying {d['release_links']} "
                f"release-shaped link(s); dates on the page: {d['long_dates']} long, "
                f"{d['ordinal_dates']} ordinal, {d['iso_dates']} ISO, "
                f"{d['dated_permalinks']} in permalinks"
            )
        lm = s.get("load_more")
        if lm:
            stop = {
                "window": "(a) the oldest item shown is older than the window's start",
                "exhausted": "(b) the control stopped adding items",
                "no-control": "(b) there is no load-more control on the page",
                "cap": f"(c) the {MAX_LOAD_MORE_CLICKS}-click ceiling",
                "error": "the renderer could not advance the page",
                "not-attempted": "not attempted",
            }.get(lm["stop"], lm["stop"])
            lines.append(
                f"* Load-more: **{lm['clicks']} click(s)**, stopped on {stop}; anchors "
                f"{lm['anchors_before']} → {lm['anchors_after']}; "
                f"{lm['seconds']}s of renderer time"
            )
            lines.append(f"    * Control: {lm['control'] or '*none found*'}")
            if s["load_more_failure"]:
                lines.append(f"    * **Failure: {s['load_more_failure']}**")
            if lm["nearby"]:
                lines.append("    * What the page has instead, or alongside:")
                lines.extend(f"        * `{n}`" for n in lm["nearby"])
        if s["sample_titles"]:
            lines.append("* What the list contains:")
            lines.extend(f"    {i + 1}. {t}" for i, t in enumerate(s["sample_titles"]))
        else:
            lines.append("* What the list contains: nothing a render could read")
        lines.append("")
    return lines


def walk_rows(
    rows: list[dict[str, Any]],
    *,
    read_page: Callable[[str], str],
    limit_pages: int = 0,
    progress: Callable[[str], None] | None = None,
) -> list[MemberResult]:
    """Walk each row's list with the injected reader. One member's failure never stops
    the others: a renderer that died is fatal, a page that would not render is not."""
    results: list[MemberResult] = []
    for index, row in enumerate(rows, start=1):
        result = walk_member(row, read_page=read_page, limit_pages=limit_pages)
        results.append(result)
        if progress:
            progress(
                f"  [{index}/{len(rows)}] {result.member_id:9} {len(result.releases):4} releases "
                f"over {result.pages_read:3} page(s)  {result.stopped}"
            )
    return results


def smoke(
    rows: list[dict[str, Any]], *, read_page: Callable[[str], str]
) -> list[dict[str, Any]]:
    """Page one only, per row, so the shape is measured before a long walk is spent.

    What it answers: does the page render at all, and does the extractor read the
    rendered shape? Those are the two assumptions the full walk rests on.
    """
    out: list[dict[str, Any]] = []
    for row in rows:
        entry: dict[str, Any] = {"id": row["id"], "url": row["press_page"]}
        try:
            html = read_page(row["press_page"])
        except (httpx.HTTPError, RenderError) as exc:
            entry |= {"error": f"{type(exc).__name__}: {exc}", "releases": 0, "bytes": 0}
            out.append(entry)
            continue
        releases = extract_releases(html, row["press_page"], row["id"])
        entry |= {
            "bytes": len(html),
            "releases": len(releases),
            "newest": max((r.date for r in releases), default=""),
            "oldest": min((r.date for r in releases), default=""),
            "first_title": releases[0].title if releases else "",
        }
        out.append(entry)
    return out


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ingest press-render")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="page one only per row, to measure the shape before spending a full walk",
    )
    parser.add_argument("--members", default="", help="comma-separated ids (default: all eleven)")
    parser.add_argument("--limit-pages", type=int, default=0, help="stop each walk after N pages")
    parser.add_argument(
        "--refresh", action="store_true", help="re-render even pages already cached"
    )
    parser.add_argument(
        "--max-clicks",
        type=int,
        default=MAX_LOAD_MORE_CLICKS,
        help=f"load-more clicks per row (default {MAX_LOAD_MORE_CLICKS})",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    data_dir = root / "data"
    ids = [m.strip() for m in args.members.split(",") if m.strip()] or None
    rows = rows_to_render(data_dir, ids)
    stats = RenderStats()

    print(f"rendered fetch: {len(rows)} row(s)" + (" — smoke, page one only" if args.smoke else ""))
    dropped = sorted(set(ids or RENDER_ROWS) - {r["id"] for r in rows})
    if dropped:
        # Never silent: a row that leaves the render set says why it left.
        print(
            f"  not rendered, this page is not their source: {', '.join(dropped)} "
            "— the count report accounts for these"
        )
    clicked: dict[str, LoadMore] = {}
    with Renderer() as renderer:
        if not args.smoke:
            # The load-more rows first: clicking OWNS their first page, and writes the
            # accumulated list into the cache for the walk below to read back.
            for row in [r for r in rows if r["id"] in LOAD_MORE_ROWS]:
                record = click_through(renderer, row, stats, max_clicks=args.max_clicks)
                clicked[row["id"]] = record
                # ASCII only: this console is cp1252 and an arrow kills the whole run.
                print(
                    f"  {row['id']:9} load-more: {record.clicks:3} click(s), "
                    f"{record.stop:12} anchors {record.anchors_before} -> "
                    f"{record.anchors_after}  {record.seconds}s"
                )
                print(f"    control: {record.control or 'none found'}")
                for line in record.nearby:
                    print(f"    nearby:  {line}")
                if record.failure:
                    print(f"    FAILURE: {record.failure}")
        read_page = make_read_page(
            renderer,
            stats,
            refresh=args.refresh,
            already_fresh=frozenset(r["press_page"] for r in rows if r["id"] in clicked),
        )
        if args.smoke:
            for entry in smoke(rows, read_page=read_page):
                if "error" in entry:
                    print(f"  {entry['id']:9} FAILED  {entry['error'][:90]}")
                else:
                    print(
                        f"  {entry['id']:9} {entry['bytes']:>8} bytes  "
                        f"{entry['releases']:3} releases  "
                        f"{entry['oldest'] or '—'}..{entry['newest'] or '—'}  "
                        f"{entry['first_title'][:50]}"
                    )
            print(f"  rendered {stats.rendered}, cached {stats.cached}, failed {stats.failed}")
            return 0
        results = walk_rows(
            rows, read_page=read_page, limit_pages=args.limit_pages, progress=print
        )

    screens = [
        screen(row, result, clicked.get(row["id"]))
        for row, result in zip(rows, results, strict=True)
    ]
    report = render_report(screens, stats, window_start=WINDOW_START)
    out = root / "docs" / "research" / f"{datetime.now(UTC).date().isoformat()}-rendered-press.md"
    cache.atomic_write_text(out, report)
    print(f"  rendered {stats.rendered}, cached {stats.cached}, failed {stats.failed}")
    print(f"  report: {out.relative_to(root)}")
    print("  statement-sources.yaml NOT touched. The seven stay refused until the owner flips.")
    return 0
