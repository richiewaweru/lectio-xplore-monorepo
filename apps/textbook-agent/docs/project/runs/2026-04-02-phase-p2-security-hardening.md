# Phase P2 Security Hardening

**Date:** 2026-04-02  
**Classification:** major  
**Subsystems:** backend runtime, CORS/startup policy, generation failure handling, test bootstrapping

## Progress

- [x] Understood requirements and mapped current repo behavior
- [x] Confirmed this phase builds on the already-landed production-stabilization pass
- [x] Tightened startup JWT secret validation
- [x] Made CORS environment-aware
- [x] Preserved existing service-layer concurrency enforcement
- [x] Extended timeout failure-path coverage
- [x] Refined stale-generation cleanup thresholding
- [x] Ran full validation
- [x] Recorded final validation and startup smoke evidence

## Summary

This phase hardens the backend before real-user exposure by enforcing secure JWT secrets at startup, rejecting wildcard/empty CORS in production-like environments, keeping generation concurrency limits in the existing service-layer gate, extending timeout error coverage, and ensuring restart cleanup only fails genuinely stale generations.

## Notes

- This pass assumes the current production-stabilization work is the base state and does not roll it back.
- `APP_ENV`/`ENVIRONMENT` remains the canonical environment flag.
- The existing database-backed generation concurrency limit stays in place; no extra route-local semaphore gate was added.

## Validation Evidence

- `uv run pytest` in `backend/` passed: `213 passed`
- `python tools/agent/check_architecture.py --format text` passed: no architecture violations found
- `python tools/agent/validate_repo.py --scope all` passed:
  - backend Ruff
  - backend pytest
  - frontend `npm run check`
  - frontend `npm run build`
  - tooling pytest

## Startup Smoke Checks

- Placeholder JWT secret rejected at settings bootstrap:
  - `JWT_SECRET_KEY='change-me' uv run python -c "from src.core.config import Settings; Settings()"`
  - result: startup failed with `JWT_SECRET_KEY is not set to a secure value`
- Production wildcard CORS rejected at app bootstrap:
  - `APP_ENV=production FRONTEND_ORIGIN='*' ... uv run python -c "from src.app import create_app; create_app()"`
  - result: startup failed with `FRONTEND_ORIGIN must be set to a specific domain in production`
- Empty production CORS rejected by the startup helper:
  - `uv run python -c "from src.app import _allowed_frontend_origins; _allowed_frontend_origins('', env='production')"`
  - result: raised the same production CORS error as wildcard origin
- Valid production-like boot succeeded:
  - `APP_ENV=production FRONTEND_ORIGIN='https://app.example.com' LESSON_BUILDER_PUBLIC_URL='https://app.example.com' DATABASE_URL='postgresql+asyncpg://...' ... uv run python -c "from src.app import create_app; create_app(); print('BOOT_OK')"`
  - result: `BOOT_OK`

## Implementation Notes

- Production-like startup smoke tests in this workspace needed `postgresql+asyncpg://...` because the local environment does not have `psycopg` installed.
- No schema or Alembic changes were required for this phase.
