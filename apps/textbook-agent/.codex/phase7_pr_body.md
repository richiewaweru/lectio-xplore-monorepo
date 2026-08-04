## Summary
Implements Phase 7 from the unified builder guide by adding version-history-adjacent print/export capabilities for editable lessons.

### Backend
- Adds `GET /api/v1/builder/lessons/{id}/print-document?audience=teacher|student` with ownership checks.
- Adds `POST /api/v1/builder/lessons/{id}/export/pdf` with audience mode and ownership checks.
- Reuses existing Playwright PDF pipeline via builder render path (`/builder/print/{id}?audience=...`).
- Adds student audience answer stripping for answer-bearing builder components.

### Frontend
- Adds builder print route: `/builder/print/[id]` for Playwright capture/readiness.
- Adds toolbar print-preview toggle (applies print styling in-canvas).
- Adds toolbar teacher/student PDF export actions.
- Adds builder PDF download helper for new backend endpoint.

### Tests
- Expands backend builder route tests for:
  - student-mode answer stripping
  - ownership enforcement on print/export endpoints
  - export render-path wiring
- Adds frontend toolbar tests for preview toggle + teacher/student export actions.

## Validation
- `uv run pytest tests/routes/test_builder_lessons.py -q` (backend): passed (11 tests)
- `uv run ruff check src tests/routes/test_builder_lessons.py` (backend): passed
- `npm run test -- src/lib/builder/components/toolbar/DocumentToolbar.test.ts src/routes/builder/page.test.ts src/routes/dashboard/page.test.ts` (frontend): passed
- `npm run check` (frontend): passed
- `npm run build` (frontend): passed

## Risks / Follow-ups
- Student answer stripping currently targets known answer-bearing components and should be extended if new answer fields are introduced.
- Builder PDF metadata currently uses default school/teacher metadata for toolbar-triggered export.
