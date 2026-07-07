"""Provider-specific configuration for live marketplaces.

:class:`LiveProviderConfig` holds everything a live provider needs to talk to a
real endpoint: base URL, credentials, timeouts, pagination sizing, rate limits,
and a nested :class:`RetryPolicy`. Validation happens at construction and raises
:class:`ProviderConfigError` with a clear message. ``from_dict`` maps a plain
(e.g. TOML-parsed) mapping onto the dataclass.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field, fields
from typing import Any

from .errors import ProviderConfigError
from .retry import RetryPolicy

_ALLOWED_SCHEMES = frozenset({"http", "https"})


@dataclass(slots=True)
class LiveProviderConfig:
    """Runtime configuration for a single live provider."""

    base_url: str
    api_key: str | None = None
    timeout: float = 10.0
    page_size: int = 20
    max_results: int = 50
    user_agent: str = "digital-arbitrage/0.0.1"
    default_currency: str = "EUR"
    rate_limit_per_second: float | None = None
    rate_limit_burst: int = 1
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    extra_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlsplit(self.base_url)
        if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
            raise ProviderConfigError(f"base_url must be an http(s) URL, got {self.base_url!r}")
        if self.timeout <= 0:
            raise ProviderConfigError("timeout must be positive")
        if self.page_size <= 0:
            raise ProviderConfigError("page_size must be positive")
        if self.max_results <= 0:
            raise ProviderConfigError("max_results must be positive")
        if self.rate_limit_per_second is not None and self.rate_limit_per_second <= 0:
            raise ProviderConfigError("rate_limit_per_second must be positive when set")
        if self.rate_limit_burst < 1:
            raise ProviderConfigError("rate_limit_burst must be >= 1")
        if not isinstance(self.retry, RetryPolicy):
            raise ProviderConfigError("retry must be a RetryPolicy")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LiveProviderConfig:
        """Build a config from a mapping, mapping a nested ``retry`` table.

        Unknown keys are rejected so typos surface immediately.
        """
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            joined = ", ".join(sorted(unknown))
            raise ProviderConfigError(f"unknown config key(s): {joined}")
        payload = dict(data)
        retry = payload.get("retry")
        if isinstance(retry, dict):
            retry_known = {f.name for f in fields(RetryPolicy)}
            retry_unknown = set(retry) - retry_known
            if retry_unknown:
                joined = ", ".join(sorted(retry_unknown))
                raise ProviderConfigError(f"unknown retry config key(s): {joined}")
            retry_payload = dict(retry)
            if "retry_on_status" in retry_payload:
                retry_payload["retry_on_status"] = frozenset(retry_payload["retry_on_status"])
            try:
                payload["retry"] = RetryPolicy(**retry_payload)
            except (TypeError, ValueError) as err:
                raise ProviderConfigError(f"invalid retry config: {err}") from err
        try:
            return cls(**payload)
        except (TypeError, ValueError) as err:
            raise ProviderConfigError(str(err)) from err
