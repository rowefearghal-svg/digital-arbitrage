"""Logging helpers for the product scanner.

A tiny wrapper around the standard library so every module logs consistently.
Application code should call :func:`get_logger`; :func:`configure_logging` is a
convenience for entry points / tests.
"""

from __future__ import annotations

import logging

_LOGGER_NAMESPACE = "digital_arbitrage.product_scanner"
_DEFAULT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging(level: int | str = logging.INFO) -> None:
    """Configure the scanner's logger namespace.

    Idempotent: a handler is attached only once so repeated calls (e.g. in
    tests) do not duplicate log output. Does not touch the root logger.
    """
    logger = logging.getLogger(_LOGGER_NAMESPACE)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        logger.addHandler(handler)
    logger.propagate = False


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the scanner namespace.

    ``get_logger("ebay")`` -> ``digital_arbitrage.product_scanner.ebay``.
    """
    if not name:
        return logging.getLogger(_LOGGER_NAMESPACE)
    return logging.getLogger(f"{_LOGGER_NAMESPACE}.{name}")
