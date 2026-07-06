"""Unit tests for the market_pricing package."""

from __future__ import annotations

import pytest

from digital_arbitrage.deduplication.models import DuplicateGroup
from digital_arbitrage.market_pricing import (
    ComparableListing,
    MarketPrice,
    MarketPriceEstimator,
    MarketPricingConfig,
    MedianStrategy,
    PricingStrategy,
    TrimmedMeanStrategy,
    WeightedAverageStrategy,
    create_strategy,
)
from digital_arbitrage.normalization.models import NormalizedListing
from digital_arbitrage.product_scanner import Listing


def nl(
    *,
    price: float | None = None,
    tokens: tuple[str, ...] = ("rtx", "4090"),
    provider: str = "ebay",
    currency: str = "EUR",
    lid: str = "1",
) -> NormalizedListing:
    listing = Listing(
        listing_id=lid,
        title=" ".join(tokens),
        provider=provider,
        url=f"https://x/{lid}",
        price=price,
        currency=currency,
    )
    return NormalizedListing(
        source=listing, title=" ".join(tokens), title_tokens=tokens, currency=currency
    )


def cl(
    price: float, *, currency: str = "EUR", weight: float = 1.0, lid: str = "1"
) -> ComparableListing:
    return ComparableListing(
        listing=nl(price=price, currency=currency, lid=lid),
        price=price,
        currency=currency,
        weight=weight,
    )


# --------------------------------------------------------------------------- #
# strategies
# --------------------------------------------------------------------------- #
def test_median_strategy() -> None:
    assert MedianStrategy().estimate([10.0, 20.0, 30.0], [1, 1, 1]) == 20.0


def test_trimmed_mean_strategy_drops_extremes() -> None:
    strategy = TrimmedMeanStrategy(trim_fraction=0.2)
    assert strategy.estimate([1.0, 2.0, 3.0, 4.0, 100.0], [1] * 5) == 3.0


def test_weighted_average_strategy() -> None:
    assert WeightedAverageStrategy().estimate([10.0, 20.0], [1.0, 3.0]) == 17.5


def test_weighted_average_zero_weight_falls_back_to_mean() -> None:
    assert WeightedAverageStrategy().estimate([10.0, 20.0], [0.0, 0.0]) == 15.0


def test_trimmed_mean_rejects_bad_fraction() -> None:
    with pytest.raises(ValueError, match="trim_fraction"):
        TrimmedMeanStrategy(trim_fraction=0.7)


def test_create_strategy_unknown() -> None:
    with pytest.raises(ValueError, match="unknown strategy"):
        create_strategy("bogus")


def test_strategy_requires_name() -> None:
    class Nameless(PricingStrategy):
        def estimate(self, prices: list[float], weights: list[float]) -> float:  # type: ignore[override]
            return 0.0

    with pytest.raises(ValueError, match="non-empty 'name'"):
        Nameless()


# --------------------------------------------------------------------------- #
# models / config validation
# --------------------------------------------------------------------------- #
def test_comparable_rejects_negative_price() -> None:
    with pytest.raises(ValueError, match="price must be non-negative"):
        cl(-1.0)


def test_comparable_rejects_bad_weight() -> None:
    with pytest.raises(ValueError, match="weight must be positive"):
        cl(10.0, weight=0.0)


def test_comparable_try_from() -> None:
    assert ComparableListing.try_from(nl(price=None)) is None
    comparable = ComparableListing.try_from(nl(price=99.0))
    assert comparable is not None
    assert comparable.price == 99.0
    assert comparable.currency == "EUR"


def test_market_price_validates_confidence() -> None:
    with pytest.raises(ValueError, match="confidence_score must be in"):
        MarketPrice(
            estimated_market_price=1.0,
            confidence_score=2.0,
            comparable_count=1,
            min_price=1.0,
            max_price=1.0,
            median_price=1.0,
            mean_price=1.0,
            currency="EUR",
            strategy="median",
        )


