"""INC-6 tests — personal-explanation parsing, member byline verification,
roll-call auto-matching, and the queue → approve → publish path. Offline: uses the
committed real Guest granule fixture + inline fixtures; the network search is not
exercised here (the parse/verify/match/publish machinery is).
"""

from __future__ import annotations

import json

import pytest

from curation import absences
from ingest.cache import repo_root
from ingest.models import Absence

GUEST_HTML = (
    repo_root() / "data" / "quality" / "samples" / "crec_personal_explanation_guest.htm"
).read_text(encoding="utf-8")

GUEST = {"id": "G000591", "name": "Michael Guest", "chamber": "house", "state": "MS"}
# A same-surname member from another state (the real wrong-Thompson collision).
THOMPSON_MS = {"id": "T000193", "name": "Bennie G. Thompson", "chamber": "house", "state": "MS"}

# Synthetic Glenn-Thompson-of-Pennsylvania granule (the actual false positive).
GLENN_PA_HTML = (
    "<pre>\n                          PERSONAL EXPLANATION\n\n"
    "                          HON. GLENN THOMPSON\n\n"
    "                            of pennsylvania\n\n"
    "                    in the house of representatives\n\n"
    "                         Thursday, May 1, 2025\n\n"
    "  Mr. THOMPSON of Pennsylvania. Mr. Speaker, I would have voted YEA on \n"
    "Roll Call No. 112.\n\n                          ____________________\n</pre>"
)


# --- parsing --------------------------------------------------------------


def test_parse_guest_granule():
    p = absences.parse_granule(GUEST_HTML)
    assert p["hon_name"] == "MICHAEL GUEST"
    assert p["state"] == "mississippi"
    assert p["roll_refs"] == [31]
    assert p["declared_position"] == "yea"
    # Verbatim, line-unwrapped, exact — no summarization.
    assert p["verbatim"] == (
        "Mr. GUEST. Mr. Speaker, had I been present, I would have voted YEA on "
        "Roll Call No. 31 (H.R. 22)."
    )


def test_multi_roll_leaves_position_none():
    two = GUEST_HTML.replace("Roll Call No. 31 (H.R. 22).",
                             "Roll Call No. 31 and NAY on Roll Call No. 32.")
    p = absences.parse_granule(two)
    assert p["roll_refs"] == [31, 32]
    assert p["declared_position"] is None  # can't mechanically pair positions to rolls


# --- byline verification (the wrong-state gate) ---------------------------


def test_verify_accepts_covered_member():
    assert absences.verify_member(absences.parse_granule(GUEST_HTML), GUEST) is True


def test_verify_rejects_same_surname_other_state():
    parsed = absences.parse_granule(GLENN_PA_HTML)
    assert parsed["state"] == "pennsylvania"
    assert absences.verify_member(parsed, THOMPSON_MS) is False  # MS member, PA byline


# --- roll-call auto-matching ----------------------------------------------


def test_match_rollcall_uses_stub_existence(monkeypatch, tmp_path):
    monkeypatch.setattr(absences, "ABSENCES_DIR", tmp_path)
    # V2-1: data/absences/ is sharded one level by congress.
    (tmp_path / "118").mkdir()
    (tmp_path / "118" / "G000591--h-118-1-0031.json").write_text("{}", encoding="utf-8")
    # 2023 granule → only 118/1 session qualifies; the stub exists → unique match.
    assert absences.match_rollcall("G000591", "house", 31, 2023) == "h-118-1-0031"
    # No stub for roll 99 → unmatched.
    assert absences.match_rollcall("G000591", "house", 99, 2023) is None


def test_match_ambiguous_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(absences, "ABSENCES_DIR", tmp_path)
    (tmp_path / "118").mkdir()
    (tmp_path / "118" / "G000591--h-118-1-0031.json").write_text("{}", encoding="utf-8")
    (tmp_path / "118" / "G000591--h-118-2-0031.json").write_text("{}", encoding="utf-8")
    # 2024 granule → both 118/1 and 118/2 qualify and both stubs exist → ambiguous.
    assert absences.match_rollcall("G000591", "house", 31, 2024) is None


# --- candidate build ------------------------------------------------------


def test_build_candidate_verified_and_matched(monkeypatch, tmp_path):
    monkeypatch.setattr(absences, "ABSENCES_DIR", tmp_path)
    (tmp_path / "118").mkdir()
    (tmp_path / "118" / "G000591--h-118-1-0031.json").write_text("{}", encoding="utf-8")
    result = {"granuleId": "CREC-2023-01-13-pt1-PgE29-4", "packageId": "CREC-2023-01-13",
              "dateIssued": "2023-01-13"}
    cand = absences.build_candidate(result, GUEST_HTML, [GUEST, THOMPSON_MS])
    assert cand is not None
    assert cand["member_id"] == "G000591"
    assert cand["matched_rollcall_id"] == "h-118-1-0031"
    assert cand["declared_position"] == "yea"
    assert cand["status"] == "pending"


def test_build_candidate_rejects_unverifiable(monkeypatch, tmp_path):
    monkeypatch.setattr(absences, "ABSENCES_DIR", tmp_path)
    result = {"granuleId": "g", "packageId": "p", "dateIssued": "2025-05-01"}
    # Only an MS delegation to match against; a PA byline verifies against nobody.
    assert absences.build_candidate(result, GLENN_PA_HTML, [THOMPSON_MS, GUEST]) is None


