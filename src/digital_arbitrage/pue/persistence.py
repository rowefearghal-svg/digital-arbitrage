"""SQLite persistence for PUE Reasoning Records (spec section 19).

Follows the existing repository convention (see
:mod:`digital_arbitrage.persistence.storage`): plain :mod:`sqlite3`, no ORM,
a small summary table plus a complete JSON payload. Complete records persist
and deserialize; historical records are never overwritten (spec 7.4/19.4).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from .comparison import ClassifierPueComparison, comparison_from_json, comparison_to_json
from .enums import (
    AbstentionReason,
    CalibrationStatus,
    CandidateOutcome,
    ClaimPredicate,
    ClaimStatus,
    ComparabilityStatus,
    ComparisonResult,
    ContradictionSeverity,
    DecisionType,
    EvidencePolarity,
    EvidenceType,
    ExplanationProfile,
    HypothesisStatus,
    IdentificationLevel,
    ProductForm,
    RetrievalMethod,
    SupportLevel,
    UncertaintyBand,
)
from .models import (
    Candidate,
    CandidateEvaluation,
    Claim,
    ComparisonFinding,
    Decision,
    DecisionUncertainty,
    Evidence,
    Explanation,
    Observation,
    ProductHypothesis,
    ReasoningRecord,
)
from .validation import PueValidationError, thaw_value

#: Current on-disk schema version for this table (bumped when the DDL changes).
#: Bumped to 2 in Sprint 2: added ``pue_classifier_comparisons`` (same
#: database file, no new database - spec: comparison records persist
#: alongside Reasoning Records).
SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pue_cases (
    case_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_listing_id TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    capability_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    knowledge_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    identification_level TEXT NOT NULL,
    product_form TEXT NOT NULL,
    selected_catalogue_product_id TEXT,
    comparability_status TEXT NOT NULL,
    reasoning_record_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pue_cases_listing
ON pue_cases(provider, provider_listing_id);

CREATE INDEX IF NOT EXISTS idx_pue_cases_fingerprint
ON pue_cases(source_fingerprint);

CREATE INDEX IF NOT EXISTS idx_pue_cases_versions
ON pue_cases(capability_version, policy_version, knowledge_version);

CREATE TABLE IF NOT EXISTS pue_classifier_comparisons (
    case_id TEXT PRIMARY KEY REFERENCES pue_cases(case_id),
    provider TEXT NOT NULL,
    provider_listing_id TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    classifier_capability_version TEXT NOT NULL,
    pue_capability_version TEXT NOT NULL,
    category TEXT NOT NULL,
    comparison_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pue_comparisons_listing
ON pue_classifier_comparisons(provider, provider_listing_id);

CREATE INDEX IF NOT EXISTS idx_pue_comparisons_fingerprint
ON pue_classifier_comparisons(source_fingerprint);

CREATE INDEX IF NOT EXISTS idx_pue_comparisons_versions
ON pue_classifier_comparisons(classifier_capability_version, pue_capability_version);
"""


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------- #
# Serialization (dataclass -> plain JSON-able dict, and back)
# --------------------------------------------------------------------------- #
def _dt(value: datetime) -> str:
    return value.isoformat()


def evidence_to_dict(e: Evidence) -> dict:
    return {
        "evidence_id": e.evidence_id,
        "observation_id": e.observation_id,
        "evidence_type": e.evidence_type.value,
        "raw_value": e.raw_value,
        "normalized_value": e.normalized_value,
        "source_field": e.source_field,
        "source_start": e.source_start,
        "source_end": e.source_end,
        "extraction_method": e.extraction_method,
        "extraction_confidence": e.extraction_confidence,
        "polarity_hint": e.polarity_hint.value if e.polarity_hint else None,
        "capability_version": e.capability_version,
    }


