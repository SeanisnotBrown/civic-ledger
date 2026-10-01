"""V2-11 task 4 — the bill-activity ingest.

Offline: the source module is monkeypatched and every path writes into tmp_path.

The two things most worth protecting here are both cost/correctness rules the
owner ratified in SD-33, not style preferences:

  1. A bill we ALREADY HOLD costs ONE request (its /actions) and is merged into
     the committed record. Refetching detail+subjects+cosponsors for every
     updated bill would be ~19-29 min/night (~560-870/month) and would not fit
     beside the D86 nightly inside the 2,000-minute free allowance.
  2. A full-Congress backfill must never run in CI: >= ~43 h, ~2,590 Actions
     minutes, more than a whole month's allowance (D88, H24).

Plus the anti-clobber rule carried from D35: a cheaper refresh path must never
write an enriched field back as the None "not collected" sentinel.
"""

from __future__ import annotations

import json

import pytest

from ingest import bills
from ingest.models import Bill, BillAction


# --- fixtures ----------------------------------------------------------------
def _bill(bill_id="hr1-119", **over):
    base = dict(
        id=bill_id, congress=119, type="hr", number=1, title_official="A Bill",
        policy_area="Health", subjects=["Health care costs"], sponsor_id="A000001",
        cosponsor_ids=["B000002", "C000003"], actions=None,
        latest_action="Referred to Committee.", latest_action_date="2025-01-03",
        cbo_estimates=[], source_url="https://www.congress.gov/bill/119/hr/1",
    )
    base.update(over)
    return Bill(**base)


def _action(text="Introduced in House", date="2025-01-03"):
    return BillAction(
        date=date, text=text, type="IntroReferral", source_system="Library of Congress"
    )


def _item(num=1, congress=119, btype="HR", latest_text=None, latest_date=None):
    it = {"congress": congress, "type": btype, "number": str(num),
          "title": f"Bill {num}", "updateDate": "2026-10-01"}
    if latest_text is not None:
        it["latestAction"] = {"text": latest_text, "actionDate": latest_date}
    return it


# --- bill_id_from_list_item --------------------------------------------------
def test_list_item_id_matches_the_canonical_shape():
    # Must round-trip through parse_bill_id or the ingest invents unusable ids.
    assert bills.bill_id_from_list_item(_item(1379, 119, "HR")) == "hr1379-119"
    assert bills.parse_bill_id("hr1379-119") == ("hr", 1379, 119)


def test_list_item_id_lowercases_type_and_strips_number():
    assert bills.bill_id_from_list_item(_item(42, 118, "SJRES")) == "sjres42-118"


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"type": "HR", "number": "1"},            # no congress
        {"type": "HR", "congress": 119},          # no number
        {"type": "", "number": "1", "congress": 119},
        {"type": "HR", "number": "not-a-number", "congress": 119},
    ],
)
def test_list_item_id_is_none_on_malformed_input(bad):
    assert bills.bill_id_from_list_item(bad) is None


