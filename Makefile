# Conduit developer task runner.
#
# Thin, discoverable wrappers around the everyday commands. `make` with no
# target prints the help. The heavy lifting for the dev boot lives in
# scripts/dev.sh (so it works for folks without `make`, e.g. on Windows).

.DEFAULT_GOAL := help
.PHONY: help install up down reset dev migrate run test lint fmt check

help: ## Show this help.
	@echo "Conduit — make targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Sync the dev environment from uv.lock.
	uv sync --extra dev

up: ## Start the Postgres container in the background.
	docker compose up -d db

down: ## Stop the Postgres container (data volume preserved).
	docker compose down

reset: ## Stop Postgres AND wipe its data volume (clean slate).
	docker compose down -v

dev: ## One-command dev boot: Postgres -> migrations -> uvicorn --reload.
	./scripts/dev.sh

migrate: ## Apply database migrations (alembic upgrade head).
	uv run alembic upgrade head

run: ## Start uvicorn against an already-running Postgres (no compose/migrate).
	./scripts/dev.sh --no-db --no-migrate

test: ## Run the test suite.
	uv run pytest

lint: ## Lint and auto-fix with ruff.
	uv run ruff check --fix .

fmt: ## Format the codebase with ruff.
	uv run ruff format .

check: lint fmt test ## Run the full quality gate (lint + format + tests).
