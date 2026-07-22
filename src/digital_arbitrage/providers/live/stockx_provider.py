"""StockX live provider (Sprint 29).

This provider integrates StockX's public ``v2`` catalog API. It authenticates
with an OAuth 2.0 authorization-code access token plus an ``x-api-key`` header,
searches the catalog, and maps each product to a canonical :class:`Listing`
using the product-level ``/v2/catalog/products/{id}/market-data`` endpoint for
pricing.

Authentication architecture (unchanged from prior sprints):

* Playwright is **only** used when the standard HTTP token refresh is blocked
  by Cloudflare. Once a refresh token is cached, normal API calls go through the
  existing :class:`HttpClient`.
* All API requests use :class:`HttpClient` with an injected
  :class:`OAuthAuthorizationCodeAuthProvider` and the ``x-api-key`` header.

Credentials live only in the environment (``STOCKX_API_KEY``,
``STOCKX_CLIENT_ID``, ``STOCKX_CLIENT_SECRET``); the cached refresh token lives
outside the repo in ``~/.digital_arbitrage/stockx_tokens.json``.
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, cast

from ...product_scanner.models import Condition, Listing
from .auth_browser import BrowserTokenExchange
from .auth_code import OAuthAuthorizationCodeAuthProvider, TokenCache
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
from .logging_utils import format_fields
from .pagination import Page
from .validation import ensure_list, ensure_mapping, optional, parse_json, require

#: Default StockX API base URL.
DEFAULT_BASE_URL = "https://api.stockx.com"
#: Default StockX OAuth authorization endpoint.
DEFAULT_OAUTH_AUTHORIZATION_URL = "https://accounts.stockx.com/authorize"
#: Default StockX OAuth token endpoint.
DEFAULT_OAUTH_TOKEN_URL = "https://accounts.stockx.com/oauth/token"
#: Scope required to receive a refresh token.
DEFAULT_OAUTH_SCOPE = "openid offline_access"
#: Required audience parameter for StockX tokens.
DEFAULT_OAUTH_AUDIENCE = "gateway.stockx.com"
#: Default currency for market-data requests.
DEFAULT_CURRENCY_CODE = "USD"

#: Catalog search endpoint (joined onto ``base_url``).
_CATALOG_SEARCH_PATH = "/v2/catalog/search"


def _parse_amount(value: object) -> float | None:
    """Parse a numeric amount that may arrive as a string or number."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _product_url(url_key: str) -> str:
    """Build a public StockX product page URL from a ``urlKey``."""
    return f"https://stockx.com/{url_key}"


def _market_data_path(product_id: str) -> str:
    return f"/v2/catalog/products/{product_id}/market-data"


def _min_lowest_ask(market_data: list[dict[str, object]]) -> tuple[float | None, float | None]:
    """Return the minimum lowest-ask and maximum highest-bid across variants.

    ``None`` is returned for either value when no variant reports it.
    """
    lowest_asks: list[float] = []
    highest_bids: list[float] = []
    for entry in market_data:
        ask = _parse_amount(entry.get("lowestAskAmount"))
        if ask is not None:
            lowest_asks.append(ask)
        bid = _parse_amount(entry.get("highestBidAmount"))
        if bid is not None:
            highest_bids.append(bid)
    return (
        min(lowest_asks) if lowest_asks else None,
        max(highest_bids) if highest_bids else None,
    )


@dataclass(slots=True)
class StockXConfig(LiveProviderConfig):
    """:class:`LiveProviderConfig` extended with StockX-specific settings."""

    oauth_authorization_url: str = DEFAULT_OAUTH_AUTHORIZATION_URL
    oauth_token_url: str = DEFAULT_OAUTH_TOKEN_URL
    oauth_scope: str = DEFAULT_OAUTH_SCOPE
    oauth_audience: str = DEFAULT_OAUTH_AUDIENCE
    currency_code: str = DEFAULT_CURRENCY_CODE

    def __post_init__(self) -> None:
        super(StockXConfig, self).__post_init__()
        for url in (self.oauth_authorization_url, self.oauth_token_url):
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
                raise ProviderConfigError(
                    f"oauth url must be an http(s) URL, got {url!r}",
                    provider=StockXProvider.name,
                )
        if not self.oauth_scope:
            raise ProviderConfigError("oauth_scope must not be empty", provider=StockXProvider.name)
        if not self.oauth_audience:
            raise ProviderConfigError(
                "oauth_audience must not be empty", provider=StockXProvider.name
            )
        if not self.currency_code:
            raise ProviderConfigError(
                "currency_code must not be empty", provider=StockXProvider.name
            )


