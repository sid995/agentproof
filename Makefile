PYTHON_SOURCE_PATHS := backend/src packages/python-sdk/src
PYTHON_TEST_PATHS := backend/tests packages/python-sdk/tests
PYTHON_PATHS := $(PYTHON_SOURCE_PATHS) $(PYTHON_TEST_PATHS)

.PHONY: install sync format format-check lint type-check test check audit build-sdk \
	infra-up infra-down infra-logs clean

install:
	uv sync --all-packages --all-groups
	uv run pre-commit install --hook-type pre-commit --hook-type pre-push

sync:
	uv sync --all-packages --all-groups

format:
	uv run ruff check --fix $(PYTHON_PATHS)
	uv run ruff format $(PYTHON_PATHS)

format-check:
	uv run ruff format --check $(PYTHON_PATHS)

lint:
	uv run ruff check $(PYTHON_PATHS)

type-check:
	uv run mypy $(PYTHON_SOURCE_PATHS)

test:
	uv run pytest

check: format-check lint type-check test

audit:
	uv run pip-audit

build-sdk:
	rm -rf dist
	uv build --package agentproof-sdk

infra-up:
	docker compose up -d

infra-down:
	docker compose down

infra-logs:
	docker compose logs -f

clean:
	rm -rf .mypy_cache
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .coverage
	rm -rf coverage_html
	rm -rf dist
	rm -rf build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.py[co]' -delete
