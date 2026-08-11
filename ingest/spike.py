"""INC-1 source feasibility spike (§7 INC-1).

Pulls one real sample from every federal source into the disk cache, copies each
into data/quality/samples/ (the committed INC-1 exception to the data/raw
gitignore, §6.2), and runs the LegiScan state-branch verdict test when a key is
present. Discovery-first: list endpoints are queried to find a real roll number /
vote number before fetching a detail, so no id is assumed.

Not a CI job — a manual run (`uv run ingest spike`) needing CONGRESS_API_KEY.
The secret-guard (`_assert_no_secret`) refuses to write any sample that contains
the API key value, so committed samples can never leak a credential.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

from ingest import env
from ingest.cache import repo_root
from ingest.config import COVERED_STATE
from ingest.sources import congress_gov, govinfo, legiscan, legislators, senate_xml

SAMPLES = repo_root() / "data" / "quality" / "samples"


def _write_sample(name: str, text: str) -> Path:
    _assert_no_secret(name, text)
    SAMPLES.mkdir(parents=True, exist_ok=True)
    path = SAMPLES / name
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"  sample: data/quality/samples/{name} ({len(text):,} bytes)")
    return path


def _assert_no_secret(name: str, text: str) -> None:
    """Refuse to write a committed sample that contains any configured secret."""
    for var in ("CONGRESS_API_KEY", "LEGISCAN_API_KEY"):
        val = env.get(var)
        if val and val in text:
            raise RuntimeError(
                f"REFUSING to write sample {name}: it contains the value of {var}. "
                "A credential must never enter a committed sample (header-auth only)."
            )


def _pretty_json(text: str) -> str:
    return json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False)


def run() -> int:
    # §0.6: run cleanly under PowerShell whatever the console codepage. Some of
    # our status output uses non-cp1252 glyphs; force UTF-8 so it never crashes.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass
    print("INC-1 spike — federal sources")

    # 1. Members (MS delegation) --------------------------------------------
    members = congress_gov.members_by_state(COVERED_STATE, current_only=True)
    _write_sample("congress_member_ms.json", _pretty_json(members.text))

    # 2. House vote: discover a real roll from the list, then detail+members --
    hv_list = congress_gov.house_vote_list(119, 1, limit=5)
    _write_sample("congress_house_vote_list_119_1.json", _pretty_json(hv_list.text))
    votes = json.loads(hv_list.text).get("houseRollCallVotes", [])
    if votes:
        roll = int(votes[0]["rollCallNumber"])
        detail = congress_gov.house_vote_detail(119, 1, roll)
        _write_sample(f"congress_house_vote_detail_119_1_{roll}.json", _pretty_json(detail.text))
        mem = congress_gov.house_vote_members(119, 1, roll)
        _write_sample(f"congress_house_vote_members_119_1_{roll}.json", _pretty_json(mem.text))
    else:
        print("  WARNING: house-vote list empty — noted in SHAPES.md")

    # 3. Bill detail with cboCostEstimates (D15) ----------------------------
    bill = congress_gov.bill_detail(119, "hr", 1)
    _write_sample("congress_bill_hr1_119.json", _pretty_json(bill.text))
    has_cbo = "cboCostEstimates" in json.loads(bill.text).get("bill", {})
    print(f"  hr1-119 cboCostEstimates present: {has_cbo}")

    # 4. CREC "personal explanation" search. The Congress.gov
    #    /congressional-record endpoint is only a date index (captured for the
    #    record), but govinfo /search DOES full-text search with the SAME
    #    api.data.gov key — that is the real INC-6 source.
    crec_index = congress_gov.congressional_record(limit=5)
    _write_sample("congress_congressional_record_index.json", _pretty_json(crec_index.text))
    crec_search = govinfo.crec_search("personal explanation", page_size=5)
    _write_sample(
        "govinfo_crec_search_personal_explanation.json",
        json.dumps(crec_search, indent=2, sort_keys=True, ensure_ascii=False),
    )
    print(f"  govinfo CREC 'personal explanation' hits: {crec_search.get('count')}")

    # 5. Senate: menu (discover a real vote number), then detail -------------
    menu = senate_xml.vote_menu(119, 1)
    _write_sample("senate_vote_menu_119_1.xml", menu.text)
    nums = re.findall(r"<vote_number>(\d+)</vote_number>", menu.text)
    if nums:
        sroll = int(nums[-1])  # menu is newest-first; last entry is vote 1
        sdetail = senate_xml.vote_detail(119, 1, sroll)
        _write_sample(f"senate_vote_detail_119_1_{sroll:05d}.xml", sdetail.text)
    else:
        print("  WARNING: senate menu had no vote_number — noted in SHAPES.md")

    # 6. Legislators crosswalk — cache full file, excerpt MS delegation ------
    leg = legislators.current()
    all_legs = yaml.safe_load(leg.text)
    ms = [p for p in all_legs if p.get("terms") and p["terms"][-1].get("state") == COVERED_STATE]
    ms_yaml = yaml.safe_dump(ms, sort_keys=True, allow_unicode=True)
    _write_sample("legislators_current_ms.yaml", ms_yaml)
    print(f"  legislators: {len(all_legs)} total → {len(ms)} MS delegation excerpted")

    # 7. State branch verdict test ------------------------------------------
    _run_state_verdict()

    print("INC-1 spike: federal samples written.")
    return 0


def _run_state_verdict() -> None:
    print("INC-1 spike — Mississippi state verdict (LegiScan)")
    if not legiscan.available():
        print("  LEGISCAN_API_KEY absent (H2 pending) → verdict = DEFER (Decision D18).")
        print("  federal build proceeds untouched; write-up in ms-state-verdict.md.")
        return
    try:
        sessions = legiscan.session_list(COVERED_STATE)
        _write_sample("legiscan_session_list_ms.json", _pretty_json(json.dumps(sessions)))
        print("  LegiScan reachable — complete the 5-bill position check per §7 INC-1 step 4.")
    except Exception as e:  # noqa: BLE001 — spike diagnostic; unreachable → DEFER
        print(f"  LegiScan unreachable ({type(e).__name__}) → verdict = DEFER.")


if __name__ == "__main__":
    raise SystemExit(run())
