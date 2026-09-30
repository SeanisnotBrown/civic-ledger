"""INC-12 — Mississippi state legislature ingest (LegiScan bulk dataset, branch A).

The GO verdict (data/quality/ms-state-verdict.md, D21): LegiScan carries accurate
per-person MS positions, verified 5/5 (470 positions) against the official billstatus
roll-call PDFs. This module turns the LegiScan bulk dataset for the current MS session
into the canonical schema, partitioned under data/state/ms/ (D51) so the federal guards
never see it.

Discipline mirrors the federal ingests:
  * pure parsers (`parse_person`/`parse_bill`/`parse_rollcall`) + a pure `build_records`
    that the tests drive offline with inlined dataset records — no network in the parse;
  * a per-roll TALLY CROSS-CHECK (per-person counts must equal the LegiScan header
    yea/nay/nv) — a mismatch raises, never silently exports (parity with the Senate path);
  * an unknown `people_id` in a vote raises `UnknownPerson` (parity with the R-2 churn
    guard) — never a position with no member;
  * `party_totals` is FULLY computed here (LegiScan gives every position, so this is the
    whole chamber, not a covered delegation) — it feeds a future MS party-unity metric.

SESSION ROLLOVER (D87). `current_session()` follows the newest regular session with no
config change, and the export ACCUMULATES: when the 2027 session lands, the 2026 records
stay on disk and every MS number spans both. That is deliberate — the owner ratified
(2026-09-30) that a Mississippi grade is a CAREER grade, matching the federal side, which
already spans the 118th and 119th Congresses. Accumulating only works if nothing is
silently replaced, so the export merges rather than overwrites:
  * a continuing legislator's member file KEEPS its earlier terms (`merge_member`);
  * a legislator absent from the new roster is marked `serving: false` in place, instead
    of being left frozen as still-serving;
  * a member's legislation record KEEPS earlier sessions' sponsorship (`merge_legislation`);
  * the crosswalk keeps departed members;
  * the manifest counts what is ON DISK, not what this one session built, and lists every
    session included.
Roll ids (`ms-h-<session>-<id>`) and bill ids (`ms-hb1-<session>`) already carry the
session, so nothing collides.

Scope honesty (limitations page, phase 6): LegiScan SCRAPES the official billstatus
record, so source_url cites LegiScan for roll calls (our actual data source) and the
official billstatus link for bills where present; the phase-3 spot check verifies scrape
fidelity against the official per-vote PDFs, exactly the risk the GO verdict measured.
"""

from __future__ import annotations

import base64
import io
import json
import re
import zipfile
from dataclasses import dataclass, field

from ingest import config
from ingest.export import (
    MS_BILLS_DIR,
    MS_MEMBERS_DIR,
    MS_VOTES_DIR,
    _dumps,
    export_bill,
    export_members,
    export_rollcall,
)
from ingest.models import Bill, LegItem, Member, MemberLegislation, MemberVote, RollCall, Term
from ingest.sources import legiscan


class UnknownPerson(RuntimeError):
    """A vote references a people_id absent from the session roster (churn/corruption)."""


class TallyMismatch(RuntimeError):
    """Per-person position counts disagree with the LegiScan header tally."""


# --- classifier (MS roll-call descriptions → canonical vote_class) --------
# LegiScan's `desc` is the question. MS floor votes are almost all up-or-down on a
# measure/amendment/report; the §A1 congressional classifier does not apply, so this is
# the MS-scoped table. Keyword order encodes precedence (checked top to bottom).

_MS_RULES: tuple[tuple[str, str, str], ...] = (
    ("veto", "veto_override", "MS-VETO"),            # "Veto Overridden" / "Veto Sustained"
    ("tabled", "procedural", "MS-TABLED"),           # "Tabled Failed" (a table motion)
    ("conference report", "passage", "MS-CONF"),     # adopting a conference report = final
    ("concurred", "passage", "MS-CONCUR"),           # concurring in the other chamber's amend
    ("passed", "passage", "MS-PASS"),
    ("adopted", "passage", "MS-ADOPT"),              # adopting a resolution
    ("failed", "passage", "MS-FAIL"),                # a failed passage attempt is passage-class
)