# --- known_rollcall_ids ------------------------------------------------------
def test_known_rollcall_ids_reads_filenames_not_contents(tmp_path, monkeypatch):
    votes = tmp_path / "data" / "votes" / "118"
    votes.mkdir(parents=True)
    (votes / "h-118-1-0001.json").write_text("{ this is not valid json", encoding="utf-8")
    (votes / "s-118-2-0042.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    # The filename IS the id, so a ~3,500-file scan opens nothing. (It is built
    # once per run; per-bill would repeat it 38,756 times in the backfill.)
    assert bills.known_rollcall_ids() == {"h-118-1-0001", "s-118-2-0042"}


# --- merge_activity: the anti-clobber contract -------------------------------
def test_merge_activity_preserves_every_field_it_does_not_refresh():
    """D35 anti-clobber. The cheap path does NOT fetch subjects or cosponsors,
    so it must carry the committed ones through. Writing them back as None would
    turn an enriched bill into a false 'not collected'."""
    existing = _bill()
    merged = bills.merge_activity(
        existing, actions=[_action()], list_item=_item(latest_text="Passed House.",
                                                       latest_date="2026-09-30")
    )
    assert merged.subjects == ["Health care costs"]
    assert merged.cosponsor_ids == ["B000002", "C000003"]
    assert merged.title_official == "A Bill"
    assert merged.sponsor_id == "A000001"
    assert merged.policy_area == "Health"


def test_merge_activity_sets_actions_and_refreshes_latest_action():
    merged = bills.merge_activity(
        _bill(), actions=[_action("Passed House.")],
        list_item=_item(latest_text="Passed House.", latest_date="2026-09-30"),
    )
    assert [a.text for a in merged.actions] == ["Passed House."]
    assert merged.latest_action == "Passed House."
    assert merged.latest_action_date == "2026-09-30"


@pytest.mark.parametrize(
    "item", [{}, {"latestAction": {}}, {"latestAction": {"text": "", "actionDate": ""}}]
)
def test_merge_activity_keeps_committed_latest_action_when_the_item_lacks_one(item):
    # Blanking a published field because the enumeration omitted it would be a
    # regression dressed as an update.
    existing = _bill()
    merged = bills.merge_activity(existing, actions=[_action()], list_item=item)
    assert merged.latest_action == existing.latest_action
    assert merged.latest_action_date == existing.latest_action_date


def test_merge_activity_can_record_an_empty_timeline():
    # [] = collected, the government lists none. Distinct from None.
    merged = bills.merge_activity(_bill(), actions=[], list_item={})
    assert merged.actions == []
    assert merged.actions is not None


# --- load_existing_bill ------------------------------------------------------
def test_load_existing_bill_round_trips(tmp_path, monkeypatch):
    bdir = tmp_path / "data" / "bills"
    bdir.mkdir(parents=True)
    (bdir / "hr1-119.json").write_text(
        json.dumps(_bill().model_dump()), encoding="utf-8"
    )
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    got = bills.load_existing_bill("hr1-119")
    assert got is not None and got.id == "hr1-119"


def test_load_existing_bill_is_none_when_absent(tmp_path, monkeypatch):
    (tmp_path / "data" / "bills").mkdir(parents=True)
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    assert bills.load_existing_bill("hr999-119") is None


def test_load_existing_bill_is_none_when_corrupt(tmp_path, monkeypatch):
    # A broken committed file must trigger a full re-fetch, never a merge into
    # a half-parsed record.
    bdir = tmp_path / "data" / "bills"
    bdir.mkdir(parents=True)
    (bdir / "hr1-119.json").write_text('{"id": "hr1-119"}', encoding="utf-8")
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    assert bills.load_existing_bill("hr1-119") is None


# --- argument parsing --------------------------------------------------------
def test_activity_args_defaults_to_a_30_hour_window():
    # 30 h, not 24: a late or retried nightly must not open a gap between runs.
    opts = bills._parse_activity_args([])
    assert opts == {
        "congress": None, "since": 30.0, "limit": None,
        "allow_ci": False, "refresh_all": False, "skip_existing": False,
    }


def test_activity_args_parses_each_flag():
    opts = bills._parse_activity_args(["--congress", "118", "--limit", "5", "--allow-ci"])
    assert opts["congress"] == 118 and opts["limit"] == 5 and opts["allow_ci"] is True


@pytest.mark.parametrize(
    "argv",
    [
        ["--typo"],
        ["--congress"],              # missing value
        ["--congress", "abc"],
        ["--congress", "117"],       # outside the covered set
        ["--since", "0"],
        ["--since", "-1"],
        ["117"],                     # bare positional
    ],
)
def test_activity_args_rejects_bad_input(argv):
    """A typo'd flag must never silently become a 43-hour run."""
    with pytest.raises(ValueError):
        bills._parse_activity_args(argv)


# --- the CI refusal ----------------------------------------------------------
@pytest.mark.parametrize("env", ["CI", "GITHUB_ACTIONS"])
def test_backfill_refuses_to_run_in_ci(monkeypatch, capsys, env):
    """SD-33 / H24: >= ~43 h is ~2,590 Actions minutes, more than a whole
    month's free allowance. The refusal is the guard, not a comment."""
    monkeypatch.setenv(env, "true")
    assert bills.run_activity(["--congress", "119"]) == 2
    out = capsys.readouterr().out
    assert "must not run in CI" in out


def test_allow_ci_overrides_the_refusal(monkeypatch):
    """The one legitimate case: a self-hosted runner, where minutes are not
    billed (the escape hatch H24 documents). It must get past the guard."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr(
        "ingest.sources.congress_gov.bills_updated_since", lambda *a, **k: []
    )
    monkeypatch.setattr(bills, "known_rollcall_ids", lambda: set())
    assert bills.run_activity(["--congress", "119", "--allow-ci"]) == 0


def test_the_delta_path_is_not_blocked_in_ci(monkeypatch):
    # Only the full backfill is refused; the nightly delta is the whole point.
    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr(
        "ingest.sources.congress_gov.bills_updated_since", lambda *a, **k: []
    )
    monkeypatch.setattr(bills, "known_rollcall_ids", lambda: set())
    assert bills.run_activity(["--since", "24"]) == 0


# --- run_activity: the one-request rule --------------------------------------
def _wire(monkeypatch, tmp_path, items, *, actions=None):
    """Point the ingest at tmp_path and stub every network call."""
    (tmp_path / "data" / "bills").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "votes").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "ingest.sources.congress_gov.bills_updated_since", lambda *a, **k: items
    )
    calls: list[str] = []

    def fake_actions(c, t, n, **kw):
        calls.append(f"actions:{t}{n}-{c}")
        return actions if actions is not None else []

    def fake_detail(c, t, n, **kw):
        calls.append(f"detail:{t}{n}-{c}")

        class R:
            @staticmethod
            def json():
                return {"bill": {
                    "title": "A Bill", "policyArea": {"name": "Health"},
                    "sponsors": [{"bioguideId": "A000001"}], "cboCostEstimates": [],
                    "latestAction": {"text": "Referred.", "actionDate": "2025-01-03"},
                }}

        return R()

    def fake_subjects(c, t, n, **kw):
        calls.append(f"subjects:{t}{n}-{c}")
        return ["Health care costs"]

    def fake_cos(c, t, n, **kw):
        calls.append(f"cosponsors:{t}{n}-{c}")
        return ["B000002"]

    monkeypatch.setattr("ingest.sources.congress_gov.bill_actions", fake_actions)
    monkeypatch.setattr("ingest.sources.congress_gov.bill_detail", fake_detail)
    monkeypatch.setattr("ingest.sources.congress_gov.bill_subjects", fake_subjects)
    monkeypatch.setattr("ingest.sources.congress_gov.bill_cosponsor_ids", fake_cos)
    return calls


def test_a_new_bill_costs_four_requests(monkeypatch, tmp_path):
    calls = _wire(monkeypatch, tmp_path, [_item(1)])
    assert bills.run_activity(["--since", "24"]) == 0
    assert sorted(calls) == [
        "actions:hr1-119", "cosponsors:hr1-119", "detail:hr1-119", "subjects:hr1-119",
    ]
    assert (tmp_path / "data" / "bills" / "hr1-119.json").exists()


def test_a_bill_we_already_hold_costs_ONE_request(monkeypatch, tmp_path):
    """SD-33 constraint 2, the difference between ~7 min/night and ~29. If this
    test goes red the nightly no longer fits the free Actions allowance."""
    bdir = tmp_path / "data" / "bills"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "hr1-119.json").write_text(
        json.dumps(_bill().model_dump()), encoding="utf-8"
    )
    calls = _wire(monkeypatch, tmp_path, [_item(1, latest_text="Passed House.",
                                                latest_date="2026-09-30")])
    assert bills.run_activity(["--since", "24"]) == 0
    assert calls == ["actions:hr1-119"], f"expected one request, got {calls}"


def test_refresh_does_not_clobber_the_committed_file(monkeypatch, tmp_path):
    bdir = tmp_path / "data" / "bills"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "hr1-119.json").write_text(
        json.dumps(_bill().model_dump()), encoding="utf-8"
    )
    _wire(monkeypatch, tmp_path, [_item(1)], actions=[{
        "actionDate": "2026-09-30", "text": "Passed House.", "type": "Floor",
        "sourceSystem": {"name": "House floor actions"},
    }])
    assert bills.run_activity(["--since", "24"]) == 0
    after = json.loads((bdir / "hr1-119.json").read_text(encoding="utf-8"))
    assert after["cosponsor_ids"] == ["B000002", "C000003"]  # the committed pair
    assert after["subjects"] == ["Health care costs"]
    assert len(after["actions"]) == 1


def test_malformed_list_item_is_quarantined_not_fatal(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path, [{"congress": 119}, _item(1)])
    # One bad item of two is 50% — over the §6.1 ceiling, so the run fails, but
    # it fails AFTER processing the good one rather than crashing on the bad.
    assert bills.run_activity(["--since", "24"]) == 1
    assert (tmp_path / "data" / "bills" / "hr1-119.json").exists()


def test_limit_truncates_the_work(monkeypatch, tmp_path):
    calls = _wire(monkeypatch, tmp_path, [_item(i) for i in range(1, 11)])
    assert bills.run_activity(["--since", "24", "--limit", "2"]) == 0
    assert len({c.split(":")[1] for c in calls}) == 2


def test_delta_ignores_bills_outside_the_covered_congresses(monkeypatch, tmp_path):
    # The unscoped /bill window spans every Congress on file (430,715 bills);
    # only 118/119 are ours.
    calls = _wire(monkeypatch, tmp_path, [_item(1, congress=117), _item(2, congress=119)])
    assert bills.run_activity(["--since", "24"]) == 0
    assert all("-117" not in c for c in calls)
    assert any("-119" in c for c in calls)


# --- V2-11 task 4b: --skip-existing, the resume flag ------------------------
# The backfill is >= ~43 h and the owner's laptop goes home at the end of the
# day, so it WILL be interrupted a dozen times. Without this flag each resume
# refetches /actions for everything already finished (~19k requests, ~5 h),
# because the raw-cache TTL is 20 h. With it, a resume costs zero requests for
# finished work. These tests are the guarantee that stays true.


def test_a_backfill_resumes_by_DEFAULT():
    """The flag has to be remembered on every one of a dozen resumes, and
    forgetting it once costs ~5 h of refetching. So resuming is the default and
    re-doing finished work is what you have to ask for (D91)."""
    assert bills._parse_activity_args(["--congress", "119"])["skip_existing"] is True
    assert bills._parse_activity_args(
        ["--congress", "119", "--refresh-all"]
    )["skip_existing"] is False


def test_the_delta_path_never_skips_held_bills():
    """On `--since` skipping would silently stop refreshing the timelines the
    nightly delta exists to refresh."""
    assert bills._parse_activity_args(["--since", "30"])["skip_existing"] is False
    assert bills._parse_activity_args([])["skip_existing"] is False
    with pytest.raises(ValueError, match="needs --congress"):
        bills._parse_activity_args(["--since", "30", "--refresh-all"])


def test_skip_existing_survives_as_a_no_op_alias():
    """It is what the first draft of the docs told the owner to type."""
    assert bills._parse_activity_args(
        ["--congress", "119", "--skip-existing"]
    )["skip_existing"] is True
    with_alias = bills._parse_activity_args(["--since", "30", "--skip-existing"])
    assert with_alias == bills._parse_activity_args(["--since", "30"])


def test_bills_with_actions_honours_the_D27_sentinel(monkeypatch, tmp_path):
    """`[]` is COLLECTED-and-empty (done); `None`/absent is NOT COLLECTED."""
    bdir = tmp_path / "data" / "bills"
    bdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    for bid, actions in (
        ("hr1-119", [_action().model_dump()]),
        ("hr2-119", []),      # collected, this bill genuinely has none -> DONE
        ("hr3-119", None),    # not collected yet -> NOT done
    ):
        (bdir / f"{bid}.json").write_text(
            json.dumps(_bill(bill_id=bid, actions=actions).model_dump()),
            encoding="utf-8",
        )
    assert bills.bills_with_actions() == {"hr1-119", "hr2-119"}


def test_a_torn_file_is_re_ingested_not_skipped(monkeypatch, tmp_path):
    """`export_bill` uses a plain `write_text`, so killing the run mid-write can
    truncate one file. It must never read as 'done'."""
    bdir = tmp_path / "data" / "bills"
    bdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("ingest.cache.repo_root", lambda: tmp_path)
    good = json.dumps(_bill(actions=[_action().model_dump()]).model_dump())
    (bdir / "hr1-119.json").write_text(good, encoding="utf-8")
    (bdir / "hr2-119.json").write_text(good[: len(good) // 2], encoding="utf-8")
    assert bills.bills_with_actions() == {"hr1-119"}


def test_resuming_a_finished_bill_costs_ZERO_requests(monkeypatch, tmp_path):
    """The whole point of the flag. One held-with-actions bill, one not held."""
    bdir = tmp_path / "data" / "bills"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "hr1-119.json").write_text(
        json.dumps(_bill(actions=[_action().model_dump()]).model_dump()),
        encoding="utf-8",
    )
    calls = _wire(monkeypatch, tmp_path, [_item(1), _item(2)])
    assert bills.run_activity(["--congress", "119", "--skip-existing"]) == 0
    assert not [c for c in calls if c.endswith("hr1-119")], \
        f"hr1 was already done and must cost nothing, got {calls}"
    assert "actions:hr2-119" in calls  # the unfinished one still gets ingested


def test_refresh_all_re_does_a_held_bill(monkeypatch, tmp_path):
    """The opt-out still works: `--refresh-all` ignores the done-set."""
    bdir = tmp_path / "data" / "bills"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "hr1-119.json").write_text(
        json.dumps(_bill(actions=[_action().model_dump()]).model_dump()),
        encoding="utf-8",
    )
    calls = _wire(monkeypatch, tmp_path, [_item(1)])
    assert bills.run_activity(["--congress", "119", "--refresh-all"]) == 0
    assert calls == ["actions:hr1-119"]


def test_skip_existing_is_idempotent_over_repeated_resumes(monkeypatch, tmp_path):
    """Run, interrupt, run again, run again: the second and third runs do no
    network work at all. This is what makes a 14-day chunked backfill free."""
    calls = _wire(monkeypatch, tmp_path, [_item(1), _item(2)])
    assert bills.run_activity(["--congress", "119", "--skip-existing"]) == 0
    first = len(calls)
    assert first > 0
    for _ in range(2):
        calls.clear()
        assert bills.run_activity(["--congress", "119", "--skip-existing"]) == 0
        assert calls == [], f"a resume must cost nothing, got {calls}"
