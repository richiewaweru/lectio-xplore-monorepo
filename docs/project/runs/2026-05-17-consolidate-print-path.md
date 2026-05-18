## Refactor: consolidate studio print path

**Classification**: major
**Scope**: frontend studio print route, V3 print-only helpers, backend V3 PDF export path
**Behavior changes**: remove `?renderer=safe` and `?renderer=canvas-test`; keep Lectio-only print rendering and `?debugPrint=true`

### Progress
- [x] Documented scope and interfaces affected
- [x] Mapped current dependencies
- [x] Established baseline (all tests passing before changes)
- [ ] Implemented structural change
- [ ] Verified all existing tests still pass (behavior preserved)
- [ ] Added tests for any new interfaces
- [ ] Ran full validation (backend + frontend)
- [ ] Updated documentation if architecture rules changed
- [ ] Self-reviewed against agents/standards/architecture.md

### Validation Evidence
- Baseline frontend:
  - `cd frontend && npm run check`
  - `cd frontend && npx vitest run src/lib/studio/v3-print-fields.test.ts src/lib/studio/v3-print-canvas.test.ts`
  - Result: `svelte-check found 0 errors and 0 warnings`; focused Vitest `15 passed`

### Risks and Follow-up
- Backend V3 export currently hardcodes `?renderer=safe`; this refactor must update that path or PDF export will break.
- `frontend/src/lib/studio/v3-print-canvas.test.ts` currently depends on `v3-print-fields.ts`; deleting the print-fields module requires test cleanup, not just file deletion.
