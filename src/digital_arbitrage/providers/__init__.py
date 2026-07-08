"""Provider frameworks for the digital-arbitrage engine.

This package hosts the *live* provider framework - production-quality building
blocks (HTTP client, retries, rate limiting, pagination, capability metadata,
typed errors, pluggable auth) for integrating real marketplaces - and the first
real integration, :class:`EbayBrowseProvider` (read-only eBay Browse API).

Standard library only, no scraping. The existing **mocked** providers used by the
scanner continue to live in
:mod:`digital_arbitrage.product_scanner.providers` and are unchanged.
"""

from __future__ import annotations

from .live import (
    DEFAULT_OAUTH_SCOPE,
    DEFAULT_OAUTH_TOKEN_URL,
    LIVE_PROVIDER_REGISTRY,
    AuthProvider,
    EbayBrowseConfig,
    EbayBrowseProvider,
    HttpClient,
    HttpRequest,
    HttpResponse,
    LiveProvider,
    LiveProviderConfig,
    NoAuthProvider,
    OAuthClientCredentialsAuthProvider,
    Page,
    ProviderAuthError,
    ProviderCapabilities,
    ProviderConfigError,
    ProviderConnectionError,
    ProviderError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderTimeoutError,
    RetryPolicy,
    StaticBearerTokenAuthProvider,
    TokenBucketRateLimiter,
    Transport,
    UrllibTransport,
    build_ebay_browse_provider,
    build_ebay_browse_provider_from_env,
    create_live_provider,
    paginate,
    register_live_provider,
)

__all__ = [
    "DEFAULT_OAUTH_SCOPE",
    "DEFAULT_OAUTH_TOKEN_URL",
    "LIVE_PROVIDER_REGISTRY",
    "AuthProvider",
    "EbayBrowseConfig",
    "EbayBrowseProvider",
    "HttpClient",
    "HttpRequest",
    "HttpResponse",
    "LiveProvider",
    "LiveProviderConfig",
    "NoAuthProvider",
    "OAuthClientCredentialsAuthProvider",
    "Page",
    "ProviderAuthError",
    "ProviderCapabilities",
    "ProviderConfigError",
    "ProviderConnectionError",
    "ProviderError",
    "ProviderHTTPError",
    "ProviderRateLimitError",
    "ProviderRequestError",
    "ProviderResponseError",
    "ProviderTimeoutError",
    "RetryPolicy",
    "StaticBearerTokenAuthProvider",
    "TokenBucketRateLimiter",
    "Transport",
    "UrllibTransport",
    "build_ebay_browse_provider",
    "build_ebay_browse_provider_from_env",
    "create_live_provider",
    "paginate",
    "register_live_provider",
]
