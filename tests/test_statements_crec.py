"""§5 Phase 3 task 2 collector (b) — Congressional Record speeches. No network.

The properties under test are the ones the collector's correctness rests on:

  * attribution comes from the Record's own `role="SPEAKING"`, so a member listed in a
    granule for any other reason (a roll-call tally lists all 435 names) is never
    collected as having spoken;
  * a member's own words are cut at the next speaker, and a shared surname never steals
    the other member's turn;
  * nothing is dropped silently — a granule MODS says the member spoke in, but whose text
    yields no attributable words, is kept, flagged and counted;
  * the run makes no AI call and takes no archive snapshot.

Every fetch is faked. `govinfo` is never called for real.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ingest import statements_crec as crec

# --- fixtures ------------------------------------------------------------------------

MODS_HEAD = (
    '<mods xmlns="http://www.loc.gov/mods/v3" version="3.3">'
)


def _granule(
    access_id: str,
    *,
    granule_class: str = "HOUSE",
    sub: str = "ALLOTHER",
    date: str = "2026-09-16",
    title: str = "A BILL; Congressional Record Vol. 172, No. 146",
    members: tuple[tuple[str, str, str], ...] = (),
) -> str:
    """One constituent granule, in the shape the real MODS uses: an `extension` block
    carrying the granule's identity and a `congMember` per member with their role."""
    people = "".join(
        f'<congMember bioGuideId="{bid}" chamber="H" congress="119" party="R" '
        f'role="{role}" state="KY"><name type="parsed">{parsed}</name>'
        f'<name type="authority-lnf">Last, First</name></congMember>'
        for bid, role, parsed in members
    )
    return (
        "<relatedItem type='constituent'><extension>"
        f"<searchTitle>{title}</searchTitle>"
        f"<granuleClass>{granule_class}</granuleClass>"
        f"<accessId>{access_id}</accessId>"
        f"<subGranuleClass>{sub}</subGranuleClass>"
        "<chamber>HOUSE</chamber>"
        f"<granuleDate>{date}</granuleDate>"
        f"{people}"
        "</extension></relatedItem>"
    )


def _issue(*granules: str) -> str:
    return MODS_HEAD + "".join(granules) + "</mods>"


SPEECH_TEXT = """<html><body><pre>
Congressional Record, Volume 172 Issue 146 (Wednesday, September 16, 2026)
[Congressional Record Volume 172, Number 146]
[House]
[Pages H5959-H5960]
From the Congressional Record Online through the Government Publishing Office [www.gpo.gov]

                               A BILL

  The SPEAKER pro tempore. The question is on the motion.
  Mr. MASSIE. Mr. Speaker, I rise in opposition to this bill because it
raises the deficit.
  I yield back the balance of my time.
  Mr. KELLY of Mississippi. Mr. Speaker, I support the bill.
  Mr. KELLY of Pennsylvania. Mr. Speaker, I do not.
</pre></body></html>"""

INSERTION_TEXT = """<html><body><pre>
[Extensions of Remarks]
                      HONORING A LOCAL VOLUNTEER

                                 ______

                            HON. JANE DOE

                              of kentucky

                    in the house of representatives

                        Friday, October 9, 2026

  The volunteer served for thirty years and deserves our thanks.
</pre></body></html>"""


def _pilot_yaml(tmp_path: Path, members: list[dict[str, str]]) -> Path:
    """A committed-shaped pilot sample holding exactly `members`."""
    cells: dict[tuple[str, str], list[dict[str, str]]] = {}
    for m in members:
        cells.setdefault((m["party"], m["chamber"]), []).append(
            {"id": m["id"], "name": m["name"], "state": m["state"]}
        )
    sample = {
        "seed": 20261009,
        "cells": [
            {"party": p, "chamber": c, "drawn": len(ms), "eligible_pool": 99, "members": ms}
            for (p, c), ms in cells.items()
        ],
    }
    path = tmp_path / "data" / "config" / "statement-pilot.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(sample, sort_keys=False), encoding="utf-8")
    return path


