"""V2-11 task 6 — the topic index (`ingest/topics.py`) and invariant 9.

What these tests exist to pin:

1. **The two vocabularies stay apart.** A bill's single `policy_area` and its many
   CRS `subjects` are different claims; merging them would publish one topic page
   that silently means both.
2. **A slug collision FAILS the run.** One URL cannot stand for two official terms
   — whichever way it resolved, a topic page would list bills the government did
   not put under the topic the reader asked for.
3. **Nothing is invented and nothing is a cap.** Terms are stored verbatim, and no
   assertion anywhere fixes the vocabulary size (SD-33's "31 + 872" was a measured
   snapshot; 877 subject terms were on disk partway through the backfill).

Fixtures in `tmp_path` only, never the real `data/` — the V2-11 backfill may be
writing `data/bills/` while the suite runs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest import topics
from ingest.export import _dumps


# --- fixtures ----------------------------------------------------------------
def _bill(bill_id="hr1-119", *, policy_area="Health", subjects=None, **over) -> dict:
    base = dict(
        id=bill_id, jurisdiction="us", congress=119, type="hr", number=1,
        title_official="A Bill", policy_area=policy_area, subjects=subjects,
        sponsor_id="A000001", cosponsor_ids=[], actions=None,
        latest_action="Referred.", latest_action_date="2026-03-04", cbo_estimates=[],
        source_url="https://www.congress.gov/bill/119/hr/1",
    )
    base.update(over)
    return base


def _dataset(tmp_path: Path, bills: list[dict]) -> Path:
    data = tmp_path / "data"
    (data / "bills").mkdir(parents=True)
    for b in bills:
        (data / "bills" / f"{b['id']}.json").write_text(json.dumps(b), encoding="utf-8")
    return data


# --- the slug rule -----------------------------------------------------------
@pytest.mark.parametrize(
    "name,want",
    [
        ("Health", "health"),
        ("Agriculture and Food", "agriculture-and-food"),
        ("Veterans' pensions", "veterans-pensions"),
        ("Labor, employment", "labor-employment"),
        (
            "Centers for Disease Control and Prevention (CDC)",
            "centers-for-disease-control-and-prevention-cdc",
        ),
        (
            "Alcoholic beverages and traffic safety (DUI/DWI)",
            "alcoholic-beverages-and-traffic-safety-dui-dwi",
        ),
        ("  padded  ", "padded"),
    ],
)
def test_the_slug_rule_is_total_not_a_list_of_special_cases(name: str, want: str) -> None:
    """Official terms are full of punctuation a URL cannot carry. The rule has to
    handle all of it mechanically, not case by case."""
    assert topics.slugify(name) == want


def test_the_official_term_is_never_altered_only_the_slug_is() -> None:
    """0.5: the government's string is what renders. The slug is only ever a URL."""
    data_name = "Veterans' pensions"
    entry = topics._entries({data_name: {"hr1-119"}}, vocabulary="subjects")[0]
    assert entry.name == data_name  # verbatim, apostrophe and all
    assert entry.slug == "veterans-pensions"


def test_a_slug_collision_fails_the_run_rather_than_picking_a_winner() -> None:
    """Two different official terms, one URL. Appending a counter would mean a topic
    page listing bills the government did not put under that topic."""
    with pytest.raises(topics.SlugCollision) as exc:
        topics._entries(
            {"Labor, employment": {"hr1-119"}, "Labor employment": {"hr2-119"}},
            vocabulary="subjects",
        )
    assert "labor-employment" in str(exc.value)
    assert "both slug to" in str(exc.value)


def test_a_term_with_no_alphanumerics_fails_rather_than_getting_an_empty_url() -> None:
    with pytest.raises(topics.SlugCollision) as exc:
        topics._entries({"---": {"hr1-119"}}, vocabulary="policy_areas")
    assert "cannot be given a URL" in str(exc.value)


# --- the two vocabularies ----------------------------------------------------
def test_policy_areas_and_subjects_are_separate_vocabularies(tmp_path: Path) -> None:
    """"Health" the policy area and "Health" the subject term are different claims
    about a bill and must not collapse into one topic."""
    data = _dataset(tmp_path, [_bill(policy_area="Health", subjects=["Health"])])
    index = topics.compute(data)
    assert [e.name for e in index.policy_areas] == ["Health"]
    assert [e.name for e in index.subjects] == ["Health"]
    assert index.counts == {"policy_areas": 1, "subjects": 1, "bills": 1}