@register_live_provider
class StockXProvider(LiveProvider):
    """Read-only live provider for the StockX catalog API."""

    name = "stockx"
    capabilities: ClassVar[ProviderCapabilities] = ProviderCapabilities(
        supports_free_text_search=True,
        supports_pagination=True,
        supports_price_filter=False,
        supports_condition_filter=False,
        supports_sorting=False,
        requires_api_key=True,
        max_page_size=50,
        max_results=None,
        supported_currencies=("USD", "EUR", "GBP"),
    )

    #: Longest query the StockX catalog search accepts in practice.
    MAX_QUERY_LENGTH: ClassVar[int] = 100

    @property
    def stockx_config(self) -> StockXConfig:
        """The provider's config, narrowed to :class:`StockXConfig`."""
        config = self._config
        if not isinstance(config, StockXConfig):
            raise ProviderConfigError("StockXProvider requires a StockXConfig", provider=self.name)
        return config

    def build_request(self, query: str, *, page: int, page_size: int) -> HttpRequest:
        return HttpRequest(
            method="GET",
            url=resolve_url(self.stockx_config.base_url, _CATALOG_SEARCH_PATH),
            params={
                "query": query[: self.MAX_QUERY_LENGTH],
                "pageNumber": str(page),
                "pageSize": str(page_size),
            },
        )

    def parse_response(self, response: HttpResponse, *, query: str) -> Page[Listing]:
        payload = ensure_mapping(parse_json(response, provider=self.name), provider=self.name)
        raw_products = payload.get("products")
        if raw_products is None:
            return Page(items=(), has_more=False)
        products = ensure_list(raw_products, context="products", provider=self.name)

        listings: list[Listing] = []
        for raw in products:
            product = ensure_mapping(raw, context="products[]", provider=self.name)
            listing = self._to_listing(product)
            if listing is not None:
                listings.append(listing)

        return Page(items=tuple(listings), has_more=self._has_more(payload, query=query))

    def _to_listing(self, product: dict[str, object]) -> Listing | None:
        ctx = "products[]"
        product_id = require(product, "productId", str, context=ctx, provider=self.name)
        title = require(product, "title", str, context=ctx, provider=self.name)
        url_key = optional(product, "urlKey", str, context=ctx, provider=self.name)
        url = _product_url(url_key) if url_key else f"https://stockx.com/{product_id}"

        price: float | None = None
        highest_bid: float | None = None
        variant_count = 0
        extra = self._build_extra(product)

        try:
            market_response = self._client.get(
                _market_data_path(product_id),
                params={"currencyCode": self.stockx_config.currency_code},
            )
            market_payload = cast(
                list[dict[str, object]],
                ensure_list(
                    parse_json(market_response, provider=self.name),
                    context="market-data",
                    provider=self.name,
                ),
            )
            variant_count = len(market_payload)
            price, highest_bid = _min_lowest_ask(market_payload)
            extra["variant_count"] = str(variant_count)
            if price is not None:
                extra["lowest_ask"] = _format_number(price)
            if highest_bid is not None:
                extra["highest_bid"] = _format_number(highest_bid)
        except ProviderResponseError:
            self._live_log.warning(
                "stockx_market_data_parse_failed %s",
                format_fields(provider=self.name, product_id=product_id),
            )
        except Exception as err:
            self._live_log.warning(
                "stockx_market_data_fetch_failed %s",
                format_fields(
                    provider=self.name,
                    product_id=product_id,
                    error=type(err).__name__,
                ),
            )

        return Listing(
            listing_id=product_id,
            title=title,
            provider=self.name,
            url=url,
            price=price,
            currency=self.stockx_config.currency_code,
            condition=Condition.NEW,
            extra=extra,
        )

    def _build_extra(self, product: dict[str, object]) -> dict[str, str]:
        """Map StockX product fields into ``Listing.extra``."""
        ctx = "products[]"
        extra: dict[str, str] = {}

        for key, out_key in (
            ("styleId", "style_id"),
            ("productType", "product_type"),
            ("brand", "brand"),
        ):
            value = optional(product, key, str, context=ctx, provider=self.name)
            if value:
                extra[out_key] = value

        attributes = optional(product, "productAttributes", dict, context=ctx, provider=self.name)
        if attributes is not None:
            actx = f"{ctx}.productAttributes"
            for key, out_key in (
                ("colorway", "colorway"),
                ("gender", "gender"),
                ("releaseDate", "release_date"),
                ("season", "season"),
            ):
                value = optional(attributes, key, str, context=actx, provider=self.name)
                if value:
                    extra[out_key] = value
            retail_price = _parse_amount(attributes.get("retailPrice"))
            if retail_price is not None:
                extra["retail_price"] = _format_number(retail_price)

        return extra

    def _has_more(self, payload: dict[str, object], *, query: str) -> bool:
        """Whether another page of search results exists."""
        has_next = payload.get("hasNextPage")
        if isinstance(has_next, bool):
            return has_next
        count = payload.get("count")
        page_number = payload.get("pageNumber")
        page_size = payload.get("pageSize")
        if (
            isinstance(count, int)
            and not isinstance(count, bool)
            and isinstance(page_number, int)
            and not isinstance(page_number, bool)
            and isinstance(page_size, int)
            and not isinstance(page_size, bool)
        ):
            return page_number * page_size < count
        return False