# --- parse_issue ---------------------------------------------------------------------


def test_only_speaking_members_are_collected() -> None:
    """A roll-call tally lists every member who voted. None of them spoke."""
    xml = _issue(
        _granule(
            "CREC-2026-09-16-pt1-PgH5959",
            members=(
                ("M001184", "SPEAKING", "Mr. MASSIE"),
                ("K000388", "VOTED YES", "Mr. KELLY of Mississippi"),
            ),
        )
    )
    rows = crec.parse_issue(xml, {"M001184", "K000388"}, package_id="CREC-2026-09-16")
    assert [r.member_id for r in rows] == ["M001184"]
    assert rows[0].parsed_name == "Mr. MASSIE"
    assert rows[0].package_id == "CREC-2026-09-16"
    assert rows[0].title == "A BILL"  # the "; Congressional Record Vol." tail is dropped
    assert rows[0].url.endswith("CREC-2026-09-16/CREC-2026-09-16-pt1-PgH5959")


def test_members_outside_the_pilot_are_ignored() -> None:
    xml = _issue(
        _granule("CREC-2026-09-16-pt1-PgH1", members=(("X000001", "SPEAKING", "Mr. OTHER"),))
    )
    assert crec.parse_issue(xml, {"M001184"}) == []


def test_classes_outside_the_record_proper_are_skipped() -> None:
    """The daily digest is GPO's summary of the day, not any member's words."""
    xml = _issue(
        _granule(
            "CREC-2026-09-16-pt1-PgD1",
            granule_class="DAILYDIGEST",
            members=(("M001184", "SPEAKING", "Mr. MASSIE"),),
        ),
        _granule(
            "CREC-2026-09-16-pt1-PgE1",
            granule_class="EXTENSIONS",
            members=(("M001184", "SPEAKING", "Mr. MASSIE"),),
        ),
    )
    rows = crec.parse_issue(xml, {"M001184"})
    assert [r.granule_class for r in rows] == ["EXTENSIONS"]


def test_a_granule_without_an_access_id_is_skipped() -> None:
    xml = (
        MODS_HEAD
        + "<relatedItem><extension><granuleClass>HOUSE</granuleClass>"
        '<congMember bioGuideId="M001184" role="SPEAKING"/></extension></relatedItem>'
        + "</mods>"
    )
    assert crec.parse_issue(xml, {"M001184"}) == []


def test_the_speaker_count_counts_everyone_not_only_the_pilot() -> None:
    """A debate with one pilot member and one other speaker is not a sole-speaker
    granule. Counting only the pilot 40 would attribute the whole exchange to the one
    member who happens to be in the sample."""
    xml = _issue(
        _granule(
            "CREC-2026-09-16-pt1-PgH5959",
            members=(
                ("M001184", "SPEAKING", "Mr. MASSIE"),
                ("X000001", "SPEAKING", "Mr. OTHER"),
                ("K000388", "VOTED YES", "Mr. KELLY of Mississippi"),
            ),
        )
    )
    rows = crec.parse_issue(xml, {"M001184"})
    assert len(rows) == 1
    assert rows[0].speakers == 2


def test_a_speaking_member_with_no_parsed_name_still_counts() -> None:
    """The count must not depend on the name being present; only the text extraction does."""
    xml = (
        MODS_HEAD
        + "<relatedItem><extension><granuleClass>HOUSE</granuleClass>"
        "<accessId>CREC-2026-09-16-pt1-PgH9</accessId>"
        "<granuleDate>2026-09-16</granuleDate>"
        '<congMember bioGuideId="M001184" role="SPEAKING">'
        '<name type="authority-lnf">Massie, Thomas</name></congMember>'
        "</extension></relatedItem></mods>"
    )
    rows = crec.parse_issue(xml, {"M001184"})
    assert rows[0].parsed_name == ""


