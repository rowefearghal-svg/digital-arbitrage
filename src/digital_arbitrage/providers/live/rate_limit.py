"""Client-side rate limiting via a token bucket.

A :class:`TokenBucketRateLimiter` smooths outbound request rate to stay within a
provider's quota. Tokens refill continuously at ``rate`` per second up to
``capacity`` (the burst allowance). The monotonic clock and sleep function are
injectable so the limiter can be tested deterministically without real waiting.
Thread-safe: a lock guards the bucket so concurrent callers share the quota.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class TokenBucketRateLimiter:
    """Blocking token-bucket limiter.

    :param rate: Sustained tokens (requests) granted per second.
    :param capacity: Maximum tokens that can accumulate (burst); defaults to 1.
    """

    def __init__(
        self,
        rate: float,
        *,
        capacity: int = 1,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._rate = float(rate)
        self._capacity = float(capacity)
        self._monotonic = monotonic
        self._sleep = sleep
        self._tokens = float(capacity)
        self._updated = monotonic()
        self._lock = threading.Lock()

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def capacity(self) -> float:
        return self._capacity

    def _refill(self, now: float) -> None:
        elapsed = now - self._updated
        if elapsed > 0:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._updated = now

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Consume ``tokens`` without blocking; return ``False`` if unavailable."""
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        if tokens > self._capacity:
            raise ValueError("tokens requested exceeds bucket capacity")
        with self._lock:
            self._refill(self._monotonic())
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def acquire(self, tokens: float = 1.0) -> float:
        """Block until ``tokens`` are available, then consume them.

        Returns the total time (seconds) spent waiting - ``0.0`` when tokens
        were immediately available.
        """
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        if tokens > self._capacity:
            raise ValueError("tokens requested exceeds bucket capacity")
        waited = 0.0
        while True:
            with self._lock:
                self._refill(self._monotonic())
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return waited
                deficit = tokens - self._tokens
                wait = deficit / self._rate
            self._sleep(wait)
            waited += wait
