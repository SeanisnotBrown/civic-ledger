"""Which amendment a House amendment vote was on (P2 review round 2, item 3).

The problem: a House amendment roll call's question is the whole of what the
congress.gov vote endpoint gives us -- and that question is always the bare
string "On Agreeing to the Amendment". 637 House roll calls in the dataset say
exactly that and nothing more, so a reader sees that their member voted Nay on
"the amendment" with no way to know which one. The Senate does not have this
problem: it writes the designation into the question itself ("On the Amendment
S.Amdt. 316 to S.Con.Res. 7"), and names no sponsor anywhere in its XML.

The source: the Clerk of the House's own roll-call XML -- the SAME document each
of these vote rows already links to as "Official record" (`rollcall.source_url`).
It carries two fields the congress.gov endpoint drops:

    <amendment-num>57</amendment-num>
    <amendment-author>Lawler of New York Part B Amendment No. 114</amendment-author>

Both are rendered verbatim. `amendment-author` is the Clerk's own phrasing, which
already reads as a sentence fragment a person can follow; parsing a surname and a
state out of it would be a derivation this file does not need to make.

Scope and politeness: one fetch per House amendment roll call, through
`ingest.cache.fetch`, so a second run is free and an interrupted run resumes.
The cache's per-host interval holds the rate at one request a second. A roll
whose XML carries no amendment fields is left exactly as it was -- the absence of
the fields is the absence of the claim.

    uv run ingest vote-amendments                 # every House amendment roll
    uv run ingest vote-amendments --limit 20      # a sample first
    uv run ingest vote-amendments --congress 119  # one congress
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from ingest.cache import RetryableHTTPError, atomic_write_text, fetch, repo_root

SOURCE = "clerk_house"

# A House roll call is an amendment vote when its question names an amendment.
# Deliberately narrow: "On Motion to Suspend the Rules and Concur in the Senate
# Amendment" is a vote on the MEASURE, not on an amendment of this chamber's, and
# the Clerk's XML carries no amendment fields for it.
_AMENDMENT_Q = re.compile(r"^on agreeing to the amendment", re.IGNORECASE)


def votes_dir() -> Path:
    return repo_root() / "data" / "votes"


def is_house_amendment(rollcall: dict) -> bool:
    """True for a House roll call whose question is an amendment question."""
    if rollcall.get("chamber") != "house":
        return False
    return bool(_AMENDMENT_Q.match(rollcall.get("question") or ""))


def parse_amendment(xml_text: str) -> tuple[str | None, str | None]:
    """`(number, author)` from the Clerk's roll-call XML, verbatim, or `(None,
    None)` when the document carries neither. The number is returned as the
    Clerk writes it, prefixed so a bare "57" cannot be read as a bill number."""
    root = ET.fromstring(xml_text)
    num_el = root.find(".//amendment-num")
    author_el = root.find(".//amendment-author")
    num = (num_el.text or "").strip() if num_el is not None else ""
    author = (author_el.text or "").strip() if author_el is not None else ""
    return (f"Amendment No. {num}" if num else None, author or None)


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ingest vote-amendments")
    ap.add_argument("--congress", type=int, default=None)
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after this many rolls (0 = no limit)")
    args = ap.parse_args(argv or [])

    targets: list[Path] = []
    for path in sorted(votes_dir().glob("*.json")):
        rc = json.loads(path.read_text(encoding="utf-8"))["rollcall"]
        if not is_house_amendment(rc):
            continue
        if args.congress is not None and rc.get("congress") != args.congress:
            continue
        targets.append(path)

    if not targets:
        print("civic-ledger ingest vote-amendments: no House amendment roll call to fill")
        return 0
    if args.limit:
        targets = targets[: args.limit]

    print(f"civic-ledger ingest vote-amendments: {len(targets)} roll call(s) to read")
    filled = 0
    unchanged = 0
    failures: list[str] = []
    for path in targets:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rc = payload["rollcall"]
        url = rc.get("source_url") or ""
        if not url.endswith(".xml"):
            failures.append(f"{rc['id']}: source_url is not the Clerk's XML")
            continue
        try:
            body = fetch(SOURCE, url, ext="xml").text
            number, author = parse_amendment(body)
        except (RetryableHTTPError, httpx.HTTPError, OSError, ET.ParseError) as exc:
            # A failure here costs one roll's attribution, never the run: the
            # cache makes a re-run cheap and only the missing rolls refetch.
            failures.append(f"{rc['id']}: {type(exc).__name__}")
            continue

        if number is None and author is None:
            unchanged += 1
            continue
        if rc.get("amendment_number") == number and rc.get("amendment_sponsor") == author:
            unchanged += 1
            continue
        rc["amendment_number"] = number
        rc["amendment_sponsor"] = author
        payload["rollcall"] = dict(sorted(rc.items()))
        atomic_write_text(
            path,
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        )
        filled += 1

    print(
        f"civic-ledger ingest vote-amendments: {filled} filled, {unchanged} already "
        f"current or carrying no amendment fields, {len(failures)} failed"
    )
    if failures:
        print(f"FAIL: {len(failures)} roll(s) could not be read: {failures[:10]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
