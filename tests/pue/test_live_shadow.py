"""Tests for the PUE v0.1 post-release live shadow trial."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from digital_arbitrage.providers.live.errors import ProviderAuthError
from digital_arbitrage.pue.live_shadow import (
    LiveShadowError,
    load_query_manifest,
    run_live_shadow_trial,
)


@pytest.fixture()
def sample_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "queries.json"
    path.write_text(
        json.dumps(
            {
                "manifest_id": "test-manifest",
                "version": "0.1.0",
                "description": "Test",
                "queries": [
                    {
                        "query_id": "q-rtx-4090",
                        "search_text": "RTX 4090",
                        "searched_product_form": "complete_product",
                        "searched_product_type": "graphics card",
                        "searched_brand": "NVIDIA",
                        "searched_family": "GeForce RTX",
                        "searched_model": "4090",
                        "max_results_per_provider": 2,
                        "providers": ["ebay_browse"],
                    },
                    {
                        "query_id": "q-rtx-4080",
                        "search_text": "RTX 4080",
                        "searched_product_form": "complete_product",
                        "searched_product_type": "graphics card",
                        "max_results_per_provider": 2,
                        "providers": ["ebay_browse", "stockx"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_load_valid_manifest(sample_manifest: Path) -> None:
    manifest = load_query_manifest(sample_manifest)
    assert manifest.manifest_id == "test-manifest"
    assert len(manifest.queries) == 2
    assert manifest.queries[0].query_id == "q-rtx-4090"
    assert manifest.queries[0].providers == ("ebay_browse",)


def test_load_manifest_missing_query_id(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "manifest_id": "bad",
                "version": "0.1.0",
                "queries": [{"search_text": "foo", "providers": ["ebay"]}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(LiveShadowError, match="missing 'query_id'"):
        load_query_manifest(path)


def test_load_manifest_duplicate_query_id(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "manifest_id": "bad",
                "version": "0.1.0",
                "queries": [
                    {"query_id": "q1", "search_text": "a", "providers": ["ebay"]},
                    {"query_id": "q1", "search_text": "b", "providers": ["ebay"]},
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(LiveShadowError, match="duplicate query_id"):
        load_query_manifest(path)


def test_load_manifest_unsupported_provider_not_rejected(sample_manifest: Path) -> None:
    # Manifest may name a provider not installed; validation is intentionally light.
    manifest = load_query_manifest(sample_manifest)
    assert "ebay_browse" in manifest.queries[0].providers


class _FakeProvider:
    name = "ebay_browse"

    def __init__(self, listings: list) -> None:
        self.listings = listings

    def search(self, query: str, *, limit: int) -> list:
        return self.listings[:limit]


class _FailingProvider:
    name = "ebay_browse"

    def search(self, query: str, *, limit: int) -> list:
        raise ProviderAuthError("no token", provider="ebay_browse")


class _ZeroProvider:
    name = "stockx"

    def search(self, query: str, *, limit: int) -> list:
        return []


def _make_listings(n: int) -> list:
    from digital_arbitrage.product_scanner.models import Condition, Listing

    return [
        Listing(
            listing_id=f"lid-{i}",
            title=f"GPU {i}",
            provider="ebay_browse",
            url=f"https://example.com/{i}",
            price=float(i * 100),
            currency="USD",
            condition=Condition.NEW,
            location=None,
            extra={},
        )
        for i in range(n)
    ]


def test_live_shadow_trial_success(tmp_path: Path, sample_manifest: Path) -> None:
    listings = _make_listings(2)
    with (
        patch(
            "digital_arbitrage.pue.live_shadow.build_live_provider_from_env",
            return_value=_FakeProvider(listings),
        ),
        patch(
            "digital_arbitrage.pue.live_shadow.run_pue_shadow",
            return_value=(),
        ),
    ):
        result = run_live_shadow_trial(
            sample_manifest,
            output_dir=tmp_path,
            max_results_per_query=2,
        )
    assert result.status == "SUCCESS"
    assert result.output_paths
    assert result.providers_requested == ("ebay_browse", "stockx")
    assert set(result.providers_contacted) == {"ebay_browse", "stockx"}


def test_live_shadow_trial_provider_failure(tmp_path: Path, sample_manifest: Path) -> None:
    with (
        patch(
            "digital_arbitrage.pue.live_shadow.build_live_provider_from_env",
            return_value=_FailingProvider(),
        ),
        patch(
            "digital_arbitrage.pue.live_shadow.run_pue_shadow",
            return_value=(),
        ),
    ):
        result = run_live_shadow_trial(
            sample_manifest,
            output_dir=tmp_path,
            max_results_per_query=2,
        )
    assert result.status == "FAILURE"
    assert all(o.error for o in result.outcomes)


def test_live_shadow_trial_zero_results_partial(tmp_path: Path, sample_manifest: Path) -> None:
    listings = _make_listings(2)
    call_count = 0

    def _make_provider(name: str, *_, **__) -> object:
        nonlocal call_count
        if name == "ebay_browse":
            call_count += 1
            if call_count == 1:
                return _FailingProvider()
            return _FakeProvider(listings)
        return _ZeroProvider()

    with (
        patch(
            "digital_arbitrage.pue.live_shadow.build_live_provider_from_env",
            side_effect=_make_provider,
        ),
        patch(
            "digital_arbitrage.pue.live_shadow.run_pue_shadow",
            return_value=(),
        ),
    ):
        result = run_live_shadow_trial(
            sample_manifest,
            output_dir=tmp_path,
            max_results_per_query=2,
        )
    assert result.status == "PARTIAL_SUCCESS"
    assert any(o.error for o in result.outcomes)
    assert any(not o.error for o in result.outcomes)


def test_review_queue_json_output(tmp_path: Path, sample_manifest: Path) -> None:
    listings = _make_listings(1)
    with (
        patch(
            "digital_arbitrage.pue.live_shadow.build_live_provider_from_env",
            return_value=_FakeProvider(listings),
        ),
        patch(
            "digital_arbitrage.pue.live_shadow.run_pue_shadow",
            return_value=(),
        ),
    ):
        result = run_live_shadow_trial(
            sample_manifest,
            output_dir=tmp_path,
            max_results_per_query=1,
        )
    queue_path = Path(result.output_paths["review_queue_json"])
    assert queue_path.exists()
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    assert isinstance(queue, list)
