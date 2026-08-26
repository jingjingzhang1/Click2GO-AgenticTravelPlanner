# ── Click2GO developer tasks ─────────────────────────────────────────────────
.DEFAULT_GOAL := help
.PHONY: help install dev run test lint format typecheck migrate revision \
        docker-up docker-down clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install runtime + dev dependencies
	pip install -r requirements.txt
	pip install ruff mypy pytest pre-commit

dev: install  ## Install and set up pre-commit hooks
	pre-commit install

run:  ## Run the API with autoreload (SQLite default)
	uvicorn backend.main:app --reload --port 8000

test:  ## Run the test suite
	python -m pytest tests/ -v

lint:  ## Lint with ruff
	ruff check backend tests

format:  ## Auto-format with ruff
	ruff format backend tests
	ruff check --fix backend tests

typecheck:  ## Static type-check with mypy
	mypy backend

migrate:  ## Apply DB migrations (alembic upgrade head)
	alembic upgrade head

revision:  ## Autogenerate a new migration: make revision m="add x"
	alembic revision --autogenerate -m "$(m)"

docker-up:  ## Build and start the full stack (API + Postgres)
	docker compose up --build

docker-down:  ## Stop the stack and remove volumes
	docker compose down -v

clean:  ## Remove caches and generated artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache __pycache__ \
		backend/**/__pycache__ test_click2go.db
