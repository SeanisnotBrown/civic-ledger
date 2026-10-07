"""Official member photographs (P2 task 6).

Source: the `unitedstates/images` project, which republishes the photographs the
Government Publishing Office distributes for members of Congress, named by
Bioguide ID. The photographs are public domain (GPO), and the project dedicates
its own files under CC0 1.0. Source and licence are recorded in
`docs/data-contract.md`.

    https://unitedstates.github.io/images/congress/{size}/{bioguide}.jpg

Why not `ingest.cache.fetch`: that cache stores decoded text and is the right
door for every JSON/YAML/XML source. A JPEG is bytes, so this module keeps its
own raw cache under the same `data/raw/` tree and the same rule (§1 rule 4 —
nothing is parsed before it has been written to disk, and a file already on disk
is never re-fetched), with the same polite 1 request/second ceiling.

Two copies on purpose:
  * `data/raw/photos/{bioguide}.jpg` — the cache. Gitignored; a re-run is free.
  * `site/public/photos/{bioguide}.jpg` — the published copy the site serves.

The roster covers two Congresses and the project does not carry a photograph for
every one of those members. A 404 is an ordinary outcome, recorded and skipped:
the member page then renders their initials. Nothing about a missing photograph
is an error, so a missing one never fails the run.

Size: 225x275, the smallest the project publishes. The member header renders at
90x110 CSS pixels, so this is still above 2x, and it keeps both the repository
and the deployed asset bundle small.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from ingest.cache import repo_root

SOURCE_URL = "https://unitedstates.github.io/images/congress/{size}/{bioguide}.jpg"
PROJECT_URL = "https://github.com/unitedstates/images"
SIZE = "225x275"
MIN_INTERVAL_SECONDS = 1.0
_TIMEOUT = httpx.Timeout(30.0, connect=15.0)
_USER_AGENT = "civic-ledger/0.0 (+https://github.com/SeanisnotBrown/civic-ledger)"


def raw_dir() -> Path:
    return repo_root() / "data" / "raw" / "photos"


def public_dir() -> Path:
    return repo_root() / "site" / "public" / "photos"


def member_ids() -> list[str]:
    """Every Bioguide id in the exported federal roster, sorted."""
    members = repo_root() / "data" / "members"
    return sorted(p.stem for p in members.glob("*.json"))


def _write_bytes(path: Path, body: bytes) -> None:
    """Atomic write, so an interrupted run never leaves a truncated JPEG that a
    later run would treat as already cached."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_bytes(body)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def run(argv: list[str] | None = None) -> int:
    args = list(argv or [])
    refetch = "--refetch" in args

    ids = member_ids()
    if not ids:
        print("civic-ledger ingest photos: data/members/ is empty - run `ingest members` first")
        return 1

    raw = raw_dir()
    pub = public_dir()
    raw.mkdir(parents=True, exist_ok=True)
    pub.mkdir(parents=True, exist_ok=True)

    cached = fetched = missing = failed = 0
    last_request = 0.0
    with httpx.Client(timeout=_TIMEOUT, headers={"User-Agent": _USER_AGENT},
                      follow_redirects=True) as client:
        for bioguide in ids:
            raw_path = raw / f"{bioguide}.jpg"
            absent_marker = raw / f"{bioguide}.absent"
            if not refetch and raw_path.exists():
                cached += 1
            elif not refetch and absent_marker.exists():
                missing += 1
                continue
            else:
                wait = MIN_INTERVAL_SECONDS - (time.monotonic() - last_request)
                if wait > 0:
                    time.sleep(wait)
                url = SOURCE_URL.format(size=SIZE, bioguide=bioguide)
                try:
                    resp = client.get(url)
                except httpx.HTTPError as exc:
                    failed += 1
                    print(f"  {bioguide}: fetch failed ({exc.__class__.__name__})")
                    last_request = time.monotonic()
                    continue
                last_request = time.monotonic()
                if resp.status_code == 404:
                    # Recorded, so a re-run does not ask again for a photograph the
                    # project does not publish.
                    absent_marker.write_text("404\n", encoding="utf-8")
                    missing += 1
                    continue
                if resp.status_code != 200 or not resp.content:
                    failed += 1
                    print(f"  {bioguide}: HTTP {resp.status_code}")
                    continue
                _write_bytes(raw_path, resp.content)
                fetched += 1

            body = raw_path.read_bytes()
            target = pub / f"{bioguide}.jpg"
            if not target.exists() or target.read_bytes() != body:
                _write_bytes(target, body)

    published = len(list(pub.glob("*.jpg")))
    print(
        f"civic-ledger ingest photos: {len(ids)} members - {fetched} fetched, "
        f"{cached} already cached, {missing} not published upstream, {failed} failed"
    )
    print(f"  {published} photograph(s) in site/public/photos/ ({SIZE}, source {PROJECT_URL})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
