"""Response validation helpers.

Turn untrusted, loosely-typed JSON into the shapes a provider expects, failing
fast with a clear :class:`ProviderResponseError` (context-prefixed) when the
payload does not match. Keeping this here means each provider's
``parse_response`` stays a short, declarative mapping instead of a maze of
``isinstance`` checks.
"""

from __future__ import annotations

import json

from .errors import ProviderResponseError
from .http import HttpResponse


def parse_json(response: HttpResponse, *, provider: str | None = None) -> object:
    """Parse ``response`` body as JSON or raise :class:`ProviderResponseError`."""
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as err:
        raise ProviderResponseError(
            f"response body is not valid JSON: {err}", provider=provider
        ) from err


def ensure_type[T](
    value: object,
    expected: type[T],
    *,
    context: str,
    provider: str | None = None,
) -> T:
    """Assert ``value`` is an instance of ``expected``; return it narrowed."""
    if isinstance(value, bool) and expected is not bool:
        raise ProviderResponseError(
            f"{context}: expected {expected.__name__}, got bool", provider=provider
        )
    if not isinstance(value, expected):
        raise ProviderResponseError(
            f"{context}: expected {expected.__name__}, got {type(value).__name__}",
            provider=provider,
        )
    return value


def ensure_mapping(
    value: object, *, context: str = "response", provider: str | None = None
) -> dict[str, object]:
    """Assert ``value`` is a JSON object (dict)."""
    return ensure_type(value, dict, context=context, provider=provider)


def ensure_list(
    value: object, *, context: str = "response", provider: str | None = None
) -> list[object]:
    """Assert ``value`` is a JSON array (list)."""
    return ensure_type(value, list, context=context, provider=provider)


def require[T](
    mapping: dict[str, object],
    key: str,
    expected: type[T],
    *,
    context: str = "response",
    provider: str | None = None,
) -> T:
    """Return ``mapping[key]`` typed as ``expected`` or raise if missing/wrong."""
    if key not in mapping:
        raise ProviderResponseError(f"{context}: missing required field '{key}'", provider=provider)
    return ensure_type(mapping[key], expected, context=f"{context}.{key}", provider=provider)


def optional[T](
    mapping: dict[str, object],
    key: str,
    expected: type[T],
    *,
    default: T | None = None,
    context: str = "response",
    provider: str | None = None,
) -> T | None:
    """Return a typed optional field: ``default`` if absent or JSON ``null``."""
    if key not in mapping or mapping[key] is None:
        return default
    return ensure_type(mapping[key], expected, context=f"{context}.{key}", provider=provider)


def require_number(
    mapping: dict[str, object],
    key: str,
    *,
    context: str = "response",
    provider: str | None = None,
) -> float:
    """Return a required numeric field (int or float, never bool) as ``float``."""
    if key not in mapping:
        raise ProviderResponseError(f"{context}: missing required field '{key}'", provider=provider)
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ProviderResponseError(
            f"{context}.{key}: expected a number, got {type(value).__name__}",
            provider=provider,
        )
    return float(value)
