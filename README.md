# Textbook Generation Agent

AI-powered core + generation + planning + pipeline system for generating personalized Lectio-native textbooks from learner context.

## Quick Start

Use the live project docs in [`docs/project/`](docs/project/README.md). The versioned `docs/v0.1.0/` set is archival.

```bash
# Full stack with Docker
cp .env.example .env
docker compose up --build

# Native backend
cd backend
uv sync --all-extras
cp .env.example .env
uv run uvicorn app:app --reload

# Native frontend
cd frontend
npm ci
cp .env.example .env
npm run dev
```

## Config Ownership

Use one env file per surface:

| Surface | Env file | Purpose |
| --- | --- | --- |
| Docker/Compose | repo-root `.env` | Full stack local Docker runtime only |
| Native backend | `backend/.env` | FastAPI backend run directly from `backend/` |
| Native frontend | `frontend/.env` | SvelteKit frontend run directly from `frontend/` |

### Common variables

| Variable | Owner file | Used by |
| --- | --- | --- |
| `GOOGLE_CLIENT_ID` | repo-root `.env`, `backend/.env` | Docker backend and native backend |
| `VITE_GOOGLE_CLIENT_ID` | `frontend/.env` | Native frontend browser runtime |
| `PUBLIC_API_URL` | repo-root `.env`, `frontend/.env` | Docker frontend build and native frontend |
| `JWT_SECRET_KEY` | repo-root `.env`, `backend/.env` | Docker backend and native backend |
| `DATABASE_URL` | `backend/.env` | Native backend only |
| `POSTGRES_*` | repo-root `.env` | Docker Postgres and backend compose wiring |
| `PIPELINE_*`, `PLANNING_*` | `backend/.env` | Backend-only routing/runtime knobs |

For Docker, the repo-root `GOOGLE_CLIENT_ID` is mapped into both the backend runtime and the frontend build as `VITE_GOOGLE_CLIENT_ID`.

Optional contract refresh from the installed Lectio package:

```bash
cd "C:\Projects\Textbook agent"
uv run python tools/update_lectio_contracts.py
```

For Docker runs, open `http://localhost:3000`.
For native frontend runs, open `http://localhost:5173`.
For Railway production, deploy the backend from the repo root with [railway.toml](/C:/Projects/Textbook%20agent/railway.toml). Keep the backend deploy strict: set a real frontend domain first, then configure `FRONTEND_ORIGIN`, `LESSON_BUILDER_PUBLIC_URL`, and `PDF_RENDER_BASE_URL` to that exact `https://` origin before the Railway rollout. After the backend is healthy, point the frontend to the Railway backend URL using `PUBLIC_API_URL` and `VITE_API_TARGET`.
Frontend deployment remains a separate manual Vercel flow documented in the project runbooks. GitHub Actions is not the deployment source of truth right now.

## PDF Export

Slice 1 PDF export is generation-based and uses the existing `document_json` artifact. The backend renders the authenticated print view at `/textbook/[id]?print=true` with Playwright and returns a direct PDF download from `POST /api/v1/generations/{id}/export/pdf`.

The key runtime settings are:

- `PDF_EXPORT_ENABLED`
- `PDF_RENDER_BASE_URL`
- `PDF_EXPORT_TIMEOUT_MS`
- `PLAYWRIGHT_TIMEOUT_MS`
- `PDF_TEMP_DIR`
- `PDF_MAX_FILE_SIZE_MB`
- `PDF_MAX_PAGE_COUNT`

Use `PDF_RENDER_BASE_URL=http://localhost:5173` for native development and `PDF_RENDER_BASE_URL=http://frontend` for the Docker stack.

Slice 2 adds:

- teacher and student export presets in the textbook UI
- print-only QR wrappers for interactive or diagram-heavy sections
- in-process PDF export telemetry surfaced in deep health checks
- Playwright and PDF temp-dir dependency checks in `/health/deep` and `/health/ready`

## Runtime Policy Configuration

The generation runtime is now configured through env-backed settings instead of hard-coded policy constants. The main knobs are:

- `GENERATION_MAX_CONCURRENT_PER_USER`
- `PIPELINE_CONCURRENCY_<MODE>_<RESOURCE>_MAX`
- `PIPELINE_TIMEOUT_<NAME>_SECONDS`
- `PIPELINE_TIMEOUT_GENERATION_{BASE,PER_SECTION,CAP}_SECONDS`
- `PIPELINE_RERENDER_<MODE>_SECTION_MAX`
- `PIPELINE_RETRY_<NAME>_MAX_ATTEMPTS`

