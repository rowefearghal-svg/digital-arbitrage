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
    from ..normalization.models import NormalizedListing
    from ..pue.models import ProductUnderstandingResult, ReasoningRecord

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
    listings: Sequence[NormalizedListing], *, config: ShadowConfig
) -> tuple[PueShadowCaseResult, ...]:
    """Run the PUE over ``listings`` in shadow mode; never raises.

    Returns an empty tuple when disabled, when there is nothing to process,
    or when the PUE itself fails - a PUE exception must never propagate into
    the calling pipeline (spec 5.3 / risk control).

    Uses each listing's already-computed ``NormalizedListing.classification``
    (set by the pipeline's classification stage before shadow mode runs) to
    build a classifier/PUE comparison record; the classifier itself is never
    invoked here, so classifier output can never influence PUE Decision
    Formation (spec: independence between the two systems).
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
            if classification is not None and record.decision.decision_type != (
                DecisionType.PROCESSING_FAILED
            ):
                comparison = compare_classifier_and_pue(classification, record)
            case_results.append(
                PueShadowCaseResult(reasoning_record=record, result=result, comparison=comparison)
            )

        if config.db_path is not None:
            with PueCaseStore(config.db_path) as store:
                for case_result in case_results:
                    try:
                        store.save_case(case_result.reasoning_record, replay=config.replay)
                    except PueValidationError:
                        # Either this exact case_id was already persisted, or
                        # (normal, non-replay processing only) an equivalent
                        # completed record already exists for this listing's
                        # source_fingerprint under the same capability/
                        # policy/knowledge versions. Both are expected,
                        # idempotent outcomes, not a pipeline failure.
                        continue
                    if case_result.comparison is not None:
                        try:
                            store.save_comparison(case_result.comparison, replay=config.replay)
                        except PueValidationError:
                            # Same idempotency reasoning as above, applied to
                            # the comparison record.
                            pass

        return tuple(case_results)
    except Exception:  # noqa: BLE001 - deliberate: shadow mode must never crash the pipeline
        logger.exception("PUE shadow execution failed; continuing without shadow output")
        return ()
