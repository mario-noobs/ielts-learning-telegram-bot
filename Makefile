# IELTS bot dev environment.
#
# One-command developer setup for contributors, designers, and QA. See
# README.md → Quickstart. macOS / Linux only — not tested on Windows.
#
# Usage:
#   make install   # venv + pip + npm install
#   make dev       # emulators + seed + api + web (parallel)
#   make seed      # (re)load deterministic demo data
#   make bot       # start Telegram bot (optional; requires real token)
#   make test      # pytest
#   make clean     # tear everything down

SHELL := /bin/bash

VENV ?= ./venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

EMULATOR_ENV := \
	FIRESTORE_EMULATOR_HOST=localhost:8080 \
	FIREBASE_AUTH_EMULATOR_HOST=localhost:9099 \
	GOOGLE_CLOUD_PROJECT=ielts-bot-dev \
	DATABASE_URL=postgresql+asyncpg://ielts:dev@localhost:5432/ielts

# ─── meta ──────────────────────────────────────────────────────────────

.PHONY: help
.DEFAULT_GOAL := help
help:  ## Show this help
	@echo "IELTS bot — developer tasks"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""
	@echo "Quick start: make install && make dev"

# ─── install ───────────────────────────────────────────────────────────

.PHONY: install
install: $(VENV)/.installed web/node_modules/.installed  ## Install Python + Node dependencies

$(VENV)/.installed: requirements.txt requirements-dev.txt
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PIP) install --quiet --upgrade pip
	@$(PIP) install --quiet -r requirements-dev.txt
	@touch $@

web/node_modules/.installed: web/package.json
	@cd web && npm install --silent
	@mkdir -p web/node_modules && touch web/node_modules/.installed

# ─── emulators ─────────────────────────────────────────────────────────

.PHONY: emulators
emulators:  ## Start Firebase emulators (auth + firestore + UI) in background
	@echo "→ Starting Firebase emulators…"
	@docker-compose --profile dev up -d firebase-emulators
	@echo -n "→ Waiting for Firestore emulator on :8080"
	@bash -c ' \
		for i in $$(seq 1 60); do \
			if bash -c ":>/dev/tcp/localhost/8080" 2>/dev/null; then \
				echo " ready."; exit 0; \
			fi; \
			echo -n "."; sleep 1; \
		done; \
		echo ""; echo "ERROR: Firestore emulator did not come up within 60s"; exit 1 \
	'

.PHONY: emulators-down
emulators-down:  ## Stop Firebase emulators
	@docker-compose --profile dev stop firebase-emulators
	@docker-compose --profile dev rm -f firebase-emulators

# ─── postgres ──────────────────────────────────────────────────────────

.PHONY: postgres
postgres:  ## Start self-hosted Postgres dev container in background
	@echo "→ Starting Postgres…"
	@docker-compose --profile dev up -d postgres
	@echo -n "→ Waiting for Postgres on :5432"
	@bash -c ' \
		for i in $$(seq 1 60); do \
			if docker exec ielts-bot-postgres-1 pg_isready -U ielts -d ielts >/dev/null 2>&1; then \
				echo " ready."; exit 0; \
			fi; \
			echo -n "."; sleep 1; \
		done; \
		echo ""; echo "ERROR: Postgres did not come up within 60s"; exit 1 \
	'

.PHONY: postgres-down
postgres-down:  ## Stop Postgres dev container
	@docker-compose --profile dev stop postgres
	@docker-compose --profile dev rm -f postgres

.PHONY: migrate
migrate:  ## Apply Alembic migrations to head (DATABASE_URL must be set)
	@$(EMULATOR_ENV) $(VENV)/bin/alembic upgrade head

# ─── seed ──────────────────────────────────────────────────────────────

.PHONY: seed
seed: migrate  ## Run migrations + seed deterministic demo data (idempotent)
	@$(EMULATOR_ENV) $(PY) scripts/seed.py

# ─── run ───────────────────────────────────────────────────────────────

.PHONY: api
api:  ## Run FastAPI against emulators
	@$(EMULATOR_ENV) $(PY) run_api.py

.PHONY: web
web:  ## Run Vite dev server
	@cd web && npm run dev

.PHONY: bot
bot:  ## Run Telegram bot (requires a real bot token)
	@$(EMULATOR_ENV) $(PY) main.py

.PHONY: dev
dev: install postgres emulators seed  ## One-command dev environment: postgres + emulators + api + web
	@echo ""
	@echo "╭──────────────────────────────────────────────────────────────╮"
	@echo "│ Dev environment ready                                        │"
	@echo "│   Web UI:      http://localhost:5173                         │"
	@echo "│   API:         http://localhost:8000/api/v1/health           │"
	@echo "│   Emulator UI: http://localhost:4000                         │"
	@echo "│   Postgres:    postgresql://ielts:dev@localhost:5432/ielts   │"
	@echo "│   Login:       demo@ielts.test / demo1234                    │"
	@echo "╰──────────────────────────────────────────────────────────────╯"
	@echo ""
	@echo "Press Ctrl-C to stop API + Web (containers keep running; use \`make emulators-down\` and \`make postgres-down\`)."
	@trap 'kill 0 2>/dev/null' INT TERM EXIT; \
	( $(EMULATOR_ENV) $(PY) run_api.py ) & \
	( cd web && npm run dev ) & \
	wait

# ─── test / clean ──────────────────────────────────────────────────────

.PHONY: test
test:  ## Run pytest (Postgres tests skip unless DATABASE_URL is set)
	@$(EMULATOR_ENV) $(PY) -m pytest -q

.PHONY: clean
clean:  ## Remove venv, caches, node_modules, and stop dev containers (prompts first)
	@read -p "This removes venv/, web/node_modules/, __pycache__, .pytest_cache, and stops emulators+postgres. Continue? [y/N] " ans; \
	if [ "$$ans" != "y" ] && [ "$$ans" != "Y" ]; then echo "aborted."; exit 0; fi; \
	$(MAKE) emulators-down 2>/dev/null || true; \
	$(MAKE) postgres-down 2>/dev/null || true; \
	rm -rf $(VENV) .pytest_cache .ruff_cache; \
	find . -type d -name __pycache__ -prune -exec rm -rf {} +; \
	rm -rf web/node_modules web/dist; \
	echo "clean."
