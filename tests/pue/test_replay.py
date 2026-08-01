"""Tests for deterministic case replay (Sprint 3, brief sections 10/16)."""

from __future__ import annotations

from pathlib import Path

import pytest

from digital_arbitrage.pipeline.pue_shadow import ShadowConfig, run_pue_shadow
from digital_arbitrage.pue.persistence import PueCaseStore
from digital_arbitrage.pue.replay import decision_signature, replay_case
from digital_arbitrage.pue.validation import PueValidationError

from .conftest import make_normalized


def _persist_one(db_path: Path, title: str) -> str:
    listing = make_normalized(title)
    config = ShadowConfig(enabled=True, db_path=db_path)
    results = run_pue_shadow([listing], config=config)
    assert len(results) == 1
    return results[0].reasoning_record.case_id


def test_replay_is_semantically_equivalent_under_identical_versions(tmp_path: Path) -> None:
    db_path = tmp_path / "shadow.db"
    case_id = _persist_one(db_path, "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")

    comparison = replay_case(case_id, database_path=str(db_path))

    assert comparison.version_match is True
    assert comparison.equivalent is True
    assert comparison.differences == ()
    assert comparison.original_signature == comparison.replay_signature


def test_replay_does_not_mutate_the_historical_record(tmp_path: Path) -> None:
    db_path = tmp_path / "shadow.db"
    case_id = _persist_one(db_path, "NVIDIA GeForce RTX 4090 Founders Edition 24GB")

    with PueCaseStore(db_path) as store:
        before = store.get_case(case_id)

    replay_case(case_id, database_path=str(db_path))

    with PueCaseStore(db_path) as store:
        after = store.get_case(case_id)

    assert before == after


def test_replay_creates_a_separate_comparison_artefact_not_a_new_persisted_row(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "shadow.db"
    case_id = _persist_one(db_path, "RTX 4090 water block")

    with PueCaseStore(db_path) as store:
        case_count_before = len(store.list_cases())

    comparison = replay_case(case_id, database_path=str(db_path))

    with PueCaseStore(db_path) as store:
        case_count_after = len(store.list_cases())

    assert case_count_after == case_count_before
    assert comparison.replay_record.case_id != comparison.original_record.case_id


def test_replay_unknown_case_id_fails_clearly(tmp_path: Path) -> None:
    db_path = tmp_path / "shadow.db"
    _persist_one(db_path, "RTX 4090")
    with pytest.raises(PueValidationError, match="not found"):
        replay_case("does-not-exist", database_path=str(db_path))


def test_replay_unavailable_requested_version_fails_clearly(tmp_path: Path) -> None:
    """brief section 10: replay does not silently fall back to the
    newest/current catalogue or policy for a version explicitly requested."""
    db_path = tmp_path / "shadow.db"
    case_id = _persist_one(db_path, "RTX 4090")
    with pytest.raises(PueValidationError, match="not available for replay"):
        replay_case(
            case_id,
            database_path=str(db_path),
            expected_knowledge_version="gpu-seed-9.9.9-does-not-exist",
        )


def test_replay_reports_changed_version_as_comparison_not_identical(tmp_path: Path) -> None:
    """brief section 10: a changed policy/catalogue version is reported as
    a comparison, not asserted as an identical replay."""
    from digital_arbitrage.pue.orchestration import build_default_context
    from digital_arbitrage.pue.policies import DecisionPolicy

    db_path = tmp_path / "shadow.db"
    case_id = _persist_one(db_path, "RTX 4090")

    custom_policy = DecisionPolicy(policy_version="gpu-policy-9.9.9-custom")
    comparison = replay_case(
        case_id,
        database_path=str(db_path),
        policy=custom_policy,
        context=build_default_context(),
    )
    assert comparison.version_match is False
    # A version mismatch never silently claims strict equivalence.
    assert comparison.equivalent is False


def test_technical_replay_failure_distinct_from_product_abstention(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = tmp_path / "shadow.db"
    case_id = _persist_one(db_path, "RTX 4090")

    import digital_arbitrage.pue.replay as replay_module

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated PUE failure")

    monkeypatch.setattr(replay_module, "process_one", _boom)
    with pytest.raises(RuntimeError):
        replay_case(case_id, database_path=str(db_path))


def test_decision_signature_ignores_volatile_identity_fields() -> None:
    """Candidate-instance UUIDs, object UUIDs and timestamps must never
    affect the semantic-equivalence signature (brief section 10)."""
    from digital_arbitrage.pue import orchestration
    from digital_arbitrage.pue.catalogue import JsonCandidateRepository

    from .conftest import DeterministicIdFactory, FixedClock

    repo = JsonCandidateRepository()
    listing_a = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    listing_b = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")

    ctx_a = orchestration.build_default_context(
        id_factory=DeterministicIdFactory("a"), clock=FixedClock()
    )
    ctx_b = orchestration.build_default_context(
        id_factory=DeterministicIdFactory("b"), clock=FixedClock()
    )

    record_a = orchestration.process_one(listing_a, ctx_a, repository=repo)
    record_b = orchestration.process_one(listing_b, ctx_b, repository=repo)

    # Different id_factory prefixes guarantee different UUIDs everywhere.
    assert record_a.case_id != record_b.case_id
    assert record_a.decision.decision_id != record_b.decision.decision_id

    assert decision_signature(record_a) == decision_signature(record_b)
