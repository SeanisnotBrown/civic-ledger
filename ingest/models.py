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
    # Full official action timeline (V2-11). Same D27 sentinel as subjects /
    # cosponsor_ids: None = NOT YET COLLECTED, [] = collected and the government
    # lists none. `latest_action` below stays as it is -- it is the one-line
    # summary the pre-V2-11 pipeline already publishes, and the timeline does not
    # replace it.
    actions: list[BillAction] | None = None
    latest_action: str
    latest_action_date: str
    cbo_estimates: list[CboRef]
    source_url: str


class BillAction(_Strict):
    """One step in a bill's official action timeline (V2-11 task 3).

    Every field is the government's own, stored verbatim: `text` is the published
    sentence and is never summarised, reworded or classified (0.5). Nullability
    below is MEASURED, not assumed -- 520 real actions across six bills spanning
    four Congresses (task 3 survey, recorded in the D88 addendum):

      actionDate    520/520   -> `date`, required
      sourceSystem  520/520   -> `source_system`, required
      text          520/520   -> `text`, OPTIONAL -- see the correction below
      type          520/520   -> `type`, required
      actionCode    337/520   -> `action_code`, optional
      actionTime    227/520   -> `time`, optional  (44% -- never a sort key)
      committees     97/520   -> `committees`, optional
      recordedVotes  58/520   -> `rollcall_id`, optional

    **CORRECTION (2026-10-05): the 520/520 reading of `text` was a SAMPLING
    ARTEFACT and `text` is NOT required.** The task-3 survey's six bills all
    happened to carry it; the full-Congress backfill then hit a row that does
    not. s4869-118's `/actions` payload (cached at
    `data/raw/congress_gov/97050f2fb96e4fb9.json`) has three rows, and the
    Library of Congress `Intro-S` row dated 2024-07-30 has **no `text` key at
    all** -- not empty, absent. Under the old required field that was a
    `KeyError: 'text'` in `parse_actions` and it quarantined the whole bill
    (`data/quality/quarantine/bill-s4869-118.json`), publishing nothing for a
    real bill. Measured rate: **1 bill in 19,125** for Congress 118 -- rare,
    real, and the government's to repeat. Keeping the field required traded one
    missing sentence for an entire missing bill, which is the worse falsehood.

    **`None` is the ONLY absent-text representation; `""` must never be stored.**
    `parse_actions` normalises an empty or missing `text` to `None` for a reason
    that is load-bearing on the site: `actionText()` in `site/src/lib/display.ts`
    substitutes "(no action text on the official record)" with `??`, which
    catches `null`/`undefined` and does NOT catch `""`. An empty string would
    sail through the guard and render a blank timeline line -- publishing an
    action with no content, a Value #1 false framing. A sentinel STRING in the
    data is equally wrong: every text field here is the government's own (0.5),
    so our wording belongs in the site's copy, never in the record.

    `source_system` stores the NAME only. The Senate's block is `{"name":
    "Senate"}` with no `code` at all, while House/LoC blocks carry one, so a
    stored code would be nullable for a whole chamber and carry no information
    the name does not.

    `type` is a plain string, not a Literal. Eight values appear in the survey
    (Floor, ResolvingDifferences, Committee, IntroReferral, President, BecameLaw,
    Calendars, NotUsed) and the set is the government's to extend; pinning it
    would quarantine a bill for the crime of a new action type.

    `committees` is NOT decoration and is not droppable: it is the only thing
    distinguishing several otherwise byte-identical actions. hr2670-118 has five
    rows reading "Forwarded by Subcommittee to Full Committee by Voice Vote ." on
    one day under one action code, differing only in which subcommittee acted.
    Without this field the rendered timeline repeats a line five times with no
    explanation, and the dedupe that produced it looks like a bug (D88 addendum).

    `rollcall_id` is set ONLY when the action's `recordedVotes` entry resolves to
    a roll call this dataset actually holds -- otherwise null. In the survey 40 of
    58 resolved; the 18 misses were all 117th/116th Congress, real votes outside
    the covered window. Emitting an id for those would render a link to a `/v/`
    page that does not exist."""

    date: str
    time: str | None = None
    # verbatim; never summarised or classified (0.5). Nullable since 2026-10-05 --
    # congress.gov omits the key on rare rows (see the CORRECTION above). Never "".
    text: str | None = None
    type: str
    action_code: str | None = None
    source_system: str
    committees: list[str] | None = None
    rollcall_id: str | None = None

    @field_validator("date")
    @classmethod
    def _iso_date(cls, v: str) -> str:
        # EXTENDED form only: YYYY-MM-DD, zero-padded, hyphen-separated. Bare
        # `_date.fromisoformat` is not enough -- on 3.11+ it also accepts the
        # basic form `20230613` and week dates `2023-W24-2`, both of which parse
        # to a real date and then sort WRONG, because the timeline is ordered by
        # string comparison on this field. A mixed-format timeline would silently
        # render out of order rather than fail (value #1: fail loudly instead).
        if len(v) != 10 or v[4] != "-" or v[7] != "-":
            raise ValueError(f"date must be YYYY-MM-DD, got {v!r}")
        _date.fromisoformat(v)  # raises -> quarantine (6.1)
        return v


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
    # LIFETIME item counts as reported by `/member/{id}` at the time of the last full
    # fetch (D86): {"sponsored": n, "cosponsored": n}. Not a published metric — the
    # metrics read `sponsored`/`cosponsored` above, which are scoped to the covered
    # Congresses. This is the nightly's change probe: an identical pair from a fresh
    # one-request detail call means nothing was sponsored or cosponsored since this
    # record was written, so the many-page list fetch is skipped and the committed
    # items are kept. None on records written before D86 (forces one full fetch).
    lifetime_counts: dict[str, int] | None = None


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
    # NOTE: retired from the FEDERAL published set (2026-08-15, owner: "a dumb stat");
    # kept here because the Mississippi layer (MsMemberMetrics) still publishes it.