def test_a_bill_contributes_to_one_policy_area_and_every_subject(tmp_path: Path) -> None:
    data = _dataset(tmp_path, [_bill(
        policy_area="Health", subjects=["Health care costs", "Medicare", "Drug safety"]
    )])
    index = topics.compute(data)
    assert len(index.policy_areas) == 1
    assert sorted(e.name for e in index.subjects) == [
        "Drug safety", "Health care costs", "Medicare"
    ]


def test_bill_ids_are_the_full_membership_and_are_sorted(tmp_path: Path) -> None:
    """Full membership, not a sample — a subscription on a topic has to resolve to
    every bill under it. Sorted so the file is byte-stable."""
    data = _dataset(tmp_path, [
        _bill("hr9-119", number=9, subjects=["Medicare"]),
        _bill("hr1-119", number=1, subjects=["Medicare"]),
        _bill("hr3-119", number=3, subjects=["Medicare"]),
    ])
    entry = topics.compute(data).subjects[0]
    assert entry.bill_ids == ["hr1-119", "hr3-119", "hr9-119"]
    assert entry.bill_count == 3 == len(entry.bill_ids)


def test_the_same_bill_is_counted_once_per_topic(tmp_path: Path) -> None:
    """A duplicate subject term on one bill must not inflate its own count."""
    data = _dataset(tmp_path, [_bill(subjects=["Medicare", "Medicare"])])
    assert topics.compute(data).subjects[0].bill_count == 1


# --- the D27 sentinel and missing values -------------------------------------
def test_subjects_not_yet_collected_contributes_nothing(tmp_path: Path) -> None:
    """D27: `None` = NOT YET COLLECTED, and the index simply grows as the backfill
    lands. Not an error, and not the same as "this bill has no subjects"."""
    index = topics.compute(_dataset(tmp_path, [_bill(subjects=None)]))
    assert index.subjects == []
    assert index.counts["bills"] == 1  # the bill is still counted as a bill


def test_subjects_collected_and_empty_also_contributes_nothing(tmp_path: Path) -> None:
    index = topics.compute(_dataset(tmp_path, [_bill(subjects=[])]))
    assert index.subjects == []


def test_a_bill_with_no_policy_area_is_not_given_one(tmp_path: Path) -> None:
    """D5: policy areas are government-assigned and never invented."""
    index = topics.compute(_dataset(tmp_path, [_bill(policy_area=None)]))
    assert index.policy_areas == []


def test_no_bills_directory_is_a_no_op(tmp_path: Path) -> None:
    assert topics.compute(tmp_path / "data") is None


# --- determinism (invariant 9's whole reason) --------------------------------
def test_entries_are_sorted_by_slug_not_by_count(tmp_path: Path) -> None:
    """Sorted by slug so the order does not move when a bill count changes — a
    count-ordered file would rewrite wholesale on any new bill."""
    data = _dataset(tmp_path, [
        _bill("hr1-119", number=1, subjects=["Zebra policy", "Apple policy"]),
        _bill("hr2-119", number=2, subjects=["Apple policy"]),
    ])
    index = topics.compute(data)
    assert [e.slug for e in index.subjects] == ["apple-policy", "zebra-policy"]
    assert [e.bill_count for e in index.subjects] == [2, 1]  # not count-ordered


def test_the_projection_is_byte_stable_across_runs(tmp_path: Path) -> None:
    data = _dataset(tmp_path, [
        _bill(f"hr{n}-119", number=n, policy_area=f"Area {n % 2}",
              subjects=[f"Term {n}", "Shared term"])
        for n in range(1, 6)
    ])
    assert _dumps(topics.compute(data).model_dump()) == _dumps(
        topics.compute(data).model_dump()
    )


def test_no_wall_clock_anywhere_in_the_module() -> None:
    src = Path(topics.__file__).read_text(encoding="utf-8")
    for banned in ("datetime", "time.time", "now(", "today("):
        assert banned not in src, f"{banned!r} in topics.py — invariant 9 needs no clock"


def test_nothing_asserts_a_vocabulary_SIZE() -> None:
    """SD-33 was ratified against a snapshot (31 policy areas, 872 CRS terms) and
    877 terms were already on disk partway through the backfill. The vocabulary is
    the government's to extend, so a hard-coded total would quarantine the dataset
    for the crime of a new subject term."""
    src = Path(topics.__file__).read_text(encoding="utf-8")
    assert "== 31" not in src and "== 872" not in src
    assert "assert" not in src.split('"""', 2)[-1]  # no assertions in the code body


