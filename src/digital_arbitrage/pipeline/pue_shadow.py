"""Configuration-gated PUE shadow execution (spec section 5.3).

Runs the Product Understanding Engine alongside the existing pipeline
without affecting it: the existing classifier, product matching,
deduplication, market pricing and commercial scoring continue producing
their current output unchanged; the PUE result is computed and persisted
separately. It is not authoritative and a PUE exception must never
terminate the current pipeline run.

Disabled by default (``ShadowConfig.enabled = False``): a fresh pipeline run
with no explicit configuration is a complete no-op for this module.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..pue.comparison import ClassifierPueComparison, compare_classifier_and_pue
from ..pue.enums import DecisionType
from ..pue.orchestration import build_default_context, process_many, publish_result
from ..pue.persistence import PueCaseStore
from ..pue.policies import DecisionPolicy
from ..pue.validation import PueValidationError

if TYPE_CHECKING:
    from ..classification.models import SearchProfile
    from ..normalization.models import NormalizedListing
    from ..pue.models import ProcessingContext, ProductUnderstandingResult, ReasoningRecord

logger = logging.getLogger(__name__)

#: Default location for shadow-mode PUE persistence, mirroring the existing
#: scan-history convention (see digital_arbitrage.pipeline.cli.DEFAULT_DB_PATH).
DEFAULT_SHADOW_DB_PATH = Path.home() / ".digital_arbitrage" / "pue_shadow.db"


@dataclass(slots=True, frozen=True)
class ShadowConfig:
    """Shadow-mode configuration. Disabled unless explicitly turned on."""

    enabled: bool = False
    db_path: str | Path | None = DEFAULT_SHADOW_DB_PATH
    policy: DecisionPolicy | None = None
    #: Explicitly marks this run as replay/evaluation activity (e.g.
    #: benchmarking a new policy against historical listings) rather than
    #: normal shadow processing. Normal processing must not accumulate
    #: duplicate completed records for the same listing under the same
    #: capability/policy/knowledge versions; replay activity may retain
    #: another record (see PueCaseStore.save_case).
    replay: bool = False


@dataclass(slots=True, frozen=True)
class PueShadowCaseResult:
    """Everything one listing's shadow run exposes (Sprint 2, Task 2).

    ``comparison`` is ``None`` when no classifier verdict was available for
    this listing before shadow execution ran (classification is never
    performed here - see module docstring / ``run_pue_shadow``), or when the
    case ended in ``PROCESSING_FAILED`` (no product-understanding signal to
    compare against the classifier).
    """

    reasoning_record: ReasoningRecord
    result: ProductUnderstandingResult
    comparison: ClassifierPueComparison | None


def run_pue_shadow(
    listings: Sequence[NormalizedListing],
    *,
    config: ShadowConfig,
    search_profile: SearchProfile | None = None,
) -> tuple[PueShadowCaseResult, ...]:
    """Run the PUE over ``listings`` in shadow mode; never raises.

    Returns an empty tuple when disabled, when there is nothing to process,
    or when the PUE itself fails - a PUE exception must never propagate into
    the calling pipeline (spec 5.3 / risk control).

    Uses each listing's already-computed ``NormalizedListing.classification``
    (set by the pipeline's classification stage before shadow mode runs) to
    build a classifier/PUE comparison record; the classifier itself is never
    invoked here, so classifier output can never influence PUE Decision
    Formation (spec: independence between the two systems). ``search_profile``
    is the :class:`~digital_arbitrage.classification.models.SearchProfile`
    that produced those classifications - required to build a comparison
    (Sprint 2 pre-merge correction: a classifier verdict is meaningless
    without knowing what it was matched against). When ``None``, no
    comparison is built for any listing (``comparison`` stays ``None`` on
    every result), matching the existing "no classification available"
    behaviour.
    """
    if not config.enabled or not listings:
        return ()

    try:
        context = build_default_context()
        records = process_many(listings, context, policy=config.policy)

        case_results = []
        for listing, record in zip(listings, records, strict=True):
            result = publish_result(record)
            comparison = None
            classification = getattr(listing, "classification", None)
            if (
                classification is not None
                and search_profile is not None
                and record.decision.decision_type != DecisionType.PROCESSING_FAILED
            ):
                comparison = compare_classifier_and_pue(
                    classification,
                    record,
                    search_profile=search_profile,
                    id_factory=context.id_factory,
                )
            case_results.append(
                PueShadowCaseResult(reasoning_record=record, result=result, comparison=comparison)
            )

        if config.db_path is not None:
            with PueCaseStore(config.db_path) as store:
                for case_result in case_results:
                    _persist_case_result(store, case_result, context, config)

        return tuple(case_results)
    except Exception:  # noqa: BLE001 - deliberate: shadow mode must never crash the pipeline
        logger.exception("PUE shadow execution failed; continuing without shadow output")
        return ()


def _persist_case_result(
    store: PueCaseStore,
    case_result: PueShadowCaseResult,
    context: ProcessingContext,
    config: ShadowConfig,
) -> None:
    """Persist one case + its optional comparison, transactionally when
    both are new; backfill the comparison onto an existing equivalent case
    when the case row already exists but has no comparison yet (Sprint 2
    pre-merge correction item 2 - a duplicate/equivalent ``save_case`` must
    not silently prevent an older case from ever receiving a comparison).
    """
    record = case_result.reasoning_record
    comparison = case_result.comparison
    try:
        store.save_case_with_comparison(record, comparison, replay=config.replay)
        return
    except PueValidationError:
        # Either this exact case_id was already persisted, or (normal,
        # non-replay processing only) an equivalent completed record
        # already exists for this listing's source_fingerprint under the
        # same capability/policy/knowledge versions. Both are expected,
        # idempotent outcomes, not a pipeline failure - fall through to
        # the backfill attempt below.
        pass

    if config.replay or comparison is None:
        return

    decision = record.decision
    target_case_id: str | None = None
    if store.get_case(record.case_id) is not None:
        target_case_id = record.case_id
    else:
        equivalent = store.find_equivalent(
            source_fingerprint=record.observation.source_fingerprint,
            capability_version=decision.capability_version,
            policy_version=decision.policy_version,
            knowledge_version=decision.knowledge_version,
        )
        if equivalent is not None:
            target_case_id = equivalent.case_id
    if target_case_id is None:
        return
    if store.get_comparisons_for_case(target_case_id):
        # Already has at least one comparison; nothing to backfill.
        return
    backfilled = dataclasses.replace(
        comparison,
        case_id=target_case_id,
        comparison_id=context.id_factory(),
    )
    try:
        store.save_comparison(backfilled, replay=config.replay)
    except PueValidationError:
        pass
