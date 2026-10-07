"""Committee assignments per member (P2 task 7).

Source: the `unitedstates/congress-legislators` project, the same project the
roster already comes from (`ingest/sources/legislators.py`), via two files:

  * `committee-membership-current.yaml` — a committee id → list of seats, each
    seat carrying the member's bioguide id, their rank within their party on that
    committee, and their title when they hold one (Chairman, Ranking Member, …).
  * `committees-current.yaml` — the committee ids' own names and official URLs,
    with subcommittees nested under their parent.

Subcommittee ids in the membership file are the parent's `thomas_id` followed by
the subcommittee's own, e.g. `HSAG` + `15` → `HSAG15`. That join is the only
derivation here; names, titles and ranks are the project's own values, verbatim.

Output: `data/committees/membership.json`, deterministic (sorted keys, sorted
seat order, no wall-clock), keyed by bioguide id. A member with no current seat
is simply absent from `members`, and the site distinguishes "this file does not
exist yet" from "this file lists no seat for them" (§4.2 — the page never implies
a member sits on nothing).

Scope note: the file is `-current`, so it describes committees as they stand now,
not as they stood in the 118th. Members who have left office therefore carry no
seats. That is the upstream project's own scope and the member page says the
section lists current assignments.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from ingest.cache import atomic_write_text, fetch, repo_root

SOURCE = "legislators"
MEMBERSHIP_URL = (
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
    "committee-membership-current.yaml"
)
COMMITTEES_URL = (
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/"
    "committees-current.yaml"
)
PROJECT_URL = "https://github.com/unitedstates/congress-legislators"


def out_path() -> Path:
    return repo_root() / "data" / "committees" / "membership.json"


def committee_index(committees_raw: list[dict]) -> dict[str, dict]:
    """Committee id → {name, parent_name, url}, parents and subcommittees alike."""
    index: dict[str, dict] = {}
    for c in committees_raw:
        cid = c.get("thomas_id")
        if not cid:
            continue
        url = c.get("url") or PROJECT_URL
        index[cid] = {"name": c.get("name") or cid, "parent_name": None, "url": url}
        for sub in c.get("subcommittees") or []:
            sub_id = sub.get("thomas_id")
            if not sub_id:
                continue
            index[f"{cid}{sub_id}"] = {
                "name": sub.get("name") or sub_id,
                "parent_name": c.get("name") or cid,
                # A subcommittee has no URL of its own upstream; its parent's is the
                # closest official page, and it is better than linking nothing.
                "url": url,
            }
    return index


def build(membership_raw: dict, committees_raw: list[dict], known_ids: set[str]) -> dict:
    """The exported structure. `known_ids` restricts output to members in our own
    roster, so the file never carries a bioguide id the site has no page for."""
    index = committee_index(committees_raw)
    by_member: dict[str, list[dict]] = {}
    for committee_id, seats in (membership_raw or {}).items():
        meta = index.get(committee_id)
        for seat in seats or []:
            bioguide = seat.get("bioguide")
            if not bioguide or bioguide not in known_ids:
                continue
            by_member.setdefault(bioguide, []).append({
                "committee_id": committee_id,
                "name": (meta or {}).get("name") or committee_id,
                "parent_name": (meta or {}).get("parent_name"),
                "rank": seat.get("rank"),
                "title": seat.get("title"),
                "source_url": (meta or {}).get("url") or PROJECT_URL,
            })
    # Deterministic order: parent committees before their subcommittees (a seat
    # with no parent_name first), then by name, then by id.
    for seats in by_member.values():
        seats.sort(key=lambda s: (s["parent_name"] or "", s["name"], s["committee_id"]))
    return {
        # No timestamp: a wall-clock would make the file differ on every run and
        # break byte-for-byte recomputability (§6.3). The git commit is the date.
        "source_url": PROJECT_URL,
        "seat_count": sum(len(v) for v in by_member.values()),
        "members": {k: by_member[k] for k in sorted(by_member)},
    }


def run(argv: list[str] | None = None) -> int:
    del argv
    members_dir = repo_root() / "data" / "members"
    known_ids = {p.stem for p in members_dir.glob("*.json")}
    if not known_ids:
        print("civic-ledger ingest committees: data/members/ is empty - run `ingest members`")
        return 1

    membership_raw = yaml.safe_load(fetch(SOURCE, MEMBERSHIP_URL, ext="yaml").text)
    committees_raw = yaml.safe_load(fetch(SOURCE, COMMITTEES_URL, ext="yaml").text)
    payload = build(membership_raw, committees_raw, known_ids)

    seats = payload["seat_count"]
    atomic_write_text(
        out_path(),
        json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
    )
    print(
        f"civic-ledger ingest committees: {seats} seat(s) across "
        f"{len(payload['members'])} member(s) -> data/committees/membership.json"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