`backend/.env.example` is the authoritative native-backend reference.
For Docker, use the repo-root `.env.example` and copy the needed runtime values into the repo-root `.env`.

## Image Diagnostics

The backend now exposes image-pipeline readiness through:

- `GET /health/deep`
- `GET /health/ready`
- `POST /health/image/probe`

Look for dependency entries named `gemini_image` and `image_store` in the readiness payloads. Use `POST /health/image/probe` when you want an explicit go/no-go check that Gemini can generate an image right now and that the active image store still appears writable.

Railway logs now use stable `image_generator:` markers. The main signatures are:

- `reason=no_api_key`: Gemini image key is missing
- `reason=client_init_failed`: Gemini client could not initialise
- `reason=store_init_failed`: image store could not initialise
- `reason=store_failed`: upload/storage failed after image generation
- `GEMINI_SUCCESS` followed by `STORE_SUCCESS`: end-to-end image path worked

Railway image env vars:

- `GOOGLE_CLOUD_NANO_API_KEY`
- `GCS_BUCKET_NAME`
- `GCS_SERVICE_ACCOUNT_JSON`
- `GCS_IMAGE_BASE_URL`

## Local Run Requirements

- Provider API keys must be present in `backend/.env`.
- Runtime policy knobs live in `backend/.env`; for Docker runs, mirror only the Docker-needed values in the repo-root `.env`.
- Google OAuth must be configured for local development:
  - native frontend: `frontend/.env` needs `VITE_GOOGLE_CLIENT_ID`
  - native backend: `backend/.env` needs `GOOGLE_CLIENT_ID`
  - Docker stack: repo-root `.env` needs `GOOGLE_CLIENT_ID`
  - the Google Cloud OAuth client must allow `http://localhost:5173` and `http://127.0.0.1:5173` as authorized JavaScript origins
  - if the OAuth consent screen is still in Testing mode, your sign-in email must be added as a test user
- For Docker-local runs, the Google Cloud OAuth client must also allow `http://localhost:3000`
- Frontend consumes the published npm `lectio` package pinned in `frontend/package.json`.
- If Lectio contracts or generated types change, refresh backend copies with:

```bash
cd "C:\Projects\Textbook agent"
uv run python tools/update_lectio_contracts.py
```

## Current Architecture

- Shared infrastructure in `backend/src/core/`
- Generation app in `backend/src/generation/`
- Planning in `backend/src/planning/`
- Generation engine in `backend/src/pipeline/`
- FastAPI composition entrypoint in `backend/src/app.py`
- SvelteKit frontend in `frontend/` with native Lectio rendering
- JSON document persistence plus authenticated SSE streaming
- Slot-based model routing and a single generation path
- Alembic startup upgrade is the only supported schema bootstrap path for runtime containers

## Live Docs

- [`docs/project/README.md`](docs/project/README.md)
- [`docs/project/ARCHITECTURE.md`](docs/project/ARCHITECTURE.md)
- [`docs/project/SETUP.md`](docs/project/SETUP.md)
- [`docs/project/DEVELOPMENT_WORKFLOW.md`](docs/project/DEVELOPMENT_WORKFLOW.md)
- [`docs/project/SCHEMAS.md`](docs/project/SCHEMAS.md)
- [`docs/project/runs/`](docs/project/runs/)
- [`docs/project/runs/2026-04-02-phase-p6-railway-backend-deployment.md`](docs/project/runs/2026-04-02-phase-p6-railway-backend-deployment.md)
- [`docs/project/runs/2026-04-03-backend-railway-readiness-handoff.md`](docs/project/runs/2026-04-03-backend-railway-readiness-handoff.md)

## Validation

```bash
python tools/agent/validate_repo.py --scope all
python tools/agent/check_architecture.py --format text
```

For pull requests, the required merge gate is intentionally lean:

- `backend-quality`
- `frontend-quality`

Additional checks such as architecture validation, tooling tests, frontend `vitest`, and app smoke tests are still recommended for release prep or operator verification, but they are not required GitHub merge blockers.

<!-- No-op doc touch to retrigger deployment -->
