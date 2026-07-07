"""Retry policy with exponential backoff.

:class:`RetryPolicy` is pure, deterministic *configuration* - it decides whether
an error is retryable and computes backoff delays. :func:`run_with_retries`
applies a policy around an operation, sleeping between attempts. Both the sleep
and jitter sources are injectable so tests stay fast and deterministic.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from .errors import (
    ProviderConnectionError,
    ProviderError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderTimeoutError,
)

#: Statuses that are safe to retry by default (transient server/limit errors).
DEFAULT_RETRY_STATUS: frozenset[int] = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How many times, and how long, to wait before retrying a failed request."""

    max_attempts: int = 3
    backoff_base: float = 0.5
    backoff_factor: float = 2.0
    max_backoff: float = 30.0
    jitter: bool = True
    retry_on_status: frozenset[int] = DEFAULT_RETRY_STATUS

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.backoff_base < 0:
            raise ValueError("backoff_base must be >= 0")
        if self.backoff_factor < 1:
            raise ValueError("backoff_factor must be >= 1")
        if self.max_backoff < 0:
            raise ValueError("max_backoff must be >= 0")

    def is_retryable(self, exc: ProviderError) -> bool:
        """Return whether ``exc`` is worth retrying under this policy."""
        if isinstance(exc, ProviderHTTPError):
            return exc.status_code in self.retry_on_status
        return isinstance(exc, ProviderTimeoutError | ProviderConnectionError)

    def backoff_delay(
        self,
        attempt: int,
        *,
        random_fn: Callable[[], float] = random.random,
    ) -> float:
        """Delay in seconds to wait *after* a failed ``attempt`` (1-based).

        Exponential: ``backoff_base * backoff_factor**(attempt - 1)``, capped at
        ``max_backoff``. With ``jitter`` the delay is scaled into
        ``[0.5, 1.0] * delay`` (equal jitter) to avoid thundering herds.
        """
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        raw = self.backoff_base * (self.backoff_factor ** (attempt - 1))
        delay = min(self.max_backoff, raw)
        if self.jitter:
            delay = delay * (0.5 + 0.5 * random_fn())
        return delay


def run_with_retries[T](
    operation: Callable[[], T],
    policy: RetryPolicy,
    *,
    on_retry: Callable[[int, ProviderError, float], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    random_fn: Callable[[], float] = random.random,
) -> T:
    """Run ``operation``, retrying retryable :class:`ProviderError`s per ``policy``.

    Between attempts the runner sleeps for the policy's backoff delay; a
    :class:`ProviderRateLimitError` with a ``retry_after`` hint raises that floor.
    ``on_retry(attempt, error, delay)`` is invoked before each sleep (for
    logging). The final error is re-raised with its ``attempts`` count set.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return operation()
        except ProviderError as exc:
            give_up = attempt >= policy.max_attempts or not policy.is_retryable(exc)
            if give_up:
                if isinstance(exc, ProviderRequestError):
                    exc.attempts = attempt
                raise
            delay = policy.backoff_delay(attempt, random_fn=random_fn)
            if isinstance(exc, ProviderRateLimitError) and exc.retry_after is not None:
                delay = max(delay, exc.retry_after)
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            sleep(delay)
