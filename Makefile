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

check: lint type test clean  ## Full quality gate: ruff -> mypy -> pytest -> clean

ingest-build:  ## Build the processed corpus (requires a pinned rev synced first)
	$(PY) -m oikonomia.cli.main ingest build

# NOTE: use `-exec rm`, never `-delete`. `find -delete` implies `-depth`, which
# silently disables `-prune` — the command would then walk into .venv and delete
# its bytecode as well.
clean:  ## Remove tool caches and compiled files (leaves .venv untouched)
	find . -path ./.venv -prune -o -type d \
	  \( -name "__pycache__" -o -name ".pytest_cache" \
	     -o -name ".ruff_cache" -o -name ".mypy_cache" \) -exec rm -rf {} + 2>/dev/null || true
	find . -path ./.venv -prune -o -name "*.pyc" -exec rm -f {} + 2>/dev/null || true