class CrossAisleValue(_Strict):
    # Final-passage rolls sponsored by the OTHER major party that the member cast yea/nay on,
    # and how many of those they voted Yea. Independents contribute nothing (no single
    # opposing party), so their denominator is 0 → pct null. Replaces party_unity federally.
    opposing_considered: int  # opposing-party final-passage bills the member voted on (yea/nay)
    opposing_yea: int         # of those, ones the member voted Yea (supported)
    pct: float | None         # 100 * opposing_yea / opposing_considered; None if considered == 0


class CountValue(_Strict):
    count: int


class EnactedRateValue(_Strict):
    sponsored: int
    enacted: int         # sponsored bills matched "Became Public Law"
    pct: float | None    # 100 * enacted / sponsored; None if sponsored == 0


class PositionMixValue(_Strict):
    cast: int            # yea + nay + present (positions actually cast; not_voting excluded)
    yea: int
    nay: int
    present: int
    yea_pct: float | None  # 100 * yea / cast; None when cast == 0. NOT an approval measure.
    nay_pct: float | None  # 100 * nay / cast; None when cast == 0


class CosponsorEnactedValue(_Strict):
    cosponsored: int
    enacted: int         # cosponsored bills that became law under their own bill number
    pct: float | None    # 100 * enacted / cosponsored; None if cosponsored == 0


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
    cross_aisle_support: CrossAisleValue  # replaced party_unity federally (2026-08-15)
    position_mix: PositionMixValue
    sponsored: CountValue
    cosponsored: CountValue
    enacted_rate: EnactedRateValue
    cosponsor_enacted_rate: CosponsorEnactedValue
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


# --- Events (V2-11 task 5) ------------------------------------------------
# The ONLY machine-readable feed the V2-12 alert Worker and the V2-13 push client
# read. Projected from data/bills/** by `ingest/events.py`; nothing here is
# collected, scored or worded by us -- every text field is the government's own.


class BillEvent(_Strict):
    """One official action on one bill, flattened for the monthly event feed.

    This is a PROJECTION, not a new source: `date`, `text`, `type`, `committees`
    and `rollcall_id` are copied verbatim off the bill's `BillAction`, and
    `policy_area`, `subjects` and `source_url` are denormalised off the bill so a
    consumer can filter a month's activity by topic without loading 38,756 bill
    files. `text` is never summarised or reworded (0.5).

    `id` hashes the WHOLE action row, not just its text. The plan said "one row
    per (bill_id, action date, action text hash)", which would silently collapse
    real distinct actions: hr2670-118 carries five actions reading "Forwarded by
    Subcommittee to Full Committee by Voice Vote ." on one date under one action
    code, differing only in `committees` (D88 addendum -- a narrower hash is
    exactly the bug that made `bill_actions()` return 225 of 234 actions). The
    id keeps the legible `{bill_id}--{date}--` prefix and widens the hash.

    `has_page` mirrors `votedBillIds()` in `site/src/lib/data.ts` -- SD-33 3(c):
    only a bill that reached a recorded vote gets a `/b/` page. A consumer links
    to `/b/{bill_id}` when this is true and to `source_url` on congress.gov when
    it is false. It is carried here rather than re-derived because the Worker and
    the push client have no access to data/votes/, and a wrong guess publishes a
    link to a page that does not exist (`npm run test:links` fails on the first)."""

    id: str  # f"{bill_id}--{date}--{sha256(action row)[:12]}"
    bill_id: str
    date: str  # the action's date, YYYY-MM-DD; the month file it lands in
    # Verbatim official action text (0.5: never summarised). NULLABLE, mirroring
    # `BillAction.text`: congress.gov omits the key on rare rows (1 bill in 19,125
    # on Congress 118 -- see the CORRECTION in BillAction's docstring). A consumer
    # must treat `null` as "the official record carries no sentence for this
    # action", NOT as "no action" -- the action itself is real and its date, type,
    # action code and source system are all here. `""` is never stored, so a
    # nullish check is sufficient and an emptiness check is not needed.
    text: str | None = None
    type: str  # the government's action type, verbatim (e.g. "Floor", "Committee")
    # `action_code` and `source_system` are carried for the SAME reason D89 carries
    # `committees`: they are in the id's hash, so without them a consumer sees two
    # events it has no way to tell apart. Measured, not hypothetical -- hr10547-118
    # has two real actions on 2024-12-20 both reading "Introduced in House" with
    # `committees: null`, differing only in `action_code` ("Intro-H" vs "1000").
    # Every field inside the hash is now visible on the row.
    action_code: str | None = None
    source_system: str  # the NAME ("House", "Senate", "Library of Congress")
    committees: list[str] | None = None  # the only thing distinguishing some rows
    rollcall_id: str | None = None  # set only when it resolves to a roll we HOLD
    policy_area: str | None = None  # denormalised off the bill
    subjects: list[str] | None = None  # denormalised off the bill, verbatim CRS terms
    source_url: str  # the bill's congress.gov URL -- the link for a pageless bill
    has_page: bool  # whether /b/{bill_id} exists (SD-33 3(c))


