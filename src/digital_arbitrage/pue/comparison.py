"""Classifier/PUE comparison contract and reporting (Sprint 2, Task 1).

Produces an *inspectable*, unlabelled comparison between the existing
deterministic title classifier's verdict (
:class:`digital_arbitrage.classification.models.ListingClassification`) and
an independently-produced PUE :class:`~digital_arbitrage.pue.models.Decision`
for the same listing.

This module never re-runs the classifier and never feeds classifier output
into PUE Decision Formation: both inputs are already-computed, and
:func:`compare_classifier_and_pue` is a pure function over them.

Categories describe **observable differences only** (spec: no ground truth
exists yet). None of the categories claim correctness - a labelled benchmark
is Sprint 3 work (see
``docs/architecture/PUE_v0.1_VERTICAL_SLICE_SPECIFICATION.md`` section 22/23.4).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ..classification.models import Classification, ListingClassification
from .enums import ComparabilityStatus, DecisionType, IdentificationLevel, ProductForm
from .models import ReasoningRecord

#: The existing title classifier has no formal version constant of its own
#: (unlike the PUE's ``pue.version`` module). This is an accepted, documented
#: deviation for Sprint 2: a stand-in capability version so comparison
#: records remain traceable if the classifier's keyword lists change.
CLASSIFIER_CAPABILITY_VERSION = "title-classifier-1.0"

#: Version of this comparison contract itself.
COMPARISON_SCHEMA_VERSION = "pue-comparison-0.1.0"


class ComparisonCategory(StrEnum):
    """A stable, unlabelled description of an observable classifier/PUE
    difference. See module docstring: none of these claim correctness."""

    AGREEMENT = "agreement"
    PRODUCT_FORM_DISAGREEMENT = "product_form_disagreement"
    PUE_ABSTAINED = "pue_abstained"
    PUE_BROADER_IDENTITY = "pue_broader_identity"
    PUE_MORE_SPECIFIC_IDENTITY = "pue_more_specific_identity"
    PUE_BLOCKED_DIRECT_COMPARABILITY = "pue_blocked_direct_comparability"
    OTHER_DISAGREEMENT = "other_disagreement"


@dataclass(frozen=True, slots=True)
class ClassifierPueComparison:
    """One case's classifier-vs-PUE comparison record."""

    case_id: str
    provider: str
    provider_listing_id: str
    source_fingerprint: str

    classifier_label: str
    classifier_score: int
    classifier_reason: str
    classifier_capability_version: str

    pue_decision_type: str
    pue_identification_level: str
    pue_product_form: str
    pue_comparability_status: str
    pue_abstention_reason: str | None
    pue_identified_family: str | None
    pue_identified_model: str | None
    pue_capability_version: str

    product_form_conclusions_agree: bool | None
    pue_abstained: bool
    classifier_complete_product_pue_blocked: bool
    identity_breadth: str

    category: ComparisonCategory


# --------------------------------------------------------------------------- #
# Product-form bucketing (spec: broad product-form conclusions, not exact
# ProductForm equality - the classifier has no notion of component vs
# accessory vs replacement part, only complete_product/accessory/part).
# --------------------------------------------------------------------------- #
_PUE_COMPLETE_BUCKET = {
    ProductForm.COMPLETE_PRODUCT,
    ProductForm.INCOMPLETE_PRODUCT,
    ProductForm.BUNDLE,
}
_PUE_NON_COMPLETE_BUCKET = {
    ProductForm.ACCESSORY,
    ProductForm.COMPONENT,
    ProductForm.REPLACEMENT_PART,
    ProductForm.COMPATIBLE_ITEM,
    ProductForm.PACKAGING_ONLY,
    ProductForm.SERVICE,
}
_CLASSIFIER_COMPLETE_BUCKET = {Classification.COMPLETE_PRODUCT}
_CLASSIFIER_NON_COMPLETE_BUCKET = {Classification.ACCESSORY, Classification.PART}
#: Both represent the classifier reaching *some* conclusion that this is not
#: a directly-relevant complete-product match; used only to detect
#: AGREEMENT when the PUE also declines (``OUTSIDE_SUPPORTED_DOMAIN``).
_CLASSIFIER_NON_MATCH_LABELS = {Classification.UNKNOWN, Classification.REJECTED}

_NOT_COMPARABLE_STATUSES = {
    ComparabilityStatus.NOT_COMPARABLE_PRODUCT_FORM,
    ComparabilityStatus.NOT_COMPARABLE_BUNDLE,
    ComparabilityStatus.NOT_COMPARABLE_CONDITION,
}

