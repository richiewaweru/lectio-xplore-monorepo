# Phase P6 Railway Backend Deployment

**Date:** 2026-04-02  
**Classification:** major  
**Subsystems:** Railway deployment config, backend container runtime, production operator workflow

## Progress

- [x] Confirmed the current repo still needed Railway-specific Docker/runtime alignment
- [x] Established a validation baseline before changes
- [x] Expanded `railway.toml` into a complete backend deployment contract
- [x] Updated the backend container to honor Railway's dynamic `PORT`
- [x] Added a backend smoke-test helper and `Makefile` smoke targets
- [x] Updated env/docs for Railway backend deployment and frontend follow-on wiring
- [x] Ran final validation
- [x] Recorded local Railway-compatibility smoke evidence

## Summary

This phase established the Railway deployment contract and backend runtime shape. The current repo already contains the core production primitives: repo-root `railway.toml`, dynamic `PORT` handling, `/health/ready` readiness checks, DB-backed document/report persistence, and strict `APP_ENV=production` validation through `Settings`. Backend deployment should stay strict: do not roll out to Railway until the real frontend origin is known and set consistently across `FRONTEND_ORIGIN`, `LESSON_BUILDER_PUBLIC_URL`, and `PDF_RENDER_BASE_URL`.

## Railway Backend Variables

Set these on the Railway backend service:

| Variable | Required | Notes |
| --- | --- | --- |
| `APP_ENV=production` | yes | canonical production environment flag |
| `DATABASE_URL` | yes | use `postgresql+asyncpg://...`, not Railway's default `postgres://` |
| `JWT_SECRET_KEY` | yes | generate a real secret; placeholder values are rejected |
| `GOOGLE_CLIENT_ID` | yes | required by backend auth validation in production |
| `ANTHROPIC_API_KEY` | yes | required for generation |
| `FRONTEND_ORIGIN` | yes | exact future frontend origin, including `https://` |
| `LESSON_BUILDER_PUBLIC_URL` | yes | exact future public frontend URL |
| `PDF_RENDER_BASE_URL` | yes | exact future frontend URL while PDF export is enabled |
| `JSON_LOGS=true` | yes | recommended for Railway log explorer |
| `LOG_LEVEL=INFO` | yes | raise only for active debugging |
| `LECTIO_CONTRACTS_DIR=/app/backend/contracts` | recommended | matches the image layout and baked-in contracts copy |
| `RUN_MIGRATIONS_ON_STARTUP=true` | recommended | pin the startup migration behavior explicitly in Railway |
| `GENERATION_MAX_CONCURRENT_PER_USER` and `PIPELINE_*` runtime vars | recommended | keep explicit production policy values rather than relying on defaults |

For Railway Postgres, create `DATABASE_URL` from plugin variables:

```text
postgresql+asyncpg://${PGUSER}:${PGPASSWORD}@${PGHOST}:${PGPORT}/${PGDATABASE}
```

## Frontend Follow-on

- Backend-first deployment is not the intended production path. The backend currently validates against localhost-like frontend values in production, so wait until the real frontend domain exists.
- When the frontend domain is known, set Railway to:
  - `FRONTEND_ORIGIN=https://your-frontend.example.com`
  - `LESSON_BUILDER_PUBLIC_URL=https://your-frontend.example.com`
  - `PDF_RENDER_BASE_URL=https://your-frontend.example.com`
- Then point the frontend at the Railway backend with:
  - `PUBLIC_API_URL=https://your-backend.up.railway.app`
  - `VITE_API_TARGET=https://your-backend.up.railway.app`
- Add the same frontend origin to Google OAuth authorized JavaScript origins.

## Deployment Checklist

1. Create a Railway project from the GitHub repo.
2. Add a PostgreSQL plugin.
3. Build `DATABASE_URL` with Railway Postgres references using the `postgresql+asyncpg://` scheme.
4. Set the backend variables listed above, including the real frontend-origin values.
5. Confirm `railway.toml` is the deploy source of truth and still uses `/health/ready`.
6. Run a local migration smoke against PostgreSQL before the first Railway deploy:
   - `cd backend`
   - `DATABASE_URL=postgresql+asyncpg://... alembic upgrade head`
   - `alembic current`