def classify_ms(desc: str) -> tuple[str, str]:
    """Map a LegiScan roll-call `desc` to (vote_class, rule_id). First keyword match
    wins. An unmatched desc returns ('other', 'MS-OTHER') — the MS classification gate
    fails on any of these so a new description is caught, never silently mislabeled."""
    low = desc.lower()
    for kw, cls, rule in _MS_RULES:
        if kw in low:
            return cls, rule
    return "other", "MS-OTHER"


# --- pure parsers ---------------------------------------------------------

_ROLE_CHAMBER = {"Rep": "house", "Sen": "senate"}
_VOTE_CHAMBER = {"H": "house", "S": "senate"}
# LegiScan vote_text for MS is exactly {Yea, Nay, NV}; NV = did not vote (absent/present
# are not distinguished in the per-person record — see the xcheck reconciliation rules).
_POSITION = {"Yea": "yea", "Nay": "nay", "NV": "not_voting"}
_ID_FIELDS = (("votesmart_id", "votesmart"), ("ballotpedia", "ballotpedia"),
              ("opensecrets_id", "opensecrets"), ("bioguide_id", "bioguide"))
_BILL_NUM_RE = re.compile(r"^([A-Za-z]+)\s*0*(\d+)$")


def _unwrap(obj: dict, key: str) -> dict:
    """LegiScan wraps each record as {"person": {...}} / {"bill": {...}} / {"roll_call":
    {...}}. Accept either the wrapped or the inner form."""
    return obj[key] if key in obj else obj


def map_party(party: str) -> str:
    """LegiScan party letter → our D/R/I model. Nonpartisan ('N') maps to Independent
    ('I') — documented on the limitations page; MS has one such member."""
    return party if party in ("D", "R", "I") else "I"


def _district_ordinal(district: str | None) -> int | None:
    """'HD-103' / 'SD-047' → 103 / 47. None if no ordinal (should not happen for MS)."""
    m = re.search(r"(\d+)", district or "")
    return int(m.group(1)) if m else None


def parse_person(person: dict, year_start: int, year_end: int) -> Member:
    p = _unwrap(person, "person")
    chamber = _ROLE_CHAMBER.get(p["role"])
    if chamber is None:
        raise ValueError(f"person {p.get('people_id')}: unknown role {p['role']!r}")
    party = map_party(p["party"])
    ids = {"legiscan": str(p["people_id"])}
    for src, dst in _ID_FIELDS:
        v = p.get(src)
        if v:
            ids[dst] = str(v)
    return Member(
        id=f"ms-{p['people_id']}",
        ids=dict(sorted(ids.items())),
        name=p["name"],
        party=party,
        state="MS",
        district=_district_ordinal(p.get("district")),
        chamber=chamber,
        jurisdiction="ms",
        serving=True,  # in THIS session's roster; `_mark_departed` flips the rest (D87)
        terms=[Term(start=f"{year_start}-01-01", end=f"{year_end}-12-31",
                    party=party, chamber=chamber)],
    )


def canonical_bill_id(bill_number: str, session_id: int) -> str:
    """'HB1' + 2249 → 'ms-hb1-2249' (lowercase, whitespace-free)."""
    return f"ms-{bill_number.lower().replace(' ', '')}-{session_id}"


def parse_bill(bill: dict, session_id: int) -> Bill:
    b = _unwrap(bill, "bill")
    num = b["bill_number"]
    m = _BILL_NUM_RE.match(num)
    if not m:
        raise ValueError(f"unparseable MS bill_number {num!r}")
    sponsors = b.get("sponsors", [])
    primary = next((s for s in sponsors if str(s.get("sponsor_type_id")) == "1"),
                   sponsors[0] if sponsors else None)
    primary_pid = primary["people_id"] if primary else None
    cosponsors = sorted({f"ms-{s['people_id']}" for s in sponsors
                         if s["people_id"] != primary_pid})
    history = b.get("history", [])
    last = history[-1] if history else {}
    return Bill(
        id=canonical_bill_id(num, session_id),
        jurisdiction="ms",
        congress=None,
        type=m.group(1).lower(),
        number=int(m.group(2)),
        title_official=b["title"],
        policy_area=None,  # LegiScan carries no policy-area taxonomy of ours (D5)
        subjects=[s["subject_name"] for s in b.get("subjects", [])],
        sponsor_id=f"ms-{primary_pid}" if primary_pid is not None else None,
        cosponsor_ids=cosponsors,
        latest_action=last.get("action", "") or str(b.get("status", "")),
        latest_action_date=last.get("date", "") or b.get("status_date", ""),
        cbo_estimates=[],
        source_url=b.get("state_link") or b["url"],  # official billstatus where present
    )