# --- the CLI + the exporter --------------------------------------------------
def test_run_writes_the_index_and_reports_both_vocabularies(tmp_path, monkeypatch, capsys):
    from ingest import cache, export

    data = _dataset(tmp_path, [_bill(policy_area="Health", subjects=["Medicare"])])
    monkeypatch.setattr(cache, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(export, "TOPICS_DIR", data / "topics")
    assert topics.run([]) == 0
    out = capsys.readouterr().out
    assert "1 policy area(s) + 1 subject term(s) over 1 bill(s)" in out
    assert (data / "topics" / "index.json").exists()


def test_run_is_a_no_op_with_no_bills(tmp_path, monkeypatch, capsys) -> None:
    from ingest import cache

    monkeypatch.setattr(cache, "repo_root", lambda: tmp_path)
    (tmp_path / "data").mkdir()
    assert topics.run([]) == 0
    assert "no bills on disk yet" in capsys.readouterr().out


def test_run_refuses_an_unknown_argument(capsys) -> None:
    assert topics.run(["--all"]) == 2
    assert "unknown argument" in capsys.readouterr().out


def test_the_cli_routes_the_topics_subcommand(monkeypatch) -> None:
    from ingest import cli

    monkeypatch.setattr(topics, "run", lambda argv: 9)
    assert cli.main(["topics"]) == 9


def test_export_topics_is_atomic_and_byte_stable(tmp_path: Path) -> None:
    from ingest.export import export_topics

    index = topics.compute(_dataset(tmp_path, [_bill(subjects=["Medicare"])]))
    path = export_topics(index, out_dir=tmp_path / "out")
    first = path.read_bytes()
    export_topics(index, out_dir=tmp_path / "out")
    assert path.read_bytes() == first
    assert [p.name for p in (tmp_path / "out").iterdir()] == ["index.json"]  # no .tmp


def test_the_published_file_validates_against_its_own_schema(tmp_path: Path) -> None:
    from ingest.models import TopicsFile

    index = topics.compute(_dataset(tmp_path, [_bill(subjects=["Medicare"])]))
    raw = json.loads(_dumps(index.model_dump()))
    assert TopicsFile(**raw).counts["subjects"] == 1


# --- invariant 9 -------------------------------------------------------------
def test_invariant_9_passes_on_a_freshly_exported_index(tmp_path, monkeypatch) -> None:
    from ingest import export, verify_recompute

    data = _dataset(tmp_path, [_bill(subjects=["Medicare"])])
    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)
    export.export_topics(topics.compute(data), out_dir=data / "topics")
    assert verify_recompute.check_topics() == []


def test_invariant_9_catches_an_edited_official_term(tmp_path, monkeypatch) -> None:
    """0.5 forbids rewording government text. This is the check that notices."""
    from ingest import export, verify_recompute

    data = _dataset(tmp_path, [_bill(subjects=["Medicare"])])
    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)
    path = export.export_topics(topics.compute(data), out_dir=data / "topics")
    path.write_text(
        path.read_text(encoding="utf-8").replace("Medicare", "MEDICARE!"),
        encoding="utf-8",
    )
    assert any("committed bytes != recompute" in f
               for f in verify_recompute.check_topics())


def test_invariant_9_catches_a_stale_index_after_a_bill_changes(tmp_path, monkeypatch):
    from ingest import export, verify_recompute

    data = _dataset(tmp_path, [_bill(subjects=["Medicare"])])
    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)
    export.export_topics(topics.compute(data), out_dir=data / "topics")
    (data / "bills" / "hr2-119.json").write_text(
        json.dumps(_bill("hr2-119", number=2, subjects=["Medicare"])), encoding="utf-8"
    )
    assert any("committed bytes != recompute" in f
               for f in verify_recompute.check_topics())


def test_invariant_9_catches_an_index_with_no_bills_behind_it(tmp_path, monkeypatch):
    """A committed index over a bills directory that has gone away is a mismatch,
    not a no-op — the file claims a membership nothing can confirm."""
    from ingest import export, verify_recompute

    data = _dataset(tmp_path, [_bill(subjects=["Medicare"])])
    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)
    export.export_topics(topics.compute(data), out_dir=data / "topics")
    for f in (data / "bills").iterdir():
        f.unlink()
    (data / "bills").rmdir()
    assert any("no bills to derive it from" in f
               for f in verify_recompute.check_topics())


def test_invariant_9_is_a_no_op_before_the_topics_directory_exists(tmp_path, monkeypatch):
    from ingest import verify_recompute

    monkeypatch.setattr(verify_recompute, "repo_root", lambda: tmp_path)
    (tmp_path / "data").mkdir()
    assert verify_recompute.check_topics() == []
