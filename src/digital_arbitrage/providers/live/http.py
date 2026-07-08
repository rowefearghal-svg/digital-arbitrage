"""HTTP client abstraction for live providers.

Three layers, each independently testable:

* :class:`HttpRequest` / :class:`HttpResponse` - immutable request/response DTOs.
* :class:`Transport` - a single raw round trip. :class:`UrllibTransport` is the
  stdlib implementation; tests substitute a fake transport (no network).
* :class:`HttpClient` - composes a transport with a :class:`RetryPolicy`, an
  optional :class:`TokenBucketRateLimiter`, default headers, and structured
  logging. This is what providers use.

Standard library only (``urllib``); no third-party HTTP dependency.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from .config import LiveProviderConfig
from .errors import (
    ProviderConnectionError,
    ProviderError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from .logging_utils import format_fields, get_logger
from .rate_limit import TokenBucketRateLimiter
from .retry import run_with_retries

if TYPE_CHECKING:
    from .auth import AuthProvider


@dataclass(frozen=True, slots=True)
class HttpRequest:
    """An immutable HTTP request specification."""

    method: str
    url: str
    params: Mapping[str, str] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None
    timeout: float | None = None

    def full_url(self) -> str:
        """The URL with ``params`` encoded onto the query string."""
        if not self.params:
            return self.url
        query = urllib.parse.urlencode(dict(self.params))
        sep = "&" if urllib.parse.urlsplit(self.url).query else "?"
        return f"{self.url}{sep}{query}"


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """An immutable HTTP response."""

    status: int
    headers: Mapping[str, str]
    body: bytes
    url: str

    @property
    def ok(self) -> bool:
        """Whether the status is a 2xx success."""
        return 200 <= self.status < 300

    @property
    def text(self) -> str:
        """Body decoded as UTF-8 (replacing undecodable bytes)."""
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Parse the body as JSON (raises on invalid JSON)."""
        return json.loads(self.body or b"null")


class Transport(ABC):
    """A single HTTP round trip. Implementations must map failures to
    :class:`~digital_arbitrage.providers.live.errors.ProviderError`."""

    @abstractmethod
    def send(self, request: HttpRequest) -> HttpResponse:
        """Perform ``request`` once and return the response."""


def _lower_headers(items: Iterable[tuple[str, str]] | None) -> dict[str, str]:
    if not items:
        return {}
    return {str(k).lower(): str(v) for k, v in items}


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class UrllibTransport(Transport):
    """:class:`Transport` backed by the standard library ``urllib``."""

    def __init__(self, *, provider: str | None = None) -> None:
        self._provider = provider

    def send(self, request: HttpRequest) -> HttpResponse:
        url = request.full_url()
        req = urllib.request.Request(
            url,
            data=request.body,
            method=request.method.upper(),
        )
        for key, value in request.headers.items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=request.timeout) as resp:
                body = resp.read()
                return HttpResponse(
                    status=resp.status,
                    headers=_lower_headers(resp.headers.items()),
                    body=body,
                    url=resp.geturl(),
                )
        except urllib.error.HTTPError as err:
            body = err.read()
            headers = _lower_headers(err.headers.items() if err.headers else None)
            if err.code == 429:
                raise ProviderRateLimitError(
                    "rate limited by provider (HTTP 429)",
                    provider=self._provider,
                    url=url,
                    body=body,
                    retry_after=_parse_retry_after(headers.get("retry-after")),
                ) from err
            raise ProviderHTTPError(
                f"provider returned HTTP {err.code}",
                status_code=err.code,
                provider=self._provider,
                url=url,
                body=body,
            ) from err
        except TimeoutError as err:
            raise ProviderTimeoutError(
                "request timed out", provider=self._provider, url=url
            ) from err
        except urllib.error.URLError as err:
            if isinstance(err.reason, TimeoutError):
                raise ProviderTimeoutError(
                    "request timed out", provider=self._provider, url=url
                ) from err
            raise ProviderConnectionError(
                f"connection failed: {err.reason}", provider=self._provider, url=url
            ) from err


