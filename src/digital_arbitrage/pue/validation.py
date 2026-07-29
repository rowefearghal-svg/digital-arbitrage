"""Deep immutability helpers and explicit validation utilities.

The PUE avoids a schema library in v0.1 (ADR: dataclasses first). Instead it
uses explicit constructors/validation functions plus a small recursive
freeze/thaw pair so ``Mapping``-typed dataclass fields are defensively
immutable (spec section 7.4 and "Implementation choices fixed for Sprint 1").
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any


class PueValidationError(ValueError):
    """Raised when a PUE object or input fails explicit validation."""


def freeze_value(value: Any) -> Any:
    """Recursively freeze ``value`` into an immutable equivalent.

    ``dict`` -> ``MappingProxyType`` (recursively frozen values); ``list``/
    ``set`` -> ``tuple`` (recursively frozen items). Strings, numbers, bools,
    ``None`` and already-immutable objects pass through unchanged.
    """
    if isinstance(value, Mapping):
        return freeze_mapping(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(freeze_value(item) for item in value)
    return value


def freeze_mapping(mapping: Mapping[Any, Any]) -> Mapping[Any, Any]:
    """Recursively freeze a mapping into a read-only ``MappingProxyType``."""
    return MappingProxyType({key: freeze_value(val) for key, val in mapping.items()})


def thaw_value(value: Any) -> Any:
    """Recursively convert a frozen value back into plain mutable JSON types.

    ``MappingProxyType``/``Mapping`` -> ``dict``; ``tuple`` -> ``list``.
    Used only for serialization; the reasoning objects themselves remain
    frozen.
    """
    if isinstance(value, Mapping):
        return {key: thaw_value(val) for key, val in value.items()}
    if isinstance(value, (tuple, list)):
        return [thaw_value(item) for item in value]
    return value


def require_non_empty_str(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PueValidationError(f"{field_name} must be a non-empty string")
    return value


def require_in_range(
    value: float, *, field_name: str, low: float = 0.0, high: float = 1.0
) -> float:
    if not (low <= value <= high):
        raise PueValidationError(f"{field_name} must be within [{low}, {high}], got {value}")
    return value


def require_non_negative_int(value: int, *, field_name: str) -> int:
    if value < 0:
        raise PueValidationError(f"{field_name} must be >= 0, got {value}")
    return value


def require_tuple(value: Sequence[Any], *, field_name: str) -> tuple[Any, ...]:
    if not isinstance(value, (tuple, list)):
        raise PueValidationError(f"{field_name} must be a sequence")
    return tuple(value)
