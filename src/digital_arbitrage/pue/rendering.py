"""Human-readable debug rendering (spec section 25). Developer tool only."""

from __future__ import annotations

from .models import ReasoningRecord


def render_trace(record: ReasoningRecord) -> str:
    """A concise, one-block-per-run trace (spec 25.1)."""
    decision = record.decision
    hard_rejected = sum(1 for e in record.candidate_evaluations if e.hard_rejected)
    leading = None
    if record.candidates:
        leading = max(record.candidates, key=lambda c: c.retrieval_score)
    lines = [
        "Case admitted" if record.observation.normalized_title else "Case admitted (empty title)",
        f"Evidence extracted: {len(record.evidence)}",
        f"Claims supported: {sum(1 for c in record.claims if c.status.value == 'supported')}",
        f"Active hypotheses: {len(record.hypotheses)}",
        f"Candidates retrieved: {len(record.candidates)}",
        f"Candidates hard rejected: {hard_rejected}",
        f"Leading Candidate: {leading.catalogue_product_id if leading else 'none'}",
        f"Decision: {decision.decision_type.value.upper()} / {decision.identification_level.value}",
        f"Comparability: {decision.comparability_status.value}",
        f"Duration: {record.operational_metrics.get('total_ms', 'n/a')} ms",
    ]
    return "\n".join(lines)


def render_full(record: ReasoningRecord) -> str:
    """Full developer rendering of Observation -> Explanation (spec 25.2)."""
    parts: list[str] = []
    o = record.observation
    parts.append(f"=== Observation {o.observation_id} ===")
    parts.append(f"raw_title: {o.raw_title!r}")
    parts.append(f"normalized_title: {o.normalized_title!r}")
    parts.append(f"provider: {o.provider} / {o.provider_listing_id}")

    parts.append(f"\n=== Evidence ({len(record.evidence)}) ===")
    for e in record.evidence:
        parts.append(
            f"  [{e.evidence_type.value}] raw={e.raw_value!r} -> {e.normalized_value!r} "
            f"(field={e.source_field}, span={e.source_start}-{e.source_end})"
        )

    parts.append(f"\n=== Claims ({len(record.claims)}) ===")
    for c in record.claims:
        parts.append(
            f"  [{c.status.value}] {c.predicate.value} = {c.value!r} ({c.support_level.value})"
        )

    parts.append(f"\n=== Hypotheses ({len(record.hypotheses)}) ===")
    for h in record.hypotheses:
        parts.append(
            f"  [{h.status.value}] form={h.product_form.value} type={h.product_type} "
            f"family={h.family} brand={h.brand} compat={h.compatibility_target} "
            f"coherence={h.coherence} coverage={h.evidence_coverage}"
        )

    parts.append(f"\n=== Candidates ({len(record.candidates)}) ===")
    for cand in record.candidates:
        parts.append(
            f"  {cand.catalogue_product_id} via {cand.retrieval_method.value} "
            f"rank={cand.retrieval_rank} score={cand.retrieval_score}"
        )

    parts.append(f"\n=== Candidate Evaluations ({len(record.candidate_evaluations)}) ===")
    for ev in record.candidate_evaluations:
        parts.append(
            f"  {ev.candidate_instance_id}: outcome={ev.evaluation_outcome.value} "
            f"hard_rejected={ev.hard_rejected} identity_fit={ev.identity_fit} "
            f"agreements={len(ev.agreements)} contradictions={len(ev.contradictions)} "
            f"missing={len(ev.missing_information)}"
        )

    d = record.decision
    parts.append("\n=== Decision ===")
    parts.append(
        f"  {d.decision_type.value} / {d.identification_level.value} "
        f"form={d.product_form.value} brand={d.identified_brand} family={d.identified_family} "
        f"comparability={d.comparability_status.value} abstention={d.abstention_reason}"
    )

    parts.append("\n=== Explanation ===")
    parts.append(f"  {record.explanation.summary}")
    for p in record.explanation.supporting_points:
        parts.append(f"  + {p}")
    for p in record.explanation.contradictory_points:
        parts.append(f"  - {p}")
    for p in record.explanation.unresolved_points:
        parts.append(f"  ? {p}")

    return "\n".join(parts)
