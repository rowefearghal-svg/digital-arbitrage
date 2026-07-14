"""eBay Browse API provider - the first real, read-only marketplace integration.

This is a thin, declarative provider on top of the live-provider framework
(ADR-015) and its auth abstraction / config-aware factory (ADR-017). It calls the
officially supported eBay **Browse API**
(``GET /buy/browse/v1/item_summary/search``) with an *application* OAuth token
(client-credentials grant) and maps each item summary onto the shared
:class:`~digital_arbitrage.product_scanner.models.Listing` model. See
``docs/EBAY_PROVIDER_PLAN.md`` and ADR-016/ADR-018 for the full design.

Scope guardrails (unchanged from prior sprints): **read-only**, **no scraping**,
**standard library only**, **no secrets in the repo or CI**, and **backwards
compatible** with the existing mock providers. Credentials come only from the
``EBAY_CLIENT_ID`` / ``EBAY_CLIENT_SECRET`` secrets; the provider never performs a
live call in automated tests (a fake :class:`Transport` is injected instead).
"""

from __future__ import annotations

import os
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from ...product_scanner.models import Condition, Listing
from .auth import OAuthClientCredentialsAuthProvider
from .base import LiveProvider
from .capabilities import ProviderCapabilities
from .config import _ALLOWED_SCHEMES, LiveProviderConfig
from .errors import ProviderConfigError, ProviderResponseError
from .factory import (
    create_live_provider,
    register_live_provider,
    register_live_provider_config_builder,
    register_live_provider_env_builder,
)
from .http import HttpRequest, HttpResponse, Transport, resolve_url
from .pagination import Page
from .validation import ensure_list, ensure_mapping, optional, parse_json, require

#: Default Browse API base URL (swap the host for the sandbox variant).
DEFAULT_BASE_URL = "https://api.ebay.com"
#: Default OAuth token endpoint (swap the host for the sandbox variant).
DEFAULT_OAUTH_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
#: Base scope sufficient for ``item_summary/search``.
DEFAULT_OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"
#: Environment variables the OAuth application credentials are read from.
CLIENT_ID_ENV = "EBAY_CLIENT_ID"
CLIENT_SECRET_ENV = "EBAY_CLIENT_SECRET"

#: eBay ``conditionId`` -> normalised :class:`Condition`. ``conditionId`` is the
#: stable signal; the free-text ``condition`` is only a fallback.
_CONDITION_BY_ID: dict[str, Condition] = {
    "1000": Condition.NEW,  # New
    "1500": Condition.NEW,  # New other
    "1750": Condition.NEW,  # New with defects / open box
    "2000": Condition.REFURBISHED,  # Certified refurbished
    "2010": Condition.REFURBISHED,  # Excellent - refurbished
    "2020": Condition.REFURBISHED,  # Very good - refurbished
    "2030": Condition.REFURBISHED,  # Good - refurbished
    "2500": Condition.REFURBISHED,  # Seller refurbished
    "3000": Condition.USED,  # Used
    "4000": Condition.USED,  # Very good
    "5000": Condition.USED,  # Good
    "6000": Condition.USED,  # Acceptable
    "7000": Condition.USED,  # For parts or not working
}


