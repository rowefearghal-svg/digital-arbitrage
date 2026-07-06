# digital-arbitrage

> Research and engineering project exploring digital arbitrage opportunities.
> This repository currently contains the **engineering foundation only** - no
> arbitrage logic is implemented yet.

[![CI](https://github.com/rowefearghal-svg/digital-arbitrage/actions/workflows/ci.yml/badge.svg)](https://github.com/rowefearghal-svg/digital-arbitrage/actions/workflows/ci.yml)
[![status](https://img.shields.io/badge/status-bootstrapping-blue)](docs/ROADMAP.md)

## Overview

`digital-arbitrage` is a long-lived Python project. This initial commit
establishes a clean, professional structure so that future development has a
solid base: packaging, tests, configuration, documentation, and a backlog.

_A concise product description will be added as scope firms up (see
[`docs/VISION.md`](docs/VISION.md))._

## Modules

- **`product_scanner`** - searches marketplaces through a common provider
  interface and returns unified `Listing` objects (currently mocked providers:
  eBay, Facebook Marketplace, Adverts.ie, DoneDeal).
- **`normalization`** - converts raw `Listing` objects into a consistent
  internal `NormalizedListing` via a configurable, provider-agnostic pipeline
  (unicode + text/whitespace/title cleanup, currency/condition/location
  normalization). No pricing, FX, or AI.
- **`product_matching`** - deterministic engine estimating whether two
  `NormalizedListing`s are the same product, via token similarity + brand/model
  heuristics with configurable thresholds. Returns an explained `MatchResult`
  (`score`, `decision`, `reasons`, matched/unmatched tokens). No AI or pricing.
- **`deduplication`** - groups duplicate/near-duplicate listings across
  providers (reusing `product_matching`), selecting one canonical listing per
  group and a deterministic fingerprint. Lossless (every input preserved) and
  toggleable via config. No pricing, scraping, or AI.
- **`market_pricing`** - estimates the market price of a product from comparable
  listings using deterministic, swappable strategies (median, trimmed mean,
  weighted average) with IQR outlier removal. Returns a `MarketPrice`
  (estimate, confidence, comparable count, min/max/median/mean). No AI/ML.
- **`opportunity`** - turns an asking price + `MarketPrice` into a scored
  arbitrage `Opportunity`: an itemized `CostBreakdown` (marketplace/payment/
  shipping/packaging/buffer/tax), a `ProfitEstimate` (gross/net profit, ROI %,
  margin %), and a `STRONG_BUY / BUY / WATCH / REJECT` recommendation with
  reasons. Conservative by default, configurable. No scraping, AI, or APIs.
- **`pipeline`** - end-to-end orchestrator wiring every stage into
  `ArbitragePipeline.analyze(query)`, returning a `PipelineResult` of
  `PipelineItemResult`s ranked by recommendation, then ROI, then confidence.
  Ships the `arb` CLI. Deterministic; mock providers only.

Pipeline order: **Scanner -> Normalization -> Product Matching -> Deduplication
-> Market Pricing -> Opportunity.**

```python
from digital_arbitrage.pipeline import ArbitragePipeline

result = ArbitragePipeline().analyze("rtx 4090")
for item in result.items:
    print(item.recommendation, item.title, item.roi_percentage, item.confidence_score)
```

### CLI

The `arb` command runs the whole pipeline (installed via `pip install -e .`):

```bash
arb scan "rtx 4090"                 # fixed-width table (default)
arb scan "rtx 4090" --format json   # JSON report
arb scan "rtx 4090" --limit 5       # cap results per provider
```

## Repository Layout

```
digital-arbitrage/
|-- src/digital_arbitrage/   # importable Python package (application code)
|-- tests/                   # test suite (pytest)
|-- configs/                 # non-secret configuration + examples
|-- scripts/                 # helper / operational scripts
|-- docs/                    # project documentation
|   |-- VISION.md            # why this project exists, long-term direction
|   |-- ROADMAP.md           # planned milestones
|   `-- DECISIONS.md         # architecture decision log
|-- BACKLOG.md               # initial issue list / work items
|-- pyproject.toml           # project metadata + tooling config
|-- requirements.txt         # pinned developer tooling
|-- .gitignore
|-- .gitattributes
`-- LICENSE                  # placeholder - license TBD
```

## Getting Started

> Requires Python 3.12+.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows:  .\.venv\Scripts\Activate.ps1
# macOS/Linux:  source .venv/bin/activate

# 2. Install the package (editable) plus dev tooling
pip install -r requirements.txt

# 3. Copy the example config and fill in values
#    (Linux/macOS shown; on Windows use Copy-Item)
cp configs/config.example.toml configs/config.toml

# 4. Run the checks
ruff check .
pytest
```

## Development

### Local checks

Run these before pushing - they mirror exactly what CI runs:

```bash
ruff check .            # lint
ruff format --check .   # formatting (use `ruff format .` to fix)
mypy src                # type check
pytest -q               # tests
```

### Continuous integration

Every `push` and `pull_request` is validated by GitHub Actions
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) on **Python 3.12**.
The pipeline fails if any of the four checks above fail, so a PR must be green
before it is merged.

### Workflow

1. Branch off `main` (`feature/*`, `fix/*`, `infrastructure/*`, `docs/*`).
2. Make focused commits; run the local checks above.
3. Open a pull request - CI runs automatically.
4. Merge only when CI is green (squash-merge, linear history, protected `main`).

Trunk-based: short-lived branches, a PR for every change, no direct pushes to
`main`. See the workspace standards in the `ai-infrastructure` repository.

## Configuration

Runtime configuration lives in `configs/`. Never commit secrets - copy
`config.example.toml` to `config.toml` (gitignored) and keep secrets in a local
`.env` (see `.env` handling in `.gitignore`).

## Data & Models

Datasets, models, and checkpoints are **not** stored in Git. Keep them in a
local `data/` directory (gitignored) or external object storage. See the
`ai-infrastructure` GitHub architecture notes.

## Documentation

- [`docs/VISION.md`](docs/VISION.md) - long-term direction and principles.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) - planned milestones.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) - architecture decision log (ADR).
- [`BACKLOG.md`](BACKLOG.md) - initial work items.

## License

License is **TBD** - see [`LICENSE`](LICENSE). Do not assume an open-source
license until one is chosen.

---

_Last updated: Sprint 9 (CI). This README will grow as the project takes shape._
