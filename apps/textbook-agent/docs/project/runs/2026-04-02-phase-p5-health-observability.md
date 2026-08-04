# Phase P5 Health And Observability

**Date:** 2026-04-02  
**Classification:** major  
**Subsystems:** backend health endpoints, deployment health checks, operator diagnostics

## Progress

- [x] Confirmed the current repo still used the legacy `/health` + `/health/ready` contract
- [x] Established a validation baseline before changes
- [x] Replaced the old health router with a canonical health module
- [x] Added `/health/deep` and aligned `/health/ready` with critical-dependency semantics
- [x] Added generation summary and event-bus readiness diagnostics
- [x] Added repo-managed Railway health check configuration
- [x] Ran final validation
- [x] Recorded runtime and failure-path smoke evidence

## Summary

This phase upgrades the app from a minimal health surface to an operational one. `/health` remains a fast liveness probe, while `/health/deep` and `/health/ready` now report Postgres status, event-bus status, generation backlog/failure summary, and instance uptime metadata. Critical dependency failure now returns `503` on readiness, and Railway is configured to poll `/health/ready`.

## Notes

- `/health/ready` and `/health/deep` share the same payload shape.
- Postgres is treated as critical and drives `unavailable` + HTTP `503`.
- The in-process event bus is non-critical and drives `degraded` + HTTP `200`.
- External uptime monitors are documented as an operator step rather than provisioned from the repo.

## Validation Evidence

- Baseline before edits:
  - `python tools/agent/check_architecture.py --format text`
  - `python tools/agent/validate_repo.py --scope all`
- Focused backend verification during implementation:
  - `cd backend && uv run pytest tests/core/health/test_health_routes.py tests/routes/test_runtime_diagnostics.py tests/routes/test_api.py -q`
  - Result: `37 passed`
  - `cd backend && uv run pytest tests/core/test_app.py tests/core/test_logging.py tests/core/health/test_health_routes.py -q`
  - Result: `19 passed`
- Final validation:
  - `python tools/agent/check_architecture.py --format text`
  - `python tools/agent/validate_repo.py --scope all`
  - Result: backend ruff passed, backend pytest `227 passed`, frontend check passed, frontend build passed, tooling pytest `8 passed`

## Runtime Smoke Evidence

- Added `railway.toml` with:
  - `healthcheckPath = "/health/ready"`
  - `healthcheckTimeout = 10`
  - `restartPolicyType = "on-failure"`
  - `restartPolicyMaxRetries = 3`
- Rebuilt the backend container with a secure `JWT_SECRET_KEY` env override so the runtime matched the committed Phase 5 code.
- Healthy runtime checks:
  - `GET /health` returned `200` with `status=ok`, `timestamp`, `instance_id`, `started_at`, and `pipeline_architecture`
  - `GET /health/deep` returned `200` with:
    - `status=ok`
    - dependencies for `postgres` and `event_bus`
    - generation summary keys `running`, `pending`, `failed_last_hour`, `completed_last_hour`
  - `GET /health/ready` returned `200` after DB recovery
  - `docker compose ps` ended with healthy `backend`, `db`, and `frontend`
- Failure-path drill:
  - `docker compose stop db`
  - `GET /health/ready` returned `503 Service Unavailable`
  - Response body included:
    - `status=unavailable`
    - dependency `postgres` with `status=unreachable`
    - dependency `event_bus` with `status=ok`
  - `docker compose up -d db` restored the stack, and `/health/ready` returned `200` again

## Operator Notes

- External uptime monitoring should target `/health/ready` and alert on non-200 responses.
- The JSON body is suitable for tools that also validate response content, but the HTTP status code is now the primary readiness signal for Railway and other load balancers.
