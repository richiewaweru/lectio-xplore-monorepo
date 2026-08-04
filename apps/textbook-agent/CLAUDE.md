# Textbook Generation Agent - Project Guide

## Project Structure
- `backend/` - FastAPI + Python backend
- `frontend/` - SvelteKit + TypeScript frontend
- `docs/project/` - live project docs
- `docs/v0.1.0/` - archival snapshot docs

## Backend
- Package manager: `uv`
- Shared core source root: `backend/src/core/`
- Generation app source root: `backend/src/generation/`
- Planning source root: `backend/src/planning/`
- Pipeline source root: `backend/src/pipeline/`
- Entry point: `uvicorn app:app`
- Validation: `python tools/agent/validate_repo.py --scope all`
- Architecture guard: `python tools/agent/check_architecture.py --format text`

## Key Runtime Contracts
- The core owns auth primitives, shared database access, and generic infrastructure.
- The generation app owns auth-aware HTTP, persistence, generation orchestration, and SSE transport.
- The planning app owns Teacher Studio flows and feeds generation.
- The pipeline owns prompts, contract loading, providers, graph orchestration, QC, and Lectio document assembly.
- The canonical saved artifact is a JSON `PipelineDocument`.
- `/studio` is the canonical teacher lesson-creation route.
- `GET /api/v1/contracts`, `POST /api/v1/brief/stream`, and `POST /api/v1/brief/commit` are the live planning endpoints.
- Public textbook viewing is generation-centric: `/textbook/[id]` maps to a generation ID, hydrates from `/document`, and streams updates from `/events`.
- The pipeline must never import `generation` or `planning`.

## Frontend
- Package manager: `npm`
- Dev: `cd frontend && npm run dev`
- Auth: Google OAuth via Google Identity Services
- Viewer: native Lectio rendering of streamed section content

## Live Docs
- `docs/project/agent-context.md`
- `docs/project/ARCHITECTURE.md`
- `docs/project/SETUP.md`
- `docs/project/DEVELOPMENT_WORKFLOW.md`
- `docs/project/SCHEMAS.md`

## Contract Sync
- Sync contracts and generated Python types from the installed frontend `lectio` package via `uv run python tools/update_lectio_contracts.py`.
- The Textbook repo should treat the synced Lectio JSON contracts and generated adapter as the planning/template source of truth.
