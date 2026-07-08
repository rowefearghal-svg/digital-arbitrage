"""Integration tests for Sprint 25 - local live eBay scanning.

Every test is hermetic: a fake :class:`Transport` replays the committed,
sanitised eBay fixtures and OAuth credentials come from a fake ``env`` mapping,
so **no network call and no secret is ever used** (satisfying "no live API calls
in CI"). Coverage spans the scanner assembly that mixes mock + live providers,
the config/env builder registries, TOML ``[providers.<name>]`` parsing (including
enable/disable and validation), the ``arb scan --provider`` override, and a full
CLI run of ``arb scan "rtx 4090" --provider ebay_browse`` through a mocked
transport.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_arbitrage.pipeline.cli import _apply_provider_override, build_parser, main
from digital_arbitrage.pipeline.config_file import ConfigError, load_pipeline_config
from digital_arbitrage.pipeline.pipeline import PipelineConfig
from digital_arbitrage.product_scanner import ScannerConfig
from digital_arbitrage.product_scanner.providers.base import PROVIDER_REGISTRY
from digital_arbitrage.providers.live import (
    LIVE_PROVIDER_ENV_BUILDERS,
    EbayBrowseConfig,
    HttpRequest,
    HttpResponse,
    LiveProviderSetting,
    ProviderConfigError,
    Transport,
    build_ebay_browse_provider_from_env,
    build_live_provider_config,
    build_live_provider_from_env,
    build_scanner_from_config,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "ebay"
_ENV = {"EBAY_CLIENT_ID": "cid", "EBAY_CLIENT_SECRET": "secret"}
_LIVE_CONFIG = {"marketplace_id": "EBAY_IE", "page_size": 2, "max_results": 50}


def _fixture_bytes(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


def _response(status: int, body: bytes) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers={},
        body=body,
        url="https://api.ebay.com/buy/browse/v1/item_summary/search",
    )


class _SearchTransport(Transport):
    """Replays search fixtures keyed by the request's ``offset`` parameter."""

    def __init__(self, by_offset: dict[str, HttpResponse]) -> None:
        self._by_offset = by_offset
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        offset = dict(request.params).get("offset", "0")
        return self._by_offset[offset]


class _StaticTransport(Transport):
    """Returns the same response for every request (the OAuth token mint)."""

    def __init__(self, response: HttpResponse) -> None:
        self._response = response
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        return self._response


def _search_transport() -> _SearchTransport:
    return _SearchTransport(
        {
            "0": _response(200, _fixture_bytes("search_page1.json")),
            "2": _response(200, _fixture_bytes("search_page2.json")),
        }
    )


def _token_transport() -> _StaticTransport:
    return _StaticTransport(_response(200, _fixture_bytes("oauth_token.json")))


# --------------------------------------------------------------------------- #
# Scanner assembly: mock + live providers
# --------------------------------------------------------------------------- #


def test_scanner_runs_live_ebay_provider_with_mocked_transport() -> None:
    scanner = build_scanner_from_config(
        ScannerConfig(providers=["ebay_browse"], max_results_per_provider=10),
        {"ebay_browse": LiveProviderSetting(config=_LIVE_CONFIG)},
        env=_ENV,
        transport=_search_transport(),
        token_transport=_token_transport(),
    )
    listings = scanner.scan("rtx 4090")
    assert len(listings) == 4
    assert {listing.provider for listing in listings} == {"ebay_browse"}
    assert any("RTX 4090" in listing.title.upper() for listing in listings)


def test_scanner_mixes_mock_and_live_providers() -> None:
    scanner = build_scanner_from_config(
        ScannerConfig(providers=["ebay", "ebay_browse"], max_results_per_provider=10),
        {"ebay_browse": LiveProviderSetting(config=_LIVE_CONFIG)},
        env=_ENV,
        transport=_search_transport(),
        token_transport=_token_transport(),
    )
    providers = {listing.provider for listing in scanner.scan("rtx 4090")}
    assert providers == {"ebay", "ebay_browse"}


