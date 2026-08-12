"""§6.11 / INC-11 — archive-link liveness sweep (weekly, network).

Every curated statement carries a permanent Wayback `archive_url`. This sweep HEADs
each one and distinguishes:

  * ALIVE (2xx/3xx) — the snapshot resolves;
  * DEAD (4xx, e.g. 404/410) — the snapshot is confirmed gone. The statement is
    flagged UNPUBLISHABLE until recaptured: its id lands in the committed report,
    which the site build reads to exclude it (data.ts::getStatements);
  * UNREACHABLE (network error / timeout / 5xx) — a TRANSIENT archive.org outage,
    which must never read as a dead link. Warn only; never excludes, never fails.

It writes `data/quality/archive-status.json` (deterministic, sorted, no wall-clock so
a no-change week is byte-identical) and exits nonzero when any link is DEAD — the
GitHub Actions failure notification is the alert channel (like nightly). This is NOT
in the default `uv run checks` suite: it is network + weekly (checks/run.py stays
offline-deterministic).
"""

from __future__ import annotations

import json

import httpx

from ingest.cache import repo_root

STATUS_PATH = repo_root() / "data" / "quality" / "archive-status.json"
_TIMEOUT = httpx.Timeout(30.0, connect=15.0)
_USER_AGENT = "civic-ledger/0.0 (+https://github.com/SeanisnotBrown/civic-ledger)"


def _load_statements() -> list[dict]:
    sdir = repo_root() / "data" / "statements"
    if not sdir.exists():
        return []
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(sdir.glob("*.json"))
        if not p.name.startswith("_")
    ]


def classify_head(client: httpx.Client, archive_url: str) -> str:
    """HEAD one archive_url → "alive" | "dead" | "unreachable". A 4xx is a confirmed
    dead snapshot; a network error or 5xx is a transient outage (unreachable)."""
    try:
        resp = client.head(archive_url, headers={"User-Agent": _USER_AGENT},
                           timeout=_TIMEOUT, follow_redirects=True)
    except httpx.HTTPError:
        return "unreachable"
    if resp.status_code >= 500:
        return "unreachable"
    if resp.status_code >= 400:
        return "dead"
    return "alive"


def sweep(statements: list[dict], client: httpx.Client) -> dict:
    """Sweep every statement's archive_url. Returns a deterministic report dict:
    sorted `dead_statement_ids`, plus `dead`/`unreachable` detail lists and counts."""
    dead: list[dict] = []
    unreachable: list[dict] = []
    alive = 0
    for s in sorted(statements, key=lambda x: x["id"]):
        verdict = classify_head(client, s["archive_url"])
        if verdict == "dead":
            dead.append({"id": s["id"], "archive_url": s["archive_url"]})
        elif verdict == "unreachable":
            unreachable.append({"id": s["id"], "archive_url": s["archive_url"]})
        else:
            alive += 1
    return {
        "checked": len(statements),
        "alive": alive,
        "dead": sorted(dead, key=lambda d: d["id"]),
        "dead_statement_ids": sorted(d["id"] for d in dead),
        "unreachable": sorted(unreachable, key=lambda u: u["id"]),
    }


def main() -> int:
    statements = _load_statements()
    if not statements:
        print("archive-links: no curated statements yet — sweep inactive (no-op).")
        return 0

    with httpx.Client() as client:
        report = sweep(statements, client)

    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )

    print(f"archive-links: swept {report['checked']} statement(s) — "
          f"{report['alive']} alive, {len(report['dead'])} dead, "
          f"{len(report['unreachable'])} unreachable.")
    if report["unreachable"]:
        print("  WARN: transient outage(s), not a failure: "
              f"{[u['id'] for u in report['unreachable']]}")
    if report["dead"]:
        print(f"  ARCHIVE LINKS FAILED — {len(report['dead'])} dead link(s), now flagged "
              "unpublishable (excluded from the site until recaptured):")
        for d in report["dead"]:
            print(f"    {d['id']}: {d['archive_url']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
