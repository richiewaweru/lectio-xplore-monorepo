# Production Stabilization Pass

**Date:** 2026-04-02  
**Classification:** major  
**Subsystems:** backend runtime, database config, Docker packaging, operator docs, test config

## Progress

- [x] Documented scope and preserved existing product behavior
- [x] Established baseline validation before changes
- [x] Tightened backend runtime/database configuration
- [x] Added production-like fail-fast environment validation
- [x] Normalized Docker vs native env/documentation
- [x] Added root operator `Makefile`
- [x] Added pytest Postgres marker/default deselection coverage
- [x] Verified Docker compose operator flows manually
- [x] Recorded final validation evidence after implementation

## Summary

This pass hardens the current application for a first Docker-host style deployment without changing the existing HTTP/API behavior. The work keeps PostgreSQL + Alembic as the only runtime schema path, preserves `GenerationMode`, and focuses on runtime safety, configuration clarity, and operator ergonomics.

## Key Changes

- Added `APP_ENV`/`ENVIRONMENT` support plus production-like validation in backend settings.
- Added explicit `DB_ECHO` support and standardized non-SQLite engine pool settings.
- Removed redundant `asyncpg` install from the backend Docker build.
- Added a repo-root `Makefile` for compose, validation, migration, and log workflows.
- Split Docker-root env guidance from backend-native env guidance across docs and examples.
- Added the `postgres` pytest marker and default deselection.
- Ignored transient database backup artifacts created during migration work.

## Baseline Validation

- `python tools/agent/check_architecture.py --format text`
- `python tools/agent/validate_repo.py --scope all`

Baseline at start of pass:
- architecture: passed
- backend ruff: passed
- backend pytest: passed
- frontend check: passed
- frontend build: passed
- tooling pytest: passed

## Risks And Follow-up

- Production-like env validation intentionally blocks localhost-only origins and placeholder JWT secrets; real deployments must provide explicit values.
- Backend remains on `--workers 1` until concurrency/state is externalized.
- This Windows environment does not have `make` installed, so the new `Makefile` was added and validated indirectly via the equivalent underlying commands rather than via `make ...` execution.

## Final Validation Evidence

- `python tools/agent/check_architecture.py --format text`
- `python tools/agent/validate_repo.py --scope all`

Final validation results:
- architecture: passed
- backend ruff: passed
- backend pytest: 206 passed
- frontend check: passed
- frontend build: passed
- tooling pytest: 8 passed

## Manual Docker Verification

- `docker compose down -v`
- `docker compose up --build -d`
- `http://localhost:8000/health` returned `200`
- `http://localhost:3000` returned `200`
- backend startup ran Alembic successfully against a clean volume
- `docker compose exec db psql -U textbook -d textbook_agent -c "select tablename from pg_tables where schemaname='public' order by tablename;"` showed:
  - `alembic_version`
  - `generations`
  - `lesson_shares`
  - `llm_calls`
  - `student_profiles`
  - `users`
- `docker compose exec backend sh -lc "/app/backend/.venv/bin/python -m alembic upgrade head"` completed as a no-op
- `docker compose restart backend` returned the backend to `healthy`
- final `docker compose ps` state: db healthy, backend healthy, frontend healthy
