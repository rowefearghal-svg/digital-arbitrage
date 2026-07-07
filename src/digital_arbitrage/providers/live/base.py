"""Base class for live marketplace providers.

:class:`LiveProvider` is a *strict superset* of the mocked
:class:`~digital_arbitrage.product_scanner.providers.base.Provider`: it subclasses
it, so a live provider is drop-in compatible with the existing scanner/registry,
while adding the production concerns a real integration needs - an
:class:`HttpClient` (retries + rate limiting), pagination, capability metadata,
typed errors, and structured logging.

Subclasses implement two small, declarative hooks:

* :meth:`build_request` - turn a query + page into an :class:`HttpRequest`.
* :meth:`parse_response` - turn an :class:`HttpResponse` into a page of
  :class:`Listing` objects (using :mod:`.validation`).

Everything else - request execution, resilience, pagination, and result
capping - is handled here. No concrete live provider (i.e. real scraping or API
access) ships in this sprint; this is the reusable framework only.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import ClassVar

from ...product_scanner.models import Listing
from ...product_scanner.providers.base import Provider
from .capabilities import ProviderCapabilities
from .config import LiveProviderConfig
from .errors import ProviderConfigError
from .http import HttpClient, HttpRequest, HttpResponse
from .logging_utils import format_fields, get_logger
from .pagination import Page, paginate


class LiveProvider(Provider):
    """Enterprise base for HTTP-backed marketplace providers."""

    #: Static feature/limit description. Subclasses override with real values.
    capabilities: ClassVar[ProviderCapabilities] = ProviderCapabilities()

    def __init__(
        self,
        config: LiveProviderConfig,
        *,
        http_client: HttpClient | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._live_log = get_logger(self.name)
        if self.capabilities.requires_api_key and not config.api_key:
            raise ProviderConfigError(
                "provider requires an api_key but none was configured",
                provider=self.name,
            )
        self._client = http_client or HttpClient(config, provider=self.name)

    @property
    def config(self) -> LiveProviderConfig:
        """The provider's configuration."""
        return self._config

    @property
    def http(self) -> HttpClient:
        """The resilient HTTP client used for requests."""
        return self._client

    @classmethod
    def get_capabilities(cls) -> ProviderCapabilities:
        """Return this provider's capability metadata."""
        return cls.capabilities

    @abstractmethod
    def build_request(self, query: str, *, page: int, page_size: int) -> HttpRequest:
        """Build the HTTP request for ``page`` (1-based) of ``query``."""

    @abstractmethod
    def parse_response(self, response: HttpResponse, *, query: str) -> Page[Listing]:
        """Parse a raw response into a :class:`Page` of listings."""

    def fetch(self, query: str, *, limit: int) -> list[Listing]:
        """Fetch up to ``limit`` listings for ``query`` (paginating as needed).

        Implements the :class:`Provider` contract. ``limit`` is clamped by the
        provider's configured ``max_results`` and its capability ``max_results``.
        Pagination is used only when the provider advertises support for it.
        """
        max_results = min(limit, self._config.max_results)
        if self.capabilities.max_results is not None:
            max_results = min(max_results, self.capabilities.max_results)
        max_results = max(max_results, 1)

        page_size = min(self._config.page_size, self.capabilities.max_page_size)
        max_pages = 1 if not self.capabilities.supports_pagination else None

        self._live_log.info(
            "provider_fetch %s",
            format_fields(
                provider=self.name,
                query=query,
                max_results=max_results,
                page_size=page_size,
            ),
        )

        def fetch_page(page_number: int) -> Page[Listing]:
            request = self.build_request(query, page=page_number, page_size=page_size)
            response = self._client.send(request)
            return self.parse_response(response, query=query)

        return paginate(fetch_page, max_results=max_results, max_pages=max_pages)