def _format_number(value: int | float) -> str:
    """Render a JSON number as a string, dropping a redundant ``.0`` on floats."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _map_condition(condition_id: str | None, condition_text: str | None) -> Condition:
    """Map an eBay condition onto our coarse :class:`Condition` enum."""
    if condition_id:
        mapped = _CONDITION_BY_ID.get(condition_id)
        if mapped is not None:
            return mapped
    if condition_text:
        lowered = condition_text.lower()
        if "refurb" in lowered:
            return Condition.REFURBISHED
        if "new" in lowered:
            return Condition.NEW
        if any(token in lowered for token in ("used", "parts", "good", "acceptable")):
            return Condition.USED
    return Condition.UNKNOWN


@dataclass(slots=True)
class EbayBrowseConfig(LiveProviderConfig):
    """:class:`LiveProviderConfig` plus the two eBay-only settings it lacks.

    ``marketplace_id`` selects the eBay marketplace (sent as the
    ``X-EBAY-C-MARKETPLACE-ID`` header); ``oauth_token_url`` / ``oauth_scope``
    drive the client-credentials token mint. Everything else (base URL, timeout,
    pagination sizing, rate limits, retry policy) is inherited unchanged, so
    ``from_dict`` transparently accepts the extra keys.
    """

    marketplace_id: str = "EBAY_IE"
    oauth_token_url: str = DEFAULT_OAUTH_TOKEN_URL
    oauth_scope: str = DEFAULT_OAUTH_SCOPE

    def __post_init__(self) -> None:
        # Explicit super() is required: ``@dataclass(slots=True)`` rebuilds the
        # class, so the zero-arg ``super()`` closure cell points at the wrong one.
        super(EbayBrowseConfig, self).__post_init__()  # noqa: UP008
        if not self.marketplace_id:
            raise ProviderConfigError("marketplace_id must not be empty")
        parsed = urllib.parse.urlsplit(self.oauth_token_url)
        if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
            raise ProviderConfigError(
                f"oauth_token_url must be an http(s) URL, got {self.oauth_token_url!r}"
            )
        if not self.oauth_scope:
            raise ProviderConfigError("oauth_scope must not be empty")


@register_live_provider
class EbayBrowseProvider(LiveProvider):
    """Read-only provider for the eBay Browse ``item_summary/search`` endpoint."""

    name = "ebay_browse"
    capabilities: ClassVar[ProviderCapabilities] = ProviderCapabilities(
        supports_free_text_search=True,
        supports_pagination=True,
        supports_price_filter=True,
        supports_condition_filter=True,
        supports_sorting=True,
        requires_api_key=True,
        max_page_size=200,
        max_results=10_000,  # eBay's hard offset ceiling
        supported_currencies=("EUR", "GBP", "USD"),
    )

    #: Browse search path, joined onto the configured ``base_url``.
    SEARCH_PATH: ClassVar[str] = "/buy/browse/v1/item_summary/search"
    #: eBay rejects ``q`` longer than this (and disallows the ``*`` wildcard).
    MAX_QUERY_LENGTH: ClassVar[int] = 100

    @property
    def ebay_config(self) -> EbayBrowseConfig:
        """The provider's config, narrowed to :class:`EbayBrowseConfig`."""
        config = self._config
        if not isinstance(config, EbayBrowseConfig):
            raise ProviderConfigError(
                "EbayBrowseProvider requires an EbayBrowseConfig", provider=self.name
            )
        return config

    def build_request(self, query: str, *, page: int, page_size: int) -> HttpRequest:
        config = self.ebay_config
        offset = (page - 1) * page_size
        return HttpRequest(
            method="GET",
            url=resolve_url(config.base_url, self.SEARCH_PATH),
            params={
                "q": query[: self.MAX_QUERY_LENGTH],
                "limit": str(page_size),
                "offset": str(offset),
            },
            headers={"X-EBAY-C-MARKETPLACE-ID": config.marketplace_id},
        )

    def parse_response(self, response: HttpResponse, *, query: str) -> Page[Listing]:
        payload = ensure_mapping(parse_json(response, provider=self.name), provider=self.name)
        raw_summaries = payload.get("itemSummaries")
        if raw_summaries is None:
            # No results: eBay omits ``itemSummaries`` entirely for an empty page.
            return Page(items=(), has_more=False)
        summaries = ensure_list(raw_summaries, context="itemSummaries", provider=self.name)
        listings = tuple(
            self._to_listing(ensure_mapping(summary, context="itemSummaries[]", provider=self.name))
            for summary in summaries
        )
        return Page(items=listings, has_more=self._has_more(payload))

    # -- response mapping helpers ------------------------------------------- #

    def _to_listing(self, summary: dict[str, object]) -> Listing:
        ctx = "itemSummaries[]"
        price, currency = self._parse_price(summary)
        condition_id = optional(summary, "conditionId", str, context=ctx, provider=self.name)
        condition_text = optional(summary, "condition", str, context=ctx, provider=self.name)
        return Listing(
            listing_id=require(summary, "itemId", str, context=ctx, provider=self.name),
            title=require(summary, "title", str, context=ctx, provider=self.name),
            provider=self.name,
            url=require(summary, "itemWebUrl", str, context=ctx, provider=self.name),
            price=price,
            currency=currency,
            location=self._parse_location(summary),
            condition=_map_condition(condition_id, condition_text),
            extra=self._build_extra(summary, condition_id=condition_id),
        )

    def _parse_price(self, summary: dict[str, object]) -> tuple[float | None, str]:
        default_currency = self.ebay_config.default_currency
        price_obj = optional(
            summary, "price", dict, context="itemSummaries[].price", provider=self.name
        )
        if price_obj is None:
            # Auction-only listings can omit ``price``; the model allows ``None``.
            return None, default_currency
        ctx = "itemSummaries[].price"
        value_text = require(price_obj, "value", str, context=ctx, provider=self.name)
        try:
            value = float(value_text)
        except ValueError as err:
            raise ProviderResponseError(
                f"{ctx}.value: expected a numeric string, got {value_text!r}",
                provider=self.name,
            ) from err
        if value < 0:
            raise ProviderResponseError(f"{ctx}.value must be non-negative", provider=self.name)
        currency = optional(
            price_obj, "currency", str, default=default_currency, context=ctx, provider=self.name
        )
        return value, currency or default_currency

    def _parse_location(self, summary: dict[str, object]) -> str | None:
        location = optional(
            summary,
            "itemLocation",
            dict,
            context="itemSummaries[].itemLocation",
            provider=self.name,
        )
        if location is None:
            return None
        ctx = "itemSummaries[].itemLocation"
        city = optional(location, "city", str, context=ctx, provider=self.name)
        state = optional(location, "stateOrProvince", str, context=ctx, provider=self.name)
        postal = optional(location, "postalCode", str, context=ctx, provider=self.name)
        country = optional(location, "country", str, context=ctx, provider=self.name)
        locality = city or state or postal
        if locality and country:
            return f"{locality}, {country}"
        return locality or country

    def _build_extra(
        self, summary: dict[str, object], *, condition_id: str | None
    ) -> dict[str, str]:
        """Map every useful Browse ``itemSummary`` field into ``Listing.extra``.

        ``Listing.extra`` is a flat ``dict[str, str]`` of provider-specific
        metadata, so scalars are coerced to strings, nested amounts are split
        into ``*_price``/``*_currency`` pairs, and lists are comma-joined. Only
        present, non-empty fields are added, so listings stay lean and the set
        of keys is fully backwards compatible (existing keys are preserved).
        See ADR-021 for the enrichment strategy.
        """
        ctx = "itemSummaries[]"
        extra: dict[str, str] = {}

        # Images: primary plus any thumbnail / additional gallery URLs.
        self._add_images(summary, extra, ctx=ctx)

        # Buying options (FIXED_PRICE / AUCTION / BEST_OFFER ...).
        self._add_str_list(extra, summary, "buyingOptions", "buying_options", ctx=ctx)

        # Condition: the stable id plus eBay's free-text label.
        if condition_id:
            extra["condition_id"] = condition_id
        self._add_str(extra, summary, "condition", "condition_text", ctx=ctx)

        # Seller identity and reputation signals.
        self._add_seller(summary, extra, ctx=ctx)

        # Shipping cost / service details (primary option).
        self._add_shipping(summary, extra, ctx=ctx)

        # Structured item location (the flat ``Listing.location`` is derived
        # from these but loses the individual components).
        self._add_location_detail(summary, extra, ctx=ctx)

        # Category classification.
        self._add_category(summary, extra, ctx=ctx)

        # Listing lifecycle timestamps (ISO-8601 strings from eBay).
        self._add_str(extra, summary, "itemCreationDate", "item_creation_date", ctx=ctx)
        self._add_str(extra, summary, "itemEndDate", "item_end_date", ctx=ctx)

        # Marketing / strike-through discount pricing.
        self._add_marketing_price(summary, extra, ctx=ctx)

        # Auction dynamics and popularity signals (present per marketplace).
        self._add_amount(
            extra, summary, "currentBidPrice", "current_bid_price", "current_bid_currency", ctx=ctx
        )
        self._add_number(extra, summary, "bidCount", "bid_count", ctx=ctx)
        self._add_number(extra, summary, "watchCount", "watch_count", ctx=ctx)

        # Unit pricing (e.g. price per 100g).
        self._add_amount(extra, summary, "unitPrice", "unit_price", "unit_price_currency", ctx=ctx)
        self._add_str(extra, summary, "unitPricingMeasure", "unit_pricing_measure", ctx=ctx)

        # Product identifiers and other marketplace metadata.
        self._add_str(extra, summary, "epid", "epid", ctx=ctx)
        self._add_str(extra, summary, "legacyItemId", "legacy_item_id", ctx=ctx)
        self._add_str(extra, summary, "itemHref", "item_href", ctx=ctx)
        self._add_str(extra, summary, "itemAffiliateWebUrl", "item_affiliate_web_url", ctx=ctx)
        self._add_str(extra, summary, "itemGroupType", "item_group_type", ctx=ctx)
        self._add_str(extra, summary, "subtitle", "subtitle", ctx=ctx)
        self._add_str(extra, summary, "shortDescription", "short_description", ctx=ctx)
        self._add_str(extra, summary, "listingMarketplaceId", "listing_marketplace_id", ctx=ctx)
        self._add_str_list(extra, summary, "qualifiedPrograms", "qualified_programs", ctx=ctx)
        self._add_bool(extra, summary, "adultOnly", "adult_only", ctx=ctx)
        self._add_bool(extra, summary, "availableCoupons", "available_coupons", ctx=ctx)
        self._add_bool(
            extra, summary, "topRatedBuyingExperience", "top_rated_buying_experience", ctx=ctx
        )
        self._add_bool(extra, summary, "priorityListing", "priority_listing", ctx=ctx)

        return extra

    # -- Listing.extra field helpers ---------------------------------------- #

    def _add_str(
        self,
        extra: dict[str, str],
        mapping: dict[str, object],
        key: str,
        out_key: str,
        *,
        ctx: str,
    ) -> None:
        """Copy a non-empty string field across (validated, type-checked)."""
        value = optional(mapping, key, str, context=ctx, provider=self.name)
        if value:
            extra[out_key] = value

    def _add_number(
        self,
        extra: dict[str, str],
        mapping: dict[str, object],
        key: str,
        out_key: str,
        *,
        ctx: str,
    ) -> None:
        """Copy a numeric field, rendered without a spurious trailing ``.0``."""
        raw = mapping.get(key)
        if raw is None:
            return
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            raise ProviderResponseError(
                f"{ctx}.{key}: expected a number, got {type(raw).__name__}", provider=self.name
            )
        extra[out_key] = _format_number(raw)

    def _add_bool(
        self,
        extra: dict[str, str],
        mapping: dict[str, object],
        key: str,
        out_key: str,
        *,
        ctx: str,
    ) -> None:
        """Copy a boolean field as the string ``"true"``/``"false"``."""
        value = optional(mapping, key, bool, context=ctx, provider=self.name)
        if value is not None:
            extra[out_key] = "true" if value else "false"

    def _add_str_list(
        self,
        extra: dict[str, str],
        mapping: dict[str, object],
        key: str,
        out_key: str,
        *,
        ctx: str,
    ) -> None:
        """Copy a list of strings as a comma-joined string (skips non-strings)."""
        raw = mapping.get(key)
        if not isinstance(raw, list):
            return
        values = [item for item in raw if isinstance(item, str) and item]
        if values:
            extra[out_key] = ",".join(values)

    def _add_amount(
        self,
        extra: dict[str, str],
        mapping: dict[str, object],
        key: str,
        value_out: str,
        currency_out: str,
        *,
        ctx: str,
    ) -> None:
        """Split an eBay amount object into ``value``/``currency`` extra keys."""
        obj = optional(mapping, key, dict, context=f"{ctx}.{key}", provider=self.name)
        if obj is None:
            return
        actx = f"{ctx}.{key}"
        self._add_str(extra, obj, "value", value_out, ctx=actx)
        self._add_str(extra, obj, "currency", currency_out, ctx=actx)

    def _add_images(self, summary: dict[str, object], extra: dict[str, str], *, ctx: str) -> None:
        image = optional(summary, "image", dict, context=f"{ctx}.image", provider=self.name)
        if image is not None:
            self._add_str(extra, image, "imageUrl", "image_url", ctx=f"{ctx}.image")
        self._add_image_urls(summary, extra, "thumbnailImages", "thumbnail_image_urls", ctx=ctx)
        self._add_image_urls(summary, extra, "additionalImages", "additional_image_urls", ctx=ctx)

    def _add_image_urls(
        self,
        summary: dict[str, object],
        extra: dict[str, str],
        key: str,
        out_key: str,
        *,
        ctx: str,
    ) -> None:
        raw = summary.get(key)
        if not isinstance(raw, list):
            return
        urls: list[str] = []
        for item in raw:
            if isinstance(item, dict):
                url = item.get("imageUrl")
                if isinstance(url, str) and url:
                    urls.append(url)
        if urls:
            extra[out_key] = ",".join(urls)

    def _add_seller(self, summary: dict[str, object], extra: dict[str, str], *, ctx: str) -> None:
        seller = optional(summary, "seller", dict, context=f"{ctx}.seller", provider=self.name)
        if seller is None:
            return
        sctx = f"{ctx}.seller"
        # ``seller`` (the username) is preserved as-is for backwards compatibility.
        self._add_str(extra, seller, "username", "seller", ctx=sctx)
        self._add_str(extra, seller, "feedbackPercentage", "seller_feedback_percentage", ctx=sctx)
        self._add_number(extra, seller, "feedbackScore", "seller_feedback_score", ctx=sctx)
        self._add_str(extra, seller, "sellerAccountType", "seller_account_type", ctx=sctx)

    def _add_shipping(self, summary: dict[str, object], extra: dict[str, str], *, ctx: str) -> None:
        raw = summary.get("shippingOptions")
        if not isinstance(raw, list) or not raw:
            return
        primary = raw[0]
        if not isinstance(primary, dict):
            return
        sctx = f"{ctx}.shippingOptions[]"
        self._add_amount(
            extra, primary, "shippingCost", "shipping_cost", "shipping_currency", ctx=sctx
        )
        self._add_str(extra, primary, "shippingCostType", "shipping_cost_type", ctx=sctx)
        self._add_str(extra, primary, "type", "shipping_type", ctx=sctx)
        self._add_str(extra, primary, "shippingCarrierCode", "shipping_carrier", ctx=sctx)
        self._add_str(extra, primary, "minEstimatedDeliveryDate", "shipping_min_delivery", ctx=sctx)
        self._add_str(extra, primary, "maxEstimatedDeliveryDate", "shipping_max_delivery", ctx=sctx)
        self._add_bool(
            extra, primary, "guaranteedDelivery", "shipping_guaranteed_delivery", ctx=sctx
        )

    def _add_location_detail(
        self, summary: dict[str, object], extra: dict[str, str], *, ctx: str
    ) -> None:
        loc = optional(
            summary, "itemLocation", dict, context=f"{ctx}.itemLocation", provider=self.name
        )
        if loc is None:
            return
        lctx = f"{ctx}.itemLocation"
        self._add_str(extra, loc, "city", "item_city", ctx=lctx)
        self._add_str(extra, loc, "stateOrProvince", "item_state", ctx=lctx)
        self._add_str(extra, loc, "postalCode", "item_postal_code", ctx=lctx)
        self._add_str(extra, loc, "country", "item_country", ctx=lctx)

    def _add_category(self, summary: dict[str, object], extra: dict[str, str], *, ctx: str) -> None:
        raw = summary.get("categories")
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            cctx = f"{ctx}.categories[]"
            self._add_str(extra, raw[0], "categoryId", "category_id", ctx=cctx)
            self._add_str(extra, raw[0], "categoryName", "category_name", ctx=cctx)
        self._add_str_list(extra, summary, "leafCategoryIds", "leaf_category_ids", ctx=ctx)

    def _add_marketing_price(
        self, summary: dict[str, object], extra: dict[str, str], *, ctx: str
    ) -> None:
        mp = optional(
            summary, "marketingPrice", dict, context=f"{ctx}.marketingPrice", provider=self.name
        )
        if mp is None:
            return
        mctx = f"{ctx}.marketingPrice"
        self._add_amount(
            extra, mp, "originalPrice", "original_price", "original_price_currency", ctx=mctx
        )
        self._add_str(extra, mp, "discountPercentage", "discount_percentage", ctx=mctx)
        self._add_amount(
            extra, mp, "discountAmount", "discount_amount", "discount_amount_currency", ctx=mctx
        )
        self._add_str(extra, mp, "priceTreatment", "price_treatment", ctx=mctx)

    def _has_more(self, payload: dict[str, object]) -> bool:
        """Whether another page exists (server ``next`` link, else offset math)."""
        next_link = payload.get("next")
        if isinstance(next_link, str) and next_link:
            return True
        total = payload.get("total")
        offset = payload.get("offset")
        limit = payload.get("limit")
        if (
            isinstance(total, int)
            and not isinstance(total, bool)
            and isinstance(offset, int)
            and not isinstance(offset, bool)
            and isinstance(limit, int)
            and not isinstance(limit, bool)
        ):
            return offset + limit < total
        return False