def test_package_id_falls_back_to_the_granule_id_when_not_supplied() -> None:
    xml = _issue(
        _granule("CREC-2026-09-16-pt1-PgH5", members=(("M001184", "SPEAKING", "Mr. MASSIE"),))
    )
    assert crec.parse_issue(xml, {"M001184"})[0].package_id == "CREC-2026-09-16"


def test_rows_are_sorted_so_a_reparse_is_identical() -> None:
    xml = _issue(
        _granule("CREC-2026-09-16-pt1-PgH9", date="2026-09-16",
                 members=(("M001184", "SPEAKING", "Mr. MASSIE"),)),
        _granule("CREC-2026-09-16-pt1-PgH1", date="2026-09-15",
                 members=(("M001184", "SPEAKING", "Mr. MASSIE"),)),
    )
    rows = crec.parse_issue(xml, {"M001184"})
    assert [r.date for r in rows] == ["2026-09-15", "2026-09-16"]


def test_unparseable_mods_raises_rather_than_counting_zero() -> None:
    with pytest.raises(crec.CrecError, match="unparseable MODS"):
        crec.parse_issue("<mods", {"M001184"})


# --- text and segments ---------------------------------------------------------------


def test_plain_text_drops_markup_and_the_citation_header() -> None:
    text = crec.plain_text(
        "<html><body><style>p{}</style><pre>[House]\nMr. X said &quot;hi&quot;.</pre></body></html>"
    )
    assert "[House]" not in text
    assert "p{}" not in text
    assert 'Mr. X said "hi".' in text


def test_a_members_turn_is_cut_at_the_next_speaker() -> None:
    text = crec.plain_text(SPEECH_TEXT)
    segments = crec.speaker_segments(text, "Mr. MASSIE")
    assert len(segments) == 1
    assert segments[0].startswith("Mr. MASSIE. Mr. Speaker, I rise in opposition")
    assert "I yield back" in segments[0]  # his own continued paragraph
    assert "Mr. KELLY" not in segments[0]  # the next speaker is not his


def test_a_shared_surname_never_takes_the_other_members_turn() -> None:
    text = crec.plain_text(SPEECH_TEXT)
    mississippi = crec.speaker_segments(text, "Mr. KELLY of Mississippi")
    assert len(mississippi) == 1
    assert "I support the bill" in mississippi[0]
    assert "I do not" not in mississippi[0]


def test_the_state_qualifier_is_optional_in_the_text() -> None:
    """MODS may give the bare name where the Record printed the qualified one."""
    text = crec.plain_text(SPEECH_TEXT)
    assert len(crec.speaker_segments(text, "Mr. KELLY")) == 2


def test_a_missing_parsed_name_yields_no_segment() -> None:
    assert crec.speaker_segments(crec.plain_text(SPEECH_TEXT), "") == []


def test_a_speaker_who_never_spoke_yields_no_segment() -> None:
    assert crec.speaker_segments(crec.plain_text(SPEECH_TEXT), "Mr. ABSENT") == []


def _row(parsed: str = "Mr. MASSIE", granule_class: str = "HOUSE") -> crec.Speaking:
    return crec.Speaking(
        member_id="M001184", date="2026-09-16", granule_id="G", package_id="P",
        granule_class=granule_class, sub_granule_class="ALLOTHER", chamber="HOUSE",
        title="A BILL", parsed_name=parsed, url="https://example.invalid/G",
    )


def test_a_turn_is_recorded_as_a_turn() -> None:
    record = crec.statement_record(
        _row(), crec.plain_text(SPEECH_TEXT), sole_speaker=False
    )
    assert record["attribution"] == "turn"
    assert record["chars"] == len(record["segments"][0])


def test_a_sole_speaker_insertion_keeps_its_body_without_gpos_header() -> None:
    record = crec.statement_record(
        _row(parsed="Mr. NOMATCH", granule_class="EXTENSIONS"),
        crec.plain_text(INSERTION_TEXT),
        sole_speaker=True,
    )
    assert record["attribution"] == "sole-speaker"
    assert record["segments"] == ["The volunteer served for thirty years and deserves our thanks."]


