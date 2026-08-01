"""Deterministic replay of a persisted case (Sprint 3, brief section 10).

This codebase keeps exactly **one** active capability/policy/knowledge/
schema version in the running process at a time (see ``pue/version.py`` and
``pue/policies.py``) - there is no multi-version catalogue/policy registry
to load an arbitrary historical version from. Replay is therefore honest
about what it can actually do:

* **Default replay** (no explicit version override) always runs the
  persisted Observation through the *current* running code's versions -
  never a copy frozen at the original record's versions, because none is
  kept. If those versions happen to equal the original record's versions,
  this is a genuine identical-version replay and the two Decisions are
  compared for full semantic equivalence. If the current versions have
  since moved on, this is reported as a **version-changed comparison**
  instead of an identical replay (brief: "changed policy or catalogue
  version is reported as a comparison, not identical replay") - the
  Decision is allowed to differ, and the report says so plainly, but the
  replay never silently pretends the versions matched.
* **Explicit version override** (``expected_*_version`` parameters) lets a
  caller assert which exact versions it expects to replay under. If any
  requested version does not equal what is actually loadable right now,
  replay fails clearly with :class:`PueValidationError` rather than
  silently falling back to the current/newest version (brief: "replay does
  not silently fall back to the newest catalogue or policy").
"""

from __future__ import annotations

from dataclasses import dataclass

from ..normalization.models import NormalizedListing
from ..product_scanner.models import Condition, Listing
from .catalogue import CandidateRepository, JsonCandidateRepository
from .enums import DecisionType
from .models import Decision, ProcessingContext, ReasoningRecord
from .orchestration import build_default_context, process_one
from .persistence import PueCaseStore
from .policies import DecisionPolicy
from .validation import PueValidationError


@dataclass(frozen=True, slots=True)
class DecisionSignature:
    """The material meaning of a Decision (brief section 10), deliberately
    excluding volatile identity fields (``decision_id``, ``case_id``,
    ``observation_id``, candidate-instance UUIDs, timestamps, durations)."""

    decision_type: str
    identification_level: str
    product_form: str
    product_type: str | None
    identified_brand: str | None
    identified_family: str | None
    identified_model: str | None
    identified_variant: str | None
    selected_catalogue_product_id: str | None
    comparability_status: str
    unresolved_fields: tuple[str, ...]
    contradiction_codes: tuple[str, ...]
    abstention_reason: str | None
    review_recommended: bool

    def to_dict(self) -> dict:
        return {
            "decision_type": self.decision_type,
            "identification_level": self.identification_level,
            "product_form": self.product_form,
            "product_type": self.product_type,
            "identified_brand": self.identified_brand,
            "identified_family": self.identified_family,
            "identified_model": self.identified_model,
            "identified_variant": self.identified_variant,
            "selected_catalogue_product_id": self.selected_catalogue_product_id,
            "comparability_status": self.comparability_status,
            "unresolved_fields": list(self.unresolved_fields),
            "contradiction_codes": list(self.contradiction_codes),
            "abstention_reason": self.abstention_reason,
            "review_recommended": self.review_recommended,
        }


def decision_signature(record: ReasoningRecord) -> DecisionSignature:
    """Extract the semantic-equivalence signature of ``record``'s Decision."""
    decision: Decision = record.decision
    selected_product_id: str | None = None
    if decision.selected_candidate_instance_id is not None:
        selected = next(
            (
                c
                for c in record.candidates
                if c.candidate_instance_id == decision.selected_candidate_instance_id
            ),
            None,
        )
        selected_product_id = selected.catalogue_product_id if selected else None
    return DecisionSignature(
        decision_type=decision.decision_type.value,
        identification_level=decision.identification_level.value,
        product_form=decision.product_form.value,
        product_type=decision.product_type,
        identified_brand=decision.identified_brand,
        identified_family=decision.identified_family,
        identified_model=decision.identified_model,
        identified_variant=decision.identified_variant,
        selected_catalogue_product_id=selected_product_id,
        comparability_status=decision.comparability_status.value,
        unresolved_fields=tuple(sorted(decision.unresolved_fields)),
        contradiction_codes=tuple(sorted(decision.contradiction_codes)),
        abstention_reason=decision.abstention_reason.value if decision.abstention_reason else None,
        review_recommended=decision.review_recommended,
    )


@dataclass(frozen=True, slots=True)
class ReplayComparison:
    """The outcome of comparing an original persisted Decision against a
    freshly re-executed one for the same Observation."""

    case_id: str
    version_match: bool
    """True when the replay ran under exactly the same capability/policy/
    knowledge/schema versions as the original record."""
    original_versions: dict
    replay_versions: dict
    equivalent: bool
    """Only meaningful (and only asserted as a release-gate requirement)
    when ``version_match`` is True - see module docstring."""
    original_signature: DecisionSignature
    replay_signature: DecisionSignature
    differences: tuple[str, ...]
    original_record: ReasoningRecord
    replay_record: ReasoningRecord

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "version_match": self.version_match,
            "original_versions": self.original_versions,
            "replay_versions": self.replay_versions,
            "equivalent": self.equivalent,
            "original_signature": self.original_signature.to_dict(),
            "replay_signature": self.replay_signature.to_dict(),
            "differences": list(self.differences),
        }


