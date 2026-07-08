"""Integration tests for Sprint 26 - first live end-to-end eBay Browse scan.

These tests drive the *whole* pipeline
(Scanner -> Normalization -> Product Matching -> Deduplication -> Market Pricing
-> Opportunity) with the live ``ebay_browse`` provider and assert that real
listings become scored opportunities. Every test is hermetic: a fake
:class:`Transport` replays the committed, sanitised eBay fixtures and OAuth
credentials come from a fake ``env`` (or monkeypatched environment), so **no
network call and no secret is ever used** (honouring "no live API calls in CI").

Sprint 25 (``test_local_ebay_scan.py``) covers scanner assembly, the builder
registries, and TOML parsing in isolation; this suite complements it by asserting
the end-to-end data flow through the real :class:`ArbitragePipeline` and the
exact documented CLI command against the committed ``configs/ebay_browse.toml``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_arbitrage.pipeline import ArbitragePipeline, PipelineConfig, load_pipeline_config
from digital_arbitrage.pipeline.cli import main
from digital_arbitrage.product_scanner import ScannerConfig
from digital_arbitrage.providers.live import (
    LIVE_PROVIDER_ENV_BUILDERS,
    EbayBrowseConfig,
    HttpRequest,
    HttpResponse,
    LiveProviderSetting,
    Transport,
    build_ebay_browse_provider_from_env,
    build_scanner_from_config,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES = Path(__file__).parent / "fixtures" / "ebay"
_ENV = {"EBAY_CLIENT_ID": "cid", "EBAY_CLIENT_SECRET": "secret"}
#: The sample config shipped for users to copy (and used in the README command).
_SAMPLE_CONFIG = _REPO_ROOT / "configs" / "ebay_browse.toml"

# The four fixture listings, keyed by the title the pipeline preserves.
_FOUNDERS = "NVIDIA GeForce RTX 4090 Founders Edition 24GB"
_REFURB = "RTX 4090 Gaming OC 24GB (Certified Refurbished)"
_USED = "Used RTX 4090 - fully tested and working"
_AUCTION = "RTX 4090 auction - no reserve"


def _bytes(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


def _response(status: int, body: bytes) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers={},
        body=body,
        url="https://api.ebay.com/buy/browse/v1/item_summary/search",
    )


class _SearchTransport(Transport):
    """Replays the two search fixtures keyed by the request ``offset``."""

    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        offset = dict(request.params).get("offset", "0")
        page = "search_page1.json" if offset == "0" else "search_page2.json"
        return _response(200, _bytes(page))


class _TokenTransport(Transport):
    """Returns the sanitised OAuth token for every mint request."""

    def __init__(self) -> None:
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        return _response(200, _bytes("oauth_token.json"))


def _live_scanner(
    search: _SearchTransport, token: _TokenTransport
) -> tuple[ArbitragePipeline, PipelineConfig]:
    scanner = build_scanner_from_config(
        ScannerConfig(providers=["ebay_browse"], max_results_per_provider=10),
        {"ebay_browse": LiveProviderSetting(config={"page_size": 2, "max_results": 50})},
        env=_ENV,
        transport=search,
        token_transport=token,
    )
    config = PipelineConfig()
    return ArbitragePipeline(config, scanner=scanner), config


# --------------------------------------------------------------------------- #
# Full pipeline: Scanner -> ... -> Opportunity, end to end
# --------------------------------------------------------------------------- #


def test_full_pipeline_produces_opportunities_from_live_listings() -> None:
    search, token = _SearchTransport(), _TokenTransport()
    pipeline, _ = _live_scanner(search, token)

    result = pipeline.analyze("rtx 4090")

    # The OAuth token was minted once and the search was paginated (2 pages of 2).
    assert len(token.requests) == 1
    assert len(search.requests) == 2

    # Every fixture listing flowed all the way through to a scored opportunity.
    assert result.total_listings_scanned == 4
    assert result.total_groups == 4
    assert len(result.items) == 4
    assert {item.title for item in result.items} == {_FOUNDERS, _REFURB, _USED, _AUCTION}
    assert {item.provider for item in result.items} == {"ebay_browse"}

    # Each item carries a recommendation, a 0-100 score, and a market-price stage.
    for item in result.items:
        assert item.recommendation.value in {"strong_buy", "buy", "watch", "reject"}
        assert 0.0 <= item.score <= 100.0
        assert item.market_price is not None


def test_pipeline_maps_prices_currencies_and_condition_end_to_end() -> None:
    search, token = _SearchTransport(), _TokenTransport()
    pipeline, _ = _live_scanner(search, token)

    by_title = {item.title: item for item in pipeline.analyze("rtx 4090").items}

    # Fixed-price EUR listing: price + currency survive to the opportunity.
    founders = by_title[_FOUNDERS].opportunity
    assert founders.asking_price == pytest.approx(1799.99)
    assert founders.currency == "EUR"

    # The USD listing keeps its own currency (cross-currency listings coexist).
    assert by_title[_USED].opportunity.currency == "USD"

    # The auction listing has no price; it still yields a (REJECT) opportunity.
    auction = by_title[_AUCTION]
    assert auction.opportunity.asking_price is None
    assert auction.recommendation.value == "reject"


def test_pipeline_preserves_ebay_only_fields_through_normalization() -> None:
    search, token = _SearchTransport(), _TokenTransport()
    pipeline, _ = _live_scanner(search, token)

    result = pipeline.analyze("rtx 4090")
    founders = next(item for item in result.items if item.title == _FOUNDERS)
    listing = founders.group.canonical.source

    # eBay-only fields land in Listing.extra and are carried by the canonical
    # listing selected for the group.
    assert listing.extra.get("seller") == "example_seller_ie"
    assert listing.extra.get("condition_id") == "1000"
    assert "image_url" in listing.extra


# --------------------------------------------------------------------------- #
# The committed sample config users copy
# --------------------------------------------------------------------------- #


def test_sample_config_file_is_present_and_valid() -> None:
    assert _SAMPLE_CONFIG.is_file(), "configs/ebay_browse.toml sample must exist"
    config = load_pipeline_config(_SAMPLE_CONFIG)
    assert config.scanner_config is not None
    assert config.scanner_config.providers == ["ebay_browse"]
    setting = config.live_provider_settings["ebay_browse"]
    assert setting.enabled is True
    # The sample never contains secrets - only non-credential settings.
    assert "EBAY_CLIENT_ID" not in setting.config
    assert "EBAY_CLIENT_SECRET" not in setting.config
    built = build_ebay_browse_provider_from_env(
        EbayBrowseConfig.from_dict({"base_url": "https://api.ebay.com", **setting.config}),
        env=_ENV,
    )
    assert isinstance(built, object)  # config is accepted by the real builder


# --------------------------------------------------------------------------- #
# The exact documented CLI command, end to end (mocked transports)
# --------------------------------------------------------------------------- #


def test_cli_scan_with_sample_config_runs_live_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    search, token = _SearchTransport(), _TokenTransport()

    def _build_with_fakes(
        config: EbayBrowseConfig,
        *,
        env: object = None,
        transport: object = None,
        token_transport: object = None,
    ) -> object:
        return build_ebay_browse_provider_from_env(
            config, env=env, transport=search, token_transport=token
        )

    monkeypatch.setitem(LIVE_PROVIDER_ENV_BUILDERS, "ebay_browse", _build_with_fakes)
    monkeypatch.setenv("EBAY_CLIENT_ID", "cid")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "secret")

    # The exact command from the README / sprint brief.
    exit_code = main(
        [
            "scan",
            "rtx 4090",
            "--provider",
            "ebay_browse",
            "--config",
            str(_SAMPLE_CONFIG),
            "--format",
            "json",
        ]
    )
    assert exit_code == 0
    assert len(token.requests) == 1
    assert search.requests

    payload = json.loads(capsys.readouterr().out)
    assert payload["total_listings_scanned"] == 4
    assert payload["items"], "the scan produced opportunities"
    assert {item["provider"] for item in payload["items"]} == {"ebay_browse"}


def test_cli_scan_with_sample_config_fails_cleanly_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)

    exit_code = main(["scan", "rtx 4090", "--config", str(_SAMPLE_CONFIG)])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "EBAY_CLIENT_ID and EBAY_CLIENT_SECRET must be set" in err