def test_a_granule_with_no_attributable_words_is_kept_and_flagged() -> None:
    record = crec.statement_record(
        _row(parsed="Mr. NOMATCH"), crec.plain_text(SPEECH_TEXT), sole_speaker=False
    )
    assert record["attribution"] == "none"
    assert record["segments"] == []
    assert record["chars"] == 0


def test_a_sole_speaker_granule_with_no_body_is_kept_and_flagged() -> None:
    record = crec.statement_record(_row(parsed=""), "   ", sole_speaker=True)
    assert record["attribution"] == "sole-speaker"
    assert record["segments"] == []


# --- the pilot sample ----------------------------------------------------------------


def test_the_pilot_sample_is_the_source_of_party_and_chamber(tmp_path: Path) -> None:
    _pilot_yaml(tmp_path, [
        {"id": "B001", "name": "B", "state": "KY", "party": "R", "chamber": "house"},
        {"id": "A001", "name": "A", "state": "CA", "party": "D", "chamber": "senate"},
    ])
    members = crec.pilot_members(tmp_path / "data")
    assert [m["id"] for m in members] == ["A001", "B001"]
    assert members[0]["party"] == "D" and members[0]["chamber"] == "senate"


def test_no_committed_sample_is_a_refusal_not_an_empty_run(tmp_path: Path) -> None:
    with pytest.raises(crec.CrecError, match="pilot-draw"):
        crec.pilot_members(tmp_path / "data")


# --- indexing ------------------------------------------------------------------------


def test_one_unreadable_issue_costs_that_issue_only() -> None:
    good = _issue(
        _granule("CREC-2026-09-16-pt1-PgH1", members=(("M001184", "SPEAKING", "Mr. MASSIE"),))
    )

    def read(pkg: str) -> str:
        if pkg == "bad":
            return "<mods"
        return good

    seen: list[tuple[int, int, int]] = []
    rows, failures = crec.build_index(
        ["bad", "CREC-2026-09-16"], {"M001184"},
        read_mods=read, on_progress=lambda *a: seen.append(a),
    )
    assert len(rows) == 1
    assert failures == ["bad: CrecError"]
    assert seen == [(1, 2, 0), (2, 2, 1)]


def test_indexing_without_a_progress_callback_is_fine() -> None:
    rows, failures = crec.build_index(
        ["CREC-2026-09-16"], {"M001184"},
        read_mods=lambda _pkg: _issue(
            _granule("CREC-2026-09-16-pt1-PgH1",
                     members=(("M001184", "SPEAKING", "Mr. MASSIE"),))
        ),
    )
    assert len(rows) == 1 and failures == []


def test_rows_are_grouped_newest_first() -> None:
    rows = [
        crec.Speaking("M1", "2023-05-01", "G1", "P", "HOUSE", "", "", "", "", ""),
        crec.Speaking("M1", "2026-01-01", "G2", "P", "HOUSE", "", "", "", "", ""),
        crec.Speaking("M2", "2024-01-01", "G3", "P", "HOUSE", "", "", "", "", ""),
    ]
    grouped = crec.by_member(rows)
    assert [r.date for r in grouped["M1"]] == ["2026-01-01", "2023-05-01"]
    assert list(grouped) == ["M1", "M2"]


# --- the report ----------------------------------------------------------------------


def test_the_report_counts_per_member_per_party_and_names_the_silent_members() -> None:
    members = [
        {"id": "M1", "name": "One", "state": "KY", "party": "R", "chamber": "house"},
        {"id": "M2", "name": "Two", "state": "CA", "party": "D", "chamber": "senate"},
    ]
    grouped = crec.by_member([
        crec.Speaking("M1", "2026-01-01", "G1", "P", "HOUSE", "", "", "", "", ""),
        crec.Speaking("M1", "2026-01-02", "G2", "P", "EXTENSIONS", "", "", "", "", ""),
    ])
    report = crec.render_report(
        members, grouped, window=("2023-01-03", "2026-10-13"), issues=790,
        failures=["CREC-2024-01-01: HTTPError"], keep_limit=60, text_fetched={"M1": 2},
    )
    assert "| One (M1) | R | house | 1 | 0 | 1 | 2 | 2 |" in report
    assert "| R | 1 | 1 | 0 | 1 | 2 | 2.0 |" in report
    assert "| D | 1 | 0 | 0 | 0 | 0 | 0.0 |" in report
    assert "no** speaking granule in the window: M2" in report
    assert "Issues that could not be read: 1 — CREC-2024-01-01: HTTPError" in report


