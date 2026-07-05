# Backlog

> Initial issue list for `digital-arbitrage`. These are proposed GitHub issues -
> convert each into a real issue (and label it) once the repo settings are in
> place. Grouped by theme; ordered roughly by priority. No arbitrage logic here.

## Legend

- **Priority:** P1 (soon) / P2 (next) / P3 (later)
- **Labels** are suggestions matching the repo's label set.

## Foundation & Repo Hygiene

- [ ] **Enable branch protection on `main`** - require PR + review, linear
  history, block force-push. `P1` `chore`
- [x] **Add CI workflow** - ruff lint + ruff format --check, mypy, pytest on
  every push/PR (Python 3.12). Done in `.github/workflows/ci.yml`. `P1` `chore`
  `tests`
- [ ] **Choose and add a LICENSE** - replace the placeholder; update
  `pyproject.toml` and README. `P1` `docs`
- [ ] **Add PR + issue templates** and a `CODEOWNERS` file. `P2` `chore`
- [ ] **Enable Dependabot** alerts + version updates for Python. `P2`
  `dependencies`

## Project Definition

- [ ] **Fill in VISION.md** - mission, problem, long-term goals, non-goals.
  `P1` `docs`
- [ ] **Define initial scope & success criteria** for the first real milestone.
  `P1` `docs`
- [ ] **Document data sources & access approach** (no secrets in Git). `P2`
  `docs`

## Engineering Baseline (no domain logic)

- [ ] **Configuration loader** - read `configs/config.toml` + env overrides.
  `P2` `enhancement`
- [ ] **Logging baseline** - structured logging honouring `log_level`. `P2`
  `enhancement`
- [ ] **Expand test scaffolding** - fixtures, coverage gate in CI. `P3` `tests`

## Research (later, separate PRs)

- [ ] **Survey arbitrage approaches** - written research note in `docs/`. `P3`
  `docs`
- [ ] **Prototype arbitrage detection** - spike behind tests; not merged to
  `main` until reviewed. `P3` `enhancement`
- [ ] **Backtesting/evaluation harness** design. `P3` `enhancement`

---

_These are planning items, not commitments. Keep this list pruned as issues are
created and closed._
