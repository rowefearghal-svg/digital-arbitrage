"""StockX provider credentials, loaded from the environment.

StockX's API is authenticated with an application **API key** plus an OAuth 2.0
**client id / client secret** pair. Following the same convention as the eBay
Browse provider, these secrets live *only* in the environment - never in a
config file, the repository, or CI - and are read here into a small, immutable
:class:`StockXCredentials` container.

Credentials come only from the ``STOCKX_API_KEY`` / ``STOCKX_CLIENT_ID`` /
``STOCKX_CLIENT_SECRET`` environment variables. Missing values fail fast with a
:class:`ProviderConfigError`; the values themselves are never logged.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from .errors import ProviderConfigError

#: Registry/config name for the (future) StockX provider.
PROVIDER_NAME = "stockx"

#: Environment variables the StockX application credentials are read from.
API_KEY_ENV = "STOCKX_API_KEY"
CLIENT_ID_ENV = "STOCKX_CLIENT_ID"
CLIENT_SECRET_ENV = "STOCKX_CLIENT_SECRET"

#: All credential env vars, in declaration order (used for error messages).
CREDENTIAL_ENV_VARS = (API_KEY_ENV, CLIENT_ID_ENV, CLIENT_SECRET_ENV)


@dataclass(frozen=True, slots=True)
class StockXCredentials:
    """Immutable StockX application credentials read from the environment.

    Use :meth:`from_env` to load them; direct construction is fine for tests.
    ``repr`` is customised so secrets never leak into logs or tracebacks.
    """

    api_key: str
    client_id: str
    client_secret: str

    def __post_init__(self) -> None:
        missing = [
            name
            for name, value in (
                (API_KEY_ENV, self.api_key),
                (CLIENT_ID_ENV, self.client_id),
                (CLIENT_SECRET_ENV, self.client_secret),
            )
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise ProviderConfigError(
                f"{joined} must be set",
                provider=PROVIDER_NAME,
            )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> StockXCredentials:
        """Load credentials from ``env`` (defaulting to :data:`os.environ`).

        All three variables are required; any missing (or empty) value raises a
        :class:`ProviderConfigError` naming the offending variable(s).
        """
        source = os.environ if env is None else env
        return cls(
            api_key=source.get(API_KEY_ENV, ""),
            client_id=source.get(CLIENT_ID_ENV, ""),
            client_secret=source.get(CLIENT_SECRET_ENV, ""),
        )

    def __repr__(self) -> str:  # pragma: no cover - trivial, secrets-safe
        return "StockXCredentials(api_key=***, client_id=***, client_secret=***)"