def evidence_from_dict(d: dict) -> Evidence:
    return Evidence(
        evidence_id=d["evidence_id"],
        observation_id=d["observation_id"],
        evidence_type=EvidenceType(d["evidence_type"]),
        raw_value=d["raw_value"],
        normalized_value=d["normalized_value"],
        source_field=d["source_field"],
        source_start=d["source_start"],
        source_end=d["source_end"],
        extraction_method=d["extraction_method"],
        extraction_confidence=d["extraction_confidence"],
        polarity_hint=EvidencePolarity(d["polarity_hint"]) if d["polarity_hint"] else None,
        capability_version=d["capability_version"],
    )


def claim_to_dict(c: Claim) -> dict:
    return {
        "claim_id": c.claim_id,
        "observation_id": c.observation_id,
        "predicate": c.predicate.value,
        "value": c.value,
        "status": c.status.value,
        "supporting_evidence_ids": list(c.supporting_evidence_ids),
        "contradicting_evidence_ids": list(c.contradicting_evidence_ids),
        "qualifying_evidence_ids": list(c.qualifying_evidence_ids),
        "support_level": c.support_level.value,
        "created_by": c.created_by,
        "capability_version": c.capability_version,
    }


def claim_from_dict(d: dict) -> Claim:
    return Claim(
        claim_id=d["claim_id"],
        observation_id=d["observation_id"],
        predicate=ClaimPredicate(d["predicate"]),
        value=d["value"],
        status=ClaimStatus(d["status"]),
        supporting_evidence_ids=tuple(d["supporting_evidence_ids"]),
        contradicting_evidence_ids=tuple(d["contradicting_evidence_ids"]),
        qualifying_evidence_ids=tuple(d["qualifying_evidence_ids"]),
        support_level=SupportLevel(d["support_level"]),
        created_by=d["created_by"],
        capability_version=d["capability_version"],
    )


def hypothesis_to_dict(h: ProductHypothesis) -> dict:
    return {
        "hypothesis_id": h.hypothesis_id,
        "observation_id": h.observation_id,
        "claim_ids": list(h.claim_ids),
        "product_form": h.product_form.value,
        "product_type": h.product_type,
        "brand": h.brand,
        "family": h.family,
        "model": h.model,
        "variant": h.variant,
        "compatibility_target": h.compatibility_target,
        "coherence": h.coherence,
        "evidence_coverage": h.evidence_coverage,
        "status": h.status.value,
        "unresolved_fields": list(h.unresolved_fields),
    }


def hypothesis_from_dict(d: dict) -> ProductHypothesis:
    return ProductHypothesis(
        hypothesis_id=d["hypothesis_id"],
        observation_id=d["observation_id"],
        claim_ids=tuple(d["claim_ids"]),
        product_form=ProductForm(d["product_form"]),
        product_type=d["product_type"],
        brand=d["brand"],
        family=d["family"],
        model=d["model"],
        variant=d["variant"],
        compatibility_target=d["compatibility_target"],
        coherence=d["coherence"],
        evidence_coverage=d["evidence_coverage"],
        status=HypothesisStatus(d["status"]),
        unresolved_fields=tuple(d["unresolved_fields"]),
    )


def candidate_to_dict(c: Candidate) -> dict:
    return {
        "candidate_instance_id": c.candidate_instance_id,
        "catalogue_product_id": c.catalogue_product_id,
        "hypothesis_id": c.hypothesis_id,
        "retrieval_method": c.retrieval_method.value,
        "retrieval_rank": c.retrieval_rank,
        "retrieval_score": c.retrieval_score,
        "matched_fields": list(c.matched_fields),
        "knowledge_version": c.knowledge_version,
    }


def candidate_from_dict(d: dict) -> Candidate:
    return Candidate(
        candidate_instance_id=d["candidate_instance_id"],
        catalogue_product_id=d["catalogue_product_id"],
        hypothesis_id=d["hypothesis_id"],
        retrieval_method=RetrievalMethod(d["retrieval_method"]),
        retrieval_rank=d["retrieval_rank"],
        retrieval_score=d["retrieval_score"],
        matched_fields=tuple(d["matched_fields"]),
        knowledge_version=d["knowledge_version"],
    )


