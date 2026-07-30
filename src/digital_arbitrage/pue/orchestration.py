"""Runtime orchestration for the PUE reasoning chain (spec section 18).

Wires ``admit_observation -> extract_evidence -> construct_claims ->
generate_hypotheses -> retrieve_candidates -> evaluate_candidates ->
form_decision -> generate_explanation -> publish_result`` into single-case
and batch entry points. Single-case functions are the reference behavior;
batching must not alter case semantics (spec 18.3).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .admission import admit_observation
from .catalogue import CandidateRepository, JsonCandidateRepository
from .claims import construct_claims, validate_identifier_claims
from .decisions import form_decision
from .enums import (
    CalibrationStatus,
    ComparabilityStatus,
    DecisionType,
    ExplanationProfile,
    IdentificationLevel,
    ProcessingFailureCategory,
    ProductForm,
    UncertaintyBand,
)
from .evaluation import evaluate_candidates
from .evidence import extract_evidence
from .explanations import generate_explanation
from .hypotheses import generate_hypotheses
from .models import (
    Candidate,
    CandidateEvaluation,
    Claim,
    Decision,
    DecisionUncertainty,
    Evidence,
    Explanation,
    Observation,
    ProcessingContext,
    ProductHypothesis,
    ProductUnderstandingResult,
    ReasoningRecord,
)
from .policies import DecisionPolicy
from .retrieval import retrieve_candidates
from .validation import PueValidationError
from .version import (
    CAPABILITY_VERSION,
    KNOWLEDGE_VERSION,
    POLICY_VERSION,
    SCHEMA_VERSION,
    TERM_VERSION,
)

if TYPE_CHECKING:
    from ..normalization.models import NormalizedListing


def default_id_factory() -> str:
    """Default injectable identifier factory (UUID4)."""
    return str(uuid.uuid4())


def default_clock() -> datetime:
    """Default injectable clock (UTC now)."""
    return datetime.now(UTC)


def build_default_context(
    *,
    id_factory: Callable[[], str] | None = None,
    clock: Callable[[], datetime] | None = None,
    schema_version: str = SCHEMA_VERSION,
    capability_version: str = CAPABILITY_VERSION,
    policy_version: str = POLICY_VERSION,
    knowledge_version: str = KNOWLEDGE_VERSION,
    term_version: str = TERM_VERSION,
) -> ProcessingContext:
    """Build a :class:`ProcessingContext` with deterministic defaults."""
    return ProcessingContext(
        schema_version=schema_version,
        capability_version=capability_version,
        policy_version=policy_version,
        knowledge_version=knowledge_version,
        term_version=term_version,
        id_factory=id_factory or default_id_factory,
        clock=clock or default_clock,
    )


DEFAULT_POLICY = DecisionPolicy()


@dataclass(slots=True)
class CaseReasoningState:
    """Mutable, internal accumulator threaded through a single case's stages.

    Not a persisted reasoning object itself; :class:`ReasoningRecord` is the
    persisted, immutable snapshot built at the end of :func:`process_one`.
    """

    observation: Observation
    evidence: Sequence[Evidence] = ()
    claims: Sequence[Claim] = ()
    hypotheses: Sequence[ProductHypothesis] = ()
    candidates: Sequence[Candidate] = ()
    candidate_evaluations: Sequence[CandidateEvaluation] = ()
    stage_timings_ms: dict[str, float] = field(default_factory=dict)


def _unknown_uncertainty() -> DecisionUncertainty:
    return DecisionUncertainty(
        observation_quality=UncertaintyBand.UNKNOWN,
        claim_support=UncertaintyBand.UNKNOWN,
        candidate_fit=UncertaintyBand.UNKNOWN,
        evidence_coverage=UncertaintyBand.UNKNOWN,
        contradiction_level=UncertaintyBand.UNKNOWN,
        distinguishability=UncertaintyBand.UNKNOWN,
        calibration_status=CalibrationStatus.OUTSIDE_EVALUATED_DOMAIN,
    )


def _failure_record(
    listing: object,
    context: ProcessingContext,
    category: ProcessingFailureCategory,
    detail: str,
) -> ReasoningRecord:
    """Build a minimal, complete ReasoningRecord for a PROCESSING_FAILED case.

    A processing failure must never be interpreted as product uncertainty
    (spec 4.2/16.8): the Decision here always carries an explicit
    ``ProcessingFailureCategory`` in its operational metrics, never an
    ``AbstentionReason``.
    """
    case_id = context.id_factory()
    observation_id = context.id_factory()
    provider = getattr(getattr(listing, "source", None), "provider", None) or "unknown"
    provider_listing_id = getattr(getattr(listing, "source", None), "listing_id", None) or "unknown"
    raw_title = getattr(getattr(listing, "source", None), "title", None) or ""

    observation = Observation(
        observation_id=observation_id,
        case_id=case_id,
        provider=str(provider),
        provider_listing_id=str(provider_listing_id),
        raw_title=str(raw_title),
        normalized_title=str(raw_title),
        raw_description=None,
        raw_category=None,
        raw_condition=None,
        raw_attributes={},
        image_refs=(),
        acquired_at=context.clock(),
        source_fingerprint="unavailable",
        schema_version=context.schema_version,
    )
    decision = Decision(
        decision_id=context.id_factory(),
        case_id=case_id,
        observation_id=observation_id,
        decision_type=DecisionType.PROCESSING_FAILED,
        identification_level=IdentificationLevel.UNKNOWN,
        selected_hypothesis_id=None,
        selected_candidate_instance_id=None,
        product_form=ProductForm.UNKNOWN,
        product_type=None,
        identified_brand=None,
        identified_family=None,
        identified_model=None,
        identified_variant=None,
        alternative_candidate_ids=(),
        unresolved_fields=(),
        contradiction_codes=(),
        abstention_reason=None,
        review_recommended=True,
        comparability_status=ComparabilityStatus.NOT_ASSESSED,
        uncertainty=_unknown_uncertainty(),
        policy_version=context.policy_version,
        knowledge_version=context.knowledge_version,
        capability_version=context.capability_version,
    )
    explanation = Explanation(
        explanation_id=context.id_factory(),
        decision_id=decision.decision_id,
        summary=f"Processing failed ({category.value}): {detail}",
        supporting_points=(),
        contradictory_points=(),
        unresolved_points=(),
        rejected_alternatives=(),
        evidence_ids=(),
        profile=ExplanationProfile.OPERATOR,
    )
    return ReasoningRecord(
        case_id=case_id,
        observation=observation,
        evidence=(),
        claims=(),
        hypotheses=(),
        candidates=(),
        candidate_evaluations=(),
        decision=decision,
        explanation=explanation,
        operational_metrics={"failure_category": category.value, "failure_detail": detail},
        schema_version=context.schema_version,
        created_at=context.clock(),
    )


def process_one(
    listing: NormalizedListing,
    context: ProcessingContext,
    *,
    repository: CandidateRepository | None = None,
    policy: DecisionPolicy | None = None,
) -> ReasoningRecord:
    """Run one listing through the complete PUE reasoning chain.

    Note on the component contract: the spec's abstract signature is
    ``process_one(listing, context) -> ReasoningRecord``. ``repository`` and
    ``policy`` are added as optional keyword parameters (defaulting to the
    seed JSON catalogue and the default policy) so the function remains
    callable with just ``(listing, context)`` while still allowing injection
    for tests.
    """
    try:
        repo = repository or JsonCandidateRepository()
    except PueValidationError as exc:
        return _failure_record(
            listing, context, ProcessingFailureCategory.CATALOGUE_UNAVAILABLE, str(exc)
        )
    active_policy = policy or DEFAULT_POLICY

    try:
        observation = admit_observation(listing, context)
    except PueValidationError as exc:
        return _failure_record(
            listing, context, ProcessingFailureCategory.MALFORMED_INPUT, str(exc)
        )

    try:
        t0 = time.perf_counter()
        evidence = extract_evidence(observation, context)
        t1 = time.perf_counter()
        claims = construct_claims(observation, evidence, context)
        claims = validate_identifier_claims(claims, context, repo)
        hypotheses = generate_hypotheses(observation, claims, context)
        t2 = time.perf_counter()
        candidates = retrieve_candidates(
            hypotheses, repo, context, observation=observation, claims=claims
        )
        t3 = time.perf_counter()
        state = CaseReasoningState(
            observation=observation,
            evidence=evidence,
            claims=claims,
            hypotheses=hypotheses,
            candidates=candidates,
        )
        evaluations = evaluate_candidates(state, repo, context)
        state.candidate_evaluations = evaluations
        t4 = time.perf_counter()
        decision = form_decision(state, active_policy, context, repository=repo)
        explanation = generate_explanation(state, decision, context)
        t5 = time.perf_counter()
    except Exception as exc:  # noqa: BLE001 - deliberate: convert to PROCESSING_FAILED
        return _failure_record(
            listing, context, ProcessingFailureCategory.UNEXPECTED_EXCEPTION, str(exc)
        )

    operational_metrics = {
        "extraction_ms": round((t1 - t0) * 1000, 4),
        "claims_hypotheses_ms": round((t2 - t1) * 1000, 4),
        "retrieval_ms": round((t3 - t2) * 1000, 4),
        "evaluation_ms": round((t4 - t3) * 1000, 4),
        "decision_explanation_ms": round((t5 - t4) * 1000, 4),
        "total_ms": round((t5 - t0) * 1000, 4),
        "evidence_count": len(evidence),
        "claim_count": len(claims),
        "hypothesis_count": len(hypotheses),
        "candidate_count": len(candidates),
    }

    return ReasoningRecord(
        case_id=observation.case_id,
        observation=observation,
        evidence=evidence,
        claims=claims,
        hypotheses=hypotheses,
        candidates=candidates,
        candidate_evaluations=evaluations,
        decision=decision,
        explanation=explanation,
        operational_metrics=operational_metrics,
        schema_version=context.schema_version,
        created_at=context.clock(),
    )


def process_many(
    listings: Sequence[NormalizedListing],
    context: ProcessingContext,
    *,
    repository: CandidateRepository | None = None,
    policy: DecisionPolicy | None = None,
) -> tuple[ReasoningRecord, ...]:
    """Batch wrapper. Semantically equivalent to calling :func:`process_one`
    for each listing in order (spec 18.3): batching never changes a case's
    Decision - including when the default catalogue is unavailable, in
    which case every listing gets its own PROCESSING_FAILED/
    CATALOGUE_UNAVAILABLE record, exactly as an individual
    ``process_one(listing, context)`` call would produce.
    """
    if repository is not None:
        repo: CandidateRepository | None = repository
    else:
        try:
            repo = JsonCandidateRepository()
        except PueValidationError as exc:
            return tuple(
                _failure_record(
                    listing, context, ProcessingFailureCategory.CATALOGUE_UNAVAILABLE, str(exc)
                )
                for listing in listings
            )
    return tuple(
        process_one(listing, context, repository=repo, policy=policy) for listing in listings
    )


def publish_result(record: ReasoningRecord) -> ProductUnderstandingResult:
    """Publish the stable envelope for a completed ReasoningRecord (spec 8.11)."""
    decision = record.decision
    identity = {
        "brand": decision.identified_brand,
        "family": decision.identified_family,
        "model": decision.identified_model,
        "variant": decision.identified_variant,
    }
    return ProductUnderstandingResult(
        result_schema_version=record.schema_version,
        case_id=record.case_id,
        observation_id=record.observation.observation_id,
        decision_id=decision.decision_id,
        status=decision.decision_type,
        identification_level=decision.identification_level,
        product_form=decision.product_form,
        product_type=decision.product_type,
        catalogue_product_id=decision.selected_candidate_instance_id
        and next(
            (
                c.catalogue_product_id
                for c in record.candidates
                if c.candidate_instance_id == decision.selected_candidate_instance_id
            ),
            None,
        ),
        identity=identity,
        comparability_status=decision.comparability_status,
        unresolved_fields=decision.unresolved_fields,
        review_recommended=decision.review_recommended,
        explanation_summary=record.explanation.summary,
        reasoning_record_ref=record.case_id,
    )
