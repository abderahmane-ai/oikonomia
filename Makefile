# OIKONOMIA — developer task aliases. See CLAUDE.md §5 for the phase-transition gate.
.PHONY: install lint type test check clean ingest-build

PY := .venv/bin/python
RUFF := .venv/bin/ruff

install:  ## Create venv and install the package with dev tools
	uv venv --python 3.12
	uv pip install -e ".[dev]"

lint:  ## Ruff lint
	$(RUFF) check src tests

type:  ## Strict type check
	$(PY) -m mypy src

test:  ## Run the test suite
	$(PY) -m pytest

check: lint type test  ## Full quality gate (run before ending a phase)

ingest-build:  ## Build the processed corpus (requires a pinned rev synced first)
	$(PY) -m oikonomia.cli.main ingest build

clean:  ## Remove tool caches and compiled files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d \( -name ".pytest_cache" -o -name ".ruff_cache" -o -name ".mypy_cache" \) -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
