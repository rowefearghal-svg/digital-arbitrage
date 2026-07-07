"""Typed exception hierarchy for the live-provider framework.

Every failure mode has a distinct, catchable type so callers can react
precisely (e.g. back off on :class:`ProviderRateLimitError`, surface a
:class:`ProviderConfigError` to the operator, or drop a provider that keeps
raising :class:`ProviderResponseError`). The base :class:`ProviderError`
carries the offending provider name for structured logging.

::

    ProviderError
    +-- ProviderConfigError
    +-- ProviderRequestError
    |   +-- ProviderTimeoutError
    |   +-- ProviderConnectionError
    |   +-- ProviderHTTPError
    |       +-- ProviderRateLimitError
    +-- ProviderResponseError
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for every error raised by the live-provider framework."""

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider

    def __str__(self) -> str:
        if self.provider:
            return f"[{self.provider}] {self.message}"
        return self.message


class ProviderConfigError(ProviderError):
    """The provider is misconfigured (bad base URL, missing API key, ...).

    Raised at construction/validation time, never mid-request; it is not
    retryable and should surface to the operator.
    """


class ProviderRequestError(ProviderError):
    """Base for failures while performing an HTTP request."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        url: str | None = None,
        attempts: int = 0,
    ) -> None:
        super().__init__(message, provider=provider)
        self.url = url
        #: Number of attempts made before giving up (set by the retry runner).
        self.attempts = attempts


class ProviderTimeoutError(ProviderRequestError):
    """The request exceeded its configured timeout. Transient/retryable."""


class ProviderConnectionError(ProviderRequestError):
    """Transport-layer failure (DNS, connection refused/reset). Retryable."""


class ProviderHTTPError(ProviderRequestError):
    """The server returned a non-success (>= 400) status code."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        provider: str | None = None,
        url: str | None = None,
        attempts: int = 0,
        body: bytes | None = None,
    ) -> None:
        super().__init__(message, provider=provider, url=url, attempts=attempts)
        self.status_code = status_code
        self.body = body


class ProviderRateLimitError(ProviderHTTPError):
    """The server signalled rate limiting (HTTP 429).

    ``retry_after`` is the server-advised delay in seconds when supplied via the
    ``Retry-After`` header; the retry runner honours it as a floor.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        url: str | None = None,
        attempts: int = 0,
        body: bytes | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=429,
            provider=provider,
            url=url,
            attempts=attempts,
            body=body,
        )
        self.retry_after = retry_after


class ProviderResponseError(ProviderError):
    """The response body could not be parsed/validated into the expected shape.

    Not retryable: a well-formed error response won't fix itself on retry.
    """
