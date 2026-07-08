"""Live-provider framework: production-quality building blocks for real
marketplace integrations.

The reusable infrastructure handles HTTP, retries with exponential backoff, rate
limiting, pagination, capability metadata, typed errors, pluggable auth, and
structured logging - so a concrete provider stays small and declarative. The
first real integration, :class:`EbayBrowseProvider` (read-only eBay Browse API),
ships here; add another marketplace by subclassing :class:`LiveProvider` and
implementing ``build_request`` / ``parse_response``.

**No scraping, standard library only.** Automated tests never make live calls -
a fake :class:`Transport` is injected instead.

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

from .auth import (
    AuthProvider,
    NoAuthProvider,
    OAuthClientCredentialsAuthProvider,
    StaticBearerTokenAuthProvider,
)
from .base import LiveProvider
from .capabilities import ProviderCapabilities
from .config import LiveProviderConfig
from .ebay_browse import (
    DEFAULT_BASE_URL,
    DEFAULT_OAUTH_SCOPE,
    DEFAULT_OAUTH_TOKEN_URL,
    EbayBrowseConfig,
    EbayBrowseProvider,
    build_ebay_browse_config,
    build_ebay_browse_provider,
    build_ebay_browse_provider_from_env,
)
from .errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderConnectionError,
    ProviderError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from .factory import (
    LIVE_PROVIDER_CONFIG_BUILDERS,
    LIVE_PROVIDER_ENV_BUILDERS,
    LIVE_PROVIDER_REGISTRY,
    build_live_provider_config,
    build_live_provider_from_env,
    create_live_provider,
    register_live_provider,
    register_live_provider_config_builder,
    register_live_provider_env_builder,
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
from .scanning import LiveProviderSetting, build_scanner_from_config
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
    "DEFAULT_BASE_URL",
    "DEFAULT_OAUTH_SCOPE",
    "DEFAULT_OAUTH_TOKEN_URL",
    "DEFAULT_RETRY_STATUS",
    "LIVE_PROVIDER_CONFIG_BUILDERS",
    "LIVE_PROVIDER_ENV_BUILDERS",
    "LIVE_PROVIDER_REGISTRY",
    "AuthProvider",
    "EbayBrowseConfig",
    "EbayBrowseProvider",
    "HttpClient",
    "HttpRequest",
    "HttpResponse",
    "LiveProvider",
    "LiveProviderConfig",
    "LiveProviderSetting",
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
    "build_ebay_browse_config",
    "build_ebay_browse_provider",
    "build_ebay_browse_provider_from_env",
    "build_live_provider_config",
    "build_live_provider_from_env",
    "build_scanner_from_config",
    "create_live_provider",
    "register_live_provider",
    "register_live_provider_config_builder",
    "register_live_provider_env_builder",
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