def _signature_differences(a: DecisionSignature, b: DecisionSignature) -> tuple[str, ...]:
    diffs = []
    for field_name in a.__dataclass_fields__:
        if getattr(a, field_name) != getattr(b, field_name):
            diffs.append(field_name)
    return tuple(diffs)


def _observation_to_listing(record: ReasoningRecord) -> NormalizedListing:
    observation = record.observation
    listing = Listing(
        listing_id=observation.provider_listing_id,
        title=observation.raw_title,
        provider=observation.provider,
        url="https://example.test/replay",
        condition=Condition.USED,
        extra={str(k): str(v) for k, v in observation.raw_attributes.items()},
    )
    normalized = NormalizedListing.from_listing(listing)
    normalized.title_tokens = tuple(observation.normalized_title.lower().split())
    return normalized


def replay_case(
    case_id: str,
    *,
    database_path: str,
    repository: CandidateRepository | None = None,
    policy: DecisionPolicy | None = None,
    context: ProcessingContext | None = None,
    expected_capability_version: str | None = None,
    expected_policy_version: str | None = None,
    expected_knowledge_version: str | None = None,
    expected_schema_version: str | None = None,
) -> ReplayComparison:
    """Replay ``case_id`` from ``database_path`` and compare it against the
    freshly re-executed Decision (brief section 10).

    Never mutates the persisted historical record (only reads it); the
    replay result is a separate, in-memory comparison artefact - nothing is
    written back to ``database_path``.

    Raises :class:`PueValidationError` if ``case_id`` is not found, or if
    any ``expected_*_version`` is given and does not equal what the current
    runtime would actually replay under (this codebase has no registry of
    historical policy/catalogue versions to load on demand - see module
    docstring).
    """
    with PueCaseStore(database_path) as store:
        original = store.get_case(case_id)
    if original is None:
        raise PueValidationError(
            f"case_id {case_id!r} was not found in {database_path!r}; cannot replay a case "
            "that was never persisted"
        )

    repo = repository or JsonCandidateRepository()
    active_policy = policy or DecisionPolicy()
    ctx = context or build_default_context()

    original_versions = {
        "capability_version": original.decision.capability_version,
        "policy_version": original.decision.policy_version,
        "knowledge_version": original.decision.knowledge_version,
        "schema_version": original.schema_version,
    }
    replay_versions = {
        "capability_version": ctx.capability_version,
        "policy_version": active_policy.policy_version,
        "knowledge_version": ctx.knowledge_version,
        "schema_version": ctx.schema_version,
    }

    for label, expected in (
        ("capability_version", expected_capability_version),
        ("policy_version", expected_policy_version),
        ("knowledge_version", expected_knowledge_version),
        ("schema_version", expected_schema_version),
    ):
        if expected is not None and replay_versions[label] != expected:
            raise PueValidationError(
                f"requested {label} {expected!r} is not available for replay; the running "
                f"system can currently only replay under {label}={replay_versions[label]!r} "
                "(this codebase keeps no historical version registry - see "
                "digital_arbitrage.pue.replay module docstring). Replay does not silently "
                "fall back to the current/newest version for a version you explicitly "
                "requested; it fails clearly instead."
            )

    version_match = original_versions == replay_versions

    listing = _observation_to_listing(original)
    replay_record = process_one(listing, ctx, repository=repo, policy=active_policy)

    original_sig = decision_signature(original)
    replay_sig = decision_signature(replay_record)
    differences = _signature_differences(original_sig, replay_sig)

    # A technical replay failure (PROCESSING_FAILED) must never be
    # conflated with a legitimate product ABSTAINED outcome (brief: keep
    # them distinct) - surfaced here as an explicit, named difference
    # rather than folded into "equivalent=False" ambiguity.
    if replay_record.decision.decision_type == DecisionType.PROCESSING_FAILED and (
        original.decision.decision_type != DecisionType.PROCESSING_FAILED
    ):
        if "decision_type" not in differences:
            differences = (*differences, "decision_type")

    equivalent = version_match and not differences

    return ReplayComparison(
        case_id=case_id,
        version_match=version_match,
        original_versions=original_versions,
        replay_versions=replay_versions,
        equivalent=equivalent,
        original_signature=original_sig,
        replay_signature=replay_sig,
        differences=differences,
        original_record=original,
        replay_record=replay_record,
    )