_SPECIFIC_IDENTIFICATION_LEVELS = {
    IdentificationLevel.FAMILY,
    IdentificationLevel.MODEL,
    IdentificationLevel.VARIANT,
    IdentificationLevel.EXACT_CATALOGUE_PRODUCT,
}
_COARSE_IDENTIFICATION_LEVELS = {
    IdentificationLevel.PRODUCT_TYPE,
    IdentificationLevel.BRAND_AND_PRODUCT_TYPE,
}

_DECLINING_DECISION_TYPES = {DecisionType.AMBIGUOUS, DecisionType.OUTSIDE_SUPPORTED_DOMAIN}


def _pue_bucket(form: ProductForm) -> str:
    if form in _PUE_COMPLETE_BUCKET:
        return "complete"
    if form in _PUE_NON_COMPLETE_BUCKET:
        return "non_complete"
    return "unknown"


def _classifier_bucket(label: Classification) -> str:
    if label in _CLASSIFIER_COMPLETE_BUCKET:
        return "complete"
    if label in _CLASSIFIER_NON_COMPLETE_BUCKET:
        return "non_complete"
    if label == Classification.REJECTED:
        # A genuine conclusion ("not a relevant match at all"), distinct
        # from UNKNOWN's "insufficient signal to conclude anything".
        return "rejected"
    return "unknown"  # Classification.UNKNOWN: no conclusion reached.


def _identity_breadth(record: ReasoningRecord) -> str:
    """Whether PUE's identification is more specific than, broader/less
    committal than, or equivalent in specificity to a title classifier's
    coarse verdict. See module docstring: descriptive only."""
    decision = record.decision
    level = decision.identification_level
    if level in _SPECIFIC_IDENTIFICATION_LEVELS:
        return "more_specific"
    if level in _COARSE_IDENTIFICATION_LEVELS:
        return "equivalent"
    # IdentificationLevel.UNKNOWN from here.
    if decision.decision_type in _DECLINING_DECISION_TYPES:
        # PUE deliberately declines to commit further than a classifier
        # label would - a broader (safer, less specific) conclusion.
        return "broader"
    return "not_applicable"


def _category(
    classification: ListingClassification,
    record: ReasoningRecord,
    *,
    product_form_conclusions_agree: bool | None,
    classifier_complete_product_pue_blocked: bool,
    identity_breadth: str,
) -> ComparisonCategory:
    decision = record.decision
    if decision.decision_type == DecisionType.PROCESSING_FAILED:
        # A technical failure carries no product-understanding signal to
        # compare against the classifier at all (spec 4.2/16.8).
        return ComparisonCategory.OTHER_DISAGREEMENT
    if classifier_complete_product_pue_blocked:
        return ComparisonCategory.PUE_BLOCKED_DIRECT_COMPARABILITY
    if decision.decision_type == DecisionType.ABSTAINED:
        return ComparisonCategory.PUE_ABSTAINED
    if decision.decision_type in _DECLINING_DECISION_TYPES:
        classifier_declined = classification.classification in _CLASSIFIER_NON_MATCH_LABELS
        pue_declined_domain = decision.decision_type == DecisionType.OUTSIDE_SUPPORTED_DOMAIN
        if classifier_declined and pue_declined_domain:
            return ComparisonCategory.AGREEMENT
        return ComparisonCategory.PUE_BROADER_IDENTITY
    if product_form_conclusions_agree is False:
        return ComparisonCategory.PRODUCT_FORM_DISAGREEMENT
    if product_form_conclusions_agree is None:
        return ComparisonCategory.OTHER_DISAGREEMENT
    if identity_breadth == "more_specific":
        return ComparisonCategory.PUE_MORE_SPECIFIC_IDENTITY
    return ComparisonCategory.AGREEMENT


