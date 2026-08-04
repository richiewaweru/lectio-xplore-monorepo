## Feature: phase 2 backtracking alignment

**Classification**: major
**Subsystems**: backend, frontend, docs, tooling

### Progress
- [x] Understood requirements and identified scope
- [x] Read relevant source code and project rules
- [x] Implemented the change
- [x] Wrote tests for new behavior
- [x] Ran validation (repo, backend, frontend, tooling)
- [x] Self-reviewed against agents/standards/review.md
- [ ] Wrote commit message(s) following agents/standards/communication.md
- [ ] Updated PR description with summary, validation evidence, risks
- [x] Noted any follow-up work or open questions

### Alignment Checklist
- [x] Viewer route normalized to generation ID
- [x] Generation-owned textbook HTML endpoint added
- [x] Raw path-based HTML fetch removed from public frontend flow
- [x] Output path handling sanitized and rooted
- [x] Standalone HTML restored to self-contained rendering
- [x] AI review prompt wiring fixed
- [x] Live docs updated to current Phase 2 behavior
- [x] Missing live project docs/stage packs added
- [x] Example env files scrubbed to placeholders
- [x] Regression tests added for contract and tooling fixes

### Validation Evidence
- Initial repo validation: `python tools/agent/validate_repo.py --scope all` -> pass
- Initial architecture guard: `python tools/agent/check_architecture.py --format text` -> no violations
- Backend targeted regression suites: `cd backend && uv run python -m pytest tests/application/test_orchestrator.py tests/infrastructure/test_renderer.py tests/interface/test_api.py tests/integration/test_mock_pipeline_render.py` -> `23 passed`
- Backend provider/schema suites: `cd backend && uv run python -m pytest tests/infrastructure/test_providers.py tests/infrastructure/test_json_utils.py` -> `6 passed`
- Frontend helper tests: `cd frontend && npm run test` -> `4 passed`
- Final backend suite: `cd backend && uv run python -m pytest` -> `107 passed, 6 deselected`
- Final repo validation: `python tools/agent/validate_repo.py --scope all` -> pass
- Final architecture guard: `python tools/agent/check_architecture.py --format text` -> no violations

### Risks and Follow-up
- `docs/v0.1.0/` remains archival and should only receive archival notes, not content rewrites.
- Real-provider integration smoke tests were not re-run in this pass; validation covered the mocked/default suites, frontend checks, tooling tests, and architecture guard.
- Prompt reference docs under `docs/` remain descriptive snapshots. Runtime prompt truth lives in `backend/src/textbook_agent/domain/prompts/`.