def test_an_uncapped_run_says_every_granule_was_pulled() -> None:
    """Collection is not capped (owner, 2026-10-13): decision 7 caps categorization, and
    the report must not imply a collection ceiling that does not exist."""
    uncapped = crec.render_report(
        [], {}, window=("2023-01-03", "2026-10-13"), issues=790, failures=[],
        keep_limit=0, text_fetched={},
    )
    assert "pulled for **every** granule" in uncapped
    capped = crec.render_report(
        [], {}, window=("2023-01-03", "2026-10-13"), issues=790, failures=[],
        keep_limit=3, text_fetched={},
    )
    assert "newest **3** per member" in capped
    assert "smoke-run knob" in capped


def test_a_zero_in_the_text_column_always_says_why() -> None:
    """The counts are final the moment indexing ends; the text pull takes hours. A reader
    must never have to guess whether 0 means "nothing there" or "not read yet"."""
    args = dict(window=("2023-01-03", "2026-10-13"), issues=790, failures=[],
                text_fetched={})
    index_only = crec.render_report([], {}, keep_limit=0, text_phase="none", **args)
    pending = crec.render_report([], {}, keep_limit=0, text_phase="pending", **args)
    assert "No granule text was pulled in this run" in index_only
    assert "still running when this was written" in pending


def test_the_report_says_so_when_nothing_failed() -> None:
    report = crec.render_report(
        [], {}, window=("2023-01-03", "2026-10-13"), issues=0, failures=[],
        keep_limit=0, text_fetched={},
    )
    assert "window: none" in report
    assert "could not be read: 0" in report


def test_the_window_ends_today() -> None:
    from datetime import UTC, datetime

    assert crec.window_end(datetime(2026, 10, 13, 5, 0, tzinfo=UTC)) == "2026-10-13"
    assert len(crec.window_end()) == 10


