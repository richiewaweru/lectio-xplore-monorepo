## Feature: presentation public switch

**Classification**: major
**Subsystems**: backend/frontend

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

### Launch Contract
- `POST /api/v1/generate` accepts optional `template_id`; unknown IDs return `400`
- `GET /api/v1/templates` returns the public launch catalog and default `T01`
- generation status/history/detail expose `requested_template_id`, `resolved_template_id`, and `resolved_template_name`
- launch templates: `T01`, `T02`, `T03`, `T05`, `T08`, `T10`

### Manual Review Matrix
- [ ] Algebra: `T01`, `T02`, `T03`, `T10` screen review
- [ ] Algebra: `T01`, `T02`, `T03`, `T10` print preview
- [ ] Calculus: `T01`, `T08`, `T10` screen review
- [ ] Calculus: `T01`, `T08`, `T10` print preview
- [ ] Chemistry: `T01`, `T02`, `T05`, `T10` screen review
- [ ] Chemistry: `T01`, `T02`, `T05`, `T10` print preview
- [ ] Fallback smoke case: requested template rerenders to fallback and UI shows the resolved template

### Validation Evidence
- `cd backend && uv run pytest tests/infrastructure/test_generation_repo.py tests/infrastructure/test_presentation_engine.py tests/application/test_orchestrator.py tests/interface/test_api.py -q` -> `41 passed`
- `cd frontend && npm test` -> `12 files passed, 38 tests passed`
- `cd frontend && npm run check` -> `0 errors, 0 warnings`
- `cd frontend && npm run build` -> production build passed
- `python tools/agent/check_architecture.py --format text` -> `No architecture violations found.`
- `python tools/agent/validate_repo.py --scope all` -> backend ruff pass, backend pytest `133 passed`, frontend check pass, tooling pytest `7 passed`

### Risks and Follow-up
- Manual artifact review is still required before treating the gallery switch as fully signed off.
- Tier remains metadata-only; no entitlement enforcement exists in this cycle.
- `T04`, `T06`, `T07`, and `T09` remain intentionally deferred.