def _leg_item(bill: dict, session_id: int) -> LegItem:
    """One `LegItem` for a member's authored bill. `became_law` is a deterministic match
    on the official history action "Approved by Governor" (the MS enactment signal);
    `enacted_action` is that verbatim action text when enacted, else None."""
    b = _unwrap(bill, "bill")
    history = b.get("history", [])
    enacted_action = next(
        (h["action"] for h in history if "approved by governor" in h.get("action", "").lower()),
        None,
    )
    return LegItem(
        bill_id=canonical_bill_id(b["bill_number"], session_id),
        congress=None,
        title=b["title"],
        introduced_date=history[0]["date"] if history else None,
        became_law=enacted_action is not None,
        enacted_action=enacted_action,
        source_url=b.get("state_link") or b["url"],
    )


def build_legislation(members: list[Member], bills: list[dict], session_id: int
                      ) -> list[MemberLegislation]:
    """Per-member sponsored + cosponsored bills over ALL session bills (not just the
    vote-referenced ones), so the sponsorship counts are complete + recomputable.

    LegiScan lists every MS bill author as sponsor_type_id 1 (it does not distinguish
    primary from co-authors for Mississippi), so the FIRST-listed author is taken as the
    principal ("sponsored") and the rest as additional authors ("cosponsored") — the
    standard reading of the MS author order. Documented on the limitations page."""
    member_ids = {m.id for m in members}
    buckets: dict[str, dict[str, list[LegItem]]] = {
        m.id: {"sponsored": [], "cosponsored": []} for m in members
    }
    for bill in bills:
        sponsors = _unwrap(bill, "bill").get("sponsors", [])
        if not sponsors:
            continue
        try:
            item = _leg_item(bill, session_id)
        except (KeyError, ValueError):
            continue  # a malformed bill is quarantined for publishing; skip it here too
        seen: set[str] = set()
        for i, s in enumerate(sponsors):
            mid = f"ms-{s['people_id']}"
            if mid not in member_ids or mid in seen:
                continue
            seen.add(mid)
            buckets[mid]["sponsored" if i == 0 else "cosponsored"].append(item)
    return [
        MemberLegislation(
            member_id=mid,
            sponsored=sorted(b["sponsored"], key=lambda x: x.bill_id),
            cosponsored=sorted(b["cosponsored"], key=lambda x: x.bill_id),
            source_url="https://legiscan.com/MS",
        )
        for mid, b in sorted(buckets.items())
    ]


def parse_rollcall(
    vote: dict, session_id: int, people_by_id: dict[int, Member],
    bill_number_by_legiscan: dict[str, str],
) -> tuple[RollCall, list[MemberVote]]:
    rc = _unwrap(vote, "roll_call")
    chamber = _VOTE_CHAMBER.get(rc["chamber"])
    if chamber is None:
        raise ValueError(f"roll {rc.get('roll_call_id')}: unknown chamber {rc['chamber']!r}")
    prefix = "h" if chamber == "house" else "s"
    rc_id = f"ms-{prefix}-{session_id}-{rc['roll_call_id']}"
    vote_class, rule = classify_ms(rc["desc"])

    counts = {"yea": 0, "nay": 0, "present": 0, "not_voting": 0}
    party_totals: dict[str, dict[str, int]] = {}
    member_votes: list[MemberVote] = []
    for v in rc["votes"]:
        member = people_by_id.get(v["people_id"])
        if member is None:
            raise UnknownPerson(
                f"roll {rc['roll_call_id']} references people_id {v['people_id']} "
                f"absent from the session roster — re-run `ingest ms` to refresh"
            )
        pos = _POSITION.get(v["vote_text"])
        if pos is None:
            raise ValueError(f"roll {rc['roll_call_id']}: unmapped vote_text {v['vote_text']!r}")
        member_votes.append(MemberVote(member_id=member.id, rollcall_id=rc_id, position=pos))
        counts[pos] += 1
        pt = party_totals.setdefault(
            member.party, {"yea": 0, "nay": 0, "present": 0, "not_voting": 0})
        pt[pos] += 1

    # Tally cross-check: per-person counts must equal the LegiScan header (yea/nay/nv;
    # absent folds into not_voting). A mismatch means a corrupt roll → raise, never export.
    header_nv = rc["nv"] + rc.get("absent", 0)
    if (counts["yea"], counts["nay"], counts["not_voting"]) != (rc["yea"], rc["nay"], header_nv):
        raise TallyMismatch(
            f"roll {rc['roll_call_id']}: per-person {counts} != header "
            f"yea={rc['yea']} nay={rc['nay']} nv={header_nv}"
        )

    bill_number = bill_number_by_legiscan.get(str(rc["bill_id"]))
    source_url = (f"https://legiscan.com/MS/rollcall/{bill_number}/id/{rc['roll_call_id']}"
                  if bill_number else f"https://legiscan.com/MS/rollcall/id/{rc['roll_call_id']}")
    rollcall = RollCall(
        id=rc_id,
        chamber=chamber,
        jurisdiction="ms",
        congress=None,
        session=session_id,
        number=rc["roll_call_id"],
        date=rc["date"],
        question=rc["desc"],
        vote_class=vote_class,
        vote_class_rule=rule,
        bill_id=canonical_bill_id(bill_number, session_id) if bill_number else None,
        result="passed" if rc.get("passed") == 1 else "failed",
        totals=counts,
        party_totals=dict(sorted(party_totals.items())),
        source_url=source_url,
    )
    return rollcall, sorted(member_votes, key=lambda mv: mv.member_id)