def build_ebay_browse_provider(
    config: EbayBrowseConfig,
    *,
    client_id: str,
    client_secret: str,
    transport: Transport | None = None,
    token_transport: Transport | None = None,
) -> EbayBrowseProvider:
    """Build an :class:`EbayBrowseProvider` wired to OAuth client-credentials auth.

    The Browse search calls go over ``transport`` (defaulting to the stdlib
    transport); the OAuth token mint uses ``token_transport`` (independently
    injectable so tests can drive both without any network). Credentials are
    passed straight through to :class:`OAuthClientCredentialsAuthProvider` and are
    never logged.
    """
    auth = OAuthClientCredentialsAuthProvider(
        client_id=client_id,
        client_secret=client_secret,
        token_url=config.oauth_token_url,
        scope=config.oauth_scope,
        provider=EbayBrowseProvider.name,
        transport=token_transport,
        timeout=config.timeout,
    )
    provider = create_live_provider(EbayBrowseProvider.name, config, auth=auth, transport=transport)
    assert isinstance(provider, EbayBrowseProvider)  # noqa: S101 - registry invariant
    return provider


def build_ebay_browse_provider_from_env(
    config: EbayBrowseConfig,
    *,
    env: Mapping[str, str] | None = None,
    transport: Transport | None = None,
    token_transport: Transport | None = None,
) -> EbayBrowseProvider:
    """Like :func:`build_ebay_browse_provider`, reading credentials from ``env``.

    ``EBAY_CLIENT_ID`` / ``EBAY_CLIENT_SECRET`` are read from ``env`` (defaulting
    to :data:`os.environ`). Missing credentials fail fast with a
    :class:`ProviderConfigError` - they are required and never committed.
    """
    source = os.environ if env is None else env
    client_id = source.get(CLIENT_ID_ENV)
    client_secret = source.get(CLIENT_SECRET_ENV)
    if not client_id or not client_secret:
        raise ProviderConfigError(
            f"{CLIENT_ID_ENV} and {CLIENT_SECRET_ENV} must be set",
            provider=EbayBrowseProvider.name,
        )
    return build_ebay_browse_provider(
        config,
        client_id=client_id,
        client_secret=client_secret,
        transport=transport,
        token_transport=token_transport,
    )


def build_ebay_browse_config(config_data: Mapping[str, object]) -> EbayBrowseConfig:
    """Build (and validate) an :class:`EbayBrowseConfig` from a plain mapping.

    ``base_url`` defaults to :data:`DEFAULT_BASE_URL` when omitted so a live scan
    works from a minimal (or empty) ``[providers.ebay_browse]`` config table.
    """
    data: dict[str, object] = {"base_url": DEFAULT_BASE_URL}
    data.update(config_data)
    config = EbayBrowseConfig.from_dict(data)
    # ``from_dict`` is inherited and typed to the base class; ``cls`` is this
    # subclass at runtime, so narrow the type for callers (and mypy).
    assert isinstance(config, EbayBrowseConfig)
    return config


# Register the eBay Browse builders so the provider can be configured and built
# by name (``ebay_browse``) from config + environment credentials.
register_live_provider_config_builder(EbayBrowseProvider.name, build_ebay_browse_config)
register_live_provider_env_builder(EbayBrowseProvider.name, build_ebay_browse_provider_from_env)
