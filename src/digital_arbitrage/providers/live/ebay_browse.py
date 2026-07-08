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
        extra: dict[str, str] = {}
        image = optional(
            summary, "image", dict, context="itemSummaries[].image", provider=self.name
        )
        if image is not None:
            image_url = optional(
                image, "imageUrl", str, context="itemSummaries[].image", provider=self.name
            )
            if image_url:
                extra["image_url"] = image_url
        buying_options = summary.get("buyingOptions")
        if isinstance(buying_options, list):
            options = [item for item in buying_options if isinstance(item, str)]
            if options:
                extra["buying_options"] = ",".join(options)
        seller = optional(
            summary, "seller", dict, context="itemSummaries[].seller", provider=self.name
        )
        if seller is not None:
            username = optional(
                seller, "username", str, context="itemSummaries[].seller", provider=self.name
            )
            if username:
                extra["seller"] = username
        if condition_id:
            extra["condition_id"] = condition_id
        return extra

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
