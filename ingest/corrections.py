"""INC-9 — corrections ledger, generated from git history (brief 5.12 / §A4).

Corrections are ordinary public commits whose subject line begins `correction:`
(never force-pushes, never silent edits). This reads `git log` for those commits
and writes `data/corrections.json`, which the /corrections page renders — so the
site still "builds from data alone" (the Cloudflare build never shells out to git,
and doesn't control clone depth). The nightly job regenerates this with a full
checkout (fetch-depth 0); a shallow checkout would see only the tip commit, so the
generation lives in the pipeline, not the page.

Deterministic: entries sorted newest-first by committer date; the only timestamps
are real commit dates. Empty history → `[]` (the page shows "no corrections yet").
"""

from __future__ import annotations

import json
import subprocess

from ingest.cache import repo_root

# Field + record separators that cannot occur in a commit subject.
_FS = "\x1f"
_RS = "\x1e"


def _git_log() -> str:
    out = subprocess.run(
        ["git", "log", "--grep", "^correction:", f"--format=%h{_FS}%cI{_FS}%s{_RS}"],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout


def parse_log(raw: str) -> list[dict[str, str]]:
    """Parse the `git log` output into correction records (pure)."""
    entries: list[dict[str, str]] = []
    for record in raw.split(_RS):
        record = record.strip()
        if not record:
            continue
        commit, date, subject = record.split(_FS)
        # The displayed text drops the `correction:` prefix (it's the tag, not content).
        text = subject.split(":", 1)[1].strip() if ":" in subject else subject
        entries.append({"commit": commit, "date": date, "subject": text})
    return entries


def build() -> list[dict[str, str]]:
    return parse_log(_git_log())


def main(argv: list[str] | None = None) -> int:
    path = repo_root() / "data" / "corrections.json"
    entries = build()
    path.write_text(
        json.dumps(entries, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"corrections: wrote {len(entries)} correction(s) to data/corrections.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
