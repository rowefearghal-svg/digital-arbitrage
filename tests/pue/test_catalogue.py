"""Unit tests: catalogue loading and malformed-entry error normalization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_arbitrage.pue.catalogue import JsonCandidateRepository, load_catalogue
from digital_arbitrage.pue.enums import DecisionType, ProcessingFailureCategory
from digital_arbitrage.pue.orchestration import build_default_context, process_many, process_one
from digital_arbitrage.pue.validation import PueValidationError

from .conftest import make_normalized

_VALID_ENTRY = {
    "catalogue_product_id": "gpu-test-0001",
    "canonical_title": "Test RTX 4090",
    "brand": "asus",
    "chipset_manufacturer": "nvidia",
    "family": "rtx 4090",
    "model": "rtx 4090",
    "variant": None,
    "product_form": "complete_product",
    "product_type": "graphics_card",
    "identifiers": {"mpn": ["TEST-4090"]},
    "aliases": [],
    "attributes": {},
    "compatibility_targets": [],
}


def _write_catalogue(tmp_path: Path, entry: dict) -> Path:
    path = tmp_path / "catalogue.json"
    path.write_text(
        json.dumps({"knowledge_version": "gpu-seed-0.1.0", "products": [entry]}), encoding="utf-8"
    )
    return path


def test_valid_entry_loads_successfully(tmp_path: Path) -> None:
    path = _write_catalogue(tmp_path, _VALID_ENTRY)
    products = load_catalogue(path)
    assert len(products) == 1
    assert products[0].catalogue_product_id == "gpu-test-0001"


def test_missing_required_field_raises_pue_validation_error(tmp_path: Path) -> None:
    entry = dict(_VALID_ENTRY)
    del entry["brand"]
    path = _write_catalogue(tmp_path, entry)
    with pytest.raises(PueValidationError):
        load_catalogue(path)


def test_invalid_product_form_raises_pue_validation_error(tmp_path: Path) -> None:
    entry = dict(_VALID_ENTRY)
    entry["product_form"] = "not_a_real_product_form"
    path = _write_catalogue(tmp_path, entry)
    with pytest.raises(PueValidationError):
        load_catalogue(path)


def test_wrong_field_type_raises_pue_validation_error(tmp_path: Path) -> None:
    entry = dict(_VALID_ENTRY)
    entry["identifiers"] = ["not", "a", "mapping"]
    path = _write_catalogue(tmp_path, entry)
    with pytest.raises(PueValidationError):
        load_catalogue(path)


def test_missing_required_field_becomes_processing_failed(monkeypatch, tmp_path: Path) -> None:
    """Default processing must convert a malformed catalogue (missing
    required field) into PROCESSING_FAILED / CATALOGUE_UNAVAILABLE, never
    an uncaught exception (pre-merge correction)."""
    entry = dict(_VALID_ENTRY)
    del entry["family"]
    path = _write_catalogue(tmp_path, entry)

    with pytest.raises(PueValidationError):
        JsonCandidateRepository.from_path(path)

    import digital_arbitrage.pue.orchestration as orchestration_module

    def _raise_like_default_catalogue() -> JsonCandidateRepository:
        return JsonCandidateRepository.from_path(path)

    monkeypatch.setattr(
        orchestration_module, "JsonCandidateRepository", _raise_like_default_catalogue
    )

    context = build_default_context()
    listing = make_normalized("RTX 4090")

    record = process_one(listing, context)
    assert record.decision.decision_type == DecisionType.PROCESSING_FAILED
    assert (
        record.operational_metrics["failure_category"]
        == ProcessingFailureCategory.CATALOGUE_UNAVAILABLE.value
    )

    batch = process_many([listing, make_normalized("RTX 3060")], context)
    assert len(batch) == 2
    for rec in batch:
        assert rec.decision.decision_type == DecisionType.PROCESSING_FAILED
        assert (
            rec.operational_metrics["failure_category"]
            == ProcessingFailureCategory.CATALOGUE_UNAVAILABLE.value
        )


def test_invalid_product_form_becomes_processing_failed(monkeypatch, tmp_path: Path) -> None:
    """A malformed default catalogue (invalid product_form) must surface as
    PROCESSING_FAILED / CATALOGUE_UNAVAILABLE from process_one/process_many,
    never an uncaught exception."""
    entry = dict(_VALID_ENTRY)
    entry["product_form"] = "not_a_real_product_form"
    path = _write_catalogue(tmp_path, entry)

    import digital_arbitrage.pue.orchestration as orchestration_module

    def _raise_like_default_catalogue() -> JsonCandidateRepository:
        return JsonCandidateRepository.from_path(path)

    monkeypatch.setattr(
        orchestration_module, "JsonCandidateRepository", _raise_like_default_catalogue
    )

    context = build_default_context()
    listing = make_normalized("RTX 4090")

    record = process_one(listing, context)
    assert record.decision.decision_type == DecisionType.PROCESSING_FAILED
    assert (
        record.operational_metrics["failure_category"]
        == ProcessingFailureCategory.CATALOGUE_UNAVAILABLE.value
    )

    batch = process_many([listing, make_normalized("RTX 3060")], context)
    assert len(batch) == 2
    for rec in batch:
        assert rec.decision.decision_type == DecisionType.PROCESSING_FAILED
        assert (
            rec.operational_metrics["failure_category"]
            == ProcessingFailureCategory.CATALOGUE_UNAVAILABLE.value
        )
