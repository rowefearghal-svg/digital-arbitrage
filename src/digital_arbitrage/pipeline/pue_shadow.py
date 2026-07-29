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

from ..pue.orchestration import build_default_context, process_many
from ..pue.persistence import PueCaseStore
from ..pue.policies import DecisionPolicy
from ..pue.validation import PueValidationError

if TYPE_CHECKING:
    from ..normalization.models import NormalizedListing
    from ..pue.models import ReasoningRecord

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


def run_pue_shadow(
    listings: Sequence[NormalizedListing], *, config: ShadowConfig
) -> tuple[ReasoningRecord, ...]:
    """Run the PUE over ``listings`` in shadow mode; never raises.

    Returns an empty tuple when disabled, when there is nothing to process,
    or when the PUE itself fails - a PUE exception must never propagate into
    the calling pipeline (spec 5.3 / risk control).
    """
    if not config.enabled or not listings:
        return ()

    try:
        context = build_default_context()
        records = process_many(listings, context)

        if config.db_path is not None:
            with PueCaseStore(config.db_path) as store:
                for record in records:
                    try:
                        store.save_case(record)
                    except PueValidationError:
                        # Already persisted for this exact case_id (e.g. a
                        # replay); this is expected idempotent behavior, not
                        # a pipeline failure.
                        continue

        return records
    except Exception:  # noqa: BLE001 - deliberate: shadow mode must never crash the pipeline
        logger.exception("PUE shadow execution failed; continuing without shadow output")
        return ()