class EventsFile(_Strict):
    """data/events/{YYYY-MM}.json -- every official action dated in that month.

    No wall-clock anywhere: `month` and `count` are both derived from the rows, so
    a quiet run re-exports byte-identically (verify-recompute invariant 8)."""

    month: str  # YYYY-MM
    count: int  # == len(events); a cheap integrity check for a feed consumer
    events: list[BillEvent]


# --- Topics (V2-11 task 6) ------------------------------------------------
# The official government vocabulary, nothing else. SD-33 decision 4(a): the 31
# policy areas and the CRS legislative subject terms, VERBATIM, with no
# owner-authored bundles this release (H22 stays optional). Nothing here is
# evaluative, so §0.8 does not apply -- a topic is a label the government already
# put on a bill, not a judgement we made about it.


class TopicEntry(_Strict):
    """One topic: the official term, its mechanical slug, and the bills under it.

    `name` is the government's string EXACTLY as published -- commas, apostrophes,
    capitalisation and all ("Veterans' pensions", "Labor, employment"). It is what
    renders. `slug` is derived from it by one mechanical rule and exists only to be
    a URL; it is never shown to a reader and never edited by hand.

    `bill_ids` is the full membership, not a sample, and is sorted so the file is
    byte-stable. It is what lets a subscription on a topic resolve to bills without
    the subscriber's client reading all 38,756 bill records."""

    slug: str  # mechanical: lowercase, non-alphanumeric runs -> "-", trimmed
    name: str  # the official term, verbatim (0.5: never reworded)
    bill_count: int  # == len(bill_ids)
    bill_ids: list[str]  # sorted


class TopicsFile(_Strict):
    """data/topics/index.json -- the whole topic vocabulary in one file.

    Two separate vocabularies, deliberately NOT merged: `policy_areas` is the
    government's single coarse classification (exactly one per bill, 31 of them),
    and `subjects` is the much larger CRS legislative-subject list (many per bill).
    Merging them would make "Health" the policy area indistinguishable from "Health"
    the subject term, which are different claims about a bill.

    `counts` is derived from the lists, so there is no wall-clock anywhere and a
    quiet re-run re-exports byte-identically (verify-recompute invariant 9).

    **No number here is a cap.** SD-33 was ratified against a measured snapshot of
    31 policy areas and 872 CRS terms; 877 distinct terms were already on disk
    partway through the V2-11 backfill. The vocabulary is the government's to
    extend, so nothing in this file or its builder asserts a total."""

    policy_areas: list[TopicEntry]  # sorted by slug
    subjects: list[TopicEntry]  # sorted by slug
    counts: dict[str, int]  # {"policy_areas": N, "subjects": M, "bills": B}


# --- Grades (V2-4, Tier 3) ------------------------------------------------
# The FIRST evaluative output (SD-26). Computed ONLY in ingest/scoring.py from the
# owner-ratified data/config/thresholds.yaml (§0.8) — every label here appears
# verbatim in that config, enforced by the §6.8 guard. V2-4 grades one category
# (attendance) on fixed bars; the overall composite grade is deferred until its
# formula is ratified. No wall-clock: provenance is `formula_version` + `ratified`.


class GradeBand(_Strict):
    grade: str  # "A".."F"
    min: int | float  # the metric value at/above which this band applies (top-down)
    label: str  # the EXACT rendered string, e.g. "A — Strong attendance"


class GradeEntry(_Strict):
    value: int | float  # the graded metric value (e.g. attendance pct)
    grade: str
    label: str


class GradesFile(_Strict):
    """data/grades/{category}.json (V2-4). One evaluative category's grade per member,
    recomputed from data/metrics.json + the ratified thresholds. No wall-clock."""

    category: str  # "attendance"
    metric: str  # the Tier-2 metric key graded
    field: str  # the scalar field of that metric graded ("pct")
    formula_version: int  # bumps when a ratified value changes (grade provenance)
    ratified: str  # the thresholds' ratification date (provenance, not wall-clock)
    min_eligible: int  # members with fewer eligible rolls are set aside (min_service)
    bands: list[GradeBand]  # the ratified cutoffs, echoed from config
    exception_label: str  # rendered for members set aside (too few votes)
    members: dict[str, GradeEntry]  # bioguide -> grade (members actually graded)
    exceptions: dict[str, str]  # bioguide -> reason (delegate | min_service | no_record)


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
