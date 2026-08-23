.PHONY: run db migrate api collector schedule status ingest test lint web up down
API_PORT ?= 8001
db:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
run:
	./run.sh
api:
	cd backend && uvicorn app.main:app --reload --port $(API_PORT)
collector:
	cd backend && python -m app.cli collector
schedule:
	cd backend && python -m app.cli schedule
status:
	cd backend && python -m app.cli collector-status
migrate:
	cd backend && alembic upgrade head
ingest:
	cd backend && python -m app.cli ingest-config ../repositories.yml
test:
	cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -p pytest_asyncio.plugin
lint:
	cd backend && ruff check . && mypy app
web:
	cd frontend && npm run dev
up:
	./run.sh
down:
	./run.sh down