def test_disabled_live_provider_is_skipped_without_credentials() -> None:
    # Disabled: neither credentials nor a transport are required.
    scanner = build_scanner_from_config(
        ScannerConfig(providers=["ebay_browse"], max_results_per_provider=10),
        {"ebay_browse": LiveProviderSetting(enabled=False)},
    )
    assert scanner.providers == []
    assert scanner.scan("rtx 4090") == []


def test_live_provider_missing_credentials_fails_fast() -> None:
    with pytest.raises(ProviderConfigError, match="EBAY_CLIENT_ID"):
        build_scanner_from_config(
            ScannerConfig(providers=["ebay_browse"]),
            {"ebay_browse": LiveProviderSetting(config=_LIVE_CONFIG)},
            env={},
        )


def test_mock_only_scanner_unchanged() -> None:
    # No live settings, no env, no transport: the mock path is untouched.
    scanner = build_scanner_from_config(ScannerConfig(providers=["ebay"]))
    listings = scanner.scan("rtx 4090")
    assert listings
    assert {listing.provider for listing in listings} == {"ebay"}


def test_default_scanner_is_mock_only() -> None:
    scanner = build_scanner_from_config()
    assert {p.name for p in scanner.providers} == set(PROVIDER_REGISTRY)


# --------------------------------------------------------------------------- #
# Config / env builder registries
# --------------------------------------------------------------------------- #


def test_build_live_provider_config_defaults_base_url() -> None:
    config = build_live_provider_config("ebay_browse", {})
    assert isinstance(config, EbayBrowseConfig)
    assert config.base_url == "https://api.ebay.com"


def test_build_live_provider_config_validates() -> None:
    with pytest.raises(ProviderConfigError, match="marketplace_id"):
        build_live_provider_config("ebay_browse", {"marketplace_id": ""})
    with pytest.raises(ProviderConfigError, match="page_size"):
        build_live_provider_config("ebay_browse", {"page_size": 0})


def test_build_live_provider_from_env_unknown_name() -> None:
    with pytest.raises(KeyError, match="ebay_browse"):
        build_live_provider_from_env("nope", {}, env=_ENV)


def test_build_live_provider_from_env_builds_provider() -> None:
    provider = build_live_provider_from_env(
        "ebay_browse",
        _LIVE_CONFIG,
        env=_ENV,
        transport=_search_transport(),
        token_transport=_token_transport(),
    )
    assert provider.name == "ebay_browse"
    assert len(provider.search("rtx 4090", limit=4)) == 4


# --------------------------------------------------------------------------- #
# TOML config parsing: enable / disable live providers
# --------------------------------------------------------------------------- #


def _write_config(tmp_path: Path, body: str) -> str:
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_config_parses_live_provider(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
        [scanner]
        providers = ["ebay", "ebay_browse"]

        [providers.ebay_browse]
        enabled = true
        marketplace_id = "EBAY_GB"
        page_size = 25

        [providers.ebay_browse.retry]
        max_attempts = 5
        """,
    )
    config = load_pipeline_config(path)
    setting = config.live_provider_settings["ebay_browse"]
    assert setting.enabled is True
    assert setting.config["marketplace_id"] == "EBAY_GB"
    assert setting.config["page_size"] == 25
    assert setting.config["retry"] == {"max_attempts": 5}
    # 'enabled' is consumed, not passed through as provider config.
    assert "enabled" not in setting.config


def test_config_can_disable_live_provider(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
        [providers.ebay_browse]
        enabled = false
        """,
    )
    config = load_pipeline_config(path)
    assert config.live_provider_settings["ebay_browse"].enabled is False


def test_config_defaults_enabled_to_true(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "[providers.ebay_browse]\nmarketplace_id = 'EBAY_IE'\n")
    assert load_pipeline_config(path).live_provider_settings["ebay_browse"].enabled is True