7. Deploy from `main`.
8. Run:
   - `python scripts/smoke_test.py https://your-backend.up.railway.app`
9. Verify Google auth and one end-to-end generation manually after the frontend is connected.

## Common Failure Modes

- Build succeeds but app never becomes healthy:
  - verify Railway is using the repo-root [railway.toml](/C:/Projects/Textbook%20agent/railway.toml)
  - verify `PORT` is not hardcoded elsewhere
  - verify `/health/ready` remains the Railway readiness target
- App crashes on startup with config validation:
  - replace placeholder `JWT_SECRET_KEY`
  - ensure `APP_ENV=production`
  - ensure `FRONTEND_ORIGIN`, `LESSON_BUILDER_PUBLIC_URL`, and `PDF_RENDER_BASE_URL` are not localhost values
- DB connection errors:
  - ensure `DATABASE_URL` uses `postgresql+asyncpg://`
  - ensure the backend image still includes the declared `asyncpg` dependency from [backend/pyproject.toml](/C:/Projects/Textbook%20agent/backend/pyproject.toml)
- CORS/login failures after frontend hookup:
  - ensure the frontend origin exactly matches Railway backend `FRONTEND_ORIGIN`
  - update Google OAuth origins to the final frontend URL

## Persistence Notes

- Documents are persisted in `generations.document_json`.
- Reports are persisted in `generations.report_json`.
- The container filesystem remains an ephemeral legacy/debug surface only.
- This means Railway's ephemeral disk is acceptable for v1 core flows so long as user-facing reads continue to come from PostgreSQL-backed APIs.

## Current Validation Notes

- `railway.json` is not required; the repo uses [railway.toml](/C:/Projects/Textbook%20agent/railway.toml) as the deployment contract.
- `app_env` and strict production validation already live in [backend/src/core/config.py](/C:/Projects/Textbook%20agent/backend/src/core/config.py); no separate startup-only JWT guard is needed.

## Validation Evidence

Baseline and final repo validation:

- `python tools/agent/check_architecture.py --format text`
- `python tools/agent/validate_repo.py --scope all`
- Focused smoke helper coverage: `cd backend && uv run pytest tests/test_smoke_test_script.py tests/core/health/test_health_routes.py tests/core/test_app.py tests/core/test_logging.py -q`

Observed results:

- Architecture check passed
- Full repo validation passed
- Backend pytest passed as part of repo validation: `229 passed`
- Focused smoke-helper validation passed: `21 passed`

## Local Railway-Compatibility Smoke Evidence

Existing local Docker stack:

- `GET http://localhost:8000/health` returned `200`
- `GET http://localhost:8000/health/ready` returned `status = "ok"`
- `python scripts/smoke_test.py http://localhost:8000` passed

Railway-style dynamic port check:

- Rebuilt the backend image from the updated [backend/Dockerfile](/C:/Projects/Textbook%20agent/backend/Dockerfile)
- Started the backend image with:
  - `PORT=8010`
  - `APP_ENV=production`
  - secure `JWT_SECRET_KEY`
  - production-style `FRONTEND_ORIGIN` and `LESSON_BUILDER_PUBLIC_URL`
  - `DATABASE_URL=postgresql+asyncpg://textbook:textbook@db:5432/textbook_agent`
- `GET http://localhost:8010/health/ready` returned `200` with `status = "ok"`
- `python scripts/smoke_test.py http://localhost:8010` passed

## Notes

- The first non-default-port probe surfaced a stale cached backend image that still used the pre-phase hardcoded `--port 8000` command. Rebuilding the backend image picked up the new dynamic `PORT` contract and resolved the issue.
- Railway deployment itself was not executed from this workstation; the repo-side config, runtime proof, and operator procedure are ready for dashboard deployment.