# --- the run -------------------------------------------------------------------------


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo root holding a two-member pilot sample, with every fetch faked."""
    _pilot_yaml(tmp_path, [
        {"id": "M001184", "name": "Thomas Massie", "state": "KY",
         "party": "R", "chamber": "house"},
        {"id": "K000388", "name": "Trent Kelly", "state": "MS",
         "party": "R", "chamber": "house"},
    ])
    (tmp_path / "docs" / "research").mkdir(parents=True)
    monkeypatch.setattr(crec, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        crec.govinfo, "published_packages",
        lambda start, end: [{"packageId": "CREC-2026-09-15"},
                            {"packageId": "CREC-2026-09-16"}],
    )
    monkeypatch.setattr(
        crec.govinfo, "package_mods",
        lambda pkg: _issue(
            _granule(
                f"{pkg}-pt1-PgH1",
                date=pkg.removeprefix("CREC-"),
                members=(("M001184", "SPEAKING", "Mr. MASSIE"),
                         ("K000388", "VOTED NO", "Mr. KELLY of Mississippi")),
            )
        ),
    )
    monkeypatch.setattr(crec.govinfo, "granule_text", lambda pkg, granule: SPEECH_TEXT)
    return tmp_path


def _index(repo: Path) -> dict:
    return json.loads((repo / "data" / "raw" / "crec" / "index.json").read_text(encoding="utf-8"))


def test_the_run_writes_an_index_a_report_and_the_candidate_statements(repo: Path) -> None:
    assert crec.run([]) == 0

    index = _index(repo)
    assert index["issues_read"] == 2
    assert [g["member_id"] for g in index["granules"]] == ["M001184", "M001184"]

    statements = json.loads(
        (repo / "data" / "raw" / "crec" / "statements" / "M001184.json").read_text(
            encoding="utf-8"
        )
    )
    assert statements["member"]["name"] == "Thomas Massie"
    assert [s["attribution"] for s in statements["statements"]] == ["turn", "turn"]

    # The member MODS records as voting, not speaking, gets an empty file rather than
    # being left out: "we looked and he said nothing" is a result.
    voted = json.loads(
        (repo / "data" / "raw" / "crec" / "statements" / "K000388.json").read_text(
            encoding="utf-8"
        )
    )
    assert voted["statements"] == []

    report = (repo / "docs" / "research" / "2026-10-13-crec-collection-counts.md")
    assert report.exists() or list((repo / "docs" / "research").glob("*-crec-*.md"))


def test_index_only_fetches_no_granule_text(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(pkg: str, granule: str) -> str:  # pragma: no cover - must not be called
        raise AssertionError("--index-only must not fetch granule text")

    monkeypatch.setattr(crec.govinfo, "granule_text", refuse)
    assert crec.run(["--index-only"]) == 0
    assert not (repo / "data" / "raw" / "crec" / "statements").exists()


def test_the_issue_limit_and_the_member_subset_narrow_the_run(repo: Path) -> None:
    assert crec.run(["--limit-issues", "1", "--members", "M001184", "--keep-limit", "1"]) == 0
    index = _index(repo)
    assert index["issues_read"] == 1
    assert not (repo / "data" / "raw" / "crec" / "statements" / "K000388.json").exists()


def test_a_member_outside_the_drawn_40_is_refused(repo: Path) -> None:
    with pytest.raises(crec.CrecError, match="not in the drawn 40: Z999999"):
        crec.run(["--members", "Z999999"])


def test_an_explicit_window_end_is_honored(repo: Path) -> None:
    assert crec.run(["--index-only", "--until", "2026-09-16"]) == 0
    assert _index(repo)["window"]["end"] == "2026-09-16"


def test_a_failed_text_fetch_costs_one_granule_not_the_run(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx

    def boom(pkg: str, granule: str) -> str:
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(crec.govinfo, "granule_text", boom)
    assert crec.run([]) == 0
    statements = json.loads(
        (repo / "data" / "raw" / "crec" / "statements" / "M001184.json").read_text(
            encoding="utf-8"
        )
    )
    assert statements["statements"] == []
    report = next((repo / "docs" / "research").glob("*-crec-*.md")).read_text(encoding="utf-8")
    assert "could not be read: 2" in report


def test_the_progress_line_reports_every_twenty_fifth_issue(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        crec.govinfo, "published_packages",
        lambda start, end: [{"packageId": f"CREC-2026-09-{i:02d}"} for i in range(1, 27)],
    )
    assert crec.run(["--index-only"]) == 0
    out = capsys.readouterr().out
    assert "indexed 25/26 issues" in out
    assert "indexed 26/26 issues" in out


# --- the source client ---------------------------------------------------------------


def test_published_packages_follows_every_page_and_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pager must stop: a repeated id or a missing nextPage both end the walk."""
    from ingest.sources import govinfo

    pages = {
        "https://api.govinfo.gov/published/2023-01-03/2026-10-13": {
            "count": 2,
            "packages": [{"packageId": "CREC-2026-09-16"}],
            "nextPage": "https://api.govinfo.gov/published/next",
        },
        "https://api.govinfo.gov/published/next": {
            "count": 2,
            "packages": [{"packageId": "CREC-2026-09-15"}, {"packageId": None}],
            "nextPage": None,
        },
    }

    class _Resp:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    monkeypatch.setattr(govinfo, "_headers", lambda: {})
    monkeypatch.setattr(
        govinfo, "fetch",
        lambda source, url, **kw: _Resp(pages[url]),
    )
    got = govinfo.published_packages("2023-01-03", "2026-10-13")
    assert [p["packageId"] for p in got] == ["CREC-2026-09-16", "CREC-2026-09-15"]
