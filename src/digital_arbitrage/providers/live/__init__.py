"""Live-provider framework: production-quality building blocks for real
marketplace integrations.

This sprint delivers the reusable infrastructure only - **no scraping, no live
API calls, no concrete live provider**. Subclass :class:`LiveProvider` and
implement ``build_request`` / ``parse_response`` to add a real marketplace; the
base handles HTTP, retries with exponential backoff, rate limiting, pagination,
capability metadata, typed errors, and structured logging.

Quick shape::

    class MyProvider(LiveProvider):
        name = "my_market"
        capabilities = ProviderCapabilities(supports_pagination=True)

        def build_request(self, query, *, page, page_size): ...
        def parse_response(self, response, *, query): ...

    provider = MyProvider(LiveProviderConfig(base_url="https://api.example.com"))
    listings = provider.search("rtx 4090", limit=25)
"""

from __future__ import annotations

from .base import LiveProvider
from .capabilities import ProviderCapabilities
from .config import LiveProviderConfig
from .errors import (
    ProviderConfigError,
    ProviderConnectionError,
    ProviderError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from .http import (
    HttpClient,
    HttpRequest,
    HttpResponse,
    Transport,
    UrllibTransport,
    resolve_url,
)
from .logging_utils import format_fields, get_logger
from .pagination import Page, paginate
from .rate_limit import TokenBucketRateLimiter
from .retry import DEFAULT_RETRY_STATUS, RetryPolicy, run_with_retries
from .validation import (
    ensure_list,
    ensure_mapping,
    ensure_type,
    optional,
    parse_json,
    require,
    require_number,
)

__all__ = [
    "DEFAULT_RETRY_STATUS",
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
    "ensure_list",
    "ensure_mapping",
    "ensure_type",
    "format_fields",
    "get_logger",
    "optional",
    "paginate",
    "parse_json",
    "require",
    "require_number",
    "resolve_url",
    "run_with_retries",
]
