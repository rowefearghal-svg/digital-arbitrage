"""Smoke tests for the bootstrap.

These do not test any arbitrage logic (there is none yet); they simply confirm
the package is importable and exposes a version, so CI has something to run.
"""

import digital_arbitrage


def test_package_imports() -> None:
    assert digital_arbitrage is not None


def test_version_is_a_nonempty_string() -> None:
    assert isinstance(digital_arbitrage.__version__, str)
    assert digital_arbitrage.__version__