def finding_to_dict(f: ComparisonFinding) -> dict:
    return {
        "field": f.field,
        # observed_value/candidate_value are ``object``-typed and may hold a
        # frozen tuple (e.g. a Candidate's MPN list); thaw to JSON-native
        # lists so this dict is byte-for-byte comparable to one produced by
        # a real JSON round trip (spec: standard JSON serialization).
        "observed_value": thaw_value(f.observed_value),
        "candidate_value": thaw_value(f.candidate_value),
        "result": f.result.value,
        "severity": f.severity.value if f.severity else None,
        "evidence_ids": list(f.evidence_ids),
        "explanation": f.explanation,
    }


def finding_from_dict(d: dict) -> ComparisonFinding:
    return ComparisonFinding(
        field=d["field"],
        observed_value=d["observed_value"],
        candidate_value=d["candidate_value"],
        result=ComparisonResult(d["result"]),
        severity=ContradictionSeverity(d["severity"]) if d["severity"] else None,
        evidence_ids=tuple(d["evidence_ids"]),
        explanation=d["explanation"],
    )


def evaluation_to_dict(ev: CandidateEvaluation) -> dict:
    return {
        "candidate_evaluation_id": ev.candidate_evaluation_id,
        "candidate_instance_id": ev.candidate_instance_id,
        "hypothesis_id": ev.hypothesis_id,
        "agreements": [finding_to_dict(f) for f in ev.agreements],
        "contradictions": [finding_to_dict(f) for f in ev.contradictions],
        "missing_information": [finding_to_dict(f) for f in ev.missing_information],
        "identity_fit": ev.identity_fit,
        "product_form_fit": ev.product_form_fit,
        "attribute_fit": ev.attribute_fit,
        "evidence_coverage": ev.evidence_coverage,
        "hard_rejected": ev.hard_rejected,
        "evaluation_outcome": ev.evaluation_outcome.value,
        "policy_version": ev.policy_version,
    }


def evaluation_from_dict(d: dict) -> CandidateEvaluation:
    return CandidateEvaluation(
        candidate_evaluation_id=d["candidate_evaluation_id"],
        candidate_instance_id=d["candidate_instance_id"],
        hypothesis_id=d["hypothesis_id"],
        agreements=tuple(finding_from_dict(f) for f in d["agreements"]),
        contradictions=tuple(finding_from_dict(f) for f in d["contradictions"]),
        missing_information=tuple(finding_from_dict(f) for f in d["missing_information"]),
        identity_fit=d["identity_fit"],
        product_form_fit=d["product_form_fit"],
        attribute_fit=d["attribute_fit"],
        evidence_coverage=d["evidence_coverage"],
        hard_rejected=d["hard_rejected"],
        evaluation_outcome=CandidateOutcome(d["evaluation_outcome"]),
        policy_version=d["policy_version"],
    )


def uncertainty_to_dict(u: DecisionUncertainty) -> dict:
    return {
        "observation_quality": u.observation_quality.value,
        "claim_support": u.claim_support.value,
        "candidate_fit": u.candidate_fit.value,
        "evidence_coverage": u.evidence_coverage.value,
        "contradiction_level": u.contradiction_level.value,
        "distinguishability": u.distinguishability.value,
        "calibration_status": u.calibration_status.value,
    }


def uncertainty_from_dict(d: dict) -> DecisionUncertainty:
    return DecisionUncertainty(
        observation_quality=UncertaintyBand(d["observation_quality"]),
        claim_support=UncertaintyBand(d["claim_support"]),
        candidate_fit=UncertaintyBand(d["candidate_fit"]),
        evidence_coverage=UncertaintyBand(d["evidence_coverage"]),
        contradiction_level=UncertaintyBand(d["contradiction_level"]),
        distinguishability=UncertaintyBand(d["distinguishability"]),
        calibration_status=CalibrationStatus(d["calibration_status"]),
    )