def test_config_rejects_unknown_live_provider(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "[providers.gumtree]\nenabled = true\n")
    with pytest.raises(ConfigError, match="unknown live provider"):
        load_pipeline_config(path)


def test_config_rejects_non_boolean_enabled(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "[providers.ebay_browse]\nenabled = 'yes'\n")
    with pytest.raises(ConfigError, match="'enabled' must be a boolean"):
        load_pipeline_config(path)


def test_config_rejects_invalid_live_config(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "[providers.ebay_browse]\nmarketplace_id = ''\n")
    with pytest.raises(ConfigError, match=r"\[providers.ebay_browse\]"):
        load_pipeline_config(path)


def test_config_without_providers_section_is_mock_only(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "[scanner]\nproviders = ['ebay']\n")
    assert load_pipeline_config(path).live_provider_settings == {}


# --------------------------------------------------------------------------- #
# CLI: --provider override
# --------------------------------------------------------------------------- #


def test_scan_provider_flag_parses_repeatably() -> None:
    args = build_parser().parse_args(
        ["scan", "rtx 4090", "--provider", "ebay_browse", "--provider", "ebay"]
    )
    assert args.provider == ["ebay_browse", "ebay"]


def test_scan_without_provider_flag_defaults_to_none() -> None:
    args = build_parser().parse_args(["scan", "rtx 4090"])
    assert args.provider is None


def test_apply_provider_override_replaces_provider_list() -> None:
    config = _apply_provider_override(PipelineConfig(), ["ebay_browse"])
    assert config.scanner_config is not None
    assert config.scanner_config.providers == ["ebay_browse"]


def test_apply_provider_override_preserves_live_settings() -> None:
    base = PipelineConfig(
        scanner_config=ScannerConfig(providers=["ebay"], max_results_per_provider=7),
        live_provider_settings={"ebay_browse": LiveProviderSetting(config=_LIVE_CONFIG)},
    )
    overridden = _apply_provider_override(base, ["ebay_browse"])
    assert overridden.scanner_config is not None
    assert overridden.scanner_config.providers == ["ebay_browse"]
    # Unrelated scanner settings and live config survive the override.
    assert overridden.scanner_config.max_results_per_provider == 7
    assert overridden.live_provider_settings["ebay_browse"].config == _LIVE_CONFIG


# --------------------------------------------------------------------------- #
# CLI end-to-end: arb scan "rtx 4090" --provider ebay_browse (mocked transport)
# --------------------------------------------------------------------------- #


def test_cli_scan_provider_ebay_browse_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    search_double = _search_transport()
    token_double = _token_transport()

    def _build_with_fakes(
        config: EbayBrowseConfig,
        *,
        env: object = None,
        transport: object = None,
        token_transport: object = None,
    ) -> object:
        # Ignore the (None) production transports; inject the fixture-backed ones.
        return build_ebay_browse_provider_from_env(
            config,
            env=env,  # type: ignore[arg-type]
            transport=search_double,
            token_transport=token_double,
        )

    monkeypatch.setitem(LIVE_PROVIDER_ENV_BUILDERS, "ebay_browse", _build_with_fakes)
    monkeypatch.setenv("EBAY_CLIENT_ID", "cid")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "secret")

    path = _write_config(
        tmp_path,
        """
        [providers.ebay_browse]
        page_size = 2
        """,
    )
    exit_code = main(
        ["scan", "rtx 4090", "--provider", "ebay_browse", "--format", "json", "--config", path]
    )
    assert exit_code == 0
    # The live path actually ran through the mocked transports (token minted once).
    assert len(token_double.requests) == 1
    assert search_double.requests
    payload = json.loads(capsys.readouterr().out)
    assert payload  # a well-formed JSON document was rendered


def test_cli_scan_live_provider_missing_credentials_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)
    exit_code = main(["scan", "rtx 4090", "--provider", "ebay_browse"])
    assert exit_code == 1
    assert "EBAY_CLIENT_ID" in capsys.readouterr().err
