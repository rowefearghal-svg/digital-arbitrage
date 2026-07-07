"""Provider frameworks for the digital-arbitrage engine.

This package hosts the *live* provider framework - production-quality building
blocks (HTTP client, retries, rate limiting, pagination, capability metadata,
typed errors) for integrating real marketplaces.

No scraping or live network integration ships here yet: this sprint delivers the
reusable infrastructure only. The existing **mocked** providers used by the
scanner continue to live in
:mod:`digital_arbitrage.product_scanner.providers` and are unchanged.
"""

from __future__ import annotations

from .live import (
    LIVE_PROVIDER_REGISTRY,
    AuthProvider,
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
    create_live_provider,
    paginate,
    register_live_provider,
)

__all__ = [
    "LIVE_PROVIDER_REGISTRY",
    "AuthProvider",
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
    "create_live_provider",
    "paginate",
    "register_live_provider",
]
