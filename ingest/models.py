"""Canonical data schemas (§5). Pydantic v2. The JSON export mirrors these
field names exactly, so a rename here is a rename of the published dataset.

Discipline (§5): all IDs are strings; all dates ISO-8601; every *published*
Tier-1 record carries a `source_url`. Tier-1 records set `extra="forbid"` so a
stray upstream field surfaces as a validation error (→ quarantine, §6.1) instead
of silently riding along.

Only Member is exported in INC-2; the rest of the layer is defined now so
`models.py` is complete and INC-3+ import their schemas from one place.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

Party = Literal["D", "R", "I"]
Chamber = Literal["house", "senate"]
Position = Literal["yea", "nay", "present", "not_voting"]
VoteClass = Literal[
    "passage", "amendment", "procedural", "nomination", "veto_override", "other"
]


class _Strict(BaseModel):
    """Base for Tier-1 records: reject unknown fields so schema drift fails loudly."""

    model_config = ConfigDict(extra="forbid")


# --- Members --------------------------------------------------------------


class Term(_Strict):
    """One stint in office. Full history is kept and party switches preserved,
    so `party` is per-term (§5), not just the member's current affiliation."""

    start: str
    end: str
    party: Party
    chamber: Chamber


class Member(_Strict):
    id: str  # bioguide id — the canonical key everywhere
    ids: dict[str, str]  # crosswalk (govtrack, lis, fec, opensecrets, …) — D20
    name: str
    party: Party  # current affiliation = party of the most recent term
    state: str
    district: int | None  # None = Senate
    chamber: Chamber
    serving: bool
    terms: list[Term]  # sorted by start; party switches preserved


# --- Bills & votes --------------------------------------------------------


class CboRef(_Strict):
    """Link-through only (§5): a CBO cost estimate lives at cbo.gov."""

    url: str
    title: str
    date: str


class Bill(_Strict):
    id: str  # "hr2-119" — type+number+congress, lowercase
    congress: int
    type: str
    number: int
    title_official: str
    policy_area: str | None  # government-assigned ONLY; never invented (D5)
    # subjects & cosponsor_ids are paginated Congress.gov sub-resources, fetched
    # by the increment that consumes them (INC-10 metrics). None = NOT YET
    # COLLECTED — deliberately distinct from [] (= collected, none exist), so an
    # empty list is never a false "zero" claim (D27; mirrors specificity_level).
    subjects: list[str] | None = None  # government-assigned legislative subject terms
    sponsor_id: str | None
    cosponsor_ids: list[str] | None = None
    latest_action: str
    latest_action_date: str
    cbo_estimates: list[CboRef]
    source_url: str


class RollCall(_Strict):
    id: str  # "h-119-1-0234" — chamber-congress-session-roll
    chamber: Chamber
    congress: int
    session: int
    number: int
    date: str
    question: str  # official question text, verbatim
    vote_class: VoteClass  # REQUIRED — classifier §A1; never null
    vote_class_rule: str  # id of the rule that fired (auditability)
    bill_id: str | None
    result: str
    totals: dict[str, int]  # yea/nay/present/not_voting
    source_url: str


class MemberVote(_Strict):
    member_id: str
    rollcall_id: str
    position: Position


class Absence(_Strict):
    member_id: str
    rollcall_id: str
    # ONLY an owner-approved, verbatim CREC quote — never inferred.
    stated_reason: str | None = None
    stated_reason_source: str | None = None  # CREC page URL, required if reason present
    declared_position: Literal["yea", "nay"] | None = None

    @model_validator(mode="after")
    def _source_required_with_reason(self) -> Absence:
        # §5 invariant: a stated reason without its CREC page is not publishable.
        if self.stated_reason is not None and not self.stated_reason_source:
            raise ValueError("stated_reason requires stated_reason_source (CREC page URL)")
        return self


# --- Member legislation (INC-10 metrics input) ----------------------------


class LegItem(_Strict):
    """One bill a member sponsored or cosponsored, scoped to the covered
    Congresses. `became_law` is a deterministic match on the official latest-action
    text ("Became Public Law") — it counts only bills enacted UNDER THEIR OWN
    NUMBER; a provision enacted by folding into another vehicle is not counted
    (stated on the methodology page).

    Deliberately carries NO live latest-action field: a bill's latest action moves
    as it works through committee, so storing it would make data/legislation/ diff
    almost every night and defeat the quiet-night diff-gate (D33). The only action
    text kept is `enacted_action`, present ONLY when `became_law` — an enacted
    bill's latest action is frozen, so it never churns. Legislation files then diff
    only on real events: new sponsorship, new cosponsorship, or an enactment. (Title
    text can still change on amendment — a low-frequency, acceptable churn source.)
    `source_url` traces each item to its Congress.gov bill page."""

    bill_id: str  # normalized "s3266-119"
    congress: int
    title: str
    introduced_date: str | None
    became_law: bool
    # the frozen "Became Public Law No…" text; None unless enacted (see class docstring)
    enacted_action: str | None = None
    source_url: str