def decision_to_dict(dec: Decision) -> dict:
    return {
        "decision_id": dec.decision_id,
        "case_id": dec.case_id,
        "observation_id": dec.observation_id,
        "decision_type": dec.decision_type.value,
        "identification_level": dec.identification_level.value,
        "selected_hypothesis_id": dec.selected_hypothesis_id,
        "selected_candidate_instance_id": dec.selected_candidate_instance_id,
        "product_form": dec.product_form.value,
        "product_type": dec.product_type,
        "identified_brand": dec.identified_brand,
        "identified_family": dec.identified_family,
        "identified_model": dec.identified_model,
        "identified_variant": dec.identified_variant,
        "alternative_candidate_ids": list(dec.alternative_candidate_ids),
        "unresolved_fields": list(dec.unresolved_fields),
        "contradiction_codes": list(dec.contradiction_codes),
        "abstention_reason": dec.abstention_reason.value if dec.abstention_reason else None,
        "review_recommended": dec.review_recommended,
        "comparability_status": dec.comparability_status.value,
        "uncertainty": uncertainty_to_dict(dec.uncertainty),
        "policy_version": dec.policy_version,
        "knowledge_version": dec.knowledge_version,
        "capability_version": dec.capability_version,
    }


def decision_from_dict(d: dict) -> Decision:
    return Decision(
        decision_id=d["decision_id"],
        case_id=d["case_id"],
        observation_id=d["observation_id"],
        decision_type=DecisionType(d["decision_type"]),
        identification_level=IdentificationLevel(d["identification_level"]),
        selected_hypothesis_id=d["selected_hypothesis_id"],
        selected_candidate_instance_id=d["selected_candidate_instance_id"],
        product_form=ProductForm(d["product_form"]),
        product_type=d["product_type"],
        identified_brand=d["identified_brand"],
        identified_family=d["identified_family"],
        identified_model=d["identified_model"],
        identified_variant=d["identified_variant"],
        alternative_candidate_ids=tuple(d["alternative_candidate_ids"]),
        unresolved_fields=tuple(d["unresolved_fields"]),
        contradiction_codes=tuple(d["contradiction_codes"]),
        abstention_reason=(
            AbstentionReason(d["abstention_reason"]) if d["abstention_reason"] else None
        ),
        review_recommended=d["review_recommended"],
        comparability_status=ComparabilityStatus(d["comparability_status"]),
        uncertainty=uncertainty_from_dict(d["uncertainty"]),
        policy_version=d["policy_version"],
        knowledge_version=d["knowledge_version"],
        capability_version=d["capability_version"],
    )


def explanation_to_dict(e: Explanation) -> dict:
    return {
        "explanation_id": e.explanation_id,
        "decision_id": e.decision_id,
        "summary": e.summary,
        "supporting_points": list(e.supporting_points),
        "contradictory_points": list(e.contradictory_points),
        "unresolved_points": list(e.unresolved_points),
        "rejected_alternatives": list(e.rejected_alternatives),
        "evidence_ids": list(e.evidence_ids),
        "profile": e.profile.value,
    }


def explanation_from_dict(d: dict) -> Explanation:
    return Explanation(
        explanation_id=d["explanation_id"],
        decision_id=d["decision_id"],
        summary=d["summary"],
        supporting_points=tuple(d["supporting_points"]),
        contradictory_points=tuple(d["contradictory_points"]),
        unresolved_points=tuple(d["unresolved_points"]),
        rejected_alternatives=tuple(d["rejected_alternatives"]),
        evidence_ids=tuple(d["evidence_ids"]),
        profile=ExplanationProfile(d["profile"]),
    )


def observation_to_dict(o: Observation) -> dict:
    return {
        "observation_id": o.observation_id,
        "case_id": o.case_id,
        "provider": o.provider,
        "provider_listing_id": o.provider_listing_id,
        "raw_title": o.raw_title,
        "normalized_title": o.normalized_title,
        "raw_description": o.raw_description,
        "raw_category": o.raw_category,
        "raw_condition": o.raw_condition,
        "raw_attributes": thaw_value(o.raw_attributes),
        "image_refs": list(o.image_refs),
        "acquired_at": _dt(o.acquired_at),
        "source_fingerprint": o.source_fingerprint,
        "schema_version": o.schema_version,
    }


