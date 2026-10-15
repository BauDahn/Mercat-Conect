# Mercat-Conect · comandos de la demo. Ayuda: make help
SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: help ensure-env demo reset seed e2e test down demo-local down-local

# Valores de .env (si existe) como punto de partida; los de la línea de comandos mandan.
-include .env

WEB_PORT ?= 5173
API_PORT ?= 8000
SEED ?= 42
LOCAL_DB_PORT ?= 5433
DEMO_DIR := .demo

help: ## Muestra esta ayuda
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-12s %s\n", $$1, $$2}'

ensure-env:
	@test -f .env || cp .env.example .env

demo: ensure-env ## Docker: levanta todo, migra y carga los datos (web en localhost:5173)
	docker compose up -d --wait --build db mailpit
	docker compose run --rm --build seed
	docker compose up -d --build api web
	@echo ""
	@echo "Demo lista: http://localhost:$(WEB_PORT)   (buzón: http://localhost:8025)"
	@echo "Analítica opcional: docker compose --profile analytics up -d metabase"

reset: ensure-env ## Docker: borra volúmenes y vuelve a levantar la demo con el mismo seed
	docker compose down -v --remove-orphans
	$(MAKE) demo

seed: ensure-env ## Docker: recarga los datos con otro seed, p. ej. make seed SEED=43
	docker compose run --rm --build -e DEMO_SEED=$(SEED) seed

e2e: ## Playwright sobre la demo en marcha (ejecuta antes make demo)
	@test -d e2e/node_modules || npm --prefix e2e install
	BASE_URL=http://localhost:$(WEB_PORT) npm --prefix e2e test

test: ## Pruebas unitarias y de concurrencia (pytest)
	uv run --project apps/api pytest -q

down: ## Docker: apaga los servicios y borra volúmenes
	docker compose down -v --remove-orphans

demo-local: ensure-env ## Sin Docker: PostgreSQL embebido, migra, siembra y lanza api y web en segundo plano
	@set -e; mkdir -p $(DEMO_DIR); \
	alive() { [ -f "$$1" ] && kill -0 "$$(cat "$$1")" 2>/dev/null; }; \
	set -a; . ./.env; set +a; \
	export DB_PORT=$(LOCAL_DB_PORT) API_PORT=$(API_PORT) WEB_PORT=$(WEB_PORT); \
	export DATABASE_URL="$$(uv run --quiet --python 3.12 --with pgserver scripts/localdb.py start)"; \
	export SMTP_HOST=localhost; \
	uv run --quiet --project apps/api alembic -c apps/api/alembic.ini upgrade head; \
	uv run --quiet --project apps/api python data/seed/run.py; \
	if ! alive $(DEMO_DIR)/api.pid; then \
	  setsid nohup uv run --project apps/api uvicorn app.main:app --app-dir apps/api \
	    --host 127.0.0.1 --port $(API_PORT) > $(DEMO_DIR)/api.log 2>&1 < /dev/null & \
	  echo $$! > $(DEMO_DIR)/api.pid; \
	fi; \
	if ! alive $(DEMO_DIR)/web.pid; then \
	  test -d apps/web/node_modules || npm --prefix apps/web install; \
	  API_TARGET=http://127.0.0.1:$(API_PORT) setsid nohup npm --prefix apps/web run dev -- \
	    --host 127.0.0.1 --port $(WEB_PORT) --strictPort > $(DEMO_DIR)/web.log 2>&1 < /dev/null & \
	  echo $$! > $(DEMO_DIR)/web.pid; \
	fi; \
	echo ""; \
	echo "Demo local lista: http://localhost:$(WEB_PORT)"; \
	echo "Logs: $(DEMO_DIR)/api.log  $(DEMO_DIR)/web.log  $(DEMO_DIR)/postgres.log"; \
	echo "Sin buzón SMTP local: los avisos por correo no llegarán (SMTP_HOST=localhost)."

down-local: ## Sin Docker: para api, web y PostgreSQL embebido (conserva .demo/pgdata)
	@for s in api web; do \
	  if [ -f $(DEMO_DIR)/$$s.pid ]; then \
	    kill -TERM -- -"$$(cat $(DEMO_DIR)/$$s.pid)" 2>/dev/null || true; \
	    rm -f $(DEMO_DIR)/$$s.pid; \
	  fi; \
	done
	uv run --quiet --python 3.12 --with pgserver scripts/localdb.py stop
