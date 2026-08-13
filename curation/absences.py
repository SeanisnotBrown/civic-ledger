"""INC-6 — Absences & personal explanations: CREC search → review queue → owner
approval → verbatim `Absence.stated_reason` + source.

Principle 5 (no builder-authored political content): this module BUILDS the tool.
`search()` extracts VERBATIM candidate text (never summarized/paraphrased) from the
primary CREC granule and parks it in a review queue; a human owner runs `approve`
to publish a reason onto an `Absence`. Nothing reaches `data/absences/` without
that human step (content = H9). Extraction is mechanical string work:

  * member identity is hard-verified against the granule byline ("HON. {NAME}" +
    "of {state}") — a surname search alone returns wrong-state members;
  * a roll reference auto-matches ONLY when exactly one covered session has an
    existing absence stub for that member+roll (stub existence = ground truth);
    zero or many → left unmatched for the owner (§7 INC-6);
  * `declared_position` is set only for a single-roll, single-"would have voted"
    insertion (the model allows just yea/nay); multi-roll → None.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from ingest import config
from ingest.export import ABSENCES_DIR, _dumps, congress_of
from ingest.models import Absence
from ingest.sources import govinfo
from ingest.sources.legislators import congress_window

QUEUE_DIR = ABSENCES_DIR.parent / "quality" / "absence-queue"

# State code → full name, for byline verification (the granule prints the full
# state name; the Member record carries the 2-letter code).
US_STATES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

_POSITION = {"YEA": "yea", "AYE": "yea", "NAY": "nay", "NO": "nay"}


# --- granule parsing (pure) -----------------------------------------------


def _plain(granule_html: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", granule_html))


def parse_granule(granule_html: str) -> dict:
    """Pure extraction from a CREC granule → {hon_name, state (lower), verbatim,
    roll_refs (sorted unique ints), declared_position|None}. `verbatim` is the
    member's statement, line-unwrapped but otherwise exact. Missing fields come
    back empty/None; the caller decides what is publishable."""
    text = _plain(granule_html)

    byline = re.search(
        r"HON\.\s+(?P<name>[A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+)*)\s*\n\s*"
        r"of\s+(?P<state>[A-Za-z][A-Za-z ]+?)\s*\n",
        text,
    )
    hon_name = re.sub(r"\s+", " ", byline.group("name")).strip() if byline else ""
    state = byline.group("state").strip().lower() if byline else ""

    # Statement: from the chamber/date header to the underscore rule that closes
    # the insertion. Whitespace (incl. the Record's ~72-col line wraps) collapses
    # to single spaces — an unwrap, not a rewrite.
    stmt = re.search(
        r"in the (?:house of representatives|senate)[^\n]*\n\s*"
        r"[A-Za-z]+,\s+[A-Za-z]+\s+\d+,\s+\d{4}\s*\n(?P<body>.*?)\n\s*_{5,}",
        text,
        re.S,
    )
    verbatim = re.sub(r"\s+", " ", stmt.group("body")).strip() if stmt else ""

    roll_refs = sorted({int(n) for n in re.findall(r"Roll\s*Call\s*No\.?\s*(\d+)", text, re.I)})

    positions = {
        _POSITION[p.upper()]
        for p in re.findall(r"would have voted\s+(YEA|NAY|AYE|NO)\b", text, re.I)
    }
    declared = next(iter(positions)) if len(roll_refs) == 1 and len(positions) == 1 else None

    return {
        "hon_name": hon_name,
        "state": state,
        "verbatim": verbatim,
        "roll_refs": roll_refs,
        "declared_position": declared,
    }


def verify_member(parsed: dict, member: dict) -> bool:
    """True iff the granule byline is the covered member: their surname appears in
    the "HON. {NAME}" line AND the byline state matches the member's state. This is
    the gate that rejects a same-surname member from another state."""
    expected_state = US_STATES.get(member["state"], "").lower()
    if not expected_state or parsed["state"] != expected_state:
        return False
    surname = member["name"].split()[-1].lower()
    return surname in parsed["hon_name"].lower()


def _session_start_year(congress: int, session: int) -> int:
    return 1789 + 2 * (congress - 1) + (session - 1)


def match_rollcall(member_id: str, chamber: str, roll: int, granule_year: int) -> str | None:
    """The one existing absence stub for member+roll across covered sessions that
    started on/before the granule year, or None if zero/ambiguous. Stub existence
    (the member was recorded not_voting on that roll) is ground truth — an
    explanation cannot precede its own vote, so later sessions are excluded."""
    prefix = "h" if chamber == "house" else "s"
    hits = []
    for congress in config.CONGRESSES:
        for session in (1, 2):
            if _session_start_year(congress, session) > granule_year:
                continue
            rc_id = f"{prefix}-{congress}-{session}-{roll:04d}"
            # V2-1: data/absences/ is sharded one level by congress.
            if (ABSENCES_DIR / str(congress) / f"{member_id}--{rc_id}.json").exists():
                hits.append(rc_id)
    return hits[0] if len(hits) == 1 else None


# --- pipeline: search → queue ---------------------------------------------


def _covered_members() -> list[dict]:
    from ingest.export import MEMBERS_DIR

    out = []
    for path in sorted(MEMBERS_DIR.glob("*.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        out.append(m)
    return out


def build_candidate(result: dict, granule_html: str, members: list[dict]) -> dict | None:
    """Turn one search result + its granule into a verified queue candidate, or
    None if no covered member's byline matches (wrong-state / wrong-member hit)."""
    parsed = parse_granule(granule_html)
    member = next((m for m in members if verify_member(parsed, m)), None)
    if member is None:
        return None
    granule_year = int(result["dateIssued"][:4])
    matched = None
    if len(parsed["roll_refs"]) == 1:
        matched = match_rollcall(
            member["id"], member["chamber"], parsed["roll_refs"][0], granule_year
        )
    return {
        "granule_id": result["granuleId"],
        "package_id": result["packageId"],
        "date_issued": result["dateIssued"],
        "member_id": member["id"],
        "hon_name": parsed["hon_name"],
        "source_url": govinfo.granule_url(result["packageId"], result["granuleId"]),
        "verbatim_text": parsed["verbatim"],
        "roll_refs": parsed["roll_refs"],
        "matched_rollcall_id": matched,
        "declared_position": parsed["declared_position"] if matched else None,
        "status": "pending",
    }