def observation_from_dict(d: dict) -> Observation:
    return Observation(
        observation_id=d["observation_id"],
        case_id=d["case_id"],
        provider=d["provider"],
        provider_listing_id=d["provider_listing_id"],
        raw_title=d["raw_title"],
        normalized_title=d["normalized_title"],
        raw_description=d["raw_description"],
        raw_category=d["raw_category"],
        raw_condition=d["raw_condition"],
        raw_attributes=d["raw_attributes"],
        image_refs=tuple(d["image_refs"]),
        acquired_at=datetime.fromisoformat(d["acquired_at"]),
        source_fingerprint=d["source_fingerprint"],
        schema_version=d["schema_version"],
    )


def reasoning_record_to_dict(record: ReasoningRecord) -> dict:
    """Serialize a complete :class:`ReasoningRecord` to a JSON-able dict."""
    return {
        "case_id": record.case_id,
        "observation": observation_to_dict(record.observation),
        "evidence": [evidence_to_dict(e) for e in record.evidence],
        "claims": [claim_to_dict(c) for c in record.claims],
        "hypotheses": [hypothesis_to_dict(h) for h in record.hypotheses],
        "candidates": [candidate_to_dict(c) for c in record.candidates],
        "candidate_evaluations": [evaluation_to_dict(e) for e in record.candidate_evaluations],
        "decision": decision_to_dict(record.decision),
        "explanation": explanation_to_dict(record.explanation),
        "operational_metrics": thaw_value(record.operational_metrics),
        "schema_version": record.schema_version,
        "created_at": _dt(record.created_at),
    }


def reasoning_record_from_dict(d: dict) -> ReasoningRecord:
    """Reconstruct a :class:`ReasoningRecord` from its JSON-able dict."""
    return ReasoningRecord(
        case_id=d["case_id"],
        observation=observation_from_dict(d["observation"]),
        evidence=tuple(evidence_from_dict(e) for e in d["evidence"]),
        claims=tuple(claim_from_dict(c) for c in d["claims"]),
        hypotheses=tuple(hypothesis_from_dict(h) for h in d["hypotheses"]),
        candidates=tuple(candidate_from_dict(c) for c in d["candidates"]),
        candidate_evaluations=tuple(evaluation_from_dict(e) for e in d["candidate_evaluations"]),
        decision=decision_from_dict(d["decision"]),
        explanation=explanation_from_dict(d["explanation"]),
        operational_metrics=d["operational_metrics"],
        schema_version=d["schema_version"],
        created_at=datetime.fromisoformat(d["created_at"]),
    )


def reasoning_record_to_json(record: ReasoningRecord) -> str:
    return json.dumps(reasoning_record_to_dict(record), sort_keys=True)


def reasoning_record_from_json(payload: str) -> ReasoningRecord:
    return reasoning_record_from_dict(json.loads(payload))


