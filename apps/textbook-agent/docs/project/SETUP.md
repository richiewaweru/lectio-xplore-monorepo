# Setup

## Install

| Surface | Directory | Command |
| --- | --- | --- |
| Backend (Python) | `backend/` | `uv sync --all-extras` |
| Frontend (SvelteKit) | `frontend/` | `npm ci` |

The frontend consumes the published npm `lectio` package pinned in `frontend/package.json`.

## Docker Stack

Use the repository-root compose file for the full stack:

```bash
cp .env.example .env
docker compose up --build
```

For the Docker stack:
- frontend is served at `http://localhost:3000`
- backend is served at `http://localhost:8000`
- backend startup runs `alembic upgrade head` before serving traffic
- backend-to-frontend PDF rendering should use `PDF_RENDER_BASE_URL=http://frontend`

For database-only Docker development, keep the app processes native and run:

```bash
docker compose --profile dev up db-dev
```

## Config Ownership

Use a different env file for each run surface:

| Surface | Env file | Notes |
| --- | --- | --- |
| Docker/Compose | repo-root `.env` | Only for `docker compose` from the repo root |
| Native backend | `backend/.env` | Canonical backend-local runtime config |
| Native frontend | `frontend/.env` | Canonical frontend-local browser config |

Key ownership rules:
- `GOOGLE_CLIENT_ID` belongs to the backend and Docker surfaces.
- `VITE_GOOGLE_CLIENT_ID` belongs only to the native frontend surface.
- Docker maps repo-root `GOOGLE_CLIENT_ID` into the frontend build as `VITE_GOOGLE_CLIENT_ID`.
- `PUBLIC_API_URL` is the canonical frontend API base; `VITE_API_TARGET` is optional and dev-only.
- `PIPELINE_*`, `PLANNING_*`, provider API keys, and backend runtime knobs belong in `backend/.env`.

## Railway Backend Deployment

- Railway should deploy from the repo root using [railway.toml](/C:/Projects/Textbook%20agent/railway.toml).
- The backend Docker image is built from `backend/Dockerfile` and uses Railway's injected `PORT`.
- Set `APP_ENV=production`, `JSON_LOGS=true`, `LOG_LEVEL=INFO`, and a `DATABASE_URL` built from Railway Postgres plugin variables using the `postgresql+asyncpg://` scheme.
- `FRONTEND_ORIGIN` and `LESSON_BUILDER_PUBLIC_URL` must be real public frontend URLs, never localhost values.
- If PDF export is enabled in production, `PDF_RENDER_BASE_URL` must also be a real public frontend URL.
- After each deploy, run `python scripts/smoke_test.py https://your-app.up.railway.app`.

### Xplore production variables

Xplore does not introduce a new runtime secret. `LECTIO_TOKEN` is a GitHub repository
secret used only by the Lectio release workflow; do not set it on the Textbook backend
or frontend.

Set these backend service variables for the provider configuration used by the
validated Xplore walkthrough:

| Variable | Production value or source |
| --- | --- |
| `APP_ENV` | `production` |
| `DATABASE_URL` | Railway Postgres URL using `postgresql+asyncpg://` |
| `JWT_SECRET_KEY` | a generated production secret |
| `GOOGLE_CLIENT_ID` | Google OAuth web client ID |
| `DEEPSEEK_API_KEY` | deployment secret |
| `ANTHROPIC_API_KEY` | deployment secret; used by the configured visual-QC slot |
| `V3_FAST_PROVIDER` | `openai_compatible` |
| `V3_FAST_MODEL_NAME` | `deepseek-v4-flash` |
| `V3_FAST_BASE_URL` | `https://api.deepseek.com` |
| `V3_FAST_API_KEY_ENV` | `DEEPSEEK_API_KEY` |
| `V3_STANDARD_PROVIDER` | `openai_compatible` |
| `V3_STANDARD_MODEL_NAME` | `deepseek-v4-pro` |
| `V3_STANDARD_BASE_URL` | `https://api.deepseek.com` |
| `V3_STANDARD_API_KEY_ENV` | `DEEPSEEK_API_KEY` |
| `V3_PREMIUM_PROVIDER` | `openai_compatible` |
| `V3_PREMIUM_MODEL_NAME` | `deepseek-v4-pro` |
| `V3_PREMIUM_BASE_URL` | `https://api.deepseek.com` |
| `V3_PREMIUM_API_KEY_ENV` | `DEEPSEEK_API_KEY` |
| `V3_STAGE2_PARALLEL` | `true` |
| `LECTIO_CONTRACTS_DIR` | `/app/backend/contracts` |
| `RUN_MIGRATIONS_ON_STARTUP` | `true` |
| `FRONTEND_ORIGIN` | exact deployed frontend `https://` origin |
| `LESSON_BUILDER_PUBLIC_URL` | exact deployed frontend `https://` origin |
| `PDF_RENDER_BASE_URL` | exact deployed frontend `https://` origin |
| `JSON_LOGS` | `true` |
| `LOG_LEVEL` | `INFO` |