def search(argv: list[str] | None = None) -> int:
    """Search CREC for the covered delegation's personal explanations, verify each
    byline, and write one pending queue file per candidate to
    data/quality/absence-queue/. Re-runnable (cached search + granules; queue files
    are only (re)written for pending/new candidates — an approved file is never
    clobbered)."""
    state_name = US_STATES[config.COVERED_STATE]
    start = congress_window(min(config.CONGRESSES))[0]
    end = congress_window(max(config.CONGRESSES))[1]
    members = _covered_members()

    data = govinfo.crec_personal_explanations(state_name, start, end)
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    n_new = n_verified = n_rejected = 0
    for result in data.get("results", []):
        granule_html = govinfo.granule_text(result["packageId"], result["granuleId"])
        candidate = build_candidate(result, granule_html, members)
        if candidate is None:
            n_rejected += 1
            continue
        n_verified += 1
        out = QUEUE_DIR / f"{candidate['granule_id']}.json"
        if out.exists() and json.loads(out.read_text(encoding="utf-8")).get("status") == "approved":
            continue  # never clobber an owner decision
        out.write_text(_dumps(candidate), encoding="utf-8", newline="\n")
        n_new += 1

    print(f"curate absences search: {data.get('count')} CREC hits for {state_name}; "
          f"{n_verified} byline-verified, {n_rejected} rejected (wrong member/state).")
    print(f"  {n_new} queue file(s) at {QUEUE_DIR.relative_to(ABSENCES_DIR.parent.parent)}/ "
          f"— run `curate absences approve` to publish.")
    return 0


# --- approval → publish ---------------------------------------------------


def _pending() -> list[Path]:
    if not QUEUE_DIR.exists():
        return []
    return [
        p for p in sorted(QUEUE_DIR.glob("*.json"))
        if json.loads(p.read_text(encoding="utf-8")).get("status") == "pending"
    ]


