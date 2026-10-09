"""§5 Phase 3 owner decision 10 — the 40-member pilot draw. No network.

The properties under test are the ones the decision exists for: equal by party,
proportional by chamber, nobody hand-picked, every exclusion applied, and the same
(seed, roster) always producing the same 40. The roster snapshot is faked; the real
`legislators.current()` is never called.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ingest import pilot


def _member(
    mid: str,
    party: str = "D",
    chamber: str = "house",
    state: str = "CA",
    *,
    serving: bool = True,
    jurisdiction: str = "us",
) -> dict:
    return {
        "id": mid,
        "name": f"Member {mid}",
        "party": party,
        "chamber": chamber,
        "state": state,
        "serving": serving,
        "jurisdiction": jurisdiction,
    }


def _roster(n_per_cell: int = 30) -> tuple[list[dict], set[str]]:
    """A synthetic roster big enough for every cell, plus its current-ids set."""
    members: list[dict] = []
    for party in ("D", "R"):
        for chamber in ("house", "senate"):
            for i in range(n_per_cell):
                members.append(
                    _member(f"{party}{chamber[0].upper()}{i:03d}", party=party, chamber=chamber)
                )
    return members, {m["id"] for m in members}


# --- eligibility ---------------------------------------------------------------------


def test_every_exclusion_in_decision_10_is_applied() -> None:
    current = {"KEEP", "LEFT_OFFICE_ABSENT", "DELEGATE", "INDY", "STATE_LEG", "ODD_CHAMBER"}
    members = [
        _member("KEEP"),
        # serving=true but gone from the live roster: the mid-term departure case
        _member("DEPARTED"),
        _member("NOT_SERVING", serving=False),
        _member("DELEGATE", state="DC"),
        _member("INDY", party="I"),
        _member("STATE_LEG", jurisdiction="ms"),
        _member("ODD_CHAMBER", chamber="assembly"),
    ]
    assert [c.id for c in pilot.eligible(members, current)] == ["KEEP"]


def test_a_mid_term_departure_is_excluded_even_though_serving_is_true() -> None:
    """The whole reason decision 10 needs the roster as well as `serving`."""
    members = [_member("STILL_HERE"), _member("RESIGNED")]
    assert all(m["serving"] for m in members)
    kept = pilot.eligible(members, {"STILL_HERE"})
    assert [c.id for c in kept] == ["STILL_HERE"]


def test_eligible_is_id_sorted_so_the_draw_cannot_depend_on_file_order() -> None:
    members = [_member("Z999"), _member("A001"), _member("M500")]
    ids = {"Z999", "A001", "M500"}
    assert [c.id for c in pilot.eligible(members, ids)] == ["A001", "M500", "Z999"]


def test_pools_ignores_a_candidate_outside_the_four_cells() -> None:
    c = pilot.Candidate(id="X", name="n", party="I", chamber="senate", state="VT")
    assert all(len(v) == 0 for v in pilot.pools([c]).values())


# --- the draw ------------------------------------------------------------------------


def test_the_draw_is_equal_by_party_and_proportional_by_chamber() -> None:
    members, current = _roster()
    picked = pilot.draw(pilot.eligible(members, current))

    assert {cell: len(v) for cell, v in picked.items()} == {
        ("D", "house"): 16, ("D", "senate"): 4, ("R", "house"): 16, ("R", "senate"): 4,
    }
    per_party: dict[str, int] = {}
    for (party, _chamber), rows in picked.items():
        per_party[party] = per_party.get(party, 0) + len(rows)
    assert per_party == {"D": 20, "R": 20}
    assert sum(per_party.values()) == 40


def test_the_same_seed_and_roster_always_draw_the_same_40() -> None:
    members, current = _roster()
    a = pilot.draw(pilot.eligible(members, current), seed=20261009)
    b = pilot.draw(pilot.eligible(members, current), seed=20261009)
    assert {k: [c.id for c in v] for k, v in a.items()} == {
        k: [c.id for c in v] for k, v in b.items()
    }


def test_a_different_seed_draws_a_different_40() -> None:
    members, current = _roster()
    a = pilot.draw(pilot.eligible(members, current), seed=1)
    b = pilot.draw(pilot.eligible(members, current), seed=2)
    assert [c.id for c in a[("D", "house")]] != [c.id for c in b[("D", "house")]]


def test_file_order_cannot_change_the_draw() -> None:
    """Shuffled input, identical output — the draw is a function of (seed, roster)."""
    members, current = _roster()
    straight = pilot.draw(pilot.eligible(members, current))
    reversed_ = pilot.draw(pilot.eligible(list(reversed(members)), current))
    assert {k: [c.id for c in v] for k, v in straight.items()} == {
        k: [c.id for c in v] for k, v in reversed_.items()
    }


def test_a_short_cell_raises_rather_than_quietly_drawing_fewer() -> None:
    """A 15-member cell would silently break the equal-n property."""
    members, current = _roster(n_per_cell=3)
    with pytest.raises(pilot.PilotError, match=r"D/house has 3 eligible member\(s\)"):
        pilot.draw(pilot.eligible(members, current))


# --- the committed sample ------------------------------------------------------------


def test_the_sample_records_the_seed_and_the_roster_snapshot() -> None:
    """The seed alone does not make the draw reproducible: the roster is a live file."""
    members, current = _roster()
    cands = pilot.eligible(members, current)
    sample = pilot.render(
        pilot.draw(cands), pilot.pools(cands), seed=7,
        roster_url="https://example.invalid/legislators-current.yaml",
        roster_fetched_at="2026-10-09T19:53:23.597766+00:00",
    )
    assert sample["seed"] == 7
    assert sample["roster_snapshot"]["fetched_at"] == "2026-10-09T19:53:23.597766+00:00"
    assert sample["ratified"] == "2026-10-09"
    assert "decision 10" in sample["decision"]
    assert len(sample["excluded_by_decision"]) == 3
    assert [(c["party"], c["chamber"], c["drawn"]) for c in sample["cells"]] == [
        ("D", "house", 16), ("D", "senate", 4), ("R", "house", 16), ("R", "senate", 4),
    ]
    assert sample["cells"][0]["eligible_pool"] == 30
    assert len(pilot.sample_ids(sample)) == 40


# --- the committed artifact on disk --------------------------------------------------


def test_the_shipped_sample_matches_decision_10() -> None:
    """The real data/config/statement-pilot.yaml, as committed."""
    path = Path(__file__).resolve().parents[1] / "data" / "config" / "statement-pilot.yaml"
    sample = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert sample["seed"] == pilot.SEED
    assert sample["roster_snapshot"]["fetched_at"]
    ids = pilot.sample_ids(sample)
    assert len(ids) == 40
    assert len(set(ids)) == 40, "a member drawn twice"

    counts = {(c["party"], c["chamber"]): len(c["members"]) for c in sample["cells"]}
    assert counts == {
        ("D", "house"): 16, ("D", "senate"): 4, ("R", "house"): 16, ("R", "senate"): 4,
    }


def test_nobody_in_the_shipped_sample_is_excluded_by_decision_10() -> None:
    """Cross-checks the artifact against the committed roster, not against the code that
    wrote it: no delegate, no independent, nobody marked not serving."""
    root = Path(__file__).resolve().parents[1]
    sample = yaml.safe_load(
        (root / "data" / "config" / "statement-pilot.yaml").read_text(encoding="utf-8"))
    for mid in pilot.sample_ids(sample):
        rec = json.loads((root / "data" / "members" / f"{mid}.json").read_text(encoding="utf-8"))
        assert rec["jurisdiction"] == "us"
        assert rec["serving"] is True
        assert rec["party"] in ("D", "R")
        assert rec["chamber"] in ("house", "senate")
        assert rec["state"] in pilot.VOTING_STATES, f"{mid} is a non-voting seat"


# --- the runner ----------------------------------------------------------------------


def _fake_repo(tmp_path: Path, members: list[dict]) -> Path:
    mdir = tmp_path / "data" / "members"
    mdir.mkdir(parents=True)
    for m in members:
        (mdir / f"{m['id']}.json").write_text(json.dumps(m), encoding="utf-8")
    return tmp_path


def test_a_missing_roster_is_named_rather_than_crashing(tmp_path: Path) -> None:
    with pytest.raises(pilot.PilotError, match="no committed roster"):
        pilot._load_members(tmp_path / "data")


def test_run_writes_the_sample_and_reports_each_cell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    members, current = _roster()
    repo = _fake_repo(tmp_path, members)
    monkeypatch.setattr(pilot, "repo_root", lambda: repo)
    monkeypatch.setattr(
        pilot, "_roster_snapshot",
        lambda: (current, "https://example.invalid/r.yaml", "2026-10-09T00:00:00+00:00"),
    )

    assert pilot.run([]) == 0
    out = capsys.readouterr().out
    assert "40 members" in out
    assert f"seed {pilot.SEED}" in out
    assert "D/house   drew 16 of  30 eligible" in out

    written = yaml.safe_load(
        (repo / "data" / "config" / "statement-pilot.yaml").read_text(encoding="utf-8"))
    assert len(pilot.sample_ids(written)) == 40


def test_run_refuses_to_silently_redraw_an_existing_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The drawn 40 is a committed decision, not a derived artifact."""
    members, current = _roster()
    repo = _fake_repo(tmp_path, members)
    out_path = repo / "data" / "config" / "statement-pilot.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("seed: 1\ncells: []\n", encoding="utf-8")
    monkeypatch.setattr(pilot, "repo_root", lambda: repo)
    monkeypatch.setattr(
        pilot, "_roster_snapshot",
        lambda: (current, "https://example.invalid/r.yaml", "2026-10-09T00:00:00+00:00"),
    )

    assert pilot.run([]) == 0
    assert "already exists" in capsys.readouterr().out
    assert out_path.read_text(encoding="utf-8") == "seed: 1\ncells: []\n"

    assert pilot.run(["--force"]) == 0
    assert len(pilot.sample_ids(
        yaml.safe_load(out_path.read_text(encoding="utf-8")))) == 40


def test_roster_snapshot_reads_the_cache_meta_not_the_wall_clock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`fetched_at` must be the cache's record of when the bytes arrived."""
    yaml_path = tmp_path / "abc.yaml"
    yaml_path.write_text(
        "- id:\n    bioguide: A000001\n- id:\n    bioguide: B000002\n- id: {}\n",
        encoding="utf-8",
    )
    (tmp_path / "abc.meta").write_text(
        json.dumps({"url": "https://example.invalid/r.yaml",
                    "fetched_at": "2026-10-09T12:34:56+00:00"}),
        encoding="utf-8",
    )

    class _Resp:
        path = yaml_path
        text = yaml_path.read_text(encoding="utf-8")

    from ingest.sources import legislators

    monkeypatch.setattr(legislators, "current", lambda: _Resp())
    ids, url, fetched_at = pilot._roster_snapshot()
    assert ids == {"A000001", "B000002"}
    assert url == "https://example.invalid/r.yaml"
    assert fetched_at == "2026-10-09T12:34:56+00:00"
