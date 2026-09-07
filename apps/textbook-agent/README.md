# Textbook Agent (Xplore)

FastAPI + SvelteKit app for Unit-based Print and Learn lesson creation.

## Layout

- `backend/src/` — `application/`, `curriculum/`, `print/`, `learn/`, `infra/`, `app.py`
- `frontend/` — SvelteKit UI (`/units`, `/studio`, `/builder`, `/learn`, …)
- Consumes workspace packages `@lectio/page` and `@lectio/learn`

## Run

```bash
# backend
cd backend && uv run uvicorn app:app --reload --app-dir src

# frontend
cd frontend && pnpm dev
```

## Architecture

See repo [docs/architecture/CURRENT_SYSTEM.md](../../docs/architecture/CURRENT_SYSTEM.md).

Canonical lesson creation is the **Unit** path (not standalone studio generation).