@pytest.mark.parametrize(
    "kwargs",
    [{"min_comparables": 0}, {"iqr_multiplier": 0.0}, {"confidence_full_count": 0}],
)
def test_config_validation(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        MarketPricingConfig(**kwargs)


# --------------------------------------------------------------------------- #
# estimator
# --------------------------------------------------------------------------- #
def test_empty_dataset() -> None:
    result = MarketPriceEstimator().estimate([])
    assert not result.is_priced
    assert result.estimated_market_price is None
    assert result.comparable_count == 0
    assert result.confidence_score == 0.0
    assert result.reliable is False


def test_identical_prices() -> None:
    comparables = [cl(200.0, lid=str(i)) for i in range(5)]
    result = MarketPriceEstimator().estimate(comparables)
    assert result.estimated_market_price == 200.0
    assert result.min_price == result.max_price == 200.0
    assert result.median_price == result.mean_price == 200.0
    assert result.confidence_score == 1.0
    assert result.reliable is True


def test_outlier_removal() -> None:
    prices = [95.0, 100.0, 100.0, 105.0, 110.0, 100000.0]
    comparables = [cl(p, lid=str(i)) for i, p in enumerate(prices)]
    result = MarketPriceEstimator().estimate(comparables)
    assert result.outliers_removed >= 1
    assert result.estimated_market_price is not None
    assert result.estimated_market_price < 1000
    assert result.comparable_count == len(prices) - result.outliers_removed


def test_outliers_kept_when_disabled() -> None:
    prices = [95.0, 100.0, 100.0, 105.0, 110.0, 100000.0]
    comparables = [cl(p, lid=str(i)) for i, p in enumerate(prices)]
    cfg = MarketPricingConfig(remove_outliers=False)
    result = MarketPriceEstimator(cfg).estimate(comparables)
    assert result.outliers_removed == 0
    assert result.max_price == 100000.0


def test_insufficient_comparables_is_unreliable() -> None:
    comparables = [cl(100.0, lid="1"), cl(110.0, lid="2")]
    result = MarketPriceEstimator(MarketPricingConfig(min_comparables=3)).estimate(comparables)
    assert result.comparable_count == 2
    assert result.estimated_market_price is not None
    assert result.reliable is False


def test_extreme_prices_have_low_confidence() -> None:
    cfg = MarketPricingConfig(remove_outliers=False)
    result = MarketPriceEstimator(cfg).estimate([cl(10.0, lid="1"), cl(1000.0, lid="2")])
    assert result.confidence_score < 0.5


def test_strategy_selection_changes_estimate() -> None:
    comparables = [cl(p, lid=str(i)) for i, p in enumerate([10.0, 10.0, 10.0, 10.0, 1000.0])]
    cfg = MarketPricingConfig(remove_outliers=False)
    median = MarketPriceEstimator(cfg).estimate(comparables).estimated_market_price
    mean_cfg = MarketPricingConfig(strategy="weighted_average", remove_outliers=False)
    mean = MarketPriceEstimator(mean_cfg).estimate(comparables).estimated_market_price
    assert median == 10.0
    assert mean is not None and mean > median


def test_accepts_strategy_instance() -> None:
    cfg = MarketPricingConfig(strategy=MedianStrategy(), remove_outliers=False)
    result = MarketPriceEstimator(cfg).estimate([cl(10.0, lid="1"), cl(30.0, lid="2")])
    assert result.strategy == "median"
    assert result.estimated_market_price == 20.0


def test_weighted_average_uses_weights() -> None:
    comparables = [cl(100.0, weight=1.0, lid="1"), cl(200.0, weight=3.0, lid="2")]
    cfg = MarketPricingConfig(strategy="weighted_average", remove_outliers=False)
    result = MarketPriceEstimator(cfg).estimate(comparables)
    assert result.estimated_market_price == 175.0


def test_currency_filtering_keeps_dominant() -> None:
    comparables = [
        cl(100.0, currency="EUR", lid="1"),
        cl(110.0, currency="EUR", lid="2"),
        cl(500.0, currency="USD", lid="3"),
    ]
    result = MarketPriceEstimator(MarketPricingConfig(remove_outliers=False)).estimate(comparables)
    assert result.currency == "EUR"
    assert result.comparable_count == 2
    assert result.max_price == 110.0


def test_forced_currency_with_no_matches_is_empty() -> None:
    result = MarketPriceEstimator(MarketPricingConfig(currency="GBP")).estimate([cl(100.0)])
    assert not result.is_priced
    assert result.currency == "GBP"


def test_estimate_from_listings_skips_priceless() -> None:
    listings = [nl(price=100.0, lid="1"), nl(price=None, lid="2"), nl(price=120.0, lid="3")]
    cfg = MarketPricingConfig(remove_outliers=False)
    result = MarketPriceEstimator(cfg).estimate_from_listings(listings)
    assert result.comparable_count == 2


def test_estimate_from_group() -> None:
    members = tuple(nl(price=p, lid=str(i)) for i, p in enumerate([100.0, 110.0, 105.0]))
    group = DuplicateGroup(fingerprint="f", canonical=members[0], members=members)
    result = MarketPriceEstimator(MarketPricingConfig(remove_outliers=False)).estimate_from_group(
        group
    )
    assert result.comparable_count == 3
    assert result.estimated_market_price == 105.0


def test_estimate_is_order_independent() -> None:
    prices = [100.0, 105.0, 110.0, 95.0]
    forward = [cl(p, lid=str(i)) for i, p in enumerate(prices)]
    reverse = list(reversed(forward))
    a = MarketPriceEstimator().estimate(forward)
    b = MarketPriceEstimator().estimate(reverse)
    assert a.estimated_market_price == b.estimated_market_price
    assert a.confidence_score == b.confidence_score