def _publish(candidate: dict, reason: str) -> Path:
    """Write the verbatim reason + source onto the matched Absence stub. Requires a
    matched roll (an Absence file is keyed member+rollcall); the Absence model
    enforces stated_reason ⇒ stated_reason_source."""
    rc_id = candidate["matched_rollcall_id"]
    if not rc_id:
        raise ValueError(f"{candidate['granule_id']}: no matched roll call — cannot publish")
    # V2-1: data/absences/ is sharded one level by congress — the stub this
    # publishes onto was already written there by the ingest (match_rollcall
    # requires stub existence, so the directory is guaranteed present).
    path = ABSENCES_DIR / congress_of(rc_id) / f"{candidate['member_id']}--{rc_id}.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    absence = Absence(
        member_id=candidate["member_id"],
        rollcall_id=rc_id,
        stated_reason=reason,
        stated_reason_source=candidate["source_url"],
        declared_position=candidate["declared_position"] or existing.get("declared_position"),
    )
    path.write_text(_dumps(absence.model_dump()), encoding="utf-8", newline="\n")
    return path


def _assert_edit_is_a_trim(edited: str, verbatim: str, source: str) -> None:
    """A `stated_reason` published with a CREC citation MUST actually appear in that
    granule (R-4b/M-5). The edit path exists for TRIMMING (dropping a salutation, a
    trailing roll ref) — not rewriting. Enforce it: the edited text, whitespace-
    normalized, must be a non-empty substring of the candidate's verbatim CREC text.
    Otherwise we would attach a primary-source citation to words that source never
    carried."""
    norm_edit = " ".join(edited.split())
    norm_verbatim = " ".join(verbatim.split())
    if not norm_edit:
        raise ValueError(f"edited reason is empty — nothing to publish ({source})")
    if norm_edit not in norm_verbatim:
        raise ValueError(
            f"edited reason is not a substring of the verbatim CREC text in {source}: "
            "trimming is allowed, rewriting is not — leave it unedited to publish verbatim"
        )


def approve_one(candidate_path: Path, reason: str | None = None) -> Path:
    """Non-interactive approve of one queue file (the owner's scriptable path, also
    the test hook): publish its verbatim text (or an owner-supplied TRIM of it) and
    mark the queue file approved. An override must be a whitespace-normalized substring
    of the verbatim CREC text (R-4b/M-5). Returns the written Absence path."""
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    if reason is not None:
        _assert_edit_is_a_trim(reason, candidate["verbatim_text"], candidate_path.name)
    written = _publish(candidate, reason if reason is not None else candidate["verbatim_text"])
    candidate["status"] = "approved"
    candidate_path.write_text(_dumps(candidate), encoding="utf-8", newline="\n")
    return written


def approve(argv: list[str] | None = None) -> int:
    """`curate absences approve [--granule <id>]`. With `--granule`, approve that one
    candidate non-interactively (owner-scriptable). Otherwise walk pending
    candidates interactively: show the verbatim excerpt + matched roll, and read
    y / n / e (edit-verbatim) per candidate. Only a matched roll can be published;
    unmatched candidates are skipped with a note (owner attaches by hand)."""
    args = sys.argv[1:] if argv is None else argv
    granule = None
    if "--granule" in args:
        granule = args[args.index("--granule") + 1]

    if granule is not None:
        path = QUEUE_DIR / f"{granule}.json"
        if not path.exists():
            print(f"no queue file for granule {granule!r}")
            return 1
        written = approve_one(path)
        print(f"approved {granule} -> {written.relative_to(ABSENCES_DIR.parent.parent)}")
        return 0

    pending = _pending()
    if not pending:
        print("curate absences approve: no pending candidates.")
        return 0
    for path in pending:
        c = json.loads(path.read_text(encoding="utf-8"))
        print("\n" + "=" * 72)
        print(f"member {c['member_id']} ({c['hon_name']}) — {c['date_issued']}")
        print(f"matched roll: {c['matched_rollcall_id'] or 'UNMATCHED (skip; attach by hand)'}")
        print(f"declared position: {c['declared_position']}")
        print(f"source: {c['source_url']}")
        print(f"verbatim:\n  {c['verbatim_text']}")
        if not c["matched_rollcall_id"]:
            print("  -> unmatched; leaving for manual attachment.")
            continue
        choice = input("approve? [y]es / [n]o / [e]dit-verbatim: ").strip().lower()
        if choice == "y":
            approve_one(path)
            print("  published.")
        elif choice == "e":
            edited = input("paste verbatim reason (a trim of the text above): ").strip()
            try:
                approve_one(path, reason=edited)
                print("  published (edited).")
            except ValueError as exc:
                print(f"  NOT published — {exc}")
        else:
            print("  skipped.")
    return 0