class MemberLegislation(_Strict):
    """A member's sponsored + cosponsored bills over the covered Congresses
    (data/legislation/{member}.json). The metrics layer reads ONLY this committed
    artifact — never the live API — so a third party can recompute every legislation
    metric from the public repo (verify-recompute contract)."""

    member_id: str
    sponsored: list[LegItem]
    cosponsored: list[LegItem]
    source_url: str  # the sponsored-legislation endpoint (human-checkable)


# --- Metrics (INC-10; data/metrics.json) ----------------------------------
# Each per-member value has its own strict model so `test_committed_schemas_up_to_date`
# catches a metric-shape change before it ships. Every metric is Tier-2 (an
# independent factual formula); NONE is combined into a per-member composite — the
# Tier-3 guard (checks/integrity.py) enforces that structurally over metrics.py.


class AttendanceValue(_Strict):
    eligible: int  # position rolls the member was covered for (non_position excluded)
    cast: int      # yea + nay + present
    missed: int    # not_voting
    pct: float     # 100 * cast / eligible


class PartyUnityValue(_Strict):
    # substantive rolls where the member cast yea/nay and their party had a majority
    substantive: int
    agreed: int          # of those, votes matching the member's party majority
    pct: float | None    # 100 * agreed / substantive; None if substantive == 0
    excluded_ties: int   # substantive rolls dropped: the member's party split evenly


class CountValue(_Strict):
    count: int


class EnactedRateValue(_Strict):
    sponsored: int
    enacted: int         # sponsored bills matched "Became Public Law"
    pct: float | None    # 100 * enacted / sponsored; None if sponsored == 0


class GapItem(_Strict):
    bill_id: str
    kind: Literal["cosponsored_and_voted_nay", "cosponsored_no_floor_action"]
    rollcall_id: str | None = None  # the nay roll, for the voted-nay kind (traceability)


class MismatchItem(_Strict):
    # Provisional shape (INC-11 curates statements; empty until then).
    statement_id: str
    bill_id: str
    statement_source_url: str
    recorded_position: Position


class AbsenceContextItem(_Strict):
    rollcall_id: str
    date: str
    same_day_total: int  # position rolls in the member's chamber that calendar day
    same_day_cast: int   # of those, ones the member cast (yea/nay/present)


class MemberMetrics(_Strict):
    attendance: AttendanceValue
    party_unity: PartyUnityValue
    sponsored: CountValue
    cosponsored: CountValue
    enacted_rate: EnactedRateValue
    cosponsor_vote_gap: list[GapItem]
    named_measure_mismatch: list[MismatchItem]
    absence_context: list[AbsenceContextItem]


class MetricMethodology(_Strict):
    label: str
    text: str  # the metric function's docstring, verbatim — the methodology-page copy


class MetricsFile(_Strict):
    """data/metrics.json. `methodology` keys == `members[*]` metric keys == the
    methodology-page section ids (asserted by test). No wall-clock (determinism)."""

    methodology: dict[str, MetricMethodology]
    members: dict[str, MemberMetrics]


# --- Statements & candidates ----------------------------------------------


class Statement(_Strict):
    id: str
    member_id: str
    text: str  # verbatim; there is deliberately no paraphrase field
    date: str
    venue: str
    source_url: str
    archive_url: str  # REQUIRED — curation refuses to save without a verified capture
    archive_captured_at: str
    named_measures: list[str]  # bill ids; ONLY basis for pairing (D9)
    specificity_level: Literal[0, 1, 2, 3] | None = None  # owner-assigned; None = unscored
    curator_note: str | None = None  # internal, never rendered


class PageCapture(_Strict):
    url: str
    captured_at: str
    archive_url: str
    text_sha256: str


class Candidate(_Strict):
    id: str
    name: str
    party: str  # free-form: minor-party / independent candidates aren't D/R/I
    office: str
    election_year: int
    incumbent_member_id: str | None
    filing_source_url: str  # SoS qualifying filing
    issues_claimed: list[str]
    statements: list[Statement]
    page_captures: list[PageCapture]  # recurring recapture appends here (INC-13)


# --- Quiz -----------------------------------------------------------------


class Provenance(_Strict):
    # instrument e.g. "ANES 2024 V241234" | "Pew ..." | "original".
    instrument: str
    source_url: str | None = None
    is_original: bool  # MUST surface in the UI when true (brief §10)


class QuizOption(_Strict):
    id: str
    text: str
    # None accommodates the "I don't know" option injected at render time.
    provenance: Provenance | None = None


class QuizQuestion(_Strict):
    id: str
    bank_version: str
    dimension: str  # maps to policy_area terms via data/quiz/dimension_map.yaml
    ladder: Literal["position", "reason", "tradeoff", "calibration"]
    text: str
    options: list[QuizOption]
    provenance: Provenance