# --- approve → publish (end-to-end on real data, in tmp) ------------------


def _guest_candidate() -> dict:
    return {
        "granule_id": "CREC-2023-01-13-pt1-PgE29-4", "package_id": "CREC-2023-01-13",
        "date_issued": "2023-01-13", "member_id": "G000591", "hon_name": "MICHAEL GUEST",
        "source_url": "https://www.govinfo.gov/app/details/CREC-2023-01-13/CREC-2023-01-13-pt1-PgE29-4",
        "verbatim_text": "Mr. GUEST. Mr. Speaker, had I been present, I would have voted YEA "
                         "on Roll Call No. 31 (H.R. 22).",
        "roll_refs": [31], "matched_rollcall_id": "h-118-1-0031",
        "declared_position": "yea", "status": "pending",
    }


def test_approve_publishes_verbatim_reason(monkeypatch, tmp_path):
    absdir = tmp_path / "absences"
    qdir = tmp_path / "queue"
    (absdir / "118").mkdir(parents=True)  # V2-1: sharded one level by congress
    qdir.mkdir()
    monkeypatch.setattr(absences, "ABSENCES_DIR", absdir)
    monkeypatch.setattr(absences, "QUEUE_DIR", qdir)
    # Seed the pending queue file + the not_voting stub it matches.
    qpath = qdir / "CREC-2023-01-13-pt1-PgE29-4.json"
    qpath.write_text(json.dumps(_guest_candidate()), encoding="utf-8")
    stub = absdir / "118" / "G000591--h-118-1-0031.json"
    stub.write_text(json.dumps(
        {"member_id": "G000591", "rollcall_id": "h-118-1-0031", "stated_reason": None,
         "stated_reason_source": None, "declared_position": None}), encoding="utf-8")

    written = absences.approve_one(qpath)

    published = json.loads(written.read_text(encoding="utf-8"))
    Absence(**published)  # round-trips through the model (invariants hold)
    assert published["stated_reason"].startswith("Mr. GUEST. Mr. Speaker")
    assert published["stated_reason_source"].startswith("https://www.govinfo.gov/app/details/")
    assert published["declared_position"] == "yea"
    # The queue file is marked approved (idempotent; re-approve won't republish blindly).
    assert json.loads(qpath.read_text(encoding="utf-8"))["status"] == "approved"


def _seed_guest(tmp_path):
    """A pending Guest queue file + its matching not_voting stub, in tmp dirs."""
    absdir = tmp_path / "absences"
    qdir = tmp_path / "queue"
    (absdir / "118").mkdir(parents=True)  # V2-1: sharded one level by congress
    qdir.mkdir()
    qpath = qdir / "CREC-2023-01-13-pt1-PgE29-4.json"
    qpath.write_text(json.dumps(_guest_candidate()), encoding="utf-8")
    (absdir / "118" / "G000591--h-118-1-0031.json").write_text(json.dumps(
        {"member_id": "G000591", "rollcall_id": "h-118-1-0031", "stated_reason": None,
         "stated_reason_source": None, "declared_position": None}), encoding="utf-8")
    return absdir, qpath


def test_edit_accepts_exact_and_trim(monkeypatch, tmp_path):
    absdir, qpath = _seed_guest(tmp_path)
    monkeypatch.setattr(absences, "ABSENCES_DIR", absdir)
    verbatim = _guest_candidate()["verbatim_text"]
    # A trim (drop the salutation) is a whitespace-normalized substring → allowed.
    trimmed = "had I been present, I would have voted YEA on Roll Call No. 31 (H.R. 22)."
    written = absences.approve_one(qpath, reason=trimmed)
    assert json.loads(written.read_text(encoding="utf-8"))["stated_reason"] == trimmed
    # Re-approving with the exact verbatim also passes (idempotent, substring of itself).
    assert absences.approve_one(qpath, reason=verbatim).exists()


def test_edit_refuses_paraphrase_and_empty(monkeypatch, tmp_path):
    absdir, qpath = _seed_guest(tmp_path)
    monkeypatch.setattr(absences, "ABSENCES_DIR", absdir)
    with pytest.raises(ValueError, match="not a substring"):
        absences.approve_one(qpath, reason="I was sick that day.")  # rewrite, not a trim
    with pytest.raises(ValueError, match="empty"):
        absences.approve_one(qpath, reason="   ")  # whitespace-only publishes nothing


def test_publish_refuses_unmatched(monkeypatch, tmp_path):
    monkeypatch.setattr(absences, "ABSENCES_DIR", tmp_path)
    cand = _guest_candidate()
    cand["matched_rollcall_id"] = None
    with pytest.raises(ValueError, match="no matched roll call"):
        absences._publish(cand, cand["verbatim_text"])


# --- publication-gate invariant -------------------------------------------


def test_committed_absences_have_no_unapproved_reason():
    # Guard the whole published set: no committed absence carries a stated_reason
    # without its source (the model invariant), and unapproved stubs stay null.
    absdir = repo_root() / "data" / "absences"
    for path in absdir.glob("*/*.json"):  # V2-1: sharded one level by congress
        rec = json.loads(path.read_text(encoding="utf-8"))
        Absence(**rec)  # every published file satisfies stated_reason ⇒ source