# --- build (pure over decoded dataset records) ----------------------------


@dataclass
class BuildResult:
    members: list[Member]
    bills: list[Bill]
    rollcalls: list[tuple[RollCall, list[MemberVote]]]
    crosswalk: dict[str, dict]
    legislation: list[MemberLegislation] = field(default_factory=list)
    quarantined: list[str] = field(default_factory=list)


def build_records(
    session_id: int, year_start: int, year_end: int,
    people: list[dict], bills: list[dict], votes: list[dict],
) -> BuildResult:
    """Pure: decoded LegiScan records → canonical records. Members + every referenced
    bill + every roll call with per-person positions. A parse failure quarantines that
    record (id logged) rather than aborting the whole session."""
    members = [parse_person(p, year_start, year_end) for p in people]
    people_by_id = {int(_unwrap(p, "person")["people_id"]): m
                    for p, m in zip(people, members, strict=True)}

    bills_by_legiscan = {str(_unwrap(b, "bill")["bill_id"]): b for b in bills}
    # Only bills that actually received a roll-call are published (parity with the
    # federal bill covered-set = vote-referenced bills, D27).
    referenced = {str(_unwrap(v, "roll_call")["bill_id"]) for v in votes}
    referenced.discard("0")

    canonical_bills: list[Bill] = []
    bill_number_by_legiscan: dict[str, str] = {}
    quarantined: list[str] = []
    for legiscan_id in sorted(referenced):
        raw = bills_by_legiscan.get(legiscan_id)
        if raw is None:
            quarantined.append(f"bill:{legiscan_id} (referenced, absent from dataset)")
            continue
        try:
            bill = parse_bill(raw, session_id)
        except (ValueError, KeyError) as exc:
            quarantined.append(f"bill:{legiscan_id} ({type(exc).__name__}: {exc})")
            continue
        canonical_bills.append(bill)
        bill_number_by_legiscan[legiscan_id] = _unwrap(raw, "bill")["bill_number"]

    rollcalls: list[tuple[RollCall, list[MemberVote]]] = []
    for v in votes:
        rid = _unwrap(v, "roll_call").get("roll_call_id")
        try:
            rollcalls.append(parse_rollcall(v, session_id, people_by_id, bill_number_by_legiscan))
        except (UnknownPerson, TallyMismatch, ValueError, KeyError) as exc:
            quarantined.append(f"roll:{rid} ({type(exc).__name__}: {exc})")

    legislation = build_legislation(members, bills, session_id)

    crosswalk = {
        m.id: {"legiscan_people_id": int(m.ids["legiscan"]), "name": m.name,
               "party": m.party, "chamber": m.chamber, "district": m.district}
        for m in sorted(members, key=lambda x: x.id)
    }
    return BuildResult(
        members=members,
        bills=sorted(canonical_bills, key=lambda b: b.id),
        rollcalls=rollcalls,
        crosswalk=crosswalk,
        legislation=legislation,
        quarantined=quarantined,
    )