def compare_classifier_and_pue(
    classification: ListingClassification,
    record: ReasoningRecord,
    *,
    classifier_capability_version: str = CLASSIFIER_CAPABILITY_VERSION,
) -> ClassifierPueComparison:
    """Pure comparison of an already-computed classifier verdict against an
    already-computed PUE :class:`ReasoningRecord` for the same listing.

    Never invokes the classifier or the PUE - both outputs must already
    exist. Never influences PUE Decision Formation (spec: independence).
    """
    decision = record.decision
    pue_bucket = _pue_bucket(decision.product_form)
    classifier_bucket = _classifier_bucket(classification.classification)
    product_form_conclusions_agree: bool | None
    if pue_bucket == "unknown" or classifier_bucket == "unknown":
        # Either side made no concrete product-form assertion at all -
        # nothing to agree or disagree with (not the same as REJECTED,
        # which is itself a conclusion).
        product_form_conclusions_agree = None
    else:
        product_form_conclusions_agree = classifier_bucket == pue_bucket

    classifier_complete_product_pue_blocked = (
        classification.classification == Classification.COMPLETE_PRODUCT
        and decision.comparability_status in _NOT_COMPARABLE_STATUSES
    )
    breadth = _identity_breadth(record)
    category = _category(
        classification,
        record,
        product_form_conclusions_agree=product_form_conclusions_agree,
        classifier_complete_product_pue_blocked=classifier_complete_product_pue_blocked,
        identity_breadth=breadth,
    )

    return ClassifierPueComparison(
        case_id=record.case_id,
        provider=record.observation.provider,
        provider_listing_id=record.observation.provider_listing_id,
        source_fingerprint=record.observation.source_fingerprint,
        classifier_label=classification.classification.value,
        classifier_score=classification.match_confidence,
        classifier_reason=classification.reason,
        classifier_capability_version=classifier_capability_version,
        pue_decision_type=decision.decision_type.value,
        pue_identification_level=decision.identification_level.value,
        pue_product_form=decision.product_form.value,
        pue_comparability_status=decision.comparability_status.value,
        pue_abstention_reason=(
            decision.abstention_reason.value if decision.abstention_reason else None
        ),
        pue_identified_family=decision.identified_family,
        pue_identified_model=decision.identified_model,
        pue_capability_version=decision.capability_version,
        product_form_conclusions_agree=product_form_conclusions_agree,
        pue_abstained=decision.decision_type == DecisionType.ABSTAINED,
        classifier_complete_product_pue_blocked=classifier_complete_product_pue_blocked,
        identity_breadth=breadth,
        category=category,
    )


def comparison_to_dict(c: ClassifierPueComparison) -> dict:
    """JSON-serialisable view of a :class:`ClassifierPueComparison`."""
    return {
        "case_id": c.case_id,
        "provider": c.provider,
        "provider_listing_id": c.provider_listing_id,
        "source_fingerprint": c.source_fingerprint,
        "classifier_label": c.classifier_label,
        "classifier_score": c.classifier_score,
        "classifier_reason": c.classifier_reason,
        "classifier_capability_version": c.classifier_capability_version,
        "pue_decision_type": c.pue_decision_type,
        "pue_identification_level": c.pue_identification_level,
        "pue_product_form": c.pue_product_form,
        "pue_comparability_status": c.pue_comparability_status,
        "pue_abstention_reason": c.pue_abstention_reason,
        "pue_identified_family": c.pue_identified_family,
        "pue_identified_model": c.pue_identified_model,
        "pue_capability_version": c.pue_capability_version,
        "product_form_conclusions_agree": c.product_form_conclusions_agree,
        "pue_abstained": c.pue_abstained,
        "classifier_complete_product_pue_blocked": c.classifier_complete_product_pue_blocked,
        "identity_breadth": c.identity_breadth,
        "category": c.category.value,
    }


def comparison_from_dict(d: dict) -> ClassifierPueComparison:
    return ClassifierPueComparison(
        case_id=d["case_id"],
        provider=d["provider"],
        provider_listing_id=d["provider_listing_id"],
        source_fingerprint=d["source_fingerprint"],
        classifier_label=d["classifier_label"],
        classifier_score=d["classifier_score"],
        classifier_reason=d["classifier_reason"],
        classifier_capability_version=d["classifier_capability_version"],
        pue_decision_type=d["pue_decision_type"],
        pue_identification_level=d["pue_identification_level"],
        pue_product_form=d["pue_product_form"],
        pue_comparability_status=d["pue_comparability_status"],
        pue_abstention_reason=d["pue_abstention_reason"],
        pue_identified_family=d["pue_identified_family"],
        pue_identified_model=d["pue_identified_model"],
        pue_capability_version=d["pue_capability_version"],
        product_form_conclusions_agree=d["product_form_conclusions_agree"],
        pue_abstained=d["pue_abstained"],
        classifier_complete_product_pue_blocked=d["classifier_complete_product_pue_blocked"],
        identity_breadth=d["identity_breadth"],
        category=ComparisonCategory(d["category"]),
    )


