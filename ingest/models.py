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

from datetime import date as _date
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

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
    id: str  # bioguide id (federal) or `ms-<people_id>` (MS state) — canonical key
    ids: dict[str, str]  # crosswalk (govtrack, lis, fec, opensecrets, legiscan, …) — D20
    name: str
    party: Party  # current affiliation = party of the most recent term
    state: str
    district: int | None  # None = US Senate; the HD/SD ordinal for MS state members
    chamber: Chamber
    # Jurisdiction the record belongs to: "us" (federal) or "ms" (Mississippi state,
    # INC-12/D51). Defaults to "us" so every pre-INC-12 federal record reads unchanged;
    # state records are written explicitly. State data lives under data/state/ms/ — the
    # field makes jurisdiction explicit once records are mixed in memory (site timelines).
    jurisdiction: str = "us"
    serving: bool
    terms: list[Term]  # sorted by start; party switches preserved


# --- Bills & votes --------------------------------------------------------


class CboRef(_Strict):
    """Link-through only (§5): a CBO cost estimate lives at cbo.gov."""

    url: str
    title: str
    date: str


class Bill(_Strict):
    id: str  # "hr2-119" (federal) or "ms-hb1-2249" (MS: type+number+session), lowercase
    jurisdiction: str = "us"  # "us" | "ms" (INC-12/D51)
    congress: int | None  # US Congress number; None for a state bill (no congress)
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
    id: str  # "h-119-1-0234" (federal) or "ms-h-2249-1612732" (MS: chamber-session-rollid)
    chamber: Chamber
    jurisdiction: str = "us"  # "us" | "ms" (INC-12/D51)
    congress: int | None  # US Congress number; None for a state roll (no congress)
    session: int  # federal: 1|2 of the congress; MS state: the LegiScan session_id
    number: int
    date: str
    question: str  # official question text, verbatim
    vote_class: VoteClass  # REQUIRED — classifier §A1; never null
    vote_class_rule: str  # id of the rule that fired (auditability)
    bill_id: str | None
    result: str
    totals: dict[str, int]  # yea/nay/present/not_voting (chamber-wide)
    # Per-party breakdown of the same tally, keyed by the source's party letter
    # (D/R/I). AGGREGATE only — no individual non-MS position is stored (value #3);
    # it is what makes an honest party-unity metric recomputable from the published
    # data (INC-10, §A). None on non_position rolls (candidate-surname elections have
    # no yea/nay to split by party) — the D27 not-applicable sentinel.
    party_totals: dict[str, dict[str, int]] | None = None
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

    bill_id: str  # normalized "s3266-119" (federal) or "ms-hb1-2249" (MS state)
    congress: int | None  # US Congress; None for a state bill (INC-13 MS metrics)
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
    pct: float | None  # 100 * cast / eligible; None when eligible == 0 (no false zero, D27)


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
    # An adjacency (never a score): a member's specificity-2/3 statement with an
    # owner-assigned stance on a named measure, and their recorded passage vote taking
    # the opposite side. Carries both records + dates so a reader checks the source; no
    # sequence is claimed (D42). Empty until qualifying statements are curated (H8).
    statement_id: str
    bill_id: str
    rollcall_id: str
    statement_source_url: str
    statement_date: str
    vote_date: str
    stated_position: Literal["support", "oppose"]  # owner-assigned stance
    recorded_position: Position  # the member's actual Yea/Nay on that passage roll


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


class MsMemberMetrics(_Strict):
    """The MS state-legislator Tier-2 metrics (INC-13). A deliberate subset of the
    federal `MemberMetrics`: the scalar factual rates that compute cleanly from the
    committed MS record (data/state/ms/). Reuses the federal value models. The
    list-type federal metrics (cosponsor_vote_gap, named_measure_mismatch,
    absence_context) are not computed for MS in this pass."""

    attendance: AttendanceValue
    party_unity: PartyUnityValue
    sponsored: CountValue
    cosponsored: CountValue
    enacted_rate: EnactedRateValue


class MetricMethodology(_Strict):
    label: str
    text: str  # the metric function's docstring, verbatim — the methodology-page copy
    digest: str  # formula identity: newline-normalized sha256(source)[:16] of the
    # metric function (R-3/D45). Bumps on ANY change to that function's body, so a
    # published number always states which formula produced it. It does NOT cover
    # shared `_`-helpers — the manual `schema_version` bump is the contract for those.


