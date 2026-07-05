# digital-arbitrage

> Research and engineering project exploring digital arbitrage opportunities.
> This repository currently contains the **engineering foundation only** - no
> arbitrage logic is implemented yet.

[![status](https://img.shields.io/badge/status-bootstrapping-blue)](docs/ROADMAP.md)

## Overview

`digital-arbitrage` is a long-lived Python project. This initial commit
establishes a clean, professional structure so that future development has a
solid base: packaging, tests, configuration, documentation, and a backlog.

_A concise product description will be added as scope firms up (see
[`docs/VISION.md`](docs/VISION.md))._

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

- **Format / lint:** `ruff check .` and `ruff format .` (or `black .`).
- **Type check:** `mypy src`.
- **Tests:** `pytest` (coverage via `pytest --cov`).
- **Branching:** trunk-based - short-lived branches off `main`, PR for every
  change, squash-merge, protected `main`. See the workspace standards in the
  `ai-infrastructure` repository.

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

_Last updated: bootstrap. This README will grow as the project takes shape._