def _format_number(value: int | float) -> str:
    """Render a number as a string, dropping a redundant ``.0``."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def build_stockx_provider(
    config: StockXConfig,
    *,
    refresh_token: str,
    client_id: str,
    client_secret: str,
    api_key: str,
    transport: Transport | None = None,
    token_transport: Transport | None = None,
    headless: bool = False,
) -> StockXProvider:
    """Build a :class:`StockXProvider` with OAuth authorization-code auth.

    ``refresh_token`` must come from a previous browser authorization and is read
    from the :class:`TokenCache` by :func:`build_stockx_provider_from_env`. The
    ``BrowserTokenExchange`` fallback is configured so that if the standard HTTP
    refresh is Cloudflare-blocked, Playwright can refresh the token; after that,
    all API calls still use ``transport``/``HttpClient``.
    """
    token_cache = TokenCache()
    browser_exchange = BrowserTokenExchange(
        client_id=client_id,
        client_secret=client_secret,
        authorization_url=config.oauth_authorization_url,
        token_url=config.oauth_token_url,
        redirect_uri="https://localhost:3000/callback",
        scope=config.oauth_scope,
        audience=config.oauth_audience,
        token_cache=token_cache,
        headless=headless,
        provider=StockXProvider.name,
    )
    auth = OAuthAuthorizationCodeAuthProvider(
        client_id=client_id,
        client_secret=client_secret,
        token_url=config.oauth_token_url,
        refresh_token=refresh_token,
        scope=config.oauth_scope,
        audience=config.oauth_audience,
        provider=StockXProvider.name,
        transport=token_transport,
        token_cache=token_cache,
        browser_exchange=browser_exchange,
        timeout=config.timeout,
    )
    config.api_key = api_key
    config.extra_headers["x-api-key"] = api_key
    provider = create_live_provider(StockXProvider.name, config, auth=auth, transport=transport)
    assert isinstance(provider, StockXProvider)
    return provider


def build_stockx_provider_from_env(
    config: StockXConfig,
    *,
    env: Mapping[str, str] | None = None,
    transport: Transport | None = None,
    token_transport: Transport | None = None,
    headless: bool = False,
) -> StockXProvider:
    """Build a :class:`StockXProvider` using credentials from ``env``.

    The refresh token is loaded from the user's token cache, not from the
    environment. If none is cached, a clear :class:`ProviderConfigError` is
    raised with instructions to run the browser authentication flow.
    """
    source = os.environ if env is None else env
    api_key = source.get("STOCKX_API_KEY", "")
    client_id = source.get("STOCKX_CLIENT_ID", "")
    client_secret = source.get("STOCKX_CLIENT_SECRET", "")
    if not api_key or not client_id or not client_secret:
        raise ProviderConfigError(
            "STOCKX_API_KEY, STOCKX_CLIENT_ID, and STOCKX_CLIENT_SECRET must be set",
            provider=StockXProvider.name,
        )

    token_cache = TokenCache()
    cached = token_cache.load()
    refresh_token = cached.get("refresh_token")
    if not refresh_token:
        raise ProviderConfigError(
            "No cached StockX refresh token. "
            "Run the browser authentication flow once to generate it:",
            provider=StockXProvider.name,
        )

    return build_stockx_provider(
        config,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        api_key=api_key,
        transport=transport,
        token_transport=token_transport,
        headless=headless,
    )


def build_stockx_config(config_data: Mapping[str, object]) -> StockXConfig:
    """Build and validate a :class:`StockXConfig` from a plain mapping."""
    data: dict[str, object] = {"base_url": DEFAULT_BASE_URL}
    data.update(config_data)
    config = StockXConfig.from_dict(data)
    assert isinstance(config, StockXConfig)
    return config


# Register the StockX builders so the provider can be configured and built by
# name from config + environment credentials.
register_live_provider_config_builder(StockXProvider.name, build_stockx_config)
register_live_provider_env_builder(StockXProvider.name, build_stockx_provider_from_env)

# Keep the public module logger at the warning level by default to avoid noisy
# browser-auth logs in normal scans.
logging.getLogger("browser_auth").setLevel(logging.WARNING)