Keep the remaining `V3_*` timeout, retry, concurrency, visual-QC, and image-provider
values aligned with [backend/.env.example](../../backend/.env.example).
For generated images, also configure the selected provider key and the `GCS_*` storage
variables listed in that example.

Set these on the production frontend:

| Variable | Production value |
| --- | --- |
| `PUBLIC_API_URL` | deployed Railway backend URL |
| `PUBLIC_GOOGLE_CLIENT_ID` | the same Google OAuth web client ID |

Add the deployed frontend origin to the Google client's Authorized JavaScript origins.
The production server chooses its own port; the `5173` requirement applies only to the
local Google OAuth test origin.

## PDF Export

- Native backend development should use `PDF_RENDER_BASE_URL=http://localhost:5173`.
- Docker compose should use `PDF_RENDER_BASE_URL=http://frontend`.
- The backend container installs Chromium during image build so Playwright can render the print route.
- The print route is `/textbook/[id]?print=true` and is authenticated with a token query param generated by the backend export endpoint.
- `/health/deep` and `/health/ready` now report `playwright`, `pdf_temp_dir`, and `pdf_exports` so operators can quickly verify export readiness.

## Local Auth and Env Requirements

- The repo-root `.env` is for Docker/compose runtime values.
- `backend/.env` is for native backend development values.
- `frontend/.env` is for native frontend development values.
- Backend provider keys must be present in `backend/.env`.
- `backend/.env` must define `GOOGLE_CLIENT_ID`.
- `frontend/.env` must define `VITE_GOOGLE_CLIENT_ID`.
- For Docker-local sign-in, the repo-root `.env` must define `GOOGLE_CLIENT_ID`.
- The Google Cloud OAuth client must list both `http://localhost:5173` and `http://127.0.0.1:5173` under `Authorized JavaScript origins`.
- For Docker-local use, also add `http://localhost:3000` as an authorized JavaScript origin.
- For Railway production, add the final frontend origin to Google OAuth authorized JavaScript origins before enabling sign-in there.
- If the Google OAuth consent screen is still in Testing mode, the local sign-in email must also be added as a test user.

## Contract Sync

Sync Lectio contracts and generated Python types into the backend consumer directory:

```bash
cd "C:\Projects\Textbook agent"
uv run python tools/update_lectio_contracts.py
```

Run this sync again whenever the frontend Lectio package version changes.

## Project-Local Tools

Validation and architecture scripts live in `tools/agent/`:

```bash
python tools/agent/validate_repo.py --scope all          # Run all validation
python tools/agent/validate_repo.py --scope backend       # Backend only
python tools/agent/check_architecture.py --format text    # Check shell + pipeline boundaries
cd frontend && npm run test                               # Frontend helper tests
```

## Dev Servers

```bash
cd backend && uv run uvicorn app:app --reload
cd frontend && npm run dev -- --host=127.0.0.1 --port=5173
```

For Google sign-in demos, prefer opening `http://localhost:5173`.

## Snapshot References

- `docs/v0.1.0/SETUP.md`
