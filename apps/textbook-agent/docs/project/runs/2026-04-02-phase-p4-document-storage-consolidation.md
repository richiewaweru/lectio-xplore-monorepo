# Phase P4 Document Storage Consolidation

**Date:** 2026-04-02  
**Classification:** major  
**Subsystems:** generation persistence, document repository, Docker runtime, telemetry document loading

## Progress

- [x] Confirmed the repo already stores documents in Postgres `document_json`
- [x] Established a validation baseline before changes
- [x] Removed filesystem fallback behavior from the SQL document repository
- [x] Updated route and telemetry document loading for DB-only references
- [x] Removed the backend document output volume from Docker compose
- [x] Updated tests to reflect generation-id document references and deprecated `document_path`
- [x] Ran final validation
- [x] Recorded runtime/document persistence smoke evidence

## Summary

This phase completes the transition away from filesystem-backed document storage. The backend already used `generations.document_json` as the canonical `PipelineDocument` store before this pass; Phase 4 now removes the SQL repository's disk fallback, writes new document saves with generation-id references and `document_path=None`, updates the document route and telemetry loading logic to work without filesystem assumptions, and removes the backend outputs volume from Docker Compose.

## Notes

- `document_json` remains the canonical document column; this phase does not add or rename to `document_content`.
- `document_path` remains on the model as a deprecated compatibility field and may be null for newly written generations.
- Report storage remains unchanged in this phase.

## Validation Evidence

- Baseline before edits:
  - `python tools/agent/check_architecture.py --format text`
  - `python tools/agent/validate_repo.py --scope all`
- Focused repository validation after repository/route changes:
  - `cd backend && uv run pytest tests/repositories/test_document_repository.py tests/routes/test_generation_document_report.py tests/routes/test_api.py -q`
  - Result: `34 passed`
- Follow-up repository validation after legacy migration-script cleanup:
  - `cd backend && uv run pytest tests/repositories/test_document_repository.py tests/repositories/test_generation_repo.py -q`
  - Result: `13 passed`
- Final repo validation:
  - `python tools/agent/check_architecture.py --format text`
  - `python tools/agent/validate_repo.py --scope all`
  - Result: backend ruff passed, backend pytest `223 passed`, frontend check passed, frontend build passed, tooling pytest `8 passed`

## Runtime Smoke Evidence

- Rendered Compose config no longer includes a backend `outputs` volume mount.
- `docker compose up --build -d db backend` started successfully after providing a secure `JWT_SECRET_KEY` override for the backend container.
- `docker compose ps` reached healthy state for `db`, `backend`, and `frontend`.
- `http://localhost:8000/health` returned `200`.
- Postgres document persistence check:
  - Query: `SELECT id, document_path IS NULL AS path_is_null, document_json->>'template_id' AS template_id, document_json->>'status' AS doc_status FROM generations WHERE id = 'p4-gen';`
  - Result: `id=p4-gen`, `path_is_null=true`, `template_id=guided-concept-path`, `doc_status=completed`

## Risks And Follow-up

- No Alembic migration was required because `generations.document_json` already existed before this phase.
- Legacy locator strings such as `generation:<id>:document` remain readable for backward compatibility, but runtime document reads no longer fall back to disk.
- The offline SQLite-to-Postgres migration helper still supports importing legacy document files, but it now does so directly without depending on the removed runtime file document repository.
- The repository-root `.env.example` still uses a placeholder `JWT_SECRET_KEY`; Docker runtime boot now requires operators to replace it with a secure value because of the earlier Phase P2 hardening.
