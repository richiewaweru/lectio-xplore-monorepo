.PHONY: dev dev-down dev-clean logs logs-backend logs-db test lint validate db-shell migrate migration smoke smoke-prod smoke-pdf

dev:
	docker compose up --build

dev-down:
	docker compose down

dev-clean:
	docker compose down -v

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-db:
	docker compose logs -f db

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check src/ tests/
	cd frontend && npm run check

validate:
	python tools/agent/validate_repo.py --scope all

smoke:
	python scripts/smoke_test.py $${BACKEND_URL:-http://localhost:8000}

smoke-prod:
	python scripts/smoke_test.py $${BACKEND_URL}

smoke-pdf:
	python scripts/pdf_export_runtime_smoke.py $${BACKEND_URL:-http://localhost:8000}

db-shell:
	docker compose exec db psql -U $${POSTGRES_USER:-textbook} -d $${POSTGRES_DB:-textbook_agent}

migrate:
	cd backend && uv run alembic upgrade head

migration:
	test -n "$(name)" || (echo "Usage: make migration name=descriptive_migration_name" && exit 1)
	cd backend && uv run alembic revision --autogenerate -m "$(name)"