class MetricsFile(_Strict):
    """data/metrics.json. `methodology` keys == `members[*]` metric keys == the
    methodology-page section ids (asserted by test). No wall-clock (determinism)."""

    schema_version: int  # formula-generation stamp (R-3/D45), manually bumped on any
    # semantic formula change; the coarse guard paired with per-metric `digest`.
    methodology: dict[str, MetricMethodology]
    members: dict[str, MemberMetrics]


class MsMetricsFile(_Strict):
    """data/state/ms/metrics.json (INC-13). Same shape as MetricsFile but the MS
    subset of metrics per member. Recomputable from the committed MS partition."""

    schema_version: int
    methodology: dict[str, MetricMethodology]
    members: dict[str, MsMemberMetrics]


# --- Rankings (V2-2) ------------------------------------------------------
# Pure per-metric rank/percentile/mean context, computed from data/metrics.json
# alone (recomputable — the verify-recompute contract). No thresholds, no labels,
# no composite: a rank is the ordinal position by value, not a judgment (best/
# worst framing is V2-4). `value` is int for count metrics, float for percentage
# metrics; the union preserves the source type so a count never renders as "45.0".


class RankingEntry(_Strict):
    value: int | float  # the metric's scalar value for this member (count or pct)
    rank: int  # standard competition rank within chamber (1 = highest value; ties
    # share a rank and the next rank skips, e.g. values 100,90,90,80 → ranks 1,2,2,4)
    percentile: float  # % of the chamber's ranked set with a STRICTLY LOWER value


class ChamberRanking(_Strict):
    covered: int  # members ranked in this chamber (non-null value; delegates per D66)
    mean: float | None  # mean value over the ranked set (null when covered == 0)
    median: float | None
    party_means: dict[str, float]  # party code (from the member's current party) ->
    # mean value within the chamber; only parties with >= 1 ranked member appear
    excluded_delegates: list[str]  # bioguides excluded from THIS ranking by D66,
    # sorted (non-voting delegates on the two vote metrics); [] when none excluded
    members: dict[str, RankingEntry]  # bioguide -> entry, ranked members only


class RankingsFile(_Strict):
    """data/rankings/{metric}.json (V2-2). Per-chamber rank/percentile/mean context
    for one Tier-2 metric, recomputed from the committed data/metrics.json. No
    wall-clock (determinism)."""

    metric: str  # the Tier-2 metric key this ranks (== a data/metrics.json key)
    value_field: str  # which scalar field of that metric is ranked ("pct"/"count")
    label: str  # human label (== METRIC_LABELS[metric]) for the methods page
    methodology: str  # the shared ranking-method text, rendered on /methods
    ranks_delegates: bool  # D66: True for the three bill metrics, False for the two
    # vote metrics (delegates cannot vote on final passage — not comparable)
    chambers: dict[str, ChamberRanking]  # "house" / "senate"


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
    named_measures: list[str]  # measures the statement names (bill ids or allowlisted titles)
    # The D9 pairing result: named_measures RESOLVED to canonical bill ids (bill-id
    # form passes through; an allowlisted short title maps to its bill id; anything
    # else is unpaired and omitted). Resolved ONCE, in Python (ingest/pairing.py), and
    # published here so both the metric layer and the site read it — neither re-resolves
    # (D41). Sorted, de-duplicated.
    paired_bill_ids: list[str]
    specificity_level: Literal[0, 1, 2, 3] | None = None  # owner-assigned; None = unscored
    # Owner-assigned stance on the named measure: "support" ⇒ expected Yea on passage,
    # "oppose" ⇒ expected Nay. NOT a paraphrase of `text` (that field stays verbatim) —
    # it is an owner classification, the sibling of specificity_level, and the ONLY basis
    # for named_measure_mismatch (D42). None = unassigned → excluded from that comparison.
    stated_position: Literal["support", "oppose"] | None = None
    curator_note: str | None = None  # internal, never rendered

    @field_validator("date")
    @classmethod
    def _date_is_iso(cls, v: str) -> str:
        # An ISO YYYY-MM-DD calendar date — never a free string (R-1a/M-6). A mistyped
        # date (`8/12/2026`) would otherwise ride into the id and break newest-first
        # timeline ordering (string comparison) silently. Validated here, at the model
        # level, so every write path (Flask app, repair, tests) is guarded at once.
        try:
            _date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"date must be ISO YYYY-MM-DD, got {v!r}") from exc
        return v


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