# --------------------------------------------------------------------------- #
# SQLite store
# --------------------------------------------------------------------------- #
class PueCaseStore:
    """Store and retrieve PUE :class:`ReasoningRecord` cases in SQLite."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            parent = Path(self.path).parent
            if parent and not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> PueCaseStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def save_case(
        self, record: ReasoningRecord, *, created_at: str | None = None, replay: bool = False
    ) -> str:
        """Persist ``record``. Raises if ``case_id`` already exists (no overwrite).

        Equivalent-record detection (application level, not a DB constraint):
        when ``replay`` is ``False`` (normal shadow processing), a case whose
        ``source_fingerprint`` and full version triple (capability/policy/
        knowledge) already match a previously persisted, completed record is
        rejected - re-running the identical listing under identical versions
        must not accumulate duplicate completed records. Pass ``replay=True``
        for explicitly marked replay/evaluation activity (e.g. benchmarking a
        new policy against historical listings), which may retain another
        record for the same fingerprint/version triple.
        """
        existing = self.get_case(record.case_id)
        if existing is not None:
            raise PueValidationError(
                f"case_id {record.case_id!r} already persisted; historical records "
                "are never overwritten (create a new case for a rerun)"
            )
        decision = record.decision
        if not replay:
            equivalent = self.find_equivalent(
                source_fingerprint=record.observation.source_fingerprint,
                capability_version=decision.capability_version,
                policy_version=decision.policy_version,
                knowledge_version=decision.knowledge_version,
            )
            if equivalent is not None:
                raise PueValidationError(
                    "an equivalent completed record already exists for "
                    f"source_fingerprint {record.observation.source_fingerprint!r} under "
                    "the same capability/policy/knowledge versions "
                    f"(case_id={equivalent.case_id!r}); pass replay=True to retain "
                    "another record for explicitly marked replay/evaluation activity"
                )
        selected_catalogue_product_id = None
        if decision.selected_candidate_instance_id is not None:
            for c in record.candidates:
                if c.candidate_instance_id == decision.selected_candidate_instance_id:
                    selected_catalogue_product_id = c.catalogue_product_id
                    break
        timestamp = created_at if created_at is not None else _utc_now()
        with self._conn:
            self._conn.execute(
                "INSERT INTO pue_cases ("
                "case_id, observation_id, provider, provider_listing_id, source_fingerprint, "
                "capability_version, policy_version, knowledge_version, schema_version, "
                "decision_type, identification_level, product_form, "
                "selected_catalogue_product_id, comparability_status, "
                "reasoning_record_json, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.case_id,
                    record.observation.observation_id,
                    record.observation.provider,
                    record.observation.provider_listing_id,
                    record.observation.source_fingerprint,
                    decision.capability_version,
                    decision.policy_version,
                    decision.knowledge_version,
                    record.schema_version,
                    decision.decision_type.value,
                    decision.identification_level.value,
                    decision.product_form.value,
                    selected_catalogue_product_id,
                    decision.comparability_status.value,
                    reasoning_record_to_json(record),
                    timestamp,
                ),
            )
        return record.case_id

    def get_case(self, case_id: str) -> ReasoningRecord | None:
        row = self._conn.execute(
            "SELECT reasoning_record_json FROM pue_cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        if row is None:
            return None
        return reasoning_record_from_json(row["reasoning_record_json"])

    def find_equivalent(
        self,
        *,
        source_fingerprint: str,
        capability_version: str,
        policy_version: str,
        knowledge_version: str,
    ) -> ReasoningRecord | None:
        """Return the earliest persisted case equivalent to this fingerprint
        and version triple, if any (application-level duplicate detection;
        see :meth:`save_case`)."""
        row = self._conn.execute(
            "SELECT reasoning_record_json FROM pue_cases WHERE source_fingerprint = ? "
            "AND capability_version = ? AND policy_version = ? AND knowledge_version = ? "
            "ORDER BY created_at ASC LIMIT 1",
            (source_fingerprint, capability_version, policy_version, knowledge_version),
        ).fetchone()
        if row is None:
            return None
        return reasoning_record_from_json(row["reasoning_record_json"])

    def find_by_fingerprint(self, source_fingerprint: str) -> list[ReasoningRecord]:
        rows = self._conn.execute(
            "SELECT reasoning_record_json FROM pue_cases WHERE source_fingerprint = ? "
            "ORDER BY created_at ASC",
            (source_fingerprint,),
        ).fetchall()
        return [reasoning_record_from_json(row["reasoning_record_json"]) for row in rows]

    def find_by_listing(self, provider: str, provider_listing_id: str) -> list[ReasoningRecord]:
        rows = self._conn.execute(
            "SELECT reasoning_record_json FROM pue_cases "
            "WHERE provider = ? AND provider_listing_id = ? ORDER BY created_at ASC",
            (provider, provider_listing_id),
        ).fetchall()
        return [reasoning_record_from_json(row["reasoning_record_json"]) for row in rows]

    def list_cases(self, *, limit: int | None = None) -> list[str]:
        sql = "SELECT case_id FROM pue_cases ORDER BY created_at DESC"
        params: tuple[int, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        rows = self._conn.execute(sql, params).fetchall()
        return [row["case_id"] for row in rows]

    # ----------------------------------------------------------------- #
    # Classifier/PUE comparison records (Sprint 2, Task 1) - same
    # database file as ``pue_cases``, not a new database.
    # ----------------------------------------------------------------- #
    def save_comparison(
        self,
        comparison: ClassifierPueComparison,
        *,
        created_at: str | None = None,
        replay: bool = False,
    ) -> str:
        """Persist ``comparison``. Raises if ``case_id`` already has a
        comparison (no overwrite; mirrors :meth:`save_case`).

        Equivalent-record detection mirrors :meth:`save_case`: when
        ``replay`` is ``False``, a comparison whose ``source_fingerprint``
        and classifier/PUE version pair already match a previously
        persisted comparison is rejected, so repeated normal processing of
        the same listing under the same versions does not accumulate
        duplicate comparison records.
        """
        if self.get_comparison(comparison.case_id) is not None:
            raise PueValidationError(
                f"a comparison for case_id {comparison.case_id!r} is already persisted; "
                "historical records are never overwritten"
            )
        if not replay:
            equivalent = self.find_comparison_equivalent(
                source_fingerprint=comparison.source_fingerprint,
                classifier_capability_version=comparison.classifier_capability_version,
                pue_capability_version=comparison.pue_capability_version,
            )
            if equivalent is not None:
                raise PueValidationError(
                    "an equivalent comparison already exists for source_fingerprint "
                    f"{comparison.source_fingerprint!r} under the same classifier/PUE "
                    f"versions (case_id={equivalent.case_id!r}); pass replay=True to "
                    "retain another record for explicitly marked replay/evaluation activity"
                )
        timestamp = created_at if created_at is not None else _utc_now()
        with self._conn:
            self._conn.execute(
                "INSERT INTO pue_classifier_comparisons ("
                "case_id, provider, provider_listing_id, source_fingerprint, "
                "classifier_capability_version, pue_capability_version, category, "
                "comparison_json, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    comparison.case_id,
                    comparison.provider,
                    comparison.provider_listing_id,
                    comparison.source_fingerprint,
                    comparison.classifier_capability_version,
                    comparison.pue_capability_version,
                    comparison.category.value,
                    comparison_to_json(comparison),
                    timestamp,
                ),
            )
        return comparison.case_id

    def get_comparison(self, case_id: str) -> ClassifierPueComparison | None:
        row = self._conn.execute(
            "SELECT comparison_json FROM pue_classifier_comparisons WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        if row is None:
            return None
        return comparison_from_json(row["comparison_json"])

    def find_comparison_equivalent(
        self,
        *,
        source_fingerprint: str,
        classifier_capability_version: str,
        pue_capability_version: str,
    ) -> ClassifierPueComparison | None:
        """Return the earliest persisted comparison equivalent to this
        fingerprint and version pair, if any (application-level duplicate
        detection; see :meth:`save_comparison`)."""
        row = self._conn.execute(
            "SELECT comparison_json FROM pue_classifier_comparisons WHERE "
            "source_fingerprint = ? AND classifier_capability_version = ? "
            "AND pue_capability_version = ? ORDER BY created_at ASC LIMIT 1",
            (source_fingerprint, classifier_capability_version, pue_capability_version),
        ).fetchone()
        if row is None:
            return None
        return comparison_from_json(row["comparison_json"])

    def list_comparisons(self, *, limit: int | None = None) -> list[ClassifierPueComparison]:
        sql = "SELECT comparison_json FROM pue_classifier_comparisons ORDER BY created_at DESC"
        params: tuple[int, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        rows = self._conn.execute(sql, params).fetchall()
        return [comparison_from_json(row["comparison_json"]) for row in rows]
