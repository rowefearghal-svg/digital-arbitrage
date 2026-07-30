"""The versioned Decision Policy (spec section 16).

Thresholds live here, not scattered through :mod:`decisions`, so a policy
change is a single, versioned, reviewable diff.
"""

from __future__ import annotations

from dataclasses import dataclass

from .version import POLICY_VERSION


@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    """Tunable thresholds for :func:`digital_arbitrage.pue.decisions.form_decision`."""

    policy_version: str = POLICY_VERSION
    #: Minimum identity_fit for an EXACT identification when no MPN/GTIN
    #: agreement is present (i.e. all decision-critical fields agree).
    exact_identity_fit_threshold: float = 0.95
    #: Minimum retrieval-score gap (0-100) required between the leading and
    #: second-best surviving Candidate for the leading one to be considered
    #: materially better (otherwise: indistinguishable / ambiguous).
    material_lead_gap: float = 8.0
    #: Minimum evidence coverage required to justify EXACT identification.
    exact_evidence_coverage_threshold: float = 0.66
    #: Minimum evidence coverage required for CLASSIFIED / PARTIAL outcomes.
    minimum_usable_evidence_coverage: float = 0.2
