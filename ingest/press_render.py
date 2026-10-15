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
from collections.abc import Callable, Iterable
from dataclasses import dataclass
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
    extract_releases,
    flatten,
    walk_member,
)

# The eleven rows the owner approved for a rendered fetch, 2026-10-14. Four were already
# accepted and came back `empty`; seven are unchecked because a plain fetch could not
# read them. K000394 (Kim) is deliberately absent: bot wall, not a rendering problem.
EMPTY_BY_MARKUP = ("K000377", "M001222", "R000622", "W000830")
CLIENT_SIDE_UNCHECKED = (
    "H001046",
    "J000299",
    "L000585",
    "M001184",
    "R000605",
    "S001181",
    "S001185",
)
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
        """One page. Returns the renderer's own verdict; never raises on a bad page."""
        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdout is None:
            raise RenderError("the renderer is not running")
        try:
            proc.stdin.write(json.dumps({"url": url}) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
        except (BrokenPipeError, OSError) as exc:
            raise RenderError(f"the renderer died while rendering {url}: {exc}") from exc
        if not line:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RenderError(f"the renderer closed its output on {url}. stderr: {stderr[:800]}")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise RenderError(f"the renderer returned non-JSON on {url}: {line[:200]}") from exc


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
    found = [r for r in sorted(rows, key=lambda r: r["id"]) if r["id"] in wanted]
    missing = wanted - {r["id"] for r in found}
    if missing:
        raise RenderError(f"not in the source list: {', '.join(sorted(missing))}")
    no_page = [r["id"] for r in found if not r.get("press_page")]
    if no_page:
        raise RenderError(f"no press_page to render: {', '.join(no_page)}")
    return found


def make_read_page(
    renderer: Renderer, stats: RenderStats, *, refresh: bool = False
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
    """

    def read_page(url: str) -> str:
        if not refresh:
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


def screen(row: dict[str, Any], result: MemberResult) -> dict[str, Any]:
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
    args = parser.parse_args(argv)

    root = repo_root()
    data_dir = root / "data"
    ids = [m.strip() for m in args.members.split(",") if m.strip()] or None
    rows = rows_to_render(data_dir, ids)
    stats = RenderStats()

    print(f"rendered fetch: {len(rows)} row(s)" + (" — smoke, page one only" if args.smoke else ""))
    with Renderer() as renderer:
        read_page = make_read_page(renderer, stats, refresh=args.refresh)
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

    screens = [screen(row, result) for row, result in zip(rows, results, strict=True)]
    report = render_report(screens, stats, window_start=WINDOW_START)
    out = root / "docs" / "research" / f"{datetime.now(UTC).date().isoformat()}-rendered-press.md"
    cache.atomic_write_text(out, report)
    print(f"  rendered {stats.rendered}, cached {stats.cached}, failed {stats.failed}")
    print(f"  report: {out.relative_to(root)}")
    print("  statement-sources.yaml NOT touched. The seven stay refused until the owner flips.")
    return 0
