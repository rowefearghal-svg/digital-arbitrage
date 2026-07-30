"""Unit tests: models, validation, and JSON serialization round trips."""

from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from digital_arbitrage.pue.enums import EvidencePolarity, EvidenceType
from digital_arbitrage.pue.models import Evidence, Observation
from digital_arbitrage.pue.persistence import (
    evidence_from_dict,
    evidence_to_dict,
    reasoning_record_from_dict,
    reasoning_record_to_dict,
)
from digital_arbitrage.pue.validation import freeze_mapping, freeze_value, thaw_value


def test_observation_freezes_raw_attributes() -> None:
    obs = Observation(
        observation_id="o1",
        case_id="c1",
        provider="test",
        provider_listing_id="l1",
        raw_title="title",
        normalized_title="title",
        raw_description=None,
        raw_category=None,
        raw_condition=None,
        raw_attributes={"a": {"nested": [1, 2]}},
        image_refs=["ref1"],
        acquired_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_fingerprint="fp",
        schema_version="0.1",
    )
    assert isinstance(obs.raw_attributes, MappingProxyType)
    assert isinstance(obs.raw_attributes["a"], MappingProxyType)
    assert obs.raw_attributes["a"]["nested"] == (1, 2)
    assert obs.image_refs == ("ref1",)


def test_observation_is_frozen() -> None:
    obs = Observation(
        observation_id="o1",
        case_id="c1",
        provider="test",
        provider_listing_id="l1",
        raw_title="title",
        normalized_title="title",
        raw_description=None,
        raw_category=None,
        raw_condition=None,
        raw_attributes={},
        image_refs=(),
        acquired_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_fingerprint="fp",
        schema_version="0.1",
    )
    with pytest.raises(AttributeError):
        obs.raw_title = "mutated"  # type: ignore[misc]


def test_freeze_thaw_roundtrip() -> None:
    original = {"a": [1, 2, {"b": 3}], "c": (4, 5)}
    frozen = freeze_value(original)
    thawed = thaw_value(frozen)
    assert thawed == {"a": [1, 2, {"b": 3}], "c": [4, 5]}


def test_freeze_mapping_is_read_only() -> None:
    frozen = freeze_mapping({"x": 1})
    with pytest.raises(TypeError):
        frozen["x"] = 2  # type: ignore[index]


def test_evidence_json_roundtrip() -> None:
    e = Evidence(
        evidence_id="e1",
        observation_id="o1",
        evidence_type=EvidenceType.BRAND_TOKEN,
        raw_value="ASUS",
        normalized_value="asus",
        source_field="normalized_title",
        source_start=0,
        source_end=4,
        extraction_method="term_match",
        extraction_confidence=1.0,
        polarity_hint=EvidencePolarity.SUPPORTING,
        capability_version="pue-0.1.0",
    )
    payload = evidence_to_dict(e)
    restored = evidence_from_dict(payload)
    assert restored == e


def test_reasoning_record_json_roundtrip(sample_reasoning_record) -> None:
    payload = reasoning_record_to_dict(sample_reasoning_record)
    restored = reasoning_record_from_dict(payload)
    assert restored == sample_reasoning_record
