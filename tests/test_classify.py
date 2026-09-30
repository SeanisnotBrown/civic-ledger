"""INC-5 tests — the §A1 vote_class classifier. Pure/offline: the golden fixture
(tests/fixtures/questions.yaml, real 118/119 strings) drives classify(), plus
ordering/precedence and totality checks. The pipeline's Rules-Committee fetch is
exercised via a monkeypatched _is_rules_reported (no network).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ingest import classify

FIXTURE = Path(__file__).parent / "fixtures" / "questions.yaml"
CASES = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_has_enough_real_strings():
    assert len(CASES) >= 40  # acceptance: ≥ 40 real question strings


def test_golden_questions_classify_exactly():
    failures = []
    for case in CASES:
        cls, rule = classify.classify(
            case["q"], is_rules_resolution=case.get("rules_resolution", False)
        )
        if (cls, rule) != (case["cls"], case["rule"]):
            failures.append(
                f"{case['q']!r}: got ({cls},{rule}) want ({case['cls']},{case['rule']})"
            )
    assert not failures, "\n".join(failures)


def test_every_fixture_rule_id_exists_in_table():
    table_ids = {r[0] for r in classify.RULES} | {"R-RULE", "R-DEFAULT"}
    used = {c["rule"] for c in CASES}
    assert used <= table_ids, f"fixture references unknown rule(s): {used - table_ids}"


def test_classify_is_total():
    # Any string returns a valid (class, rule); never raises.
    cls, rule = classify.classify("")
    assert cls == "other" and rule == "R-DEFAULT"


def test_cloture_beats_motion_to_proceed_for_audit():
    # Both are procedural, but the rule id must reflect cloture (precedence/order).
    cls, rule = classify.classify("On Cloture on the Motion to Proceed H.R. 23")
    assert (cls, rule) == ("procedural", "R-PROC-1")


def test_treaty_not_swallowed_by_resolution_rule():
    cls, rule = classify.classify("On the Resolution of Ratification Treaty Doc. 112-8")
    assert (cls, rule) == ("other", "R-TREATY")


def test_rules_resolution_flag_only_affects_resolution_rule():
    # The flag must not perturb a non-resolution question.
    assert classify.classify("On Passage", is_rules_resolution=True) == ("passage", "R-PASS-1")
    # And it flips exactly the resolution rule.
    assert classify.classify("On Agreeing to the Resolution") == ("passage", "R-RES")
    assert classify.classify("On Agreeing to the Resolution", is_rules_resolution=True) == (
        "procedural", "R-RULE",
    )


def test_senate_trailing_measure_text_does_not_break_prefix():
    assert classify.classify("On the Nomination PN1")[0] == "nomination"
    assert classify.classify("On Passage of the Bill H.R. 1")[0] == "passage"
    assert classify.classify("On the Cloture Motion PN373")[0] == "procedural"


def test_is_rules_reported_reads_hsru00_activity(monkeypatch):
    # A House Rules-reported resolution → True; a bill reported by another committee
    # → False; a non-hres → False without any fetch.
    class _Resp:
        def __init__(self, payload):
            self._p = payload

        def json(self):
            return self._p

    reported = {"committees": [{"systemCode": "hsru00", "name": "Rules Committee",
                                "activities": [{"name": "Reported Original Measure"}]}]}
    other = {"committees": [{"systemCode": "hsju00", "name": "Judiciary",
                             "activities": [{"name": "Referred to"}]}]}

    def fake(congress, bill_type, number, *, ttl_hours=None):
        return _Resp(reported if number == 1009 else other)

    import ingest.sources.congress_gov as cg
    monkeypatch.setattr(cg, "bill_committees", fake)

    assert classify._is_rules_reported("hres1009-119") is True
    assert classify._is_rules_reported("hres5-119") is False
    assert classify._is_rules_reported("hconres14-119") is False  # non-hres, no fetch
