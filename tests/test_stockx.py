"""Tests for StockX credentials loaded from the environment."""

from __future__ import annotations

import pytest

from digital_arbitrage.providers.live import ProviderConfigError, StockXCredentials


def _env() -> dict[str, str]:
    return {
        "STOCKX_API_KEY": "key",
        "STOCKX_CLIENT_ID": "cid",
        "STOCKX_CLIENT_SECRET": "secret",
    }


def test_from_env_reads_credentials() -> None:
    creds = StockXCredentials.from_env(_env())
    assert creds.api_key == "key"
    assert creds.client_id == "cid"
    assert creds.client_secret == "secret"


def test_from_env_missing_all_fails() -> None:
    with pytest.raises(ProviderConfigError, match="STOCKX_API_KEY"):
        StockXCredentials.from_env({})


@pytest.mark.parametrize(
    "missing",
    ["STOCKX_API_KEY", "STOCKX_CLIENT_ID", "STOCKX_CLIENT_SECRET"],
)
def test_from_env_missing_one_names_it(missing: str) -> None:
    env = _env()
    del env[missing]
    with pytest.raises(ProviderConfigError, match=missing):
        StockXCredentials.from_env(env)


def test_from_env_uses_os_environ_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in _env().items():
        monkeypatch.setenv(name, value)
    creds = StockXCredentials.from_env()
    assert creds.client_id == "cid"


def test_repr_hides_secrets() -> None:
    text = repr(StockXCredentials.from_env(_env()))
    # The secret *values* must not leak (field names may contain "secret"/"key").
    assert "cid" not in text
    assert text.count("***") == 3
