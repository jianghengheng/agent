PYTHON := uv run python

.PHONY: install dev lint format test run

install:
	uv sync --dev

dev:
	uv run uvicorn ai_multi_agent.main:app --factory --reload

lint:
	uv run ruff check .
	uv run mypy .

format:
	uv run ruff check . --fix
	uv run ruff format .

test:
	uv run pytest

run:
	uv run uvicorn ai_multi_agent.main:app --factory --host 0.0.0.0 --port 8000

