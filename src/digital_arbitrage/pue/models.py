"""Immutable object model for the Product Understanding Engine (PUE).

Every material reasoning object is a ``@dataclass(frozen=True, slots=True)``
(spec section 6.1). Mapping-typed fields are recursively frozen into
``MappingProxyType`` trees by :func:`digital_arbitrage.pue.validation.freeze`
so that nested dicts/lists cannot be mutated after construction (spec section
7.4). Objects that have entered a completed :class:`ReasoningRecord` must not
be mutated; corrections create new objects and a new Decision.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime

from .enums import (
    AbstentionReason,
    CalibrationStatus,
    CandidateOutcome,
    ClaimPredicate,
    ClaimStatus,
    ComparabilityStatus,
    ComparisonResult,
    ContradictionSeverity,
    DecisionType,
    EvidencePolarity,
    EvidenceType,
    ExplanationProfile,
    HypothesisStatus,
    IdentificationLevel,
    ProductForm,
    RetrievalMethod,
    SupportLevel,
    UncertaintyBand,
)
from .validation import freeze_mapping, freeze_value


# --------------------------------------------------------------------------- #
# 8.1 Observation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Observation:
    """The preserved PUE representation of a source listing (spec 8.1)."""

    observation_id: str
    case_id: str
    provider: str
    provider_listing_id: str
    raw_title: str
    normalized_title: str
    raw_description: str | None
    raw_category: str | None
    raw_condition: str | None
    raw_attributes: Mapping[str, object]
    image_refs: tuple[str, ...]
    acquired_at: datetime
    source_fingerprint: str
    schema_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_attributes", freeze_mapping(self.raw_attributes))
        object.__setattr__(self, "image_refs", tuple(self.image_refs))


# --------------------------------------------------------------------------- #
# 8.2 Evidence
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Evidence:
    """Something detected in an Observation (spec 8.2)."""

    evidence_id: str
    observation_id: str
    evidence_type: EvidenceType
    raw_value: str
    normalized_value: str | int | float | bool | None
    source_field: str
    source_start: int | None
    source_end: int | None
    extraction_method: str
    extraction_confidence: float | None
    polarity_hint: EvidencePolarity | None
    capability_version: str


# --------------------------------------------------------------------------- #
# 8.3 Claim
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Claim:
    """A product-relevant proposition supported by Evidence (spec 8.3)."""

    claim_id: str
    observation_id: str
    predicate: ClaimPredicate
    value: str | int | float | bool
    status: ClaimStatus
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...]
    qualifying_evidence_ids: tuple[str, ...]
    support_level: SupportLevel
    created_by: str
    capability_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "supporting_evidence_ids", tuple(self.supporting_evidence_ids))
        object.__setattr__(
            self, "contradicting_evidence_ids", tuple(self.contradicting_evidence_ids)
        )
        object.__setattr__(self, "qualifying_evidence_ids", tuple(self.qualifying_evidence_ids))


# --------------------------------------------------------------------------- #
# 8.4 Product Hypothesis
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ProductHypothesis:
    """One coherent possible interpretation of the Observation (spec 8.4)."""

    hypothesis_id: str
    observation_id: str
    claim_ids: tuple[str, ...]
    product_form: ProductForm
    product_type: str | None
    brand: str | None
    family: str | None
    model: str | None
    variant: str | None
    compatibility_target: str | None
    coherence: float
    evidence_coverage: float
    status: HypothesisStatus
    unresolved_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_ids", tuple(self.claim_ids))
        object.__setattr__(self, "unresolved_fields", tuple(self.unresolved_fields))


# --------------------------------------------------------------------------- #
# 8.5 Candidate (catalogue record + retrieval instance)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class CatalogueProduct:
    """A known catalogue product or product concept (spec 8.5)."""

    catalogue_product_id: str
    canonical_title: str
    brand: str
    chipset_manufacturer: str | None
    family: str
    model: str
    variant: str | None
    product_form: ProductForm
    product_type: str
    identifiers: Mapping[str, tuple[str, ...]]
    aliases: tuple[str, ...]
    attributes: Mapping[str, object]
    compatibility_targets: tuple[str, ...]
    knowledge_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "identifiers",
            freeze_mapping({k: tuple(v) for k, v in self.identifiers.items()}),
        )
        object.__setattr__(self, "aliases", tuple(self.aliases))
        object.__setattr__(self, "attributes", freeze_mapping(self.attributes))
        object.__setattr__(self, "compatibility_targets", tuple(self.compatibility_targets))


@dataclass(frozen=True, slots=True)
class Candidate:
    """A retrieval instance referencing a :class:`CatalogueProduct` (spec 8.5)."""

    candidate_instance_id: str
    catalogue_product_id: str
    hypothesis_id: str
    retrieval_method: RetrievalMethod
    retrieval_rank: int
    retrieval_score: float
    matched_fields: tuple[str, ...]
    knowledge_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "matched_fields", tuple(self.matched_fields))


# --------------------------------------------------------------------------- #
# 8.6 Candidate Evaluation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ComparisonFinding:
    """A single agreement/contradiction/missing-information finding (spec 8.6)."""

    field: str
    observed_value: object
    candidate_value: object
    result: ComparisonResult
    severity: ContradictionSeverity | None
    evidence_ids: tuple[str, ...]
    explanation: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        # Normalize list-like values to tuples so JSON round trips (which
        # cannot distinguish list from tuple) compare equal to the original.
        object.__setattr__(self, "observed_value", freeze_value(self.observed_value))
        object.__setattr__(self, "candidate_value", freeze_value(self.candidate_value))


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    """How well a Candidate explains the listing (spec 8.6)."""

    candidate_evaluation_id: str
    candidate_instance_id: str
    hypothesis_id: str
    agreements: tuple[ComparisonFinding, ...]
    contradictions: tuple[ComparisonFinding, ...]
    missing_information: tuple[ComparisonFinding, ...]
    identity_fit: float
    product_form_fit: float
    attribute_fit: float
    evidence_coverage: float
    hard_rejected: bool
    evaluation_outcome: CandidateOutcome
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "agreements", tuple(self.agreements))
        object.__setattr__(self, "contradictions", tuple(self.contradictions))
        object.__setattr__(self, "missing_information", tuple(self.missing_information))


# --------------------------------------------------------------------------- #
# 8.8 Decision uncertainty
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class DecisionUncertainty:
    """Named uncertainty dimensions, not a probability (spec 8.8)."""

    observation_quality: UncertaintyBand
    claim_support: UncertaintyBand
    candidate_fit: UncertaintyBand
    evidence_coverage: UncertaintyBand
    contradiction_level: UncertaintyBand
    distinguishability: UncertaintyBand
    calibration_status: CalibrationStatus


# --------------------------------------------------------------------------- #
# 8.7 Decision
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Decision:
    """The formal product-understanding result (spec 8.7)."""

    decision_id: str
    case_id: str
    observation_id: str
    decision_type: DecisionType
    identification_level: IdentificationLevel
    selected_hypothesis_id: str | None
    selected_candidate_instance_id: str | None
    product_form: ProductForm
    product_type: str | None
    identified_brand: str | None
    identified_family: str | None
    identified_model: str | None
    identified_variant: str | None
    alternative_candidate_ids: tuple[str, ...]
    unresolved_fields: tuple[str, ...]
    contradiction_codes: tuple[str, ...]
    abstention_reason: AbstentionReason | None
    review_recommended: bool
    comparability_status: ComparabilityStatus
    uncertainty: DecisionUncertainty
    policy_version: str
    knowledge_version: str
    capability_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "alternative_candidate_ids", tuple(self.alternative_candidate_ids))
        object.__setattr__(self, "unresolved_fields", tuple(self.unresolved_fields))
        object.__setattr__(self, "contradiction_codes", tuple(self.contradiction_codes))


# --------------------------------------------------------------------------- #
# 8.9 Explanation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Explanation:
    """An explanation derived from the actual reasoning record (spec 8.9)."""

    explanation_id: str
    decision_id: str
    summary: str
    supporting_points: tuple[str, ...]
    contradictory_points: tuple[str, ...]
    unresolved_points: tuple[str, ...]
    rejected_alternatives: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    profile: ExplanationProfile

    def __post_init__(self) -> None:
        object.__setattr__(self, "supporting_points", tuple(self.supporting_points))
        object.__setattr__(self, "contradictory_points", tuple(self.contradictory_points))
        object.__setattr__(self, "unresolved_points", tuple(self.unresolved_points))
        object.__setattr__(self, "rejected_alternatives", tuple(self.rejected_alternatives))
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))


# --------------------------------------------------------------------------- #
# 8.10 Reasoning Record
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ReasoningRecord:
    """The top-level persisted unit (spec 8.10)."""

    case_id: str
    observation: Observation
    evidence: tuple[Evidence, ...]
    claims: tuple[Claim, ...]
    hypotheses: tuple[ProductHypothesis, ...]
    candidates: tuple[Candidate, ...]
    candidate_evaluations: tuple[CandidateEvaluation, ...]
    decision: Decision
    explanation: Explanation
    operational_metrics: Mapping[str, object]
    schema_version: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "claims", tuple(self.claims))
        object.__setattr__(self, "hypotheses", tuple(self.hypotheses))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "candidate_evaluations", tuple(self.candidate_evaluations))
        object.__setattr__(self, "operational_metrics", freeze_mapping(self.operational_metrics))


# --------------------------------------------------------------------------- #
# 8.11 Product Understanding Result
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ProductUnderstandingResult:
    """Stable publication envelope; not a new reasoning stage (spec 8.11)."""

    result_schema_version: str
    case_id: str
    observation_id: str
    decision_id: str
    status: DecisionType
    identification_level: IdentificationLevel
    product_form: ProductForm
    product_type: str | None
    catalogue_product_id: str | None
    identity: Mapping[str, object]
    comparability_status: ComparabilityStatus
    unresolved_fields: tuple[str, ...]
    review_recommended: bool
    explanation_summary: str
    reasoning_record_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "identity", freeze_mapping(self.identity))
        object.__setattr__(self, "unresolved_fields", tuple(self.unresolved_fields))


# --------------------------------------------------------------------------- #
# Supporting runtime objects (not persisted reasoning objects themselves)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ProcessingContext:
    """Injectable, deterministic runtime context for a PUE run.

    ``id_factory`` and ``clock`` are injectable so tests can produce
    deterministic UUIDs/timestamps (spec: "UUID object identity with
    injectable ID factory").
    """

    schema_version: str
    capability_version: str
    policy_version: str
    knowledge_version: str
    term_version: str
    id_factory: Callable[[], str] = field(repr=False)
    clock: Callable[[], datetime] = field(repr=False)
    max_active_hypotheses: int = 3
    max_candidates_before_rerank: int = 20
    max_candidate_evaluations: int = 10


@dataclass(frozen=True, slots=True)
class CandidateQuery:
    """Query passed to a :class:`CandidateRepository` (spec section 13)."""

    brand: str | None
    family: str | None
    model: str | None
    variant: str | None
    product_form: ProductForm
    product_type: str | None
    identifiers: Mapping[str, str]
    attributes: Mapping[str, object]
    normalized_text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "identifiers", freeze_mapping(self.identifiers))
        object.__setattr__(self, "attributes", freeze_mapping(self.attributes))
