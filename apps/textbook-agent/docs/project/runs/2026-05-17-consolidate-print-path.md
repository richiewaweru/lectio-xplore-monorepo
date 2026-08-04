## Refactor: consolidate studio print path

**Classification**: major
**Scope**: frontend studio print route, V3 print-only helpers, backend V3 PDF export path
**Behavior changes**: remove `?renderer=safe` and `?renderer=canvas-test`; keep Lectio-only print rendering and `?debugPrint=true`

### Progress
- [x] Documented scope and interfaces affected
- [x] Mapped current dependencies
- [x] Established baseline (all tests passing before changes)
- [x] Implemented structural change
- [x] Verified all existing tests still pass (behavior preserved)
- [x] Added tests for any new interfaces
- [x] Ran full validation (backend + frontend)
- [x] Updated documentation if architecture rules changed
- [x] Self-reviewed against agents/standards/architecture.md

### Validation Evidence
- Baseline frontend:
  - `cd frontend && npm run check`
  - `cd frontend && npx vitest run src/lib/studio/v3-print-fields.test.ts src/lib/studio/v3-print-canvas.test.ts`
  - Result: `svelte-check found 0 errors and 0 warnings`; focused Vitest `15 passed`
- Final frontend:
  - `cd frontend && npm run check`
  - `cd frontend && npm run build`
  - `cd frontend && npm run test`
  - `cd frontend && npx vitest run src/lib/studio/v3-print-canvas.test.ts`
  - Result: check passed; build passed; full Vitest `53 passed / 163 passed`; focused Vitest `3 passed`
- Final backend:
  - `uv run --directory backend pytest ../backend/tests/generation/test_playwright_rendering.py ../backend/tests/generation/test_pdf_export_service.py -q`
  - `python tools/agent/check_architecture.py --format text`
  - Result: targeted pytest `3 passed`; architecture check passed
- Manual verification:
  - Not run in this session. No local authenticated print route was exercised in a browser.

### Risks and Follow-up
- Manual browser verification of `/studio/print/[id]` and one live V3 PDF export is still worth doing in an authenticated environment, even though the route and backend path are covered by build and targeted tests.