# --- network: fetch + decode the LegiScan bulk dataset --------------------


def _decode_dataset_zip(get_dataset_response: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Decode the base64 ZIP in a getDataset response → (people, bills, votes) lists."""
    raw = base64.b64decode(get_dataset_response["dataset"]["zip"])
    people: list[dict] = []
    bills: list[dict] = []
    votes: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            if "/people/" in name:
                people.append(json.loads(zf.read(name)))
            elif "/bill/" in name:
                bills.append(json.loads(zf.read(name)))
            elif "/vote/" in name:
                votes.append(json.loads(zf.read(name)))
    return people, bills, votes


def current_session(state: str = config.COVERED_STATE) -> dict:
    """The current REGULAR session dataset row (max year_start, non-special) from
    getDatasetList — carries `access_key` + `dataset_hash` (the nightly change gate).
    Deterministic given the API response; follows the newest regular session over time."""
    rows = [r for r in legiscan.dataset_list(state).get("datasetlist", [])
            if str(r.get("special", "0")) == "0"]
    if not rows:
        raise RuntimeError(f"no regular MS session in getDatasetList for {state}")
    return max(rows, key=lambda r: int(r["year_start"]))


def fetch_dataset(state: str = config.COVERED_STATE,
                  session: dict | None = None) -> tuple[dict, list, list, list]:
    """Network: pull the session's dataset and decode the ZIP → (session_row, people,
    bills, votes). `session` may be a pre-selected `current_session()` row (avoids a
    second getDatasetList call)."""
    session = session or current_session(state)
    resp = legiscan.get_dataset(int(session["session_id"]), session["access_key"])
    people, bills, votes = _decode_dataset_zip(resp)
    return session, people, bills, votes


# --- multi-session merge (pure; D87) --------------------------------------


def merge_member(prior: dict | None, fresh: Member) -> Member:
    """Fresh member record + the terms already on disk. Pure.

    A continuing legislator appears in every session's roster, so without this the
    2027 export would replace their file with a 2027-only term while their 2026 votes
    still counted against them — a career number over a one-session term list. Terms
    are deduped on the whole term and sorted by start, so a single-session re-export
    is byte-identical to what is already committed."""
    if prior is None:
        return fresh
    seen = {(t.start, t.end, t.party, t.chamber): t for t in fresh.terms}
    for raw in prior.get("terms", []):
        t = Term(**raw)
        seen.setdefault((t.start, t.end, t.party, t.chamber), t)
    return fresh.model_copy(
        update={"terms": sorted(seen.values(), key=lambda t: (t.start, t.end))}
    )


def merge_legislation(prior: dict | None, fresh: MemberLegislation) -> MemberLegislation:
    """Fresh sponsorship + what is already on disk, deduped on bill_id. Pure.

    MS legislation files are keyed by member, not by session, so without this the 2027
    export would drop every 2026 bill the member authored — silently lowering their
    sponsored/cosponsored/enacted numbers. Bill ids carry the session, so the union is
    unambiguous and a single-session re-export is byte-identical."""
    if prior is None:
        return fresh

    def _union(fresh_items: list[LegItem], prior_raw: list[dict]) -> list[LegItem]:
        by_id = {it.bill_id: it for it in fresh_items}
        for raw in prior_raw:
            by_id.setdefault(raw["bill_id"], LegItem(**raw))
        return [by_id[k] for k in sorted(by_id)]

    return fresh.model_copy(update={
        "sponsored": _union(fresh.sponsored, prior.get("sponsored", [])),
        "cosponsored": _union(fresh.cosponsored, prior.get("cosponsored", [])),
    })


def _read_json(path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _mark_departed(roster_ids: set[str]) -> list[str]:
    """Flip `serving` to false on every committed MS member NOT in the new session's
    roster, and return their ids. `export_members` only writes the members it is given,
    so a legislator who left after a session would otherwise stay `serving: true`
    forever. Rewrites only the files that actually change (quiet-night diff-gate)."""
    changed: list[str] = []
    if not MS_MEMBERS_DIR.exists():
        return changed
    for path in sorted(MS_MEMBERS_DIR.glob("*.json")):
        rec = _read_json(path)
        if rec is None or rec.get("id") in roster_ids or rec.get("serving") is False:
            continue
        rec["serving"] = False
        path.write_text(_dumps(rec), encoding="utf-8", newline="\n")
        changed.append(rec["id"])
    return changed


def disk_counts() -> dict:
    """The manifest `counts` recomputed from what is ON DISK under data/state/ms/.

    Was computed from the one session just built, which is the same thing while only
    one session exists — and wrong the moment two do (the manifest would describe 2027
    while the pages showed 2026 + 2027). Reads the committed partition only."""
    members = sorted(MS_MEMBERS_DIR.glob("*.json")) if MS_MEMBERS_DIR.exists() else []
    bills = sorted(MS_BILLS_DIR.glob("*.json")) if MS_BILLS_DIR.exists() else []
    votes = sorted(MS_VOTES_DIR.glob("*.json")) if MS_VOTES_DIR.exists() else []
    by_chamber: dict[str, int] = {}
    by_class: dict[str, int] = {}
    member_votes = 0
    for path in votes:
        rec = json.loads(path.read_text(encoding="utf-8"))
        rc = rec["rollcall"]
        by_chamber[rc["chamber"]] = by_chamber.get(rc["chamber"], 0) + 1
        by_class[rc["vote_class"]] = by_class.get(rc["vote_class"], 0) + 1
        member_votes += len(rec["member_votes"])
    return {
        "members": len(members),
        "rollcalls": len(votes),
        "rollcalls_by_chamber": dict(sorted(by_chamber.items())),
        "rollcalls_by_vote_class": dict(sorted(by_class.items())),
        "member_votes": member_votes,
        "bills": len(bills),
    }


# --- export + manifest ----------------------------------------------------


def _session_row(session: dict) -> dict:
    return {
        "session_id": int(session["session_id"]),
        "session_name": session.get("session_name", ""),
        "year_start": int(session["year_start"]),
        "year_end": int(session["year_end"]),
    }


def merge_sessions(prior_manifest: dict | None, session: dict) -> list[dict]:
    """Every session included in the committed partition, newest first (D87). Pure."""
    rows = {r["session_id"]: r for r in (prior_manifest or {}).get("sessions", [])}
    fresh = _session_row(session)
    rows[fresh["session_id"]] = fresh
    return sorted(rows.values(), key=lambda r: r["session_id"], reverse=True)


def build_ms_manifest(session: dict, counts: dict, sessions: list[dict],
                      generated_at: str, commit: str) -> dict:
    """The MS partition manifest (data/state/ms/manifest.json). generated_at/commit are
    INJECTED (the one wall-clock, mirroring the federal manifest, D51).

    `session_id`/`dataset_hash` describe the CURRENT session — the nightly change gate
    reads dataset_hash. `counts` describes the WHOLE committed partition and `sessions`
    lists every session in it: once 2027 lands the partition spans both, and a manifest
    that counted only the newest build would understate what the pages show (D87)."""
    return {
        "jurisdiction": "ms",
        "generated_at": generated_at,
        "commit": commit,
        "session_id": int(session["session_id"]),
        "session_name": session.get("session_name", ""),
        "dataset_hash": session["dataset_hash"],
        "year_start": int(session["year_start"]),
        "year_end": int(session["year_end"]),
        "sessions": sessions,
        "counts": counts,
    }


def _export_records(result: BuildResult) -> list[str]:
    """Write this session's records, MERGING with what is already committed (D87), and
    return the ids of members marked no-longer-serving. Byte-identical to a plain
    overwrite while only one session exists (every merge dedups to the same record)."""
    from ingest.export import MS_DIR, MS_LEGISLATION_DIR, export_member_legislation

    merged = [merge_member(_read_json(MS_MEMBERS_DIR / f"{m.id}.json"), m)
              for m in result.members]
    export_members(merged, MS_MEMBERS_DIR)
    for bill in result.bills:
        export_bill(bill, MS_BILLS_DIR)
    for rollcall, member_votes in result.rollcalls:
        export_rollcall(rollcall, member_votes, MS_VOTES_DIR)
    for leg in result.legislation:
        prior = _read_json(MS_LEGISLATION_DIR / f"{leg.member_id}.json")
        export_member_legislation(merge_legislation(prior, leg), MS_LEGISLATION_DIR)

    # The crosswalk is rebuilt from THIS session's roster, so a departed legislator
    # would drop out of it while their vote records still name them.
    MS_DIR.mkdir(parents=True, exist_ok=True)
    crosswalk = {**(_read_json(MS_DIR / "crosswalk.json") or {}), **result.crosswalk}
    (MS_DIR / "crosswalk.json").write_text(
        _dumps(dict(sorted(crosswalk.items()))), encoding="utf-8", newline="\n")
    return _mark_departed({m.id for m in result.members})


def _export_manifest(manifest: dict) -> None:
    from ingest.export import MS_MANIFEST_PATH

    MS_MANIFEST_PATH.write_text(_dumps(manifest), encoding="utf-8", newline="\n")


def _ms_manifest_path():
    from ingest.export import MS_MANIFEST_PATH

    return MS_MANIFEST_PATH


def _committed_dataset_hash() -> str | None:
    """The dataset_hash of the currently committed MS manifest, or None if none."""
    return (_read_json(_ms_manifest_path()) or {}).get("dataset_hash")


def run(argv: list[str] | None = None) -> int:
    """`ingest ms` — fetch the current MS session's LegiScan dataset, build the canonical
    records, and export them under data/state/ms/. Idempotent (a byte-identical session
    re-exports byte-identical).

    NIGHTLY GATE (D55): getDatasetList (one cheap call) carries the session's
    `dataset_hash`. If it equals the committed manifest's hash and the data is already
    present, nothing is re-fetched or rewritten — so a quiet night makes ONE request and
    produces ZERO diff (the manifest's wall-clock `generated_at` is not touched, so it
    never false-triggers the nightly diff-gate). `--force` bypasses the gate."""
    import os
    from datetime import UTC, datetime

    from ingest.export import _git_head

    args = argv or []
    if not legiscan.available():
        print("ingest ms: LEGISCAN_API_KEY absent — cannot ingest MS state data (H2).")
        return 2

    session_row = current_session()
    committed = _committed_dataset_hash()
    if ("--force" not in args and committed is not None
            and committed == session_row["dataset_hash"] and MS_VOTES_DIR.exists()):
        print(f"ingest ms: session {session_row['session_id']} unchanged "
              f"(dataset_hash {committed[:8]}) — nothing to do.")
        return 0

    prior_manifest = _read_json(_ms_manifest_path())
    prior_session = (prior_manifest or {}).get("session_id")
    if prior_session is not None and int(prior_session) != int(session_row["session_id"]):
        # Session rollover (D87). Nothing is deleted: MS numbers are CAREER numbers
        # spanning every ingested session (owner, 2026-09-30), matching the federal
        # side's 118th + 119th. The merges below are what make that safe.
        print(f"ingest ms: session rollover {prior_session} -> "
              f"{session_row['session_id']} — earlier sessions are KEPT (D87).")

    session, people, bills, votes = fetch_dataset(session=session_row)
    result = build_records(int(session["session_id"]), int(session["year_start"]),
                           int(session["year_end"]), people, bills, votes)

    total = len(votes) + len({str(_unwrap(v, "roll_call")["bill_id"]) for v in votes} - {"0"})
    if result.quarantined:
        frac = len(result.quarantined) / total if total else 0.0
        print(f"ingest ms: {len(result.quarantined)} quarantined ({frac:.2%}): "
              f"{result.quarantined[:10]}")
        if frac > config.QUARANTINE_MAX_FRACTION:
            print(f"FAIL: quarantine {frac:.2%} exceeds {config.QUARANTINE_MAX_FRACTION:.0%}")
            return 1

    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    generated_at = os.environ.get("CIVIC_GENERATED_AT", now)
    commit = os.environ.get("CIVIC_COMMIT") or _git_head()
    departed = _export_records(result)
    # Counts AFTER the export: they describe the committed partition, not this build.
    manifest = build_ms_manifest(session, disk_counts(),
                                 merge_sessions(prior_manifest, session),
                                 generated_at, commit)
    _export_manifest(manifest)
    if departed:
        print(f"ingest ms: {len(departed)} member(s) no longer serving, marked in place: "
              f"{departed[:10]}")

    # Tier-2 metrics recompute from the just-exported committed partition (INC-13).
    from ingest import ms_metrics
    ms_metrics.export()

    print(f"ingest ms: {session['session_name']} (session {session['session_id']}) - "
          f"{len(result.members)} members, {len(result.rollcalls)} roll calls, "
          f"{len(result.bills)} bills, {len(result.legislation)} legislation records, "
          f"metrics -> data/state/ms/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
