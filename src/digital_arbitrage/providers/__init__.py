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
    HttpClient,
    HttpRequest,
    HttpResponse,
    LiveProvider,
    LiveProviderConfig,
    Page,
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
    TokenBucketRateLimiter,
    Transport,
    UrllibTransport,
    paginate,
)

__all__ = [
    "HttpClient",
    "HttpRequest",
    "HttpResponse",
    "LiveProvider",
    "LiveProviderConfig",
    "Page",
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
    "TokenBucketRateLimiter",
    "Transport",
    "UrllibTransport",
    "paginate",
]