def resolve_url(base_url: str, path: str) -> str:
    """Join ``path`` onto ``base_url`` (absolute ``path`` overrides the base)."""
    if not path:
        return base_url
    return urllib.parse.urljoin(base_url, path)


class HttpClient:
    """Resilient HTTP client: transport + retries + rate limiting + logging."""

    def __init__(
        self,
        config: LiveProviderConfig,
        *,
        provider: str | None = None,
        transport: Transport | None = None,
        auth: AuthProvider | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        random_fn: Callable[[], float] | None = None,
    ) -> None:
        self._config = config
        self._provider = provider
        self._transport = transport or UrllibTransport(provider=provider)
        self._auth = auth
        self._sleep = sleep
        self._random_fn = random_fn
        self._log = get_logger(provider or "http")
        if rate_limiter is not None:
            self._rate_limiter: TokenBucketRateLimiter | None = rate_limiter
        elif config.rate_limit_per_second is not None:
            self._rate_limiter = TokenBucketRateLimiter(
                config.rate_limit_per_second,
                capacity=config.rate_limit_burst,
                monotonic=monotonic,
                sleep=sleep,
            )
        else:
            self._rate_limiter = None

    @property
    def config(self) -> LiveProviderConfig:
        return self._config

    def _authorization(self) -> str | None:
        """Resolve the ``Authorization`` header value for a request.

        An injected :class:`AuthProvider` takes precedence; otherwise fall back
        to the static ``config.api_key`` (preserving pre-auth behaviour).
        """
        if self._auth is not None:
            return self._auth.authorization()
        if self._config.api_key:
            return f"Bearer {self._config.api_key}"
        return None

    def _default_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": self._config.user_agent,
            "Accept": "application/json",
        }
        authorization = self._authorization()
        if authorization:
            headers["Authorization"] = authorization
        headers.update(self._config.extra_headers)
        return headers

    def send(self, request: HttpRequest) -> HttpResponse:
        """Send ``request`` with default headers, retries, and rate limiting."""
        headers = self._default_headers()
        headers.update(request.headers)
        timeout = request.timeout if request.timeout is not None else self._config.timeout
        prepared = replace(request, headers=headers, timeout=timeout)

        def _operation() -> HttpResponse:
            if self._rate_limiter is not None:
                self._rate_limiter.acquire()
            started = time.monotonic()
            response = self._transport.send(prepared)
            elapsed_ms = round((time.monotonic() - started) * 1000, 1)
            self._log.info(
                "http_request %s",
                format_fields(
                    provider=self._provider,
                    method=prepared.method.upper(),
                    url=prepared.full_url(),
                    status=response.status,
                    elapsed_ms=elapsed_ms,
                ),
            )
            return response

        kwargs: dict[str, Any] = {"sleep": self._sleep, "on_retry": self._log_retry}
        if self._random_fn is not None:
            kwargs["random_fn"] = self._random_fn
        return run_with_retries(_operation, self._config.retry, **kwargs)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        body: bytes | None = None,
    ) -> HttpResponse:
        """Build a request against ``base_url + path`` and :meth:`send` it."""
        request = HttpRequest(
            method=method,
            url=resolve_url(self._config.base_url, path),
            params=dict(params or {}),
            headers=dict(headers or {}),
            body=body,
        )
        return self.send(request)

    def get(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        """Convenience for a GET request."""
        return self.request("GET", path, params=params, headers=headers)

    def _log_retry(self, attempt: int, error: ProviderError, delay: float) -> None:
        self._log.warning(
            "http_retry %s",
            format_fields(
                provider=self._provider,
                attempt=attempt,
                error=type(error).__name__,
                delay_s=round(delay, 3),
            ),
        )
