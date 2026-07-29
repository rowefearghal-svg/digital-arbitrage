"""Product Understanding Engine (PUE) v0.1 - Sprint 1 vertical slice.

Deterministic, local, title-first, single-process, GPU-domain reasoning
chain: ``NormalizedListing -> Observation -> Evidence -> Claim ->
ProductHypothesis -> Candidate Retrieval -> Candidate Evaluation -> Decision
-> Explanation -> ReasoningRecord``.

See ``docs/architecture/PUE_v0.1_VERTICAL_SLICE_SPECIFICATION.md`` for the
implementation authority and ``docs/decisions/`` for the Sprint 1 ADRs.

This package runs in shadow mode: it does not affect existing classification,
product matching, deduplication or commercial scoring (see
:mod:`digital_arbitrage.pipeline.pue_shadow`).
"""

from __future__ import annotations

from .orchestration import build_default_context, process_many, process_one, publish_result
from .version import (
    CAPABILITY_VERSION,
    KNOWLEDGE_VERSION,
    POLICY_VERSION,
    SCHEMA_VERSION,
    TERM_VERSION,
)

__all__ = [
    "CAPABILITY_VERSION",
    "KNOWLEDGE_VERSION",
    "POLICY_VERSION",
    "SCHEMA_VERSION",
    "TERM_VERSION",
    "build_default_context",
    "process_many",
    "process_one",
    "publish_result",
]
