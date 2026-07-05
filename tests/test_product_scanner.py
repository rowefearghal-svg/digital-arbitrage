"""Unit tests for the product_scanner module."""

from __future__ import annotations

import logging

import pytest

from digital_arbitrage.product_scanner import (
    Condition,
    Listing,
    Provider,
    Scanner,
    ScannerConfig,
    build_scanner,
    configure_logging,
    create_provider,
    load_config,
)
from digital_arbitrage.product_scanner.config import DEFAULT_PROVIDERS
from digital_arbitrage.product_scanner.providers import PROVIDER_REGISTRY

BUILTIN_PROVIDERS = ["ebay", "facebook_marketplace", "adverts_ie", "donedeal"]


# --------------------------------------------------------------------------- #
# Listing model
# --------------------------------------------------------------------------- #
def test_listing_defaults_and_timestamp() -> None:
    listing = Listing(listing_id="x1", title="RTX 4090", provider="ebay", url="http://e/1")
    assert listing.currency == "EUR"
    assert listing.condition is Condition.UNKNOWN
    assert listing.scanned_at is not None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"listing_id": "", "title": "t"}, "listing_id"),
        ({"listing_id": "1", "title": ""}, "title"),
    ],
)
def test_listing_rejects_empty_required_fields(kwargs: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Listing(provider="ebay", url="http://e/1", **kwargs)


def test_listing_rejects_negative_price() -> None:
    with pytest.raises(ValueError, match="price"):
        Listing(listing_id="1", title="t", provider="ebay", url="http://e/1", price=-1)


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
def test_all_builtin_providers_registered() -> None:
    for name in BUILTIN_PROVIDERS:
        assert name in PROVIDER_REGISTRY


@pytest.mark.parametrize("name", BUILTIN_PROVIDERS)
def test_provider_returns_normalised_listings(name: str) -> None:
    provider = create_provider(name)
    listings = provider.search("rtx 4090", limit=5)
    assert len(listings) == 5
    assert all(isinstance(item, Listing) for item in listings)
    assert all(item.provider == name for item in listings)
    assert all("rtx 4090".lower() in item.title.lower() for item in listings)


def test_provider_respects_limit() -> None:
    provider = create_provider("ebay")
    assert len(provider.search("gpu", limit=3)) == 3


def test_provider_results_are_deterministic() -> None:
    provider = create_provider("ebay")
    first = provider.search("rtx 4090", limit=4)
    second = provider.search("rtx 4090", limit=4)
    assert [item.listing_id for item in first] == [item.listing_id for item in second]


@pytest.mark.parametrize("bad_query", ["", "   "])
def test_provider_rejects_empty_query(bad_query: str) -> None:
    with pytest.raises(ValueError, match="query"):
        create_provider("ebay").search(bad_query)


def test_create_unknown_provider_raises() -> None:
    with pytest.raises(KeyError, match="unknown provider"):
        create_provider("gumtree")


# --------------------------------------------------------------------------- #
# Scanner
# --------------------------------------------------------------------------- #
def test_scan_aggregates_across_providers() -> None:
    scanner = build_scanner()
    listings = scanner.scan("rtx 4090", limit=2)
    assert len(listings) == len(BUILTIN_PROVIDERS) * 2
    assert {item.provider for item in listings} == set(BUILTIN_PROVIDERS)
    assert all(isinstance(item, Listing) for item in listings)


def test_scan_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query"):
        build_scanner().scan("  ")


def test_scan_isolates_failing_provider(caplog: pytest.LogCaptureFixture) -> None:
    class BoomProvider(Provider):
        name = "boom"

        def fetch(self, query: str, *, limit: int) -> list[Listing]:
            raise RuntimeError("kaboom")

    good = create_provider("ebay")
    scanner = Scanner([good, BoomProvider()], max_results_per_provider=2)
    with caplog.at_level(logging.ERROR):
        listings = scanner.scan("gpu")
    assert len(listings) == 2  # only the good provider contributed
    assert "boom" in caplog.text


def test_add_provider_extensibility() -> None:
    scanner = Scanner([create_provider("ebay")], max_results_per_provider=1)
    assert len(scanner.scan("gpu")) == 1
    scanner.add_provider(create_provider("donedeal"))
    assert len(scanner.scan("gpu")) == 2


def test_scan_returns_list_of_listing_objects() -> None:
    result = build_scanner().scan("rtx 4090")
    assert isinstance(result, list)
    assert all(isinstance(item, Listing) for item in result)


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def test_default_config() -> None:
    cfg = load_config()
    assert list(DEFAULT_PROVIDERS) == cfg.providers
    assert cfg.default_currency == "EUR"


def test_config_from_dict_filters_unknown_keys() -> None:
    cfg = ScannerConfig.from_dict(
        {"scanner": {"providers": ["ebay"], "max_results_per_provider": 3, "junk": 1}}
    )
    assert cfg.providers == ["ebay"]
    assert cfg.max_results_per_provider == 3


def test_config_from_toml(tmp_path) -> None:  # noqa: ANN001 - pytest fixture
    toml = tmp_path / "scanner.toml"
    toml.write_text('[scanner]\nproviders = ["ebay", "donedeal"]\nmax_results_per_provider = 5\n')
    cfg = load_config(toml)
    assert cfg.providers == ["ebay", "donedeal"]
    assert cfg.max_results_per_provider == 5


@pytest.mark.parametrize(
    "kwargs",
    [{"max_results_per_provider": 0}, {"providers": []}],
)
def test_invalid_config_raises(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ScannerConfig(**kwargs)


def test_build_scanner_uses_configured_providers() -> None:
    scanner = build_scanner(ScannerConfig(providers=["ebay"], max_results_per_provider=1))
    assert [p.name for p in scanner.providers] == ["ebay"]


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def test_configure_logging_is_idempotent() -> None:
    configure_logging(logging.DEBUG)
    logger = logging.getLogger("digital_arbitrage.product_scanner")
    count = len(logger.handlers)
    configure_logging(logging.DEBUG)
    assert len(logger.handlers) == count  # no duplicate handlers
