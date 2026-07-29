"""Enumerations for the Product Understanding Engine (PUE).

All enumerations are explicit :class:`~enum.StrEnum` members serialized by
their stable string value (see
``docs/architecture/PUE_v0.1_VERTICAL_SLICE_SPECIFICATION.md`` section 7.5).
Unknown future values must never silently map onto an existing member: callers
should fail loudly (e.g. via ``EnumType(value)``) rather than guess.

``ESCALATED`` is deliberately absent from :class:`DecisionType`. Escalation is
a runtime action taken before a final Decision, not a Decision outcome.
"""

from __future__ import annotations

from enum import StrEnum


class EvidenceType(StrEnum):
    BRAND_TOKEN = "brand_token"
    PRODUCT_FAMILY_TOKEN = "product_family_token"
    MODEL_TOKEN = "model_token"
    VARIANT_TOKEN = "variant_token"
    MPN_TOKEN = "mpn_token"
    GTIN_TOKEN = "gtin_token"
    CAPACITY_VALUE = "capacity_value"
    PRODUCT_FORM_TERM = "product_form_term"
    PRODUCT_TYPE_TERM = "product_type_term"
    COMPATIBILITY_TERM = "compatibility_term"
    EXCLUSION_TERM = "exclusion_term"
    CONDITION_TERM = "condition_term"
    BUNDLE_TERM = "bundle_term"
    PACKAGING_TERM = "packaging_term"
    STRUCTURED_ATTRIBUTE = "structured_attribute"
    CLASSIFIER_OUTPUT = "classifier_output"


class EvidencePolarity(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    QUALIFYING = "qualifying"
    NEUTRAL = "neutral"
    UNRESOLVED = "unresolved"


class ClaimPredicate(StrEnum):
    BRAND = "brand"
    CHIPSET_MANUFACTURER = "chipset_manufacturer"
    PRODUCT_FAMILY = "product_family"
    MODEL = "model"
    VARIANT = "variant"
    MPN = "mpn"
    GTIN = "gtin"
    PRODUCT_FORM = "product_form"
    PRODUCT_TYPE = "product_type"
    CONDITION = "condition"
    CAPACITY = "capacity"
    COMPATIBLE_WITH = "compatible_with"
    BUNDLE_CONTENT = "bundle_content"
    INCLUDED = "included"
    NOT_INCLUDED = "not_included"


class ClaimStatus(StrEnum):
    PROPOSED = "proposed"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    QUALIFIED = "qualified"
    UNRESOLVED = "unresolved"
    REJECTED = "rejected"


class SupportLevel(StrEnum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    DETERMINISTIC = "deterministic"


class ProductForm(StrEnum):
    COMPLETE_PRODUCT = "complete_product"
    ACCESSORY = "accessory"
    COMPONENT = "component"
    REPLACEMENT_PART = "replacement_part"
    COMPATIBLE_ITEM = "compatible_item"
    PACKAGING_ONLY = "packaging_only"
    BUNDLE = "bundle"
    SERVICE = "service"
    INCOMPLETE_PRODUCT = "incomplete_product"
    UNKNOWN = "unknown"


class HypothesisStatus(StrEnum):
    ACTIVE = "active"
    WEAK = "weak"
    CONTRADICTED = "contradicted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class RetrievalMethod(StrEnum):
    EXACT_MPN = "exact_mpn"
    EXACT_GTIN = "exact_gtin"
    EXACT_CANONICAL_NAME = "exact_canonical_name"
    STRUCTURED_FILTER = "structured_filter"
    NORMALIZED_TOKEN_MATCH = "normalized_token_match"
    FUZZY_TITLE_MATCH = "fuzzy_title_match"
    ALIAS_MATCH = "alias_match"


class ComparisonResult(StrEnum):
    AGREE = "agree"
    CONTRADICT = "contradict"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


class ContradictionSeverity(StrEnum):
    SOFT = "soft"
    HARD = "hard"


class CandidateOutcome(StrEnum):
    STRONGLY_SUPPORTED = "strongly_supported"
    SUPPORTED = "supported"
    PROVISIONALLY_SUPPORTED = "provisionally_supported"
    WEAKLY_SUPPORTED = "weakly_supported"
    INDISTINGUISHABLE = "indistinguishable"
    CONTRADICTED = "contradicted"
    REJECTED = "rejected"
    UNEVALUABLE = "unevaluable"


class DecisionType(StrEnum):
    """The seven valid final Decision outcomes.

    ``ESCALATED`` is intentionally not a member of this enum.
    """

    IDENTIFIED = "identified"
    PARTIALLY_IDENTIFIED = "partially_identified"
    CLASSIFIED = "classified"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    OUTSIDE_SUPPORTED_DOMAIN = "outside_supported_domain"
    PROCESSING_FAILED = "processing_failed"


class IdentificationLevel(StrEnum):
    EXACT_CATALOGUE_PRODUCT = "exact_catalogue_product"
    VARIANT = "variant"
    MODEL = "model"
    FAMILY = "family"
    BRAND_AND_PRODUCT_TYPE = "brand_and_product_type"
    PRODUCT_TYPE = "product_type"
    UNKNOWN = "unknown"


class ComparabilityStatus(StrEnum):
    DIRECTLY_COMPARABLE = "directly_comparable"
    COMPARABLE_AT_BROADER_LEVEL = "comparable_at_broader_level"
    NOT_COMPARABLE_PRODUCT_FORM = "not_comparable_product_form"
    NOT_COMPARABLE_BUNDLE = "not_comparable_bundle"
    NOT_COMPARABLE_CONDITION = "not_comparable_condition"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    NOT_ASSESSED = "not_assessed"


class UncertaintyBand(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"


class CalibrationStatus(StrEnum):
    UNCALIBRATED = "uncalibrated"
    PROVISIONAL = "provisional"
    EVALUATED = "evaluated"
    OUTSIDE_EVALUATED_DOMAIN = "outside_evaluated_domain"


class AbstentionReason(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNRESOLVED_CONTRADICTION = "unresolved_contradiction"
    CANDIDATES_INDISTINGUISHABLE = "candidates_indistinguishable"
    NO_SUITABLE_CANDIDATE = "no_suitable_candidate"
    SOURCE_QUALITY_TOO_LOW = "source_quality_too_low"
    PROCESSING_LIMIT_REACHED = "processing_limit_reached"
    UNKNOWN_PRODUCT_PATTERN = "unknown_product_pattern"


class ExplanationProfile(StrEnum):
    OPERATOR = "operator"


class CaseState(StrEnum):
    RECEIVED = "received"
    ADMITTED = "admitted"
    EXTRACTING = "extracting"
    CONSTRUCTING_CLAIMS = "constructing_claims"
    GENERATING_HYPOTHESES = "generating_hypotheses"
    RETRIEVING_CANDIDATES = "retrieving_candidates"
    EVALUATING_CANDIDATES = "evaluating_candidates"
    FORMING_DECISION = "forming_decision"
    GENERATING_EXPLANATION = "generating_explanation"
    PERSISTING = "persisting"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingFailureCategory(StrEnum):
    """Explicit failure categories for ``PROCESSING_FAILED`` Decisions."""

    MALFORMED_INPUT = "malformed_input"
    CATALOGUE_UNAVAILABLE = "catalogue_unavailable"
    PERSISTENCE_FAILURE = "persistence_failure"
    UNEXPECTED_EXCEPTION = "unexpected_exception"
