## Feature: Textbook Generator PDF Export Slice 1

**Classification**: major
**Subsystems**: backend/frontend/both

### Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Implemented the change
- [x] Wrote tests for new behavior
- [x] Ran validation (backend: ruff + pytest, frontend: check + build)
- [x] Self-reviewed against agents/standards/review.md
- [ ] Wrote commit message(s) following agents/standards/communication.md
- [ ] Updated PR description with summary, validation evidence, risks
- [x] Noted any follow-up work or open questions

### Validation Evidence
- Synced print-capable Lectio vendor build into `frontend/vendor/lectio`
- Added backend PDF export route, service, components, Playwright renderer, and cleanup
- Added frontend print-mode handling and completed-generation export action
- `uv run python -m pytest tests/generation/test_pdf_export_components.py tests/routes/test_api.py -q`
- `npm test -- src/lib/api/client.test.ts`
- `npx vitest run --reporter verbose --config vite.config.ts -- 'src/routes/textbook/[id]/page.test.ts'`
- `npm run check`

### Risks and Follow-up
- Slice 2 still needs QR wrappers, richer export telemetry, health/deep Playwright checks, and stronger export operations tooling.
- Production deployments must set `PDF_RENDER_BASE_URL` to the real frontend origin whenever `PDF_EXPORT_ENABLED=true`.
- End-to-end manual PDF rendering against a live frontend/backend pair still needs to be recorded after the full repo validation pass.