def comparison_to_json(c: ClassifierPueComparison) -> str:
    return json.dumps(comparison_to_dict(c), sort_keys=True)


def comparison_from_json(payload: str) -> ClassifierPueComparison:
    return comparison_from_dict(json.loads(payload))


# --------------------------------------------------------------------------- #
# Deterministic aggregate report
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ComparisonReport:
    """Deterministic counts over a set of comparison records.

    Counts are unlabelled observations, not correctness metrics (spec 22.4 /
    23.4: a single overall accuracy score is insufficient and no ground truth
    exists yet for these categories).
    """

    schema_version: str
    generated_at: str
    total_cases: int
    agreements: int
    product_form_disagreements: int
    pue_abstentions: int
    pue_blocked_direct_comparability: int
    pue_broader_identity: int
    pue_more_specific_identity: int
    other_disagreements: int


def _default_clock() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)


def build_comparison_report(
    comparisons: Sequence[ClassifierPueComparison],
    *,
    clock: Callable[[], datetime] = _default_clock,
) -> ComparisonReport:
    """Build a deterministic aggregate report over ``comparisons``."""
    counts = {category: 0 for category in ComparisonCategory}
    for c in comparisons:
        counts[c.category] += 1
    return ComparisonReport(
        schema_version=COMPARISON_SCHEMA_VERSION,
        generated_at=clock().isoformat(),
        total_cases=len(comparisons),
        agreements=counts[ComparisonCategory.AGREEMENT],
        product_form_disagreements=counts[ComparisonCategory.PRODUCT_FORM_DISAGREEMENT],
        pue_abstentions=counts[ComparisonCategory.PUE_ABSTAINED],
        pue_blocked_direct_comparability=counts[
            ComparisonCategory.PUE_BLOCKED_DIRECT_COMPARABILITY
        ],
        pue_broader_identity=counts[ComparisonCategory.PUE_BROADER_IDENTITY],
        pue_more_specific_identity=counts[ComparisonCategory.PUE_MORE_SPECIFIC_IDENTITY],
        other_disagreements=counts[ComparisonCategory.OTHER_DISAGREEMENT],
    )


def report_to_dict(report: ComparisonReport) -> dict:
    return {
        "schema_version": report.schema_version,
        "generated_at": report.generated_at,
        "total_cases": report.total_cases,
        "agreements": report.agreements,
        "product_form_disagreements": report.product_form_disagreements,
        "pue_abstentions": report.pue_abstentions,
        "pue_blocked_direct_comparability": report.pue_blocked_direct_comparability,
        "pue_broader_identity": report.pue_broader_identity,
        "pue_more_specific_identity": report.pue_more_specific_identity,
        "other_disagreements": report.other_disagreements,
    }


def render_report_json(report: ComparisonReport) -> str:
    return json.dumps(report_to_dict(report), sort_keys=True, indent=2)


def render_report_markdown(
    report: ComparisonReport, comparisons: Sequence[ClassifierPueComparison] = ()
) -> str:
    """Human-readable Markdown rendering: aggregate counts, then a per-case
    table of the same comparisons (empty table body if none given)."""
    lines = [
        "# Classifier/PUE Comparison Report",
        "",
        f"*Schema version: {report.schema_version} - generated {report.generated_at}*",
        "",
        "This report describes **observable differences only**. No category "
        "claims the classifier or the PUE is correct; that requires a "
        "labelled benchmark (Sprint 3).",
        "",
        "## Aggregate counts",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Total cases | {report.total_cases} |",
        f"| Agreements | {report.agreements} |",
        f"| Product-form disagreements | {report.product_form_disagreements} |",
        f"| PUE abstentions | {report.pue_abstentions} |",
        f"| PUE blocked direct comparability | {report.pue_blocked_direct_comparability} |",
        f"| PUE broader identity | {report.pue_broader_identity} |",
        f"| PUE more specific identity | {report.pue_more_specific_identity} |",
        f"| Other disagreements | {report.other_disagreements} |",
    ]
    if comparisons:
        lines += [
            "",
            "## Per-case comparisons",
            "",
            "| Case ID | Provider | Classifier | PUE Decision | PUE Form | Category |",
            "|---|---|---|---|---|---|",
        ]
        for c in comparisons:
            lines.append(
                f"| {c.case_id} | {c.provider} | "
                f"{c.classifier_label} ({c.classifier_score}) | "
                f"{c.pue_decision_type} | {c.pue_product_form} | {c.category.value} |"
            )
    lines.append("")
    return "\n".join(lines)
