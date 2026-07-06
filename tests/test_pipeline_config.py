"""Unit tests for the TOML pipeline config loader and CLI --config wiring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_arbitrage.pipeline import (
    ArbitragePipeline,
    ConfigError,
    PipelineConfig,
    load_pipeline_config,
)
from digital_arbitrage.pipeline.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "default.toml"


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# happy path
# --------------------------------------------------------------------------- #
def test_shipped_default_config_loads() -> None:
    config = load_pipeline_config(DEFAULT_CONFIG)
    assert isinstance(config, PipelineConfig)
    assert config.scan_limit == 10
    assert config.scanner_config is not None
    assert config.scanner_config.providers == [
        "ebay",
        "facebook_marketplace",
        "adverts_ie",
        "donedeal",
    ]
    assert config.opportunity_config is not None
    assert config.opportunity_config.buy_roi == 0.15
    assert config.pricing_config is not None
    assert config.pricing_config.strategy == "median"


def test_default_config_drives_pipeline() -> None:
    config = load_pipeline_config(DEFAULT_CONFIG)
    result = ArbitragePipeline(config).analyze("rtx 4090")
    assert result.total_listings_scanned > 0


def test_partial_config_leaves_other_stages_none(tmp_path: Path) -> None:
    path = write(tmp_path, "[opportunity]\nbuy_roi = 0.2\n")
    config = load_pipeline_config(path)
    assert config.scanner_config is None
    assert config.normalization_config is None
    assert config.pricing_config is None
    assert config.opportunity_config is not None
    assert config.opportunity_config.buy_roi == 0.2


def test_matching_section_nested_into_deduplication(tmp_path: Path) -> None:
    path = write(tmp_path, "[matching]\nsame_threshold = 0.8\n")
    config = load_pipeline_config(path)
    assert config.deduplication_config is not None
    assert config.deduplication_config.match_config is not None
    assert config.deduplication_config.match_config.same_threshold == 0.8


def test_scoring_section_loads(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "[scoring]\nroi_weight = 0.5\nrisk_weight = 0.0\nrisk_full_comparables = 8\n",
    )
    config = load_pipeline_config(path)
    assert config.scoring_config is not None
    assert config.scoring_config.roi_weight == 0.5
    assert config.scoring_config.risk_weight == 0.0
    assert config.scoring_config.risk_full_comparables == 8


def test_shipped_default_config_has_scoring() -> None:
    config = load_pipeline_config(DEFAULT_CONFIG)
    assert config.scoring_config is not None
    assert config.scoring_config.roi_reference == 30.0


def test_scoring_unknown_key_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, "[scoring]\nroi_weight = 0.5\nbogus = 1\n")
    with pytest.raises(ConfigError, match=r"\[scoring\].*bogus"):
        load_pipeline_config(path)


def test_scoring_invalid_value_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, "[scoring]\nroi_reference = 0.0\n")
    with pytest.raises(ConfigError, match=r"\[scoring\]"):
        load_pipeline_config(path)


def test_scoring_config_changes_pipeline_score(tmp_path: Path) -> None:
    # A config that weights only confidence must produce different scores than
    # one weighting only ROI - proving the loaded config reaches the scorer.
    conf_path = tmp_path / "conf_only.toml"
    conf_path.write_text(
        "[scoring]\nroi_weight = 0.0\nnet_profit_weight = 0.0\n"
        "confidence_weight = 1.0\nrisk_weight = 0.0\n",
        encoding="utf-8",
    )
    roi_path = tmp_path / "roi_only.toml"
    roi_path.write_text(
        "[scoring]\nroi_weight = 1.0\nnet_profit_weight = 0.0\n"
        "confidence_weight = 0.0\nrisk_weight = 0.0\n",
        encoding="utf-8",
    )
    conf_only = load_pipeline_config(conf_path)
    roi_only = load_pipeline_config(roi_path)
    conf_scores = [i.score for i in ArbitragePipeline(conf_only).analyze("rtx 4090").items]
    roi_scores = [i.score for i in ArbitragePipeline(roi_only).analyze("rtx 4090").items]
    assert conf_scores != roi_scores


def test_list_coercions(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "[matching]\nbrands = ['nvidia', 'amd']\n"
        "[deduplication]\nprovider_priority = ['ebay', 'donedeal']\n"
        "[normalization]\nfiller_words = ['brand', 'new']\n",
    )
    config = load_pipeline_config(path)
    assert config.deduplication_config is not None
    assert config.deduplication_config.match_config is not None
    assert config.deduplication_config.match_config.brands == frozenset({"nvidia", "amd"})
    assert config.deduplication_config.provider_priority == ("ebay", "donedeal")
    assert config.normalization_config is not None
    assert config.normalization_config.filler_words == frozenset({"brand", "new"})


def test_scan_limit_from_pipeline_section(tmp_path: Path) -> None:
    path = write(tmp_path, "[pipeline]\nscan_limit = 1\n")
    config = load_pipeline_config(path)
    assert config.scan_limit == 1
    result = ArbitragePipeline(config).analyze("rtx 4090")
    baseline = ArbitragePipeline().analyze("rtx 4090")
    assert result.total_listings_scanned < baseline.total_listings_scanned


# --------------------------------------------------------------------------- #
# validation / errors
# --------------------------------------------------------------------------- #
def test_missing_file() -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_pipeline_config("/no/such/config.toml")


def test_invalid_toml(tmp_path: Path) -> None:
    path = write(tmp_path, "this is = = not toml")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_pipeline_config(path)


def test_unknown_section(tmp_path: Path) -> None:
    path = write(tmp_path, "[nonsense]\nfoo = 1\n")
    with pytest.raises(ConfigError, match="unknown section"):
        load_pipeline_config(path)


def test_unknown_key(tmp_path: Path) -> None:
    path = write(tmp_path, "[opportunity]\nbogus = 1\n")
    with pytest.raises(ConfigError, match=r"\[opportunity\] unknown key"):
        load_pipeline_config(path)


def test_wrong_type(tmp_path: Path) -> None:
    path = write(tmp_path, "[opportunity]\nbuy_roi = 'high'\n")
    with pytest.raises(ConfigError, match="must be a number"):
        load_pipeline_config(path)


def test_bool_is_not_integer(tmp_path: Path) -> None:
    path = write(tmp_path, "[scanner]\nmax_results_per_provider = true\n")
    with pytest.raises(ConfigError, match="must be an integer"):
        load_pipeline_config(path)


def test_invalid_value_bubbles_from_dataclass(tmp_path: Path) -> None:
    path = write(tmp_path, "[scanner]\nmax_results_per_provider = 0\n")
    with pytest.raises(ConfigError, match=r"\[scanner\]"):
        load_pipeline_config(path)


def test_invalid_strategy(tmp_path: Path) -> None:
    path = write(tmp_path, "[market_pricing]\nstrategy = 'magic'\n")
    with pytest.raises(ConfigError, match="strategy"):
        load_pipeline_config(path)


def test_invalid_unicode_form(tmp_path: Path) -> None:
    path = write(tmp_path, "[normalization]\nunicode_form = 'NFZZ'\n")
    with pytest.raises(ConfigError, match="unicode_form"):
        load_pipeline_config(path)


def test_bad_matching_threshold(tmp_path: Path) -> None:
    path = write(tmp_path, "[matching]\nsame_threshold = 5.0\n")
    with pytest.raises(ConfigError, match=r"\[matching\]"):
        load_pipeline_config(path)


# --------------------------------------------------------------------------- #
# CLI integration
# --------------------------------------------------------------------------- #
def test_cli_with_config(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["scan", "rtx 4090", "--config", str(DEFAULT_CONFIG), "--format", "json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "rtx 4090"


def test_cli_limit_overrides_config(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["scan", "rtx 4090", "--config", str(DEFAULT_CONFIG), "--limit", "1", "--format", "json"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    limited = payload["total_listings_scanned"]
    assert limited == len(payload["items"]) or limited <= 4


def test_cli_bad_config_returns_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write(tmp_path, "[nonsense]\nx = 1\n")
    code = main(["scan", "rtx 4090", "--config", str(path)])
    assert code == 1
    assert "error:" in capsys.readouterr().err
